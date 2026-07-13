from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar

from .errors import ValidationIssue


T = TypeVar("T")


class AgentStatus(str, Enum):
    SUCCESS = "success"
    FALLBACK = "fallback"
    FAILED = "failed"


class AgentSource(str, Enum):
    API = "api"
    LOCAL_MODEL = "local_model"
    RULE = "rule"
    TOOL = "tool"
    MIXED = "mixed"


@dataclass
class AgentResult(Generic[T]):
    value: Optional[T]
    status: AgentStatus
    source: AgentSource
    confidence: Optional[float] = None
    errors: List[ValidationIssue] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status != AgentStatus.FAILED and self.value is not None

    @classmethod
    def success(cls, value: T, source: AgentSource, **metadata):
        return cls(value=value, status=AgentStatus.SUCCESS, source=source, metadata=metadata)

    @classmethod
    def fallback(cls, value: T, source: AgentSource, errors=None, **metadata):
        return cls(
            value=value,
            status=AgentStatus.FALLBACK,
            source=source,
            errors=list(errors or []),
            metadata=metadata,
        )

    @classmethod
    def failed(cls, source: AgentSource, errors=None, **metadata):
        return cls(
            value=None,
            status=AgentStatus.FAILED,
            source=source,
            errors=list(errors or []),
            metadata=metadata,
        )
