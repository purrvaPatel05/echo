# ECHO frontend → backend contract changes

The ECHO frontend (Member 2) is built against these shapes today using an in-browser mock
(`frontend/src/mock/`). To switch to the real backend, set `VITE_USE_MOCK=false` in `frontend/.env`
and implement the endpoints below. The TypeScript shapes live in `frontend/src/echo/types.ts`; the
HTTP calls are in `frontend/src/echo/http.ts`. These endpoints are documented here, not in an OpenAPI file:
the backend serves them from a hidden router, so neither `openapi.json` describes them.

> **Backend status:** this contract is now served by `backend/app/echo/` on top of the delivered backend
> (`docs/echo-compat-notes.md` lists every place the two contracts were reconciled, how to run it with the dev
> header, and the items flagged for the backend/integration side). Sections below that say "not verified on the real
> backend" were checked against it with the mock off; the exceptions are called out in that file.

## 1. Urgency has three levels: `routine | soon | urgent`  (needs Member 1)

The product uses three urgency levels. The current API (`Urgency` in `backend/app/models.py`) is
`routine | urgent | emergent`.

**Requested change:** replace it with `routine | soon | urgent`. Do not map `soon` onto `emergent`.
Matching should treat `soon` as sooner than routine and `urgent` as earliest available.

## 2. New Referral submits more than `POST /api/cases` accepts today

The New Referral form maps to the current contract like this:

| Form field | Today (`CaseCreate`) | Status |
|---|---|---|
| Referral reason | `title` | exists |
| Symptoms and history | `notes` | exists |
| Patient (a record) | `patient_age`, `patient_sex` | partially: needs a patient id |
| Urgency | `urgency` | needs change #1 |
| Patient location | not in contract | **new** |
| Insurance | not in contract | **new** |
| Specialty (suspected) | not in contract | **new** (hint for the matcher; `ParsedCase.specialty` is still derived from the notes) |
| Subspecialty (optional) | not in contract | **new** |
| Preferred travel distance (miles) | not in contract | **new** (the API currently returns `distance_km`; the UI shows miles) |

## 3. Proposed endpoints (paths used by `httpEchoApi`)

| Method | Path | Returns | Notes |
|---|---|---|---|
| GET | `/api/echo/me` | `Physician` | id, name, specialty, organization |
| GET | `/api/echo/patients` | `Patient[]` | id, name, age, sex, insurance, location. Patients are selectable records, not free text. |
| GET | `/api/echo/referral-options` | `ReferralOptions` | `specialties[{name, subspecialties[]}]`, `insurers[]`, `distancesMiles[]` |
| GET | `/api/echo/referrals` | `Referral[]` | includes `patient`, `reason`, `details`, `preferredDistanceMiles`, `urgency`, `status`, `attention`, `timeline` |
| POST | `/api/echo/referrals` | `Referral` | body `NewReferralInput` (below) |

`NewReferralInput`:

```json
{
  "patientId": "p_1",
  "patientLocation": "Roanoke, VA",
  "insurance": "Blue Cross Blue Shield",
  "specialty": "Orthopedics",
  "subspecialty": "Knee",
  "preferredDistanceMiles": 25,
  "urgency": "soon",
  "reason": "Knee pain, suspected meniscal tear",
  "details": "Right knee pain for 6 weeks after a twisting injury..."
}
```

- `patientLocation` and `insurance` are prefilled from the patient record but the physician can edit them per
  referral, so the referral should store the submitted values (a snapshot), not just the patient id.
- `subspecialty` is `null` when the physician chooses "Any subspecialty".

## 4. Analysis (after Find Specialist Matches)

**Referral saved when analysis begins — mock-confirmed, backend behavior to verify.** In the mock, submitting the
form creates the referral immediately (it then appears on the dashboard as "Awaiting your approval") and the analysis
runs against it. The Analysis screen's copy ("Your referral is saved to the dashboard") relies on this. Please confirm
the real backend does the same (create the referral first, then match).

