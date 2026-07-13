from agents.sub_agents.fillers.body_agent import BodyAgent
from agents.sub_agents.fillers.header_agent import HeaderAgent
from agents.sub_agents.planners.schema_agent import SchemaAgent
from agents.sub_agents.planners.style_agent import StyleAgent
from agents.sub_agents.planners.topic_agent import TopicAgent
from agents.tools.rendering.html_builder import HtmlBuilder
from agents.agent_types import TableRequest
from agents.domain.state import GenerationState
from agents.filling.filling_agent import FillingAgent
from agents.memory import InnerMemory, JsonMemoryStore, OuterMemory
from agents.evaluation import SemanticEvaluator
from agents.planners import CorePlanner
from agents.domain import BudgetExceeded, BudgetLimits, BudgetTracker, ErrorCode, ValidationIssue
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
            core_planner_client=None,
            semantic_evaluator_client=None,
            use_llm_topic=False,
            use_llm_header=False,
            use_llm_body=False,
            max_schema_retries=3,
            max_filling_retries=2,
            candidate_count=1,
            augmentation_count=0,
            memory_path=None,
            session_id="default",
            max_model_calls=100,
            max_elapsed_seconds=300.0,
            max_candidates=100):
        self.memory_store = JsonMemoryStore(memory_path) if memory_path else None
        self.inner_memory = InnerMemory(self.memory_store) if self.memory_store else None
        self.outer_memory = OuterMemory(self.memory_store) if self.memory_store else None
        self.session_id = session_id
        self.budget_limits = BudgetLimits(
            max_model_calls=max_model_calls,
            max_elapsed_seconds=max_elapsed_seconds,
            max_schema_attempts=max_schema_retries,
            max_filling_attempts=max_schema_retries * max_filling_retries * max(1, candidate_count),
            max_candidates=max_candidates,
        )
        self.core_planner = CorePlanner(
            client=core_planner_client,
            use_model=core_planner_client is not None,
        )
        self.topic_agent = topic_agent or TopicAgent(
            llm_topic_client=llm_topic_client,
            use_llm=use_llm_topic,
            inner_memory=self.inner_memory,
        )
        if topic_agent is not None and self.inner_memory is not None:
            self.topic_agent.inner_memory = self.inner_memory
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
        self.semantic_evaluator = SemanticEvaluator(
            client=semantic_evaluator_client,
            use_model=semantic_evaluator_client is not None,
        )
        self.filling_checker = FillingChecker(semantic_evaluator=self.semantic_evaluator)
        self.html_builder = HtmlBuilder()
        self.max_schema_retries = max_schema_retries
        self.max_filling_retries = max_filling_retries
        self.candidate_count = max(1, int(candidate_count))
        self.augmentation_count = max(0, min(4, int(augmentation_count)))
        self.last_state = None

    def generate(self, request: TableRequest):
        state = GenerationState(request=request, budget=BudgetTracker(self.budget_limits))
        self.last_state = state
        if self.outer_memory is not None:
            self.outer_memory.set_preferences(
                self.session_id,
                {
                    "domain": request.domain,
                    "language": request.language,
                    "simple": request.simple,
                    "colored": request.colored,
                    "lined": request.lined,
                },
            )
            if request.natural_language_request:
                self.outer_memory.append(
                    self.session_id,
                    "user",
                    request.natural_language_request,
                )
        planned_request = self.core_planner.plan(request)
        core_result = self.core_planner.last_result
        if self.outer_memory is not None and request.natural_language_request:
            self.outer_memory.append(
                self.session_id,
                "assistant",
                "Core Planner produced a constrained request.",
                {
                    "status": core_result.status.value,
                    "source": core_result.source.value,
                    "planned_request": asdict(planned_request),
                },
            )
        if request.natural_language_request and self.core_planner.use_model:
            self._consume_budget(state, "model_calls", self._model_attempts(core_result))
        state.record(
            "core_planning",
            core_result.status.value,
            issues=core_result.errors,
            source=core_result.source.value,
            result_metadata=core_result.metadata,
        )
        plan = self.topic_agent.plan(planned_request)
        if getattr(self.topic_agent, "use_llm", False):
            self._consume_budget(
                state,
                "model_calls",
                self._model_attempts(getattr(self.topic_agent, "last_result", None)),
            )
        style = self.style_agent.build(plan)
        state.plan = plan
        state.style = style
        topic_result = getattr(self.topic_agent, "last_result", None)
        state.record(
            "planning",
            "complete",
            issues=getattr(topic_result, "errors", []),
            source=getattr(getattr(topic_result, "source", None), "value", "unknown"),
            status=getattr(getattr(topic_result, "status", None), "value", "unknown"),
            result_metadata=getattr(topic_result, "metadata", {}),
        )
        filling_agent = FillingAgent(
            schema_agent=self.schema_agent,
            header_agent=self.header_agent,
            body_agent=self.body_agent,
            validator=self.validator_agent,
            checker=self.filling_checker,
            html_builder=self.html_builder,
            max_schema_retries=self.max_schema_retries,
            max_filling_retries=self.max_filling_retries,
            candidate_count=self.candidate_count,
            augmentation_count=self.augmentation_count,
            inner_memory=self.inner_memory,
            style_agent=self.style_agent,
        )
        try:
            return filling_agent.generate(state)
        except BudgetExceeded as exc:
            issue = ValidationIssue(ErrorCode.BUDGET_EXHAUSTED, str(exc))
            state.record("budget", "exhausted", issues=[issue], budget=state.budget.snapshot())
            raise ValueError(str(exc)) from exc

    def _consume_budget(self, state, resource, amount=1):
        try:
            state.consume(resource, amount)
        except BudgetExceeded as exc:
            issue = ValidationIssue(ErrorCode.BUDGET_EXHAUSTED, str(exc))
            state.record("budget", "exhausted", issues=[issue], budget=state.budget.snapshot())
            raise ValueError(str(exc)) from exc

    def _model_attempts(self, result):
        metadata = getattr(result, "metadata", {}) or {}
        backend = metadata.get("backend_metadata", {}) or {}
        attempts = backend.get("attempts", [])
        return max(1, len(attempts))

    def _needs_schema_retry(self, filling_report):
        return filling_report.title_score <= 0.0 or filling_report.header_score <= 0.0

    def _format_filling_error(self, filling_report):
        return FillingAgent.format_filling_error(self, filling_report)

    def _low_filling_dimensions(self, filling_report):
        return FillingAgent.low_filling_dimensions(self, filling_report)
from dataclasses import asdict
