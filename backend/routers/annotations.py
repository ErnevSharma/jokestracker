from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.db import get_session
from backend.models import Annotation, Version
from backend import storage

router = APIRouter(tags=["annotations"])


class AnnotationCreate(BaseModel):
    char_start: int
    char_end: int
    note: Optional[str] = None


class AnnotationUpdate(BaseModel):
    note: str


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/versions/{version_id}/annotations")
def list_annotations(version_id: UUID, session: Session = Depends(get_session)):
    version = session.get(Version, version_id)
    if not version:
        raise HTTPException(404, "Version not found")
    return session.exec(
        select(Annotation).where(Annotation.version_id == version_id)
    ).all()


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("/versions/{version_id}/annotations", status_code=201)
def create_annotation(version_id: UUID, body: AnnotationCreate, session: Session = Depends(get_session)):
    version = session.get(Version, version_id)
    if not version:
        raise HTTPException(404, "Version not found")
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
    annotation = session.get(Annotation, annotation_id)
    if not annotation:
        raise HTTPException(404, "Annotation not found")
    annotation.note = body.note
    session.add(annotation)
    session.commit()
    session.refresh(annotation)
    return annotation


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/annotations/{annotation_id}", status_code=204)
def delete_annotation(annotation_id: UUID, session: Session = Depends(get_session)):
    annotation = session.get(Annotation, annotation_id)
    if not annotation:
        raise HTTPException(404, "Annotation not found")
    session.delete(annotation)
    session.commit()


# ── Audio playback URL ────────────────────────────────────────────────────────

@router.get("/annotations/{annotation_id}/audio")
def get_annotation_audio(annotation_id: UUID, session: Session = Depends(get_session)):
    annotation = session.get(Annotation, annotation_id)
    if not annotation:
        raise HTTPException(404, "Annotation not found")
    if not annotation.audio_key:
        raise HTTPException(404, "No audio attached to this annotation")
    try:
        url = storage.presigned_url(annotation.audio_key)
    except Exception as e:
        raise HTTPException(500, f"Could not generate URL: {e}")
    return {"url": url}


# ── Audio upload ──────────────────────────────────────────────────────────────

@router.post("/annotations/{annotation_id}/audio")
def upload_annotation_audio(
    annotation_id: UUID,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    annotation = session.get(Annotation, annotation_id)
    if not annotation:
        raise HTTPException(404, "Annotation not found")
    if annotation.audio_key:
        raise HTTPException(409, "Audio already attached to this annotation")
    try:
        data = file.file.read()
        content_type = file.content_type or "audio/webm"
        key = storage.upload(data, content_type, prefix="annotations")
    except Exception as e:
        raise HTTPException(500, f"R2 upload failed: {e}")
    annotation.audio_key = key
    session.add(annotation)
    session.commit()
    session.refresh(annotation)
    return {"audio_key": key}
