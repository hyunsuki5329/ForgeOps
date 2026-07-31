"""Tests for the Phase 0 exit registry contract."""

from __future__ import annotations

import json
import hashlib
import shutil
import argparse
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from tools.phase_exit import verify


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts/forgeops-phase-exit-contract/1.0/schema.json"
SUITE_PATH = ROOT / "fixtures/forgeops-phase-exit/phase-0-suite.json"
VALIDATION_AT = "2026-07-26T00:00:00Z"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_suite() -> dict:
    return json.loads(SUITE_PATH.read_text(encoding="utf-8"))


def walk(value: object):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from walk(nested)


def set_nested(mapping: dict, dotted_path: str, value: object) -> None:
    target = mapping
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def temporary_complete_bundle(test_case: unittest.TestCase) -> tuple[Path, dict]:
    """Create only public, fresh, hash-pinned results for every registration."""
    directory = Path(tempfile.mkdtemp())
    test_case.addCleanup(shutil.rmtree, directory, True)
    suite = json.loads(json.dumps(load_suite()))
    for registration in suite["registrations"]:
        for input_ref in registration["input_refs"]:
            input_path = directory / input_ref
            input_path.parent.mkdir(parents=True, exist_ok=True)
            input_path.write_text(input_ref, encoding="utf-8")
        if registration["gate_id"] == "VG-008":
            artifact = {
                "category": "SANDBOX_RUNTIME_AVAILABLE",
                "command_id": registration["command_id"],
                "counts": {"cases_total": 1, "failed": 0, "not_run": 0, "passed": 1},
                "e3_runtime_assertion": True,
                "effect_counters": {"network_calls": 0, "provision_calls": 0, "write_calls": 0},
                "input_hashes": {},
                "residue_counters": {"leases": 0, "mounts": 0, "processes": 0, "transient_secrets": 0, "workspaces": 0},
                "result_version": "1.0",
                "runtime": "docker",
                "status": "PASSED",
                "time": VALIDATION_AT,
            }
        else:
            artifact = {
                "gate_id": registration["gate_id"],
                "profile_id": registration["profile_id"],
                "command_id": registration["command_id"],
                "status": "PASSED",
                "observed_at": VALIDATION_AT,
                "evidence_tier": registration["required_tier"],
            }
        for input_ref, hash_field in registration["hash_fields"].items():
            digest = hashlib.sha256((directory / input_ref).read_bytes()).hexdigest()
            set_nested(artifact, hash_field, digest)
        artifact_path = directory / registration["artifact_ref"]
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    return directory, suite


def mutate_artifact(root: Path, suite: dict, index: int, **changes: object) -> None:
    path = root / suite["registrations"][index]["artifact_ref"]
    artifact = json.loads(path.read_text(encoding="utf-8"))
    artifact.update(changes)
    path.write_text(json.dumps(artifact), encoding="utf-8")


def mutate_command_artifact(root: Path, suite: dict, command_id: str, **changes: object) -> None:
    index = next(i for i, item in enumerate(suite["registrations"]) if item["command_id"] == command_id)
    mutate_artifact(root, suite, index, **changes)


def blocker_codes(result: dict) -> set[str]:
    return {blocker["reason_code"] for blocker in result["blockers"]}


class PhaseExitSchemaTests(unittest.TestCase):
    def test_all_objects_are_closed(self):
        """An added schema property must be rejected by the closed contract."""
        schema = load_schema()
        objects = [node for node in walk(schema) if node.get("type") == "object"]
        self.assertTrue(objects)
        self.assertTrue(all(node.get("additionalProperties") is False for node in objects))


