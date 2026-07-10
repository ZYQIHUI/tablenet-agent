import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.export_qwen_sft.export_qwen_sft import build_samples, split_samples, write_split


def write_jsonl(path, rows):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def make_dataset(root, count=5):
    (root / "img").mkdir()
    metas = []
    cells = []
    gts = []
    for idx in range(count):
        filename = f"img/sample_{idx}.jpg"
        Image.new("RGB", (20, 20), "white").save(root / filename)
        metas.append({"filename": filename, "topic": f"sample {idx}"})
        cells.append({"filename": filename, "cells": [{"text": str(idx), "bbox": [[0, 0], [10, 0], [10, 10], [0, 10]]}]})
        gts.append({
            "filename": filename,
            "html": {
                "cells": [{"tokens": [str(idx)]}],
                "structure": {"tokens": ["<table>", "<tr>", "<td>", "</td>", "</tr>", "</table>"]},
            },
        })
    write_jsonl(root / "meta.jsonl", metas)
    write_jsonl(root / "cells.jsonl", cells)
    write_jsonl(root / "gt.txt", gts)


class ExportQwenSftTest(unittest.TestCase):
    def test_build_samples_uses_messages_and_images(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_dataset(root, count=1)
            samples = build_samples(root, "prompt", False, "html")
            self.assertEqual(len(samples), 1)
            self.assertEqual(samples[0]["messages"][0]["role"], "user")
            self.assertEqual(samples[0]["messages"][1]["role"], "assistant")
            self.assertEqual(samples[0]["images"], ["img/sample_0.jpg"])
            self.assertIn("<image>", samples[0]["messages"][0]["content"])
            self.assertIn("<table>", samples[0]["messages"][1]["content"])

    def test_absolute_image_paths_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_dataset(root, count=1)
            samples = build_samples(root, "prompt", True, "cells")
            self.assertTrue(Path(samples[0]["images"][0]).is_absolute())
            self.assertIn('"text": "0"', samples[0]["messages"][1]["content"])

    def test_html_target_wraps_structure_fragments(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_dataset(root, count=1)
            gt_path = root / "gt.txt"
            rows = [json.loads(line) for line in gt_path.read_text(encoding="utf-8").splitlines()]
            rows[0]["html"]["structure"]["tokens"] = ["<tr>", "<td>", "</td>", "</tr>"]
            write_jsonl(gt_path, rows)

            samples = build_samples(root, "prompt", False, "html")

            self.assertEqual(samples[0]["messages"][1]["content"], "<table><tr><td>0</td></tr></table>")

    def test_split_and_write_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_dataset(root, count=10)
            samples = build_samples(root, "prompt", False, "html")
            split = split_samples(samples, val_ratio=0.2, test_ratio=0.1, seed=7)
            self.assertEqual(len(split["train"]), 7)
            self.assertEqual(len(split["val"]), 2)
            self.assertEqual(len(split["test"]), 1)
            out = root / "sft"
            manifest = write_split(out, split)
            self.assertEqual(manifest, {"train": 7, "val": 2, "test": 1})
            self.assertTrue((out / "train.json").exists())
            self.assertTrue((out / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
