"""Schema and fixture-catalog tests for the evidence contract."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from argparse import Namespace


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts/forgeops-evidence-contract/1.0/schema.json"
SUITE_PATH = ROOT / "fixtures/forgeops-evidence-contract/suite.json"

EVIDENCE_CASES = (
    ("positive-file-revision", "PASSED"),
    ("positive-command-time", "PASSED"),
    ("negative-type-case", "EVIDENCE_TYPE_INVALID"),
    ("negative-tier-case", "EVIDENCE_TIER_INVALID"),
    ("negative-file-with-time", "EVIDENCE_FRESHNESS_INVALID"),
    ("negative-command-with-revision", "EVIDENCE_FRESHNESS_INVALID"),
    ("negative-stale-time", "EVIDENCE_FRESHNESS_INVALID"),
    ("negative-future-time", "EVIDENCE_FRESHNESS_INVALID"),
    ("negative-dangling-ref", "EVIDENCE_REFERENCE_INVALID"),
    ("negative-duplicate-ref", "EVIDENCE_REFERENCE_INVALID"),
)

PROVENANCE_CASES = (
    ("positive-plugin-provenance", "PASSED"),
    ("positive-static-provenance", "PASSED"),
    ("negative-producer-kind", "EVIDENCE_PROVENANCE_INVALID"),
    ("negative-task-mismatch", "EVIDENCE_PROVENANCE_INVALID"),
    ("negative-run-mismatch", "EVIDENCE_PROVENANCE_INVALID"),
    ("negative-source-hash", "EVIDENCE_PROVENANCE_INVALID"),
    ("negative-duplicate-finding-ref", "EVIDENCE_PROVENANCE_INVALID"),
    ("negative-authority-field", "EVIDENCE_SCHEMA_INVALID"),
)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def load_schema() -> dict:
    return load_json(SCHEMA_PATH)


def walk(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


class EvidenceSchemaTests(unittest.TestCase):
    def test_schema_closes_every_object(self):
        schema = load_schema()
        objects = [node for node in walk(schema) if node.get("type") == "object"]
        self.assertTrue(objects)
        self.assertTrue(all(node.get("additionalProperties") is False for node in objects))

    def test_evidence_enums_are_exact(self):
        schema = load_schema()
        record = schema["$defs"]["EvidenceRecord"]
        self.assertEqual(
            ["file", "diff", "command", "test", "render", "runtime", "approval"],
            record["properties"]["type"]["enum"],
        )
        self.assertEqual(["E0", "E1", "E2", "E3"], record["properties"]["tier"]["enum"])

    def test_record_definitions_are_closed_and_required(self):
        schema = load_schema()
        evidence = schema["$defs"]["EvidenceRecord"]
        provenance = schema["$defs"]["ExtensionProvenanceRecord"]
        self.assertIs(False, evidence["additionalProperties"])
        self.assertEqual(
            {"id", "tier", "type", "source_ref", "observation", "evidence_refs"},
            set(evidence["required"]),
        )
        self.assertIs(False, provenance["additionalProperties"])
        self.assertEqual(
            {
                "provenance_id",
                "producer_kind",
                "task_id",
                "run_id",
                "source_ref",
                "source_sha256",
                "finding_refs",
            },
            set(provenance["required"]),
        )


class CatalogTests(unittest.TestCase):
    def test_duplicate_catalog_ids_are_rejected(self):
        from jsonschema import Draft202012Validator

        schema = load_schema()
        suite = load_json(SUITE_PATH)
        duplicate_catalog = copy.deepcopy(suite)
        duplicate_catalog["evidence_cases"][0]["catalog_ids"].append("EVID-001")

        errors = list(Draft202012Validator(schema).iter_errors(duplicate_catalog))

        self.assertTrue(errors)
        self.assertTrue(
            any(
                list(error.path) == ["evidence_cases", 0, "catalog_ids"]
                for error in errors
            )
        )

    def test_catalog_case_ids_and_expected_categories_are_exact(self):
        suite = load_json(SUITE_PATH)
        self.assertEqual(EVIDENCE_CASES, tuple((case["id"], case["expected"]) for case in suite["evidence_cases"]))
        self.assertEqual(PROVENANCE_CASES, tuple((case["id"], case["expected"]) for case in suite["provenance_cases"]))

    def test_suite_root_and_case_effect_counts_are_closed(self):
        suite = load_json(SUITE_PATH)
        self.assertEqual(
            {"suite_id", "suite_version", "validation_at", "base_revision", "evidence_cases", "provenance_cases"},
            set(suite),
        )
        for case in (*suite["evidence_cases"], *suite["provenance_cases"]):
            if case["kind"] != "negative":
                continue
            self.assertEqual(0, case["expected_accept_calls"])
            self.assertEqual(0, case["expected_append_calls"])
        for case in suite["evidence_cases"][:2]:
            self.assertEqual(1, case["expected_accept_calls"])
        for case in suite["provenance_cases"][:2]:
            self.assertEqual(1, case["expected_append_calls"])


class EvidenceEvaluatorTests(unittest.TestCase):
    @staticmethod
    def valid_command_evidence() -> dict:
        return {
            "id": "EVID-TEST",
            "tier": "E2",
            "type": "command",
            "source_ref": "python -m unittest tests.evidence_contract.test_verify",
            "observation": "focused evaluator test passed",
            "evidence_refs": [],
            "observed_at": "2026-07-26T00:04:00Z",
        }

    @staticmethod
    def valid_plugin_provenance() -> dict:
        return {
            "provenance_id": "PROV-TEST",
            "producer_kind": "plugin",
            "task_id": "TASK-001",
            "run_id": "RUN-001",
            "source_ref": "plugins/example/finding.json",
            "source_sha256": "637ba4f365de653abe58805066f69b5fc08aac8fc0f825fdff01fa040b9818cb",
            "finding_refs": ["FIND-TEST"],
        }

    def test_wrong_mode_freshness_is_rejected_before_accept(self):
        from tools.evidence_contract import verify

        record = self.valid_command_evidence()
        record["observed_revision"] = 7
        spy = verify.EffectSpy()

        with self.assertRaisesRegex(verify.EvidenceError, "EVIDENCE_FRESHNESS_INVALID"):
            verify.validate_evidence(
                record,
                base_revision=7,
                validation_at="2026-07-26T00:04:00Z",
                catalog_ids=[record["id"]],
                spy=spy,
            )

        self.assertEqual((0, 0), (spy.accept_calls, spy.append_calls))

    def test_noncanonical_timestamp_is_rejected_before_accept(self):
        from tools.evidence_contract import verify

        record = self.valid_command_evidence()
        record["observed_at"] = "2026-7-26T00:04:00Z"
        spy = verify.EffectSpy()

        with self.assertRaisesRegex(verify.EvidenceError, "EVIDENCE_FRESHNESS_INVALID"):
            verify.validate_evidence(
                record,
                base_revision=7,
                validation_at="2026-07-26T00:04:00Z",
                catalog_ids=[record["id"]],
                spy=spy,
            )

        self.assertEqual((0, 0), (spy.accept_calls, spy.append_calls))

    def test_negative_base_revision_is_rejected_before_accept(self):
        from tools.evidence_contract import verify

        record = self.valid_command_evidence()
        spy = verify.EffectSpy()

        with self.assertRaisesRegex(verify.EvidenceError, "EVIDENCE_FRESHNESS_INVALID"):
            verify.validate_evidence(
                record,
                base_revision=-1,
                validation_at="2026-07-26T00:04:00Z",
                catalog_ids=[record["id"]],
                spy=spy,
            )

        self.assertEqual((0, 0), (spy.accept_calls, spy.append_calls))

    def test_negative_observed_revision_is_rejected_before_accept(self):
        from tools.evidence_contract import verify

        record = {
            "id": "EVID-REVISION",
            "tier": "E2",
            "type": "file",
            "source_ref": "contracts/forgeops-evidence-contract/1.0/schema.json",
            "observation": "negative revision rejection",
            "evidence_refs": [],
            "observed_revision": -1,
        }
        spy = verify.EffectSpy()

        with self.assertRaisesRegex(verify.EvidenceError, "EVIDENCE_FRESHNESS_INVALID"):
            verify.validate_evidence(
                record,
                base_revision=7,
                validation_at="2026-07-26T00:04:00Z",
                catalog_ids=[record["id"]],
                spy=spy,
            )

        self.assertEqual((0, 0), (spy.accept_calls, spy.append_calls))

    def test_time_freshness_accepts_exact_zero_and_three_hundred_second_boundaries(self):
        from tools.evidence_contract import verify

        for observed_at in ("2026-07-26T00:04:00Z", "2026-07-25T23:59:00Z"):
            record = self.valid_command_evidence()
            record["observed_at"] = observed_at
            spy = verify.EffectSpy()

            verify.validate_evidence(
                record,
                base_revision=7,
                validation_at="2026-07-26T00:04:00Z",
                catalog_ids=[record["id"]],
                spy=spy,
            )

            self.assertEqual((1, 0), (spy.accept_calls, spy.append_calls))

    def test_invalid_evidence_fixture_cases_have_no_effects_and_stable_categories(self):
        from tools.evidence_contract import verify

        suite = load_json(SUITE_PATH)
        results = verify.run_cases("evidence-positive-negative", suite)

        self.assertEqual(
            [(case["id"], case["expected"]) for case in suite["evidence_cases"]],
            [(result["case_id"], result["actual"]) for result in results],
        )
        self.assertTrue(all(result["status"] == "PASSED" for result in results))
        for result in results[2:]:
            self.assertEqual((0, 0), (result["accept_calls"], result["append_calls"]))


    def test_provenance_hash_mismatch_never_appends(self):
        from tools.evidence_contract import verify

        record = self.valid_plugin_provenance()
        record["source_sha256"] = "0" * 64
        spy = verify.EffectSpy()

        with self.assertRaisesRegex(verify.EvidenceError, "EVIDENCE_PROVENANCE_INVALID"):
            verify.validate_extension_provenance(
                record,
                expected_task_id="TASK-001",
                expected_run_id="RUN-001",
                spy=spy,
            )

        self.assertEqual((0, 0), (spy.accept_calls, spy.append_calls))

    def test_provenance_fixture_cases_have_no_effects_on_rejection(self):
        from tools.evidence_contract import verify

        suite = load_json(SUITE_PATH)
        results = verify.run_cases("extension-provenance", suite)

        self.assertEqual(
            [(case["id"], case["expected"]) for case in suite["provenance_cases"]],
            [(result["case_id"], result["actual"]) for result in results],
        )
        self.assertTrue(all(result["status"] == "PASSED" for result in results))
        for result in results[2:]:
            self.assertEqual((0, 0), (result["accept_calls"], result["append_calls"]))


class RegisteredCliTests(unittest.TestCase):
    @staticmethod
    def registered_namespace(**overrides: str) -> Namespace:
        from tools.evidence_contract import verify

        values = {
            "schema": verify.SCHEMA_REF,
            "suite": verify.SUITE_REF,
            "result": verify.TRUSTED_RESULTS["evidence-positive-negative"],
            "command_id": "evidence-positive-negative",
        }
        values.update(overrides)
        return Namespace(**values)

    def assert_unsafe_success_case_is_rejected_before_result_write(self, case_id: str):
        from tools.evidence_contract import verify

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            schema_path = temporary_root / verify.SCHEMA_REF
            suite_path = temporary_root / verify.SUITE_REF
            result_path = temporary_root / verify.TRUSTED_RESULTS["evidence-positive-negative"]
            schema_path.parent.mkdir(parents=True)
            suite_path.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / verify.SCHEMA_REF, schema_path)
            suite = load_json(SUITE_PATH)
            suite["evidence_cases"][0]["id"] = case_id
            suite_path.write_text(json.dumps(suite), encoding="utf-8")

            with self.assertRaisesRegex(verify.EvidenceError, "EVIDENCE_RESULT_UNSAFE"):
                verify.run_conformance(
                    {"schema": schema_path, "suite": suite_path, "result": result_path},
                    "evidence-positive-negative",
                    "2026-07-26T00:05:00Z",
                )

            self.assertFalse(result_path.exists())

    def test_unregistered_result_and_abbreviated_flag_are_denied(self):
        from tools.evidence_contract import verify

        with self.assertRaisesRegex(verify.EvidenceError, "EVIDENCE_RUNNER_CONTRACT_INVALID"):
            verify.parse_args(["--sch", verify.SCHEMA_REF])
        args = self.registered_namespace(result="artifacts/verification/other.json")
        with self.assertRaisesRegex(verify.EvidenceError, "EVIDENCE_RUNNER_CONTRACT_INVALID"):
            verify.validate_registered_paths(args)

    def test_parse_failure_writes_no_exception_or_absolute_path(self):
        from tools.evidence_contract import verify

        result = verify.safe_failure("evidence-positive-negative", "EVIDENCE_RUNNER_CONTRACT_INVALID")
        encoded = json.dumps(result)
        self.assertEqual("VG-023", result["gate_id"])
        self.assertEqual("FAILED", result["status"])
        self.assertEqual("EVIDENCE_RUNNER_CONTRACT_INVALID", result["failure_code"])
        self.assertNotIn("exception", encoded.lower())
        self.assertNotIn(str(ROOT), encoded)

    def test_registered_result_is_written_atomically(self):
        from tools.evidence_contract import verify

        with tempfile.TemporaryDirectory() as temporary_directory:
            result_path = Path(temporary_directory) / "result.json"
            verify.write_result_atomically(result_path, {"status": "PASSED"})
            self.assertEqual({"status": "PASSED"}, load_json(result_path))
            self.assertEqual([], list(result_path.parent.glob("result.json.*.tmp")))

    def test_invalid_registered_input_preserves_temp_sentinel_and_creates_no_target(self):
        from tools.evidence_contract import verify

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            schema_path = temporary_root / verify.SCHEMA_REF
            suite_path = temporary_root / verify.SUITE_REF
            sentinel_path = temporary_root / verify.TRUSTED_RESULTS["evidence-positive-negative"]
            missing_target = temporary_root / verify.TRUSTED_RESULTS["extension-provenance"]
            schema_path.parent.mkdir(parents=True)
            suite_path.parent.mkdir(parents=True)
            sentinel_path.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / verify.SCHEMA_REF, schema_path)
            shutil.copyfile(ROOT / verify.SUITE_REF, suite_path)
            sentinel_path.write_text("sentinel", encoding="utf-8")

            exit_code = verify.main(
                [
                    "--schema",
                    "other.json",
                    "--suite",
                    verify.SUITE_REF,
                    "--result",
                    verify.TRUSTED_RESULTS["extension-provenance"],
                    "--command-id",
                    "extension-provenance",
                ],
                root=temporary_root,
            )

            self.assertEqual(1, exit_code)
            self.assertEqual(b"sentinel", sentinel_path.read_bytes())
            self.assertFalse(missing_target.exists())

    def test_embedded_absolute_path_in_success_case_is_rejected_before_result_write(self):
        from tools.evidence_contract import verify

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            schema_path = temporary_root / verify.SCHEMA_REF
            suite_path = temporary_root / verify.SUITE_REF
            result_path = temporary_root / verify.TRUSTED_RESULTS["evidence-positive-negative"]
            schema_path.parent.mkdir(parents=True)
            suite_path.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / verify.SCHEMA_REF, schema_path)
            suite = load_json(SUITE_PATH)
            suite["evidence_cases"][0]["id"] = "case /var/lib/forgeops/fixture.json detail"
            suite_path.write_text(json.dumps(suite), encoding="utf-8")

            with self.assertRaisesRegex(verify.EvidenceError, "EVIDENCE_RESULT_UNSAFE"):
                verify.run_conformance(
                    {"schema": schema_path, "suite": suite_path, "result": result_path},
                    "evidence-positive-negative",
                    "2026-07-26T00:05:00Z",
                )

            self.assertFalse(result_path.exists())

    def test_credential_assignment_in_success_case_is_rejected_before_result_write(self):
        from tools.evidence_contract import verify

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            schema_path = temporary_root / verify.SCHEMA_REF
            suite_path = temporary_root / verify.SUITE_REF
            result_path = temporary_root / verify.TRUSTED_RESULTS["evidence-positive-negative"]
            schema_path.parent.mkdir(parents=True)
            suite_path.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / verify.SCHEMA_REF, schema_path)
            suite = load_json(SUITE_PATH)
            suite["evidence_cases"][0]["id"] = "case client_secret=unsafe"
            suite_path.write_text(json.dumps(suite), encoding="utf-8")

            with self.assertRaisesRegex(verify.EvidenceError, "EVIDENCE_RESULT_UNSAFE"):
                verify.run_conformance(
                    {"schema": schema_path, "suite": suite_path, "result": result_path},
                    "evidence-positive-negative",
                    "2026-07-26T00:05:00Z",
                )

            self.assertFalse(result_path.exists())

    def test_windows_absolute_path_in_success_case_is_rejected_before_result_write(self):
        self.assert_unsafe_success_case_is_rejected_before_result_write(
            r"case C:\private\sample.txt detail"
        )

    def test_access_token_assignment_in_success_case_is_rejected_before_result_write(self):
        self.assert_unsafe_success_case_is_rejected_before_result_write(
            "case access_token=unsafe"
        )

    def test_api_key_assignment_in_success_case_is_rejected_before_result_write(self):
        self.assert_unsafe_success_case_is_rejected_before_result_write(
            "case api_key=unsafe"
        )

    def test_valid_registered_execution_failure_writes_only_safe_failure_result(self):
        from tools.evidence_contract import verify

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            schema_path = temporary_root / verify.SCHEMA_REF
            suite_path = temporary_root / verify.SUITE_REF
            result_path = temporary_root / verify.TRUSTED_RESULTS["evidence-positive-negative"]
            schema_path.parent.mkdir(parents=True)
            suite_path.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / verify.SCHEMA_REF, schema_path)
            suite = load_json(SUITE_PATH)
            suite["evidence_cases"][0]["id"] = "case client_secret=unsafe"
            suite_path.write_text(json.dumps(suite), encoding="utf-8")

            exit_code = verify.main(
                [
                    "--schema",
                    verify.SCHEMA_REF,
                    "--suite",
                    verify.SUITE_REF,
                    "--result",
                    verify.TRUSTED_RESULTS["evidence-positive-negative"],
                    "--command-id",
                    "evidence-positive-negative",
                ],
                root=temporary_root,
            )

            result = load_json(result_path)
            self.assertEqual(1, exit_code)
            self.assertEqual("FAILED", result["status"])
            self.assertEqual("EVIDENCE_RESULT_UNSAFE", result["failure_code"])
            self.assertNotIn("client_secret=unsafe", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
