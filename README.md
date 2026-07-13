# TableNet-mini 复现项目

本仓库是在原始 `TableGeneration` 表格渲染代码上，加入 TableNet-mini 多智能体生成链后的复现项目。当前已经跑通“数据生成、自动校验、标注、SFT 导出、Qwen2-VL QLoRA 训练、批量评价”的最小闭环。

> 本项目采用资源受限的 TableNet-mini 路线，目标是验证论文方法并逐步扩大实验规模；当前结果不代表已经复现论文的 445K 完整数据集和全部实验。

## 当前进度

更新日期：2026-07-13

| 模块 | 状态 | 当前结果 |
|---|---|---|
| 多智能体表格生成 | 已完成 | 支持规则、LLM 和模板模式，覆盖 8 类视觉配置与 7 类复杂结构 |
| 校验、重试与标注 | 已完成 | 输出样本元数据、cell bbox/role、结构与失败报告 |
| 300 样本 QLoRA smoke | 已完成 | 跑通数据转换、训练、Adapter 回载和同样本推理 |
| 30 样本批量对比 | 已完成 | 结构分 0.711 -> 0.896，文字准确率 0.581 -> 0.673 |
| 1K v2 训练与评价 | 已完成 | 100 样本文字准确率 84.17%，结构分 0.938 |
| 5K 数据阶段 | 数据已完成 | 已生成 5000 张并转换为 4000/500/500 的 SFT 划分，模型训练和正式评价待完成 |
| 自动化测试 | 通过 | 本地 `pytest -q`：持续随多智能体重构扩展 |

当前尚未完成 TEDS 正式指标、真实数据泛化、论文完整 S/C/H/V 标注、5+4 数据增强、两级记忆和 445K 全规模实验。详细事实、服务器产物和限制以[复现过程实验记录](./复现过程实验记录.md)为准。

## 快速验证

```powershell
cd TableGeneration
pip install -r requirements.txt
pytest -q
python agents\run_agents.py --num 1 --semantic_mode rule --output output\smoke
```

生成图片需要 Chrome 和版本匹配的 ChromeDriver，具体配置见下文。

成功标准：命令退出码为 0，`output\smoke\img` 中有 JPG，且同目录存在 `gt.txt`、`meta.jsonl` 和 `cells.jsonl`。

## 1. 入口选择

当前有两个主要入口：

| 入口 | 用途 | 推荐场景 |
|---|---|---|
| `TableGeneration/agents/run_agents.py` | 多智能体生成链 | 默认使用，生成带 `meta.jsonl`、`cells.jsonl`、报告的 TableNet-mini 数据 |
| `TableGeneration/generate_data.py` | 原始生成器 | 对照原始代码、只生成基础 PP-Structure 风格数据 |

进入代码目录：

```powershell
cd TableGeneration
```

后续命令默认都在 `TableGeneration/` 目录下执行。

## 2. 必要启用条件

### 2.1 安装依赖

```powershell
pip install -r requirements.txt
```

建议使用 Python 3.10+。

推荐使用独立虚拟环境。在 Windows PowerShell 中：

```powershell
cd "E:\SchoolContents\2026-TableNet- A Large-Scale Table Dataset with L\TableGeneration"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest -q
```

在 Linux / PAI-DSW 中：

```bash
cd /mnt/workspace/tablenet/tablenet-agent/TableGeneration
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest -q
```

`requirements.txt` 只包含数据生成端依赖。Qwen2-VL 推理和 QLoRA 训练还需要 PyTorch、Transformers、PEFT、bitsandbytes、Qwen-VL 相关依赖及 LLaMA-Factory，建议在 GPU 服务器按 `PAI-DSW部署步骤.md` 单独配置。

### 2.2 启用浏览器渲染

生成图片需要 Chrome 和 ChromeDriver。

ChromeDriver 可放在任一位置：

```text
仓库根目录/chromedriver-win64/chromedriver.exe
TableGeneration/chromedriver-win64/chromedriver.exe
系统 PATH 中的 chromedriver.exe
```

