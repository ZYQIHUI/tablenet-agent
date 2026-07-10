# PAI-DSW 部署与 QLoRA 微调入门

目标是在阿里云 PAI-DSW 上完成一条可验证的 TableNet-mini 实验链路：

```text
多智能体生成表格数据
        -> 检查图片与标注
        -> 转换为 Qwen2-VL 训练格式
        -> 测试基础模型推理
        -> 进行 QLoRA 微调
        -> 加载 LoRA adapter 推理
        -> 比较微调前后效果
```

基础模型 `Qwen/Qwen2-VL-2B-Instruct` 已经完成预训练；本实验只用自己的表格数据训练少量 LoRA 参数。训练仍属于深度学习，但 LLaMA-Factory 已封装模型加载、损失计算、反向传播和 checkpoint 保存，因此不需要手写完整的 PyTorch 训练循环。

## 0. 开始前先理解四件事

### 0.1 三种数据规模的用途不同

| 阶段 | 建议数量 | 目的 | 能否证明模型有效 |
|---|---:|---|---|
| 生成 smoke | 16 | 检查浏览器、字体、图片和标注链路 | 不能 |
| 训练 smoke | 300 | 检查数据转换、模型下载和 QLoRA 链路 | 不能单独证明 |
| 正式实验 | 1K -> 5K -> 10K | 比较微调前后指标，研究数据规模影响 | 需要独立测试集 |

不要一开始就生成 10K。错误的数据生成器会快速制造大量错误标注，既浪费费用，也会误导模型。

### 0.2 QLoRA 会下载基础模型

配置中的：

```yaml
model_name_or_path: Qwen/Qwen2-VL-2B-Instruct
```

会触发 Hugging Face 或指定模型源下载模型。不是“完全不下载”，而是由程序自动下载并缓存。训练结束保存的主要是 LoRA adapter，后续推理仍需要：

```text
Qwen2-VL-2B 基础模型 + TableNet LoRA adapter
```

### 0.3 训练成功不等于效果提升

出现 loss、生成 adapter 文件，只能说明训练程序跑通。必须在训练时未见过的测试集上比较基础模型和微调模型，才能判断微调是否有效。

### 0.4 DSW 有计费和数据丢失风险

- GPU 实例运行时持续计费，实验结束后要停止实例。
- 删除实例通常会释放系统盘；重要数据必须保存到 OSS、NAS 或本地。
- 模型缓存、数据集、checkpoint 会快速占用磁盘。
- 不要把 Access Token、`.env` 或密钥提交到 Git。

## 1. 创建 DSW 实例

在阿里云控制台进入：

```text
人工智能平台 PAI
-> 工作空间
-> 模型开发与训练
-> 交互式建模（DSW）
-> 新建实例
```

建议配置：

| 配置项 | 起步建议 | 说明 |
|---|---|---|
| GPU | A10 24GB 或同级 | 适合 Qwen2-VL-2B 4-bit QLoRA smoke |
| CPU / 内存 | 8 vCPU / 30 GiB 左右 | 数据生成和预处理够用 |
| 镜像 | PyTorch 2.x、CUDA 12.x、Python 3.10/3.11 | 优先选择 ModelScope 或 PAI 官方 GPU 镜像 |
| 系统盘 | 建议 200 GiB | 100 GiB 容易被模型缓存和数据占满 |
| 竞价实例 | smoke 阶段先关闭 | 避免训练中途被抢占 |
| 公网 | 开启公网网关 | Git、pip 和模型下载需要网络 |
| 持久化存储 | 正式实验挂 OSS/NAS | 系统盘不适合长期归档 |

资源规格和镜像名称会随地域、库存和时间变化，不要机械照抄某个实例型号。核心条件是：NVIDIA GPU 可用、CUDA 与 PyTorch 兼容、磁盘充足、可以访问依赖和模型源。

## 2. 环境预检

打开 DSW Terminal，先执行：

```bash
nvidia-smi
python --version
python -m pip --version
df -h
pwd
```

成功标准：

- `nvidia-smi` 能看到 NVIDIA GPU，且没有驱动错误。
- Python 和 pip 可以正常运行。
- 确认哪个目录有足够空间。
- 记住当前实例的实际工作路径，不要先假设一定是 `/mnt/systemdisk`。

