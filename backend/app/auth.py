"""Authentication and authorization.

Identity comes from a verified Auth0 access token (or, in dev mode, a header), never from the
request body. See docs/AUTH.md for the Auth0 setup and claim contract.
"""

import logging
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, WebSocket
from fastapi.concurrency import run_in_threadpool
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import settings

logger = logging.getLogger(__name__)


class Role(StrEnum):
    REFERRING_PHYSICIAN = "referring_physician"
    SPECIALIST = "specialist"  # defined, but no flow uses it yet, so it has no access
    ADMIN = "admin"


# Roles allowed to use the API. A specialist login is authenticated but gets 403.
_PERMITTED_ROLES = {Role.REFERRING_PHYSICIAN, Role.ADMIN}


@dataclass(frozen=True)
class CurrentUser:
    subject: str
    physician_id: str
    roles: frozenset[str]

    @property
    def is_admin(self) -> bool:
        return Role.ADMIN in self.roles


bearer_scheme = HTTPBearer(auto_error=False, description="Auth0 access token")
dev_header_scheme = APIKeyHeader(
    name="X-Dev-Physician",
    auto_error=False,
    description="Dev mode only (AUTH_MODE=dev): act as this physician id, e.g. doc_001",
)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


@lru_cache
def _jwks_client() -> PyJWKClient:
    return PyJWKClient(f"https://{settings.auth0_domain}/.well-known/jwks.json", cache_keys=True)


def _signing_key(token: str):
    """The public key that signed `token`. Separate function so tests can substitute a key."""
    return _jwks_client().get_signing_key_from_jwt(token).key


def verify_token(token: str) -> dict:
    """Blocking (may fetch Auth0's keys); call through the threadpool."""
    try:
        return jwt.decode(
            token,
            _signing_key(token),
            algorithms=["RS256"],
            audience=settings.auth0_audience,
            issuer=f"https://{settings.auth0_domain}/",
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        logger.info("Rejected access token: %s", type(exc).__name__)
        raise _unauthorized("Invalid or expired access token") from None


def _user_from_claims(claims: dict) -> CurrentUser:
    ns = settings.auth_claim_namespace.rstrip("/")
    physician_id = claims.get(f"{ns}/physician_id")
    roles = frozenset(claims.get(f"{ns}/roles") or [])
    if not physician_id:
        raise HTTPException(403, "This account is not linked to a physician")
    if not roles & _PERMITTED_ROLES:
        raise HTTPException(403, "Your role does not have access to this API")
    return CurrentUser(subject=claims["sub"], physician_id=physician_id, roles=roles)


async def authenticate(token: str | None, dev_physician: str | None) -> CurrentUser:
    if settings.auth_mode == "dev":
        if not dev_physician:
            raise _unauthorized("Dev mode: send an X-Dev-Physician header")
        return CurrentUser(
            subject=f"dev|{dev_physician}",
            physician_id=dev_physician,
            roles=frozenset({Role.REFERRING_PHYSICIAN}),
        )
    if not settings.auth0_domain or not settings.auth0_audience:
        # Fail closed: never fall back to an open API because config is missing.
        raise HTTPException(503, "Authentication is not configured on this server")
    if not token:
        raise _unauthorized("Missing bearer token")
    return _user_from_claims(await run_in_threadpool(verify_token, token))


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    dev_physician: str | None = Depends(dev_header_scheme),
) -> CurrentUser:
    return await authenticate(creds.credentials if creds else None, dev_physician)


async def authenticate_websocket(websocket: WebSocket) -> CurrentUser | None:
    """Browsers can't set headers on a WebSocket, so the token travels as ?token=.
    Closes the socket (4401 unauthenticated / 4403 forbidden) and returns None on failure."""
    query = websocket.query_params
    try:
        return await authenticate(
            query.get("token"),
            websocket.headers.get("x-dev-physician") or query.get("dev_physician"),
        )
    except HTTPException as exc:
        await websocket.close(code=4401 if exc.status_code == 401 else 4403)
        return None


def require_same_physician(claimed: str | None, user: CurrentUser, field: str) -> None:
    """Request bodies may still carry a physician id for backward compatibility, but it must
    match the signed-in physician."""
    if claimed is not None and claimed != user.physician_id:
        raise HTTPException(403, f"{field} does not match the signed-in physician")
