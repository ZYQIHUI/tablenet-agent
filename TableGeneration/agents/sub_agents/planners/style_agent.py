import random

from ...types import TablePlan, TableStyle


class StyleAgent:
    """Chooses visual styling attributes for rendered tables."""

    def build(self, plan: TablePlan) -> TableStyle:
        line_name, table_border, cell_border, header_border = self._line_style(plan)
        header_bg = "background:#e8f2ff;" if plan.colored else ""
        body_bg = "background:#fff7e6;" if plan.colored else ""
        table_bg = "background:white;"
        return TableStyle(
            name=self._style_name(plan, line_name),
            table_css=f"border-collapse:collapse;text-align:center;{table_bg}{table_border}",
            cell_css=f"padding:6px 14px;word-break:break-all;{cell_border}{body_bg}",
            header_css=f"padding:7px 16px;font-weight:bold;{header_border}{header_bg}",
        )

    def _line_style(self, plan: TablePlan):
        if plan.lined:
            return random.choice([
                (
                    "full",
                    "border:1px solid #111;",
                    "border:1px solid #111;",
                    "border:1px solid #111;",
                ),
                (
                    "horizontal",
                    "border-top:1px solid #111;border-bottom:1px solid #111;",
                    "border-top:1px solid #333;border-bottom:1px solid #333;",
                    "border-top:1px solid #111;border-bottom:1px solid #111;",
                ),
                (
                    "vertical",
                    "border-left:1px solid #111;border-right:1px solid #111;",
                    "border-left:1px solid #333;border-right:1px solid #333;",
                    "border-left:1px solid #111;border-right:1px solid #111;",
                ),
                (
                    "header",
                    "",
                    "",
                    "border-bottom:2px solid #111;",
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