The UI polls a snapshot and never assumes how long the backend takes:

| Method | Path | Returns |
|---|---|---|
| GET | `/api/echo/referrals/{id}` | `Referral` (404 if unknown) |
| GET | `/api/echo/referrals/{id}/analysis` | `Analysis` |
| POST | `/api/echo/referrals/{id}/analysis/retry` | `Analysis` (fresh snapshot after a failure) |

```json
{
  "referralId": "ref_100",
  "status": "running",            // running | complete | error
  "checks": [                       // in display order
    { "key": "clinical_fit", "state": "done" },
    { "key": "insurance",    "state": "done" },
    { "key": "distance",     "state": "active" },
    { "key": "urgency",      "state": "waiting" },
    { "key": "availability", "state": "waiting" }
  ],
  "matchCount": null                // number once status is "complete"
}
```

- `key`: `clinical_fit | insurance | distance | urgency | availability`.
- `state`: `done | active | waiting | error`. A check in `error` makes `status` `error`; the UI shows which check
  failed and offers Try again, which calls the retry endpoint.
- The frontend polls (about every 0.7s) while `status` is `running` and stops on `complete` or `error`. Server-sent
  events or a websocket push could replace polling later without UI changes beyond the hook.
- `matchCount` drives "N specialist matches are ready". The match list itself comes with the Specialist Matches screen.
- Mock only: adding `?mock=error` to the New Referral or Analysis URL makes the first attempt fail on the last check.

## 5. Specialist matches

Today (`SpecialistMatch` in `backend/app/models.py`, from `POST /api/cases/{id}/match`) a match is:
`specialist`, a 0-1 `score`, `distance_km`, one free-text `rationale`, and `next_slot`. The screen needs per-factor
evidence and shows a label, not a number, so this needs changes.

| Endpoint | Returns |
|---|---|
| `GET /api/echo/referrals/{id}/matches` | `MatchesResult` |
| `GET /api/echo/referrals/{id}/matches?distanceMiles=50` | same, using a wider preferred distance ("Expand the travel distance") |
| `GET /api/echo/referrals/{id}/matches?includePartial=true` | same, also including specialists who meet most but not all criteria ("Show partial matches") |

```json
{
  "referralId": "ref_100",
  "searchDistanceMiles": 25,
  "noMatchReason": null,               // string when matches is empty
  "matches": [                          // 0-3, already ordered by the matching logic
    {
      "specialist": { "id": "sp_chen", "name": "Dr. Sarah Chen", "specialty": "Orthopedics",
                      "subspecialty": "Knee", "organization": "Carilion Orthopedics", "city": "Roanoke, VA" },
      "distanceMiles": 8.4,
      "strength": "strong",            // strong | good | partial  (a label; never shown as a number)
      "factors": [                      // in display order
        { "key": "clinical_fit", "status": "met",     "detail": "Knee subspecialty" },
        { "key": "insurance",    "status": "met",     "detail": "Accepted" },
        { "key": "distance",     "status": "met",     "detail": "8.4 miles" },
        { "key": "availability", "status": "met",     "detail": "Tue, Sep 22 · 10:30 AM (3 days)" },
        { "key": "urgency",      "status": "met",     "detail": "Within timeframe" }
      ],
      "why": "Strong clinical fit; earliest opening in 3 days, 8.4 miles away.",
      "nextSlot": { "id": "slot_1", "startsAt": "2026-09-22T10:30:00-04:00" }
    }
  ]
}
```

Changes from today, for Member 1:

