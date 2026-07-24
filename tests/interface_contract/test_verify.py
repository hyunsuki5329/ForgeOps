"""Integrated VG-004 runner tests for exact inputs and safe result writes."""

from __future__ import annotations

import argparse
import copy
import json
import runpy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from tools.interface_contract.common import ContractError, is_strict_utc
from tools.interface_contract import verify


ROOT = Path(__file__).resolve().parents[2]
REGISTERED_ARGUMENTS = [
    "--openapi",
    "contracts/forgeops-api/1.0/openapi.yaml",
    "--event-schema",
    "contracts/forgeops-event/1.0/schema.json",
    "--manifest-schema",
    "contracts/forgeops-run-manifest/1.0/schema.json",
    "--api-version-suite",
    "fixtures/forgeops-api/version-envelope-suite.json",
    "--api-boundary-suite",
    "fixtures/forgeops-api/data-control-suite.json",
    "--event-suite",
    "fixtures/forgeops-event-contract/suite.json",
    "--manifest-suite",
    "fixtures/forgeops-run-manifest/suite.json",
    "--result",
    "artifacts/verification/vg-004-interface-contract-result.json",
    "--command-id",
    "interface-contract-fixture",
]


def registered_namespace(**overrides: str) -> argparse.Namespace:
    values = dict(verify.TRUSTED)
    values["command_id"] = verify.COMMAND_ID
    values.update(overrides)
    return argparse.Namespace(**values)


def valid_integrated_bundle() -> dict:
    api_suite = json.loads(
        (ROOT / verify.TRUSTED["api_boundary_suite"]).read_text(encoding="utf-8")
    )
    event_suite = json.loads(
        (ROOT / verify.TRUSTED["event_suite"]).read_text(encoding="utf-8")
    )
    manifest_suite = json.loads(
        (ROOT / verify.TRUSTED["manifest_suite"]).read_text(encoding="utf-8")
    )
    api_fixture = next(
        case for case in api_suite["cases"] if case["id"] == "get-run-valid"
    )
    event_fixture = next(
        case for case in event_suite["positive"] if case["id"] == "first-append"
    )
    manifest_fixture = next(
        case
        for case in manifest_suite["positive"]
        if case["id"] == "primary-terminal"
    )
    api_case = copy.deepcopy(api_fixture["response"]["data"])
    api_case["reference_context"] = copy.deepcopy(
        api_fixture["reference_context"]
    )
    return {
        "api_case": api_case,
        "event_records": copy.deepcopy(event_fixture["records"]),
        "manifest": copy.deepcopy(manifest_fixture["manifest"]),
    }


class RegisteredPathTests(unittest.TestCase):
    def test_exact_registered_literals_are_accepted(self):
        verify.validate_registered_paths(registered_namespace())

    def test_arbitrary_input_result_and_command_literals_are_denied(self):
        probes = {
            "openapi": "contracts/forgeops-api/1.0/../1.0/openapi.yaml",
            "result": "artifacts/verification/other.json",
            "command_id": "interface-contract-fixture-copy",
        }
        for name, value in probes.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(
                    ContractError, "INTERFACE_RUNNER_CONTRACT_INVALID"
                ):
                    verify.validate_registered_paths(
                        registered_namespace(**{name: value})
                    )

    def test_abbreviated_cli_flag_is_denied(self):
        arguments = copy.deepcopy(REGISTERED_ARGUMENTS)
        arguments[arguments.index("--openapi")] = "--open"

        with self.assertRaisesRegex(
            ContractError, "INTERFACE_RUNNER_CONTRACT_INVALID"
        ):
            verify.parse_args(arguments)

    def test_script_mode_bootstraps_repository_import_path(self):
        script = ROOT / "tools" / "interface_contract" / "verify.py"
        original_path = list(sys.path)
        try:
            sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != ROOT]
            namespace = runpy.run_path(str(script), run_name="verify_entrypoint_probe")
        finally:
            sys.path[:] = original_path

        self.assertEqual(ROOT, namespace["REPOSITORY_ROOT"])
        self.assertTrue(callable(namespace["main"]))


