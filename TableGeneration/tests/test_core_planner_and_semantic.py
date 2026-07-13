import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.agent_types import Cell, TablePlan, TableRequest, TableSchema
from agents.domain import AgentSource, AgentStatus
from agents.evaluation import SemanticEvaluator
from agents.planners import CorePlanner
from agents.sub_agents.validators.filling_checker import FillingChecker
from agents.core_agent import CoreAgent


class FakeCoreClient:
    backend_source = "local_model"

    def plan_request(self, request_text, defaults):
        return {
            "domain": "finance",
            "min_rows": 5,
            "max_rows": 8,
            "simple": False,
            "forbidden_tool": "delete files",
        }


class FakeSemanticClient:
    backend_source = "api"

    def __init__(self, topic=0.9, semantic=0.8):
        self.topic = topic
        self.semantic = semantic

    def evaluate_semantics(self, topic, domain, headers, rows):
        return {
            "topic_score": self.topic,
            "semantic_score": self.semantic,
            "errors": [],
            "evidence": ["anonymous evaluation"],
        }


def plan():
    return TablePlan(
        domain="telecommunications",
        language="zh",
        topic="区域用户统计",
        rows=2,
        cols=2,
        simple=True,
        colored=False,
        lined=True,
    )


def schema():
    return TableSchema(2, 2, [
        Cell(0, 0, role="header", text="区域", cell_id=0),
        Cell(0, 1, role="header", text="用户数", cell_id=1),
        Cell(1, 0, role="body", text="东区", cell_id=2),
        Cell(1, 1, role="body", text="10", cell_id=3),
    ])


class CorePlannerAndSemanticTest(unittest.TestCase):
    def test_core_planner_applies_only_valid_whitelisted_fields(self):
        request = TableRequest(natural_language_request="生成复杂财务表")
        planner = CorePlanner(FakeCoreClient(), use_model=True)

        result = planner.plan(request)

        self.assertEqual(result.domain, "finance")
        self.assertEqual((result.min_rows, result.max_rows), (5, 8))
        self.assertFalse(result.simple)
        self.assertFalse(hasattr(result, "forbidden_tool"))
        self.assertEqual(planner.last_result.status, AgentStatus.SUCCESS)
        self.assertEqual(planner.last_result.source, AgentSource.LOCAL_MODEL)

    def test_core_planner_invalid_bounds_fall_back_to_original_request(self):
        class BadClient:
            def plan_request(self, request_text, defaults):
                return {"min_rows": 9, "max_rows": 2}

        request = TableRequest(natural_language_request="bad")
        planner = CorePlanner(BadClient(), use_model=True)
        result = planner.plan(request)

        self.assertIs(result, request)
        self.assertEqual(planner.last_result.status, AgentStatus.FALLBACK)

    def test_filling_checker_uses_model_semantic_scores(self):
        evaluator = SemanticEvaluator(FakeSemanticClient(topic=0.85, semantic=0.75), use_model=True)
        report = FillingChecker(semantic_evaluator=evaluator).evaluate(schema(), plan())

        self.assertEqual(report.llm_topic_score, 0.85)
        self.assertEqual(report.llm_semantic_score, 0.75)
        self.assertEqual(report.semantic_evaluator["evidence"], ["anonymous evaluation"])

    def test_low_model_semantic_score_is_a_hard_error(self):
        evaluator = SemanticEvaluator(FakeSemanticClient(topic=0.9, semantic=0.2), use_model=True)
        report = FillingChecker(semantic_evaluator=evaluator).evaluate(schema(), plan())

        self.assertFalse(report.ok)
        self.assertIn("LLM evaluator rejected semantic consistency", report.errors)

    def test_core_records_explicit_budget_exhaustion(self):
        core = CoreAgent(max_candidates=0)
        request = TableRequest(
            min_rows=2,
            max_rows=2,
            min_cols=2,
            max_cols=2,
            simple=True,
        )

        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            core.generate(request)

        self.assertEqual(core.last_state.events[-1].stage, "budget")
        self.assertEqual(core.last_state.events[-1].action, "exhausted")


if __name__ == "__main__":
    unittest.main()
