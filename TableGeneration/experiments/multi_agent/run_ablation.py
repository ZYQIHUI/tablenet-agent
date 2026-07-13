import argparse
import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.agent_types import TableRequest
from agents.core_agent import CoreAgent
from agents.observability import state_to_record
from experiments.multi_agent.summarize_traces import summarize


CONFIGURATIONS = {
    "single": {"candidate_count": 1, "augmentation_count": 0},
    "multi": {"candidate_count": 5, "augmentation_count": 0},
    "paper_5_plus_4": {"candidate_count": 5, "augmentation_count": 4},
}


def run(samples_per_config=10, seed=42):
    results = {}
    traces = {}
    for config_index, (name, settings) in enumerate(CONFIGURATIONS.items()):
        random.seed(seed + config_index)
        core = CoreAgent(**settings)
        records = []
        for sample_index in range(samples_per_config):
            request = TableRequest(
                domain="telecommunications",
                language="zh",
                min_rows=6,
                max_rows=10,
                min_cols=4,
                max_cols=7,
                simple=(sample_index % 2 == 0),
                config_id=f"{name}_{sample_index}",
            )
            try:
                core.generate(request)
                records.append(state_to_record(core.last_state, "success"))
            except Exception as exc:
                records.append(state_to_record(core.last_state, "failed", error=exc))
        traces[name] = records
        results[name] = summarize(records)
    return results, traces


def write_results(results, traces, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with open(output_dir / "summary.csv", "w", encoding="utf-8", newline="") as file_object:
        fieldnames = [
            "configuration", "requests", "success_rate", "average_candidates",
            "average_filling_attempts", "average_schema_attempts", "average_model_calls",
        ]
        writer = csv.DictWriter(file_object, fieldnames=fieldnames)
        writer.writeheader()
        for name, summary in results.items():
            writer.writerow({"configuration": name, **{key: summary[key] for key in fieldnames[1:]}})
    with open(output_dir / "traces.jsonl", "w", encoding="utf-8") as file_object:
        for configuration, records in traces.items():
            for record in records:
                file_object.write(json.dumps({"configuration": configuration, **record}, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples_per_config", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="experiments/multi_agent/results/ablation")
    args = parser.parse_args()
    results, traces = run(args.samples_per_config, args.seed)
    write_results(results, traces, args.output)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
