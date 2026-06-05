**Title:** Cat 4 — surface edge counts per duplicate ID in canonical collision report

**Where this came from.** Running `sme-eval check --adapter ladybug
--auto-discover` against a content-engine KG (LadybugDB, declared
schema, ~230 nodes) as a pre-rebuild baseline. SME flagged 8
canonical-collision pairs in one node type. The collisions were
useful — they pointed straight at a real `_ensure_<type>_node()`
canonicalization bug where two ID forms (a numbered prefix and the
short form, e.g. `01-foo` vs `foo`) created split nodes.

**The gap.** Current Cat 4 output for a collision pair:

```
[NodeType] "Display Name", "Display Name" → 2 distinct IDs
```

That tells me two IDs exist for the same canonical key, but not which
ID is the "real" one — the one I want to keep when I write the
dedup migration. To find that I had to drop into Cypher and query
edge degree per ID:

```cypher
MATCH (p:NodeType {id: $sid}) OPTIONAL MATCH (p)-[r]-()
RETURN count(DISTINCT r) AS deg
```

That answer tells me which is the populated node (deg=18) and which
is the rump duplicate (deg=2). Without it, I either keep the wrong
side or have to spelunk the graph.

**Proposal.** Extend the collision row in the report and JSON:

```
[NodeType] "Display Name" → 2 distinct IDs:
              01-foo  (deg=18)   ← keep
              foo     (deg=2)
```

JSON shape (additive — `id_counts` stays):

```json
{
  "node_type": "NodeType",
  "canonical_key": "display name",
  "ids": [
    {"id": "01-foo", "degree": 18, "in_degree": 6, "out_degree": 12},
    {"id": "foo", "degree": 2, "in_degree": 0, "out_degree": 2}
  ]
}
```

The "keep" hint can be heuristic ("highest degree") and explicit in
the human-readable line; consumers that want to override pick from
the JSON.

**Why this is small.** SME already does the
`MATCH-OPTIONAL-MATCH-count` pattern in Cat 5's structural-health
pass. It would just hoist the per-ID degree query into the Cat 4
collision builder. No new categories, no new spec text — the
existing Cat 4 spec ("name AND entity_type") already implies the
report should be operator-actionable, this just makes it so.

**Adapter compatibility.** The `LadybugDBAdapter` already exposes
the snapshot. For adapters that don't return edges (rare; Cat 5
already requires this), fall back to printing without the degree
column.