| Needed | Today | Change |
|---|---|---|
| Per-factor evidence | none | `factors[]`: `key` (`clinical_fit`, `insurance`, `distance`, `availability`, `urgency`), `status` (`met`, `partial`, `unmet`), `detail` (short factual text) |
| Strength label | numeric `score` | `strength`: `strong`, `good` or `partial`. Keep `score` internal; the UI never shows a number. |
| "Why this match?" | `rationale` | Keep as `why`: **one short, evidence-based, neutral sentence** that states facts and never says what the physician should accept or trade off. Example: "Strong clinical fit; earliest opening in 2 days, 64.8 miles away." |
| Insurance acceptance | none | A `factors[]` entry; needs each specialist's accepted plans |
| Distance in miles | `distance_km` | `distanceMiles` (number) on the match; the distance factor `detail` is short, e.g. "64.8 miles · over 25-mile preference" |
| Urgency relevance | none | A `factors[]` entry; needs the `soon` urgency level (section 1) |
| Availability | `next_slot` | Keep as `nextSlot` (`{ id, startsAt }`); the "(in N days)" wording lives in the availability `detail` |
| No matches | none | `matches: []` plus `noMatchReason` |
| Widen distance / include partial | none | The two query parameters above |
| Match list per referral | only `POST /cases/{id}/match` | New `GET` endpoint above |

- Ordering is the backend's: the UI shows matches left to right in the order returned and adds no "Recommended" marker.
- Nothing is booked by this screen. Selecting a specialist only carries `specialist id` to the approval screen.
- Mock only, on the Matches URL: `?mock=no-matches` (nothing qualifies until "Show partial matches") and
  `?mock=matches-error` (first request fails, Try again succeeds).

## 6. Approval and booking

The physician reviews the selected match on `/referral/{id}/review?specialist={id}[&distance=50][&partial=1]`
(the search options that produced the match travel in the URL) and explicitly confirms before anything is booked.

| Method | Path | Returns |
|---|---|---|
| GET | `/api/echo/specialists/{id}/slots` | `Slot[]`: the specialist's **currently open** slots, earliest first (`{ id, startsAt }`). Feeds the Appointment select. |
| POST | `/api/echo/referrals/{id}/approve` | The updated `Referral` (`status: "scheduled"`, `specialist`, `appointmentAt`, timeline events) |

`POST .../approve` body: `{ "specialistId": "sp_chen", "slotId": "slot_1" }`.

- **Slot taken** -> respond **409**. The UI shows "That appointment is no longer available", refetches the slot list and
  asks the physician to pick another currently open time (or another specialist). Any other failure is a generic
  "Couldn't book" with Try again; the request must be safe to retry (nothing booked on failure).
- **Referral fields used after booking:** `specialist` (with `city`), `appointmentAt`, `status`, and
  `insuranceAccepted` (whether the booked specialist accepts the patient's plan; may be false when the physician
  booked a partial match). The location shown is `specialist.organization` + `specialist.city`.
- **Status values** must align: the UI uses `awaiting_approval | awaiting_patient | scheduled`; the current backend
  has `pending | accepted | declined | scheduled`.
- **Timeline:** booking should record `approved`, `sent_to_patient` and `scheduled` events. The Booking Confirmation
  "Next steps" reads them: Approved (you), Sent to patient, and Patient confirmation (waiting until a `patient_viewed`
  event exists).
- **Patient notification is NOT verified.** In the mock, `sent_to_patient` is only a timeline event; no message is
  sent. The UI does not claim the patient was notified anywhere except that "Sent to patient" step. Confirm what the
  real backend does on approval, and either send the notification or drop/relabel that step.
- Mock only, on the Approval URL: `?mock=book-error` (first booking attempt fails, Try again succeeds) and
  `?mock=slot-taken` (first attempt finds the chosen slot taken; the physician picks another).

## 7. Patient confirmation and referral tracking

> **Scope:** these are frontend expectations for the backend team. The frontend implements only the mock
> (`frontend/src/mock/`); nothing here has been built or verified on the real backend.

