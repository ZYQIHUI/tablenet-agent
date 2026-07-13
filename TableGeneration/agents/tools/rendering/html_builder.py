from html import escape

from ...agent_types import AgentTable, TablePlan, TableSchema, TableStyle


class HtmlBuilder:
    """Converts planned cells into renderable HTML and structure tokens."""

    def build(self, plan: TablePlan, schema: TableSchema, style: TableStyle) -> AgentTable:
        html = ["<html>", self._style(style), "<body><table>"]
        structure = []
        id_count = 0
        cells_by_row = {}
        for cell in schema.cells:
            cells_by_row.setdefault(cell.row, []).append(cell)
        for row in range(schema.rows):
            html.append("<tr>")
            structure.append("<tr>")
            for cell in sorted(cells_by_row.get(row, []), key=lambda item: item.col):
                attrs = [f"id={id_count}"]
                if cell.rowspan > 1:
                    attrs.append(f'rowspan="{cell.rowspan}"')
                if cell.colspan > 1:
                    attrs.append(f'colspan="{cell.colspan}"')
                if cell.visual:
                    inline_style = ";".join(
                        f"{escape(str(name), quote=True)}:{escape(str(value), quote=True)}"
                        for name, value in sorted(cell.visual.items())
                    )
                    attrs.append(f'style="{inline_style}"')
                tag = cell.tag
                html.append(f"<{tag} {' '.join(attrs)}>{escape(cell.text)}</{tag}>")
                self._append_structure(structure, cell)
                id_count += 1
            html.append("</tr>")
            structure.append("</tr>")
        html.append("</table></body></html>")
        return AgentTable(
            plan=plan,
            schema=schema,
            style=style,
            html="".join(html),
            structure_tokens=structure,
            id_count=id_count,
        )

    def _style(self, style: TableStyle) -> str:
        return (
            '<head><meta charset="UTF-8"><style>'
            f"html{{background-color:white;}}"
            f"table{{{style.table_css}}}"
            f"td{{{style.cell_css}}}"
            f"th{{{style.header_css}}}"
            "</style></head>"
        )

    def _append_structure(self, structure, cell):
        if cell.rowspan > 1 or cell.colspan > 1:
            structure.append("<td")
            if cell.rowspan > 1:
                structure.append(f' rowspan="{cell.rowspan}"')
            if cell.colspan > 1:
                structure.append(f' colspan="{cell.colspan}"')
            structure.append(">")
        else:
            structure.append("<td>")
        structure.append("</td>")
