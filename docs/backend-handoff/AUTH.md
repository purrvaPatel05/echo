# Authentication (Auth0)

The API trusts a signed Auth0 access token, never an id typed into a request. This page covers the one-time Auth0 setup, what the backend expects, and how the frontend signs in.

## 1. Auth0 setup (about 20 minutes, dashboard only)

Use a **development tenant**. All data in this project is synthetic. Menu names below match Auth0's current dashboard; if a label differs slightly, look for the closest one.

### Step 1: Create the tenant
1. Go to **auth0.com** and sign up or log in.
2. When asked to create a tenant, choose a name (e.g. `echo-dev`), a region (e.g. US), and set the environment to **Development**.
3. Your tenant **domain** is now `echo-dev.us.auth0.com` (the exact text depends on your name and region). Copy it.

### Step 2: Create the API
1. **Applications → APIs → Create API.**
2. Name: `ECHO API`. Identifier: `https://api.echo.local`. Signing algorithm: **RS256**. Click **Create**.
3. The identifier is your **audience**. Copy it exactly, with no trailing slash. It doesn't need to be a real website.
4. Open the API's **Settings** tab, scroll to **RBAC Settings**, and turn on **Enable RBAC**. Save. (Leave "Add Permissions in the Access Token" off; it isn't needed.)

### Step 3: Create the roles
**User Management → Roles → Create Role**, three times: `referring_physician`, `specialist`, `admin`. Descriptions are optional. Don't add permissions.

### Step 4: Create three test users
**User Management → Users → Create User.** Repeat for each:

| Email (examples) | Role | `physician_id` |
|---|---|---|
| `doc1@echo.test` | `referring_physician` and `admin` | `doc_001` |
| `doc2@echo.test` | `referring_physician` | `doc_002` |
| `doc3@echo.test` | `referring_physician` | `doc_003` |

For each user:
1. Fill in the email and a password, keep the connection as **Username-Password-Authentication**, and create it.
2. Open the user → **Roles** tab → **Assign Roles**, and pick the roles from the table.
3. Go back to the **Details** tab, scroll to **Metadata**, and in the **app_metadata** box (not `user_metadata`) enter, for example: `{"physician_id": "doc_001"}`. Save.

The `physician_id` values must match the seeded physicians (`doc_001`, `doc_002`, `doc_003`); this is what links a login to a person in the database.

### Step 5: Create the frontend application
1. **Applications → Applications → Create Application.**
2. Name: `ECHO Web`. Type: **Single Page Web Applications**. Create.
3. Open the **Settings** tab and copy the **Domain** and **Client ID** for Member 2. There is no secret to share for this type of app.
4. Scroll down and set all three of these to `http://localhost:5173`:
   - **Allowed Callback URLs**
   - **Allowed Logout URLs**
   - **Allowed Web Origins**

   (Add your deployed frontend URL to each later, comma-separated.) Click **Save Changes**.
5. **Authorize the app for the API** (easy to miss): Applications → APIs → `ECHO API` → **Application Access** tab (older dashboards: "Machine to Machine Applications") → find `ECHO Web` → **Edit** → set **User Access** to **Authorized** → Save. Without this, login fails with "Client is not authorized to access resource server".
6. Open the application's **Connections** tab and make sure **Username-Password-Authentication** is switched on (this is the email-and-password login; leave social logins like Google off). If Auth0's setup wizard asks how users log in, choose **Database**.

### Step 6: Create and attach the post-login Action
This puts the physician id and roles into the access token; without it the backend rejects every login.
1. **Actions → Library → Create Action → Build from scratch.** Name: `Add ECHO claims`. Trigger: **Login / Post Login**. Create.
2. Replace the code with:

   ```js
   exports.onExecutePostLogin = async (event, api) => {
     const ns = 'https://echo';
     const physicianId = event.user.app_metadata && event.user.app_metadata.physician_id;
     if (physicianId) {
       api.accessToken.setCustomClaim(`${ns}/physician_id`, physicianId);
     }
     api.accessToken.setCustomClaim(
       `${ns}/roles`,
       (event.authorization && event.authorization.roles) || []
     );
   };
   ```
3. Click **Deploy** (top right).
4. Go to **Actions → Triggers** (older dashboards: **Actions → Flows**) → **post-login**. Drag `Add ECHO claims` from the right-hand panel into the flow between **Start** and **Complete**, then click **Apply**.

### Step 7: Send the values
You need to give:
- **To me (backend):** the **domain** and the **audience** (API identifier). Neither is secret.
- **To Member 2 (frontend):** the **domain**, the **Client ID**, and the audience.

