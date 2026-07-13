import os
import random

from ...agent_types import TablePlan, TableSchema
from ...domain.errors import ErrorCode, ValidationIssue
from ...domain.results import AgentResult, AgentSource


def _load_corpus(path):
    """Load a corpus file into a single string."""
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, mode="r", encoding="utf-8") as f:
            lines = [line.strip("\n").strip("\r\n") for line in f.readlines()]
        return "".join(lines)
    except (OSError, UnicodeDecodeError):
        return ""


def _sample_text(corpus, min_len=2, max_len=8):
    """Sample a random substring from corpus."""
    if not corpus or len(corpus) < min_len:
        return ""
    effective = min(len(corpus), max_len)
    # ensure we have room
    hi = len(corpus) - min_len
    if hi <= 0:
        return corpus[:max_len]
    start = random.randint(0, hi)
    length = random.randint(min_len, min(max_len, len(corpus) - start))
    return corpus[start:start + length]


class BodyAgent:
    """Fills body cells with lightweight semantic templates."""

    REGIONS = ["东区", "西区", "南区", "北区", "中心区", "新区"]
    STATUS = ["正常", "待优化", "已完成", "跟进中", "需复核"]
    PEOPLE = ["张工", "李工", "王工", "赵工", "陈工"]
    DEPARTMENTS = ["网络部", "市场部", "客服中心", "装维中心", "政企部", "运维部"]
    SUGGESTIONS = ["扩容小区", "优化参数", "安排复测", "跟进回访", "升级设备", "保持观察"]
    ORDER_TYPES = ["网络慢", "频繁掉线", "计费疑问", "装维延迟", "信号弱", "服务咨询"]
    PACKAGES = ["畅享套餐", "融合套餐", "校园套餐", "政企套餐", "家庭套餐", "流量包"]
    TIME_WINDOWS = ["早高峰", "午间", "晚高峰", "夜间", "节假日", "工作日"]

    def __init__(self, llm_body_client=None, use_llm=False,
                 ch_corpus_path=None, en_corpus_path=None):
        self.llm_body_client = llm_body_client
        self.use_llm = use_llm
        self.ch_corpus = _load_corpus(ch_corpus_path) if ch_corpus_path else ""
        self.en_corpus = _load_corpus(en_corpus_path) if en_corpus_path else ""
        self.last_result = None
        self._last_llm_error = None
        # Minimal corpus for English fallback
        if not self.en_corpus:
            self.en_corpus = "abcdefghijklmnopqrstuvwxyz"

    def _text(self, language="zh"):
        """Generate diverse text from corpus, falling back to small pool."""
        if language == "zh" and self.ch_corpus:
            text = _sample_text(self.ch_corpus, min_len=3, max_len=10)
            if text:
                return text
        if language == "en" and self.en_corpus:
            text = _sample_text(self.en_corpus, min_len=3, max_len=10)
            if text:
                return text
        # Ultimate fallback — unchanged small pool
        return random.choice(self.STATUS)

    def fill(
            self,
            schema: TableSchema,
            plan: TablePlan,
            target_cells=None,
            target_columns=None,
            preserve_existing=False) -> TableSchema:
        target_cells = set(target_cells or [])
        target_columns = set(target_columns or [])
        headers = self._headers_by_col(schema)
        row_headers = self._row_headers_by_row(schema)
        selected_cells = [
            cell for cell in schema.cells
            if cell.role == "body" and self._is_targeted(cell, target_cells, target_columns)
        ]
        llm_result = self._values_from_llm(
            schema,
            plan,
            headers,
            row_headers,
            selected_cells=selected_cells,
        )
        if llm_result:
            llm_values, body_cells = llm_result
            if self._apply_llm_values(
                    schema,
                    body_cells,
                    llm_values,
                    plan.language,
                    selected_cells=selected_cells):
                self.last_result = AgentResult.success(
                    schema,
                    self._client_source(),
                    actual_source=self._client_source().value,
                    backend_metadata=self._backend_metadata(),
                )
                return schema
        for cell in schema.cells:
            if cell.role != "body":
                continue
            if preserve_existing and not self._is_targeted(cell, target_cells, target_columns):
                continue
            header = headers.get(cell.col, "")
            if any(keyword in header for keyword in ("区域", "所属区域", "装机区域")):
                cell.text = random.choice(self.REGIONS)
            elif any(keyword in header for keyword in ("投诉类型",)):
                cell.text = random.choice(self.ORDER_TYPES)
            elif any(keyword in header for keyword in ("套餐名称",)):
                cell.text = random.choice(self.PACKAGES)
            elif any(keyword in header for keyword in ("监控时段", "时段")):
                cell.text = random.choice(self.TIME_WINDOWS)
            elif any(keyword in header for keyword in ("责任部门", "部门")):
                cell.text = random.choice(self.DEPARTMENTS)
            elif any(keyword in header for keyword in ("率", "同比", "进度", "占比", "满意度", "评分", "覆盖率")):
                cell.text = "{:.1f}%".format(random.uniform(70, 99.9))
            elif any(keyword in header for keyword in ("日期",)):
                cell.text = f"2026-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
            elif any(keyword in header for keyword in ("编号",)):
                cell.text = f"BS-{random.randint(1000, 9999)}"
            elif any(keyword in header for keyword in ("建议", "意见", "备注")):
                cell.text = random.choice(self.SUGGESTIONS)
            elif any(keyword in header for keyword in ("站点数", "用户数", "故障数", "数量", "预算", "支出", "收入", "利润", "流量", "时长", "速度", "次数", "频次", "投诉", "延迟", "覆盖", "活跃", "告警", "受理", "完结", "响应", "订购", "新增", "退订", "带宽", "拥塞", "预约", "完成", "超时", "修复", "ARPU")):
                cell.text = str(random.randint(10, 999))
            elif any(keyword in header for keyword in ("负责人", "维护人员", "装维人员")):
                cell.text = random.choice(self.PEOPLE)
            elif any(keyword in header for keyword in ("状态", "类型", "偏好", "设备")):
                cell.text = random.choice(self.STATUS)
            else:
                cell.text = self._text(plan.language)
        if self.use_llm:
            reason = self._last_llm_error or "body model returned an invalid response"
            self.last_result = AgentResult.fallback(
                schema,
                AgentSource.RULE,
                errors=[ValidationIssue(ErrorCode.LLM_CALL_FAILED, reason)],
                actual_source="rule",
                fallback_reason=reason,
                backend_metadata=self._backend_metadata(),
            )
        else:
            self.last_result = AgentResult.success(schema, AgentSource.RULE, actual_source="rule")
        return schema

    def _values_from_llm(
            self,
            schema: TableSchema,
            plan: TablePlan,
            headers,
            row_headers,
            selected_cells=None):
        if not self.use_llm or self.llm_body_client is None:
            if self.use_llm:
                self._last_llm_error = "no body model client configured"
            return None
        self._last_llm_error = None
        selected_positions = None
        if selected_cells is not None:
            selected_positions = {(cell.row, cell.col) for cell in selected_cells}
        body_cells = [
            {
                "row": cell.row,
                "col": cell.col,
                "header": headers.get(cell.col, ""),
                "row_label": row_headers.get(cell.row, ""),
                "expected_type": self._expected_type(headers.get(cell.col, "")),
            }
            for cell in sorted(schema.cells, key=lambda item: (item.row, item.col))
            if cell.role == "body" and (
                selected_positions is None or (cell.row, cell.col) in selected_positions
            )
        ]
        try:
            values = self.llm_body_client.generate_body_values(
                domain=plan.domain,
                language=plan.language,
                topic=plan.topic,
                headers=[headers.get(col, "") for col in range(schema.cols)],
                row_headers=row_headers,
                body_cells=body_cells,
            )
        except Exception as exc:
            self._last_llm_error = str(exc)
            return None
        if not values:
            self._last_llm_error = "body model returned an empty response"
            return None
        return values, body_cells

    def _client_source(self):
        if getattr(self.llm_body_client, "backend_source", "api") == "local_model":
            return AgentSource.LOCAL_MODEL
        return AgentSource.API

    def _backend_metadata(self):
        result = getattr(self.llm_body_client, "last_result", None)
        return getattr(result, "metadata", {})

    def _apply_llm_values(
            self,
            schema: TableSchema,
            body_cells,
            values,
            language="zh",
            selected_cells=None):
        selected_positions = None
        if selected_cells is not None:
            selected_positions = {(cell.row, cell.col) for cell in selected_cells}
        schema_body_cells = [
            cell for cell in sorted(schema.cells, key=lambda item: (item.row, item.col))
            if cell.role == "body" and (
                selected_positions is None or (cell.row, cell.col) in selected_positions
            )
        ]
        if isinstance(values, dict):
            values = self._values_from_mapping(schema_body_cells, values)
            if values is None:
                return False
        elif not isinstance(values, list):
            return False
        if len(values) != len(schema_body_cells):
            return False
        if len(body_cells) != len(schema_body_cells):
            return False
        if not all(isinstance(value, (str, int, float)) and str(value).strip() for value in values):
            return False
        for schema_cell, value, body_meta in zip(schema_body_cells, values, body_cells):
            schema_cell.text = self._normalize_value(
                body_meta.get("expected_type", "text"),
                body_meta.get("header", ""),
                value,
                language=language,
            )
        return True

    def _is_targeted(self, cell, target_cells, target_columns):
        if not target_cells and not target_columns:
            return True
        return (cell.row, cell.col) in target_cells or cell.col in target_columns

    def _values_from_mapping(self, schema_body_cells, values):
        ordered = []
        for cell in schema_body_cells:
            key = f"{cell.row},{cell.col}"
            alt_key = f"{cell.row}:{cell.col}"
            value = values.get(key, values.get(alt_key))
            if not isinstance(value, (str, int, float)) or not str(value).strip():
                return None
            ordered.append(str(value).strip())
        return ordered

    def _headers_by_col(self, schema: TableSchema):
        headers = {}
        for cell in schema.cells:
            if cell.role == "header":
                for col in range(cell.col, cell.col + cell.colspan):
                    headers[col] = cell.text
        return headers

    def _row_headers_by_row(self, schema: TableSchema):
        row_headers = {}
        for cell in schema.cells:
            if cell.role == "header" and cell.col == 0:
                row_headers[cell.row] = cell.text
        return row_headers

    def _expected_type(self, header: str) -> str:
        if any(keyword in header for keyword in ("率", "同比", "进度", "占比", "满意度", "评分", "覆盖率")):
            return "percent"
        if any(keyword in header for keyword in ("站点数", "用户数", "故障数", "数量", "预算", "支出", "收入", "利润", "流量", "时长", "速度", "次数", "频次", "投诉", "延迟", "覆盖", "活跃", "容量", "告警", "受理", "完结", "响应", "订购", "新增", "退订", "带宽", "拥塞", "预约", "完成", "超时", "修复", "ARPU")):
            return "numeric"
        return "text"

    def _normalize_value(self, expected_type: str, header: str, value,
                         language="zh") -> str:
        text = str(value).strip()
        if expected_type == "percent":
            if text.endswith("%"):
                return text
            numeric = self._leading_numeric(text)
            if numeric is not None:
                return f"{numeric}%"
            return "{:.1f}%".format(random.uniform(70, 99.9))
        if expected_type == "numeric":
            numeric = self._leading_numeric(text)
            if numeric is not None:
                return numeric
            return str(random.randint(10, 999))
        if not text:
            if any(keyword in header for keyword in ("状态", "备注", "类型", "时段", "偏好", "设备")):
                return random.choice(self.STATUS)
            if any(keyword in header for keyword in ("区域", "部门", "项目", "用户类型", "客户类型", "群体")):
                return random.choice(self.REGIONS)
            return self._text(language)
        return text

    def _leading_numeric(self, text: str):
        cleaned = text.replace(",", "").strip()
        number = []
        seen_digit = False
        for char in cleaned:
            if char.isdigit() or (char == "." and seen_digit):
                number.append(char)
                seen_digit = True
            elif not seen_digit and char in "+-":
                number.append(char)
            else:
                break
        candidate = "".join(number).strip()
        if candidate and candidate not in ("+", "-", ".", "+.", "-."):
            try:
                float(candidate)
                return candidate
            except ValueError:
                return None
        return None

    def _fallback_value(self, col: int) -> str:
        if col == 0:
            return random.choice(self.REGIONS)
        if col in (1, 2, 3):
            return str(random.randint(10, 999))
        return random.choice(self.STATUS)
