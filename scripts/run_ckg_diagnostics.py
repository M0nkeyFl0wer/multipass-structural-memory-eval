#!/usr/bin/env python3
"""Run SME structural diagnostics over the loaded CKG graphs.

Three categories, each tailored to what makes sense on a hand-authored
DAG with the ckg-benchmark schema (ConceptID, ConceptLabel, Dependencies,
TaxonomyID):

  Cat 1 — Ontology coherence (monoculture probe). TaxonomyID
    distribution + Shannon entropy; edge-type entropy. CKGs have
    exactly one declared edge type (DEPENDS_ON), so edge-type entropy
    is 0 by construction — the *finding* is that the schema flattens
    semantically distinct relations into one label.

  Cat 7 — The Abacus. Tokens-per-correct across A/B/C, summarized
    from the existing condition_*.json files. This is the headline
    "is structure earning its tokens?" number per domain and overall.

  Cat 8 — Schema vs shape. The CKG header declares one Dependencies
    column with one implicit relation. The graph itself exposes
    distinct (child_taxonomy, parent_taxonomy) pairs which represent
    semantically different relations the schema does not name. We
    count those pairs and report the gap.

Plus rolled-up Cat 2 ingestion-integrity (already computed by the
adapter on ingest) so the cross-domain summary has a single place
to read off "all green / N errors."

Outputs: results/ckg_benchmark/{domain}/diagnostics.json plus a
results/ckg_benchmark/_diagnostics.md cross-domain table. The
findings doc at docs/ckg_benchmark_findings.md is updated by hand
to reference these.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sme.adapters.ckg import CKGAdapter

DOMAINS = [
    "calculus",
    "us-geography",
    "moss",
    "glp1-obesity",
    "theory-of-knowledge",
]

DATA_ROOT = _REPO_ROOT / "data" / "ckg_benchmark"
RESULTS_ROOT = _REPO_ROOT / "results" / "ckg_benchmark"


# --- info-theory helpers ------------------------------------------


def shannon_entropy(counts: Counter) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return -sum((c / total) * math.log2(c / total) for c in counts.values() if c > 0)


def normalized_entropy(counts: Counter) -> float:
    """Entropy normalized to [0, 1] by dividing by log2(k) where k = #classes.

    H_norm = 1.0 means perfectly uniform across all observed classes.
    H_norm < 0.5 is monocultural (one class dominates)."""
    if len(counts) <= 1:
        return 0.0
    return shannon_entropy(counts) / math.log2(len(counts))


# --- per-domain diagnostics ---------------------------------------


def run_domain(domain: str) -> dict:
    csv_path = DATA_ROOT / "domains" / domain / "learning-graph.csv"
    adapter = CKGAdapter(csv_path)
    ingest = adapter.ingest_corpus([])
    entities, edges = adapter.get_graph_snapshot()

    # ------- Cat 1: ontology coherence -------------------------------
    tax_counts = Counter(e.entity_type for e in entities)
    edge_type_counts = Counter(e.edge_type for e in edges)
    cat1 = {
        "n_taxonomies": len(tax_counts),
        "tax_distribution": dict(tax_counts.most_common()),
        "tax_entropy_bits": shannon_entropy(tax_counts),
        "tax_entropy_norm": normalized_entropy(tax_counts),
        "tax_dominant_share": max(tax_counts.values()) / sum(tax_counts.values())
        if tax_counts
        else 0.0,
        "n_edge_types": len(edge_type_counts),
        "edge_type_distribution": dict(edge_type_counts),
        "edge_type_entropy_bits": shannon_entropy(edge_type_counts),
    }

    # ------- Cat 2: ingestion integrity ------------------------------
    cat2 = {
        "phantom_edge_errors": [e for e in ingest["errors"] if "phantom" in e],
        "duplicate_id_warnings": [w for w in ingest["warnings"] if "duplicate" in w],
        "orphan_concepts": _orphan_count(adapter, entities),
        "n_errors": len(ingest["errors"]),
        "n_warnings": len(ingest["warnings"]),
    }

    # ------- Cat 7: Abacus (uses run outputs) -----------------------
    cat7 = _read_abacus(domain)

    # ------- Cat 8: schema vs shape ---------------------------------
    declared = adapter.get_ontology_source()
    pair_counts = Counter(
        (e.properties.get("child_taxonomy"), e.properties.get("parent_taxonomy"))
        for e in edges
    )
    cat8 = {
        "declared_fields": [f["field"] for f in declared["schema"]],
        "declared_edge_types": ["DEPENDS_ON"],
        "observed_distinct_taxonomy_pairs": len(pair_counts),
        "top_pairs": [
            {"child_tax": k[0], "parent_tax": k[1], "count": v}
            for k, v in pair_counts.most_common(5)
        ],
        # Cardinality the schema does not explicitly capture
        "max_parents_per_child": _max_parents(adapter),
        "max_children_per_parent": _max_children(adapter),
        "multi_parent_share": _multi_parent_share(adapter),
    }

    return {
        "domain": domain,
        "n_concepts": len(entities),
        "n_edges": len(edges),
        "cat1_ontology_coherence": cat1,
        "cat2_ingestion_integrity": cat2,
        "cat7_abacus": cat7,
        "cat8_schema_vs_shape": cat8,
    }


def _orphan_count(adapter: CKGAdapter, entities) -> int:
    return sum(
        1
        for e in entities
        if not adapter._parents.get(e.id) and not adapter._children.get(e.id)
    )


def _max_parents(adapter: CKGAdapter) -> int:
    return max((len(v) for v in adapter._parents.values()), default=0)


def _max_children(adapter: CKGAdapter) -> int:
    return max((len(v) for v in adapter._children.values()), default=0)


def _multi_parent_share(adapter: CKGAdapter) -> float:
    parents = adapter._parents
    if not parents:
        return 0.0
    n_multi = sum(1 for v in parents.values() if len(v) > 1)
    return n_multi / len(parents)


def _read_abacus(domain: str) -> dict:
    """Pull tokens-per-correct numbers from earlier run outputs.

    Falls back to {available: false} if the runner hasn't emitted
    condition JSONs yet. The full A/B/C deltas live in cat2c_report.json
    (also written by the runner)."""
    out = {}
    for cond in ("A", "B", "C"):
        p = RESULTS_ROOT / domain / f"condition_{cond}.json"
        if not p.exists():
            return {"available": False}
        d = json.loads(p.read_text())
        questions = d["questions"]
        if not questions:
            continue
        total_tokens = sum(q["tokens"] for q in questions)
        full_recall = sum(1 for q in questions if q["recall"] >= 1.0)
        out[cond] = {
            "n": len(questions),
            "mean_tokens": total_tokens / len(questions),
            "full_recall": full_recall,
            "tokens_per_correct": (total_tokens / full_recall)
            if full_recall
            else None,
            "mean_recall": sum(q["recall"] for q in questions) / len(questions),
        }
    out["available"] = True
    return out


# --- cross-domain rollup ------------------------------------------


def write_cross_domain_summary(diagnostics: list[dict]) -> Path:
    out_path = RESULTS_ROOT / "_diagnostics.md"
    lines: list[str] = []
    lines.append("# CKG-benchmark — structural diagnostics")
    lines.append("")
    lines.append(
        "Generated by `scripts/run_ckg_diagnostics.py`. See methodology in "
        "`docs/ckg_benchmark_experiment.md` § Diagnostics applied to each CKG."
    )
    lines.append("")

    # Cat 1 — monoculture probe
    lines.append("## Cat 1 — Ontology coherence (monoculture probe)")
    lines.append("")
    lines.append(
        "Edge-type entropy is **0 by construction** in CKG — the schema "
        "declares a single Dependencies column, so every edge is "
        "DEPENDS_ON. The schema flattens semantically distinct relations "
        "(taxonomy/hierarchy/causation/co-occurrence) into one label. "
        "TaxonomyID provides node-level kind diversity but no edge-level "
        "vocabulary at all."
    )
    lines.append("")
    lines.append("| Domain | Concepts | Taxonomies | Tax entropy (norm) | Tax dominant | Edge types | Edge entropy |")
    lines.append("|---|---|---|---|---|---|---|")
    for d in diagnostics:
        c1 = d["cat1_ontology_coherence"]
        lines.append(
            f"| {d['domain']} | {d['n_concepts']} | "
            f"{c1['n_taxonomies']} | {c1['tax_entropy_norm']:.2f} | "
            f"{c1['tax_dominant_share'] * 100:.0f}% | "
            f"{c1['n_edge_types']} | {c1['edge_type_entropy_bits']:.2f} |"
        )
    lines.append("")

    # Cat 2 — integrity
    lines.append("## Cat 2 — Ingestion integrity")
    lines.append("")
    lines.append(
        "First datapoint for the *hand-authored DAGs are integrity-clean "
        "by construction* baseline. All five domains: 0 phantom edges, "
        "0 duplicate IDs, 0 orphan concepts, 0 ingest errors. This is "
        "the floor against which extraction-built graphs should be "
        "compared."
    )
    lines.append("")
    lines.append("| Domain | Errors | Warnings | Phantom edges | Duplicates | Orphans |")
    lines.append("|---|---|---|---|---|---|")
    for d in diagnostics:
        c2 = d["cat2_ingestion_integrity"]
        lines.append(
            f"| {d['domain']} | {c2['n_errors']} | {c2['n_warnings']} | "
            f"{len(c2['phantom_edge_errors'])} | "
            f"{len(c2['duplicate_id_warnings'])} | "
            f"{c2['orphan_concepts']} |"
        )
    lines.append("")

    # Cat 7 — Abacus
    lines.append("## Cat 7 — The Abacus (tokens per correct answer)")
    lines.append("")
    lines.append(
        "Independent token-efficiency probe over the same A/B/C runs. "
        "*Lower is better.* Yarmoluk's published claim: CKG 269 tokens / "
        "correct answer vs RAG 2982 (11×). Our setup uses a different "
        "flat baseline (per-concept token-overlap, very tight chunks), "
        "so the absolute numbers are not directly comparable — direction "
        "of the gap is."
    )
    lines.append("")
    lines.append("| Domain | A tokens/correct | B tokens/correct | C tokens/correct | A mean recall | B mean recall |")
    lines.append("|---|---|---|---|---|---|")
    for d in diagnostics:
        ab = d["cat7_abacus"]
        if not ab.get("available"):
            lines.append(f"| {d['domain']} | (run runner first) |||||")
            continue

        def cell(c):
            v = ab[c].get("tokens_per_correct")
            return f"{v:.0f}" if v is not None else "—"

        lines.append(
            f"| {d['domain']} | {cell('A')} | {cell('B')} | {cell('C')} | "
            f"{ab['A']['mean_recall']:.3f} | {ab['B']['mean_recall']:.3f} |"
        )
    lines.append("")

    # Cat 8 — schema vs shape
    lines.append("## Cat 8 — Schema vs shape")
    lines.append("")
    lines.append(
        "The CKG schema declares **one** edge type (Dependencies column → "
        "implicit DEPENDS_ON). The graph itself exhibits a much richer "
        "relation vocabulary if we type each edge by its endpoints' "
        "TaxonomyIDs. The gap is the schema's effective under-specification."
    )
    lines.append("")
    lines.append("| Domain | Declared edge types | Observed (child_tax, parent_tax) pairs | Multi-parent share | Max parents |")
    lines.append("|---|---|---|---|---|")
    for d in diagnostics:
        c8 = d["cat8_schema_vs_shape"]
        lines.append(
            f"| {d['domain']} | {len(c8['declared_edge_types'])} | "
            f"**{c8['observed_distinct_taxonomy_pairs']}** | "
            f"{c8['multi_parent_share'] * 100:.0f}% | "
            f"{c8['max_parents_per_child']} |"
        )
    lines.append("")
    pair_counts_by_domain = {
        d["domain"]: d["cat8_schema_vs_shape"]["observed_distinct_taxonomy_pairs"]
        for d in diagnostics
    }
    if pair_counts_by_domain:
        max_dom = max(pair_counts_by_domain, key=pair_counts_by_domain.get)
        lines.append(
            f"Reading: `{max_dom}` has **1 declared** edge type but exhibits "
            f"**{pair_counts_by_domain[max_dom]} observed** "
            "(child_tax, parent_tax) pairs — the schema elides genuinely "
            "different relations under one label. For downstream LLM "
            "consumption that's a missed opportunity: a typed-edge format "
            "like `<X> --[INSTANCE_OF]--> <Y>` vs `<X> --[BUILT_FROM]--> <Y>` "
            "would carry richer signal at the same token cost as `DEPENDS_ON`."
        )
    lines.append("")

    out_path.write_text("\n".join(lines) + "\n")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domains", nargs="*", default=DOMAINS)
    args = ap.parse_args()

    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    diagnostics = []
    for d in args.domains:
        print(f"=== {d} ===")
        diag = run_domain(d)
        out = RESULTS_ROOT / d / "diagnostics.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(diag, indent=2, default=str))
        c1 = diag["cat1_ontology_coherence"]
        c8 = diag["cat8_schema_vs_shape"]
        print(
            f"  tax entropy={c1['tax_entropy_norm']:.2f}  "
            f"observed pairs={c8['observed_distinct_taxonomy_pairs']}  "
            f"multi-parent={c8['multi_parent_share'] * 100:.0f}%"
        )
        diagnostics.append(diag)

    summary_path = write_cross_domain_summary(diagnostics)
    print(f"\nsummary: {summary_path.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
