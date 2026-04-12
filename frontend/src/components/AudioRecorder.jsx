import React, { useRef, useState } from "react";

/**
 * Inline audio recorder using MediaRecorder API.
 * onRecorded(blob) is called when the user stops recording.
 * Also accepts a file upload as an alternative.
 */
export default function AudioRecorder({ onRecorded, disabled = false }) {
  const [state, setState] = useState("idle"); // idle | requesting | recording | done
  const [seconds, setSeconds] = useState(0);
  const [blob, setBlob] = useState(null);
  const mediaRecorder = useRef(null);
  const chunks = useRef([]);
  const timer = useRef(null);

  async function startRecording() {
    setState("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunks.current = [];
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunks.current.push(e.data); };
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        clearInterval(timer.current);
        const recorded = new Blob(chunks.current, { type: "audio/webm" });
        setBlob(recorded);
        setState("done");
        onRecorded(recorded);
      };
      mr.start(100);
      mediaRecorder.current = mr;
      setState("recording");
      setSeconds(0);
      timer.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch {
      setState("idle");
      alert("Microphone access denied.");
    }
  }

  function stopRecording() {
    mediaRecorder.current?.stop();
  }

  function discard() {
    setBlob(null);
    setSeconds(0);
    setState("idle");
    onRecorded(null);
  }

  function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBlob(file);
    setState("done");
    onRecorded(file);
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      {state === "idle" && (
        <>
          <button
            type="button"
            onClick={startRecording}
            disabled={disabled}
            className="flex items-center gap-1.5 px-2 py-1 rounded border border-gray-600 text-gray-400 hover:text-white hover:border-gray-400 disabled:opacity-40 transition-colors"
          >
            <span className="text-red-500">●</span> Record
          </button>
          <label className="text-xs text-gray-500 hover:text-gray-300 cursor-pointer">
            or upload
            <input type="file" accept="audio/*" className="hidden" onChange={handleFile} />
          </label>
        </>
      )}

      {state === "requesting" && (
        <span className="text-gray-500 text-xs animate-pulse">Waiting for mic…</span>
      )}

      {state === "recording" && (
        <button
          type="button"
          onClick={stopRecording}
          className="flex items-center gap-1.5 px-2 py-1 rounded border border-red-600 text-red-400 hover:text-red-300 animate-pulse"
        >
          <span>■</span> Stop · {seconds}s
        </button>
      )}

      {state === "done" && (
        <>
          <span className="text-green-500 text-xs">
            ✓ {blob instanceof File ? blob.name : `${seconds}s recorded`}
          </span>
          <button
            type="button"
            onClick={discard}
            className="text-xs text-gray-500 hover:text-red-400"
          >
            discard
          </button>
        </>
      )}
    </div>
  );
}
