"""Data access for the echo_* tables (and the one core lookup the layer needs that the core
repository doesn't expose)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppointmentRow, SpecialistInsuranceRow
from app.echo.tables import EchoPatientMetaRow, EchoReferralMetaRow, EchoSimulatedMessageRow


class EchoStore:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def patient_meta(self, patient_id: str) -> EchoPatientMetaRow | None:
        return await self._s.get(EchoPatientMetaRow, patient_id)

    async def patient_metas(self) -> dict[str, EchoPatientMetaRow]:
        rows = await self._s.scalars(select(EchoPatientMetaRow))
        return {r.patient_id: r for r in rows}

    async def referral_meta(self, referral_id: str) -> EchoReferralMetaRow | None:
        # Populate from the database on every call: another session (the background analysis
        # job) may have changed it since this session last read the row.
        return await self._s.scalar(
            select(EchoReferralMetaRow)
            .where(EchoReferralMetaRow.referral_id == referral_id)
            .execution_options(populate_existing=True)
        )

    async def add_referral_meta(self, row: EchoReferralMetaRow) -> None:
        self._s.add(row)
        await self._s.commit()

    async def commit(self) -> None:
        await self._s.commit()

    async def appointment_for(self, referral_id: str, slot_id: str) -> AppointmentRow | None:
        """An appointment this referral already holds on this slot (makes approving retry-safe)."""
        return await self._s.scalar(
            select(AppointmentRow).where(
                AppointmentRow.referral_id == referral_id, AppointmentRow.slot_id == slot_id
            )
        )

    async def network_payers(self) -> set[str]:
        """Every payer the insurance-network table has data for."""
        return set(await self._s.scalars(select(SpecialistInsuranceRow.payer).distinct()))

    async def simulated_message_ids(self, message_ids: list[str]) -> set[str]:
        """Which of these consult messages were written by the demo colleague simulator."""
        if not message_ids:
            return set()
        rows = await self._s.scalars(
            select(EchoSimulatedMessageRow.message_id).where(
                EchoSimulatedMessageRow.message_id.in_(message_ids)
            )
        )
        return set(rows)
