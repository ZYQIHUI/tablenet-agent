import json
import re
from typing import Optional


class LocalQwenClient:
    """Lazy local Qwen client implementing the existing semantic client methods."""

    backend_source = "local_model"

    def __init__(
            self,
            model_path: str,
            device: str = "auto",
            max_new_tokens: int = 2048,
            temperature: float = 0.7):
        if not model_path:
            raise ValueError("model_path is required for the local backend")
        self.model_path = model_path
        self.device = device
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self._model = None
        self._processor = None
        self.last_usage = {}

    def generate_topic(
            self,
            domain,
            language,
            used_topics,
            min_rows,
            max_rows,
            min_cols,
            max_cols):
        prompt = (
            "Generate one domain-relevant table topic as JSON with keys topic, domain, "
            "and semantic_scenario. Do not return dimensions, structure, or style. "
            f"domain={domain}; language={language}; rows={min_rows}-{max_rows}; "
            f"cols={min_cols}-{max_cols}; used_topics={json.dumps(used_topics, ensure_ascii=False)}"
        )
        return self._generate_json("You are the Topic Agent. Return valid JSON only.", prompt)

    def generate_headers(self, domain, language, topic, cols):
        prompt = (
            "Generate table headers as JSON with string-list keys headers, group_headers, "
            f"and row_headers. domain={domain}; language={language}; topic={topic}; cols={cols}"
        )
        return self._generate_json("You are the Header Agent. Return valid JSON only.", prompt)

    def generate_body_values(
            self,
            domain,
            language,
            topic,
            headers,
            row_headers,
            body_cells):
        prompt = (
            "Fill only the requested body cells. Return a JSON object mapping each row,col "
            "coordinate to one scalar value. Preserve the expected type and table semantics. "
            f"domain={domain}; language={language}; topic={topic}; "
            f"headers={json.dumps(headers, ensure_ascii=False)}; "
            f"row_headers={json.dumps(row_headers, ensure_ascii=False)}; "
            f"body_cells={json.dumps(body_cells, ensure_ascii=False)}"
        )
        return self._generate_json("You are the Body Agent. Return valid JSON only.", prompt)

    def plan_request(self, request_text, defaults):
        prompt = (
            "Convert the request to constrained JSON. Use only domain, language, min_rows, "
            "max_rows, min_cols, max_cols, simple, colored, lined, structure_type. "
            f"request={request_text}; defaults={json.dumps(defaults, ensure_ascii=False)}"
        )
        return self._generate_json("You are the Core Planner. Return valid JSON only.", prompt)

    def evaluate_semantics(self, topic, domain, headers, rows):
        prompt = (
            "Anonymously evaluate topic relevance and semantic consistency. Return JSON with "
            "topic_score, semantic_score, errors, evidence. Scores range from 0 to 1. "
            f"topic={topic}; domain={domain}; headers={json.dumps(headers, ensure_ascii=False)}; "
            f"rows={json.dumps(rows, ensure_ascii=False)}"
        )
        return self._generate_json("You are the Semantic Evaluator. Return valid JSON only.", prompt)

    def _generate_json(self, system_prompt: str, user_prompt: str):
        response = self._generate_text(system_prompt, user_prompt)
        payload = self._extract_json(response)
        if payload is None:
            raise ValueError("local Qwen returned invalid JSON")
        return payload

    def _generate_text(self, system_prompt: str, user_prompt: str) -> str:
        self._ensure_loaded()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        text = self._processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self._processor(text=[text], padding=True, return_tensors="pt")
        model_device = next(self._model.parameters()).device
        inputs = {key: value.to(model_device) for key, value in inputs.items()}
        generation = self._model.generate(
            **inputs,
            max_new_tokens=self.max_new_tokens,
            do_sample=self.temperature > 0,
            temperature=max(self.temperature, 1e-5),
        )
        input_length = inputs["input_ids"].shape[1]
        generated = generation[:, input_length:]
        self.last_usage = {
            "prompt_tokens": int(input_length),
            "completion_tokens": int(generated.shape[1]),
            "total_tokens": int(input_length + generated.shape[1]),
        }
        return self._processor.batch_decode(
            generated,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]

    def _ensure_loaded(self):
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
        except ImportError as exc:
            raise RuntimeError(
                "local Qwen backend requires torch and a transformers version with Qwen2-VL support"
            ) from exc

        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        device_map = self.device if self.device != "auto" else "auto"
        self._processor = AutoProcessor.from_pretrained(self.model_path)
        self._model = Qwen2VLForConditionalGeneration.from_pretrained(
            self.model_path,
            torch_dtype=dtype,
            device_map=device_map,
        )
        self._model.eval()

    def _extract_json(self, text: str) -> Optional[object]:
        text = text.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if fenced:
            text = fenced.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        for start_char, end_char in (("{", "}"), ("[", "]")):
            start = text.find(start_char)
            end = text.rfind(end_char)
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    continue
        return None
