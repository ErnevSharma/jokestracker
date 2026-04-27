from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.db import get_session
from backend.models import Annotation, Version
from backend import storage

router = APIRouter(tags=["annotations"])


def require_version(version_id: UUID, session: Session) -> Version:
    """Fetch version or raise 404."""
    version = session.get(Version, version_id)
    if not version:
        raise HTTPException(404, "Version not found")
    return version


def require_annotation(annotation_id: UUID, session: Session) -> Annotation:
    """Fetch annotation or raise 404."""
    annotation = session.get(Annotation, annotation_id)
    if not annotation:
        raise HTTPException(404, "Annotation not found")
    return annotation


class AnnotationCreate(BaseModel):
    char_start: int
    char_end: int
    note: Optional[str] = None


class AnnotationUpdate(BaseModel):
    note: str


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/versions/{version_id}/annotations")
def list_annotations(version_id: UUID, session: Session = Depends(get_session)):
    require_version(version_id, session)
    return session.exec(
        select(Annotation).where(Annotation.version_id == version_id)
    ).all()


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("/versions/{version_id}/annotations", status_code=201)
def create_annotation(version_id: UUID, body: AnnotationCreate, session: Session = Depends(get_session)):
    version = require_version(version_id, session)
    if body.char_start < 0 or body.char_end > len(version.body) or body.char_start >= body.char_end:
        raise HTTPException(422, "char_start/char_end out of range")
    annotation = Annotation(version_id=version_id, **body.model_dump())
    session.add(annotation)
    session.commit()
    session.refresh(annotation)
    return annotation


# ── Update note ───────────────────────────────────────────────────────────────

@router.patch("/annotations/{annotation_id}")
def update_annotation(annotation_id: UUID, body: AnnotationUpdate, session: Session = Depends(get_session)):
    annotation = require_annotation(annotation_id, session)
    annotation.note = body.note
    session.add(annotation)
    session.commit()
    session.refresh(annotation)
    return annotation


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/annotations/{annotation_id}", status_code=204)
def delete_annotation(annotation_id: UUID, session: Session = Depends(get_session)):
    annotation = require_annotation(annotation_id, session)
    session.delete(annotation)
    session.commit()


# ── Audio proxy ───────────────────────────────────────────────────────────────

@router.get("/annotations/{annotation_id}/audio")
def get_annotation_audio(annotation_id: UUID, session: Session = Depends(get_session)):
    annotation = require_annotation(annotation_id, session)
    if not annotation.audio_key:
        raise HTTPException(404, "No audio attached to this annotation")
    try:
        data, content_type = storage.download(annotation.audio_key)
    except Exception as e:
        raise HTTPException(500, f"Could not retrieve audio: {e}")
    return Response(content=data, media_type=content_type)


# ── Audio upload ──────────────────────────────────────────────────────────────

@router.post("/annotations/{annotation_id}/audio")
def upload_annotation_audio(
    annotation_id: UUID,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    annotation = require_annotation(annotation_id, session)
    if annotation.audio_key:
        raise HTTPException(409, "Audio already attached to this annotation")
    try:
        data = file.file.read()
        key = storage.upload(data, file.content_type or "audio/webm", prefix="annotations")
    except Exception as e:
        raise HTTPException(500, f"R2 upload failed: {e}")
    annotation.audio_key = key
    session.add(annotation)
    session.commit()
    session.refresh(annotation)
    return {"audio_key": key}
