from typing import Callable, Dict

from ...capabilities.protocols import CapabilityRequest
from ...domain.results import AgentResult, AgentSource


class LocalCallableBackend:
    """Backend-neutral adapter for an in-process model or local model service."""

    def __init__(self, handlers: Dict[str, Callable], name: str = "local"):
        self.name = name
        self.handlers = dict(handlers)

    def supports(self, capability: str) -> bool:
        return capability in self.handlers

    def execute(self, request: CapabilityRequest):
        value = self.handlers[request.capability](**request.payload)
        return AgentResult.success(value, AgentSource.LOCAL_MODEL, backend=self.name)
