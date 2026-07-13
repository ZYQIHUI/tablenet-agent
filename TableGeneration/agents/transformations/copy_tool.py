from copy import deepcopy

from .region_model import RegionModel, next_cell_id, refresh_schema_flags


class CopyTool:
    def apply(self, schema, axis: str, start: int, count: int = 1):
        result = deepcopy(schema)
        model = RegionModel(result)
        region = model.region(axis, start, count)
        selected = list(model.contained_cells(region))
        next_id = next_cell_id(result)

        if axis == "row":
            for cell in result.cells:
                if cell.row >= region.end:
                    cell.row += region.size
            for original in selected:
                clone = deepcopy(original)
                clone.row += region.size
                clone.cell_id = next_id
                next_id += 1
                result.cells.append(clone)
            result.rows += region.size
        else:
            for cell in result.cells:
                if cell.col >= region.end:
                    cell.col += region.size
            for original in selected:
                clone = deepcopy(original)
                clone.col += region.size
                clone.cell_id = next_id
                next_id += 1
                result.cells.append(clone)
            result.cols += region.size
        return refresh_schema_flags(result)