如果没有放在默认位置，运行时显式传入：

```powershell
python agents\run_agents.py --num 1 --chrome_driver_path ..\chromedriver-win64\chromedriver.exe
```

Linux / PAI-DSW 环境中，如果 apt 源里的 `chromium` / `chromium-driver` 不可用，或 `chromedriver --version` 提示需要安装 chromium snap，可以改用 Google Chrome 和 Chrome for Testing 的 chromedriver：

```bash
cd /mnt/systemDisk

wget -O google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get update
sudo apt-get install -y ./google-chrome.deb unzip fonts-noto-cjk fonts-wqy-zenhei

CHROME_MAJOR=$(google-chrome --version | grep -oP '[0-9]+' | head -1)
DRIVER_VERSION=$(wget -qO- https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR})
wget -O chromedriver.zip https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip
unzip -o chromedriver.zip
sudo mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver
sudo chmod +x /usr/local/bin/chromedriver
```

验证：

```bash
google-chrome --version
/usr/local/bin/chromedriver --version
which -a chromedriver
```

如果系统仍默认命中 `/usr/bin/chromedriver` 的 snap 占位命令，让 `/usr/local/bin` 优先：

```bash
export PATH=/usr/local/bin:$PATH
hash -r
chromedriver --version
grep -q 'export PATH=/usr/local/bin:$PATH' ~/.bashrc || echo 'export PATH=/usr/local/bin:$PATH' >> ~/.bashrc
```

在 DSW 批量生成时也可以直接传入：

```bash
python agents/run_agents.py --num 1 --chrome_driver_path /usr/local/bin/chromedriver
```

参数名沿用了原始代码拼写：`--brower chrome`，不是 `--browser`。

## 3. 启用规则生成

如果只想使用本地规则模板，不调用 LLM，使用：

```powershell
python agents\run_agents.py --num 1 --output output\agent_rule --semantic_mode rule
```

这是最稳定的 smoke test。成功后会输出：

```text
output/agent_rule/
├─ html/
├─ img/
├─ gt.txt
├─ meta.jsonl
└─ cells.jsonl
```

## 4. 启用 LLM 语义生成

语义 Agent 与具体推理后端解耦。入口支持四种模式：

| 模式 | 参数 | 说明 |
|---|---|---|
| 规则流 | `--backend_mode rule` | 不调用模型，使用规则、模板和本地语料 |
| 远程 API | `--backend_mode api` | 使用下方 OpenAI-compatible API 配置 |
| 本地模型 | `--backend_mode local` | 惰性加载本地 Qwen2-VL 权重，Topic/Header/Body 共用一个模型实例 |
| 混合模式 | `--backend_mode hybrid` | 配置本地模型路径时优先使用本地模型，否则使用 API，并允许显式规则回退 |

`--semantic_mode auto|llm|rule` 暂时保留用于兼容旧命令；新实验应使用含义更明确的 `--backend_mode`。

本地 Qwen 示例：

```powershell
python agents\run_agents.py `
  --backend_mode local `
  --local_model_path D:\models\Qwen2-VL-2B-Instruct `
  --local_model_device auto `
  --output output\agent_local
```

本地模式仅在首次模型调用时导入并加载 `torch`、`transformers` 和 Qwen2-VL 权重；规则模式和普通单元测试不要求安装这些训练/推理依赖。模型调用失败后的规则结果会显式记录为 `fallback`，而不是计为模型成功。

论文的普通候选与四类增强可通过快捷参数启用：

```powershell
python agents\run_agents.py `
  --backend_mode rule `
  --paper_candidate_mode `
  --output output\paper_candidates
