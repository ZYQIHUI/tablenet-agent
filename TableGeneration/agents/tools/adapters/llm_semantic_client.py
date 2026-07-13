import json

from .llm_topic_client import LLMTopicClient


class LLMSemanticClient(LLMTopicClient):
    backend_source = "api"
    DEFAULT_SYSTEM_PROMPT = (
        "You are an anonymous table quality evaluator. Return JSON only with topic_score, "
        "semantic_score, errors, and evidence. Scores must be numbers from 0 to 1."
    )

    def evaluate_semantics(self, topic, domain, headers, rows):
        if not self.api_key or not self.base_url or not self.model:
            return None
        prompt = json.dumps({
            "topic": topic,
            "domain": domain,
            "headers": headers,
            "rows": rows,
            "criteria": {
                "topic_score": "relevance to the requested topic",
                "semantic_score": "header-body alignment and cross-row consistency",
            },
        }, ensure_ascii=False)
        try:
            data = self._loads_json_object(self._chat_completion(prompt))
            return self._normalize(data)
        except Exception:
            return None

    def _normalize(self, data):
        try:
            topic = max(0.0, min(1.0, float(data["topic_score"])))
            semantic = max(0.0, min(1.0, float(data["semantic_score"])))
        except (KeyError, TypeError, ValueError):
            return None
        errors = data.get("errors", [])
        evidence = data.get("evidence", [])
        return {
            "topic_score": topic,
            "semantic_score": semantic,
            "errors": [str(item) for item in errors] if isinstance(errors, list) else [],
            "evidence": [str(item) for item in evidence] if isinstance(evidence, list) else [],
        }