class RegistryTests(unittest.TestCase):
    def test_phase_zero_registry_has_exact_18_commands(self):
        """A missing, reordered, duplicate, or unplanned command must be detected."""
        suite = load_suite()
        observed = [(r["gate_id"], r["command_id"]) for r in suite["registrations"]]
        self.assertEqual(list(verify.EXPECTED_COMMANDS), observed)
        self.assertEqual(18, len(observed))
        self.assertEqual(18, len(set(observed)))

    def test_registration_refs_are_project_relative_and_closed(self):
        """A registry reference must remain a non-wildcard public project path."""
        suite = load_suite()
        for registration in suite["registrations"]:
            self.assertEqual(
                set(registration),
                {
                    "gate_id",
                    "profile_id",
                    "command_id",
                    "artifact_ref",
                    "required_tier",
                    "input_refs",
                    "hash_fields",
                },
            )
            refs = [registration["artifact_ref"], *registration["input_refs"]]
            self.assertTrue(all(not Path(ref).is_absolute() for ref in refs))
            self.assertTrue(all("*" not in ref and "?" not in ref for ref in refs))
            self.assertEqual(set(registration["input_refs"]), set(registration["hash_fields"]))

    def test_canonical_catalog_rejects_tuple_and_floor_substitution(self):
        """A weakened registered floor must never become a new Phase 0 baseline."""
        suite = load_suite()
        suite["registrations"][14]["required_tier"] = "E0"
        suite["registrations"][14]["profile_id"] = "forgeops-untrusted"

        with self.assertRaisesRegex(verify.PhaseExitError, "PHASE_EXIT_REGISTRY_CATALOG_MISMATCH"):
            verify.validate_registry(suite)


class AggregationTests(unittest.TestCase):
    def test_registered_public_envelopes_pass_without_vg008_runtime_capability(self):
        """Existing public verifier envelopes are admitted by their registered adapter."""
        suite = load_suite()
        for registration in suite["registrations"]:
            if registration["gate_id"] == "VG-008":
                continue
            artifact = json.loads((ROOT / registration["artifact_ref"]).read_text(encoding="utf-8"))
            gate_result, blockers = verify.inspect_registration(
                ROOT,
                registration,
                artifact["observed_at"],
            )
            with self.subTest(command_id=registration["command_id"]):
                self.assertEqual("PASSED", gate_result["status"])
                self.assertFalse(blockers)

    def test_missing_artifact_is_not_ready(self):
        root, suite = temporary_complete_bundle(self)
        (root / suite["registrations"][0]["artifact_ref"]).unlink()

        result = verify.aggregate_phase_zero(root, suite, VALIDATION_AT)

        self.assertEqual("NOT_READY", result["status"])
        self.assertIn("PHASE_EXIT_ARTIFACT_MISSING", blocker_codes(result))

    def test_stale_and_future_results_are_not_ready(self):
        for observed_at, code in (
            ("2026-07-25T23:54:59Z", "PHASE_EXIT_EVIDENCE_STALE"),
            ("2026-07-26T00:00:01Z", "PHASE_EXIT_EVIDENCE_FUTURE"),
        ):
            with self.subTest(observed_at=observed_at):
                root, suite = temporary_complete_bundle(self)
                mutate_artifact(root, suite, 0, observed_at=observed_at)

                result = verify.aggregate_phase_zero(root, suite, VALIDATION_AT)

                self.assertEqual("NOT_READY", result["status"])
                self.assertIn(code, blocker_codes(result))

    def test_one_not_run_sandbox_result_blocks_ready(self):
        root, suite = temporary_complete_bundle(self)
        mutate_command_artifact(root, suite, "teardown-negative", status="NOT_RUN")

        result = verify.aggregate_phase_zero(root, suite, VALIDATION_AT)

        self.assertEqual("NOT_READY", result["status"])
        self.assertIn("PHASE_EXIT_STATUS_NOT_RUN", blocker_codes(result))

    def test_hash_identity_tier_and_unsafe_artifacts_are_blockers(self):
        root, suite = temporary_complete_bundle(self)
        mutate_artifact(root, suite, 0, gate_id="VG-999")
        mutate_artifact(root, suite, 1, evidence_tier="E1")
        mutate_artifact(root, suite, 2, raw_log="__SYNTHETIC__")
        input_path = root / suite["registrations"][3]["input_refs"][0]
        input_path.write_text("changed input", encoding="utf-8")

        result = verify.aggregate_phase_zero(root, suite, VALIDATION_AT)

        codes = blocker_codes(result)
        self.assertEqual("NOT_READY", result["status"])
        self.assertTrue(
            {
                "PHASE_EXIT_IDENTITY_MISMATCH",
                "PHASE_EXIT_EVIDENCE_TIER_INSUFFICIENT",
                "PHASE_EXIT_PUBLIC_UNSAFE",
                "PHASE_EXIT_INPUT_HASH_MISMATCH",
            }.issubset(codes)
        )

    def test_nested_query_credential_is_not_public_safe(self):
        root, suite = temporary_complete_bundle(self)
        artifact_path = root / suite["registrations"][0]["artifact_ref"]
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["hashes"]["metadata"] = {"callback": "https://example.test/check?token=redacted"}
        artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

        result = verify.aggregate_phase_zero(root, suite, VALIDATION_AT)

        self.assertEqual("NOT_READY", result["status"])
        self.assertIn("PHASE_EXIT_PUBLIC_UNSAFE", blocker_codes(result))

    def test_malformed_artifact_time_keeps_closed_decision_schema_valid(self):
        root, suite = temporary_complete_bundle(self)
        mutate_artifact(root, suite, 0, observed_at="not-a-timestamp")

        result = verify.aggregate_phase_zero(root, suite, VALIDATION_AT)
        errors = list(Draft202012Validator(load_schema()).iter_errors(result))

        self.assertEqual("NOT_READY", result["status"])
        self.assertFalse(errors, [error.message for error in errors])

    def test_vg008_not_run_envelope_uses_registered_time_hash_and_runtime_tier_shape(self):
        root, suite = temporary_complete_bundle(self)
        registration = next(item for item in suite["registrations"] if item["command_id"] == "teardown-negative")
        mutate_command_artifact(root, suite, "teardown-negative", status="NOT_RUN")
        artifact = json.loads((root / registration["artifact_ref"]).read_text(encoding="utf-8"))

        gate_result, blockers = verify.inspect_registration(root, registration, artifact["time"])

        self.assertEqual("NOT_RUN", gate_result["status"])
        self.assertEqual(artifact["time"], gate_result["observed_at"])
        self.assertTrue(gate_result["input_hashes_valid"])
        self.assertEqual("E3", gate_result["required_tier"])
        self.assertEqual(["PHASE_EXIT_STATUS_NOT_RUN"], [item["reason_code"] for item in blockers])

    def test_complete_fresh_public_bundle_is_ready(self):
        root, suite = temporary_complete_bundle(self)

        result = verify.aggregate_phase_zero(root, suite, VALIDATION_AT)

        self.assertEqual("READY", result["status"])
        self.assertEqual(
            {"required": 18, "passed": 18, "failed": 0, "not_run": 0, "blocked": 0},
            result["summary"],
        )
        self.assertFalse(result["blockers"])