class CatalogGuardTests(unittest.TestCase):
    def _suite(self, name: str) -> dict:
        path = ROOT / verify.TRUSTED[name]
        return json.loads(path.read_text(encoding="utf-8"))

    def test_registered_catalogs_are_accepted_in_exact_order(self):
        for name in verify.SUITE_NAMES:
            with self.subTest(name=name):
                verify.validate_suite_catalog(name, self._suite(name))

    def test_case_reorder_rename_and_unknown_fields_are_denied(self):
        probes = []

        reordered = self._suite("api_version_suite")
        reordered["cases"] = list(reversed(reordered["cases"]))
        probes.append(("api_version_suite", reordered))

        renamed = self._suite("event_suite")
        renamed["negative_records"][0]["id"] = "renamed-case"
        probes.append(("event_suite", renamed))

        unknown = self._suite("manifest_suite")
        unknown["negative_reference"][0]["unknown"] = True
        probes.append(("manifest_suite", unknown))

        for name, suite in probes:
            with self.subTest(name=name):
                with self.assertRaisesRegex(
                    ContractError, "INTERFACE_RUNNER_CONTRACT_INVALID"
                ):
                    verify.validate_suite_catalog(name, suite)

    def test_public_categories_are_exact_per_registered_case(self):
        manifest = self._suite("manifest_suite")
        manifest["positive"][0]["kind"] = "UNTRUSTED_RAW_MARKER"
        event = self._suite("event_suite")
        event["negative_records"][0]["expected_error"] = "UNTRUSTED_RAW_MARKER"

        for name, suite in (
            ("manifest_suite", manifest),
            ("event_suite", event),
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(
                    ContractError, "INTERFACE_RUNNER_CONTRACT_INVALID"
                ):
                    verify.validate_suite_catalog(name, suite)


class CrossContractTests(unittest.TestCase):
    def assert_cross_reference_invalid(self, bundle: dict) -> None:
        with self.assertRaisesRegex(
            ContractError, "INTERFACE_CROSS_REFERENCE_INVALID"
        ):
            verify.validate_cross_contract(**bundle)

    def test_registered_positive_fixtures_form_one_integrated_bundle(self):
        verify.validate_cross_contract(**valid_integrated_bundle())

    def test_task_run_and_correlation_identity_must_match_every_surface(self):
        for surface, path in (
            ("api", ("api_case", "task_id")),
            ("event", ("event_records", 0, "run_id")),
            ("manifest", ("manifest", "correlation_id")),
        ):
            bundle = valid_integrated_bundle()
            target = bundle
            for segment in path[:-1]:
                target = target[segment]
            target[path[-1]] = f"MISMATCH-{surface}"
            with self.subTest(surface=surface):
                self.assert_cross_reference_invalid(bundle)

    def test_event_evidence_resolves_exactly_once_in_same_manifest(self):
        missing = valid_integrated_bundle()
        missing["event_records"][0]["canonical_event"]["evidence_refs"] = [
            "EVID-missing"
        ]
        duplicate = valid_integrated_bundle()
        duplicate["manifest"]["evidence"].append(
            copy.deepcopy(duplicate["manifest"]["evidence"][0])
        )

        for name, bundle in (("missing", missing), ("duplicate", duplicate)):
            with self.subTest(name=name):
                self.assert_cross_reference_invalid(bundle)

    def test_api_references_name_the_exact_fixture_stream_and_manifest(self):
        for field in ("event_stream_ref", "manifest_ref"):
            bundle = valid_integrated_bundle()
            old_ref = bundle["api_case"][field]
            new_ref = old_ref + "-other"
            bundle["api_case"][field] = new_ref
            bundle["api_case"]["reference_context"][new_ref] = bundle[
                "api_case"
            ]["reference_context"].pop(old_ref)
            with self.subTest(field=field):
                self.assert_cross_reference_invalid(bundle)

    def test_all_manifest_producers_are_inside_the_fixture_event_range(self):
        for catalog in ("artifacts", "evidence", "decision_refs"):
            bundle = valid_integrated_bundle()
            bundle["manifest"][catalog][0]["producer_event_seq"] = 0
            with self.subTest(catalog=catalog):
                self.assert_cross_reference_invalid(bundle)

    def test_terminal_status_and_revision_match_final_main_state_event(self):
        probes = (
            ("manifest_revision", ("manifest", "accepted_revision"), 1),
            ("api_revision", ("api_case", "accepted_revision"), 1),
            ("api_status", ("api_case", "status"), "FAILED"),
            ("event_actor", ("event_records", 0, "canonical_event", "actor"), "work"),
            ("event_code", ("event_records", 0, "canonical_event", "code"), "OTHER"),
            ("event_status", ("event_records", 0, "canonical_event", "action"), "FAILED"),
        )
        for name, path, value in probes:
            bundle = valid_integrated_bundle()
            target = bundle
            for segment in path[:-1]:
                target = target[segment]
            target[path[-1]] = value
            with self.subTest(name=name):
                self.assert_cross_reference_invalid(bundle)


class ResultSafetyTests(unittest.TestCase):
    def test_closed_integrated_result_is_public_safe(self):
        result = verify.run_conformance(
            verify.resolve_registered_paths(ROOT, registered_namespace()),
            "2026-07-24T04:00:00Z",
        )

        verify.assert_public_safe_result(result)

    def test_exact_forbidden_raw_keys_are_rejected_recursively(self):
        for key in (
            "request",
            "response",
            "body",
            "headers",
            "raw_event",
            "raw_manifest",
            "payload",
            "credential",
            "token",
            "secret",
            "private",
            "exception",
        ):
            result = verify.run_conformance(
                verify.resolve_registered_paths(ROOT, registered_namespace()),
                "2026-07-24T04:00:00Z",
            )
            result["components"]["event"]["cases"][0][key] = "redacted"
            with self.subTest(key=key):
                with self.assertRaisesRegex(
                    ContractError, "INTERFACE_RESULT_UNSAFE"
                ):
                    verify.assert_public_safe_result(result)

    def test_credential_material_and_absolute_host_paths_are_rejected(self):
        probes = (
            "Bearer abc.def.ghi",
            "token=public-looking-value",
            "-----BEGIN PRIVATE KEY-----",
            "C:\\Users\\operator\\result.json",
            "/home/operator/result.json",
            "\\\\server\\share\\result.json",
        )
        for value in probes:
            result = verify.run_conformance(
                verify.resolve_registered_paths(ROOT, registered_namespace()),
                "2026-07-24T04:00:00Z",
            )
            result["components"]["event"]["cases"][0]["actual"] = value
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ContractError, "INTERFACE_RESULT_UNSAFE"
                ):
                    verify.assert_public_safe_result(result)

    def test_safe_schema_hash_metadata_names_remain_allowed(self):
        result = verify.run_conformance(
            verify.resolve_registered_paths(ROOT, registered_namespace()),
            "2026-07-24T04:00:00Z",
        )

        self.assertIn("event_schema_sha256", result["hashes"])
        self.assertIn("manifest_schema_sha256", result["hashes"])
        verify.assert_public_safe_result(result)

    def test_unknown_result_fields_are_rejected_even_when_values_look_safe(self):
        result = verify.run_conformance(
            verify.resolve_registered_paths(ROOT, registered_namespace()),
            "2026-07-24T04:00:00Z",
        )
        result["components"]["event"]["unexpected"] = "safe-looking"

        with self.assertRaisesRegex(ContractError, "INTERFACE_RESULT_UNSAFE"):
            verify.assert_public_safe_result(result)

