import sys
import unittest
import json
from io import StringIO
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.backends import BackendRegistry, BackendRouter
from agents.backends.api import ApiCallableBackend
from agents.backends.router import BackendRoute
from agents.backends.rule import RuleCallableBackend
from agents.capabilities import CapabilityRequest
from agents.domain import AgentSource, AgentStatus, GenerationState
from agents.domain import BudgetExceeded, BudgetLimits, BudgetTracker
from agents.domain.state import CandidateState
from agents.evaluation import ScorePolicy
from agents.filling import CandidatePool, CandidateSelector
from agents.orchestration import RepairRouter
from agents.agent_types import Cell, TablePlan, TableRequest, TableSchema
from agents.sub_agents.fillers.body_agent import BodyAgent
from agents.sub_agents.validators.filling_checker import FillingCheckReport
from agents.sub_agents.planners.topic_agent import TopicAgent
from agents.run_agents import build_semantic_clients, use_llm
from agents.observability import TraceRecorder


class AgentArchitectureTest(unittest.TestCase):
    def test_backend_router_records_explicit_rule_fallback(self):
        def unavailable(**kwargs):
            raise RuntimeError("api unavailable")

        api = ApiCallableBackend({"topic_generation": unavailable}, name="remote")
        rule = RuleCallableBackend(
            {"topic_generation": lambda domain: f"{domain} topic"},
            name="rules",
        )
        router = BackendRouter(
            BackendRegistry([api, rule]),
            {"topic_generation": BackendRoute("remote", ("rules",))},
        )

        result = router.execute(CapabilityRequest("topic_generation", {"domain": "telecom"}))

        self.assertEqual(result.value, "telecom topic")
        self.assertEqual(result.status, AgentStatus.FALLBACK)
        self.assertEqual(result.source, AgentSource.RULE)
        self.assertEqual(result.metadata["requested_backend"], "remote")
        self.assertEqual(result.metadata["actual_backend"], "rules")
        self.assertEqual(len(result.metadata["attempts"]), 2)

    def test_generation_state_tracks_candidates_and_selection(self):
        state = GenerationState(TableRequest())
        first = state.increment("schema_attempts")
        state.record("schema", "build", attempt=first)

        self.assertTrue(state.request_id.startswith("req_"))
        self.assertEqual(state.retry_counters["schema_attempts"], 1)
        self.assertEqual(state.events[0].stage, "schema")

    def test_repair_router_extracts_cell_and_column_targets(self):
        report = FillingCheckReport(
            ok=False,
            score=0.4,
            title_score=1.0,
            header_score=1.0,
            body_score=0.4,
            errors=["numeric-like column has non-numeric value at (3, 2)"],
        )

        decision = RepairRouter().for_filling_report(report)

        self.assertEqual(decision.target_cells, ((3, 2),))
        self.assertEqual(decision.target_columns, (2,))

    def test_body_agent_preserves_cells_outside_repair_scope(self):
        plan = TablePlan(
            domain="telecommunications",
            language="zh",
            topic="局部修复",
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
                Cell(0, 0, role="header", text="区域"),
                Cell(0, 1, role="header", text="用户数"),
                Cell(1, 0, role="body", text="必须保留"),
                Cell(1, 1, role="body", text="错误值"),
            ],
        )

        BodyAgent().fill(
            schema,
            plan,
            target_cells=[(1, 1)],
            preserve_existing=True,
        )

        self.assertEqual(schema.cells[2].text, "必须保留")
        self.assertNotEqual(schema.cells[3].text, "错误值")
        self.assertTrue(schema.cells[3].text.isdigit())

    def test_local_backend_mode_reuses_one_lazy_client(self):
        args = Namespace(
            backend_mode="local",
            local_model_path="D:/models/Qwen2-VL-2B-Instruct",
            local_model_device="auto",
            local_model_max_new_tokens=256,
            local_model_temperature=0.2,
        )

        clients = build_semantic_clients(args, True, True, True)

        self.assertEqual(len(clients), 5)
        self.assertTrue(all(client is clients[0] for client in clients))
        local_backend = clients[0].router.registry.get("local")
        local_client = local_backend.capabilities["request_planning"][0]
        self.assertIsNone(local_client._model)
        self.assertTrue(use_llm(args, "topic"))

    def test_topic_agent_exposes_rule_fallback_reason(self):
        class BrokenClient:
            backend_source = "local_model"

            def generate_topic(self, **kwargs):
                raise RuntimeError("model offline")

        agent = TopicAgent(llm_topic_client=BrokenClient(), use_llm=True)
        agent.plan(TableRequest())

        self.assertEqual(agent.last_result.status, AgentStatus.FALLBACK)
        self.assertEqual(agent.last_result.source, AgentSource.RULE)
        self.assertEqual(agent.last_result.metadata["actual_source"], "rule")
        self.assertIn("model offline", agent.last_result.metadata["fallback_reason"])

    def test_candidate_pool_rejects_equivalent_schema_and_content(self):
        schema = TableSchema(
            rows=1,
            cols=1,
            cells=[Cell(0, 0, role="body", text="  SAME   VALUE ")],
        )
        equivalent = TableSchema(
            rows=1,
            cols=1,
            cells=[Cell(0, 0, role="body", text="same value")],
        )
        pool = CandidatePool()

        self.assertTrue(pool.add(CandidateState(schema=schema)))
        duplicate = CandidateState(schema=equivalent)
        self.assertFalse(pool.add(duplicate))
        self.assertTrue(duplicate.metadata["duplicate"])

    def test_score_policy_rejects_low_dimension_despite_high_average(self):
        report = FillingCheckReport(
            ok=True,
            score=0.85,
            title_score=1.0,
            header_score=1.0,
            body_score=1.0,
            topic_consistency_score=0.2,
        )

        scores = ScorePolicy(minimum_dimension_score=0.58).evaluate(
            {"ok": True, "errors": []},
            report,
        )

        self.assertGreater(scores.ranking, 0.7)
        self.assertEqual(scores.overall, 0.2)
        self.assertFalse(scores.passed)

    def test_selector_chooses_best_candidate_after_hard_gate(self):
        def candidate(topic_score, body_score):
            item = CandidateState(schema=TableSchema(1, 1, [Cell(0, 0, text=str(topic_score))]))
            item.validation_result = {"ok": True, "errors": []}
            item.checker_report = FillingCheckReport(
                ok=True,
                score=0.8,
                title_score=1.0,
                header_score=0.9,
                body_score=body_score,
                topic_consistency_score=topic_score,
            )
            return item

        lower = candidate(0.7, 0.7)
        higher = candidate(0.9, 0.9)
        selected = CandidateSelector().select([lower, higher])

        self.assertIs(selected, higher)
        self.assertEqual(selected.metadata["selection_reason"], "highest_ranking_score_after_hard_gate")

    def test_trace_recorder_serializes_candidate_lineage_and_scores(self):
        state = GenerationState(TableRequest())
        parent = CandidateState(schema=TableSchema(1, 1, [Cell(0, 0, text="x")]))
        child = CandidateState(
            schema=TableSchema(1, 1, [Cell(0, 0, text="y")]),
            parent_candidate_id=parent.candidate_id,
            transformation="alter",
        )
        state.candidates.extend([parent, child])
        state.select(child)
        output = StringIO()

        TraceRecorder(output).write(state, outcome="success")
        record = json.loads(output.getvalue())

        self.assertEqual(record["selected_candidate_id"], child.candidate_id)
        self.assertEqual(record["candidates"][1]["parent_candidate_id"], parent.candidate_id)
        self.assertEqual(record["candidates"][1]["transformation"], "alter")

    def test_budget_tracker_terminates_on_candidate_limit(self):
        tracker = BudgetTracker(BudgetLimits(max_candidates=1))
        tracker.consume("candidates")

        with self.assertRaises(BudgetExceeded):
            tracker.consume("candidates")

        self.assertEqual(tracker.snapshot()["candidates"], 2)


if __name__ == "__main__":
    unittest.main()