class ReportTests(unittest.TestCase):
    def test_not_ready_report_names_blockers_and_never_says_exit_achieved(self):
        root, suite = temporary_complete_bundle(self)
        mutate_artifact(root, suite, 0, observed_at="2026-07-25T23:54:59Z")
        result = verify.aggregate_phase_zero(root, suite, VALIDATION_AT)

        report = verify.render_report(result)

        self.assertIn("NOT_READY", report)
        self.assertIn("PHASE_EXIT_EVIDENCE_STALE", report)
        self.assertNotIn("Phase 0 Exit conditions satisfied", report)

    def test_ready_report_is_derived_only_from_closed_result(self):
        root, suite = temporary_complete_bundle(self)
        result = verify.aggregate_phase_zero(root, suite, VALIDATION_AT)

        report = verify.render_report(result)

        self.assertIn("18/18", report)
        self.assertIn("READY", report)
        self.assertIn("Phase 0 Exit conditions satisfied", report)

    def test_renderer_rejects_unsafe_gate_value_even_when_called_directly(self):
        root, suite = temporary_complete_bundle(self)
        result = verify.aggregate_phase_zero(root, suite, VALIDATION_AT)
        result["gate_results"][0]["profile_id"] = "C:\\private\\profile"

        with self.assertRaisesRegex(verify.PhaseExitError, "PHASE_EXIT_PUBLIC_UNSAFE"):
            verify.render_report(result)


