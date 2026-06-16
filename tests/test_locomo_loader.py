"""Tests for sme.corpora.locomo_loader.

Uses a small inline fixture (2 questions, 1 dialogue) rather than the
upstream dataset, so the tests run without any external download.
The fixture's schema mirrors the LoCoMo QA file shape documented in
``docs/related_work/locomo-and-memorybench.md``.
"""
from __future__ import annotations

import json

import pytest
import yaml

from sme.corpora.locomo_loader import (
    LOCOMO_TO_SME_CATEGORY,
    LOCOMOQuestion,
    load_locomo_questions,
    materialize_locomo_corpus,
)


FIXTURE = [
    {
        "question_id": "locomo_q1",
        "question_type": "single-hop",
        "question": "What is Alice's favorite color?",
        "answer": "Blue",
        "dialogue_id": "dlg_1",
        "session_id": "sess_1",
        "turn_index": 5,
        "expected_sources": ["sess_1_turn_3"],
        "dialogue_turns": [
            {
                "role": "user",
                "content": "Hi I'm Alice.",
                "session_id": "sess_1",
                "turn_index": 1,
            },
            {
                "role": "assistant",
                "content": "Hello Alice.",
                "session_id": "sess_1",
                "turn_index": 2,
            },
            {
                "role": "user",
                "content": "My favorite color is blue.",
                "session_id": "sess_1",
                "turn_index": 3,
            },
            {
                "role": "assistant",
                "content": "Nice.",
                "session_id": "sess_1",
                "turn_index": 4,
            },
        ],
    },
    {
        "question_id": "locomo_q2",
        "question_type": "adversarial",
        "question": "What did Alice say about her submarine?",
        "answer": "N/A",
        "dialogue_id": "dlg_1",
        "session_id": "sess_1",
        "turn_index": 6,
        "expected_sources": [],
    },
]


@pytest.fixture
def fixture_path(tmp_path):
    p = tmp_path / "locomo_fixture.json"
    p.write_text(json.dumps(FIXTURE))
    return p


def test_load_questions_returns_list(fixture_path):
    questions = load_locomo_questions(fixture_path)
    assert isinstance(questions, list)
    assert len(questions) == 2
    assert all(isinstance(q, LOCOMOQuestion) for q in questions)


def test_field_mapping(fixture_path):
    questions = load_locomo_questions(fixture_path)
    q1 = questions[0]
    assert q1.question_id == "locomo_q1"
    assert q1.question_type == "single-hop"
    assert q1.question == "What is Alice's favorite color?"
    assert q1.answer == "Blue"
    assert q1.dialogue_id == "dlg_1"
    assert q1.session_id == "sess_1"
    assert q1.turn_index == 5
    assert q1.expected_sources == ["sess_1_turn_3"]
    assert len(q1.dialogue_turns) == 4


def test_missing_key_handling(tmp_path):
    partial = [
        {
            "question_id": "partial_q",
            "question_type": "multi-hop",
            "question": "Missing some fields?",
            # missing answer, dialogue_id, session_id, turn_index
        }
    ]
    p = tmp_path / "partial.json"
    p.write_text(json.dumps(partial))
    q = load_locomo_questions(p)[0]
    assert q.question_id == "partial_q"
    assert q.answer == ""
    assert q.dialogue_id == ""
    assert q.session_id == ""
    assert q.turn_index == 0
    assert q.expected_sources == []
    assert q.dialogue_turns == []


def test_image_question_flag(tmp_path):
    img_fixture = [
        {
            "question_id": "img_q",
            "question_type": "single-hop",
            "question": "Describe the image.",
            "answer": "A cat",
            "dialogue_id": "dlg_1",
            "session_id": "sess_1",
            "turn_index": 7,
            "image_url": "http://example.com/cat.png",
        }
    ]
    p = tmp_path / "img.json"
    p.write_text(json.dumps(img_fixture))

    # With skip_image_questions=True (default), the image question is omitted.
    skipped = load_locomo_questions(p, skip_image_questions=True)
    assert len(skipped) == 0

    # With skip_image_questions=False, it is present and flagged.
    kept = load_locomo_questions(p, skip_image_questions=False)
    assert len(kept) == 1
    assert kept[0].requires_image is True


def test_category_mapping(fixture_path):
    questions = load_locomo_questions(fixture_path)
    q1, q2 = questions
    assert q1.sme_category == "cat_1"  # single-hop
    assert q2.sme_category == "cat_1_negative"  # adversarial


def test_category_mapping_all_types():
    """Every mapped type resolves to the expected SME category."""
    from sme.corpora.locomo_loader import _parse_record

    for qtype, expected in LOCOMO_TO_SME_CATEGORY.items():
        record = {
            "question_id": f"q_{qtype}",
            "question_type": qtype,
            "question": "test",
            "answer": "test",
            "dialogue_id": "d1",
            "session_id": "s1",
            "turn_index": 1,
        }
        q = _parse_record(record)
        assert q.sme_category == expected


def test_materialize_writes_files_correctly(fixture_path, tmp_path):
    questions = load_locomo_questions(fixture_path)
    out = materialize_locomo_corpus(questions, tmp_path / "locomo_corpus")
    assert out.is_dir()
    vault = out / "vault"
    assert vault.is_dir()

    # q1 has dialogue turns → one session file
    q1_dir = vault / "locomo_q1"
    assert q1_dir.is_dir()
    session_file = q1_dir / "sess_1.md"
    assert session_file.exists()
    text = session_file.read_text()
    assert "source: locomo" in text
    assert "Hi I'm Alice." in text
    assert "# Session sess_1" in text

    # q2 has no dialogue turns → stub file
    q2_dir = vault / "locomo_q2"
    assert q2_dir.is_dir()
    stub = q2_dir / "stub.md"
    assert stub.exists()
    stub_text = stub.read_text()
    assert "No dialogue turns provided" in stub_text
    assert "source: locomo" in stub_text


def test_materialize_writes_questions_yaml(fixture_path, tmp_path):
    questions = load_locomo_questions(fixture_path)
    out = materialize_locomo_corpus(questions, tmp_path / "locomo_corpus")
    qy_path = out / "questions.yaml"
    assert qy_path.exists()
    data = yaml.safe_load(qy_path.read_text())
    assert data["version"] == "locomo-v1"
    assert "github.com/snap-research/locomo" in data["source"]
    assert len(data["questions"]) == 2
    assert data["questions"][0]["id"] == "locomo_q1"
    assert data["questions"][0]["sme_category"] == "cat_1"
    assert data["questions"][1]["id"] == "locomo_q2"
    assert data["questions"][1]["sme_category"] == "cat_1_negative"


def test_load_questions_rejects_non_list_non_dict(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps("just a string"))
    with pytest.raises(ValueError, match="expected top-level JSON array or object"):
        load_locomo_questions(bad)


def test_load_questions_rejects_dict_without_list_questions(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"questions": "not a list"}))
    with pytest.raises(ValueError, match="expected 'questions' to be a list"):
        load_locomo_questions(bad)
