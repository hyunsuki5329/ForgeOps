"""Focused conformance tests for the ForgeOps run-manifest boundary."""

from __future__ import annotations

import hashlib
import importlib
import json
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts" / "forgeops-run-manifest" / "1.0" / "schema.json"
SUITE_PATH = ROOT / "fixtures" / "forgeops-run-manifest" / "suite.json"
MODULE_PATH = ROOT / "tools" / "interface_contract" / "manifest_contract.py"


class ManifestShapeTests(unittest.TestCase):
    def _runtime(self):
        self.assertTrue(MODULE_PATH.is_file(), "manifest validator is not implemented")
        module = importlib.import_module("tools.interface_contract.manifest_contract")
        for name in (
            "canonical_manifest_bytes",
            "calculate_manifest_sha256",
            "validate_manifest",
        ):
            self.assertTrue(hasattr(module, name), f"missing manifest interface: {name}")
        return module

    def _catalog(self):
        self.assertTrue(SCHEMA_PATH.is_file(), "manifest schema is not implemented")
        self.assertTrue(SUITE_PATH.is_file(), "manifest fixture suite is not implemented")
        return (
            json.loads(SCHEMA_PATH.read_text(encoding="utf-8")),
            json.loads(SUITE_PATH.read_text(encoding="utf-8")),
        )

    @staticmethod
    def _case_by_id(suite, case_id):
        return next(case for case in suite["positive"] if case["id"] == case_id)

    @staticmethod
    def _mutate(manifest, mutations):
        result = deepcopy(manifest)
        for mutation in mutations:
            target = result
            for segment in mutation["path"][:-1]:
                target = target[segment]
            leaf = mutation["path"][-1]
            if mutation["operation"] == "remove":
                target.pop(leaf)
            else:
                target[leaf] = deepcopy(mutation["value"])
        return result

    def test_primary_terminal_manifest_is_valid(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        manifest = self._case_by_id(suite, "primary-terminal")["manifest"]

        self.assertEqual("PASSED", runtime.validate_manifest(manifest, schema))

    def test_all_positive_lifecycle_fixtures_are_valid(self):
        runtime = self._runtime()
        schema, suite = self._catalog()

        expected_ids = {
            "primary-terminal",
            "non-terminal-snapshot",
            "audit-replay",
            "counterfactual",
            "revision-evidence",
            "time-evidence",
            "blocked-terminal",
        }
        self.assertEqual(expected_ids, {case["id"] for case in suite["positive"]})
        for case in suite["positive"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(
                    "PASSED", runtime.validate_manifest(case["manifest"], schema)
                )

    def test_manifest_hash_excludes_only_root_hash_field(self):
        runtime = self._runtime()
        _, suite = self._catalog()
        manifest = deepcopy(
            self._case_by_id(suite, "primary-terminal")["manifest"]
        )

        payload = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
        expected_bytes = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        self.assertEqual(expected_bytes, runtime.canonical_manifest_bytes(manifest))
        self.assertFalse(runtime.canonical_manifest_bytes(manifest).startswith(b"\xef\xbb\xbf"))
        self.assertEqual(
            hashlib.sha256(expected_bytes).hexdigest(), manifest["manifest_sha256"]
        )

        changed = deepcopy(manifest)
        changed["manifest_sha256"] = "f" * 64
        self.assertEqual(
            runtime.canonical_manifest_bytes(manifest),
            runtime.canonical_manifest_bytes(changed),
        )
        changed["source_contract"]["artifact_version"] = 2
        self.assertNotEqual(
            runtime.canonical_manifest_bytes(manifest),
            runtime.canonical_manifest_bytes(changed),
        )

        unicode_probe = {
            "manifest_sha256": "root-is-excluded",
            "label": "검증",
            "nested": {"manifest_sha256": "nested-is-preserved"},
        }
        encoded = runtime.canonical_manifest_bytes(unicode_probe)
        self.assertIn("검증".encode("utf-8"), encoded)
        self.assertIn(b'"manifest_sha256":"nested-is-preserved"', encoded)
        self.assertNotIn(b"root-is-excluded", encoded)

    def test_event_count_matches_inclusive_range(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        manifest = deepcopy(
            self._case_by_id(suite, "primary-terminal")["manifest"]
        )
        manifest["event_stream"]["count"] += 1
        manifest["manifest_sha256"] = runtime.calculate_manifest_sha256(manifest)

        with self.assertRaisesRegex(
            runtime.ContractError, "MANIFEST_EVENT_RANGE_INVALID"
        ):
            runtime.validate_manifest(manifest, schema)

    def test_inclusive_range_does_not_assume_first_sequence_is_one(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        manifest = self._case_by_id(suite, "time-evidence")["manifest"]

        self.assertEqual(
            {"first_seq": 7, "last_seq": 8, "count": 2},
            {
                key: manifest["event_stream"][key]
                for key in ("first_seq", "last_seq", "count")
            },
        )
        self.assertEqual("PASSED", runtime.validate_manifest(manifest, schema))

    def test_blocked_status_requires_terminal_lifecycle(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        manifest = deepcopy(
            self._case_by_id(suite, "non-terminal-snapshot")["manifest"]
        )
        manifest["status"] = "BLOCKED"
        manifest["manifest_sha256"] = runtime.calculate_manifest_sha256(manifest)

        with self.assertRaisesRegex(
            runtime.ContractError, "MANIFEST_IDENTITY_MISMATCH"
        ):
            runtime.validate_manifest(manifest, schema)

        manifest["decision_refs"] = [
            {
                "decision_id": "DEC-blocked-terminal",
                "decision_kind": "TERMINAL",
                "subject_id": manifest["task_id"],
                "artifact_refs": [],
                "evidence_refs": [],
                "producer_event_seq": manifest["event_stream"]["last_seq"],
            }
        ]
        manifest["finalized_at"] = "2026-07-24T01:20:00Z"
        manifest["manifest_sha256"] = runtime.calculate_manifest_sha256(manifest)
        self.assertEqual("PASSED", runtime.validate_manifest(manifest, schema))

    def test_revision_evidence_preserves_integer_revision_type(self):
        self._runtime()
        schema, suite = self._catalog()
        observed_revision = schema["properties"]["evidence"]["items"][
            "properties"
        ]["observed_revision"]
        manifest = self._case_by_id(suite, "revision-evidence")["manifest"]

        self.assertEqual("integer", observed_revision["type"])
        self.assertEqual(
            manifest["accepted_revision"],
            manifest["evidence"][0]["observed_revision"],
        )

    def test_source_contract_preserves_product_contract_artifact_identity(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        manifest = deepcopy(
            self._case_by_id(suite, "non-terminal-snapshot")["manifest"]
        )
        manifest["source_contract"]["artifact_id"] = "task_contract:public_fixture:v1"
        manifest["manifest_sha256"] = runtime.calculate_manifest_sha256(manifest)

        self.assertEqual("PASSED", runtime.validate_manifest(manifest, schema))

    def test_invalid_schema_is_reported_as_stable_contract_error(self):
        runtime = self._runtime()
        _, suite = self._catalog()
        manifest = self._case_by_id(suite, "non-terminal-snapshot")["manifest"]
        invalid_schema = {
            "type": "object",
            "properties": {"manifest_id": {"type": "not-a-json-schema-type"}},
        }

        with self.assertRaisesRegex(
            runtime.ContractError, "MANIFEST_SCHEMA_INVALID"
        ):
            runtime.validate_manifest(manifest, invalid_schema)

    def test_lifecycle_negative_catalog_returns_stable_errors(self):
        runtime = self._runtime()
        schema, suite = self._catalog()

        for case in suite["negative_lifecycle"]:
            base = self._case_by_id(suite, case["base_case"])["manifest"]
            manifest = self._mutate(base, case["mutations"])
            if case["rehash"]:
                manifest["manifest_sha256"] = runtime.calculate_manifest_sha256(manifest)
            with self.subTest(case=case["id"]):
                with self.assertRaises(runtime.ContractError) as caught:
                    runtime.validate_manifest(manifest, schema)
                self.assertEqual(case["expected_error"], caught.exception.code)

    def test_schema_is_closed_at_every_manifest_object_boundary(self):
        self._runtime()
        schema, _ = self._catalog()

        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["source_contract"]["additionalProperties"])
        self.assertFalse(schema["properties"]["event_stream"]["additionalProperties"])
        self.assertFalse(schema["properties"]["artifacts"]["items"]["additionalProperties"])
        self.assertFalse(schema["properties"]["evidence"]["items"]["additionalProperties"])
        self.assertFalse(schema["properties"]["decision_refs"]["items"]["additionalProperties"])

    def test_manifest_schema_uses_exact_closed_enums(self):
        self._runtime()
        schema, _ = self._catalog()

        self.assertEqual(
            ["PRIMARY", "AUDIT_REPLAY", "COUNTERFACTUAL", "REEXECUTE"],
            schema["properties"]["run_mode"]["enum"],
        )
        self.assertEqual(
            [
                "PENDING",
                "IN_PROGRESS",
                "WAITING_FOR_HUMAN",
                "BLOCKED",
                "SUCCEEDED",
                "FAILED",
                "PARTIAL",
            ],
            schema["properties"]["status"]["enum"],
        )
        self.assertEqual(
            ["CANDIDATE", "CRITERION", "TERMINAL"],
            schema["properties"]["decision_refs"]["items"]["properties"][
                "decision_kind"
            ]["enum"],
        )


class ManifestReferenceTests(unittest.TestCase):
    def _runtime(self):
        module = importlib.import_module("tools.interface_contract.manifest_contract")
        required = (
            "StorageSpy",
            "validate_catalogs_and_references",
            "validate_manifest_case",
            "validate_source_ref",
        )
        missing = [name for name in required if not hasattr(module, name)]
        self.assertEqual([], missing, f"missing Task 2 interfaces: {missing}")
        return module

    def _catalog(self):
        return (
            json.loads(SCHEMA_PATH.read_text(encoding="utf-8")),
            json.loads(SUITE_PATH.read_text(encoding="utf-8")),
        )

    @staticmethod
    def _case_by_id(suite, case_id):
        return next(case for case in suite["positive"] if case["id"] == case_id)

    def _manifest(self, suite, case_id="primary-terminal"):
        return deepcopy(self._case_by_id(suite, case_id)["manifest"])

    @staticmethod
    def _rehash(runtime, manifest):
        manifest["manifest_sha256"] = runtime.calculate_manifest_sha256(manifest)
        return manifest

    def test_duplicate_catalog_and_decision_ids_are_rejected(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        mutations = []

        duplicate_evidence = self._manifest(suite)
        duplicate_evidence["evidence"].append(deepcopy(duplicate_evidence["evidence"][0]))
        mutations.append(duplicate_evidence)

        duplicate_artifact = self._manifest(suite)
        duplicate_artifact["artifacts"].append(deepcopy(duplicate_artifact["artifacts"][0]))
        mutations.append(duplicate_artifact)

        duplicate_decision = self._manifest(suite)
        duplicate_decision["decision_refs"].append(deepcopy(duplicate_decision["decision_refs"][0]))
        mutations.append(duplicate_decision)

        for manifest in mutations:
            with self.subTest(
                artifacts=len(manifest["artifacts"]),
                evidence=len(manifest["evidence"]),
                decisions=len(manifest["decision_refs"]),
            ):
                self._rehash(runtime, manifest)
                with self.assertRaisesRegex(runtime.ContractError, "MANIFEST_ID_DUPLICATE"):
                    runtime.validate_manifest(manifest, schema)

    def test_dangling_artifact_and_evidence_references_are_rejected(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        for field, missing_id in (
            ("artifact_refs", "ART-missing"),
            ("evidence_refs", "EVID-missing"),
        ):
            manifest = self._manifest(suite)
            manifest["decision_refs"][0][field] = [missing_id]
            self._rehash(runtime, manifest)
            with self.subTest(field=field):
                with self.assertRaisesRegex(runtime.ContractError, "MANIFEST_REFERENCE_DANGLING"):
                    runtime.validate_manifest(manifest, schema)

        duplicate_reference = self._manifest(suite)
        duplicate_reference["decision_refs"][0]["evidence_refs"] = [
            "EVID-first",
            "EVID-first",
        ]
        self._rehash(runtime, duplicate_reference)
        with self.assertRaisesRegex(runtime.ContractError, "MANIFEST_ID_DUPLICATE"):
            runtime.validate_manifest(duplicate_reference, schema)

    def test_producer_sequence_uses_inclusive_event_range(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        manifest = self._manifest(suite, "time-evidence")

        manifest["evidence"][0]["producer_event_seq"] = 7
        manifest["decision_refs"][0]["producer_event_seq"] = 8
        self._rehash(runtime, manifest)
        self.assertEqual("PASSED", runtime.validate_manifest(manifest, schema))

        for value in (6, 9):
            for collection in ("artifacts", "evidence", "decision_refs"):
                invalid = deepcopy(manifest)
                if collection == "artifacts":
                    invalid["artifacts"] = [
                        {
                            "artifact_id": "ART-range-probe",
                            "artifact_version": 1,
                            "kind": "RESULT",
                            "content_sha256": "f" * 64,
                            "media_type": "application/json",
                            "classification": "INTERNAL",
                            "producer_event_seq": value,
                        }
                    ]
                else:
                    invalid[collection][0]["producer_event_seq"] = value
                self._rehash(runtime, invalid)
                with self.subTest(value=value, collection=collection):
                    with self.assertRaisesRegex(runtime.ContractError, "MANIFEST_PRODUCER_SEQUENCE_INVALID"):
                        runtime.validate_manifest(invalid, schema)

    def test_evidence_freshness_union_returns_stable_error(self):
        runtime = self._runtime()
        schema, suite = self._catalog()

        file_with_time = self._manifest(suite, "revision-evidence")
        file_with_time["evidence"][0]["observed_at"] = "2026-07-24T02:30:00Z"

        time_with_revision = self._manifest(suite, "time-evidence")
        time_with_revision["evidence"][0]["observed_revision"] = 1

        invalid_utc = self._manifest(suite, "time-evidence")
        invalid_utc["evidence"][0]["observed_at"] = "2026-07-24T02:30:00+00:00"

        for manifest in (file_with_time, time_with_revision, invalid_utc):
            self._rehash(runtime, manifest)
            with self.assertRaisesRegex(runtime.ContractError, "MANIFEST_EVIDENCE_FRESHNESS_INVALID"):
                runtime.validate_manifest(manifest, schema)

    def test_source_ref_accepts_only_canonical_relative_or_forgeops_urn(self):
        runtime = self._runtime()
        for accepted in (
            "artifacts/verification/result.json",
            "docs/project/wbs.md",
            "forgeops:evidence:audit-run",
            "forgeops:command:manifest-fixture",
            "forgeops:test:manifest-fixture",
            "forgeops:runtime:run-observation",
        ):
            with self.subTest(accepted=accepted):
                runtime.validate_source_ref(accepted)

        rejected = (
            "/etc/passwd",
            "C:/Users/User/secret.txt",
            "//server/share/result.json",
            "..\\secret.txt",
            "artifacts/../secret.txt",
            "artifacts\\result.json",
            "artifacts/*.json",
            "artifacts/result.json?token=signed",
            "artifacts/result.json#fragment",
            "https://store.example/result?X-Amz-Signature=abc",
            "forgeops:evidence:audit-run?sig=abc",
            ".env",
            ".env.production",
            "config/credentials.json",
            "secrets/token.txt",
            "forgeops:token:opaque-id",
            "forgeops:credential:opaque-id",
            "forgeops:tenant:opaque-id",
            "forgeops:secret:opaque-id",
        )
        for source_ref in rejected:
            with self.subTest(rejected=source_ref):
                with self.assertRaisesRegex(runtime.ContractError, "MANIFEST_SENSITIVE_CONTENT_FORBIDDEN"):
                    runtime.validate_source_ref(source_ref)

    def test_invalid_run_mode_precedes_schema_validation_and_storage(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        mode_fixture = next(
            case
            for case in suite["negative_reference"]
            if case["id"] == "invalid-run-mode"
        )
        self.assertEqual(
            mode_fixture["manifest"]["manifest_sha256"],
            runtime.calculate_manifest_sha256(mode_fixture["manifest"]),
        )
        for invalid_mode in ("UNKNOWN", 7, None, ["PRIMARY"]):
            manifest = self._manifest(suite, "non-terminal-snapshot")
            manifest["run_mode"] = invalid_mode
            manifest["unknown_shape_field"] = "schema-invalid-after-mode"
            self._rehash(runtime, manifest)
            spy = runtime.StorageSpy()
            case = {
                "id": "invalid-run-mode",
                "kind": "run_mode",
                "manifest": manifest,
                "resolution_context": {},
                "expected": "MANIFEST_MODE_INVALID",
                "expected_storage_calls": 0,
            }
            with self.subTest(run_mode=invalid_mode):
                with self.assertRaisesRegex(runtime.ContractError, "MANIFEST_MODE_INVALID"):
                    runtime.validate_manifest_case(case, schema, spy)
                self.assertEqual(0, spy.calls)

    def test_raw_secret_and_path_fields_are_rejected_before_storage(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        for field, value in (
            ("raw_secret", "do-not-store"),
            ("credential", "opaque-but-forbidden"),
            ("tenant_id", "tenant-123"),
            ("absolute_path", "C:/private/result.json"),
            ("signed_url", "https://store.example/result?sig=abc"),
        ):
            manifest = self._manifest(suite, "non-terminal-snapshot")
            manifest[field] = value
            self._rehash(runtime, manifest)
            spy = runtime.StorageSpy()
            case = {
                "id": f"forbidden-{field}",
                "kind": "sensitive_boundary",
                "manifest": manifest,
                "resolution_context": {},
                "expected": "MANIFEST_SENSITIVE_CONTENT_FORBIDDEN",
                "expected_storage_calls": 0,
            }
            with self.subTest(field=field):
                with self.assertRaisesRegex(runtime.ContractError, "MANIFEST_SENSITIVE_CONTENT_FORBIDDEN"):
                    runtime.validate_manifest_case(case, schema, spy)
                self.assertEqual(0, spy.calls)

    def test_cross_run_or_incomplete_resolution_context_is_rejected(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        manifest = self._manifest(suite)
        contexts = (
            {
                "ART-primary-result": {"task_id": manifest["task_id"], "run_id": "RUN-other"},
                "EVID-first": {"task_id": manifest["task_id"], "run_id": manifest["run_id"]},
            },
            {
                "ART-primary-result": {"task_id": manifest["task_id"], "run_id": manifest["run_id"]},
            },
        )
        for resolution_context in contexts:
            spy = runtime.StorageSpy()
            case = {
                "id": "cross-run-reference",
                "kind": "reference_resolution",
                "manifest": manifest,
                "resolution_context": resolution_context,
                "expected": "MANIFEST_REFERENCE_CROSS_RUN",
                "expected_storage_calls": 0,
            }
            with self.subTest(context=resolution_context):
                with self.assertRaisesRegex(runtime.ContractError, "MANIFEST_REFERENCE_CROSS_RUN"):
                    runtime.validate_manifest_case(case, schema, spy)
                self.assertEqual(0, spy.calls)

    def test_negative_reference_fixture_catalog_is_exact_and_zero_storage(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        expected_fields = {
            "id",
            "kind",
            "manifest",
            "resolution_context",
            "expected",
            "expected_storage_calls",
        }
        expected_ids = {
            "duplicate-evidence-id",
            "dangling-reference",
            "producer-outside-range",
            "file-evidence-with-time",
            "time-evidence-with-revision",
            "invalid-strict-utc",
            "raw-secret-field",
            "absolute-source-ref",
            "traversal-source-ref",
            "signed-url-source-ref",
            "cross-run-reference",
            "invalid-run-mode",
            "sensitive-urn-token",
            "sensitive-urn-credential",
            "sensitive-urn-tenant",
            "sensitive-urn-secret",
        }
        self.assertEqual(expected_ids, {case["id"] for case in suite["negative_reference"]})
        for case in suite["negative_reference"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(expected_fields, set(case))
                spy = runtime.StorageSpy()
                with self.assertRaises(runtime.ContractError) as caught:
                    runtime.validate_manifest_case(case, schema, spy)
                self.assertEqual(case["expected"], caught.exception.code)
                self.assertEqual(case["expected_storage_calls"], spy.calls)

    def test_positive_fixture_cases_resolve_without_storage_effects(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        for case in suite["positive"]:
            with self.subTest(case=case["id"]):
                spy = runtime.StorageSpy()
                self.assertEqual("PASSED", runtime.validate_manifest_case(case, schema, spy))
                self.assertEqual(case["expected_storage_calls"], spy.calls)

    def test_lifecycle_and_hash_negative_cases_also_have_zero_storage_effects(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        for negative in suite["negative_lifecycle"]:
            base_case = self._case_by_id(suite, negative["base_case"])
            manifest = ManifestShapeTests._mutate(
                base_case["manifest"], negative["mutations"]
            )
            if negative["rehash"]:
                self._rehash(runtime, manifest)
            case = {
                "id": negative["id"],
                "kind": "lifecycle_or_hash",
                "manifest": manifest,
                "resolution_context": deepcopy(base_case["resolution_context"]),
                "expected": negative["expected_error"],
                "expected_storage_calls": 0,
            }
            spy = runtime.StorageSpy()
            with self.subTest(case=negative["id"]):
                with self.assertRaises(runtime.ContractError) as caught:
                    runtime.validate_manifest_case(case, schema, spy)
                self.assertEqual(negative["expected_error"], caught.exception.code)
                self.assertEqual(0, spy.calls)


if __name__ == "__main__":
    unittest.main()
