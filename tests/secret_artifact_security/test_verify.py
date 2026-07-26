"""Schema and ordered-fixture tests for secret/artifact security."""

from __future__ import annotations

import copy
import base64
import hashlib
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts/forgeops-secret-artifact-contract/1.0/schema.json"
SUITE_PATH = ROOT / "fixtures/forgeops-secret-artifact-security/suite.json"
TEST_MARKER = "FORGEOPS_TEST_SECRET_DO_NOT_STORE"

SECRET_CASES = (
    ("positive-public-packet", "positive", "packet", "PASSED"),
    ("positive-exact-marker-redacted", "positive", "packet", "PASSED"),
    ("negative-packet-raw-secret", "negative", "packet", "SECRET_SURFACE_LEAK"),
    ("negative-event-encoded-secret", "negative", "event", "SECRET_SURFACE_LEAK"),
    ("negative-prompt-credential-field", "negative", "prompt", "SECRET_SURFACE_LEAK"),
    ("negative-artifact-raw-preview", "negative", "artifact", "SECRET_SURFACE_LEAK"),
    ("negative-trace-private-id", "negative", "trace", "SECRET_SURFACE_LEAK"),
    ("negative-telemetry-secret", "negative", "telemetry", "SECRET_SURFACE_LEAK"),
    ("negative-response-token", "negative", "response", "SECRET_SURFACE_LEAK"),
    ("negative-unredactable-content", "negative", "response", "REDACTION_UNSUPPORTED"),
)

