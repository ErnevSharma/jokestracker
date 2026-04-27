import React, { useEffect, useState } from "react";
import { listShows, createShow, getShow, updateShow, uploadShowAudio, getJob, listSets, listSetVersions } from "../api";
import LaughHeatmap from "../components/LaughHeatmap";
import AudioRecorder from "../components/AudioRecorder";

const CROWD_SIZE = ["small", "medium", "large"];
const CROWD_ENERGY = ["dead", "lukewarm", "warm", "hot"];
const RATING = ["killed", "ok", "died"];

export default function ShowsView() {
  const [shows, setShows] = useState([]);
  const [selected, setSelected] = useState(null);
  const [sets, setSets] = useState([]);
  const [setVersions, setSetVersions] = useState([]);
  const [form, setForm] = useState({ set_version_id: "", date: "", venue: "", crowd_size: "", crowd_energy: "", rating: "", notes: "" });
  const [creating, setCreating] = useState(false);
  const [polling, setPolling] = useState(null); // job_id being polled

  useEffect(() => {
    listShows().then(setShows);
    listSets().then(setSets);
  }, []);

  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(async () => {
      const job = await getJob(polling);
      if (job.status === "complete" || job.status === "failed") {
        clearInterval(interval);
        setPolling(null);
        if (selected) {
          const refreshed = await getShow(selected.id);
          setSelected(refreshed);
        }
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [polling, selected]);

  async function selectShow(s) {
    const detail = await getShow(s.id);
    setSelected(detail);
  }

  async function handleSetChange(setId) {
    setForm((f) => ({ ...f, set_version_id: "", _set_id: setId }));
    if (setId) {
      const svs = await listSetVersions(setId);
      setSetVersions(svs);
    } else {
      setSetVersions([]);
    }
  }

  async function handleCreate(e) {
    e.preventDefault();
    const payload = Object.fromEntries(
      Object.entries(form).filter(([k, v]) => v && !k.startsWith("_"))
    );
    await createShow(payload);
    setCreating(false);
    setForm({ set_version_id: "", date: "", venue: "", crowd_size: "", crowd_energy: "", rating: "", notes: "" });
    listShows().then(setShows);
  }

  async function handleAudioUpload(file) {
    if (!selected) return;
    const res = await uploadShowAudio(selected.id, file);
    setPolling(res.job_id);
    const refreshed = await getShow(selected.id);
    setSelected(refreshed);
  }

  async function handleRatingChange(rating) {
    if (!selected) return;
    await updateShow(selected.id, { rating });
    const refreshed = await getShow(selected.id);
    setSelected(refreshed);
    listShows().then(setShows);
  }

  return (
    <div className="space-y-6">
      {/* Create show */}
      <button
        onClick={() => setCreating((c) => !c)}
        className="text-sm text-gray-400 hover:text-white border border-gray-700 border-dashed px-3 py-1 rounded hover:border-gray-500"
      >
        {creating ? "Cancel" : "+ Log Show"}
      </button>

      {creating && (
        <form onSubmit={handleCreate} className="border border-gray-800 rounded p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500">Set</label>
              <select
                className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-white mt-0.5"
                onChange={(e) => handleSetChange(e.target.value)}
              >
                <option value="">Choose set…</option>
                {sets.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500">Set Version</label>
              <select
                className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-white mt-0.5"
                value={form.set_version_id}
                onChange={(e) => setForm((f) => ({ ...f, set_version_id: e.target.value }))}
              >
                <option value="">Choose version…</option>
                {setVersions.map((sv) => <option key={sv.id} value={sv.id}>v{sv.version_num} ({sv.item_count} bits)</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500">Date</label>
              <input
                type="date"
                required
                className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-white mt-0.5"
                value={form.date}
                onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-xs text-gray-500">Venue</label>
              <input
                className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-white mt-0.5 placeholder-gray-600"
                placeholder="optional"
                value={form.venue}
                onChange={(e) => setForm((f) => ({ ...f, venue: e.target.value }))}
              />
            </div>
          </div>

          <div className="flex gap-3">
            <SegmentPicker label="Crowd" options={CROWD_SIZE} value={form.crowd_size} onChange={(v) => setForm((f) => ({ ...f, crowd_size: v }))} />
            <SegmentPicker label="Energy" options={CROWD_ENERGY} value={form.crowd_energy} onChange={(v) => setForm((f) => ({ ...f, crowd_energy: v }))} />
            <SegmentPicker label="Rating" options={RATING} value={form.rating} onChange={(v) => setForm((f) => ({ ...f, rating: v }))} />
          </div>

          <textarea
            placeholder="Notes (optional)…"
            rows={2}
            className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-white placeholder-gray-600"
            value={form.notes}
            onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
          />

          <button
            type="submit"
            disabled={!form.set_version_id || !form.date}
            className="px-3 py-1 bg-blue-700 text-white rounded text-sm hover:bg-blue-600 disabled:opacity-40"
          >
            Log Show
          </button>
        </form>
      )}

      {/* Show list */}
      <ul className="space-y-1">
        {shows.map((s) => (
          <li key={s.id}>
            <button
              onClick={() => selectShow(s)}
              className={`w-full text-left text-sm px-2 py-1 rounded hover:bg-gray-800 ${selected?.id === s.id ? "bg-gray-800" : ""}`}
            >
              <span className="text-gray-200">{s.date}</span>
              {s.venue && <span className="ml-2 text-gray-400">{s.venue}</span>}
              {s.rating && <span className={`ml-2 text-xs ${ratingColor(s.rating)}`}>{s.rating}</span>}
            </button>
          </li>
        ))}
      </ul>

      {/* Show detail */}
      {selected && (
        <div className="border border-gray-800 rounded p-4 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold">{selected.date}{selected.venue && ` · ${selected.venue}`}</p>
              <div className="flex gap-3 mt-1 text-xs text-gray-400">
                {selected.crowd_size && <span>crowd: {selected.crowd_size}</span>}
                {selected.crowd_energy && <span>energy: {selected.crowd_energy}</span>}
              </div>
            </div>
            <button onClick={() => setSelected(null)} className="text-xs text-gray-500 hover:text-white">×</button>
          </div>

          {/* Rating picker */}
          <SegmentPicker
            label="Rating"
            options={RATING}
            value={selected.rating}
            onChange={handleRatingChange}
          />

          {selected.notes && <p className="text-sm text-gray-400">{selected.notes}</p>}

          {/* Audio upload / record */}
          {!selected.audio_key && (
            <div className="border border-dashed border-gray-700 rounded px-3 py-2">
              <p className="text-xs text-gray-500 mb-2">Show recording</p>
              <AudioRecorder onRecorded={(blob) => blob && handleAudioUpload(blob)} />
            </div>
          )}

          {/* Job status */}
          {selected.job && selected.job.status !== "complete" && (
            <div className="text-sm text-gray-400 flex items-center gap-2">
              <span className="animate-pulse">●</span>
              Analysis {selected.job.status}…
            </div>
          )}

          {selected.job?.status === "failed" && (
            <p className="text-sm text-red-400">Analysis failed: {selected.job.error}</p>
          )}

          {/* Analysis result - Transcript with laugh heatmap */}
          {selected.result && (
            <div className="border-t border-gray-800 pt-4 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Transcript & Laugh Detection</p>
                {selected.result.laugh_timestamps && JSON.parse(selected.result.laugh_timestamps).length > 0 && (
                  <span className="text-xs text-green-400">
                    {JSON.parse(selected.result.laugh_timestamps).length} laughs detected
                  </span>
                )}
              </div>
              <LaughHeatmap
                transcript={selected.result.whisper_transcript}
                laughTimestamps={selected.result.laugh_timestamps}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SegmentPicker({ label, options, value, onChange }) {
  return (
    <div>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <div className="flex gap-1">
        {options.map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => onChange(value === opt ? "" : opt)}
            className={`px-2 py-0.5 rounded text-xs border transition-colors ${
              value === opt
                ? "bg-gray-600 border-gray-500 text-white"
                : "border-gray-700 text-gray-500 hover:text-white hover:border-gray-500"
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  );
}

function ratingColor(r) {
  return r === "killed" ? "text-green-400" : r === "died" ? "text-red-400" : "text-gray-400";
}
