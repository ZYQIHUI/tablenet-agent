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
            use_llm_body=False):
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

    def generate(self, request: TableRequest):
        plan = self.topic_agent.plan(request)
        schema = self.schema_agent.build(plan)
        style = self.style_agent.build(plan)
        schema = self.header_agent.fill(schema, plan)
        schema = self.body_agent.fill(schema, plan)
        ok, errors = self.validator_agent.validate(schema)

        if not ok:
            raise ValueError("invalid table schema: " + "; ".join(errors))
        filling_report = self.filling_checker.evaluate(schema, plan)
        if not filling_report.ok:
            raise ValueError(
                "invalid table filling "
                f"(score={filling_report.score:.3f}, "
                f"title={filling_report.title_score:.3f}, "
                f"header={filling_report.header_score:.3f}, "
                f"body={filling_report.body_score:.3f}): "
                + "; ".join(filling_report.errors)
            )
        return self.html_builder.build(plan, schema, style)
