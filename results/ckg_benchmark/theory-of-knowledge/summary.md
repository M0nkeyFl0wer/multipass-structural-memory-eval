# CKG-benchmark — theory-of-knowledge

- queries run: **175**
- target-match failures (B): **0**
- tokenizer: `tiktoken-cl100k_base`

## Condition totals

| Cond | label | mean recall | full-recall | mean tokens | tokens/correct |
|------|-------|-------------|-------------|-------------|----------------|
| A | A: flat token-overlap | 0.829 | 135/175 | 114 | 148 |
| B | B: 2-hop structured | 0.940 | 151/175 | 1066 | 1236 |
| C | C: same-nodes prose | 0.960 | 159/175 | 675 | 743 |
| B2 | B2: hierarchical | 0.934 | 169/175 | 127 | 123 |

## B − A by hop_depth (recall pp, tokens)

| hop | n | A recall | B recall | Δrecall (pp) | A tokens | B tokens | Δtokens |
|-----|---|----------|----------|--------------|----------|----------|---------|
| 0 | 62 | 0.807 | 0.912 | +10.5 | 100 | 1579 | +1479 |
| 1 | 90 | 0.956 | 1.000 | +4.4 | 122 | 774 | +652 |
| 2 | 6 | 0.444 | 1.000 | +55.6 | 119 | 1421 | +1302 |
| 3 | 8 | 0.500 | 0.844 | +34.4 | 119 | 366 | +247 |
| 4 | 6 | 0.267 | 0.633 | +36.7 | 119 | 1176 | +1056 |
| 5 | 3 | 0.278 | 0.500 | +22.2 | 119 | 166 | +47 |

## B − C by hop_depth (the structure-isolation signal)

| hop | n | C recall | B recall | Δrecall (pp) | C tokens | B tokens | Δtokens |
|-----|---|----------|----------|--------------|----------|----------|---------|
| 0 | 62 | 0.917 | 0.912 | -0.6 | 963 | 1579 | +616 |
| 1 | 90 | 1.000 | 1.000 | +0.0 | 513 | 774 | +261 |
| 2 | 6 | 1.000 | 1.000 | +0.0 | 881 | 1421 | +541 |
| 3 | 8 | 1.000 | 0.844 | -15.6 | 276 | 366 | +90 |
| 4 | 6 | 0.867 | 0.633 | -23.3 | 732 | 1176 | +443 |
| 5 | 3 | 0.667 | 0.500 | -16.7 | 117 | 166 | +49 |

## B − B2 by hop_depth (format: triples vs hierarchical)

| hop | n | B2 recall | B recall | Δrecall (pp) | B2 tokens | B tokens | Δtokens |
|-----|---|-----------|----------|--------------|-----------|----------|---------|
| 0 | 62 | 0.830 | 0.912 | -8.2 | 132 | 1579 | -1448 |
| 1 | 90 | 1.000 | 1.000 | +0.0 | 120 | 774 | -654 |
| 2 | 6 | 0.944 | 1.000 | -5.6 | 144 | 1421 | -1277 |
| 3 | 8 | 1.000 | 0.844 | +15.6 | 133 | 366 | -232 |
| 4 | 6 | 0.900 | 0.633 | +26.7 | 167 | 1176 | -1009 |
| 5 | 3 | 1.000 | 0.500 | +50.0 | 109 | 166 | -57 |

**B vs B2:** recall 0.940 vs 0.934 (-0.6pp), tokens 1066 vs 127 (fewer by 88%)

**Verdict:** structure earns complexity (scales with depth)

- B - C is negative at hops 3,4,5 — structural routing is actively harmful
- B/A ratio grows with hop depth as the spec predicts — multi-hop traversal is working
