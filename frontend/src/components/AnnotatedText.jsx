import React, { useState } from "react";

/**
 * Renders version body text with annotation highlights.
 * Clicking a highlighted range shows the note.
 * Selecting text and pressing "Annotate" calls onAnnotate(start, end).
 */
export default function AnnotatedText({ body, annotations = [], onAnnotate }) {
  const [tooltip, setTooltip] = useState(null); // { note, audio_key, x, y }
  const [selection, setSelection] = useState(null); // { start, end }

  // Build segments: split body into annotated/plain spans
  const segments = buildSegments(body, annotations);

  function handleMouseUp() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) { setSelection(null); return; }
    const range = sel.getRangeAt(0);
    const container = document.getElementById("annotated-body");
    if (!container || !container.contains(range.commonAncestorContainer)) return;

    // Compute char offsets relative to body
    const preRange = range.cloneRange();
    preRange.selectNodeContents(container);
    preRange.setEnd(range.startContainer, range.startOffset);
    const start = preRange.toString().length;
    const end = start + range.toString().length;
    if (start < end) setSelection({ start, end });
  }

  return (
    <div className="relative">
      <pre
        id="annotated-body"
        className="whitespace-pre-wrap text-sm leading-relaxed text-gray-200 select-text"
        onMouseUp={handleMouseUp}
      >
        {segments.map((seg, i) =>
          seg.annotation ? (
            <mark
              key={i}
              className="bg-yellow-500/30 text-yellow-200 cursor-pointer rounded px-0.5"
              onClick={(e) =>
                setTooltip({ note: seg.annotation.note, audio_key: seg.annotation.audio_key, x: e.clientX, y: e.clientY })
              }
            >
              {seg.text}
            </mark>
          ) : (
            <span key={i}>{seg.text}</span>
          )
        )}
      </pre>

      {/* Annotation tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 bg-gray-800 border border-gray-600 rounded p-3 text-sm max-w-xs shadow-lg"
          style={{ top: tooltip.y + 12, left: tooltip.x }}
          onClick={() => setTooltip(null)}
        >
          <p className="text-gray-200">{tooltip.note}</p>
          {tooltip.audio_key && (
            <p className="text-xs text-gray-400 mt-1">Has delivery audio</p>
          )}
          <p className="text-xs text-gray-500 mt-1">click to dismiss</p>
        </div>
      )}

      {/* Selection action */}
      {selection && onAnnotate && (
        <div className="mt-2 flex items-center gap-2 text-sm">
          <span className="text-gray-400">
            Selected chars {selection.start}–{selection.end}
          </span>
          <button
            className="px-2 py-0.5 bg-yellow-600 text-white rounded hover:bg-yellow-500 text-xs"
            onClick={() => { onAnnotate(selection.start, selection.end); setSelection(null); }}
          >
            Annotate
          </button>
          <button
            className="px-2 py-0.5 text-gray-500 hover:text-gray-300 text-xs"
            onClick={() => setSelection(null)}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

function buildSegments(body, annotations) {
  if (!annotations.length) return [{ text: body }];

  // Sort by char_start, non-overlapping (take first)
  const sorted = [...annotations].sort((a, b) => a.char_start - b.char_start);
  const segments = [];
  let cursor = 0;

  for (const ann of sorted) {
    if (ann.char_start < cursor) continue;
    if (ann.char_start > cursor) segments.push({ text: body.slice(cursor, ann.char_start) });
    segments.push({ text: body.slice(ann.char_start, ann.char_end), annotation: ann });
    cursor = ann.char_end;
  }
  if (cursor < body.length) segments.push({ text: body.slice(cursor) });
  return segments;
}
