import json, collections, os
ents = collections.defaultdict(lambda: {"count":0,"desc":""})
by_type = collections.defaultdict(dict)
for line in open("/tmp/gd_extractions.jsonl"):
    n=json.loads(line)
    for e in n.get("entities",[]):
        lbl=e["label"]; t=e.get("type","concept")
        d=by_type[t].setdefault(lbl,{"label":lbl,"count":0,"desc":""})
        d["count"]+=1
        if not d["desc"] and e.get("description"): d["desc"]=e["description"]
os.makedirs("/tmp/gd_resolve",exist_ok=True)
index=[]
for t,labels in by_type.items():
    items=sorted(labels.values(), key=lambda x:-x["count"])
    p=f"/tmp/gd_resolve/{t}.json"
    json.dump(items, open(p,"w"), indent=1)
    index.append({"type":t,"path":p,"n":len(items)})
index.sort(key=lambda x:-x["n"])
json.dump(index, open("/tmp/gd_resolve/index.json","w"), indent=1)
for r in index: print(f"  {r['type']:14s} {r['n']:4d} distinct labels -> {r['path']}")
print("total distinct:", sum(r['n'] for r in index))
