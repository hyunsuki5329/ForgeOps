import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator

from tools.phase1_safety import verify
from tools.phase1_safety.audit import reduce_security_negative
from tools.phase1_safety.model import SourceIdentity
from tools.phase1_safety.registry import load_registry


ROOT = Path(__file__).resolve().parents[2]
SUITE = json.loads((ROOT / "fixtures/forgeops-phase1-safety/suite.json").read_text(encoding="utf-8"))
REGISTRATIONS = load_registry(SUITE)
SECURITY_COMMANDS = tuple(SUITE["subsets"]["security_negative"])
NOW = datetime(2026, 8, 29, 0, 0, 0, tzinfo=timezone.utc)
NOW_TEXT = "2026-08-29T00:00:00Z"
IDENTITY = SourceIdentity(
    repository="example/forgeops",
    repository_id="123",
    default_branch="main",
    workflow_ref="refs/heads/main",
    source_sha="a" * 40,
    workflow_sha="a" * 40,
    run_id="1001",
    run_attempt=1,
)


def _set_dotted(value: dict, dotted: str, replacement: object) -> None:
    current = value
    parts = dotted.split(".")
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = replacement


def _fixture_root(directory: str) -> tuple[Path, dict[str, dict]]:
    root = Path(directory)
    artifacts: dict[str, dict] = {}
    for registration in REGISTRATIONS:
        if registration.command_id not in SECURITY_COMMANDS:
            continue
        value = json.loads((ROOT / registration.artifact_ref).read_text(encoding="utf-8"))
        value[registration.observed_at_field] = NOW_TEXT
        for field in registration.hash_fields:
            _set_dotted(value, field, "b" * 64)
        target = root / registration.artifact_ref
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding="utf-8")
        artifacts[registration.command_id] = value
    return root, artifacts


def _run(root: Path) -> dict:
    return reduce_security_negative(
        root,
        registrations=REGISTRATIONS,
        validated_at=NOW,
        source_identity=IDENTITY,
        binding_resolver=lambda _root, _binding: "b" * 64,
        source_checker=lambda _root, _identity: True,
    )


def _install_contract(root: Path) -> None:
    for relative in (
        "contracts/forgeops-phase1-safety/1.0/schema.json",
        "fixtures/forgeops-phase1-safety/suite.json",
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())


