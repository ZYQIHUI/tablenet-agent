from typing import Callable, Dict

from ...capabilities.protocols import CapabilityRequest
from ...domain.results import AgentResult, AgentSource


class RuleCallableBackend:
    def __init__(self, handlers: Dict[str, Callable], name: str = "rule"):
        self.name = name
        self.handlers = dict(handlers)

    def supports(self, capability: str) -> bool:
        return capability in self.handlers

    def execute(self, request: CapabilityRequest):
        value = self.handlers[request.capability](**request.payload)
        return AgentResult.success(value, AgentSource.RULE, backend=self.name)
