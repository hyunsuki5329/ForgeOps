import copy
import hashlib
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "contracts/forgeops-patch-verification/1.0/schema.json"
SUITE = ROOT / "fixtures/forgeops-patch-verification/suite.json"
WBS_COLUMNS = (
    "id", "phase", "week", "status", "person_day", "predecessor",
    "prd_ids", "deliverable", "definition_of_done", "vg_ids", "evidence_types",
)

COMMAND_CASE_IDS = {
    "task-checks": (
        "POSITIVE_BOUNDED_PATCH",
        "NEGATIVE_ABSOLUTE_RESOURCE",
        "NEGATIVE_TRAVERSAL_RESOURCE",
        "NEGATIVE_UNKNOWN_RESOURCE",
        "NEGATIVE_BEFORE_HASH_MISMATCH",
        "NEGATIVE_SOURCE_AS_WORKSPACE",
        "NEGATIVE_WORKSPACE_SYMLINK_ESCAPE",
        "NEGATIVE_DIFF_LIMIT",
        "NEGATIVE_RAW_PATCH_INPUT",
    ),
    "regression-checks": (
        "POSITIVE_TRUSTED_CHECKS",
        "NEGATIVE_TASK_CHECK_FAILURE",
        "NEGATIVE_NEW_REGRESSION",
        "NEGATIVE_BASELINE_UNHEALTHY",
        "NEGATIVE_LINT_FAILURE",
        "NEGATIVE_TYPECHECK_FAILURE",
        "NEGATIVE_UNKNOWN_PROFILE",
        "NEGATIVE_PROFILE_DIGEST_MISMATCH",
        "NEGATIVE_STALE_EVIDENCE",
    ),
    "verification-anti-tamper": (
        "POSITIVE_GUARDS_UNCHANGED",
        "NEGATIVE_TEST_DELETE",
        "NEGATIVE_SKIP_INJECTION",
        "NEGATIVE_XFAIL_INJECTION",
        "NEGATIVE_ASSERTION_WEAKEN",
        "NEGATIVE_COVERAGE_EXCLUSION",
        "NEGATIVE_PROFILE_CHANGE",
        "NEGATIVE_TEST_SYMLINK",
        "NEGATIVE_TEST_RENAME",
    ),
}

EXPECTED_HASHES = {
    "src/calculator.py": "d7c0073ac57f6b7f11d524b13b0eb3a0badc43380985b593aa7a59b6b0d1b461",
    "tests/test_calculator.py": "9de315c74fa479ed3f924a2a38bbe5752cec3675d8175310e172a7052409f0ea",
    ".coveragerc": "ee199da3fd728b9e24cc6ffe76dc69adf4db903056e1d56801d3163608e35dcd",
    "verification-profile.json": "78891da4564a528c252606a97db065c9b784dd1d79c99384f2488f0ff64eb826",
}


def _load() -> tuple[dict[str, object], dict[str, object]]:
    return (
        json.loads(SCHEMA.read_text(encoding="utf-8")),
        json.loads(SUITE.read_text(encoding="utf-8")),
    )


