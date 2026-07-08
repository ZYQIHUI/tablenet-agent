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
        os.makedirs(self.output, exist_ok=True)
        os.makedirs(os.path.join(self.output, "html"), exist_ok=True)
        os.makedirs(os.path.join(self.output, "img"), exist_ok=True)
        gt_path = os.path.join(self.output, "gt.txt")
        meta_path = os.path.join(self.output, "meta.jsonl")
        with open(gt_path, "w", encoding="utf-8") as f_gt, open(
                meta_path, "w", encoding="utf-8") as f_meta:
            for idx, table in enumerate(tables):
                self.render_one(table, idx, f_gt, f_meta)

    def render_one(self, table, idx, f_gt, f_meta):
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
        f_meta.write(
            json.dumps(
                {
                    "filename": img_file_name,
                    "source": "agent_generated",
                    "domain": table.plan.domain,
                    "topic": table.plan.topic,
                    "rows": table.plan.rows,
                    "cols": table.plan.cols,
                    "simple": table.plan.simple,
                    "colored": table.plan.colored,
                    "lined": table.plan.lined,
                    "style": table.style.name,
                },
                ensure_ascii=False,
            ) + "\n")

    def close(self):
        self.generator.close()

    def _name(self, border, idx):
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
        return f"{border}_{idx}_{suffix}"
