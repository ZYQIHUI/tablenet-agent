from dataclasses import dataclass, field
from typing import Any, Dict, Protocol

from ..domain.results import AgentResult


@dataclass(frozen=True)
class CapabilityRequest:
    capability: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


class CapabilityBackend(Protocol):
    name: str

    def supports(self, capability: str) -> bool:
        ...

    def execute(self, request: CapabilityRequest) -> AgentResult[Any]:
        ...
