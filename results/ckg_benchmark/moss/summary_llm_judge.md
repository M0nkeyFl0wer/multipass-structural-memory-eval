# CKG-benchmark — moss — LLM judge

Reader: gpt-4o-mini · Judge: gpt-4o-2024-08-06

## Overall (LLM-judge label distribution)

| Cond | n | CORRECT | PARTIAL | INCORRECT | ERROR | accuracy (C/P) |
|---|---|---|---|---|---|---|
| A | 176 | 55 | 96 | 25 | 0 | 0.585 |
| B | 176 | 51 | 91 | 34 | 0 | 0.548 |
| C | 176 | 65 | 81 | 30 | 0 | 0.599 |

## By hop_depth — LLM-judge accuracy

| hop | n | A acc | B acc | C acc | B−A pp | B−C pp |
|---|---|---|---|---|---|---|
| 0 | 63 | 0.444 | 0.373 | 0.373 | -7.1 | +0.0 |
| 1 | 90 | 0.756 | 0.744 | 0.794 | -1.1 | -5.0 |
| 2 | 6 | 0.667 | 0.917 | 1.000 | +25.0 | -8.3 |
| 3 | 9 | 0.167 | 0.056 | 0.500 | -11.1 | -44.4 |
| 4 | 5 | 0.300 | 0.000 | 0.000 | -30.0 | +0.0 |
| 5 | 3 | 0.000 | 0.000 | 0.000 | +0.0 | +0.0 |

