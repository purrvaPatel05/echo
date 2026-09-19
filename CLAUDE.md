# ECHO — Claude Code Guide

ECHO is a hackathon platform for physician-to-specialist referrals. A referring physician submits a patient case; ECHO ranks the best-fit specialists nearby with transparent reasoning, checks availability, and books once the physician approves. For rare cases it also surfaces relevant clinical trials and lets physicians "ping" peers for a quick consult.

**Core principle: the physician stays in control at every step. Nothing is sent or booked without explicit physician approval.** Never build a code path that skips this.

## Who I am in this repo

I am acting as **Member 1 — Backend Core (Matching + Data)**. The repo was reset; earlier contents were scratch work and were removed (recoverable from git history at `d34f889` if needed).

### I own
- Database schema (PostgreSQL) and migrations
- Case / specialist / referral / appointment data models
- Mock data: physicians, specialists, patients, insurance, referrals, appointments
- The Claude-based matching engine (case notes → structured case → ranked specialists)
- The rules guardrail layer over Claude's output
- Final ranking logic that combines all five factors into what the physician sees
- The OpenAPI contract (written first — see below)

### I do NOT own (don't build these; consume their contract)
- **Member 2 — Frontend:** all React screens. They work against mock JSON that mirrors my endpoints.
- **Member 3 — Integrations:** peer consult/ping WebSockets, ClinicalTrials.gov integration, geolocation/distance, the mock scheduling service + booking/fallback logic, insurance/network verification.

My matching engine *calls* Member 3's distance, availability, and insurance functionality through the agreed interfaces. Until those exist, use stubs behind the same interface so nothing blocks. Don't reimplement their logic inside matching code.

## Tech stack (backend)

- Python + FastAPI (async throughout)
- PostgreSQL (Vultr Managed Database in deployment; local Postgres for dev)
- Redis + Celery (or RQ) for background jobs — matching runs must not block the API response
- Claude API for parsing case notes and ranking specialist fit
- Auth0 or Firebase Auth with roles: referring physician / specialist / admin
- GitHub Actions CI: lint + test on push

Hosting: Vultr Cloud Compute. Frontend is on Vercel/Netlify (not my concern).

## Contract-first workflow

The OpenAPI spec is written **before** backend logic. It is what lets three people work in parallel.

1. Change the Pydantic models / route signatures first and regenerate the spec.
2. Treat the committed spec as locked: breaking changes (renamed/removed fields, changed types) need a heads-up to Members 2 and 3 before merging. Additive changes are fine.
3. Every endpoint must be usable from Swagger UI with mock data alone — no dependency on the frontend or the consult feature.

## Matching design

Patient care is the priority, so matching is **gate first, then weight**: convenience factors may never buy back clinical quality.

Five factors, from the ECHO spec:

| Factor | Question | Data source |
|---|---|---|
| Clinical fit | Does specialty/subspecialty match the case? | Claude-parsed case + specialist profile |
| Insurance | What is the specialist's network status for the patient's plan? | Member 3's verification logic |
| Location | How far is the specialist from the patient? | Member 3's distance calc |
| Urgency | How fast must the patient be seen? | Referral priority: routine / soon / urgent — sets the availability window and shifts weights; not a separately scored factor |
| Availability | Earliest open appointment? | Member 3's scheduling service |

Pipeline: **parse case (Claude) → gates (rules) → score survivors → rank → explain.**

### Gates (pass/fail — failing candidates never appear in the ranked list)
- **Clinical fit** below a minimum threshold (single config value). Convenience can't rescue a poor clinical match.
- **Insurance** status is `not_accepted`.
- **Urgency window:** earliest slot is beyond the window for the referral priority. List these separately as "available but too late" rather than dropping them silently. Windows (starting values): urgent ≤ 3 days, soon ≤ 14 days, routine ≤ 60 days.

### Insurance is a status, not a boolean
Member 3's verification returns a status plus a detail string; it is scored, and only `not_accepted` is a gate.

| Status | Score | Shown to physician |
|---|---|---|
| `in_network` | 1.0 | ✓ In-network with <plan> |
| `unverified` | ~0.5 | ? Coverage unverified — confirm with plan |
| `out_of_network` | ~0.3 | ⚠ Out-of-network — patient may pay more |
| `not_accepted` | gated out | not shown in ranked list |

