from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.db import get_session
from backend.models import Line, LineAnnotation
from backend import storage

router = APIRouter(prefix="/lines", tags=["lines"])


def require_line(line_id: UUID, session: Session) -> Line:
    """Fetch line or raise 404."""
    line = session.get(Line, line_id)
    if not line:
        raise HTTPException(404, "Line not found")
    return line


def require_line_annotation(annotation_id: UUID, session: Session) -> LineAnnotation:
    """Fetch line annotation or raise 404."""
    annotation = session.get(LineAnnotation, annotation_id)
    if not annotation:
        raise HTTPException(404, "Annotation not found")
    return annotation


class LineCreate(BaseModel):
    body: str


class LineUpdate(BaseModel):
    body: str


class LineAnnotationCreate(BaseModel):
    char_start: int
    char_end: int
    note: Optional[str] = None


class LineAnnotationUpdate(BaseModel):
    note: str


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("")
def list_lines(session: Session = Depends(get_session)):
    lines = session.exec(select(Line).order_by(Line.updated_at.desc())).all()
    return lines


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_line(body: LineCreate, session: Session = Depends(get_session)):
    line = Line(**body.model_dump())
    session.add(line)
    session.commit()
    session.refresh(line)
    return line


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{line_id}")
def get_line(line_id: UUID, session: Session = Depends(get_session)):
    line = require_line(line_id, session)
    annotations = session.exec(
        select(LineAnnotation).where(LineAnnotation.line_id == line_id)
    ).all()
    return {**line.model_dump(), "annotations": [a.model_dump() for a in annotations]}


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch("/{line_id}")
def update_line(line_id: UUID, body: LineUpdate, session: Session = Depends(get_session)):
    line = require_line(line_id, session)
    line.body = body.body
    line.updated_at = datetime.utcnow()
    session.add(line)
    session.commit()
    session.refresh(line)
    return line


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{line_id}", status_code=204)
def delete_line(line_id: UUID, session: Session = Depends(get_session)):
    line = require_line(line_id, session)
    # Delete all annotations first
    annotations = session.exec(
        select(LineAnnotation).where(LineAnnotation.line_id == line_id)
    ).all()
    for annotation in annotations:
        session.delete(annotation)
    session.delete(line)
    session.commit()


# ── Line Annotations ──────────────────────────────────────────────────────────

@router.post("/{line_id}/annotations", status_code=201)
def create_line_annotation(
    line_id: UUID, body: LineAnnotationCreate, session: Session = Depends(get_session)
):
    line = require_line(line_id, session)
    if body.char_start < 0 or body.char_end > len(line.body) or body.char_start >= body.char_end:
        raise HTTPException(422, "char_start/char_end out of range")
    annotation = LineAnnotation(line_id=line_id, **body.model_dump())
    session.add(annotation)
    session.commit()
    session.refresh(annotation)
    return annotation


@router.patch("/annotations/{annotation_id}")
def update_line_annotation(
    annotation_id: UUID, body: LineAnnotationUpdate, session: Session = Depends(get_session)
):
    annotation = require_line_annotation(annotation_id, session)
    annotation.note = body.note
    session.add(annotation)
    session.commit()
    session.refresh(annotation)
    return annotation


@router.delete("/annotations/{annotation_id}", status_code=204)
def delete_line_annotation(annotation_id: UUID, session: Session = Depends(get_session)):
    annotation = require_line_annotation(annotation_id, session)
    session.delete(annotation)
    session.commit()


# ── Annotation Audio ──────────────────────────────────────────────────────────

@router.get("/annotations/{annotation_id}/audio")
def get_line_annotation_audio(annotation_id: UUID, session: Session = Depends(get_session)):
    annotation = require_line_annotation(annotation_id, session)
    if not annotation.audio_key:
        raise HTTPException(404, "No audio attached to this annotation")
    try:
        data, content_type = storage.download(annotation.audio_key)
    except Exception as e:
        raise HTTPException(500, f"Could not retrieve audio: {e}")
    return Response(content=data, media_type=content_type)


@router.post("/annotations/{annotation_id}/audio")
def upload_line_annotation_audio(
    annotation_id: UUID,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    annotation = require_line_annotation(annotation_id, session)
    if annotation.audio_key:
        raise HTTPException(409, "Audio already attached to this annotation")
    try:
        data = file.file.read()
        key = storage.upload(data, file.content_type or "audio/webm", prefix="line_annotations")
    except Exception as e:
        raise HTTPException(500, f"R2 upload failed: {e}")
    annotation.audio_key = key
    session.add(annotation)
    session.commit()
    session.refresh(annotation)
    return {"audio_key": key}
