import React, { useState } from "react";
import { getAnnotationAudioUrl } from "../api";

/**
 * Fetches a presigned R2 URL for an annotation's audio and renders a player.
 * URL is fetched lazily on first click (presigned URLs expire after 1hr).
 */
export default function AnnotationPlayer({ annotationId }) {
  const [url, setUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function load() {
    if (url) return; // already loaded
    setLoading(true);
    setError(null);
    try {
      const res = await getAnnotationAudioUrl(annotationId);
      setUrl(res.url);
    } catch {
      setError("Could not load audio");
    } finally {
      setLoading(false);
    }
  }

  if (error) return <span className="text-xs text-red-400">{error}</span>;

  if (!url) {
    return (
      <button
        type="button"
        onClick={load}
        disabled={loading}
        className="text-xs text-green-500 hover:text-green-300 disabled:opacity-50"
      >
        {loading ? "loading…" : "▶ play"}
      </button>
    );
  }

  return (
    <audio
      src={url}
      controls
      autoPlay
      className="h-7 max-w-[180px]"
    />
  );
}
