#!/usr/bin/env python3
"""
Rebuild the good-dog graph from SUBAGENT-extracted triplets.

Instead of calling Ollama for edge extraction, this driver feeds
pre-computed subagent triplets (one JSONL line per note) into the
EXISTING second-brain ingest pipeline by monkeypatching the module-level
`extract_triplets_from_text`. Everything downstream — id resolution,
canonicalize, dedup, --force full-reset bulk load, local nomic embeddings,
HNSW rebuild — is the stock, graph-sins-safe reconstruct path.

Usage:
  python /tmp/ingest_subagent.py \
    --repo /home/m0nk/Projects/second-brain-hybrid-graph \
    --vault    /home/m0nk/Projects/.sme-v3-corpus-ro/sme/corpora/good-dog-corpus/vault \
    --ontology /home/m0nk/Projects/.sme-v3-corpus-ro/sme/corpora/good-dog-corpus/ontology.yaml \
    --extractions /tmp/gd_extractions.jsonl
"""
import argparse
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--vault", required=True)
    ap.add_argument("--ontology", required=True)
    ap.add_argument("--extractions", required=True)
    ap.add_argument("--graph-out", default=None, help="override config.GRAPH_DIR (isolate build)")
    ap.add_argument("--chunk-out", default=None, help="override config.CHUNK_STORE_PATH")
    args = ap.parse_args()

    # Run from the repo root so `sys.path.insert(0, ".")` + second_brain imports work.
    os.chdir(args.repo)
    sys.path.insert(0, args.repo)

    if args.graph_out or args.chunk_out:
        from pathlib import Path
        from second_brain import config as _cfg
        if args.graph_out:
            _cfg.GRAPH_DIR = Path(args.graph_out)
        if args.chunk_out:
            _cfg.CHUNK_STORE_PATH = Path(args.chunk_out)
        print(f"Build paths overridden: graph={_cfg.GRAPH_DIR} chunks={_cfg.CHUNK_STORE_PATH}")

    # --- load subagent extractions, keyed by relative_path -----------------
    # JSONL line shape (workflow output):
    #   {"relative_path": "...", "entities": [{label,type,description,confidence}],
    #                            "edges": [{source,target,type,evidence,confidence}]}
    rel_to_raw = {}
    n_lines = n_ent = n_edge = 0
    with open(args.extractions) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rel = rec["relative_path"]
            # Transform entity shape -> the RAW shape extract_from_text expects:
            #   {"label","type","meta":{"description":...},"confidence"}
            ents = []
            for e in rec.get("entities", []):
                if not (e.get("label") or "").strip():
                    continue
                ents.append({
                    "label": e["label"],
                    "type": e.get("type", "concept"),
                    "meta": {"description": e.get("description", "")},
                    "confidence": float(e.get("confidence", 0.7)),
                })
            edges = []
            for g in rec.get("edges", []):
                if not (g.get("source") or "").strip() or not (g.get("target") or "").strip():
                    continue
                edges.append({
                    "source": g["source"],
                    "target": g["target"],
                    "type": g.get("type", "mentions"),
                    "evidence": g.get("evidence", ""),
                    "confidence": float(g.get("confidence", 0.7)),
                })
            rel_to_raw[rel] = {"entities": ents, "edges": edges}
            n_lines += 1
            n_ent += len(ents)
            n_edge += len(edges)
    print(f"Loaded extractions: {n_lines} notes, {n_ent} raw entities, {n_edge} raw edges")

    # --- map note body -> raw (extract_from_text is called with note['body']) ---
    from second_brain.obsidian import scan_vault
    notes = scan_vault(args.vault)
    body_to_raw = {}
    matched = 0
    for note in notes:
        raw = rel_to_raw.get(note["relative_path"])
        if raw is not None:
            body_to_raw[note["body"]] = raw
            matched += 1
    print(f"scan_vault: {len(notes)} notes; matched to extractions: {matched}")
    missing = [n["relative_path"] for n in notes if n["relative_path"] not in rel_to_raw]
    if missing:
        print(f"  WARN: {len(missing)} notes have no extraction (will be entity-less): {missing[:5]}")

    # --- monkeypatch the ollama extraction call ----------------------------
    import second_brain.extract as extract_mod

    def _subagent_extract(text, edge_types, model=None, host=None, node_types=None, **kw):
        return body_to_raw.get(text, {"entities": [], "edges": []})

    extract_mod.extract_triplets_from_text = _subagent_extract
    print("Patched second_brain.extract.extract_triplets_from_text -> subagent triplets")

    # --- run the stock ingest (force full-reset reconstruct) ---------------
    import scripts.ingest_obsidian as ingest
    sys.argv = [
        "ingest_obsidian.py",
        "--vault", args.vault,
        "--ontology", args.ontology,
        "--force",
        "--workers", "1",
    ]
    ingest.main()


if __name__ == "__main__":
    main()
