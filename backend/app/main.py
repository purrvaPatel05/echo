import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.echo.router import router as echo_router
from app.routers import consult, directory, referrals, trials

_production = settings.environment == "production"
if settings.auth_mode == "dev":
    logging.getLogger(__name__).warning(
        "AUTH_MODE=dev: requests are trusted without login. Local development only."
    )

app = FastAPI(
    title="ECHO API",
    version="0.1.0",
    description=(
        "Physician-first referral matching. Nothing is sent or booked without physician approval."
    ),
    # The interactive docs and schema are for development; don't publish them from production.
    docs_url=None if _production else "/docs",
    redoc_url=None if _production else "/redoc",
    openapi_url=None if _production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(referrals.router)
app.include_router(directory.router)
app.include_router(trials.router)
app.include_router(consult.router)
app.include_router(echo_router)  # /api/echo/*: the ECHO frontend's contract


@app.get("/health", tags=["meta"])
@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}