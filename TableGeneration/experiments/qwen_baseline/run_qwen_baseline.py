import argparse
import json
from pathlib import Path

import torch
import transformers
from peft import PeftModel
from qwen_vl_utils import process_vision_info
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration


DEFAULT_PROMPT = (
    "请识别图片中的表格结构和文本，并输出完整 HTML table。"
    "只输出 HTML，不要解释，不要 Markdown 代码块。"
)


def parse_args():
    parser = argparse.ArgumentParser(description="Run a reproducible Qwen2-VL TableNet baseline.")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--sample-index", type=int, default=0)
    parser.add_argument("--max-new-tokens", type=int, default=2048)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    return parser.parse_args()


def main():
    args = parse_args()
    rows = json.loads(args.dataset.read_text(encoding="utf-8"))
    if not rows:
        raise ValueError(f"Dataset is empty: {args.dataset}")
    if not 0 <= args.sample_index < len(rows):
        raise IndexError(f"sample-index {args.sample_index} is outside [0, {len(rows)})")

    sample = rows[args.sample_index]
    image_path = Path(sample["images"][0])
    if not image_path.is_file():
        raise FileNotFoundError(f"Image does not exist: {image_path}")

    model = Qwen2VLForConditionalGeneration.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        local_files_only=True,
    )
    if args.adapter:
        model = PeftModel.from_pretrained(model, args.adapter, is_trainable=False)
    processor = AutoProcessor.from_pretrained(args.model, local_files_only=True)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": str(image_path)},
                {"type": "text", "text": args.prompt},
            ],
        }
    ]
    chat_text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[chat_text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(model.device)

    with torch.inference_mode():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
            do_sample=False,
        )
    generated_ids = [output[len(input_ids):] for input_ids, output in zip(inputs.input_ids, generated_ids)]
    prediction = processor.batch_decode(
        generated_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0].strip()

    result = {
        "sample_index": args.sample_index,
        "image": str(image_path),
        "prompt": args.prompt,
        "prediction": prediction,
        "reference": sample["messages"][1]["content"],
        "model": str(args.model.resolve()),
        "adapter": str(args.adapter.resolve()) if args.adapter else None,
        "generation": {
            "max_new_tokens": args.max_new_tokens,
            "do_sample": False,
            "torch_dtype": "bfloat16",
        },
        "versions": {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved baseline to {args.output}")
    print(f"prediction_chars={len(prediction)}")
    print(prediction[:500])


if __name__ == "__main__":
    main()
