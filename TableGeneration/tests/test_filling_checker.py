import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.sub_agents.validators.filling_checker import FillingChecker
from agents.agent_types import Cell, TablePlan, TableSchema


def telecom_plan():
    return TablePlan(
        domain="telecommunications",
        language="zh",
        topic="客户投诉受理与闭环统计",
        rows=4,
        cols=4,
        simple=False,
        colored=False,
        lined=True,
        semantic_scenario="customer_complaints",
    )


def schema_with_content(title, headers, rows):
    cells = [
        Cell(row=0, col=0, tag="th", role="title", text=title, colspan=len(headers), cell_id=0),
    ]
    for col, header in enumerate(headers):
        cells.append(Cell(row=1, col=col, tag="th", role="header", text=header, cell_id=10 + col))
    cell_id = 100
    for row_index, values in enumerate(rows, start=2):
        for col, value in enumerate(values):
            cells.append(Cell(row=row_index, col=col, tag="td", role="body", text=value, cell_id=cell_id))
            cell_id += 1
    return TableSchema(rows=len(rows) + 2, cols=len(headers), cells=cells)


class FillingCheckerTest(unittest.TestCase):
    def test_report_exposes_dimension_scores(self):
        schema = schema_with_content(
            "客户投诉受理与闭环统计",
            ["投诉类型", "受理量", "平均响应时长", "处理状态"],
            [
                ["网络慢", "128", "15", "跟进中"],
                ["频繁掉线", "96", "12", "已完成"],
            ],
        )
        report = FillingChecker().evaluate(schema, telecom_plan())
        self.assertIn("title", report.dimension_scores)
        self.assertIn("header", report.dimension_scores)
        self.assertIn("body", report.dimension_scores)
        self.assertIn("topic_consistency", report.dimension_scores)
        self.assertGreater(report.topic_consistency_score, 0.6)

    def test_unrelated_filling_lowers_topic_consistency(self):
        schema = schema_with_content(
            "水果颜色记录",
            ["水果", "颜色", "天气", "口味"],
            [
                ["苹果", "红色", "晴天", "很甜"],
                ["香蕉", "黄色", "阴天", "软糯"],
            ],
        )
        report = FillingChecker().evaluate(schema, telecom_plan())
        self.assertFalse(report.ok)
        self.assertLess(report.topic_consistency_score, 0.6)
        self.assertLess(report.score, 0.58)
        self.assertTrue(
            any("topic" in issue or "semantic scenario" in issue for issue in report.errors + report.warnings)
        )

    def test_header_body_semantic_mismatch_is_penalized(self):
        schema = schema_with_content(
            "客户投诉受理与闭环统计",
            ["投诉类型", "受理量", "平均响应时长", "处理状态"],
            [
                ["999", "很多", "很快", "苹果"],
                ["无关", "红色", "晴天", "香蕉"],
            ],
        )
        report = FillingChecker().evaluate(schema, telecom_plan())
        self.assertFalse(report.ok)
        self.assertLess(report.body_score, 0.6)
        self.assertTrue(any("non-numeric" in issue for issue in report.errors))


if __name__ == "__main__":
    unittest.main()
