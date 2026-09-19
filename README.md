# openEvidence

Mock referral app: physicians find and refer to specialists, get trial matches, and ping each other in real time.
Everything runs on in-memory fake data so the team shares one working baseline. Swap pieces for the real thing one seam at a time.

| Layer | Tech |
|---|---|
| Backend | FastAPI, python-socketio (WebSockets), Pydantic |
| Frontend | React + Vite + TypeScript, Tailwind v4, shadcn/ui-style components, TanStack Query, socket.io-client |
| Contract | `openapi.json` (generated from the FastAPI models) -> TS types via openapi-typescript |
| CI | GitHub Actions: ruff + pytest, oxlint + build, and checks that the generated spec/types are committed |

## Run it

```bash
# terminal 1 -- API + Socket.IO on :8000
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# terminal 2 -- UI on :5173 (proxies /api and /socket.io to :8000)
cd frontend
npm install
npm run dev
```

Swagger UI: http://localhost:8000/docs

## Try it

1. **Cases** -> open the seeded case: notes are parsed, specialists ranked, trials listed.
2. **Refer** -> the Referrals page shows `pending`, then flips to `accepted` about 4s later via a live socket push. Pick a slot to book.
3. **Consults** -> message a specialist; a canned reply comes back over the socket.

## Changing the API (contract-first workflow)

1. Edit the Pydantic models / routes in `backend/app`.
2. `cd backend && python -m app.export_openapi` -> updates `openapi.json`.
3. `cd frontend && npm run gen:api` -> updates `src/api/schema.d.ts`.
4. Commit all of it. CI fails if they drift.

Frontend never hand-writes API types; import them from `src/api/client.ts`.

## What's mocked, and where the real thing plugs in

| Mock | File | Real replacement |
|---|---|---|
| In-memory data | `backend/app/store.py` | SQLAlchemy + Vultr Managed PostgreSQL (`docker-compose.yml` has local Postgres/Redis) |
| Case parsing | `services/matching.py: parse_case` | Claude API |
| Specialist ranking | `services/matching.py: rank_specialists` | Claude for fit; keep `passes_guardrails` (rules layer) as-is |
| Trials | `services/matching.py: find_trials` | ClinicalTrials.gov API v2 |
| Distance | `services/matching.py: distance_km` | Google Maps Distance Matrix |
| Sync matching | `routers/api.py: match_case` | Celery task + job-status polling (see `useMatch` in `frontend/src/api/hooks.ts`) |
| Logged-in user | `store.CURRENT_USER`, `GET /api/me` | Auth0 / Firebase + role claims |
| Scheduling | `store.SLOTS` | Stays a Postgres table for MVP |
| Specialist accepting referral | `_mock_specialist_accepts` | Specialist-side UI calling `PATCH /referrals/{id}/status` |

## Adding shadcn components

`components.json` is configured, so `npx shadcn@latest add dialog` works. The few components already in `src/components/ui` are hand-copied in the same style.

## Tests

```bash
cd backend && pytest
cd frontend && npm run lint && npm run build
```
