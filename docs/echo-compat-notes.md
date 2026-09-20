# ECHO backend compatibility layer

The frontend is built against `docs/echo-api-contract-changes.md` (`/api/echo/*`, camelCase). The backend
delivered in `echo-2026-09-19.zip` has its own contract (`openapi.json`, snake_case, no `/api` prefix, and a
different referral flow). Rather than change the frontend, `backend/app/echo/` serves the frontend's contract on
top of the backend's own domain. It adds no second source of truth; it reads referrals, match runs, slots, and
consult threads from the core and stores only what the core has no place for.

**Changes to the delivered backend are small and listed here.** Compatibility layer hooks: `app/main.py` (mounts the
router), `app/seed/__main__.py` (seeds two display facts), `app/config.py` (one setting), and `migrations/env.py` (so
Alembic sees the two new tables). Cleanup: `app/db/repository.py` (`book_slot` retry-safety, below) and
`app/export_openapi.py` (the spec now lives at `backend/openapi.json`). The core routes and models are otherwise
untouched, and the compatibility layer is hidden from the OpenAPI schema.

## Known contract reconciliation: complexity is auto-accepted

**Decision (frontend owner): keep this as is for now.** The backend's core API will not run matching until the
physician confirms a referral's `complexity` (`routine` or `rare_complex`); it returns 409 otherwise. The ECHO frontend has
no such step: the physician sets urgency on the New Referral form and nothing more. So the compatibility layer
**accepts the parser's `suggested_complexity` automatically** (Claude's when a key is set, otherwise the keyword
fallback's) and runs matching. Complexity only changes which weight profile the ranking uses, and it is what the core
uses to gate its own `/trials` endpoint (not applied here; see difference 14).

- **What it means:** on the ECHO screens the physician never sees or overrides the complexity the ranking used. Urgency
  is still theirs. Specialist choice, approval and booking remain fully theirs.
- **Where it lives:** `backend/app/echo/pipeline.py` (`start_match_run`). One line to change if that decision reverses.
- **Core API unaffected:** `PATCH /referrals/{id}` still lets a physician confirm or override complexity, and the core
  flow still requires it. A referral whose complexity was set that way keeps it; the layer only fills in a missing one.
- **If it should change later:** add a confirm-complexity step to the frontend, and have the layer wait for it instead
  of defaulting. The contract can't express that step today, which is why it is not done here.

## Run it locally

```bash
cd backend
uv sync
export DATABASE_URL=sqlite+aiosqlite:///./echo.db AUTH_MODE=dev      # no Docker needed
uv run alembic upgrade head && uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000

cd ../frontend && VITE_USE_MOCK=false npm run dev                    # proxies /api to :8000
```

**Auth for local integration.** The browser frontend sends no credentials. With `AUTH_MODE=dev`, a request to
`/api/echo/*` with no `X-Dev-Physician` header acts as `DEV_DEFAULT_PHYSICIAN` (default `doc_001`); send the header to
act as someone else, or set `DEV_DEFAULT_PHYSICIAN=` (empty) to require it. This applies **only** to `/api/echo/*` and
**only** in dev mode. With `AUTH_MODE=auth0` the layer requires a valid bearer token exactly like the core, and
the dev default and the dev-only endpoint below do nothing.

Without `ANTHROPIC_API_KEY` matching uses the keyword fallback (the run is marked `degraded` in the core; the
frontend contract has no field for that, so it is not shown).

## What is implemented

All of the contract, tested in `backend/tests/test_echo_api.py` (25 tests) and by driving the real frontend
against the real backend in Chrome (mock off): dashboard, New Referral, analysis, matches, select, approval and
booking, tracking, patient confirmation, consult (compose, waiting, responded, list), and trials.

| Endpoint | Backed by |
|---|---|
| `GET /api/echo/me`, `/patients`, `/referral-options`, `/colleagues` | physicians, patients, specialists, insurance-network tables |
| `GET/POST /api/echo/referrals`, `GET /referrals/{id}` | referrals + `echo_referral_meta` + match runs |
| `GET /referrals/{id}/analysis`, `POST .../analysis/retry` | parse result + latest match run |
| `GET /referrals/{id}/matches?distanceMiles&includePartial` | latest completed match run |
| `POST /referrals/{id}/select` | `echo_referral_meta` |
| `GET /specialists/{id}/slots`, `POST /referrals/{id}/approve` | slots, appointments, `DbBooker` |
| `GET /consults`, `GET/POST /referrals/{id}/consult`, `GET /colleagues` | consult threads and messages |
| `GET /referrals/{id}/trials`, `GET /referrals/{id}/trials/criteria` | the core's trial list + `trial_info.py` |
| `POST /referrals/{id}/patient-response` (**dev only**) | `echo_referral_meta` |

