import os, re, json, pathlib
WT = "/home/m0nk/Projects/.sme-v3-corpus-ro/sme/corpora/good-dog-corpus/vault"
out_dir = "/tmp/gd_prose"
fm_re = re.compile(r'^---\s*\n.*?\n---\s*\n', re.DOTALL)
notes = []
for p in sorted(pathlib.Path(WT).rglob("*.md")):
    rel = str(p.relative_to(WT))
    if pathlib.Path(rel).name in ("README.md", "ONTOLOGY.md"):
        continue
    raw = p.read_text(encoding="utf-8")
    # strip leading YAML frontmatter (ground-truth entities:/edges: live here)
    prose = fm_re.sub("", raw, count=1)
    had_fm = prose != raw
    idx = len(notes)
    prose_path = os.path.join(out_dir, f"{idx:02d}.txt")
    pathlib.Path(prose_path).write_text(prose, encoding="utf-8")
    notes.append({"idx": idx, "relative_path": rel, "prose_path": prose_path,
                  "prose_len": len(prose), "had_frontmatter": had_fm})
pathlib.Path("/tmp/gd_prose/index.json").write_text(json.dumps(notes, indent=2))
print(f"notes: {len(notes)}")
print(f"with_frontmatter_stripped: {sum(n['had_frontmatter'] for n in notes)}")
print(f"prose_len min/mean/max: {min(n['prose_len'] for n in notes)}/"
      f"{sum(n['prose_len'] for n in notes)//len(notes)}/{max(n['prose_len'] for n in notes)}")
# leak check: does any prose still contain a frontmatter-style entities:/edges: block?
leak = [n['relative_path'] for n in notes
        if re.search(r'^\s*(entities|edges):\s*$', pathlib.Path(n['prose_path']).read_text(), re.M)]
print(f"potential ground-truth leak in prose: {len(leak)} -> {leak[:5]}")
