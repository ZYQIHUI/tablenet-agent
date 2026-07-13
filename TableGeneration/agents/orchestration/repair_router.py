from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..domain.errors import ErrorCode, RepairAction, ValidationIssue


@dataclass(frozen=True)
class RepairDecision:
    action: RepairAction
    issues: List[ValidationIssue] = field(default_factory=list)
    target_cells: Tuple[Tuple[int, int], ...] = ()
    target_columns: Tuple[int, ...] = ()


class RepairRouter:
    """Maps validator/checker output to an explicit workflow action."""

    def for_structure_errors(self, errors) -> RepairDecision:
        issues = [
            ValidationIssue(ErrorCode.STRUCTURE_INVALID, str(error))
            for error in errors
        ]
        return RepairDecision(RepairAction.REBUILD_SCHEMA, issues)

    def for_filling_report(self, report) -> RepairDecision:
        issues = []
        cells = []
        columns = set()
        for message in list(report.errors) + list(report.warnings):
            issue = self._classify_message(message)
            issues.append(issue)
            if issue.location is not None:
                cells.append(issue.location)
                columns.add(issue.location[1])

        if getattr(report, "title_score", 1.0) <= 0.0:
            return RepairDecision(RepairAction.REBUILD_SCHEMA, issues)
        if getattr(report, "header_score", 1.0) <= 0.0:
            return RepairDecision(RepairAction.REPAIR_HEADER, issues, target_columns=tuple(sorted(columns)))
        if cells:
            return RepairDecision(
                RepairAction.REPAIR_CELLS,
                issues,
                target_cells=tuple(cells),
                target_columns=tuple(sorted(columns)),
            )
        return RepairDecision(RepairAction.REPAIR_BODY, issues)

    def _classify_message(self, message: str) -> ValidationIssue:
        location = self._extract_location(message)
        lower = message.lower()
        if "empty header" in lower or "no header" in lower:
            code = ErrorCode.HEADER_INCOMPLETE
        elif "empty body" in lower:
            code = ErrorCode.EMPTY_CELL
        elif "non-percentage" in lower or "non-numeric" in lower:
            code = ErrorCode.INVALID_CELL_TYPE
        elif "does not match header" in lower:
            code = ErrorCode.HEADER_BODY_MISMATCH
        elif "topic" in lower or "semantic scenario" in lower:
            code = ErrorCode.TOPIC_MISMATCH
        elif "duplication" in lower or "duplicate" in lower:
            code = ErrorCode.DUPLICATE_CONTENT
        else:
            code = ErrorCode.SEMANTIC_CONFLICT
        severity = "warning" if "warning" in lower else "error"
        return ValidationIssue(code, message, severity=severity, location=location)

    def _extract_location(self, message: str) -> Optional[Tuple[int, int]]:
        start = message.find("(")
        end = message.find(")", start + 1)
        if start < 0 or end < 0:
            return None
        parts = message[start + 1:end].split(",")
        if len(parts) != 2:
            return None
        try:
            return int(parts[0].strip()), int(parts[1].strip())
        except ValueError:
            return None
