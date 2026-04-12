# SPEC.md — Comedy Set Tracker

## Status
Draft — not yet handed to Claude Code

---

## 1. Overview

> A personal web app for tracking the evolution of standup comedy bits. A comedian writes bits, creates immutable versions as they evolve, annotates specific lines with performance notes, records sets, and gets automated analysis (transcript diff + laughter heatmap) from audio recordings.

---

## 2. Goals

- Immutable version history for every bit
- Inline annotations tied to specific character offsets in a version, with optional audio for capturing tone and delivery
- Set management: ordered, versioned, immutable snapshots of which bit versions make up a set
- Per-show performance logging with audio attachment at the show level
- Async audio analysis pipeline: Whisper transcription + laughter detection → per-line heatmap against full set text
- Cross-reference navigation: Bit → Sets it appears in → Shows those sets were performed at
- PWA accessible from phone browser

## 3. Non-Goals (v1)

- No multi-user support
- No authentication (single user, personal deployment)
- No video support (audio only for now)
- No real-time collaboration
- No AI joke suggestions
- No native iOS/Android app
- No R2 audio cleanup on annotation or show deletion

---

## 4. Data Model

### Bit
```
id            UUID, primary key
title         string, required
status        enum: drafting | working | dead
created_at    datetime
updated_at    datetime
```

### Version
```
id            UUID, primary key
bit_id        UUID, foreign key → Bit
body          text, required (the full joke text)
version_num   integer (auto-incremented per bit, starting at 1)
created_at    datetime

IMMUTABLE — no update endpoint exists for body
```

### Annotation
```
id            UUID, primary key
version_id    UUID, foreign key → Version
char_start    integer (offset into version.body)
char_end      integer (offset into version.body)
note          text
audio_key     string, nullable (R2 object key — single audio clip for tone/delivery capture)
created_at    datetime

char_start and char_end are IMMUTABLE — only note and audio_key are patchable
```

### Set
```
id            UUID, primary key
name          string, required
created_at    datetime
updated_at    datetime
```

### SetVersion
```
id            UUID, primary key
set_id        UUID, foreign key → Set
version_num   integer (auto-incremented per set, starting at 1)
created_at    datetime

IMMUTABLE — no update endpoint exists; create a new SetVersion to change the set
```

### SetVersionItem
```
id              UUID, primary key
set_version_id  UUID, foreign key → SetVersion
version_id      UUID, foreign key → Version (the specific bit version in this set)
position        integer (1-based ordering within the set version)

IMMUTABLE — part of the SetVersion snapshot
```

### Show
```
id              UUID, primary key
set_version_id  UUID, foreign key → SetVersion (the exact set ordering performed)
date            date, required
venue           string
crowd_size      enum: small | medium | large
crowd_energy    enum: dead | lukewarm | warm | hot
notes           text
rating          enum: killed | ok | died
audio_key       string, nullable (R2 object key for the show recording)
created_at      datetime
```

### AnalysisJob
```
id              UUID, primary key
show_id         UUID, foreign key → Show
status          enum: pending | running | complete | failed
error           text, nullable
created_at      datetime
completed_at    datetime, nullable
```

### AnalysisResult
```
id                    UUID, primary key
analysis_job_id       UUID, foreign key → AnalysisJob
whisper_transcript    text (raw Whisper output for full show audio)
laugh_timestamps      JSON (array of {start, end} in seconds)
line_scores           JSON (array of {line, laugh_count, laugh_duration})
diff                  JSON (structured diff of full set text vs whisper_transcript)
created_at            datetime
```

---

## 5. API Contract

All endpoints return JSON. All request bodies are JSON unless noted.

### Bits

```
GET    /bits                          → list all bits (id, title, status, version_count)
POST   /bits                          → create bit {title, status}
GET    /bits/:id                      → bit detail + all versions (no bodies)
PATCH  /bits/:id                      → update {title, status} only
DELETE /bits/:id                      → soft delete (sets status=dead)
GET    /bits/:id/appearances          → list all {set, set_version, shows[]} where any version of this bit appears
```

### Versions

```
GET    /bits/:id/versions             → list versions (id, version_num, created_at, char_count)
POST   /bits/:id/versions             → create version {body} — always immutable after creation
GET    /versions/:id                  → version detail + body + annotations
GET    /versions/:id/diff/:other_id   → diff between two versions, returned as structured JSON
```

### Annotations

```
GET    /versions/:id/annotations      → list annotations for a version
POST   /versions/:id/annotations      → create {char_start, char_end, note}
PATCH  /annotations/:id               → update {note} only — offsets and audio_key are immutable once set
DELETE /annotations/:id               → hard delete (audio in R2 is NOT cleaned up in v1)
POST   /annotations/:id/audio         → multipart upload; stores to R2, sets audio_key on annotation
```

### Sets

```
GET    /sets                          → list all sets (id, name, version_count)
POST   /sets                          → create {name}
GET    /sets/:id                      → set detail + list of set versions (no items)
PATCH  /sets/:id                      → update {name}
GET    /sets/:id/shows                → list all shows across all set versions of this set
```

### Set Versions

```
GET    /sets/:id/versions                     → list set versions (id, version_num, created_at, item_count)
POST   /sets/:id/versions                     → create set version {items: [{version_id, position}]} — immutable after creation
GET    /set-versions/:id                      → set version detail + ordered items (includes bit title and version_num per item)
```

### Shows

