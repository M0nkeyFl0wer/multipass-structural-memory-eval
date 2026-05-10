# CKG-benchmark — glp1-obesity — LLM judge

Reader: gpt-4o-mini · Judge: gpt-4o-2024-08-06

## Overall (LLM-judge label distribution)

| Cond | n | CORRECT | PARTIAL | INCORRECT | ERROR | accuracy (C/P) |
|---|---|---|---|---|---|---|
| A | 170 | 55 | 84 | 31 | 0 | 0.571 |
| B | 170 | 47 | 94 | 29 | 0 | 0.553 |
| C | 170 | 58 | 84 | 28 | 0 | 0.588 |

## By hop_depth — LLM-judge accuracy

| hop | n | A acc | B acc | C acc | B−A pp | B−C pp |
|---|---|---|---|---|---|---|
| 0 | 57 | 0.456 | 0.465 | 0.474 | +0.9 | -0.9 |
| 1 | 88 | 0.733 | 0.733 | 0.784 | +0.0 | -5.1 |
| 2 | 1 | 0.500 | 0.500 | 0.500 | +0.0 | +0.0 |
| 3 | 6 | 0.583 | 0.250 | 0.333 | -33.3 | -8.3 |
| 4 | 13 | 0.077 | 0.077 | 0.077 | +0.0 | +0.0 |
| 5 | 5 | 0.300 | 0.000 | 0.100 | -30.0 | -10.0 |

