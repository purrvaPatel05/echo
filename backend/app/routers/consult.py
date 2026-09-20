"""Peer consult/ping. REST is the durable source of truth (a thread/message always persists
first); the WebSocket only relays live delivery on top of it via Redis pub/sub, so a message is
never lost just because the recipient wasn't connected or Redis was briefly unreachable -- they
still see it next time they list/open the thread.
"""

import asyncio
import contextlib
import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.auth import (
    CurrentUser,
    authenticate_websocket,
    current_user,
    require_same_physician,
)
from app.db.repository import Repository
from app.deps import get_redis, get_repo
from app.models.consult import (
    ConsultMessage,
    ConsultThread,
    SendMessageRequest,
    StartConsultRequest,
)
from app.services import referrals as svc

logger = logging.getLogger(__name__)
router = APIRouter(tags=["consult"])


def _channel(physician_id: str) -> str:
    return f"consult:{physician_id}"


async def _publish(redis_client, physician_id: str, message: ConsultMessage) -> None:
    try:
        await redis_client.publish(_channel(physician_id), message.model_dump_json())
    except Exception:
        # Already persisted -- the recipient sees it on their next GET /consults either way.
        logger.warning("Redis publish failed; recipient will see the message on next poll")


def _other_participant(thread: ConsultThread, sender_physician_id: str) -> str:
    if sender_physician_id == thread.initiator_physician_id:
        return thread.recipient_physician_id
    return thread.initiator_physician_id


async def _get_participant_thread(
    repo: Repository, thread_id: str, physician_id: str
) -> ConsultThread:
    thread = await repo.consult_thread(thread_id)
    if thread is None:
        raise HTTPException(404, "Consult thread not found")
    if physician_id not in (thread.initiator_physician_id, thread.recipient_physician_id):
        raise HTTPException(403, "Not a participant in this consult")
    return thread


@router.post("/consults", response_model=ConsultThread, status_code=201)
async def start_consult(
    body: StartConsultRequest,
    repo: Repository = Depends(get_repo),
    redis_client=Depends(get_redis),
    user: CurrentUser = Depends(current_user),
):
    require_same_physician(body.from_physician_id, user, "from_physician_id")
    if await repo.physician(user.physician_id) is None:
        raise HTTPException(403, "This account is linked to an unknown physician")
    if await repo.physician(body.to_physician_id) is None:
        raise HTTPException(404, "Recipient physician not found")
    if body.referral_id is not None:
        # Only a referral the user can see may be attached as context.
        await svc.get_or_404(repo, body.referral_id, user)

    thread = await repo.create_consult_thread(
        user.physician_id, body.to_physician_id, body.referral_id
    )
    message = await repo.create_consult_message(thread.id, user.physician_id, body.body)
    await _publish(redis_client, body.to_physician_id, message)
    thread.last_message = message
    return thread


@router.get("/consults", response_model=list[ConsultThread])
async def list_consults(
    physician_id: str | None = None,
    repo: Repository = Depends(get_repo),
    user: CurrentUser = Depends(current_user),
):
    """The signed-in physician's threads, each with its last message and unread count.
    `physician_id` is optional; if sent it must be the signed-in physician."""
    require_same_physician(physician_id, user, "physician_id")
    return await repo.threads_for(user.physician_id)


@router.get("/consults/{thread_id}/messages", response_model=list[ConsultMessage])
async def get_consult_messages(
    thread_id: str,
    reader_physician_id: str | None = None,
    repo: Repository = Depends(get_repo),
    user: CurrentUser = Depends(current_user),
):
    """Full history; marks the other participant's messages as read by the signed-in physician.
    `reader_physician_id` is optional; if sent it must be the signed-in physician."""
    require_same_physician(reader_physician_id, user, "reader_physician_id")
    await _get_participant_thread(repo, thread_id, user.physician_id)
    await repo.mark_consult_read(thread_id, user.physician_id)
    return await repo.consult_messages(thread_id)


@router.post("/consults/{thread_id}/messages", response_model=ConsultMessage, status_code=201)
async def send_consult_message(
    thread_id: str,
    body: SendMessageRequest,
    repo: Repository = Depends(get_repo),
    redis_client=Depends(get_redis),
    user: CurrentUser = Depends(current_user),
):
    require_same_physician(body.sender_physician_id, user, "sender_physician_id")
    thread = await _get_participant_thread(repo, thread_id, user.physician_id)
    message = await repo.create_consult_message(thread_id, user.physician_id, body.body)
    await _publish(redis_client, _other_participant(thread, user.physician_id), message)
    return message


@router.websocket("/ws/consults/{physician_id}")
async def consult_socket(websocket: WebSocket, physician_id: str, redis_client=Depends(get_redis)):
    """One socket per physician: live delivery of every message sent to them, across all their
    consult threads, relayed through Redis pub/sub so it works across API instances too.
    Authenticated with ?token=<access token>; you can only listen on your own id."""
    user = await authenticate_websocket(websocket)
    if user is None:
        return
    if physician_id != user.physician_id:
        await websocket.close(code=4403)
        return
    await websocket.accept()
    pubsub = redis_client.pubsub()
    channel = _channel(physician_id)
    await pubsub.subscribe(channel)

    async def forward() -> None:
        async for item in pubsub.listen():
            if item["type"] == "message":
                await websocket.send_text(item["data"])

    forward_task = asyncio.create_task(forward())
    try:
        while True:
            await websocket.receive_text()  # blocks until the client sends or disconnects
    except WebSocketDisconnect:
        pass
    finally:
        forward_task.cancel()
        with contextlib.suppress(Exception):
            await pubsub.unsubscribe(channel)
            await pubsub.close()
