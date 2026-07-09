import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMBodyClient:
    """Optional LLM entry point for BodyAgent."""

    DEFAULT_SYSTEM_PROMPT = (
        "You are a domain-aware table body generation agent. "
        "Generate realistic body values that match the headers and topic. "
        "Return valid JSON only with values as a text list or cell_values as a text mapping. "
        "Do not generate table structure, headers, HTML, or metadata."
    )

    def __init__(self, api_key=None, base_url=None, model=None, system_prompt=None):
        env = self._load_env()
        self.api_key = api_key or env.get("LLM_BODY_API_KEY") or env.get("LLM_HEADER_API_KEY") or env.get("LLM_TOPIC_API_KEY")
        self.base_url = base_url or env.get("LLM_BODY_BASE_URL") or env.get("LLM_HEADER_BASE_URL") or env.get("LLM_TOPIC_BASE_URL")
        self.model = model or env.get("LLM_BODY_MODEL") or env.get("LLM_HEADER_MODEL") or env.get("LLM_TOPIC_MODEL")
        self.timeout = float(env.get("LLM_BODY_TIMEOUT") or env.get("LLM_HEADER_TIMEOUT") or env.get("LLM_TOPIC_TIMEOUT") or "60")
        self.system_prompt = (
            system_prompt
            or env.get("LLM_BODY_SYSTEM_PROMPT")
            or self.DEFAULT_SYSTEM_PROMPT
        )

    def generate_body_values(self, domain, language, topic, headers, row_headers, body_cells):
        if not self.api_key or not self.base_url or not self.model:
            return None
        prompt = self._build_prompt(domain, language, topic, headers, row_headers, body_cells)
        try:
            content = self._chat_completion(prompt)
            return self._parse_values(content, len(body_cells))
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
            return None

    def _chat_completion(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }
        request = Request(
            self._chat_completions_url(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"]

    def _chat_completions_url(self) -> str:
        base_url = self.base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/chat/completions"

    def _parse_values(self, content: str, expected_len: int):
        data = self._loads_json_object(content)
        values = data.get("values")
        if isinstance(values, dict):
            return self._clean_mapping(values)
        if values is None and isinstance(data.get("cell_values"), dict):
            return self._clean_mapping(data.get("cell_values"))
        if not isinstance(values, list) or len(values) != expected_len:
            return None
        cleaned = []
        for value in values:
            if not isinstance(value, (str, int, float)):
                return None
            text = str(value).strip()
            if not text:
                return None
            cleaned.append(text)
        return cleaned

    def _clean_mapping(self, values):
        cleaned = {}
        for key, value in values.items():
            if not isinstance(key, str) or not isinstance(value, (str, int, float)):
                return None
            text = str(value).strip()
            if not text:
                return None
            cleaned[key.strip()] = text
        return cleaned or None

    def _loads_json_object(self, content: str):
        if not isinstance(content, str):
            raise ValueError("LLM response must be a string")
        content = content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("LLM response must be a JSON object")
        forbidden_keys = {"rows", "cols", "cells", "schema", "html", "headers"}
        if any(key in data for key in forbidden_keys):
            raise ValueError("LLM body response must not include table structure")
        return data

    def _build_prompt(self, domain, language, topic, headers, row_headers, body_cells) -> str:
        payload = {
            "domain": domain,
            "language": language,
            "topic": topic,
            "headers": headers,
            "row_headers": row_headers,
            "body_cells": body_cells,
            "task": (
                "Generate a JSON object with values or cell_values. "
                "values must be a list of strings, same length and order as body_cells. "
                "Alternatively, cell_values may map \"row,col\" to a string. "
                "Each value should match the corresponding header, row label, and expected_type. "
                "Return only body text; do not return structure, headers, cells, HTML, rows, or cols."
            ),
        }
        return json.dumps(payload, ensure_ascii=False)

    def _load_env(self):
        env = {}
        env_path = self._find_env_path()
        if env_path is not None:
            env.update(self._parse_env_file(env_path))
        for key in (
                "LLM_BODY_API_KEY",
                "LLM_BODY_BASE_URL",
                "LLM_BODY_MODEL",
                "LLM_BODY_SYSTEM_PROMPT",
                "LLM_BODY_TIMEOUT",
                "LLM_HEADER_API_KEY",
                "LLM_HEADER_BASE_URL",
                "LLM_HEADER_MODEL",
                "LLM_HEADER_TIMEOUT",
                "LLM_TOPIC_API_KEY",
                "LLM_TOPIC_BASE_URL",
                "LLM_TOPIC_MODEL",
                "LLM_TOPIC_TIMEOUT",
        ):
            if os.environ.get(key):
                env[key] = os.environ[key]
        return env

    def _find_env_path(self):
        candidates = []
        if os.environ.get("LLM_BODY_ENV_PATH"):
            candidates.append(Path(os.environ["LLM_BODY_ENV_PATH"]))
        module_dir = Path(__file__).resolve().parent
        candidates.append(module_dir / ".env")
        candidates.extend([parent / ".env" for parent in module_dir.parents])
        cwd = Path.cwd()
        candidates.extend([cwd / ".env", *[parent / ".env" for parent in cwd.parents]])
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def _parse_env_file(self, env_path):
        values = {}
        with open(env_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    values[key] = value
        return values
