"""Quick integration test against a running server on localhost:8000."""
import json
import sys
import httpx

BASE = "http://127.0.0.1:8000"
c = httpx.Client(base_url=BASE, timeout=10)


def ok(r, label):
    assert r.status_code < 300, f"{label} failed {r.status_code}: {r.text}"
    return r.json()


# ── Health ────────────────────────────────────────────────────────────────────
ok(c.get("/health"), "health")
print("✓ health")

# ── Bits ──────────────────────────────────────────────────────────────────────
bit = ok(c.post("/bits", json={"title": "Airport Bit", "status": "drafting"}), "create bit")
bit_id = bit["id"]

bits = ok(c.get("/bits"), "list bits")
assert any(b["id"] == bit_id for b in bits)
print("✓ bits: create + list")

# ── Versions ──────────────────────────────────────────────────────────────────
v1 = ok(c.post(f"/bits/{bit_id}/versions", json={
    "body": "I hate airports.\nSecurity takes forever.\nShoes off, dignity gone."
}), "create version 1")
v1_id = v1["id"]
assert v1["version_num"] == 1

v2 = ok(c.post(f"/bits/{bit_id}/versions", json={
    "body": "I hate airports.\nSecurity takes forty-five minutes.\nShoes off, laptop out, dignity gone."
}), "create version 2")
v2_id = v2["id"]
assert v2["version_num"] == 2
print("✓ versions: create two, version_num increments")

versions = ok(c.get(f"/bits/{bit_id}/versions"), "list versions")
assert len(versions) == 2
assert versions[0]["char_count"] > 0
print("✓ versions: list with char_count")

v1_detail = ok(c.get(f"/versions/{v1_id}"), "version detail")
assert v1_detail["body"].startswith("I hate")
print("✓ versions: detail")

diff = ok(c.get(f"/versions/{v1_id}/diff/{v2_id}"), "diff")
assert "opcodes" in diff and len(diff["opcodes"]) > 0
print("✓ versions: diff")

# ── Annotations ───────────────────────────────────────────────────────────────
ann = ok(c.post(f"/versions/{v1_id}/annotations", json={
    "char_start": 0, "char_end": 17, "note": "Slow delivery"
}), "create annotation")
ann_id = ann["id"]

anns = ok(c.get(f"/versions/{v1_id}/annotations"), "list annotations")
assert len(anns) == 1
print("✓ annotations: create + list")

patched = ok(c.patch(f"/annotations/{ann_id}", json={"note": "Even slower"}), "patch annotation")
assert patched["note"] == "Even slower"
assert patched["char_start"] == 0   # immutable
print("✓ annotations: patch note only")

# Bad range
r = c.post(f"/versions/{v1_id}/annotations", json={"char_start": 100, "char_end": 5})
assert r.status_code == 422
print("✓ annotations: invalid range rejected")

# ── Sets + SetVersions ────────────────────────────────────────────────────────
s = ok(c.post("/sets", json={"name": "Club Set"}), "create set")
set_id = s["id"]

sets = ok(c.get("/sets"), "list sets")
assert any(x["id"] == set_id for x in sets)
print("✓ sets: create + list")

sv = ok(c.post(f"/sets/{set_id}/versions", json={
    "items": [
        {"version_id": v1_id, "position": 1},
        {"version_id": v2_id, "position": 2},
    ]
}), "create set version")
sv_id = sv["id"]
assert sv["version_num"] == 1
print("✓ set versions: create")

sv_detail = ok(c.get(f"/set-versions/{sv_id}"), "set version detail")
assert len(sv_detail["items"]) == 2
assert sv_detail["items"][0]["position"] == 1
assert sv_detail["items"][0]["bit_title"] == "Airport Bit"
print("✓ set versions: detail with enriched items")

# ── Shows ─────────────────────────────────────────────────────────────────────
show = ok(c.post("/shows", json={
    "set_version_id": sv_id,
    "date": "2026-04-11",
    "venue": "The Comedy Store",
    "crowd_size": "medium",
    "crowd_energy": "warm",
    "rating": "ok",
}), "create show")
show_id = show["id"]

shows = ok(c.get("/shows"), "list shows")
assert any(x["id"] == show_id for x in shows)
print("✓ shows: create + list")

show_detail = ok(c.get(f"/shows/{show_id}"), "show detail")
assert show_detail["venue"] == "The Comedy Store"
assert show_detail["job"] is None
print("✓ shows: detail (no job yet)")

patched_show = ok(c.patch(f"/shows/{show_id}", json={"rating": "killed"}), "patch show")
assert patched_show["rating"] == "killed"
print("✓ shows: patch")

# ── Set → Shows cross-reference ───────────────────────────────────────────────
set_shows = ok(c.get(f"/sets/{set_id}/shows"), "set shows")
assert any(x["id"] == show_id for x in set_shows)
print("✓ sets: /sets/:id/shows")

# ── Bit appearances ───────────────────────────────────────────────────────────
appearances = ok(c.get(f"/bits/{bit_id}/appearances"), "appearances")
assert appearances["bit"]["id"] == bit_id
assert len(appearances["versions"]) == 2
print("✓ bits: /appearances")

# ── Patch bit ─────────────────────────────────────────────────────────────────
patched_bit = ok(c.patch(f"/bits/{bit_id}", json={"status": "working"}), "patch bit")
assert patched_bit["status"] == "working"
print("✓ bits: patch")

# ── Soft delete ───────────────────────────────────────────────────────────────
r = c.delete(f"/bits/{bit_id}")
assert r.status_code == 204
bit_check = ok(c.get(f"/bits/{bit_id}"), "bit after delete")
assert bit_check["status"] == "dead"
print("✓ bits: soft delete sets status=dead")

print("\n✅ All tests passed")
