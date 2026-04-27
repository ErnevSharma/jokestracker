# Laughter Attribution with Claude - Design Document

## Problem Statement

Current laughter attribution has gaps because it uses naive character-position mapping:
- No understanding of joke structure (setup → punchline → laugh)
- Rough approximation of laugh timing to transcript segments
- No semantic understanding of what caused laughs
- Missing performance insights (which jokes killed, which flopped)

## Solution: Claude-Powered Laughter Analysis

Use Claude Sonnet to intelligently analyze the transcript with laugh timestamps and provide:
1. **Joke segmentation** - Identify discrete jokes/bits in the transcript
2. **Laugh attribution** - Map laughs to the specific jokes that caused them
3. **Performance summary** - Which jokes worked, which didn't, overall pacing
4. **Structural analysis** - Setup/punchline identification, callback recognition

---

## Data Flow

```
Show Recording
    ↓
Modal: Whisper Transcription (word timestamps)
    ↓
Modal: Laugh Detection (timestamps)
    ↓
Backend: Claude Analysis ← NEW!
    ├─ Input: transcript + laugh_timestamps + word_timestamps
    ├─ Process: Identify jokes, attribute laughs, generate insights
    └─ Output: structured analysis JSON
    ↓
Database: Store analysis in AnalysisResult
    ↓
Frontend: Rich heatmap + performance summary
```

---

## Claude Prompt Design

### Input Format
```json
{
  "transcript": "So I was at the airport... And this guy says... You know what I mean?",
  "word_timestamps": [
    {"word": "So", "start": 0.5, "end": 0.7},
    {"word": "I", "start": 0.8, "end": 0.9},
    ...
  ],
  "laugh_timestamps": [
    {"start": 5.2, "end": 7.3},
    {"start": 12.1, "end": 14.5}
  ]
}
```

### Prompt Template
```
You are analyzing a standup comedy performance transcript with detected audience laughter.

TRANSCRIPT WITH WORD TIMESTAMPS:
[word-level transcript with start/end times]

DETECTED LAUGHS:
[laugh timestamps]

Your task:
1. Segment the transcript into discrete jokes/bits
2. For each joke, identify:
   - Setup text
   - Punchline text
   - Tags (callback, observational, story, one-liner, crowd work)
   - Laugh attribution (which laughs this joke generated)
   - Success rating (killed/strong/medium/weak/died based on laugh intensity)

3. Provide overall performance summary:
   - Total jokes attempted
   - Hit rate (% that got laughs)
   - Pacing (jokes per minute)
   - Strongest moments
   - Weakest moments
   - Callbacks that landed

Output valid JSON with this structure:
{
  "jokes": [
    {
      "id": 1,
      "start_time": 0.5,
      "end_time": 8.2,
      "setup": "So I was at the airport and...",
      "punchline": "That's when I realized...",
      "text": "Full joke text",
      "tags": ["observational", "travel"],
      "laughs": [
        {"timestamp": 5.2, "duration": 2.1, "intensity": "strong"}
      ],
      "rating": "killed",
      "laugh_count": 2,
      "total_laugh_duration": 4.5
    }
  ],
  "summary": {
    "total_jokes": 12,
    "jokes_with_laughs": 9,
    "hit_rate": 0.75,
    "jokes_per_minute": 2.1,
    "strongest_jokes": [1, 5, 8],
    "weakest_jokes": [3, 11],
    "callbacks": ["airport guy mentioned 3 times"],
    "overall_assessment": "Strong set with good pacing..."
  }
}
```

---

## Backend Implementation

### 1. Add Claude to Backend Dependencies

```python
# backend/requirements.txt
anthropic>=0.40.0
```

### 2. Add Claude Config

```python
# backend/config.py
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
```

### 3. Create Claude Analysis Module

