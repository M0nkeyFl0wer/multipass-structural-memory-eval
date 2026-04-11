# v0.1 Corpus Authoring Contract

**Purpose:** Define exactly what goes into the starter corpus so that the benchmark pipeline can be validated end-to-end before scaling to v1.0.

**Principle:** Hand-author everything. No LLM synthesis, no dataset adaptation. At 30 notes this is 2-3 hours of writing. The payoff is that every ground-truth answer is verified and every defect is intentional.

---

## Corpus structure

```
sme/corpora/standard_v0_1/
  ├── AUTHORING.md                  # this file
  ├── corpus.yaml                   # structured ground truth
  ├── calibration.json              # frozen structural reference + corpus hash
  ├── implied_ontology_mempalace.yaml  # pre-extracted for MemPalace README
  ├── vault/                        # Obsidian-format mirror
  │   ├── auth_engineering/         # 8 notes
  │   ├── privacy_research/         # 7 notes
  │   ├── infrastructure/           # 6 notes
  │   ├── temporal/                 # 4 notes (fact evolution chain)
  │   └── injected_defects/         # 5 notes
  └── calibration_50q.yaml          # human-judged calibration set for judge agreement
```

---

## Notes: 30 total

### Domain: auth_engineering (8 notes)
| # | Filename | Content summary | Entities introduced | Chains |
|---|---|---|---|---|
| 1 | kai-oauth-debugging.md | Kai debugged OAuth token refresh | Kai (person), OAuth token refresh (concept) | Start of 3-hop chain A |
| 2 | driftwood-auth-migration.md | Driftwood migration blocked by token expiry | Driftwood (project), auth migration (concept) | Hop 2 of chain A |
| 3 | clerk-auth-decision.md | Session 12: team chose Clerk for auth | Clerk (tool) | Contradiction pair 1a |
| 4 | auth0-switch.md | Session 47: switched to Auth0, Clerk pricing didn't work | Auth0 (tool) | Contradiction pair 1b |
| 5 | infra-team-roster.md | Infrastructure team includes Kai | infrastructure team (organization) | Hop 0 of chain A (enables 3-hop: team→Kai→OAuth→Driftwood) |
| 6 | oauth-token-spec.md | Technical spec for OAuth token refresh flow | OAuth spec (concept) | 1-hop target |
| 7 | auth-system-comparison.md | Comparison of Clerk, Auth0, Supabase Auth | Supabase Auth (tool) | Enriches Cat 3 |
| 8 | auth-meeting-notes.md | Meeting notes referencing "the auth decision" | — | Context for temporal queries |

### Domain: privacy_research (7 notes)
| # | Filename | Content summary | Entities introduced | Chains |
|---|---|---|---|---|
| 9 | zk-proof-overview.md | Overview of zero-knowledge proofs | ZK proof (concept) | Alias pair 1a |
| 10 | zero-knowledge-cryptography.md | Zero-knowledge cryptography in identity | zero-knowledge cryptography (concept) | Alias pair 1b |
| 11 | cbt-therapy-notes.md | Cognitive Behavioral Therapy session notes | CBT (concept) | Alias pair 2a |
| 12 | cognitive-behavioral-overview.md | Cognitive Behavioral Therapy overview | Cognitive Behavioral Therapy (concept) | Alias pair 2b |
| 13 | k8s-deployment.md | Kubernetes deployment for privacy service | k8s (tool) | Alias pair 3a |
| 14 | kubernetes-architecture.md | Kubernetes cluster architecture | Kubernetes (tool) | Alias pair 3b |
| 15 | privacy-token-identity.md | Token-based identity in privacy systems | token-based identity (concept) | Gap bridge topic (but NO edge to auth_engineering) |

### Domain: infrastructure (6 notes)
| # | Filename | Content summary | Entities introduced | Chains |
|---|---|---|---|---|
| 16 | postgresql-setup.md | Session 5: using PostgreSQL | PostgreSQL (tool) | Temporal evolution step 1 |
| 17 | sqlite-migration.md | Session 23: migrating to SQLite | SQLite (tool) | Temporal evolution step 2 |
| 18 | back-to-postgresql.md | Session 41: back to PostgreSQL, SQLite concurrent writes | — | Temporal evolution step 3 |
| 19 | deployment-pipeline.md | CI/CD pipeline for infrastructure | CI/CD (concept) | General |
| 20 | monitoring-setup.md | Monitoring and alerting configuration | monitoring (concept) | 2-hop chain B target |
| 21 | alerting-oauth-integration.md | Alerting system integrates with OAuth for SSO | — | Hop 2 of chain B (monitoring→alerting→OAuth) |

### Domain: temporal (4 notes)
| # | Filename | Content summary | Entities introduced | Chains |
|---|---|---|---|---|
| 22 | project-kickoff.md | Project kickoff, initial tech decisions | — | Early session context |
| 23 | mid-project-review.md | Mid-project review, migration discussion | — | Session 23 context |
| 24 | post-migration-retro.md | Post-migration retrospective | — | Session 41 context |
| 25 | current-stack-doc.md | Current state of the stack | — | "What are we using now?" target |

