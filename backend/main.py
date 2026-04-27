import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.db import create_db
from backend.routers import bits, versions, annotations, sets, shows, analysis, lines


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    yield


app = FastAPI(title="Comedy Set Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bits.router)
app.include_router(versions.router)
app.include_router(annotations.router)
app.include_router(sets.router)
app.include_router(shows.router)
app.include_router(analysis.router)
app.include_router(lines.router)


@app.get("/health")
def health():
    return {"ok": True}


# Serve built frontend — must be mounted last so API routes take priority
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