class IntegratedRunnerTests(unittest.TestCase):
    def _temporary_root(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        for literal in verify.TRUSTED.values():
            if literal == verify.TRUSTED["result"]:
                continue
            source = ROOT / literal
            target = root / literal
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        product_source = ROOT / verify.PRODUCT_SCHEMA_LITERAL
        product_target = root / verify.PRODUCT_SCHEMA_LITERAL
        product_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(product_source, product_target)
        return temporary, root

    def test_integrated_registered_catalogs_pass_with_closed_public_counts(self):
        result = verify.run_conformance(
            verify.resolve_registered_paths(ROOT, registered_namespace()),
            "2026-07-24T04:00:00Z",
        )

        self.assertEqual(
            {
                "gate_id",
                "profile_id",
                "command_id",
                "status",
                "observed_at",
                "hashes",
                "components",
                "assertions",
            },
            set(result),
        )
        self.assertEqual("PASSED", result["status"])
        self.assertEqual(
            {"api_version": 16, "api_boundary": 28, "event": 26, "manifest": 34},
            {
                name: component["total"]
                for name, component in result["components"].items()
            },
        )
        self.assertTrue(all(item["failed"] == 0 for item in result["components"].values()))
        self.assertEqual(0, result["assertions"]["negative_effect_calls"])
        self.assertTrue(result["assertions"]["no_sensitive_content"])
        self.assertTrue(is_strict_utc(result["observed_at"]))
        self.assertEqual(7, len(result["hashes"]))

    def test_first_append_source_main_decision_hash_mismatch_is_provenance_invalid(self):
        temporary, root = self._temporary_root()
        self.addCleanup(temporary.cleanup)
        suite_path = root / verify.TRUSTED["event_suite"]
        suite = json.loads(suite_path.read_text(encoding="utf-8"))
        first_append = next(
            case for case in suite["positive"] if case["id"] == "first-append"
        )
        first_append["source_main_decisions"]["MDEC-first"]["content_sha256"] = (
            "b" * 64
        )
        suite_path.write_text(json.dumps(suite), encoding="utf-8")

        result = verify.run_conformance(
            verify.resolve_registered_paths(root, registered_namespace()),
            "2026-07-24T04:00:00Z",
        )
        first_append_result = next(
            case
            for case in result["components"]["event"]["cases"]
            if case["case_id"] == "first-append"
        )

        self.assertEqual("EVENT_PROVENANCE_INVALID", first_append_result["actual"])
        self.assertEqual("FAILED", result["status"])
        self.assertEqual(0, result["assertions"]["negative_effect_calls"])

    def test_non_strict_observation_time_is_denied_before_public_result(self):
        paths = verify.resolve_registered_paths(ROOT, registered_namespace())

        with self.assertRaisesRegex(
            ContractError, "INTERFACE_RUNNER_CONTRACT_INVALID"
        ):
            verify.run_conformance(paths, "2026-07-24T04:00:00+00:00")

    def test_corrupt_suite_replaces_registered_result_with_safe_failure(self):
        temporary, root = self._temporary_root()
        self.addCleanup(temporary.cleanup)
        result_path = root / verify.TRUSTED["result"]
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text('{"status":"STALE"}\n', encoding="utf-8")
        (root / verify.TRUSTED["api_version_suite"]).write_bytes(b"not-json")

        exit_code = verify.main(REGISTERED_ARGUMENTS, root=root)
        result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(1, exit_code)
        self.assertEqual(
            {
                "assertions",
                "command_id",
                "failure_code",
                "gate_id",
                "observed_at",
                "profile_id",
                "status",
            },
            set(result),
        )
        self.assertEqual("FAILED", result["status"])
        self.assertEqual("INTERFACE_RUNNER_CONTRACT_INVALID", result["failure_code"])
        serialized = json.dumps(result, sort_keys=True).lower()
        for forbidden in ("not-json", "exception", "payload", "traceback"):
            self.assertNotIn(forbidden, serialized)
        self.assertFalse(result_path.with_suffix(result_path.suffix + ".tmp").exists())

    def test_invalid_result_argument_writes_only_registered_failure_target(self):
        temporary, root = self._temporary_root()
        self.addCleanup(temporary.cleanup)
        arguments = copy.deepcopy(REGISTERED_ARGUMENTS)
        result_index = arguments.index("--result") + 1
        arguments[result_index] = "artifacts/verification/untrusted.json"

        self.assertEqual(1, verify.main(arguments, root=root))

        registered = root / verify.TRUSTED["result"]
        untrusted = root / arguments[result_index]
        result = json.loads(registered.read_text(encoding="utf-8"))
        self.assertEqual("INTERFACE_RUNNER_CONTRACT_INVALID", result["failure_code"])
        self.assertFalse(untrusted.exists())

    def test_cli_parse_error_writes_closed_failure_without_parser_detail(self):
        temporary, root = self._temporary_root()
        self.addCleanup(temporary.cleanup)

        self.assertEqual(1, verify.main(["--openapi"], root=root))

        result_path = root / verify.TRUSTED["result"]
        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual("INTERFACE_RUNNER_CONTRACT_INVALID", result["failure_code"])
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertNotIn("expected one argument", serialized)
        self.assertNotIn("usage", serialized)

    def test_tampered_public_category_is_replaced_by_safe_failure(self):
        temporary, root = self._temporary_root()
        self.addCleanup(temporary.cleanup)
        suite_path = root / verify.TRUSTED["manifest_suite"]
        suite = json.loads(suite_path.read_text(encoding="utf-8"))
        suite["positive"][0]["kind"] = "UNTRUSTED_RAW_MARKER"
        suite_path.write_text(json.dumps(suite), encoding="utf-8")

        self.assertEqual(1, verify.main(REGISTERED_ARGUMENTS, root=root))

        result = json.loads(
            (root / verify.TRUSTED["result"]).read_text(encoding="utf-8")
        )
        self.assertEqual("INTERFACE_RUNNER_CONTRACT_INVALID", result["failure_code"])
        self.assertNotIn("UNTRUSTED_RAW_MARKER", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