The layer is hidden from the OpenAPI schema (`include_in_schema=False`), so the core's `openapi.json` is unaffected.

## Where the two contracts differ, and what the layer does

Each of these is a choice for the backend owners to confirm or change.

1. **Complexity is accepted from the parser.** See "Known contract reconciliation" above.
2. **Analysis progress is coarse.** The core reports no per-check progress. The snapshot shows clinical fit while
   parsing, then the rest in progress until the run completes. On failure it marks the last check (or clinical
   fit if the case never parsed) as `error`; which step really broke isn't known.
3. **Analysis runs in-process** (FastAPI background task), even with `JOB_BACKEND=celery`. The core's Celery tasks
   are separate (parse and match); the layer's parse-then-match chain has no Celery version.
4. **Match strength is a label derived from the factors.** `strong` = excellent clinical fit and every factor met;
   `good` = good fit and every factor met; `partial` = at least one factor not met (each says which). The default list holds the
   matches with every factor met (including the preferred distance, which the core scores but never gates on), **and when
   there are none it shows the partial ones instead, so the page is never empty while the ranking found someone**; measured on the
   seed data, the strict list alone left 69% of patient/specialty combinations empty. `includePartial=true` always adds them.
   At most 3 are returned. `match_percent` is never exposed.
   **Opening the matches of a referral nobody has analyzed (such as the seeded demo ones), or whose analysis failed, analyzes it
   on the spot** (up to ~20 s with Claude) instead of failing with a 409.
5. **The `urgency` factor is derived** from the referral's urgency window (`URGENCY_WINDOW_DAYS`) and the earliest
   opening. The core has no such factor; results already outside the window are excluded (`too_late`).
6. **Approval accepts any open slot** of a specialist who is in the latest match results. The core's `/approve`
   only accepts each specialist's earliest slot; the frontend's Appointment select offers every open slot.
7. **Approving is retry-safe in this layer:** a slot the same referral already holds is reused, so a retry after
   a partial failure succeeds. The core bug it worked around is now fixed too (see "Resolved" below), so both paths are safe.
8. **`status` mapping:** booked with an appointment is `scheduled`; approved without one is `awaiting_patient`;
   everything else (draft, matched, waitlisted, cancelled) is `awaiting_approval`. `attention` is derived:
   analysis failed ("Retry analysis"), no default match ("Expand search"), or a booked referral with no patient
   response for 3+ days ("Contact patient").
9. **The timeline is derived** from what the core records (created, latest match run, approval, appointment) plus
   `selected_at` and the patient response. `sent_to_patient` is **only a recorded event at approval time. No
   message is sent to the patient by anything here.** Same as the mock, and still unverified (contract section 6).
10. **Patient confirmation has no real source.** No patient-facing flow exists. Status is `pending` until the
    dev-only `POST .../patient-response` sets it. In auth0 mode nothing can set it.
11. **The form's edited insurance is honored in matching; the edited location is not.** The core measures distance
    from the patient record's coordinates, and there is no geocoder, so `patientLocation` is stored and shown but
    does not move the distance calculation.
12. **Patient `sex` and `city` are seeded** into `echo_patient_meta` (the core patient has neither).
13. **Consult is a chat on core threads.** A conversation is a core consult thread between two physicians with any number of
    messages, optionally about one of the sender's referrals (a consult needs no referral). Status is derived: the last message is
    mine = `pending`, theirs = `responded`. The colleague answers through the existing `POST /consults/{id}/messages`. The
    colleague's view never carries the referral or the patient's name; `sharedContext` is age, sex, reason and summary only.
    Colleagues are the other physicians (only two are seeded). Live delivery over the WebSocket is best effort.
14. **Trials are served for any parsed referral.** The core only allows them for `rare_complex` cases (409
    otherwise); the frontend shows trials for every referral, so that gate is not applied here. Trial `status`,
    `intervention`, and site are added from `trial_info.py`, and distance is computed from the patient's
    coordinates. The trial list is 4 synthetic trials (rare neuromuscular, PAH, arrhythmia, neuropathy), so most
    referrals correctly show "No trials found". Their NCT ids are synthetic: **the ClinicalTrials.gov links do not
    resolve to real studies.**
15. **Referrals not created here** (the demo referrals) are described from their case notes and parsed case; the
    first time the frontend changes one (select, retry), a description row is recorded for it.
