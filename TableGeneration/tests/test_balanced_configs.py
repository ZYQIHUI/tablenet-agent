import argparse
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.run_agents import BALANCED_CONFIGS, COMPLEX_STRUCTURE_TYPES, build_report, max_attempts, requests_for_args, target_num, use_llm


class BalancedConfigsTest(unittest.TestCase):
    def args(self, num):
        return argparse.Namespace(
            num=num,
            target_num=None,
            max_attempts=None,
            retry_failed=False,
            output="output/test",
            semantic_mode="auto",
            domain="telecommunications",
            language="zh",
            min_row=4,
            max_row=8,
            min_col=3,
            max_col=6,
            simple=False,
            complex=False,
            colored=None,
            lined=None,
            balanced_configs=True,
            balanced_structures=False,
        )

    def test_balanced_configs_repeat_evenly(self):
        requests = requests_for_args(self.args(num=16))
        counts = Counter(request.config_id for request in requests)
        self.assertEqual(len(requests), 16)
        self.assertEqual(set(counts), {item[0] for item in BALANCED_CONFIGS})
        self.assertTrue(all(count == 2 for count in counts.values()))

    def test_balanced_config_attributes_match_id(self):
        requests = requests_for_args(self.args(num=len(BALANCED_CONFIGS)))
        for request, (config_id, simple, colored, lined) in zip(requests, BALANCED_CONFIGS):
            self.assertEqual(request.config_id, config_id)
            self.assertEqual(request.simple, simple)
            self.assertEqual(request.colored, colored)
            self.assertEqual(request.lined, lined)

    def test_target_num_overrides_num(self):
        args = self.args(num=8)
        args.target_num = 12
        args.retry_failed = True
        self.assertEqual(target_num(args), 12)
        self.assertEqual(max_attempts(args), 36)
        self.assertEqual(len(requests_for_args(args)), 12)

    def test_report_counts_success_metadata(self):
        args = self.args(num=2)
        records = [
            {
                "config_id": "simple_colored_lined",
                "header_type": "simple_single_header",
                "simple": True,
                "has_rowspan": False,
                "has_colspan": False,
            },
            {
                "config_id": "complex_plain_lined",
                "header_type": "mixed_headers",
                "simple": False,
                "has_rowspan": True,
                "has_colspan": True,
            },
        ]
        report = build_report(args, records, [{"reason": "schema_invalid"}], attempts=3)
        self.assertEqual(report["success"], 2)
        self.assertEqual(report["failure_counts"]["schema_invalid"], 1)
        self.assertEqual(report["config_counts"]["complex_plain_lined"], 1)
        self.assertEqual(report["span_counts"]["complex_total"], 1)
        self.assertEqual(report["span_counts"]["complex_has_rowspan"], 1)

    def test_semantic_mode_defaults_to_llm_with_fallback(self):
        args = self.args(num=1)
        self.assertTrue(use_llm(args, "topic"))
        self.assertTrue(use_llm(args, "header"))
        self.assertTrue(use_llm(args, "body"))

    def test_semantic_mode_rule_disables_llm(self):
        args = self.args(num=1)
        args.semantic_mode = "rule"
        args.use_llm_topic = True
        args.use_llm_header = True
        args.use_llm_body = True
        self.assertFalse(use_llm(args, "topic"))
        self.assertFalse(use_llm(args, "header"))
        self.assertFalse(use_llm(args, "body"))

    def test_balanced_structures_assigns_only_complex_requests(self):
        args = self.args(num=16)
        args.balanced_structures = True
        requests = requests_for_args(args)
        complex_requests = [request for request in requests if request.simple is False]
        simple_requests = [request for request in requests if request.simple is True]
        self.assertTrue(all(request.structure_type is None for request in simple_requests))
        self.assertEqual(
            [request.structure_type for request in complex_requests],
            [COMPLEX_STRUCTURE_TYPES[idx % len(COMPLEX_STRUCTURE_TYPES)] for idx in range(8)],
        )


if __name__ == "__main__":
    unittest.main()
