"""Tests for sme.corpora.longmemeval.loader.

Uses a small inline fixture (2 records) rather than the upstream
15-90 MB JSON files, so the tests run without any external download.
The fixture's schema mirrors the LongMemEval-cleaned dataset format
documented in upstream README at
https://github.com/xiaowu0162/LongMemEval.
"""
from __future__ import annotations

import json

import pytest

from sme.corpora.longmemeval import (
    LME_TO_SME_CATEGORY,
    LMEQuestion,
    LMESession,
    LMETurn,
    load_questions,
    materialize_sme_corpus,
)


FIXTURE = [
    {
        "question_id": "test_001_temporal",
        "question_type": "temporal-reasoning",
        "question": "What was the first issue I had with my new car after its first service?",
        "answer": "GPS system not functioning correctly",
        "question_date": "2023/04/10 (Mon) 23:07",
        "haystack_session_ids": ["sess_001_a", "sess_001_b", "sess_001_c"],
        "haystack_dates": [
            "2023/03/01 (Wed) 10:00",
            "2023/03/15 (Wed) 14:30",
            "2023/04/05 (Wed) 09:15",
        ],
        "haystack_sessions": [
            [
                {"role": "user", "content": "I just bought a new car."},
                {"role": "assistant", "content": "Congrats! What model?"},
            ],
            [
                {
                    "role": "user",
                    "content": "Took the car for its first service yesterday.",
                    "has_answer": True,
                },
                {
                    "role": "assistant",
                    "content": "How did it go?",
                },
                {
                    "role": "user",
                    "content": "GPS isn't working right since they updated firmware.",
                    "has_answer": True,
                },
            ],
            [
                {"role": "user", "content": "Unrelated chat about coffee."},
                {"role": "assistant", "content": "I prefer tea."},
            ],
        ],
        "answer_session_ids": ["sess_001_b"],
    },
    {
        "question_id": "test_002_abstain_abs",
        "question_type": "single-session-user",
        "question": "What did I say about my submarine purchase?",
        "answer": "abstain",
        "question_date": "2023/05/01 (Mon) 09:00",
        "haystack_session_ids": ["sess_002_a"],
        "haystack_dates": ["2023/04/20 (Thu) 12:00"],
        "haystack_sessions": [
            [
                {"role": "user", "content": "I bought a kayak last week."},
                {"role": "assistant", "content": "Sounds fun!"},
            ],
        ],
        "answer_session_ids": [],
    },
]


@pytest.fixture
def fixture_path(tmp_path):
    p = tmp_path / "longmemeval_oracle_fixture.json"
    p.write_text(json.dumps(FIXTURE))
    return p


def test_load_questions_yields_dataclasses(fixture_path):
    questions = list(load_questions(fixture_path))
    assert len(questions) == 2
    assert all(isinstance(q, LMEQuestion) for q in questions)


def test_temporal_record_parses_fully(fixture_path):
    q = next(load_questions(fixture_path))
    assert q.question_id == "test_001_temporal"
    assert q.question_type == "temporal-reasoning"
    assert q.is_abstention is False
    assert q.sme_category == "cat_6"
    assert q.answer_session_ids == ["sess_001_b"]
    # 3 haystack sessions, 2 turns + 3 turns + 2 turns
    assert len(q.haystack_sessions) == 3
    assert all(isinstance(s, LMESession) for s in q.haystack_sessions)
    assert all(isinstance(t, LMETurn) for s in q.haystack_sessions for t in s.turns)


def test_abstention_record_detected_by_suffix(fixture_path):
    q = list(load_questions(fixture_path))[1]
    assert q.is_abstention is True
    assert q.sme_category == "cat_1_negative"


def test_evidence_session_level(fixture_path):
    q = next(load_questions(fixture_path))
    assert q.expected_sources_session_level() == ["sess_001_b"]


def test_evidence_turn_level_extracts_has_answer_turns(fixture_path):
    q = next(load_questions(fixture_path))
    turns = q.expected_sources_turn_level()
    assert len(turns) == 2
    assert "first service yesterday" in turns[0]
    assert "GPS isn't working right" in turns[1]


def test_to_sme_question_shape(fixture_path):
    q = next(load_questions(fixture_path))
    sme_q = q.to_sme_question()
    assert sme_q["id"] == "test_001_temporal"
    assert sme_q["sme_category"] == "cat_6"
    assert sme_q["expected_sources"] == ["sess_001_b"]
    assert sme_q["gold_answer"] == "GPS system not functioning correctly"
    assert sme_q["longmemeval"]["is_abstention"] is False
    assert sme_q["longmemeval"]["question_type"] == "temporal-reasoning"


def test_unknown_question_type_marked_unmapped(tmp_path):
    weird = [
        {
            **FIXTURE[0],
            "question_id": "weird_001",
            "question_type": "made-up-category",
        }
    ]
    p = tmp_path / "weird.json"
    p.write_text(json.dumps(weird))
    q = next(load_questions(p))
    assert q.sme_category == "unmapped"


def test_load_questions_rejects_non_list_top_level(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"records": []}))
    with pytest.raises(ValueError, match="expected top-level JSON array"):
        list(load_questions(bad))


def test_lme_to_sme_category_includes_all_documented_types():
    """Every type in LME_TO_SME_CATEGORY (except `abstention`, which is
    derived from the `_abs` suffix) is one of the upstream-documented
    LME_QUESTION_TYPES."""
    from sme.corpora.longmemeval.loader import LME_QUESTION_TYPES

    derived_types = set(LME_TO_SME_CATEGORY) - {"abstention"}
    assert derived_types == LME_QUESTION_TYPES


def test_materialize_writes_per_question_vault(fixture_path, tmp_path):
    out = tmp_path / "lme_corpus"
    summary = materialize_sme_corpus(load_questions(fixture_path), out)
    assert summary["questions_count"] == 2
    vault = out / "vault"
    assert vault.is_dir()
    # Per-question subdirs
    assert (vault / "test_001_temporal").is_dir()
    assert (vault / "test_002_abstain_abs").is_dir()
    # Each session is one .md file
    sessions = sorted((vault / "test_001_temporal").glob("*.md"))
    assert len(sessions) == 3
    # Frontmatter contains expected fields
    sample = (vault / "test_001_temporal" / "sess_001_b.md").read_text()
    assert "session_id: sess_001_b" in sample
    assert "is_evidence: true" in sample
    assert "<!-- evidence -->" in sample  # turn-level marker


def test_materialize_respects_max_questions(fixture_path, tmp_path):
    out = tmp_path / "lme_corpus"
    summary = materialize_sme_corpus(
        load_questions(fixture_path), out, max_questions=1
    )
    assert summary["questions_count"] == 1
    assert (out / "vault" / "test_001_temporal").is_dir()
    assert not (out / "vault" / "test_002_abstain_abs").exists()


def test_materialize_writes_questions_yaml(fixture_path, tmp_path):
    import yaml

    out = tmp_path / "lme_corpus"
    materialize_sme_corpus(load_questions(fixture_path), out)
    qy = yaml.safe_load((out / "questions.yaml").read_text())
    assert qy["version"] == "longmemeval-oracle-v1"
    assert "github.com/xiaowu0162/LongMemEval" in qy["source"]
    assert len(qy["questions"]) == 2
    assert qy["questions"][0]["id"] == "test_001_temporal"
