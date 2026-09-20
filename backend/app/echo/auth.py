"""Authentication for /api/echo/*.

Identical to the core `current_user`, plus two modes the browser frontend needs (it sends no
credentials of any kind):

- dev:  a request with no X-Dev-Physician header acts as `settings.dev_default_physician`.
        Local development only; refused at startup when ENVIRONMENT=production.
- session: demo physicians sign in on the login page (POST /api/echo/auth/login) and send the
        signed token as "Authorization: Bearer ...". Each account has its own data.
- demo: a temporary public-demo mode. Every request must carry `X-Demo-Access: <DEMO_ACCESS_TOKEN>`
        (the reverse proxy in front of the site adds it), and everyone acts as DEMO_PHYSICIAN_ID.
        X-Dev-Physician and bearer tokens are ignored here, so nobody can pick their identity.

In `auth0` mode nothing changes: a valid bearer token is required and the failure mode stays closed.
"""

import hmac

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials

from app.auth import CurrentUser, Role, authenticate, bearer_scheme, dev_header_scheme
from app.config import settings
from app.echo.session import read_token

demo_header_scheme = APIKeyHeader(
    name="X-Demo-Access", auto_error=False, description="AUTH_MODE=demo only"
)


def demo_user(presented: str | None) -> CurrentUser:
    expected = settings.demo_access_token
    if not expected:  # the settings validator prevents this; fail closed anyway
        raise HTTPException(503, "Demo access is not configured on this server")
    if not presented or not hmac.compare_digest(presented.encode(), expected.encode()):
        raise HTTPException(401, "Missing or invalid demo access token")
    return CurrentUser(
        subject="demo",
        physician_id=settings.demo_physician_id,
        roles=frozenset({Role.REFERRING_PHYSICIAN}),
    )


async def echo_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    dev_physician: str | None = Depends(dev_header_scheme),
    demo_access: str | None = Depends(demo_header_scheme),
) -> CurrentUser:
    if settings.auth_mode == "demo":
        return demo_user(demo_access)
    if settings.auth_mode == "session":
        physician_id = read_token(creds.credentials) if creds else None
        if physician_id is None:
            raise HTTPException(401, "Sign in required", headers={"WWW-Authenticate": "Bearer"})
        return CurrentUser(
            subject=f"session|{physician_id}",
            physician_id=physician_id,
            roles=frozenset({Role.REFERRING_PHYSICIAN}),
        )
    if settings.auth_mode == "dev" and not dev_physician:
        dev_physician = settings.dev_default_physician or None
    return await authenticate(creds.credentials if creds else None, dev_physician)
