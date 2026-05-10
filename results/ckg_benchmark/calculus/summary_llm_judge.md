# CKG-benchmark — calculus — LLM judge

Reader: gpt-4o-mini · Judge: gpt-4o-2024-08-06

## Overall (LLM-judge label distribution)

| Cond | n | CORRECT | PARTIAL | INCORRECT | ERROR | accuracy (C/P) |
|---|---|---|---|---|---|---|
| A | 180 | 47 | 100 | 33 | 0 | 0.539 |
| B | 180 | 51 | 99 | 30 | 0 | 0.558 |
| C | 180 | 59 | 95 | 26 | 0 | 0.592 |

## By hop_depth — LLM-judge accuracy

| hop | n | A acc | B acc | C acc | B−A pp | B−C pp |
|---|---|---|---|---|---|---|
| 0 | 67 | 0.418 | 0.418 | 0.388 | +0.0 | +3.0 |
| 1 | 88 | 0.733 | 0.739 | 0.790 | +0.6 | -5.1 |
| 2 | 2 | 0.500 | 0.500 | 0.500 | +0.0 | +0.0 |
| 3 | 7 | 0.214 | 0.500 | 0.714 | +28.6 | -21.4 |
| 4 | 9 | 0.111 | 0.333 | 0.389 | +22.2 | -5.6 |
| 5 | 7 | 0.143 | 0.000 | 0.214 | -14.3 | -21.4 |

