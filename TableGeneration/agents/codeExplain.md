# TableNet 多智能体表格生成系统 - 代码详解

## 📋 整体架构概览

这是一个**规则驱动的多智能体表格生成系统**（TableNet）。它的目标是：**自动生成带有标注的表格图像数据集**，用于训练表格识别模型。

### 系统工作流程（Pipeline）

```
用户请求 → CoreAgent（协调器）
    ↓
1. TopicAgent   → 生成表格主题和属性
2. SchemaAgent  → 构建表格结构（行列布局）
3. StyleAgent   → 生成 CSS 样式
4. HeaderAgent  → 填充表头内容
5. BodyAgent    → 填充表体内容
6. ValidatorAgent → 验证结构合法性
7. FillingChecker → 验证内容合理性
8. HtmlBuilder  → 生成最终 HTML
    ↓
RendererTool → 用 Selenium 渲染成图片 + 标注文件
```

### 当前目录结构

现在代码已经按职责拆分成子包：

```text
agents/
  core_agent.py
  types.py
  sub_agents/
    planners/
      topic_agent.py
      schema_agent.py
      style_agent.py
    fillers/
      header_agent.py
      body_agent.py
    validators/
      validator_agent.py
      filling_checker.py
  tools/
    adapters/
      llm_topic_client.py
      llm_header_client.py
      llm_body_client.py
    rendering/
      html_builder.py
      renderer_tool.py
```

---

## 📁 逐文件详解

### 第一步：类型定义 `types.py`

这是整个系统的**数据结构基础**，定义了 6 个核心数据类：

```python
@dataclass
class TableRequest:
    """用户请求 - 定义想要什么样的表格"""
    domain: str = "telecommunications"  # 领域：电信/金融/通用
    language: str = "zh"                # 语言
    min_rows: int = 4                   # 最小行数
    max_rows: int = 12                  # 最大行数
    min_cols: int = 3                   # 最小列数
    max_cols: int = 8                   # 最大列数
    simple: Optional[bool] = None       # 是否简单表格（无合并单元格）
    colored: Optional[bool] = None      # 是否带颜色
    lined: Optional[bool] = None        # 是否有边框线
```

```python
@dataclass
class TablePlan:
    """主题规划 - TopicAgent 的输出"""
    domain: str        # 领域
    language: str      # 语言
    topic: str         # 具体主题（如"5G基站月度维护统计"）
    rows: int          # 确定的行数
    cols: int          # 确定的列数
    simple: bool       # 是否简单表格
    colored: bool      # 是否带颜色
    lined: bool        # 是否有边框
```

```python
@dataclass
class Cell:
    """单元格 - 表格的最小单位"""
    row: int           # 行位置
    col: int           # 列位置
    tag: str = "td"    # HTML 标签（th 或 td）
    text: str = ""     # 单元格内容
    rowspan: int = 1   # 行合并数
    colspan: int = 1   # 列合并数
    role: str = "body" # 角色：title/header/body
    cell_id: Optional[int] = None  # 唯一标识
```

```python
@dataclass
class TableSchema:
    """表格结构 - SchemaAgent 的输出"""
    rows: int
    cols: int
    cells: List[Cell] = field(default_factory=list)  # 所有单元格列表
```

```python
@dataclass
class TableStyle:
    """表格样式 - StyleAgent 的输出"""
    name: str          # 样式名称（如 "agent_simple_colored_lined"）
    table_css: str     # 表格整体 CSS
    cell_css: str      # 普通单元格 CSS
    header_css: str    # 表头单元格 CSS
```

```python
@dataclass
class AgentTable:
    """最终输出 - 包含所有信息"""
    plan: TablePlan           # 主题规划
    schema: TableSchema       # 表格结构
    style: TableStyle         # 样式
    html: str                 # 完整 HTML 字符串
    structure_tokens: List[str]  # 结构标记（用于标注）
    id_count: int             # 单元格总数
```

**数据流：**
```markdown
TableRequest → TablePlan → TableSchema + TableStyle → AgentTable
```

---

### 第二步：核心协调器 `core_agent.py`

