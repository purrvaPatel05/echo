import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import store
from .realtime import sio
from .routers.api import router

api = FastAPI(title="OpenEvidence Referral API", version="0.1.0")
api.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
api.include_router(router)
store.seed_demo_data()

# `uvicorn app.main:app` serves REST + Socket.IO on one port.
# Use `api` directly for tests / OpenAPI export.
app = socketio.ASGIApp(sio, other_asgi_app=api)
