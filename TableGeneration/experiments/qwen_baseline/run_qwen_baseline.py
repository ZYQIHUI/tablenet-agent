"""
Batch inference & evaluation for Qwen2-VL on TableNet SFT data.

Usage:
  # Single-sample (backward compatible)
  python run_qwen_baseline.py \\
    --model /path/to/Qwen2-VL-2B-Instruct \\
    --data_json /path/to/test.json \\
    --sample_index 0 \\
    --output results/sample_000.json

  # Batch evaluation on all samples
  python run_qwen_baseline.py \\
    --model /path/to/Qwen2-VL-2B-Instruct \\
    --data_json /path/to/test.json \\
    --meta_jsonl /path/to/meta.jsonl \\
    --output results/batch_eval

  # With adapter
  python run_qwen_baseline.py \\
    --model /path/to/Qwen2-VL-2B-Instruct \\
    --data_json /path/to/test.json \\
    --adapter /path/to/adapter \\
    --output results/adapter_eval

  # Limit to first N samples
  python run_qwen_baseline.py \\
    --model /path/to/Qwen2-VL-2B-Instruct \\
    --data_json /path/to/test.json \\
    --max_samples 10 \\
    --output results/smoke_eval
"""

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
import transformers
from peft import PeftModel
from qwen_vl_utils import process_vision_info
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PROMPT = (
    "请识别图片中的表格结构和文本，并输出完整 HTML table。"
    "只输出 HTML，不要解释，不要 Markdown 代码块。"
)

GROUP_CONFIGS = {
    "simple_colored_lined": (True, True, True),
    "simple_colored_unlined": (True, True, False),
    "simple_plain_lined": (True, False, True),
    "simple_plain_unlined": (True, False, False),
    "complex_colored_lined": (False, True, True),
    "complex_colored_unlined": (False, True, False),
    "complex_plain_lined": (False, False, True),
    "complex_plain_unlined": (False, False, False),
}


# ---------------------------------------------------------------------------
# HTML parser (reused from structure_fidelity experiment)
# ---------------------------------------------------------------------------

@dataclass
class ParsedCell:
    row: int
    col: int
    rowspan: int
    colspan: int
    tag: str
    text: str


class TableHTMLParser(HTMLParser):
    """Parse HTML table into structured cell data."""

    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.current_tag = None
        self.current_attrs = {}
        self.current_text = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
        elif tag == "tr" and self.in_table:
            self.in_row = True
        elif tag in ("td", "th") and self.in_row:
            self.current_tag = tag
            self.current_attrs = dict(attrs)
            self.current_text = []

    def handle_data(self, data):
        if self.current_tag:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.current_tag == tag:
            row_cells = self.rows[-1] if self.rows else []
            row_cells.append({
                "tag": self.current_tag,
                "rowspan": _int_attr(self.current_attrs.get("rowspan"), 1),
                "colspan": _int_attr(self.current_attrs.get("colspan"), 1),
                "text": "".join(self.current_text).strip(),
            })
            self.current_tag = None
            self.current_attrs = {}
            self.current_text = []
        elif tag == "tr" and self.in_row:
            self.rows.append([])
            self.in_row = False
        elif tag == "table":
            self.in_table = False


