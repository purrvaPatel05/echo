"""Socket.IO server: consult chat + referral status pushes."""
import asyncio

import socketio

from . import store
from .models import ConsultMessage, Referral

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")


def room(consult_id: str) -> str:
    return "consult:%s" % consult_id


@sio.event
async def join(sid, data):
    await sio.enter_room(sid, room(data["consult_id"]))


@sio.event
async def leave(sid, data):
    await sio.leave_room(sid, room(data["consult_id"]))


@sio.event
async def send_message(sid, data):
    """Client -> server. Persists the message, fans it out, then fakes a specialist reply."""
    msg = add_message(data["consult_id"], store.CURRENT_USER.id, store.CURRENT_USER.name, data["body"])
    await sio.emit("message", msg.model_dump(), room=room(msg.consult_id))
    asyncio.create_task(_mock_reply(data["consult_id"]))


def add_message(consult_id: str, sender_id: str, sender_name: str, body: str) -> ConsultMessage:
    msg = ConsultMessage(
        id=store.new_id("msg"), consult_id=consult_id, sender_id=sender_id,
        sender_name=sender_name, body=body, sent_at=store.now_iso(),
    )
    store.MESSAGES.setdefault(consult_id, []).append(msg)
    return msg


async def _mock_reply(consult_id: str) -> None:
    spec = store.SPECIALISTS.get(consult_id)
    if not spec:
        return
    await asyncio.sleep(1.5)
    msg = add_message(consult_id, spec.id, spec.name, "Thanks for the ping -- send over the labs and I'll take a look.")
    await sio.emit("message", msg.model_dump(), room=room(consult_id))


async def emit_referral_update(referral: Referral) -> None:
    await sio.emit("referral:update", referral.model_dump())
