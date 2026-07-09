import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.structure_fidelity.run_structure_fidelity import (
    evaluate_sample,
    parse_html_table,
    summarize,
)


class StructureFidelityExperimentTest(unittest.TestCase):
    def test_parse_html_table_reads_spans(self):
        html = (
            "<table>"
            "<tr><th colspan=\"2\">title</th></tr>"
            "<tr><td>A</td><td>B</td></tr>"
            "</table>"
        )
        cells, matrix, errors = parse_html_table(html)
        self.assertEqual(len(cells), 3)
        self.assertEqual(cells[0].colspan, 2)
        self.assertEqual(len(matrix), 2)
        self.assertEqual(len(matrix[0]), 2)
        self.assertEqual(errors, [])

    def test_agent_tool_matches_simple_structure(self):
        row = evaluate_sample("agent_tool", "simple_with_content", True, True, 0)
        self.assertTrue(row["exact_match"])
        self.assertEqual(row["structure_score"], 1.0)

    def test_direct_baseline_drops_complex_fidelity(self):
        agent = evaluate_sample("agent_tool", "complex_with_content", False, True, 0)
        direct = evaluate_sample("llm_direct", "complex_with_content", False, True, 0)
        self.assertEqual(agent["structure_score"], 1.0)
        self.assertLess(direct["structure_score"], agent["structure_score"])

    def test_summary_groups_rows(self):
        rows = [
            evaluate_sample("agent_tool", "simple_with_content", True, True, 0),
            evaluate_sample("llm_direct", "simple_with_content", True, True, 0),
        ]
        summary = summarize(rows)
        simple_agent = [
            row for row in summary
            if row["method"] == "agent_tool" and row["case"] == "simple_with_content"
        ][0]
        self.assertEqual(simple_agent["samples"], 1)


if __name__ == "__main__":
    unittest.main()
