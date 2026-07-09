import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.sub_agents.fillers.header_agent import HeaderAgent
from agents.sub_agents.planners.schema_agent import SchemaAgent
from agents.sub_agents.planners.topic_agent import TopicAgent
from agents.types import TablePlan, TableRequest


class SemanticTemplatesTest(unittest.TestCase):
    def test_rule_topic_agent_assigns_telecom_scenario(self):
        agent = TopicAgent(use_llm=False)
        plan = agent.plan(TableRequest(domain="telecommunications"))
        self.assertIn(plan.semantic_scenario, TopicAgent.SCENARIOS["telecommunications"])
        scenario_topics = TopicAgent.SCENARIOS["telecommunications"][plan.semantic_scenario]
        self.assertIn(plan.topic, scenario_topics)

    def test_header_agent_uses_scenario_specific_headers(self):
        plan = TablePlan(
            domain="telecommunications",
            language="zh",
            topic="客户投诉受理与闭环统计",
            rows=5,
            cols=5,
            simple=True,
            colored=False,
            lined=True,
            semantic_scenario="customer_complaints",
        )
        schema = SchemaAgent().build(plan)
        HeaderAgent().fill(schema, plan)
        header_texts = [cell.text for cell in schema.cells if cell.role == "header"]
        self.assertIn("投诉类型", header_texts)
        self.assertIn("受理量", header_texts)
        self.assertNotIn("站点数", header_texts[:3])


if __name__ == "__main__":
    unittest.main()
