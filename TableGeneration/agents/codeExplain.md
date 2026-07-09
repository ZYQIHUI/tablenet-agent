# TableNet-mini 多智能体生成系统代码说明

本文档说明 `TableGeneration/agents/` 下的当前实现。项目定位是 TableNet-mini 的生成侧复现：不追求论文 445K 规模，但尽量对齐论文中的可控生成、多智能体分工、8 路配置、质量检查、批量报告和标注输出。

## 1. 当前能力概览

当前代码已经具备一条可运行的数据生成闭环：

```text
TableRequest
-> CoreAgent
-> TopicAgent
-> SchemaAgent
-> StyleAgent
-> HeaderAgent
-> BodyAgent
-> ValidatorAgent
-> FillingChecker
-> HtmlBuilder
-> RendererTool
-> html / img / gt.txt / meta.jsonl / cells.jsonl / report
```

已经实现的能力：

- simple / complex 表格生成。
- colored / plain 样式控制。
- lined / unlined 样式控制。
- 8 路 balanced config 轮询生成。
- 默认启用 OpenAI-compatible LLM 语义入口，并保留规则 fallback。
- 结构验证、填充质量评分、局部重试和批量报告。
- PP-Structure 风格 `gt.txt`。
- 样本级 `meta.jsonl`。
- cell-level `cells.jsonl`。

仍然待增强的能力：

- 更丰富的 complex 结构类型。
- 更细的视觉扰动和视觉标签。
- 完整 S / C / H / V 标注体系。
- copy / delete / swap / alter 数据增强。
- Agent Tool vs LLM Direct 的结构保真度实验。
- TSR 微调和主动学习实验。

## 2. 目录结构

```text
agents/
├─ core_agent.py
├─ run_agents.py
├─ types.py
├─ codeExplain.md
├─ sub_agents/
│  ├─ planners/
│  │  ├─ topic_agent.py
│  │  ├─ schema_agent.py
│  │  └─ style_agent.py
│  ├─ fillers/
│  │  ├─ header_agent.py
│  │  └─ body_agent.py
│  └─ validators/
│     ├─ validator_agent.py
│     └─ filling_checker.py
└─ tools/
   ├─ adapters/
   │  ├─ llm_topic_client.py
   │  ├─ llm_header_client.py
   │  └─ llm_body_client.py
   └─ rendering/
      ├─ html_builder.py
      └─ renderer_tool.py
```

## 3. 核心数据结构

所有核心类型都定义在 `types.py`。

### TableRequest

`TableRequest` 是外部请求，表示用户想生成什么样的表格。

关键字段：

```text
domain      领域，默认 telecommunications
language    语言，默认 zh
min_rows    最小行数
max_rows    最大行数
min_cols    最小列数
max_cols    最大列数
simple      是否简单表格，None 表示随机
colored     是否带颜色，None 表示随机
lined       是否完整线框，None 表示随机
config_id   8 路配置 ID 或 manual
structure_type  指定 complex 结构类型，None 表示由 SchemaAgent 决定
```

### TablePlan

`TablePlan` 是 `TopicAgent` 的输出。它把随机或用户指定的约束具体化。

关键字段：

```text
domain
language
topic
rows
cols
simple
colored
lined
config_id
semantic_scenario
structure_type
```

### Cell

`Cell` 是结构生成阶段的最小单元。

关键字段：

```text
row       起始行
col       起始列
tag       th 或 td
text      单元格文本
rowspan   跨行数
colspan   跨列数
role      title / header / body
cell_id   与 HTML id 对齐的内部编号
```

### TableSchema

`TableSchema` 是表格逻辑结构。

关键字段：

```text
rows
cols
cells
header_type
has_rowspan
has_colspan
```

`header_type` 目前可能取值：

```text
simple_single_header
title_header
grouped_columns
left_headers
body_rowspan
mixed_headers
two_axis_header
summary_row_colspan
multi_level_column_header
```

### TableStyle

