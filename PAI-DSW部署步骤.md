# PAI-DSW 部署步骤

本文档用于把 TableNet 复现实验从本地迁移到阿里云 PAI-DSW。目标是让 DSW 同时承担两件事：

```text
1. 批量生成 TableNet-mini 数据集
2. 微调 Qwen2-VL-2B 做 table image -> HTML
```

推荐主线：

```text
本地：开发代码、小规模验证、整理实验记录
PAI-DSW：批量生成数据、训练模型、跑评估
PAI-DLC：后续正式大规模训练任务
```

当前阶段先不用 DLC。先在 DSW 上跑通 16 张数据生成 smoke，再跑 300 张数据生成和 Qwen2-VL-2B QLoRA smoke。

## 1. 创建 DSW 实例

在阿里云控制台进入：

```text
人工智能平台 PAI
-> 工作空间
-> 模型开发与训练
-> 交互式建模（DSW）
-> 新建实例
```

DSW 是阿里云 PAI 提供的云端开发环境，支持 Notebook、VSCode/WebIDE 和 Terminal，适合我们调代码、生成数据和训练模型。

## 2. 推荐实例配置

结合当前实验目标，推荐如下配置：

| 配置项 | 推荐值 | 说明 |
|---|---|---|
| 实例名称 | `tablenet-main` | 比 `main` 更容易识别用途 |
| 资源类型 | 公共资源 | 起步最方便，按量付费 |
| 资源规格 | `ecs.gn7i-c8g1.2xlarge` 或同级 A10 | 8 vCPU / 30 GiB / A10 x 1，适合 Qwen2-VL-2B QLoRA |
| 竞价购买 | 先关闭 | smoke 阶段追求稳定，不要被抢占 |
| 驱动设置 | 550 | 截图里的默认值可保留 |
| 镜像配置 | `modelscope:...pytorch2.3.1...gpu-py311-cu121-ubuntu22.04` | 适合国内模型下载和 PyTorch GPU 环境 |
| 系统盘 | 建议 200 GiB | 100 GiB 前期能跑，但模型缓存和数据集很快会占满 |
| 数据集挂载 | 第一轮可不挂 | smoke 可以只用系统盘 |
| 存储挂载 | 后续建议挂 OSS | 正式 1K/5K/10K 数据建议持久化 |
| 工作目录 | 系统盘 `/mnt/systemdisk` | 未挂存储时使用 |
| 专有网络配置 | 可先不选 | 先降低配置复杂度 |
| 从实例访问公网 | 公网网关 | 需要 git clone、pip install、下载模型 |
| 启用 SSH | 可先关闭 | DSW 自带 Terminal，后续需要 VSCode Remote 再开 |
| 可见范围 | 仅创建者可见 | 个人实验更安全 |

注意：

- 公共资源通常是按量计费，实例运行时会持续扣费。
- 公共资源 GPU 在单账号单地域有卡数限制，创建失败时可以换规格或地域。
- 系统盘默认有免费额度，但删除实例会释放系统盘；重要数据必须备份到 OSS/NAS/本地。
- 如果只使用默认 100 GiB 系统盘，长时间停止后也有被清理风险；正式数据不要只放系统盘。

## 3. 创建后的第一轮检查

实例创建成功后，点击：

```text
打开
```

进入 DSW 开发环境后，打开 Terminal。先执行：

```bash
nvidia-smi
python --version
pip --version
df -h
pwd
```

预期：

```text
nvidia-smi 能看到 NVIDIA A10
Python 能正常运行
pip 可用
系统盘空间足够
当前工作目录在 /mnt/systemdisk 或 /mnt/workspace 附近
```

建议建立固定目录：

```bash
mkdir -p /mnt/systemdisk/tablenet
mkdir -p /mnt/systemdisk/tablenet/data
mkdir -p /mnt/systemdisk/tablenet/models
mkdir -p /mnt/systemdisk/tablenet/results
cd /mnt/systemdisk/tablenet
```

后续本文默认项目路径是：

```text
/mnt/systemdisk/tablenet/2026-TableNet
```

数据输出路径是：

```text
/mnt/systemdisk/tablenet/data
```

## 4. 上传或拉取项目代码

有两种方式。

### 4.1 推荐方式：Git 拉取

如果项目已经放到 GitHub/Gitee/Codeup：

```bash
cd /mnt/systemdisk/tablenet
git clone <你的仓库地址> 2026-TableNet
cd 2026-TableNet
```

