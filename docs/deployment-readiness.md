# Deployment readiness (audit, 2026-09-19)

Status: **YELLOW.** Deployable as a hackathon demo behind a reverse proxy, with the limitations below. It is **not** ready
for real multi-user production, because the approved frontend cannot log in (see 1). Nothing has been deployed.

## What must be true at deploy time

| # | Requirement | Where |
|---|---|---|
| 1 | Build the frontend with `VITE_USE_MOCK=false` **set on the hosting platform**. Without it the site ships the in-browser mock and never calls the backend (verified: 0 real API paths in a bundle built without it). `frontend/.env` is git-ignored, so a host does not have it | host build settings |
| 2 | Site and `/api/*` on **one origin**. The frontend calls a relative `/api/...` (no base-URL setting), so a separate API host cannot work without a source change | reverse proxy |
| 3 | `ENVIRONMENT=production` on the backend. It then refuses `AUTH_MODE=dev`, SQLite, default database credentials, `*` in CORS, and hides `/docs` | backend env |
| 4 | `AUTH_MODE=demo` + `DEMO_ACCESS_TOKEN` (>= 24 random chars) on the backend; the proxy adds `X-Demo-Access: <token>` to every `/api` request | backend env, proxy |
| 5 | `DATABASE_URL=postgresql+asyncpg://USER:PASS@HOST:5432/DB?ssl=require` (managed Postgres needs TLS; asyncpg does not accept `sslmode=`) | backend env |
| 6 | Run `uv run alembic upgrade head && uv run python -m app.seed` once, and re-run the seed at least every ~8 weeks (appointment slots are generated 9 weeks ahead) | deploy step |
| 7 | Run the API as `uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers` (no `--reload`), only reachable through the proxy | process manager |

Every backend variable is documented in `backend/.env.example` (a test keeps it matching `app/config.py`).

## Authentication: how it works in the cloud

- **Real logins (`AUTH_MODE=auth0`) do not work with the current frontend.** The frontend never sends a credential (no
  `Authorization` header, no token storage, no login screen; confirmed by searching all of `frontend/src`). Auth0 mode returns 401
  to every browser request. Using it needs a frontend change (login, token, API base URL), which is out of scope.
- **`AUTH_MODE=dev` is never for a public host.** It trusts a client-supplied `X-Dev-Physician` header, so anyone can act as any
  physician. With `ENVIRONMENT=production` the backend refuses to start in this mode.
- **`AUTH_MODE=demo` is the explicit, temporary alternative.** Only `/api/echo/*` works, and only with the correct
  `X-Demo-Access` header (constant-time compared); everyone acts as `DEMO_PHYSICIAN_ID`. A client cannot choose an identity
  (`X-Dev-Physician` is ignored). The core API (`/referrals`, `/patients`, `/consults`, ...) stays closed (401/503). Verified over
  real HTTP.
- The dev-only patient-response endpoint (`POST /api/echo/referrals/{id}/patient-response`) is also available in demo mode,
  behind the token, so a demo operator can show Confirmed/Declined with `curl`.

## Update: `AUTH_MODE=session` (login page) is now the simpler public-demo mode

The frontend now has a login page, so it *can* send a credential. With `AUTH_MODE=session` (`SESSION_SECRET`, `DEMO_PASSWORD`,
optionally `DEMO_ACCOUNT_LOGIN=true`) each demo doctor signs in and has their own data, and **no proxy has to inject a secret
header**: the token comes from the browser. That removes the Netlify-header and single-VM-proxy constraints below; any host that
serves the site and forwards `/api/*` to the backend works, including Vercel. It is still demo-grade (shared password, tokens
not revocable), and with `DEMO_ACCOUNT_LOGIN=true` anyone who reaches the page can enter as any demo doctor. Not re-verified
for deployment; the sections below describe the earlier `demo` mode and still apply to it.

## Proposed hosting configuration (NOT applied; untested: Caddy is not installed here)

One VM (for example Vultr Cloud Compute), Caddy in front, managed PostgreSQL. `X-Demo-Access` is added by the proxy, so the
token never reaches the browser.

