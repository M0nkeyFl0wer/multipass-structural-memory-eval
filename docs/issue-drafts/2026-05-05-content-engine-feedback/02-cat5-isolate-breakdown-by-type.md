**Title:** Cat 5 — break down isolate count by node type

**Where this came from.** Same pre-rebuild baseline pass. Cat 5
flagged "Isolates: 17.8% of entities have no edges (42 of 236)
[concerning]" on a content-engine KG. The reading is correct and
the band is right (`> ~5%` is concerning for KGs). What I couldn't
do was act on it.

**The gap.** "42 orphans" doesn't tell me where to look. The
actionable forms — *which* extractor / *which* sync produced them —
require knowing the type breakdown. In my case the choices were:

- 42 orphan `Topic` nodes → fix `_ensure_topic_node` callers
- 42 orphan `Species`/`Zone`/`Community` nodes → fix the registry
  sync that materializes these nodes ahead of any reference
- 42 orphan `Persona` nodes → wholly different bug class

Without the breakdown I had to drop into Cypher again:

```cypher
MATCH (n) WHERE NOT (n)--()
RETURN labels(n)[0] AS t, count(*) AS c ORDER BY c DESC
```

That single query is what makes the metric actionable.

**Proposal.** Extend the Cat 5 metric block:

```
Isolated nodes:    42 (17.8%)
  by type:
    Species         18  (42.9% of isolates)
    Zone            12
    Community        8
    Topic            4
```

JSON additive shape:

```json
{
  "metric": "isolated_nodes",
  "count": 42,
  "fraction": 0.178,
  "by_type": {"Species": 18, "Zone": 12, "Community": 8, "Topic": 4}
}
```

Reading text can append a typed pointer:

> Top isolate types: `Species` (18), `Zone` (12). If these come from
> a registry sync that materializes nodes before any content
> references them, prune at sync or only materialize on first
> reference.

**Why this is small.** Same shape as the existing connectivity
calculation; just `groupby(label)` on the isolate set rather than a
bare count. SME already calls `get_graph_snapshot()` which returns
typed entities.

**Optional companion.** Same breakdown for the *largest component*
inverse — "the 5 entity types that dominate the largest component"
— would be useful for understanding what the connected core actually
contains. Lower priority; flagging here in case it's a one-line add
in the same patch.
