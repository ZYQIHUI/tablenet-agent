import random
from typing import Callable, Optional

from ...agent_types import TablePlan, TableRequest
from ...domain.errors import ErrorCode, ValidationIssue
from ...domain.results import AgentResult, AgentSource


class TopicAgent:
    """Chooses domain topic/scenario without controlling structure or style."""

    TOPICS = {
        "telecommunications": [
            "5G基站月度维护统计",
            "宽带用户增长分析",
            "通信网络故障处理记录",
            "套餐收入与用户规模对比",
            "区域网络覆盖质量评估",
        ],
        "finance": [
            "季度营收与成本分析",
            "部门预算执行情况",
            "资产负债摘要",
        ],
        "general": [
            "项目进度统计",
            "设备巡检记录",
            "业务指标汇总",
        ],
    }

    SCENARIOS = {
        "telecommunications": {
            "base_station_maintenance": [
                "5G基站月度维护统计",
                "基站巡检与告警处理记录",
                "无线站点维护工单汇总",
            ],
            "network_coverage": [
                "区域网络覆盖质量评估",
                "弱覆盖小区优化跟踪",
                "城区网络覆盖提升分析",
            ],
            "customer_complaints": [
                "客户投诉受理与闭环统计",
                "服务工单处理效率分析",
                "网络质量投诉趋势跟踪",
            ],
            "package_revenue": [
                "套餐收入与用户规模对比",
                "移动套餐订购转化统计",
                "宽带融合套餐经营分析",
            ],
            "traffic_monitoring": [
                "移动数据流量高峰监控",
                "核心网流量负载日报",
                "用户上网行为流量分析",
            ],
            "broadband_installation": [
                "宽带装机与故障修复统计",
                "家庭宽带开通进度跟踪",
                "装维人员服务质量评估",
            ],
        },
        "finance": {
            "budget_execution": [
                "部门预算执行情况",
                "季度费用支出跟踪",
            ],
            "revenue_profit": [
                "季度营收与成本分析",
                "利润指标完成情况",
            ],
            "risk_status": [
                "资产负债摘要",
                "风险事项处置进展",
            ],
        },
        "general": {
            "project_tracking": [
                "项目进度统计",
                "阶段任务完成情况",
            ],
            "inspection": [
                "设备巡检记录",
                "问题整改跟踪表",
            ],
            "business_metrics": [
                "业务指标汇总",
                "运营数据日报",
            ],
        },
    }

    def __init__(
            self,
            llm_topic_client: Optional[object] = None,
            llm_topic_fn: Optional[Callable] = None,
            use_llm: bool = False,
            inner_memory=None):
        self.llm_topic_client = llm_topic_client
        self.llm_topic_fn = llm_topic_fn
        self.use_llm = use_llm
        self.inner_memory = inner_memory
        self.used_topics = set()
        self.last_result = None
        self._last_llm_error = None

    def plan(self, request: TableRequest) -> TablePlan:
        if self.inner_memory is not None:
            self.used_topics.update(self.inner_memory.topics())
        # Template mode: pre-generated template data takes priority
        if request.template_data:
            tpl = request.template_data
            rows = random.randint(request.min_rows, request.max_rows)
            cols = random.randint(request.min_cols, request.max_cols)
            simple = request.simple if request.simple is not None else random.random() < 0.55
            colored = request.colored if request.colored is not None else random.random() < 0.4
            lined = request.lined if request.lined is not None else random.random() < 0.7
            self.used_topics.add(tpl.get("topic", ""))
            if self.inner_memory is not None:
                self.inner_memory.remember_topic(
                    tpl.get("topic", ""),
                    {"domain": tpl.get("domain", request.domain), "source": "template"},
                )
            self.last_result = AgentResult.success(
                tpl,
                AgentSource.RULE,
                requested_mode="template",
                actual_source="template",
            )
            return TablePlan(
                domain=tpl.get("domain", request.domain),
                language=request.language,
                topic=tpl.get("topic", ""),
                rows=rows,
                cols=cols,
                simple=simple,
                colored=colored,
                lined=lined,
                config_id=request.config_id,
                semantic_scenario=tpl.get("semantic_scenario", "template"),
                structure_type=request.structure_type,
                template_headers=tpl.get("headers"),
                template_row_headers=tpl.get("row_headers"),
                template_group_headers=tpl.get("group_headers"),
            )

        rows = random.randint(request.min_rows, request.max_rows)
        cols = random.randint(request.min_cols, request.max_cols)
        simple = request.simple if request.simple is not None else random.random() < 0.55
        colored = request.colored if request.colored is not None else random.random() < 0.4
        lined = request.lined if request.lined is not None else random.random() < 0.7
        semantic_scenario, topic, llm_plan = self._choose_topic(request)
        if request.structure_type == "multi_level_column_header" and rows < 5:
            if request.max_rows < 5:
                raise ValueError(
                    "unsupported request: multi_level_column_header requires max_rows >= 5"
                )
            rows = 5
        self.used_topics.add(topic)
        if self.inner_memory is not None:
            self.inner_memory.remember_topic(
                topic,
                {"domain": request.domain, "scenario": semantic_scenario},
            )
        return TablePlan(
            domain=request.domain,
            language=request.language,
            topic=topic,
            rows=rows,
            cols=cols,
            simple=simple,
            colored=colored,
            lined=lined,
            config_id=request.config_id,
            semantic_scenario=semantic_scenario,
            structure_type=request.structure_type,
        )

    def _choose_topic(self, request: TableRequest):
        if self.use_llm:
            topic_plan = self._topic_from_llm(request)
            if topic_plan:
                self.last_result = AgentResult.success(
                    topic_plan,
                    self._client_source(),
                    requested_mode="model",
                    actual_source=self._client_source().value,
                    backend_metadata=self._backend_metadata(),
                )
                scenario = self._normalize_text(topic_plan.get("semantic_scenario")) or "llm_generated"
                return scenario, topic_plan["topic"], topic_plan
        scenario, topic = self._topic_from_rules(request)
        if self.use_llm:
            reason = self._last_llm_error or "model output was unavailable or invalid"
            self.last_result = AgentResult.fallback(
                {"topic": topic, "semantic_scenario": scenario},
                AgentSource.RULE,
                errors=[ValidationIssue(ErrorCode.LLM_CALL_FAILED, reason)],
                requested_mode="model",
                actual_source="rule",
                fallback_reason=reason,
                backend_metadata=self._backend_metadata(),
            )
        else:
            self.last_result = AgentResult.success(
                {"topic": topic, "semantic_scenario": scenario},
                AgentSource.RULE,
                requested_mode="rule",
                actual_source="rule",
            )
        return scenario, topic, None

    def _topic_from_llm(self, request: TableRequest) -> Optional[dict]:
        self._last_llm_error = None
        try:
            if self.llm_topic_fn is not None:
                topic = self._call_topic_fn(request)
            elif self.llm_topic_client is not None:
                topic = self.llm_topic_client.generate_topic(
                    domain=request.domain,
                    language=request.language,
                    used_topics=sorted(self.used_topics),
                    min_rows=request.min_rows,
                    max_rows=request.max_rows,
                    min_cols=request.min_cols,
                    max_cols=request.max_cols,
                )
            else:
                self._last_llm_error = "no topic model client configured"
                return None
        except Exception as exc:
            self._last_llm_error = str(exc)
            return None
        normalized = self._normalize_topic_plan(topic, request)
        if normalized is None:
            self._last_llm_error = "topic model returned an invalid or duplicate plan"
        return normalized

    def _client_source(self):
        source = getattr(self.llm_topic_client, "backend_source", "api")
        if source == "local_model":
            return AgentSource.LOCAL_MODEL
        return AgentSource.API

    def _backend_metadata(self):
        result = getattr(self.llm_topic_client, "last_result", None)
        return getattr(result, "metadata", {})

    def _call_topic_fn(self, request: TableRequest):
        try:
            return self.llm_topic_fn(
                domain=request.domain,
                language=request.language,
                used_topics=sorted(self.used_topics),
                min_rows=request.min_rows,
                max_rows=request.max_rows,
                min_cols=request.min_cols,
                max_cols=request.max_cols,
            )
        except TypeError:
            return self.llm_topic_fn(
                domain=request.domain,
                language=request.language,
                used_topics=sorted(self.used_topics),
            )

    def _topic_from_rules(self, request: TableRequest):
        scenarios = self.SCENARIOS.get(request.domain, self.SCENARIOS["general"])
        scenario = random.choice(list(scenarios))
        topics = scenarios[scenario]
        available_topics = [topic for topic in topics if topic not in self.used_topics]
        if not available_topics:
            available_topics = topics
        return scenario, random.choice(available_topics)

    def _normalize_topic_plan(self, value, request: TableRequest) -> Optional[dict]:
        if isinstance(value, str):
            value = {"topic": value}
        if not isinstance(value, dict):
            return None
        topic = self._normalize_text(value.get("topic"))
        if not topic or topic in self.used_topics:
            return None
        plan = dict(value)
        plan["topic"] = topic
        if self._normalize_text(plan.get("domain")) is None:
            plan["domain"] = request.domain
        return plan

    def _normalize_text(self, value) -> Optional[str]:
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    def _bounded_int(self, value, lower: int, upper: int, fallback: int) -> int:
        if isinstance(value, bool):
            return fallback
        try:
            value = int(value)
        except (TypeError, ValueError):
            return fallback
        return max(lower, min(upper, value))

    def _coerce_optional_bool(self, value, fallback: bool, requested):
        if requested is not None:
            return requested
        if isinstance(value, bool):
            return value
        return fallback
