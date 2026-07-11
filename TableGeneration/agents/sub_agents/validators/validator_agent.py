from ...agent_types import TableSchema


class ValidatorAgent:
    """Checks row/column coverage before rendering."""

    def validate(self, schema: TableSchema):
        matrix, errors = self.build_matrix(schema)
        if errors:
            return False, errors
        for row, row_cells in enumerate(matrix):
            if any(cell_id is None for cell_id in row_cells):
                covered = len([cell_id for cell_id in row_cells if cell_id is not None])
                errors.append(f"row {row} covers {covered} cells, expected {schema.cols}")
        return len(errors) == 0, errors

    def build_matrix(self, schema: TableSchema):
        matrix = [[None for _ in range(schema.cols)] for _ in range(schema.rows)]
        errors = []
        for cell in schema.cells:
            if cell.row < 0 or cell.col < 0:
                errors.append(f"negative cell position at ({cell.row}, {cell.col})")
                continue
            if cell.rowspan < 1 or cell.colspan < 1:
                errors.append(f"invalid span value at ({cell.row}, {cell.col})")
                continue
            if cell.row + cell.rowspan > schema.rows or cell.col + cell.colspan > schema.cols:
                errors.append(f"span out of range at ({cell.row}, {cell.col})")
                continue
            for row in range(cell.row, cell.row + cell.rowspan):
                for col in range(cell.col, cell.col + cell.colspan):
                    if matrix[row][col] is not None:
                        errors.append(f"overlapped cell at ({row}, {col})")
                        continue
                    matrix[row][col] = cell.cell_id
        return matrix, errors