记录原始深度学习环境，便于依赖安装出错后排查：

```bash
python - <<'PY'
import sys
print("python:", sys.version)
try:
    import torch
    print("torch:", torch.__version__)
    print("cuda build:", torch.version.cuda)
    print("cuda available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("gpu:", torch.cuda.get_device_name(0))
except Exception as exc:
    print("torch check failed:", repr(exc))
PY
```

如果 `torch.cuda.is_available()` 为 `False`，先解决镜像、驱动或 CUDA 问题，不要继续安装训练框架。

## 3. 只在这里配置一次路径

以下路径只是示例。先根据 `df -h` 和 `pwd` 修改 `WORK_ROOT`：

```bash
export WORK_ROOT=/mnt/systemdisk/tablenet
export PROJECT_DIR="$WORK_ROOT/2026-TableNet"
export DATA_DIR="$WORK_ROOT/data"
export MODEL_DIR="$WORK_ROOT/models"
export RESULT_DIR="$WORK_ROOT/results"
export LLAMA_FACTORY_DIR="$WORK_ROOT/LLaMA-Factory"
export HF_HOME="$MODEL_DIR/huggingface"
```

创建目录并检查：

```bash
mkdir -p "$WORK_ROOT" "$DATA_DIR" "$MODEL_DIR" "$RESULT_DIR"
printf 'WORK_ROOT=%s\nPROJECT_DIR=%s\nDATA_DIR=%s\nMODEL_DIR=%s\nRESULT_DIR=%s\n' \
  "$WORK_ROOT" "$PROJECT_DIR" "$DATA_DIR" "$MODEL_DIR" "$RESULT_DIR"
```

注意：`export` 默认只在当前 Terminal 会话有效。重新打开 Terminal 后需要再次执行。建议把上述变量保存为自己的 `env.sh`，每次进入实例后执行：

```bash
source /你的实际路径/env.sh
```

本文后续命令都使用变量，不依赖固定的 `/mnt/systemdisk`。路径中出现空格时必须保留双引号。

## 4. 获取项目代码

### 4.1 Git 方式

```bash
cd "$WORK_ROOT"
git clone <你的仓库地址> "$PROJECT_DIR"
cd "$PROJECT_DIR"
git status
```

私有仓库建议使用 SSH key 或安全的凭据管理。不要把 Token 直接写进命令历史、脚本或仓库文件。

### 4.2 ZIP 方式

没有远程仓库时，可以上传 ZIP 后解压。解压前先查看 ZIP 顶层结构，避免形成 `2026-TableNet/2026-TableNet/` 双层目录：

```bash
unzip -l /上传位置/2026-TableNet.zip | head -30
mkdir -p "$PROJECT_DIR"
unzip /上传位置/2026-TableNet.zip -d "$PROJECT_DIR"
find "$PROJECT_DIR" -maxdepth 2 -type f | head
```

如果 ZIP 内已经包含名为 `2026-TableNet` 的顶层目录，应解压到 `"$WORK_ROOT"`，而不是再次解压到 `"$PROJECT_DIR"`。

上传前不要打包 `.git/`、`__pycache__/`、本地 `output/`、虚拟环境和大模型文件。

## 5. 安装浏览器、Driver 和中文字体

数据生成需要用浏览器把 HTML 渲染成图片。不同 DSW 镜像的软件源不同，先尝试系统 Chromium：

```bash
sudo apt-get update
sudo apt-get install -y \
  chromium \
  chromium-driver \
  fonts-noto-cjk \
  fonts-wqy-zenhei \
  unzip \
  zip \
  tree
```

某些 Ubuntu 镜像使用以下包名：

```bash
sudo apt-get install -y chromium-browser chromium-chromedriver
```

检查：

```bash
which chromium || which chromium-browser || which google-chrome
which -a chromedriver
chromedriver --version
fc-list | grep -i "Noto Sans CJK" | head
```

### 5.1 遇到 snap 占位 Driver

如果 `chromedriver --version` 提示安装 Chromium snap，当前 `/usr/bin/chromedriver` 只是占位命令。DSW 容器里通常不适合使用 snap，可以改用 Google Chrome 和 Chrome for Testing：

