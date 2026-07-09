import json
import os
import random
import string

from TableGeneration.GenerateTable import GenerateTable


class RendererTool:
    """Renders AgentTable objects and writes PP-Structure style labels."""

    def __init__(
            self,
            output,
            ch_dict_path="dict/ch_news.txt",
            en_dict_path="dict/en_corpus.txt",
            brower="chrome",
            chrome_driver_path=None,
            brower_width=1920,
            brower_height=2440):
        self.output = output
        self.generator = GenerateTable(
            output=output,
            ch_dict_path=ch_dict_path,
            en_dict_path=en_dict_path,
            brower=brower,
            brower_width=brower_width,
            brower_height=brower_height,
            chrome_driver_path=chrome_driver_path,
        )

    def render_many(self, tables):
        self.prepare_output()
        gt_path = os.path.join(self.output, "gt.txt")
        meta_path = os.path.join(self.output, "meta.jsonl")
        cells_path = os.path.join(self.output, "cells.jsonl")
        with open(gt_path, "w", encoding="utf-8") as f_gt, open(
                meta_path, "w", encoding="utf-8") as f_meta, open(
                cells_path, "w", encoding="utf-8") as f_cells:
            for idx, table in enumerate(tables):
                self.render_one(table, idx, f_gt, f_meta, f_cells)

    def prepare_output(self):
        os.makedirs(self.output, exist_ok=True)
        os.makedirs(os.path.join(self.output, "html"), exist_ok=True)
        os.makedirs(os.path.join(self.output, "img"), exist_ok=True)

    def render_one(self, table, idx, f_gt, f_meta, f_cells=None):
        border = table.style.name
        im, html, structure, contens, _ = self.generator.render_table(
            table.html,
            table.structure_tokens,
            table.id_count,
            border,
        )
        name = self._name(border, idx)
        html_save_path = os.path.join(self.output, "html", name + ".html")
        img_save_path = os.path.join(self.output, "img", name + ".jpg")
        with open(html_save_path, "w", encoding="utf-8") as f:
            f.write(html)
        im.save(img_save_path, dpi=(600, 600))

        img_file_name = os.path.join("img", name + ".jpg")
        label_info = self.generator.make_ppstructure_label(
            structure,
            contens,
            img_file_name,
        )
        f_gt.write(json.dumps(label_info, ensure_ascii=False) + "\n")
        meta = self._metadata(table, img_file_name)
        f_meta.write(json.dumps(meta, ensure_ascii=False) + "\n")
        if f_cells is not None:
            f_cells.write(
                json.dumps(
                    self._cell_annotations(table, contens, img_file_name),
                    ensure_ascii=False,
                ) + "\n")
        return meta

    def close(self):
        self.generator.close()

    def _name(self, border, idx):
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
        return f"{border}_{idx}_{suffix}"

    def _line_type(self, style_name):
        if style_name.endswith("_full"):
            return "fully_lined"
        if style_name.endswith("_horizontal") or style_name.endswith("_light_horizontal"):
            return "horizontal_lined"
        if style_name.endswith("_vertical"):
            return "vertical_lined"
        if style_name.endswith("_header"):
            return "header_lined"
        return "unlined"

    def _metadata(self, table, img_file_name):
        return {
            "filename": img_file_name,
            "source": "agent_generated",
            "domain": table.plan.domain,
            "language": table.plan.language,
            "config_id": table.plan.config_id,
            "topic": table.plan.topic,
            "rows": table.plan.rows,
            "cols": table.plan.cols,
            "simple": table.plan.simple,
            "colored": table.plan.colored,
            "lined": table.plan.lined,
            "style": table.style.name,
            "line_type": self._line_type(table.style.name),
            "header_type": table.schema.header_type,
            "has_rowspan": table.schema.has_rowspan,
            "has_colspan": table.schema.has_colspan,
        }

    @staticmethod
    def _cell_annotations(table, contens, img_file_name):
        cells = []
        sorted_cells = sorted(table.schema.cells, key=lambda cell: cell.cell_id)
        for cell, content in zip(sorted_cells, contens):
            text = content[1]
            bbox = content[2]
            cells.append({
                "cell_id": cell.cell_id,
                "row": cell.row,
                "col": cell.col,
                "rowspan": cell.rowspan,
                "colspan": cell.colspan,
                "tag": cell.tag,
                "role": RendererTool._role(cell),
                "text": text,
                "tokens": list(text),
                "bbox": bbox,
                "is_header": cell.role in ("title", "header"),
                "is_empty": text == "",
            })
        return {
            "filename": img_file_name,
            "config_id": table.plan.config_id,
            "header_type": table.schema.header_type,
            "rows": table.schema.rows,
            "cols": table.schema.cols,
            "cell_count": len(cells),
            "cells": cells,
        }

    @staticmethod
    def _role(cell):
        if cell.role == "title":
            return "title"
        if cell.role == "header" and cell.col == 0 and cell.row > 1:
            return "row_header"
        if cell.role == "header":
            return "column_header"
        return "body"
