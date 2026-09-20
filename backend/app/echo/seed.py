"""Display facts for the seeded patients (sex, and the city the frontend shows)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.echo.tables import EchoPatientMetaRow

# patient id -> (sex, city). Synthetic, like the patients themselves.
PATIENT_META: dict[str, tuple[str, str]] = {
    "pat_001": ("F", "Cambridge, MA"),
    "pat_002": ("M", "Brookline, MA"),
    "pat_003": ("F", "Boston, MA"),
    "pat_004": ("M", "Cambridge, MA"),
    "pat_005": ("F", "Somerville, MA"),
    "pat_006": ("M", "Watertown, MA"),
}


async def seed_echo(session: AsyncSession) -> None:
    """Idempotent: rows that already exist are left untouched."""
    for patient_id, (sex, city) in PATIENT_META.items():
        if await session.get(EchoPatientMetaRow, patient_id) is None:
            session.add(EchoPatientMetaRow(patient_id=patient_id, sex=sex, city=city))
    await session.commit()
