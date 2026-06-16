# Upstream issue drafts — content-engine baseline pass, 2026-05-05

These drafts came out of running `sme-eval check` (Cat 4 + Cat 5) and
`analyze` against an unrelated content-engine KG I'm maintaining,
captured as a pre-rebuild baseline. The KG:

- LadybugDB 0.15.3, declared schema, 19 node tables / 34 rel tables
- ~230 nodes / ~410 edges at baseline
- Schema-agnostic `ladybug` adapter with `--auto-discover`

SME caught a real bug (canonical collisions in one node table) and
gave actionable readings on connectivity / isolate fraction / edge
entropy. Three classes of follow-up surfaced in the process — items
SME *already computes or is one query away from* that would turn the
existing readings from "interesting" into "fix this and re-run".

The issues below are independent and small. Each one is:

- a workflow note (what the operator was trying to learn)
- the gap (what the current report says vs. what's needed)
- a proposal (what to add, with a sketch of the shape)

No client/project data in any of them.

## Index

- [01-cat4-edge-counts-per-collision.md](01-cat4-edge-counts-per-collision.md)
- [02-cat5-isolate-breakdown-by-type.md](02-cat5-isolate-breakdown-by-type.md)
- [03-cat4c-weight-per-edge-type-components.md](03-cat4c-weight-per-edge-type-components.md)
- [04-cat5-representative-cycles-for-betti1.md](04-cat5-representative-cycles-for-betti1.md)
- [05-cat5-per-component-shape-summary.md](05-cat5-per-component-shape-summary.md)