```

`--paper_candidate_mode` 等价于 `--candidate_count 5 --augmentation_count 4`。四个增强候选分别执行 span-aware 的 `copy`、`delete`、`swap` 和 `alter`；每次变换后都会重新运行结构验证和三维质量门控。

每次运行还会写出 `trace.jsonl`，其中包含：

- `request_id` 和候选 ID；
- 普通候选与增强候选的父子关系；
- Validator、Checker 和论文三维分数；
- API、本地模型或规则的实际来源及回退原因；
- 修复动作、目标 cell/column、淘汰原因和最终选择依据。

需要跨运行保持论文两级记忆时，指定共享记忆文件和会话 ID：

```powershell
python agents\run_agents.py `
  --backend_mode rule `
  --memory_path output\memory.json `
  --session_id telecom-generation `
  --output output\memory_run
```

Inner Memory 持久化 topic、schema signature、被拒候选和失败原因，用于跨进程去重；Outer Memory 按 `session_id` 保存请求偏好和对话记录。JSON 使用进程级锁、临时文件和原子替换写入，避免并发丢更新或异常中断留下半写文件。单机多 worker 可以共享同一路径；跨机器并发仍应改用数据库存储。

当 SchemaAgent 在结构重建预算内持续失败时，系统最后调用 Fallback Constructor。Fallback 会构造可通过 coverage 验证的单位网格，并把旧 cell 到新 cell 的映射、原始错误和保留内容写入 trace，而不是静默随机换表。

自然语言请求可通过 `--request_text` 交给受约束 Core Planner：

```powershell
python agents\run_agents.py `
  --backend_mode local `
  --local_model_path D:\models\Qwen2-VL-2B-Instruct `
  --request_text "生成复杂的中文基站维护表，6 到 10 行" `
  --output output\planned_tables
```

Core Planner 只能提出 domain、language、行列范围、simple/colored/lined 和 structure type 等白名单字段；确定性 Orchestrator 负责类型、范围、预算和动作校验。API/本地模型模式下，FillingChecker 还会调用匿名 Semantic Evaluator 评价 topic relevance 和 semantic consistency；结构正确性始终由确定性 Validator 判断。

每张表的执行预算可独立限制：

```powershell
python agents\run_agents.py `
  --backend_mode hybrid `
  --max_model_calls 40 `
  --max_elapsed_seconds 180 `
  --max_schema_retries 3 `
  --max_filling_retries 2 `
  --max_candidates 20
```

预算耗尽会写入 `BUDGET_EXHAUSTED` trace 并明确终止。API 的 token usage、本地 Qwen 的输入/输出 token 数和 hybrid 的每次后端尝试都会保留在 Agent 事件中。

多智能体部分的消融和统计工具位于 `TableGeneration/experiments/multi_agent/`：

```powershell
python experiments\multi_agent\run_ablation.py --samples_per_config 20 --output experiments\multi_agent\results\ablation
python experiments\multi_agent\summarize_traces.py --trace ..\output\paper_trace_smoke\trace.jsonl --output experiments\multi_agent\results\trace_summary
python experiments\multi_agent\checker_human_correlation.py --ratings ratings.csv --output experiments\multi_agent\results\human_correlation.json
```

消融固定比较单候选、5 个普通候选和完整 5+4。人工相关性脚本只计算真实评分 CSV，不生成或替代人工标签。

多智能体链包含三个可选 LLM 入口：

| Agent | 作用 |
|---|---|
| `TopicAgent` | 生成主题、领域、语义场景 |
| `HeaderAgent` | 生成标题、列头、分组表头、行表头 |
| `BodyAgent` | 生成表体内容 |

语义模式由 `--semantic_mode` 控制：

| 模式 | 行为 |
|---|---|
| `auto` | 默认值，尝试调用 LLM；缺配置或调用失败时回退规则 |
| `llm` | 显式启用 LLM 语义入口；当前仍保留规则 fallback，避免批量中断 |
| `rule` | 强制规则生成，不调用 LLM |

推荐把密钥放到：

```text
TableGeneration/agents/.env
```

可从根目录示例复制：

```powershell
copy ..\.env.example agents\.env
```

示例配置：

```env
LLM_TOPIC_API_KEY=your_api_key_here
LLM_TOPIC_BASE_URL=https://your-base-url.example.com/v1
LLM_TOPIC_MODEL=your-model-name
LLM_TOPIC_SYSTEM_PROMPT=You are a domain-aware table topic generation agent. Return valid JSON only.

