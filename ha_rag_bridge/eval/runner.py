from __future__ import annotations

import json
from pathlib import Path

from .metrics import rouge_l_f1


def run(dataset_path: str, threshold: float) -> float:
    """Run evaluation on DATASET_PATH and return average score."""
    from ha_rag_bridge.pipeline import query as pipeline_query

    data = json.loads(Path(dataset_path).read_text())
    scores = []
    for item in data:
        question = item["question"]
        ref = item["reference"]
        result = pipeline_query(question)
        scores.append(rouge_l_f1(result.get("answer", ""), ref))

    avg_score = sum(scores) / len(scores)
    if avg_score < threshold:
        raise SystemExit(1)
    return avg_score
