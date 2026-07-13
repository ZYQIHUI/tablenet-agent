from typing import List

from ..domain.state import CandidateState
from .alter_tool import AlterTool
from .copy_tool import CopyTool
from .delete_tool import DeleteTool
from .region_model import RegionModel, UnsafeRegionError
from .swap_tool import SwapTool


class AugmentationPipeline:
    """Builds validated copy/delete/swap/alter descendants of one candidate."""

    TRANSFORMATIONS = ("copy", "delete", "swap", "alter")

    def __init__(self, validator, checker, selector):
        self.validator = validator
        self.checker = checker
        self.selector = selector
        self.tools = {
            "copy": CopyTool(),
            "delete": DeleteTool(),
            "swap": SwapTool(),
            "alter": AlterTool(),
        }

    def generate(self, parent, plan, limit: int = 4) -> List[CandidateState]:
        results = []
        for name in self.TRANSFORMATIONS[:max(0, min(limit, 4))]:
            candidate = self._transform(parent, name)
            if candidate is None:
                continue
            ok, errors = self.validator.validate(candidate.schema)
            candidate.validation_result = {"ok": ok, "errors": list(errors)}
            if not ok:
                candidate.metadata["rejection_reason"] = "structure_validation_failed"
                results.append(candidate)
                continue
            report = self.checker.evaluate(candidate.schema, plan)
            candidate.checker_report = report
            self.selector.score(candidate)
            results.append(candidate)
        return results

    def _transform(self, parent, name):
        schema = parent.schema
        safe_rows = self._safe_body_regions(schema, "row")
        safe_columns = self._safe_body_regions(schema, "column")
        try:
            if name == "copy":
                if safe_rows:
                    start, count = safe_rows[-1]
                    transformed = self.tools[name].apply(schema, "row", start, count)
                    params = {"axis": "row", "start": start, "count": count}
                elif safe_columns:
                    start, count = safe_columns[-1]
                    transformed = self.tools[name].apply(schema, "column", start, count)
                    params = {"axis": "column", "start": start, "count": count}
                else:
                    return None
            elif name == "delete":
                if safe_rows:
                    start, count = safe_rows[-1]
                    transformed = self.tools[name].apply(schema, "row", start, count)
                    params = {"axis": "row", "start": start, "count": count}
                elif safe_columns:
                    start, count = safe_columns[-1]
                    transformed = self.tools[name].apply(schema, "column", start, count)
                    params = {"axis": "column", "start": start, "count": count}
                else:
                    return None
            elif name == "swap":
                if len(safe_rows) >= 2:
                    first, first_count = safe_rows[0]
                    second, second_count = safe_rows[-1]
                    transformed = self.tools[name].apply(
                        schema, "row", first, second, first_count, second_count,
                    )
                    params = {
                        "axis": "row", "first": first, "second": second,
                        "count": first_count, "second_count": second_count,
                    }
                elif len(safe_columns) >= 2:
                    first, first_count = safe_columns[0]
                    second, second_count = safe_columns[-1]
                    transformed = self.tools[name].apply(
                        schema, "column", first, second, first_count, second_count,
                    )
                    params = {
                        "axis": "column", "first": first, "second": second,
                        "count": first_count, "second_count": second_count,
                    }
                else:
                    body_cells = [
                        cell for cell in schema.cells
                        if cell.role == "body" and cell.rowspan == 1 and cell.colspan == 1
                    ]
                    if len(body_cells) < 2:
                        return None
                    first = body_cells[0]
                    second = body_cells[-1]
                    transformed = self.tools[name].apply_cells(
                        schema,
                        (first.row, first.col),
                        (second.row, second.col),
                    )
                    params = {
                        "axis": "cell_block",
                        "first": [first.row, first.col],
                        "second": [second.row, second.col],
                    }
            else:
                alter_rows = safe_rows or self._safe_regions(schema, "row")
                if not alter_rows:
                    return None
                start, count = alter_rows[-1]
                transformed = self.tools[name].apply(schema, start, count=count)
                params = {"row": start, "count": count}
        except (UnsafeRegionError, ValueError):
            return None

        return CandidateState(
            schema=transformed,
            parent_candidate_id=parent.candidate_id,
            generation_source="transformation",
            transformation=name,
            metadata={"transformation_params": params},
        )

    def _safe_body_regions(self, schema, axis):
        regions = []
        model = RegionModel(schema)
        limit = schema.rows if axis == "row" else schema.cols
        boundaries = [index for index in range(limit + 1) if model.is_safe_boundary(axis, index)]
        for start, end in zip(boundaries, boundaries[1:]):
            region = model.region(axis, start, end - start)
            cells = model.contained_cells(region)
            if (
                cells
                and any(cell.role == "body" for cell in cells)
                and all(cell.role != "title" for cell in cells)
            ):
                regions.append((start, end - start))
        return regions

    def _safe_regions(self, schema, axis):
        regions = []
        model = RegionModel(schema)
        limit = schema.rows if axis == "row" else schema.cols
        boundaries = [index for index in range(limit + 1) if model.is_safe_boundary(axis, index)]
        for start, end in zip(boundaries, boundaries[1:]):
            region = model.region(axis, start, end - start)
            if model.contained_cells(region):
                regions.append((start, end - start))
        return regions
