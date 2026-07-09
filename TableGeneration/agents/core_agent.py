from copy import deepcopy

from agents.sub_agents.fillers.body_agent import BodyAgent
from agents.sub_agents.fillers.header_agent import HeaderAgent
from agents.sub_agents.planners.schema_agent import SchemaAgent
from agents.sub_agents.planners.style_agent import StyleAgent
from agents.sub_agents.planners.topic_agent import TopicAgent
from agents.tools.rendering.html_builder import HtmlBuilder
from agents.types import TableRequest
from agents.sub_agents.validators.filling_checker import FillingChecker
from agents.sub_agents.validators.validator_agent import ValidatorAgent

class CoreAgent:
    """Coordinates rule-driven agents following the TableNet workflow."""

    def __init__(
            self,
            topic_agent=None,
            header_agent=None,
            body_agent=None,
            llm_topic_client=None,
            llm_header_client=None,
            llm_body_client=None,
            use_llm_topic=False,
            use_llm_header=False,
            use_llm_body=False,
            max_schema_retries=3,
            max_filling_retries=2):
        self.topic_agent = topic_agent or TopicAgent(
            llm_topic_client=llm_topic_client,
            use_llm=use_llm_topic,
        )
        self.schema_agent = SchemaAgent()
        self.header_agent = header_agent or HeaderAgent(
            llm_header_client=llm_header_client,
            use_llm=use_llm_header,
        )
        self.body_agent = body_agent or BodyAgent(
            llm_body_client=llm_body_client,
            use_llm=use_llm_body,
        )
        self.style_agent = StyleAgent()
        self.validator_agent = ValidatorAgent()
        self.filling_checker = FillingChecker()
        self.html_builder = HtmlBuilder()
        self.max_schema_retries = max_schema_retries
        self.max_filling_retries = max_filling_retries

    def generate(self, request: TableRequest):
        plan = self.topic_agent.plan(request)
        style = self.style_agent.build(plan)
        last_schema_errors = []
        last_filling_report = None

        for _ in range(self.max_schema_retries):
            base_schema = self.schema_agent.build(plan)
            ok, errors = self.validator_agent.validate(base_schema)
            if not ok:
                last_schema_errors = errors
                continue

            for _ in range(self.max_filling_retries):
                schema = deepcopy(base_schema)
                schema = self.header_agent.fill(schema, plan)
                schema = self.body_agent.fill(schema, plan)
                ok, errors = self.validator_agent.validate(schema)
                if not ok:
                    last_schema_errors = errors
                    break

                filling_report = self.filling_checker.evaluate(schema, plan)
                if filling_report.ok:
                    return self.html_builder.build(plan, schema, style)

                last_filling_report = filling_report
                if self._needs_schema_retry(filling_report):
                    break

        if last_schema_errors and last_filling_report is None:
            raise ValueError("invalid table schema: " + "; ".join(last_schema_errors))
        if last_filling_report is not None:
            raise ValueError(self._format_filling_error(last_filling_report))
        raise ValueError("failed to generate a valid table")

    def _needs_schema_retry(self, filling_report):
        return filling_report.title_score <= 0.0 or filling_report.header_score <= 0.0

    def _format_filling_error(self, filling_report):
        low_dimensions = self._low_filling_dimensions(filling_report)
        low_dimension_text = ""
        if low_dimensions:
            low_dimension_text = ", low_dimensions=" + ",".join(low_dimensions)
        issues = list(filling_report.errors)
        if not issues:
            issues = list(filling_report.warnings)
        issue_text = "; ".join(issues[:5]) if issues else "no detailed filling issue reported"
        return (
            "invalid table filling "
            f"(score={filling_report.score:.3f}, "
            f"title={filling_report.title_score:.3f}, "
            f"header={filling_report.header_score:.3f}, "
            f"body={filling_report.body_score:.3f}, "
            f"topic_consistency={getattr(filling_report, 'topic_consistency_score', 1.0):.3f}"
            f"{low_dimension_text}): "
            + issue_text
        )

    def _low_filling_dimensions(self, filling_report):
        dimension_scores = getattr(filling_report, "dimension_scores", None) or {
            "title": filling_report.title_score,
            "header": filling_report.header_score,
            "body": filling_report.body_score,
            "topic_consistency": getattr(filling_report, "topic_consistency_score", 1.0),
        }
        return [
            f"{name}:{score:.3f}"
            for name, score in sorted(dimension_scores.items(), key=lambda item: item[1])
            if score < 0.6
        ][:3]
