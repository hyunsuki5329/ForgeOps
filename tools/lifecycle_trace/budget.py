from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable

from .model import CANONICAL_NAME, CANONICAL_REF, SHA256, LifecycleError, canonical_hash


@dataclass(frozen=True)
class BudgetLimits:
    time_ms: int
    tokens: int
    tool_calls: int
    command_calls: int
    repair_attempts: int
    cost_microunits: int

    def __post_init__(self) -> None:
        if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0
               for value in self.__dict__.values()):
            raise LifecycleError("BUDGET_INPUT_INVALID")


@dataclass
class BudgetUsage:
    tokens: int = 0
    tool_calls: int = 0
    command_calls: int = 0
    repair_attempts: int = 0
    cost_microunits: int = 0

    def __getitem__(self, dimension: str) -> int:
        if dimension not in ERRORS:
            raise KeyError(dimension)
        return getattr(self, dimension)

    def as_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in ERRORS}


ERRORS = {
    "tokens": "BUDGET_TOKEN_EXCEEDED",
    "tool_calls": "BUDGET_TOOL_EXCEEDED",
    "command_calls": "BUDGET_COMMAND_EXCEEDED",
    "repair_attempts": "BUDGET_REPAIR_EXCEEDED",
    "cost_microunits": "BUDGET_COST_EXCEEDED",
}


class BudgetController:
    def __init__(self, limits: BudgetLimits, *, clock_ms: Callable[[], int]):
        self.limits = limits
        self._clock_ms = clock_ms
        self._started_at = clock_ms()
        self.state = "ACTIVE"
        self.stop_reason: str | None = None
        self.usage = BudgetUsage()

    def _stop(self, code: str) -> None:
        self.state = "STOPPED"
        self.stop_reason = code

    def stop(self, code: str) -> None:
        if not isinstance(code, str) or not CANONICAL_NAME.fullmatch(code):
            raise LifecycleError("BUDGET_INPUT_INVALID")
        if self.state == "ACTIVE":
            self._stop(code)

    def authorize_dispatch(self) -> None:
        if self.state != "ACTIVE":
            raise LifecycleError("DISPATCH_FORBIDDEN")
        if self._clock_ms() - self._started_at > self.limits.time_ms:
            self._stop("BUDGET_TIME_EXCEEDED")
            raise LifecycleError("BUDGET_TIME_EXCEEDED")

    def reserve(self, dimension: str, amount: int = 1) -> None:
        if dimension not in ERRORS or not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise LifecycleError("BUDGET_INPUT_INVALID")
        self.authorize_dispatch()
        projected = self.usage[dimension] + amount
        if projected > getattr(self.limits, dimension):
            code = ERRORS[dimension]
            self._stop(code)
            raise LifecycleError(code)
        setattr(self.usage, dimension, projected)

    def reserve_many(self, reservations: dict[str, int]) -> None:
        if not isinstance(reservations, dict) or not reservations:
            raise LifecycleError("BUDGET_INPUT_INVALID")
        self.authorize_dispatch()
        if any(dimension not in ERRORS or not isinstance(amount, int)
               or isinstance(amount, bool) or amount <= 0
               for dimension, amount in reservations.items()):
            raise LifecycleError("BUDGET_INPUT_INVALID")
        projected: dict[str, int] = {}
        for dimension in ERRORS:
            if dimension not in reservations:
                continue
            amount = reservations[dimension]
            projected[dimension] = self.usage[dimension] + amount
            if projected[dimension] > getattr(self.limits, dimension):
                code = ERRORS[dimension]
                self._stop(code)
                raise LifecycleError(code)
        for dimension, value in projected.items():
            setattr(self.usage, dimension, value)

    def snapshot(self) -> dict[str, object]:
        return {"state": self.state, "stop_reason": self.stop_reason,
                "elapsed_ms": max(0, self._clock_ms() - self._started_at),
                "usage": self.usage.as_dict(), "limits": dict(self.limits.__dict__)}


class NoProgressGuard:
    def __init__(self, *, limit: int, budget: BudgetController):
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise LifecycleError("PROGRESS_INPUT_INVALID")
        self.limit = limit
        self.budget = budget
        self._fingerprint: str | None = None
        self._repeat_count = 0

    def observe(self, signature: str, evidence_refs: tuple[str, ...], diff_hash: str,
                *, trusted: bool) -> bool:
        if (not isinstance(signature, str) or not CANONICAL_NAME.fullmatch(signature)
                or not isinstance(evidence_refs, tuple) or not evidence_refs
                or any(not isinstance(ref, str) or not CANONICAL_REF.fullmatch(ref)
                       or not ref.startswith("EVID-") for ref in evidence_refs)
                or len(set(evidence_refs)) != len(evidence_refs)
                or not isinstance(diff_hash, str) or not SHA256.fullmatch(diff_hash)
                or not isinstance(trusted, bool)):
            raise LifecycleError("PROGRESS_INPUT_INVALID")

        fingerprint = canonical_hash({"signature": signature,
                                      "evidence_refs": list(evidence_refs),
                                      "diff_hash": diff_hash})
        if trusted and fingerprint != self._fingerprint:
            self._fingerprint = fingerprint
            self._repeat_count = 0
            return True

        self._repeat_count += 1
        if self._repeat_count >= self.limit:
            self.budget.stop("NO_PROGRESS_STOPPED")
            raise LifecycleError("NO_PROGRESS_STOPPED")
        return False
