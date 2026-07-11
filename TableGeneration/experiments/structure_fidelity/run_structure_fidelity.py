import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.run_agents import COMPLEX_STRUCTURE_TYPES
from agents.sub_agents.fillers.body_agent import BodyAgent
from agents.sub_agents.fillers.header_agent import HeaderAgent
from agents.sub_agents.planners.schema_agent import SchemaAgent
from agents.tools.rendering.html_builder import HtmlBuilder
from agents.agent_types import TablePlan, TableStyle


CASES = (
    ("simple_with_content", True, True),
    ("simple_without_content", True, False),
    ("complex_with_content", False, True),
    ("complex_without_content", False, False),
)


@dataclass
class ParsedCell:
    row: int
    col: int
    rowspan: int
    colspan: int
    tag: str
    text: str


class TableHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.current_tag = None
        self.current_attrs = {}
        self.current_text = []
        self.rows = []
        self.row_cells = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.row_cells = []
        elif tag in ("td", "th") and self.in_row:
            self.current_tag = tag
            self.current_attrs = dict(attrs)
            self.current_text = []

    def handle_data(self, data):
        if self.current_tag:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.current_tag == tag:
            self.row_cells.append({
                "tag": self.current_tag,
                "rowspan": _int_attr(self.current_attrs.get("rowspan"), 1),
                "colspan": _int_attr(self.current_attrs.get("colspan"), 1),
                "text": "".join(self.current_text).strip(),
            })
            self.current_tag = None
            self.current_attrs = {}
            self.current_text = []
        elif tag == "tr" and self.in_row:
            self.rows.append(self.row_cells)
            self.row_cells = []
            self.in_row = False
        elif tag == "table":
            self.in_table = False