`TableStyle` 保存样式名称和 CSS 片段。

关键字段：

```text
name
table_css
cell_css
header_css
visual
```

`visual` 是结构化视觉属性，目前记录 `font_family / font_size / padding_mode / align / background_mode / border_weight` 等字段。

### AgentTable

`AgentTable` 是 `HtmlBuilder` 的输出，也是 `RendererTool` 的输入。

关键字段：

```text
plan
schema
style
html
structure_tokens
id_count
```

## 4. CoreAgent 主流程

`core_agent.py` 中的 `CoreAgent` 负责串联各个 Agent。

实际流程：

```text
1. TopicAgent.plan(request)
2. StyleAgent.build(plan)
3. SchemaAgent.build(plan)
4. ValidatorAgent.validate(base_schema)
5. HeaderAgent.fill(schema, plan)
6. BodyAgent.fill(schema, plan)
7. ValidatorAgent.validate(filled_schema)
8. FillingChecker.evaluate(schema, plan)
9. HtmlBuilder.build(plan, schema, style)
```

`CoreAgent` 现在有两层重试：

- `max_schema_retries`：结构验证失败，或 FillingChecker 判断标题 / 表头基础质量为 0 时，重新构建 schema。
- `max_filling_retries`：结构可用但填充质量低时，保留同一基础 schema，重新填充 header/body。

如果结构验证失败，会抛出：

```text
invalid table schema
```

如果填充质量失败，会抛出：

```text
invalid table filling
```

这些错误会被 `run_agents.py` 的批量入口分类统计。

## 5. Planner Agents

### TopicAgent

文件：

```text
sub_agents/planners/topic_agent.py
```

职责：

- 选择领域主题。
- 随机或按请求确定行列数。
- 随机或按请求确定 simple / colored / lined。
- 传递 `config_id`。
- 为规则 fallback 选择 `semantic_scenario`，驱动 topic / header / body 模板。
- 默认可调用 LLM 生成主题；缺少配置或调用失败时回退规则主题。
- 用 `used_topics` 做简单主题去重。

规则主题库目前覆盖：

```text
telecommunications
finance
general
```

### SchemaAgent

文件：

```text
sub_agents/planners/schema_agent.py
```

职责：

- 生成 `TableSchema`。
- 分配 cell 的 row / col / rowspan / colspan。
- 分配 tag 和 role。
- 分配 cell_id。
- 生成结构摘要字段。

simple 表格：

```text
第一行是 header
其余行是 body
无 rowspan / colspan
```

complex 表格目前包含：

```text
title_header       标题行 colspan
grouped_columns    分组列头
left_headers       左侧行表头
body_rowspan       表体第一列跨行
mixed_headers      标题 + 分组列头 + 左侧表头
multi_level_column_header  多级列头
two_axis_header    双轴表头，左侧两列为行表头
summary_row_colspan 汇总行，左侧标签跨列
```

注意：`_title_header()` 目前只在行列过小时作为 fallback；`multi_level_column_header` 需要至少 5 行，避免只有表头没有表体。

### StyleAgent

文件：

```text
sub_agents/planners/style_agent.py
```

职责：

- 根据 `plan.colored` 决定表头和表体背景。
- 根据 `plan.lined` 决定线型。
- 随机采样字体、字号、padding、对齐方式、背景模式和边框粗细。
- 生成 `TableStyle.name`，用于文件名前缀和 metadata。
- 生成 `TableStyle.visual`，用于 mini 版 V annotation。

当前 line style 包括：

```text
full
horizontal
vertical
header
none
light_horizontal
```

`RendererTool` 会根据 style name 推导 `line_type`。

## 6. Filler Agents

### HeaderAgent

文件：

```text
sub_agents/fillers/header_agent.py
```

职责：

- 填充 title。
- 填充 column header。
- 填充 grouped header。
- 填充 row header。
- 默认可调用 LLM 生成 headers / group_headers / row_headers；缺少配置或调用失败时回退规则模板。