LLM_HEADER_API_KEY=your_api_key_here
LLM_HEADER_BASE_URL=https://your-base-url.example.com/v1
LLM_HEADER_MODEL=your-model-name
LLM_HEADER_SYSTEM_PROMPT=You are a domain-aware table header generation agent. Return valid JSON only.

LLM_BODY_API_KEY=your_api_key_here
LLM_BODY_BASE_URL=https://your-base-url.example.com/v1
LLM_BODY_MODEL=your-model-name
LLM_BODY_SYSTEM_PROMPT=You are a domain-aware table body generation agent. Return valid JSON only.
```

启用 LLM：

```powershell
python agents\run_agents.py --num 1 --output output\agent_llm --semantic_mode llm
```

如果只想兼容旧开关，也可以使用：

```powershell
python agents\run_agents.py --num 1 --use_llm_topic --use_llm_header --use_llm_body
```

但推荐优先使用 `--semantic_mode`。

## 5. 启用表格形态控制

### 5.1 简单表格

```powershell
python agents\run_agents.py --target_num 8 --simple --semantic_mode rule --output output\simple_smoke
```

### 5.2 复杂表格

```powershell
python agents\run_agents.py --target_num 8 --complex --retry_failed --report --semantic_mode rule --output output\complex_smoke
```

### 5.3 彩色 / 无色

```powershell
python agents\run_agents.py --target_num 8 --colored --output output\colored_smoke
python agents\run_agents.py --target_num 8 --no-colored --output output\plain_smoke
```

### 5.4 有线框 / 无线框

```powershell
python agents\run_agents.py --target_num 8 --lined --output output\lined_smoke
python agents\run_agents.py --target_num 8 --no-lined --output output\unlined_smoke
```

### 5.5 行列范围

```powershell
python agents\run_agents.py --target_num 8 --min_row 6 --max_row 12 --min_col 4 --max_col 8 --output output\size_smoke
```

## 6. 启用 8 路均衡生成

`--balanced_configs` 会轮询 8 种配置：

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

生成 16 张，理论上每种配置 2 张：

```powershell
python agents\run_agents.py --target_num 16 --balanced_configs --retry_failed --report --semantic_mode rule --output output\balanced_smoke
```

如果还想让 complex 结构类型轮询，增加 `--balanced_structures`：

```powershell
python agents\run_agents.py --target_num 56 --balanced_configs --balanced_structures --retry_failed --report --semantic_mode rule --output output\balanced_structures_smoke
```

## 7. 启用失败重试和报告

推荐批量生成时同时启用：

```powershell
python agents\run_agents.py --target_num 80 --balanced_configs --retry_failed --max_attempts 240 --report --semantic_mode rule --output output\pilot_80
```

参数含义：

| 参数 | 含义 |
|---|---|
| `--target_num` | 目标合格样本数 |
| `--max_attempts` | 最大尝试次数 |
| `--retry_failed` | 单次失败后继续尝试 |
| `--report` | 写出 `report.json` 和 `report.md` |

失败类型会统计为：

```text
schema_invalid
filling_low_score
render_failed
generation_failed
```

### 7.1 Agent 入口完整参数

以下参数以当前 `python agents\run_agents.py --help` 为准：

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--num` | `1` | 未设置 `--target_num` 时的生成数量 |
| `--target_num` | 空 | 要得到的合格样本数；批量生成推荐使用 |
| `--max_attempts` | 自动 | 最大尝试次数；启用重试时默认是目标数的 3 倍 |
| `--retry_failed` | 关闭 | 单个样本失败后继续生成，直到达标或达到最大尝试数 |
| `--report` | 关闭 | 生成 `report.json` 和 `report.md` |
| `--output` | `output/agent_table` | 输出目录；相对于当前工作目录解析 |
| `--domain` | `telecommunications` | 语义领域 |
| `--language` | `zh` | 内容语言 |
| `--min_row` / `--max_row` | `4` / `12` | 表格行数范围 |
| `--min_col` / `--max_col` | `3` / `8` | 表格列数范围 |
| `--simple` / `--complex` | 随机 | 二选一，强制简单或复杂结构 |
| `--colored` / `--no-colored` | 随机 | 强制彩色或无色样式 |
| `--lined` / `--no-lined` | 随机 | 强制有线框或无线框 |
| `--balanced_configs` | 关闭 | 轮询 8 种简单/复杂、彩色/无色、线框/无线框组合 |
| `--balanced_structures` | 关闭 | 对复杂样本轮询 7 种结构类型 |
| `--brower` | `chrome` | 浏览器类型；参数名是代码中的历史拼写 |
| `--brower_width` / `--brower_height` | `1920` / `2440` | 浏览器渲染画布尺寸 |
| `--chrome_driver_path` | 自动查找 | ChromeDriver 可执行文件路径 |
| `--semantic_mode` | `auto` | `rule`、`auto` 或 `llm`，详见第 4 节 |