Two screens read the referral: **Patient Confirmation** (`/referral/{id}/confirmation`, the patient's response) and
**Referral Tracking** (`/referral/{id}`, the full lifecycle). Both use `GET /api/echo/referrals/{id}` and always refetch
when opened.

**Referral additions**

```json
{
  "patientConfirmation": { "status": "pending", "respondedAt": null },   // pending | confirmed | declined
  "timeline": [ { "kind": "specialist_selected", "at": "2026-09-19T10:40:00-04:00" } ]
}
```

- `patientConfirmation.status`: `pending | confirmed | declined`; `respondedAt` (ISO 8601) is set once the patient responds.
- **Timeline event kinds**, in lifecycle order: `created`, `matches_found`, `specialist_selected`, `approved`,
  `sent_to_patient`, `scheduled`, then `patient_confirmed` or `patient_declined`. New: `specialist_selected`,
  `patient_confirmed`, `patient_declined`. (`patient_viewed` remains but is not a confirmation.)
- **Naming:** the UI shows `matches_found` as **"Analysis completed"**. The backend event keeps its name; if it is
  renamed to `analysis_completed`, tell the frontend (one string in `frontend/src/echo/lifecycle.ts`).
- **404** for an unknown referral id: the UI shows "We couldn't find that referral" and does not retry. Any other
  failure shows "Couldn't load..." with Try again.

**New endpoint: record the selected specialist**

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/api/echo/referrals/{id}/select` | `{ "specialistId": "sp_chen" }` | The updated `Referral` (`specialist` set, one `specialist_selected` event) |

The frontend calls it when the physician clicks **Review selection** on Specialist Matches (fire-and-forget; the
screen does not wait for it), so that Referral Tracking can show "Specialist selected" and "Review and approve" for a
referral that is awaiting approval. Selecting again replaces the previous choice.

**What is mock-confirmed vs. still needs backend verification**

| Behavior | Status |
|---|---|
| Approving books the slot and records `approved`, `sent_to_patient`, `scheduled` events | **Mock-confirmed only** (see section 6) |
| "Sent to patient" means a message actually reached the patient | **Not verified.** In the mock it is only a timeline event. The UI never says email/SMS/notified. |
| A patient can confirm or decline an appointment, and how (link, portal, phone, staff entry) | **Not defined.** There is no patient-facing screen. The mock uses URL switches, below. |
| What happens after a decline (rebook, waitlist, release the slot) | **Not defined.** The UI only offers **Choose another specialist** (the existing Matches flow). |
| `patientConfirmation` and `respondedAt` set by the backend | **Requested**, not built |
| `specialist_selected` recorded on select | **Requested**, not built |

**Mock-only URL switches** (on the Patient Confirmation or Tracking URL of a *booked* referral; they do not persist):
`?mock=patient-confirmed`, `?mock=patient-declined`, and `?mock=referral-error` (the first load fails; Try again works).

## 8. Physician consult and clinical trials

> **Scope:** frontend expectations for the backend team. The frontend implements only the mock
> (`frontend/src/mock/consults.ts`, `trials.ts`, `echoApi.ts`) behind `VITE_USE_MOCK`; `httpEchoApi` calls the paths
> below. Nothing here has been built or verified on the real backend.

### 8.1 Consult (a chat between two physicians)

Consults look and work like a chat: a list of conversations and, for the open one, messages each way. A conversation is
between the signed-in physician and one colleague, has **any number of messages**, and **may be about one of the sender's
referrals, but does not have to be** (the physician can consult a colleague at any time, not only after a referral).

**Screen:** `/consults` (conversation list + the newest conversation open), `/consults/{id}` (a conversation) and
`/consults/new[?referral={id}]` (the New consult form; the referral is optional). The "Consult a colleague" buttons on the
referral screens open New consult with that referral chosen. The old `/referral/{id}/consult` URL redirects there.

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/echo/colleagues` | none | `Colleague[]` for the recipient select |
| GET | `/api/echo/consults` | none | `ConsultSummary[]`, newest activity first (conversations I started **or** received) |
| GET | `/api/echo/consults/{id}` | none | `ConsultThread`; **404** if it doesn't exist or I'm not in it |
| POST | `/api/echo/consults` | `{ "colleagueId": "doc_002", "text": "...", "referralId": "ref_1" }` (`referralId` optional) | The new `ConsultThread` (201) |
| POST | `/api/echo/consults/{id}/messages` | `{ "text": "..." }` | The updated `ConsultThread` (201) |

```json
{
  "ConsultSummary": {
    "id": "consult_1",
    "colleague": { "id": "doc_002", "name": "Dr. Marcus Bell", "specialty": "Internal Medicine", "organization": "Harbor Internal Medicine" },
    "referral": { "id": "ref_1", "patientName": "Maria Lopez", "age": 58, "sex": "F", "reason": "Knee pain" },   // null if none
    "status": "pending",                       // pending = my message is the last one; responded = theirs is
    "lastMessage": { "text": "...", "at": "2026-09-19T10:52:00-04:00", "fromMe": true }
  },
  "ConsultThread": "ConsultSummary + { messages: [{ id, fromMe, text, at }], sharedContext: { age, sex, reason, summary } | null }"
}
```

- **Privacy:** the sender's own screens show the patient's name (`referral.patientName`). What the colleague is given
  (`sharedContext`) is **age, sex, reason and summary, never the name**, and the colleague's view of a conversation has
  `referral: null`. This is the mock/demo behavior; real privacy rules and whether a colleague can see the context at all are
  a backend/product decision. There is no colleague-facing screen yet, so the "Shared with ..." note in the UI is a statement of
  what would be shared, not a claim it was delivered.
- **"Sent" means recorded.** Nothing tells the colleague, and the UI never says delivered, read, typing or notified. A message
  that fails to send shows "Not sent · Nothing was delivered" with **Retry**; the physician's text is kept.
- **Validation:** `colleagueId` and `text` are required (blank text is rejected, 422). A colleague can't be yourself (422). A
  `referralId` must be one of the sender's own referrals (404 otherwise). The frontend validates first and shows field errors.
- **Answering:** a colleague answers through the existing core consult API (`POST /consults/{id}/messages`); there is no
  colleague-facing ECHO screen. In `AUTH_MODE=demo` that route is closed, so demo conversations stay "Awaiting response".
- **Updates are not live.** The page refetches when opened and after sending. The core WebSocket exists for live delivery but
  the frontend does not use it.

**Mock-only URL switches** (`?mock=`; they do not persist): `consult-responded` (waiting conversations get a reply),
`consult-send-error` (the first send, a new consult or a message, fails; retrying works), `consult-load-error` (the first load
of the list fails; Try again works), `consults-empty` (an empty list).

### 8.2 Clinical trials

Trials to **review** for one referral. They are not recommendations and nothing checks the patient's eligibility.

**Screen:** `/referral/{id}/trials`. There is no trial detail page: each row's title links to the trial's page on
ClinicalTrials.gov (`url`, opens in a new tab).

| Method | Path | Query | Returns |
|---|---|---|---|
| GET | `/api/echo/referrals/{id}/trials/criteria` | `distanceMiles`, `allStatuses` | `TrialCriteria` (cheap; shown while results load) |
| GET | `/api/echo/referrals/{id}/trials` | `distanceMiles`, `allStatuses` | `TrialsResult` |

- **Query:** defaults are **within 100 miles** and **recruiting or not yet recruiting**. The "no trials found" screen
  offers *Widen location* (`distanceMiles=250` or `distanceMiles=any`) and *Include all statuses*
  (`allStatuses=true`). Both endpoints take the same query so the criteria card always matches the results.

```json
{
  "TrialCriteria": {
    "condition": "Meniscal tear, knee",
    "patient": "47y M",
    "location": "Within 100 miles of Roanoke, VA",
    "status": "Recruiting or not yet recruiting",
    "source": "ClinicalTrials.gov",
    "distanceMiles": 100,                  // null = any location
    "allStatuses": false
  },
  "TrialsResult": {
    "referralId": "ref_1",
    "trials": [
      {
        "nctId": "NCT05123456",
        "title": "Arthroscopic Partial Meniscectomy vs Physical Therapy for Degenerative Meniscal Tear",
        "condition": "Meniscal tear",
        "intervention": "Procedure: partial meniscectomy vs. physical therapy",
        "location": "Roanoke, VA",
        "distanceMiles": 8,
        "status": "recruiting",            // recruiting | not_yet_recruiting | active_not_recruiting
        "relevance": "Studies meniscal tear, the reported condition.",
        "url": "https://clinicaltrials.gov/study/NCT05123456"
      }
    ]
  }
}
```

- The criteria fields are display-ready strings, rendered as given.
- **`relevance`** is one short factual sentence tying the trial to the referral's recorded condition (for example
  "Studies meniscal injury, a related condition."). **No score, percentage, "best match" or eligibility statement.**
  `null` is allowed; the UI then shows "Condition matches the search."