默认领域模板包括：

```text
telecommunications
finance
general
```

### BodyAgent

文件：

```text
sub_agents/fillers/body_agent.py
```

职责：

- 根据列头语义填充 body。
- 支持区域、数字、百分比、负责人、状态等字段。
- 默认可调用 LLM 生成表体；缺少配置或调用失败时回退规则模板。
- 对 LLM 返回值做轻量归一化。

当前规则示例：

```text
包含 “率 / 同比 / 进度” 的列 -> 百分比
包含 “站点数 / 用户数 / 收入” 的列 -> 数字
包含 “负责人” 的列 -> 人名
包含 “状态 / 备注” 的列 -> 状态文本
```

## 7. Validators

### ValidatorAgent

文件：

```text
sub_agents/validators/validator_agent.py
```

职责：

- 构建 coverage matrix。
- 检查负坐标。
- 检查 rowspan / colspan 是否小于 1。
- 检查 span 是否越界。
- 检查单元格是否重叠。
- 检查每行是否完整覆盖。

这是结构稳定性的核心，论文中对应 structure validator / matrix representation。

### FillingChecker

文件：

```text
sub_agents/validators/filling_checker.py
```

职责：

- 对填充质量打分。
- 检查标题是否和 topic 对齐。
- 检查 header 是否为空或重复。
- 检查 body 是否符合列头预期类型。
- 输出 `FillingCheckReport`。

报告字段：

```text
ok
score
title_score
header_score
body_score
errors
warnings
column_scores
cell_scores
```

当前是规则评分版，还没有做到论文里的 LLM ranking / 人类排序相关性实验。

## 8. Rendering Tools

### HtmlBuilder

文件：

```text
tools/rendering/html_builder.py
```

职责：

- 将 `TableSchema` 和 `TableStyle` 转成完整 HTML。
- 给每个 cell 写入递增 id。
- 生成 PP-Structure 风格的 `structure_tokens`。
- 返回 `AgentTable`。

注意：HTML id 的顺序和 `cell_id` 顺序一致，这让后续 bbox 可以回连到 schema cell。

### RendererTool

文件：

```text
tools/rendering/renderer_tool.py
```

职责：

- 调用原始 `TableGeneration.GenerateTable` 的 Selenium 渲染能力。
- 保存 HTML。
- 保存 JPG。
- 输出 `gt.txt`。
- 输出 `meta.jsonl`。
- 输出 `cells.jsonl`。

输出目录结构：

```text
output_xxx/
├─ html/
│  └─ *.html
├─ img/
│  └─ *.jpg
├─ gt.txt
├─ meta.jsonl
├─ cells.jsonl
├─ report.json
└─ report.md
```

`gt.txt` 是 PP-Structure 风格标注，每行一张图。

`meta.jsonl` 是样本级 metadata，关键字段包括：

```text
filename
source
domain
language
config_id
semantic_scenario
topic
rows
cols
simple
colored
lined
style
line_type
visual
header_type
has_rowspan
has_colspan
```

`cells.jsonl` 是 cell-level 标注，每行一张图，关键字段包括：

```text
filename
config_id
semantic_scenario
visual
header_type
rows
cols
cell_count
cells
```

每个 cell 包含：

```text
cell_id
row
col
rowspan
colspan
tag
role
text
tokens
bbox
is_header
is_empty
```

当前 role 映射：

```text
title
column_header
row_header
body
```

## 9. LLM Adapter 与语义模式

文件：

```text
tools/adapters/llm_topic_client.py
tools/adapters/llm_header_client.py
tools/adapters/llm_body_client.py
```

职责：

- 提供 OpenAI-compatible API 调用。
- 支持 api_key / base_url / model / system_prompt。
- Topic / Header / Body 默认在 `semantic_mode=auto` 下启用。

语义模式由 `run_agents.py` 的 `--semantic_mode` 控制：

