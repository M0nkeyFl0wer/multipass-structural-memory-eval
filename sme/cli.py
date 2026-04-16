"""SME command-line interface.

First pass: a single `analyze` subcommand that loads a graph from an
adapter and prints a structural report. This is the smoke test for
the adapter + topology layer. Full `run`, `compare`, `calibrate`, etc
come later when the category scoring is implemented.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from sme.adapters.base import SMEAdapter
from sme.topology import TopologyAnalyzer

log = logging.getLogger("sme")


def _load_adapter(name: str, **kwargs) -> SMEAdapter:
    name = name.lower()
    # Drop Nones so adapter defaults kick in
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    if name == "ladybugdb" or name == "ladybug":
        from sme.adapters.ladybugdb import LadybugDBAdapter

        return LadybugDBAdapter(**kwargs)

    if name == "mempalace":
        from sme.adapters.mempalace import MemPalaceAdapter

        # LadybugDB-specific kwargs are silently ignored for other adapters
        for k in (
            "include_node_tables",
            "include_edge_tables",
            "auto_discover",
            "api_url",
            "default_query_mode",
        ):
            kwargs.pop(k, None)
        return MemPalaceAdapter(**kwargs)

    if name == "flat" or name == "flat_baseline":
        from sme.adapters.flat_baseline import FlatBaselineAdapter

        for k in (
            "include_node_tables",
            "include_edge_tables",
            "auto_discover",
            "kg_path",
            "api_url",
            "default_query_mode",
        ):
            kwargs.pop(k, None)
        return FlatBaselineAdapter(**kwargs)

    raise SystemExit(f"unknown adapter: {name}")


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def _print_report(
    health: dict,
    community: Any,
    edge_type_components: dict[str, int],
    ontology: dict,
    elapsed: dict[str, float],
    betti: Any = None,
) -> None:
    print()
    print("=" * 70)
    print(" Structural Memory Evaluation — structural analysis")
    print("=" * 70)

    print(f"\nGraph size")
    print(f"  nodes:                {_fmt_int(health['nodes'])}")
    print(f"  edges:                {_fmt_int(health['edges'])}")
    print(f"  components:           {_fmt_int(health['components'])}")
    print(
        f"  largest component:    {_fmt_int(health['largest_component_size'])}"
        f"  ({health['largest_component_ratio']*100:.1f}% of nodes)"
    )
    print(f"  isolated nodes:       {_fmt_int(health['isolated_nodes'])}")
    print(f"  avg degree:           {health['avg_degree']:.2f}")
    print(f"  max degree:           {_fmt_int(health['max_degree'])}")

    print(f"\nEntity type distribution")
    for et, c in list(health["entity_type_distribution"].items())[:15]:
        print(f"  {et:35s} {c:>8,}")

    print(f"\nEdge type distribution")
    total_edges = sum(health["edge_type_distribution"].values()) or 1
    for et, c in health["edge_type_distribution"].items():
        pct = 100 * c / total_edges
        print(f"  {et:35s} {c:>8,}   ({pct:5.1f}%)")
    print(f"\n  edge type entropy:    {health['edge_type_entropy_bits']:.2f} bits")
    print(
        "                        (higher = more diverse vocabulary; "
        "low bits indicate monoculture)"
    )

    print(f"\nCommunity structure (Louvain)")
    print(f"  communities:          {_fmt_int(community.count)}")
    print(f"  modularity:           {community.modularity:.3f}")
    print(
        f"  inter-community:      {_fmt_int(community.inter_community_edges)} edges  "
        f"({community.inter_community_ratio*100:.1f}%)"
    )
    print(f"  top sizes:            {community.sizes[:10]}")

    print(f"\nPer-edge-type component count  (Cat 4c monoculture signal)")
    for et, n_comp in sorted(
        edge_type_components.items(), key=lambda kv: -kv[1]
    )[:15]:
        print(f"  {et:35s} {n_comp:>8,}  components")

    if betti is not None:
        print(f"\nPersistent homology  (Cat 5 gap detection)")
        print(
            f"  component size:       {_fmt_int(betti.component_size)} nodes"
            f"  (largest connected component)"
        )
        if betti.skipped:
            print(f"  SKIPPED: {betti.skip_reason}")
        else:
            print(
                f"  Betti-0:              {betti.betti_0}"
                "   (should be 1 for a single component)"
            )
            print(
                f"  Betti-1:              {betti.betti_1}"
                "   (structural loops / holes)"
            )
            if betti.h1_bars:
                print(f"  max H1 persistence:   {betti.max_h1_persistence:.2f} hops")
                print(f"  top H1 bars (birth, death, persistence):")
                for b, d, p in betti.h1_bars[:10]:
                    print(
                        f"    birth={b:5.2f}  death={d:5.2f}  persistence={p:5.2f}"
                    )
            else:
                print("  no H1 features found — graph is acyclic / tree-like")

    if ontology.get("schema") or ontology.get("documentation"):
        print(f"\nDeclared ontology (source: {ontology.get('type', '?')})")
        for entry in ontology.get("schema") or []:
            kind = entry.get("kind", "?")
            # Known LadybugDB shapes
            if kind == "node":
                print(f"  node tables:          {', '.join(entry['tables'])}")
            elif kind == "rel":
                print(f"  rel tables:           {', '.join(entry['tables'])}")
            elif kind == "entity_edge_types":
                print(
                    "  entity_type vocab:    "
                    + (", ".join(entry["values"]) or "<none>")
                )
            else:
                # Generic shape: print whatever list-valued keys are there
                for key, val in entry.items():
                    if key == "kind":
                        continue
                    if isinstance(val, list):
                        print(f"  {kind}.{key}:".ljust(24) + ", ".join(str(v) for v in val))
                    else:
                        print(f"  {kind}.{key}:".ljust(24) + str(val))

        doc = ontology.get("documentation")
        if doc:
            # Wrap to 66 cols under a "documentation:" label
            import textwrap
            print("  documentation:")
            for line in textwrap.wrap(doc, width=66):
                print(f"    {line}")

    print(f"\nTiming")
    for step, t in elapsed.items():
        print(f"  {step:20s} {t:>7.2f}s")
    print()


def cmd_analyze(args: argparse.Namespace) -> int:
    elapsed: dict[str, float] = {}

    adapter_kwargs: dict[str, Any] = {
        "db_path": args.db,
        "read_only": True,
        "auto_discover": args.auto_discover,
    }
    if args.node_tables:
        adapter_kwargs["include_node_tables"] = args.node_tables
    if args.edge_tables:
        adapter_kwargs["include_edge_tables"] = args.edge_tables
    if args.kg_path:
        adapter_kwargs["kg_path"] = args.kg_path
    if args.collection_name:
        adapter_kwargs["collection_name"] = args.collection_name

    t0 = time.time()
    adapter = _load_adapter(args.adapter, **adapter_kwargs)
    elapsed["open"] = time.time() - t0

    t0 = time.time()
    entities, edges = adapter.get_graph_snapshot()
    elapsed["snapshot"] = time.time() - t0
    log.info("snapshot: %d entities, %d edges", len(entities), len(edges))

    t0 = time.time()
    topo = TopologyAnalyzer(entities, edges)
    health = topo.structural_health()
    elapsed["structural_health"] = time.time() - t0

    t0 = time.time()
    community = topo.community_structure()
    elapsed["community_louvain"] = time.time() - t0

    t0 = time.time()
    etc = topo.edge_type_components()
    elapsed["edge_type_components"] = time.time() - t0

    betti = None
    if args.betti:
        t0 = time.time()
        try:
            betti = topo.betti_numbers(
                component="largest",
                max_dim=1,
                max_nodes=args.betti_max_nodes,
                subsample=args.betti_subsample,
            )
            elapsed["betti_numbers"] = time.time() - t0
        except ImportError:
            log.warning("ripser not installed — skipping Betti numbers")
            elapsed["betti_numbers"] = time.time() - t0

    t0 = time.time()
    ontology = adapter.get_ontology_source()
    elapsed["ontology_source"] = time.time() - t0

    _print_report(health, community, etc, ontology, elapsed, betti=betti)

    if args.json:
        out = {
            "health": health,
            "community": {
                "count": community.count,
                "modularity": community.modularity,
                "sizes": community.sizes,
                "inter_community_edges": community.inter_community_edges,
                "inter_community_ratio": community.inter_community_ratio,
            },
            "edge_type_components": etc,
            "ontology": ontology,
            "elapsed_seconds": elapsed,
        }
        if betti is not None:
            out["betti"] = {
                "component_size": betti.component_size,
                "betti_0": betti.betti_0,
                "betti_1": betti.betti_1,
                "max_h1_persistence": betti.max_h1_persistence,
                "h1_bars": betti.h1_bars[:50],
            }
        Path(args.json).write_text(json.dumps(out, indent=2, default=str))
        print(f"JSON report written to {args.json}")

    adapter.close()
    return 0


def cmd_cat8(args: argparse.Namespace) -> int:
    """Run Category 8 ontology coherence against a system."""
    import textwrap

    from sme.categories.ontology_coherence import (
        ImpliedOntology,
        load_claim_library,
        score_cat8,
    )
    from sme.topology import TopologyAnalyzer

    # Load implied ontology
    implied = ImpliedOntology.load(args.implied_ontology)

    # Load adapter and pull snapshot
    adapter_kwargs: dict[str, Any] = {"db_path": args.db, "read_only": True}
    if args.collection_name:
        adapter_kwargs["collection_name"] = args.collection_name
    if args.kg_path:
        adapter_kwargs["kg_path"] = args.kg_path
    adapter = _load_adapter(args.adapter, **adapter_kwargs)
    entities, edges = adapter.get_graph_snapshot()

    # Structural health (needed for entropy / concentration)
    topo = TopologyAnalyzer(entities, edges)
    health = topo.structural_health()

    # Optional cross-category evidence
    cat7 = None
    if args.cat7_flat or args.cat7_graph:
        cat7 = {}
        if args.cat7_flat:
            with open(args.cat7_flat) as f:
                d = json.load(f)
            cat7["flat_mean_recall"] = d.get("summary", {}).get("mean_recall")
        if args.cat7_graph:
            with open(args.cat7_graph) as f:
                d = json.load(f)
            cat7["graph_mean_recall"] = d.get("summary", {}).get("mean_recall")

    library = load_claim_library()
    report = score_cat8(
        implied,
        entities,
        edges,
        health,
        cat7_results=cat7,
        claim_library=library,
    )

    # Render
    print()
    print("=" * 78)
    print(f" Category 8: Ontology Coherence — {args.adapter} ({args.db})")
    print("=" * 78)
    print(f"\nImplied ontology source: {implied.source}")
    print(f"  version:                {implied.version}")
    print(f"  entity types declared:  {', '.join(implied.entity_types) or '(none)'}")
    print(f"  edge types declared:    {', '.join(implied.edge_types) or '(none)'}")
    print(f"  structural claims:      {len(implied.structural_claims)}")
    print(f"  vocabulary claims:      {len(implied.vocabulary_claims)}")
    print(f"  retrieval claims:       {len(implied.retrieval_claims)}")

    print(f"\n8a Type coverage")
    print(f"   declared:   {len(report.types_declared)}")
    print(f"   found:      {len(report.types_found)}  ({', '.join(report.types_found) or '—'})")
    print(f"   missing:    {len(report.types_missing)}  ({', '.join(report.types_missing) or '—'})")
    if report.types_undeclared:
        print(f"   undeclared: {len(report.types_undeclared)}  (in graph but not in ontology)")
        for t in report.types_undeclared[:10]:
            print(f"     - {t}")
    print(f"   coverage:   {report.type_coverage:.1%}")

    print(f"\n8b Edge vocabulary")
    print(f"   declared:   {len(report.edges_declared)}")
    print(f"   found:      {len(report.edges_found)}  ({', '.join(report.edges_found) or '—'})")
    print(f"   missing:    {len(report.edges_missing)}  ({', '.join(report.edges_missing) or '—'})")
    if report.edges_undeclared:
        print(f"   undeclared: {len(report.edges_undeclared)}  ({', '.join(report.edges_undeclared[:8])}{'...' if len(report.edges_undeclared) > 8 else ''})")
    print(f"   coverage:   {report.edge_vocabulary_coverage:.1%}")

    print(f"\n8c Schema-data alignment")
    if report.entity_type_concentration:
        c = report.entity_type_concentration
        print(
            f"   top entity type:  {c['top_type']}  "
            f"({c['count']}/{c['total']} = {c['fraction']:.1%})"
        )
    print(f"   edge type entropy: {report.edge_type_entropy_bits:.2f} bits")
    if report.concentration_warning:
        print(f"   ⚠ {report.concentration_warning}")

    print(f"\n8d Ontology drift")
    print(f"   drift score:      {report.drift_score:.1%}")
    print(f"   declared union:   {len(report.declared_union)}")
    print(f"   effective union:  {len(report.effective_union)}")
    if report.hall_usage:
        hu = report.hall_usage
        print(f"\n   Hall usage (MemPalace-specific):")
        print(f"     total drawers:         {hu['total_drawers']}")
        print(
            f"     drawers with hall set: {hu['populated_count']}  "
            f"({hu['fraction_populated']:.1%})"
        )
        print(f"     declared vocabulary:   {', '.join(hu['declared_vocabulary'])}")
        if hu["distribution"]:
            print(f"     actual distribution:")
            for hv, c in list(hu["distribution"].items())[:10]:
                print(f"       {hv:20s} {c}")
        else:
            print(f"     actual distribution:   (empty — no drawers have hall set)")

    print(f"\n8e Claim verification")
    print(f"   tested:      {report.claims_tested}")
    print(f"   passed:      {report.claims_passed}")
    print(f"   untestable:  {report.claims_untestable}")
    print(f"   pass rate:   {report.claims_pass_rate:.1%}")
    print()
    for c in report.claims:
        marker = {
            "pass": "✓",
            "fail": "✗",
            "untestable": "?",
            "skipped": "-",
        }.get(c.status, "?")
        print(f"   {marker} [{c.status:10s}] {c.claim_id}")
        print(f"        \"{c.claim_text}\"")
        if c.operational_definition:
            op_short = " ".join(c.operational_definition.split())[:100]
            print(f"        op:    {op_short}")
        if c.notes:
            print(f"        note:  {c.notes}")
        if c.metrics:
            short_metrics = {
                k: (round(v, 3) if isinstance(v, float) else v)
                for k, v in c.metrics.items()
            }
            print(f"        data:  {short_metrics}")
        print()

    print(f"Introspection")
    print(f"   available checks: {len(report.introspection_available)}")
    print(f"   score:            {report.introspection_score:.1%}")
    print(
        "   (most systems have no health-check APIs for type drift, "
        "schema alignment, or self-testing — this is expected)"
    )

    if args.json:
        Path(args.json).write_text(
            json.dumps(report.to_dict(), indent=2, default=str)
        )
        print(f"\nJSON report written to {args.json}")

    adapter.close()
    return 0


def _load_adapter_from_args(args: argparse.Namespace) -> SMEAdapter:
    """Shared adapter construction for cat4/cat5/check."""
    db = getattr(args, "db", None)
    api_url = getattr(args, "api_url", None)
    adapter_kwargs: dict[str, Any] = {"read_only": True}
    if db:
        adapter_kwargs["db_path"] = db
    if api_url:
        adapter_kwargs["api_url"] = api_url
    for attr, key in (
        ("auto_discover", "auto_discover"),
        ("node_tables", "include_node_tables"),
        ("edge_tables", "include_edge_tables"),
        ("kg_path", "kg_path"),
        ("collection_name", "collection_name"),
    ):
        val = getattr(args, attr, None)
        if val:
            adapter_kwargs[key] = val
    return _load_adapter(args.adapter, **adapter_kwargs)


def _source_label(args: argparse.Namespace) -> str:
    """Display label for the data source (db path or API URL)."""
    return getattr(args, "db", None) or getattr(args, "api_url", None) or "?"


def _add_db_or_api_args(parser: argparse.ArgumentParser) -> None:
    """Add --db and --api-url to a subparser (at least one required)."""
    parser.add_argument(
        "--db",
        default=None,
        help="path to the adapter's db file (file mode). Optional when "
        "--api-url is supplied.",
    )
    parser.add_argument(
        "--api-url",
        default=None,
        metavar="URL",
        help="HTTP base URL for the graph's API (e.g. http://localhost:7740). "
        "Enables graph-snapshot queries through the Cypher endpoint "
        "instead of opening the .ldb file — works against locked DBs.",
    )


def cmd_cat4(args: argparse.Namespace) -> int:
    """Run Category 4 (ingestion integrity) against a system."""
    from sme.categories.ingestion_integrity import (
        format_report,
        score_ingestion_integrity,
    )

    adapter = _load_adapter_from_args(args)
    entities, edges = adapter.get_graph_snapshot()
    log.info("snapshot: %d entities, %d edges", len(entities), len(edges))

    report = score_ingestion_integrity(entities, edges)

    print()
    print("=" * 70)
    print(f" {args.adapter} ({_source_label(args)})")
    print("=" * 70)
    print(format_report(report))

    if args.json:
        out = {
            "adapter": args.adapter,
            "source": _source_label(args),
            "entities": report.entities,
            "edges": report.edges,
            "unique_canonical_keys": report.unique_canonical_keys,
            "canonical_collisions": report.canonical_collisions,
            "collision_groups": [
                {
                    "canonical_key": g.canonical_key,
                    "entity_type": g.entity_type,
                    "ids": g.ids,
                    "names": g.names,
                }
                for g in report.collision_groups
            ],
            "required_field_gaps": report.required_field_gaps,
            "required_field_coverage": report.required_field_coverage,
            "gap_examples": report.gap_examples,
            "edge_type_counts": report.edge_type_counts,
            "edge_type_entropy_bits": report.edge_type_entropy_bits,
            "edge_type_entropy_normalized": report.edge_type_entropy_normalized,
            "dominant_edge_type": report.dominant_edge_type,
            "dominant_edge_type_fraction": report.dominant_edge_type_fraction,
            "per_edge_type_components": report.per_edge_type_components,
        }
        Path(args.json).write_text(json.dumps(out, indent=2, default=str))
        print(f"\nJSON report written to {args.json}")

    adapter.close()
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Run the default test suite (Cat 4 + Cat 5 + structural analyze).

    One command, three readings, unified card. Designed for daily /
    nightly use against your own graphs rather than benchmark runs.
    """
    from sme.categories.gap_detection import (
        format_report as format_cat5,
        score_gap_detection,
    )
    from sme.categories.ingestion_integrity import (
        format_report as format_cat4,
        score_ingestion_integrity,
    )

    adapter = _load_adapter_from_args(args)
    entities, edges = adapter.get_graph_snapshot()
    log.info("snapshot: %d entities, %d edges", len(entities), len(edges))

    cat4 = score_ingestion_integrity(entities, edges)
    cat5 = score_gap_detection(
        entities,
        edges,
        run_homology=not args.no_homology,
        betti_max_nodes=args.betti_max_nodes,
    )

    print()
    print("=" * 70)
    print(f" sme-eval check — {args.adapter} ({_source_label(args)})")
    print("=" * 70)
    print()
    print(format_cat4(cat4))
    print()
    print(format_cat5(cat5))

    if args.json:
        out = {
            "adapter": args.adapter,
            "source": _source_label(args),
            "cat4": {
                "entities": cat4.entities,
                "edges": cat4.edges,
                "canonical_collisions": cat4.canonical_collisions,
                "unique_canonical_keys": cat4.unique_canonical_keys,
                "required_field_gaps": cat4.required_field_gaps,
                "required_field_coverage": cat4.required_field_coverage,
                "edge_type_counts": cat4.edge_type_counts,
                "edge_type_entropy_bits": cat4.edge_type_entropy_bits,
                "edge_type_entropy_normalized": cat4.edge_type_entropy_normalized,
                "dominant_edge_type": cat4.dominant_edge_type,
                "dominant_edge_type_fraction": cat4.dominant_edge_type_fraction,
                "per_edge_type_components": cat4.per_edge_type_components,
            },
            "cat5": {
                "components": cat5.components,
                "largest_component_size": cat5.largest_component_size,
                "isolated_nodes": cat5.isolated_nodes,
                "bridges": len(cat5.bridges),
                "betti_0_largest": cat5.betti_0_largest,
                "betti_1_largest": cat5.betti_1_largest,
                "h1_max_persistence": cat5.h1_max_persistence,
                "h1_skipped": cat5.h1_skipped,
                "candidate_gaps_shown": len(cat5.candidate_gaps),
                "candidate_gaps_considered": cat5.candidate_gaps_considered,
            },
        }
        Path(args.json).write_text(json.dumps(out, indent=2, default=str))
        print(f"\nJSON report written to {args.json}")

    adapter.close()
    return 0