如果是私有仓库，建议先配置 SSH key 或使用 access token。

### 4.2 临时方式：上传 zip

如果还没有远程仓库：

1. 本地把整个项目压缩成 zip。
2. 在 DSW 左侧文件面板上传 zip。
3. Terminal 解压：

```bash
cd /mnt/systemdisk/tablenet
unzip 2026-TableNet.zip -d 2026-TableNet
cd 2026-TableNet
```

注意不要把本地 `output/`、`.git/`、`__pycache__/`、大模型文件一起打进去。上传前最好确认 `.gitignore` 已排除临时输出。

## 5. 安装系统依赖

数据生成需要 Selenium 浏览器渲染。DSW 镜像通常没有完整浏览器环境，先安装 Chromium 和中文字体。

```bash
sudo apt-get update
sudo apt-get install -y \
  chromium-browser \
  chromium-chromedriver \
  fonts-noto-cjk \
  fonts-wqy-zenhei \
  unzip \
  zip \
  tree
```

如果 `chromium-browser` 或 `chromium-chromedriver` 找不到，改用：

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

检查安装：

```bash
which chromium || which chromium-browser || which google-chrome
which chromedriver
chromedriver --version
fc-list | grep -i "Noto Sans CJK" | head
```

如果 `which chromedriver` 没有输出，后面可以先不传 `--chrome_driver_path`，让 Selenium Manager 尝试自动处理；但更推荐显式找到 chromedriver 路径。

## 6. 安装 Python 依赖

进入项目的 `TableGeneration` 目录：

```bash
cd /mnt/systemdisk/tablenet/2026-TableNet/TableGeneration
pip install -r requirements.txt
```

如果下载慢，使用国内源：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

检查核心包：

```bash
python - <<'PY'
import selenium
import cv2
import PIL
import numpy
print("selenium", selenium.__version__)
print("cv2", cv2.__version__)
print("PIL ok")
print("numpy", numpy.__version__)
PY
```

## 7. 跑本地单元测试

先确认代码没有在 Linux 环境下破掉：

```bash
cd /mnt/systemdisk/tablenet/2026-TableNet/TableGeneration
python -m unittest discover -s tests -p "test_*.py"
```

预期：

```text
全部测试通过
```

如果有 Windows 路径相关问题，优先修路径，不要直接跳过测试。

## 8. DSW 数据生成 smoke：16 张

先跑最小批量，确认 Chromium、字体、渲染和标注都正常。

查找 chromedriver：

```bash
which chromedriver
```

假设输出是：

```text
/usr/bin/chromedriver
```

执行：

```bash
cd /mnt/systemdisk/tablenet/2026-TableNet/TableGeneration

python agents/run_agents.py \
  --target_num 16 \
  --balanced_configs \
  --balanced_structures \
  --semantic_mode rule \
  --retry_failed \
  --max_attempts 48 \
  --report \
  --output /mnt/systemdisk/tablenet/data/tablenet_dsw_smoke_16 \
  --min_row 6 \
  --max_row 8 \
  --min_col 4 \
  --max_col 6 \
  --chrome_driver_path /usr/bin/chromedriver
```

如果 chromedriver 路径不同，就替换最后一行。

如果没有 chromedriver，可以先试：

```bash
python agents/run_agents.py \
  --target_num 16 \
  --balanced_configs \
  --balanced_structures \
  --semantic_mode rule \
  --retry_failed \
  --max_attempts 48 \
  --report \
  --output /mnt/systemdisk/tablenet/data/tablenet_dsw_smoke_16 \
  --min_row 6 \
  --max_row 8 \
  --min_col 4 \
  --max_col 6
```

## 9. 检查 smoke 输出

```bash
OUT=/mnt/systemdisk/tablenet/data/tablenet_dsw_smoke_16

find "$OUT/img" -name "*.jpg" | wc -l
find "$OUT/html" -name "*.html" | wc -l
wc -l "$OUT/gt.txt"
wc -l "$OUT/meta.jsonl"
wc -l "$OUT/cells.jsonl"
cat "$OUT/report.md"
```

预期：

```text
img: 16
html: 16
gt.txt: 16 行
meta.jsonl: 16 行
cells.jsonl: 16 行
report complete: true
```

抽样看图片：

```bash
find "$OUT/img" -name "*.jpg" | head
```

可以在 DSW 左侧文件面板打开图片查看。

如果图片乱码或中文字体异常：