```text
auto  默认值，尝试 LLM，缺配置或失败时自动回退规则
llm   尝试 LLM，当前仍保留规则 fallback，避免批量生成中断
rule  强制规则生成，不调用 LLM
```

旧参数 `--use_llm_topic / --use_llm_header / --use_llm_body` 仍保留兼容，但推荐使用 `--semantic_mode`。

推荐在：

```text
TableGeneration/agents/.env
```

中配置本地密钥和模型地址。该文件不应提交。

## 10. run_agents.py 批量入口

文件：

```text
run_agents.py
```

这是当前最重要的命令行入口。

### 基础参数

```text
--num
--target_num
--max_attempts
--retry_failed
--report
--output
--domain
--language
--min_row
--max_row
--min_col
--max_col
```

### 表格属性参数

```text
--simple
--complex
--colored / --no-colored
--lined / --no-lined
--balanced_configs
--balanced_structures
```

`--simple` 和 `--complex` 互斥。

### 浏览器参数

```text
--brower
--brower_width
--brower_height
--chrome_driver_path
--semantic_mode
```

注意：参数名沿用了原项目拼写 `brower`。

### LLM 参数

```text
--use_llm_topic
--llm_topic_api_key
--llm_topic_base_url
--llm_topic_model
--llm_topic_system_prompt

--use_llm_header
--llm_header_api_key
--llm_header_base_url
--llm_header_model
--llm_header_system_prompt

--use_llm_body
--llm_body_api_key
--llm_body_base_url
--llm_body_model
--llm_body_system_prompt
```

## 11. 8 路 Balanced Config

`run_agents.py` 中固定定义了 8 路配置：

```text
simple_colored_lined
simple_colored_unlined
simple_plain_lined
simple_plain_unlined
complex_colored_lined
complex_colored_unlined
complex_plain_lined
complex_plain_unlined
```

每一项对应：

```text
config_id, simple, colored, lined
```

当传入：

```bash
python agents/run_agents.py --target_num 80 --balanced_configs
```

系统会按 8 路轮询生成，理想情况下每种配置 10 张。

如果同时传入：

```bash
python agents/run_agents.py --target_num 56 --balanced_configs --balanced_structures
```

complex 样本会在以下结构类型中轮询：

```text
grouped_columns
left_headers
body_rowspan
mixed_headers
two_axis_header
summary_row_colspan
multi_level_column_header
```

## 12. 失败重试与报告

`run_agents.py` 当前支持目标数量生成。

示例：

```powershell
python agents\run_agents.py ^
  --target_num 8 ^
  --balanced_configs ^
  --retry_failed ^
  --max_attempts 24 ^
  --report ^
  --output ..\output\retry_report_smoke ^
  --chrome_driver_path ..\chromedriver-win64\chromedriver.exe
```

行为：

- `target_num` 表示目标合格样本数。
- `max_attempts` 表示最多尝试次数。
- `retry_failed` 表示失败后继续尝试。
- `report` 表示写出报告。

如果未传 `--target_num`，目标数默认等于 `--num`，因此旧命令仍可使用。

失败分类：

```text
schema_invalid
filling_low_score
render_failed
generation_failed
```

`report.json` / `report.md` 包含：

```text
target_num
max_attempts
retry_failed
attempts
success
failed
success_rate
complete
failure_counts
config_counts
header_type_counts
span_counts
failures
```

## 13. 常用命令

进入项目代码目录：

```powershell
cd TableGeneration
```

生成 1 张规则表：

```powershell
python agents\run_agents.py --num 1 --output output\agent_table
```

强制生成 complex 表：

```powershell
python agents\run_agents.py --target_num 8 --complex --retry_failed --report --output output\complex_smoke
```

8 路均衡生成：

```powershell
python agents\run_agents.py --target_num 16 --balanced_configs --retry_failed --report --output output\balanced_smoke
```

使用根目录 ChromeDriver：