def _parse_wbs_rows() -> dict[str, dict[str, str]]:
    records = {}
    for line in (ROOT / "docs/project/wbs.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("| WBS-"):
            continue
        values = tuple(value.strip() for value in line.strip("|").split("|"))
        if len(values) == len(WBS_COLUMNS):
            record = dict(zip(WBS_COLUMNS, values, strict=True))
            records[record["id"]] = record
    return records


def _comma_ids(raw: str) -> tuple[str, ...]:
    return tuple(value.strip() for value in raw.split(",") if value.strip())


class PatchVerificationContractTests(unittest.TestCase):
    def test_schema_validates_the_exact_closed_suite_and_catalog(self):
        schema, suite = _load()
        self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
        Draft202012Validator.check_schema(schema)
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual([], list(Draft202012Validator(schema).iter_errors(suite)))

        expected = tuple(
            case_id
            for command_id in COMMAND_CASE_IDS
            for case_id in COMMAND_CASE_IDS[command_id]
        )
        self.assertEqual(expected, tuple(case["id"] for case in suite["cases"]))
        self.assertEqual(27, len({case["id"] for case in suite["cases"]}))
        for command_id, ids in COMMAND_CASE_IDS.items():
            self.assertEqual(
                ids,
                tuple(case["id"] for case in suite["cases"] if case["command_id"] == command_id),
            )

    def test_fixture_hashes_and_patch_identity_are_hand_derived(self):
        _, suite = _load()
        files = {item["path"]: item for item in suite["base_fixture"]["files"]}
        for path, expected in EXPECTED_HASHES.items():
            with self.subTest(path=path):
                content = files[path]["content"].encode("utf-8")
                self.assertEqual(expected, hashlib.sha256(content).hexdigest())
                self.assertEqual(expected, files[path]["sha256"])
        intent = suite["base_fixture"]["patch_intent"]
        self.assertEqual("src/calculator.py", intent["resource_ref"])
        self.assertEqual(EXPECTED_HASHES["src/calculator.py"], intent["before_sha256"])
        self.assertEqual(
            "a735f4673c5cdda031f0e3a32ae62b05c404cbd868f7b491df598d67051c7af1",
            intent["after_sha256"],
        )

    def test_suite_and_result_objects_reject_unknown_fields_and_non_null_unobserved_effects(self):
        schema, suite = _load()
        invalid_suite = copy.deepcopy(suite)
        invalid_suite["unexpected"] = True
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(invalid_suite)))

        result_schema = {"$ref": "#/$defs/publicResult", "$defs": schema["$defs"]}
        result = {
            "result_version": "1.0",
            "gate_id": "VG-013",
            "profile_id": "forgeops-patch-verification",
            "command_id": "task-checks",
            "status": "PASSED",
            "evidence_tier": "E2",
            "observed_at": "2026-08-19T00:00:00Z",
            "input_hashes": {"schema": "a" * 64, "suite": "b" * 64, "profile_source": "c" * 64},
            "profile_digest": "d" * 64,
            "summary": {"total": 9, "passed": 9, "failed": 0},
            "effect_counters": {
                "source_tree_hash_unchanged": True,
                "unauthorized_workspace_effects": 0,
                "outside_workspace_write_attempts": 0,
                "remote_write_attempts": 0,
                "result_artifact_raw_secret_occurrences": 0,
                "host_external_writes": None,
                "network_calls": None,
            },
            "cases": [],
        }
        self.assertEqual([], list(Draft202012Validator(result_schema).iter_errors(result)))
        for field in ("host_external_writes", "network_calls"):
            with self.subTest(field=field):
                invalid = copy.deepcopy(result)
                invalid["effect_counters"][field] = 0
                self.assertTrue(list(Draft202012Validator(result_schema).iter_errors(invalid)))

    def test_agents_registers_exact_w7_commands_and_ordered_profile(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        expected_commands = {
            "task-checks": "artifacts/verification/vg-013-task-checks-result.json",
            "regression-checks": "artifacts/verification/vg-013-regression-checks-result.json",
            "verification-anti-tamper": "artifacts/verification/vg-013-verification-anti-tamper-result.json",
        }
        positions = []
        for command_id, result_path in expected_commands.items():
            marker = f"    - id: {command_id}\n"
            position = text.index(marker)
            positions.append(position)
            block = text[position:position + 700]
            self.assertIn("python tools/patch_verification/verify.py", block)
            self.assertIn(f"--result {result_path}", block)
            self.assertIn(f"--command-id {command_id}", block)
            self.assertIn("evidence_tier: E2", block)
            self.assertIn("required: true", block)
        self.assertEqual(sorted(positions), positions)
        profile = text.index("        - id: forgeops-patch-verification\n")
        profile_block = text[profile:profile + 300]
        self.assertLess(profile_block.index("- task-checks"), profile_block.index("- regression-checks"))
        self.assertLess(profile_block.index("- regression-checks"), profile_block.index("- verification-anti-tamper"))

    def test_wbs_assigns_w7_to_vg013_without_completing_it_early(self):
        rows = _parse_wbs_rows()
        for wbs_id in ("WBS-020", "WBS-021", "WBS-022"):
            with self.subTest(wbs_id=wbs_id):
                self.assertEqual("WBS_NOT_STARTED", rows[wbs_id]["status"])
                self.assertEqual(("VG-013",), _comma_ids(rows[wbs_id]["vg_ids"]))
        wbs = (ROOT / "docs/project/wbs.md").read_text(encoding="utf-8")
        self.assertIn("W7/VG-013 patch verification", wbs)
        self.assertIn("VG-015", wbs)
        self.assertIn("W8", wbs)


if __name__ == "__main__":
    unittest.main()
