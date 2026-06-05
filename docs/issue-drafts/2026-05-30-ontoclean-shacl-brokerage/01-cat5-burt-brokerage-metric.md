**Title:** Cat 5 — add Burt brokerage (constraint / effective size) + rename "structural holes" to "topological holes"

**Where this came from.** A method-coverage review of the topology
layer. Cat 5 and the topology analyzer already compute every
*ingredient* of a brokerage analysis — Louvain communities
(`TopologyAnalyzer.community_structure`), `inter_community_ratio`,
structural bridges (`_structural_bridges` → `nx.bridges`), and degree
stats — but never ask the question those ingredients set up:

> **Which entities broker across communities, and how concentrated is
> that brokerage?**

That is precisely Ronald Burt's *structural holes* (1992): a
structural hole is the absence of a tie between two of a node's
neighbours, and the node spanning it holds a **brokerage** position.
It is a *local-redundancy* read, distinct from the two things SME
already has:

- a **bridge** (`nx.bridges`) is a *global cut* edge — remove it and
  the component count rises. Burt brokerage exists even when no global
  disconnection results.
- a **topological hole** (Cat 5 Betti-1 / H1) is a cycle that bounds
  no 2-cell — a TDA feature, nothing to do with brokerage.

For a personal graph like vault-rag (~17K entities, 13 edge types),
the actionable finding is: *"one `concept` entity is the sole broker
between your infrastructure knowledge and your campaign knowledge —
high constraint, low redundancy. If it's mis-typed or pruned, the two
halves disconnect."* That's structure-as-thinking-tool, not retrieval.

**Naming bug fixed alongside (do regardless).** Cat 5 currently prints
`● Structural holes:` for its H1/Betti-1 features. To anyone who has
read Burt, "structural holes" means brokerage positions — so the term
collides head-on the moment brokerage enters the vocabulary. Renamed
to **`Topological holes (H1 cycles)`** across `gap_detection.py`
(report strings + docstring), `sme_spec_v8.md`, and
`corpus_spec_2026.md`. "Structural holes / brokerage" is now reserved
for the Burt metric below. *(Already applied on this branch.)*

**Proposal.** Add a node-level brokerage reading to
`sme/topology/analyzer.py`, computed over the Louvain partition the
analyzer already produces. NetworkX ships the primitives — no new
dependency:

```python
# nx.constraint(G) -> {node: Burt's constraint in [0,1]}  (lower = more brokerage)
# nx.effective_size(G) -> {node: non-redundant neighbour count}
def brokerage(self, top_k: int = 10) -> BrokerageReport:
    G = self._undirected_simple()                # reuse existing projection
    constraint = nx.constraint(G)                # NaN for isolated/degree-1
    eff_size = nx.effective_size(G)
    comms = self._louvain_membership()           # reuse community_structure
    # a broker is a low-constraint node whose neighbours span >1 community
    brokers = sorted(
        ((n, constraint[n], eff_size[n], self._neighbour_communities(n, comms))
         for n in G if not math.isnan(constraint.get(n, float("nan")))),
        key=lambda r: r[1],                       # ascending constraint
    )
    # concentration: Gini (or top-1 share) of inverse-constraint mass
    return BrokerageReport(top_brokers=brokers[:top_k],
                           concentration=_gini_inv_constraint(constraint),
                           n_cross_community_brokers=...)
```

Report shape (additive — new keys, nothing renamed):

```json
{
  "brokerage": {
    "concentration": 0.71,            // 0 = evenly distributed, 1 = one broker
    "concentration_band": "concentrated",
    "n_cross_community_brokers": 3,
    "top_brokers": [
      {"node": "Entity:token-based-identity", "type": "concept",
       "constraint": 0.08, "effective_size": 11.4,
       "spans_communities": ["infrastructure", "campaign"]}
    ]
  }
}
```

Human reading (one band line, in the Cat 5 / `analyze` output):

```
● Brokerage: concentrated (top broker holds 71% of cross-community
  brokerage mass). Entity:token-based-identity (concept) is the sole
  low-constraint span between communities {infrastructure, campaign}.
  Single point of structural failure — if it's mis-typed or pruned,
  those communities disconnect.
```

**Why this is small.** `nx.constraint` and `nx.effective_size` are
built-ins; the Louvain partition and undirected projection already
exist in `analyzer.py`. The only genuinely new code is (a) intersecting
each broker's neighbourhood with community membership and (b) a
concentration scalar (Gini or top-1 share). No new dependency, no
RDF, no LLM. ~half day including tests against `topology/fixtures.py`.

**Why this matters.** It's the one addition that turns the topology
layer from "here are your components and loops" into "here is the
entity your whole graph's cross-domain reasoning routes through."
For SME's stated primary value — *making the maintainer's own graph
healthier* — concentrated brokerage is a higher-signal, more
actionable finding than bridge count or Betti-1 alone. It's also a
new diagnostic *axis* (concentrated vs distributed), not just another
scalar.

**Posture.** Diagnostic, not prescriptive — report the broker and the
concentration band; the maintainer decides whether to add redundant
cross-community edges. Never auto-edit. Consistent with the rest of
Cat 5.

**Watch-outs.**
- `nx.constraint` is `O(n·d²)`-ish; on the largest component only, and
  skip isolated / degree-1 nodes (constraint is NaN / trivially 1).
- Directionality: compute on the undirected simple projection (same as
  bridges), so a `concept` brokering via incoming + outgoing edges is
  counted once.
- Which snapshot: `semantic_snapshot` (same as the rest of Cat 5) —
  document-mention edges would make every Document a spurious broker.