class AtomicWriteTests(unittest.TestCase):
    def test_atomic_writer_creates_nested_target_with_exact_text(self):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        target = directory / "nested" / "phase-0-exit-report.md"

        verify.write_text_atomically(target, "public report\n")

        self.assertEqual("public report\n", target.read_text(encoding="utf-8"))


class CliRunnerTests(unittest.TestCase):
    def registered_namespace(self, **overrides: str):
        values = {
            "schema": "contracts/forgeops-phase-exit-contract/1.0/schema.json",
            "suite": "fixtures/forgeops-phase-exit/phase-0-suite.json",
            "result": "artifacts/verification/phase-0-exit-result.json",
            "report": "artifacts/reviews/phase-0-exit-report.md",
            "command_id": "phase0-exit-gate",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_report_and_result_paths_are_exact(self):
        args = self.registered_namespace(report="artifacts/reviews/other.md")

        with self.assertRaisesRegex(verify.PhaseExitError, "PHASE_EXIT_RUNNER_CONTRACT_INVALID"):
            verify.validate_registered_paths(args)

    def test_cli_writes_not_ready_for_missing_artifact(self):
        temporary_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temporary_root, True)
        for relative in ("contracts", "fixtures"):
            shutil.copytree(ROOT / relative, temporary_root / relative)
        result_path = temporary_root / "artifacts/verification/phase-0-exit-result.json"
        report_path = temporary_root / "artifacts/reviews/phase-0-exit-report.md"

        exit_code = verify.run_cli(
            schema="contracts/forgeops-phase-exit-contract/1.0/schema.json",
            suite="fixtures/forgeops-phase-exit/phase-0-suite.json",
            result="artifacts/verification/phase-0-exit-result.json",
            report="artifacts/reviews/phase-0-exit-report.md",
            command_id="phase0-exit-gate",
            project_root=temporary_root,
        )
        result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(1, exit_code)
        self.assertEqual("NOT_READY", result["status"])
        self.assertTrue(report_path.is_file())

    def test_runner_contract_failure_writes_closed_outputs_to_trusted_targets(self):
        temporary_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temporary_root, True)
        result_path = temporary_root / "artifacts/verification/phase-0-exit-result.json"
        report_path = temporary_root / "artifacts/reviews/phase-0-exit-report.md"

        exit_code = verify.run_cli(
            schema="contracts/other.json",
            suite="fixtures/forgeops-phase-exit/phase-0-suite.json",
            result="artifacts/verification/phase-0-exit-result.json",
            report="artifacts/reviews/phase-0-exit-report.md",
            command_id="phase0-exit-gate",
            project_root=temporary_root,
            validation_at=VALIDATION_AT,
        )

        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(1, exit_code)
        self.assertEqual("NOT_READY", result["status"])
        self.assertIn("PHASE_EXIT_RUNNER_CONTRACT_INVALID", report_path.read_text(encoding="utf-8"))
        self.assertNotIn("Traceback", report_path.read_text(encoding="utf-8"))

    def test_parse_failure_writes_closed_outputs_without_parser_text(self):
        temporary_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temporary_root, True)
        original_root = verify._ROOT
        verify._ROOT = temporary_root
        self.addCleanup(setattr, verify, "_ROOT", original_root)
        result_path = temporary_root / "artifacts/verification/phase-0-exit-result.json"
        report_path = temporary_root / "artifacts/reviews/phase-0-exit-report.md"

        exit_code = verify.main([
            "--schema", "contracts/forgeops-phase-exit-contract/1.0/schema.json",
            "--suite", "fixtures/forgeops-phase-exit/phase-0-suite.json",
            "--result", "artifacts/verification/phase-0-exit-result.json",
            "--report", "artifacts/reviews/phase-0-exit-report.md",
            "--command-id", "phase0-exit-gate",
            "--unexpected",
        ])

        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(1, exit_code)
        self.assertEqual("NOT_READY", result["status"])
        self.assertIn("PHASE_EXIT_RUNNER_CONTRACT_INVALID", report_path.read_text(encoding="utf-8"))