Rationale: patients skip specialists they can't afford, and for rare cases an out-of-network expert may still be the right referral — so out-of-network can rank high on strong clinical fit but always carries the warning. Mock data models network status only; real cost (deductibles, prior auth, referral requirements) is phase 2 and should be stated as such. The patient-facing summary must mention cost implications when status isn't `in_network`.

### Scoring (survivors only; each sub-score 0–1, weighted sum → match %)

| Factor | Routine (default) | Urgent | Rare / complex | Urgent + rare/complex |
|---|---|---|---|---|
| Clinical fit | 50% | 40% | 65% | 52.5% |
| Availability | 20% | 35% | 10% | 22.5% |
| Insurance | 15% | 10% | 10% | 10% |
| Distance | 15% | 15% | 15% | 15% |

Urgent + rare/complex is the average of the two profiles (user-approved). Only `urgent` switches the profile; `soon` scores like routine with a tighter window.

Weights, gate threshold, urgency windows, and score curves (e.g. distance 1.0 at 0–5 mi decaying to 0 at 50+ mi) are **starting guesses** with no clinical basis — keep them all in one config module, and have a physician sanity-check them before any real use. For the hackathon they just need to rank the seeded demo scenarios sensibly. Ties break on earlier appointment, then shorter distance.

### Rules for the matching layer
- **Rules are a guardrail, not a suggestion.** Claude proposes/ranks; plain Python conditionals enforce the gates. A Claude output can never override a gate.
- **Always return the reasoning.** Each recommendation carries a match percentage *and* per-factor detail (e.g. "✓ 8.4 miles away", "✓ Appointment available in 3 days"). Show clinical fit as its own line, separate from the overall score, so quality and convenience are visible apart. When a closer/sooner specialist ranks lower, include a "why not #1" note (e.g. "Closer, but weaker subspecialty match"). Never return a bare "best" specialist.
- **Deterministic scoring, LLM-assisted judgment.** Sub-scores and the weighted combination are plain Python so results are explainable and testable; Claude contributes the clinical-fit assessment and the natural-language explanation.
- **Fallbacks:** if the top match becomes unavailable, return the next-best; if none qualify, offer a waitlist. (Booking mechanics belong to Member 3; the ranked fallback list is mine.)
- **Claude failure must degrade gracefully.** If the API errors or times out, fall back to a rules-only keyword/specialty match and flag the response as such. The demo must not die on a network blip.
- Long-running matching runs go through the task queue; the API returns a job/status the frontend can poll.

### Decisions locked in (approved by the user)
- **Clinical fit is a tier, not a number.** Claude returns `excellent | good | partial | poor` plus a rationale; fixed scores 1.0 / 0.7 / 0.35; `poor` is the gate.
- **Rare/complex is Claude-suggested, physician-confirmed.** The parsed case carries `complexity` (`routine | rare_complex`); the physician can override before matching. It selects the weight profile and triggers trial lookup.
- **Sub-score curves are linear.** Distance: 1.0 at ≤5 mi → 0 at ≥50 mi. Availability: 1.0 same-day → 0 at the urgency-window edge. Insurance: in-network 1.0, unverified 0.5, out-of-network 0.3.
- **Urgent + rare/complex uses the average of the two weight profiles**; the urgency window still gates.
- **Claude supplies clinical-fit tiers + rationale only.** The explanation and "why not #1" text are built deterministically from the factor results (fewer Claude calls, fully testable).
- **Default model is `claude-opus-5`** (env `CLAUDE_MODEL`); the API is asked to use server-side refusal fallbacks (`CLAUDE_SERVER_FALLBACK`). This has **not been exercised against the live API** (no key in dev) -- only against a stub client. Check it first when a key is available.
- All of the above live in `backend/app/matching/config.py` (numbers) and `scoring.py` (pure functions).

## Dev setup and commands

