from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, func

from backend.db import get_session
from backend.models import ComedySet, SetVersion, SetVersionItem, Version, Bit, Show

router = APIRouter(tags=["sets"])


class SetCreate(BaseModel):
    name: str


class SetUpdate(BaseModel):
    name: str


class SetVersionItemInput(BaseModel):
    version_id: UUID
    position: int


class SetVersionCreate(BaseModel):
    items: list[SetVersionItemInput]


# ── Sets ──────────────────────────────────────────────────────────────────────

@router.get("/sets")
def list_sets(session: Session = Depends(get_session)):
    sets = session.exec(select(ComedySet)).all()
    result = []
    for s in sets:
        count = session.exec(
            select(func.count(SetVersion.id)).where(SetVersion.set_id == s.id)
        ).one()
        result.append({**s.model_dump(), "version_count": count})
    return result


@router.post("/sets", status_code=201)
def create_set(body: SetCreate, session: Session = Depends(get_session)):
    s = ComedySet(**body.model_dump())
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


@router.get("/sets/{set_id}")
def get_set(set_id: UUID, session: Session = Depends(get_session)):
    s = session.get(ComedySet, set_id)
    if not s:
        raise HTTPException(404, "Set not found")
    versions = session.exec(
        select(SetVersion).where(SetVersion.set_id == set_id).order_by(SetVersion.version_num)
    ).all()
    return {
        **s.model_dump(),
        "set_versions": [
            {"id": sv.id, "version_num": sv.version_num, "created_at": sv.created_at}
            for sv in versions
        ],
    }


@router.patch("/sets/{set_id}")
def update_set(set_id: UUID, body: SetUpdate, session: Session = Depends(get_session)):
    s = session.get(ComedySet, set_id)
    if not s:
        raise HTTPException(404, "Set not found")
    s.name = body.name
    s.updated_at = datetime.utcnow()
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


@router.get("/sets/{set_id}/shows")
def get_set_shows(set_id: UUID, session: Session = Depends(get_session)):
    s = session.get(ComedySet, set_id)
    if not s:
        raise HTTPException(404, "Set not found")
    set_versions = session.exec(
        select(SetVersion).where(SetVersion.set_id == set_id)
    ).all()
    sv_ids = [sv.id for sv in set_versions]
    if not sv_ids:
        return []
    shows = session.exec(
        select(Show).where(Show.set_version_id.in_(sv_ids))
    ).all()
    return shows


# ── Set Versions ──────────────────────────────────────────────────────────────

@router.get("/sets/{set_id}/versions")
def list_set_versions(set_id: UUID, session: Session = Depends(get_session)):
    s = session.get(ComedySet, set_id)
    if not s:
        raise HTTPException(404, "Set not found")
    set_versions = session.exec(
        select(SetVersion).where(SetVersion.set_id == set_id).order_by(SetVersion.version_num)
    ).all()
    result = []
    for sv in set_versions:
        count = session.exec(
            select(func.count(SetVersionItem.id)).where(SetVersionItem.set_version_id == sv.id)
        ).one()
        result.append({**sv.model_dump(), "item_count": count})
    return result


@router.post("/sets/{set_id}/versions", status_code=201)
def create_set_version(set_id: UUID, body: SetVersionCreate, session: Session = Depends(get_session)):
    s = session.get(ComedySet, set_id)
    if not s:
        raise HTTPException(404, "Set not found")

    # Validate all version_ids exist
    for item in body.items:
        if not session.get(Version, item.version_id):
            raise HTTPException(404, f"Version {item.version_id} not found")

    max_num = session.exec(
        select(func.max(SetVersion.version_num)).where(SetVersion.set_id == set_id)
    ).one()
    sv = SetVersion(set_id=set_id, version_num=(max_num or 0) + 1)
    session.add(sv)
    session.flush()

    for item in body.items:
        session.add(SetVersionItem(
            set_version_id=sv.id,
            version_id=item.version_id,
            position=item.position,
        ))

    session.commit()
    session.refresh(sv)
    return sv


@router.get("/set-versions/{sv_id}")
def get_set_version(sv_id: UUID, session: Session = Depends(get_session)):
    sv = session.get(SetVersion, sv_id)
    if not sv:
        raise HTTPException(404, "SetVersion not found")

    items = session.exec(
        select(SetVersionItem).where(SetVersionItem.set_version_id == sv_id).order_by(SetVersionItem.position)
    ).all()

    enriched = []
    for item in items:
        version = session.get(Version, item.version_id)
        bit = session.get(Bit, version.bit_id)
        enriched.append({
            "id": item.id,
            "position": item.position,
            "version_id": item.version_id,
            "version_num": version.version_num,
            "bit_id": bit.id,
            "bit_title": bit.title,
        })

    return {**sv.model_dump(), "items": enriched}
