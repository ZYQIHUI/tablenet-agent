import argparse
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

from PIL import Image


REQUIRED_FILES = ("gt.txt", "meta.jsonl", "cells.jsonl", "report.json")


def read_jsonl(path):
    rows = []
    errors = []
    if not path.exists():
        return rows, [f"missing file: {path.name}"]
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                errors.append(f"{path.name}:{line_no}: invalid json: {error}")
    return rows, errors


def load_report(path):
    if not path.exists():
        return {}, [f"missing file: {path.name}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as error:
        return {}, [f"report.json: invalid json: {error}"]


def filename_of(row):
    return row.get("filename") or row.get("image") or row.get("img") or row.get("img_path")


def stem_for(filename):
    return Path(str(filename)).stem if filename else ""


def normalize_label_path(path):
    return str(Path(path)).replace("\\", "/")


def open_image(path):
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            return True, image.size, None
    except Exception as error:
        return False, (0, 0), str(error)


def bbox_points(bbox):
    if not isinstance(bbox, list) or len(bbox) < 4:
        return None
    points = []
    for point in bbox:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return None
        try:
            x = float(point[0])
            y = float(point[1])
        except (TypeError, ValueError):
            return None
        if not math.isfinite(x) or not math.isfinite(y):
            return None
        points.append((x, y))
    return points


def polygon_area(points):
    area = 0.0
    for idx, (x1, y1) in enumerate(points):
        x2, y2 = points[(idx + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def validate_bbox(bbox, width, height):
    points = bbox_points(bbox)
    if points is None:
        return False, "bbox must be a polygon with numeric points"
    if polygon_area(points) <= 0:
        return False, "bbox area must be positive"
    for x, y in points:
        if x < 0 or y < 0 or x > width or y > height:
            return False, f"bbox point out of image bounds ({width}x{height})"
    return True, None


def index_by_filename(rows):
    result = {}
    duplicates = []
    missing = []
    for row in rows:
        filename = filename_of(row)
        if not filename:
            missing.append(row)
            continue
        if filename in result:
            duplicates.append(filename)
        result[filename] = row
    return result, duplicates, missing


def audit_dataset(data_dir):
    data_dir = Path(data_dir)
    errors = []
    warnings = []
    for name in REQUIRED_FILES:
        if not (data_dir / name).exists():
            errors.append(f"missing required file: {name}")

    gt_rows, gt_errors = read_jsonl(data_dir / "gt.txt")
    meta_rows, meta_errors = read_jsonl(data_dir / "meta.jsonl")
    cell_rows, cell_errors = read_jsonl(data_dir / "cells.jsonl")
    report, report_errors = load_report(data_dir / "report.json")
    errors.extend(gt_errors + meta_errors + cell_errors + report_errors)

    gt_by_file, gt_dupes, gt_missing = index_by_filename(gt_rows)
    meta_by_file, meta_dupes, meta_missing = index_by_filename(meta_rows)
    cells_by_file, cell_dupes, cell_missing = index_by_filename(cell_rows)
    for label, dupes in (("gt.txt", gt_dupes), ("meta.jsonl", meta_dupes), ("cells.jsonl", cell_dupes)):
        if dupes:
            errors.append(f"{label}: duplicate filenames: {sorted(set(dupes))}")
    for label, missing_rows in (("gt.txt", gt_missing), ("meta.jsonl", meta_missing), ("cells.jsonl", cell_missing)):
        if missing_rows:
            errors.append(f"{label}: {len(missing_rows)} rows missing filename")

    gt_files = set(gt_by_file)
    meta_files = set(meta_by_file)
    cell_files = set(cells_by_file)
    all_label_files = gt_files | meta_files | cell_files
    for label, files in (("gt.txt", gt_files), ("meta.jsonl", meta_files), ("cells.jsonl", cell_files)):
        missing = sorted(all_label_files - files)
        if missing:
            errors.append(f"{label}: missing rows for {len(missing)} filenames")

    img_dir = data_dir / "img"
    html_dir = data_dir / "html"
    actual_images = {normalize_label_path(Path("img") / path.name) for path in img_dir.glob("*") if path.is_file()} if img_dir.exists() else set()
    actual_html_stems = {path.stem for path in html_dir.glob("*.html")} if html_dir.exists() else set()
    if not img_dir.exists():
        errors.append("missing directory: img")
    if not html_dir.exists():
        errors.append("missing directory: html")

    image_info = {}
    bad_images = []
    missing_images = []
    missing_html = []
    for filename in sorted(all_label_files):
        image_path = data_dir / filename
        if not image_path.exists():
            missing_images.append(filename)
            continue
        ok, size, message = open_image(image_path)
        image_info[filename] = {"ok": ok, "width": size[0], "height": size[1]}
        if not ok:
            bad_images.append({"filename": filename, "error": message})
        if stem_for(filename) not in actual_html_stems:
            missing_html.append(filename)
    extra_images = sorted(actual_images - all_label_files)

    if missing_images:
        errors.append(f"missing image files: {len(missing_images)}")
    if bad_images:
        errors.append(f"unreadable image files: {len(bad_images)}")
    if missing_html:
        errors.append(f"missing html files matching images: {len(missing_html)}")
    if extra_images:
        warnings.append(f"extra image files without labels: {len(extra_images)}")

    role_counts = Counter()
    config_counts = Counter()
    header_counts = Counter()
    visual_counts = Counter()
    invalid_bboxes = []
    total_cells = 0
    cell_count_mismatches = []

    for row in cell_rows:
        filename = filename_of(row)
        info = image_info.get(filename, {})
        width = info.get("width", 0)
        height = info.get("height", 0)
        cells = row.get("cells", [])
        if not isinstance(cells, list):
            errors.append(f"cells.jsonl: cells is not a list for {filename}")
            continue
        total_cells += len(cells)
        if row.get("cell_count") is not None and row.get("cell_count") != len(cells):
            cell_count_mismatches.append(filename)
        for idx, cell in enumerate(cells):
            role_counts.update([cell.get("role", "unknown")])
            if width and height:
                ok, message = validate_bbox(cell.get("bbox"), width, height)
                if not ok:
                    invalid_bboxes.append({"filename": filename, "cell_index": idx, "reason": message})
            else:
                invalid_bboxes.append({"filename": filename, "cell_index": idx, "reason": "image size unavailable"})

    if invalid_bboxes:
        errors.append(f"invalid bboxes: {len(invalid_bboxes)}")
    if cell_count_mismatches:
        errors.append(f"cell_count mismatches: {len(cell_count_mismatches)}")

    distribution_rows = meta_rows if meta_rows else cell_rows
    for row in distribution_rows:
        config_counts.update([row.get("config_id", "unknown")])
        header_counts.update([row.get("header_type", "unknown")])
        visual_counts.update(normalize_visual_counts(row.get("visual", "unknown")))

    report_success = report.get("success")
    if report_success is not None and report_success != len(meta_rows):
        warnings.append(f"report success={report_success} differs from meta rows={len(meta_rows)}")

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "data_dir": str(data_dir),
        "status": "pass" if not errors else "fail",
        "sample_count": len(all_label_files),
        "gt_rows": len(gt_rows),
        "meta_rows": len(meta_rows),
        "cells_rows": len(cell_rows),
        "image_files": len(actual_images),
        "html_files": len(actual_html_stems),
        "total_cells": total_cells,
        "invalid_bbox_count": len(invalid_bboxes),
        "role_counts": dict(sorted(role_counts.items())),
        "config_counts": dict(sorted(config_counts.items())),
        "header_type_counts": dict(sorted(header_counts.items())),
        "visual_counts": dict(sorted(visual_counts.items())),
        "errors": errors,
        "warnings": warnings,
        "details": {
            "missing_images": missing_images,
            "bad_images": bad_images,
            "missing_html": missing_html,
            "extra_images": extra_images,
            "invalid_bboxes": invalid_bboxes,
            "cell_count_mismatches": cell_count_mismatches,
        },
    }
    return summary


def normalize_visual_counts(visual):
    if isinstance(visual, dict):
        values = []
        for key, value in sorted(visual.items()):
            if isinstance(value, (str, int, float, bool)) or value is None:
                values.append(f"{key}={value}")
            else:
                values.append(f"{key}={json.dumps(value, ensure_ascii=False, sort_keys=True)}")
        return values or ["unknown"]
    if isinstance(visual, str) and visual:
        return [visual]
    return ["unknown"]


def audit_markdown(audit):
    lines = [
        "# Dataset Audit",
        "",
        f"- Data dir: `{audit['data_dir']}`",
        f"- Status: {audit['status']}",
        f"- Samples: {audit['sample_count']}",
        f"- Rows: gt={audit['gt_rows']}, meta={audit['meta_rows']}, cells={audit['cells_rows']}",
        f"- Files: images={audit['image_files']}, html={audit['html_files']}",
        f"- Total cells: {audit['total_cells']}",
        f"- Invalid bboxes: {audit['invalid_bbox_count']}",
        "",
        "## Role Counts",
        "",
    ]
    lines.extend(bullet_lines(counter_lines(audit["role_counts"])))
    lines.extend(["", "## Config Counts", ""])
    lines.extend(bullet_lines(counter_lines(audit["config_counts"])))
    lines.extend(["", "## Header Types", ""])
    lines.extend(bullet_lines(counter_lines(audit["header_type_counts"])))
    lines.extend(["", "## Visual Counts", ""])
    lines.extend(bullet_lines(counter_lines(audit["visual_counts"])))
    lines.extend(["", "## Errors", ""])
    lines.extend(bullet_lines(audit["errors"] or ["none"]))
    lines.extend(["", "## Warnings", ""])
    lines.extend(bullet_lines(audit["warnings"] or ["none"]))
    return "\n".join(lines) + "\n"


def counter_lines(counter):
    if not counter:
        return ["none"]
    return [f"{key}: {value}" for key, value in counter.items()]


def bullet_lines(lines):
    return [f"- {line}" for line in lines]


def write_outputs(audit, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "audit.md").write_text(audit_markdown(audit), encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="Audit generated TableGeneration dataset outputs.")
    parser.add_argument("--input", "--data_dir", dest="input", type=Path, required=True,
                        help="Generated output directory containing img/html/gt.txt/meta.jsonl/cells.jsonl/report.json.")
    parser.add_argument("--output_dir", type=Path, default=None,
                        help="Directory for audit.json and audit.md. Defaults to --input.")
    parser.add_argument("--fail_on_error", action="store_true",
                        help="Exit with code 1 when audit status is fail.")
    return parser.parse_args()


def main():
    args = parse_args()
    audit = audit_dataset(args.input)
    output_dir = args.output_dir or args.input
    write_outputs(audit, output_dir)
    print(f"wrote audit.json and audit.md into {output_dir}")
    print(f"status={audit['status']} samples={audit['sample_count']} invalid_bboxes={audit['invalid_bbox_count']}")
    if args.fail_on_error and audit["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
