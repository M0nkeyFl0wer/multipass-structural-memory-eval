#!/usr/bin/env python3
"""Apply Stage-8 resolution clusters to the raw extractions JSONL.

Relabels entity/edge labels to their canonical form (reversible: reads raw,
writes a new resolved JSONL), dedups within-note entities, and reports.
"""
import json, sys, argparse, collections

ap = argparse.ArgumentParser()
ap.add_argument("--clusters", required=True, help="workflow output JSON")
ap.add_argument("--raw", default="/tmp/gd_extractions.raw.jsonl")
ap.add_argument("--out", default="/tmp/gd_extractions.resolved.jsonl")
a = ap.parse_args()

data = json.load(open(a.clusters))
res = data.get("result") or data
if isinstance(res, str):
    res = json.loads(res)
clusters = res["clusters"]
print(f"clusters: {len(clusters)} (stats: {res.get('stats')})")

# build member -> canonical map; detect collisions
m2c = {}
collisions = []
for c in clusters:
    canon = c["canonical"]
    for mem in c["members"]:
        if mem in m2c and m2c[mem] != canon:
            collisions.append((mem, m2c[mem], canon))
        m2c[mem] = canon
# never map a label to itself-erasing: ensure canonical maps to itself
for c in clusters:
    m2c.setdefault(c["canonical"], c["canonical"])
if collisions:
    print(f"  WARN {len(collisions)} label->multiple-canonical collisions (kept last): {collisions[:5]}")
print(f"  member labels that will be folded: {sum(1 for k,v in m2c.items() if k!=v)}")

def canon(lbl):
    return m2c.get(lbl, lbl)

n_relabel = 0
distinct_before, distinct_after = set(), set()
out_lines = []
for line in open(a.raw):
    line = line.strip()
    if not line:
        continue
    note = json.loads(line)
    # entities: relabel + dedup within note (prefer longest description)
    merged = {}
    for e in note.get("entities", []):
        distinct_before.add(e["label"])
        new = canon(e["label"])
        if new != e["label"]:
            n_relabel += 1
        distinct_after.add(new)
        e2 = dict(e); e2["label"] = new
        cur = merged.get(new)
        if cur is None or len(e2.get("description", "")) > len(cur.get("description", "")):
            merged[new] = e2
    note["entities"] = list(merged.values())
    # edges: relabel endpoints
    for g in note.get("edges", []):
        g["source"] = canon(g["source"])
        g["target"] = canon(g["target"])
    out_lines.append(json.dumps(note))

open(a.out, "w").write("\n".join(out_lines) + "\n")
print(f"  entity-mention relabels applied: {n_relabel}")
print(f"  distinct entity labels: {len(distinct_before)} -> {len(distinct_after)}")
print(f"wrote {a.out}")