def _int_attr(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def parse_html_table(html):
    parser = TableHTMLParser()
    parser.feed(html)
    return place_cells(parser.rows)


def place_cells(rows):
    matrix = []
    cells = []
    errors = []
    occupied = {}
    max_col = 0
    for row_index, row_cells in enumerate(rows):
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
            for row in range(row_index, row_index + rowspan):
                for item_col in range(col, col + colspan):
                    key = (row, item_col)
                    if key in occupied:
                        errors.append(f"overlap at ({row}, {item_col})")
                    occupied[key] = len(cells) - 1
            col += colspan
            max_col = max(max_col, col)
    max_row = max([row for row, _ in occupied], default=-1) + 1
    for row in range(max_row):
        matrix_row = []
        for col in range(max_col):
            matrix_row.append(occupied.get((row, col)))
        matrix.append(matrix_row)
        if any(item is None for item in matrix_row):
            errors.append(f"row {row} has uncovered slots")
    if rows and len(matrix) != len(rows):
        errors.append(f"row count expanded from {len(rows)} to {len(matrix)}")
    return cells, matrix, errors


def expected_spans(schema):
    return {
        (cell.row, cell.col, cell.rowspan, cell.colspan)
        for cell in schema.cells
    }


def parsed_spans(cells):
    return {
        (cell.row, cell.col, cell.rowspan, cell.colspan)
        for cell in cells
    }


def structure_score(expected, observed):
    if not expected and not observed:
        return 1.0
    overlap = len(expected & observed)
    return round((2 * overlap) / (len(expected) + len(observed)), 4)


def make_plan(case_name, simple, sample_index):
    structure_type = None
    if not simple:
        structure_type = COMPLEX_STRUCTURE_TYPES[sample_index % len(COMPLEX_STRUCTURE_TYPES)]
    return TablePlan(
        domain="telecommunications",
        language="zh",
        topic=f"mini结构保真度实验-{case_name}-{sample_index}",
        rows=7,
        cols=5,
        simple=simple,
        colored=True,
        lined=True,
        config_id=f"{'simple' if simple else 'complex'}_colored_lined",
        semantic_scenario="network_coverage",
        structure_type=structure_type,
    )


def build_schema(plan, with_content):
    schema = SchemaAgent().build(plan)
    if with_content:
        schema = HeaderAgent().fill(schema, plan)
        schema = BodyAgent().fill(schema, plan)
    return schema


def agent_tool_html(plan, schema):
    style = TableStyle(name="structure_fidelity", table_css="", cell_css="", header_css="")
    return HtmlBuilder().build(plan, schema, style).html


def direct_baseline_html(schema, with_content):
    rows = []
    for row in range(schema.rows):
        row_cells = [cell for cell in schema.cells if cell.row == row]
        row_cells.sort(key=lambda item: item.col)
        html_cells = []
        for position, cell in enumerate(row_cells):
            if _drop_direct_cell(schema, cell, position, with_content):
                continue
            attrs = []
            rowspan, colspan = _direct_spans(schema, cell, with_content)
            if rowspan > 1:
                attrs.append(f'rowspan="{rowspan}"')
            if colspan > 1:
                attrs.append(f'colspan="{colspan}"')
            text = cell.text if with_content else ""
            attr_text = " " + " ".join(attrs) if attrs else ""
            html_cells.append(f"<{cell.tag}{attr_text}>{text}</{cell.tag}>")
        rows.append("<tr>" + "".join(html_cells) + "</tr>")
    return "<html><body><table>" + "".join(rows) + "</table></body></html>"


def _drop_direct_cell(schema, cell, position, with_content):
    if schema.header_type == "simple_single_header":
        return False
    if with_content and schema.header_type in ("mixed_headers", "two_axis_header"):
        return cell.role == "header" and cell.row > 2 and cell.col == 1
    if not with_content and schema.header_type == "body_rowspan":
        return cell.row > 2 and cell.col == 0 and position == 0
    return False


def _direct_spans(schema, cell, with_content):
    rowspan = cell.rowspan
    colspan = cell.colspan
    if schema.header_type == "simple_single_header":
        return rowspan, colspan
    if cell.colspan > 1:
        if with_content:
            colspan = max(1, cell.colspan - 1)
        elif schema.header_type in ("grouped_columns", "summary_row_colspan"):
            colspan = 1
    if cell.rowspan > 1:
        if with_content or schema.header_type in ("body_rowspan", "multi_level_column_header"):
            rowspan = 1
    return rowspan, colspan


def evaluate_sample(method, case_name, simple, with_content, sample_index):
    plan = make_plan(case_name, simple, sample_index)
    schema = build_schema(plan, with_content)
    html = agent_tool_html(plan, schema)
    if method == "llm_direct":
        html = direct_baseline_html(schema, with_content)
    parsed_cells, matrix, errors = parse_html_table(html)
    exp = expected_spans(schema)
    obs = parsed_spans(parsed_cells)
    score = structure_score(exp, obs)
    row_count = len(matrix)
    col_count = len(matrix[0]) if matrix else 0
    exact = score == 1.0 and row_count == schema.rows and col_count == schema.cols and not errors
    return {
        "method": method,
        "case": case_name,
        "sample_index": sample_index,
        "header_type": schema.header_type,
        "expected_rows": schema.rows,
        "expected_cols": schema.cols,
        "parsed_rows": row_count,
        "parsed_cols": col_count,
        "expected_cells": len(schema.cells),
        "parsed_cells": len(parsed_cells),
        "structure_score": score,
        "exact_match": exact,
        "structure_valid": not errors and row_count == schema.rows and col_count == schema.cols,
        "error_count": len(errors),
    }


def summarize(rows):
    summaries = []
    for method in ("agent_tool", "llm_direct"):
        for case_name, _, _ in CASES:
            group = [row for row in rows if row["method"] == method and row["case"] == case_name]
            total = len(group)
            summaries.append({
                "method": method,
                "case": case_name,
                "samples": total,
                "exact_match": sum(1 for row in group if row["exact_match"]),
                "structure_valid": sum(1 for row in group if row["structure_valid"]),
                "avg_structure_score": round(sum(row["structure_score"] for row in group) / total, 4) if total else 0.0,
                "avg_error_count": round(sum(row["error_count"] for row in group) / total, 4) if total else 0.0,
            })
    return summaries


def write_outputs(output, rows, summaries):
    output.mkdir(parents=True, exist_ok=True)
    (output / "samples.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    with open(output / "summary.csv", "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(summaries[0].keys()))
        writer.writeheader()
        writer.writerows(summaries)
    (output / "summary.md").write_text(summary_markdown(summaries), encoding="utf-8")


def summary_markdown(summaries):
    lines = [
        "# Mini Structure Fidelity Experiment",
        "",
        f"- Created at: {datetime.now().isoformat(timespec='seconds')}",
        "- Metric: span-level structure score, exact match, parsed structure validity.",
        "- Direct baseline: deterministic offline HTML baseline for LLM-direct style errors.",
        "",
        "| Method | Case | Samples | Exact Match | Structure Valid | Avg Structure Score | Avg Error Count |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['method']} | {row['case']} | {row['samples']} | "
            f"{row['exact_match']} | {row['structure_valid']} | "
            f"{row['avg_structure_score']} | {row['avg_error_count']} |"
        )
    return "\n".join(lines) + "\n"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples_per_case", type=int, default=7)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/structure_fidelity/results"),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    rows = []
    for case_name, simple, with_content in CASES:
        for sample_index in range(args.samples_per_case):
            for method in ("agent_tool", "llm_direct"):
                rows.append(evaluate_sample(method, case_name, simple, with_content, sample_index))
    summaries = summarize(rows)
    write_outputs(args.output, rows, summaries)
    print(f"wrote structure fidelity results into {args.output}")
    print(summary_markdown(summaries))


if __name__ == "__main__":
    main()
