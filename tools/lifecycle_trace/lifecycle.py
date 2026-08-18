from __future__ import annotations

from copy import deepcopy
import re

from .budget import BudgetController
from .model import LifecycleError, canonical_hash


RESOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class ResourceLedger:
    KINDS = ("processes", "mounts", "leases", "transient_secrets", "workspaces")
    RESIDUE_ERRORS = {
        "processes": "PROCESS_RESIDUE",
        "mounts": "MOUNT_RESIDUE",
        "leases": "LEASE_RESIDUE",
        "transient_secrets": "SECRET_RESIDUE",
        "workspaces": "WORKSPACE_RESIDUE",
    }

    def __init__(self, *, cleanup_failures: set[str] | None = None):
        failures = set(cleanup_failures or ())
        if not failures.issubset(self.KINDS):
            raise LifecycleError("RESOURCE_INPUT_INVALID")
        self._items = {kind: set() for kind in self.KINDS}
        self._cleanup_failures = failures

    def acquire(self, kind: str, resource_id: str) -> None:
        if (kind not in self._items or not isinstance(resource_id, str)
                or not RESOURCE_ID.fullmatch(resource_id)
                or resource_id in self._items[kind]):
            raise LifecycleError("RESOURCE_INPUT_INVALID")
        self._items[kind].add(resource_id)

    def counts(self) -> dict[str, int]:
        return {kind: len(self._items[kind]) for kind in self.KINDS}

    def release_all(self) -> dict[str, object]:
        released: dict[str, int] = {}
        for kind in self.KINDS:
            released[kind] = 0 if kind in self._cleanup_failures else len(self._items[kind])
            if kind not in self._cleanup_failures:
                self._items[kind].clear()
        remaining = self.counts()
        for kind in self.KINDS:
            if remaining[kind]:
                raise LifecycleError(self.RESIDUE_ERRORS[kind])
        return {"released": released, "remaining": remaining}


class LifecycleRun:
    def __init__(self, budget: BudgetController, *, resources: ResourceLedger | None = None):
        self.budget = budget
        self.resources = resources or ResourceLedger()
        self.state = "ACTIVE"
        self.terminal_reason: str | None = None
        self._cleanup_receipt: dict[str, object] | None = None
        self._cleanup_hash: str | None = None

    def authorize_dispatch(self) -> None:
        if self.state == "CANCELLED":
            raise LifecycleError("RUN_CANCELLED")
        if self.state != "ACTIVE":
            raise LifecycleError("DISPATCH_FORBIDDEN")
        try:
            self.budget.authorize_dispatch()
        except LifecycleError as error:
            self.state = "STOPPED"
            self.terminal_reason = error.code
            raise

    def cleanup(self) -> dict[str, object]:
        if self._cleanup_receipt is not None:
            if canonical_hash(self._cleanup_receipt) != self._cleanup_hash:
                raise LifecycleError("CLEANUP_NOT_IDEMPOTENT")
            return deepcopy(self._cleanup_receipt)
        receipt = self.resources.release_all()
        self._cleanup_receipt = receipt
        self._cleanup_hash = canonical_hash(receipt)
        return deepcopy(receipt)

    def cancel(self, reason: str = "USER_CANCELLED") -> dict[str, object]:
        if self.state == "CANCELLED":
            return self.cleanup()
        if self.state != "ACTIVE":
            raise LifecycleError("DISPATCH_FORBIDDEN")
        self.state = "CANCELLED"
        self.terminal_reason = reason
        self.budget.stop("RUN_CANCELLED")
        return self.cleanup()

    def complete(self) -> dict[str, object]:
        if self.state != "ACTIVE":
            raise LifecycleError("DISPATCH_FORBIDDEN")
        receipt = self.cleanup()
        self.state = "COMPLETED"
        self.terminal_reason = "SUCCESS"
        self.budget.stop("SUCCESS")
        return receipt
