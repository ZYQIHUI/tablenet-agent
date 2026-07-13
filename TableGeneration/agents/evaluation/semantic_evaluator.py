from ..domain.errors import ErrorCode, ValidationIssue
from ..domain.results import AgentResult, AgentSource


class SemanticEvaluator:
    def __init__(self, client=None, use_model=False):
        self.client = client
        self.use_model = use_model
        self.last_result = None

    def evaluate(self, schema, plan):
        if not self.use_model or self.client is None:
            return None
        headers = [
            {"row": cell.row, "col": cell.col, "text": cell.text}
            for cell in schema.cells if cell.role == "header"
        ]
        rows = {}
        for cell in schema.cells:
            if cell.role == "body":
                rows.setdefault(str(cell.row), []).append({"col": cell.col, "text": cell.text})
        try:
            value = self.client.evaluate_semantics(plan.topic, plan.domain, headers, rows)
        except Exception as exc:
            return self._failed(str(exc))
        normalized = self._normalize(value)
        if normalized is None:
            return self._failed("semantic model returned an invalid response")
        source = AgentSource.LOCAL_MODEL if getattr(self.client, "backend_source", "api") == "local_model" else AgentSource.API
        backend_result = getattr(self.client, "last_result", None)
        self.last_result = AgentResult.success(
            normalized,
            source,
            actual_source=source.value,
            backend_metadata=getattr(backend_result, "metadata", {}),
        )
        return normalized

    def _normalize(self, value):
        if not isinstance(value, dict):
            return None
        try:
            topic_score = max(0.0, min(1.0, float(value["topic_score"])))
            semantic_score = max(0.0, min(1.0, float(value["semantic_score"])))
        except (KeyError, TypeError, ValueError):
            return None
        errors = value.get("errors", [])
        evidence = value.get("evidence", [])
        return {
            "topic_score": topic_score,
            "semantic_score": semantic_score,
            "errors": [str(item) for item in errors] if isinstance(errors, list) else [],
            "evidence": [str(item) for item in evidence] if isinstance(evidence, list) else [],
        }

    def _failed(self, reason):
        backend_result = getattr(self.client, "last_result", None)
        self.last_result = AgentResult.failed(
            AgentSource.MIXED,
            errors=[ValidationIssue(ErrorCode.LLM_CALL_FAILED, reason)],
            fallback_reason=reason,
            backend_metadata=getattr(backend_result, "metadata", {}),
        )
        return None
