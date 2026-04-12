import React from "react";

/**
 * Horizontal list of version chips for a bit.
 * versions: [{id, version_num, created_at, char_count}]
 */
export default function VersionTimeline({ versions, selectedId, onSelect }) {
  if (!versions?.length) return null;

  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1">
      <span className="text-xs text-gray-500 shrink-0">versions:</span>
      {versions.map((v) => (
        <button
          key={v.id}
          onClick={() => onSelect(v)}
          className={`shrink-0 px-2 py-0.5 rounded text-xs border transition-colors ${
            v.id === selectedId
              ? "bg-gray-600 border-gray-500 text-white"
              : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white"
          }`}
        >
          v{v.version_num}
          <span className="ml-1 text-gray-500">{v.char_count}c</span>
        </button>
      ))}
    </div>
  );
}
