"""Peer consult/ping: REST persistence + gating (no Redis needed -- a publish failure degrades
gracefully, see app.routers.consult._publish), and one live end-to-end WebSocket test against an
in-memory fake pub/sub standing in for Redis.
"""

import asyncio

from fastapi.testclient import TestClient

from app.deps import get_redis
from app.main import app

DOC1, DOC2, DOC3 = "doc_001", "doc_002", "doc_003"
KNEE = "ref_demo_knee"


async def test_start_consult_validates_participants_and_referral(api):
    c = api.client
    body = {"from_physician_id": DOC1, "to_physician_id": DOC2, "body": "quick question"}
    assert (
        await c.post("/consults", json={**body, "from_physician_id": "nope"})
    ).status_code == 403  # must be the signed-in physician
    assert (await c.post("/consults", json={**body, "to_physician_id": "nope"})).status_code == 404
    assert (await c.post("/consults", json={**body, "referral_id": "nope"})).status_code == 404

    ok = await c.post("/consults", json={**body, "referral_id": KNEE})
    assert ok.status_code == 201
    thread = ok.json()
    assert thread["referral_id"] == KNEE
    assert thread["last_message"]["body"] == "quick question"


async def test_start_consult_without_referral_is_allowed(api):
    r = await api.client.post(
        "/consults",
        json={"from_physician_id": DOC1, "to_physician_id": DOC2, "body": "informal question"},
    )
    assert r.status_code == 201
    assert r.json()["referral_id"] is None


async def test_list_consults_shows_unread_count_and_last_message(api):
    c = api.client
    thread_id = (
        await c.post(
            "/consults", json={"from_physician_id": DOC1, "to_physician_id": DOC2, "body": "hi"}
        )
    ).json()["id"]
    await c.post(f"/consults/{thread_id}/messages", json={"sender_physician_id": DOC1, "body": "2"})

    api.as_physician(DOC2)
    recipient_view = (await c.get("/consults", params={"physician_id": DOC2})).json()
    thread = next(t for t in recipient_view if t["id"] == thread_id)
    assert thread["unread_count"] == 2
    assert thread["last_message"]["body"] == "2"

    api.as_physician(DOC1)
    sender_view = (await c.get("/consults", params={"physician_id": DOC1})).json()
    assert next(t for t in sender_view if t["id"] == thread_id)["unread_count"] == 0


async def test_reading_messages_marks_them_read(api):
    c = api.client
    thread_id = (
        await c.post(
            "/consults", json={"from_physician_id": DOC1, "to_physician_id": DOC2, "body": "hi"}
        )
    ).json()["id"]

    api.as_physician(DOC2)
    messages = await c.get(f"/consults/{thread_id}/messages", params={"reader_physician_id": DOC2})
    assert messages.status_code == 200
    assert len(messages.json()) == 1

    after = (await c.get("/consults", params={"physician_id": DOC2})).json()
    assert next(t for t in after if t["id"] == thread_id)["unread_count"] == 0


async def test_non_participant_cannot_read_or_send(api):
    c = api.client
    thread_id = (
        await c.post(
            "/consults", json={"from_physician_id": DOC1, "to_physician_id": DOC2, "body": "hi"}
        )
    ).json()["id"]

    api.as_physician(DOC3)
    assert (
        await c.get(f"/consults/{thread_id}/messages", params={"reader_physician_id": DOC3})
    ).status_code == 403
    assert (
        await c.post(
            f"/consults/{thread_id}/messages", json={"sender_physician_id": DOC3, "body": "x"}
        )
    ).status_code == 403


async def test_send_message_to_missing_thread_404s(api):
    r = await api.client.post(
        "/consults/nope/messages", json={"sender_physician_id": DOC1, "body": "x"}
    )
    assert r.status_code == 404


# ---- live WebSocket relay, via an in-memory fake standing in for Redis -------------------------


class FakeRedis:
    """Enough of redis.asyncio.Redis's pub/sub surface for the WS handler, no network involved."""

    def __init__(self):
        self._channels: dict[str, list[asyncio.Queue]] = {}

    async def publish(self, channel: str, message: str) -> None:
        for q in self._channels.get(channel, []):
            await q.put(message)

    def pubsub(self):
        return _FakePubSub(self)


class _FakePubSub:
    def __init__(self, redis: FakeRedis):
        self._redis = redis
        self._queue: asyncio.Queue | None = None
        self._channel: str | None = None

    async def subscribe(self, channel: str) -> None:
        self._channel = channel
        self._queue = asyncio.Queue()
        self._redis._channels.setdefault(channel, []).append(self._queue)

    async def listen(self):
        while True:
            data = await self._queue.get()
            yield {"type": "message", "data": data}

    async def unsubscribe(self, channel: str | None = None) -> None:
        queues = self._redis._channels.get(self._channel or channel, [])
        if self._queue in queues:
            queues.remove(self._queue)

    async def close(self) -> None:
        pass


async def test_ws_delivers_a_live_message_sent_after_connecting(api):
    """A ping sent before the recipient connects is NOT delivered live (it's just in the
    thread, per the "stored, delivered on reconnect/poll" design); one sent after they connect
    arrives over the socket."""
    fake_redis = FakeRedis()
    app.dependency_overrides[get_redis] = lambda: fake_redis
    try:
        client = TestClient(app, headers={"X-Dev-Physician": DOC1})
        thread_id = client.post(
            "/consults", json={"from_physician_id": DOC1, "to_physician_id": DOC2, "body": "hi"}
        ).json()["id"]

        with client.websocket_connect(
            f"/ws/consults/{DOC2}", headers={"X-Dev-Physician": DOC2}
        ) as ws:
            sent = client.post(
                f"/consults/{thread_id}/messages",
                json={"sender_physician_id": DOC1, "body": "live ping"},
            )
            assert sent.status_code == 201
            received = ws.receive_json()
            assert received["body"] == "live ping"
            assert received["sender_physician_id"] == DOC1
    finally:
        del app.dependency_overrides[get_redis]
