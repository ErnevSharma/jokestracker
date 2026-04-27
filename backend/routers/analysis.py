import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.db import get_session
from backend.models import AnalysisJob, AnalysisResult, JobStatus

router = APIRouter(tags=["analysis"])


class JobCompletePayload(BaseModel):
    whisper_transcript: str
    laugh_timestamps: list
    line_scores: list
    diff: list
    claude_analysis: Optional[str] = None


# ── Poll job status ───────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}")
def get_job(job_id: UUID, session: Session = Depends(get_session)):
    job = session.get(AnalysisJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    result = None
    if job.status == JobStatus.complete:
        result = session.exec(
            select(AnalysisResult).where(AnalysisResult.analysis_job_id == job_id)
        ).first()

    return {
        **job.model_dump(),
        "result": result.model_dump() if result else None,
    }


# ── Modal callback ────────────────────────────────────────────────────────────

@router.post("/internal/jobs/{job_id}/complete", include_in_schema=False)
def complete_job(job_id: UUID, payload: JobCompletePayload, session: Session = Depends(get_session)):
    job = session.get(AnalysisJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    result = AnalysisResult(
        analysis_job_id=job_id,
        whisper_transcript=payload.whisper_transcript,
        laugh_timestamps=json.dumps(payload.laugh_timestamps),
        line_scores=json.dumps(payload.line_scores),
        diff=json.dumps(payload.diff),
        claude_analysis=payload.claude_analysis,  # Already JSON string from Modal
    )
    session.add(result)

    job.status = JobStatus.complete
    job.completed_at = datetime.utcnow()
    session.add(job)
    session.commit()
    return {"ok": True}


@router.post("/internal/jobs/{job_id}/fail", include_in_schema=False)
def fail_job(job_id: UUID, error: str, session: Session = Depends(get_session)):
    job = session.get(AnalysisJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    job.status = JobStatus.failed
    job.error = error
    job.completed_at = datetime.utcnow()
    session.add(job)
    session.commit()
    return {"ok": True}