```python
class CoreAgent:
    """协调所有 Agent 的工作流程"""
    
    def __init__(self):
        # 初始化所有子 Agent
        self.topic_agent = TopicAgent()
        self.schema_agent = SchemaAgent()
        self.header_agent = HeaderAgent()
        self.body_agent = BodyAgent()
        self.style_agent = StyleAgent()
        self.validator_agent = ValidatorAgent()
        self.filling_checker = FillingChecker()
        self.html_builder = HtmlBuilder()

    def generate(self, request: TableRequest):
        # 按顺序执行流水线
        plan = self.topic_agent.plan(request)           # 1. 生成主题
        schema = self.schema_agent.build(plan)           # 2. 构建结构
        style = self.style_agent.build(plan)             # 3. 生成样式
        schema = self.header_agent.fill(schema, plan)    # 4. 填充表头
        schema = self.body_agent.fill(schema, plan)      # 5. 填充表体
        
        # 6. 验证结构
        ok, errors = self.validator_agent.validate(schema)
        if not ok:
            raise ValueError("invalid table schema: " + "; ".join(errors))
        
        # 7. 验证内容
        ok, errors = self.filling_checker.check(schema, plan)
        if not ok:
            raise ValueError("invalid table filling: " + "; ".join(errors))
        
        # 8. 生成 HTML
        return self.html_builder.build(plan, schema, style)
```

**关键点：** 这是一个**管道模式**，每个 Agent 处理完后把结果传给下一个。

---

### 第三步：主题生成 `topic_agent.py`

```python
class TopicAgent:
    """从预定义主题库中随机选择主题"""
    
    TOPICS = {
        "telecommunications": [
            "5G基站月度维护统计",
            "宽带用户增长分析",
            "通信网络故障处理记录",
            "套餐收入与用户规模对比",
            "区域网络覆盖质量评估",
        ],
        "finance": [
            "季度营收与成本分析",
            "部门预算执行情况",
            "资产负债摘要",
        ],
        "general": [
            "项目进度统计",
            "设备巡检记录",
            "业务指标汇总",
        ],
    }

    def plan(self, request: TableRequest) -> TablePlan:
        # 根据领域选择主题列表
        topics = self.TOPICS.get(request.domain, self.TOPICS["general"])
        
        # 随机确定行列数（在用户指定范围内）
        rows = random.randint(request.min_rows, request.max_rows)
        cols = random.randint(request.min_cols, request.max_cols)
        
        # 随机决定样式属性（如果用户没指定）
        simple = request.simple if request.simple is not None else random.random() < 0.55
        colored = request.colored if request.colored is not None else random.random() < 0.4
        lined = request.lined if request.lined is not None else random.random() < 0.7
        
        return TablePlan(
            domain=request.domain,
            language=request.language,
            topic=random.choice(topics),  # 随机选一个主题
            rows=rows,
            cols=cols,
            simple=simple,
            colored=colored,
            lined=lined,
        )
```

**作用：** 把用户的模糊请求（"给我一个电信表格"）转化为具体的计划。

---

### 第四步：结构构建 `schema_agent.py`

```python
class SchemaAgent:
    """根据计划构建表格的单元格布局"""
    
    def build(self, plan: TablePlan) -> TableSchema:
        cells = []
        
        if plan.simple:
            # 简单表格：第一行是表头，其余是表体
            for row in range(plan.rows):
                for col in range(plan.cols):
                    role = "header" if row == 0 else "body"
                    tag = "th" if role == "header" else "td"
                    cells.append(Cell(row=row, col=col, tag=tag, role=role))
        else:
            # 复杂表格：第一行是标题（跨所有列），第二行是表头
            cells.append(Cell(
                row=0, col=0,
                tag="th",
                role="title",      # 标题行
                colspan=plan.cols,  # 合并所有列
            ))
            for row in range(1, plan.rows):
                for col in range(plan.cols):
                    role = "header" if row == 1 else "body"
                    tag = "th" if role == "header" else "td"
                    cells.append(Cell(row=row, col=col, tag=tag, role=role))
        
        # 给每个单元格分配唯一 ID
        for idx, cell in enumerate(cells):
            cell.cell_id = idx
        
        return TableSchema(rows=plan.rows, cols=plan.cols, cells=cells)
```

