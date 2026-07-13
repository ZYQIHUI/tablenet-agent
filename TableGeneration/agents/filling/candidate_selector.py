from typing import Iterable, Optional

from ..evaluation.score_policy import ScorePolicy


class CandidateSelector:
    def __init__(self, score_policy=None):
        self.score_policy = score_policy or ScorePolicy()

    def score(self, candidate):
        scores = self.score_policy.evaluate(
            candidate.validation_result,
            candidate.checker_report,
        )
        candidate.metadata["core_scores"] = scores.as_dict()
        candidate.metadata["passed_hard_gate"] = scores.passed
        if not scores.passed:
            candidate.metadata.setdefault("rejection_reason", "quality_gate_failed")
        return scores

    def select(self, candidates: Iterable) -> Optional[object]:
        ranked = []
        for candidate in candidates:
            scores = self.score(candidate)
            if scores.passed and not candidate.metadata.get("duplicate"):
                ranked.append((scores.ranking, scores.overall, candidate.candidate_id, candidate))
        if not ranked:
            return None
        ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
        selected = ranked[0][3]
        selected.metadata["selection_reason"] = "highest_ranking_score_after_hard_gate"
        return selected