```caddy
{$SITE_ADDRESS} {
	encode gzip

	# Optional but recommended for a public demo: password-gate the whole site (Claude credits are spent per referral).
	# basic_auth {
	#     demo {$DEMO_BASIC_AUTH_HASH}     # generate with: caddy hash-password
	# }

	handle /api/* {
		reverse_proxy 127.0.0.1:8000 {
			header_up X-Demo-Access {$DEMO_ACCESS_TOKEN}
		}
	}
	# The frontend still opens a Socket.IO connection the backend does not have; answer it cheaply.
	handle /socket.io/* {
		respond 404
	}
	handle {
		root * /srv/echo/dist          # `npm run build` output, built with VITE_USE_MOCK=false
		try_files {path} /index.html   # deep links such as /referral/ref_1/matches
		file_server
	}
}
```

Netlify can replace Caddy for the front half: it can forward `/api/*` to the backend and add the secret header to those requests
(per its documentation; not tried here), for example in `netlify.toml`:

```toml
[[redirects]]
from = "/api/*"
to = "https://YOUR-BACKEND-HOST/api/:splat"
status = 200
force = true
headers = {X-Demo-Access = "THE-DEMO-ACCESS-TOKEN"}
```

Proxied requests time out after 26 seconds (the frontend's requests are short, so this should be fine). The backend still needs a
host. Vercel can forward `/api/*` too, but its documentation does not show a way to add a header to the forwarded request, so it
does not fit demo mode as written. Either way the frontend needs `/socket.io/*` to return 404 rather than the SPA fallback page.

Frontend build variable to set on the host (replaces the removed `frontend/.env.example`, which was not recreated because
`frontend/` is frozen):

```
VITE_USE_MOCK=false
```

## Verified, and how

| Item | Result |
|---|---|
| Migrations on **real PostgreSQL 16.2** (embedded server, no Docker) | all 5 apply; `alembic check` clean; seed idempotent; downgrade/upgrade round trip |
| Full app flow on PostgreSQL over HTTP (create, analysis, matches, select, approve, retry, taken slot 409, patient response, consult, trials) | 14/14 |
| Demo auth over real HTTP on PostgreSQL | no/wrong token 401; spoofed identity ignored; core API closed; only `/health` open |
| CORS | allowed origin echoed; other origins get no header |
| Production refuses unsafe config | dev auth, SQLite, default credentials, missing Auth0 settings: refused. A safe demo config starts with `/docs` hidden |
| Secrets | the real Anthropic key is in no file git could publish and not in git history; `.env` files are git-ignored |
| Google Maps | not required anywhere; straight-line distance is used without a key |

## Not verified / known limitations

- **Docker was not run.** There is **no Dockerfile** for the backend or frontend; `docker-compose.yml` only defines local Postgres
  and Redis. Deploying with containers needs a Dockerfile first. Once Docker is available, test: `docker compose config`,
  `up -d`, both health checks reaching "healthy", `alembic upgrade head` against it, data surviving `down`/`up`. Ports are now
  bound to `127.0.0.1` (they were open on every interface with a public password).
- **GitHub Actions has not run.** The repository is private, `gh` is not installed and no token is available, so no run could be
  read or triggered. The steps were run locally one by one, but the workflow itself is unverified.
- **TLS to a managed Postgres** (`?ssl=require`) was not exercised; the embedded test server has no TLS.
- **The proxy config above is untested** (no Caddy here).
- **Demo mode is one shared identity** with no rate limiting: anyone with access sees all demo data and can spend Claude credits.
  Gate the site (Basic auth above) and set a spending limit on the Anthropic key.
- **An analysis interrupted by a restart never finishes.** It runs inside the API process; if the process restarts mid-analysis the
  referral shows "running" forever (Try again only appears on failure). Do not deploy mid-demo; a fix needs a start timestamp.
- **In demo mode a colleague cannot reply** (the reply route is a core endpoint, which stays closed), so consults stay "Awaiting
  response".
- Trial NCT links are synthetic and do not resolve; only 4 synthetic trials exist. Slot times are generated in UTC (about 5 AM
  Eastern). `/health` does not check the database.
- The full test suites, lint, migrations, frontend checks and the live browser test were **not re-run after today's changes**
  (by instruction). Only the new tests (25) were run. Re-run everything before deploying.
