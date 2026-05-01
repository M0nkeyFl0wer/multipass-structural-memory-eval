"""End-to-end tests for B-Cubed scoring against a gold-aliases YAML.

Covers `sme.categories.ingestion_integrity.score_alias_resolution_against_gold`
which is the integration point between the existing Cat 4a collision
detector and the new `_bcubed.bcubed_score`.
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest
import yaml

from sme.adapters.base import Entity
from sme.categories.ingestion_integrity import (
    score_alias_resolution_against_gold,
    score_ingestion_integrity,
)


def _close(a: float, b: float, *, tol: float = 1e-9) -> bool:
    return math.isclose(a, b, abs_tol=tol)


def _entity(eid: str, name: str, etype: str = "concept") -> Entity:
    return Entity(id=eid, name=name, entity_type=etype, properties={})


GOLD_ALIASES = {
    "aliases": {
        "german_shepherd": {
            "canonical": "German Shepherd",
            "aliases": ["GSD", "Alsatian", "German Shepherd Dog"],
        },
        "pit_bull": {
            "canonical": "American Pit Bull Terrier",
            "aliases": ["Pit Bull", "APBT"],
        },
    }
}


@pytest.fixture
def gold_yaml(tmp_path):
    p = tmp_path / "gold_aliases.yaml"
    p.write_text(yaml.safe_dump(GOLD_ALIASES))
    return p


def test_no_overlap_returns_none(gold_yaml):
    """Graph contains entities whose names don't appear in any gold cluster.
    Nothing to score."""
    entities = [
        _entity("e1", "Border Collie"),
        _entity("e2", "Labrador Retriever"),
    ]
    report = score_ingestion_integrity(entities, [])
    result = score_alias_resolution_against_gold(report, entities, gold_yaml)
    assert result is None


def test_perfect_score_when_aliases_collide_via_canonicalization(tmp_path):
    """If the canonicalizer happens to merge the gold aliases (because
    they're case variants), B-Cubed should report perfect F1."""
    # Construct a gold registry where the aliases are case variants —
    # default_canonical_key WILL merge them.
    gold = {
        "aliases": {
            "tofu_test": {
                "canonical": "Tofu",
                "aliases": ["tofu", "TOFU", "Tofu "],
            }
        }
    }
    p = tmp_path / "gold.yaml"
    p.write_text(yaml.safe_dump(gold))
    entities = [
        _entity("e1", "Tofu"),
        _entity("e2", "tofu"),
        _entity("e3", "TOFU"),
        _entity("e4", "Tofu "),
    ]
    report = score_ingestion_integrity(entities, [])
    # All 4 should canonicalize together
    assert report.canonical_collisions == 3  # 4 ids, 1 cluster, 3 "extras"
    result = score_alias_resolution_against_gold(report, entities, p)
    assert result is not None
    assert _close(result.precision, 1.0)
    assert _close(result.recall, 1.0)


def test_full_recall_loss_when_aliases_dont_collide(gold_yaml):
    """default_canonical_key only does case + whitespace normalization.
    GSD and German Shepherd Dog don't collide that way, so the
    predicted clustering treats them as singletons and recall takes
    the hit (each item only sees itself in its cluster, but the
    gold cluster has 4 items). Precision is 1.0 because each
    singleton is correctly grouped (with itself, which is valid).
    """
    entities = [
        _entity("e1", "German Shepherd"),
        _entity("e2", "GSD"),
        _entity("e3", "Alsatian"),
        _entity("e4", "German Shepherd Dog"),
    ]
    report = score_ingestion_integrity(entities, [])
    # default_canonical_key won't merge these — different surface forms
    assert report.canonical_collisions == 0

    result = score_alias_resolution_against_gold(report, entities, gold_yaml)
    assert result is not None
    # 4 items in graph that overlap with gold (all of GSD cluster).
    # Each item is a singleton in predicted (size 1), gold cluster has
    # size 4 → precision_i = 1/1, recall_i = 1/4. Average gives:
    assert _close(result.precision, 1.0)
    assert _close(result.recall, 0.25)


def test_partial_collision_partial_score(tmp_path):
    """Only some of the gold-cluster items are case-variants that the
    canonicalizer merges; others are not. Recall is partial."""
    gold = {
        "aliases": {
            "mixed": {
                "canonical": "Foo",
                "aliases": ["foo", "FOO", "Bar"],
            }
        }
    }
    p = tmp_path / "gold.yaml"
    p.write_text(yaml.safe_dump(gold))
    entities = [
        _entity("e1", "Foo"),
        _entity("e2", "foo"),
        _entity("e3", "FOO"),
        _entity("e4", "Bar"),
    ]
    report = score_ingestion_integrity(entities, [])
    # Foo / foo / FOO collide (3 ids, 1 cluster, 2 extras); Bar is alone
    assert report.canonical_collisions == 2

    result = score_alias_resolution_against_gold(report, entities, p)
    assert result is not None
    # Predicted: {Foo, foo, FOO} + {Bar}
    # Gold:      {Foo, foo, FOO, Bar}
    # Per-item:
    #   Foo: pred = {Foo,foo,FOO}, gold ∩ pred = 3, pred = 3, gold = 4 → P=1, R=3/4
    #   foo: same                                                      → P=1, R=3/4
    #   FOO: same                                                      → P=1, R=3/4
    #   Bar: pred = {Bar}, gold ∩ pred = 1, pred = 1, gold = 4         → P=1, R=1/4
    # Average: P = 1.0, R = (3/4 + 3/4 + 3/4 + 1/4)/4 = 10/16 = 0.625
    assert _close(result.precision, 1.0)
    assert _close(result.recall, 0.625)


def test_ignores_gold_items_not_in_graph(tmp_path):
    """Gold registry covers items the graph doesn't have. Score only
    over the in-graph subset."""
    gold = {
        "aliases": {
            "vehicle_types": {
                "canonical": "car",
                "aliases": ["automobile", "vehicle", "auto"],
            }
        }
    }
    p = tmp_path / "gold.yaml"
    p.write_text(yaml.safe_dump(gold))
    entities = [
        _entity("e1", "car"),  # in-graph + in-gold
        _entity("e2", "automobile"),  # in-graph + in-gold
        _entity("e3", "Border Collie"),  # in-graph, NOT in-gold (ignored)
    ]
    report = score_ingestion_integrity(entities, [])
    result = score_alias_resolution_against_gold(report, entities, p)
    assert result is not None
    # Only 2 items scored (car, automobile). Both are singletons in
    # predicted; gold has them together. P=1.0, R=0.5 each → avg P=1.0, R=0.5
    assert result.n_items == 2
    assert _close(result.precision, 1.0)
    assert _close(result.recall, 0.5)


def test_missing_aliases_section_raises(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump({"version": "1"}))
    entities = [_entity("e1", "x")]
    report = score_ingestion_integrity(entities, [])
    with pytest.raises(ValueError, match="expected top-level `aliases:`"):
        score_alias_resolution_against_gold(report, entities, p)


def test_singleton_gold_clusters_are_skipped(tmp_path):
    """A gold entry with no aliases has nothing to test resolution
    against. Should be filtered, leaving no clusters → return None."""
    gold = {
        "aliases": {
            "alone": {"canonical": "Solo", "aliases": []},
        }
    }
    p = tmp_path / "gold.yaml"
    p.write_text(yaml.safe_dump(gold))
    entities = [_entity("e1", "Solo")]
    report = score_ingestion_integrity(entities, [])
    result = score_alias_resolution_against_gold(report, entities, p)
    assert result is None


def test_works_with_good_dog_corpus_ontology_yaml():
    """End-to-end against the actual good-dog-corpus ontology.yaml. Uses
    a synthetic graph that exercises the seeded GSD + APBT alias pairs."""
    ontology_path = (
        Path(__file__).resolve().parent.parent
        / "sme"
        / "corpora"
        / "good-dog-corpus"
        / "ontology.yaml"
    )
    assert ontology_path.exists(), f"ontology not found at {ontology_path}"

    # Synthetic graph reflecting "system canonicalized GSD/Alsatian/etc.
    # via case+whitespace only — semantic aliases not merged."
    entities = [
        _entity("e1", "German Shepherd", "breed"),
        _entity("e2", "GSD", "breed"),
        _entity("e3", "Alsatian", "breed"),
        _entity("e4", "American Pit Bull Terrier", "breed"),
        _entity("e5", "Pit Bull", "breed"),
        _entity("e6", "APBT", "breed"),
    ]
    report = score_ingestion_integrity(entities, [])
    result = score_alias_resolution_against_gold(
        report, entities, ontology_path
    )
    assert result is not None
    # All 6 items in graph, all in gold universe (GSD + APBT clusters).
    # Each is a singleton in predicted (case canonicalization doesn't
    # merge aliases). Each gold cluster has size 3 → recall = 1/3 per item.
    # Precision = 1.0 (every singleton is correctly clustered with itself).
    assert _close(result.precision, 1.0)
    assert _close(result.recall, 1 / 3)
    assert result.n_items == 6
