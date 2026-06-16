**Title:** Cat 5 — surface representative cycles for Betti-1 holes

**Where this came from.** Same baseline. Cat 5 reported:

```
Betti-1 (largest):     188
H1 max persistence:    1.000
● Structural holes: 188 persistent H1 feature(s) on the largest
  component (max persistence 1.00 hops). Loops in the knowledge
  core that don't fill in under the Vietoris-Rips filtration.
  Long-persistence H1 bars usually mark real gaps where an
  enriching edge would close the loop.
```

Reading: "188 H1 features" is correctly computed and the
interpretation text is right — these are real loops where an
edge would close a gap. But there are 188 of them and the
metric doesn't tell me where any of them *are*. To act on it I'd
need to compute representative cycles myself.

**Proposal.** When `--betti` (or whatever current flag triggers H1
computation) is set, surface the top-K longest-persistence
representative cycles in the report:

```
Top H1 representative cycles (by persistence, descending):
  cycle 1  (persistence 1.00, length 4 hops):
    Topic:foo → ResearchDoc:bar → Topic:baz → Topic:foo
  cycle 2  (persistence 1.00, length 3 hops):
    Persona:p1 → Content:c1 → Persona:p2 → Persona:p1
  cycle 3  ...
```

JSON additive shape:

```json
{
  "h1_features": 188,
  "max_persistence": 1.0,
  "representative_cycles": [
    {"persistence": 1.0, "length": 4,
     "nodes": ["Topic:foo", "ResearchDoc:bar", "Topic:baz", "Topic:foo"]},
    ...
  ]
}
```

K = 5 by default; configurable.

**Why this is small.** Ripser already returns persistence pairs
with birth/death simplices when run with the right flag
(`do_cocycles=True` in ripser.py, or the equivalent in
ripser-plusplus). The representative-cycle extraction is a
one-time cost during the Betti computation, not a separate pass.
SME already imports ripser-equivalent under the `ripser` skill /
optional dependency, so the data is *there*; it's just not
surfaced.

**Why this matters.** On a 194-node component, "188 H1 features"
without representatives is too dense to act on. With three
representatives, an operator can immediately see the shape of
the gaps and propose closing edges. This converts a research-feel
metric into an engineering-feel one.

**Adapter compatibility.** No adapter changes — this is purely
post-processing of the snapshot SME already builds.

**Edge case.** Some H1 features at persistence 1.0 are essentially
"any cycle" — a long thin loop will produce many such bars. Show
length distribution if K representatives all sit at the same
persistence so the operator can see they're not redundant
descriptions of the same hole.
