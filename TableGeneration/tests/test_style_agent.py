import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.sub_agents.planners.style_agent import StyleAgent
from agents.agent_types import TablePlan


class StyleAgentTest(unittest.TestCase):
    def plan(self, colored=True, lined=True):
        return TablePlan(
            domain="telecommunications",
            language="zh",
            topic="视觉样式测试",
            rows=6,
            cols=4,
            simple=False,
            colored=colored,
            lined=lined,
            config_id="complex_colored_lined",
            semantic_scenario="network_coverage",
        )

    def test_style_contains_structured_visual_attributes(self):
        style = StyleAgent().build(self.plan())
        for key in (
                "font_family",
                "font_size",
                "padding_mode",
                "align",
                "background_mode",
                "border_weight"):
            self.assertIn(key, style.visual)
        self.assertIn("font-family", style.table_css)
        self.assertIn("font-size", style.table_css)
        self.assertIn("padding:", style.cell_css)
        self.assertIn("padding:", style.header_css)

    def test_plain_style_records_plain_background(self):
        style = StyleAgent().build(self.plan(colored=False, lined=False))
        self.assertEqual(style.visual["background_mode"], "plain")


if __name__ == "__main__":
    unittest.main()
