import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.sub_agents.planners.schema_agent import SchemaAgent
from agents.sub_agents.validators.validator_agent import ValidatorAgent
from agents.types import Cell, TablePlan, TableSchema


def assign_ids(cells):
    for idx, cell in enumerate(cells):
        cell.cell_id = idx
    return cells


class ValidatorAgentTest(unittest.TestCase):
    def setUp(self):
        self.validator = ValidatorAgent()
        self.schema_agent = SchemaAgent()

    def plan(self, simple=False):
        return TablePlan(
            domain="telecommunications",
            language="zh",
            topic="结构验证样例",
            rows=6,
            cols=4,
            simple=simple,
            colored=False,
            lined=True,
        )

    def assert_valid(self, schema):
        ok, errors = self.validator.validate(schema)
        self.assertTrue(ok, errors)

    def assert_invalid_contains(self, schema, expected):
        ok, errors = self.validator.validate(schema)
        self.assertFalse(ok)
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_simple_table_passes(self):
        self.assert_valid(self.schema_agent._simple(self.plan(simple=True)))

    def test_title_colspan_table_passes(self):
        schema = self.schema_agent._title_header(self.plan())
        self.assert_valid(schema)
        self.assertTrue(schema.has_colspan)
        self.assertEqual(schema.header_type, "title_header")

    def test_grouped_columns_table_passes(self):
        schema = self.schema_agent._grouped_columns(self.plan())
        self.assert_valid(schema)
        self.assertTrue(schema.has_rowspan)
        self.assertTrue(schema.has_colspan)
        self.assertEqual(schema.header_type, "grouped_columns")

    def test_span_out_of_range_fails(self):
        schema = TableSchema(
            rows=2,
            cols=2,
            cells=assign_ids([Cell(row=0, col=0, colspan=3)]),
        )
        self.assert_invalid_contains(schema, "span out of range")

    def test_overlapped_cell_fails(self):
        schema = TableSchema(
            rows=2,
            cols=2,
            cells=assign_ids([
                Cell(row=0, col=0, colspan=2),
                Cell(row=0, col=1),
            ]),
        )
        self.assert_invalid_contains(schema, "overlapped cell")


if __name__ == "__main__":
    unittest.main()
