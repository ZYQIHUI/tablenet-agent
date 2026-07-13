import random

from ...agent_types import Cell, TablePlan, TableSchema


class SchemaAgent:
    """Builds valid table layouts with simple and complex span patterns."""

    COMPLEX_PATTERN_NAMES = (
        "grouped_columns",
        "left_headers",
        "body_rowspan",
        "mixed_headers",
        "two_axis_header",
        "summary_row_colspan",
        "multi_level_column_header",
    )

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
        return self._schema(plan, cells, "simple_single_header")

    def _complex(self, plan: TablePlan) -> TableSchema:
        if plan.rows < 4 or plan.cols < 3:
            return self._title_header(plan)
        if plan.structure_type:
            return self._build_named_pattern(plan, plan.structure_type)
        patterns = [
            self._grouped_columns,
            self._left_headers,
            self._body_rowspan,
            self._mixed_headers,
            self._two_axis_header,
            self._summary_row_colspan,
        ]
        if plan.rows >= 5:
            patterns.append(self._multi_level_column_header)
        pattern = random.choice(patterns)
        return pattern(plan)

    def _build_named_pattern(self, plan: TablePlan, structure_type: str) -> TableSchema:
        builders = {
            "grouped_columns": self._grouped_columns,
            "left_headers": self._left_headers,
            "body_rowspan": self._body_rowspan,
            "mixed_headers": self._mixed_headers,
            "two_axis_header": self._two_axis_header,
            "summary_row_colspan": self._summary_row_colspan,
            "multi_level_column_header": self._multi_level_column_header,
        }
        if structure_type == "multi_level_column_header" and plan.rows < 5:
            raise ValueError(
                "unsupported request: multi_level_column_header requires at least 5 rows"
            )
        builder = builders.get(structure_type)
        if builder is None:
            raise ValueError(f"unsupported request: unknown structure_type={structure_type}")
        return builder(plan)

    def _title_header(self, plan: TablePlan) -> TableSchema:
        cells = [Cell(row=0, col=0, tag="th", role="title", colspan=plan.cols)]
        for row in range(1, plan.rows):
            for col in range(plan.cols):
                role = "header" if row == 1 else "body"
                tag = "th" if role == "header" else "td"
                cells.append(Cell(row=row, col=col, tag=tag, role=role))
        return self._schema(plan, cells, "title_header")

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
        return self._schema(plan, cells, "grouped_columns")

    def _left_headers(self, plan: TablePlan) -> TableSchema:
        cells = [Cell(row=0, col=0, tag="th", role="title", colspan=plan.cols)]
        for col in range(plan.cols):
            cells.append(Cell(row=1, col=col, tag="th", role="header"))
        for row in range(2, plan.rows):
            cells.append(Cell(row=row, col=0, tag="th", role="header"))
            for col in range(1, plan.cols):
                cells.append(Cell(row=row, col=col, tag="td", role="body"))
        return self._schema(plan, cells, "left_headers")

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
        return self._schema(plan, cells, "body_rowspan")

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
        return self._schema(plan, cells, "mixed_headers")

    def _multi_level_column_header(self, plan: TablePlan) -> TableSchema:
        cells = [Cell(row=0, col=0, tag="th", role="title", colspan=plan.cols)]
        cells.append(Cell(row=1, col=0, tag="th", role="header", rowspan=3))
        start = 1
        while start < plan.cols:
            width = min(random.choice([2, 3]), plan.cols - start)
            if width == 1:
                cells.append(Cell(row=1, col=start, tag="th", role="header", rowspan=2))
            else:
                cells.append(Cell(row=1, col=start, tag="th", role="header", colspan=width))
                split = max(1, width // 2)
                cells.append(Cell(row=2, col=start, tag="th", role="header", colspan=split))
                if split < width:
                    cells.append(Cell(row=2, col=start + split, tag="th", role="header", colspan=width - split))
            start += width
        for col in range(1, plan.cols):
            cells.append(Cell(row=3, col=col, tag="th", role="header"))
        for row in range(4, plan.rows):
            for col in range(plan.cols):
                cells.append(Cell(row=row, col=col, tag="td", role="body"))
        return self._schema(plan, cells, "multi_level_column_header")

    def _two_axis_header(self, plan: TablePlan) -> TableSchema:
        cells = [Cell(row=0, col=0, tag="th", role="title", colspan=plan.cols)]
        cells.append(Cell(row=1, col=0, tag="th", role="header", colspan=2))
        if plan.cols > 2:
            cells.append(Cell(row=1, col=2, tag="th", role="header", colspan=plan.cols - 2))
        cells.append(Cell(row=2, col=0, tag="th", role="header"))
        cells.append(Cell(row=2, col=1, tag="th", role="header"))
        for col in range(2, plan.cols):
            cells.append(Cell(row=2, col=col, tag="th", role="header"))
        for row in range(3, plan.rows):
            cells.append(Cell(row=row, col=0, tag="th", role="header"))
            cells.append(Cell(row=row, col=1, tag="th", role="header"))
            for col in range(2, plan.cols):
                cells.append(Cell(row=row, col=col, tag="td", role="body"))
        return self._schema(plan, cells, "two_axis_header")

    def _summary_row_colspan(self, plan: TablePlan) -> TableSchema:
        cells = [Cell(row=0, col=0, tag="th", role="title", colspan=plan.cols)]
        for col in range(plan.cols):
            cells.append(Cell(row=1, col=col, tag="th", role="header"))
        summary_row = plan.rows - 1
        for row in range(2, summary_row):
            for col in range(plan.cols):
                cells.append(Cell(row=row, col=col, tag="td", role="body"))
        label_span = max(1, plan.cols - 2)
        cells.append(Cell(row=summary_row, col=0, tag="th", role="header", colspan=label_span))
        for col in range(label_span, plan.cols):
            cells.append(Cell(row=summary_row, col=col, tag="td", role="body"))
        return self._schema(plan, cells, "summary_row_colspan")

    def _schema(self, plan: TablePlan, cells, header_type: str):
        for idx, cell in enumerate(cells):
            cell.cell_id = idx
        return TableSchema(
            rows=plan.rows,
            cols=plan.cols,
            cells=cells,
            header_type=header_type,
            has_rowspan=any(cell.rowspan > 1 for cell in cells),
            has_colspan=any(cell.colspan > 1 for cell in cells),
        )
