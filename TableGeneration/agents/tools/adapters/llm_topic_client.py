import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMTopicClient:
    """Optional LLM entry point for TopicAgent.

    Returns a validated dict for TopicAgent or None when the model response
    cannot be trusted.
    """

    DEFAULT_SYSTEM_PROMPT = (
        "You are a domain-aware table topic generation agent. "
        "Generate concise, specific, realistic table plans for synthetic table data. "
        "Return valid JSON only with keys: topic, domain, semantic_scenario. "
        "Do not generate dimensions, styles, structure, or table cells."
    )

    def __init__(self, api_key=None, base_url=None, model=None, system_prompt=None):
        env = self._load_env()
        self.api_key = api_key or env.get("LLM_TOPIC_API_KEY")
        self.base_url = base_url or env.get("LLM_TOPIC_BASE_URL")
        self.model = model or env.get("LLM_TOPIC_MODEL")
        self.timeout = float(env.get("LLM_TOPIC_TIMEOUT", "30"))
        self.system_prompt = (
            system_prompt
            or env.get("LLM_TOPIC_SYSTEM_PROMPT")
            or self.DEFAULT_SYSTEM_PROMPT
        )
        self.last_usage = {}

    def generate_topic(
            self,
            domain: str,
            language: str,
            used_topics,
            min_rows: int = 4,
            max_rows: int = 12,
            min_cols: int = 3,
            max_cols: int = 8):
        prompt = self._build_prompt(domain, language, used_topics, min_rows, max_rows, min_cols, max_cols)
        if not self.api_key or not self.base_url or not self.model:
            return None
        try:
            content = self._chat_completion(prompt)
            return self._parse_topic(content)
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
            return None

    def _chat_completion(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.8,
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

    def _parse_topic(self, content: str):
        data = self._loads_json_object(content)
        topic = self._clean_text(data.get("topic"))
        if not topic:
            return None
        result = {
            "topic": topic,
            "domain": self._clean_text(data.get("domain")),
            "semantic_scenario": self._clean_text(data.get("semantic_scenario")),
        }
        return result

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
        return data

    def _clean_text(self, value):
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    def _build_prompt(self, domain: str, language: str, used_topics, min_rows, max_rows, min_cols, max_cols) -> str:
        payload = {
            "domain": domain,
            "language": language,
            "used_topics": used_topics,
            "bounds": {
                "min_rows": min_rows,
                "max_rows": max_rows,
                "min_cols": min_cols,
                "max_cols": max_cols,
            },
            "task": (
                "Generate one concise, domain-specific table topic. "
                "Avoid used topics. Return JSON only with keys: "
                "topic, domain, semantic_scenario. Do not return dimensions, style, structure, or cells."
            ),
            "format": {
                "topic": "客户投诉受理与闭环统计",
                "domain": domain,
                "semantic_scenario": "customer_complaints",
            },
        }
        return json.dumps(payload, ensure_ascii=False)

    def _load_env(self):
        env = {}
        env_path = self._find_env_path()
        if env_path is not None:
            env.update(self._parse_env_file(env_path))
        for key in (
                "LLM_TOPIC_API_KEY",
                "LLM_TOPIC_BASE_URL",
                "LLM_TOPIC_MODEL",
                "LLM_TOPIC_SYSTEM_PROMPT",
                "LLM_TOPIC_TIMEOUT",
        ):
            if os.environ.get(key):
                env[key] = os.environ[key]
        return env

    def _find_env_path(self):
        candidates = []
        if os.environ.get("LLM_TOPIC_ENV_PATH"):
            candidates.append(Path(os.environ["LLM_TOPIC_ENV_PATH"]))
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
