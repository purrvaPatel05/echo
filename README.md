# ECHO

Physician-first referral navigation. A referring physician submits a case; ECHO reads it, finds and ranks
nearby specialists with the evidence behind each match, checks availability, and books only after the physician
approves. **Nothing is sent or booked without the physician's explicit approval.**

| Part | What it is |
|---|---|
| `backend/` | FastAPI + SQLAlchemy (async), Alembic migrations, Claude-based matching with a rules-only fallback, mock scheduling/insurance/trials, Auth0 or dev-header auth |
| `frontend/` | React + Vite + TypeScript, Tailwind v4, TanStack Query. Runs on an in-browser mock **or** the real backend. Design: violet, navy and mint with a heartbeat motif (Figma file "ECHO", page "ECHO — Final") |
| `deploy/` | Production deploy on one server: Docker Compose (Postgres + API + Caddy with automatic HTTPS). See [`deploy/README.md`](deploy/README.md) |
| `docs/` | The frontend's API contract, the compatibility notes, and the backend handoff/auth guides |

## Run it

The backend needs Python 3.12 and [`uv`](https://docs.astral.sh/uv/). Node 22 for the frontend.

```bash
# 1. Backend on :8000 (SQLite file, no Docker needed)
cd backend
uv sync
cat > .env <<'EOF'             # backend/.env: local settings (git-ignored); every option is in backend/app/config.py
DATABASE_URL=sqlite+aiosqlite:///./echo.db
AUTH_MODE=dev
EOF
uv run alembic upgrade head && uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000

# 2. Frontend on :5173 (proxies /api to :8000)
cd frontend
npm install
echo 'VITE_USE_MOCK=false' > .env   # frontend/.env: false = real backend, true (default) = in-browser mock
npm run dev
```

- **Mock or real:** with `VITE_USE_MOCK=true` the ECHO screens need no backend at all. With `false` they call the
  backend's `/api/echo/*` endpoints. Restart `npm run dev` after changing it.
- **Postgres instead of SQLite:** `docker compose up -d`, then in `backend/.env` use
  `DATABASE_URL=postgresql+asyncpg://echo:echo@localhost:5432/echo` (also the default if you set nothing).
- **Real Claude matching:** set `ANTHROPIC_API_KEY` in `backend/.env`. Without it a keyword fallback is used and results
  are less accurate. `GOOGLE_MAPS_API_KEY` is optional too (without it, distances are straight-line).
- **Sign-in page:** set `AUTH_MODE=session` with `SESSION_SECRET` and `DEMO_PASSWORD` (see `backend/.env.example`) and the app shows a login
  page; each demo doctor has their own referrals and conversations. Type the doctor's email (shown on the page, e.g.
  `elena.ruiz@riverside.example`) with the demo password, or, with `DEMO_ACCOUNT_LOGIN=true`, click a demo doctor. Mock mode and
  `AUTH_MODE=dev` have no login.
- **Login:** the backend defaults to `AUTH_MODE=auth0` and refuses requests until Auth0 is configured, so local runs set
  `AUTH_MODE=dev`, which needs no login (requests act as `DEV_DEFAULT_PHYSICIAN`, or the `X-Dev-Physician` header).
  `auth0` mode needs a real token; see [`docs/backend-handoff/AUTH.md`](docs/backend-handoff/AUTH.md).
- **Demo colleague replies:** `SIMULATE_COLLEAGUE_REPLIES=true` makes a colleague answer chat messages a few seconds later with a canned
  reply labelled "Demo reply". Demo only; refused with `AUTH_MODE=auth0`.
- Swagger UI for the core API is at http://localhost:8000/docs (hidden when `ENVIRONMENT=production`).

## Deploying

**One server with Docker** (tested on a Vultr Ubuntu VM): follow [`deploy/README.md`](deploy/README.md). `docker compose up -d --build`
in `deploy/` starts Postgres, the API and the website; Caddy serves the site, forwards `/api` to the API, and gets a free HTTPS
certificate for `SITE_ADDRESS` (a real domain, or `<ip-with-dashes>.sslip.io` until you have one). Real settings go in `deploy/.env`
(git-ignored; the template is `deploy/.env.example`). Production mode (`ENVIRONMENT=production`) refuses dev auth, SQLite,
default database credentials and `*` in CORS, and hides `/docs`.

- Sign-in for a public demo is `AUTH_MODE=session` (shared demo password, optional one-click demo doctors). It is demo-grade:
  tokens are not revocable and anyone with the address can use it. Real logins need `AUTH_MODE=auth0` (see
  [`docs/backend-handoff/AUTH.md`](docs/backend-handoff/AUTH.md)).
- With `ANTHROPIC_API_KEY` set, every referral spends Claude credits. Leave it empty to use the free keyword fallback.
- The Docker images were first built on the server, not in CI, and `vercel.json` (a separate Vercel attempt) is untested.

Older background, still accurate for its checks and known limitations: [`docs/deployment-readiness.md`](docs/deployment-readiness.md).
Every backend setting is documented in [`backend/.env.example`](backend/.env.example).

## How the pieces fit

The frontend was designed first, against [`docs/echo-api-contract-changes.md`](docs/echo-api-contract-changes.md)
(`/api/echo/*`, camelCase). The backend has its own core API (`/referrals`, `/consults`, ...). The **compatibility layer**
in `backend/app/echo/` serves the frontend's contract on top of the core domain, without changing the frontend.
Every place the two were reconciled is listed in [`docs/echo-compat-notes.md`](docs/echo-compat-notes.md), including the
one to know about: **complexity is auto-accepted from the parser's suggestion** because the frontend has no confirm step.

## The two OpenAPI files

| File | Describes | Used by |
|---|---|---|
| `backend/openapi.json` | The backend's core API (generated: `cd backend && uv run python -m app.export_openapi`) | Backend CI checks it is up to date |
| `openapi.json` (repo root) | The **old prototype API**, kept frozen | The frontend's `npm run gen:api` and its legacy client types (`frontend/src/api/schema.d.ts`); frontend CI checks those |

The `/api/echo/*` endpoints are documented in `docs/echo-api-contract-changes.md`, not in either OpenAPI file. When the
frontend's legacy client is retired, point `gen:api` at `../backend/openapi.json` and delete the root file.

## Tests

```bash
cd backend && uv run ruff check . && uv run pytest         # core API, migrations, the /api/echo contract, config checks
cd frontend && npm run lint && npm run build
```

CI (`.github/workflows/ci.yml`) runs both. The backend job also fails if `backend/openapi.json` is stale; the frontend job
fails if `src/api/schema.d.ts` no longer matches the root `openapi.json`.

## What is mocked

| Area | Status |
|---|---|
| Patients, specialists, calendars, insurance networks, clinical trials | Synthetic seed data (`backend/app/seed`, `backend/app/trials`). Trial NCT ids are made up, so their ClinicalTrials.gov links do not resolve |
| Distance | Straight-line, or Google Maps if a key is set |
| Case reading and specialist fit | Claude if a key is set, otherwise a keyword fallback |
| Patient notification and confirmation | **Not implemented.** "Sent to patient" is only a timeline event; a dev-only endpoint stands in for the patient's answer |
| Consult delivery | Messages are saved; live delivery over a WebSocket needs Redis and is best effort. In demo setups a simulated colleague replies (labelled "Demo reply") |
