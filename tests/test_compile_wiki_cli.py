"""compile-wiki --dry-run / --json.

--dry-run must be safe to hand to an automated planner: no LLM call, no API
key read, nothing written. Its plan must agree with what a real run then does.
"""

from __future__ import annotations

import json
from pathlib import Path

from sme.cli import main
from sme.conditions.wiki_compiler import compile_vault, plan_compile
from tests.test_wiki_compiler import _FakeLLM, _write


def _vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    _write(v / "a.md", "# A\nalpha")
    _write(v / "sub" / "b.md", "# B\nbeta")
    return v


def test_dry_run_writes_nothing_and_builds_no_client(tmp_path, monkeypatch):
    v, out = _vault(tmp_path), tmp_path / "out"

    # Any attempt to build a real client would be a key read; make it fatal.
    import sme.eval.llm_clients as clients
    def _boom(*a, **k):
        raise AssertionError("dry run built an LLM client")
    for name in ("OpenAILLMClient", "AnthropicLLMClient", "OpenRouterLLMClient"):
        monkeypatch.setattr(clients, name, _boom)

    rc = main(["compile-wiki", "--vault", str(v), "--output", str(out),
               "--llm-provider", "openai", "--dry-run", "--json", str(tmp_path / "plan.json")])
    assert rc == 0
    assert not out.exists()  # not even the directory
    plan = json.loads((tmp_path / "plan.json").read_text())
    assert plan["dry_run"] is True
    assert sorted(plan["would_compile"]) == ["a.md", "sub/b.md"]
    assert plan["llm_calls"] == 3  # two articles + the index


def test_plan_matches_a_real_run_then_sees_the_cache(tmp_path):
    v, out = _vault(tmp_path), tmp_path / "out"
    llm = _FakeLLM()
    report = compile_vault(v, out, llm)
    assert len(llm.prompts) == plan_compile(v, tmp_path / "fresh")["llm_calls"]
    assert report.n_compiled == 2

    # Second look: everything cached, only the index call remains.
    plan = plan_compile(v, out)
    assert plan["would_compile"] == [] and sorted(plan["would_skip_cached"]) == ["a.md", "sub/b.md"]

    # Edit one note: the plan names exactly that one.
    (v / "a.md").write_text("# A\nchanged")
    assert plan_compile(v, out)["would_compile"] == ["a.md"]
    assert sorted(plan_compile(v, out, force=True)["would_compile"]) == ["a.md", "sub/b.md"]


def test_real_run_json_report(tmp_path):
    v, out, rep = _vault(tmp_path), tmp_path / "out", tmp_path / "report.json"
    assert main(["compile-wiki", "--vault", str(v), "--output", str(out),
                 "--json", str(rep)]) == 0  # stub provider: no network
    data = json.loads(rep.read_text())
    assert (data["n_notes"], data["n_compiled"], data["n_failed"]) == (2, 2, 0)
    assert data["failures"] == [] and data["output_dir"] == str(out)
    assert data["llm_provider"] == "stub" and data["llm_model"] is None
