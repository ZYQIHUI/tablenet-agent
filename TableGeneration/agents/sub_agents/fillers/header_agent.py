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

    SCENARIO_HEADERS = {
        "base_station_maintenance": {
            "headers": ["基站编号", "所属区域", "巡检日期", "告警次数", "处理时长", "维护人员", "维护状态", "备注"],
            "group_headers": ["站点信息", "巡检记录", "告警处理", "维护结果"],
            "row_headers": ["宏站A", "宏站B", "室分点", "边缘站", "核心站", "应急站"],
        },
        "network_coverage": {
            "headers": ["区域", "覆盖率", "弱覆盖点", "平均速率", "掉线率", "优化次数", "验收状态", "优化建议"],
            "group_headers": ["覆盖范围", "质量指标", "优化动作", "验收结果"],
            "row_headers": ["东区", "西区", "南区", "北区", "中心区", "新区"],
        },
        "customer_complaints": {
            "headers": ["投诉类型", "受理量", "完结量", "平均响应时长", "满意度", "责任部门", "处理状态", "复核意见"],
            "group_headers": ["投诉来源", "处理效率", "客户反馈", "闭环状态"],
            "row_headers": ["网络慢", "频繁掉线", "计费疑问", "装维延迟", "信号弱", "服务态度"],
        },
        "package_revenue": {
            "headers": ["套餐名称", "订购用户", "新增用户", "退订用户", "月收入", "ARPU", "转化率", "同比"],
            "group_headers": ["套餐信息", "用户规模", "收入表现", "增长趋势"],
            "row_headers": ["畅享套餐", "融合套餐", "校园套餐", "政企套餐", "家庭套餐", "流量包"],
        },
        "traffic_monitoring": {
            "headers": ["监控时段", "总流量", "峰值带宽", "活跃用户", "拥塞小区", "平均时延", "丢包率", "扩容建议"],
            "group_headers": ["时段信息", "流量负载", "网络质量", "容量规划"],
            "row_headers": ["早高峰", "午间", "晚高峰", "夜间", "节假日", "工作日"],
        },
        "broadband_installation": {
            "headers": ["装机区域", "预约量", "完成量", "超时单", "修复时长", "装维人员", "客户评分", "工单状态"],
            "group_headers": ["区域信息", "装机进度", "修复效率", "服务评价"],
            "row_headers": ["东区", "西区", "南区", "北区", "老城区", "新小区"],
        },
    }

    def __init__(self, llm_header_client=None, use_llm=False):
        self.llm_header_client = llm_header_client
        self.use_llm = use_llm

    def fill(self, schema: TableSchema, plan: TablePlan) -> TableSchema:
        headers = self.HEADERS.get(plan.domain, self.HEADERS["general"])
        group_headers = self.GROUP_HEADERS.get(plan.domain, self.GROUP_HEADERS["general"])
        row_headers = self.ROW_HEADERS.get(plan.domain, self.ROW_HEADERS["general"])
        scenario_headers = self.SCENARIO_HEADERS.get(plan.semantic_scenario)
        if scenario_headers:
            headers = scenario_headers["headers"]
            group_headers = scenario_headers["group_headers"]
            row_headers = scenario_headers["row_headers"]
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