ARTIFACT_CASES = (
    ("positive-same-tenant-encrypted", "positive", "PASSED"),
    ("positive-public-safe-artifact", "positive", "PASSED"),
    ("negative-cross-tenant", "negative", "ARTIFACT_TENANT_VIOLATION"),
    ("negative-absolute-source", "negative", "ARTIFACT_REFERENCE_INVALID"),
    ("negative-signed-url", "negative", "ARTIFACT_REFERENCE_INVALID"),
    ("negative-unencrypted-sensitive", "negative", "ARTIFACT_POLICY_INVALID"),
    ("negative-retention-mismatch", "negative", "ARTIFACT_POLICY_INVALID"),
    ("negative-tamper-ref", "negative", "ARTIFACT_POLICY_INVALID"),
    ("negative-unknown-field", "negative", "ARTIFACT_POLICY_INVALID"),
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


def empty_schema_paths(value: object, path: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    if isinstance(value, dict):
        paths = [path] if value == {} else []
        for key, child in value.items():
            paths.extend(empty_schema_paths(child, path + (key,)))
        return paths
    if isinstance(value, list):
        return [item for index, child in enumerate(value) for item in empty_schema_paths(child, path + (index,))]
    return []


def marker_paths(value: object, path: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    if isinstance(value, str):
        return [path] if TEST_MARKER in value else []
    if isinstance(value, dict):
        return [item for key, child in value.items() for item in marker_paths(child, path + (key,))]
    if isinstance(value, list):
        return [item for index, child in enumerate(value) for item in marker_paths(child, path + (index,))]
    return []


def load_evaluator():
    try:
        from tools.secret_artifact_security import verify
    except ModuleNotFoundError:
        raise AssertionError("Task 2 evaluator must exist") from None
    return verify


def valid_artifact(*, tenant_id: str = "TENANT-A") -> dict:
    return {
        "artifact_id": "ART-TEST",
        "tenant_id": tenant_id,
        "source_ref": "artifacts/tenant-a/record.json",
        "checksum_sha256": "a" * 64,
        "encryption_state": "ENCRYPTED",
        "retention_class": "AUDIT_SHORT",
        "deletion_policy": "DELETE_AFTER_RETENTION",
        "tamper_ref": "forgeops:tamper:TAMPER-TEST",
    }


class SecretArtifactSchemaTests(unittest.TestCase):
    def test_objects_are_closed_and_surface_enum_is_exact(self):
        self.assertTrue(SCHEMA_PATH.is_file(), "Task 1 schema must exist")
        schema = load_schema()
        objects = [node for node in walk(schema) if node.get("type") == "object"]
        self.assertTrue(objects)
        self.assertTrue(all(node.get("additionalProperties") is False for node in objects))
        self.assertEqual(
            ["packet", "event", "prompt", "artifact", "trace", "telemetry", "response"],
            schema["$defs"]["SurfaceCase"]["properties"]["surface"]["enum"],
        )

    def test_artifact_metadata_is_closed_and_requires_policy_fields(self):
        self.assertTrue(SCHEMA_PATH.is_file(), "Task 1 schema must exist")
        artifact = load_schema()["$defs"]["ArtifactMetadata"]
        self.assertIs(False, artifact["additionalProperties"])
        self.assertEqual(
            {
                "artifact_id",
                "tenant_id",
                "source_ref",
                "checksum_sha256",
                "encryption_state",
                "retention_class",
                "deletion_policy",
                "tamper_ref",
            },
            set(artifact["required"]),
        )

    def test_fixture_envelopes_have_no_unconstrained_schema_nodes(self):
        schema = load_schema()
        self.assertEqual([], empty_schema_paths(schema))

    def test_source_ref_accepts_only_canonical_root_relative_or_opaque_artifact_values(self):
        source_ref = load_schema()["$defs"]["SourceRef"]
        validator = Draft202012Validator(source_ref)
        for value in ("artifacts/tenant-a/record.json", "forgeops:artifact:opaque-record"):
            with self.subTest(valid=value):
                self.assertTrue(validator.is_valid(value))
        for value in (
            ".",
            "./record.json",
            "..",
            "/private/record.json",
            r"C:\private\record.json",
            "artifacts/../record.json",
            r"artifacts\record.json",
            "https://example.invalid/record.json",
            "record.json?signature=synthetic",
            "record.json#fragment",
            "user@example.invalid/record.json",
            "forgeops:secret:opaque-record",
            "urn:forgeops:artifact:opaque-record",
        ):
            with self.subTest(invalid=value):
                self.assertFalse(validator.is_valid(value))


class CatalogTests(unittest.TestCase):
    def test_catalog_case_ids_and_expected_categories_are_exact(self):
        self.assertTrue(SUITE_PATH.is_file(), "Task 1 fixture suite must exist")
        suite = load_json(SUITE_PATH)
        self.assertEqual(
            SECRET_CASES,
            tuple((case["id"], case["kind"], case["surface"], case["expected"]) for case in suite["surface_cases"]),
        )
        self.assertEqual(
            ARTIFACT_CASES,
            tuple((case["id"], case["kind"], case["expected"]) for case in suite["artifact_cases"]),
        )

    def test_schema_is_valid_and_checked_in_suite_conforms(self):
        schema = load_schema()
        suite = load_json(SUITE_PATH)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(suite)

    def test_fixture_envelope_rejects_unlisted_artifact_field(self):
        schema = load_schema()
        suite = load_json(SUITE_PATH)
        malformed_suite = copy.deepcopy(suite)
        malformed_suite["artifact_cases"][0]["artifact"]["unexpected_field"] = "denied"

        errors = list(Draft202012Validator(schema).iter_errors(malformed_suite))

        self.assertTrue(errors)
        self.assertTrue(
            any(
                list(error.path) == ["artifact_cases", 0, "artifact"]
                for error in errors
            )
        )

    def test_negative_cases_have_no_effects_or_raw_occurrences(self):
        self.assertTrue(SUITE_PATH.is_file(), "Task 1 fixture suite must exist")
        suite = load_json(SUITE_PATH)
        for case in (*suite["surface_cases"], *suite["artifact_cases"]):
            if case["kind"] == "negative":
                self.assertEqual(
                    {
                        "store_calls": 0,
                        "export_calls": 0,
                        "publish_calls": 0,
                        "raw_occurrences": 0,
                    },
                    case["expected_effects"],
                )

    def test_synthetic_marker_occurs_only_in_fixture_inputs(self):
        self.assertTrue(SUITE_PATH.is_file(), "Task 1 fixture suite must exist")
        suite = load_json(SUITE_PATH)
        paths = marker_paths(suite)
        self.assertTrue(paths)
        for path in paths:
            self.assertIn("input", path)


class RedactionTests(unittest.TestCase):
    def test_raw_marker_never_reaches_any_surface(self):
        verify = load_evaluator()
        for surface in verify.SURFACES:
            with self.subTest(surface=surface):
                projected = verify.redact_surface(
                    surface,
                    {"message": TEST_MARKER},
                    (TEST_MARKER,),
                )
                self.assertNotIn(TEST_MARKER, json.dumps(projected))

    def test_encoded_marker_and_marker_hash_are_not_public_values(self):
        verify = load_evaluator()
        marker_hash = hashlib.sha256(TEST_MARKER.encode("utf-8")).hexdigest()
        marker_base64 = base64.b64encode(TEST_MARKER.encode("utf-8")).decode("ascii")
        for unsafe_value in (TEST_MARKER, marker_base64, marker_hash):
            with self.subTest(unsafe_value=unsafe_value):
                with self.assertRaisesRegex(verify.SecretArtifactError, "REDACTION_UNSUPPORTED"):
                    verify.validate_public_projection({"message": unsafe_value}, (TEST_MARKER,))

    def test_uppercase_hex_and_digest_marker_variants_are_redacted_and_counted(self):
        verify = load_evaluator()
        marker_bytes = TEST_MARKER.encode("utf-8")
        uppercase_variants = (
            marker_bytes.hex().upper(),
            hashlib.sha256(marker_bytes).hexdigest().upper(),
        )
        for unsafe_value in uppercase_variants:
            with self.subTest(unsafe_value=unsafe_value):
                projected = verify.redact_surface("packet", {"message": unsafe_value}, (TEST_MARKER,))
                self.assertEqual("[REDACTED]", projected["message"])
                with self.assertRaisesRegex(verify.SecretArtifactError, "REDACTION_UNSUPPORTED"):
                    verify.validate_public_projection({"message": unsafe_value}, (TEST_MARKER,))
                self.assertEqual(1, verify._raw_occurrences([{"message": unsafe_value}], (TEST_MARKER,)))

    def test_forbidden_keys_credential_patterns_and_unredactable_values_are_denied_or_redacted(self):
        verify = load_evaluator()
        projected = verify.redact_surface(
            "event",
            {"credential": "synthetic", "message": "Bearer synthetic-value"},
            (TEST_MARKER,),
        )
        self.assertEqual("[REDACTED]", projected["credential"])
        self.assertEqual("[REDACTED]", projected["message"])
        with self.assertRaisesRegex(verify.SecretArtifactError, "REDACTION_UNSUPPORTED"):
            verify.redact_surface("response", {"content": {"unsupported": "value"}}, (TEST_MARKER,))

    def test_redaction_rejects_depth_item_and_string_limit_overruns(self):
        verify = load_evaluator()
        too_deep: object = "safe"
        for _ in range(13):
            too_deep = [too_deep]
        for value in (too_deep, list(range(1001)), "x" * 4097):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaisesRegex(verify.SecretArtifactError, "REDACTION_UNSUPPORTED"):
                    verify.redact_surface("packet", value, (TEST_MARKER,))


class ArtifactAdmissionTests(unittest.TestCase):
    def test_cross_tenant_artifact_is_denied_before_store(self):
        verify = load_evaluator()
        spy = verify.SurfaceSpy()
        with self.assertRaisesRegex(verify.SecretArtifactError, "ARTIFACT_TENANT_VIOLATION"):
            verify.admit_artifact(valid_artifact(tenant_id="TENANT-B"), "TENANT-A", spy)
        self.assertEqual((0, 0, 0), (spy.store_calls, spy.export_calls, spy.publish_calls))

    def test_artifact_validation_order_rejects_before_effects(self):
        verify = load_evaluator()
        cases = (
            (dict(valid_artifact(), unexpected="denied"), "ARTIFACT_POLICY_INVALID"),
            ({**valid_artifact(), "source_ref": "https://example.invalid/signed?token=synthetic"}, "ARTIFACT_REFERENCE_INVALID"),
            ({**valid_artifact(), "encryption_state": "PUBLIC_SAFE"}, "ARTIFACT_POLICY_INVALID"),
            ({**valid_artifact(), "checksum_sha256": "not-a-checksum"}, "ARTIFACT_POLICY_INVALID"),
            ({**valid_artifact(), "tamper_ref": "https://example.invalid/tamper"}, "ARTIFACT_POLICY_INVALID"),
        )
        for artifact, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                spy = verify.SurfaceSpy()
                with self.assertRaisesRegex(verify.SecretArtifactError, expected_code):
                    verify.admit_artifact(artifact, "TENANT-A", spy)
                self.assertEqual((0, 0, 0), (spy.store_calls, spy.export_calls, spy.publish_calls))

    def test_valid_artifact_is_stored_as_safe_metadata_only(self):
        verify = load_evaluator()
        spy = verify.SurfaceSpy()
        verify.admit_artifact(valid_artifact(), "TENANT-A", spy)
        self.assertEqual((1, 0, 0), (spy.store_calls, spy.export_calls, spy.publish_calls))
        self.assertEqual([valid_artifact()], spy.admitted_values)


class CaseRunnerTests(unittest.TestCase):
    def test_case_records_are_closed_and_negative_cases_have_no_effects_or_raw_values(self):
        verify = load_evaluator()
        suite = load_json(SUITE_PATH)
        results = verify.run_cases("secret-surface-negative", suite)
        self.assertEqual(len(suite["surface_cases"]), len(results))
        for case, result in zip(suite["surface_cases"], results, strict=True):
            with self.subTest(case_id=case["id"]):
                self.assertEqual(
                    {"case_id", "expected", "actual", "status", "store_calls", "export_calls", "publish_calls", "raw_occurrences"},
                    set(result),
                )
                self.assertEqual("PASSED", result["status"])
                self.assertEqual(0, result["raw_occurrences"])
                if case["kind"] == "negative":
                    self.assertEqual((0, 0, 0), (result["store_calls"], result["export_calls"], result["publish_calls"]))
                self.assertNotIn(TEST_MARKER, json.dumps(result))

    def test_artifact_runner_denies_duplicate_artifact_ids_before_store(self):
        verify = load_evaluator()
        suite = load_json(SUITE_PATH)
        duplicated = copy.deepcopy(suite)
        duplicated["artifact_cases"][1]["artifact"]["artifact_id"] = duplicated["artifact_cases"][0]["artifact"]["artifact_id"]
        results = verify.run_cases("artifact-isolation-negative", duplicated)
        self.assertEqual("ARTIFACT_POLICY_INVALID", results[1]["actual"])
        self.assertEqual((0, 0, 0), (results[1]["store_calls"], results[1]["export_calls"], results[1]["publish_calls"]))

    def test_case_runner_never_projects_an_unsafe_fixture_id(self):
        verify = load_evaluator()
        suite = load_json(SUITE_PATH)
        unsafe_suite = copy.deepcopy(suite)
        unsafe_suite["surface_cases"][0]["id"] = TEST_MARKER
        result = verify.run_cases("secret-surface-negative", unsafe_suite)[0]
        self.assertNotIn(TEST_MARKER, json.dumps(result))


if __name__ == "__main__":
    unittest.main()