def _int_attr(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def parse_html_table(html: str) -> Tuple[List[ParsedCell], List[List[Optional[int]]], List[str]]:
    """Parse HTML table string into cells, occupancy matrix, and errors."""
    parser = TableHTMLParser()
    parser.feed(html)

    # Flatten rows into placed cells with resolved coordinates
    occupied = {}
    cells = []
    errors = []
    max_col = 0

    for row_index, row_cells in enumerate(parser.rows):
        col = 0
        while (row_index, col) in occupied:
            col += 1
        for raw_cell in row_cells:
            while (row_index, col) in occupied:
                col += 1
            rowspan = raw_cell["rowspan"]
            colspan = raw_cell["colspan"]
            cell = ParsedCell(
                row=row_index,
                col=col,
                rowspan=rowspan,
                colspan=colspan,
                tag=raw_cell["tag"],
                text=raw_cell["text"],
            )
            cells.append(cell)
            for r in range(row_index, row_index + rowspan):
                for c in range(col, col + colspan):
                    key = (r, c)
                    if key in occupied:
                        errors.append(f"overlap at ({r}, {c})")
                    occupied[key] = len(cells) - 1
            col += colspan
            max_col = max(max_col, col)

    max_row = max((r for r, _ in occupied), default=-1) + 1
    matrix = []
    for r in range(max_row):
        matrix_row = []
        for c in range(max_col):
            matrix_row.append(occupied.get((r, c)))
        matrix.append(matrix_row)
        if any(item is None for item in matrix_row):
            errors.append(f"row {r} has uncovered slots")

    return cells, matrix, errors


def html_structure_signature(cells: List[ParsedCell]) -> str:
    """Compact structure signature for exact-match comparison."""
    sig_parts = []
    for cell in sorted(cells, key=lambda x: (x.row, x.col)):
        sig_parts.append(
            f"{cell.tag}[{cell.row},{cell.col}]({cell.rowspan},{cell.colspan})"
        )
    return "|".join(sig_parts)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class SampleMetrics:
    html_valid: bool = False
    parsed_rows: int = 0
    parsed_cols: int = 0
    structure_signature_match: bool = False
    ref_cell_count: int = 0
    pred_cell_count: int = 0
    correct_cell_text: int = 0
    cell_text_accuracy: float = 0.0
    structure_score: float = 0.0
    errors: List[str] = field(default_factory=list)


def compute_metrics(pred_html: str, ref_html: str) -> SampleMetrics:
    """Compute all metrics between predicted and reference HTML."""
    metrics = SampleMetrics()

    # Parse both HTML strings
    pred_cells, pred_matrix, pred_errors = parse_html_table(pred_html)
    ref_cells, ref_matrix, ref_errors = parse_html_table(ref_html)

    metrics.html_valid = len(pred_errors) == 0
    metrics.parsed_rows = len(pred_matrix)
    metrics.parsed_cols = len(pred_matrix[0]) if pred_matrix else 0
    metrics.errors = pred_errors

    if not ref_cells:
        return metrics

    # Structure signature exact match
    pred_sig = html_structure_signature(pred_cells)
    ref_sig = html_structure_signature(ref_cells)
    metrics.structure_signature_match = pred_sig == ref_sig

    # Structure score (span-level overlap, from structure_fidelity)
    pred_spans = {(c.row, c.col, c.rowspan, c.colspan) for c in pred_cells}
    ref_spans = {(c.row, c.col, c.rowspan, c.colspan) for c in ref_cells}
    overlap = len(pred_spans & ref_spans)
    metrics.structure_score = round(
        (2 * overlap) / (len(pred_spans) + len(ref_spans)), 4
    ) if pred_spans or ref_spans else 1.0

    # Cell text accuracy (cell-by-cell, matched by (row, col))
    metrics.ref_cell_count = len(ref_cells)
    metrics.pred_cell_count = len(pred_cells)

    ref_by_pos = {(c.row, c.col): c for c in ref_cells}
    pred_by_pos = {(c.row, c.col): c for c in pred_cells}

    correct = 0
    total = max(len(ref_cells), len(pred_cells))
    for pos, ref_cell in ref_by_pos.items():
        pred_cell = pred_by_pos.get(pos)
        if pred_cell and ref_cell.text == pred_cell.text:
            correct += 1

    metrics.correct_cell_text = correct
    metrics.cell_text_accuracy = round(correct / total, 4) if total > 0 else 0.0

    return metrics


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_metadata_index(meta_jsonl: Path) -> Dict[str, dict]:
    """Build filename -> metadata dict from meta.jsonl."""
    index = {}
    if not meta_jsonl or not meta_jsonl.exists():
        return index
    for line in meta_jsonl.read_text(encoding="utf-8").strip().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        fname = entry.get("filename", "")
        # Normalize: handle both Windows and Linux path separators
        fname = Path(fname).name  # extract just the basename
        index[fname] = entry
    return index


def lookup_metadata(meta_index: Dict[str, dict], image_path: str) -> Optional[dict]:
    """Look up metadata for an image path."""
    fname = Path(image_path).name
    return meta_index.get(fname)


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def run_inference(
    model,
    processor,
    image_path: Path,
    prompt: str,
    max_new_tokens: int,
) -> str:
    """Run single-image inference and return predicted text."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": str(image_path)},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    chat_text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[chat_text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(model.device)

    with torch.inference_mode():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
        )
    generated_ids = [
        output[len(input_ids):]
        for input_ids, output in zip(inputs.input_ids, generated_ids)
    ]
    prediction = processor.batch_decode(
        generated_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0].strip()
    return prediction


# ---------------------------------------------------------------------------
# Summary / report
# ---------------------------------------------------------------------------

@dataclass
class SummaryStats:
    total: int = 0
    html_valid: int = 0
    structure_exact_match: int = 0
    avg_cell_accuracy: float = 0.0
    avg_structure_score: float = 0.0
    avg_ref_cells: float = 0.0
    avg_pred_cells: float = 0.0
    avg_prediction_chars: float = 0.0
    avg_inference_seconds: float = 0.0


def compute_summary(results: List[dict]) -> SummaryStats:
    s = SummaryStats(total=len(results))
    for r in results:
        s.html_valid += 1 if r.get("html_valid") else 0
        s.structure_exact_match += 1 if r.get("structure_signature_match") else 0
        s.avg_cell_accuracy += r.get("cell_text_accuracy", 0.0)
        s.avg_structure_score += r.get("structure_score", 0.0)
        s.avg_ref_cells += r.get("ref_cell_count", 0)
        s.avg_pred_cells += r.get("pred_cell_count", 0)
        s.avg_prediction_chars += len(r.get("prediction", ""))
        s.avg_inference_seconds += r.get("inference_seconds", 0.0)
    n = s.total
    if n:
        s.avg_cell_accuracy = round(s.avg_cell_accuracy / n, 4)
        s.avg_structure_score = round(s.avg_structure_score / n, 4)
        s.avg_ref_cells = round(s.avg_ref_cells / n, 2)
        s.avg_pred_cells = round(s.avg_pred_cells / n, 2)
        s.avg_prediction_chars = round(s.avg_prediction_chars / n, 1)
        s.avg_inference_seconds = round(s.avg_inference_seconds / n, 2)
    return s


def group_summaries(results: List[dict]) -> List[dict]:
    """Group results by config_id and header_type."""
    groups = {}

    for r in results:
        config_id = r.get("config_id", "unknown")
        header_type = r.get("header_type", "unknown")
        group_key = f"{config_id}__{header_type}"

        if group_key not in groups:
            groups[group_key] = {
                "config_id": config_id,
                "simple": r.get("simple", None),
                "colored": r.get("colored", None),
                "lined": r.get("lined", None),
                "header_type": header_type,
                "has_rowspan": r.get("has_rowspan", None),
                "has_colspan": r.get("has_colspan", None),
                "results": [],
            }
        groups[group_key]["results"].append(r)

    summaries = []
    for g in groups.values():
        grp = g["results"]
        n = len(grp)
        summaries.append({
            "config_id": g["config_id"],
            "simple": g["simple"],
            "colored": g["colored"],
            "lined": g["lined"],
            "header_type": g["header_type"],
            "has_rowspan": g["has_rowspan"],
            "has_colspan": g["has_colspan"],
            "samples": n,
            "html_valid": sum(1 for r in grp if r.get("html_valid")),
            "structure_exact_match": sum(1 for r in grp if r.get("structure_signature_match")),
            "avg_cell_accuracy": round(sum(r.get("cell_text_accuracy", 0.0) for r in grp) / n, 4),
            "avg_structure_score": round(sum(r.get("structure_score", 0.0) for r in grp) / n, 4),
            "avg_ref_cells": round(sum(r.get("ref_cell_count", 0) for r in grp) / n, 2),
            "avg_pred_cells": round(sum(r.get("pred_cell_count", 0) for r in grp) / n, 2),
        })
    summaries.sort(key=lambda x: (x["config_id"], x["header_type"]))
    return summaries


def write_summary(output_dir: Path, stats: SummaryStats, group_sums: List[dict], args: dict):
    """Write summary.json, summary.csv, and summary.md."""
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_data = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "args": args,
        "overall": {
            "total": stats.total,
            "html_valid": stats.html_valid,
            "structure_exact_match": stats.structure_exact_match,
            "avg_cell_accuracy": stats.avg_cell_accuracy,
            "avg_structure_score": stats.avg_structure_score,
            "avg_ref_cells": stats.avg_ref_cells,
            "avg_pred_cells": stats.avg_pred_cells,
            "avg_prediction_chars": stats.avg_prediction_chars,
            "avg_inference_seconds": stats.avg_inference_seconds,
        },
        "groups": group_sums,
    }

    # summary.json
    (output_dir / "summary.json").write_text(
        json.dumps(summary_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # summary.csv
    if group_sums:
        fieldnames = [
            "config_id", "simple", "colored", "lined", "header_type",
            "has_rowspan", "has_colspan", "samples",
            "html_valid", "structure_exact_match",
            "avg_cell_accuracy", "avg_structure_score",
            "avg_ref_cells", "avg_pred_cells",
        ]
        with open(output_dir / "summary.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(group_sums)

    # summary.md
    lines = [
        "# Batch Evaluation Summary",
        "",
        f"- Created at: {summary_data['created_at']}",
        f"- Total samples: {stats.total}",
        f"- HTML valid: {stats.html_valid}/{stats.total} ({_pct(stats.html_valid, stats.total)})",
        f"- Structure exact match: {stats.structure_exact_match}/{stats.total} ({_pct(stats.structure_exact_match, stats.total)})",
        f"- Avg cell text accuracy: {stats.avg_cell_accuracy}",
        f"- Avg structure score: {stats.avg_structure_score}",
        f"- Avg inference time: {stats.avg_inference_seconds}s",
        "",
        "## Grouped Results",
        "",
        "| Config | Header Type | Samples | HTML Valid | Struct Exact | Cell Acc | Struct Score |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for g in group_sums:
        lines.append(
            f"| {g['config_id']} | {g['header_type']} | {g['samples']} | "
            f"{g['html_valid']} | {g['structure_exact_match']} | "
            f"{g['avg_cell_accuracy']} | {g['avg_structure_score']} |"
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Summary written to {output_dir / 'summary.md'}")


def _pct(n, total):
    return f"{100.0 * n / total:.1f}%" if total else "0.0%"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Batch inference & evaluation for Qwen2-VL on TableNet SFT data."
    )
    # Model / data
    parser.add_argument("--model", type=Path, required=True, help="Path to Qwen2-VL model")
    parser.add_argument("--data_json", type=Path, required=True, help="Path to SFT JSON (train/val/test)")
    parser.add_argument("--meta_jsonl", type=Path, default=None, help="Path to meta.jsonl for grouping metadata")
    parser.add_argument("--adapter", type=Path, default=None, help="Optional PEFT adapter path")

    # Sample selection
    parser.add_argument("--sample_index", type=int, default=None, help="Single sample mode: index to process")
    parser.add_argument("--max_samples", type=int, default=None, help="Max samples to process in batch mode")

    # Inference
    parser.add_argument("--max_new_tokens", type=int, default=2048)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)

    # Output
    parser.add_argument("--output", type=Path, required=True, help="Output path (file for single, dir for batch)")

    return parser.parse_args()


def main():
    args = parse_args()

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    rows = json.loads(args.data_json.read_text(encoding="utf-8"))
    if not rows:
        raise ValueError(f"Dataset is empty: {args.data_json}")

    # Load metadata index if provided
    meta_index = load_metadata_index(args.meta_jsonl) if args.meta_jsonl else {}

    # ------------------------------------------------------------------
    # Load model
    # ------------------------------------------------------------------
    print(f"Loading model from {args.model} ...")
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        local_files_only=True,
    )
    if args.adapter:
        print(f"Loading adapter from {args.adapter} ...")
        model = PeftModel.from_pretrained(model, args.adapter, is_trainable=False)
    processor = AutoProcessor.from_pretrained(args.model, local_files_only=True)
    print(f"Model loaded. Device: {model.device}")

    # ------------------------------------------------------------------
    # Determine sample selection
    # ------------------------------------------------------------------
    is_batch = args.sample_index is None

    if not is_batch:
        # Single-sample mode
        if not 0 <= args.sample_index < len(rows):
            raise IndexError(f"sample-index {args.sample_index} is outside [0, {len(rows)})")
        indices = [args.sample_index]
    else:
        indices = list(range(len(rows)))
        if args.max_samples and args.max_samples < len(indices):
            indices = indices[:args.max_samples]

    print(f"Processing {len(indices)} sample(s) out of {len(rows)} total ...")
    print(f"  Prompt: {args.prompt[:60]}...")
    print(f"  Max new tokens: {args.max_new_tokens}")

    # ------------------------------------------------------------------
    # Run inference
    # ------------------------------------------------------------------
    results = []
    n_total = len(indices)

    for i, idx in enumerate(indices):
        sample = rows[idx]
        image_path = Path(sample["images"][0])
        if not image_path.is_file():
            print(f"  [{i+1}/{n_total}] SKIP: image not found {image_path}")
            continue

        reference = sample["messages"][1]["content"]

        # Run inference
        t0 = time.time()
        try:
            prediction = run_inference(
                model, processor, image_path, args.prompt, args.max_new_tokens,
            )
        except Exception as e:
            print(f"  [{i+1}/{n_total}] ERROR at index {idx}: {e}")
            continue
        elapsed = time.time() - t0

        # Compute metrics
        metrics = compute_metrics(prediction, reference)

        # Look up metadata
        meta = lookup_metadata(meta_index, str(image_path))

        # Build result record
        result = {
            "sample_index": idx,
            "image": str(image_path),
            "prompt": args.prompt,
            "prediction": prediction,
            "prediction_chars": len(prediction),
            "reference": reference,
            "reference_chars": len(reference),
            "html_valid": metrics.html_valid,
            "parsed_rows": metrics.parsed_rows,
            "parsed_cols": metrics.parsed_cols,
            "structure_signature_match": metrics.structure_signature_match,
            "structure_score": metrics.structure_score,
            "ref_cell_count": metrics.ref_cell_count,
            "pred_cell_count": metrics.pred_cell_count,
            "correct_cell_text": metrics.correct_cell_text,
            "cell_text_accuracy": metrics.cell_text_accuracy,
            "parse_errors": metrics.errors,
            "inference_seconds": round(elapsed, 2),
            "model": str(args.model.resolve()),
            "adapter": str(args.adapter.resolve()) if args.adapter else None,
            "generation": {
                "max_new_tokens": args.max_new_tokens,
                "do_sample": False,
                "torch_dtype": "bfloat16",
            },
            "versions": {
                "torch": torch.__version__,
                "transformers": transformers.__version__,
            },
        }

        # Enrich with metadata if available
        if meta:
            result["config_id"] = meta.get("config_id")
            result["simple"] = meta.get("simple")
            result["colored"] = meta.get("colored")
            result["lined"] = meta.get("lined")
            result["header_type"] = meta.get("header_type")
            result["has_rowspan"] = meta.get("has_rowspan")
            result["has_colspan"] = meta.get("has_colspan")
            result["rows"] = meta.get("rows")
            result["cols"] = meta.get("cols")
            result["semantic_scenario"] = meta.get("semantic_scenario")
            result["topic"] = meta.get("topic")

        results.append(result)

        # Print progress
        cell_info = f"cell_acc={metrics.cell_text_accuracy:.3f}"
        struct_info = "struct=OK" if metrics.structure_signature_match else "struct=MISMATCH"
        print(
            f"  [{i+1}/{n_total}] idx={idx:3d} "
            f"{cell_info} {struct_info} "
            f"chars={len(prediction):4d} "
            f"{elapsed:.1f}s"
        )

        # Write per-sample result in single-sample mode
        if not is_batch:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"\nSaved single result to {args.output}")
            print(f"Prediction ({len(prediction)} chars):")
            print(prediction[:500])

    # ------------------------------------------------------------------
    # Write batch output
    # ------------------------------------------------------------------
    if is_batch and results:
        output_dir = args.output
        output_dir.mkdir(parents=True, exist_ok=True)

        # results.jsonl
        (output_dir / "results.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n",
            encoding="utf-8",
        )

        # Also write per-sample JSON files for easy inspection
        samples_dir = output_dir / "samples"
        samples_dir.mkdir(parents=True, exist_ok=True)
        for r in results:
            sidx = r["sample_index"]
            (samples_dir / f"sample_{sidx:03d}.json").write_text(
                json.dumps(r, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        # Compute and write summaries
        stats = compute_summary(results)
        group_sums = group_summaries(results)
        write_summary(output_dir, stats, group_sums, {
            "model": str(args.model),
            "data_json": str(args.data_json),
            "meta_jsonl": str(args.meta_jsonl) if args.meta_jsonl else None,
            "adapter": str(args.adapter) if args.adapter else None,
            "max_samples": args.max_samples,
            "prompt": args.prompt,
            "max_new_tokens": args.max_new_tokens,
        })

        # Print summary table
        print("\n" + "=" * 70)
        print("OVERALL RESULTS")
        print("=" * 70)
        print(f"  Total samples:          {stats.total}")
        print(f"  HTML valid:             {stats.html_valid}/{stats.total} ({_pct(stats.html_valid, stats.total)})")
        print(f"  Structure exact match:  {stats.structure_exact_match}/{stats.total} ({_pct(stats.structure_exact_match, stats.total)})")
        print(f"  Avg cell text accuracy: {stats.avg_cell_accuracy}")
        print(f"  Avg structure score:    {stats.avg_structure_score}")
        print(f"  Avg inference time:     {stats.avg_inference_seconds}s")
        print(f"\nOutput: {output_dir.resolve()}")

    elif not results:
        print("No results generated.")


if __name__ == "__main__":
    main()
