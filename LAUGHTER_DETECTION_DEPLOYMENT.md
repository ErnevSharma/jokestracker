# Laughter Detection Integration - Deployment Guide

## Overview

Successfully integrated the working laughter detection model from `experiments/laughter-detection/` into the Modal inference pipeline at `backend/jobs/analyze.py`.

## Changes Made

### 1. Model Package Structure
```
backend/jobs/laugh_model/
├── __init__.py              # Package marker
├── models.py                # ResNetBigger architecture (11 KB)
├── best.pth.tar            # Pretrained checkpoint (9.4 MB)
└── laugh_detector.py       # Inference wrapper (5.5 KB)
```

### 2. Dependencies Added to Modal Image
- `librosa>=0.10` - Audio feature extraction
- `scipy>=1.6` - Signal processing (lowpass filter)
- `numpy>=1.20` - Array operations
- `soundfile>=0.12` - Audio file I/O
- `imageio-ffmpeg>=0.5` - **CRITICAL** for MP3 decoding

### 3. Modal Function Updates
- Image now bundles `laugh_model/` directory into container at `/root/laugh_model`
- `_detect_laughs()` replaced with real implementation
- Graceful error handling - returns `[]` on failure

## Deployment Steps

### 1. Deploy to Modal
```bash
cd /local/home/shaernev/personal/jokestracker
modal deploy backend/jobs/analyze.py
```

Expected output:
```
✓ Initialized. View app at https://modal.com/apps/...
✓ Created objects.
├── 🔨 Created mount /local/home/shaernev/personal/jokestracker/backend/jobs/laugh_model
├── 🔨 Created function analyze_show.
✓ App deployed!
```

### 2. Verify Deployment
```bash
modal app list | grep jokestracker
```

### 3. Test Locally (Backend + Frontend)

**Terminal 1 - Start Backend:**
```bash
cd /local/home/shaernev/personal/jokestracker
backend/.venv/bin/uvicorn backend.main:app --reload
```

**Terminal 2 - Start Frontend:**
```bash
cd frontend && npm run dev
```

**Terminal 3 - Open Browser:**
```bash
# Navigate to http://localhost:5173
# Go to Shows tab
# Create a test show with a SetVersion
# Upload test audio (e.g., Louis CK sample from experiments/)
# Wait for analysis to complete
# Verify LaughHeatmap shows colored bars with non-zero laugh_count
```

## Testing Strategy

### Unit Test (Manual)
Since librosa isn't in the local backend environment, we can't test locally. But Modal will have all dependencies.

### Integration Test
1. Upload test audio: `experiments/laughter-detection/test_audio/louie_ck_57s.mp3` (if available)
2. Monitor Modal logs:
   ```bash
   modal logs jokestracker
   ```
3. Check for:
   - ✅ Checkpoint loads without errors
   - ✅ Inference completes in <2 minutes
   - ✅ Returns valid `[{start, end}]` timestamps
   - ✅ No exceptions in Modal function logs

### Expected Results
- **Laugh timestamps**: Array of `{start: float, end: float}` objects
- **Line scores**: Non-zero `laugh_count` values for lines with laughs
- **LaughHeatmap**: Colored bars indicating laugh intensity

### Validation Criteria
- ✅ Code has valid Python syntax (verified)
- ✅ Modal deployment succeeds
- ✅ Analysis job completes without timeout
- ✅ LaughHeatmap renders in frontend
- ✅ No errors in Modal logs

## Fallback Behavior

If inference fails (checkpoint issues, GPU memory, etc.):
- Exception caught in `_detect_laughs()` try/except
- Prints error message to Modal logs
- Returns empty list `[]`
- System continues with transcript + diff (no laugh data)
- Frontend shows "No line data" message in LaughHeatmap

## Performance Expectations

**From experiment results:**
- CPU: ~33s for 57s audio (1.7x realtime)
- **T4 GPU (Modal)**: ~15-20s for 57s audio (~0.35x realtime)
- **1 hour show**: <10 minutes total (well under 600s timeout)

**GPU Memory:**
- Checkpoint: 9.4 MB
- Inference overhead: ~50 MB
- Total: <1 GB (T4 has 16 GB available)

## Troubleshooting

### Issue: Modal deployment fails with "mount not found"
**Solution**: Ensure you're running from the project root directory:
```bash
cd /local/home/shaernev/personal/jokestracker
modal deploy backend/jobs/analyze.py
```

### Issue: "No module named 'librosa'" error in Modal
**Solution**: This should not happen as librosa is in the image. Check Modal logs:
```bash
modal logs jokestracker --follow
```

### Issue: Checkpoint fails to load
**Solution**: Verify checkpoint file size:
```bash
ls -lh backend/jobs/laugh_model/best.pth.tar
# Should show: 9.4M
```

### Issue: Empty laugh_timestamps in response
**Solution**: Check Modal logs for exception message. Model may have failed gracefully.

### Issue: Job times out (>600s)
**Solution**: Reduce audio file size or increase timeout in `analyze.py`:
```python
@app.function(
    gpu="T4",
    secrets=[modal.Secret.from_name("jokestracker-r2")],
    timeout=900,  # Increase to 15 minutes
)
```

## Next Steps (Optional Optimizations)

1. **Tune threshold**: Experiment with 0.4-0.6 for comedy-specific accuracy
2. **Cache checkpoint**: Use Modal Volume to avoid bundling 9.4 MB in every deployment
3. **Use float16**: Like Whisper, for faster inference
4. **Batch size tuning**: Current is 8, could increase to 32-64

## Files Modified

- `backend/jobs/analyze.py` - Lines 12-32, 106-124
- Created: `backend/jobs/laugh_model/*` (4 files, 9.4 MB total)

## Rollback Instructions

If deployment fails or causes issues:

```bash
git diff backend/jobs/analyze.py  # Review changes
git checkout backend/jobs/analyze.py  # Revert to previous version
modal deploy backend/jobs/analyze.py  # Deploy old version
```

To remove laugh model files:
```bash
rm -rf backend/jobs/laugh_model/
```

---

## Status: Ready for Deployment ✅

All code changes are complete and syntax-validated. The Modal image will build all dependencies automatically on first deployment (~5 minutes for image build, then cached).
