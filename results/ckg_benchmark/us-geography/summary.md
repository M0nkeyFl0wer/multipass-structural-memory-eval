# CKG-benchmark — us-geography

- queries run: **176**
- target-match failures (B): **11**
- tokenizer: `tiktoken-cl100k_base`

## Condition totals

| Cond | label | mean recall | full-recall | mean tokens | tokens/correct |
|------|-------|-------------|-------------|-------------|----------------|
| A | A: flat token-overlap | 0.873 | 138/176 | 89 | 114 |
| B | B: 2-hop structured | 0.901 | 142/176 | 1156 | 1433 |
| C | C: same-nodes prose | 0.901 | 142/176 | 801 | 993 |
| B2 | B2: hierarchical | 0.858 | 165/176 | 130 | 139 |

## B − A by hop_depth (recall pp, tokens)

| hop | n | A recall | B recall | Δrecall (pp) | A tokens | B tokens | Δtokens |
|-----|---|----------|----------|--------------|----------|----------|---------|
| 0 | 63 | 0.905 | 0.820 | -8.5 | 83 | 841 | +758 |
| 1 | 88 | 0.977 | 1.000 | +2.3 | 88 | 1096 | +1008 |
| 2 | 3 | 0.333 | 1.000 | +66.7 | 109 | 2159 | +2050 |
| 3 | 18 | 0.361 | 0.750 | +38.9 | 109 | 2159 | +2050 |
| 4 | 4 | 0.800 | 0.600 | -20.0 | 106 | 2159 | +2053 |

## B − C by hop_depth (the structure-isolation signal)

| hop | n | C recall | B recall | Δrecall (pp) | C tokens | B tokens | Δtokens |
|-----|---|----------|----------|--------------|----------|----------|---------|
| 0 | 63 | 0.821 | 0.820 | -0.1 | 619 | 841 | +223 |
| 1 | 88 | 1.000 | 1.000 | +0.0 | 776 | 1096 | +320 |
| 2 | 3 | 1.000 | 1.000 | +0.0 | 1349 | 2159 | +810 |
| 3 | 18 | 0.750 | 0.750 | +0.0 | 1349 | 2159 | +810 |
| 4 | 4 | 0.600 | 0.600 | +0.0 | 1349 | 2159 | +810 |

## B − B2 by hop_depth (format: triples vs hierarchical)

| hop | n | B2 recall | B recall | Δrecall (pp) | B2 tokens | B tokens | Δtokens |
|-----|---|-----------|----------|--------------|-----------|----------|---------|
| 0 | 63 | 0.799 | 0.820 | -2.1 | 110 | 841 | -731 |
| 1 | 88 | 1.000 | 1.000 | +0.0 | 152 | 1096 | -944 |
| 2 | 3 | 0.667 | 1.000 | -33.3 | 100 | 2159 | -2059 |
| 3 | 18 | 0.500 | 0.750 | -25.0 | 100 | 2159 | -2059 |
| 4 | 4 | 0.400 | 0.600 | -20.0 | 100 | 2159 | -2059 |

**B vs B2:** recall 0.901 vs 0.858 (-4.3pp), tokens 1156 vs 130 (fewer by 89%)

**Verdict:** mixed: structure helps at some depths and hurts at others

- B - C is near zero across all hop depths — structure is a neutral tax, adds nothing beyond metadata
