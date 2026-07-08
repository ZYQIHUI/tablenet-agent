import random

from ...types import Cell, TablePlan, TableSchema


class SchemaAgent:
    """Builds valid table layouts with simple and complex span patterns."""

    def build(self, plan: TablePlan) -> TableSchema:
        if plan.simple:
            return self._simple(plan)
        return self._complex(plan)

    def _simple(self, plan: TablePlan) -> TableSchema:
        cells = []
        for row in range(plan.rows):
            for col in range(plan.cols):
                role = "header" if row == 0 else "body"
                tag = "th" if role == "header" else "td"
                cells.append(Cell(row=row, col=col, tag=tag, role=role))
        return self._schema(plan, cells)

    def _complex(self, plan: TablePlan) -> TableSchema:
        if plan.rows < 4 or plan.cols < 3:
            return self._title_header(plan)
        pattern = random.choice(
            [
                self._grouped_columns,
                self._left_headers,
                self._body_rowspan,
                self._mixed_headers,
            ])
        return pattern(plan)

    def _title_header(self, plan: TablePlan) -> TableSchema:
        cells = [Cell(row=0, col=0, tag="th", role="title", colspan=plan.cols)]
        for row in range(1, plan.rows):
            for col in range(plan.cols):
                role = "header" if row == 1 else "body"
                tag = "th" if role == "header" else "td"
                cells.append(Cell(row=row, col=col, tag=tag, role=role))
        return self._schema(plan, cells)

    def _grouped_columns(self, plan: TablePlan) -> TableSchema:
        cells = [Cell(row=0, col=0, tag="th", role="title", colspan=plan.cols)]
        split = max(2, plan.cols // 2)
        cells.append(Cell(row=1, col=0, tag="th", role="header", rowspan=2))
        cells.append(Cell(row=1, col=1, tag="th", role="header", colspan=split - 1))
        if split < plan.cols:
            cells.append(Cell(row=1, col=split, tag="th", role="header", colspan=plan.cols - split))
        for col in range(1, plan.cols):
            cells.append(Cell(row=2, col=col, tag="th", role="header"))
        for row in range(3, plan.rows):
            for col in range(plan.cols):
                cells.append(Cell(row=row, col=col, tag="td", role="body"))
        return self._schema(plan, cells)

    def _left_headers(self, plan: TablePlan) -> TableSchema:
        cells = [Cell(row=0, col=0, tag="th", role="title", colspan=plan.cols)]
        for col in range(plan.cols):
            cells.append(Cell(row=1, col=col, tag="th", role="header"))
        for row in range(2, plan.rows):
            cells.append(Cell(row=row, col=0, tag="th", role="header"))
            for col in range(1, plan.cols):
                cells.append(Cell(row=row, col=col, tag="td", role="body"))
        return self._schema(plan, cells)

    def _body_rowspan(self, plan: TablePlan) -> TableSchema:
        cells = [Cell(row=0, col=0, tag="th", role="title", colspan=plan.cols)]
        for col in range(plan.cols):
            cells.append(Cell(row=1, col=col, tag="th", role="header"))
        row = 2
        while row < plan.rows:
            can_span = row + 1 < plan.rows and random.random() < 0.5
            rowspan = 2 if can_span else 1
            cells.append(Cell(row=row, col=0, tag="td", role="body", rowspan=rowspan))
            for offset in range(rowspan):
                for col in range(1, plan.cols):
                    cells.append(Cell(row=row + offset, col=col, tag="td", role="body"))
            row += rowspan
        return self._schema(plan, cells)

    def _mixed_headers(self, plan: TablePlan) -> TableSchema:
        cells = [Cell(row=0, col=0, tag="th", role="title", colspan=plan.cols)]
        cells.append(Cell(row=1, col=0, tag="th", role="header", rowspan=2))
        cells.append(Cell(row=1, col=1, tag="th", role="header", colspan=plan.cols - 1))
        for col in range(1, plan.cols):
            cells.append(Cell(row=2, col=col, tag="th", role="header"))
        for row in range(3, plan.rows):
            cells.append(Cell(row=row, col=0, tag="th", role="header"))
            for col in range(1, plan.cols):
                cells.append(Cell(row=row, col=col, tag="td", role="body"))
        return self._schema(plan, cells)

    def _schema(self, plan: TablePlan, cells):
        for idx, cell in enumerate(cells):
            cell.cell_id = idx
        return TableSchema(rows=plan.rows, cols=plan.cols, cells=cells)