```bash
cd "$WORK_ROOT"
wget -O google-chrome.deb \
  https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get install -y ./google-chrome.deb unzip fonts-noto-cjk fonts-wqy-zenhei

CHROME_MAJOR=$(google-chrome --version | grep -oP '[0-9]+' | head -1)
DRIVER_VERSION=$(wget -qO- \
  "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR}")
wget -O chromedriver.zip \
  "https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip"
unzip -o chromedriver.zip
sudo mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver
sudo chmod +x /usr/local/bin/chromedriver
```

验证主版本一致：

```bash
google-chrome --version
/usr/local/bin/chromedriver --version
export CHROMEDRIVER=/usr/local/bin/chromedriver
```

不建议删除 `/usr/bin/chromedriver`。显式使用 `CHROMEDRIVER` 更容易排查问题。

## 6. 安装项目依赖并运行测试

项目的 `requirements.txt` 不包含 PyTorch，因此不会主动安装另一套 PyTorch。仍建议先确认文件内容，再安装：

```bash
cd "$PROJECT_DIR/TableGeneration"
sed -n '1,120p' requirements.txt
python -m pip install -r requirements.txt \
  -i https://pypi.tuna.tsinghua.edu.cn/simple
```

检查核心依赖：

```bash
python - <<'PY'
import cv2
import numpy
import PIL
import selenium
print("selenium:", selenium.__version__)
print("opencv:", cv2.__version__)
print("numpy:", numpy.__version__)
print("Pillow: ok")
PY
```

运行单元测试：

```bash
cd "$PROJECT_DIR/TableGeneration"
python -m unittest discover -s tests -p "test_*.py"
```

成功标准：测试全部通过。若出现 Windows 路径、缺少模块或版本错误，应先修复，不要直接跳过测试。

## 7. 生成 16 张数据 smoke

先设置输出目录：

```bash
export SMOKE16_DIR="$DATA_DIR/tablenet_smoke_16"
```

如果已确认 Driver 路径：

```bash
cd "$PROJECT_DIR/TableGeneration"

python agents/run_agents.py \
  --target_num 16 \
  --balanced_configs \
  --balanced_structures \
  --semantic_mode rule \
  --retry_failed \
  --max_attempts 48 \
  --report \
  --output "$SMOKE16_DIR" \
  --min_row 6 \
  --max_row 8 \
  --min_col 4 \
  --max_col 6 \
  --chrome_driver_path "$CHROMEDRIVER"
```

如果没有设置 `CHROMEDRIVER`，可以先省略最后一项，让项目尝试自动查找；失败时再回到第 5 节处理。

这里使用 `--semantic_mode rule`，目的是先验证本地规则生成链路，不产生大模型 API 调用和额外费用。

## 8. 验收 16 张输出

先检查数量：

```bash
find "$SMOKE16_DIR/img" -name "*.jpg" | wc -l
find "$SMOKE16_DIR/html" -name "*.html" | wc -l
wc -l "$SMOKE16_DIR/gt.txt"
wc -l "$SMOKE16_DIR/meta.jsonl"
wc -l "$SMOKE16_DIR/cells.jsonl"
cat "$SMOKE16_DIR/report.md"
```

最低成功标准：

```text
图片 16 张
HTML 16 个
gt.txt、meta.jsonl、cells.jsonl 各 16 行
report 中 complete 为 true
```

数量正确还不够。必须人工抽查至少 4 张，覆盖简单/复杂、有线/无线、彩色/无色：

- 图片是否为空白、截断或乱码。
- 图片中的行列数是否与 HTML 一致。
- 合并单元格的 `rowspan`、`colspan` 是否正确。
- 中文字体是否正常。
- 标注文件中的图片路径是否存在。

图片乱码时执行：

```bash
sudo apt-get install -y fonts-noto-cjk fonts-wqy-zenhei
fc-cache -fv
```

然后删除本次失败输出目录或换一个新输出目录重新生成。不要把失败样本混入训练集。

## 9. 生成 300 张训练 smoke

16 张通过后再生成 300 张：

