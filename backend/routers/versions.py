import difflib
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, func

from backend.db import get_session
from backend.models import Bit, Version, Annotation

router = APIRouter(tags=["versions"])


class VersionCreate(BaseModel):
    body: str


# ── List versions for a bit ───────────────────────────────────────────────────

@router.get("/bits/{bit_id}/versions")
def list_versions(bit_id: UUID, session: Session = Depends(get_session)):
    bit = session.get(Bit, bit_id)
    if not bit:
        raise HTTPException(404, "Bit not found")
    versions = session.exec(
        select(Version).where(Version.bit_id == bit_id).order_by(Version.version_num)
    ).all()
    return [
        {"id": v.id, "version_num": v.version_num, "created_at": v.created_at, "char_count": len(v.body)}
        for v in versions
    ]


# ── Create version ────────────────────────────────────────────────────────────

@router.post("/bits/{bit_id}/versions", status_code=201)
def create_version(bit_id: UUID, body: VersionCreate, session: Session = Depends(get_session)):
    bit = session.get(Bit, bit_id)
    if not bit:
        raise HTTPException(404, "Bit not found")
    max_num = session.exec(
        select(func.max(Version.version_num)).where(Version.bit_id == bit_id)
    ).one()
    version = Version(bit_id=bit_id, body=body.body, version_num=(max_num or 0) + 1)
    session.add(version)
    session.commit()
    session.refresh(version)
    return version


# ── Version detail ────────────────────────────────────────────────────────────

@router.get("/versions/{version_id}")
def get_version(version_id: UUID, session: Session = Depends(get_session)):
    version = session.get(Version, version_id)
    if not version:
        raise HTTPException(404, "Version not found")
    annotations = session.exec(
        select(Annotation).where(Annotation.version_id == version_id)
    ).all()
    return {**version.model_dump(), "annotations": [a.model_dump() for a in annotations]}


# ── Diff ──────────────────────────────────────────────────────────────────────

@router.get("/versions/{version_id}/diff/{other_id}")
def diff_versions(version_id: UUID, other_id: UUID, session: Session = Depends(get_session)):
    a = session.get(Version, version_id)
    b = session.get(Version, other_id)
    if not a or not b:
        raise HTTPException(404, "Version not found")

    lines_a = a.body.splitlines()
    lines_b = b.body.splitlines()
    matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
    opcodes = [
        {"tag": tag, "a_start": i1, "a_end": i2, "b_start": j1, "b_end": j2}
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
    ]
    return {
        "version_a": {"id": a.id, "version_num": a.version_num},
        "version_b": {"id": b.id, "version_num": b.version_num},
        "opcodes": opcodes,
        "lines_a": lines_a,
        "lines_b": lines_b,
    }
