"""Demo colleague: answers a chat message a few seconds after it is sent.

Only for SIMULATE_COLLEAGUE_REPLIES=true (dev or demo auth; the settings refuse it with real
logins). The reply is written into the conversation as if from the colleague, but is recorded in
`echo_simulated_messages`, so the API marks it and the UI labels it "Demo reply". It is canned
text: it never claims to be a clinical opinion.
"""

import asyncio

from app.db.repository import Repository
from app.db.session import SessionFactory
from app.echo.tables import EchoSimulatedMessageRow

# Neutral follow-up questions: a back-and-forth reads naturally, with no medical advice in it.
REPLIES = [
    "Thanks for sending this. Could you share the most recent results?",
    "That's helpful. How long has this been going on, and has anything changed recently?",
    "Understood. Please send anything new before the visit and I'll review it.",
    "Sounds reasonable to me. Let me know how the patient responds.",
]


def reply_text(my_message_count: int) -> str:
    return REPLIES[(max(my_message_count, 1) - 1) % len(REPLIES)]


async def simulate_reply(
    thread_id: str, colleague_id: str, session_factory: SessionFactory, delay_seconds: float
) -> None:
    """Wait, then answer once if the colleague has not already spoken last."""
    await asyncio.sleep(delay_seconds)
    async with session_factory() as session:
        repo = Repository(session)
        messages = await repo.consult_messages(thread_id)
        if not messages or messages[-1].sender_physician_id == colleague_id:
            return  # nothing to answer, or it was already answered
        mine = sum(1 for m in messages if m.sender_physician_id != colleague_id)
        message = await repo.create_consult_message(thread_id, colleague_id, reply_text(mine))
        session.add(EchoSimulatedMessageRow(message_id=message.id))
        await session.commit()
