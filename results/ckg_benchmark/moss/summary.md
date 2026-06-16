# CKG-benchmark — moss

- queries run: **176**
- target-match failures (B): **0**
- tokenizer: `tiktoken-cl100k_base`

## Condition totals

| Cond | label | mean recall | full-recall | mean tokens | tokens/correct |
|------|-------|-------------|-------------|-------------|----------------|
| A | A: flat token-overlap | 0.883 | 146/176 | 126 | 152 |
| B | B: 2-hop structured | 0.898 | 146/176 | 1080 | 1302 |
| C | C: same-nodes prose | 0.919 | 155/176 | 715 | 812 |
| B2 | B2: hierarchical | 0.912 | 165/176 | 115 | 116 |

## B − A by hop_depth (recall pp, tokens)

| hop | n | A recall | B recall | Δrecall (pp) | A tokens | B tokens | Δtokens |
|-----|---|----------|----------|--------------|----------|----------|---------|
| 0 | 63 | 0.818 | 0.805 | -1.3 | 119 | 869 | +750 |
| 1 | 90 | 0.983 | 1.000 | +1.7 | 129 | 1270 | +1141 |
| 2 | 6 | 0.778 | 1.000 | +22.2 | 133 | 1907 | +1774 |
| 3 | 9 | 0.639 | 0.750 | +11.1 | 131 | 277 | +146 |
| 4 | 5 | 0.760 | 0.600 | -16.0 | 123 | 769 | +647 |
| 5 | 3 | 0.389 | 0.556 | +16.7 | 130 | 1115 | +985 |

## B − C by hop_depth (the structure-isolation signal)

| hop | n | C recall | B recall | Δrecall (pp) | C tokens | B tokens | Δtokens |
|-----|---|----------|----------|--------------|----------|----------|---------|
| 0 | 63 | 0.807 | 0.805 | -0.2 | 579 | 869 | +291 |
| 1 | 90 | 1.000 | 1.000 | +0.0 | 835 | 1270 | +434 |
| 2 | 6 | 1.000 | 1.000 | +0.0 | 1240 | 1907 | +667 |
| 3 | 9 | 1.000 | 0.750 | -25.0 | 217 | 277 | +60 |
| 4 | 5 | 0.760 | 0.600 | -16.0 | 548 | 769 | +222 |
| 5 | 3 | 0.722 | 0.556 | -16.7 | 715 | 1115 | +400 |

## B − B2 by hop_depth (format: triples vs hierarchical)

| hop | n | B2 recall | B recall | Δrecall (pp) | B2 tokens | B tokens | Δtokens |
|-----|---|-----------|----------|--------------|-----------|----------|---------|
| 0 | 63 | 0.798 | 0.805 | -0.7 | 98 | 869 | -771 |
| 1 | 90 | 1.000 | 1.000 | +0.0 | 122 | 1270 | -1148 |
| 2 | 6 | 0.833 | 1.000 | -16.7 | 183 | 1907 | -1724 |
| 3 | 9 | 1.000 | 0.750 | +25.0 | 113 | 277 | -164 |
| 4 | 5 | 0.760 | 0.600 | +16.0 | 119 | 769 | -650 |
| 5 | 3 | 0.833 | 0.556 | +27.8 | 144 | 1115 | -971 |

**B vs B2:** recall 0.898 vs 0.912 (+1.4pp), tokens 1080 vs 115 (fewer by 89%)

**Verdict:** mixed: structure helps at some depths and hurts at others

- B - C is negative at hops 3,4,5 — structural routing is actively harmful
