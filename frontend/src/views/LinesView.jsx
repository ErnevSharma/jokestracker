import React, { useEffect, useState, useCallback } from "react";
import {
  listLines, createLine, getLine, updateLine, deleteLine,
  createLineAnnotation, updateLineAnnotation, deleteLineAnnotation,
  uploadLineAnnotationAudio,
} from "../api";
import AnnotatedText from "../components/AnnotatedText";
import AudioRecorder from "../components/AudioRecorder";
import AnnotationPlayer from "../components/AnnotationPlayer";

export default function LinesView() {
  const [lines, setLines] = useState([]);
  const [selected, setSelected] = useState(null);      // line with annotations
  const [newBody, setNewBody] = useState("");
  const [editing, setEditing] = useState(null);        // line id being edited
  const [editBody, setEditBody] = useState("");
  const [annotating, setAnnotating] = useState(null);  // {start, end}
  const [annotNote, setAnnotNote] = useState("");
  const [annotAudio, setAnnotAudio] = useState(null);  // Blob | File | null

  const reload = useCallback(async () => {
    const ls = await listLines();
    setLines(ls);
  }, []);

  useEffect(() => { reload(); }, []);

  async function selectLine(line) {
    const res = await getLine(line.id);
    setSelected(res);
    setEditing(null);
  }

  async function handleCreateLine(e) {
    e.preventDefault();
    if (!newBody.trim()) return;
    await createLine({ body: newBody.trim() });
    setNewBody("");
    reload();
  }

  async function startEdit(line) {
    setEditing(line.id);
    setEditBody(line.body);
  }

  async function handleUpdateLine(e) {
    e.preventDefault();
    if (!editing || !editBody.trim()) return;
    await updateLine(editing, { body: editBody.trim() });
    setEditing(null);
    reload();
    if (selected?.id === editing) {
      const refreshed = await getLine(editing);
      setSelected(refreshed);
    }
  }

  async function handleDeleteLine(lineId) {
    if (!confirm("Delete this line and all its annotations?")) return;
    await deleteLine(lineId);
    if (selected?.id === lineId) setSelected(null);
    reload();
  }

  async function handleAnnotate(start, end) {
    setAnnotating({ start, end });
    setAnnotNote("");
    setAnnotAudio(null);
  }

  async function submitAnnotation(e) {
    e.preventDefault();
    if (!selected || !annotating) return;
    const ann = await createLineAnnotation(selected.id, {
      char_start: annotating.start,
      char_end: annotating.end,
      note: annotNote,
    });
    if (annotAudio) {
      await uploadLineAnnotationAudio(ann.id, annotAudio);
    }
    setAnnotating(null);
    setAnnotAudio(null);
    const refreshed = await getLine(selected.id);
    setSelected(refreshed);
  }

  async function handleDeleteAnnotation(annId) {
    await deleteLineAnnotation(annId);
    const refreshed = await getLine(selected.id);
    setSelected(refreshed);
  }

  async function handleAudioUpload(annId, file) {
    await uploadLineAnnotationAudio(annId, file);
    const refreshed = await getLine(selected.id);
    setSelected(refreshed);
  }

  return (
    <div className="space-y-6">
      {/* Create line */}
      <form onSubmit={handleCreateLine} className="space-y-2">
        <textarea
          value={newBody}
          onChange={(e) => setNewBody(e.target.value)}
          placeholder="Write a new line or idea…"
          rows={3}
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gray-500 font-mono"
        />
        <button className="px-3 py-1.5 bg-gray-700 text-white rounded text-sm hover:bg-gray-600">
          Add Line
        </button>
      </form>

      {/* Lines list */}
      <div className="space-y-2">
        {lines.map((line) => (
          <div
            key={line.id}
            className={`border border-gray-800 rounded p-3 ${
              selected?.id === line.id ? "bg-gray-900" : ""
            }`}
          >
            {editing === line.id ? (
              <form onSubmit={handleUpdateLine} className="space-y-2">
                <textarea
                  value={editBody}
                  onChange={(e) => setEditBody(e.target.value)}
                  rows={3}
                  className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-white font-mono focus:outline-none"
                  autoFocus
                />
                <div className="flex gap-2">
                  <button className="px-2 py-1 bg-gray-700 text-white rounded text-xs hover:bg-gray-600">
                    Save
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditing(null)}
                    className="text-xs text-gray-500 hover:text-white"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            ) : (
              <>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <button
                    onClick={() => selectLine(line)}
                    className="flex-1 text-left text-sm text-gray-300 whitespace-pre-wrap font-mono hover:text-white"
                  >
                    {line.body}
                  </button>
                  <div className="flex gap-2">
                    <button
                      onClick={() => startEdit(line)}
                      className="text-xs text-gray-600 hover:text-gray-300"
                    >
                      edit
                    </button>
                    <button
                      onClick={() => handleDeleteLine(line.id)}
                      className="text-xs text-red-600 hover:text-red-400"
                    >
                      ×
                    </button>
                  </div>
                </div>
                <p className="text-xs text-gray-600">
                  {new Date(line.updated_at).toLocaleDateString()}
                </p>
              </>
            )}

            {/* Expanded line detail */}
            {selected?.id === line.id && !editing && (
              <div className="mt-4 space-y-4 border-t border-gray-800 pt-4">
                <AnnotatedText
                  body={selected.body}
                  annotations={selected.annotations}
                  onAnnotate={handleAnnotate}
                />

                {/* Annotate form */}
                {annotating && (
                  <form onSubmit={submitAnnotation} className="space-y-2 border border-gray-700 rounded p-3">
                    <input
                      value={annotNote}
                      onChange={(e) => setAnnotNote(e.target.value)}
                      placeholder="Note for this selection…"
                      className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1 text-sm text-white placeholder-gray-500 focus:outline-none"
                      autoFocus
                    />
                    <AudioRecorder onRecorded={setAnnotAudio} />
                    <div className="flex gap-2">
                      <button className="px-2 py-1 bg-yellow-700 text-white rounded text-sm hover:bg-yellow-600">
                        Save
                      </button>
                      <button
                        type="button"
                        onClick={() => setAnnotating(null)}
                        className="text-sm text-gray-500 hover:text-white"
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                )}

                {/* Annotation list */}
                {selected.annotations?.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs text-gray-500">annotations</p>
                    {selected.annotations.map((ann) => (
                      <div key={ann.id} className="flex items-start gap-2 text-sm">
                        <span className="text-gray-600 text-xs mt-0.5">
                          {ann.char_start}–{ann.char_end}
                        </span>
                        <span className="flex-1 text-gray-300">{ann.note}</span>
                        {ann.audio_key ? (
                          <AnnotationPlayer
                            annotationId={ann.id}
                            apiPath={`/lines/annotations/${ann.id}/audio`}
                          />
                        ) : (
                          <label className="text-xs text-gray-500 hover:text-white cursor-pointer">
                            + audio
                            <input
                              type="file"
                              accept="audio/*"
                              className="hidden"
                              onChange={(e) =>
                                e.target.files[0] && handleAudioUpload(ann.id, e.target.files[0])
                              }
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
        ))}
      </div>
    </div>
  );
}
