# Colab 部署步骤

本文档目标是把当前项目变成一条清晰的云端训练链路：

```text
本地 TableNet-mini 生成器
-> 生成图片、HTML、gt、meta、cells
-> 打包上传 Google Drive
-> Colab 挂载数据集
-> Qwen2-VL-2B LoRA / QLoRA 微调
-> 保存 adapter、日志和预测结果
-> 回到本地做 TEDS / 结构指标评估
```

当前本地仓库已经能生成训练数据，但还没有专门的 TSR 微调脚本。Colab 第一版建议使用 LLaMA-Factory 跑 Qwen2-VL-2B 的 SFT LoRA smoke test，先验证数据格式、显存、loss 和输出链路。

## 1. 实验定位

论文里用于 TSR 微调的核心模型是 `Qwen2-VL-2B`，任务是：

```text
输入：表格图片
输出：表格 HTML
```

论文设置大致是：

| 项目 | 论文设置 | 我们的 Colab 起步设置 |
|---|---|---|
| 模型 | Qwen2-VL-2B | Qwen/Qwen2-VL-2B-Instruct |
| 训练方式 | 全参数训练 | LoRA / QLoRA |
| 数据量 | 约 48K | 先 100-300 smoke，再 1K / 5K |
| 硬件 | 2 x RTX 4090 | Colab T4 / L4 / A100 |
| batch size | 1 | 1 |
| epoch | 2 | smoke 1 epoch 或少量 step |
| 指标 | TEDS | 先 loss + 样例输出，后接 TEDS |

不要一开始追论文的 0.877 TEDS。我们的第一目标是：

```text
数据能读进去，训练能跑起来，显存不炸，模型能输出 HTML。
```

## 2. 本地生成 TableNet-mini 数据集

在本地仓库根目录打开 PowerShell：

```powershell
conda activate tablenet
cd "E:\SchoolContents\2026-TableNet- A Large-Scale Table Dataset with L\TableGeneration"
```

先生成一个 300 张的 smoke 数据集：

```powershell
python agents\run_agents.py `
  --target_num 300 `
  --balanced_configs `
  --balanced_structures `
  --semantic_mode rule `
  --retry_failed `
  --max_attempts 900 `
  --report `
  --output ..\output\tablenet_mini_colab_smoke `
  --min_row 6 `
  --max_row 8 `
  --min_col 4 `
  --max_col 6 `
  --chrome_driver_path ..\chromedriver-win64\chromedriver.exe
```

成功后应看到：

```text
output/tablenet_mini_colab_smoke/
├─ html/
├─ img/
├─ gt.txt
├─ meta.jsonl
├─ cells.jsonl
├─ report.json
└─ report.md
```

检查文件数量：

```powershell
cd ..
(Get-ChildItem output\tablenet_mini_colab_smoke\img -Filter *.jpg).Count
(Get-ChildItem output\tablenet_mini_colab_smoke\html -Filter *.html).Count
(Get-Content output\tablenet_mini_colab_smoke\meta.jsonl).Count
(Get-Content output\tablenet_mini_colab_smoke\cells.jsonl).Count
```

打包数据集：

```powershell
Compress-Archive `
  -Path output\tablenet_mini_colab_smoke `
  -DestinationPath output\tablenet_mini_colab_smoke.zip `
  -Force
```

然后把 `output\tablenet_mini_colab_smoke.zip` 上传到 Google Drive，例如：

```text
MyDrive/TableNet/tablenet_mini_colab_smoke.zip
```

## 3. Colab 启动设置

在 Colab 里新建 notebook。

菜单选择：

```text
Runtime -> Change runtime type -> GPU
```

建议优先级：

```text
A100 最好
L4 可以
T4 可以 smoke，但建议 QLoRA + 小图 + 小 batch
CPU 不建议训练
```

第一个 cell 检查 GPU：

```python
!nvidia-smi
```

挂载 Google Drive：

```python
from google.colab import drive
drive.mount("/content/drive")
```

设置路径：

```python
from pathlib import Path

DRIVE_ROOT = Path("/content/drive/MyDrive/TableNet")
ZIP_PATH = DRIVE_ROOT / "tablenet_mini_colab_smoke.zip"
DATA_ROOT = Path("/content/tablenet_mini_colab_smoke")
WORK_ROOT = Path("/content/work")

DRIVE_ROOT.mkdir(parents=True, exist_ok=True)
WORK_ROOT.mkdir(parents=True, exist_ok=True)

print(ZIP_PATH)
```

