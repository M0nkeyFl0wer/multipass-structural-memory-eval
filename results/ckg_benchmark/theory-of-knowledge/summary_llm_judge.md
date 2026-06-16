# CKG-benchmark — theory-of-knowledge — LLM judge

Reader: gpt-4o-mini · Judge: gpt-4o-2024-08-06

## Overall (LLM-judge label distribution)

| Cond | n | CORRECT | PARTIAL | INCORRECT | ERROR | accuracy (C/P) |
|---|---|---|---|---|---|---|
| A | 175 | 61 | 77 | 37 | 0 | 0.569 |
| B | 175 | 68 | 93 | 14 | 0 | 0.654 |
| C | 175 | 71 | 98 | 6 | 0 | 0.686 |

## By hop_depth — LLM-judge accuracy

| hop | n | A acc | B acc | C acc | B−A pp | B−C pp |
|---|---|---|---|---|---|---|
| 0 | 62 | 0.452 | 0.540 | 0.556 | +8.9 | -1.6 |
| 1 | 90 | 0.772 | 0.806 | 0.833 | +3.3 | -2.8 |
| 2 | 6 | 0.167 | 0.583 | 0.500 | +41.7 | +8.3 |
| 3 | 8 | 0.125 | 0.500 | 0.500 | +37.5 | +0.0 |
| 4 | 6 | 0.000 | 0.167 | 0.333 | +16.7 | -16.7 |
| 5 | 3 | 0.000 | 0.000 | 0.500 | +0.0 | -50.0 |

