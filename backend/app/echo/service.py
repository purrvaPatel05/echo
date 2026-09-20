"""Turns the core domain into the shapes of the ECHO frontend contract.

The contract is docs/echo-api-contract-changes.md. Where the frontend needs something the core
doesn't model, the choice made here is written next to the code and listed in
docs/echo-compat-notes.md, so the backend owners can see every place the contracts were reconciled.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException

from app.auth import CurrentUser
from app.booking import Booker, SlotUnavailableError
from app.db.repository import Repository
from app.echo import schemas as s
from app.echo.store import EchoStore
from app.echo.tables import EchoPatientMetaRow, EchoReferralMetaRow
from app.echo.trial_info import TRIAL_INFO
from app.integrations.maps import haversine_miles
from app.matching.config import URGENCY_WINDOW_DAYS
from app.models import consult as core_consult
from app.models.enums import (
    FitTier,
    InsuranceStatus,
    JobStatus,
    ReferralStatus,
)
from app.models.match import MatchResult, MatchRun
from app.models.people import GeoPoint, Patient, Specialist
from app.models.referral import Approval, Referral, ReferralCreate
from app.services import referrals as core
from app.trials.matcher import match_trials

try:  # the demo data is Boston-area; show slot times there, and fall back to UTC without tzdata
    _LOCAL = ZoneInfo("America/New_York")
except ZoneInfoNotFoundError:  # pragma: no cover
    _LOCAL = UTC

_EDITABLE = (ReferralStatus.DRAFT, ReferralStatus.MATCHED, ReferralStatus.WAITLISTED)
_DISTANCES = [10, 25, 50, 100]
_MAX_MATCHES = 3
_DEFAULT_TRIAL_MILES = 100
_CHECKS = ["clinical_fit", "insurance", "distance", "urgency", "availability"]
_TIER_WORD = {FitTier.EXCELLENT: "Excellent", FitTier.GOOD: "Good", FitTier.PARTIAL: "Partial"}
_MAX_REASON = 90


def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=UTC)


def _iso(dt: datetime | None) -> str | None:
    dt = _aware(dt)
    return dt.isoformat() if dt else None


def _local_iso(dt: datetime) -> str:
    """Slot times are shown in the specialists' local time (same instant, Eastern offset)."""
    return _aware(dt).astimezone(_LOCAL).isoformat()


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _city(address: str) -> str:
    """ "120 Main St, Cambridge, MA" -> "Cambridge, MA"."""
    parts = [p.strip() for p in address.split(",")]
    return ", ".join(parts[-2:]) if len(parts) >= 2 else address


def _fmt_slot(start: datetime, days: int | None) -> str:
    local = _aware(start).astimezone(_LOCAL)
    text = f"{local:%a, %b} {local.day} · {local:%I:%M %p}".replace(" 0", " ", 1)
    text = text.replace("· 0", "· ")
    if days is None:
        return text
    return f"{text} ({'today' if days <= 0 else '1 day' if days == 1 else f'{days} days'})"


def _in_days(days: int | None) -> str:
    return "today" if days is not None and days <= 0 else f"in {days} day{'s' if days != 1 else ''}"


@dataclass
class _Bundle:
    """Everything needed to describe one referral."""

    ref: Referral
    patient: Patient
    pmeta: EchoPatientMetaRow | None
    meta: EchoReferralMetaRow | None
    run: MatchRun | None  # the latest match run


