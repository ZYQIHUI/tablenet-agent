import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.dataset_audit.run_dataset_audit import audit_dataset, write_outputs


def write_jsonl(path, rows):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def make_dataset(root):
    (root / "img").mkdir()
    (root / "html").mkdir()
    Image.new("RGB", (100, 80), "white").save(root / "img" / "sample.jpg")
    (root / "html" / "sample.html").write_text("<table><tr><td>A</td></tr></table>", encoding="utf-8")
    filename = "img/sample.jpg"
    write_jsonl(root / "gt.txt", [{
        "filename": filename,
        "html": {"cells": [{"tokens": ["A"], "bbox": [[0, 0], [50, 0], [50, 20], [0, 20]]}],
                 "structure": {"tokens": ["<table>", "<tr>", "<td>", "</td>", "</tr>", "</table>"]}},
    }])
    write_jsonl(root / "meta.jsonl", [{
        "filename": filename,
        "config_id": "simple_colored_lined",
        "header_type": "simple_single_header",
        "visual": "plain",
    }])
    write_jsonl(root / "cells.jsonl", [{
        "filename": filename,
        "config_id": "simple_colored_lined",
        "header_type": "simple_single_header",
        "visual": "plain",
        "cell_count": 1,
        "cells": [{
            "role": "body",
            "bbox": [[0, 0], [50, 0], [50, 20], [0, 20]],
            "text": "A",
        }],
    }])
    (root / "report.json").write_text(json.dumps({"success": 1}), encoding="utf-8")


class DatasetAuditTest(unittest.TestCase):
    def test_valid_minimal_dataset_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_dataset(root)
            audit = audit_dataset(root)
            self.assertEqual(audit["status"], "pass")
            self.assertEqual(audit["sample_count"], 1)
            self.assertEqual(audit["role_counts"]["body"], 1)
            self.assertEqual(audit["invalid_bbox_count"], 0)

    def test_invalid_bbox_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_dataset(root)
            rows = [json.loads((root / "cells.jsonl").read_text(encoding="utf-8").strip())]
            rows[0]["cells"][0]["bbox"] = [[0, 0], [200, 0], [200, 20], [0, 20]]
            write_jsonl(root / "cells.jsonl", rows)
            audit = audit_dataset(root)
            self.assertEqual(audit["status"], "fail")
            self.assertEqual(audit["invalid_bbox_count"], 1)

    def test_write_outputs_creates_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_dataset(root)
            audit = audit_dataset(root)
            out = root / "audit_out"
            write_outputs(audit, out)
            self.assertTrue((out / "audit.json").exists())
            self.assertTrue((out / "audit.md").exists())

    def test_dict_visual_is_counted_by_attributes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_dataset(root)
            rows = [json.loads((root / "meta.jsonl").read_text(encoding="utf-8").strip())]
            rows[0]["visual"] = {"font_family": "Noto Sans CJK", "background_mode": "zebra"}
            write_jsonl(root / "meta.jsonl", rows)
            audit = audit_dataset(root)
            self.assertEqual(audit["status"], "pass")
            self.assertEqual(audit["visual_counts"]["background_mode=zebra"], 1)
            self.assertEqual(audit["visual_counts"]["font_family=Noto Sans CJK"], 1)


if __name__ == "__main__":
    unittest.main()
