import random
from typing import Callable, Optional

from ...types import TablePlan, TableRequest


class TopicAgent:
    """Plans the domain topic and high-level table attributes."""

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

    def __init__(
            self,
            llm_topic_client: Optional[object] = None,
            llm_topic_fn: Optional[Callable] = None,
            use_llm: bool = False):
        self.llm_topic_client = llm_topic_client
        self.llm_topic_fn = llm_topic_fn
        self.use_llm = use_llm
        self.used_topics = set()

    def plan(self, request: TableRequest) -> TablePlan:
        rows = random.randint(request.min_rows, request.max_rows)
        cols = random.randint(request.min_cols, request.max_cols)
        simple = request.simple if request.simple is not None else random.random() < 0.55
        colored = request.colored if request.colored is not None else random.random() < 0.4
        lined = request.lined if request.lined is not None else random.random() < 0.7
        topic = self._choose_topic(request)
        self.used_topics.add(topic)
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
        )

    def _choose_topic(self, request: TableRequest) -> str:
        if self.use_llm:
            topic = self._topic_from_llm(request)
            if topic:
                return topic
        return self._topic_from_rules(request)

    def _topic_from_llm(self, request: TableRequest) -> Optional[str]:
        try:
            if self.llm_topic_fn is not None:
                topic = self.llm_topic_fn(
                    domain=request.domain,
                    language=request.language,
                    used_topics=sorted(self.used_topics),
                )
            elif self.llm_topic_client is not None:
                topic = self.llm_topic_client.generate_topic(
                    domain=request.domain,
                    language=request.language,
                    used_topics=sorted(self.used_topics),
                )
            else:
                return None
        except Exception:
            return None
        return self._normalize_topic(topic)

    def _topic_from_rules(self, request: TableRequest) -> str:
        topics = self.TOPICS.get(request.domain, self.TOPICS["general"])
        available_topics = [topic for topic in topics if topic not in self.used_topics]
        if not available_topics:
            available_topics = topics
        return random.choice(available_topics)

    def _normalize_topic(self, topic) -> Optional[str]:
        if isinstance(topic, dict):
            topic = topic.get("topic")
        if not isinstance(topic, str):
            return None
        topic = topic.strip()
        if not topic or topic in self.used_topics:
            return None
        return topic
