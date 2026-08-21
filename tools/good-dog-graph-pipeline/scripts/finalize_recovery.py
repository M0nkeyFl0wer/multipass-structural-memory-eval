import json, re, pathlib, collections
REC="/tmp/claude-1000/-home-m0nk-Projects-multipass-structural-memory-eval/f1df5495-b2d5-4441-a2d0-ec58b3708739/tasks/w9qb1unj0.output"
prose={n["relative_path"]:pathlib.Path(n["prose_path"]).read_text() for n in json.load(open("/tmp/gd_prose/index.json"))}
def norm(s):
    s=s.lower().replace("*","").replace("`","").replace('"',' ').replace("'"," ")
    return re.sub(r"\s+"," ",s).strip()
def grounded(ev,pnorm,mw=6):
    toks=norm(ev).split()
    if len(toks)<mw: return norm(ev) in pnorm and len(norm(ev))>=20
    for i in range(len(toks)):
        if " ".join(toks[i:i+mw]) in pnorm: return True
    return False
META=re.compile(r'`|\b(pub|concept|org|breed|person|event|location)_[a-z0-9_]{3,}|declares a|ground-truth|needs_grounding|this note|the corpus|is bound|paralleling', re.I)
data=json.load(open(REC)); res=data.get("result") or data
if isinstance(res,str): res=json.loads(res)
add={n["relative_path"]:n for n in res["notes"]}
base={}
for line in open("/tmp/gd_extractions.resolved.jsonl"):
    if line.strip(): n=json.loads(line); base[n["relative_path"]]=n
kept=dg=dm=0; kbt=collections.Counter(); out=[]
for rel,note in base.items():
    a=add.get(rel,{}); pnorm=norm(prose.get(rel,""))
    bk={(g["source"],g["type"],g["target"]) for g in note.get("edges",[])}
    new=[]; ep=set()
    for g in a.get("edges",[]):
        k=(g["source"],g["type"],g["target"])
        if k in bk: continue
        ev=g.get("evidence","")
        if META.search(ev): dm+=1; continue
        if not grounded(ev,pnorm): dg+=1; continue
        new.append(g); ep.add(g["source"]); ep.add(g["target"]); kept+=1; kbt[g["type"]]+=1
    ent={e["label"]:e for e in note.get("entities",[])}
    for e in a.get("entities",[]):
        if e["label"] in ep and e["label"] not in ent: ent[e["label"]]=e
    seen=set(); edges=[]
    for g in note.get("edges",[])+new:
        k=(g["source"],g["type"],g["target"])
        if k in seen: continue
        seen.add(k); edges.append(g)
    out.append({"relative_path":rel,"entities":list(ent.values()),"edges":edges})
open("/tmp/gd_extractions.recovered.jsonl","w").write("\n".join(json.dumps(n) for n in out)+"\n")
te=sum(len(n["entities"]) for n in out); tg=sum(len(n["edges"]) for n in out)
print(f"recovered edges KEPT {kept}; dropped {dm} (meta-scaffolding evidence) + {dg} (not in prose)")
print(f"kept by type: {dict(kbt.most_common())}")
print(f"merged totals (pre-build dedup): {te} entity-mentions, {tg} edges (base resolved had 303)")
