from ..capabilities import CapabilityRequest


class RoutedSemanticClient:
    """Legacy method facade backed by BackendRouter for incremental Agent migration."""

    def __init__(self, router):
        self.router = router
        self.last_result = None

    @property
    def backend_source(self):
        if self.last_result is None:
            return "mixed"
        return self.last_result.source.value

    def plan_request(self, request_text, defaults):
        return self._execute("request_planning", {
            "request_text": request_text,
            "defaults": defaults,
        })

    def generate_topic(self, **payload):
        return self._execute("topic_generation", payload)

    def generate_headers(self, **payload):
        return self._execute("header_generation", payload)

    def generate_body_values(self, **payload):
        return self._execute("body_generation", payload)

    def evaluate_semantics(self, topic, domain, headers, rows):
        return self._execute("semantic_judging", {
            "topic": topic,
            "domain": domain,
            "headers": headers,
            "rows": rows,
        })

    def _execute(self, capability, payload):
        self.last_result = self.router.execute(CapabilityRequest(capability, payload))
        if not self.last_result.ok:
            reasons = "; ".join(issue.message for issue in self.last_result.errors)
            raise RuntimeError(reasons or f"all backends failed for {capability}")
        return self.last_result.value
