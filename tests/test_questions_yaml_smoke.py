"""Smoke check: every expected_source substring in good-dog-corpus's
questions.yaml exists in at least one vault note.

Catches wrong-attribution at authoring time — the substring matcher
will silently report 0 recall for any expected_source string that
doesn't appear in the corpus, and that failure mode is invisible
without a check like this.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


CORPUS_ROOT = (
    Path(__file__).resolve().parent.parent
    / "sme"
    / "corpora"
    / "good-dog-corpus"
)
QUESTIONS_PATH = CORPUS_ROOT / "questions.yaml"
VAULT_DIR = CORPUS_ROOT / "vault"


@pytest.fixture(scope="module")
def all_vault_text() -> str:
    parts = []
    for md in sorted(VAULT_DIR.rglob("*.md")):
        parts.append(md.read_text())
    return "\n\n".join(parts)


@pytest.fixture(scope="module")
def questions_yaml() -> dict:
    return yaml.safe_load(QUESTIONS_PATH.read_text())


def test_questions_yaml_parses(questions_yaml):
    assert questions_yaml.get("version", "").startswith("good-dog-corpus")
    assert isinstance(questions_yaml.get("questions"), list)
    assert len(questions_yaml["questions"]) >= 12


def test_required_fields_present(questions_yaml):
    for q in questions_yaml["questions"]:
        assert "id" in q, f"question missing id: {q}"
        assert "text" in q, f"question {q['id']} missing text"
        assert "expected_sources" in q, f"question {q['id']} missing expected_sources"
        assert "min_hops" in q, f"question {q['id']} missing min_hops"
        assert "sme_category" in q, f"question {q['id']} missing sme_category"
        assert isinstance(q["expected_sources"], list)
        assert q["min_hops"] in (0, 1, 2, 3, 4, 5), (
            f"question {q['id']} has implausible min_hops={q['min_hops']}"
        )


def test_question_ids_unique(questions_yaml):
    ids = [q["id"] for q in questions_yaml["questions"]]
    assert len(ids) == len(set(ids)), f"duplicate ids: {ids}"


def test_sme_categories_are_known(questions_yaml):
    """The cross-validation report groups by these category strings;
    typos here would silently bucket questions into 'unknown'."""
    known = {"cat_1", "cat_2c", "cat_3", "cat_4", "cat_5", "cat_6", "cat_7"}
    for q in questions_yaml["questions"]:
        assert q["sme_category"] in known, (
            f"question {q['id']} has unknown sme_category={q['sme_category']!r}"
        )


def test_every_expected_source_appears_in_at_least_one_note(
    questions_yaml, all_vault_text
):
    """The load-bearing check. If a substring doesn't appear anywhere in
    the corpus, the substring matcher will always score 0 for it — a
    silent authoring bug. Catches that here."""
    missing: list[tuple[str, str]] = []
    for q in questions_yaml["questions"]:
        for term in q["expected_sources"]:
            if term not in all_vault_text:
                missing.append((q["id"], term))

    assert not missing, (
        "expected_sources substrings missing from the vault — these "
        "would silently score 0:\n"
        + "\n".join(f"  {qid}: {term!r}" for qid, term in missing)
    )


def test_no_question_has_empty_expected_sources(questions_yaml):
    """A question with no expected_sources can't be scored. If you
    deliberately want a no-score question, mark it with an explicit
    `unscored: true` flag (and update this check). For now, every
    question must have at least one expected_source."""
    for q in questions_yaml["questions"]:
        assert q["expected_sources"], (
            f"question {q['id']} has empty expected_sources — "
            "scoring would always return 0/0"
        )


def test_contradiction_pair_ids_referenced_consistently(questions_yaml):
    """If two questions cite the same contradiction_pair_id, they're
    probing the same seeded chain — make sure those land in compatible
    sme_categories (cat_3 contradiction-surfacing OR cat_6 temporal,
    not e.g. cat_4 alias)."""
    pair_to_cats: dict[str, set[str]] = {}
    for q in questions_yaml["questions"]:
        pair = q.get("contradiction_pair_id")
        if not pair:
            continue
        pair_to_cats.setdefault(pair, set()).add(q["sme_category"])

    valid_cats = {"cat_3", "cat_6"}
    for pair, cats in pair_to_cats.items():
        bad = cats - valid_cats
        assert not bad, (
            f"contradiction_pair_id={pair!r} probed under categories "
            f"{cats}; expected only {valid_cats}"
        )


def test_alias_pair_ids_match_ontology_registry():
    """Any alias_pair_id referenced in questions.yaml must exist in
    ontology.yaml#aliases — otherwise B-Cubed scoring against the
    gold registry would skip that question silently."""
    ontology = yaml.safe_load((CORPUS_ROOT / "ontology.yaml").read_text())
    questions = yaml.safe_load(QUESTIONS_PATH.read_text())
    registered_aliases = set((ontology.get("aliases") or {}).keys())

    referenced = set()
    for q in questions["questions"]:
        if "alias_pair_id" in q:
            referenced.add(q["alias_pair_id"])

    unknown = referenced - registered_aliases
    assert not unknown, (
        f"questions.yaml references alias_pair_ids not in "
        f"ontology.yaml#aliases: {sorted(unknown)}"
    )
