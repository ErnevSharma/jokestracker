import React from "react";

/**
 * Renders per-line laugh scores as a heatmap bar.
 * line_scores: [{line, laugh_count, laugh_duration}]
 */
export default function LaughHeatmap({ lineScores }) {
  if (!lineScores?.length) return null;

  const maxCount = Math.max(...lineScores.map((l) => l.laugh_count), 1);

  return (
    <div className="space-y-1">
      {lineScores.map((entry, i) => {
        const pct = Math.round((entry.laugh_count / maxCount) * 100);
        const heat = pct === 0 ? "bg-gray-700" : pct < 40 ? "bg-yellow-700" : pct < 70 ? "bg-orange-500" : "bg-green-500";
        return (
          <div key={i} className="flex items-start gap-2">
            <div className="w-1 mt-1.5 shrink-0">
              <div className={`h-3 rounded-sm ${heat}`} style={{ width: `${Math.max(pct, 4)}%`, minWidth: "4px" }} />
            </div>
            <p className="text-xs text-gray-300 leading-snug flex-1">{entry.line}</p>
            {entry.laugh_count > 0 && (
              <span className="text-xs text-gray-500 shrink-0">
                {entry.laugh_count}× {entry.laugh_duration.toFixed(1)}s
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
