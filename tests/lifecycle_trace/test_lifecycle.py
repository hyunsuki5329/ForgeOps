import unittest

from tools.lifecycle_trace.budget import BudgetController, BudgetLimits
from tools.lifecycle_trace.lifecycle import LifecycleRun, ResourceLedger
from tools.lifecycle_trace.model import LifecycleError


def budget():
    return BudgetController(BudgetLimits(1000, 100, 4, 3, 2, 500), clock_ms=lambda: 0)


class LifecycleTests(unittest.TestCase):
    def test_cancel_closes_dispatch_and_cleans_all_adapter_resources(self):
        run = LifecycleRun(budget())
        for kind in ResourceLedger.KINDS:
            run.resources.acquire(kind, f"{kind}-1")
        receipt = run.cancel("USER_CANCELLED")
        self.assertEqual("CANCELLED", run.state)
        self.assertEqual({kind: 0 for kind in ResourceLedger.KINDS}, receipt["remaining"])
        with self.assertRaisesRegex(LifecycleError, "RUN_CANCELLED"):
            run.authorize_dispatch()

    def test_cleanup_is_idempotent_and_receipt_is_stable(self):
        run = LifecycleRun(budget())
        run.resources.acquire("leases", "LEASE-1")
        first = run.cleanup()
        second = run.cleanup()
        self.assertEqual(first, second)
        self.assertEqual(1, first["released"]["leases"])

    def test_each_residue_has_a_stable_error(self):
        errors = {
            "processes": "PROCESS_RESIDUE", "mounts": "MOUNT_RESIDUE",
            "leases": "LEASE_RESIDUE", "transient_secrets": "SECRET_RESIDUE",
            "workspaces": "WORKSPACE_RESIDUE",
        }
        for kind, code in errors.items():
            with self.subTest(kind=kind):
                ledger = ResourceLedger(cleanup_failures={kind})
                run = LifecycleRun(budget(), resources=ledger)
                ledger.acquire(kind, f"{kind}-1")
                with self.assertRaisesRegex(LifecycleError, code):
                    run.cleanup()

    def test_residue_precedence_is_resource_order(self):
        ledger = ResourceLedger(cleanup_failures={"mounts", "processes"})
        for kind in ("mounts", "processes"):
            ledger.acquire(kind, kind)
        with self.assertRaisesRegex(LifecycleError, "PROCESS_RESIDUE"):
            LifecycleRun(budget(), resources=ledger).cleanup()

    def test_mutated_cleanup_receipt_is_detected(self):
        run = LifecycleRun(budget())
        run.cleanup()
        run._cleanup_receipt["remaining"]["leases"] = 1
        with self.assertRaisesRegex(LifecycleError, "CLEANUP_NOT_IDEMPOTENT"):
            run.cleanup()

    def test_unknown_resource_and_duplicate_identity_are_rejected(self):
        ledger = ResourceLedger()
        with self.assertRaisesRegex(LifecycleError, "RESOURCE_INPUT_INVALID"):
            ledger.acquire("unknown", "X")
        ledger.acquire("leases", "LEASE-1")
        with self.assertRaisesRegex(LifecycleError, "RESOURCE_INPUT_INVALID"):
            ledger.acquire("leases", "LEASE-1")

    def test_budget_failure_becomes_terminal_and_is_not_cancelled(self):
        now = 0
        controller = BudgetController(BudgetLimits(1, 100, 4, 3, 2, 500), clock_ms=lambda: now)
        run = LifecycleRun(controller)
        now = 2
        with self.assertRaisesRegex(LifecycleError, "BUDGET_TIME_EXCEEDED"):
            run.authorize_dispatch()
        self.assertEqual("STOPPED", run.state)
        self.assertEqual("BUDGET_TIME_EXCEEDED", run.terminal_reason)


if __name__ == "__main__":
    unittest.main()
