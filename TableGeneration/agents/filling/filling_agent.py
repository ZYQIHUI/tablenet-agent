from copy import deepcopy

from ..construction.fallback_constructor import FallbackConstructor
from ..domain.errors import RepairAction
from ..domain.state import CandidateState
from ..orchestration.repair_router import RepairRouter
from ..transformations.augmentation_pipeline import AugmentationPipeline
from .candidate_pool import CandidatePool
from .candidate_selector import CandidateSelector


class FillingAgent:
    """Owns schema candidates, filling retries, validation, and selection."""

    def __init__(
            self,
            schema_agent,
            header_agent,
            body_agent,
            validator,
            checker,
            html_builder,
            max_schema_retries=3,
            max_filling_retries=2,
            candidate_count=1,
            augmentation_count=0,
            repair_router=None,
            candidate_selector=None,
            fallback_constructor=None,
            inner_memory=None,
            style_agent=None):
        self.schema_agent = schema_agent
        self.header_agent = header_agent
        self.body_agent = body_agent
        self.validator = validator
        self.checker = checker
        self.html_builder = html_builder
        self.max_schema_retries = max_schema_retries
        self.max_filling_retries = max_filling_retries
        self.candidate_count = max(1, int(candidate_count))
        self.augmentation_count = max(0, min(4, int(augmentation_count)))
        self.repair_router = repair_router or RepairRouter()
        self.candidate_selector = candidate_selector or CandidateSelector()
        self.fallback_constructor = fallback_constructor or FallbackConstructor()
        self.inner_memory = inner_memory
        self.style_agent = style_agent

    def generate(self, state):
        self._recorded_results = set()
        last_schema_errors = []
        last_filling_report = None
        candidate_pool = CandidatePool()

        for schema_attempt in range(1, self.max_schema_retries + 1):
            state.increment("schema_attempts")
            base_schema = self.schema_agent.build(state.plan)
            ok, errors = self.validator.validate(base_schema)
            if not ok:
                last_schema_errors = errors
                decision = self.repair_router.for_structure_errors(errors)
                if schema_attempt < self.max_schema_retries:
                    state.record(
                        "schema",
                        decision.action.value,
                        attempt=schema_attempt,
                        issues=decision.issues,
                    )
                    continue
                fallback = self.fallback_constructor.construct(
                    base_schema,
                    errors=errors,
                    target_rows=state.plan.rows,
                    target_cols=state.plan.cols,
                    preserve_content=True,
                )
                fallback_ok, fallback_errors = self.validator.validate(fallback.schema)
                state.record(
                    "schema",
                    "fallback" if fallback_ok else decision.action.value,
                    attempt=schema_attempt,
                    issues=decision.issues,
                    fallback_ok=fallback_ok,
                    fallback_errors=fallback_errors,
                    cell_mapping=fallback.cell_mapping,
                    preserved_cell_ids=fallback.preserved_cell_ids,
                )
                if not fallback_ok:
                    last_schema_errors = fallback_errors
                    continue
                base_schema = fallback.schema

            rebuild_schema = False
            for candidate_index in range(1, self.candidate_count + 1):
                working_schema = deepcopy(base_schema)
                repair_decision = None
                for filling_attempt in range(1, self.max_filling_retries + 1):
                    state.increment("filling_attempts")
                    schema = deepcopy(working_schema)
                    schema = self._fill_or_repair(schema, state.plan, repair_decision)
                    self._record_filler_result(state, self.header_agent, filling_attempt)
                    self._record_filler_result(state, self.body_agent, filling_attempt)
                    candidate = CandidateState(
                        schema=schema,
                        generation_source="ordinary",
                        metadata={"candidate_index": candidate_index},
                    )
                    state.consume("candidates")
                    state.candidates.append(candidate)

                    ok, errors = self.validator.validate(schema)
                    candidate.validation_result = {"ok": ok, "errors": list(errors)}
                    if not ok:
                        last_schema_errors = errors
                        decision = self.repair_router.for_structure_errors(errors)
                        state.record(
                            "filling_validation",
                            decision.action.value,
                            attempt=filling_attempt,
                            candidate_id=candidate.candidate_id,
                            issues=decision.issues,
                            candidate_index=candidate_index,
                        )
                        rebuild_schema = True
                        break

                    report = self.checker.evaluate(schema, state.plan)
                    self._record_semantic_evaluator(state, filling_attempt)
                    candidate.checker_report = report
                    scores = self.candidate_selector.score(candidate)
                    if scores.passed:
                        signature = candidate_pool.signature(candidate.schema)
                        globally_duplicate = (
                            self.inner_memory is not None
                            and self.inner_memory.has_schema(signature)
                        )
                        if globally_duplicate:
                            candidate.metadata.update({
                                "signature": signature,
                                "duplicate": True,
                                "rejection_reason": "dataset_memory_duplicate",
                            })
                            if self.inner_memory is not None:
                                self.inner_memory.remember_rejection(
                                    candidate.candidate_id,
                                    {"reason": "dataset_memory_duplicate", "signature": signature},
                                )
                            state.record(
                                "candidate_pool",
                                "reject_dataset_duplicate",
                                attempt=filling_attempt,
                                candidate_id=candidate.candidate_id,
                                candidate_index=candidate_index,
                            )
                        elif candidate_pool.add(candidate):
                            state.record(
                                "candidate_pool",
                                "accept",
                                attempt=filling_attempt,
                                candidate_id=candidate.candidate_id,
                                candidate_index=candidate_index,
                                scores=scores.as_dict(),
                            )
                        else:
                            if self.inner_memory is not None:
                                self.inner_memory.remember_rejection(
                                    candidate.candidate_id,
                                    {"reason": "duplicate_candidate"},
                                )
                            state.record(
                                "candidate_pool",
                                "reject_duplicate",
                                attempt=filling_attempt,
                                candidate_id=candidate.candidate_id,
                                candidate_index=candidate_index,
                            )
                        break

                    last_filling_report = report
                    if self.inner_memory is not None:
                        self.inner_memory.remember_rejection(
                            candidate.candidate_id,
                            {
                                "reason": "quality_gate_failed",
                                "core_scores": scores.as_dict(),
                            },
                        )
                        for reason in list(report.errors)[:5]:
                            self.inner_memory.remember_failure(
                                reason,
                                {"candidate_id": candidate.candidate_id},
                            )
                    decision = self.repair_router.for_filling_report(report)
                    state.record(
                        "filling",
                        decision.action.value,
                        attempt=filling_attempt,
                        candidate_id=candidate.candidate_id,
                        issues=decision.issues,
                        score=report.score,
                        core_scores=scores.as_dict(),
                        target_cells=list(decision.target_cells),
                        target_columns=list(decision.target_columns),
                        candidate_index=candidate_index,
                    )
                    if decision.action == RepairAction.REBUILD_SCHEMA:
                        rebuild_schema = True
                        break
                    working_schema = schema
                    repair_decision = decision
                if rebuild_schema:
                    break

            selected = self.candidate_selector.select(candidate_pool.candidates)
            if selected is not None and self.augmentation_count:
                augmentation = AugmentationPipeline(
                    self.validator,
                    self.checker,
                    self.candidate_selector,
                )
                augmented = augmentation.generate(
                    selected,
                    state.plan,
                    limit=self.augmentation_count,
                )
                for candidate in augmented:
                    state.consume("candidates")
                    state.candidates.append(candidate)
                    passed = candidate.metadata.get("passed_hard_gate", False)
                    added = passed and candidate_pool.add(candidate)
                    state.record(
                        "augmentation",
                        "accept" if added else "reject",
                        candidate_id=candidate.candidate_id,
                        parent_candidate_id=candidate.parent_candidate_id,
                        transformation=candidate.transformation,
                        validation=candidate.validation_result,
                        scores=candidate.metadata.get("core_scores"),
                        rejection_reason=candidate.metadata.get("rejection_reason"),
                    )
                selected = self.candidate_selector.select(candidate_pool.candidates)
            if selected is not None:
                state.select(selected)
                state.record(
                    "candidate_selection",
                    "select",
                    candidate_id=selected.candidate_id,
                    candidate_count=len(candidate_pool.candidates),
                    ordinary_candidate_target=self.candidate_count,
                    augmentation_target=self.augmentation_count,
                    reason=selected.metadata["selection_reason"],
                    scores=selected.metadata["core_scores"],
                )
                if self.style_agent is not None:
                    try:
                        state.style = self.style_agent.build(state.plan, selected.schema)
                    except TypeError as exc:
                        if "positional argument" not in str(exc):
                            raise
                        state.style = self.style_agent.build(state.plan)
                table = self.html_builder.build(state.plan, selected.schema, state.style)
                if self.inner_memory is not None:
                    signature = selected.metadata.get("signature") or candidate_pool.signature(selected.schema)
                    self.inner_memory.remember_schema(
                        signature,
                        {
                            "request_id": state.request_id,
                            "candidate_id": selected.candidate_id,
                            "topic": state.plan.topic,
                        },
                    )
                state.result = table
                return table

        if last_schema_errors and last_filling_report is None:
            raise ValueError("invalid table schema: " + "; ".join(last_schema_errors))
        if last_filling_report is not None:
            raise ValueError(self.format_filling_error(last_filling_report))
        raise ValueError("failed to generate a valid table")

    def _fill_or_repair(self, schema, plan, decision):
        if decision is None:
            schema = self._call_filler(self.header_agent, schema, plan)
            return self._call_filler(self.body_agent, schema, plan)

        if decision.action == RepairAction.REPAIR_HEADER:
            schema = self._call_filler(
                self.header_agent,
                schema,
                plan,
                target_cells=decision.target_cells,
                target_columns=decision.target_columns,
                preserve_existing=True,
            )
            return self._call_filler(
                self.body_agent,
                schema,
                plan,
                target_columns=decision.target_columns,
                preserve_existing=True,
            )

        if decision.action in (RepairAction.REPAIR_CELLS, RepairAction.REPAIR_COLUMNS):
            return self._call_filler(
                self.body_agent,
                schema,
                plan,
                target_cells=decision.target_cells,
                target_columns=decision.target_columns,
                preserve_existing=True,
            )

        return self._call_filler(
            self.body_agent,
            schema,
            plan,
            preserve_existing=False,
        )

    def _call_filler(self, filler, schema, plan, **repair_scope):
        try:
            return filler.fill(schema, plan, **repair_scope)
        except TypeError as exc:
            if not repair_scope or "unexpected keyword argument" not in str(exc):
                raise
            return filler.fill(schema, plan)

    def _record_filler_result(self, state, filler, attempt):
        result = getattr(filler, "last_result", None)
        if result is None:
            return
        result_key = id(result)
        if result_key in self._recorded_results:
            return
        self._recorded_results.add(result_key)
        if getattr(filler, "use_llm", False):
            state.consume("model_calls", self._model_attempts(result))
        state.record(
            filler.__class__.__name__,
            result.status.value,
            attempt=attempt,
            issues=result.errors,
            source=result.source.value,
            result_metadata=result.metadata,
        )

    def _record_semantic_evaluator(self, state, attempt):
        evaluator = getattr(self.checker, "semantic_evaluator", None)
        result = getattr(evaluator, "last_result", None)
        if result is None:
            return
        result_key = id(result)
        if result_key in self._recorded_results:
            return
        self._recorded_results.add(result_key)
        state.consume("model_calls", self._model_attempts(result))
        state.record(
            "SemanticEvaluator",
            result.status.value,
            attempt=attempt,
            issues=result.errors,
            source=result.source.value,
            result_metadata=result.metadata,
        )

    def _model_attempts(self, result):
        backend = (result.metadata.get("backend_metadata", {}) or {})
        attempts = backend.get("attempts", [])
        return max(1, len(attempts))

    def format_filling_error(self, report):
        low_dimensions = self.low_filling_dimensions(report)
        low_dimension_text = ""
        if low_dimensions:
            low_dimension_text = ", low_dimensions=" + ",".join(low_dimensions)
        issues = list(report.errors) or list(report.warnings)
        issue_text = "; ".join(issues[:5]) if issues else "no detailed filling issue reported"
        return (
            "invalid table filling "
            f"(score={report.score:.3f}, "
            f"title={report.title_score:.3f}, "
            f"header={report.header_score:.3f}, "
            f"body={report.body_score:.3f}, "
            f"topic_consistency={getattr(report, 'topic_consistency_score', 1.0):.3f}"
            f"{low_dimension_text}): "
            + issue_text
        )

    def low_filling_dimensions(self, report):
        scores = getattr(report, "dimension_scores", None) or {
            "title": report.title_score,
            "header": report.header_score,
            "body": report.body_score,
            "topic_consistency": getattr(report, "topic_consistency_score", 1.0),
        }
        return [
            f"{name}:{score:.3f}"
            for name, score in sorted(scores.items(), key=lambda item: item[1])
            if score < 0.6
        ][:3]
