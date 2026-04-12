import React, { useState } from "react";

const BASE = import.meta.env.VITE_API_BASE ?? "";

/**
 * Streams annotation audio directly through the FastAPI proxy.
 * No presigned URLs — avoids R2 CORS issues entirely.
 */
export default function AnnotationPlayer({ annotationId }) {
  const [open, setOpen] = useState(false);
  const src = `${BASE}/annotations/${annotationId}/audio`;

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs text-green-500 hover:text-green-300"
      >
        ▶ play
      </button>
    );
  }

  return (
    <audio
      src={src}
      controls
      autoPlay
      className="h-7 max-w-[180px]"
    />
  );
}