LLM 的 Topic、Header、Body 三组参数均支持 `--use_llm_*`、`--llm_*_api_key`、`--llm_*_base_url`、`--llm_*_model` 和 `--llm_*_system_prompt`。密钥推荐写入 `agents/.env`，不要直接写入命令历史、README 或 Git。

随时用下面的命令核对当前代码支持的参数：

```powershell
python agents\run_agents.py --help
```

## 8. 启用原始生成器

如果只想使用原始 `TableGeneration` 生成器：

```powershell
python generate_data.py --output output\simple_table --num=1
```

指定 ChromeDriver：

```powershell
python generate_data.py --output output\simple_table --num=1 --chrome_driver_path ..\chromedriver-win64\chromedriver.exe
```

生成彩色表格：

```powershell
python generate_data.py --output output\color_table --num=8 --color_prob=0.3
```

校验标注可视化：

```powershell
python vis_gt.py --image_dir output\simple_table\img --gt_path output\simple_table\gt.txt
```

## 9. 输出说明

Agent 生成链输出：

| 文件 / 目录 | 内容 |
|---|---|
| `html/` | 每张表格的 HTML |
| `img/` | Selenium 渲染后的 JPG |
| `gt.txt` | PP-Structure 风格结构标注 |
| `meta.jsonl` | 样本级 metadata |
| `cells.jsonl` | cell-level 标注，包含 bbox、rowspan、colspan、role 等 |
| `report.json` | 批量统计，需启用 `--report` |
| `report.md` | 批量统计 Markdown，需启用 `--report` |

### 9.1 生成后验收

先检查报告中的目标数、成功数、成功率和失败分类：

```powershell
Get-Content ..\output\balanced_rule\report.md
Get-Content ..\output\balanced_rule\report.json
```

再运行数据审计。审计会检查图片、HTML、GT、metadata 和 cell 标注之间的一致性：

```powershell
python experiments\dataset_audit\run_dataset_audit.py `
  --input ..\output\balanced_rule `
  --output_dir ..\output\balanced_rule `
  --fail_on_error
```

审计完成后查看：

```powershell
Get-Content ..\output\balanced_rule\audit.md
```

用于自动化或 CI 时保留 `--fail_on_error`，发现严重错误会返回非零退出码；人工探索时可以去掉该参数。

### 9.2 可视化检查 GT

```powershell
python vis_gt.py `
  --image_dir ..\output\balanced_rule\img `
  --gt_path ..\output\balanced_rule\gt.txt
