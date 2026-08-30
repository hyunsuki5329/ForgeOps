import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator

from tests.phase1_safety.test_freshness import NOW, Phase1ArtifactBoundaryTests
from tools.phase1_safety import verify
from tools.phase1_safety.audit import decide_phase1_safety
from tools.phase1_safety.model import SourceIdentity, canonical_json_bytes
from tools.phase1_safety.registry import load_registry


ROOT = Path(__file__).resolve().parents[2]
SUITE = json.loads((ROOT / "fixtures/forgeops-phase1-safety/suite.json").read_text(encoding="utf-8"))
REGISTRATIONS = load_registry(SUITE)


def _prepared(root: Path):
    expected_identity, runner = Phase1ArtifactBoundaryTests()._source(root)
    identity = SourceIdentity(
        expected_identity.repository,
        expected_identity.repository_id,
        expected_identity.default_branch,
        expected_identity.workflow_ref,
        expected_identity.source_sha,
        expected_identity.workflow_sha,
        expected_identity.run_id,
        expected_identity.run_attempt,
    )
    kwargs = {
        "registrations": REGISTRATIONS,
        "validated_at": NOW,
        "source_identity": identity,
        "binding_resolver": lambda _root, _binding: "b" * 64,
        "source_checker": lambda _root, _identity: True,
        "receipt_validator": lambda _root, _identity, _when: True,
    }
    return identity, runner, kwargs


class Phase1SafetyGateTests(unittest.TestCase):
    def test_valid_reaudited_input_is_exact_ready_nineteen_of_nineteen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _identity, _runner, kwargs = _prepared(root)
            decision = decide_phase1_safety(root, **kwargs)

        self.assertEqual("READY", decision["status"])
        self.assertEqual("E3", decision["evidence_tier"])
        self.assertEqual({"total": 19, "passed": 19, "failed": 0, "blockers": 0}, decision["summary"])
        self.assertEqual(19, len(decision["gates"]))
        self.assertEqual([], decision["blockers"])
        self.assertFalse(any(decision["effect_counters"].values()))

    def test_tampered_reducer_summary_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _identity, _runner, kwargs = _prepared(root)
            target = root / "artifacts/verification/phase-1-security-negative-result.json"
            saved = json.loads(target.read_text(encoding="utf-8"))
            saved["summary"]["passed"] = 19
            saved["summary"]["failed"] = 1
            target.write_text(json.dumps(saved), encoding="utf-8")
            decision = decide_phase1_safety(root, **kwargs)

        self.assertEqual("NOT_READY", decision["status"])
        self.assertIn("REDUCER_RESULT_MISMATCH", {item["reason_code"] for item in decision["blockers"]})

    def test_missing_stale_or_effectful_source_is_not_ready(self):
        cases = ("missing", "stale", "effect")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _identity, _runner, kwargs = _prepared(root)
                registration = next(item for item in REGISTRATIONS if item.command_id == "task-checks")
                target = root / registration.artifact_ref
                if case == "missing":
                    target.unlink()
                else:
                    value = json.loads(target.read_text(encoding="utf-8"))
                    if case == "stale":
                        value["observed_at"] = "2026-08-28T23:54:59Z"
                    else:
                        value["effect_counters"]["unauthorized_workspace_effects"] = 1
                    target.write_text(json.dumps(value), encoding="utf-8")
                decision = decide_phase1_safety(root, **kwargs)
                self.assertEqual("NOT_READY", decision["status"])
                self.assertGreater(decision["summary"]["blockers"], 0)

    def test_decision_is_canonical_and_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _identity, _runner, kwargs = _prepared(root)
            first = decide_phase1_safety(root, **kwargs)
            second = decide_phase1_safety(root, **kwargs)

        self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))

    def test_decision_uses_one_snapshot_when_original_changes_mid_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _identity, _runner, kwargs = _prepared(root)
            target = root / "artifacts/verification/phase-1-security-negative-result.json"

            def mutate_original_after_snapshot(_snapshot_root, _identity, _when):
                saved = json.loads(target.read_text(encoding="utf-8"))
                saved["summary"]["passed"] = 0
                target.write_text(json.dumps(saved), encoding="utf-8")
                return True

            kwargs["receipt_validator"] = mutate_original_after_snapshot
            decision = decide_phase1_safety(root, **kwargs)

        self.assertEqual("READY", decision["status"])

    def test_registered_gate_cli_writes_one_schema_valid_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity, _runner, _kwargs = _prepared(root)
            for relative in (
                "contracts/forgeops-phase1-safety/1.0/schema.json",
                "fixtures/forgeops-phase1-safety/suite.json",
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            argv = [
                "--schema", "contracts/forgeops-phase1-safety/1.0/schema.json",
                "--suite", "fixtures/forgeops-phase1-safety/suite.json",
                "--result", "artifacts/verification/phase-1-safety-gate-result.json",
                "--report-md", "artifacts/reviews/phase-1-safety-scorecard.md",
                "--report-html", "artifacts/reviews/phase-1-safety-scorecard.html",
                "--command-id", "phase1-safety-gate",
            ]
            exit_code = verify.main(
                argv,
                root=root,
                validated_at=NOW,
                source_identity=identity,
                binding_resolver=lambda _root, _binding: "b" * 64,
                source_checker=lambda _root, _identity: True,
                receipt_validator=lambda _root, _identity, _when: True,
            )
            result = json.loads((root / "artifacts/verification/phase-1-safety-gate-result.json").read_text(encoding="utf-8"))
            schema = json.loads((root / "contracts/forgeops-phase1-safety/1.0/schema.json").read_text(encoding="utf-8"))
            gate_schema = {"$ref": "#/$defs/gateResult", "$defs": schema["$defs"]}

        self.assertEqual(0, exit_code)
        self.assertEqual([], list(Draft202012Validator(gate_schema).iter_errors(result)))

    def test_started_gate_failure_removes_an_earlier_ready_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity, _runner, _kwargs = _prepared(root)
            contract = root / "contracts/forgeops-phase1-safety/1.0/schema.json"
            suite = root / "fixtures/forgeops-phase1-safety/suite.json"
            contract.parent.mkdir(parents=True, exist_ok=True)
            suite.parent.mkdir(parents=True, exist_ok=True)
            contract.write_text("{}", encoding="utf-8")
            suite.write_bytes((ROOT / "fixtures/forgeops-phase1-safety/suite.json").read_bytes())
            targets = (
                root / "artifacts/verification/phase-1-safety-gate-result.json",
                root / "artifacts/reviews/phase-1-safety-scorecard.md",
                root / "artifacts/reviews/phase-1-safety-scorecard.html",
            )
            for target in targets:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("old-ready", encoding="utf-8")
            exit_code = verify.main(
                [
                    "--schema", "contracts/forgeops-phase1-safety/1.0/schema.json",
                    "--suite", "fixtures/forgeops-phase1-safety/suite.json",
                    "--result", "artifacts/verification/phase-1-safety-gate-result.json",
                    "--report-md", "artifacts/reviews/phase-1-safety-scorecard.md",
                    "--report-html", "artifacts/reviews/phase-1-safety-scorecard.html",
                    "--command-id", "phase1-safety-gate",
                ],
                root=root,
                validated_at=NOW,
                source_identity=identity,
            )
            outputs_exist = [target.exists() for target in targets]

        self.assertEqual(2, exit_code)
        self.assertFalse(any(outputs_exist))


if __name__ == "__main__":
    unittest.main()
