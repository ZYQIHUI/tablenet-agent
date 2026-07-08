import random

from ...types import TablePlan, TableSchema


class BodyAgent:
    """Fills body cells with lightweight semantic templates."""

    REGIONS = ["东区", "西区", "南区", "北区", "中心区", "新区"]
    STATUS = ["正常", "待优化", "已完成", "跟进中", "需复核"]
    PEOPLE = ["张工", "李工", "王工", "赵工", "陈工"]

    def __init__(self, llm_body_client=None, use_llm=False):
        self.llm_body_client = llm_body_client
        self.use_llm = use_llm

    def fill(self, schema: TableSchema, plan: TablePlan) -> TableSchema:
        headers = self._headers_by_col(schema)
        row_headers = self._row_headers_by_row(schema)
        llm_result = self._values_from_llm(schema, plan, headers, row_headers)
        if llm_result:
            llm_values, body_cells = llm_result
            if self._apply_llm_values(schema, body_cells, llm_values):
                return schema
        for cell in schema.cells:
            if cell.role != "body":
                continue
            header = headers.get(cell.col, "")
            if any(keyword in header for keyword in ("区域", "部门", "项目", "用户类型", "客户类型", "群体")):
                cell.text = random.choice(self.REGIONS)
            elif any(keyword in header for keyword in ("率", "同比", "进度", "占比", "满意度", "评分", "覆盖率")):
                cell.text = "{:.1f}%".format(random.uniform(70, 99.9))
            elif any(keyword in header for keyword in ("站点数", "用户数", "故障数", "数量", "预算", "支出", "收入", "利润", "流量", "时长", "速度", "次数", "频次", "投诉", "延迟", "覆盖", "活跃")):
                cell.text = str(random.randint(10, 999))
            elif any(keyword in header for keyword in ("负责人",)):
                cell.text = random.choice(self.PEOPLE)
            elif any(keyword in header for keyword in ("状态", "备注", "类型", "时段", "偏好", "设备")):
                cell.text = random.choice(self.STATUS)
            else:
                cell.text = self._fallback_value(cell.col)
        return schema

    def _values_from_llm(self, schema: TableSchema, plan: TablePlan, headers, row_headers):
        if not self.use_llm or self.llm_body_client is None:
            return None
        body_cells = [
            {
                "row": cell.row,
                "col": cell.col,
                "header": headers.get(cell.col, ""),
                "row_label": row_headers.get(cell.row, ""),
                "expected_type": self._expected_type(headers.get(cell.col, "")),
            }
            for cell in sorted(schema.cells, key=lambda item: (item.row, item.col))
            if cell.role == "body"
        ]
        values = self.llm_body_client.generate_body_values(
            domain=plan.domain,
            language=plan.language,
            topic=plan.topic,
            headers=[headers.get(col, "") for col in range(schema.cols)],
            row_headers=row_headers,
            body_cells=body_cells,
        )
        if not values:
            return None
        return values, body_cells

    def _apply_llm_values(self, schema: TableSchema, body_cells, values):
        schema_body_cells = [
            cell for cell in sorted(schema.cells, key=lambda item: (item.row, item.col))
            if cell.role == "body"
        ]
        if len(values) != len(schema_body_cells):
            return False
        if len(body_cells) != len(schema_body_cells):
            return False
        for schema_cell, value, body_meta in zip(schema_body_cells, values, body_cells):
            schema_cell.text = self._normalize_value(
                body_meta.get("expected_type", "text"),
                body_meta.get("header", ""),
                value,
            )
        return True

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
        if any(keyword in header for keyword in ("站点数", "用户数", "故障数", "数量", "预算", "支出", "收入", "利润", "流量", "时长", "速度", "次数", "频次", "投诉", "延迟", "覆盖", "活跃", "容量")):
            return "numeric"
        return "text"

    def _normalize_value(self, expected_type: str, header: str, value) -> str:
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
