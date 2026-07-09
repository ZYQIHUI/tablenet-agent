import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.core_agent import CoreAgent
from agents.tools.adapters.llm_body_client import LLMBodyClient
from agents.tools.adapters.llm_header_client import LLMHeaderClient
from agents.tools.adapters.llm_topic_client import LLMTopicClient
from agents.tools.rendering.renderer_tool import RendererTool
from agents.types import TableRequest


BALANCED_CONFIGS = [
    ("simple_colored_lined", True, True, True),
    ("simple_colored_unlined", True, True, False),
    ("simple_plain_lined", True, False, True),
    ("simple_plain_unlined", True, False, False),
    ("complex_colored_lined", False, True, True),
    ("complex_colored_unlined", False, True, False),
    ("complex_plain_lined", False, False, True),
    ("complex_plain_unlined", False, False, False),
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num", type=int, default=1)
    parser.add_argument("--target_num", type=int, default=None)
    parser.add_argument("--max_attempts", type=int, default=None)
    parser.add_argument("--retry_failed", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--output", type=str, default="output/agent_table")
    parser.add_argument("--domain", type=str, default="telecommunications")
    parser.add_argument("--language", type=str, default="zh")
    parser.add_argument("--min_row", type=int, default=4)
    parser.add_argument("--max_row", type=int, default=12)
    parser.add_argument("--min_col", type=int, default=3)
    parser.add_argument("--max_col", type=int, default=8)
    shape_group = parser.add_mutually_exclusive_group()
    shape_group.add_argument("--simple", action="store_true", default=None)
    shape_group.add_argument("--complex", action="store_true", default=None)
    parser.add_argument("--colored", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--lined", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--balanced_configs", action="store_true")
    parser.add_argument("--brower", type=str, default="chrome")
    parser.add_argument("--brower_width", type=int, default=1920)
    parser.add_argument("--brower_height", type=int, default=2440)
    parser.add_argument("--chrome_driver_path", type=str, default=None)
    parser.add_argument("--use_llm_topic", action="store_true")
    parser.add_argument("--llm_topic_api_key", type=str, default=None)
    parser.add_argument("--llm_topic_base_url", type=str, default=None)
    parser.add_argument("--llm_topic_model", type=str, default=None)
    parser.add_argument("--llm_topic_system_prompt", type=str, default=None)
    parser.add_argument("--use_llm_header", action="store_true")
    parser.add_argument("--llm_header_api_key", type=str, default=None)
    parser.add_argument("--llm_header_base_url", type=str, default=None)
    parser.add_argument("--llm_header_model", type=str, default=None)
    parser.add_argument("--llm_header_system_prompt", type=str, default=None)
    parser.add_argument("--use_llm_body", action="store_true")
    parser.add_argument("--llm_body_api_key", type=str, default=None)
    parser.add_argument("--llm_body_base_url", type=str, default=None)
    parser.add_argument("--llm_body_model", type=str, default=None)
    parser.add_argument("--llm_body_system_prompt", type=str, default=None)
    return parser.parse_args()


def find_default_chromedriver():
    for candidate in [
            Path("chromedriver-win64/chromedriver.exe"),
            Path("../chromedriver-win64/chromedriver.exe")]:
        if candidate.exists():
            return str(candidate)
    return None


def build_request(args, simple=None, colored=None, lined=None, config_id=None):
    return TableRequest(
        domain=args.domain,
        language=args.language,
        min_rows=args.min_row,
        max_rows=args.max_row,
        min_cols=args.min_col,
        max_cols=args.max_col,
        simple=simple,
        colored=colored,
        lined=lined,
        config_id=config_id,
    )


def target_num(args):
    return args.target_num if args.target_num is not None else args.num


def max_attempts(args):
    target = target_num(args)
    if args.max_attempts is not None:
        return args.max_attempts
    if args.retry_failed:
        return max(target * 3, target)
    return target


def request_for_index(args, idx):
    if args.balanced_configs:
        config_id, simple, colored, lined = BALANCED_CONFIGS[idx % len(BALANCED_CONFIGS)]
        return build_request(args, simple, colored, lined, config_id)
    simple = True if args.simple else False if args.complex else None
    return build_request(
        args,
        simple=simple,
        colored=args.colored,
        lined=args.lined,
        config_id="manual",
    )


def requests_for_args(args):
    return [request_for_index(args, idx) for idx in range(target_num(args))]


def classify_error(error):
    message = str(error)
    lowered = message.lower()
    if "invalid table schema" in lowered:
        return "schema_invalid"
    if "invalid table filling" in lowered:
        return "filling_low_score"
    if "render" in lowered or "selenium" in lowered or "webdriver" in lowered:
        return "render_failed"
    return "generation_failed"


def build_report(args, success_records, failures, attempts):
    config_counts = Counter(record.get("config_id") for record in success_records)
    header_type_counts = Counter(record.get("header_type") for record in success_records)
    complex_records = [record for record in success_records if not record.get("simple")]
    failure_counts = Counter(failure["reason"] for failure in failures)
    target = target_num(args)
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "output": args.output,
        "target_num": target,
        "max_attempts": max_attempts(args),
        "retry_failed": args.retry_failed,
        "attempts": attempts,
        "success": len(success_records),
        "failed": len(failures),
        "success_rate": round(len(success_records) / attempts, 4) if attempts else 0.0,
        "complete": len(success_records) >= target,
        "failure_counts": dict(sorted(failure_counts.items())),
        "config_counts": dict(sorted(config_counts.items())),
        "header_type_counts": dict(sorted(header_type_counts.items())),
        "span_counts": {
            "complex_total": len(complex_records),
            "complex_has_rowspan": sum(1 for record in complex_records if record.get("has_rowspan")),
            "complex_has_colspan": sum(1 for record in complex_records if record.get("has_colspan")),
        },
        "failures": failures,
    }


def write_report(output, report):
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "report.json"
    md_path = output_path / "report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(report_markdown(report), encoding="utf-8")


def report_markdown(report):
    lines = [
        "# Batch Generation Report",
        "",
        f"- Output: `{report['output']}`",
        f"- Target: {report['target_num']}",
        f"- Success: {report['success']}",
        f"- Attempts: {report['attempts']}",
        f"- Success rate: {report['success_rate']}",
        f"- Complete: {report['complete']}",
        "",
        "## Failure Counts",
        "",
    ]
    if report["failure_counts"]:
        for key, value in report["failure_counts"].items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none: 0")
    lines.extend(["", "## Config Counts", ""])
    for key, value in report["config_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Header Types", ""])
    for key, value in report["header_type_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Span Counts", ""])
    for key, value in report["span_counts"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def main():
    args = parse_args()
    if args.brower == "chrome" and args.chrome_driver_path is None:
        args.chrome_driver_path = find_default_chromedriver()
    llm_topic_client = None
    if args.use_llm_topic:
        llm_topic_client = LLMTopicClient(
            api_key=args.llm_topic_api_key,
            base_url=args.llm_topic_base_url,
            model=args.llm_topic_model,
            system_prompt=args.llm_topic_system_prompt,
        )
    llm_header_client = None
    if args.use_llm_header:
        llm_header_client = LLMHeaderClient(
            api_key=args.llm_header_api_key,
            base_url=args.llm_header_base_url,
            model=args.llm_header_model,
            system_prompt=args.llm_header_system_prompt,
        )
    llm_body_client = None
    if args.use_llm_body:
        llm_body_client = LLMBodyClient(
            api_key=args.llm_body_api_key,
            base_url=args.llm_body_base_url,
            model=args.llm_body_model,
            system_prompt=args.llm_body_system_prompt,
        )
    core = CoreAgent(
        llm_topic_client=llm_topic_client,
        llm_header_client=llm_header_client,
        llm_body_client=llm_body_client,
        use_llm_topic=args.use_llm_topic,
        use_llm_header=args.use_llm_header,
        use_llm_body=args.use_llm_body,
    )
    renderer = RendererTool(
        output=args.output,
        brower=args.brower,
        brower_width=args.brower_width,
        brower_height=args.brower_height,
        chrome_driver_path=args.chrome_driver_path,
    )
    target = target_num(args)
    limit = max_attempts(args)
    successes = []
    failures = []
    attempts = 0
    try:
        renderer.prepare_output()
        gt_path = Path(args.output) / "gt.txt"
        meta_path = Path(args.output) / "meta.jsonl"
        cells_path = Path(args.output) / "cells.jsonl"
        with open(gt_path, "w", encoding="utf-8") as f_gt, open(
                meta_path, "w", encoding="utf-8") as f_meta, open(
                cells_path, "w", encoding="utf-8") as f_cells:
            while len(successes) < target and attempts < limit:
                attempts += 1
                request = request_for_index(args, len(successes))
                try:
                    table = core.generate(request)
                    meta = renderer.render_one(
                        table,
                        len(successes),
                        f_gt,
                        f_meta,
                        f_cells,
                    )
                    successes.append(meta)
                except Exception as error:
                    reason = classify_error(error)
                    failures.append({
                        "attempt": attempts,
                        "target_index": len(successes),
                        "config_id": request.config_id,
                        "reason": reason,
                        "message": str(error),
                    })
                    if not args.retry_failed:
                        raise
    finally:
        renderer.close()
    report = build_report(args, successes, failures, attempts)
    if args.report:
        write_report(args.output, report)
    if len(successes) < target:
        raise RuntimeError(
            f"generated {len(successes)} valid tables out of target {target} "
            f"after {attempts} attempts"
        )
    print(f"generated {len(successes)} valid agent tables into {args.output}")
    if args.report:
        print(f"wrote report.json and report.md into {args.output}")


if __name__ == "__main__":
    main()
