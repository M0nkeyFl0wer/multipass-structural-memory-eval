# CKG-benchmark — us-geography — LLM judge

Reader: gpt-4o-mini · Judge: gpt-4o-2024-08-06

## Overall (LLM-judge label distribution)

| Cond | n | CORRECT | PARTIAL | INCORRECT | ERROR | accuracy (C/P) |
|---|---|---|---|---|---|---|
| A | 176 | 70 | 78 | 28 | 0 | 0.619 |
| B | 176 | 76 | 67 | 33 | 0 | 0.622 |
| C | 176 | 62 | 85 | 29 | 0 | 0.594 |

## By hop_depth — LLM-judge accuracy

| hop | n | A acc | B acc | C acc | B−A pp | B−C pp |
|---|---|---|---|---|---|---|
| 0 | 63 | 0.563 | 0.516 | 0.452 | -4.8 | +6.3 |
| 1 | 88 | 0.812 | 0.824 | 0.812 | +1.1 | +1.1 |
| 2 | 3 | 0.000 | 1.000 | 0.667 | +100.0 | +33.3 |
| 3 | 18 | 0.000 | 0.056 | 0.028 | +5.6 | +2.8 |
| 4 | 4 | 0.500 | 0.125 | 0.500 | -37.5 | -37.5 |

