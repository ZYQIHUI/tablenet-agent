from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class CandidateScores:
    structure: float
    topic: float
    semantic: float
    overall: float
    ranking: float
    passed: bool

    def as_dict(self) -> Dict[str, float]:
        return {
            "structure": self.structure,
            "topic": self.topic,
            "semantic": self.semantic,
            "overall": self.overall,
            "ranking": self.ranking,
        }


class ScorePolicy:
    """Paper-aligned hard gating plus a separate ranking score."""

    def __init__(self, minimum_dimension_score: float = 0.58):
        self.minimum_dimension_score = minimum_dimension_score

    def evaluate(self, validation_result, checker_report) -> CandidateScores:
        structure = 1.0 if validation_result and validation_result.get("ok") else 0.0
        llm_topic = getattr(checker_report, "llm_topic_score", None)
        llm_semantic = getattr(checker_report, "llm_semantic_score", None)
        topic = float(llm_topic if llm_topic is not None else getattr(checker_report, "topic_consistency_score", 0.0))
        header = float(getattr(checker_report, "header_score", 0.0))
        body = float(getattr(checker_report, "body_score", 0.0))
        semantic = float(llm_semantic) if llm_semantic is not None else min(header, body)
        overall = min(structure, topic, semantic)
        ranking = 0.35 * structure + 0.25 * topic + 0.40 * semantic
        has_errors = bool(getattr(checker_report, "errors", []))
        passed = (
            structure == 1.0
            and overall >= self.minimum_dimension_score
            and not has_errors
        )
        return CandidateScores(
            structure=round(structure, 4),
            topic=round(topic, 4),
            semantic=round(semantic, 4),
            overall=round(overall, 4),
            ranking=round(ranking, 4),
            passed=passed,
        )
