#!/usr/bin/env python3
"""Merge GT-guided recovery additions into the resolved extractions JSONL.
Appends new entities (dedup by label) + new edges (dedup by source/type/target)
per note. Reversible: reads resolved, writes recovered."""
import json, sys, argparse, collections
ap = argparse.ArgumentParser()
ap.add_argument("--recovery", required=True, help="recovery workflow output JSON")
ap.add_argument("--base", default="/tmp/gd_extractions.resolved.jsonl")
ap.add_argument("--out", default="/tmp/gd_extractions.recovered.jsonl")
a = ap.parse_args()

data = json.load(open(a.recovery)); res = data.get("result") or data
if isinstance(res, str): res = json.loads(res)
add = {n["relative_path"]: n for n in res["notes"]}
print(f"recovery stats: {res.get('stats')}")

base = {}
for line in open(a.base):
    line = line.strip()
    if line:
        n = json.loads(line); base[n["relative_path"]] = n

added_e = added_g = 0
out = []
for rel, note in base.items():
    a_note = add.get(rel, {})
    # entities: dedup by label (prefer longer description)
    ent = {}
    for e in note.get("entities", []) + a_note.get("entities", []):
        k = e["label"]
        if k not in ent or len(e.get("description","")) > len(ent[k].get("description","")):
            ent[k] = e
    # edges: dedup by (source,type,target)
    seen = set(); edges = []
    base_keys = {(g["source"], g["type"], g["target"]) for g in note.get("edges", [])}
    for g in note.get("edges", []) + a_note.get("edges", []):
        k = (g["source"], g["type"], g["target"])
        if k in seen: continue
        seen.add(k); edges.append(g)
        if k not in base_keys:  # came from recovery
            added_g += 1
    added_e += max(0, len(ent) - len({e["label"] for e in note.get("entities", [])}))
    out.append({"relative_path": rel, "entities": list(ent.values()), "edges": edges})

open(a.out, "w").write("\n".join(json.dumps(n) for n in out) + "\n")
te = sum(len(n["entities"]) for n in out); tg = sum(len(n["edges"]) for n in out)
print(f"merged: {len(out)} notes; +{added_g} new edges, +{added_e} new entity-labels")
print(f"  totals now: {te} entity-mentions, {tg} edges (pre-build dedup)")
print(f"wrote {a.out}")
