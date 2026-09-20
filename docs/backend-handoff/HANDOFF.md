# ECHO API handoff

Everything here was checked against the running backend (real Claude, real database, real booking) on 2026-09-19. All data is synthetic.

The source of truth is [`backend/openapi.json`](../../backend/openapi.json). This guide explains the flow and the rules the UI has to respect. Swagger UI is at `http://localhost:8000/docs`.

## 1. Run the backend locally

```bash
cd backend
uv sync
export DATABASE_URL=sqlite+aiosqlite:///./echo.db      # no Docker needed
uv run alembic upgrade head && uv run python -m app.seed
uv run uvicorn app.main:app --reload                   # http://localhost:8000
```

- Put `ANTHROPIC_API_KEY=...` in `backend/.env` for real Claude analysis. Without it everything still works, but matching uses the keyword fallback and every match run comes back with `degraded: true`.
- Re-running the seed is safe. It tops up appointment slots relative to today, so re-run it if the demo dates go stale.
- Seeded people: physicians `doc_001`..`doc_003`, patients `pat_001`..`pat_006`. Demo referrals: `ref_demo_knee`, `ref_demo_rare_neuro`, `ref_demo_urgent_chest`, `ref_demo_rare_pulm`, `ref_demo_derm`, `ref_demo_thyroid`.
- CORS allows `http://localhost:5173` (Vite). For another origin set `CORS_ORIGINS='["https://your-site"]'`.

## 2. Frontend setup notes (the old `frontend/` is stale)

- The old scratch frontend targets the old mock API. Regenerate types with `npm run gen:api` (today it reads the repo-root `openapi.json`, the old prototype API; see the root README).
- The new API has **no `/api` prefix**. Call `http://localhost:8000/referrals`, or point the Vite proxy at the root.
- Live consult uses a **native WebSocket**, not Socket.IO: `ws://localhost:8000/ws/consults/{physician_id}?token=<access token>` (dev mode: `?dev_physician=doc_001`). Each frame is one `ConsultMessage` as JSON. Remove the `socket.io` proxy/client.
- **Login:** the API now requires authentication; see [AUTH.md](AUTH.md). Send `Authorization: Bearer <Auth0 access token>`. For local work without an Auth0 tenant, run the backend with `AUTH_MODE=dev` and send `X-Dev-Physician: doc_001` instead (the app can offer a "sign in as" picker from `GET /physicians` in that mode).
- You **don't need to send** `referring_physician_id`, `approved_by`, `from_physician_id`, `sender_physician_id` or the `physician_id` query parameter any more: the server uses the signed-in physician. If you do send one, it must match, or you get 403.
- `GET /referrals` returns only the signed-in physician's referrals. Another physician's referral returns 404.

## 3. The referral flow, screen by screen