class EchoService:
    def __init__(self, repo: Repository, store: EchoStore, user: CurrentUser):
        self.repo = repo
        self.store = store
        self.user = user

    # ---- directory ---------------------------------------------------------------------------

    async def me(self) -> s.Physician:
        p = await self.repo.physician(self.user.physician_id)
        if p is None:
            raise HTTPException(403, "This account is linked to an unknown physician")
        return s.Physician(
            id=p.id, name=p.name, specialty=p.specialty, organization=p.practice_name
        )

    def _patient_out(self, p: Patient, pmeta: EchoPatientMetaRow | None, meta=None) -> s.Patient:
        return s.Patient(
            id=p.id,
            name=p.display_name,
            age=p.age,
            sex=(pmeta.sex if pmeta else "X"),  # type: ignore[arg-type]
            insurance=meta.insurance if meta else p.insurance.payer,
            location=meta.patient_location if meta else (pmeta.city if pmeta else p.zip_code),
        )

    async def patients(self) -> list[s.Patient]:
        metas = await self.store.patient_metas()
        rows = await self.repo.patients()
        return sorted((self._patient_out(p, metas.get(p.id)) for p in rows), key=lambda x: x.name)

    async def referral_options(self) -> s.ReferralOptions:
        specialists = await self.repo.specialists()
        by_specialty: dict[str, set[str]] = {}
        for sp in specialists:
            by_specialty.setdefault(sp.specialty, set()).update(_cap(x) for x in sp.subspecialties)
        # Payers on patient records plus payers the network table has data for.
        payers = {p.insurance.payer for p in await self.repo.patients()}
        return s.ReferralOptions(
            specialties=[
                s.SpecialtyOption(name=n, subspecialties=sorted(subs))
                for n, subs in sorted(by_specialty.items())
            ],
            insurers=sorted(payers | await self.store.network_payers()),
            distances_miles=_DISTANCES,
        )

    # ---- referral description ----------------------------------------------------------------

    async def _bundle(self, ref: Referral) -> _Bundle:
        patient = await self.repo.patient(ref.patient_id)
        return _Bundle(
            ref=ref,
            patient=patient,
            pmeta=await self.store.patient_meta(ref.patient_id),
            meta=await self.store.referral_meta(ref.id),
            run=await self.repo.latest_match_run(ref.id),
        )

    @staticmethod
    def _describe(b: _Bundle) -> tuple[str, str, str, str, int]:
        """reason, details, specialty, subspecialty, preferred distance. Referrals not created
        through /api/echo (no form data) are described from the case notes and the parsed case."""
        if b.meta:
            m = b.meta
            return m.reason, m.details, m.specialty, m.subspecialty, m.preferred_distance_miles
        parsed = b.ref.parsed_case
        first_line = b.ref.case_notes.strip().splitlines()[0]
        reason = (parsed.condition_summary if parsed else first_line)[:_MAX_REASON]
        specialty = (
            parsed.suggested_specialties[0] if parsed and parsed.suggested_specialties else ""
        )
        return reason, b.ref.case_notes, specialty, "", 25

    def _specialist_out(
        self, sp: Specialist, subspecialty: str = "", with_city: bool = True
    ) -> s.SpecialistSummary:
        subs = sp.subspecialties
        pick = next((x for x in subs if x.lower() == subspecialty.lower()), subs[0] if subs else "")
        return s.SpecialistSummary(
            id=sp.id,
            name=sp.name,
            specialty=sp.specialty,
            subspecialty=_cap(pick),
            organization=sp.practice_name,
            city=_city(sp.address) if with_city else None,
        )

    @staticmethod
    def _status(ref: Referral) -> str:
        if ref.status == ReferralStatus.BOOKED and ref.appointment is not None:
            return "scheduled"
        if ref.status in (ReferralStatus.APPROVED, ReferralStatus.BOOKED):
            return "awaiting_patient"
        return "awaiting_approval"

    @staticmethod
    def _analysis_failed(b: _Bundle) -> bool:
        return bool(b.meta and b.meta.analysis_error) or bool(
            b.run and b.run.status == JobStatus.FAILED
        )

    def _timeline(self, b: _Bundle) -> list[s.TimelineEvent]:
        """Derived from what the core already records, so it can't drift. `sent_to_patient` is
        only a recorded event: no message is sent to the patient (see docs/echo-compat-notes.md)."""
        ref, events = b.ref, []
        events.append(("created", ref.created_at))
        if b.run and b.run.status == JobStatus.COMPLETE and b.run.completed_at:
            events.append(("matches_found", b.run.completed_at))
        chosen_at = b.meta.selected_at if b.meta and b.meta.selected_at else None
        if chosen_at is None and ref.approval:
            chosen_at = ref.approval.approved_at
        if chosen_at:
            events.append(("specialist_selected", chosen_at))
        if ref.approval:
            events.append(("approved", ref.approval.approved_at))
            events.append(("sent_to_patient", ref.approval.approved_at))
            if ref.appointment:
                events.append(("scheduled", ref.approval.approved_at))
        if (
            b.meta
            and b.meta.patient_status in ("confirmed", "declined")
            and b.meta.patient_responded_at
        ):
            events.append((f"patient_{b.meta.patient_status}", b.meta.patient_responded_at))
        order = {k: i for i, (k, _) in enumerate(events)}
        events.sort(key=lambda e: (_aware(e[1]), order[e[0]]))
        return [s.TimelineEvent(kind=k, at=_iso(at)) for k, at in events]

    def _confirmation(self, b: _Bundle) -> s.PatientConfirmation:
        st = b.meta.patient_status if b.meta else "pending"
        return s.PatientConfirmation(
            status=st,  # type: ignore[arg-type]
            responded_at=_iso(b.meta.patient_responded_at) if b.meta and st != "pending" else None,
        )

    def _attention(
        self, b: _Bundle, status: str, default_count: int | None, distance: int
    ) -> s.Attention | None:
        if status == "awaiting_approval":
            if self._analysis_failed(b):
                return s.Attention(reason="Analysis didn't finish", action="Retry analysis")
            if default_count == 0:
                return s.Attention(
                    reason=f"No strong match within {distance} miles", action="Expand search"
                )
        if (
            status == "awaiting_patient"
            and b.ref.approval
            and self._confirmation(b).status == "pending"
        ):
            days = (datetime.now(UTC) - _aware(b.ref.approval.approved_at)).days
            if days >= 3:
                return s.Attention(
                    reason=f"Patient hasn't responded in {days} days", action="Contact patient"
                )
        return None

    async def _referral_out(self, b: _Bundle, specialists: dict[str, Specialist]) -> s.Referral:
        ref = b.ref
        reason, details, specialty, subspecialty, distance = self._describe(b)
        status = self._status(ref)

        chosen_id = (
            ref.approval.specialist_id
            if ref.approval
            else (b.meta.selected_specialist_id if b.meta else None)
        )
        sp = specialists.get(chosen_id) if chosen_id else None

        default_count = None
        if b.run and b.run.status == JobStatus.COMPLETE and status == "awaiting_approval":
            default_count = len(self._matches(b, specialists, distance, False, cap=False)[0])

        insurance_accepted = None
        if ref.approval and b.run:
            res = next(
                (r for r in b.run.results if r.specialist.id == ref.approval.specialist_id), None
            )
            if res is not None:
                insurance_accepted = res.insurance.status == InsuranceStatus.IN_NETWORK

        return s.Referral(
            id=ref.id,
            patient=self._patient_out(b.patient, b.pmeta, b.meta),
            reason=reason,
            details=details,
            preferred_distance_miles=distance,
            specialty=specialty,
            subspecialty=subspecialty,
            urgency=ref.urgency,
            status=status,  # type: ignore[arg-type]
            created_at=_iso(ref.created_at),
            specialist=self._specialist_out(sp, subspecialty) if sp else None,
            appointment_at=_local_iso(ref.appointment.slot.start) if ref.appointment else None,
            attention=self._attention(b, status, default_count, distance),
            insurance_accepted=insurance_accepted,
            patient_confirmation=self._confirmation(b),
            timeline=self._timeline(b),
        )

    async def _specialists(self) -> dict[str, Specialist]:
        return {sp.id: sp for sp in await self.repo.specialists()}

    async def referrals(self) -> list[s.Referral]:
        specialists = await self._specialists()
        rows = await self.repo.referrals(None if self.user.is_admin else self.user.physician_id)
        return [await self._referral_out(await self._bundle(r), specialists) for r in rows]

    async def referral(self, referral_id: str) -> s.Referral:
        ref = await core.get_or_404(self.repo, referral_id, self.user)
        return await self._referral_out(await self._bundle(ref), await self._specialists())

    async def _owned(self, referral_id: str) -> _Bundle:
        ref = await core.get_or_404(self.repo, referral_id, self.user)
        return await self._bundle(ref)

    async def _ensure_meta(self, b: _Bundle) -> EchoReferralMetaRow:
        """Referrals made outside /api/echo get their description recorded the first time the
        frontend needs to change something about them."""
        if b.meta is None:
            reason, details, specialty, sub, distance = self._describe(b)
            pmeta = b.pmeta
            b.meta = EchoReferralMetaRow(
                referral_id=b.ref.id,
                reason=reason,
                details=details,
                specialty=specialty,
                subspecialty=sub,
                preferred_distance_miles=distance,
                patient_location=pmeta.city if pmeta else b.patient.zip_code,
                insurance=b.patient.insurance.payer,
                pipeline_started=0,
            )
            await self.store.add_referral_meta(b.meta)
        return b.meta

    # ---- create + analysis -------------------------------------------------------------------

    async def create_referral(self, body: s.NewReferralInput) -> Referral:
        patient = await self.repo.patient(body.patient_id)
        if patient is None:
            raise HTTPException(404, "Patient not found")
        if await self.repo.physician(self.user.physician_id) is None:
            raise HTTPException(403, "This account is linked to an unknown physician")
        hint = f"Suspected specialty: {body.specialty}" + (
            f" ({body.subspecialty})" if body.subspecialty else ""
        )
        # The form's fields become the case notes the parser reads; the specialty is a hint.
        notes = f"{body.reason.strip()}\n\n{body.details.strip()}\n\n{hint}."
        ref = await self.repo.create_referral(
            ReferralCreate(
                patient_id=body.patient_id,
                referring_physician_id=self.user.physician_id,
                case_notes=notes,
                urgency=body.urgency,
            )
        )
        await self.store.add_referral_meta(
            EchoReferralMetaRow(
                referral_id=ref.id,
                reason=body.reason.strip(),
                details=body.details.strip(),
                specialty=body.specialty,
                subspecialty=body.subspecialty or "",
                preferred_distance_miles=body.preferred_distance_miles,
                patient_location=body.patient_location.strip(),
                insurance=body.insurance.strip(),
                pipeline_started=1,
            )
        )
        return ref

    def _analysis(self, b: _Bundle, match_count: int | None) -> s.Analysis:
        ref, run = b.ref, b.run
        started = bool(b.meta and b.meta.pipeline_started)
        parsed = ref.parsed_case is not None

        def checks(done: int, active: int | None = None, error: int | None = None):
            out = []
            for i, key in enumerate(_CHECKS):
                state = "waiting"
                if error is not None and i == error:
                    state = "error"
                elif i < done:
                    state = "done"
                elif active is not None and i == active:
                    state = "active"
                out.append(s.AnalysisCheck(key=key, state=state))  # type: ignore[arg-type]
            return out

        if run and run.status == JobStatus.COMPLETE and not self._analysis_failed(b):
            return s.Analysis(
                referral_id=ref.id,
                status="complete",
                checks=checks(len(_CHECKS)),
                match_count=match_count,
            )
        if self._analysis_failed(b) or (not started and not parsed and run is None):
            # The core doesn't report which step broke: clinical fit if the case never parsed,
            # otherwise the last (the run failed while gathering availability and ranking).
            failed_at = 0 if not parsed else len(_CHECKS) - 1
            return s.Analysis(
                referral_id=ref.id,
                status="error",
                checks=checks(failed_at, error=failed_at),
                match_count=None,
            )
        # Still working. The core doesn't report per-check progress, so this is coarse:
        # parsing -> clinical fit active; matching -> clinical fit done, the rest in progress.
        return s.Analysis(
            referral_id=ref.id,
            status="running",
            checks=checks(1, active=1) if parsed else checks(0, active=0),
            match_count=None,
        )

    async def analysis(self, referral_id: str) -> s.Analysis:
        b = await self._owned(referral_id)
        count = None
        if b.run and b.run.status == JobStatus.COMPLETE:
            distance = self._describe(b)[4]
            count = len(self._matches(b, await self._specialists(), distance, False)[0])
        return self._analysis(b, count)

    async def prepare_retry(self, referral_id: str) -> _Bundle:
        """Clear a failed analysis so the pipeline can run again."""
        b = await self._owned(referral_id)
        if b.ref.status not in _EDITABLE:
            raise HTTPException(409, f"Referral is {b.ref.status.value}; it can't be re-analyzed")
        meta = await self._ensure_meta(b)
        meta.analysis_error = None
        meta.pipeline_started = 1
        await self.store.commit()
        return b

    # ---- matches -----------------------------------------------------------------------------

    def _factors(self, res: MatchResult, b: _Bundle, distance: int) -> list[s.MatchFactor]:
        fit = res.clinical_fit.tier
        ins = res.insurance.status
        slot, days = res.earliest_slot, res.days_until_slot
        window = URGENCY_WINDOW_DAYS[b.ref.urgency]
        within = res.distance_miles <= distance
        miles = f"{res.distance_miles:.1f} miles"

        if ins == InsuranceStatus.IN_NETWORK:
            insurance = ("met", "Accepted")
        elif ins == InsuranceStatus.UNVERIFIED:
            insurance = ("partial", "Coverage unverified")
        else:
            insurance = ("unmet", "Out of network")
        if slot is None:
            availability = ("unmet", "No open appointment")
            urgency = ("unmet", "No opening to compare")
        else:
            availability = ("met", _fmt_slot(slot.start, days))
            urgency = (
                ("met", "Within timeframe")
                if days is not None and days <= window
                else ("partial", f"Later than the {b.ref.urgency.value} timeframe")
            )
        out = [
            (
                "clinical_fit",
                "partial" if fit == FitTier.PARTIAL else "met",
                f"{_TIER_WORD[fit]} clinical fit",
            ),
            ("insurance", *insurance),
            (
                "distance",
                "met" if within else "partial",
                miles if within else f"{miles} · over {distance}-mile preference",
            ),
            ("availability", *availability),
            ("urgency", *urgency),
        ]
        return [s.MatchFactor(key=k, status=st, detail=d) for k, st, d in out]  # type: ignore[arg-type]

    def _matches(
        self,
        b: _Bundle,
        specialists: dict[str, Specialist],
        distance: int,
        include_partial: bool,
        cap: bool = True,
    ) -> tuple[list[s.SpecialistMatch], int]:
        """Ranked matches from the latest completed run, in the core's order.

        A match is listed by default only if every factor is met (a preference-distance limit is
        applied here, since the core scores distance but never gates on it). With
        `include_partial`, specialists who miss a factor are added after them, labelled partial.
        """
        run = b.run
        if run is None or run.status != JobStatus.COMPLETE:
            return [], distance
        _, _, _, subspecialty, _ = self._describe(b)
        full, partial = [], []
        for res in run.results:
            factors = self._factors(res, b, distance)
            all_met = all(f.status == "met" for f in factors)
            strength = (
                ("strong" if res.clinical_fit.tier == FitTier.EXCELLENT else "good")
                if all_met
                else "partial"
            )
            slot = res.earliest_slot
            why = f"{_TIER_WORD[res.clinical_fit.tier]} clinical fit"
            if slot is not None:
                why += f"; earliest opening {_in_days(res.days_until_slot)}"
            why += f", {res.distance_miles:.1f} miles away."
            if res.insurance.status != InsuranceStatus.IN_NETWORK:
                why += f" Insurance: {res.insurance.status.value.replace('_', '-')}."
            sp = specialists.get(res.specialist.id) or res.specialist
            m = s.SpecialistMatch(
                specialist=self._specialist_out(sp, subspecialty),
                distance_miles=round(res.distance_miles, 1),
                strength=strength,  # type: ignore[arg-type]
                factors=factors,
                why=why,
                next_slot=s.Slot(id=slot.id, starts_at=_local_iso(slot.start)) if slot else None,
            )
            (full if all_met else partial).append(m)
        # Show specialists who miss a factor only when asked, or when nobody meets every factor:
        # an empty page is never the answer while the ranking found people, and each partial match
        # says exactly which factor it misses.
        out = full + (partial if include_partial or not full else [])
        return (out[:_MAX_MATCHES] if cap else out), distance

    async def needs_analysis(self, referral_id: str) -> bool:
        """True when nothing has analyzed this referral (a referral created outside the ECHO
        form, such as the seeded demo ones) or its last analysis failed and this is a retry."""
        b = await self._owned(referral_id)
        if self._analysis_failed(b):
            return True
        started = bool(b.meta and b.meta.pipeline_started)
        return b.run is None and not started

    async def mark_analysis_started(self, referral_id: str) -> None:
        b = await self._owned(referral_id)
        meta = await self._ensure_meta(b)
        meta.analysis_error = None
        meta.pipeline_started = 1
        await self.store.commit()

    async def matches(
        self, referral_id: str, distance: int | None, include_partial: bool
    ) -> s.MatchesResult:
        b = await self._owned(referral_id)
        if b.run is None or b.run.status != JobStatus.COMPLETE:
            raise HTTPException(409, "Analysis has not finished for this referral")
        reason, _, specialty, _, pref = self._describe(b)
        search = distance or pref
        matches, _ = self._matches(b, await self._specialists(), search, include_partial)
        note = None
        if not matches:
            city = self._patient_out(b.patient, b.pmeta, b.meta).location
            note = (
                "No specialist met the clinical fit, insurance and availability "
                "requirements for this case."
                if not b.run.results
                else f"No {specialty or 'matching'} specialist near {city} meets every "
                f"criterion within {search} miles."
            )
        return s.MatchesResult(
            referral_id=b.ref.id,
            search_distance_miles=search,
            matches=matches,
            no_match_reason=note,
        )

    async def slots(self, specialist_id: str) -> list[s.Slot]:
        if await self.repo.specialist(specialist_id) is None:
            raise HTTPException(404, "Specialist not found")
        rows = await self.repo.open_slots(specialist_id, datetime.now(UTC), limit=12)
        return [s.Slot(id=x.id, starts_at=_local_iso(x.start)) for x in rows]

    # ---- selection, approval ------------------------------------------------------------------

    async def select(self, referral_id: str, specialist_id: str) -> s.Referral:
        b = await self._owned(referral_id)
        if b.ref.status not in _EDITABLE:
            raise HTTPException(
                409, f"Referral is {b.ref.status.value}; the specialist can't change"
            )
        if await self.repo.specialist(specialist_id) is None:
            raise HTTPException(404, "Specialist not found")
        meta = await self._ensure_meta(b)
        meta.selected_specialist_id = specialist_id
        meta.selected_at = datetime.now(UTC)
        await self.store.commit()
        return await self._referral_out(await self._bundle(b.ref), await self._specialists())

    async def approve(self, referral_id: str, body: s.ApproveInput, booker: Booker) -> s.Referral:
        """The physician's explicit approval; the only path here that books.

        Unlike the core's /approve, any currently open slot of a listed specialist may be chosen
        (the frontend's Appointment select offers them all), not only the earliest one. Retrying
        after a partial failure is safe: a slot this referral already holds is reused.
        """
        b = await self._owned(referral_id)
        core.require_owner(b.ref, self.user)
        ref = b.ref
        held = await self.store.appointment_for(ref.id, body.slot_id)
        already = ref.approval is not None and ref.approval.slot_id == body.slot_id
        if ref.status not in _EDITABLE and not (held and already):
            raise HTTPException(409, f"Referral is {ref.status.value}; it can't be approved again")
        if held is None:
            if b.run is None or b.run.status != JobStatus.COMPLETE:
                raise HTTPException(409, "Analysis has not finished for this referral")
            if not any(r.specialist.id == body.specialist_id for r in b.run.results):
                raise HTTPException(422, "Specialist was not in the match results")
        try:
            appointment = (
                await self._existing_appointment(held, ref.id)
                if held is not None
                else await booker.book(ref, body.specialist_id, body.slot_id)
            )
        except SlotUnavailableError:
            raise HTTPException(409, "That slot is no longer available") from None

        ref.approval = Approval(
            specialist_id=body.specialist_id,
            slot_id=body.slot_id,
            approved_by=self.user.physician_id,
            approved_at=(ref.approval.approved_at if ref.approval else datetime.now(UTC)),
        )
        ref.appointment = appointment
        ref.status = ReferralStatus.BOOKED
        await self.repo.save_referral(ref)
        return await self._referral_out(await self._bundle(ref), await self._specialists())

    async def _existing_appointment(self, row, referral_id: str):
        from app.models.scheduling import Appointment

        slot = await self.repo.slot(row.slot_id)
        return Appointment(
            id=row.id, referral_id=referral_id, slot=slot, status=ReferralStatus.BOOKED
        )

    async def patient_response(self, referral_id: str, status: str) -> s.Referral:
        """Dev-only stand-in for the patient's answer (there is no patient-facing screen)."""
        b = await self._owned(referral_id)
        if b.ref.status != ReferralStatus.BOOKED:
            raise HTTPException(409, "There is no booked appointment to respond to")
        meta = await self._ensure_meta(b)
        meta.patient_status = status
        meta.patient_responded_at = datetime.now(UTC)
        await self.store.commit()
        return await self._referral_out(await self._bundle(b.ref), await self._specialists())

    # ---- consult (chat) ----------------------------------------------------------------------
    #
    # A consult is a core consult thread between two physicians: any number of messages each way,
    # optionally about one of the sender's referrals. "Sent" means recorded here; nothing tells the
    # colleague, and nothing here says they were notified, delivered to, or have read anything.

    async def colleagues(self) -> list[s.Colleague]:
        return [
            s.Colleague(id=p.id, name=p.name, specialty=p.specialty, organization=p.practice_name)
            for p in await self.repo.physicians()
            if p.id != self.user.physician_id
        ]

    async def _colleague(self, physician_id: str) -> s.Colleague:
        p = await self.repo.physician(physician_id)
        return s.Colleague(
            id=physician_id,
            name=p.name if p else physician_id,
            specialty=p.specialty if p else "",
            organization=p.practice_name if p else "",
        )

    def _other(self, thread: core_consult.ConsultThread) -> str:
        me = self.user.physician_id
        return (
            thread.recipient_physician_id
            if thread.initiator_physician_id == me
            else thread.initiator_physician_id
        )

    async def _referral_context(self, thread: core_consult.ConsultThread):
        """(what the sender sees, what the colleague is given) for the attached referral, if any."""
        if thread.referral_id is None:
            return None, None
        ref = await self.repo.referral(thread.referral_id)
        if ref is None:
            return None, None
        b = await self._bundle(ref)
        reason, details, *_ = self._describe(b)
        sex = b.pmeta.sex if b.pmeta else "X"
        context = s.ConsultContext(age=b.patient.age, sex=sex, reason=reason, summary=details)  # type: ignore[arg-type]
        mine = thread.initiator_physician_id == self.user.physician_id
        seen = (
            s.ConsultReferralRef(
                id=ref.id,
                patient_name=b.patient.display_name,
                age=b.patient.age,
                sex=sex,
                reason=reason,
            )  # type: ignore[arg-type]
            if mine
            else None  # a colleague never sees the name, or the referral itself
        )
        return seen, context

    def _summary_parts(self, thread, messages):
        last = messages[-1]
        from_me = last.sender_physician_id == self.user.physician_id
        return (
            "pending" if from_me else "responded",
            s.ConsultLastMessage(text=last.body, at=_iso(last.created_at), from_me=from_me),
        )

    async def _thread_summary(self, thread, messages) -> s.ConsultSummary:
        status, last = self._summary_parts(thread, messages)
        seen, _ = await self._referral_context(thread)
        return s.ConsultSummary(
            id=thread.id,
            colleague=await self._colleague(self._other(thread)),
            referral=seen,
            status=status,  # type: ignore[arg-type]
            last_message=last,
        )

    async def _thread_detail(self, thread, messages) -> s.ConsultThread:
        summary = await self._thread_summary(thread, messages)
        _, context = await self._referral_context(thread)
        me = self.user.physician_id
        simulated = await self.store.simulated_message_ids([m.id for m in messages])
        return s.ConsultThread(
            **summary.model_dump(),
            messages=[
                s.ConsultMessage(
                    id=m.id,
                    from_me=m.sender_physician_id == me,
                    text=m.body,
                    at=_iso(m.created_at),
                    simulated=m.id in simulated,
                )
                for m in messages
            ],
            shared_context=context,
        )

    async def consult_threads(self) -> list[s.ConsultSummary]:
        """Every conversation I am in, newest activity first."""
        out = []
        for thread in await self.repo.threads_for(self.user.physician_id):
            messages = await self.repo.consult_messages(thread.id)
            if messages:
                out.append((messages[-1].created_at, await self._thread_summary(thread, messages)))
        return [x for _, x in sorted(out, key=lambda t: _aware(t[0]), reverse=True)]

    async def _participant_thread(self, thread_id: str) -> core_consult.ConsultThread:
        thread = await self.repo.consult_thread(thread_id)
        me = self.user.physician_id
        if thread is None or me not in (
            thread.initiator_physician_id,
            thread.recipient_physician_id,
        ):
            raise HTTPException(404, "Consult not found")  # not revealed to non-participants
        return thread

    async def consult_thread(self, thread_id: str) -> s.ConsultThread:
        thread = await self._participant_thread(thread_id)
        await self.repo.mark_consult_read(thread_id, self.user.physician_id)
        return await self._thread_detail(thread, await self.repo.consult_messages(thread_id))

    async def start_consult(self, body: s.StartConsultInput):
        """The physician's explicit action. Returns the new conversation and its first message."""
        if body.colleague_id == self.user.physician_id:
            raise HTTPException(422, "Choose a colleague other than yourself")
        if await self.repo.physician(body.colleague_id) is None:
            raise HTTPException(404, "Colleague not found")
        if body.referral_id is not None:
            await self._owned(body.referral_id)  # only one of my own referrals can be attached
        text = body.text.strip()
        if not text:
            raise HTTPException(422, "Write a message")
        thread = await self.repo.create_consult_thread(
            self.user.physician_id, body.colleague_id, body.referral_id
        )
        message = await self.repo.create_consult_message(thread.id, self.user.physician_id, text)
        return await self._thread_detail(thread, [message]), message

    async def send_consult_message(self, thread_id: str, text: str):
        thread = await self._participant_thread(thread_id)
        text = text.strip()
        if not text:
            raise HTTPException(422, "Write a message")
        message = await self.repo.create_consult_message(thread_id, self.user.physician_id, text)
        return await self._thread_detail(
            thread, await self.repo.consult_messages(thread_id)
        ), message

    # ---- clinical trials ---------------------------------------------------------------------

    @staticmethod
    def _trial_options(distance_miles: str | None, all_statuses: bool) -> tuple[int | None, bool]:
        if distance_miles is None:
            return _DEFAULT_TRIAL_MILES, all_statuses
        if distance_miles == "any":
            return None, all_statuses
        try:
            miles = int(distance_miles)
        except ValueError:
            raise HTTPException(422, "distanceMiles must be a number or 'any'") from None
        if miles <= 0:
            raise HTTPException(422, "distanceMiles must be positive")
        return miles, all_statuses

    async def trial_criteria(
        self, referral_id: str, distance_miles: str | None, all_statuses: bool
    ) -> s.TrialCriteria:
        b = await self._owned(referral_id)
        miles, all_st = self._trial_options(distance_miles, all_statuses)
        reason, *_ = self._describe(b)
        patient = self._patient_out(b.patient, b.pmeta, b.meta)
        return s.TrialCriteria(
            condition=reason,
            patient=f"{patient.age}y {patient.sex}",
            location="Any location"
            if miles is None
            else f"Within {miles} miles of {patient.location}",
            status="Recruiting, not yet recruiting, or active"
            if all_st
            else "Recruiting or not yet recruiting",
            source="ClinicalTrials.gov",
            distance_miles=miles,
            all_statuses=all_st,
        )

    async def trials(
        self, referral_id: str, distance_miles: str | None, all_statuses: bool
    ) -> s.TrialsResult:
        """Trials to review, from the core's (synthetic) trial list, matched to the parsed case by
        keyword. Unlike the core's /trials this does not require `rare_complex`: the frontend shows
        trials for any referral. A case that hasn't been parsed yet has none."""
        b = await self._owned(referral_id)
        miles, all_st = self._trial_options(distance_miles, all_statuses)
        parsed = b.ref.parsed_case
        if parsed is None:
            return s.TrialsResult(referral_id=b.ref.id, trials=[])
        wanted = {t.lower() for t in parsed.subspecialty_tags} | {
            x.lower() for x in parsed.suggested_specialties
        }
        origin = await self._patient_point(b.patient.id)
        out = []
        for t in match_trials(parsed):
            info = TRIAL_INFO.get(t.id)
            status = info.status if info else "recruiting"
            dist = (
                round(haversine_miles(origin, GeoPoint(lat=info.lat, lng=info.lng)), 1)
                if info and origin
                else None
            )
            if not all_st and status == "active_not_recruiting":
                continue
            if miles is not None and dist is not None and dist > miles:
                continue
            overlap = sorted(wanted & {k.lower() for k in t.condition_keywords})
            out.append(
                s.Trial(
                    nct_id=t.nct_id,
                    title=t.title,
                    condition=t.condition,
                    intervention=info.intervention if info else t.phase,
                    location=info.site if info else t.location,
                    distance_miles=dist,
                    status=status,  # type: ignore[arg-type]
                    relevance=(
                        f"Studies {t.condition.lower()}; the case mentions {', '.join(overlap)}."
                        if overlap
                        else None
                    ),
                    url=f"https://clinicaltrials.gov/study/{t.nct_id}",
                )
            )
        out.sort(key=lambda x: (x.distance_miles is None, x.distance_miles or 0))
        return s.TrialsResult(referral_id=b.ref.id, trials=out)

    async def _patient_point(self, patient_id: str) -> GeoPoint | None:
        p = await self.repo.patient(patient_id)
        return p.location if p else None
