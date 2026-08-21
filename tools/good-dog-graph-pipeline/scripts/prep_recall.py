import re, json, pathlib, yaml, collections
WT="/home/m0nk/Projects/.sme-v3-corpus-ro/sme/corpora/good-dog-corpus/vault"
fm=re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)

# 1) global id -> {canonical, aliases, type}
idmap={}
note_meta={}  # relative_path -> meta
for p in sorted(pathlib.Path(WT).rglob("*.md")):
    if p.name in ("README.md","ONTOLOGY.md"): continue
    m=fm.match(p.read_text())
    if not m: continue
    meta=yaml.safe_load(m.group(1)) or {}
    rel=str(p.relative_to(WT)); note_meta[rel]=meta
    for e in (meta.get("entities") or []):
        if e.get("id"):
            idmap[e["id"]]={"canonical":e.get("canonical",e["id"]),
                            "aliases":e.get("aliases") or [], "type":e.get("type","")}
def lbl(i):
    d=idmap.get(i)
    return d["canonical"] if d else i
def al(i):
    d=idmap.get(i)
    return d["aliases"] if d else []

# 2) our extracted edges per note + global pool
our=collections.defaultdict(list); pool=[]
for line in open("/tmp/gd_extractions.resolved.jsonl"):
    n=json.loads(line); rel=n["relative_path"]
    for g in n.get("edges",[]):
        e=(g["source"],g["type"],g["target"])
        our[rel].append(e); pool.append(e)
poolstr="\n".join(f"{s} --{t}--> {d}" for s,t,d in sorted(set(pool)))
pathlib.Path("/tmp/gd_recall/all_extracted_edges.txt").write_text(poolstr)

# 3) per-note matcher inputs
index=[]; gt_total=0
for rel,meta in note_meta.items():
    ge=[]
    for e in (meta.get("edges") or []):
        f,t,ty=e.get("from"),e.get("to"),e.get("type")
        if not (f and t and ty): continue
        ge.append({"from":lbl(f),"from_aliases":al(f),"type":ty,
                   "to":lbl(t),"to_aliases":al(t)})
    if not ge: continue
    gt_total+=len(ge)
    i=len(index)
    rec={"relative_path":rel,"gt_edges":ge,
         "our_edges":[{"source":s,"type":t,"target":d} for s,t,d in our.get(rel,[])]}
    pp=f"/tmp/gd_recall/{i:02d}.json"
    pathlib.Path(pp).write_text(json.dumps(rec,indent=1))
    index.append({"idx":i,"relative_path":rel,"path":pp,"n_gt":len(ge)})
json.dump(index, open("/tmp/gd_recall/index.json","w"))
print(f"notes with GT edges: {len(index)}; total GT edges: {gt_total}")
print(f"global extracted-edge pool (distinct): {len(set(pool))}")
print(json.dumps(index[:3],indent=1))
