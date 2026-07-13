import hashlib
import json
from typing import Iterable, List, Optional

from ..domain.state import CandidateState


class CandidatePool:
    """Owns candidate identity and deterministic structure/content deduplication."""

    def __init__(self):
        self._candidates: List[CandidateState] = []
        self._signatures = set()

    @property
    def candidates(self):
        return tuple(self._candidates)

    def add(self, candidate: CandidateState) -> bool:
        signature = self.signature(candidate.schema)
        candidate.metadata["signature"] = signature
        if signature in self._signatures:
            candidate.metadata["duplicate"] = True
            candidate.metadata["rejection_reason"] = "duplicate_candidate"
            return False
        self._signatures.add(signature)
        self._candidates.append(candidate)
        candidate.metadata["duplicate"] = False
        return True

    def signature(self, schema) -> str:
        cells = []
        for cell in sorted(schema.cells, key=lambda item: (item.row, item.col, item.role, item.tag)):
            cells.append({
                "row": cell.row,
                "col": cell.col,
                "rowspan": cell.rowspan,
                "colspan": cell.colspan,
                "role": cell.role,
                "tag": cell.tag,
                "text": self._normalize_text(cell.text),
                "visual": dict(sorted(cell.visual.items())),
            })
        payload = {
            "rows": schema.rows,
            "cols": schema.cols,
            "header_type": schema.header_type,
            "cells": cells,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _normalize_text(self, value) -> str:
        return " ".join(str(value or "").strip().lower().split())
