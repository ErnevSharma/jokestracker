from datetime import datetime, date
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


# ── Enums ────────────────────────────────────────────────────────────────────

class BitStatus(str, Enum):
    drafting = "drafting"
    working = "working"
    dead = "dead"


class CrowdSize(str, Enum):
    small = "small"
    medium = "medium"
    large = "large"


class CrowdEnergy(str, Enum):
    dead = "dead"
    lukewarm = "lukewarm"
    warm = "warm"
    hot = "hot"


class ShowRating(str, Enum):
    killed = "killed"
    ok = "ok"
    died = "died"


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    complete = "complete"
    failed = "failed"


# ── Table Models ──────────────────────────────────────────────────────────────

class Bit(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    title: str
    status: BitStatus = BitStatus.drafting
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Version(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    bit_id: UUID = Field(foreign_key="bit.id")
    body: str
    version_num: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Annotation(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    version_id: UUID = Field(foreign_key="version.id")
    char_start: int
    char_end: int
    note: Optional[str] = None
    audio_key: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ComedySet(SQLModel, table=True):
    __tablename__ = "comedy_set"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SetVersion(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    set_id: UUID = Field(foreign_key="comedy_set.id")
    version_num: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SetVersionItem(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    set_version_id: UUID = Field(foreign_key="setversion.id")
    version_id: UUID = Field(foreign_key="version.id")
    position: int


class Show(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    set_version_id: UUID = Field(foreign_key="setversion.id")
    date: date
    venue: Optional[str] = None
    crowd_size: Optional[CrowdSize] = None
    crowd_energy: Optional[CrowdEnergy] = None
    notes: Optional[str] = None
    rating: Optional[ShowRating] = None
    audio_key: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AnalysisJob(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    show_id: UUID = Field(foreign_key="show.id")
    status: JobStatus = JobStatus.pending
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class AnalysisResult(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    analysis_job_id: UUID = Field(foreign_key="analysisjob.id")
    whisper_transcript: str
    laugh_timestamps: Optional[str] = Field(default=None)   # JSON string
    line_scores: Optional[str] = Field(default=None)        # JSON string
    diff: Optional[str] = Field(default=None)               # JSON string
    claude_analysis: Optional[str] = Field(default=None)    # JSON string with AI-powered joke segmentation
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Line(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    body: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LineAnnotation(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    line_id: UUID = Field(foreign_key="line.id")
    char_start: int
    char_end: int
    note: Optional[str] = None
    audio_key: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
