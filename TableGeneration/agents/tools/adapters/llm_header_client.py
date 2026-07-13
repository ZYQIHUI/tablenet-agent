import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMHeaderClient:
    """Optional LLM entry point for HeaderAgent."""

    DEFAULT_SYSTEM_PROMPT = (
        "You are a domain-aware table header generation agent. "
        "Generate concise, realistic headers for synthetic business tables. "
        "Return valid JSON only with text lists: headers, group_headers, row_headers. "
        "Do not generate table structure, rows, cells, HTML, or metadata."
    )

    def __init__(self, api_key=None, base_url=None, model=None, system_prompt=None):
        env = self._load_env()
        self.api_key = api_key or env.get("LLM_HEADER_API_KEY") or env.get("LLM_TOPIC_API_KEY")
        self.base_url = base_url or env.get("LLM_HEADER_BASE_URL") or env.get("LLM_TOPIC_BASE_URL")
        self.model = model or env.get("LLM_HEADER_MODEL") or env.get("LLM_TOPIC_MODEL")
        self.timeout = float(env.get("LLM_HEADER_TIMEOUT") or env.get("LLM_TOPIC_TIMEOUT") or "60")
        self.system_prompt = (
            system_prompt
            or env.get("LLM_HEADER_SYSTEM_PROMPT")
            or self.DEFAULT_SYSTEM_PROMPT
        )
        self.last_usage = {}

    def generate_headers(self, domain: str, language: str, topic: str, cols: int):
        if not self.api_key or not self.base_url or not self.model:
            return None
        prompt = self._build_prompt(domain, language, topic, cols)
        try:
            content = self._chat_completion(prompt)
            return self._parse_headers(content)
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
            return None

    def _chat_completion(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.6,
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
        self.last_usage = dict(result.get("usage") or {})
        return result["choices"][0]["message"]["content"]

    def _chat_completions_url(self) -> str:
        base_url = self.base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/chat/completions"

    def _parse_headers(self, content: str):
        data = self._loads_json_object(content)
        headers = self._clean_list(data.get("headers"))
        group_headers = self._clean_list(data.get("group_headers"))
        row_headers = self._clean_list(data.get("row_headers"))
        if not headers:
            return None
        return {
            "headers": headers,
            "group_headers": group_headers,
            "row_headers": row_headers,
        }

    def _clean_list(self, value):
        if not isinstance(value, list):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

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
        forbidden_keys = {"rows", "cols", "cells", "schema", "html", "structure"}
        if any(key in data for key in forbidden_keys):
            raise ValueError("LLM header response must not include table structure")
        return data

    def _build_prompt(self, domain: str, language: str, topic: str, cols: int) -> str:
        payload = {
            "domain": domain,
            "language": language,
            "topic": topic,
            "column_count": cols,
            "task": (
                "Generate headers for a table about the topic. "
                "Return JSON only with keys: headers, group_headers, row_headers. "
                "Only return text lists; do not return table structure, cells, HTML, or row/column counts. "
                "headers should contain at least column_count short leaf headers. "
                "group_headers should contain 3 to 5 higher-level header group names. "
                "row_headers should contain 6 short row labels suitable for the domain."
            ),
            "format": {
                "headers": ["区域", "用户数", "日均流量", "高峰时段"],
                "group_headers": ["基础信息", "使用指标", "服务质量"],
                "row_headers": ["东区", "西区", "南区", "北区"],
            },
        }
        return json.dumps(payload, ensure_ascii=False)

    def _load_env(self):
        env = {}
        env_path = self._find_env_path()
        if env_path is not None:
            env.update(self._parse_env_file(env_path))
        for key in (
                "LLM_HEADER_API_KEY",
                "LLM_HEADER_BASE_URL",
                "LLM_HEADER_MODEL",
                "LLM_HEADER_SYSTEM_PROMPT",
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
        if os.environ.get("LLM_HEADER_ENV_PATH"):
            candidates.append(Path(os.environ["LLM_HEADER_ENV_PATH"]))
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
