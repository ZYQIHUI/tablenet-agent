from dataclasses import asdict, replace

from ..domain.errors import ErrorCode, ValidationIssue
from ..domain.results import AgentResult, AgentSource


class CorePlanner:
    ALLOWED_FIELDS = {
        "domain", "language", "min_rows", "max_rows", "min_cols", "max_cols",
        "simple", "colored", "lined", "structure_type",
    }

    def __init__(self, client=None, use_model=False):
        self.client = client
        self.use_model = use_model
        self.last_result = None

    def plan(self, request):
        text = request.natural_language_request
        if not text or not self.use_model:
            self.last_result = AgentResult.success(request, AgentSource.RULE, actual_source="structured_request")
            return request
        if self.client is None:
            return self._fallback(request, "no Core Planner model configured")
        try:
            proposed = self.client.plan_request(text, asdict(request))
        except Exception as exc:
            return self._fallback(request, str(exc))
        if not isinstance(proposed, dict):
            return self._fallback(request, "Core Planner returned invalid JSON")
        updates = {key: value for key, value in proposed.items() if key in self.ALLOWED_FIELDS}
        try:
            planned = self._validated_replace(request, updates)
        except (TypeError, ValueError) as exc:
            return self._fallback(request, str(exc))
        source = AgentSource.LOCAL_MODEL if getattr(self.client, "backend_source", "api") == "local_model" else AgentSource.API
        backend_result = getattr(self.client, "last_result", None)
        self.last_result = AgentResult.success(
            planned,
            source,
            actual_source=source.value,
            proposed_fields=sorted(updates),
            backend_metadata=getattr(backend_result, "metadata", {}),
        )
        return planned

    def _validated_replace(self, request, updates):
        for key in ("min_rows", "max_rows", "min_cols", "max_cols"):
            if key in updates:
                if isinstance(updates[key], bool):
                    raise ValueError(f"{key} must be an integer")
                updates[key] = int(updates[key])
        planned = replace(request, **updates)
        if planned.min_rows < 1 or planned.min_rows > planned.max_rows:
            raise ValueError("invalid row bounds from Core Planner")
        if planned.min_cols < 1 or planned.min_cols > planned.max_cols:
            raise ValueError("invalid column bounds from Core Planner")
        for key in ("simple", "colored", "lined"):
            if getattr(planned, key) is not None and not isinstance(getattr(planned, key), bool):
                raise ValueError(f"{key} must be boolean or null")
        return planned

    def _fallback(self, request, reason):
        backend_result = getattr(self.client, "last_result", None)
        self.last_result = AgentResult.fallback(
            request,
            AgentSource.RULE,
            errors=[ValidationIssue(ErrorCode.LLM_CALL_FAILED, reason)],
            actual_source="structured_request",
            fallback_reason=reason,
            backend_metadata=getattr(backend_result, "metadata", {}),
        )
        return request