### Injected defects (5 notes)
| # | Filename | Defect type | What it tests |
|---|---|---|---|
| 26 | boilerplate-evidence-1.md | Evidence duplication | 10 edges with identical evidence "Supports general architecture patterns" |
| 27 | boilerplate-evidence-2.md | Evidence duplication | Same 10 edges, different source doc — system should flag |
| 28 | gps-scheduling-misattrib.md | Evidence misattribution | Note about GPS tracking, but edges connect scheduling→anti_pattern |
| 29 | yaml-frontmatter-trap.md | Ghost entity (NER bait) | Frontmatter with "John Smith: reviewer", "npm:@scope/pkg" — NER should NOT create person/org entities from these |
| 30 | related-monoculture-batch.md | Edge type monoculture | 10 relationships that should be SUPPORTS/DERIVES_FROM but injected as RELATED |

---

## Ground truth questions: 50 total

### Multi-hop chains (10 queries, annotated with ground-truth hop depth)

| # | Query | Answer | min_hops | Chain |
|---|---|---|---|---|
| H1 | "What auth system is Kai working on?" | OAuth token refresh | 1 | Direct |
| H2 | "What is the OAuth token refresh spec about?" | [spec content] | 1 | Direct |
| H3 | "What system does the alerting integrate with for SSO?" | OAuth | 1 | Direct |
| H4 | "Who debugged the system that blocked the Driftwood migration?" | Kai | 2 | Kai→OAuth→Driftwood |
| H5 | "What monitoring system connects to the auth infrastructure?" | Alerting→OAuth | 2 | monitoring→alerting→OAuth |
| H6 | "What project uses the token system debugged by Kai?" | Driftwood | 2 | Kai→OAuth→Driftwood |
| H7 | "Which deployment blocked by the same token issue that the alerting SSO depends on?" | Driftwood | 2 | alerting→OAuth→Driftwood |
| H8 | "What project was affected by the issue debugged by someone on the infrastructure team?" | Driftwood | 3 | team→Kai→OAuth→Driftwood |
| H9 | "What monitoring connects to the auth system debugged by a member of the infrastructure team?" | alerting→OAuth←Kai←team | 3 | team→Kai→OAuth←alerting |
| H10 | "Which team member's debugging work relates to the system used for deployment SSO?" | Kai (OAuth used by alerting for SSO) | 3 | team→Kai→OAuth→alerting |

### Category-specific queries (40 queries, ~8 per category)

**Cat 1 — Factual retrieval (8):** Direct fact questions with single ground-truth answers. "When did the team decide to use Clerk?" "What issue did Kai debug?"

**Cat 2b — Canonicalization (6):** Queries that require alias resolution. "What privacy technology is used in identity verification?" (must surface both ZK proof and zero-knowledge cryptography). "What container orchestration tool is deployed?" (must surface both k8s and Kubernetes).

**Cat 3 — Contradiction (4):** "What auth system are we using?" (should flag Clerk vs Auth0). "What database are we using?" (should surface PostgreSQL with evolution chain or flag SQLite contradiction).

**Cat 4 — Ingestion integrity (4):** These don't have "queries" in the traditional sense — they test whether the system or SME detects the injected defects. Scored by defect detection rate, not QA accuracy.

**Cat 5 — Gap detection (4):** "What topics span auth_engineering and privacy_research?" (should surface token-based identity gap). "What areas have no cross-references?" Scored at L1/L2/L3.

**Cat 6 — Temporal (6):** "What database are we using?" (current: PostgreSQL). "What database were we using in session 25?" (SQLite). "When did our database choice change?" (full evolution chain). "What was the most recent auth decision?" (Auth0, superseding Clerk).

**Cat 7 — Token efficiency (8):** Same queries as Cat 1 and multi-hop, but scored for tokens-per-correct-answer across Conditions A and B.

**Cat 8 — Ontology coherence (0 explicit queries):** Scored from graph snapshot analysis, not from queries. The corpus's entity type and edge type distributions provide the ground truth.

---

## Calibration thresholds

| Property | Threshold | Rationale |
|---|---|---|
| Gap disconnection | Shortest path auth_engineering↔privacy_research > 4 hops | No accidental bridges |
| Alias string similarity | Max Jaccard < 0.25 | Confirms testing canonicalization |
| Alias semantic similarity | Min cosine > 0.78 (nomic-embed-text) | Confirms aliases are semantically close |
| Runaway cluster | Ghost entities in own connected component | Not bridged to main graph |
| Monoculture batch | Betti-0 divergence > 2.0 (typed vs RELATED subgraphs) | Detectable split |
| Contradiction placement | Clerk and Auth0 notes in different retrieval neighborhoods | Cosine similarity of their chunks < 0.6 |

---

## Held-out split

v0.1 is entirely dev. No held-out portion.

v1.0 will split into:
- `corpus_dev.yaml` — for tuning (in repo)
- `corpus_heldout.yaml` — for reporting (separate download, hash-locked, not in main repo)

---

## Domain coverage limitations

v0.1 is tech/dev focused: auth, infrastructure, privacy, deployment. This biases toward systems built for developer knowledge.

v1.0 must add:
- Personal knowledge domain (health, relationships, daily routines)
- Creative domain (writing projects, research notes)
- Professional domain (meetings, decisions, org structure)

This is a known limitation, stated in the benchmark report for any v0.1 results.
