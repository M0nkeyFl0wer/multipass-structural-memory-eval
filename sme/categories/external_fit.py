"""Cat 8 sub-check 8f: external-standard ontology fit + auto-generated audit.

Phase 1 slice. See
``docs/issue-drafts/2026-05-30-ontoclean-shacl-brokerage/04-cat8-external-standard-fit-and-audit.md``.

The other two Cat 8 deepenings (8g OntoClean, SHACL) check the graph
against a spec the maintainer hand-authored. This axis adds the one
yardstick that *isn't* self-authored — a published standard — and asks
whether the declared ontology matches it:

  * align each declared edge/entity term (and the provenance/temporal
    fields SME already tracks) against a static reference set
    (Phase 1: PROV-O + OWL-Time, ``sme/claims/standard_ontologies.yaml``),
  * classify each declared term as **mappable** / **under-specified**
    (one corpus term spanning several standard terms) / **idiosyncratic**
    (no standard analog — flagged, never auto-remapped),
  * auto-generate the conformance audit from each mapping's constraint
    and emit it in ``sh:ValidationReport`` shape (draft 03), with
    per-rule provenance and **confidence gating**: a high-confidence
    mapping's failure is a ``sh:Violation``; a low-confidence one is
    only ``sh:Info``. A guessed audit must never read as a clean one.

No new dependency, no RDF projection, no SHACL engine.

PRECONDITION (jphein, issue #45): the entities/edges passed in must come
from the *full* graph (or an explicitly uniform sample), never an
order-dependent / scaffold-padded projection — otherwise the audit
measures sampling bias, not ontology fit.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

import yaml

from sme.adapters.base import Edge, Entity

log = logging.getLogger(__name__)

DEFAULT_MAPPINGS_PATH = "sme/claims/standard_ontologies.yaml"

# at or above -> a failing constraint is a sh:Violation; below -> sh:Info
HIGH_CONFIDENCE = 0.85

# Permissive xsd:dateTime / ISO-8601: date, optional time, optional tz.
_ISO8601 = re.compile(
    r"^\d{4}-\d{2}-\d{2}"
    r"([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$"
)


# ── Loading ─────────────────────────────────────────────────────────


def load_standard_mappings(path: str | Path | None = None) -> dict:
    """Load the standard-ontology reference table."""
    p = Path(path) if path else None
    if p is None:
        here = Path(__file__).resolve().parent.parent.parent
        p = here / DEFAULT_MAPPINGS_PATH
    elif not p.is_absolute():
        here = Path(__file__).resolve().parent.parent.parent
        p = here / p
    with open(p) as f:
        return yaml.safe_load(f)


# ── Small helpers ───────────────────────────────────────────────────


def _term_ids(seq: Any) -> list[str]:
    """Declared types may be plain strings or ``{id: ...}`` dicts. Normalize."""
    out: list[str] = []
    for item in seq or []:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict) and "id" in item:
            out.append(item["id"])
    return out


def _std_prefix(curie: str) -> str:
    return curie.split(":", 1)[0]


def _iso_ok(v: Any) -> bool:
    return isinstance(v, str) and bool(_ISO8601.match(v.strip()))


def _infer_reference_set(rows: list[dict]) -> list[str]:
    return sorted({_std_prefix(r["standard_term"]) for r in rows})


# ── Constraint runner (the audit's per-rule check) ──────────────────


def _run_constraint(
    constraint: dict,
    row: dict,
    entities: list[Entity],
    edges: list[Edge],
) -> Optional[dict]:
    """Run one mapping's constraint. Return an sh:result-shaped finding
    dict if it is violated, or ``None`` if it conforms / is untestable
    on this graph (no relevant data)."""
    kind = constraint.get("kind")
    rel = row["corpus_term"]
    component = constraint.get("component", "sh:ConstraintComponent")
    msg = constraint.get("message", "")

    def finding(focus: str, value: Optional[str], detail: str) -> dict:
        out = {
            "sh:focusNode": focus,
            "sh:resultPath": rel,
            "sh:sourceConstraintComponent": component,
            "sh:resultMessage": f"{msg}; {detail}" if msg else detail,
        }
        if value is not None:
            out["sh:value"] = value
        return out

    if kind == "target_entity_type_in":
        allowed = set(constraint.get("allowed", []))
        ent_type = {e.id: e.entity_type for e in entities}
        rel_edges = [ed for ed in edges if ed.edge_type == rel]
        if not rel_edges:
            return None
        bad = [ed for ed in rel_edges if ent_type.get(ed.target_id) not in allowed]
        if not bad:
            return None
        return finding(
            f"Edge:{rel}",
            bad[0].target_id,
            f"{len(bad)}/{len(rel_edges)} targets are not in {sorted(allowed)}",
        )

    if kind == "endpoints_same_entity_type":
        ent_type = {e.id: e.entity_type for e in entities}
        rel_edges = [ed for ed in edges if ed.edge_type == rel]
        if not rel_edges:
            return None
        bad = [
            ed
            for ed in rel_edges
            if ent_type.get(ed.source_id) != ent_type.get(ed.target_id)
        ]
        if not bad:
            return None
        return finding(
            f"Edge:{rel}",
            None,
            f"{len(bad)}/{len(rel_edges)} edges cross entity-type boundaries",
        )

    if kind == "edge_field_coverage":
        field = constraint["field"]
        min_cov = float(constraint.get("min_coverage", 0.5))
        if not edges:
            return None
        present = sum(1 for ed in edges if ed.properties.get(field))
        cov = present / len(edges)
        if cov >= min_cov:
            return None
        return finding(
            f"Field:{field}",
            None,
            f"coverage {cov:.1%} < required {min_cov:.0%} ({present}/{len(edges)} edges)",
        )

    if kind == "edge_field_iso8601":
        field = constraint["field"]
        vals = [
            (ed, ed.properties.get(field))
            for ed in edges
            if ed.properties.get(field) is not None
        ]
        if not vals:
            return None
        bad = [(ed, v) for ed, v in vals if not _iso_ok(v)]
        if not bad:
            return None
        return finding(
            f"Field:{field}",
            str(bad[0][1]),
            f"{len(bad)}/{len(vals)} {field} values are not xsd:dateTime",
        )

    if kind == "entity_field_iso8601":
        field = constraint["field"]
        et = constraint.get("applies_to_entity_type")
        scope = [
            e
            for e in entities
            if (et is None or e.entity_type == et) and e.properties.get(field) is not None
        ]
        if not scope:
            return None
        bad = [e for e in scope if not _iso_ok(e.properties.get(field))]
        if not bad:
            return None
        return finding(
            f"Entity:{bad[0].id}",
            str(bad[0].properties.get(field)),
            f"{len(bad)}/{len(scope)} {et or 'entity'}.{field} values are not xsd:dateTime",
        )

    log.warning("external_fit: unknown constraint kind %r (skipped)", kind)
    return None


# ── Main scorer ─────────────────────────────────────────────────────


def score_external_fit(
    implied,
    entities: list[Entity],
    edges: list[Edge],
    *,
    mappings: Optional[dict] = None,
    reference_set: Optional[list[str]] = None,
    high_confidence: float = HIGH_CONFIDENCE,
) -> dict:
    """Produce the ``8f_external_fit`` report dict (see module docstring)."""
    if mappings is None:
        mappings = load_standard_mappings()
    rows: list[dict] = mappings.get("mappings", []) or []
    ref_set = (
        reference_set
        or mappings.get("reference_set")
        or _infer_reference_set(rows)
    )
    ref_set = list(ref_set)

    # index rows by (corpus_term) restricted to the active reference set
    in_scope = [r for r in rows if _std_prefix(r["standard_term"]) in ref_set]
    by_term: dict[str, list[dict]] = {}
    for r in in_scope:
        by_term.setdefault(r["corpus_term"], []).append(r)

    declared = [(t, "edge_type") for t in _term_ids(implied.edge_types)]
    declared += [(t, "entity_type") for t in _term_ids(implied.entity_types)]

    alignments: list[dict] = []
    unaligned: list[str] = []
    mappable = 0

    for term, kind in declared:
        matches = [
            m
            for m in by_term.get(term, [])
            if m.get("corpus_kind", kind) in (kind, None)
        ]
        if not matches:
            unaligned.append(term)
            continue
        distinct_std = {m["standard_term"] for m in matches}
        outcome = "under-specified" if len(distinct_std) > 1 else "mappable"
        if outcome == "mappable":
            mappable += 1
        for m in matches:
            alignments.append(
                {
                    "corpus_term": term,
                    "corpus_kind": kind,
                    "standard_term": m["standard_term"],
                    "confidence": m.get("confidence", 0.0),
                    "outcome": outcome,
                }
            )

    considered = len(declared)
    aligned_coverage = mappable / considered if considered else 0.0

    # --- audit: run each in-scope constraint, gated by confidence ---
    results: list[dict] = []
    for r in in_scope:
        constraint = r.get("constraint")
        if not constraint:
            continue
        finding = _run_constraint(constraint, r, entities, edges)
        if finding is None:
            continue
        conf = float(r.get("confidence", 0.0))
        finding["sh:resultSeverity"] = (
            "sh:Violation" if conf >= high_confidence else "sh:Info"
        )
        finding["provenance"] = f'{r["standard_term"]} (alignment conf {conf:.2f})'
        results.append(finding)

    violations = [x for x in results if x["sh:resultSeverity"] == "sh:Violation"]

    return {
        "reference_set": ref_set,
        "high_confidence_threshold": high_confidence,
        "considered_terms": considered,
        "aligned_coverage": round(aligned_coverage, 4),
        "mappable_count": mappable,
        "unaligned_types": sorted(unaligned),
        "alignments": alignments,
        "audit": {
            # @id coercion on the SHACL-vocabulary terms so that
            # "sh:Violation" / "sh:ClassConstraintComponent" parse as IRIs
            # (not string literals) under a real JSON-LD/SHACL reader — see
            # tests/test_cat8_shacl_conformance.py. The node-reference terms
            # (sh:focusNode, sh:value, sh:resultPath) remain graph-local
            # STRINGS, not IRIs: minting IRIs for property-graph nodes is the
            # RDF-projection commitment draft 03 deliberately defers. A
            # consumer can read conformance + severity + constraint-component;
            # it cannot dereference the focus nodes. That tradeoff is explicit.
            "@context": {
                "sh": "http://www.w3.org/ns/shacl#",
                "sh:resultSeverity": {"@type": "@id"},
                "sh:sourceConstraintComponent": {"@type": "@id"},
            },
            "sh:conforms": len(violations) == 0,
            "sh:result": results,
        },
    }
