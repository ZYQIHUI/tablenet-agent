from typing import Dict, Tuple

from ..capabilities import CapabilityRequest
from ..domain.errors import ErrorCode, ValidationIssue
from ..domain.results import AgentResult, AgentSource


class ClientCapabilityBackend:
    """Adapts existing method-based clients to the unified backend protocol."""

    def __init__(self, name: str, source: AgentSource, capabilities: Dict[str, Tuple[object, str]]):
        self.name = name
        self.source = source
        self.capabilities = dict(capabilities)

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def execute(self, request: CapabilityRequest):
        client, method_name = self.capabilities[request.capability]
        method = getattr(client, method_name)
        value = method(**request.payload)
        if value is None:
            return AgentResult.failed(
                self.source,
                errors=[ValidationIssue(
                    ErrorCode.LLM_CALL_FAILED,
                    f"{self.name} returned no valid result for {request.capability}",
                )],
                backend=self.name,
                capability=request.capability,
            )
        return AgentResult.success(
            value,
            self.source,
            backend=self.name,
            capability=request.capability,
            usage=dict(getattr(client, "last_usage", {}) or {}),
        )
