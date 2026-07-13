from copy import deepcopy

from .region_model import RegionModel, refresh_schema_flags


class SwapTool:
    def apply(
            self,
            schema,
            axis: str,
            first: int,
            second: int,
            count: int = 1,
            second_count=None):
        result = deepcopy(schema)
        model = RegionModel(result)
        left = model.region(axis, first, count)
        right = model.region(axis, second, second_count or count)
        if left.start > right.start:
            left, right = right, left
        if left.end > right.start:
            raise ValueError("swap regions must not overlap")
        left_cells = list(model.contained_cells(left))
        right_cells = list(model.contained_cells(right))
        middle_cells = []
        if left.end < right.start:
            middle = model.region(axis, left.end, right.start - left.end)
            middle_cells = list(model.contained_cells(middle))
        left_shift = right.end - left.size - left.start
        right_shift = left.start - right.start
        middle_shift = right.size - left.size
        for cell in left_cells:
            if axis == "row":
                cell.row += left_shift
            else:
                cell.col += left_shift
        for cell in right_cells:
            if axis == "row":
                cell.row += right_shift
            else:
                cell.col += right_shift
        for cell in middle_cells:
            if axis == "row":
                cell.row += middle_shift
            else:
                cell.col += middle_shift
        return refresh_schema_flags(result)

    def apply_cells(self, schema, first_position, second_position):
        result = deepcopy(schema)
        by_position = {(cell.row, cell.col): cell for cell in result.cells}
        first = by_position.get(tuple(first_position))
        second = by_position.get(tuple(second_position))
        if first is None or second is None:
            raise ValueError("swap cell position does not exist")
        if first.rowspan != 1 or first.colspan != 1 or second.rowspan != 1 or second.colspan != 1:
            raise ValueError("cell-level swap requires independent non-spanning cells")
        first.text, second.text = second.text, first.text
        first.visual, second.visual = second.visual, first.visual
        return refresh_schema_flags(result)
