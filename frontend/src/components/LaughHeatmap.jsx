import React from "react";

/**
 * Renders transcript with laugh indicators inline.
 * transcript: string (Whisper output)
 * laughTimestamps: [{start, end}]
 */
export default function LaughHeatmap({ transcript, laughTimestamps }) {
  if (!transcript) return <p className="text-xs text-gray-500">No transcript available</p>;

  // Split transcript into sentences/phrases for better readability
  const lines = transcript
    .split(/(?<=[.!?])\s+/)
    .map(line => line.trim())
    .filter(Boolean);

  if (!lines.length) return <p className="text-xs text-gray-500">No content in transcript</p>;

  // Parse laugh timestamps
  const laughs = laughTimestamps ? JSON.parse(laughTimestamps) : [];

  // Calculate total laugh duration for each line (rough estimation)
  // We'll distribute laughs across lines proportionally by line length
  const totalChars = lines.reduce((sum, line) => sum + line.length, 0);
  let charPosition = 0;

  const lineData = lines.map((line, i) => {
    const lineStartRatio = charPosition / totalChars;
    charPosition += line.length;
    const lineEndRatio = charPosition / totalChars;

    // Find laughs that might correspond to this portion of the transcript
    // This is an approximation since we don't have exact word timestamps
    const lineLaughs = laughs.filter(laugh => {
      const laughRatio = laugh.start / (laughs[laughs.length - 1]?.end || 1);
      return laughRatio >= lineStartRatio && laughRatio <= lineEndRatio;
    });

    const laughDuration = lineLaughs.reduce((sum, l) => sum + (l.end - l.start), 0);
    const laughCount = lineLaughs.length;

    return { line, laughCount, laughDuration };
  });

  const maxCount = Math.max(...lineData.map(l => l.laughCount), 1);

  return (
    <div className="space-y-2">
      {lineData.map((entry, i) => {
        const pct = entry.laughCount > 0 ? Math.round((entry.laughCount / maxCount) * 100) : 0;
        const heat = pct === 0
          ? "bg-gray-800"
          : pct < 40
            ? "bg-yellow-600/30"
            : pct < 70
              ? "bg-orange-500/40"
              : "bg-green-500/50";

        return (
          <div
            key={i}
            className={`flex items-start gap-3 px-3 py-2 rounded ${heat} ${pct > 0 ? 'border-l-2 border-l-green-500' : ''}`}
          >
            <p className="text-sm text-gray-200 leading-relaxed flex-1">{entry.line}</p>
            {entry.laughCount > 0 && (
              <span className="text-xs text-green-400 font-medium shrink-0 mt-0.5">
                {entry.laughCount}× 😂
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