```

至少人工抽查简单、复杂、rowspan、colspan、无线框和中文长文本样本，确认 bbox 没有明显错位。

## 10. 常见启用组合

本地最小验证：

```powershell
python agents\run_agents.py --num 1 --semantic_mode rule --output output\smoke
```

本地 8 路规则数据：

```powershell
python agents\run_agents.py --target_num 16 --balanced_configs --retry_failed --report --semantic_mode rule --output output\balanced_rule
```

LLM 语义 smoke：

```powershell
python agents\run_agents.py --num 1 --semantic_mode llm --output output\llm_smoke
```

训练前小数据集：

```powershell
python agents\run_agents.py --target_num 300 --balanced_configs --balanced_structures --retry_failed --max_attempts 900 --report --semantic_mode rule --output ..\output\tablenet_mini_300
```

生成一批可复用的 LLM 语义模板：

```powershell
python experiments\generate_templates.py --count 50 --output output\semantic_templates.json
```

该命令会尝试调用 LLM；缺少配置或调用失败时会写出内置 fallback 模板。当前本地 `run_agents.py` 尚未公开 `--templates` 参数，因此模板文件的批量消费流程不要仅凭 `experiments/run_parallel.py` 直接启动；该脚本保留了服务器实验路径和参数，使用前需先与当前入口对齐。

将生成结果导出为 Qwen2-VL/LLaMA-Factory 使用的 SFT 数据：

```powershell
python experiments\export_qwen_sft\export_qwen_sft.py `
  --input ..\output\tablenet_mini_300 `
  --output_dir ..\output\tablenet_mini_300_sft `
  --val_ratio 0.1 `
  --test_ratio 0.1 `
  --target html
```

导出参数说明：

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--input` | 必填 | 包含 `meta.jsonl`、`cells.jsonl`、`img/` 和可选 `gt.txt` 的生成目录 |
| `--output_dir` | 必填 | 写出训练数据的目录 |
| `--val_ratio` / `--test_ratio` | `0.1` / `0.1` | 验证集与测试集比例 |
| `--seed` | `42` | 固定数据划分，复现实验时不要随意改变 |
| `--absolute_images` | 关闭 | 写入绝对图片路径，服务器训练时通常需要启用 |
| `--target` | `html` | 可选 `html`、`cells` 或 `json` |
| `--prompt` | 内置提示词 | 覆盖用户提示词；对比实验必须保持一致 |

导出器只会写出 `train.json`、`val.json`、`test.json` 和 `manifest.json`，不会自动修改 LLaMA-Factory。先检查文件和样本数：

```powershell
Get-ChildItem ..\output\tablenet_mini_300_sft
Get-Content ..\output\tablenet_mini_300_sft\manifest.json
```

随后需要把这些 JSON 放到 LLaMA-Factory 可访问的位置，并在其 `data/dataset_info.json` 中手动注册 train/val 数据集。注册名必须与训练 YAML 的 `dataset`、`eval_dataset` 完全一致。

### 10.1 结构保真度实验

这是轻量级离线实验，不需要加载 Qwen 模型：

```powershell
python experiments\structure_fidelity\run_structure_fidelity.py `
  --samples_per_case 7 `
  --output experiments\structure_fidelity\results
```

输出包括 `summary.md`、`summary.csv` 和 `samples.jsonl`。其中 `llm_direct` 是确定性离线模拟基线，不能表述为真实在线 LLM 结果。

### 10.2 QLoRA 训练

训练在已安装 LLaMA-Factory 且具备 NVIDIA GPU 的 Linux/DSW 环境进行。先根据实际目录修改 YAML 中的 `model_name_or_path`、`dataset_dir` 和 `output_dir`，然后先跑 20 样本预检：

```bash
llamafactory-cli train /mnt/workspace/tablenet/tablenet-agent/TableGeneration/experiments/qwen_qlora/preflight_20.yaml
```

确认没有 OOM、NaN 或数据解析错误，并且输出目录生成 Adapter 文件后，再运行 300 样本 smoke：

```bash
llamafactory-cli train /mnt/workspace/tablenet/tablenet-agent/TableGeneration/experiments/qwen_qlora/smoke_300.yaml
```

不要直接照搬 YAML 中的绝对路径到另一台机器。LLaMA-Factory 的 `dataset_info.json` 还需要注册导出的数据集，并正确配置 ShareGPT 的 role/content tags；完整示例见 `PAI-DSW部署步骤.md`。

### 10.3 基线与 Adapter 批量评价

推理脚本额外依赖 `torch`、`transformers`、`peft` 和 Qwen2-VL 运行环境。基础模型评价：

```bash
python experiments/qwen_baseline/run_qwen_baseline.py \
  --model /mnt/workspace/models/Qwen2-VL-2B-Instruct \
  --data_json /mnt/workspace/tablenet/data/tablenet_smoke_300_sft/test.json \
  --meta_jsonl /mnt/workspace/tablenet/data/tablenet_dsw_smoke_300/meta.jsonl \
  --output /mnt/workspace/tablenet/results/baseline/qwen2-vl-2b/test_30
