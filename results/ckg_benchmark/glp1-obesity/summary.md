# CKG-benchmark — glp1-obesity

- queries run: **170**
- target-match failures (B): **0**
- tokenizer: `tiktoken-cl100k_base`

## Condition totals

| Cond | label | mean recall | full-recall | mean tokens | tokens/correct |
|------|-------|-------------|-------------|-------------|----------------|
| A | A: flat token-overlap | 0.869 | 130/170 | 208 | 272 |
| B | B: 2-hop structured | 0.895 | 133/170 | 1588 | 2030 |
| C | C: same-nodes prose | 0.921 | 136/170 | 1115 | 1394 |
| B2 | B2: hierarchical | 0.919 | 167/170 | 192 | 190 |

## B − A by hop_depth (recall pp, tokens)

| hop | n | A recall | B recall | Δrecall (pp) | A tokens | B tokens | Δtokens |
|-----|---|----------|----------|--------------|----------|----------|---------|
| 0 | 57 | 0.892 | 0.866 | -2.5 | 186 | 1557 | +1371 |
| 1 | 88 | 0.922 | 0.989 | +6.6 | 218 | 1813 | +1595 |
| 2 | 1 | 1.000 | 1.000 | +0.0 | 142 | 796 | +654 |
| 3 | 6 | 0.958 | 0.750 | -20.8 | 172 | 960 | +788 |
| 4 | 13 | 0.431 | 0.600 | +16.9 | 247 | 922 | +675 |
| 5 | 5 | 0.667 | 0.500 | -16.7 | 243 | 623 | +380 |

## B − C by hop_depth (the structure-isolation signal)

| hop | n | C recall | B recall | Δrecall (pp) | C tokens | B tokens | Δtokens |
|-----|---|----------|----------|--------------|----------|----------|---------|
| 0 | 57 | 0.884 | 0.866 | -1.8 | 1094 | 1557 | +463 |
| 1 | 88 | 0.989 | 0.989 | +0.0 | 1260 | 1813 | +553 |
| 2 | 1 | 1.000 | 1.000 | +0.0 | 501 | 796 | +295 |
| 3 | 6 | 0.875 | 0.750 | -12.5 | 703 | 960 | +258 |
| 4 | 13 | 0.738 | 0.600 | -13.8 | 703 | 922 | +218 |
| 5 | 5 | 0.667 | 0.500 | -16.7 | 499 | 623 | +124 |

## B − B2 by hop_depth (format: triples vs hierarchical)

| hop | n | B2 recall | B recall | Δrecall (pp) | B2 tokens | B tokens | Δtokens |
|-----|---|-----------|----------|--------------|-----------|----------|---------|
| 0 | 57 | 0.868 | 0.866 | +0.2 | 186 | 1557 | -1371 |
| 1 | 88 | 0.989 | 0.989 | +0.0 | 203 | 1813 | -1610 |
| 2 | 1 | 1.000 | 1.000 | +0.0 | 137 | 796 | -659 |
| 3 | 6 | 0.750 | 0.750 | +0.0 | 80 | 960 | -880 |
| 4 | 13 | 0.769 | 0.600 | +16.9 | 185 | 922 | -736 |
| 5 | 5 | 0.833 | 0.500 | +33.3 | 217 | 623 | -406 |

**B vs B2:** recall 0.895 vs 0.919 (+2.3pp), tokens 1588 vs 192 (fewer by 88%)

**Verdict:** mixed: structure helps at some depths and hurts at others

- B - C is negative at hops 3,4,5 — structural routing is actively harmful