| Screen | Calls |
|---|---|
| Dashboard | `GET /referrals` (each has a `status`) |
| New referral | `GET /patients`, then `POST /referrals` |
| Case review | `POST /referrals/{id}/parse` → **202**, then poll `GET /referrals/{id}` until `parsed_case` is set |
| Confirm | `PATCH /referrals/{id}` with `{urgency, complexity}` (the physician confirms or overrides Claude's suggestions) |
| Match results | `POST /referrals/{id}/match` → **202**, then poll `GET /referrals/{id}/match` until `status` is `complete` or `failed` |
| Approve | `POST /referrals/{id}/approve` |
| Waitlist | `POST /referrals/{id}/waitlist` |
| Patient view | `GET /referrals/{id}/patient-summary` |
| Trials | `GET /referrals/{id}/trials`, then `POST /referrals/{id}/trials/{trial_id}/approve` |
| Consult | `GET/POST /consults`, `GET/POST /consults/{thread_id}/messages`, plus the WebSocket |

Poll every 1–2 seconds. Parsing and matching take a few seconds with real Claude.

**Referral status:** `draft → matched → approved → booked`, or `matched → waitlisted → (re-match) → matched`. Editing urgency or complexity after a match sends the referral back to `draft`, and the old match can no longer be approved.

## 4. Showing match results

`GET /referrals/{id}/match` returns a `MatchRun`. Real example of `results[0]` (trimmed):

```json
{
  "rank": 1,
  "specialist": { "id": "sp_chen", "name": "Dr. Sarah Chen", "specialty": "Orthopedics", "practice_name": "Charles River Orthopedics" },
  "match_percent": 99,
  "clinical_fit": { "tier": "excellent", "rationale": "Orthopedic surgeon with knee and sports medicine focus directly matches progressive knee osteoarthritis..." },
  "insurance": { "status": "in_network", "detail": "In-network with Aetna PPO Choice" },
  "distance_miles": 0.717,
  "earliest_slot": { "id": "slot_sp_chen_20260921T0900", "start": "2026-09-21T09:00:00Z", "end": "2026-09-21T09:30:00Z" },
  "days_until_slot": 2,
  "factors": [
    { "factor": "clinical_fit", "verdict": "good", "score": 1.0, "weight": 0.5, "detail": "Excellent clinical fit" },
    { "factor": "distance", "verdict": "good", "score": 1.0, "weight": 0.15, "detail": "0.7 miles away" }
  ],
  "explanation": "Excellent clinical fit: ... In-network with Aetna PPO Choice; 0.7 miles away; appointment available in 2 days.",
  "why_not_first": null
}
```

Rendering rules:

- **Factor lines:** render each `factors[]` entry as ✓ (`good`), ⚠ (`caution`) or ? (`unknown`) plus its `detail`. Insurance is the one that can be `unknown` (coverage unverified).
- **Clinical fit is its own line,** separate from `match_percent`. Show `clinical_fit.tier` and `rationale` prominently.
- **At most 5 results** are returned (weaker matches are dropped), so the list never needs paging.
- **`why_not_first`** is null for rank 1. For the others, show it as the tradeoff, e.g. "Closer, but weaker clinical fit".
- **Out-of-network** (`insurance.status: "out_of_network"`) needs a visible warning, not just an icon.
- **`too_late`** lists specialists who fit but whose earliest slot is outside the urgency window. Show them in a separate "available but too late" section.
- **`degraded: true`** means Claude wasn't available and the keyword fallback ran. Show a banner asking the physician to review carefully.
- **`weight_profile`** says which scoring profile applied (`routine`, `urgent`, `rare_complex`, `urgent_rare_complex`). Optional detail for an explanation screen.
- **Format numbers in the UI:** `distance_miles` has many decimals, so show one. `start` times are UTC.
- **`parsed_case.red_flags`:** when it is non-empty, show an alert. A real example is chest pain with ST changes. That patient may need emergency care, not a specialist appointment within 3 days. The API does not do this for you.
- **Claude only suggests:** `parsed_case.suggested_urgency` and `suggested_complexity` are suggestions. Show them, and let the physician confirm or change them before matching. Matching returns 409 until `complexity` is confirmed.

## 5. Approval rules and errors

Nothing is booked until the referring physician approves. `POST /referrals/{id}/approve` body:

```json
{ "match_run_id": "match_…", "specialist_id": "sp_chen", "slot_id": "slot_sp_chen_20260921T0900", "approved_by": "doc_001" }
```

| Code | Meaning | What to do |
|---|---|---|
| 200 | Approved and booked. `status: "booked"`, `appointment` is filled in | Show confirmation |
| 403 | You are not the referring physician, or a body id doesn't match your login | Show an error |
| 401 | Not signed in or token expired | Send the user to login |
| 409 | Stale match run, referral not in `matched`, or the slot was just taken | Re-run matching and let the physician choose again |
| 422 | Specialist or slot was not in the match results | Bug in the client |

Only the earliest slot per specialist is offered.

## 6. Patient view and trials

- `GET /referrals/{id}/patient-summary` returns plain-language `summary`, `appointment`, and `cost_note`. Show `cost_note` whenever it is non-null (out-of-network or unverified coverage). Until a specialist is approved it returns a generic "your doctor is reviewing" message.
- Trials apply only when the physician has confirmed `complexity: "rare_complex"`. On any other case `GET /referrals/{id}/trials` returns 409. Trial data is **mock data**, matched by keyword.
- The patient only sees a trial (`trial_note`) after the physician approves it **and** approves the specialist referral.

## 7. Consult (physician-to-physician)

- `POST /consults` `{from_physician_id, to_physician_id, referral_id?, body}` starts a thread and sends the first message.
- `GET /consults?physician_id=…` lists a physician's threads, with `unread_count` and `last_message`.
- Messages are always saved first, so a thread survives a disconnect. The WebSocket only adds live delivery, and it needs Redis running. Without Redis, messages still arrive when the recipient reloads the thread.

## 8. Known limits

- Any signed-in physician can list all patients (no patient-to-physician assignment in the data model yet). There is no patient login and the specialist role has no access; see [AUTH.md](AUTH.md).
- Distance is a straight-line estimate unless a Google Maps key is configured.
- Trials and insurance networks are mock data. Appointment slots are generated from a weekly pattern.

---

## Requests for Member 3

1. **Make booking safe to retry.** Booking commits before the referral is marked booked, in a separate step. If that second step fails, the slot stays taken but the referral shows as unbooked, and a retry gets a 409 for a slot already booked by the same referral. Suggested fix: in `book_slot`, if an appointment already exists for that slot **and** that `referral_id`, return it instead of raising `SlotUnavailableError`.
2. **Round `distance_miles`** in the candidate provider (one decimal). Right now the API returns the raw float.
3. **Consult identity:** done on the backend (identity now comes from the login). Please review the changes to `routers/consult.py` and `models/consult.py`, and the new `tests/test_auth.py` consult and WebSocket cases.
