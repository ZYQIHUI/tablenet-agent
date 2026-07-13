from copy import deepcopy

from .region_model import RegionModel, refresh_schema_flags


class DeleteTool:
    def apply(self, schema, axis: str, start: int, count: int = 1):
        result = deepcopy(schema)
        model = RegionModel(result)
        region = model.region(axis, start, count)
        if (axis == "row" and region.size >= result.rows) or (
                axis == "column" and region.size >= result.cols):
            raise ValueError("cannot delete the entire table")
        selected_ids = {id(cell) for cell in model.contained_cells(region)}
        result.cells = [cell for cell in result.cells if id(cell) not in selected_ids]
        if axis == "row":
            for cell in result.cells:
                if cell.row >= region.end:
                    cell.row -= region.size
            result.rows -= region.size
        else:
            for cell in result.cells:
                if cell.col >= region.end:
                    cell.col -= region.size
            result.cols -= region.size
        return refresh_schema_flags(result)
