from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TableRequest:
    # 用户请求 -定义想要什么样子的表格-
    domain: str = "telecommunications"
    language: str = "zh"
    min_rows: int = 4
    max_rows: int = 12
    min_cols: int = 3
    max_cols: int = 8
    simple: Optional[bool] = None
    colored: Optional[bool] = None
    lined: Optional[bool] = None


@dataclass
class TablePlan:
    domain: str
    language: str
    topic: str
    rows: int
    cols: int
    simple: bool
    colored: bool
    lined: bool


@dataclass
class Cell:
    row: int
    col: int
    tag: str = "td"
    text: str = ""
    rowspan: int = 1
    colspan: int = 1
    role: str = "body"
    cell_id: Optional[int] = None


@dataclass
class TableSchema:
    rows: int
    cols: int
    cells: List[Cell] = field(default_factory=list)


@dataclass
class TableStyle:
    name: str
    table_css: str
    cell_css: str
    header_css: str


@dataclass
class AgentTable:
    plan: TablePlan
    schema: TableSchema
    style: TableStyle
    html: str
    structure_tokens: List[str]
    id_count: int