### Checklist before moving on
- [ ] The API identifier has no trailing slash and is written the same everywhere.
- [ ] Every test user has a role assigned **and** `physician_id` in `app_metadata`.
- [ ] The Action is **deployed and dragged into the post-login flow** (deploying alone does nothing).
- [ ] The callback, logout and web origin URLs are all `http://localhost:5173`.
- [ ] `ECHO Web` is **authorized for `ECHO API`** (API → Application Access → User Access: Authorized).
- [ ] **Username-Password-Authentication** is enabled on the `ECHO Web` application's Connections tab.

### Common mistakes
- **`physician_id` in `user_metadata` instead of `app_metadata`:** the Action reads only `app_metadata`.
- **Action not attached to the flow:** logins work but the API returns 403 "not linked to a physician".
- **Audience mismatch** between Auth0, `AUTH0_AUDIENCE`, and the frontend: the API returns 401.
- **"Client is not authorized to access resource server":** the app isn't authorized for the API (Step 5, item 5).
- **Wrong namespace:** the Action uses `https://echo`; `AUTH_CLAIM_NAMESPACE` must be the same.

### Step 8: Verify a real login (optional but recommended)
With the API running in `AUTH_MODE=auth0` and nothing using port 5173, from `backend/`:

```bash
uv run python -m scripts.auth0_login_check --client-id <ECHO Web Client ID>
```

It opens the Auth0 login, and after you sign in as a test user it prints the physician id and roles found in the token and calls the API with it. It never prints the token.

## 2. Backend configuration

Environment variables (`backend/.env` locally, real environment variables in deployment):

| Variable | Value |
|---|---|
| `AUTH_MODE` | `auth0` (default, secure) or `dev` (local only, see below) |
| `AUTH0_DOMAIN` | e.g. `dev-abc123.us.auth0.com` |
| `AUTH0_AUDIENCE` | the API identifier from step 2 |
| `AUTH_CLAIM_NAMESPACE` | `https://echo` (only change it if you change the Action) |

If `AUTH_MODE=auth0` and the domain or audience is missing, every request returns **503**. The API never falls back to being open.

## 3. What the API enforces

| Situation | Response |
|---|---|
| No token, bad token, expired token, wrong audience or issuer | **401** |
| Token is valid but not linked to a physician, or the role is `specialist` | **403** |
| Requesting another physician's referral (any endpoint) | **404** (its existence is not revealed) |
| Approving or booking a referral you don't own, even as `admin` | **403** |
| A body field like `approved_by` that doesn't match the signed-in physician | **403** |

- Body fields such as `referring_physician_id`, `approved_by`, `from_physician_id`, `sender_physician_id` and the `physician_id` query parameter are **optional now**. The server uses the token's physician id. If one is sent it must match.
- `GET /referrals` returns the signed-in physician's referrals. An `admin` sees all referrals, and can view them but cannot approve them.
- Consult threads are visible only to their two participants, and a referral can be attached to a consult only by someone who can see that referral.
- `GET /health` needs no login. `/docs` (Swagger) has an **Authorize** button for a bearer token.

## 4. Frontend (Member 2)

- Sign in with `@auth0/auth0-react`, requesting the API audience:
  `getAccessTokenSilently({ authorizationParams: { audience: 'https://api.echo.local' } })`.
- Send `Authorization: Bearer <token>` on every request.
- **WebSocket:** browsers can't set headers on a WebSocket, so connect with the token in the URL: `ws://localhost:8000/ws/consults/{your physician id}?token=<access token>`. The id must be your own, and the socket closes with code 4401 (not signed in) or 4403 (not allowed) otherwise. Your physician id is the `https://echo/physician_id` claim in the token, or `GET /physicians` matched to your login.

## 5. Dev mode (local development and demo fallback)

With `AUTH_MODE=dev` the API skips Auth0 and trusts a header: `X-Dev-Physician: doc_001` (or `?dev_physician=doc_001` on the WebSocket). This lets the frontend and backend run without a tenant, and it's the fallback if login breaks during a demo.

**Never enable dev mode on a deployed server:** anyone could act as any physician. It logs no warning by itself, so check the deployed environment variables.

## 6. Not covered yet

- **Patient access:** there is no patient login. `patient-summary` is a physician view of what the patient will be told.
- **Specialist role:** defined, but no flow uses it, so it has no access.
- **Least-privilege on patients:** any signed-in physician can list all patients, because the data model has no patient-to-physician assignment yet.
- **Real patient data:** before any real PHI, you'd need business associate agreements with Auth0, Anthropic, and the hosting and database providers, plus an audit log of who viewed what. Case notes are sent to Claude for analysis.
