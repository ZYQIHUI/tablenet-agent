# TableNet Agent 启用手册

本仓库是在原始 `TableGeneration` 表格渲染代码上，加入 TableNet-mini 多智能体生成链后的复现项目。README 的重点是说明各个能力如何启用；论文整理、实验记录和云端训练流程见文末参考。

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

## 11. 参考文档

- [TableNet 中文整理](./2026-TableNet-cn.md)
- [复现过程实验记录](./复现过程实验记录.md)
- [Colab 部署步骤](./Colab部署步骤.md)
- [PAI-DSW 部署步骤](./PAI-DSW部署步骤.md)
- [原始 TableGeneration 说明](./TableGeneration/README.md)
- [Agent 代码说明](./TableGeneration/agents/codeExplain.md)
