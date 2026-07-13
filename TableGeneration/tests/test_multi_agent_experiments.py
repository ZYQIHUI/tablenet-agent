import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.multi_agent.checker_human_correlation import calculate, kendall_tau_b, pearson, rank
from experiments.multi_agent.run_ablation import CONFIGURATIONS, run
from experiments.multi_agent.summarize_traces import summarize


class MultiAgentExperimentsTest(unittest.TestCase):
    def test_perfect_human_checker_agreement_scores_one(self):
        rows = []
        for value in (0.1, 0.4, 0.8, 1.0):
            row = {}
            for dimension in ("structure", "topic", "semantic"):
                row[f"human_{dimension}"] = value
                row[f"checker_{dimension}"] = value
            rows.append(row)

        result = calculate(rows)

        for scores in result["dimensions"].values():
            self.assertEqual(scores["pearson"], 1.0)
            self.assertEqual(scores["spearman"], 1.0)
            self.assertEqual(scores["kendall"], 1.0)

    def test_trace_summary_counts_transformations_and_fallbacks(self):
        records = [{
            "outcome": "success",
            "candidates": [
                {"generation_source": "ordinary", "metadata": {}},
                {"generation_source": "transformation", "transformation": "copy", "metadata": {}},
            ],
            "events": [{"action": "fallback", "metadata": {"source": "rule"}}],
            "budget": {"model_calls": 1, "elapsed_seconds": 0.5},
            "retry_counters": {"filling_attempts": 2, "schema_attempts": 1},
        }]

        result = summarize(records)

        self.assertEqual(result["success_rate"], 1.0)
        self.assertEqual(result["transformations"], {"copy": 1})
        self.assertEqual(result["actions"], {"fallback": 1})

    def test_small_ablation_runs_all_fixed_configurations(self):
        results, traces = run(samples_per_config=1, seed=7)

        self.assertEqual(set(results), set(CONFIGURATIONS))
        self.assertTrue(all(len(records) == 1 for records in traces.values()))
        self.assertTrue(all(summary["requests"] == 1 for summary in results.values()))


if __name__ == "__main__":
    unittest.main()
