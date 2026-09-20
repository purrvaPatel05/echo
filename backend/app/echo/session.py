"""Session tokens and demo-account sign-in for AUTH_MODE=session.

A token is `base64url(json{sub, exp}).base64url(HMAC-SHA256(payload))`, signed with SESSION_SECRET.
It is stateless: signing out just discards it, and it expires on its own. This is demo-grade
sign-in (a shared demo password, no password storage, no revocation); real deployments use
AUTH_MODE=auth0.
"""

import base64
import hashlib
import hmac
import json
import re
import time
from collections import defaultdict

from app.config import settings
from app.models.people import Physician


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload_b64: str) -> str:
    key = (settings.session_secret or "").encode()
    return _b64(hmac.new(key, payload_b64.encode(), hashlib.sha256).digest())


def issue_token(physician_id: str, now: float | None = None) -> str:
    exp = int((now if now is not None else time.time()) + settings.session_hours * 3600)
    payload = _b64(json.dumps({"sub": physician_id, "exp": exp}, separators=(",", ":")).encode())
    return f"{payload}.{_sign(payload)}"


def read_token(token: str, now: float | None = None) -> str | None:
    """The physician id a valid, unexpired token was issued for, else None."""
    try:
        payload, signature = token.split(".", 1)
        if not hmac.compare_digest(signature, _sign(payload)):
            return None
        claims = json.loads(_unb64(payload))
        if claims["exp"] <= (now if now is not None else time.time()):
            return None
        return str(claims["sub"])
    except (ValueError, KeyError, TypeError):
        return None


def demo_email(physician: Physician) -> str:
    """Deterministic demo email: Dr. Elena Ruiz at Riverside Family Practice is
    elena.ruiz@riverside.example."""
    name = re.sub(r"^dr\.?\s+", "", physician.name.strip(), flags=re.I)
    local = ".".join(re.sub(r"[^a-z]", "", part.lower()) for part in name.split())
    domain = re.sub(r"[^a-z]", "", physician.practice_name.split()[0].lower())
    return f"{local}@{domain}.example"


def password_matches(presented: str) -> bool:
    expected = settings.demo_password or ""
    ok = hmac.compare_digest(presented.encode(), expected.encode())
    return ok and len(expected) >= 8


class LoginLimiter:
    """Slows password guessing: after `limit` failures in `window` seconds, attempts are refused."""

    def __init__(self, limit: int = 8, window: float = 60.0):
        self.limit, self.window = limit, window
        self._failures: dict[str, list[float]] = defaultdict(list)

    def blocked(self, key: str, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        recent = [t for t in self._failures[key] if now - t < self.window]
        self._failures[key] = recent
        return len(recent) >= self.limit

    def record_failure(self, key: str, now: float | None = None) -> None:
        self._failures[key].append(now if now is not None else time.time())

    def clear(self, key: str) -> None:
        self._failures.pop(key, None)


limiter = LoginLimiter()
