from datetime import date, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.db import get_session
from backend.models import Show, SetVersion, AnalysisJob, AnalysisResult, JobStatus, CrowdSize, CrowdEnergy, ShowRating
from backend import storage

router = APIRouter(prefix="/shows", tags=["shows"])


def require_show(show_id: UUID, session: Session) -> Show:
    """Fetch show or raise 404."""
    show = session.get(Show, show_id)
    if not show:
        raise HTTPException(404, "Show not found")
    return show


class ShowCreate(BaseModel):
    set_version_id: UUID
    date: date
    venue: Optional[str] = None
    crowd_size: Optional[CrowdSize] = None
    crowd_energy: Optional[CrowdEnergy] = None
    notes: Optional[str] = None
    rating: Optional[ShowRating] = None


class ShowUpdate(BaseModel):
    date: Optional[date] = None
    venue: Optional[str] = None
    crowd_size: Optional[CrowdSize] = None
    crowd_energy: Optional[CrowdEnergy] = None
    notes: Optional[str] = None
    rating: Optional[ShowRating] = None


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("")
def list_shows(session: Session = Depends(get_session)):
    return session.exec(select(Show)).all()


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_show(body: ShowCreate, session: Session = Depends(get_session)):
    if not session.get(SetVersion, body.set_version_id):
        raise HTTPException(404, "SetVersion not found")
    show = Show(**body.model_dump())
    session.add(show)
    session.commit()
    session.refresh(show)
    return show


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{show_id}")
def get_show(show_id: UUID, session: Session = Depends(get_session)):
    show = require_show(show_id, session)

    job = session.exec(
        select(AnalysisJob).where(AnalysisJob.show_id == show_id)
    ).first()

    result = None
    if job and job.status == JobStatus.complete:
        result = session.exec(
            select(AnalysisResult).where(AnalysisResult.analysis_job_id == job.id)
        ).first()

    return {
        **show.model_dump(),
        "job": job.model_dump() if job else None,
        "result": result.model_dump() if result else None,
    }


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch("/{show_id}")
def update_show(show_id: UUID, body: ShowUpdate, session: Session = Depends(get_session)):
    show = require_show(show_id, session)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(show, k, v)
    session.add(show)
    session.commit()
    session.refresh(show)
    return show


# ── Audio upload ──────────────────────────────────────────────────────────────

@router.post("/{show_id}/audio")
def upload_show_audio(
    show_id: UUID,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    show = require_show(show_id, session)
    if show.audio_key:
        raise HTTPException(409, "Audio already uploaded for this show")

    existing_job = session.exec(
        select(AnalysisJob).where(AnalysisJob.show_id == show_id)
    ).first()
    if existing_job:
        raise HTTPException(409, "Analysis job already exists for this show")

    try:
        data = file.file.read()
        audio_key = storage.upload(data, file.content_type or "audio/webm", prefix="shows")
    except Exception as e:
        raise HTTPException(500, f"R2 upload failed: {e}")

    show.audio_key = audio_key
    session.add(show)

    job = AnalysisJob(show_id=show_id)
    session.add(job)
    session.commit()
    session.refresh(job)

    _trigger_analysis(job.id, show, session)

    return {"job_id": job.id, "audio_key": audio_key}


def _trigger_analysis(job_id: UUID, show: Show, session: Session):
    from backend.config import MODAL_APP_NAME, BACKEND_BASE_URL
    from backend.models import SetVersionItem, Version

    items = session.exec(
        select(SetVersionItem)
        .where(SetVersionItem.set_version_id == show.set_version_id)
        .order_by(SetVersionItem.position)
    ).all()
    set_text = "\n\n".join(
        session.get(Version, item.version_id).body for item in items
    )

    try:
        import modal
        # Modal automatically uses MODAL_TOKEN_ID and MODAL_TOKEN_SECRET from environment
        # No explicit configuration needed - Railway env vars are sufficient

        fn = modal.Function.from_name(MODAL_APP_NAME, "analyze_show")
        fn.spawn(
            str(job_id),
            show.audio_key,
            set_text,
            f"{BACKEND_BASE_URL}/internal/jobs/{job_id}/complete",
        )
    except Exception as e:
        # Modal not deployed yet or unavailable — job stays pending
        import logging
        logging.warning(f"Could not trigger Modal job: {e}")
