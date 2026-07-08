from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ...types import TablePlan, TableSchema


@dataclass
class FillingCheckReport:
    """Structured result for filling quality assessment."""

    ok: bool
    score: float
    title_score: float
    header_score: float
    body_score: float
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    column_scores: Dict[int, float] = field(default_factory=dict)
    cell_scores: Dict[Tuple[int, int], float] = field(default_factory=dict)


class FillingChecker:
    """Scores whether filled table content is semantically and structurally plausible."""

    NUMERIC_HINTS = (
        "数",
        "收入",
        "预算",
        "支出",
        "利润",
        "同比",
        "完成率",
        "评分",
        "流量",
        "时长",
        "速度",
        "次数",
        "频次",
        "投诉",
        "覆盖",
        "用户",
        "容量",
    )
    PERCENT_HINTS = ("率", "同比", "进度", "占比", "满意度", "覆盖率")
    STATUS_HINTS = ("状态", "备注", "类型", "时段", "偏好", "设备")
    ENTITY_HINTS = ("区域", "部门", "项目", "用户类型", "客户类型", "群体", "负责人")
    DEFAULT_MIN_SCORE = 0.58

    def __init__(self, min_score: float = DEFAULT_MIN_SCORE):
        self.min_score = min_score

    def evaluate(self, schema: TableSchema, plan: TablePlan, min_score: Optional[float] = None) -> FillingCheckReport:
        headers = self._headers_by_col(schema)
        errors: List[str] = []
        warnings: List[str] = []
        column_scores: Dict[int, float] = {}
        cell_scores: Dict[Tuple[int, int], float] = {}

        title_score = self._score_title(schema, plan, errors, warnings)
        header_score = self._score_headers(schema, headers, errors, warnings, column_scores)
        body_score = self._score_body(schema, headers, errors, warnings, cell_scores, column_scores)

        score = round(
            0.2 * title_score +
            0.25 * header_score +
            0.55 * body_score,
            4,
        )
        threshold = self.min_score if min_score is None else min_score
        ok = len(errors) == 0 and score >= threshold
        if score < threshold and not errors:
            warnings.append(f"overall filling score {score:.3f} below threshold {threshold:.3f}")

        return FillingCheckReport(
            ok=ok,
            score=score,
            title_score=round(title_score, 4),
            header_score=round(header_score, 4),
            body_score=round(body_score, 4),
            errors=errors,
            warnings=warnings,
            column_scores=column_scores,
            cell_scores=cell_scores,
        )

    def check(self, schema: TableSchema, plan: TablePlan):
        report = self.evaluate(schema, plan)
        return report.ok, report.errors

    def _score_title(
            self,
            schema: TableSchema,
            plan: TablePlan,
            errors: List[str],
            warnings: List[str]) -> float:
        title_cells = [cell for cell in schema.cells if cell.role == "title"]
        if plan.simple:
            if title_cells:
                title_text = " ".join(cell.text.strip() for cell in title_cells if cell.text.strip())
                if title_text:
                    warnings.append("simple table unexpectedly contains a title row")
                    return 0.9
            return 1.0

        if not title_cells:
            errors.append("complex table is missing a title cell")
            return 0.0

        title_text = " ".join(cell.text.strip() for cell in title_cells if cell.text.strip())
        if not title_text:
            errors.append("complex table title is empty")
            return 0.0

        if plan.topic in title_text:
            return 1.0

        overlap = self._token_overlap(title_text, plan.topic)
        if overlap >= 0.5:
            warnings.append("complex table title is related to the planned topic but not exact")
            return 0.75

        errors.append("complex table title does not contain or align with the planned topic")
        return 0.0

    def _score_headers(
            self,
            schema: TableSchema,
            headers: Dict[int, str],
            errors: List[str],
            warnings: List[str],
            column_scores: Dict[int, float]) -> float:
        header_cells = [cell for cell in schema.cells if cell.role == "header"]
        if not header_cells:
            errors.append("table has no header cells")
            return 0.0

        total = 0
        passed = 0
        seen = set()
        duplicate_count = 0

        for cell in header_cells:
            text = cell.text.strip()
            total += 1
            if not text:
                errors.append(f"empty header cell at ({cell.row}, {cell.col})")
                column_scores[cell.col] = 0.0
                continue
            if text in seen:
                duplicate_count += 1
            seen.add(text)

            coverage = 0
            for col in range(cell.col, cell.col + cell.colspan):
                headers[col] = text
                coverage += 1
            if coverage > 0:
                passed += 1
                for col in range(cell.col, cell.col + cell.colspan):
                    column_scores.setdefault(col, 1.0)

        if duplicate_count:
            warnings.append(f"header duplication detected in {duplicate_count} header cells")

        if total == 0:
            return 0.0

        non_empty_ratio = passed / total
        uniqueness_ratio = len(seen) / max(1, total)
        return min(1.0, 0.7 * non_empty_ratio + 0.3 * uniqueness_ratio)

    def _score_body(
            self,
            schema: TableSchema,
            headers: Dict[int, str],
            errors: List[str],
            warnings: List[str],
            cell_scores: Dict[Tuple[int, int], float],
            column_scores: Dict[int, float]) -> float:
        body_cells = [cell for cell in schema.cells if cell.role == "body"]
        if not body_cells:
            warnings.append("table has no body cells")
            return 1.0

        score_sum = 0.0
        score_count = 0
        col_pass = {}
        col_total = {}

        for cell in body_cells:
            header = headers.get(cell.col, "")
            text = cell.text.strip()
            expected_type = self._expected_type(header)
            cell_score, issue = self._score_body_cell(text, header, expected_type)

            cell_scores[(cell.row, cell.col)] = round(cell_score, 4)
            score_sum += cell_score
            score_count += 1
            col_total[cell.col] = col_total.get(cell.col, 0) + 1
            if cell_score >= 0.75:
                col_pass[cell.col] = col_pass.get(cell.col, 0) + 1

            if issue == "empty":
                errors.append(f"empty body cell at ({cell.row}, {cell.col})")
            elif issue == "percent":
                errors.append(f"percentage-like column has non-percentage value at ({cell.row}, {cell.col})")
            elif issue == "numeric":
                errors.append(f"numeric-like column has non-numeric value at ({cell.row}, {cell.col})")
            elif issue == "weak_text":
                warnings.append(f"body cell at ({cell.row}, {cell.col}) looks generic for header '{header}'")

        for col, total in col_total.items():
            column_scores[col] = round(col_pass.get(col, 0) / total, 4)

        if score_count == 0:
            return 0.0

        return score_sum / score_count

    def _score_body_cell(self, text: str, header: str, expected_type: str):
        if not text:
            return 0.0, "empty"

        if expected_type == "percent":
            if self._looks_like_percent(text):
                return 1.0, None
            return 0.0, "percent"

        if expected_type == "numeric":
            if self._is_numeric_like(text):
                return 1.0, None
            return 0.0, "numeric"

        if expected_type == "entity":
            if self._looks_like_entity(text):
                return 0.95, None
            return 0.7, "weak_text"

        if expected_type == "status":
            if self._looks_like_status(text):
                return 0.95, None
            return 0.75, "weak_text"

        if len(text) <= 2:
            return 0.6, "weak_text"

        if self._is_generic_placeholder(text, header):
            return 0.55, "weak_text"

        return 0.9, None

    def _headers_by_col(self, schema: TableSchema):
        headers = {}
        for cell in schema.cells:
            if cell.role == "header":
                for col in range(cell.col, cell.col + cell.colspan):
                    headers[col] = cell.text
        return headers

    def _expected_type(self, header: str) -> str:
        if any(hint in header for hint in self.PERCENT_HINTS):
            return "percent"
        if any(hint in header for hint in self.NUMERIC_HINTS):
            return "numeric"
        if any(hint in header for hint in self.ENTITY_HINTS):
            return "entity"
        if any(hint in header for hint in self.STATUS_HINTS):
            return "status"
        return "text"

    def _looks_like_percent(self, text: str) -> bool:
        if text.endswith("%"):
            return self._is_numeric_like(text[:-1].strip())
        return False

    def _looks_like_entity(self, text: str) -> bool:
        return any(hint in text for hint in ("区", "部", "组", "项目", "部门", "中心", "站", "工"))

    def _looks_like_status(self, text: str) -> bool:
        return any(hint in text for hint in ("正常", "完成", "待", "进行", "复核", "优化", "跟进", "异常"))

    def _is_generic_placeholder(self, text: str, header: str) -> bool:
        if not text:
            return True
        if text == header:
            return True
        if text in {"数据", "内容", "示例", "待填", "未知", "暂无"}:
            return True
        return False

    def _is_numeric_like(self, text: str) -> bool:
        value = text.replace(",", "").strip()
        value = value.rstrip("%")
        while value and value[-1].isalpha():
            value = value[:-1].rstrip()
        while value and ("\u4e00" <= value[-1] <= "\u9fff"):
            value = value[:-1].rstrip()
        try:
            float(value)
            return True
        except ValueError:
            return False

    def _token_overlap(self, lhs: str, rhs: str) -> float:
        lhs_tokens = self._tokenize(lhs)
        rhs_tokens = self._tokenize(rhs)
        if not lhs_tokens or not rhs_tokens:
            return 0.0
        intersection = len(lhs_tokens & rhs_tokens)
        union = len(lhs_tokens | rhs_tokens)
        return intersection / union if union else 0.0

    def _tokenize(self, text: str):
        cleaned = []
        current = []
        for char in text:
            if char.isalnum() or ("\u4e00" <= char <= "\u9fff"):
                current.append(char.lower())
            else:
                if current:
                    cleaned.append("".join(current))
                    current = []
        if current:
            cleaned.append("".join(current))
        return set(cleaned)