```bash
sudo apt-get install -y fonts-noto-cjk fonts-wqy-zenhei
fc-cache -fv
```

然后重新生成。

## 10. 生成 300 张训练 smoke 数据

16 张通过后再跑 300 张：

```bash
cd /mnt/systemdisk/tablenet/2026-TableNet/TableGeneration

python agents/run_agents.py \
  --target_num 300 \
  --balanced_configs \
  --balanced_structures \
  --semantic_mode rule \
  --retry_failed \
  --max_attempts 900 \
  --report \
  --output /mnt/systemdisk/tablenet/data/tablenet_mini_dsw_smoke_300 \
  --min_row 6 \
  --max_row 8 \
  --min_col 4 \
  --max_col 6 \
  --chrome_driver_path /usr/bin/chromedriver
```

检查：

```bash
OUT=/mnt/systemdisk/tablenet/data/tablenet_mini_dsw_smoke_300
find "$OUT/img" -name "*.jpg" | wc -l
find "$OUT/html" -name "*.html" | wc -l
wc -l "$OUT/meta.jsonl"
wc -l "$OUT/cells.jsonl"
cat "$OUT/report.md"
du -sh "$OUT"
```

打包：

```bash
cd /mnt/systemdisk/tablenet/data
zip -r tablenet_mini_dsw_smoke_300.zip tablenet_mini_dsw_smoke_300
ls -lh tablenet_mini_dsw_smoke_300.zip
```

## 11. 数据规模推进建议

不要一上来跑 10K。按下面顺序推进：

| 阶段 | 数量 | 目的 |
|---|---:|---|
| DSW smoke | 16 | 验证渲染环境 |
| train smoke | 300 | 验证 Qwen2-VL 训练链路 |
| V0 | 1K | 验证训练稳定性和数据质量 |
| V1 | 5K | 初步 TableNet-mini 实验 |
| V2 | 10K | 正式小规模复现实验 |

1K 示例：

```bash
cd /mnt/systemdisk/tablenet/2026-TableNet/TableGeneration

python agents/run_agents.py \
  --target_num 1000 \
  --balanced_configs \
  --balanced_structures \
  --semantic_mode rule \
  --retry_failed \
  --max_attempts 3000 \
  --report \
  --output /mnt/systemdisk/tablenet/data/tablenet_mini_v0_1k \
  --min_row 6 \
  --max_row 10 \
  --min_col 4 \
  --max_col 7 \
  --chrome_driver_path /usr/bin/chromedriver
```

## 12. 安装 LLaMA-Factory

训练第一版使用 LLaMA-Factory，原因是它支持 Qwen2-VL、多模态 SFT、LoRA 和 QLoRA。

```bash
cd /mnt/systemdisk/tablenet
git clone --depth 1 https://github.com/hiyouga/LLaMA-Factory.git
cd LLaMA-Factory
pip install -e ".[torch,metrics]" -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install qwen-vl-utils -i https://pypi.tuna.tsinghua.edu.cn/simple
```

检查：

```bash
llamafactory-cli version
```

如果依赖冲突，优先确认当前镜像的 Python/CUDA/PyTorch 版本。必要时新建 DSW 实例换更新的 ModelScope / PyTorch 镜像。

## 13. 转换数据为多模态 SFT 格式