```

加载 Adapter 对同一个 test split 评价：

```bash
python experiments/qwen_baseline/run_qwen_baseline.py \
  --model /mnt/workspace/models/Qwen2-VL-2B-Instruct \
  --adapter /mnt/workspace/tablenet/results/qwen2-vl-2b/qlora/smoke_300 \
  --data_json /mnt/workspace/tablenet/data/tablenet_smoke_300_sft/test.json \
  --meta_jsonl /mnt/workspace/tablenet/data/tablenet_dsw_smoke_300/meta.jsonl \
  --output /mnt/workspace/tablenet/results/qwen2-vl-2b/adapter/test_30
```

快速检查单个样本可增加 `--sample_index 0`，限制批量样本数可使用 `--max_samples 10`。正式对比必须固定 test split、prompt、`--max_new_tokens`、模型版本和清洗/评价代码。

## 11. 常见问题

### ChromeDriver 无法启动

依次检查 Chrome 与 Driver 的主版本是否一致、路径是否正确，以及 Linux 中是否命中了 snap 占位命令：

```powershell
& "..\chromedriver-win64\chromedriver.exe" --version
```

```bash
google-chrome --version
chromedriver --version
which -a chromedriver
```

### 生成数量少于目标数

使用 `--target_num`、`--retry_failed` 和足够大的 `--max_attempts`，然后检查 `report.json` 中的 `failure_counts`。`--num` 表示计划尝试数，不保证失败后补足；批量数据应优先使用 `--target_num`。

### LLM 模式没有生成 LLM 内容

`auto` 和 `llm` 都保留规则 fallback。检查 `agents/.env` 的 API key、base URL、model 和 system prompt 是否完整，并检查终端中的调用错误。需要完全离线和确定性执行时使用 `--semantic_mode rule`。

### Qwen 推理提示缺少模块

出现 `ModuleNotFoundError: peft`、`torch` 或 `transformers` 时，说明当前环境只有数据生成依赖。请切换到 GPU 推理/训练环境，不要把模型依赖强行加入轻量数据生成环境后就假定 CUDA 配置正确。

### LLaMA-Factory 报 `KeyError: 'from'`

检查 `dataset_info.json` 是否为 ShareGPT 数据配置了 `role_tag`、`content_tag`、`user_tag` 和 `assistant_tag`。同时确认图片字段和 `<image>` 占位符符合 `qwen2_vl` 模板要求。

### Windows 路径与服务器路径不一致

本地生成可以使用相对路径；服务器训练推荐导出时使用 `--absolute_images`。移动数据后需要重新导出或更新 JSON 中的图片路径，不能只移动 `img/` 目录。

QLoRA 预检和训练配置位于 `TableGeneration/experiments/qwen_qlora/`。模型依赖、服务器目录和批量评价流程见 `PAI-DSW部署步骤.md` 与 `复现过程实验记录.md`。

## 12. 参考文档

- [TableNet 中文整理](./2026-TableNet-cn.md)
- [复现过程实验记录](./复现过程实验记录.md)
- [Colab 部署步骤](./Colab部署步骤.md)
- [PAI-DSW 部署步骤](./PAI-DSW部署步骤.md)
- [原始 TableGeneration 说明](./TableGeneration/README.md)
- [Agent 代码说明](./TableGeneration/agents/codeExplain.md)
- [30 样本批量评价报告](./output/batch_eval_analysis.md)