```bash
export SMOKE300_DIR="$DATA_DIR/tablenet_smoke_300"

cd "$PROJECT_DIR/TableGeneration"
python agents/run_agents.py \
  --target_num 300 \
  --balanced_configs \
  --balanced_structures \
  --semantic_mode rule \
  --retry_failed \
  --max_attempts 900 \
  --report \
  --output "$SMOKE300_DIR" \
  --min_row 6 \
  --max_row 8 \
  --min_col 4 \
  --max_col 6 \
  --chrome_driver_path "$CHROMEDRIVER"
```

使用与第 8 节相同的方法检查数量和样本质量：

```bash
cat "$SMOKE300_DIR/report.md"
du -sh "$SMOKE300_DIR"
```

300 张仍然主要用于训练链路 smoke，不应据此宣称模型已经获得稳定提升。

## 10. 使用项目自带工具转换 SFT 数据

仓库已经提供并测试了：

```text
TableGeneration/experiments/export_qwen_sft/export_qwen_sft.py
```

不需要在 DSW 上临时手写另一套转换脚本。执行：

```bash
export SFT_DIR="$DATA_DIR/tablenet_smoke_300_sft"

cd "$PROJECT_DIR/TableGeneration"
python experiments/export_qwen_sft/export_qwen_sft.py \
  --input "$SMOKE300_DIR" \
  --output_dir "$SFT_DIR" \
  --val_ratio 0.1 \
  --test_ratio 0.1 \
  --seed 20260709 \
  --absolute_images \
  --target html
```

输出应包含：

```text
train.json
val.json
test.json
manifest.json
```

检查转换结果：

```bash
cat "$SFT_DIR/manifest.json"

python - <<'PY'
import json
import os
from pathlib import Path

sft_dir = Path(os.environ["SFT_DIR"])
samples = json.loads((sft_dir / "train.json").read_text(encoding="utf-8"))
assert samples, "train.json 为空"
sample = samples[0]
image = Path(sample["images"][0])
answer = sample["messages"][1]["content"]
print("train samples:", len(samples))
print("image:", image)
print("image exists:", image.exists())
print("answer chars:", len(answer))
print("answer preview:", answer[:200])
assert image.exists(), f"图片不存在: {image}"
assert "<image>" in sample["messages"][0]["content"]
assert "<table" in answer.lower(), "答案不像 HTML table"
PY
```

成功标准：训练、验证、测试数量合理；图片真实存在；用户消息含 `<image>`；assistant 答案包含完整表格 HTML。

注意：随机拆分适合 smoke，但正式论文实验应尽量按模板、结构类型或生成种子分组拆分，避免高度相似的表格同时进入训练集和测试集，造成指标虚高。真实表格测试集应与合成训练集分开保存。

## 11. 安装并固定 LLaMA-Factory 环境

不要直接假定最新版永远兼容。先记录当前环境：

```bash
python -m pip freeze > "$RESULT_DIR/pip-freeze-before-llamafactory.txt"
```

安装：

```bash
cd "$WORK_ROOT"
git clone --depth 1 https://github.com/hiyouga/LLaMA-Factory.git "$LLAMA_FACTORY_DIR"
cd "$LLAMA_FACTORY_DIR"
git rev-parse HEAD | tee "$RESULT_DIR/llamafactory-commit.txt"

python -m pip install -e ".[torch,metrics]" \
  -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip install qwen-vl-utils \
  -i https://pypi.tuna.tsinghua.edu.cn/simple
```

检查：

```bash
llamafactory-cli version
python -m pip freeze > "$RESULT_DIR/pip-freeze-after-llamafactory.txt"

python - <<'PY'
import torch
import transformers
import peft
print("torch:", torch.__version__)
print("transformers:", transformers.__version__)
print("peft:", peft.__version__)
print("cuda available:", torch.cuda.is_available())
PY
```

如果安装后 CUDA 从可用变成不可用，或 PyTorch/CUDA 版本发生意外变化，应停止并检查依赖，不要继续训练。

LLaMA-Factory 更新较快。教程中的 YAML 参数若提示未知，应先查看当前 checkout 对应的官方示例和 `llamafactory-cli train --help`，不要盲目混用不同版本文档。

## 12. 注册数据集

把导出的三个 JSON 复制到 LLaMA-Factory 数据目录：