def cmd_cat5(args: argparse.Namespace) -> int:
    """Run Category 5 (gap detection) against a system."""
    from sme.categories.gap_detection import format_report, score_gap_detection

    seeded: list[tuple[str, str]] | None = None
    if args.seeded_gaps:
        import yaml

        with open(args.seeded_gaps) as f:
            doc = yaml.safe_load(f) or {}
        raw = doc.get("missing_edges") or doc.get("seeded_missing_edges") or []
        seeded = [(pair[0], pair[1]) for pair in raw if len(pair) == 2]

    adapter_kwargs: dict[str, Any] = {
        "db_path": args.db,
        "read_only": True,
        "auto_discover": args.auto_discover,
    }
    if args.node_tables:
        adapter_kwargs["include_node_tables"] = args.node_tables
    if args.edge_tables:
        adapter_kwargs["include_edge_tables"] = args.edge_tables
    if args.kg_path:
        adapter_kwargs["kg_path"] = args.kg_path
    if args.collection_name:
        adapter_kwargs["collection_name"] = args.collection_name

    adapter = _load_adapter(args.adapter, **adapter_kwargs)
    entities, edges = adapter.get_graph_snapshot()
    log.info("snapshot: %d entities, %d edges", len(entities), len(edges))

    report = score_gap_detection(
        entities,
        edges,
        seeded_missing_edges=seeded,
        run_homology=not args.no_homology,
        betti_max_nodes=args.betti_max_nodes,
        min_component_size=args.min_component_size,
        max_type_prevalence=args.max_type_prevalence,
        top_k=args.top_k,
    )

    print()
    print("=" * 70)
    print(f" {args.adapter} ({_source_label(args)})")
    print("=" * 70)
    print(format_report(report))

    if args.json:
        out = {
            "adapter": args.adapter,
            "source": _source_label(args),
            "nodes": report.nodes,
            "edges": report.edges,
            "components": report.components,
            "largest_component_size": report.largest_component_size,
            "isolated_nodes": report.isolated_nodes,
            "bridges": report.bridges,
            "betti_0_largest": report.betti_0_largest,
            "betti_1_largest": report.betti_1_largest,
            "h1_max_persistence": report.h1_max_persistence,
            "h1_skipped": report.h1_skipped,
            "h1_skip_reason": report.h1_skip_reason,
            "candidate_gaps": [
                {
                    "component_a": g.component_a,
                    "component_b": g.component_b,
                    "size_a": g.size_a,
                    "size_b": g.size_b,
                    "shared_entity_types": g.shared_entity_types,
                    "score": g.score,
                    "example_ids_a": g.example_ids_a,
                    "example_ids_b": g.example_ids_b,
                }
                for g in report.candidate_gaps
            ],
            "candidate_gaps_considered": report.candidate_gaps_considered,
            "gap_recall": report.gap_recall,
            "gap_precision": report.gap_precision,
            "detection_level": report.detection_level,
        }
        Path(args.json).write_text(json.dumps(out, indent=2, default=str))
        print(f"\nJSON report written to {args.json}")

    adapter.close()
    return 0


