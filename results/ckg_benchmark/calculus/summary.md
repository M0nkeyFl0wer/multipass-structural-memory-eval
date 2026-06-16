# CKG-benchmark — calculus

- queries run: **180**
- target-match failures (B): **0**
- tokenizer: `tiktoken-cl100k_base`

## Condition totals

| Cond | label | mean recall | full-recall | mean tokens | tokens/correct |
|------|-------|-------------|-------------|-------------|----------------|
| A | A: flat token-overlap | 0.846 | 141/180 | 125 | 160 |
| B | B: 2-hop structured | 0.875 | 144/180 | 467 | 584 |
| C | C: same-nodes prose | 0.902 | 154/180 | 351 | 410 |
| B2 | B2: hierarchical | 0.903 | 167/180 | 108 | 109 |

## B − A by hop_depth (recall pp, tokens)

| hop | n | A recall | B recall | Δrecall (pp) | A tokens | B tokens | Δtokens |
|-----|---|----------|----------|--------------|----------|----------|---------|
| 0 | 67 | 0.782 | 0.773 | -0.9 | 120 | 552 | +432 |
| 1 | 88 | 0.966 | 1.000 | +3.4 | 128 | 453 | +326 |
| 2 | 2 | 1.000 | 1.000 | +0.0 | 135 | 472 | +336 |
| 3 | 7 | 0.786 | 0.893 | +10.7 | 128 | 316 | +188 |
| 4 | 9 | 0.444 | 0.667 | +22.2 | 135 | 252 | +117 |
| 5 | 7 | 0.476 | 0.500 | +2.4 | 125 | 250 | +124 |

## B − C by hop_depth (the structure-isolation signal)

| hop | n | C recall | B recall | Δrecall (pp) | C tokens | B tokens | Δtokens |
|-----|---|----------|----------|--------------|----------|----------|---------|
| 0 | 67 | 0.777 | 0.773 | -0.3 | 406 | 552 | +146 |
| 1 | 88 | 1.000 | 1.000 | +0.0 | 344 | 453 | +109 |
| 2 | 2 | 1.000 | 1.000 | +0.0 | 350 | 472 | +122 |
| 3 | 7 | 1.000 | 0.893 | -10.7 | 253 | 316 | +63 |
| 4 | 9 | 0.956 | 0.667 | -28.9 | 204 | 252 | +48 |
| 5 | 7 | 0.667 | 0.500 | -16.7 | 199 | 250 | +51 |

## B − B2 by hop_depth (format: triples vs hierarchical)

| hop | n | B2 recall | B recall | Δrecall (pp) | B2 tokens | B tokens | Δtokens |
|-----|---|-----------|----------|--------------|-----------|----------|---------|
| 0 | 67 | 0.757 | 0.773 | -1.6 | 109 | 552 | -443 |
| 1 | 88 | 1.000 | 1.000 | +0.0 | 106 | 453 | -347 |
| 2 | 2 | 1.000 | 1.000 | +0.0 | 99 | 472 | -372 |
| 3 | 7 | 1.000 | 0.893 | +10.7 | 122 | 316 | -194 |
| 4 | 9 | 1.000 | 0.667 | +33.3 | 115 | 252 | -137 |
| 5 | 7 | 0.833 | 0.500 | +33.3 | 104 | 250 | -145 |

**B vs B2:** recall 0.875 vs 0.903 (+2.8pp), tokens 467 vs 108 (fewer by 77%)

**Verdict:** structure adds value at uniform scale

- B - C is negative at hops 3,4,5 — structural routing is actively harmful
- B beats flat but the advantage does not grow with depth — traversal may not be active, benefits may come from re-ranking