class SecurityNegativeReducerTests(unittest.TestCase):
    def test_exact_twenty_artifacts_reduce_to_public_zero_effect_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = _fixture_root(directory)
            result = _run(root)

        self.assertEqual("PASSED", result["status"])
        self.assertEqual({"total": 20, "passed": 20, "failed": 0, "blockers": 0}, result["summary"])
        self.assertEqual(20, len(result["gates"]))
        self.assertEqual([], result["blockers"])
        self.assertEqual({
            "unauthorized_executions": 0,
            "approval_bypasses": 0,
            "containment_or_egress_escapes": 0,
            "injection_acceptances": 0,
            "raw_secret_occurrences": 0,
            "cleanup_failures": 0,
            "evidence_integrity_failures": 0,
            "external_writes": 0,
        }, result["effect_counters"])
        rendered = json.dumps(result, sort_keys=True)
        self.assertNotIn('"cases"', rendered)
        self.assertNotIn("FORGEOPS_TEST_SENTINEL", rendered)

    def test_each_normalized_effect_blocks_the_reducer(self):
        mutations = (
            ("task-checks", "effect_counters.unauthorized_workspace_effects", 1, "unauthorized_executions"),
            ("approval-negative-fixture", "assertions.negative_zero_dispatcher_calls", False, "approval_bypasses"),
            ("containment-egress-negative", "status", "FAILED", "containment_or_egress_escapes"),
            ("injection-negative", "status", "FAILED", "injection_acceptances"),
            ("secret-surface-negative", "assertions.negative_raw_occurrences", 1, "raw_secret_occurrences"),
            ("teardown-negative", "residue_counters.processes", 1, "cleanup_failures"),
            ("evidence-positive-negative", "assertions.negative_accept_calls", 1, "evidence_integrity_failures"),
            ("external-write-negative", "effect_counters.external_write_attempts", 1, "external_writes"),
        )
        for command_id, field, value, counter in mutations:
            with self.subTest(command_id=command_id), tempfile.TemporaryDirectory() as directory:
                root, artifacts = _fixture_root(directory)
                _set_dotted(artifacts[command_id], field, value)
                registration = next(item for item in REGISTRATIONS if item.command_id == command_id)
                (root / registration.artifact_ref).write_text(json.dumps(artifacts[command_id]), encoding="utf-8")
                result = _run(root)
                self.assertEqual("FAILED", result["status"])
                self.assertGreater(result["effect_counters"][counter], 0)
                self.assertIn("NEGATIVE_EFFECT_OBSERVED", {item["reason_code"] for item in result["blockers"]})

    def test_missing_malformed_unknown_and_wrong_identity_fail_closed(self):
        cases = []
        with tempfile.TemporaryDirectory() as directory:
            root, artifacts = _fixture_root(directory)
            registration = next(item for item in REGISTRATIONS if item.command_id == "task-checks")
            target = root / registration.artifact_ref

            target.unlink()
            cases.append(_run(root))

            target.write_text("{", encoding="utf-8")
            cases.append(_run(root))

            unknown = copy.deepcopy(artifacts["task-checks"])
            unknown["unknown"] = True
            target.write_text(json.dumps(unknown), encoding="utf-8")
            cases.append(_run(root))

            wrong = copy.deepcopy(artifacts["task-checks"])
            wrong["command_id"] = "regression-checks"
            target.write_text(json.dumps(wrong), encoding="utf-8")
            cases.append(_run(root))

        for result in cases:
            self.assertEqual("FAILED", result["status"])
            self.assertGreater(result["summary"]["blockers"], 0)

    def test_structurally_incomplete_e3_artifact_returns_failed_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root, artifacts = _fixture_root(directory)
            registration = next(item for item in REGISTRATIONS if item.command_id == "teardown-negative")
            artifacts["teardown-negative"].pop("residue_counters")
            (root / registration.artifact_ref).write_text(json.dumps(artifacts["teardown-negative"]), encoding="utf-8")
            result = _run(root)

        self.assertEqual("FAILED", result["status"])
        gate = next(item for item in result["gates"] if item["command_id"] == "teardown-negative")
        self.assertIn("ARTIFACT_INVALID", gate["blocker_codes"])

    def test_stale_future_low_tier_and_hash_mismatch_fail_closed(self):
        mutations = (
            ("task-checks", "observed_at", "2026-08-28T23:54:59Z"),
            ("task-checks", "observed_at", "2026-08-29T00:00:01Z"),
            ("task-checks", "evidence_tier", "E1"),
            ("task-checks", "input_hashes.schema", "c" * 64),
        )
        for command_id, field, value in mutations:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root, artifacts = _fixture_root(directory)
                _set_dotted(artifacts[command_id], field, value)
                registration = next(item for item in REGISTRATIONS if item.command_id == command_id)
                (root / registration.artifact_ref).write_text(json.dumps(artifacts[command_id]), encoding="utf-8")
                result = _run(root)
                self.assertEqual("FAILED", result["status"])
                self.assertGreater(result["summary"]["blockers"], 0)

    def test_required_counter_type_is_not_coerced(self):
        for value in (None, "0", False, -1, 2**64):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                root, artifacts = _fixture_root(directory)
                _set_dotted(artifacts["task-checks"], "effect_counters.unauthorized_workspace_effects", value)
                registration = next(item for item in REGISTRATIONS if item.command_id == "task-checks")
                (root / registration.artifact_ref).write_text(json.dumps(artifacts["task-checks"]), encoding="utf-8")
                result = _run(root)
                self.assertEqual("FAILED", result["status"])

    def test_nested_active_remote_environment_and_secret_surfaces_are_rejected(self):
        mutations = (
            ("actual", "https://example.invalid/result"),
            ("actual", "<script>alert(1)</script>"),
            ("actual", "FORGEOPS_PRIVATE_VALUE"),
            ("token", "redacted"),
        )
        for key, value in mutations:
            with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as directory:
                root, artifacts = _fixture_root(directory)
                artifacts["task-checks"]["cases"][0][key] = value
                registration = next(item for item in REGISTRATIONS if item.command_id == "task-checks")
                (root / registration.artifact_ref).write_text(json.dumps(artifacts["task-checks"]), encoding="utf-8")
                result = _run(root)
                gate = next(item for item in result["gates"] if item["command_id"] == "task-checks")
                self.assertFalse(gate["public_safe"])
                self.assertIn("ARTIFACT_NOT_PUBLIC_SAFE", gate["blocker_codes"])

    def test_registered_cli_writes_schema_valid_result_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = _fixture_root(directory)
            _install_contract(root)
            argv = [
                "--schema", "contracts/forgeops-phase1-safety/1.0/schema.json",
                "--suite", "fixtures/forgeops-phase1-safety/suite.json",
                "--result", "artifacts/verification/phase-1-security-negative-result.json",
                "--command-id", "phase1-security-negative",
            ]
            exit_code = verify.main(
                argv,
                root=root,
                validated_at=NOW,
                source_identity=IDENTITY,
                binding_resolver=lambda _root, _binding: "b" * 64,
                source_checker=lambda _root, _identity: True,
            )
            result = json.loads((root / "artifacts/verification/phase-1-security-negative-result.json").read_text(encoding="utf-8"))
            schema = json.loads((root / "contracts/forgeops-phase1-safety/1.0/schema.json").read_text(encoding="utf-8"))
            result_schema = {"$ref": "#/$defs/reducerResult", "$defs": schema["$defs"]}

        self.assertEqual(0, exit_code)
        self.assertEqual([], list(Draft202012Validator(result_schema).iter_errors(result)))

    def test_wrong_cli_identity_preserves_existing_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = _fixture_root(directory)
            _install_contract(root)
            target = root / "artifacts/verification/phase-1-security-negative-result.json"
            target.write_text('{"sentinel":true}\n', encoding="utf-8")
            exit_code = verify.main(
                [
                    "--schema", "contracts/forgeops-phase1-safety/1.0/schema.json",
                    "--suite", "fixtures/forgeops-phase1-safety/suite.json",
                    "--result", "artifacts/verification/substitute.json",
                    "--command-id", "phase1-security-negative",
                ],
                root=root,
                validated_at=NOW,
                source_identity=IDENTITY,
                binding_resolver=lambda _root, _binding: "b" * 64,
                source_checker=lambda _root, _identity: True,
            )
            preserved = target.read_text(encoding="utf-8")

        self.assertEqual(2, exit_code)
        self.assertEqual('{"sentinel":true}\n', preserved)


if __name__ == "__main__":
    unittest.main()
