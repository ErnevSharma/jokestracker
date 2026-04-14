# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Comedy Set Tracker — a single-user PWA for standup comedians to track material evolution, assemble sets, and analyze show recordings with ML-powered laugh detection. No authentication required (personal deployment).

Read `DESIGN.md` for the full system design document.

## Architecture

**Monorepo structure:**
- `backend/` — FastAPI + SQLModel + SQLite
- `frontend/` — React 18 + Vite 5 + Tailwind CSS 3
- Deployment: Railway (always-on server with persistent volume at `/data`)
- ML: Modal serverless GPU functions for Whisper transcription + laugh analysis
- Storage: Cloudflare R2 (S3-compatible) for audio files

**Data model has two independent lineages converging at Show:**

```
Material:   Bit → Version → Annotation (with optional audio)
Sets:       ComedySet → SetVersion → SetVersionItem → references Version
Shows:      Show → AnalysisJob → AnalysisResult (ML output)
```

**Key invariants:**
- Versions are immutable after creation (body is write-once)
- SetVersions are immutable (edits create new versions)
- Annotations: `char_start`, `char_end`, `audio_key` immutable; only `note` is patchable
- Bits use soft-delete (status = `dead`) to preserve Version history
- Immutability enforced at API layer, not database

## Development Commands

**Setup backend (first time):**
```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Run development servers (two terminals):**
```bash
# Terminal 1 — Backend (runs on :8000)
backend/.venv/bin/uvicorn backend.main:app --reload

# Terminal 2 — Frontend (runs on :5173)
cd frontend && npm run dev
```

**Run integration tests:**
```bash
backend/.venv/bin/python backend/test_api.py
```
19 assertions covering all route groups. Requires backend server running. No mocking — tests hit real SQLite.

**Deploy Modal analysis function:**
```bash
modal deploy backend/jobs/analyze.py
```
Deploys to Modal's GPU infrastructure. Requires `modal token set` first.

**Production build:**
```bash
docker build -t jokestracker .
```
Multi-stage: builds frontend in Node 20, then copies dist to Python 3.12 image. Railway auto-deploys on push to `main`.

## Audio Pipeline

**Three audio paths through the system:**

1. **Annotation audio (delivery memos):**
   - `POST /annotations/:id/audio` → multipart upload → backend writes to R2 with prefix `annotations/` → stores `audio_key` in database
   - `GET /annotations/:id/audio` → backend returns presigned R2 URL (1 hour expiry) → frontend fetches directly from R2
   - Frontend component: `AnnotationPlayer` (lazy fetch on play)

2. **Show audio uploads (for analysis):**
   - `POST /shows/:id/audio` → multipart upload → backend writes to R2 with prefix `shows/` → creates `AnalysisJob` with status `pending` → spawns Modal function fire-and-forget
   - Modal: downloads from R2 → runs Whisper large-v3 → laugh detection → callback to FastAPI
   - `POST /internal/jobs/:id/complete` → writes `AnalysisResult` → sets job status to `complete`
   - Frontend polls `GET /jobs/:id` every 3 seconds until complete

3. **Modal function signature:**
   ```python
   analyze_show(job_id: str, audio_key: str, set_text: str, callback_url: str)
   ```
   - Runs on T4 GPU with faster-whisper
   - Returns transcript, laugh timestamps, line scores, and diff of planned vs actual
   - On failure, POSTs to `/internal/jobs/:id/fail` with error string

**Storage layer:** `backend/storage.py` wraps boto3 for R2. Functions: `upload()`, `download()`, `presigned_url()`. Keys are `{prefix}/{uuid4}` with no extension.

## Frontend Architecture

**No router.** Single-page app with tab-based navigation managed by `useState` in `App.jsx`:
- Tabs: `BitsView`, `SetsView`, `ShowsView`

**API calls:** All network requests go through `frontend/src/api.js`. Base URL from `VITE_API_BASE`:
- Development: `http://localhost:8000` (set in `frontend/.env.development`)
- Production: empty string → same-origin requests

**Key components:**
- `AnnotatedText` — renders Version body with yellow highlights for annotations, character-offset selection for creating new annotations
- `VersionTimeline` — horizontal chips showing version history
- `AudioRecorder` — MediaRecorder API wrapper, produces `audio/webm` Blob
- `LaughHeatmap` — visualizes `line_scores` from AnalysisResult with color-coded bars
- `SetBuilder` — drag-and-drop UI for composing SetVersions from Bit Versions

## Database

**SQLite paths:**
- Development: `sqlite:///./data/db.sqlite` (relative path, gitignored)
- Production: `sqlite:////data/db.sqlite` (Railway persistent volume)

**Schema defined in `backend/models.py` using SQLModel.** Tables auto-created via `SQLModel.metadata.create_all(engine)` on startup.

**Enums:**
- `BitStatus`: drafting | working | dead
- `JobStatus`: pending | running | complete | failed
- `ShowRating`: killed | ok | died
- `CrowdSize`: small | medium | large
- `CrowdEnergy`: dead | lukewarm | warm | hot

## Environment Variables

**Backend (`backend/config.py`):**
- `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` — required for R2
- `DATABASE_URL` — defaults to `sqlite:///./data/db.sqlite`
- `MODAL_APP_NAME` — defaults to `jokestracker`
- `BACKEND_BASE_URL` — defaults to `http://localhost:8000`

**Frontend:**
- `VITE_API_BASE` — API base URL (set in `frontend/.env.development` for dev, empty in prod)

**Modal secret:** `jokestracker-r2` contains R2 credentials for Modal function to download/upload audio.

## API Design Patterns

**Diff endpoint:** `GET /versions/:id/diff/:other_id` returns Python `difflib` opcodes + full line arrays. Frontend reconstructs diff view.

**Audio upload:** Multipart form. Backend reads bytes → pushes to R2 via boto3 → stores object key → returns key. Browser never talks directly to R2 for uploads.

**Job callback:** Modal POSTs to `/internal/jobs/:id/complete` with full result payload. Not in public docs. Client polls `/jobs/:id` until status changes.

**No pagination.** Personal app with small data. All list endpoints return full collections.

## Known Limitations

- **Laugh detection:** `LaughterSegmentation` not pip-installable. `_detect_laughs()` returns `[]`. Line scores show 0 laughs.
- **Audio cleanup:** Deleting annotations/shows doesn't delete R2 objects. Storage grows indefinitely.
- **Job retry:** Failed Modal jobs stay `failed`. No automatic retry. User must re-upload.
- **Diff alignment:** Fuzzy word matching can misalign on heavily improvised performances.

## Code Style

- Backend routers organized by resource group in `backend/routers/`
- All routes return JSON, no HTML rendering
- Frontend components are functional with hooks
- Use SQLModel for database models (combines SQLAlchemy + Pydantic)
- No type hints in Modal function imports (imported inside function for cold start optimization)
