import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMTopicClient:
    """Optional LLM entry point for TopicAgent.

    Fill in generate_topic with your preferred model API. Return either a plain
    topic string or a dict like {"topic": "..."}.
    """

    DEFAULT_SYSTEM_PROMPT = (
        "You are a domain-aware table topic generation agent. "
        "Generate concise, specific, realistic table topics for synthetic table data. "
        "Return valid JSON only."
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

    def generate_topic(self, domain: str, language: str, used_topics):
        prompt = self._build_prompt(domain, language, used_topics)
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
        return result["choices"][0]["message"]["content"]

    def _chat_completions_url(self) -> str:
        base_url = self.base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/chat/completions"

    def _parse_topic(self, content: str):
        content = content.strip()
        if content.startswith("```"):
            content = content.strip("`").strip()
            if content.startswith("json"):
                content = content[4:].strip()
        data = json.loads(content)
        return data.get("topic")

    def _build_prompt(self, domain: str, language: str, used_topics) -> str:
        payload = {
            "domain": domain,
            "language": language,
            "used_topics": used_topics,
            "task": (
                "Generate one concise, domain-specific table topic. "
                "Avoid used topics and return JSON only: {\"topic\": \"...\"}."
            ),
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
