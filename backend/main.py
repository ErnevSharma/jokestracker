from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db import create_db
from backend.routers import bits, versions, annotations, sets, shows, analysis

app = FastAPI(title="Comedy Set Tracker")

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


@app.on_event("startup")
def on_startup():
    create_db()


@app.get("/health")
def health():
    return {"ok": True}
