"""Load synthetic data: `uv run python -m app.seed` (run `alembic upgrade head` first)."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PatientRow, PhysicianRow, SpecialistRow
from app.db.repository import Repository
from app.db.session import default_session_factory
from app.models.referral import ReferralCreate
from app.seed.data import DEMO_CASES, PATIENTS, PHYSICIANS, SPECIALISTS


async def seed(session: AsyncSession) -> None:
    """Idempotent: rows that already exist are left untouched."""
    for p in PHYSICIANS:
        if await session.get(PhysicianRow, p.id) is None:
            session.add(
                PhysicianRow(
                    id=p.id, name=p.name, specialty=p.specialty, practice_name=p.practice_name
                )
            )
    for p in PATIENTS:
        if await session.get(PatientRow, p.id) is None:
            session.add(
                PatientRow(
                    id=p.id,
                    display_name=p.display_name,
                    age=p.age,
                    zip_code=p.zip_code,
                    lat=p.location.lat,
                    lng=p.location.lng,
                    payer=p.insurance.payer,
                    plan_name=p.insurance.plan_name,
                )
            )
    for s in SPECIALISTS:
        if await session.get(SpecialistRow, s.id) is None:
            session.add(
                SpecialistRow(
                    id=s.id,
                    name=s.name,
                    specialty=s.specialty,
                    subspecialties=s.subspecialties,
                    practice_name=s.practice_name,
                    address=s.address,
                    lat=s.location.lat,
                    lng=s.location.lng,
                )
            )
    await session.commit()

    repo = Repository(session)
    for c in DEMO_CASES:
        if await repo.referral(c.referral_id) is None:
            await repo.create_referral(
                ReferralCreate(
                    patient_id=c.patient_id,
                    referring_physician_id=c.physician_id,
                    case_notes=c.notes,
                    urgency=c.urgency,
                ),
                referral_id=c.referral_id,
            )


async def main() -> None:
    async with default_session_factory()() as session:
        await seed(session)
    print(
        f"seeded {len(PHYSICIANS)} physicians, {len(PATIENTS)} patients, "
        f"{len(SPECIALISTS)} specialists, {len(DEMO_CASES)} demo referrals"
    )


if __name__ == "__main__":
    asyncio.run(main())
