# Comedy Set Tracker — System Design

## Overview

A personal web app for a standup comedian to track the evolution of material. Bits are written and versioned, annotated with delivery notes, assembled into ordered sets, and performed at shows. Audio from shows is uploaded and analyzed to produce a transcript and per-line laugh heatmap.

The app is a PWA accessible from a phone browser. There is no authentication — it is a single-user personal deployment.

---

## Architecture

```
Browser (PWA)
     │
     │  HTTP (same-origin in production, CORS in dev)
     ▼
FastAPI (Railway)
     ├── SQLite on Railway volume  (/data/db.sqlite)
     ├── Cloudflare R2             (audio files)
     └── Modal (async)            (Whisper + analysis)
              │
              └── callback → FastAPI  (POST /internal/jobs/:id/complete)
```

**Key properties:**
- Single process, single database file, no message broker
- Audio is stored in object storage (R2), never on the app server
- ML runs on-demand on a GPU worker (Modal), not on the app server
- The backend serves both the API and the built frontend from the same process

---

## Data Model

The data model has two independent lineages that converge at `Show`.

### Lineage 1 — Material

```
Bit  ──(1:many)──  Version  ──(1:many)──  Annotation
                                               └── audio_key (R2)
```

**Bit** is the top-level container for a piece of material. It has a title and a lifecycle status (`drafting → working → dead`). Deletion is a soft delete — status is set to `dead`, nothing is removed from the database.

**Version** is an immutable snapshot of a Bit's text at a point in time. The `body` field is write-once. Every edit produces a new Version; old Versions are never modified or deleted. `version_num` auto-increments per Bit starting at 1.

**Annotation** marks a character range (`char_start`, `char_end`) within a specific Version's body. It captures a text note and an optional audio clip (a delivery memo — the comedian records themselves saying the line to capture tone). `char_start` and `char_end` are immutable once set; only the `note` is patchable. The `audio_key` is set once via an upload endpoint and cannot be changed.

### Lineage 2 — Sets

```
ComedySet  ──(1:many)──  SetVersion  ──(1:many)──  SetVersionItem
                                                         └── version_id → Version
```

**ComedySet** is a named collection of material. Like `Bit`, it is a container.

**SetVersion** is an immutable snapshot of a set's ordered contents. To reorder bits or swap a bit version, you create a new SetVersion. `version_num` auto-increments per ComedySet.

**SetVersionItem** is a row in the ordered list. Each item references a specific `Version` (not just a Bit), so the exact text performed is captured. Items have a `position` integer for ordering.

### Convergence — Shows

```
SetVersion  ──(1:many)──  Show  ──(1:1)──  AnalysisJob  ──(1:1)──  AnalysisResult
```

**Show** records a performance. It references a specific `SetVersion` (capturing the exact ordering performed), and carries metadata: date, venue, crowd size, crowd energy, and a rating (`killed / ok / died`). It also holds `audio_key` — the R2 key for the full show recording.

**AnalysisJob** is created when audio is uploaded to a Show. It tracks the lifecycle of the background ML job: `pending → running → complete | failed`.

**AnalysisResult** holds the output once the job completes: the raw Whisper transcript, laugh timestamps (JSON array of `{start, end}` in seconds), per-line laugh scores, and a structured diff of the planned set text versus what was actually said.

### Cross-Reference

Because a Version belongs to a Bit, and SetVersionItems reference Versions, you can navigate in both directions:

- **Forward**: Bit → which Sets include it → which Shows those Sets were performed at
- **Reverse**: Show → SetVersion → items → Versions → Bits

The `GET /bits/:id/appearances` endpoint materialises the forward path as a single response.

---

## Immutability

Immutability is enforced at the API layer — there are simply no PATCH or PUT endpoints for fields that must not change. The database has no triggers or constraints for this; the application is the enforcement point.

| Model | Immutable fields | Mutable fields |
|---|---|---|
| Version | `body` | — (nothing) |
| Annotation | `char_start`, `char_end`, `audio_key` | `note` |
| SetVersion | entire row | — |
| SetVersionItem | entire row | — |

Bits use soft-delete (`status = dead`) instead of hard delete so Versions are never orphaned.

---

## API Design

All routes return JSON. No pagination (personal app, small data). No authentication.

### Route Groups

