import random

from ...agent_types import TablePlan, TableStyle


class StyleAgent:
    """Chooses visual styling attributes for rendered tables."""

    def build(self, plan: TablePlan, schema=None) -> TableStyle:
        visual = self._visual_attributes(plan, schema)
        line_name, table_border, cell_border, header_border = self._line_style(plan, visual)
        header_bg = f"background:{visual['header_background']};" if plan.colored else ""
        body_bg = f"background:{visual['body_background']};" if plan.colored else ""
        table_bg = f"background:{visual['table_background']};"
        align_css = f"text-align:{visual['align']};"
        font_css = f"font-family:{visual['font_family']};font-size:{visual['font_size']}px;"
        return TableStyle(
            name=self._style_name(plan, line_name),
            table_css=f"border-collapse:collapse;{align_css}{font_css}{table_bg}{table_border}",
            cell_css=f"padding:{visual['cell_padding']};word-break:break-all;{cell_border}{body_bg}",
            header_css=f"padding:{visual['header_padding']};font-weight:bold;{header_border}{header_bg}",
            visual=visual,
        )

    def _visual_attributes(self, plan: TablePlan, schema=None):
        rows = getattr(schema, "rows", plan.rows)
        cols = getattr(schema, "cols", plan.cols)
        texts = [cell.text for cell in getattr(schema, "cells", []) if cell.text]
        max_text_length = max((len(text) for text in texts), default=0)
        density = rows * cols
        if density >= 60 or max_text_length >= 18:
            padding = ("compact", "4px 8px", "5px 10px")
            font_size = random.choice([12, 13])
        elif density >= 30 or max_text_length >= 10:
            padding = random.choice([
                ("compact", "4px 10px", "5px 12px"),
                ("regular", "6px 12px", "7px 14px"),
            ])
            font_size = random.choice([12, 13, 14])
        else:
            padding = random.choice([
                ("regular", "6px 14px", "7px 16px"),
                ("loose", "8px 18px", "9px 20px"),
            ])
            font_size = random.choice([13, 14, 15])
        fonts = (
            ["Arial", "Times New Roman", "Microsoft YaHei"]
            if plan.language == "en"
            else ["Microsoft YaHei", "SimSun", "SimHei", "Arial"]
        )
        background_mode = random.choice(["plain", "zebra", "soft_fill"]) if plan.colored else "plain"
        return {
            "font_family": random.choice(fonts),
            "font_size": font_size,
            "padding_mode": padding[0],
            "cell_padding": padding[1],
            "header_padding": padding[2],
            "align": random.choice(["center", "left", "right"]),
            "background_mode": background_mode,
            "table_background": "white",
            "header_background": random.choice(["#e8f2ff", "#edf7ed", "#fff0d9", "#f2ecff"]),
            "body_background": "#fff7e6" if background_mode != "plain" else "white",
            "zebra_background": random.choice(["#f7fbff", "#f8f8f8", "#fffaf0"]),
            "border_weight": random.choice(["thin", "regular", "strong"]),
            "density": density,
            "max_text_length": max_text_length,
        }

    def _line_style(self, plan: TablePlan, visual):
        border_width = {
            "thin": "1px",
            "regular": "1px",
            "strong": "2px",
        }[visual["border_weight"]]
        if plan.lined:
            return random.choice([
                (
                    "full",
                    f"border:{border_width} solid #111;",
                    f"border:{border_width} solid #111;",
                    f"border:{border_width} solid #111;",
                ),
                (
                    "horizontal",
                    f"border-top:{border_width} solid #111;border-bottom:{border_width} solid #111;",
                    f"border-top:{border_width} solid #333;border-bottom:{border_width} solid #333;",
                    f"border-top:{border_width} solid #111;border-bottom:{border_width} solid #111;",
                ),
                (
                    "vertical",
                    f"border-left:{border_width} solid #111;border-right:{border_width} solid #111;",
                    f"border-left:{border_width} solid #333;border-right:{border_width} solid #333;",
                    f"border-left:{border_width} solid #111;border-right:{border_width} solid #111;",
                ),
                (
                    "header",
                    "",
                    "",
                    f"border-bottom:{border_width} solid #111;",
                ),
            ])
        return random.choice([
            ("none", "", "", ""),
            ("light_horizontal", "", "border-bottom:1px solid #ddd;", "border-bottom:1px solid #999;"),
        ])

    def _style_name(self, plan: TablePlan, line_name: str) -> str:
        parts = ["agent"]
        parts.append("simple" if plan.simple else "complex")
        parts.append("colored" if plan.colored else "plain")
        parts.append(line_name)
        return "_".join(parts)