```python
# backend/services/claude_analyzer.py
from anthropic import Anthropic
import json

def analyze_comedy_performance(transcript, word_timestamps, laugh_timestamps):
    """
    Use Claude to analyze comedy performance and attribute laughs to jokes.

    Returns:
    {
      "jokes": [...],
      "summary": {...}
    }
    """
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    # Format word timestamps for Claude
    word_text = "\n".join([
        f"[{w['start']:.1f}s] {w['word']}"
        for w in word_timestamps
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
1. Segment the transcript into discrete jokes/bits
2. For each joke, identify:
   - Setup text
   - Punchline text
   - Tags (callback, observational, story, one-liner, crowd work)
   - Which laughs this joke generated (match by timestamp proximity)
   - Success rating based on laugh response

3. Provide overall performance summary

Output ONLY valid JSON (no markdown formatting) with this structure:
{{
  "jokes": [
    {{
      "id": 1,
      "start_time": 0.5,
      "end_time": 8.2,
      "setup": "text of setup",
      "punchline": "text of punchline",
      "text": "full joke text",
      "tags": ["observational"],
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
    "strongest_jokes": [1, 5],
    "weakest_jokes": [3],
    "callbacks": [],
    "overall_assessment": "Strong set..."
  }}
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse JSON response
        analysis = json.loads(response.content[0].text)
        return analysis

    except Exception as e:
        # Fallback to simple analysis if Claude fails
        return {
            "jokes": [],
            "summary": {
                "error": str(e),
                "total_jokes": 0,
                "jokes_with_laughs": 0,
                "hit_rate": 0,
                "overall_assessment": "Analysis failed"
            }
        }
```

### 4. Update Modal Function

```python
# backend/jobs/analyze.py

def analyze_show(job_id: str, audio_key: str, set_text: str, callback_url: str):
    # ... existing Whisper + laugh detection code ...

    # NEW: Claude analysis
    try:
        from anthropic import Anthropic
        import os

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            claude_analysis = _analyze_with_claude(
                whisper_transcript,
                words,  # Whisper word timestamps
                laugh_timestamps
            )
        else:
            claude_analysis = None
    except Exception as e:
        print(f"Claude analysis failed: {e}")
        claude_analysis = None

    # Send to callback with Claude analysis
    requests.post(callback_url, json={
        "whisper_transcript": whisper_transcript,
        "laugh_timestamps": laugh_timestamps,
        "line_scores": line_scores,  # Keep for backward compatibility
        "diff": diff,
        "claude_analysis": json.dumps(claude_analysis) if claude_analysis else None
    })


def _analyze_with_claude(transcript, word_timestamps, laugh_timestamps):
    """Claude analysis within Modal function."""
    client = Anthropic()

    # Format data for Claude
    word_list = [{"word": w.word, "start": w.start, "end": w.end} for w in word_timestamps]

    # ... same prompt as above ...

    response = client.messages.create(...)
    return json.loads(response.content[0].text)
```

### 5. Update Database Model

```python
# backend/models.py

class AnalysisResult(SQLModel, table=True):
    # ... existing fields ...
    claude_analysis: Optional[str] = None  # JSON string with joke segmentation
```

---

## Frontend Implementation

### 1. New Component: ClaudeHeatmap

