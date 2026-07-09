import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.sub_agents.fillers.body_agent import BodyAgent
from agents.sub_agents.fillers.header_agent import HeaderAgent
from agents.sub_agents.planners.schema_agent import SchemaAgent
from agents.sub_agents.planners.topic_agent import TopicAgent
from agents.tools.adapters.llm_topic_client import LLMTopicClient
from agents.types import Cell, TablePlan, TableRequest, TableSchema


class FakeTopicClient:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def generate_topic(self, **kwargs):
        self.calls += 1
        return self.response


class FakeHeaderClient:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def generate_headers(self, **kwargs):
        self.calls += 1
        return self.response


class FakeBodyClient:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def generate_body_values(self, **kwargs):
        self.calls += 1
        return self.response


class BadJsonTopicClient(LLMTopicClient):
    def _chat_completion(self, prompt: str) -> str:
        return "{not json"


class LLMFallbackTest(unittest.TestCase):
    def test_topic_agent_uses_llm_plan_and_clamps_shape(self):
        client = FakeTopicClient({
            "topic": "政企专线服务质量日报",
            "domain": "telecommunications",
            "semantic_scenario": "enterprise_service_quality",
            "rows": 99,
            "cols": 1,
            "attributes": {"simple": False, "colored": True, "lined": False},
        })
        request = TableRequest(domain="telecommunications", min_rows=4, max_rows=6, min_cols=3, max_cols=5)
        plan = TopicAgent(llm_topic_client=client, use_llm=True).plan(request)
        self.assertEqual(client.calls, 1)
        self.assertEqual(plan.topic, "政企专线服务质量日报")
        self.assertEqual(plan.semantic_scenario, "enterprise_service_quality")
        self.assertEqual(plan.rows, 6)
        self.assertEqual(plan.cols, 3)
        self.assertFalse(plan.simple)
        self.assertTrue(plan.colored)
        self.assertFalse(plan.lined)

    def test_bad_json_topic_client_falls_back_to_rules(self):
        client = BadJsonTopicClient(api_key="key", base_url="https://example.invalid/v1", model="fake")
        agent = TopicAgent(llm_topic_client=client, use_llm=True)
        plan = agent.plan(TableRequest(domain="telecommunications"))
        self.assertIn(plan.semantic_scenario, TopicAgent.SCENARIOS["telecommunications"])
        self.assertIn(plan.topic, TopicAgent.SCENARIOS["telecommunications"][plan.semantic_scenario])

    def test_rule_mode_topic_does_not_call_client(self):
        client = FakeTopicClient({"topic": "不应调用"})
        plan = TopicAgent(llm_topic_client=client, use_llm=False).plan(TableRequest(domain="telecommunications"))
        self.assertEqual(client.calls, 0)
        self.assertNotEqual(plan.topic, "不应调用")

    def test_header_agent_uses_valid_llm_text_lists(self):
        plan = TablePlan(
            domain="telecommunications",
            language="zh",
            topic="政企专线服务质量日报",
            rows=4,
            cols=4,
            simple=True,
            colored=False,
            lined=True,
            semantic_scenario="unknown",
        )
        client = FakeHeaderClient({
            "headers": ["客户名称", "专线带宽", "可用率", "处理状态"],
            "group_headers": ["客户信息", "网络指标"],
            "row_headers": ["客户A", "客户B"],
        })
        schema = SchemaAgent().build(plan)
        HeaderAgent(llm_header_client=client, use_llm=True).fill(schema, plan)
        header_texts = [cell.text for cell in schema.cells if cell.role == "header"]
        self.assertEqual(client.calls, 1)
        self.assertIn("客户名称", header_texts)
        self.assertIn("专线带宽", header_texts)

    def test_rule_mode_header_does_not_call_client(self):
        plan = TablePlan(
            domain="telecommunications",
            language="zh",
            topic="政企专线服务质量日报",
            rows=4,
            cols=4,
            simple=True,
            colored=False,
            lined=True,
            semantic_scenario="unknown",
        )
        client = FakeHeaderClient({"headers": ["不应调用"]})
        schema = SchemaAgent().build(plan)
        HeaderAgent(llm_header_client=client, use_llm=False).fill(schema, plan)
        header_texts = [cell.text for cell in schema.cells if cell.role == "header"]
        self.assertEqual(client.calls, 0)
        self.assertNotIn("不应调用", header_texts)

    def test_header_agent_bad_shape_falls_back(self):
        plan = TablePlan(
            domain="telecommunications",
            language="zh",
            topic="政企专线服务质量日报",
            rows=4,
            cols=4,
            simple=True,
            colored=False,
            lined=True,
            semantic_scenario="unknown",
        )
        schema = SchemaAgent().build(plan)
        HeaderAgent(llm_header_client=FakeHeaderClient({"headers": [{"bad": "shape"}]}), use_llm=True).fill(schema, plan)
        header_texts = [cell.text for cell in schema.cells if cell.role == "header"]
        self.assertIn("区域", header_texts)

    def test_body_agent_uses_valid_llm_values_and_mapping(self):
        plan = TablePlan(
            domain="telecommunications",
            language="zh",
            topic="客户增长",
            rows=2,
            cols=2,
            simple=True,
            colored=False,
            lined=True,
        )
        schema = TableSchema(
            rows=2,
            cols=2,
            cells=[
                Cell(row=0, col=0, tag="th", role="header", text="区域"),
                Cell(row=0, col=1, tag="th", role="header", text="用户数"),
                Cell(row=1, col=0, tag="td", role="body"),
                Cell(row=1, col=1, tag="td", role="body"),
            ],
        )
        client = FakeBodyClient({"1,0": "东区", "1,1": "88"})
        BodyAgent(llm_body_client=client, use_llm=True).fill(schema, plan)
        self.assertEqual(client.calls, 1)
        self.assertEqual([cell.text for cell in schema.cells if cell.role == "body"], ["东区", "88"])

    def test_rule_mode_body_does_not_call_client(self):
        plan = TablePlan(
            domain="telecommunications",
            language="zh",
            topic="客户增长",
            rows=2,
            cols=2,
            simple=True,
            colored=False,
            lined=True,
        )
        schema = TableSchema(
            rows=2,
            cols=2,
            cells=[
                Cell(row=0, col=0, tag="th", role="header", text="区域"),
                Cell(row=0, col=1, tag="th", role="header", text="用户数"),
                Cell(row=1, col=0, tag="td", role="body"),
                Cell(row=1, col=1, tag="td", role="body"),
            ],
        )
        client = FakeBodyClient(["不应调用", "不应调用"])
        BodyAgent(llm_body_client=client, use_llm=False).fill(schema, plan)
        body_texts = [cell.text for cell in schema.cells if cell.role == "body"]
        self.assertEqual(client.calls, 0)
        self.assertNotIn("不应调用", body_texts)

    def test_body_agent_bad_shape_falls_back(self):
        plan = TablePlan(
            domain="telecommunications",
            language="zh",
            topic="客户增长",
            rows=2,
            cols=2,
            simple=True,
            colored=False,
            lined=True,
        )
        schema = TableSchema(
            rows=2,
            cols=2,
            cells=[
                Cell(row=0, col=0, tag="th", role="header", text="区域"),
                Cell(row=0, col=1, tag="th", role="header", text="用户数"),
                Cell(row=1, col=0, tag="td", role="body"),
                Cell(row=1, col=1, tag="td", role="body"),
            ],
        )
        BodyAgent(llm_body_client=FakeBodyClient(["only one value"]), use_llm=True).fill(schema, plan)
        body_texts = [cell.text for cell in schema.cells if cell.role == "body"]
        self.assertEqual(len(body_texts), 2)
        self.assertTrue(all(body_texts))


if __name__ == "__main__":
    unittest.main()
