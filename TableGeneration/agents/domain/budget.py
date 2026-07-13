from dataclasses import dataclass
from time import monotonic


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class BudgetLimits:
    max_model_calls: int = 100
    max_elapsed_seconds: float = 300.0
    max_schema_attempts: int = 3
    max_filling_attempts: int = 20
    max_candidates: int = 20


class BudgetTracker:
    def __init__(self, limits=None):
        self.limits = limits or BudgetLimits()
        self.started_at = monotonic()
        self.usage = {
            "model_calls": 0,
            "schema_attempts": 0,
            "filling_attempts": 0,
            "candidates": 0,
        }

    @property
    def elapsed_seconds(self):
        return max(0.0, monotonic() - self.started_at)

    def consume(self, resource: str, amount: int = 1):
        if resource not in self.usage:
            raise KeyError(f"unknown budget resource: {resource}")
        self.usage[resource] += amount
        self.check()

    def check(self):
        checks = {
            "model_calls": self.limits.max_model_calls,
            "schema_attempts": self.limits.max_schema_attempts,
            "filling_attempts": self.limits.max_filling_attempts,
            "candidates": self.limits.max_candidates,
        }
        for resource, maximum in checks.items():
            if maximum >= 0 and self.usage[resource] > maximum:
                raise BudgetExceeded(
                    f"budget exhausted: {resource}={self.usage[resource]} exceeds {maximum}"
                )
        if self.limits.max_elapsed_seconds >= 0 and self.elapsed_seconds > self.limits.max_elapsed_seconds:
            raise BudgetExceeded(
                f"budget exhausted: elapsed_seconds={self.elapsed_seconds:.3f} "
                f"exceeds {self.limits.max_elapsed_seconds:.3f}"
            )

    def snapshot(self):
        return {
            **self.usage,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "limits": {
                "max_model_calls": self.limits.max_model_calls,
                "max_elapsed_seconds": self.limits.max_elapsed_seconds,
                "max_schema_attempts": self.limits.max_schema_attempts,
                "max_filling_attempts": self.limits.max_filling_attempts,
                "max_candidates": self.limits.max_candidates,
            },
        }
