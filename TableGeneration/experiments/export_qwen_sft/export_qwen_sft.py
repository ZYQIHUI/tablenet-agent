import argparse
import json
import random
from pathlib import Path


DEFAULT_PROMPT = "请识别图片中的表格，并输出可还原表格结构和文本内容的 HTML。"


def read_jsonl(path):
    rows = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def filename_of(row):
    return row.get("filename") or row.get("image") or row.get("img") or row.get("img_path")


def index_by_filename(rows):
    return {filename_of(row): row for row in rows if filename_of(row)}


def clean_text(text):
    for token in ("<b>", "</b>", "<i>", "</i>", "\u2028"):
        text = text.replace(token, "")
    return text.strip()


def gt_to_html(gt_row):
    html = gt_row.get("html", {})
    structure = html.get("structure", {}).get("tokens", [])
    cells = html.get("cells", [])
    tokens = list(structure)
    insert_positions = [idx for idx, token in enumerate(tokens) if token in ("<td>", "<th>", ">")]
    for position, cell in zip(reversed(insert_positions), reversed(cells)):
        text = clean_text("".join(cell.get("tokens", [])))
        if text:
            tokens.insert(position + 1, text)
    return "".join(tokens)


def target_text(target, gt_row, cell_row, meta_row):
    if target == "html":
        if gt_row:
            html = gt_to_html(gt_row)
            if html:
                return html
        return json.dumps(cell_row.get("cells", []), ensure_ascii=False)
    if target == "cells":
        return json.dumps(cell_row.get("cells", []), ensure_ascii=False)
    payload = {
        "meta": meta_row,
        "cells": cell_row.get("cells", []),
    }
    if gt_row:
        payload["pp_structure"] = gt_row.get("html", {})
    return json.dumps(payload, ensure_ascii=False)


def image_path_for(data_dir, filename, absolute):
    path = data_dir / filename
    return str(path.resolve()) if absolute else filename.replace("\\", "/")


def build_samples(data_dir, prompt, absolute_images, target):
    data_dir = Path(data_dir)
    meta_rows = read_jsonl(data_dir / "meta.jsonl")
    cell_rows = read_jsonl(data_dir / "cells.jsonl")
    gt_rows = read_jsonl(data_dir / "gt.txt") if (data_dir / "gt.txt").exists() else []
    cells_by_file = index_by_filename(cell_rows)
    gt_by_file = index_by_filename(gt_rows)
    samples = []
    for meta in meta_rows:
        filename = filename_of(meta)
        if not filename or filename not in cells_by_file:
            continue
        cell_row = cells_by_file[filename]
        gt_row = gt_by_file.get(filename)
        samples.append({
            "messages": [
                {"role": "user", "content": f"<image>\n{prompt}"},
                {"role": "assistant", "content": target_text(target, gt_row, cell_row, meta)},
            ],
            "images": [image_path_for(data_dir, filename, absolute_images)],
        })
    return samples


def split_samples(samples, val_ratio, test_ratio, seed):
    if val_ratio < 0 or test_ratio < 0 or val_ratio + test_ratio >= 1:
        raise ValueError("val_ratio and test_ratio must be non-negative and sum to less than 1")
    shuffled = list(samples)
    random.Random(seed).shuffle(shuffled)
    total = len(shuffled)
    test_count = int(total * test_ratio)
    val_count = int(total * val_ratio)
    test = shuffled[:test_count]
    val = shuffled[test_count:test_count + val_count]
    train = shuffled[test_count + val_count:]
    return {"train": train, "val": val, "test": test}


def write_split(output_dir, split):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in split.items():
        (output_dir / f"{name}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    manifest = {name: len(rows) for name, rows in split.items()}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def parse_args():
    parser = argparse.ArgumentParser(description="Export generated tables to Qwen2-VL/LLaMA-Factory SFT JSON.")
    parser.add_argument("--input", "--data_dir", dest="input", type=Path, required=True,
                        help="Generated output directory containing meta.jsonl/cells.jsonl/img and optional gt.txt.")
    parser.add_argument("--output_dir", type=Path, required=True,
                        help="Directory for train.json, val.json, test.json and manifest.json.")
    parser.add_argument("--val_ratio", type=float, default=0.1)
    parser.add_argument("--test_ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--absolute_images", action="store_true",
                        help="Write absolute image paths. Default writes paths relative to --input.")
    parser.add_argument("--target", choices=("html", "cells", "json"), default="html",
                        help="Assistant target content to export.")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    return parser.parse_args()


def main():
    args = parse_args()
    samples = build_samples(args.input, args.prompt, args.absolute_images, args.target)
    split = split_samples(samples, args.val_ratio, args.test_ratio, args.seed)
    manifest = write_split(args.output_dir, split)
    print(f"wrote Qwen SFT files into {args.output_dir}")
    print(f"train={manifest['train']} val={manifest['val']} test={manifest['test']}")


if __name__ == "__main__":
    main()