**两种表格类型：**

- **简单表格（simple=True）：**
  ```
  | 表头1 | 表头2 | 表头3 |   ← row=0, role=header
  | 数据  | 数据  | 数据  |   ← row=1, role=body
  | 数据  | 数据  | 数据  |   ← row=2, role=body
  ```

- **复杂表格（simple=False）：**
  ```
  |      标题（colspan=3）    |   ← row=0, role=title
  | 表头1 | 表头2 | 表头3 |   ← row=1, role=header
  | 数据  | 数据  | 数据  |   ← row=2, role=body
  ```

---

### 第五步：样式生成 `style_agent.py`

```python
class StyleAgent:
    """根据计划生成 CSS 样式"""
    
    def build(self, plan: TablePlan) -> TableStyle:
        # 根据是否有边框选择不同的 border 样式
        border = "border:1px solid #111;" if plan.lined else "border-bottom:1px solid #333;"
        
        # 根据是否带颜色设置背景色
        header_bg = "background:#e8f2ff;" if plan.colored else ""  # 表头蓝色
        body_bg = "background:#fff7e6;" if plan.colored else ""    # 表体橙色
        
        return TableStyle(
            name=self._style_name(plan),  # 如 "agent_simple_colored_lined"
            table_css="border-collapse:collapse;text-align:center;background:white;",
            cell_css=f"padding:6px 14px;word-break:break-all;{border}{body_bg}",
            header_css=f"padding:7px 16px;font-weight:bold;{border}{header_bg}",
        )
    
    def _style_name(self, plan: TablePlan) -> str:
        # 生成描述性名称
        parts = ["agent"]
        parts.append("simple" if plan.simple else "complex")
        parts.append("colored" if plan.colored else "plain")
        parts.append("lined" if plan.lined else "lineless")
        return "_".join(parts)  # 如 "agent_simple_colored_lined"
```

**作用：** 控制表格的视觉外观。

---

### 第六步：表头填充 `header_agent.py`

```python
class HeaderAgent:
    """用领域相关的标签填充表头"""
    
    HEADERS = {
        "telecommunications": [
            "区域", "站点数", "用户数", "故障数", 
            "完成率", "收入", "同比", "备注",
        ],
        "finance": [
            "部门", "预算", "支出", "收入", 
            "利润", "同比", "状态", "备注",
        ],
        "general": [
            "项目", "负责人", "数量", "进度", 
            "状态", "评分", "日期", "备注",
        ],
    }

    def fill(self, schema: TableSchema, plan: TablePlan) -> TableSchema:
        headers = self.HEADERS.get(plan.domain, self.HEADERS["general"])
        
        for cell in schema.cells:
            if cell.role == "title":
                cell.text = plan.topic  # 标题单元格填主题
            elif cell.role == "header":
                # 表头单元格从预定义列表中循环取
                cell.text = headers[cell.col % len(headers)]
        
        return schema
```

**示例：** 如果是电信领域，3 列表格的表头会是：`["区域", "站点数", "用户数"]`

---

### 第七步：表体填充 `body_agent.py`