| Prefix | Responsibility |
|---|---|
| `/bits` | Bit CRUD, soft delete, appearances |
| `/bits/:id/versions`, `/versions/:id` | Version create, read, diff |
| `/versions/:id/annotations`, `/annotations/:id` | Annotation CRUD, audio upload/playback |
| `/sets`, `/sets/:id/versions`, `/set-versions/:id` | Set and SetVersion management |
| `/shows`, `/shows/:id` | Show CRUD, audio upload |
| `/jobs/:id` | Analysis job polling |
| `/internal/jobs/:id/complete` | Modal callback (not in public docs) |
| `/health` | Liveness check |

### Notable patterns

**Diff endpoint** (`GET /versions/:id/diff/:other_id`): Returns Python `difflib` opcodes plus the full line arrays for both versions. The frontend can reconstruct any diff view from this — the server does no rendering.

**Audio upload** (`POST /annotations/:id/audio`, `POST /shows/:id/audio`): Multipart form upload. The backend reads the bytes, pushes to R2 via boto3, stores the returned object key in the database, and returns the key. The browser never talks to R2 directly.

**Audio playback** (`GET /annotations/:id/audio`): Returns a short-lived (1 hour) presigned R2 URL. The browser fetches this URL directly from R2. The key is never embedded permanently in the frontend — each play request generates a fresh URL.

**Job callback** (`POST /internal/jobs/:id/complete`): Called by the Modal function when analysis finishes. Accepts the full result payload, writes `AnalysisResult`, and flips `AnalysisJob.status` to `complete`. The client polls `GET /jobs/:id` until it sees `complete`.

---

## Audio Storage — Cloudflare R2

R2 is an S3-compatible object store used to hold audio files. The backend communicates with R2 using `boto3` pointed at Cloudflare's S3-compatible endpoint.

Two prefixes are used in the bucket:

| Prefix | Content |
|---|---|
| `annotations/` | Delivery memo clips (per annotation) |
| `shows/` | Full show recordings |

Files are named `{prefix}/{uuid4}` with no extension. Content-type is stored as S3 object metadata and set at upload time.

R2 objects are never deleted in v1. There is no lifecycle policy — this is a known limitation.

---

## Analysis Pipeline

The analysis pipeline runs entirely outside the web server process, on Modal's GPU infrastructure.

### Trigger

When the user uploads audio for a Show:
1. Backend stores the audio in R2
2. Backend creates an `AnalysisJob` row with `status = pending`
3. Backend calls `modal.Function.from_name("jokestracker", "analyze_show").spawn(...)`, passing: `job_id`, `audio_key`, `set_text` (the full ordered text of all Versions in the SetVersion), and `callback_url`
4. The spawn is fire-and-forget — the API returns `{job_id}` immediately
5. If Modal is unavailable, the spawn fails silently; the job stays `pending` and can be retried

### Modal Function

The Modal function runs on a T4 GPU with `faster-whisper` and `torch` installed. It:

1. Downloads the audio file from R2 using boto3 (R2 credentials come from a Modal secret named `jokestracker-r2`)
2. Runs `WhisperModel("large-v3")` with `word_timestamps=True` to get a full transcript with per-word start/end times
3. Runs laugh detection (currently returns `[]` — LaughterSegmentation is not yet pip-installable)
4. Assembles the full set text by joining the Version bodies in SetVersion order
5. Computes a `difflib.SequenceMatcher` diff of planned text vs transcript
6. Maps laugh timestamps to lines using a 3-second attribution window: any laugh that starts within 3 seconds after a line ends is attributed to that line
7. POSTs the result to the callback URL on the Railway backend
8. On any exception, POSTs to `/internal/jobs/:id/fail` with the error string

### Polling

The client polls `GET /jobs/:id` every 3 seconds until `status` is `complete` or `failed`. FastAPI reads directly from the database — no cache, no pub/sub. Appropriate for a personal app where at most one job runs at a time.

---

## Frontend

The frontend is a React 18 + Vite 5 + Tailwind CSS 3 single-page app, configured as a PWA.

### Navigation

No router. The app has three tabs managed by a `useState` in `App.jsx`:

| Tab | View |
|---|---|
| Bits | `BitsView` |
| Sets | `SetsView` |
| Shows | `ShowsView` |

### API Layer (`api.js`)

All network calls go through a single `api.js` file. Every function is a thin wrapper over a `fetch` call. The base URL is read from `import.meta.env.VITE_API_BASE`:

- **Development**: `VITE_API_BASE=http://localhost:8000` (set in `.env.development`). The browser calls the FastAPI server directly; CORS is open on the backend.
- **Production**: `VITE_API_BASE` is unset → empty string → all calls go to the same origin where FastAPI is serving the built frontend.

### Components

**`AnnotatedText`** — Renders a Version's body as plain text with yellow highlight spans over annotated ranges. Clicking a highlight shows a tooltip with the note. Text selection triggers an "Annotate" button that captures the character offsets of the selection and opens the annotation form.

**`VersionTimeline`** — A horizontal row of version chips (`v1 · 142c`, `v2 · 198c`) for a Bit. Clicking a chip loads that version's detail and annotations.

**`AudioRecorder`** — Uses the browser `MediaRecorder` API to record audio from the microphone. States: `idle → requesting → recording → done`. Also accepts a file upload as a fallback. On stop, produces a `Blob` with type `audio/webm` and calls `onRecorded(blob)`.

**`AnnotationPlayer`** — Renders a `▶ play` link for annotations that have audio. On click, calls `GET /annotations/:id/audio` to get a fresh presigned R2 URL, then renders a native `<audio>` element with `autoPlay`. URL is fetched lazily and not stored permanently.

**`LaughHeatmap`** — Renders `line_scores` from an `AnalysisResult` as a list of lines, each with a coloured bar proportional to `laugh_count`. Colour scale: grey (0), yellow (<40%), orange (<70%), green (≥70%).

**`SetBuilder`** — UI for composing a new SetVersion. Lists all non-dead Bits; clicking a Bit expands its versions. Clicking a version adds it to an ordered list. Items can be reordered with ↑/↓ and removed with ×. Submitting calls `POST /sets/:id/versions` with the ordered `[{version_id, position}]` array.

### PWA

A `manifest.json` is served from `/public`. The app can be installed to a phone's home screen from the browser's "Add to Home Screen" prompt. There is no service worker — offline mode is out of scope.

---

## Infrastructure

### Railway

Hosts the FastAPI backend on an always-on small instance. A persistent volume (`tranquil-joy-volume`) is mounted at `/data`, providing durable storage for SQLite. The service is connected to the GitHub repo and redeploys automatically on push to `main`.

The database path in production is `sqlite:////data/db.sqlite`. In local development it is `sqlite:///./data/db.sqlite` (relative path, gitignored).

### Build Process (Dockerfile)

A multi-stage Dockerfile handles the monorepo build:

1. **Stage 1 (Node 20)**: `npm ci` + `npm run build` → produces `frontend/dist`
2. **Stage 2 (Python 3.12)**: `pip install -r backend/requirements.txt` + copies `backend/` and `frontend/dist` from Stage 1

FastAPI mounts `frontend/dist` as a `StaticFiles` app at `/` after all API routes are registered. API routes take priority; anything unmatched falls through to the static file handler, which serves `index.html` for all unmatched paths (enabling direct URL access).

### Modal

Runs the ML analysis function serverlessly on GPU. A Modal secret (`jokestracker-r2`) holds the R2 credentials so the function can download and upload files independently of the Railway server. The function is deployed separately with `modal deploy backend/jobs/analyze.py`.

---

## Local Development

Two processes run in parallel:

```
# Terminal 1 — backend
backend/.venv/bin/uvicorn backend.main:app --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

The Vite dev server runs on `:5173`. `VITE_API_BASE=http://localhost:8000` points all API calls directly at the FastAPI server. Hot module replacement works for all frontend changes. Backend changes reload automatically via `--reload`.

The integration test (`backend/test_api.py`) can be run against the live local server:

```
backend/.venv/bin/python backend/test_api.py
```

It covers 19 assertions across every route group and requires no mocking — it hits the real SQLite database.

---

## Known Limitations

| Area | Limitation |
|---|---|
| Laugh detection | `LaughterSegmentation` is not pip-installable; `_detect_laughs` returns `[]`. Line scores will all show 0 laughs until resolved. |
| Audio cleanup | Deleting an annotation or show does not delete the corresponding R2 object. Storage grows indefinitely. |
| Job retry | If a Modal job fails, there is no retry mechanism. The job stays `failed` and the user must re-upload audio. |
| Offline | No service worker; the PWA cannot function without a network connection. |
| Diff alignment | Laugh-to-line mapping uses fuzzy word matching which can misalign on heavily improvised performances. |