```jsx
// frontend/src/components/ClaudeHeatmap.jsx

import React from "react";

export default function ClaudeHeatmap({ claudeAnalysis }) {
  if (!claudeAnalysis) {
    return <p className="text-xs text-gray-500">AI analysis not available</p>;
  }

  const analysis = JSON.parse(claudeAnalysis);
  const { jokes, summary } = analysis;

  const getRatingColor = (rating) => {
    switch (rating) {
      case "killed": return "bg-green-500/50 border-green-500";
      case "strong": return "bg-green-600/30 border-green-600";
      case "medium": return "bg-yellow-600/30 border-yellow-600";
      case "weak": return "bg-orange-600/30 border-orange-600";
      case "died": return "bg-red-600/30 border-red-600";
      default: return "bg-gray-800 border-gray-700";
    }
  };

  const getRatingEmoji = (rating) => {
    switch (rating) {
      case "killed": return "🔥";
      case "strong": return "😂";
      case "medium": return "😊";
      case "weak": return "😐";
      case "died": return "💀";
      default: return "";
    }
  };

  return (
    <div className="space-y-6">
      {/* Performance Summary */}
      <div className="bg-gray-800/50 rounded-lg p-4 space-y-3">
        <h3 className="text-sm font-semibold text-gray-200">Performance Summary</h3>

        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-green-400">{summary.jokes_with_laughs}/{summary.total_jokes}</div>
            <div className="text-xs text-gray-400">Jokes Landed</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-blue-400">{(summary.hit_rate * 100).toFixed(0)}%</div>
            <div className="text-xs text-gray-400">Hit Rate</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-purple-400">{summary.jokes_per_minute.toFixed(1)}</div>
            <div className="text-xs text-gray-400">Jokes/Minute</div>
          </div>
        </div>

        <p className="text-sm text-gray-300 leading-relaxed border-t border-gray-700 pt-3">
          {summary.overall_assessment}
        </p>

        {summary.callbacks?.length > 0 && (
          <div className="text-xs text-gray-400 border-t border-gray-700 pt-2">
            <strong>Callbacks:</strong> {summary.callbacks.join(", ")}
          </div>
        )}
      </div>

      {/* Joke-by-Joke Breakdown */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-gray-200">Joke Breakdown</h3>

        {jokes.map((joke) => (
          <div
            key={joke.id}
            className={`rounded-lg border-l-4 p-4 ${getRatingColor(joke.rating)}`}
          >
            {/* Header */}
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-lg">{getRatingEmoji(joke.rating)}</span>
                <span className="text-xs font-mono text-gray-400">
                  {joke.start_time.toFixed(1)}s - {joke.end_time.toFixed(1)}s
                </span>
              </div>
              <div className="flex items-center gap-2">
                {joke.laugh_count > 0 && (
                  <span className="text-xs font-medium text-green-400">
                    {joke.laugh_count}× laughs ({joke.total_laugh_duration.toFixed(1)}s)
                  </span>
                )}
                <span className={`text-xs px-2 py-0.5 rounded ${
                  joke.rating === "killed" ? "bg-green-500 text-white" :
                  joke.rating === "strong" ? "bg-green-600 text-white" :
                  joke.rating === "medium" ? "bg-yellow-600 text-white" :
                  joke.rating === "weak" ? "bg-orange-600 text-white" :
                  "bg-red-600 text-white"
                }`}>
                  {joke.rating}
                </span>
              </div>
            </div>

            {/* Joke Text */}
            <div className="space-y-2">
              {joke.setup && (
                <p className="text-sm text-gray-300 leading-relaxed">
                  <span className="text-gray-500 text-xs uppercase font-semibold">Setup:</span><br />
                  {joke.setup}
                </p>
              )}
              {joke.punchline && (
                <p className="text-sm text-gray-200 font-medium leading-relaxed">
                  <span className="text-gray-500 text-xs uppercase font-semibold">Punchline:</span><br />
                  {joke.punchline}
                </p>
              )}
              {!joke.setup && !joke.punchline && (
                <p className="text-sm text-gray-300 leading-relaxed">{joke.text}</p>
              )}
            </div>

            {/* Tags */}
            {joke.tags?.length > 0 && (
              <div className="flex gap-1 mt-2">
                {joke.tags.map((tag, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 bg-gray-700 text-gray-300 rounded">
                    {tag}
                  </span>
                ))}
              </div>
            )}

            {/* Laugh Details */}
            {joke.laughs?.length > 0 && (
              <div className="mt-2 pt-2 border-t border-gray-700/50">
                <div className="flex flex-wrap gap-2">
                  {joke.laughs.map((laugh, i) => (
                    <span key={i} className="text-xs text-gray-400 font-mono">
                      @ {laugh.timestamp.toFixed(1)}s ({laugh.duration.toFixed(1)}s, {laugh.intensity})
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 2. Update ShowsView to Use ClaudeHeatmap

```jsx
// frontend/src/views/ShowsView.jsx

import ClaudeHeatmap from "../components/ClaudeHeatmap";
import LaughHeatmap from "../components/LaughHeatmap"; // Keep as fallback