```python
class BodyAgent:
    """根据表头语义填充合理的数据"""
    
    REGIONS = ["东区", "西区", "南区", "北区", "中心区", "新区"]
    STATUS = ["正常", "待优化", "已完成", "跟进中", "需复核"]
    PEOPLE = ["张工", "李工", "王工", "赵工", "陈工"]

    def fill(self, schema: TableSchema, plan: TablePlan) -> TableSchema:
        headers = self._headers_by_col(schema)  # 获取每列的表头名
        
        for cell in schema.cells:
            if cell.role != "body":
                continue
            
            header = headers.get(cell.col, "")
            
            # 根据表头关键词智能填充
            if any(keyword in header for keyword in ("区域", "部门", "项目")):
                cell.text = random.choice(self.REGIONS)  # 随机区域名
            elif any(keyword in header for keyword in ("站点数", "用户数", "数量", "预算", "支出", "收入", "利润")):
                cell.text = str(random.randint(10, 999))  # 随机数字
            elif any(keyword in header for keyword in ("完成率", "同比", "进度", "评分")):
                cell.text = "{:.1f}%".format(random.uniform(70, 99.9))  # 百分比
            elif any(keyword in header for keyword in ("负责人",)):
                cell.text = random.choice(self.PEOPLE)  # 随机人名
            elif any(keyword in header for keyword in ("状态", "备注")):
                cell.text = random.choice(self.STATUS)  # 随机状态
            else:
                cell.text = self._fallback_value(cell.col)  # 兜底值
        
        return schema
    
    def _headers_by_col(self, schema: TableSchema):
        """构建 {列号: 表头名} 的映射"""
        headers = {}
        for cell in schema.cells:
            if cell.role == "header":
                for col in range(cell.col, cell.col + cell.colspan):
                    headers[col] = cell.text
        return headers
    
    def _fallback_value(self, col: int) -> str:
        """兜底值生成"""
        if col == 0:
            return random.choice(self.REGIONS)
        if col in (1, 2, 3):
            return str(random.randint(10, 999))
        return random.choice(self.STATUS)
```

**核心逻辑：** 通过**表头关键词匹配**来决定填什么类型的数据。比如看到"完成率"就填百分比，看到"区域"就填地名。

---

### 第八步：结构验证 `validator_agent.py`

```python
class ValidatorAgent:
    """验证表格结构的合法性"""
    
    def validate(self, schema: TableSchema):
        occupied = set()  # 已占用的位置
        errors = []
        
        for cell in schema.cells:
            # 检查1：位置不能为负
            if cell.row < 0 or cell.col < 0:
                errors.append(f"negative cell position at ({cell.row}, {cell.col})")
                continue
            
            # 检查2：不能超出表格边界
            if cell.row + cell.rowspan > schema.rows or cell.col + cell.colspan > schema.cols:
                errors.append(f"span out of range at ({cell.row}, {cell.col})")
                continue
            
            # 检查3：不能有重叠
            for row in range(cell.row, cell.row + cell.rowspan):
                for col in range(cell.col, cell.col + cell.colspan):
                    key = (row, col)
                    if key in occupied:
                        errors.append(f"overlapped cell at {key}")
                    occupied.add(key)
        
        # 检查4：每行必须填满
        for row in range(schema.rows):
            row_cells = [key for key in occupied if key[0] == row]
            if len(row_cells) != schema.cols:
                errors.append(f"row {row} covers {len(row_cells)} cells, expected {schema.cols}")
        
        return len(errors) == 0, errors
```

**验证内容：**
1. 位置合法性（不能有负数）
2. 边界检查（不能超出表格）
3. 重叠检查（合并单元格不能重叠）
4. 完整性检查（每行必须填满）

---

### 第九步：内容验证 `filling_checker.py`

`FillingChecker` 现在不只是返回 `True / False`，而是先生成一份 `FillingCheckReport`，里面包含：

- `score`：整体填充质量分
- `title_score`：标题和主题的匹配分
- `header_score`：表头质量分
- `body_score`：表体质量分
- `errors`：硬错误
- `warnings`：软警告
- `column_scores`：列级别评分

它仍然保留 `check()`，所以旧调用方式不变；只是内部先走 `evaluate()`，再决定是否通过。

**作用：** 不仅检查“有没有错”，还给出“哪里弱、弱到什么程度”，更接近论文里“排序型检查器”的思路。

---

### 第十步：HTML 构建 `html_builder.py`

