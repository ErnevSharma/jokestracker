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


def require_job(job_id: UUID, session: Session) -> AnalysisJob:
    """Fetch analysis job or raise 404."""
    job = session.get(AnalysisJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


class JobCompletePayload(BaseModel):
    whisper_transcript: str
    word_timestamps: list  # Word-level timestamps from Whisper
    laugh_timestamps: list


# ── Poll job status ───────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}")
def get_job(job_id: UUID, session: Session = Depends(get_session)):
    job = require_job(job_id, session)
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
async def complete_job(job_id: UUID, payload: JobCompletePayload, session: Session = Depends(get_session)):
    job = require_job(job_id, session)

    # Store initial result without Claude analysis
    result = AnalysisResult(
        analysis_job_id=job_id,
        whisper_transcript=payload.whisper_transcript,
        laugh_timestamps=json.dumps(payload.laugh_timestamps),
        claude_analysis=None,  # Will be added in background
    )
    session.add(result)

    job.status = JobStatus.complete
    job.completed_at = datetime.utcnow()
    session.add(job)
    session.commit()
    session.refresh(result)

    # Return immediately to Modal (prevents timeout)
    # Run Claude analysis in background
    import asyncio
    asyncio.create_task(_run_claude_analysis_async(
        result.id,
        payload.word_timestamps,
        payload.laugh_timestamps
    ))

    return {"ok": True}


async def _run_claude_analysis_async(result_id: UUID, word_timestamps: list, laugh_timestamps: list):
    """Run Claude analysis in background task."""
    print(f"Starting Claude analysis for result {result_id}...")

    # Run synchronous Claude call in thread pool
    import asyncio
    from starlette.concurrency import run_in_threadpool

    claude_analysis = await run_in_threadpool(
        _analyze_with_claude,
        word_timestamps,
        laugh_timestamps
    )

    if claude_analysis:
        print(f"✓ Claude analysis succeeded for result {result_id}")
        # Update the result in database
        from backend.db import get_session
        with next(get_session()) as session:
            result = session.get(AnalysisResult, result_id)
            if result:
                result.claude_analysis = claude_analysis
                session.add(result)
                session.commit()
    else:
        print(f"✗ Claude analysis returned None for result {result_id}")


def _analyze_with_claude(word_timestamps: list, laugh_timestamps: list) -> Optional[str]:
    """
    Use Claude to analyze comedy performance and intelligently attribute laughs to jokes.
    Returns JSON string with joke segmentation and performance insights.
    """
    try:
        import os
        from anthropic import Anthropic

        # Check if API key is available
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("ANTHROPIC_API_KEY not set, skipping Claude analysis")
            return None

        client = Anthropic(api_key=api_key)

        # Format word timestamps for Claude
        word_text = "\n".join([
            f"[{w['start']:.1f}s] {w['word']}"
            for w in word_timestamps[:500]  # Limit to first 500 words
        ])

        # Format laugh timestamps
        laugh_text = "\n".join([
            f"Laugh: {l['start']:.1f}s - {l['end']:.1f}s (duration: {l['end']-l['start']:.1f}s)"
            for l in laugh_timestamps
        ])

        prompt = f"""You are analyzing a standup comedy performance transcript with detected audience laughter.

TRANSCRIPT WITH WORD TIMESTAMPS:
{word_text}

DETECTED LAUGHS:
{laugh_text}

Your task:
1. Segment the transcript into discrete jokes/bits (identify natural joke boundaries)
2. For each joke, determine:
   - Full text of the joke
   - Setup and punchline (if applicable)
   - Tags (e.g., observational, story, one-liner, callback, crowd-work)
   - Which detected laughs this joke generated (match by timestamp proximity - laughs typically come 0-3 seconds after punchline)
   - Rating: "killed" (multiple strong laughs), "strong" (consistent laugh), "medium" (some response), "weak" (minimal response), or "died" (no laugh)

3. Provide overall performance summary including:
   - Total jokes attempted
   - How many got laughs (jokes_with_laughs)
   - Hit rate (% that landed)
   - Jokes per minute
   - Which jokes were strongest/weakest
   - Any callbacks you noticed

Output ONLY valid JSON (no markdown, no code blocks) with this exact structure:
{{
  "jokes": [
    {{
      "id": 1,
      "start_time": 0.5,
      "end_time": 8.2,
      "text": "full joke text",
      "setup": "setup text (optional)",
      "punchline": "punchline text (optional)",
      "tags": ["observational", "story"],
      "laughs": [
        {{"timestamp": 5.2, "duration": 2.1, "intensity": "strong"}}
      ],
      "rating": "killed",
      "laugh_count": 2,
      "total_laugh_duration": 4.5
    }}
  ],
  "summary": {{
    "total_jokes": 12,
    "jokes_with_laughs": 9,
    "hit_rate": 0.75,
    "jokes_per_minute": 2.1,
    "strongest_jokes": [1, 5, 8],
    "weakest_jokes": [3, 11],
    "callbacks": ["repeated airport theme 3 times"],
    "overall_assessment": "Strong set with good pacing. Opening killed, middle section dragged slightly, closed strong. Callbacks landed well."
  }}
}}"""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract JSON from response
        analysis_text = response.content[0].text.strip()

        # Remove markdown code blocks if present
        if analysis_text.startswith("```"):
            analysis_text = analysis_text.split("```")[1]
            if analysis_text.startswith("json"):
                analysis_text = analysis_text[4:]
            analysis_text = analysis_text.strip()

        # Validate JSON
        json.loads(analysis_text)  # Just validate, return as string

        return analysis_text

    except Exception as e:
        import traceback
        print(f"Claude analysis failed: {e}")
        print(traceback.format_exc())
        return None


@router.post("/internal/jobs/{job_id}/fail", include_in_schema=False)
def fail_job(job_id: UUID, error: str, session: Session = Depends(get_session)):
    job = require_job(job_id, session)
    job.status = JobStatus.failed
    job.error = error
    job.completed_at = datetime.utcnow()
    session.add(job)
    session.commit()
    return {"ok": True}
