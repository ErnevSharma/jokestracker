import React, { useState } from "react";
import BitsView from "./views/BitsView";
import SetsView from "./views/SetsView";
import ShowsView from "./views/ShowsView";

const TABS = ["Bits", "Sets", "Shows"];

export default function App() {
  const [tab, setTab] = useState("Bits");

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-mono">
      {/* Header */}
      <header className="border-b border-gray-800 px-4 py-3 flex items-center gap-6">
        <span className="text-lg font-bold tracking-tight">jokes tracker</span>
        <nav className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1 rounded text-sm transition-colors ${
                tab === t
                  ? "bg-gray-700 text-white"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              {t.toLowerCase()}
            </button>
          ))}
        </nav>
      </header>

      {/* Content */}
      <main className="max-w-3xl mx-auto px-4 py-6">
        {tab === "Bits" && <BitsView />}
        {tab === "Sets" && <SetsView />}
        {tab === "Shows" && <ShowsView />}
      </main>
    </div>
  );
}
