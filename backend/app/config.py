from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    """Runtime settings, read from environment variables / .env. Never hard-code secrets."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-5"
    database_url: str = "postgresql+asyncpg://echo:echo@localhost:5432/echo"
    redis_url: str = "redis://localhost:6379/0"
    # "inline" runs parse/match after the HTTP response inside the API process (no Redis needed);
    # "celery" hands them to a worker: `celery -A app.celery_app worker`.
    job_backend: Literal["inline", "celery"] = "inline"
    claude_timeout_seconds: float = 60.0
    # Ask the API to re-run a safety-declined request on another model server-side.
    claude_server_fallback: bool = True

    # "development" (default) or "production". Production turns on strict startup checks below:
    # no dev auth, PostgreSQL required, no default credentials, no /docs. Set it in every deploy.
    environment: Literal["development", "production"] = "development"

    # Authentication.
    #   auth0: verifies Auth0 access tokens (fail-closed if not configured). The real mode.
    #   dev:   trusts an X-Dev-Physician header. Local development only; refused in production.
    #   demo:  a temporary, explicit mode for a public demo whose frontend can't log in. Only
    #          /api/echo/* works, and only for requests carrying X-Demo-Access: <DEMO_ACCESS_TOKEN>
    #          (a reverse proxy adds it). Everyone acts as DEMO_PHYSICIAN_ID.
    auth_mode: Literal["auth0", "dev", "demo", "session"] = "auth0"
    demo_access_token: str | None = None  # >= 24 characters; required when AUTH_MODE=demo
    demo_physician_id: str = "doc_001"

    # AUTH_MODE=session: demo physicians sign in on the login page and get a signed session token.
    # Each account has its own referrals and conversations. Demo-grade: shared DEMO_PASSWORD.
    session_secret: str | None = (
        None  # >= 32 characters; signs the tokens. Required for session mode.
    )
    session_hours: float = 12.0
    demo_password: str | None = None  # >= 8 characters; the shared password of the demo accounts
    # Also allow the one-click "Demo accounts" sign-in (no password). Anyone who reaches the login
    # page can then enter as any demo physician, so leave it false unless the site is only a demo.
    demo_account_login: bool = False

    # Demo only: a colleague "answers" a chat message a few seconds after it is sent, with a canned
    # reply that is always labelled "Demo reply". It writes messages no real colleague sent, so it
    # is refused in auth0 mode.
    simulate_colleague_replies: bool = False
    simulated_reply_delay_seconds: float = 3.0
    auth0_domain: str | None = None  # e.g. dev-abc123.us.auth0.com
    auth0_audience: str | None = None  # the API identifier, e.g. https://api.echo.local
    # Custom claims added by the Auth0 post-login Action: <ns>/physician_id and <ns>/roles.
    auth_claim_namespace: str = "https://echo"
    # Dev mode only: the physician a request acts as when it carries no X-Dev-Physician header.
    # Lets the browser frontend (which sends no credentials) work against a local backend.
    # Only /api/echo/* uses it, and never outside AUTH_MODE=dev. Leave empty to require the header.
    dev_default_physician: str | None = "doc_001"

    # Browser origins allowed to call the API. Set CORS_ORIGINS as a JSON list in deployment,
    # e.g. '["https://echo.vercel.app"]'. Defaults to the local Vite dev server.
    cors_origins: list[str] = ["http://localhost:5173"]

    # Distance: Google Maps Distance Matrix when set; otherwise (or on failure) haversine.
    google_maps_api_key: str | None = None
    google_maps_timeout_seconds: float = 5.0

    @model_validator(mode="after")
    def _check_deployment_safety(self):
        if self.auth_mode == "session":
            if len(self.session_secret or "") < 32:
                raise ValueError(
                    "AUTH_MODE=session requires SESSION_SECRET of at least 32 characters"
                )
            if len(self.demo_password or "") < 8 and not self.demo_account_login:
                raise ValueError(
                    "AUTH_MODE=session requires DEMO_PASSWORD (8+ chars) or DEMO_ACCOUNT_LOGIN=true"
                )
        if self.simulate_colleague_replies and self.auth_mode == "auth0":
            raise ValueError(
                "SIMULATE_COLLEAGUE_REPLIES is for AUTH_MODE=dev, demo or session only: it writes "
                "messages that no colleague sent"
            )
        if self.auth_mode == "demo" and len(self.demo_access_token or "") < 24:
            raise ValueError("AUTH_MODE=demo requires DEMO_ACCESS_TOKEN of at least 24 characters")
        if self.environment != "production":
            return self
        problems = []
        if self.auth_mode == "dev":
            problems.append("AUTH_MODE=dev is not allowed (it trusts a client-supplied header)")
        if self.auth_mode == "auth0" and not (self.auth0_domain and self.auth0_audience):
            problems.append("AUTH_MODE=auth0 needs AUTH0_DOMAIN and AUTH0_AUDIENCE")
        url = make_url(self.database_url)
        if url.drivername != "postgresql+asyncpg":
            problems.append("DATABASE_URL must be a PostgreSQL URL using the asyncpg driver")
        elif url.password in (None, "", "echo", "postgres", "password") or url.host in (
            None,
            "localhost",
            "127.0.0.1",
        ):
            problems.append("DATABASE_URL must point at the real database with its own password")
        if "*" in self.cors_origins:
            problems.append("CORS_ORIGINS must not contain '*'")
        if problems:
            raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self


settings = Settings()
