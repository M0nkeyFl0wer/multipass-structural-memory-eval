"""LongMemEval corpus loader for SME cross-validation.

LongMemEval (Wu et al., ICLR 2025; arXiv 2410.10813; MIT license) is a
500-question benchmark for long-term memory in chat assistants. This
package loads the upstream JSON dataset and produces SME-shape question
records so SME's category readings can be cross-validated against
LongMemEval's GPT-4o judge methodology.

The dataset itself is NOT committed to this repo (15-90 MB). Download
with:

    cd sme/corpora/longmemeval
    wget https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_oracle.json

See README.md for the full download list and the data layout this
loader expects.
"""

from sme.corpora.longmemeval.loader import (
    LMEQuestion,
    LMESession,
    LMETurn,
    LME_TO_SME_CATEGORY,
    load_questions,
    materialize_sme_corpus,
)

__all__ = [
    "LMEQuestion",
    "LMESession",
    "LMETurn",
    "LME_TO_SME_CATEGORY",
    "load_questions",
    "materialize_sme_corpus",
]