```python
class HtmlBuilder:
    """将所有信息组装成最终的 HTML"""
    
    def build(self, plan: TablePlan, schema: TableSchema, style: TableStyle) -> AgentTable:
        html = ["<html>", self._style(style), "<body><table>"]
        structure = []  # 用于标注的结构标记
        id_count = 0
        
        # 按行分组
        cells_by_row = {}
        for cell in schema.cells:
            cells_by_row.setdefault(cell.row, []).append(cell)
        
        # 逐行生成 HTML
        for row in range(schema.rows):
            html.append("<tr>")
            structure.append("<tr>")
            
            for cell in sorted(cells_by_row.get(row, []), key=lambda item: item.col):
                attrs = [f"id={id_count}"]
                if cell.rowspan > 1:
                    attrs.append(f'rowspan="{cell.rowspan}"')
                if cell.colspan > 1:
                    attrs.append(f'colspan="{cell.colspan}"')
                
                tag = cell.tag
                html.append(f"<{tag} {' '.join(attrs)}>{escape(cell.text)}</{tag}>")
                self._append_structure(structure, cell)
                id_count += 1
            
            html.append("</tr>")
            structure.append("</tr>")
        
        html.append("</table></body></html>")
        
        return AgentTable(
            plan=plan,
            schema=schema,
            style=style,
            html="".join(html),           # 完整 HTML
            structure_tokens=structure,    # 结构标记
            id_count=id_count,            # 单元格数量
        )
    
    def _style(self, style: TableStyle) -> str:
        """生成 <head> 标签和 CSS"""
        return (
            '<head><meta charset="UTF-8"><style>'
            f"html{{background-color:white;}}"
            f"table{{{style.table_css}}}"
            f"td{{{style.cell_css}}}"
            f"th{{{style.header_css}}}"
            "</style></head>"
        )
    
    def _append_structure(self, structure, cell):
        """添加结构标记（用于后续标注）"""
        if cell.rowspan > 1 or cell.colspan > 1:
            structure.append("<td")
            if cell.rowspan > 1:
                structure.append(f' rowspan="{cell.rowspan}"')
            if cell.colspan > 1:
                structure.append(f' colspan="{cell.colspan}"')
            structure.append(">")
        else:
            structure.append("<td>")
        structure.append("</td>")
```

**输出示例：**
```html
<html>
<head><meta charset="UTF-8"><style>...</style></head>
<body><table>
<tr><th id=0 colspan="3">5G基站月度维护统计</th></tr>
<tr><th id=1>区域</th><th id=2>站点数</th><th id=3>用户数</th></tr>
<tr><td id=4>东区</td><td id=5>156</td><td id=6>89.5%</td></tr>
</table></body></html>
```

---

### 第十一步：渲染工具 `renderer_tool.py`

```python
class RendererTool:
    """使用 Selenium 渲染 HTML 为图片，并生成标注文件"""
    
    def __init__(self, output, ch_dict_path="dict/ch_news.txt", en_dict_path="dict/en_corpus.txt", 
                 brower="chrome", chrome_driver_path=None, brower_width=1920, brower_height=2440):
        self.output = output
        self.generator = GenerateTable(
            output=output,
            ch_dict_path=ch_dict_path,
            en_dict_path=en_dict_path,
            brower=brower,
            brower_width=brower_width,
            brower_height=brower_height,
            chrome_driver_path=chrome_driver_path,
        )

    def render_many(self, tables):
        """批量渲染多个表格"""
        # 创建输出目录
        os.makedirs(self.output, exist_ok=True)
        os.makedirs(os.path.join(self.output, "html"), exist_ok=True)
        os.makedirs(os.path.join(self.output, "img"), exist_ok=True)
        
        # 打开标注文件
        gt_path = os.path.join(self.output, "gt.txt")
        meta_path = os.path.join(self.output, "meta.jsonl")
        
        with open(gt_path, "w", encoding="utf-8") as f_gt, open(meta_path, "w", encoding="utf-8") as f_meta:
            for idx, table in enumerate(tables):
                self.render_one(table, idx, f_gt, f_meta)

    def render_one(self, table, idx, f_gt, f_meta):
        """渲染单个表格"""
        border = table.style.name
        
        # 1. 渲染 HTML 为图片
        im, html, structure, contents, _ = self.generator.render_table(
            table.html,
            table.structure_tokens,
            table.id_count,
            border,
        )
        
        # 2. 生成文件名
        name = self._name(border, idx)
        
        # 3. 保存 HTML 文件
        html_save_path = os.path.join(self.output, "html", name + ".html")
        with open(html_save_path, "w", encoding="utf-8") as f:
            f.write(html)
        
        # 4. 保存图片（600 DPI）
        img_save_path = os.path.join(self.output, "img", name + ".jpg")
        im.save(img_save_path, dpi=(600, 600))
        
        # 5. 生成 PP-Structure 标注
        img_file_name = os.path.join("img", name + ".jpg")
        label_info = self.generator.make_ppstructure_label(
            structure,
            contents,
            img_file_name,
        )
        f_gt.write(json.dumps(label_info, ensure_ascii=False) + "\n")
        
        # 6. 生成元数据
        f_meta.write(
            json.dumps(
                {
                    "filename": img_file_name,
                    "source": "agent_generated",
                    "domain": table.plan.domain,
                    "topic": table.plan.topic,
                    "rows": table.plan.rows,
                    "cols": table.plan.cols,
                    "simple": table.plan.simple,
                    "colored": table.plan.colored,
                    "lined": table.plan.lined,
                    "style": table.style.name,
                },
                ensure_ascii=False,
            ) + "\n")

    def close(self):
        """关闭浏览器"""
        self.generator.close()

    def _name(self, border, idx):
        """生成唯一文件名"""
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
        return f"{border}_{idx}_{suffix}"
```