```bash
cp "$SFT_DIR/train.json" "$LLAMA_FACTORY_DIR/data/tablenet_train.json"
cp "$SFT_DIR/val.json" "$LLAMA_FACTORY_DIR/data/tablenet_val.json"
cp "$SFT_DIR/test.json" "$LLAMA_FACTORY_DIR/data/tablenet_test.json"
```

注册数据集：

```bash
cd "$LLAMA_FACTORY_DIR"

python - <<'PY'
import json
from pathlib import Path

path = Path("data/dataset_info.json")
info = json.loads(path.read_text(encoding="utf-8"))

for name, file_name in {
    "tablenet_train": "tablenet_train.json",
    "tablenet_val": "tablenet_val.json",
    "tablenet_test": "tablenet_test.json",
}.items():
    info[name] = {
        "file_name": file_name,
        "formatting": "sharegpt",
        "columns": {
            "messages": "messages",
            "images": "images"
        }
    }

path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
print("registered tablenet_train, tablenet_val, tablenet_test")
PY
```

检查注册项：

```bash
grep -n 'tablenet_' data/dataset_info.json
```

## 13. 准备基础模型

### 13.1 自动下载

YAML 使用：

```yaml
model_name_or_path: Qwen/Qwen2-VL-2B-Instruct
```

首次推理或训练时会自动下载到 `HF_HOME`。确保公网和磁盘可用。

### 13.2 国内网络不稳定时预下载

可以通过 ModelScope 下载到明确目录：

```bash
python -m pip install modelscope \
  -i https://pypi.tuna.tsinghua.edu.cn/simple

modelscope download \
  --model Qwen/Qwen2-VL-2B-Instruct \
  --local_dir "$MODEL_DIR/Qwen2-VL-2B-Instruct"
```

然后把所有 YAML 中的模型路径改为：

```yaml
model_name_or_path: /你的实际路径/models/Qwen2-VL-2B-Instruct
```

`MODEL_DIR` 是 shell 变量，YAML 不一定会自动展开 `$MODEL_DIR`。为初学者避免歧义，建议在 YAML 中填写执行 `echo "$MODEL_DIR/Qwen2-VL-2B-Instruct"` 得到的真实绝对路径。

下载后检查：

```bash
du -sh "$MODEL_DIR"
df -h
```

## 14. 先做一次基础模型推理

在微调之前，应先确认基础模型能读取图片并生成结果。这样训练失败时，能区分是模型环境问题还是 LoRA 配置问题。

从 `test.json` 取第一张测试图片路径：

```bash
export TEST_IMAGE=$(python - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["LLAMA_FACTORY_DIR"]) / "data/tablenet_test.json"
rows = json.loads(path.read_text(encoding="utf-8"))
if not rows:
    raise SystemExit("tablenet_test.json 为空")
print(rows[0]["images"][0])
PY
)
printf 'TEST_IMAGE=%s\n' "$TEST_IMAGE"
test -f "$TEST_IMAGE" && echo "test image exists"
```

在 `"$LLAMA_FACTORY_DIR"` 创建 `infer_tablenet_baseline.yaml`：

```yaml
model_name_or_path: Qwen/Qwen2-VL-2B-Instruct
template: qwen2_vl
infer_backend: huggingface
trust_remote_code: true
```

如果基础模型已经预下载，应把 `model_name_or_path` 改为第 13.2 节的真实本地路径。

先查看当前版本支持的推理入口：

```bash
cd "$LLAMA_FACTORY_DIR"
llamafactory-cli --help
```

若帮助中提供 `webchat`，运行：

```bash
llamafactory-cli webchat infer_tablenet_baseline.yaml
```

通过 DSW 显示的 Web 地址打开页面，上传 `TEST_IMAGE`，输入固定提示词：

```text
请识别图片中的表格结构和文本，并输出完整 HTML table。只输出 HTML，不要解释，不要 Markdown 代码块。
```

如果当前版本只提供 `chat` 或 WebUI，应使用对应入口，但模型、模板、图片和提示词必须保持一致。LLaMA-Factory 的界面和命令会随版本变化，因此先看当前 checkout 的 `--help`，不要照搬其他版本的启动命令。

保存以下信息到 `RESULT_DIR/baseline/`：

```text
测试图片路径
提示词
基础模型原始输出
模型和依赖版本
```