def cmd_cat2c(args: argparse.Namespace) -> int:
    """Produce a multi-hop recall scorecard from retrieval result JSONs."""
    from sme.categories.multi_hop import format_report, score_cat2c

    report = score_cat2c(
        flat_json=args.flat,
        graph_json=args.graph,
        no_structure_json=args.no_structure,
        flat_label=args.flat_label or "flat baseline (A)",
        graph_label=args.graph_label or "full pipeline (B)",
        no_structure_label=args.no_structure_label or "structure disabled (C)",
    )

    print(format_report(report))

    if args.json:
        Path(args.json).write_text(
            json.dumps(report.to_dict(), indent=2, default=str)
        )
        print(f"JSON report written to {args.json}")

    return 0


def cmd_retrieve(args: argparse.Namespace) -> int:
    """Run a question set through an adapter's query() and score it."""
    import yaml

    # tiktoken for real token counts
    try:
        import tiktoken

        _enc = tiktoken.get_encoding("cl100k_base")

        def count_tokens(text: str) -> int:
            return len(_enc.encode(text)) if text else 0
    except Exception:
        log.warning("tiktoken unavailable — falling back to char count / 4")

        def count_tokens(text: str) -> int:
            return len(text) // 4 if text else 0

    # Load questions
    with open(args.questions) as f:
        qdoc = yaml.safe_load(f)
    questions = qdoc.get("questions", [])
    if not questions:
        raise SystemExit(f"no questions found in {args.questions}")

    # Load adapter
    adapter_kwargs: dict[str, Any] = {
        "db_path": args.db,
        "read_only": True,
    }
    if args.collection_name:
        adapter_kwargs["collection_name"] = args.collection_name
    if getattr(args, "api_url", None):
        adapter_kwargs["api_url"] = args.api_url
    if getattr(args, "query_mode", None):
        adapter_kwargs["default_query_mode"] = args.query_mode
    adapter = _load_adapter(args.adapter, **adapter_kwargs)

    # Run each question
    per_question: list[dict] = []
    print()
    print("=" * 80)
    print(f" Retrieval test — adapter={args.adapter} corpus={qdoc.get('version','?')}")
    print(f" n_results={args.n_results}  questions={len(questions)}")
    print("=" * 80)

    for q in questions:
        qid = q.get("id", "?")
        text = q.get("text", "")
        expected = q.get("expected_sources", []) or []
        min_hops = q.get("min_hops", 0)
        t0 = time.time()
        try:
            # MemPalaceAdapter.query takes n_results + route kwargs;
            # other adapters don't — fall back through typing errors.
            try:
                result = adapter.query(
                    text, n_results=args.n_results, route=not args.no_route
                )
            except TypeError:
                try:
                    result = adapter.query(text, n_results=args.n_results)
                except TypeError:
                    result = adapter.query(text)
        except Exception as e:  # pragma: no cover
            result = type(
                "QR", (), {"answer": "", "context_string": "", "error": str(e), "retrieved_entities": [], "retrieval_path": []}
            )()
        elapsed = time.time() - t0

        ctx = getattr(result, "context_string", "") or ""
        err = getattr(result, "error", None)
        tokens = count_tokens(ctx)

        # Scoring: did any expected source file show up in the context?
        matches = [src for src in expected if src in ctx]
        recall = len(matches) / len(expected) if expected else 0.0
        hit = recall > 0

        # Where it came from (for MemPalace)
        path = getattr(result, "retrieval_path", []) or []
        path_note = f"  [{'; '.join(path)}]" if path else ""

        status = "✓" if recall >= 1.0 else ("~" if hit else "✗")
        print(
            f"\n{qid}  (hops={min_hops})  {status}  recall={recall:.2f}  "
            f"tokens={tokens}  {elapsed*1000:.0f}ms{path_note}"
        )
        print(f"  Q: {text}")
        print(f"  expected: {expected}")
        print(f"  matched:  {matches}")
        if err:
            print(f"  ERROR: {err}")

        per_question.append(
            {
                "id": qid,
                "text": text,
                "min_hops": min_hops,
                "expected_sources": expected,
                "matched_sources": matches,
                "recall": recall,
                "hit": hit,
                "tokens": tokens,
                "elapsed_ms": round(elapsed * 1000, 1),
                "retrieval_path": path,
                "error": err,
            }
        )

    # Summary
    print()
    print("=" * 80)
    print(" Summary")
    print("=" * 80)

    # By hop depth
    by_hop: dict[int, list[dict]] = {}
    for pq in per_question:
        by_hop.setdefault(pq["min_hops"], []).append(pq)

    print(f"\n{'hops':>6}  {'n':>4}  {'recall':>8}  {'hit-rate':>10}  {'avg tok':>8}")
    print(f"{'----':>6}  {'---':>4}  {'------':>8}  {'--------':>10}  {'-------':>8}")
    for hops in sorted(by_hop.keys()):
        group = by_hop[hops]
        n = len(group)
        avg_recall = sum(pq["recall"] for pq in group) / n if n else 0.0
        hit_rate = sum(1 for pq in group if pq["hit"]) / n if n else 0.0
        avg_tokens = sum(pq["tokens"] for pq in group) / n if n else 0.0
        print(
            f"{hops:>6}  {n:>4}  {avg_recall:>7.2%}  {hit_rate:>9.2%}  {avg_tokens:>8.0f}"
        )

    total_n = len(per_question)
    total_recall = sum(pq["recall"] for pq in per_question) / total_n if total_n else 0.0
    total_hit_rate = sum(1 for pq in per_question if pq["hit"]) / total_n if total_n else 0.0
    total_tokens = sum(pq["tokens"] for pq in per_question)
    correct_count = sum(1 for pq in per_question if pq["recall"] >= 1.0)
    tokens_per_correct = (total_tokens / correct_count) if correct_count else float("inf")
    print(
        f"\n{'total':>6}  {total_n:>4}  {total_recall:>7.2%}  {total_hit_rate:>9.2%}  "
        f"{total_tokens / total_n:>8.0f}"
    )
    print(f"\n  full recall@K: {correct_count}/{total_n}")
    print(f"  partial hit:   {sum(1 for pq in per_question if pq['hit'])}/{total_n}")
    print(f"  total tokens:  {total_tokens:,}")
    print(
        f"  tokens / correct answer: "
        + (f"{tokens_per_correct:.0f}" if correct_count else "inf (no full-recall questions)")
    )

    if args.json:
        out = {
            "adapter": args.adapter,
            "db_path": args.db,
            "collection_name": args.collection_name,
            "corpus_version": qdoc.get("version", "?"),
            "n_results": args.n_results,
            "questions": per_question,
            "summary": {
                "total": total_n,
                "full_recall": correct_count,
                "partial_hit": sum(1 for pq in per_question if pq["hit"]),
                "mean_recall": total_recall,
                "mean_tokens": total_tokens / total_n if total_n else 0.0,
                "tokens_per_correct_answer": (
                    tokens_per_correct if correct_count else None
                ),
                "by_hop": {
                    str(h): {
                        "n": len(g),
                        "mean_recall": sum(pq["recall"] for pq in g) / len(g),
                        "hit_rate": sum(1 for pq in g if pq["hit"]) / len(g),
                        "mean_tokens": sum(pq["tokens"] for pq in g) / len(g),
                    }
                    for h, g in by_hop.items()
                },
            },
        }
        Path(args.json).write_text(json.dumps(out, indent=2, default=str))
        print(f"\nJSON report written to {args.json}")

    adapter.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sme-eval",
        description="Structural Memory Evaluation — analyze a memory system's graph.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="enable info logging"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ana = sub.add_parser(
        "analyze",
        help="Load a graph via an adapter and print a structural report.",
    )
    ana.add_argument(
        "--adapter",
        default="ladybugdb",
        help="adapter name (default: ladybugdb)",
    )
    ana.add_argument(
        "--db",
        required=True,
        help="path to the database file (e.g. .vault-idx/graph.ldb)",
    )
    ana.add_argument(
        "--auto-discover",
        action="store_true",
        help="include every non-empty NODE and REL table discovered on "
        "the database, minus operational infrastructure (logs/caches). "
        "Use this for unfamiliar schemas.",
    )
    ana.add_argument(
        "--node-tables",
        nargs="+",
        metavar="TABLE",
        help="node tables to include (overrides default and --auto-discover)",
    )
    ana.add_argument(
        "--edge-tables",
        nargs="+",
        metavar="TABLE",
        help="edge tables to include in the snapshot "
        "(default: ENTITY_TO_ENTITY NOTE_TO_ENTITY NOTE_TO_NOTE)",
    )
    ana.add_argument(
        "--kg-path",
        metavar="PATH",
        help="(mempalace adapter) path to the SQLite knowledge graph file. "
        "Defaults to ~/.mempalace/knowledge_graph.sqlite3. Adapter skips "
        "the KG layer silently if the file doesn't exist.",
    )
    ana.add_argument(
        "--collection-name",
        metavar="NAME",
        help="(mempalace adapter) ChromaDB collection name. "
        "Defaults to mempalace_drawers.",
    )
    ana.add_argument(
        "--betti",
        action="store_true",
        help="also compute persistent homology (H0, H1) on the largest "
        "connected component via Ripser. Heavier than the other steps.",
    )
    ana.add_argument(
        "--betti-max-nodes",
        type=int,
        default=2000,
        help="maximum node count for Ripser input. Components larger "
        "than this are skipped unless --betti-subsample is set. Ripser's "
        "Vietoris-Rips complex construction scales poorly on dense large "
        "graphs. Default: 2000.",
    )
    ana.add_argument(
        "--betti-subsample",
        action="store_true",
        help="if the largest component exceeds --betti-max-nodes, take "
        "a random subsample instead of skipping. Betti numbers become "
        "approximate; use with caution.",
    )
    ana.add_argument(
        "--json",
        metavar="PATH",
        help="also write the full report as JSON to this path",
    )
    ana.set_defaults(func=cmd_analyze)

    # --- retrieve subcommand -----------------------------------------

    ret = sub.add_parser(
        "retrieve",
        help="Run a YAML question set through an adapter's query() "
        "method and score with substring match + tiktoken token count.",
    )
    ret.add_argument(
        "--adapter",
        required=True,
        help="adapter name (flat | mempalace | ladybugdb)",
    )
    ret.add_argument(
        "--db",
        required=False,
        default=None,
        help="path passed to the adapter as db_path. Optional when "
        "--api-url is supplied (ladybugdb adapter in API-only mode).",
    )
    ret.add_argument(
        "--api-url",
        metavar="URL",
        help="(ladybugdb) HTTP base URL for API-mode queries (e.g. "
        "http://localhost:7720). Lets the adapter query a live server "
        "without opening the local .ldb file (avoiding writer locks).",
    )
    ret.add_argument(
        "--query-mode",
        metavar="MODE",
        help="(ladybugdb) /search mode: semantic | hybrid | graph | "
        "path. Defaults to 'hybrid' (full pipeline). Use 'semantic' as "
        "Condition C (structure disabled).",
    )
    ret.add_argument(
        "--collection-name",
        metavar="NAME",
        help="(flat, mempalace) ChromaDB collection name",
    )
    ret.add_argument(
        "--questions",
        required=True,
        metavar="YAML",
        help="path to a questions YAML file with id/text/expected_sources",
    )
    ret.add_argument(
        "--n-results",
        type=int,
        default=5,
        help="top-K results per query (default: 5)",
    )
    ret.add_argument(
        "--no-route",
        action="store_true",
        help="(mempalace adapter) disable inferred wing/room routing — "
        "runs the same ChromaDB collection without metadata filtering. "
        "Lets you isolate the contribution of the routing layer from "
        "the retrieval layer.",
    )
    ret.add_argument(
        "--json",
        metavar="PATH",
        help="write full per-question results to this JSON path",
    )
    ret.set_defaults(func=cmd_retrieve)

    # --- cat8 subcommand ---------------------------------------------

    c8 = sub.add_parser(
        "cat8",
        help="Run Category 8 (ontology coherence) against a system. "
        "Compares the system's declared ontology to its actual graph.",
    )
    c8.add_argument("--adapter", required=True)
    c8.add_argument("--db", required=True, help="path to the adapter's db")
    c8.add_argument(
        "--implied-ontology",
        required=True,
        metavar="YAML",
        help="path to the implied ontology YAML (hand-authored or pre-extracted)",
    )
    c8.add_argument(
        "--collection-name",
        metavar="NAME",
        help="(mempalace/flat) ChromaDB collection name override",
    )
    c8.add_argument(
        "--kg-path",
        metavar="PATH",
        help="(mempalace) SQLite knowledge graph path override",
    )
    c8.add_argument(
        "--cat7-flat",
        metavar="JSON",
        help="retrieve-results JSON for the flat baseline (Condition A). "
        "When combined with --cat7-graph, enables Cat 8e cross-reference "
        "of 'improves retrieval' claims against real benchmark data.",
    )
    c8.add_argument(
        "--cat7-graph",
        metavar="JSON",
        help="retrieve-results JSON for the system under test (Condition B).",
    )
    c8.add_argument("--json", metavar="PATH", help="write full report as JSON")
    c8.set_defaults(func=cmd_cat8)

    # --- cat4 subcommand ---------------------------------------------

    c4 = sub.add_parser(
        "cat4",
        help="Run Category 4 (The Threshold — ingestion integrity) "
        "against a system. Reports canonical-collision dedup, required-"
        "field coverage, and edge-type monoculture signals.",
    )
    c4.add_argument("--adapter", required=True)
    _add_db_or_api_args(c4)
    c4.add_argument(
        "--auto-discover",
        action="store_true",
        help="include every non-empty NODE and REL table discovered on "
        "the database, minus operational infrastructure.",
    )
    c4.add_argument(
        "--node-tables",
        nargs="+",
        metavar="TABLE",
        help="node tables to include (overrides default and --auto-discover)",
    )
    c4.add_argument(
        "--edge-tables",
        nargs="+",
        metavar="TABLE",
        help="edge tables to include in the snapshot",
    )
    c4.add_argument(
        "--kg-path",
        metavar="PATH",
        help="(mempalace) SQLite knowledge graph path override",
    )
    c4.add_argument(
        "--collection-name",
        metavar="NAME",
        help="(mempalace/flat) ChromaDB collection name",
    )
    c4.add_argument("--json", metavar="PATH", help="write full report as JSON")
    c4.set_defaults(func=cmd_cat4)

    # --- check subcommand (test-suite runner) ------------------------

    chk = sub.add_parser(
        "check",
        help="Default test suite: Cat 4 (ingestion integrity) + Cat 5 "
        "(gap detection). One command, unified card, designed for daily "
        "/ nightly diagnostic runs against your own graphs.",
    )
    chk.add_argument("--adapter", required=True)
    _add_db_or_api_args(chk)
    chk.add_argument(
        "--auto-discover",
        action="store_true",
        help="include every non-empty NODE and REL table discovered.",
    )
    chk.add_argument("--node-tables", nargs="+", metavar="TABLE")
    chk.add_argument("--edge-tables", nargs="+", metavar="TABLE")
    chk.add_argument("--kg-path", metavar="PATH")
    chk.add_argument("--collection-name", metavar="NAME")
    chk.add_argument(
        "--no-homology",
        action="store_true",
        help="skip the Cat 5 Ripser pass (no Betti-1 reading).",
    )
    chk.add_argument(
        "--betti-max-nodes",
        type=int,
        default=2000,
        help="skip homology when the largest component exceeds this size.",
    )
    chk.add_argument("--json", metavar="PATH", help="write combined report as JSON")
    chk.set_defaults(func=cmd_check)

    # --- cat5 subcommand ---------------------------------------------

    c5 = sub.add_parser(
        "cat5",
        help="Run Category 5 (The Missing Room — gap detection) against a "
        "system. External (L3) reading only: components, bridges, Betti-1 on "
        "the largest component, and candidate cross-component gaps.",
    )
    c5.add_argument("--adapter", required=True)
    _add_db_or_api_args(c5)
    c5.add_argument(
        "--auto-discover",
        action="store_true",
        help="include every non-empty NODE and REL table discovered on "
        "the database, minus operational infrastructure.",
    )
    c5.add_argument(
        "--node-tables",
        nargs="+",
        metavar="TABLE",
        help="node tables to include (overrides default and --auto-discover)",
    )
    c5.add_argument(
        "--edge-tables",
        nargs="+",
        metavar="TABLE",
        help="edge tables to include in the snapshot",
    )
    c5.add_argument(
        "--kg-path",
        metavar="PATH",
        help="(mempalace) SQLite knowledge graph path override",
    )
    c5.add_argument(
        "--collection-name",
        metavar="NAME",
        help="(mempalace/flat) ChromaDB collection name",
    )
    c5.add_argument(
        "--seeded-gaps",
        metavar="YAML",
        help="YAML file with a `missing_edges: [[src_id, tgt_id], ...]` list "
        "of known-missing edges. Enables gap recall/precision scoring.",
    )
    c5.add_argument(
        "--no-homology",
        action="store_true",
        help="skip the Ripser pass (no Betti-1 reading). Useful when "
        "ripser is not installed or the largest component is huge.",
    )
    c5.add_argument(
        "--betti-max-nodes",
        type=int,
        default=2000,
        help="skip homology when the largest component exceeds this size. "
        "Default: 2000.",
    )
    c5.add_argument(
        "--min-component-size",
        type=int,
        default=3,
        help="candidate-gap pairs only consider components with at least "
        "this many nodes on both sides. Filters out orphan-pair noise. "
        "Default: 3.",
    )
    c5.add_argument(
        "--max-type-prevalence",
        type=float,
        default=0.5,
        help="entity types present in more than this fraction of sized "
        "components are treated as universal and don't score. Default 0.5.",
    )
    c5.add_argument(
        "--top-k",
        type=int,
        default=20,
        help="keep the top-K candidate gaps by score. The report still "
        "records how many pairs were considered. Default: 20.",
    )
    c5.add_argument("--json", metavar="PATH", help="write full report as JSON")
    c5.set_defaults(func=cmd_cat5)

    # --- cat2c subcommand --------------------------------------------

    c2c = sub.add_parser(
        "cat2c",
        help="Multi-hop recall scorecard from retrieval result JSONs. "
        "Compares Condition A (flat) / B (full pipeline) / C (structure "
        "disabled) by hop depth.",
    )
    c2c.add_argument(
        "--flat", metavar="JSON", help="retrieve-results JSON for Condition A"
    )
    c2c.add_argument(
        "--graph",
        required=True,
        metavar="JSON",
        help="retrieve-results JSON for Condition B (system under test)",
    )
    c2c.add_argument(
        "--no-structure",
        metavar="JSON",
        help="retrieve-results JSON for Condition C (structure disabled)",
    )
    c2c.add_argument("--flat-label", help="custom label for Condition A")
    c2c.add_argument("--graph-label", help="custom label for Condition B")
    c2c.add_argument(
        "--no-structure-label", help="custom label for Condition C"
    )
    c2c.add_argument("--json", metavar="PATH", help="write full report as JSON")
    c2c.set_defaults(func=cmd_cat2c)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