16. **Slot times** are generated in UTC by the core and shown here in Eastern time (`...-04:00`), so the demo slots
    appear at 5:00-5:30 AM. That is the seed generator's pattern, not a layer bug.
17. **Only the signed-in physician's referrals** are visible (404 for anyone else's), as in the core.
18. **The form's specialty is added to the parsed case.** The parser (especially the keyword fallback, used when
    there is no `ANTHROPIC_API_KEY`) may find no specialty in the notes ("skin burns, redness" contains none of its
    dermatology words), which filters out every specialist. The specialty and subspecialty the physician chose on the
    form are appended to `suggested_specialties` and `subspecialty_tags` (never removed or overridden), and the parse
    `rationale` says so. Retrying a referral's analysis re-applies it.
19. **Sign-in (`AUTH_MODE=session`).** A login page with email + password and one-click demo accounts; see the contract doc,
    section 9. Demo-grade on purpose. In this mode `SIMULATE_COLLEAGUE_REPLIES` and the dev-only patient-response endpoint are still
    allowed (both are synthetic-data demo features); neither exists with `AUTH_MODE=auth0`.

## Resolved backend/integration cleanup

### A. Booking retry-safety in the core (`HANDOFF.md`, request 1): fixed

`Repository.book_slot` commits the appointment first; the referral is then saved as booked in a separate step. If that
second step failed, the slot stayed taken while the referral was still `matched`, and a retry got **409** for a slot the
same referral already held. Now, if the slot is already held by **this same referral**, `book_slot` returns that
appointment instead of raising. This also covers two retries racing (the loser of the unique-constraint race re-reads the
winner). A different referral still gets `SlotUnavailableError` (409), and an unknown slot is still unavailable.
The frontend contract is unchanged. Tests: `backend/tests/test_booking_retry.py` (they fail without the fix). Not part of
this change: `HANDOFF.md` request 2 (round `distance_miles` to one decimal); the ECHO layer already rounds for its own shapes.

### B. Root CI, Docker, and config: reconciled with the new backend

- **`.github/workflows/ci.yml`:** the backend job now uses `uv` (`uv sync --frozen`, `uv run ruff check .`,
  `uv run pytest -q`) instead of `pip install -r requirements-dev.txt`, and checks `backend/openapi.json` is current.
  The frontend job is unchanged.
- **`docker-compose.yml`:** Postgres user/password/db are `echo`/`echo`/`echo`, matching the backend's default
  `DATABASE_URL`; adds health checks and a data volume.
- **`.env.example`:** removed by the team; settings live in `backend/.env` (git-ignored) and are defined in
  `backend/app/config.py`. The backend's default `AUTH_MODE` is `auth0`, so local runs must set `AUTH_MODE=dev`.
- **`README.md`:** rewritten for the ECHO app and how to run it.
- **Two OpenAPI files, on purpose.** The backend's spec is now `backend/openapi.json` (`app/export_openapi.py` writes
  there; `tests/test_contract.py` checks it). The **repo-root `openapi.json` is left as it was**, because it is the input
  of the frontend's `npm run gen:api`, whose output (`frontend/src/api/schema.d.ts`) CI diffs and whose legacy client
  (`src/api/client.ts`) imports types that exist only in that old spec. Replacing the root file would have required
  regenerating `schema.d.ts` and rewriting that client, i.e. changing `frontend/`, so it was not done. When the legacy
  client is retired, point `gen:api` at `../backend/openapi.json` and delete the root file.
- **Kept consistent by a test:** `backend/tests/test_repo_config.py` fails if the compose Postgres stops matching the
  default `DATABASE_URL`, if the two OpenAPI
  files get mixed up, or if the CI workflow stops referring to what exists.
- **Not verified here:** Docker isn't installed on the dev machine, so `docker-compose.yml` was checked for valid YAML and
  against the settings test, not run. The CI workflow was checked by running each of its backend and frontend commands
  locally, not on GitHub.

### C. Frontend-side notes (no frontend change was made)

- `useReferralRealtime` (`frontend/src/api/socket.ts`) still opens a Socket.IO connection to `/socket.io`; the new
  backend has none, so the browser console logs a stream of 404s. It is harmless (nothing depends on it) but noisy.
  The backend's live consult channel is a native WebSocket (`/ws/consults/{id}`), which the ECHO screens don't use.
- Nothing in the frontend contract was found to be impossible for the backend to support, so no frontend adapter
  is needed. The complexity behavior is documented above as a known reconciliation.