{selected.result && (
  <div className="border-t border-gray-800 pt-4 space-y-3">
    <div className="flex items-center justify-between">
      <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">
        Performance Analysis
      </p>
      {selected.result.laugh_timestamps && JSON.parse(selected.result.laugh_timestamps).length > 0 && (
        <span className="text-xs text-green-400">
          {JSON.parse(selected.result.laugh_timestamps).length} laughs detected
        </span>
      )}
    </div>

    {/* Use Claude analysis if available, fallback to simple heatmap */}
    {selected.result.claude_analysis ? (
      <ClaudeHeatmap claudeAnalysis={selected.result.claude_analysis} />
    ) : (
      <LaughHeatmap
        transcript={selected.result.whisper_transcript}
        laughTimestamps={selected.result.laugh_timestamps}
      />
    )}
  </div>
)}
```

---

## Environment Setup

### Railway Variables
```bash
ANTHROPIC_API_KEY=sk-ant-...  # Add to Railway dashboard
```

### Modal Secrets
```bash
modal secret create anthropic-api ANTHROPIC_API_KEY=sk-ant-...
```

Update Modal function to use secret:
```python
@app.function(
    gpu="T4",
    secrets=[
        modal.Secret.from_name("jokestracker-r2"),
        modal.Secret.from_name("anthropic-api")  # NEW
    ],
    timeout=600,
)
```

---

## Migration Strategy

### Phase 1: Add Claude Analysis (Non-Breaking)
1. Add `claude_analysis` field to AnalysisResult (nullable)
2. Update Modal function to call Claude after Whisper + laugh detection
3. Frontend checks for claude_analysis and falls back to simple heatmap
4. Deploy incrementally

### Phase 2: New Shows Get Rich Analysis
- New shows analyzed after deployment get Claude insights
- Old shows still show basic heatmap (no re-processing needed)

### Phase 3: (Optional) Backfill
- Add admin endpoint to re-analyze old shows
- Batch process through Claude
- Update database records

---

## Cost Estimation

### Claude Sonnet 4 Pricing (April 2025)
- Input: $3 / million tokens
- Output: $15 / million tokens

### Typical Show Analysis
- Input: ~2000 tokens (transcript + timestamps + prompt)
- Output: ~1500 tokens (structured JSON)
- Cost per show: ~$0.03

### Monthly Cost (50 shows)
- 50 shows × $0.03 = **$1.50/month**

Very affordable for the value added!

---

## Error Handling & Fallbacks

1. **Claude API unavailable**: Fall back to simple heatmap
2. **Claude returns invalid JSON**: Parse error, use fallback
3. **No ANTHROPIC_API_KEY**: Skip Claude, use basic analysis
4. **Timeout**: Set 30s timeout for Claude, continue without it
5. **Rate limiting**: Exponential backoff, queue for retry

---

## Benefits

✅ **Accurate laugh attribution** - AI understands joke structure
✅ **Performance insights** - Know which jokes worked and why
✅ **Callback detection** - Identifies recurring bits
✅ **Hit rate tracking** - Measure improvement over time
✅ **Pacing analysis** - Jokes per minute insights
✅ **Tagging** - Categorize jokes (observational, story, one-liner)
✅ **Non-breaking** - Falls back gracefully for old shows

---

## Next Steps

1. Add `anthropic` to backend requirements
2. Create `backend/services/claude_analyzer.py`
3. Update Modal function with Claude analysis
4. Add database migration for `claude_analysis` field
5. Create `ClaudeHeatmap` component
6. Update ShowsView to use new component
7. Add ANTHROPIC_API_KEY to Railway + Modal
8. Test with real show data
9. Iterate on prompt based on results

---

## Success Metrics

- ✅ Zero gaps in laugh attribution
- ✅ Accurate joke segmentation (95%+ accuracy)
- ✅ Useful performance insights
- ✅ <5s analysis time per show
- ✅ <$0.05 cost per show
- ✅ Graceful degradation when Claude unavailable
