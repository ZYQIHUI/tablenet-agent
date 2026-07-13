from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..agent_types import Cell, TableSchema


@dataclass
class FallbackResult:
    schema: TableSchema
    cell_mapping: Dict[str, List[int]] = field(default_factory=dict)
    source_errors: List[str] = field(default_factory=list)
    preserved_cell_ids: List[str] = field(default_factory=list)


class FallbackConstructor:
    """Rebuilds a valid unit-cell schema and records old-to-new cell lineage."""

    def construct(
            self,
            original: Optional[TableSchema],
            errors=None,
            target_rows: Optional[int] = None,
            target_cols: Optional[int] = None,
            preserve_content: bool = True) -> FallbackResult:
        rows = target_rows or getattr(original, "rows", 0)
        cols = target_cols or getattr(original, "cols", 0)
        if rows < 1 or cols < 1:
            raise ValueError("fallback target rows and cols must be positive")

        original_cells = list(getattr(original, "cells", []) or [])
        title = next((cell for cell in original_cells if cell.role == "title"), None)
        header_rows = self._header_rows(original_cells)
        source_by_position = self._source_positions(original_cells, rows, cols)
        cells = []
        mapping: Dict[str, List[int]] = {}
        preserved = set()

        if title is not None:
            new_cell = Cell(
                row=0,
                col=0,
                tag="th",
                text=title.text if preserve_content else "",
                colspan=cols,
                role="title",
                cell_id=len(cells),
                visual=dict(title.visual),
            )
            cells.append(new_cell)
            self._map_cell(mapping, title, new_cell.cell_id)
            preserved.add(self._old_key(title))

        start_row = 1 if title is not None else 0
        for row in range(start_row, rows):
            for col in range(cols):
                source = source_by_position.get((row, col))
                role = self._role_for(row, header_rows, source)
                tag = "th" if role in ("title", "header") else "td"
                text = ""
                visual = {}
                if source is not None and preserve_content:
                    text = source.text
                    visual = dict(source.visual)
                    preserved.add(self._old_key(source))
                new_cell = Cell(
                    row=row,
                    col=col,
                    tag=tag,
                    text=text,
                    role=role,
                    cell_id=len(cells),
                    visual=visual,
                )
                cells.append(new_cell)
                if source is not None:
                    self._map_cell(mapping, source, new_cell.cell_id)

        schema = TableSchema(
            rows=rows,
            cols=cols,
            cells=cells,
            header_type="fallback_unit_grid",
            has_rowspan=False,
            has_colspan=bool(title is not None and cols > 1),
        )
        return FallbackResult(
            schema=schema,
            cell_mapping=mapping,
            source_errors=[str(error) for error in (errors or [])],
            preserved_cell_ids=sorted(preserved),
        )

    def _source_positions(self, cells, rows, cols):
        positions = {}
        for cell in cells:
            if cell.row < 0 or cell.col < 0:
                continue
            for row in range(cell.row, min(rows, cell.row + max(1, cell.rowspan))):
                for col in range(cell.col, min(cols, cell.col + max(1, cell.colspan))):
                    positions.setdefault((row, col), cell)
        return positions

    def _header_rows(self, cells):
        return {cell.row for cell in cells if cell.role == "header"}

    def _role_for(self, row, header_rows, source):
        if source is not None and source.role in ("header", "body"):
            return source.role
        if row in header_rows or (not header_rows and row == 0):
            return "header"
        return "body"

    def _map_cell(self, mapping, old_cell, new_id):
        mapping.setdefault(self._old_key(old_cell), []).append(new_id)

    def _old_key(self, cell):
        if cell.cell_id is not None:
            return str(cell.cell_id)
        return f"{cell.row},{cell.col}"