- **Order:** by `distanceMiles` ascending (the footer says "Sorted by distance"). `distanceMiles` may be `null`.
- **Empty:** `trials: []` is a normal 200 and shows "No trials found" with the widen options above.
- **Failure:** any non-404 error, including ClinicalTrials.gov being unreachable, shows "Couldn't load trials" with
  Try again (no automatic retry). 404 means unknown referral.
- The frontend never calls ClinicalTrials.gov directly: the backend proxies and normalises it.

**Mock-only URL switches:** `trials-empty` (the default search finds nothing; widening finds trials) and
`trials-error` (the first load fails, Try again works).

### 8.3 Entry points (frontend only, no backend needed)

- **Tracking, Approval and Matches** show two quiet buttons at the top right of the header: *Consult a colleague*
  (`/referral/{id}/consult`) and *Clinical trials* (`/referral/{id}/trials`). These are an addition to the approved
  frames; they are not in Figma.
- **Matches, no-match state:** the "Consult a colleague" row's button reads **Consult** (was "Ping") and opens New consult with
  that referral chosen.
- Top nav **Consults** opens the consults list.

## 9. Sign-in (login page)

With a session backend (`AUTH_MODE=session`) the app shows a login page and every `/api/echo/*` call except these needs
`Authorization: Bearer <token>`. In mock mode, and on a dev backend, there is no login.

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/echo/auth/config` | none | `{ "login": true, "demoAccounts": true }`. Open. `login: false` = no login screen |
| POST | `/api/echo/auth/login` | `{ "email", "password" }` | `{ "token", "physician" }`; **401** "Check your email and password." (same for an unknown email); **429** after repeated failures |
| GET | `/api/echo/auth/demo-accounts` | none | The demo physicians for the one-click list; **404** unless `DEMO_ACCOUNT_LOGIN=true` |
| POST | `/api/echo/auth/demo-login` | `{ "physicianId" }` | `{ "token", "physician" }`; **404** unless `DEMO_ACCOUNT_LOGIN=true` |

- **Demo-grade.** All demo accounts share `DEMO_PASSWORD`; emails are `first.last@practice.example` (for example
  `elena.ruiz@riverside.example`). Tokens are HMAC-signed (`SESSION_SECRET`), expire after `SESSION_HOURS`, and are not revocable:
  **Sign out** just discards the token. Real deployments use `AUTH_MODE=auth0`.
- **Each account has its own data:** its own referrals and conversations. Specialists, slots and the patient list are shared. Two
  windows signed in as two doctors give a real two-sided chat.
- The frontend keeps the token in `localStorage`, sends it on every request, and returns to the login page ("Your session
  ended") when the API answers 401 to a request that carried one.

## 10. Still to come

Dashboard filters use `Referral.status` (`awaiting_approval | awaiting_patient | scheduled`) and
`Referral.attention` (`{ reason, action }`). Match results, approval, booking and timeline shapes will be
added here as those screens are designed.