解压数据集：

```python
!rm -rf /content/tablenet_mini_colab_smoke
!unzip -q "{ZIP_PATH}" -d /content
!find /content/tablenet_mini_colab_smoke -maxdepth 2 -type f | head
```

如果 zip 解压后多了一层目录，手动确认：

```python
!ls -lah /content
!ls -lah /content/tablenet_mini_colab_smoke
```

## 4. Colab 数据完整性检查

```python
from pathlib import Path

root = Path("/content/tablenet_mini_colab_smoke")
img_count = len(list((root / "img").glob("*.jpg")))
html_count = len(list((root / "html").glob("*.html")))
meta_count = sum(1 for _ in open(root / "meta.jsonl", encoding="utf-8"))
cells_count = sum(1 for _ in open(root / "cells.jsonl", encoding="utf-8"))

print({
    "img": img_count,
    "html": html_count,
    "meta": meta_count,
    "cells": cells_count,
})
```

四个数量应基本一致。若不一致，先不要训练。

快速看一张图片：

```python
from IPython.display import Image, display
sample_img = next((root / "img").glob("*.jpg"))
display(Image(filename=str(sample_img), width=600))
```

## 5. 安装训练工具

推荐第一版使用 LLaMA-Factory，因为它已经支持多模态 SFT、LoRA、QLoRA 和 Qwen2-VL 模板。

```python
%cd /content
!rm -rf LLaMA-Factory
!git clone --depth 1 https://github.com/hiyouga/LLaMA-Factory.git
%cd /content/LLaMA-Factory
!pip install -e ".[torch,metrics]" -q
!pip install qwen-vl-utils -q
```

检查安装：

```python
!llamafactory-cli version
```

如果 Colab 提示需要重启 runtime，重启后重新执行挂载 Drive、设置路径、进入 `/content/LLaMA-Factory`。

## 6. 转换为多模态 SFT 数据格式

LLaMA-Factory 的多模态样本可以使用 `messages + images` 格式。我们把每张表格转换成：

```json
{
  "messages": [
    {
      "role": "user",
      "content": "<image>请识别图片中的表格结构，并输出完整 HTML table。只输出 HTML，不要解释。"
    },
    {
      "role": "assistant",
      "content": "<html>...</html>"
    }
  ],
  "images": ["/content/tablenet_mini_colab_smoke/img/xxx.jpg"]
}
```

在 Colab 执行：

```python
import json
import random
from pathlib import Path

root = Path("/content/tablenet_mini_colab_smoke")
out_dir = Path("/content/LLaMA-Factory/data")
train_path = out_dir / "tablenet_mini_train.json"
val_path = out_dir / "tablenet_mini_val.json"

prompt = (
    "<image>请识别图片中的表格结构，并输出完整 HTML table。"
    "只输出 HTML，不要解释，不要 Markdown 代码块。"
)

samples = []
with open(root / "meta.jsonl", encoding="utf-8") as f:
    for line in f:
        meta = json.loads(line)
        image_rel = meta["filename"]
        image_path = root / image_rel
        html_path = root / "html" / (Path(image_rel).stem + ".html")
        if not image_path.exists() or not html_path.exists():
            continue
        html = html_path.read_text(encoding="utf-8").strip()
        samples.append({
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": html},
            ],
            "images": [str(image_path)],
        })

random.seed(20260709)
random.shuffle(samples)

split = max(1, int(len(samples) * 0.9))
train_samples = samples[:split]
val_samples = samples[split:]

train_path.write_text(json.dumps(train_samples, ensure_ascii=False, indent=2), encoding="utf-8")
val_path.write_text(json.dumps(val_samples, ensure_ascii=False, indent=2), encoding="utf-8")

print({
    "total": len(samples),
    "train": len(train_samples),
    "val": len(val_samples),
    "train_path": str(train_path),
    "val_path": str(val_path),
})
```

注册数据集到 LLaMA-Factory：

```python
import json
from pathlib import Path

info_path = Path("/content/LLaMA-Factory/data/dataset_info.json")
info = json.loads(info_path.read_text(encoding="utf-8"))

info["tablenet_mini_train"] = {
    "file_name": "tablenet_mini_train.json",
    "formatting": "sharegpt",
    "columns": {
        "messages": "messages",
        "images": "images"
    }
}

info["tablenet_mini_val"] = {
    "file_name": "tablenet_mini_val.json",
    "formatting": "sharegpt",
    "columns": {
        "messages": "messages",
        "images": "images"
    }
}

info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
print("registered tablenet_mini_train and tablenet_mini_val")
```

