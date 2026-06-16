**Title:** Cat 4c — per-edge-type component count is structurally noisy on small edge populations

**Where this came from.** Same baseline. The Cat 4c monoculture
signal section reported, on a ~230-node graph (placeholder labels;
shape is what matters):

```
Per-edge-type component count (4c monoculture signal):
  REL_RARE_A      ~N-1 components   ← table has 1 edge total
  REL_RARE_B      ~N-2 components   ← table has 5 edges
  REL_RARE_C      ~N-3 components   ← table has 11 edges
  ...
  REL_DENSE_X      130 components   ← table has 100+ edges
  REL_DENSE_Y      128 components   ← table has 100+ edges
```

**The issue.** When an edge type has *N_edges* < ~10 over a
*N_nodes* graph, "component count when only this edge type is
considered" is dominated by the singleton nodes. A type with 1 edge
across 236 nodes will always report ≈ 235 components — that's
trivially `N_nodes - 1`, and tells me nothing about whether the
edge type is fragmenting the graph. The actually-monocultural signal
(few large connected pieces vs many small ones) only emerges when
the edge population is non-trivial.

This makes the table sort by an artifact of edge-type *rarity*
rather than monoculture, which is the opposite of the intent.

**Proposal.** Two small changes:

1. **Filter or annotate by edge count.** Either hide types below a
   threshold (e.g. < 5 edges) from the headline display, or sort by
   a normalized metric like:
   ```
   monoculture_score = components_among_endpoints /
                       (number_of_endpoint_nodes_for_this_type)
   ```
   so single-edge types report a small score (1 component over 2
   endpoints = 0.5) instead of a large absolute one.

2. **Show edge count alongside component count** so the reader can
   see when a row is dominated by singletons:

   ```
   Per-edge-type component count (4c monoculture signal):
     REL_DENSE_X        130 components  (~100 edges, ~90 endpoint nodes)
     REL_DENSE_Y        128 components  (~100 edges, ~110 endpoint nodes)
     REL_MID_Z          ~~~              (~70 edges, ...)
     ...
   ```

The interpretation note in the spec stays the same — the per-edge
view is about whether removing a type splits the graph — but the
ranking starts surfacing types where the answer is meaningful.

**Why this matters.** On the same baseline, the *real* signal —
the two dense types that together form most of the connected
fabric — was buried under several rows of trivially-high
component counts driven by tiny edge populations. With the
fix, the operator's eye lands on the rows where the metric actually
encodes something.

**Lower-effort alternative if a refactor is heavy.** Just add the
`edge count` column. The current ranking stays; the noise becomes
self-evident.
