# Implementation Summary

## What Was Built

Full-stack Comedy Set Tracker as specified in SPEC.md.

---

## Backend (`backend/`)

### Stack
FastAPI · SQLModel · SQLite · boto3 (R2) · Modal

### Files
| File | Purpose |
|------|---------|
| `config.py` | Env var loading via dotenv |
| `db.py` | SQLite engine, session dep, auto-creates data dir |
| `models.py` | All 9 SQLModel table definitions + enums |
| `storage.py` | R2 upload / download / presigned URL |
| `main.py` | App factory, CORS, router registration, startup hook |
| `routers/bits.py` | Bit CRUD + soft delete + `/appearances` |
| `routers/versions.py` | Version create/list/detail/diff |
| `routers/annotations.py` | Annotation CRUD + audio upload to R2 |
| `routers/sets.py` | Set + SetVersion CRUD + `/sets/:id/shows` |
| `routers/shows.py` | Show CRUD + audio upload + Modal trigger |
| `routers/analysis.py` | Job poll + `/internal/jobs/:id/complete` callback |
| `jobs/analyze.py` | Modal function: Whisper + LaughterSegmentation |
| `requirements.txt` | Python deps |
| `test_api.py` | 19-assertion integration test (all passing) |

### Key behaviours honoured
- `Version.body`, `SetVersion`, `SetVersionItem` are write-once (no PATCH endpoints)
- `Annotation.char_start` / `char_end` immutable; only `note` patchable
- `Annotation.audio_key` set once via upload, not patchable
- Bit delete is soft (sets `status=dead`)
- `version_num` auto-increments per-bit; `SetVersion.version_num` per-set
- Modal trigger wrapped in try/except — all CRUD works without Modal deployed

### Running locally
```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

### Running tests
```bash
# With server running on :8000
backend/.venv/bin/python backend/test_api.py
```

---

## Frontend (`frontend/`)

### Stack
React 18 · Vite 5 · Tailwind CSS 3 · PWA manifest

### Files
| File | Purpose |
|------|---------|
| `src/api.js` | All fetch calls, single file, proxied via `/api` |
| `src/App.jsx` | Tab shell: Bits / Sets / Shows |
| `src/views/BitsView.jsx` | Bit list, version timeline, text editor, annotation UI |
| `src/views/SetsView.jsx` | Set list, set version list, SetBuilder |
| `src/views/ShowsView.jsx` | Show log form, audio upload, job polling, heatmap |
| `src/components/AnnotatedText.jsx` | Renders version body with highlight spans; text selection → annotate |
| `src/components/VersionTimeline.jsx` | Horizontal version chip row |
| `src/components/LaughHeatmap.jsx` | Per-line laugh score bars |
| `src/components/SetBuilder.jsx` | Drag-to-order bit version picker for new SetVersion |

### Proxy
Vite dev server proxies `/api/*` → `http://localhost:8000` so no CORS config needed during development.

### Running locally
```bash
cd frontend && npm install && npm run dev
```

---

## Modal Analysis Job (`backend/jobs/analyze.py`)

- App name: `jokestracker` (workspace: `ernev-sharma-us`)
- GPU: T4
- Reads R2 credentials from a Modal secret named `jokestracker-r2`
- Flow: download audio → Whisper large-v3 → LaughterSegmentation → diff → POST callback to backend
- Laugh attribution window: 3 seconds post-line end

### Deploy when ready
```bash
modal deploy backend/jobs/analyze.py
```

### Modal secret setup (before deploying)
```bash
modal secret create jokestracker-r2 \
  R2_ENDPOINT_URL=... \
  R2_ACCESS_KEY_ID=... \
  R2_SECRET_ACCESS_KEY=... \
  R2_BUCKET_NAME=jokestracker-audio
```

---

## What's Left Before Production

- [ ] Deploy backend to Railway (sets `BACKEND_BASE_URL` env var)
- [ ] Create Modal secret (`jokestracker-r2`) and run `modal deploy`
- [ ] Set all env vars in Railway service settings
- [ ] Build frontend and serve static files (or host separately)
- [ ] Close SPEC open question: laugh attribution window (currently 3s)
