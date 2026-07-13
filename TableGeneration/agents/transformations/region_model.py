from dataclasses import dataclass


class UnsafeRegionError(ValueError):
    pass


@dataclass(frozen=True)
class Region:
    axis: str
    start: int
    end: int

    @property
    def size(self):
        return self.end - self.start


class RegionModel:
    """Finds row/column boundaries that do not split spanning cells."""

    def __init__(self, schema):
        self.schema = schema

    def region(self, axis: str, start: int, count: int = 1) -> Region:
        if axis not in ("row", "column"):
            raise ValueError("axis must be 'row' or 'column'")
        if count < 1:
            raise ValueError("region count must be positive")
        limit = self.schema.rows if axis == "row" else self.schema.cols
        end = start + count
        if start < 0 or end > limit:
            raise UnsafeRegionError(f"{axis} region [{start}, {end}) is out of range")
        if not self.is_safe_boundary(axis, start) or not self.is_safe_boundary(axis, end):
            raise UnsafeRegionError(f"{axis} region [{start}, {end}) splits a spanning cell")
        return Region(axis, start, end)

    def is_safe_boundary(self, axis: str, boundary: int) -> bool:
        limit = self.schema.rows if axis == "row" else self.schema.cols
        if boundary < 0 or boundary > limit:
            return False
        if boundary in (0, limit):
            return True
        for cell in self.schema.cells:
            start = cell.row if axis == "row" else cell.col
            span = cell.rowspan if axis == "row" else cell.colspan
            if start < boundary < start + span:
                return False
        return True

    def contained_cells(self, region: Region):
        cells = []
        for cell in self.schema.cells:
            start = cell.row if region.axis == "row" else cell.col
            span = cell.rowspan if region.axis == "row" else cell.colspan
            if region.start <= start and start + span <= region.end:
                cells.append(cell)
        return cells


def next_cell_id(schema):
    ids = [cell.cell_id for cell in schema.cells if isinstance(cell.cell_id, int)]
    return max(ids, default=-1) + 1


def refresh_schema_flags(schema):
    schema.has_rowspan = any(cell.rowspan > 1 for cell in schema.cells)
    schema.has_colspan = any(cell.colspan > 1 for cell in schema.cells)
    return schema
