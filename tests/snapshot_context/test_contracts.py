import copy
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_SCHEMA = ROOT / "contracts/forgeops-snapshot-contract/1.0/schema.json"
CONTEXT_SCHEMA = ROOT / "contracts/forgeops-context-pack/1.0/schema.json"
SNAPSHOT_SUITE = ROOT / "fixtures/forgeops-snapshot-baseline/suite.json"
CONTEXT_SUITE = ROOT / "fixtures/forgeops-context-security/suite.json"

SNAPSHOT_CASES = (
    "POSITIVE_CLEAN_REPEAT",
    "POSITIVE_DIRTY_STAGED_MODIFIED_UNTRACKED",
    "POSITIVE_WORKSPACE_SEPARATION",
    "NEGATIVE_SOURCE_NOT_GIT",
    "NEGATIVE_PATH_TRAVERSAL",
    "NEGATIVE_SYMLINK",
    "NEGATIVE_PROTECTED_PATH",
    "NEGATIVE_CONTENT_CHANGED",
    "NEGATIVE_PROFILE_RAW_SHELL",
    "NEGATIVE_PROFILE_CWD_ESCAPE",
    "NEGATIVE_BASELINE_NONZERO",
    "NEGATIVE_BASELINE_TIMEOUT",
)
CONTEXT_CASES = (
    "POSITIVE_PATH_SELECTION",
    "POSITIVE_CONTENT_SELECTION",
    "POSITIVE_REPEATABLE_PACK",
    "NEGATIVE_EMPTY_QUERY",
    "NEGATIVE_TOP_K_RANGE",
    "NEGATIVE_MANIFEST_HASH_MISMATCH",
    "NEGATIVE_BINARY_EXCLUDED",
    "NEGATIVE_OVERSIZED_EXCLUDED",
    "NEGATIVE_REPOSITORY_INSTRUCTION",
    "NEGATIVE_CONTROL_FIELD_INJECTION",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class SnapshotContextContractTests(unittest.TestCase):
    def test_schemas_are_draft_2020_12_and_closed(self):
        for path, schema_id in (
            (SNAPSHOT_SCHEMA, "contracts/forgeops-snapshot-contract/1.0/schema.json"),
            (CONTEXT_SCHEMA, "contracts/forgeops-context-pack/1.0/schema.json"),
        ):
            with self.subTest(path=path):
                schema = load_json(path)
                self.assertEqual(schema_id, schema["$id"])
                self.assertEqual(
                    "https://json-schema.org/draft/2020-12/schema",
                    schema["$schema"],
                )
                self.assertFalse(schema["additionalProperties"])
                Draft202012Validator.check_schema(schema)

    def test_snapshot_schema_accepts_manifest_and_rejects_unknown_field(self):
        schema = load_json(SNAPSHOT_SCHEMA)
        validator = Draft202012Validator(schema)
        manifest = {
            "snapshot_version": "1.0",
            "snapshot_id": "sha256:" + "a" * 64,
            "source": {
                "repository_label": "fixture-repository",
                "head_sha": "b" * 40,
                "git_state_sha256": "c" * 64,
            },
            "dirty": True,
            "entries": [
                {
                    "path": "src/app.py",
                    "size": 12,
                    "sha256": "d" * 64,
                    "mode": "100644",
                    "source_states": ["tracked", "staged", "modified"],
                }
            ],
            "deleted_paths": ["src/old.py"],
            "manifest_sha256": "a" * 64,
        }
        self.assertEqual([], list(validator.iter_errors(manifest)))
        invalid = copy.deepcopy(manifest)
        invalid["authority"] = {"write_scope": "PROJECT"}
        self.assertTrue(list(validator.iter_errors(invalid)))

    def test_snapshot_schema_contains_closed_baseline_artifact(self):
        schema = load_json(SNAPSHOT_SCHEMA)
        baseline_schema = schema["$defs"]["baseline_artifact"]
        validator = Draft202012Validator(baseline_schema)
        artifact = {
            "baseline_version": "1.0",
            "snapshot_id": "sha256:" + "a" * 64,
            "profile_id": "fixture-baseline",
            "profile_version": "1.0",
            "status": "BASELINE_UNHEALTHY",
            "started_at": "2026-08-01T00:00:00Z",
            "completed_at": "2026-08-01T00:00:01Z",
            "commands": [
                {
                    "command_id": "fixture-fail",
                    "argv": ["python", "-c", "raise SystemExit(1)"],
                    "cwd": ".",
                    "status": "BASELINE_UNHEALTHY",
                    "exit_code": 1,
                    "stdout_bytes_seen": 0,
                    "stderr_bytes_seen": 0,
                    "output_truncated": False,
                    "result_fingerprint": "e" * 64,
                }
            ],
            "summary": {"total": 1, "passed": 0, "failed": 1, "not_run": 0},
        }
        self.assertEqual([], list(validator.iter_errors(artifact)))
        artifact["commands"][0]["stdout"] = "private output"
        self.assertTrue(list(validator.iter_errors(artifact)))

    def test_context_schema_accepts_untrusted_items_and_forbids_control_fields(self):
        schema = load_json(CONTEXT_SCHEMA)
        validator = Draft202012Validator(schema)
        context_pack = {
            "context_pack_version": "1.0",
            "snapshot_id": "sha256:" + "a" * 64,
            "query_tokens": ["calculator"],
            "items": [
                {
                    "path": "src/calculator.py",
                    "sha256": "b" * 64,
                    "size": 20,
                    "media_type": "text/plain",
                    "selection_reason": ["PATH_SUBSTRING"],
                    "score": 100,
                    "excerpt": "def calculator(): pass",
                    "trust": "UNTRUSTED_SOURCE",
                }
            ],
            "summary": {"selected": 1, "excluded_binary": 0, "excluded_oversized": 0},
            "control_claims_accepted": False,
        }
        self.assertEqual([], list(validator.iter_errors(context_pack)))
        invalid = copy.deepcopy(context_pack)
        invalid["authority"] = {"read_scope": "PROJECT"}
        self.assertTrue(list(validator.iter_errors(invalid)))

    def test_fixture_case_catalogs_are_exact_and_unique(self):
        snapshot = load_json(SNAPSHOT_SUITE)
        context = load_json(CONTEXT_SUITE)
        self.assertEqual(
            {
                "suite_id",
                "suite_version",
                "snapshot_schema_ref",
                "context_schema_ref",
                "trusted_profile",
                "cases",
            },
            set(snapshot),
        )
        self.assertEqual(
            {
                "suite_id",
                "suite_version",
                "snapshot_schema_ref",
                "context_schema_ref",
                "cases",
            },
            set(context),
        )
        self.assertEqual(SNAPSHOT_CASES, tuple(case["id"] for case in snapshot["cases"]))
        self.assertEqual(CONTEXT_CASES, tuple(case["id"] for case in context["cases"]))
        self.assertEqual(len(SNAPSHOT_CASES), len(set(SNAPSHOT_CASES)))
        self.assertEqual(len(CONTEXT_CASES), len(set(CONTEXT_CASES)))


if __name__ == "__main__":
    unittest.main()
