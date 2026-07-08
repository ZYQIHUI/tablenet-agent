from ...types import TablePlan, TableSchema


class HeaderAgent:
    """Fills title and header cells with domain-aware labels."""

    GROUP_HEADERS = {
        "telecommunications": ["基础信息", "网络规模", "服务质量", "经营指标"],
        "finance": ["组织信息", "预算执行", "收益指标", "风险状态"],
        "general": ["基础信息", "执行情况", "质量指标", "补充说明"],
    }

    ROW_HEADERS = {
        "telecommunications": ["东区", "西区", "南区", "北区", "中心区", "新区"],
        "finance": ["研发部", "市场部", "运营部", "财务部", "客服部", "采购部"],
        "general": ["阶段一", "阶段二", "阶段三", "阶段四", "阶段五", "阶段六"],
    }

    HEADERS = {
        "telecommunications": [
            "区域",
            "站点数",
            "用户数",
            "故障数",
            "完成率",
            "收入",
            "同比",
            "备注",
        ],
        "finance": [
            "部门",
            "预算",
            "支出",
            "收入",
            "利润",
            "同比",
            "状态",
            "备注",
        ],
        "general": [
            "项目",
            "负责人",
            "数量",
            "进度",
            "状态",
            "评分",
            "日期",
            "备注",
        ],
    }

    def __init__(self, llm_header_client=None, use_llm=False):
        self.llm_header_client = llm_header_client
        self.use_llm = use_llm

    def fill(self, schema: TableSchema, plan: TablePlan) -> TableSchema:
        headers = self.HEADERS.get(plan.domain, self.HEADERS["general"])
        group_headers = self.GROUP_HEADERS.get(plan.domain, self.GROUP_HEADERS["general"])
        row_headers = self.ROW_HEADERS.get(plan.domain, self.ROW_HEADERS["general"])
        llm_headers = self._headers_from_llm(plan)
        if llm_headers:
            headers = self._merge_headers(headers, llm_headers.get("headers"))
            group_headers = self._merge_headers(group_headers, llm_headers.get("group_headers"))
            row_headers = self._merge_headers(row_headers, llm_headers.get("row_headers"))
        for cell in schema.cells:
            if cell.role == "title":
                cell.text = plan.topic
            elif cell.role == "header":
                cell.text = self._header_text(cell, headers, group_headers, row_headers)
        return schema

    def _headers_from_llm(self, plan: TablePlan):
        if not self.use_llm or self.llm_header_client is None:
            return None
        return self.llm_header_client.generate_headers(
            domain=plan.domain,
            language=plan.language,
            topic=plan.topic,
            cols=plan.cols,
        )

    def _merge_headers(self, fallback, generated):
        if not generated:
            return fallback
        merged = list(generated)
        for item in fallback:
            if item not in merged:
                merged.append(item)
        return merged

    def _header_text(self, cell, headers, group_headers, row_headers):
        if cell.colspan > 1:
            group_index = max(0, cell.col - 1) % len(group_headers)
            return group_headers[group_index]
        if cell.rowspan > 1 and cell.row <= 2:
            return headers[cell.col % len(headers)]
        if cell.row > 1 and cell.col == 0:
            return row_headers[(cell.row - 2) % len(row_headers)]
        return headers[cell.col % len(headers)]