**输出目录结构：**
```
output/
├── html/           # HTML 文件
│   ├── agent_simple_colored_lined_0_ABC123.html
│   └── ...
├── img/            # 渲染的图片
│   ├── agent_simple_colored_lined_0_ABC123.jpg
│   └── ...
├── gt.txt          # PP-Structure 标注（每行一个 JSON）
└── meta.jsonl      # 元数据（每行一个 JSON）
```

---

### 第十二步：运行入口 `run_agents.py`

```python
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.core_agent import CoreAgent
from agents.tools.rendering.renderer_tool import RendererTool
from agents.types import TableRequest


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--num", type=int, default=1)
    parser.add_argument("--output", type=str, default="output/agent_table")
    parser.add_argument("--domain", type=str, default="telecommunications")
    parser.add_argument("--language", type=str, default="zh")
    parser.add_argument("--min_row", type=int, default=4)
    parser.add_argument("--max_row", type=int, default=12)
    parser.add_argument("--min_col", type=int, default=3)
    parser.add_argument("--max_col", type=int, default=8)
    parser.add_argument("--brower", type=str, default="chrome")
    parser.add_argument("--brower_width", type=int, default=1920)
    parser.add_argument("--brower_height", type=int, default=2440)
    parser.add_argument("--chrome_driver_path", type=str, default=None)
    return parser.parse_args()


def find_default_chromedriver():
    """查找默认的 ChromeDriver 路径"""
    for candidate in [
            Path("chromedriver-win64/chromedriver.exe"),
            Path("../chromedriver-win64/chromedriver.exe")]:
        if candidate.exists():
            return str(candidate)
    return None


def main():
    """主函数"""
    args = parse_args()
    
    # 自动查找 ChromeDriver
    if args.brower == "chrome" and args.chrome_driver_path is None:
        args.chrome_driver_path = find_default_chromedriver()
    
    # 1. 创建请求
    request = TableRequest(
        domain=args.domain,
        language=args.language,
        min_rows=args.min_row,
        max_rows=args.max_row,
        min_cols=args.min_col,
        max_cols=args.max_col,
    )
    
    # 2. 生成表格
    core = CoreAgent()
    tables = [core.generate(request) for _ in range(args.num)]
    
    # 3. 渲染输出
    renderer = RendererTool(
        output=args.output,
        brower=args.brower,
        brower_width=args.brower_width,
        brower_height=args.brower_height,
        chrome_driver_path=args.chrome_driver_path,
    )
    try:
        renderer.render_many(tables)
    finally:
        renderer.close()
    
    print(f"generated {args.num} agent tables into {args.output}")


if __name__ == "__main__":
    main()
```

**使用方式：**
```bash
# 生成 10 个电信领域表格
python run_agents.py --num 10 --domain telecommunications --output output/my_tables

# 生成 5 个金融领域表格，指定行列范围
python run_agents.py --num 5 --domain finance --min_row 6 --max_row 10 --min_col 4 --max_col 6

# 使用自定义 ChromeDriver
python run_agents.py --num 1 --chrome_driver_path /path/to/chromedriver
```

