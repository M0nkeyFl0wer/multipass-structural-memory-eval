**Title:** Cat 5 — add per-component shape summary

**Where this came from.** Same baseline. Cat 5 reported:

```
Components:            43
Largest component:     194  (82.2% of nodes)
Isolated nodes:        42
Bridges:               37
```

Reading those numbers: 43 components, one of which is the 194-node
core, and 42 of the rest are isolates. That accounts for
194 + 42 = 236 of 236 nodes — meaning the remaining 0 components
have... 0 nodes? Off by one somewhere; let me re-derive: 43 - 1
(largest) - ? singletons = some number of mid components. The
math has to work out, but the summary doesn't make it easy.

**The gap.** With 43 components I want a one-glance distribution:

- how many singletons (component size 1)
- how many small (2-5)
- how many mid (6-20)
- how many large (>20)

— and for the non-trivial components, what entity types dominate
each one. This is the shape data that tells me whether the
"non-largest" components are noise (a stray pair of nodes left
over from a bad sync) or substantive (an unconnected subdomain
the extractor missed).

**Proposal.** Replace / augment the bare component count with a
distribution:

```
Components:            43
  by size:
    1   (singleton):   42
    2–5:                0
    6–20:               0
    > 20  (large):      1   ← the 194-node core
  largest component:   194  (82.2%)
```

For non-trivial components (size ≥ 2), surface dominant types:

```
Non-trivial components (≥ 2 nodes):
  comp_a   194 nodes — top types: TypeP (~50%), TypeQ (~10%), TypeR (~4%), …
  (only the largest in this run; would list each ≥ 2)
```

JSON additive:

```json
{
  "components": 43,
  "size_distribution": {"1": 42, "2-5": 0, "6-20": 0, ">20": 1},
  "non_trivial": [
    {"id": "c_001", "size": 194,
     "type_distribution": {"TypeP": 108, "TypeQ": 21, "TypeR": 8}}
  ]
}
```

**Reading update.** When all non-singleton mass is in one component,
say so explicitly — that's the diagnostic the operator wants:

> All 194 connected nodes are in one component. The other 42 are
> isolates. There is no mid-sized "almost connected" subgraph.

vs. the contrasting case:

> 4 components in the 6-20 band — these are likely subdomains the
> linker isn't bridging. Listed by dominant type below.

**Why this matters.** Right now the operator has to do the
"194 + 42 = 236, so the other 0 must be...?" math in their head
to realize the structure is degenerate (one core + dust). The
distribution makes that visible at a glance.

**Why this is small.** SME already groups nodes into components
during structural-health computation. This just exposes the
distribution and (optionally) the type-counts per non-trivial
component.
