import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.patch_verification.model import PatchVerificationError, public_sha256
from tools.patch_verification.patch import apply_bounded_patch, materialize_fixture
from tools.patch_verification.model import EffectAudit
from tools.patch_verification.profiles import (
    TRUSTED_PROFILE,
    TRUSTED_PROFILE_DIGEST,
    compare_baseline_and_changed,
    run_trusted_profile,
)


ROOT = Path(__file__).resolve().parents[2]
SUITE = json.loads((ROOT / "fixtures/forgeops-patch-verification/suite.json").read_text(encoding="utf-8"))
OBSERVED = "2026-08-19T00:05:00Z"


class TrustedProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.source = base / "source"
        self.changed = base / "changed"
        files = SUITE["base_fixture"]["files"]
        materialize_fixture(self.source, files)
        materialize_fixture(self.changed, files)

    def run_profile(self, root, **overrides):
        arguments = {
            "profile_id": TRUSTED_PROFILE["profile_id"],
            "profile_digest": TRUSTED_PROFILE_DIGEST,
            "observed_at": OBSERVED,
            "validation_at": OBSERVED,
        }
        arguments.update(overrides)
        return run_trusted_profile(root, **arguments)

    def test_profile_identity_order_and_digest_are_code_owned(self):
        self.assertEqual(
            ("TASK_TEST", "REGRESSION_TEST", "LINT", "TYPECHECK"),
            tuple(item["id"] for item in TRUSTED_PROFILE["checks"]),
        )
        self.assertEqual(public_sha256(TRUSTED_PROFILE), TRUSTED_PROFILE_DIGEST)

    def test_baseline_known_failure_and_changed_success_have_closed_e2_evidence(self):
        baseline = self.run_profile(self.source)
        apply_bounded_patch(
            self.source,
            self.changed,
            SUITE["base_fixture"]["patch_intent"],
            audit=EffectAudit(),
        )
        changed = self.run_profile(self.changed)
        self.assertEqual(
            [("FAILED", "TASK_EXPECTATION_FAILED"), ("PASSED", "CHECK_PASSED"), ("PASSED", "CHECK_PASSED"), ("PASSED", "CHECK_PASSED")],
            [(item["status"], item["reason"]) for item in baseline["checks"]],
        )
        self.assertTrue(all(item["status"] == "PASSED" for item in changed["checks"]))
        self.assertEqual("PASSED", compare_baseline_and_changed(baseline, changed))
        for phase, result in (("baseline", baseline), ("changed", changed)):
            for item in result["checks"]:
                self.assertEqual(
                    {"check_id", "kind", "status", "reason", "evidence"}, set(item)
                )
                evidence = item["evidence"]
                self.assertEqual("E2", evidence["tier"])
                self.assertEqual("test", evidence["type"])
                self.assertEqual(OBSERVED, evidence["observed_at"])
                self.assertEqual(TRUSTED_PROFILE_DIGEST, evidence["profile_digest"])
                self.assertEqual(
                    f"EVID-W7-{item['check_id']}-{phase}", evidence["evidence_id"]
                )
                self.assertEqual(64, len(evidence["result_fingerprint"]))
                self.assertNotIn("exit_code", evidence)

    def test_profile_identity_digest_companion_and_time_fail_closed(self):
        cases = [
            ({"profile_id": "unknown"}, "PROFILE_IDENTITY_INVALID"),
            ({"profile_digest": "0" * 64}, "PROFILE_DIGEST_INVALID"),
            ({"observed_at": "2026-08-19T00:05:00+00:00"}, "EVIDENCE_FRESHNESS_INVALID"),
            ({"observed_at": "2026-08-19T00:10:01Z"}, "EVIDENCE_FRESHNESS_INVALID"),
        ]
        for overrides, code in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(PatchVerificationError) as caught:
                    self.run_profile(self.source, **overrides)
                self.assertEqual(code, caught.exception.code)
        companion = self.source / "verification-profile.json"
        companion.write_text('{"profile_id":"other","checks":[]}\n', encoding="utf-8")
        with self.assertRaises(PatchVerificationError) as caught:
            self.run_profile(self.source)
        self.assertEqual("VERIFICATION_PROFILE_CHANGED", caught.exception.code)

    def test_baseline_infrastructure_failure_is_unhealthy(self):
        (self.source / "src/calculator.py").write_text("def total(:\n", encoding="utf-8")
        baseline = self.run_profile(self.source)
        changed = copy.deepcopy(baseline)
        with self.assertRaises(PatchVerificationError) as caught:
            compare_baseline_and_changed(baseline, changed)
        self.assertEqual("BASELINE_UNHEALTHY", caught.exception.code)

    def test_changed_task_lint_type_and_regression_failures_are_distinct(self):
        baseline = self.run_profile(self.source)
        apply_bounded_patch(self.source, self.changed, SUITE["base_fixture"]["patch_intent"], audit=EffectAudit())
        changed = self.run_profile(self.changed)
        mutations = {
            "TASK_TEST": "TASK_CHECK_FAILED",
            "REGRESSION_TEST": "NEW_REGRESSION",
            "LINT": "LINT_FAILED",
            "TYPECHECK": "TYPECHECK_FAILED",
        }
        for check_id, expected in mutations.items():
            with self.subTest(check_id=check_id):
                altered = copy.deepcopy(changed)
                record = next(item for item in altered["checks"] if item["check_id"] == check_id)
                record["status"] = "FAILED"
                record["reason"] = f"{check_id}_FAILED"
                with self.assertRaises(PatchVerificationError) as caught:
                    compare_baseline_and_changed(baseline, altered)
                self.assertEqual(expected, caught.exception.code)


if __name__ == "__main__":
    unittest.main()
