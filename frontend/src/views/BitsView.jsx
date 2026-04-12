import React, { useEffect, useState, useCallback } from "react";
import {
  listBits, createBit, getBit, updateBit, deleteBit,
  getVersion, createVersion, createAnnotation, updateAnnotation,
  deleteAnnotation, uploadAnnotationAudio,
} from "../api";
import AnnotatedText from "../components/AnnotatedText";
import VersionTimeline from "../components/VersionTimeline";

const STATUS_COLORS = {
  drafting: "text-gray-400",
  working: "text-green-400",
  dead: "text-red-500 line-through",
};

export default function BitsView() {
  const [bits, setBits] = useState([]);
  const [selected, setSelected] = useState(null);        // bit (with versions[])
  const [activeVersion, setActiveVersion] = useState(null); // version detail
  const [newTitle, setNewTitle] = useState("");
  const [newBody, setNewBody] = useState("");
  const [annotating, setAnnotating] = useState(null);   // {start, end}
  const [annotNote, setAnnotNote] = useState("");

  const reload = useCallback(async () => {
    const bs = await listBits();
    setBits(bs);
    if (selected) {
      // Re-fetch selected bit to get updated version list
      const fresh = bs.find((b) => b.id === selected.id);
      if (fresh) setSelected(fresh);
    }
  }, [selected]);

  useEffect(() => { reload(); }, []);

  async function selectBit(bit) {
    const res = await getBit(bit.id);
    setSelected(res);
    setActiveVersion(null);
    setNewBody("");
  }

  async function selectVersion(v) {
    const detail = await getVersion(v.id);
    setActiveVersion(detail);
  }

  async function handleCreateBit(e) {
    e.preventDefault();
    if (!newTitle.trim()) return;
    await createBit({ title: newTitle.trim(), status: "drafting" });
    setNewTitle("");
    reload();
  }

  async function handleCreateVersion(e) {
    e.preventDefault();
    if (!selected || !newBody.trim()) return;
    await createVersion(selected.id, { body: newBody.trim() });
    setNewBody("");
    const res = await getBit(selected.id);
    setSelected(res);
    if (res.versions.length > 0) {
      const latest = res.versions[res.versions.length - 1];
      selectVersion(latest);
    }
  }

  async function handleAnnotate(start, end) {
    setAnnotating({ start, end });
    setAnnotNote("");
  }

  async function submitAnnotation(e) {
    e.preventDefault();
    if (!activeVersion || !annotating) return;
    await createAnnotation(activeVersion.id, {
      char_start: annotating.start,
      char_end: annotating.end,
      note: annotNote,
    });
    setAnnotating(null);
    const refreshed = await getVersion(activeVersion.id);
    setActiveVersion(refreshed);
  }

  async function handleDeleteAnnotation(annId) {
    await deleteAnnotation(annId);
    const refreshed = await getVersion(activeVersion.id);
    setActiveVersion(refreshed);
  }

  async function handleAudioUpload(annId, file) {
    await uploadAnnotationAudio(annId, file);
    const refreshed = await getVersion(activeVersion.id);
    setActiveVersion(refreshed);
  }

  async function cycleStatus(bit) {
    const next = { drafting: "working", working: "dead", dead: "drafting" };
    await updateBit(bit.id, { status: next[bit.status] });
    reload();
  }

  return (
    <div className="space-y-6">
      {/* Create bit */}
      <form onSubmit={handleCreateBit} className="flex gap-2">
        <input
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          placeholder="New bit title…"
          className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gray-500"
        />
        <button className="px-3 py-1.5 bg-gray-700 text-white rounded text-sm hover:bg-gray-600">
          Add
        </button>
      </form>

      {/* Bit list */}
      <ul className="space-y-1">
        {bits.map((bit) => (
          <li key={bit.id} className="flex items-center gap-2">
            <button
              onClick={() => selectBit(bit)}
              className={`flex-1 text-left text-sm px-2 py-1 rounded hover:bg-gray-800 ${
                selected?.id === bit.id ? "bg-gray-800" : ""
              } ${STATUS_COLORS[bit.status]}`}
            >
              {bit.title}
              <span className="ml-2 text-xs text-gray-600">{bit.version_count}v</span>
            </button>
            <button
              onClick={() => cycleStatus(bit)}
              className="text-xs text-gray-600 hover:text-gray-300 px-1"
              title="Cycle status"
            >
              {bit.status}
            </button>
          </li>
        ))}
      </ul>

      {/* Bit detail */}
      {selected && (
        <div className="border border-gray-800 rounded p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">{selected.title}</h2>
            <button onClick={() => setSelected(null)} className="text-xs text-gray-500 hover:text-white">×</button>
          </div>

          <VersionTimeline
            versions={selected.versions}
            selectedId={activeVersion?.id}
            onSelect={selectVersion}
          />

          {/* New version */}
          <form onSubmit={handleCreateVersion} className="space-y-2">
            <textarea
              value={newBody}
              onChange={(e) => setNewBody(e.target.value)}
              placeholder="Write new version…"
              rows={4}
              className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-gray-500 font-mono"
            />
            <button className="px-3 py-1 bg-gray-700 text-white rounded text-sm hover:bg-gray-600">
              Save Version
            </button>
          </form>

          {/* Version detail */}
          {activeVersion && (
            <div className="space-y-4">
              <div className="border-t border-gray-800 pt-4">
                <p className="text-xs text-gray-500 mb-2">
                  v{activeVersion.version_num} · {new Date(activeVersion.created_at).toLocaleDateString()}
                </p>
                <AnnotatedText
                  body={activeVersion.body}
                  annotations={activeVersion.annotations}
                  onAnnotate={handleAnnotate}
                />
              </div>

              {/* Annotate form */}
              {annotating && (
                <form onSubmit={submitAnnotation} className="flex gap-2 items-center">
                  <input
                    value={annotNote}
                    onChange={(e) => setAnnotNote(e.target.value)}
                    placeholder="Note for this selection…"
                    className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1 text-sm text-white placeholder-gray-500 focus:outline-none"
                    autoFocus
                  />
                  <button className="px-2 py-1 bg-yellow-700 text-white rounded text-sm hover:bg-yellow-600">Save</button>
                  <button type="button" onClick={() => setAnnotating(null)} className="text-sm text-gray-500 hover:text-white">Cancel</button>
                </form>
              )}

              {/* Annotation list */}
              {activeVersion.annotations?.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs text-gray-500">annotations</p>
                  {activeVersion.annotations.map((ann) => (
                    <div key={ann.id} className="flex items-start gap-2 text-sm">
                      <span className="text-gray-600 text-xs mt-0.5">
                        {ann.char_start}–{ann.char_end}
                      </span>
                      <span className="flex-1 text-gray-300">{ann.note}</span>
                      {ann.audio_key ? (
                        <span className="text-xs text-green-500">audio</span>
                      ) : (
                        <label className="text-xs text-gray-500 hover:text-white cursor-pointer">
                          + audio
                          <input
                            type="file"
                            accept="audio/*"
                            className="hidden"
                            onChange={(e) => e.target.files[0] && handleAudioUpload(ann.id, e.target.files[0])}
                          />
                        </label>
                      )}
                      <button
                        onClick={() => handleDeleteAnnotation(ann.id)}
                        className="text-red-600 hover:text-red-400 text-xs"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
