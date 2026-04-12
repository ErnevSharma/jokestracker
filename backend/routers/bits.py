from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, func

from backend.db import get_session
from backend.models import Bit, BitStatus, Version, SetVersionItem, SetVersion, ComedySet, Show

router = APIRouter(prefix="/bits", tags=["bits"])


class BitCreate(BaseModel):
    title: str
    status: BitStatus = BitStatus.drafting


class BitUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[BitStatus] = None


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("")
def list_bits(session: Session = Depends(get_session)):
    bits = session.exec(select(Bit)).all()
    result = []
    for bit in bits:
        count = session.exec(
            select(func.count(Version.id)).where(Version.bit_id == bit.id)
        ).one()
        result.append({**bit.model_dump(), "version_count": count})
    return result


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_bit(body: BitCreate, session: Session = Depends(get_session)):
    bit = Bit(**body.model_dump())
    session.add(bit)
    session.commit()
    session.refresh(bit)
    return bit


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{bit_id}")
def get_bit(bit_id: UUID, session: Session = Depends(get_session)):
    bit = session.get(Bit, bit_id)
    if not bit:
        raise HTTPException(404, "Bit not found")
    versions = session.exec(
        select(Version).where(Version.bit_id == bit_id).order_by(Version.version_num)
    ).all()
    version_list = [
        {"id": v.id, "version_num": v.version_num, "created_at": v.created_at, "char_count": len(v.body)}
        for v in versions
    ]
    return {**bit.model_dump(), "versions": version_list}


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch("/{bit_id}")
def update_bit(bit_id: UUID, body: BitUpdate, session: Session = Depends(get_session)):
    bit = session.get(Bit, bit_id)
    if not bit:
        raise HTTPException(404, "Bit not found")
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(bit, k, v)
    bit.updated_at = datetime.utcnow()
    session.add(bit)
    session.commit()
    session.refresh(bit)
    return bit


# ── Soft Delete ───────────────────────────────────────────────────────────────

@router.delete("/{bit_id}", status_code=204)
def delete_bit(bit_id: UUID, session: Session = Depends(get_session)):
    bit = session.get(Bit, bit_id)
    if not bit:
        raise HTTPException(404, "Bit not found")
    bit.status = BitStatus.dead
    bit.updated_at = datetime.utcnow()
    session.add(bit)
    session.commit()


# ── Appearances ───────────────────────────────────────────────────────────────

@router.get("/{bit_id}/appearances")
def get_appearances(bit_id: UUID, session: Session = Depends(get_session)):
    bit = session.get(Bit, bit_id)
    if not bit:
        raise HTTPException(404, "Bit not found")

    versions = session.exec(
        select(Version).where(Version.bit_id == bit_id).order_by(Version.version_num)
    ).all()

    result = []
    for version in versions:
        items = session.exec(
            select(SetVersionItem).where(SetVersionItem.version_id == version.id)
        ).all()

        sv_groups = {}
        for item in items:
            sv_id = str(item.set_version_id)
            if sv_id not in sv_groups:
                sv = session.get(SetVersion, item.set_version_id)
                comedy_set = session.get(ComedySet, sv.set_id)
                shows = session.exec(
                    select(Show).where(Show.set_version_id == sv.id)
                ).all()
                sv_groups[sv_id] = {
                    "set_version": {"id": sv.id, "version_num": sv.version_num, "created_at": sv.created_at},
                    "set": {"id": comedy_set.id, "name": comedy_set.name},
                    "shows": [{"id": s.id, "date": s.date, "venue": s.venue, "rating": s.rating} for s in shows],
                }

        result.append({
            "version": {"id": version.id, "version_num": version.version_num, "created_at": version.created_at},
            "set_versions": list(sv_groups.values()),
        })

    return {"bit": bit.model_dump(), "versions": result}
