// Dev: VITE_API_BASE=http://localhost:8000 (set in .env.development)
// Production: empty string → same-origin (FastAPI serves the frontend)
const BASE = import.meta.env.VITE_API_BASE ?? "";

async function req(method, path, body, isForm = false) {
  const opts = { method, headers: {} };
  if (body && !isForm) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  } else if (isForm) {
    opts.body = body; // FormData
  }
  const r = await fetch(`${BASE}${path}`, opts);
  if (!r.ok) throw new Error(`${method} ${path} → ${r.status}`);
  if (r.status === 204) return null;
  return r.json();
}

// ── Bits ──────────────────────────────────────────────────────────────────────
export const listBits = () => req("GET", "/bits");
export const createBit = (data) => req("POST", "/bits", data);
export const getBit = (id) => req("GET", `/bits/${id}`);
export const updateBit = (id, data) => req("PATCH", `/bits/${id}`, data);
export const deleteBit = (id) => req("DELETE", `/bits/${id}`);
export const getBitAppearances = (id) => req("GET", `/bits/${id}/appearances`);

// ── Versions ──────────────────────────────────────────────────────────────────
export const listVersions = (bitId) => req("GET", `/bits/${bitId}/versions`);
export const createVersion = (bitId, data) => req("POST", `/bits/${bitId}/versions`, data);
export const getVersion = (id) => req("GET", `/versions/${id}`);
export const diffVersions = (aId, bId) => req("GET", `/versions/${aId}/diff/${bId}`);

// ── Annotations ───────────────────────────────────────────────────────────────
export const listAnnotations = (versionId) => req("GET", `/versions/${versionId}/annotations`);
export const createAnnotation = (versionId, data) => req("POST", `/versions/${versionId}/annotations`, data);
export const updateAnnotation = (id, data) => req("PATCH", `/annotations/${id}`, data);
export const deleteAnnotation = (id) => req("DELETE", `/annotations/${id}`);
export const getAnnotationAudioUrl = (id) => req("GET", `/annotations/${id}/audio`);
export const uploadAnnotationAudio = (id, file) => {
  const fd = new FormData();
  // Give blobs a filename so python-multipart correctly parses the content-type
  const name = file instanceof File ? file.name : "recording.webm";
  fd.append("file", file, name);
  return req("POST", `/annotations/${id}/audio`, fd, true);
};

// ── Sets ──────────────────────────────────────────────────────────────────────
export const listSets = () => req("GET", "/sets");
export const createSet = (data) => req("POST", "/sets", data);
export const getSet = (id) => req("GET", `/sets/${id}`);
export const updateSet = (id, data) => req("PATCH", `/sets/${id}`, data);
export const getSetShows = (id) => req("GET", `/sets/${id}/shows`);
export const listSetVersions = (setId) => req("GET", `/sets/${setId}/versions`);
export const createSetVersion = (setId, data) => req("POST", `/sets/${setId}/versions`, data);
export const getSetVersion = (id) => req("GET", `/set-versions/${id}`);

// ── Shows ─────────────────────────────────────────────────────────────────────
export const listShows = () => req("GET", "/shows");
export const createShow = (data) => req("POST", "/shows", data);
export const getShow = (id) => req("GET", `/shows/${id}`);
export const updateShow = (id, data) => req("PATCH", `/shows/${id}`, data);
export const uploadShowAudio = (id, file) => {
  const fd = new FormData();
  const name = file instanceof File ? file.name : "recording.webm";
  fd.append("file", file, name);
  return req("POST", `/shows/${id}/audio`, fd, true);
};

// ── Analysis ──────────────────────────────────────────────────────────────────
export const getJob = (id) => req("GET", `/jobs/${id}`);
