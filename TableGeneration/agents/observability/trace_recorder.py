import json
from dataclasses import asdict, is_dataclass
from enum import Enum


class TraceRecorder:
    def __init__(self, file_object):
        self.file_object = file_object

    def write(self, state, outcome: str, error=None):
        record = state_to_record(state, outcome=outcome, error=error)
        self.file_object.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.file_object.flush()
        return record


def state_to_record(state, outcome: str, error=None):
    candidates = []
    for candidate in state.candidates:
        report = candidate.checker_report
        candidates.append({
            "candidate_id": candidate.candidate_id,
            "parent_candidate_id": candidate.parent_candidate_id,
            "generation_source": candidate.generation_source,
            "transformation": candidate.transformation,
            "rows": candidate.schema.rows,
            "cols": candidate.schema.cols,
            "selected": candidate.selected,
            "validation": _json_value(candidate.validation_result),
            "checker": _checker_summary(report),
            "metadata": _json_value(candidate.metadata),
        })
    return {
        "request_id": state.request_id,
        "outcome": outcome,
        "error": str(error) if error is not None else None,
        "request": _json_value(state.request),
        "plan": _json_value(state.plan),
        "retry_counters": dict(state.retry_counters),
        "budget": state.budget.snapshot() if state.budget is not None else None,
        "selected_candidate_id": state.selected_candidate_id,
        "candidates": candidates,
        "events": [_json_value(event) for event in state.events],
    }


def _checker_summary(report):
    if report is None:
        return None
    return {
        "ok": report.ok,
        "score": report.score,
        "title_score": report.title_score,
        "header_score": report.header_score,
        "body_score": report.body_score,
        "topic_consistency_score": report.topic_consistency_score,
        "errors": list(report.errors),
        "warnings": list(report.warnings),
        "dimension_scores": dict(report.dimension_scores),
        "column_scores": {str(key): value for key, value in report.column_scores.items()},
        "cell_scores": {f"{key[0]},{key[1]}": value for key, value in report.cell_scores.items()},
        "llm_topic_score": report.llm_topic_score,
        "llm_semantic_score": report.llm_semantic_score,
        "semantic_evaluator": dict(report.semantic_evaluator),
    }


def _json_value(value):
    if is_dataclass(value):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
