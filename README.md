# TableNet Agent

基于 TableNet 论文与原始 `TableGeneration` 代码库整理的表格生成复现项目。当前仓库的主线是：在保留原始渲染与标注能力的基础上，加入一套可选的多智能体生成工作流，让主题、结构、表头、表体、检查与渲染分层处理，方便逐步复现论文里的生成侧系统。

## 现在包含什么

- 原始表格生成器：`TableGeneration/TableGeneration/GenerateTable.py`
- 原始 HTML 结构与渲染流程：`TableGeneration/TableGeneration/Table.py`
- 多智能体生成链：`TableGeneration/agents/`
- 论文整理与复盘记录：`2026-TableNet-cn.md`、`复现过程实验记录.md`
- 论文原文与翻译版：`2026-TableNet- A Large-Scale Table Dataset with L.pdf`、`2026-TableNet- A Large-Scale Table Dataset with L_translated.pdf`

## 当前能力

- `TopicAgent` 支持规则主题和可选 LLM 入口
- `HeaderAgent` 支持表头填充与可选 LLM 入口
- `BodyAgent` 支持表体填充与可选 LLM 入口
- `ValidatorAgent` 负责结构合法性检查
- `FillingChecker` 负责填充质量评分与内容合理性检查
- `RendererTool` 复用原始生成器做渲染、裁边和 PP-Structure 风格标注输出

## 项目结构

```text
.
├─ TableGeneration/
│  ├─ TableGeneration/
│  │  ├─ GenerateTable.py
│  │  └─ Table.py
│  ├─ agents/
│  │  ├─ core_agent.py
│  │  ├─ sub_agents/
│  │  │  ├─ planners/
│  │  │  ├─ fillers/
│  │  │  └─ validators/
│  │  └─ tools/
│  │     ├─ adapters/
│  │     └─ rendering/
│  ├─ generate_data.py
│  └─ vis_gt.py
├─ 2026-TableNet-cn.md
├─ 复现过程实验记录.md
└─ README.md
```

## 环境准备

建议使用 Python 3.10+。

安装依赖：

```bash
cd TableGeneration
pip install -r requirements.txt
```

如果你要运行 Selenium 渲染，还需要准备浏览器和驱动：

- Chrome + chromedriver，或
- Firefox + geckodriver

项目里已经预留了 Windows 常见路径的自动查找逻辑。

## 快速开始

### 1. 原始生成器

生成一张基础表格：

```bash
cd TableGeneration
python generate_data.py --output output/simple_table --num=1
```

### 2. 多智能体生成器

生成一张 Agent 表格：

```bash
cd TableGeneration
python agents/run_agents.py --num 1 --output output/agent_table
```

如果要启用 LLM 入口，传入对应开关即可：

```bash
python agents/run_agents.py --num 1 --use_llm_topic --use_llm_header --use_llm_body
```

## LLM 配置

推荐把配置放在 `TableGeneration/agents/.env`。

示例：

```env
LLM_TOPIC_API_KEY=your_api_key_here
LLM_TOPIC_BASE_URL=https://your-base-url.example.com/v1
LLM_TOPIC_MODEL=your-model-name

LLM_HEADER_API_KEY=your_api_key_here
LLM_HEADER_BASE_URL=https://your-base-url.example.com/v1
LLM_HEADER_MODEL=your-model-name

LLM_BODY_API_KEY=your_api_key_here
LLM_BODY_BASE_URL=https://your-base-url.example.com/v1
LLM_BODY_MODEL=your-model-name
```

如果某一层没配好，系统会自动回退到规则生成，保证主流程可用。

## 输出结果

Agent 流程会输出：

- `html/`：表格 HTML
- `img/`：渲染后的图片
- `gt.txt`：PP-Structure 风格标注
- `meta.jsonl`：样本元信息

## 目前的复现进度

当前已完成的是生成主线的可运行闭环：

`CoreAgent -> Topic -> Schema -> Style -> Header -> Body -> Validator -> FillingChecker -> HtmlBuilder -> RendererTool`

也就是说，我们已经把论文里“生成工作流”的骨架跑通了，并且保留了原始生成器作为渲染与标注底座。后续还会继续补增强、重试、批量 8 路生成、主动学习和 TSR 微调等论文后半段内容。

## 参考

- [TableNet 中文整理](./2026-TableNet-cn.md)
- [复现过程实验记录](./复现过程实验记录.md)
- [原始 TableGeneration 说明](./TableGeneration/README.md)

