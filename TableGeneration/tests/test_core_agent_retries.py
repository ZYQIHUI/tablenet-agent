import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.core_agent import CoreAgent
from agents.sub_agents.validators.filling_checker import FillingCheckReport
from agents.types import AgentTable, Cell, TablePlan, TableRequest, TableSchema, TableStyle


class StaticTopicAgent:
    def plan(self, request):
        return TablePlan(
            domain="telecommunications",
            language="zh",
            topic="重试测试",
            rows=2,
            cols=2,
            simple=True,
            colored=False,
            lined=True,
        )


class StaticStyleAgent:
    def build(self, plan):
        return TableStyle("test_style", "", "", "")


class SequenceSchemaAgent:
    def __init__(self, schemas):
        self.schemas = list(schemas)
        self.calls = 0

    def build(self, plan):
        self.calls += 1
        if len(self.schemas) > 1:
            return self.schemas.pop(0)
        return self.schemas[0]


class NoopFiller:
    def __init__(self):
        self.calls = 0

    def fill(self, schema, plan):
        self.calls += 1
        return schema


class SequenceValidator:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def validate(self, schema):
        self.calls += 1
        if len(self.results) > 1:
            return self.results.pop(0)
        return self.results[0]


class SequenceFillingChecker:
    def __init__(self, reports):
        self.reports = list(reports)
        self.calls = 0

    def evaluate(self, schema, plan):
        self.calls += 1
        if len(self.reports) > 1:
            return self.reports.pop(0)
        return self.reports[0]


class StaticHtmlBuilder:
    def build(self, plan, schema, style):
        return AgentTable(plan, schema, style, "<table></table>", [], len(schema.cells))


def schema():
    return TableSchema(
        rows=2,
        cols=2,
        cells=[
            Cell(row=0, col=0, tag="th", role="header", cell_id=0),
            Cell(row=0, col=1, tag="th", role="header", cell_id=1),
            Cell(row=1, col=0, tag="td", role="body", cell_id=2),
            Cell(row=1, col=1, tag="td", role="body", cell_id=3),
        ],
    )


def report(ok, score=1.0, header=1.0, body=1.0):
    return FillingCheckReport(
        ok=ok,
        score=score,
        title_score=1.0,
        header_score=header,
        body_score=body,
        errors=[] if ok else ["synthetic filling issue"],
    )


class CoreAgentRetriesTest(unittest.TestCase):
    def agent(self):
        agent = CoreAgent(
            topic_agent=StaticTopicAgent(),
            header_agent=NoopFiller(),
            body_agent=NoopFiller(),
            max_schema_retries=3,
            max_filling_retries=2,
        )
        agent.style_agent = StaticStyleAgent()
        agent.html_builder = StaticHtmlBuilder()
        return agent

    def test_retries_filling_before_returning_table(self):
        agent = self.agent()
        agent.schema_agent = SequenceSchemaAgent([schema()])
        agent.validator_agent = SequenceValidator([(True, [])])
        agent.filling_checker = SequenceFillingChecker([
            report(False, score=0.4, body=0.3),
            report(True),
        ])
        table = agent.generate(TableRequest())
        self.assertEqual(table.html, "<table></table>")
        self.assertEqual(agent.schema_agent.calls, 1)
        self.assertEqual(agent.filling_checker.calls, 2)
        self.assertEqual(agent.body_agent.calls, 2)

    def test_rebuilds_schema_after_structure_failure(self):
        agent = self.agent()
        agent.schema_agent = SequenceSchemaAgent([schema(), schema()])
        agent.validator_agent = SequenceValidator([
            (False, ["overlapped cell"]),
            (True, []),
        ])
        agent.filling_checker = SequenceFillingChecker([report(True)])
        table = agent.generate(TableRequest())
        self.assertEqual(table.html, "<table></table>")
        self.assertEqual(agent.schema_agent.calls, 2)
        self.assertEqual(agent.filling_checker.calls, 1)


if __name__ == "__main__":
    unittest.main()
