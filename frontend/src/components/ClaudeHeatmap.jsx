import React from "react";

/**
 * AI-powered comedy performance analysis with intelligent laugh attribution.
 * Uses Claude to segment jokes and map laughs accurately.
 */
export default function ClaudeHeatmap({ claudeAnalysis }) {
  if (!claudeAnalysis) {
    return <p className="text-xs text-gray-500">AI analysis not available</p>;
  }

  let analysis;
  try {
    analysis = JSON.parse(claudeAnalysis);
  } catch (e) {
    return <p className="text-xs text-red-400">Error parsing analysis data</p>;
  }

  const { jokes = [], summary = {} } = analysis;

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
      default: return "❓";
    }
  };

  const getRatingBadgeColor = (rating) => {
    switch (rating) {
      case "killed": return "bg-green-500 text-white";
      case "strong": return "bg-green-600 text-white";
      case "medium": return "bg-yellow-600 text-white";
      case "weak": return "bg-orange-600 text-white";
      case "died": return "bg-red-600 text-white";
      default: return "bg-gray-600 text-white";
    }
  };

  return (
    <div className="space-y-6">
      {/* Performance Summary Card */}
      <div className="bg-gray-800/50 rounded-lg p-5 space-y-4">
        <h3 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">
          Performance Summary
        </h3>

        {/* Key Metrics */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center">
            <div className="text-3xl font-bold text-green-400">
              {summary.jokes_with_laughs || 0}/{summary.total_jokes || 0}
            </div>
            <div className="text-xs text-gray-400 mt-1">Jokes Landed</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-blue-400">
              {summary.hit_rate ? (summary.hit_rate * 100).toFixed(0) : 0}%
            </div>
            <div className="text-xs text-gray-400 mt-1">Hit Rate</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-purple-400">
              {summary.jokes_per_minute ? summary.jokes_per_minute.toFixed(1) : 0}
            </div>
            <div className="text-xs text-gray-400 mt-1">Jokes/Minute</div>
          </div>
        </div>

        {/* Overall Assessment */}
        {summary.overall_assessment && (
          <p className="text-sm text-gray-300 leading-relaxed border-t border-gray-700 pt-3">
            {summary.overall_assessment}
          </p>
        )}

        {/* Callbacks */}
        {summary.callbacks?.length > 0 && (
          <div className="text-xs text-gray-400 border-t border-gray-700 pt-2">
            <strong className="text-gray-300">Callbacks:</strong> {summary.callbacks.join(", ")}
          </div>
        )}
      </div>

      {/* Joke-by-Joke Breakdown */}
      {jokes.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">
            Joke Breakdown ({jokes.length} jokes)
          </h3>

          {jokes.map((joke) => (
            <div
              key={joke.id}
              className={`rounded-lg border-l-4 p-4 transition-all hover:bg-gray-800/30 ${getRatingColor(joke.rating)}`}
            >
              {/* Header Row */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{getRatingEmoji(joke.rating)}</span>
                  <div>
                    <span className="text-xs font-mono text-gray-400">
                      {joke.start_time?.toFixed(1)}s - {joke.end_time?.toFixed(1)}s
                    </span>
                    {joke.tags?.length > 0 && (
                      <div className="flex gap-1 mt-1">
                        {joke.tags.map((tag, i) => (
                          <span key={i} className="text-xs px-1.5 py-0.5 bg-gray-700/60 text-gray-300 rounded">
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {joke.laugh_count > 0 && (
                    <span className="text-xs font-medium text-green-400 bg-green-500/10 px-2 py-1 rounded">
                      {joke.laugh_count}× ({joke.total_laugh_duration?.toFixed(1)}s)
                    </span>
                  )}
                  <span className={`text-xs px-2 py-1 rounded font-medium ${getRatingBadgeColor(joke.rating)}`}>
                    {joke.rating}
                  </span>
                </div>
              </div>

              {/* Joke Content */}
              <div className="space-y-2">
                {joke.setup && (
                  <div>
                    <p className="text-xs text-gray-500 uppercase font-semibold mb-1">Setup</p>
                    <p className="text-sm text-gray-300 leading-relaxed">{joke.setup}</p>
                  </div>
                )}
                {joke.punchline && (
                  <div>
                    <p className="text-xs text-gray-500 uppercase font-semibold mb-1">Punchline</p>
                    <p className="text-sm text-white font-medium leading-relaxed">{joke.punchline}</p>
                  </div>
                )}
                {!joke.setup && !joke.punchline && joke.text && (
                  <p className="text-sm text-gray-300 leading-relaxed">{joke.text}</p>
                )}
              </div>

              {/* Laugh Details */}
              {joke.laughs?.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-700/50">
                  <p className="text-xs text-gray-500 uppercase font-semibold mb-2">Audience Response</p>
                  <div className="flex flex-wrap gap-2">
                    {joke.laughs.map((laugh, i) => (
                      <div key={i} className="text-xs text-gray-400 bg-gray-700/40 px-2 py-1 rounded font-mono">
                        @ {laugh.timestamp?.toFixed(1)}s
                        <span className="ml-1 text-gray-500">•</span>
                        <span className="ml-1">{laugh.duration?.toFixed(1)}s</span>
                        <span className="ml-1 text-gray-500">•</span>
                        <span className={`ml-1 ${
                          laugh.intensity === "strong" ? "text-green-400" :
                          laugh.intensity === "medium" ? "text-yellow-400" :
                          "text-gray-400"
                        }`}>
                          {laugh.intensity}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {jokes.length === 0 && (
        <p className="text-xs text-gray-500 text-center py-4">
          No jokes detected in this recording
        </p>
      )}
    </div>
  );
}