训练格式：

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
  "images": ["/mnt/systemdisk/tablenet/data/.../img/xxx.jpg"]
}
```

创建转换脚本：

```bash
cat > /mnt/systemdisk/tablenet/convert_tablenet_to_sft.py <<'PY'
import argparse
import json
import random
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_root", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--train_name", default="tablenet_mini_train.json")
    parser.add_argument("--val_name", default="tablenet_mini_val.json")
    parser.add_argument("--val_ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=20260709)
    return parser.parse_args()


def main():
    args = parse_args()
    root = Path(args.dataset_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

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

    random.seed(args.seed)
    random.shuffle(samples)
    split = max(1, int(len(samples) * (1 - args.val_ratio)))
    train_samples = samples[:split]
    val_samples = samples[split:]

    train_path = output_dir / args.train_name
    val_path = output_dir / args.val_name
    train_path.write_text(json.dumps(train_samples, ensure_ascii=False, indent=2), encoding="utf-8")
    val_path.write_text(json.dumps(val_samples, ensure_ascii=False, indent=2), encoding="utf-8")

    print({
        "dataset_root": str(root),
        "total": len(samples),
        "train": len(train_samples),
        "val": len(val_samples),
        "train_path": str(train_path),
        "val_path": str(val_path),
    })


if __name__ == "__main__":
    main()
PY
```

执行转换：

```bash
python /mnt/systemdisk/tablenet/convert_tablenet_to_sft.py \
  --dataset_root /mnt/systemdisk/tablenet/data/tablenet_mini_dsw_smoke_300 \
  --output_dir /mnt/systemdisk/tablenet/LLaMA-Factory/data
```

注册数据集：

```bash
cd /mnt/systemdisk/tablenet/LLaMA-Factory

python - <<'PY'
import json
from pathlib import Path

info_path = Path("data/dataset_info.json")
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
PY
```

## 14. 配置 Qwen2-VL-2B QLoRA 训练

A10 24GB 推荐先用 4-bit QLoRA。等 smoke 成功后，再考虑普通 LoRA。

```bash
cd /mnt/systemdisk/tablenet/LLaMA-Factory

cat > train_tablenet_qwen2vl_lora.yaml <<'YAML'
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
YAML
```

说明：

- `quantization_bit: 4` 用于降低显存压力。
- `cutoff_len: 4096` 是 smoke 阶段的保守设置。
- 如果 HTML 被截断，后续可调到 `8192`。
- 如果 A10 显存仍紧张，先把 `max_samples` 改成 `50` 或 `100`。

## 15. 启动训练 smoke

```bash
cd /mnt/systemdisk/tablenet/LLaMA-Factory
llamafactory-cli train train_tablenet_qwen2vl_lora.yaml
```

训练中重点观察：

```text
1. 是否成功加载 Qwen/Qwen2-VL-2B-Instruct
2. 是否成功读取 tablenet_mini_train
3. 是否出现 CUDA out of memory
4. loss 是否正常打印
5. saves/qwen2vl-2b-tablenet-mini/lora/smoke 是否生成 adapter 文件
```

如果 OOM：

```text
先把 max_samples 改成 50
再把 cutoff_len 改成 2048
保留 quantization_bit: 4
仍不行就换更大显存资源
```

训练结束检查：

```bash
ls -lah saves/qwen2vl-2b-tablenet-mini/lora/smoke
find saves/qwen2vl-2b-tablenet-mini/lora/smoke -maxdepth 2 -type f
```

## 16. 保存结果

如果没有挂 OSS，先保存到系统盘结果目录，并打包下载。

```bash
mkdir -p /mnt/systemdisk/tablenet/results

cp train_tablenet_qwen2vl_lora.yaml \
  /mnt/systemdisk/tablenet/results/

tar -czf /mnt/systemdisk/tablenet/results/qwen2vl-2b-tablenet-mini-lora-smoke.tar.gz \
  -C /mnt/systemdisk/tablenet/LLaMA-Factory/saves/qwen2vl-2b-tablenet-mini/lora \
  smoke

ls -lh /mnt/systemdisk/tablenet/results
```

如果已经挂 OSS，推荐把结果复制到 OSS 挂载目录，例如：

```bash
mkdir -p /mnt/data/tablenet/results
cp /mnt/systemdisk/tablenet/results/qwen2vl-2b-tablenet-mini-lora-smoke.tar.gz \
  /mnt/data/tablenet/results/
```

注意：系统盘不是长期归档位置。正式实验必须把数据集、adapter、日志和评估结果保存到 OSS/NAS 或下载到本地。

## 17. 正式数据生成建议

1K：

```bash
cd /mnt/systemdisk/tablenet/2026-TableNet/TableGeneration

python agents/run_agents.py \
  --target_num 1000 \
  --balanced_configs \
  --balanced_structures \
  --semantic_mode rule \
  --retry_failed \
  --max_attempts 3000 \
  --report \
  --output /mnt/systemdisk/tablenet/data/tablenet_mini_v0_1k \
  --min_row 6 \
  --max_row 10 \
  --min_col 4 \
  --max_col 7 \
  --chrome_driver_path /usr/bin/chromedriver
```

5K：

```bash
cd /mnt/systemdisk/tablenet/2026-TableNet/TableGeneration

python agents/run_agents.py \
  --target_num 5000 \
  --balanced_configs \
  --balanced_structures \
  --semantic_mode rule \
  --retry_failed \
  --max_attempts 15000 \
  --report \
  --output /mnt/systemdisk/tablenet/data/tablenet_mini_v1_5k \
  --min_row 6 \
  --max_row 10 \
  --min_col 4 \
  --max_col 7 \
  --chrome_driver_path /usr/bin/chromedriver
```

10K：

```bash
cd /mnt/systemdisk/tablenet/2026-TableNet/TableGeneration

python agents/run_agents.py \
  --target_num 10000 \
  --balanced_configs \
  --balanced_structures \
  --semantic_mode rule \
  --retry_failed \
  --max_attempts 30000 \
  --report \
  --output /mnt/systemdisk/tablenet/data/tablenet_mini_v2_10k \
  --min_row 6 \
  --max_row 12 \
  --min_col 4 \
  --max_col 8 \
  --chrome_driver_path /usr/bin/chromedriver
```

10K 建议挂 OSS/NAS，不建议只放系统盘。

## 18. 后续评估任务

训练 smoke 通过后，还需要补正式评估：

```text
1. 推理脚本：读取验证集图片，生成 HTML。
2. 清洗脚本：去掉 Markdown code fence，只保留 HTML。
3. Full TEDS：比较预测 HTML 和真实 HTML。
4. Structure-only TEDS：去掉文本后只评结构。
5. 分组报告：All / Simple / Complex / Colored / Colorless / Lined / Lineless。
```

建议预测输出：

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

## 19. 常见问题

### 19.1 DSW 实例启动失败

优先看实例详情里的事件信息。常见原因：

```text
资源库存不足
GPU 卡数超过账号限制
地域不支持当前规格
镜像拉取失败
```

处理：

```text
换同级 GPU 规格
换地域
稍后重试
提交工单提升 GPU 限额
```

### 19.2 pip 安装慢或失败

使用国内源：

```bash
pip install <package> -i https://pypi.tuna.tsinghua.edu.cn/simple
```

或换 ModelScope / PyTorch 官方镜像。

### 19.3 Chromium 找不到

尝试：

```bash
sudo apt-get install -y chromium chromium-driver
```

或：

```bash
sudo apt-get install -y chromium-browser chromium-chromedriver
```

然后确认：

```bash
which chromium
which chromedriver
```

### 19.4 中文显示异常

安装字体并刷新缓存：

```bash
sudo apt-get install -y fonts-noto-cjk fonts-wqy-zenhei
fc-cache -fv
```

### 19.5 系统盘不够

先检查：

```bash
df -h
du -sh /mnt/systemdisk/tablenet/*
```

处理顺序：

```text
删除中间缓存
把 zip / 数据集迁移到 OSS
扩容系统盘
重新创建实例并挂载 OSS/NAS
```

### 19.6 训练 OOM

处理顺序：

```text
确认 quantization_bit: 4
max_samples 降到 50
cutoff_len 降到 2048
gradient_accumulation_steps 保持或提高
换 A100 / 更大显存资源
```

### 19.7 忘记停止实例

DSW 公共资源实例运行中会持续计费。每天实验结束后：

```text
保存代码、数据、模型到 OSS/本地
停止实例
确认不再计费
```

重要数据不要只留在即将删除的实例系统盘里。

## 20. 推荐执行顺序

第一天只做这些：

```text
1. 创建 A10 DSW 实例
2. Terminal 检查 nvidia-smi / df -h
3. 上传或 git clone 项目
4. 安装 Chromium / chromedriver / 字体
5. pip install -r requirements.txt
6. 跑单元测试
7. 生成 16 张 smoke 数据
8. 检查图片、gt、meta、cells
```

第二天再做：

```text
1. 生成 300 张训练 smoke 数据
2. 安装 LLaMA-Factory
3. 转换 SFT 格式
4. 跑 Qwen2-VL-2B QLoRA smoke
5. 保存 adapter 和日志
```

第三步才扩展：

```text
1K -> 5K -> 10K
```

## 21. 参考

- 阿里云 DSW 交互式建模快速入门：<https://help.aliyun.com/zh/pai/product-overview/dsw-quickstart>
- 阿里云创建 DSW 实例文档：<https://help.aliyun.com/zh/pai/create-and-manage-dsw-instances>
- 阿里云 DSW 常见问题：<https://help.aliyun.com/zh/pai/faq-about-dsw>
- Qwen2-VL 模型：<https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct>
- Qwen2-VL 官方仓库：<https://github.com/QwenLM/Qwen2-VL>
- LLaMA-Factory 官方仓库：<https://github.com/hiyouga/LLaMA-Factory>

