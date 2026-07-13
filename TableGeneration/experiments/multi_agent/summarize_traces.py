import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def summarize(records):
    outcomes = Counter(record.get("outcome", "unknown") for record in records)
    candidates = [candidate for record in records for candidate in record.get("candidates", [])]
    events = [event for record in records for event in record.get("events", [])]
    transformations = Counter(
        candidate.get("transformation") for candidate in candidates if candidate.get("transformation")
    )
    sources = Counter(
        event.get("metadata", {}).get("source")
        for event in events
        if event.get("metadata", {}).get("source")
    )
    actions = Counter(event.get("action") for event in events if event.get("action"))
    rejection_reasons = Counter(
        candidate.get("metadata", {}).get("rejection_reason")
        for candidate in candidates
        if candidate.get("metadata", {}).get("rejection_reason")
    )
    budgets = [record.get("budget") or {} for record in records]
    return {
        "requests": len(records),
        "outcomes": dict(outcomes),
        "success_rate": round(outcomes.get("success", 0) / len(records), 4) if records else 0.0,
        "candidates": len(candidates),
        "average_candidates": round(len(candidates) / len(records), 4) if records else 0.0,
        "ordinary_candidates": sum(item.get("generation_source") == "ordinary" for item in candidates),
        "transformed_candidates": sum(item.get("generation_source") == "transformation" for item in candidates),
        "transformations": dict(transformations),
        "sources": dict(sources),
        "actions": dict(actions),
        "rejection_reasons": dict(rejection_reasons),
        "average_model_calls": _average(budget.get("model_calls", 0) for budget in budgets),
        "average_elapsed_seconds": _average(budget.get("elapsed_seconds", 0) for budget in budgets),
        "average_filling_attempts": _average(
            record.get("retry_counters", {}).get("filling_attempts", 0) for record in records
        ),
        "average_schema_attempts": _average(
            record.get("retry_counters", {}).get("schema_attempts", 0) for record in records
        ),
    }


def read_jsonl(path):
    records = []
    with open(path, "r", encoding="utf-8") as file_object:
        for line_number, line in enumerate(file_object, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"trace line {line_number} is not an object")
            records.append(value)
    return records


def write_summary(summary, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "summary.json", "w", encoding="utf-8") as file_object:
        json.dump(summary, file_object, ensure_ascii=False, indent=2)
    with open(output_dir / "summary.csv", "w", encoding="utf-8", newline="") as file_object:
        writer = csv.writer(file_object)
        writer.writerow(["metric", "value"])
        for key, value in summary.items():
            writer.writerow([key, json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value])
    lines = ["# Multi-Agent Trace Summary", ""]
    for key, value in summary.items():
        lines.append(f"- `{key}`: {json.dumps(value, ensure_ascii=False)}")
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _average(values):
    values = list(values)
    return round(sum(values) / len(values), 4) if values else 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    summary = summarize(read_jsonl(args.trace))
    write_summary(summary, args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
