import React, { useEffect, useState } from "react";
import { listSets, createSet, getSet, getSetVersion } from "../api";
import SetBuilder from "../components/SetBuilder";

export default function SetsView() {
  const [sets, setSets] = useState([]);
  const [selected, setSelected] = useState(null);       // set detail with set_versions
  const [activeSetVersion, setActiveSetVersion] = useState(null); // set version detail
  const [newName, setNewName] = useState("");
  const [building, setBuilding] = useState(false);

  useEffect(() => { listSets().then(setSets); }, []);

  async function selectSet(s) {
    const detail = await getSet(s.id);
    setSelected(detail);
    setActiveSetVersion(null);
    setBuilding(false);
  }

  async function selectSetVersion(sv) {
    const detail = await getSetVersion(sv.id);
    setActiveSetVersion(detail);
  }

  async function handleCreate(e) {
    e.preventDefault();
    if (!newName.trim()) return;
    await createSet({ name: newName.trim() });
    setNewName("");
    listSets().then(setSets);
  }

  async function handleBuilderCreated(sv) {
    setBuilding(false);
    const detail = await getSet(selected.id);
    setSelected(detail);
    selectSetVersion(sv);
  }

  return (
    <div className="space-y-6">
      {/* Create set */}
      <form onSubmit={handleCreate} className="flex gap-2">
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="New set name…"
          className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gray-500"
        />
        <button className="px-3 py-1.5 bg-gray-700 text-white rounded text-sm hover:bg-gray-600">
          Add
        </button>
      </form>

      {/* Set list */}
      <ul className="space-y-1">
        {sets.map((s) => (
          <li key={s.id}>
            <button
              onClick={() => selectSet(s)}
              className={`w-full text-left text-sm px-2 py-1 rounded hover:bg-gray-800 ${
                selected?.id === s.id ? "bg-gray-800" : ""
              } text-gray-200`}
            >
              {s.name}
              <span className="ml-2 text-xs text-gray-600">{s.version_count} version{s.version_count !== 1 ? "s" : ""}</span>
            </button>
          </li>
        ))}
      </ul>

      {/* Set detail */}
      {selected && (
        <div className="border border-gray-800 rounded p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">{selected.name}</h2>
            <button onClick={() => setSelected(null)} className="text-xs text-gray-500 hover:text-white">×</button>
          </div>

          {/* Set versions */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-gray-500">versions:</span>
            {selected.set_versions?.map((sv) => (
              <button
                key={sv.id}
                onClick={() => selectSetVersion(sv)}
                className={`px-2 py-0.5 rounded text-xs border transition-colors ${
                  activeSetVersion?.id === sv.id
                    ? "bg-gray-600 border-gray-500 text-white"
                    : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white"
                }`}
              >
                v{sv.version_num}
              </button>
            ))}
            <button
              onClick={() => setBuilding(true)}
              className="px-2 py-0.5 border border-dashed border-gray-700 text-gray-500 hover:text-white hover:border-gray-500 rounded text-xs"
            >
              + new version
            </button>
          </div>

          {/* Set version builder */}
          {building && (
            <SetBuilder
              setId={selected.id}
              onCreated={handleBuilderCreated}
              onCancel={() => setBuilding(false)}
            />
          )}

          {/* Set version detail */}
          {activeSetVersion && (
            <div className="border-t border-gray-800 pt-4 space-y-2">
              <p className="text-xs text-gray-500">
                v{activeSetVersion.version_num} · {activeSetVersion.items?.length} bit{activeSetVersion.items?.length !== 1 ? "s" : ""}
              </p>
              <ol className="space-y-1">
                {activeSetVersion.items?.map((item) => (
                  <li key={item.id} className="flex items-center gap-2 text-sm">
                    <span className="text-gray-600 w-4">{item.position}.</span>
                    <span className="text-gray-200">{item.bit_title}</span>
                    <span className="text-gray-500">v{item.version_num}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