成功标准不是 HTML 一定正确，而是：模型能加载、GPU 推理正常、图片能被读取、输出不是空字符串。基础输出将作为微调后的对照。

不要在未完成基础推理时直接进入训练。

## 15. 配置 QLoRA 训练 smoke

在 `"$LLAMA_FACTORY_DIR"` 下创建 `train_tablenet_qwen2vl_qlora.yaml`。下面是 A10 24GB 的保守起点：

```yaml
### model
model_name_or_path: Qwen/Qwen2-VL-2B-Instruct
trust_remote_code: true

### method
stage: sft
do_train: true
finetuning_type: lora
lora_target: all
quantization_bit: 4

### dataset
dataset: tablenet_train
eval_dataset: tablenet_val
template: qwen2_vl
cutoff_len: 4096
max_samples: 300
overwrite_cache: true
preprocessing_num_workers: 2

### output
output_dir: saves/qwen2vl-2b-tablenet/qlora/smoke_300
logging_steps: 5
save_steps: 20
plot_loss: true
overwrite_output_dir: true

### train
per_device_train_batch_size: 1
gradient_accumulation_steps: 8
learning_rate: 1.0e-4
num_train_epochs: 1.0
lr_scheduler_type: cosine
warmup_ratio: 0.03
fp16: true

### eval
per_device_eval_batch_size: 1
eval_strategy: steps
eval_steps: 20
```

参数含义：

- `quantization_bit: 4`：以 4-bit 加载冻结的基础模型。
- `finetuning_type: lora`：只训练 LoRA 小矩阵。
- `lora_target: all`：在多个线性层加入 LoRA，适配能力较强，显存也会增加。
- `cutoff_len: 4096`：文本 token 上限；HTML 超长可能被静默截断。
- `batch_size: 1` 与梯度累计 8 次：有效批大小约为 8。
- `eval_strategy: steps`：训练中定期使用验证集，但测试集绝不能参与训练调参。

如果当前 Transformers/LLaMA-Factory 版本不识别 `eval_strategy`，查看该版本示例是否使用 `evaluation_strategy`。两者不要同时写。

先用 300 张配置跑链路。若希望更快定位环境问题，可临时把 `max_samples` 改为 `20`，但这只能证明程序可运行。

## 16. 启动并观察训练

```bash
cd "$LLAMA_FACTORY_DIR"
llamafactory-cli train train_tablenet_qwen2vl_qlora.yaml 2>&1 | \
  tee "$RESULT_DIR/train-smoke-300.log"
```

重点观察：

- 是否正确加载 Qwen2-VL-2B，而不是纯文本模型。
- 是否读到 `tablenet_train` 和图片。
- 可训练参数占比是否符合 LoRA，而不是全参数训练。
- 是否出现 CUDA OOM、NaN loss 或图片路径不存在。
- 训练和验证 loss 是否有输出。
- adapter checkpoint 是否生成。

训练后检查：

```bash
find saves/qwen2vl-2b-tablenet/qlora/smoke_300 -maxdepth 2 -type f
```

通常应看到：

```text
adapter_config.json
adapter_model.safetensors
trainer_state.json
训练参数和 loss 曲线文件
```

### 16.1 OOM 处理顺序

1. 保留 `quantization_bit: 4`。
2. 降低图片分辨率相关设置，具体参数以当前 LLaMA-Factory Qwen2-VL 示例为准。
3. 把 `cutoff_len` 从 4096 降到 2048，但先确认不会截断大量 HTML。
4. 保持 batch size 为 1，提高梯度累计不能降低单个样本的峰值显存。
5. 仍然 OOM 时换更大显存 GPU。

`max_samples` 只减少训练时长，通常不能解决单个样本导致的峰值显存 OOM。

## 17. 加载 adapter 做微调后推理

训练完成后，在 `"$LLAMA_FACTORY_DIR"` 创建 `infer_tablenet_qlora.yaml`：

```yaml
model_name_or_path: Qwen/Qwen2-VL-2B-Instruct
adapter_name_or_path: saves/qwen2vl-2b-tablenet/qlora/smoke_300
template: qwen2_vl
finetuning_type: lora
infer_backend: huggingface
trust_remote_code: true
```

