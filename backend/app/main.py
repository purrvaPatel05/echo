from fastapi import FastAPI

from app.routers import consult, directory, referrals, trials

app = FastAPI(
    title="ECHO API",
    version="0.1.0",
    description=(
        "Physician-first referral matching. Nothing is sent or booked without physician approval."
    ),
)

app.include_router(referrals.router)
app.include_router(directory.router)
app.include_router(trials.router)
app.include_router(consult.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
