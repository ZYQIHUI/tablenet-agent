import json

from .llm_topic_client import LLMTopicClient


class LLMCoreClient(LLMTopicClient):
    backend_source = "api"
    DEFAULT_SYSTEM_PROMPT = (
        "You are the Core Planner for a table generation system. Convert the user request "
        "to constrained JSON only. Never output code, HTML, tool calls, or extra text."
    )

    def plan_request(self, request_text, defaults):
        if not self.api_key or not self.base_url or not self.model:
            return None
        prompt = json.dumps({
            "request": request_text,
            "defaults": defaults,
            "allowed_keys": [
                "domain", "language", "min_rows", "max_rows", "min_cols", "max_cols",
                "simple", "colored", "lined", "structure_type",
            ],
        }, ensure_ascii=False)
        try:
            return self._loads_json_object(self._chat_completion(prompt))
        except Exception:
            return None