Python is managed with [uv](https://docs.astral.sh/uv/) (Python 3.12, pinned in `backend/.python-version`). From `backend/`:

```bash
uv sync                                   # create .venv and install deps
uv run pytest -q                          # tests (in-memory SQLite; no Docker/Redis/Claude needed)
uv run ruff check --fix . && uv run ruff format .
uv run python -m app.export_openapi       # regenerate ../openapi.json after any model/route change

# run the API against a local DB (SQLite needs no Docker; or `docker compose up -d` for Postgres+Redis)
export DATABASE_URL=sqlite+aiosqlite:///./echo.db      # default is Postgres, see .env.example
uv run alembic upgrade head && uv run python -m app.seed
uv run uvicorn app.main:app --reload      # API on :8000, Swagger at /docs

# optional background worker (set JOB_BACKEND=celery on the API; needs Redis)
uv run celery -A app.celery_app worker
```

Without `ANTHROPIC_API_KEY`, matching runs rules-only and every match run is flagged `degraded`.
Schema changes: edit `app/db/models.py`, then `uv run alembic revision --autogenerate -m "..."`; a test fails if models and migrations drift.

## Data and safety

- **All data is synthetic.** Providers, schedules, appointments, patients, and insurance are mock data for the hackathon. Never put real patient data (PHI) in the repo, fixtures, logs, or prompts.
- Keep mock data realistic enough to exercise every branch: multiple specialties/subspecialties, all four insurance statuses, varied distances, sparse vs. open calendars, and at least one rare-condition case that triggers the trial pathway.
- Seed 4–5 demo scenarios that pin expected ranking behavior (and back them with tests), e.g.: rare condition with a distant expert who should still rank high; urgent case where a nearby, sooner specialist beats a slightly better fit; out-of-network expert surfaced with a warning; specialist gated out for poor clinical fit despite being closest.
- Referral state changes must record who approved and when. Status flow: `draft → matched → approved → booked` (plus `waitlisted` / `cancelled`); transitions to `approved`/`booked` require a physician action.
- Secrets (Claude API key, DB URL, Auth keys) come from environment variables. Commit a `.env.example`, never `.env`. Don't hard-code a model ID — read it from config.

## Code conventions

- Python 3.11+, type hints everywhere, Pydantic models for all request/response shapes.
- Async endpoints and DB access; no blocking calls in the request path.
- Keep routes thin: routers → service layer (matching, referrals) → data layer. Matching logic must be importable and testable without running the server.
- Tests with pytest. Prioritize: hard-filter guardrails, urgency/availability interaction, ranking order on the mock dataset, and the Claude-failure fallback (mock the Claude client — tests must not hit the network).
- Lint with ruff; CI runs lint + tests on every push.
- Match the style of surrounding code; keep comments for non-obvious *why*.

## Layout (`backend/`)

```
app/
  main.py, config.py, deps.py     # app, env Settings, dependency providers
  models/                         # Pydantic schemas = the contract (enums, people, referral, match, scheduling)
  routers/                        # thin HTTP layer: referrals, directory
  services/referrals.py           # referral rules: confirm, approve (only path that approves/books), waitlist, summary
  matching/                       # config.py (all tunables), scoring.py, ranking.py (gate->score->rank->explain),
                                  #   types.py (Candidate + CaseAnalyzer/CandidateProvider protocols),
                                  #   claude_analyzer.py, rules_analyzer.py (fallback), service.py (degradation)
  db/                             # SQLAlchemy tables, session, Repository (returns Pydantic models)
  jobs.py, celery_app.py          # parse/match jobs: inline BackgroundTasks or Celery
  booking.py                      # Booker seam for Member 3 (nothing implements it yet)
  seed/                           # data.py (synthetic people + demo cases), fixtures.py (PLACEHOLDER logistics), __main__.py
migrations/                       # Alembic
tests/                            # scenarios.py pins demo rankings; test_contract.py fails if openapi.json is stale
../openapi.json                   # committed contract
```

### Seams where Member 3's work plugs in (I do not build these)
- `matching.types.CandidateProvider` -- distance, insurance status and earliest slot per specialist. Today `seed/fixtures.py: FixtureCandidateProvider` supplies **hand-typed placeholder values**; swap it in `deps.build_candidate_provider`.
- `booking.Booker` -- booking + slot-taken handling (`SlotUnavailableError` -> 409). Until one is provided via `deps.get_booker`, approving records the approval (`approved`) but books nothing.
- Trials (ClinicalTrials.gov) and consult/ping WebSockets are not in this API yet.

Still to build: auth (Auth0 vs Firebase undecided; `referring_physician_id` is passed in the body meanwhile), Postgres verification (only SQLite has been run so far), Redis/Celery verification.

## Out of scope (don't build unless asked)

- Real EHR/FHIR scheduling (phase 2)
- ElevenLabs voice input (optional stretch, frontend-side)
- Frontend, WebSocket consult, ClinicalTrials.gov, distance, scheduling internals (Members 2 and 3)