```powershell
python agents\run_agents.py --target_num 8 --balanced_configs --retry_failed --report --output ..\output\smoke --chrome_driver_path ..\chromedriver-win64\chromedriver.exe
```

默认尝试 LLM，缺配置自动回退规则：

```powershell
python agents\run_agents.py --target_num 8 --balanced_configs
```

强制规则生成：

```powershell
python agents\run_agents.py --target_num 8 --balanced_configs --semantic_mode rule
```

显式使用 LLM 语义模式：

```powershell
python agents\run_agents.py --target_num 8 --balanced_configs --semantic_mode llm
```

## 14. 测试

测试文件位于：

```text
TableGeneration/tests/
```

当前测试覆盖：

- balanced config 是否均匀轮询。
- target_num / max_attempts 逻辑。
- semantic_mode 默认 LLM 和规则强制关闭逻辑。
- semantic_scenario 和场景化表头模板。
- report 统计逻辑。
- ValidatorAgent 结构验证。
- cell-level annotation 字段。

运行测试：

```powershell
cd TableGeneration
python -m unittest discover -s tests -p "test_*.py"
```

当前期望结果：

```text
Ran 17 tests
OK
```

## 15. 与论文 TableNet 的对应关系

当前实现和论文机制的对应：

| 论文机制 | 当前实现 | 状态 |
|---|---|---|
| Core LLM 编排 | CoreAgent 编排规则/LLM Agent | 基础完成 |
| Topic LLM | TopicAgent + 可选 LLM | 基础完成 |
| Header infilling LLM | HeaderAgent + 可选 LLM | 基础完成 |
| Body infilling LLM | BodyAgent + 可选 LLM | 基础完成 |
| CSS generator | StyleAgent + structured visual metadata | 第一版完成 |
| HTML tags generator | SchemaAgent + HtmlBuilder | 基础完成 |
| Structure validator | ValidatorAgent matrix 检查 | 基础完成 |
| Fallback constructor | retry loop 粗粒度重试 | 第一版完成 |
| Selenium renderer | RendererTool | 完成 |
| 8-way generation | --balanced_configs | mini 版完成 |
| S annotation | gt.txt / structure_tokens | 部分完成 |
| C annotation | cells.jsonl | 第一版完成 |
| H annotation | html + role 字段 | 第一版完成 |
| V annotation | meta/cells 中 simple/colored/lined/line_type/visual | 第一版完成 |
| Filling checker ranking | FillingChecker 规则评分 | 基础完成 |
| augmentation | 未实现 | 待做 |
| structure fidelity experiment | 未实现 | 待做 |
| active learning TSR | 未实现 | 待做 |

## 16. 当前输出质量基线

最近一次 8 路 smoke 的预期形态：

```text
html: 8
img: 8
gt.txt: 8 行
meta.jsonl: 8 行
cells.jsonl: 8 行
report.json: 1
report.md: 1
```

cell-level 标注检查应满足：

```text
cells.jsonl 行数 == meta.jsonl 行数
每行 cell_count == len(cells)
bbox 非法数量 == 0
role 覆盖 body 和 column_header
complex 样本中应出现 title / row_header / colspan / rowspan 的一部分
```

## 17. 后续建议

短期优先级：

1. 完善 `cells.jsonl`，加入更严格的 bbox 与 HTML structure 对齐检查。
2. 增强 complex 结构分布，例如 multi-level column header、two-axis header、summary row。
3. 扩展 `StyleAgent`，加入字体、字号、padding、对齐、背景、水印和噪声。
4. 将 FillingChecker 分数真正接入 retry 策略，例如低分重填而不是整表重建。
5. 建立 Agent Tool vs LLM Direct 的 mini 版结构保真度实验。

中期目标：

```text
TableNet-mini Pilot-500
```

要求：

- 500 张生成成功。
- 8 路配置尽量均衡。
- `report.json` 记录成功率和失败类型。
- `cells.jsonl` 可用于训练/评估前处理。
- 人工抽查图像、HTML、gt、meta、cells 一致性。
