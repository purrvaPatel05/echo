"""The analysis pipeline the New Referral form kicks off: parse the case, accept the parser's
suggested complexity, then run matching. Runs in-process after the HTTP response (like the core's
inline jobs); the frontend polls /api/echo/referrals/{id}/analysis.

The core makes the physician confirm complexity before matching. The frontend has no such
step (the physician confirms urgency on the form), so here complexity defaults to the parser's
suggestion. That is a deliberate deviation, listed in docs/echo-compat-notes.md.
"""

import logging
from collections.abc import Sequence

from app import jobs
from app.db.repository import Repository
from app.db.session import SessionFactory
from app.echo.store import EchoStore
from app.matching.service import Analyzers
from app.matching.types import Candidate, CandidateProvider
from app.models.people import Patient, Specialist
from app.models.referral import ParsedCase

logger = logging.getLogger(__name__)


class PayerOverrideProvider:
    """Matches using the insurance the physician submitted for this referral, which may differ
    from the patient record (the New Referral form lets them edit it)."""

    def __init__(self, inner: CandidateProvider, payer: str):
        self._inner = inner
        self._payer = payer

    async def candidates_for(
        self, patient: Patient, specialists: Sequence[Specialist]
    ) -> list[Candidate]:
        plan = patient.insurance.model_copy(update={"payer": self._payer})
        return await self._inner.candidates_for(
            patient.model_copy(update={"insurance": plan}), specialists
        )


async def _record_failure(referral_id: str, session_factory: SessionFactory, exc: Exception):
    async with session_factory() as session:
        store = EchoStore(session)
        meta = await store.referral_meta(referral_id)
        if meta is not None:
            meta.analysis_error = f"{type(exc).__name__}: {exc}"[:500]
            await store.commit()


async def _submitted_provider(
    referral_id: str, session_factory: SessionFactory, provider: CandidateProvider
) -> CandidateProvider:
    async with session_factory() as session:
        meta = await EchoStore(session).referral_meta(referral_id)
    return PayerOverrideProvider(provider, meta.insurance) if meta and meta.insurance else provider


def _with_form_specialty(parsed: ParsedCase, specialty: str, subspecialty: str) -> ParsedCase:
    """The specialty (and subspecialty) the physician chose on the form are added to what the
    parser found; they are never removed or overridden. The keyword fallback only knows a few
    symptom words, so without this a case like "skin burns, redness" parses to no specialty at
    all and every specialist is filtered out, even though the physician said Dermatology."""
    specialties, tags = list(parsed.suggested_specialties), list(parsed.subspecialty_tags)
    added = []
    if specialty and specialty.lower() not in {x.lower() for x in specialties}:
        specialties.append(specialty)
        added.append(specialty)
    if subspecialty and subspecialty.lower() not in {x.lower() for x in tags}:
        tags.append(subspecialty.lower())
        added.append(subspecialty)
    if not added:
        return parsed
    return parsed.model_copy(
        update={
            "suggested_specialties": specialties,
            "subspecialty_tags": tags,
            "rationale": f"{parsed.rationale} Added from the referral form: {', '.join(added)}.",
        }
    )


async def start_match_run(referral_id: str, session_factory: SessionFactory) -> str:
    """Accept the parser's complexity if the physician hasn't set one, apply the form's specialty
    hint, and queue a match run. Done before the HTTP response so the analysis snapshot already
    shows the fresh attempt."""
    async with session_factory() as session:
        repo = Repository(session)
        ref = await repo.referral(referral_id)
        if ref is None or ref.parsed_case is None:
            raise RuntimeError("Case could not be parsed")
        meta = await EchoStore(session).referral_meta(referral_id)
        if meta is not None:
            ref.parsed_case = _with_form_specialty(
                ref.parsed_case, meta.specialty, meta.subspecialty
            )
            await repo.save_referral(ref)
        if ref.complexity is None:
            ref.complexity = ref.parsed_case.suggested_complexity
            await repo.save_referral(ref)
        return (await repo.create_match_run(referral_id)).id


async def run_matching(
    run_id: str,
    referral_id: str,
    session_factory: SessionFactory,
    analyzers: Analyzers,
    provider: CandidateProvider,
) -> None:
    """Run an already-queued match run. `jobs.run_match` records its own failure on the run."""
    try:
        provider = await _submitted_provider(referral_id, session_factory, provider)
        await jobs.run_match(run_id, session_factory, analyzers, provider)
    except Exception as exc:
        logger.exception("Matching failed for %s", referral_id)
        await _record_failure(referral_id, session_factory, exc)


async def run_pipeline(
    referral_id: str,
    session_factory: SessionFactory,
    analyzers: Analyzers,
    provider: CandidateProvider,
) -> None:
    """Parse, then match."""
    try:
        await jobs.run_parse(referral_id, session_factory, analyzers)
        run_id = await start_match_run(referral_id, session_factory)
    except Exception as exc:
        logger.exception("Analysis pipeline failed for %s", referral_id)
        await _record_failure(referral_id, session_factory, exc)
        return
    await run_matching(run_id, referral_id, session_factory, analyzers, provider)
