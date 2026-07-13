from typing import Callable, Dict

from ...capabilities.protocols import CapabilityRequest
from ...domain.results import AgentResult, AgentSource


class ApiCallableBackend:
    """Compatibility adapter for existing API clients during migration."""

    def __init__(self, handlers: Dict[str, Callable], name: str = "api"):
        self.name = name
        self.handlers = dict(handlers)

    def supports(self, capability: str) -> bool:
        return capability in self.handlers

    def execute(self, request: CapabilityRequest):
        value = self.handlers[request.capability](**request.payload)
        return AgentResult.success(value, AgentSource.API, backend=self.name)