## 7. 写入 Qwen2-VL-2B QLoRA 训练配置

T4 / L4 推荐先用 4-bit QLoRA。A100 可以去掉 `quantization_bit: 4`，改为普通 LoRA。

```python
from pathlib import Path

yaml_text = r"""
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
dataset: tablenet_mini_train
eval_dataset: tablenet_mini_val
template: qwen2_vl
cutoff_len: 4096
max_samples: 300
overwrite_cache: true
preprocessing_num_workers: 2

### output
output_dir: saves/qwen2vl-2b-tablenet-mini/lora/smoke
logging_steps: 5
save_steps: 50
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
val_size: 0.0
per_device_eval_batch_size: 1
eval_strategy: "no"
"""

config_path = Path("/content/LLaMA-Factory/train_tablenet_qwen2vl_lora.yaml")
config_path.write_text(yaml_text.strip() + "\n", encoding="utf-8")
print(config_path)
```

说明：

- `quantization_bit: 4` 是为了降低 Colab 显存压力。
- `cutoff_len: 4096` 可能不够容纳特别复杂的 HTML，smoke 阶段先用它控制显存。
- 如果出现 answer 被截断，后面再提高到 `8192`，但显存压力会变大。
- 如果 GPU 是 A100，可以尝试把 `fp16: true` 改成 `bf16: true`。

## 8. 开始 smoke 训练

```python
%cd /content/LLaMA-Factory
!llamafactory-cli train train_tablenet_qwen2vl_lora.yaml
```

训练中重点看：

```text
1. 是否成功加载 Qwen/Qwen2-VL-2B-Instruct
2. 是否成功读取 tablenet_mini_train
3. 是否出现 CUDA out of memory
4. loss 是否正常打印
5. saves/qwen2vl-2b-tablenet-mini/lora/smoke 是否生成 adapter 文件
```

如果 OOM：

1. 确认正在使用 GPU runtime。
2. 把 `max_samples` 改成 `50`。
3. 把 `cutoff_len` 改成 `2048`。
4. 保留 `quantization_bit: 4`。
5. 如果仍然 OOM，换 L4 / A100 runtime。

## 9. 保存训练结果到 Google Drive

Colab runtime 会丢失本地文件，所以训练结束必须复制到 Drive：

```python
from pathlib import Path

src = Path("/content/LLaMA-Factory/saves/qwen2vl-2b-tablenet-mini/lora/smoke")
dst = Path("/content/drive/MyDrive/TableNet/qwen2vl-2b-tablenet-mini-lora-smoke")

!rm -rf "{dst}"
!mkdir -p "{dst.parent}"
!cp -r "{src}" "{dst}"
!find "{dst}" -maxdepth 2 -type f | head
```

建议同时保存训练配置和数据转换脚本：

```python
!cp /content/LLaMA-Factory/train_tablenet_qwen2vl_lora.yaml "{dst}/"
!cp /content/LLaMA-Factory/data/tablenet_mini_train.json "{dst}/tablenet_mini_train.preview.json"
!cp /content/LLaMA-Factory/data/tablenet_mini_val.json "{dst}/tablenet_mini_val.preview.json"
```

如果数据文件很大，不建议完整复制 JSON 到结果目录，只保存前几条预览即可。

## 10. smoke 成功标准

第一轮 Colab 不追求效果，只看链路是否打通。

必须满足：

```text
数据集能解压
图片和 HTML 数量一致
LLaMA-Factory 能读取多模态数据
Qwen2-VL-2B 能加载
LoRA / QLoRA 能开始训练
loss 正常打印
adapter 能保存到 Google Drive
```

建议记录：

```text
Colab GPU 型号
训练样本数
cutoff_len
是否使用 quantization_bit: 4
训练耗时
峰值显存
最终 loss
是否 OOM
adapter 保存路径
```

可以把记录追加到 `复现过程实验记录.md`。

## 11. 第二轮：扩大数据规模

smoke 通过后再扩大：

| 轮次 | 数据量 | 目的 |
|---|---:|---|
| smoke | 100-300 | 验证环境和格式 |
| V0 | 1K | 验证训练稳定性 |
| V1 | 5K | 初步复现实验 |
| V2 | 10K | 正式 TableNet-mini 实验 |

