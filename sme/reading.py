"""Score a graph snapshot into the reading `sme-eval check --json` writes.

One function, so the nightly `check` and the defect-injection harness build
the exact same reading. If they built it separately, "the harness detects
X" would say nothing about whether the nightly detects X.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Optional

from sme.adapters.base import Edge, Entity
from sme.check_regression import short_name


def score_reading(
    entities: list[Entity],
    edges: list[Edge],
    *,
    ontology: Optional[str] = None,
    run_homology: bool = False,
    betti_max_nodes: int = 2000,
) -> tuple[dict, Any, Any, Any]:
    """Return `(reading, cat4, cat5, cat8)`; cat8 is None without `ontology`.

    `reading` holds the `cat4`, `cat5` and (optionally) `cat8` blocks.
    Callers add their own `adapter` / `source` / `regression` keys.
    """
    from sme.categories.gap_detection import score_gap_detection
    from sme.categories.ingestion_integrity import score_ingestion_integrity

    cat4 = score_ingestion_integrity(entities, edges)
    cat5 = score_gap_detection(
        entities, edges, run_homology=run_homology, betti_max_nodes=betti_max_nodes
    )
    reading: dict = {
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
            # Per-type denominators, so a regression can be located
            # ("isolated share of Concept rose"), not just sized.
            "entity_type_counts": dict(Counter(e.entity_type or "unknown" for e in entities)),
            # The largest duplicate groups, so a collision rise names the
            # names. Capped: this is a pointer, not the full list.
            "collision_examples": [
                {
                    "key": short_name(g.canonical_key),
                    "type": g.entity_type,
                    "n": len(g.ids),
                    "names": [short_name(x) for x in g.names[:5]],
                }
                for g in sorted(cat4.collision_groups, key=lambda g: -len(g.ids))[:10]
            ],
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
            "isolated_by_type": cat5.isolated_by_type,
        },
    }

    # Cat 8 vocabulary (8a/8b/8d) against a declared ontology, on the same
    # snapshot. Deterministic and cheap, and it is the part that drifts.
    cat8 = None
    if ontology:
        from sme.categories.ontology_coherence import (
            ImpliedOntology,
            load_claim_library,
            score_cat8,
        )

        cat8 = score_cat8(
            ImpliedOntology.load(ontology),
            entities,
            edges,
            {"edge_type_entropy_bits": cat4.edge_type_entropy_bits},
            claim_library=load_claim_library(),
        )
        reading["cat8"] = {
            "ontology": str(ontology),
            "type_coverage": cat8.type_coverage,
            "types_missing": cat8.types_missing,
            "types_undeclared": cat8.types_undeclared,
            "edge_vocabulary_coverage": cat8.edge_vocabulary_coverage,
            "edges_missing": cat8.edges_missing,
            "edges_undeclared": cat8.edges_undeclared,
            "drift_score": cat8.drift_score,
        }
    return reading, cat4, cat5, cat8
