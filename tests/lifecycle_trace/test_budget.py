import unittest

from tools.lifecycle_trace.budget import BudgetController, BudgetLimits, BudgetUsage, NoProgressGuard
from tools.lifecycle_trace.model import LifecycleError


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.limits = BudgetLimits(1000, 100, 4, 3, 2, 500)
        self.budget = BudgetController(self.limits, clock_ms=lambda: self.now)

    def test_each_dimension_stops_before_over_limit(self):
        dimensions = {
            "tokens": (101, "BUDGET_TOKEN_EXCEEDED"),
            "tool_calls": (5, "BUDGET_TOOL_EXCEEDED"),
            "command_calls": (4, "BUDGET_COMMAND_EXCEEDED"),
            "repair_attempts": (3, "BUDGET_REPAIR_EXCEEDED"),
            "cost_microunits": (501, "BUDGET_COST_EXCEEDED"),
        }
        for dimension, (amount, code) in dimensions.items():
            with self.subTest(dimension=dimension):
                budget = BudgetController(self.limits, clock_ms=lambda: 0)
                with self.assertRaisesRegex(LifecycleError, code):
                    budget.reserve(dimension, amount)
                self.assertEqual("STOPPED", budget.state)
                self.assertEqual(0, budget.usage[dimension])

    def test_time_is_checked_before_dispatch(self):
        self.now = 1001
        with self.assertRaisesRegex(LifecycleError, "BUDGET_TIME_EXCEEDED"):
            self.budget.authorize_dispatch()
        with self.assertRaisesRegex(LifecycleError, "DISPATCH_FORBIDDEN"):
            self.budget.authorize_dispatch()

    def test_budget_precedence_and_exact_limit(self):
        self.budget.reserve("repair_attempts", 2)
        self.assertEqual(2, self.budget.usage["repair_attempts"])
        with self.assertRaisesRegex(LifecycleError, "BUDGET_REPAIR_EXCEEDED"):
            self.budget.reserve("repair_attempts", 1)

    def test_unknown_or_nonpositive_reservation_is_rejected(self):
        for dimension, amount in (("unknown", 1), ("tokens", 0), ("tokens", -1),
                                  ("tokens", True), ("tokens", 1.5)):
            with self.subTest(dimension=dimension, amount=amount):
                budget = BudgetController(self.limits, clock_ms=lambda: 0)
                with self.assertRaisesRegex(LifecycleError, "BUDGET_INPUT_INVALID"):
                    budget.reserve(dimension, amount)

    def test_batch_reservation_is_atomic_and_usage_is_closed(self):
        self.assertIsInstance(self.budget.usage, BudgetUsage)
        with self.assertRaisesRegex(LifecycleError, "BUDGET_COMMAND_EXCEEDED"):
            self.budget.reserve_many({"tokens": 10, "command_calls": 4})
        self.assertEqual(0, self.budget.usage.tokens)
        self.assertEqual(0, self.budget.usage.command_calls)
        budget = BudgetController(self.limits, clock_ms=lambda: 0)
        with self.assertRaisesRegex(LifecycleError, "BUDGET_TOKEN_EXCEEDED"):
            budget.reserve_many({"command_calls": 4, "tokens": 101})
        self.assertEqual(BudgetUsage(), budget.usage)

    def test_bool_or_noninteger_limit_is_rejected(self):
        for value in (True, 1.5):
            with self.subTest(value=value):
                with self.assertRaisesRegex(LifecycleError, "BUDGET_INPUT_INVALID"):
                    BudgetLimits(value, 100, 4, 3, 2, 500)


class NoProgressTests(unittest.TestCase):
    def setUp(self):
        self.budget = BudgetController(BudgetLimits(1000, 100, 4, 3, 2, 500), clock_ms=lambda: 0)
        self.guard = NoProgressGuard(limit=2, budget=self.budget)

    def test_changed_trusted_signature_resets_repeat_count(self):
        self.assertTrue(self.guard.observe("CHECK_A", ("EVID-A",), "a" * 64, trusted=True))
        self.assertTrue(self.guard.observe("CHECK_B", ("EVID-B",), "b" * 64, trusted=True))
        self.assertFalse(self.guard.observe("CHECK_B", ("EVID-B",), "b" * 64, trusted=True))

    def test_two_identical_observations_stop_and_close_dispatch(self):
        self.guard.observe("CHECK_A", ("EVID-A",), "a" * 64, trusted=True)
        self.assertFalse(self.guard.observe("CHECK_A", ("EVID-A",), "a" * 64, trusted=True))
        with self.assertRaisesRegex(LifecycleError, "NO_PROGRESS_STOPPED"):
            self.guard.observe("CHECK_A", ("EVID-A",), "a" * 64, trusted=True)
        with self.assertRaisesRegex(LifecycleError, "DISPATCH_FORBIDDEN"):
            self.budget.authorize_dispatch()

    def test_untrusted_progress_cannot_reset_repeat_count(self):
        self.guard.observe("CHECK_A", ("EVID-A",), "a" * 64, trusted=True)
        self.assertFalse(self.guard.observe("CHECK_B", ("EVID-B",), "b" * 64, trusted=False))
        with self.assertRaisesRegex(LifecycleError, "NO_PROGRESS_STOPPED"):
            self.guard.observe("CHECK_C", ("EVID-C",), "c" * 64, trusted=False)

    def test_noncanonical_progress_inputs_are_rejected(self):
        bad = (("check a", ("EVID-A",), "a" * 64), ("CHECK_A", ("bad",), "a" * 64),
               ("CHECK_A", ("EVID-A",), "xyz"))
        for signature, evidence, diff_hash in bad:
            with self.subTest(signature=signature):
                with self.assertRaisesRegex(LifecycleError, "PROGRESS_INPUT_INVALID"):
                    self.guard.observe(signature, evidence, diff_hash, trusted=True)


if __name__ == "__main__":
    unittest.main()
