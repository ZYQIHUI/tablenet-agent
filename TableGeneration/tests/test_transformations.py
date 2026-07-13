import sys
import unittest
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.agent_types import Cell, TablePlan, TableSchema
from agents.domain.state import CandidateState
from agents.filling import CandidateSelector
from agents.sub_agents.validators.filling_checker import FillingCheckReport
from agents.sub_agents.validators.validator_agent import ValidatorAgent
from agents.sub_agents.planners.schema_agent import SchemaAgent
from agents.sub_agents.fillers.header_agent import HeaderAgent
from agents.sub_agents.fillers.body_agent import BodyAgent
from agents.tools.rendering.renderer_tool import RendererTool
from agents.transformations import (
    AlterTool,
    AugmentationPipeline,
    CopyTool,
    DeleteTool,
    RegionModel,
    SwapTool,
    UnsafeRegionError,
)


def simple_schema():
    cells = []
    cell_id = 0
    values = [
        ["区域", "用户数"],
        ["东区", "10"],
        ["西区", "20"],
        ["南区", "30"],
    ]
    for row, row_values in enumerate(values):
        for col, value in enumerate(row_values):
            role = "header" if row == 0 else "body"
            cells.append(Cell(row, col, role=role, text=value, cell_id=cell_id))
            cell_id += 1
    return TableSchema(4, 2, cells)


class PassingChecker:
    def evaluate(self, schema, plan):
        return FillingCheckReport(
            ok=True,
            score=0.9,
            title_score=1.0,
            header_score=0.9,
            body_score=0.9,
            topic_consistency_score=0.9,
        )


class TransformationsTest(unittest.TestCase):
    def setUp(self):
        self.validator = ValidatorAgent()

    def assert_valid(self, schema):
        ok, errors = self.validator.validate(schema)
        self.assertTrue(ok, errors)

    def test_copy_delete_and_swap_preserve_coverage(self):
        original = simple_schema()
        copied = CopyTool().apply(original, "row", 1)
        deleted = DeleteTool().apply(copied, "row", 2)
        swapped = SwapTool().apply(original, "row", 1, 3)

        self.assertEqual(copied.rows, 5)
        self.assertEqual(deleted.rows, 4)
        self.assertEqual(original.rows, 4)
        self.assert_valid(copied)
        self.assert_valid(deleted)
        self.assert_valid(swapped)
        swapped_values = {
            (cell.row, cell.col): cell.text for cell in swapped.cells if cell.role == "body"
        }
        self.assertEqual(swapped_values[(1, 0)], "南区")
        self.assertEqual(swapped_values[(3, 0)], "东区")

    def test_region_model_rejects_boundary_inside_rowspan(self):
        schema = TableSchema(
            3,
            2,
            [
                Cell(0, 0, colspan=2, cell_id=0),
                Cell(1, 0, rowspan=2, cell_id=1),
                Cell(1, 1, cell_id=2),
                Cell(2, 1, cell_id=3),
            ],
        )

        self.assertFalse(RegionModel(schema).is_safe_boundary("row", 2))
        with self.assertRaises(UnsafeRegionError):
            CopyTool().apply(schema, "row", 1)

    def test_alter_changes_visual_only(self):
        original = simple_schema()
        altered = AlterTool().apply(original, row=2, background_color="#ffffff")

        self.assertTrue(all(not cell.visual for cell in original.cells))
        changed = [cell for cell in altered.cells if cell.row == 2]
        self.assertTrue(changed)
        self.assertTrue(all(cell.visual["background-color"] == "#ffffff" for cell in changed))
        self.assert_valid(altered)

    def test_augmentation_pipeline_revalidates_all_four_operations(self):
        plan = TablePlan(
            domain="telecommunications",
            language="zh",
            topic="区域用户统计",
            rows=4,
            cols=2,
            simple=True,
            colored=False,
            lined=True,
        )
        parent = CandidateState(schema=simple_schema())
        parent.validation_result = {"ok": True, "errors": []}
        parent.checker_report = PassingChecker().evaluate(parent.schema, plan)
        pipeline = AugmentationPipeline(self.validator, PassingChecker(), CandidateSelector())

        candidates = pipeline.generate(parent, plan, limit=4)

        self.assertEqual({item.transformation for item in candidates}, {"copy", "delete", "swap", "alter"})
        for candidate in candidates:
            self.assertEqual(candidate.parent_candidate_id, parent.candidate_id)
            self.assertTrue(candidate.validation_result["ok"])
            self.assertTrue(candidate.metadata["passed_hard_gate"])

    def test_swap_supports_complete_blocks_with_different_heights(self):
        schema = TableSchema(5, 1, [
            Cell(0, 0, role="header", text="H", cell_id=0),
            Cell(1, 0, role="body", text="A", rowspan=2, cell_id=1),
            Cell(3, 0, role="body", text="B", cell_id=2),
            Cell(4, 0, role="body", text="C", cell_id=3),
        ])

        swapped = SwapTool().apply(schema, "row", 1, 3, count=2, second_count=1)

        self.assert_valid(swapped)
        values = {cell.text: cell.row for cell in swapped.cells}
        self.assertEqual(values["B"], 1)
        self.assertEqual(values["A"], 2)

    def test_all_complex_patterns_support_four_valid_transformations(self):
        for index, structure_type in enumerate(SchemaAgent.COMPLEX_PATTERN_NAMES):
            with self.subTest(structure_type=structure_type):
                random.seed(100 + index)
                plan = TablePlan(
                    domain="telecommunications",
                    language="zh",
                    topic="复杂结构测试",
                    rows=8,
                    cols=6,
                    simple=False,
                    colored=False,
                    lined=True,
                    structure_type=structure_type,
                )
                schema = SchemaAgent().build(plan)
                schema = HeaderAgent().fill(schema, plan)
                schema = BodyAgent().fill(schema, plan)
                parent = CandidateState(schema=schema)
                pipeline = AugmentationPipeline(
                    self.validator,
                    PassingChecker(),
                    CandidateSelector(),
                )

                candidates = pipeline.generate(parent, plan, limit=4)

                self.assertEqual(
                    {item.transformation for item in candidates},
                    {"copy", "delete", "swap", "alter"},
                )
                for candidate in candidates:
                    self.assertTrue(candidate.validation_result["ok"])

    def test_render_annotation_order_follows_transformed_dom_order(self):
        swapped = SwapTool().apply(simple_schema(), "row", 1, 3)
        table = type("Table", (), {
            "schema": swapped,
            "plan": type("Plan", (), {
                "config_id": None,
                "semantic_scenario": "test",
                "structure_type": None,
            })(),
            "style": type("Style", (), {"visual": {}})(),
        })()
        dom_cells = sorted(swapped.cells, key=lambda cell: (cell.row, cell.col))
        contents = [[None, f"dom-{index}", [0, 0, 1, 1]] for index in range(len(dom_cells))]

        annotations = RendererTool._cell_annotations(table, contents, "img.jpg")

        for index, cell in enumerate(dom_cells):
            self.assertEqual(annotations["cells"][index]["row"], cell.row)
            self.assertEqual(annotations["cells"][index]["col"], cell.col)
            self.assertEqual(annotations["cells"][index]["text"], f"dom-{index}")


if __name__ == "__main__":
    unittest.main()
