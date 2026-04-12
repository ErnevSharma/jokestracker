"""
Modal function for show audio analysis.
Deploy with: modal deploy backend/jobs/analyze.py
"""
import difflib
import json
import os
import tempfile

import modal

# Image with all ML deps
# Note: LaughterSegmentation is not pip-installable; _detect_laughs returns []
# until an installable package is available.
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "faster-whisper==1.0.3",
        "boto3",
        "requests",
        "torch",
        "torchaudio",
    )
)

app = modal.App("jokestracker", image=image)

LAUGH_WINDOW = 3.0  # seconds after line end to attribute laughs


@app.function(
    gpu="T4",
    secrets=[modal.Secret.from_name("jokestracker-r2")],
    timeout=600,
)
def analyze_show(job_id: str, audio_key: str, set_text: str, callback_url: str):
    import boto3
    import requests
    from faster_whisper import WhisperModel

    # ── Download audio from R2 ────────────────────────────────────────────────
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        audio_path = f.name
        s3.download_fileobj(os.environ["R2_BUCKET_NAME"], audio_key, f)

    try:
        # ── Transcribe with Whisper ───────────────────────────────────────────
        whisper = WhisperModel("large-v3", device="cuda", compute_type="float16")
        segments, _ = whisper.transcribe(audio_path, word_timestamps=True)
        segments = list(segments)

        words = []
        for seg in segments:
            if seg.words:
                words.extend(seg.words)

        whisper_transcript = " ".join(w.word for w in words)

        # ── Laugh detection ───────────────────────────────────────────────────
        laugh_timestamps = _detect_laughs(audio_path)

        # ── Map laughs to lines ───────────────────────────────────────────────
        lines = [l for l in set_text.splitlines() if l.strip()]
        line_scores = _score_lines(lines, words, laugh_timestamps)

        # ── Diff planned vs transcript ────────────────────────────────────────
        planned_lines = set_text.splitlines()
        transcript_lines = whisper_transcript.splitlines()
        matcher = difflib.SequenceMatcher(None, planned_lines, transcript_lines)
        diff = [
            {"tag": tag, "a_start": i1, "a_end": i2, "b_start": j1, "b_end": j2}
            for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        ]

        # ── Callback to backend ───────────────────────────────────────────────
        requests.post(callback_url, json={
            "whisper_transcript": whisper_transcript,
            "laugh_timestamps": laugh_timestamps,
            "line_scores": line_scores,
            "diff": diff,
        }, timeout=30)

    except Exception as e:
        fail_url = callback_url.replace("/complete", "/fail")
        requests.post(fail_url, params={"error": str(e)}, timeout=10)

    finally:
        os.unlink(audio_path)


def _detect_laughs(audio_path: str) -> list:
    """Run LaughterSegmentation model and return [{start, end}] list."""
    try:
        from laughter_segmentation import LaughterDetector
        detector = LaughterDetector()
        segments = detector.detect(audio_path)
        return [{"start": s.start, "end": s.end} for s in segments]
    except Exception:
        return []


def _score_lines(lines: list, words: list, laugh_timestamps: list) -> list:
    """Attribute laughs to lines based on word timestamps."""
    if not words:
        return [{"line": l, "laugh_count": 0, "laugh_duration": 0.0} for l in lines]

    word_idx = 0
    scores = []

    for line in lines:
        line_words = line.split()
        matched = []

        for lw in line_words:
            if word_idx < len(words) and _fuzzy_match(words[word_idx].word, lw):
                matched.append(words[word_idx])
                word_idx += 1

        if not matched:
            scores.append({"line": line, "laugh_count": 0, "laugh_duration": 0.0})
            continue

        line_end = matched[-1].end
        window_end = line_end + LAUGH_WINDOW

        count = 0
        duration = 0.0
        for laugh in laugh_timestamps:
            if laugh["start"] >= line_end and laugh["start"] <= window_end:
                count += 1
                duration += laugh["end"] - laugh["start"]

        scores.append({"line": line, "laugh_count": count, "laugh_duration": round(duration, 2)})

    return scores


def _fuzzy_match(a: str, b: str) -> bool:
    return a.strip().lower().rstrip(".,!?") == b.strip().lower().rstrip(".,!?")