本地生成 1K 示例：

```powershell
cd "E:\SchoolContents\2026-TableNet- A Large-Scale Table Dataset with L\TableGeneration"

python agents\run_agents.py `
  --target_num 1000 `
  --balanced_configs `
  --balanced_structures `
  --semantic_mode rule `
  --retry_failed `
  --max_attempts 3000 `
  --report `
  --output ..\output\tablenet_mini_v0_1k `
  --min_row 6 `
  --max_row 10 `
  --min_col 4 `
  --max_col 7 `
  --chrome_driver_path ..\chromedriver-win64\chromedriver.exe
```

打包：

```powershell
cd ..
Compress-Archive `
  -Path output\tablenet_mini_v0_1k `
  -DestinationPath output\tablenet_mini_v0_1k.zip `
  -Force
```

上传到：

```text
MyDrive/TableNet/tablenet_mini_v0_1k.zip
```

Colab 中只需要替换：

```python
ZIP_PATH = DRIVE_ROOT / "tablenet_mini_v0_1k.zip"
DATA_ROOT = Path("/content/tablenet_mini_v0_1k")
```

并修改训练配置：

```yaml
max_samples: 1000
save_steps: 100
```

## 12. 后续正式评估

训练 smoke 阶段只证明能跑。正式实验还需要补：

```text
1. 预测脚本：读取 val 图片，让模型生成 HTML。
2. 清洗脚本：去掉 Markdown code fence，只保留 HTML。
3. TEDS 评估：比较预测 HTML 和真实 HTML。
4. Structure-only TEDS：去掉文本，只评结构。
5. 分组报告：All / Simple / Complex / Colored / Colorless / Lined / Lineless。
```

建议输出格式：

```text
predictions.jsonl
```

每行：

```json
{
  "filename": "img/xxx.jpg",
  "config_id": "complex_colored_lined",
  "header_type": "grouped_columns",
  "target_html": "<html>...</html>",
  "pred_html": "<html>...</html>",
  "full_teds": 0.0,
  "structure_teds": 0.0
}
```

这部分可以在下一阶段单独实现，不需要塞进第一版 Colab smoke。

## 13. 常见问题

### 13.1 数据能不能直接在 Colab 生成？

理论上可以，但不建议作为第一方案。

原因：

- 当前本地已经配置好了 Chrome / ChromeDriver。
- Colab 上 Selenium 渲染也能配，但会引入额外变量。
- 我们现在真正缺的是 GPU 训练，不是表格生成。

所以推荐：

```text
本地生成数据
Colab 训练模型
```

### 13.2 为什么先用 rule 语义模式？

因为第一轮目标是训练链路，不是语义质量上限。`--semantic_mode rule` 可以减少外部 LLM API 的不确定性，让数据生成可复现。

等训练链路稳定后，再生成一版：

```text
semantic_mode auto / llm
```

用于比较语义丰富度对 TSR 微调的影响。

### 13.3 HTML 太长怎么办？

如果训练日志提示序列被截断：

- smoke 阶段可以先接受。
- 正式训练时提高 `cutoff_len` 到 `8192`。
- 或者限制本地生成时的行列数。
- 或者把目标输出从完整 HTML 简化成 table 内部片段。

### 13.4 Colab 免费版能不能跑？

可能能跑 smoke，但不保证稳定。建议：

```text
T4: 4-bit QLoRA，100-300 张，cutoff_len 2048/4096
L4: 4-bit QLoRA，1K 尝试
A100: LoRA 或 QLoRA，5K/10K 更现实
```

### 13.5 训练结果在哪里？

Colab 本地路径：

```text
/content/LLaMA-Factory/saves/qwen2vl-2b-tablenet-mini/lora/smoke
```

Drive 持久化路径：

```text
MyDrive/TableNet/qwen2vl-2b-tablenet-mini-lora-smoke
```

## 14. 参考链接

- Qwen2-VL HuggingFace 模型：<https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct>
- Qwen2-VL 官方仓库：<https://github.com/QwenLM/Qwen2-VL>
- LLaMA-Factory 官方仓库：<https://github.com/hiyouga/LLaMA-Factory>
- LLaMA-Factory 多模态数据格式说明：<https://github.com/hiyouga/LLaMA-Factory/blob/main/data/README.md>

