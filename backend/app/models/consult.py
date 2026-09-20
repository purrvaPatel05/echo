"""Peer consult/ping (Member 3): physician-to-physician messaging, optionally about a case but
not a formal referral action. Persisted so a thread survives a disconnect or an offline
recipient; the WebSocket (app.routers.consult) only carries live delivery on top of this."""

from datetime import datetime

from pydantic import BaseModel, Field


class ConsultMessage(BaseModel):
    id: str
    thread_id: str
    sender_physician_id: str | None = None  # optional; if sent it must match the signed-in user
    body: str
    created_at: datetime
    read_at: datetime | None = None


class ConsultThread(BaseModel):
    id: str
    initiator_physician_id: str
    recipient_physician_id: str
    referral_id: str | None = None  # optional case context; not a formal referral action
    created_at: datetime
    last_message: ConsultMessage | None = None
    unread_count: int = 0  # relative to whichever physician the thread was listed for


class StartConsultRequest(BaseModel):
    from_physician_id: str | None = None  # optional; if sent it must match the signed-in user
    to_physician_id: str
    referral_id: str | None = None
    body: str = Field(min_length=1)


class SendMessageRequest(BaseModel):
    sender_physician_id: str
    body: str = Field(min_length=1)