如果基础模型已经预下载，同样要修改 `model_name_or_path`。启动带 adapter 的推理：

```bash
cd "$LLAMA_FACTORY_DIR"
llamafactory-cli webchat infer_tablenet_qlora.yaml
```

如果当前版本使用其他推理入口，按第 14 节的 `--help` 结果调整。然后用第 14 节完全相同的测试图片、提示词和生成参数再次推理：

```text
基础模型：Qwen2-VL-2B-Instruct
Adapter：saves/qwen2vl-2b-tablenet/qlora/smoke_300
模板：qwen2_vl
```

保存到 `RESULT_DIR/finetuned/`，并检查：

- adapter 是否成功加载，而不是仍在使用纯基础模型。
- 输出是否只包含 HTML，是否出现 Markdown 代码块或解释文字。
- `<table>`、`<tr>`、`<td>`、`rowspan`、`colspan` 是否闭合且合理。
- 输出是否因 `max_new_tokens` 太小而被截断。

同一张图片必须保留三份内容：

```text
标准 HTML
基础模型预测 HTML
微调模型预测 HTML
```

肉眼看一张样本只能用于排查，不能代替正式评估。

## 18. 正式评估设计

至少比较两组：

```text
Baseline：原始 Qwen2-VL-2B-Instruct
QLoRA：基础模型 + TableNet adapter
```

两组必须使用同一测试集、同一提示词、同一图片预处理和同一生成参数。建议输出 `predictions.jsonl`：

```json
{
  "filename": "img/xxx.jpg",
  "config_id": "complex_colored_lined",
  "header_type": "grouped_columns",
  "target_html": "<table>...</table>",
  "pred_html": "<table>...</table>",
  "full_teds": 0.0,
  "structure_teds": 0.0
}
```

建议指标：

- Full TEDS：结构和文本综合相似度。
- Structure-only TEDS：去掉单元格文本后比较结构。
- HTML 有效率：输出能否被正常解析。
- 完整输出率：是否含闭合表格且未被截断。
- 分组结果：Simple / Complex、Colored / Colorless、Lined / Lineless。

测试集优先级：

```text
独立真实表格测试集 > 不同模板的合成测试集 > 随机拆分的同生成器测试集
```

仅在同生成器随机测试集上提升，不能充分证明真实场景泛化能力。

## 19. 扩展到 1K、5K、10K

只有满足以下条件才扩大数据规模：

- 16 张数据生成 smoke 完整通过。
- 300 张 QLoRA smoke 能训练、保存和加载 adapter。
- 已经跑通基础模型与微调模型的同集对比。
- 生成数据经过抽样审计，没有明显系统性标注错误。
- 数据和结果已有持久化备份。

建议：

| 阶段 | 数量 | 用途 |
|---|---:|---|
| V0 | 1K | 检查训练稳定性、截断率和初步指标 |
| V1 | 5K | 正式对照实验和结构分组分析 |
| V2 | 10K | 在前述结果证明有效后扩展 |

生成命令只需调整变量和规模，例如：

```bash
export DATASET_DIR="$DATA_DIR/tablenet_v0_1k"

cd "$PROJECT_DIR/TableGeneration"
python agents/run_agents.py \
  --target_num 1000 \
  --balanced_configs \
  --balanced_structures \
  --semantic_mode rule \
  --retry_failed \
  --max_attempts 3000 \
  --report \
  --output "$DATASET_DIR" \
  --min_row 6 \
  --max_row 10 \
  --min_col 4 \
  --max_col 7 \
  --chrome_driver_path "$CHROMEDRIVER"
```

5K 和 10K 不建议只放系统盘。正式实验还应固定随机种子、代码 commit、依赖版本、训练 YAML 和数据 manifest，保证结果可复现。

## 20. 保存结果与停止实例

至少保存：

```text
项目代码 commit
数据集 manifest 和审计报告
训练、验证、测试拆分文件
训练 YAML
LLaMA-Factory commit
pip freeze
训练日志
LoRA adapter
推理结果和评估报告
```

打包 adapter 示例：

