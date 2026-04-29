"""
Modal function for show audio analysis.
Deploy with: modal deploy backend/jobs/analyze.py
"""
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
    )
    .add_local_dir(
        "backend/jobs/laugh_model",
        remote_path="/root/laugh_model"
    )
)

app = modal.App("jokestracker", image=image)


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


        # ── Callback to backend ───────────────────────────────────────────────
        # Backend will run Claude analysis after receiving this callback
        word_timestamps = [{"word": w.word, "start": w.start, "end": w.end} for w in words]

        requests.post(callback_url, json={
            "whisper_transcript": whisper_transcript,
            "word_timestamps": word_timestamps,
            "laugh_timestamps": laugh_timestamps,
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