```
GET    /shows                         → list shows (id, date, venue, set_version_id)
POST   /shows                         → create {set_version_id, date, venue, crowd_size, crowd_energy, notes, rating}
GET    /shows/:id                     → show detail + analysis job/result if exists
PATCH  /shows/:id                     → update {date, venue, crowd_size, crowd_energy, notes, rating}
POST   /shows/:id/audio               → multipart upload; stores to R2, sets audio_key, kicks off AnalysisJob
```

### Analysis

```
GET    /jobs/:id                      → job status + result if complete
```

---

## 6. Tech Stack

### Frontend
- React + Vite
- Tailwind CSS (no component library)
- PWA manifest + service worker for home screen install
- No React Router — single page, tab-based navigation

### Backend
- FastAPI
- SQLModel (SQLAlchemy + Pydantic combined)
- SQLite (single file, `/data/db.sqlite`)
- Cloudflare R2 via boto3 (S3-compatible)
- Modal for async GPU jobs

### ML / Analysis
- Whisper large-v3 (via faster-whisper for speed)
- LaughterSegmentation model (Interspeech 2024, omine-me/LaughterSegmentation)
- Both run inside a Modal function, not on the app server

### Infrastructure
- Backend: Railway — project `endearing-rejoicing`, service `tranquil-joy` (always-on, small instance)
- ML jobs: Modal — workspace `ernev-sharma-us`, app name `jokestracker` (serverless GPU, spun up per job)
- File storage: Cloudflare R2 — bucket `jokestracker-audio`, endpoint `https://4c3b4be75d916e4db343338e22dbfd48.r2.cloudflarestorage.com`
- Database: SQLite on persistent volume — production path `/data/db.sqlite` (volume `tranquil-joy-volume` mounted at `/data`)

---

## 7. Key Behaviors

### Immutability
- `Version.body` is write-once. No PATCH or PUT endpoint exists for it.
- `Annotation.char_start` and `char_end` are write-once. Only `note` is patchable. `audio_key` is set once via the audio upload endpoint and not patchable thereafter.
- `SetVersion` and its `SetVersionItem` rows are write-once. To change a set's contents or ordering, create a new SetVersion.
- Deleting a bit is a soft delete (status flag). Versions are never deleted.

### Analysis Pipeline
1. Client uploads show audio to `POST /shows/:id/audio`
2. Backend uploads file to R2, sets `audio_key` on the Show, creates `AnalysisJob` with status `pending`, returns `{job_id}` immediately
3. Backend enqueues Modal job (async, do not await)
4. Modal job:
   - Pulls audio from R2
   - Runs faster-whisper → full show transcript with word-level timestamps
   - Runs LaughterSegmentation → laugh timestamp ranges
   - Assembles the full set text by concatenating `Version.body` for each `SetVersionItem` in order
   - Computes diff of set text vs whisper transcript using difflib
   - Maps laugh timestamps to lines using the 3-second post-line attribution window
   - Writes `AnalysisResult`
   - Updates `AnalysisJob.status` to `complete`
5. Client polls `GET /jobs/:id` until status is `complete`, then fetches result via `GET /shows/:id`

### Diff Logic
- Full set text is split into lines/sentences across all bits in the SetVersion (in order)
- Whisper transcript is aligned to the same structure
- Diff is computed with difflib (Python stdlib), stored as JSON
- Never recomputed on the fly — stored once at analysis time

### Laugh-to-Line Mapping
- Each Whisper word has a timestamp
- Each line is mapped to a time range (first word start → last word end)
- Any laugh timestamp that falls within 3 seconds after a line end is attributed to that line
- Result stored in `line_scores`

### Cross-Reference Navigation
- `GET /bits/:id/appearances` enables the Bit → Set → Show drill-down in the UI
- Response shape: `{bit, versions: [{version, set_versions: [{set_version, set, shows: [...]}]}]}`

---

## 8. File Structure

```
/
├── SPEC.md
├── AGENTS.md
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── views/          # BitsView, VersionView, SetsView, ShowsView, AnalysisView
│   │   ├── components/     # VersionTimeline, AnnotatedText, LaughHeatmap, SetBuilder
│   │   └── api.js          # all fetch calls, one file
│   ├── public/
│   │   └── manifest.json
│   └── vite.config.js
├── backend/
│   ├── main.py             # FastAPI app, router registration
│   ├── models.py           # SQLModel table definitions
│   ├── routers/            # bits.py, versions.py, annotations.py, sets.py, shows.py, analysis.py
│   ├── storage.py          # R2 upload/download helpers
│   ├── jobs/
│   │   └── analyze.py      # Modal function definition
│   └── db.py               # engine + session dependency
└── data/                   # gitignored, SQLite lives here locally
```

---

## 9. Out of Scope Clarifications

- Do not add JWT or session auth
- Do not add user accounts or login screens
- Do not add rate limiting
- Do not add pagination (personal app, small data)
- Do not add websockets — polling is fine for job status
- Do not use an ORM other than SQLModel
- Do not add Docker unless explicitly asked
- Do not clean up R2 objects on deletion in v1

---

## 10. Open Questions

> Fill these in before handing to Claude Code. Unresolved questions here will become bad assumptions in the code.

- [x] What is the R2 bucket name and region? → `jokestracker-audio`, endpoint `https://4c3b4be75d916e4db343338e22dbfd48.r2.cloudflarestorage.com`
- [x] What is the Modal app name? → `jokestracker` (workspace: `ernev-sharma-us`)
- [x] Where does the SQLite file live in production? → `/data/db.sqlite` (Railway volume `tranquil-joy-volume` mounted at `/data`)
- [x] What is the base URL for the deployed backend? → `https://tranquil-joy-production-e0ef.up.railway.app`
- [ ] Laugh attribution window — is 3 seconds post-line the right heuristic?
