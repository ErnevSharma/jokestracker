import React, { useEffect, useState } from "react";
import { listBits, listVersions, createSetVersion } from "../api";

/**
 * UI for creating a new SetVersion from available bit versions.
 * onCreated: called with the new set version after creation.
 */
export default function SetBuilder({ setId, onCreated, onCancel }) {
  const [bits, setBits] = useState([]);
  const [selectedItems, setSelectedItems] = useState([]); // [{bit, version}]
  const [versionMap, setVersionMap] = useState({}); // bit_id → versions[]
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    listBits().then((bs) => setBits(bs.filter((b) => b.status !== "dead")));
  }, []);

  async function loadVersions(bit) {
    if (versionMap[bit.id]) return;
    const vs = await listVersions(bit.id);
    setVersionMap((m) => ({ ...m, [bit.id]: vs }));
  }

  function addItem(bit, version) {
    if (selectedItems.find((i) => i.version.id === version.id)) return;
    setSelectedItems((prev) => [...prev, { bit, version }]);
  }

  function removeItem(versionId) {
    setSelectedItems((prev) => prev.filter((i) => i.version.id !== versionId));
  }

  function move(idx, dir) {
    const next = [...selectedItems];
    const swap = idx + dir;
    if (swap < 0 || swap >= next.length) return;
    [next[idx], next[swap]] = [next[swap], next[idx]];
    setSelectedItems(next);
  }

  async function save() {
    if (!selectedItems.length) return;
    setSaving(true);
    try {
      const sv = await createSetVersion(setId, {
        items: selectedItems.map((item, i) => ({
          version_id: item.version.id,
          position: i + 1,
        })),
      });
      onCreated(sv);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="border border-gray-700 rounded p-4 space-y-4">
      <h4 className="text-sm font-semibold text-gray-300">New Set Version</h4>

      {/* Selected order */}
      {selectedItems.length > 0 && (
        <ol className="space-y-1">
          {selectedItems.map((item, i) => (
            <li key={item.version.id} className="flex items-center gap-2 text-sm">
              <span className="text-gray-500 w-4">{i + 1}.</span>
              <span className="flex-1 text-gray-200">{item.bit.title}</span>
              <span className="text-gray-500">v{item.version.version_num}</span>
              <button onClick={() => move(i, -1)} className="text-gray-500 hover:text-white">↑</button>
              <button onClick={() => move(i, 1)} className="text-gray-500 hover:text-white">↓</button>
              <button onClick={() => removeItem(item.version.id)} className="text-red-500 hover:text-red-300">×</button>
            </li>
          ))}
        </ol>
      )}

      {/* Bit picker */}
      <div className="space-y-2">
        {bits.map((bit) => (
          <div key={bit.id} className="text-sm">
            <button
              className="text-gray-400 hover:text-white flex items-center gap-1"
              onClick={() => loadVersions(bit)}
            >
              + {bit.title}
            </button>
            {versionMap[bit.id] && (
              <div className="ml-4 flex gap-1 mt-1 flex-wrap">
                {versionMap[bit.id].map((v) => (
                  <button
                    key={v.id}
                    onClick={() => addItem(bit, v)}
                    className="px-2 py-0.5 border border-gray-700 rounded text-xs text-gray-400 hover:text-white hover:border-gray-500"
                  >
                    v{v.version_num} <span className="text-gray-600">{v.char_count}c</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <button
          onClick={save}
          disabled={!selectedItems.length || saving}
          className="px-3 py-1 bg-blue-700 text-white rounded text-sm disabled:opacity-40 hover:bg-blue-600"
        >
          {saving ? "Saving…" : "Save Set Version"}
        </button>
        <button onClick={onCancel} className="px-3 py-1 text-gray-500 hover:text-white text-sm">
          Cancel
        </button>
      </div>
    </div>
  );
}
