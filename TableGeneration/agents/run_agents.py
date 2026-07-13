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
from agents.tools.adapters.llm_core_client import LLMCoreClient
from agents.tools.adapters.llm_semantic_client import LLMSemanticClient
from agents.tools.rendering.renderer_tool import RendererTool
from agents.agent_types import TableRequest
from agents.backends.local import LocalQwenClient
from agents.backends import (
    BackendRegistry,
    BackendRoute,
    BackendRouter,
    ClientCapabilityBackend,
    RoutedSemanticClient,
)
from agents.domain import AgentSource
from agents.observability import TraceRecorder


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

COMPLEX_STRUCTURE_TYPES = [
    "grouped_columns",
    "left_headers",
    "body_rowspan",
    "mixed_headers",
    "two_axis_header",
    "summary_row_colspan",
    "multi_level_column_header",
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num", type=int, default=1)
    parser.add_argument("--target_num", type=int, default=None)
    parser.add_argument("--max_attempts", type=int, default=None)
    parser.add_argument("--max_schema_retries", type=int, default=3)
    parser.add_argument("--max_filling_retries", type=int, default=2)
    parser.add_argument("--max_model_calls", type=int, default=100)
    parser.add_argument("--max_elapsed_seconds", type=float, default=300.0)
    parser.add_argument("--max_candidates", type=int, default=100)
    parser.add_argument(
        "--candidate_count",
        type=int,
        default=1,
        help="Ordinary content candidates per schema; use 5 for the paper configuration.",
    )
    parser.add_argument(
        "--augmentation_count",
        type=int,
        default=0,
        help="Validated transformed candidates (0-4); use 4 for the paper configuration.",
    )
    parser.add_argument(
        "--paper_candidate_mode",
        action="store_true",
        help="Shortcut for --candidate_count=5 --augmentation_count=4.",
    )
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
    parser.add_argument("--balanced_structures", action="store_true")
    parser.add_argument("--structure_type", choices=COMPLEX_STRUCTURE_TYPES, default=None)
    parser.add_argument("--brower", type=str, default="chrome")
    parser.add_argument("--brower_width", type=int, default=1920)
    parser.add_argument("--brower_height", type=int, default=2440)
    parser.add_argument("--chrome_driver_path", type=str, default=None)
    parser.add_argument(
        "--semantic_mode",
        choices=("auto", "llm", "rule"),
        default="auto",
        help="auto/llm enables LLM semantic agents with rule fallback; rule disables LLM calls.",
    )
    parser.add_argument(
        "--backend_mode",
        choices=("rule", "api", "local", "hybrid"),
        default=None,
        help="Semantic backend. Overrides legacy --semantic_mode when provided.",
    )
    parser.add_argument("--local_model_path", type=str, default=None)
    parser.add_argument("--local_model_device", type=str, default="auto")
    parser.add_argument("--local_model_max_new_tokens", type=int, default=2048)
    parser.add_argument("--local_model_temperature", type=float, default=0.7)
    parser.add_argument(
        "--memory_path",
        type=str,
        default=None,
        help="Persistent JSON store for Outer/Inner Memory.",
    )
    parser.add_argument("--session_id", type=str, default="default")
    parser.add_argument("--request_text", type=str, default=None)
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


def build_request(args, simple=None, colored=None, lined=None, config_id=None, structure_type=None, template_data=None):
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
        structure_type=structure_type,
        template_data=template_data,
        natural_language_request=getattr(args, "request_text", None),
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


def request_for_index(args, idx, templates=None):
    # Pick a template if templates are loaded
    template = random.choice(templates) if templates else None

    if args.balanced_configs:
        config_id, simple, colored, lined = BALANCED_CONFIGS[idx % len(BALANCED_CONFIGS)]
        structure_type = structure_type_for_index(args, idx, simple)
        return build_request(args, simple, colored, lined, config_id, structure_type, template)
    simple = True if args.simple else False if args.complex else None
    structure_type = structure_type_for_index(args, idx, simple)
    return build_request(
        args,
        simple=simple,
        colored=args.colored,
        lined=args.lined,
        config_id="manual",
        structure_type=structure_type,
        template_data=template,
    )


def requests_for_args(args):
    return [request_for_index(args, idx) for idx in range(target_num(args))]


def structure_type_for_index(args, idx, simple):
    requested = getattr(args, "structure_type", None)
    if requested is not None:
        if simple is True:
            raise ValueError("unsupported request: structure_type cannot be used with --simple")
        return requested
    if not args.balanced_structures or simple is True:
        return None
    if args.balanced_configs:
        complex_position = sum(1 for i in range(idx + 1) if not BALANCED_CONFIGS[i % len(BALANCED_CONFIGS)][1]) - 1
    else:
        complex_position = idx
    return COMPLEX_STRUCTURE_TYPES[complex_position % len(COMPLEX_STRUCTURE_TYPES)]


def classify_error(error):
    message = str(error)
    lowered = message.lower()
    if "invalid table schema" in lowered:
        return "schema_invalid"
    if "invalid table filling" in lowered:
        return "filling_low_score"
    if "render" in lowered or "selenium" in lowered or "webdriver" in lowered:
        return "render_failed"
    if "unsupported request" in lowered:
        return "unsupported_request"
    if "budget exhausted" in lowered:
        return "budget_exhausted"
    return "generation_failed"


def use_llm(args, stage):
    backend_mode = getattr(args, "backend_mode", None)
    if backend_mode == "rule":
        return False
    if backend_mode in ("api", "local", "hybrid"):
        return True
    if args.semantic_mode == "rule":
        return False
    return args.semantic_mode in ("auto", "llm") or getattr(args, f"use_llm_{stage}")


def build_semantic_clients(args, use_topic, use_header, use_body):
    mode = getattr(args, "backend_mode", None)
    if mode == "rule":
        return None, None, None, None, None
    local_model_path = getattr(args, "local_model_path", None)
    registry = BackendRegistry()
    backend_names = []

    if mode in ("local", "hybrid") and local_model_path:
        local_client = LocalQwenClient(
            model_path=local_model_path,
            device=getattr(args, "local_model_device", "auto"),
            max_new_tokens=getattr(args, "local_model_max_new_tokens", 2048),
            temperature=getattr(args, "local_model_temperature", 0.7),
        )
        registry.register(ClientCapabilityBackend(
            "local",
            AgentSource.LOCAL_MODEL,
            {
                "request_planning": (local_client, "plan_request"),
                "topic_generation": (local_client, "generate_topic"),
                "header_generation": (local_client, "generate_headers"),
                "body_generation": (local_client, "generate_body_values"),
                "semantic_judging": (local_client, "evaluate_semantics"),
            },
        ))
        backend_names.append("local")
    if mode == "local" and not local_model_path:
        raise ValueError("--local_model_path is required when --backend_mode=local")

    include_api = mode in (None, "api", "hybrid")
    if include_api:
        core_api = LLMCoreClient(
            api_key=getattr(args, "llm_topic_api_key", None),
            base_url=getattr(args, "llm_topic_base_url", None),
            model=getattr(args, "llm_topic_model", None),
        )
        topic_api = LLMTopicClient(
            api_key=getattr(args, "llm_topic_api_key", None),
            base_url=getattr(args, "llm_topic_base_url", None),
            model=getattr(args, "llm_topic_model", None),
            system_prompt=getattr(args, "llm_topic_system_prompt", None),
        )
        header_api = LLMHeaderClient(
            api_key=getattr(args, "llm_header_api_key", None),
            base_url=getattr(args, "llm_header_base_url", None),
            model=getattr(args, "llm_header_model", None),
            system_prompt=getattr(args, "llm_header_system_prompt", None),
        )
        body_api = LLMBodyClient(
            api_key=getattr(args, "llm_body_api_key", None),
            base_url=getattr(args, "llm_body_base_url", None),
            model=getattr(args, "llm_body_model", None),
            system_prompt=getattr(args, "llm_body_system_prompt", None),
        )
        semantic_api = LLMSemanticClient(
            api_key=getattr(args, "llm_topic_api_key", None),
            base_url=getattr(args, "llm_topic_base_url", None),
            model=getattr(args, "llm_topic_model", None),
        )
        registry.register(ClientCapabilityBackend(
            "api",
            AgentSource.API,
            {
                "request_planning": (core_api, "plan_request"),
                "topic_generation": (topic_api, "generate_topic"),
                "header_generation": (header_api, "generate_headers"),
                "body_generation": (body_api, "generate_body_values"),
                "semantic_judging": (semantic_api, "evaluate_semantics"),
            },
        ))
        backend_names.append("api")

    if not backend_names:
        return None, None, None, None, None
    primary = "local" if mode == "hybrid" and "local" in backend_names else backend_names[0]
    fallbacks = tuple(name for name in backend_names if name != primary)
    routes = {
        capability: BackendRoute(primary, fallbacks)
        for capability in (
            "request_planning", "topic_generation", "header_generation",
            "body_generation", "semantic_judging",
        )
    }
    routed = RoutedSemanticClient(BackendRouter(registry, routes))
    explicit_mode = mode in ("api", "local", "hybrid")
    return (
        routed if explicit_mode else None,
        routed if use_topic else None,
        routed if use_header else None,
        routed if use_body else None,
        routed if explicit_mode else None,
    )


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
    if args.paper_candidate_mode:
        args.candidate_count = 5
        args.augmentation_count = 4
    if args.brower == "chrome" and args.chrome_driver_path is None:
        args.chrome_driver_path = find_default_chromedriver()
    use_llm_topic = use_llm(args, "topic")
    use_llm_header = use_llm(args, "header")
    use_llm_body = use_llm(args, "body")
    core_planner_client, llm_topic_client, llm_header_client, llm_body_client, semantic_evaluator_client = build_semantic_clients(
        args,
        use_llm_topic,
        use_llm_header,
        use_llm_body,
    )
    core = CoreAgent(
        llm_topic_client=llm_topic_client,
        llm_header_client=llm_header_client,
        llm_body_client=llm_body_client,
        core_planner_client=core_planner_client,
        semantic_evaluator_client=semantic_evaluator_client,
        use_llm_topic=use_llm_topic,
        use_llm_header=use_llm_header,
        use_llm_body=use_llm_body,
        candidate_count=args.candidate_count,
        augmentation_count=args.augmentation_count,
        memory_path=args.memory_path,
        session_id=args.session_id,
        max_schema_retries=args.max_schema_retries,
        max_filling_retries=args.max_filling_retries,
        max_model_calls=args.max_model_calls,
        max_elapsed_seconds=args.max_elapsed_seconds,
        max_candidates=args.max_candidates,
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
        trace_path = Path(args.output) / "trace.jsonl"
        with open(gt_path, "w", encoding="utf-8") as f_gt, open(
                meta_path, "w", encoding="utf-8") as f_meta, open(
                cells_path, "w", encoding="utf-8") as f_cells, open(
                trace_path, "w", encoding="utf-8") as f_trace:
            trace_recorder = TraceRecorder(f_trace)
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
                    trace_recorder.write(core.last_state, outcome="success")
                except Exception as error:
                    if core.last_state is not None:
                        trace_recorder.write(core.last_state, outcome="failed", error=error)
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
