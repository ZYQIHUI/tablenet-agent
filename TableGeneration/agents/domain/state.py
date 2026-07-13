from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .errors import RepairAction, ValidationIssue


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkflowEvent:
    stage: str
    action: str
    attempt: int = 0
    candidate_id: Optional[str] = None
    issues: List[ValidationIssue] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now)


@dataclass
class CandidateState:
    schema: Any
    candidate_id: str = field(default_factory=lambda: _new_id("cand"))
    parent_candidate_id: Optional[str] = None
    generation_source: str = "unknown"
    transformation: Optional[str] = None
    validation_result: Any = None
    checker_report: Any = None
    selected: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationState:
    request: Any
    request_id: str = field(default_factory=lambda: _new_id("req"))
    plan: Any = None
    style: Any = None
    candidates: List[CandidateState] = field(default_factory=list)
    events: List[WorkflowEvent] = field(default_factory=list)
    retry_counters: Dict[str, int] = field(default_factory=dict)
    failure_history: List[ValidationIssue] = field(default_factory=list)
    selected_candidate_id: Optional[str] = None
    result: Any = None
    budget: Any = None

    def increment(self, counter: str) -> int:
        value = self.retry_counters.get(counter, 0) + 1
        self.retry_counters[counter] = value
        if self.budget is not None and counter in self.budget.usage:
            self.budget.consume(counter)
        return value

    def consume(self, resource: str, amount: int = 1) -> None:
        if self.budget is not None:
            self.budget.consume(resource, amount)

    def check_budget(self) -> None:
        if self.budget is not None:
            self.budget.check()

    def record(
            self,
            stage: str,
            action: str,
            attempt: int = 0,
            candidate_id: Optional[str] = None,
            issues=None,
            **metadata) -> WorkflowEvent:
        event = WorkflowEvent(
            stage=stage,
            action=action,
            attempt=attempt,
            candidate_id=candidate_id,
            issues=list(issues or []),
            metadata=metadata,
        )
        self.events.append(event)
        self.failure_history.extend(event.issues)
        return event

    def select(self, candidate: CandidateState) -> None:
        for item in self.candidates:
            item.selected = item.candidate_id == candidate.candidate_id
        candidate.selected = True
        self.selected_candidate_id = candidate.candidate_id
