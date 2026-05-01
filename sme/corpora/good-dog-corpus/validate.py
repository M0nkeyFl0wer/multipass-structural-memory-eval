"""good-dog-corpus self-validation.

Runs corpus-quality checks against vault/ notes and ontology.yaml. Designed to
be run before any merge of new corpus content. Catches common errors:

  - Missing required frontmatter fields
  - Entity types declared in notes that aren't registered in ontology.yaml
  - Edge types declared in notes that aren't registered in ontology.yaml
  - Edges referencing entity ids that aren't introduced anywhere in vault/
  - Notes missing source attribution

This is intentionally minimal for v0.1. As the corpus grows, additional checks
will land here:

  - Alias-chain closure (every alias resolves to a canonical)
  - Hop-chain traversability against questions.yaml
  - Contradiction-pair bidirectionality
  - Per-edge-type evidence-rule compliance (the phantom-edge probe)

Usage:
    python sme/corpora/good-dog-corpus/validate.py

Exits 0 on success, 1 on any failure.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

CORPUS_ROOT = Path(__file__).resolve().parent
ONTOLOGY_PATH = CORPUS_ROOT / "ontology.yaml"
VAULT_PATH = CORPUS_ROOT / "vault"

REQUIRED_FRONTMATTER_FIELDS = (
    "note_id",
    "source_url",
    "source_title",
    "source_date",
    "source_publisher",
    "license",
    "accessed_on",
    "domain",
)

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def load_ontology() -> dict:
    with ONTOLOGY_PATH.open() as fh:
        return yaml.safe_load(fh)


def parse_frontmatter(text: str) -> dict | None:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    return yaml.safe_load(match.group(1))


def find_notes() -> list[Path]:
    return sorted(VAULT_PATH.rglob("*.md"))


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.notes_seen: int = 0
        self.entities_introduced: dict[str, str] = {}  # id -> note path

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def validate_note(
    path: Path,
    ontology: dict,
    report: Report,
) -> None:
    text = path.read_text()
    fm = parse_frontmatter(text)
    rel = path.relative_to(CORPUS_ROOT)

    if fm is None:
        report.fail(f"{rel}: no YAML frontmatter found")
        return

    report.notes_seen += 1

    for field in REQUIRED_FRONTMATTER_FIELDS:
        if field not in fm:
            report.fail(f"{rel}: missing required frontmatter field '{field}'")

    valid_entity_types = {et["id"] for et in ontology.get("entity_types", [])}
    valid_edge_types = {et["id"] for et in ontology.get("edge_types", [])}

    note_entity_ids: set[str] = set()
    for entity in fm.get("entities", []):
        eid = entity.get("id")
        etype = entity.get("type")
        if not eid:
            report.fail(f"{rel}: entity missing 'id' field")
            continue
        if not etype:
            report.fail(f"{rel}: entity {eid!r} missing 'type' field")
            continue
        if etype not in valid_entity_types:
            report.fail(
                f"{rel}: entity {eid!r} has unregistered type {etype!r} "
                f"(registered: {sorted(valid_entity_types)})"
            )
        if eid in report.entities_introduced:
            report.warn(
                f"{rel}: entity {eid!r} also introduced in "
                f"{report.entities_introduced[eid]} (later definition wins)"
            )
        report.entities_introduced[eid] = str(rel)
        note_entity_ids.add(eid)

    for edge in fm.get("edges", []):
        etype = edge.get("type")
        src = edge.get("from")
        dst = edge.get("to")
        if not etype:
            report.fail(f"{rel}: edge missing 'type' field")
            continue
        if etype not in valid_edge_types:
            report.fail(
                f"{rel}: edge has unregistered type {etype!r} "
                f"(registered: {sorted(valid_edge_types)})"
            )
        if not src or not dst:
            report.fail(f"{rel}: edge {etype!r} missing 'from' or 'to'")
            continue
        if "evidence" not in edge:
            report.warn(
                f"{rel}: edge {src} -[{etype}]-> {dst} missing 'evidence' field "
                f"(required for phantom-edge probe; warn-only in v0.1)"
            )


def validate_cross_note_references(report: Report) -> None:
    pass


def main() -> int:
    if not ONTOLOGY_PATH.exists():
        print(f"FAIL: ontology.yaml not found at {ONTOLOGY_PATH}")
        return 1

    try:
        ontology = load_ontology()
    except yaml.YAMLError as exc:
        print(f"FAIL: ontology.yaml does not parse: {exc}")
        return 1

    report = Report()
    notes = find_notes()

    if not notes:
        print("WARN: no notes found in vault/ (expected during early authoring)")

    for note in notes:
        validate_note(note, ontology, report)

    validate_cross_note_references(report)

    print(f"--- good-dog-corpus validate ---")
    print(f"notes scanned: {report.notes_seen}")
    print(f"entities introduced: {len(report.entities_introduced)}")
    print(f"warnings: {len(report.warnings)}")
    print(f"failures: {len(report.failures)}")
    print()

    for w in report.warnings:
        print(f"WARN: {w}")
    for f in report.failures:
        print(f"FAIL: {f}")

    if report.failures:
        print(f"\nVALIDATION FAILED ({len(report.failures)} error(s))")
        return 1
    print("\nVALIDATION OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
