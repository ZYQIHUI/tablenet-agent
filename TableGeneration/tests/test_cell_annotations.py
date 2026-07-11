import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.tools.rendering.renderer_tool import RendererTool
from agents.agent_types import AgentTable, Cell, TablePlan, TableSchema, TableStyle


class CellAnnotationsTest(unittest.TestCase):
    def table(self):
        plan = TablePlan(
            domain="telecommunications",
            language="zh",
            topic="测试表格",
            rows=3,
            cols=2,
            simple=False,
            colored=True,
            lined=True,
            config_id="complex_colored_lined",
        )
        cells = [
            Cell(row=0, col=0, tag="th", role="title", colspan=2, text="测试表格", cell_id=0),
            Cell(row=1, col=0, tag="th", role="header", text="区域", cell_id=1),
            Cell(row=1, col=1, tag="th", role="header", text="数量", cell_id=2),
            Cell(row=2, col=0, tag="th", role="header", text="东区", cell_id=3),
            Cell(row=2, col=1, tag="td", role="body", text="12", cell_id=4),
        ]
        schema = TableSchema(
            rows=3,
            cols=2,
            cells=cells,
            header_type="mixed_headers",
            has_colspan=True,
            has_rowspan=False,
        )
        style = TableStyle(name="agent_complex_colored_full", table_css="", cell_css="", header_css="")
        return AgentTable(plan, schema, style, "", [], len(cells))

    def test_cell_annotations_include_roles_and_geometry(self):
        table = self.table()
        contens = [
            [4, "测试表格", [[0, 0], [100, 0], [100, 20], [0, 20]]],
            [2, "区域", [[0, 20], [50, 20], [50, 40], [0, 40]]],
            [2, "数量", [[50, 20], [100, 20], [100, 40], [50, 40]]],
            [2, "东区", [[0, 40], [50, 40], [50, 60], [0, 60]]],
            [2, "12", [[50, 40], [100, 40], [100, 60], [50, 60]]],
        ]
        annotations = RendererTool._cell_annotations(table, contens, "img/test.jpg")
        self.assertEqual(annotations["cell_count"], 5)
        self.assertEqual(annotations["cells"][0]["role"], "title")
        self.assertEqual(annotations["cells"][1]["role"], "column_header")
        self.assertEqual(annotations["cells"][3]["role"], "row_header")
        self.assertEqual(annotations["cells"][4]["role"], "body")
        self.assertEqual(annotations["cells"][0]["colspan"], 2)
        self.assertEqual(annotations["cells"][4]["bbox"], contens[4][2])


if __name__ == "__main__":
    unittest.main()
