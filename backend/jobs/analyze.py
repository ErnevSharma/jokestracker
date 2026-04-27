"""
Modal function for show audio analysis.
Deploy with: modal deploy backend/jobs/analyze.py
"""
import difflib
import json
import os
import tempfile

import modal

# Image with all ML deps including laughter detection
# Use CUDA base image for GPU support (includes libcublas and CUDA runtime)
image = (
    modal.Image.from_registry("nvidia/cuda:12.1.0-runtime-ubuntu22.04", add_python="3.11")
    .pip_install(
        "faster-whisper==1.0.3",
        "boto3",
        "requests",
        "torch",  # Will use CUDA 12.1 from base image
        "torchaudio",
        # Laughter detection dependencies
        "librosa>=0.10",           # Audio processing & feature extraction
        "scipy>=1.6",              # Signal processing (lowpass filter)
        "numpy>=1.20",             # Array operations
        "soundfile>=0.12",         # Audio file I/O
        "imageio-ffmpeg>=0.5",     # CRITICAL: MP3 decoding (bundles ffmpeg)
        "nvidia-cudnn-cu12",       # Explicit CUDA DNN library
        # Claude API for intelligent laugh attribution
        "anthropic>=0.40.0",
    )
    .add_local_dir(
        "backend/jobs/laugh_model",
        remote_path="/root/laugh_model"
    )
)

app = modal.App("jokestracker", image=image)

LAUGH_WINDOW = 3.0  # seconds after line end to attribute laughs


@app.function(
    gpu="T4",
    secrets=[
        modal.Secret.from_name("jokestracker-r2"),
        modal.Secret.from_name("anthropic-api"),
    ],
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

        # ── Claude AI analysis ────────────────────────────────────────────────
        claude_analysis = _analyze_with_claude(words, laugh_timestamps)

        # ── Callback to backend ───────────────────────────────────────────────
        requests.post(callback_url, json={
            "whisper_transcript": whisper_transcript,
            "laugh_timestamps": laugh_timestamps,
            "line_scores": line_scores,
            "diff": diff,
            "claude_analysis": claude_analysis,
        }, timeout=30)

    except Exception as e:
        fail_url = callback_url.replace("/complete", "/fail")
        requests.post(fail_url, params={"error": str(e)}, timeout=10)

    finally:
        os.unlink(audio_path)


def _detect_laughs(audio_path: str) -> list:
    """Run laughter detection model and return [{start, end}] list."""
    try:
        import sys
        sys.path.insert(0, '/root/laugh_model')
        from laugh_detector import LaughterDetector

        detector = LaughterDetector(
            model_path='/root/laugh_model/best.pth.tar',
            device='cuda',  # Use T4 GPU
            threshold=0.5,
            min_length=0.2
        )
        segments = detector.detect(audio_path)
        return [{"start": float(s[0]), "end": float(s[1])} for s in segments]
    except Exception as e:
        # Graceful degradation - system continues without laugh detection
        print(f"Laugh detection failed: {e}")
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


def _analyze_with_claude(words: list, laugh_timestamps: list) -> str:
    """
    Use Claude to analyze comedy performance and intelligently attribute laughs to jokes.
    Returns JSON string with joke segmentation and performance insights.
    """
    try:
        import json
        from anthropic import Anthropic

        # Check if API key is available
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("ANTHROPIC_API_KEY not set, skipping Claude analysis")
            return None

        client = Anthropic(api_key=api_key)

        # Format word timestamps for Claude
        word_text = "\n".join([
            f"[{w.start:.1f}s] {w.word}"
            for w in words[:500]  # Limit to first 500 words to keep prompt size manageable
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
            model="claude-sonnet-4-20250514",
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
        analysis = json.loads(analysis_text)

        return json.dumps(analysis)

    except Exception as e:
        print(f"Claude analysis failed: {e}")
        return None
