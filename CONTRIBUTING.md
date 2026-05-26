# Contributing to SME

Thanks for picking this up. This doc is the minimum you need to land
a PR that doesn't surprise anyone. It's short on purpose — when
something isn't covered here, ask in the issue thread rather than
guess. The repo's constitutional principle is **lightweight and
locally runnable** ([rationale](docs/industry_standards_integration.md#constitutional-principle));
most other conventions flow from that.

## Dev setup

```bash
git clone https://github.com/M0nkeyFl0wer/multipass-structural-memory-eval
cd multipass-structural-memory-eval
python -m venv .venv && source .venv/bin/activate
pip install -e ".[topology]"
pip install pytest pytest-cov ruff pyyaml
```

`pip install -e .` gives you the core package; the `[topology]` extra
adds Ripser + python-louvain (needed for Cat 5 gap detection). Adapter-
specific extras (`[ladybugdb]`, `[neo4j]`) only matter if you're
touching that adapter's code path.

## Before you push

CI runs ruff and pytest across Python 3.10 / 3.11 / 3.12. Run them
locally first:

```bash
ruff check .
python -m pytest tests/ -q
```

Both have to pass. Ruff errors are the most common cause of CI red
and they're trivial to fix locally.

If you're iterating on one adapter or one category, scope the test
run:

```bash
python -m pytest tests/test_adapter_contract.py -k "ladybugdb" -v
python -m pytest tests/test_gap_detection.py -v
```

## PRs

**One issue per PR.** Reference it in the description: `Closes #N`.
Smaller PRs land faster — if you're touching three categories, that's
three PRs.

**Stage explicit paths, not `git add -A` or `git add .`** This project
is multi-agent friendly (several contributors run concurrent local AI
sessions); broad adds pick up sibling work and land it in the wrong
commit.

**No AI co-author trailers** in commits, PR descriptions, or code. Tools
don't own what you build with them.

## Standards-first

Before adding a new measurement module, category, or adapter,
check [`docs/industry_standards_integration.md`](docs/industry_standards_integration.md).
The audit catalogues which layers already have battle-tested standards
(SHACL, PROV-O, OpenLineage, MCP-Bench naming, HELM cost-per-correct,
YCSB latency, TREC bounds, BH-FDR) and where SME deliberately rolls
its own.

Two rules of thumb:

1. **Wrap scipy / numpy / networkx; don't reimplement them.** If
   `scipy.stats.bootstrap` already gives you a paired bootstrap CI,
   wrapping it is preferable to a hand-rolled implementation. The
   constitutional principle (lightweight + locally runnable) tolerates
   scipy; it does not tolerate LangChain. Reimplementations carry bugs
   the libraries don't and diverge from published numbers over time.

2. **Cite the methodology in the module docstring.** If you're implementing
   HELM-style cost-per-correct, YCSB latency percentiles, TREC random/
   oracle bounds, or BH-FDR correction, name the paper. Future readers
   shouldn't have to grep the issue thread to find out what convention
   you followed.

When in doubt, propose the integration in an issue first so the
constitutional cost-benefit gets explicit discussion.

## Adapter PRs

If your PR adds, removes, or modifies an `SMEAdapter` subclass:

1. **Parametrize it into the contract testkit.** `tests/test_adapter_contract.py`
   runs every registered adapter through 27 conformance tests. Add
   yours to the parametrize list. Don't ship without — the testkit is
   the abstraction that catches the regression class PR #30 was built
   around.

2. **Implement the required ABC methods.** `ingest_corpus()`, `query()`,
   `get_graph_snapshot()`. The three optional methods (`get_flat_retrieval()`,
   `get_ontology_source()`, `get_harness_manifest()`) have defaults —
   override only when your system has something better than the
   default.

3. **Register in the CLI allowlist.** `sme/cli.py` has an
   `_ADAPTER_REGISTRY` tuple of `_AdapterSpec` entries. Add yours with
   an explicit `accepts: frozenset[str]` listing the kwargs your
   constructor takes. Unknown kwargs are silently dropped — this is
   the structural fix that prevents drop-list drift, but it means a
   forgotten `accepts` entry silently makes your adapter ignore CLI
   flags.

## Corpus PRs

New corpora live under `sme/corpora/<corpus-name>/`. A complete corpus
ships with:

- `README.md` — domain framing, source-discovery pass, design intent
- `ontology.yaml` — entity types, relation types, alias pairs,
  injected defects
- `ontology.py` — executable form for ingestion-time validation
- notes/ — the actual hand-authored content
- `questions.yaml` — annotated questions with `min_hops_in_ground_truth_graph`
- `ground_truth.yaml` — expected sources per question
- `validate.py` — corpus self-check (uniqueness, link integrity, frontmatter)

See `sme/corpora/good-dog-corpus/` for the current reference layout.
Corpora are hand-authored, not LLM-synthesized — at the scale SME
operates (≤100 notes per corpus), the verifiability gain outweighs
the authoring cost.

## Spec edits and new categories

`docs/sme_spec_v8.md` is the source of truth for what each category
measures. **Circulate changes before they land** — open an issue with
the proposed spec text, link the PRs that motivated it, give other
contributors a few days to push back. Spec changes that ship without
review create the kind of methodology drift that makes cross-paper
comparison impossible.

Edits that add or rename sub-statistics (e.g. the Cat 9a.1/9a.2/9a.3
decomposition under discussion in #3) need a deprecation note for the
prior shape so existing readings stay interpretable.

**Proposing a new category** (Cat 10+):

1. File an issue with the methodology source (JEPSEN, MCP-Bench, etc.)
   and a worked-example reading.
2. Discussion thread converges on the metric shape before any code.
3. Spec PR with the category text — separate from any implementation PR.
4. Implementation PR adds the category module, CLI subcommand, tests,
   and an entry in the README's category status table.

## Code quality bars

These apply across the codebase, not just to measurement modules:

- **No `assert` for input validation.** Asserts get stripped under
  `python -O`. Raise `ValueError` / `TypeError` instead. Asserts in
  tests are fine.
- **Deterministic outputs.** Tie-breaks in voting / sorting / ranking
  must be explicit — `Counter.most_common()` and sort-by-single-key on
  ties both produce non-reproducible output. Pin the rule.
- **No non-deterministic test behaviour.** `time.sleep()` in timing
  assertions, float equality, unseeded RNG, sort-by-dict-iteration
  all share the same shape and all cause flake. Use `pytest.approx()`,
  mock clocks, and seeded RNG.
- **Cheap-by-default tests.** If a test takes >1s on a typical CI run
  (`n_bootstrap=10000`, etc.), make it cheap (`n_bootstrap=200`) and
  add a separate slow variant if the larger N is load-bearing for the
  assertion.

## Issues

When you file an issue:

- Title names the thing concretely (`Cat 4c — per-edge-type component
  count is structurally noisy on small edge populations`), not vaguely
  (`improve Cat 4`).
- Include the methodology source if you're proposing a metric shape
  (HELM, YCSB, TREC, JEPSEN, BH-FDR, etc.).
- If you're filing against a specific reading, link the result JSON
  or commit hash that produced it.

## Reviewing PRs

We're a small project. Reviews lead with what worked before flagging
what didn't — substantive disagreement is welcome, nitpicks should be
clearly labelled as such so authors can triage.

Two patterns worth naming explicitly:

- **Copilot-bot review comments are noisy by default.** Treat them as
  a starting point, not a checklist. Some flags (asserts that disappear
  under `-O`, non-deterministic tie-breaks, missing input validation)
  are real and worth fixing; many (dead loggers, "use approx", float
  equality in tests where the result is integer-valued) are noise.
- **When you spot the same shape across three or more PRs**, that's
  usually a signal to build an abstraction (testkit, pre-commit hook,
  shared helper) rather than fixing the same thing per-PR.

## License

MIT. No CLA, no contributor agreement; opening a PR signals you're
licensing the contribution under the same terms as the rest of the
repo.
