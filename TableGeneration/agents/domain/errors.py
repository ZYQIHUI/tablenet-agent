from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class ErrorCode(str, Enum):
    STRUCTURE_INVALID = "STRUCTURE_INVALID"
    TOPIC_MISMATCH = "TOPIC_MISMATCH"
    HEADER_INCOMPLETE = "HEADER_INCOMPLETE"
    HEADER_BODY_MISMATCH = "HEADER_BODY_MISMATCH"
    INVALID_CELL_TYPE = "INVALID_CELL_TYPE"
    EMPTY_CELL = "EMPTY_CELL"
    DUPLICATE_CONTENT = "DUPLICATE_CONTENT"
    SEMANTIC_CONFLICT = "SEMANTIC_CONFLICT"
    LLM_CALL_FAILED = "LLM_CALL_FAILED"
    UNSUPPORTED_REQUEST = "UNSUPPORTED_REQUEST"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class RepairAction(str, Enum):
    RETRY = "retry"
    REPAIR_HEADER = "repair_header"
    REPAIR_BODY = "repair_body"
    REPAIR_CELLS = "repair_cells"
    REPAIR_COLUMNS = "repair_columns"
    REBUILD_SCHEMA = "rebuild_schema"
    FALLBACK = "fallback"
    REJECT = "reject"


@dataclass(frozen=True)
class ValidationIssue:
    code: ErrorCode
    message: str
    severity: str = "error"
    location: Optional[Tuple[int, int]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