```bash
mkdir -p "$RESULT_DIR"
cp "$LLAMA_FACTORY_DIR/train_tablenet_qwen2vl_qlora.yaml" "$RESULT_DIR/"

tar -czf "$RESULT_DIR/qwen2vl-tablenet-qlora-smoke-300.tar.gz" \
  -C "$LLAMA_FACTORY_DIR/saves/qwen2vl-2b-tablenet/qlora" \
  smoke_300

ls -lh "$RESULT_DIR"
```

将结果复制到 OSS/NAS 或下载到本地后，再停止 DSW 实例。停止前确认：

```bash
df -h
du -sh "$DATA_DIR" "$MODEL_DIR" "$RESULT_DIR"
```

停止实例不等于删除实例。是否继续收取系统盘或其他存储费用，以阿里云控制台当时显示的计费规则为准。

## 21. 常见问题速查

### GPU 不可用

先看 `nvidia-smi` 和 `torch.cuda.is_available()`。不要通过反复安装随机版本 PyTorch 掩盖驱动或镜像问题。

### pip 安装后环境损坏

比较安装前后的 `pip-freeze`，确认 PyTorch、CUDA 相关包是否被替换。必要时重新创建干净实例，比在混乱环境里继续叠加依赖更可靠。

### Hugging Face 下载失败

检查公网、DNS 和磁盘；国内环境可以使用 ModelScope 预下载，然后在 YAML 中填写本地绝对路径。

### Chromium 或 Driver 失败

确认浏览器与 Driver 主版本一致，并显式传入 `--chrome_driver_path`。出现 snap 提示时按第 5.1 节处理。

### 中文乱码

安装中文字体、执行 `fc-cache -fv` 后重新生成。旧图片不会因为安装字体自动修复。

### 数据转换后样本数量为 0

检查 `meta.jsonl`、`cells.jsonl`、`gt.txt` 的 `filename` 是否一致，图片是否存在，以及生成任务是否完整结束。

### HTML 被截断

统计训练答案 token 长度，再决定是否增大 `cutoff_len`。增大长度会提高显存和训练时间；不要只凭字符数估计 token 数。

### loss 下降但输出仍然很差

可能是训练数据太少、标签格式不一致、模板泄漏、输出截断或合成数据与真实数据差距过大。先检查样本和评估设计，不要立刻扩大训练轮数。

### 忘记停止实例

设置日程提醒。每次实验结束执行：保存结果、复制到持久化存储、停止实例、确认控制台状态。

## 22. 推荐执行清单

第一阶段，数据链路：

```text
[ ] GPU、Python、PyTorch、磁盘检查通过
[ ] 路径变量按自己的实例设置完成
[ ] Chrome、Driver、中文字体正常
[ ] 项目单元测试通过
[ ] 16 张数据数量检查通过
[ ] 人工抽查至少 4 张图片和 HTML
```

第二阶段，训练链路：

```text
[ ] 300 张数据生成并审计
[ ] 使用项目自带脚本导出 train/val/test
[ ] 随机检查一条 SFT 样本
[ ] LLaMA-Factory 版本和依赖已记录
[ ] 基础模型推理结果已保存
[ ] QLoRA 能生成 adapter
[ ] adapter 能成功加载并推理
```

第三阶段，正式实验：

```text
[ ] 基础模型与 QLoRA 使用完全相同的测试设置
[ ] 计算 Full TEDS 和 Structure-only TEDS
[ ] 按表格类型输出分组报告
[ ] 使用独立真实测试集验证泛化
[ ] 结果、日志、adapter 和环境信息已备份
[ ] 确认 DSW 实例已停止
```

## 23. 参考资料

- 阿里云 DSW 快速入门：<https://help.aliyun.com/zh/pai/product-overview/dsw-quickstart>
- 阿里云创建和管理 DSW 实例：<https://help.aliyun.com/zh/pai/create-and-manage-dsw-instances>
- 阿里云 DSW 常见问题：<https://help.aliyun.com/zh/pai/faq-about-dsw>
- Qwen2-VL 模型：<https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct>
- Qwen2-VL 官方仓库：<https://github.com/QwenLM/Qwen2-VL>
- LLaMA-Factory 官方仓库：<https://github.com/hiyouga/LLaMA-Factory>

外部工具和云平台会更新。实际执行时，以所安装版本的官方文档、仓库示例和 DSW 控制台实时信息为准，并记录本次实验使用的具体版本。