---

## 🎯 Agent 职责总结表

| Agent | 输入 | 输出 | 职责 |
|-------|------|------|------|
| **TopicAgent** | TableRequest | TablePlan | 确定主题和表格属性 |
| **SchemaAgent** | TablePlan | TableSchema | 构建单元格布局 |
| **StyleAgent** | TablePlan | TableStyle | 生成 CSS 样式 |
| **HeaderAgent** | TableSchema + TablePlan | TableSchema | 填充表头文本 |
| **BodyAgent** | TableSchema + TablePlan | TableSchema | 填充表体数据 |
| **ValidatorAgent** | TableSchema | (bool, errors) | 验证结构合法性 |
| **FillingChecker** | TableSchema + TablePlan | FillingCheckReport / (bool, errors) | 验证内容合理性与质量评分 |
| **HtmlBuilder** | 全部 | AgentTable | 组装最终 HTML |
| **RendererTool** | AgentTable | 图片 + 标注 | 渲染和保存 |

---

## 🏗️ 设计亮点

1. **模块化设计**：每个 Agent 职责单一，易于维护和扩展
2. **可扩展性**：添加新领域只需修改主题和表头字典
3. **双重验证**：结构验证 + 内容验证确保输出质量
4. **随机性**：每次生成都不同，增加数据集多样性
5. **标注支持**：自动生成 PP-Structure 格式的标注文件
6. **批量处理**：支持一次性生成多个表格

---

## 📊 数据流图

```
┌─────────────────────────────────────────────────────────────┐
│                      TableRequest                           │
│  (domain, language, rows, cols, simple, colored, lined)     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      TopicAgent.plan()                      │
│  - 从预定义主题库随机选择                                      │
│  - 确定行列数（在指定范围内随机）                                │
│  - 确定样式属性                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                       TablePlan                             │
│  (domain, language, topic, rows, cols, simple, colored, lined)│
└─────────────────────────────────────────────────────────────┘
                            ↓
              ┌─────────────┴─────────────┐
              ↓                           ↓
┌─────────────────────────┐   ┌─────────────────────────┐
│   SchemaAgent.build()   │   │    StyleAgent.build()   │
│  - 构建单元格列表        │   │  - 生成 CSS 样式        │
│  - 分配 role 和 tag     │   │  - 根据属性组合样式      │
└─────────────────────────┘   └─────────────────────────┘
              ↓                           ↓
┌─────────────────────────┐   ┌─────────────────────────┐
│      TableSchema        │   │       TableStyle        │
│  (rows, cols, cells)    │   │  (name, table_css, ...) │
└─────────────────────────┘   └─────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│                   HeaderAgent.fill()                        │
│  - 填充 title 单元格（主题）                                  │
│  - 填充 header 单元格（领域相关标签）                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    BodyAgent.fill()                         │
│  - 根据表头关键词匹配填充数据                                  │
│  - 区域名、数字、百分比、人名、状态                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                ValidatorAgent.validate()                    │
│  ✓ 位置合法性  ✓ 边界检查  ✓ 重叠检查  ✓ 完整性检查            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              FillingChecker.evaluate()/check()              │
│  ✓ 标题匹配  ✓ 头部质量  ✓ 表体一致性  ✓ 评分/警告输出        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   HtmlBuilder.build()                       │
│  - 组装完整 HTML                                            │
│  - 生成结构标记（用于标注）                                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                       AgentTable                            │
│  (plan, schema, style, html, structure_tokens, id_count)    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   RendererTool.render_many()                │
│  - Selenium 渲染 HTML → 图片                                 │
│  - 保存 HTML、图片、标注文件                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      输出文件                                │
│  ├── html/*.html      # HTML 源文件                          │
│  ├── img/*.jpg        # 渲染的表格图片                        │
│  ├── gt.txt           # PP-Structure 标注                    │
│  └── meta.jsonl       # 元数据                               │
└─────────────────────────────────────────────────────────────┘
```
