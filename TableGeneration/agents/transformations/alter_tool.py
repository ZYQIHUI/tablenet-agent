from copy import deepcopy

from .region_model import RegionModel


class AlterTool:
    def apply(self, schema, row: int, background_color: str = "#f2f6fa", count: int = 1):
        result = deepcopy(schema)
        region = RegionModel(result).region("row", row, count)
        cells = RegionModel(result).contained_cells(region)
        if not cells:
            raise ValueError(f"row block [{row}, {row + count}) has no independently alterable cells")
        for cell in cells:
            cell.visual["background-color"] = background_color
        return result
