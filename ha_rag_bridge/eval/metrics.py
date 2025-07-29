from __future__ import annotations

from rouge_score import rouge_scorer


scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)


def rouge_l_f1(system: str, reference: str) -> float:
    """Return the Rouge-L F1 score for a single prediction."""
    return scorer.score(reference, system)["rougeL"].fmeasure
