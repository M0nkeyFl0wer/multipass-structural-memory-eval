"""Load LoCoMo JSON records into SME-shape Python objects.

Schema reference: docs/related_work/locomo-and-memorybench.md
(ACL 2024, Maharana et al., arXiv 2402.17753).

Since the upstream dataset is not available in this repo, the loader
is written against the documented shape and is defensive to missing
keys and shape variations.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOCOMO_QUESTION_TYPES = {
    "single-hop",
    "multi-hop",
    "temporal",
    "open-domain",
    "adversarial",
}

# Mapping from LoCoMo question types to SME categories.
LOCOMO_TO_SME_CATEGORY = {
    "single-hop": "cat_1",
    "multi-hop": "cat_2c",
    "temporal": "cat_6",
    "open-domain": "cat_1",
    "adversarial": "cat_1_negative",
}


@dataclass(frozen=True)
class LOCOMOTurn:
    """One turn within a LoCoMo dialogue."""

    role: str
    content: str
    session_id: str = ""
    turn_index: int = 0


@dataclass(frozen=True)
class LOCOMOSession:
    """One chat session in a LoCoMo dialogue."""

    session_id: str
    turns: list[LOCOMOTurn] = field(default_factory=list)


@dataclass(frozen=True)
class LOCOMOQuestion:
    """One LoCoMo evaluation instance, parsed from JSON."""

    question_id: str
    question_type: str
    question: str
    answer: str
    dialogue_id: str
    session_id: str
    turn_index: int
    expected_sources: list[str] = field(default_factory=list)
    requires_image: bool = False
    dialogue_turns: list[LOCOMOTurn] = field(default_factory=list)
    sme_category: str = ""

    def to_sme_question(self) -> dict[str, Any]:
        """Render as a single SME ``questions.yaml`` entry."""
        return {
            "id": self.question_id,
            "text": self.question,
            "expected_sources": list(self.expected_sources),
            "gold_answer": self.answer,
            "locomo": {
                "question_type": self.question_type,
                "dialogue_id": self.dialogue_id,
                "session_id": self.session_id,
                "turn_index": self.turn_index,
                "requires_image": self.requires_image,
            },
            "sme_category": self.sme_category,
        }


def _is_image_question(record: dict) -> bool:
    """Heuristic: mark questions that depend on images."""
    if record.get("requires_image") is True:
        return True
    if record.get("image_url") not in (None, ""):
        return True
    if record.get("image") not in (None, ""):
        return True
    if record.get("multi_modal") is True:
        return True
    return False


def _parse_record(record: dict) -> LOCOMOQuestion:
    qid = str(record.get("question_id", ""))
    qtype = str(record.get("question_type", ""))
    sme_cat = LOCOMO_TO_SME_CATEGORY.get(qtype, "unmapped")

    turns: list[LOCOMOTurn] = []
    for raw_turn in record.get("dialogue_turns", []):
        if not isinstance(raw_turn, dict):
            continue
        turns.append(
            LOCOMOTurn(
                role=str(raw_turn.get("role", "")),
                content=str(raw_turn.get("content", "")),
                session_id=str(raw_turn.get("session_id", "")),
                turn_index=int(raw_turn.get("turn_index", 0)),
            )
        )

    return LOCOMOQuestion(
        question_id=qid,
        question_type=qtype,
        question=str(record.get("question", "")),
        answer=str(record.get("answer", "")),
        dialogue_id=str(record.get("dialogue_id", "")),
        session_id=str(record.get("session_id", "")),
        turn_index=int(record.get("turn_index", 0)),
        expected_sources=list(record.get("expected_sources", [])),
        requires_image=_is_image_question(record),
        dialogue_turns=turns,
        sme_category=sme_cat,
    )


def load_locomo_questions(
    path: str | Path, *, skip_image_questions: bool = True
) -> list[LOCOMOQuestion]:
    """Parse a LoCoMo JSON file and return a list of `LOCOMOQuestion` records.

    Args:
        path: Path to the LoCoMo QA JSON file. Expected top-level shape
            is a list of question records, or a dict with a ``questions``
            key.
        skip_image_questions: If ``True``, omit questions that depend on
            images from the returned list.

    Returns:
        List of parsed ``LOCOMOQuestion`` instances.
    """
    path = Path(path)
    raw = json.loads(path.read_text())

    if isinstance(raw, dict):
        records = raw.get("questions", [])
        if not isinstance(records, list):
            raise ValueError(
                f"{path}: expected 'questions' to be a list, got "
                f"{type(records).__name__}"
            )
    elif isinstance(raw, list):
        records = raw
    else:
        raise ValueError(
            f"{path}: expected top-level JSON array or object, got "
            f"{type(raw).__name__}"
        )

    questions: list[LOCOMOQuestion] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        q = _parse_record(record)
        if q.requires_image and skip_image_questions:
            continue
        questions.append(q)
    return questions


def _render_session_md(session: LOCOMOSession, question: LOCOMOQuestion) -> str:
    """Render one session as a markdown file with frontmatter."""
    lines = [
        "---",
        f"session_id: {session.session_id}",
        f"dialogue_id: {question.dialogue_id}",
        f"question_id: {question.question_id}",
        "source: locomo",
        "---",
        "",
        f"# Session {session.session_id}",
        "",
    ]
    for turn in session.turns:
        lines.append(f"## {turn.role}")
        lines.append("")
        lines.append(turn.content)
        lines.append("")
    return "\n".join(lines)


def materialize_locomo_corpus(
    questions: list[LOCOMOQuestion], out_dir: Path | str
) -> Path:
    """Write a per-question SME-shape corpus to disk.

    Each LoCoMo question gets its own subdirectory under
    ``<out_dir>/vault/<question_id>/`` containing one markdown file
    per session derived from ``dialogue_turns``.

    ``<out_dir>/questions.yaml`` is written as a single index covering
    all materialized questions.

    Args:
        questions: list of ``LOCOMOQuestion`` records.
        out_dir: where to write ``vault/`` and ``questions.yaml``.

    Returns:
        The output directory path.
    """
    out_dir = Path(out_dir)
    vault_dir = out_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)

    questions_yaml: list[dict[str, Any]] = []
    for q in questions:
        q_dir = vault_dir / q.question_id
        q_dir.mkdir(exist_ok=True)

        sessions: dict[str, LOCOMOSession] = {}
        for turn in q.dialogue_turns:
            sid = turn.session_id or "unknown"
            if sid not in sessions:
                sessions[sid] = LOCOMOSession(session_id=sid)
            sessions[sid].turns.append(turn)

        if not sessions:
            stub = q_dir / "stub.md"
            stub.write_text(
                f"---\n"
                f"dialogue_id: {q.dialogue_id}\n"
                f"question_id: {q.question_id}\n"
                f"source: locomo\n"
                f"---\n\n"
                f"# Stub for {q.question_id}\n\n"
                f"No dialogue turns provided in source record.\n"
            )
        else:
            for session in sessions.values():
                note_path = q_dir / f"{session.session_id}.md"
                note_path.write_text(_render_session_md(session, q))

        questions_yaml.append(q.to_sme_question())

    # Defer import so the loader module itself doesn't pull pyyaml
    # unless materialization is actually requested.
    import yaml

    (out_dir / "questions.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "locomo-v1",
                "source": "https://github.com/snap-research/locomo",
                "license": "Apache-2.0 (Maharana et al., ACL 2024)",
                "questions": questions_yaml,
            },
            sort_keys=False,
            allow_unicode=True,
        )
    )

    return out_dir
