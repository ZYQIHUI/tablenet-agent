from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple

from ..capabilities.protocols import CapabilityRequest
from ..domain.errors import ErrorCode, ValidationIssue
from ..domain.results import AgentResult, AgentSource, AgentStatus
from .registry import BackendRegistry


@dataclass(frozen=True)
class BackendRoute:
    primary: str
    fallbacks: Tuple[str, ...] = ()


class BackendRouter:
    def __init__(self, registry: BackendRegistry, routes: Optional[Dict[str, BackendRoute]] = None):
        self.registry = registry
        self.routes = dict(routes or {})

    def set_route(self, capability: str, primary: str, fallbacks: Iterable[str] = ()) -> None:
        self.routes[capability] = BackendRoute(primary=primary, fallbacks=tuple(fallbacks))

    def execute(self, request: CapabilityRequest) -> AgentResult[Any]:
        route = self.routes.get(request.capability)
        if route is None:
            raise KeyError(f"no backend route configured for capability: {request.capability}")

        attempts = []
        last_result = None
        for backend_name in (route.primary,) + route.fallbacks:
            backend = self.registry.get(backend_name)
            if not backend.supports(request.capability):
                attempts.append({"backend": backend_name, "status": "unsupported"})
                continue
            try:
                result = backend.execute(request)
            except Exception as exc:
                attempts.append({"backend": backend_name, "status": "failed", "reason": str(exc)})
                last_result = AgentResult.failed(
                    source=AgentSource.MIXED,
                    errors=[ValidationIssue(ErrorCode.LLM_CALL_FAILED, str(exc))],
                    backend=backend_name,
                )
                continue
            attempts.append({"backend": backend_name, "status": result.status.value})
            last_result = result
            if result.ok:
                if backend_name != route.primary or result.status == AgentStatus.FALLBACK:
                    result.status = AgentStatus.FALLBACK
                result.metadata.setdefault("requested_backend", route.primary)
                result.metadata["actual_backend"] = backend_name
                result.metadata["attempts"] = attempts
                return result

        if last_result is None:
            last_result = AgentResult.failed(
                source=AgentSource.MIXED,
                errors=[ValidationIssue(ErrorCode.UNSUPPORTED_REQUEST, "no backend supports capability")],
            )
        last_result.metadata.setdefault("requested_backend", route.primary)
        last_result.metadata["attempts"] = attempts
        return last_result
