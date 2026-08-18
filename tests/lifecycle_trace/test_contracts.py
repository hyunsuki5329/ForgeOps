import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "contracts/forgeops-lifecycle-trace/1.0/schema.json"
SUITE = ROOT / "fixtures/forgeops-lifecycle-trace/suite.json"

COMMAND_CASES = {
    "budget-cancel-negative": (
        "POSITIVE_BUDGETED_SUCCESS", "POSITIVE_CANCEL_CLEANUP",
        "NEGATIVE_TIME_LIMIT", "NEGATIVE_TOKEN_LIMIT", "NEGATIVE_TOOL_LIMIT",
        "NEGATIVE_COMMAND_LIMIT", "NEGATIVE_REPAIR_LIMIT", "NEGATIVE_COST_LIMIT",
        "NEGATIVE_DISPATCH_AFTER_LIMIT", "NEGATIVE_DISPATCH_AFTER_CANCEL",
        "NEGATIVE_PROCESS_RESIDUE", "NEGATIVE_MOUNT_RESIDUE",
        "NEGATIVE_LEASE_RESIDUE", "NEGATIVE_SECRET_RESIDUE",
        "NEGATIVE_WORKSPACE_RESIDUE", "NEGATIVE_CLEANUP_NOT_IDEMPOTENT",
    ),
    "no-progress-stop": (
        "POSITIVE_PROGRESS_CONTINUES", "POSITIVE_SIGNATURE_CHANGE_CONTINUES",
        "NEGATIVE_IDENTICAL_SIGNATURE", "NEGATIVE_EVIDENCE_UNCHANGED",
        "NEGATIVE_DIFF_UNCHANGED", "NEGATIVE_NO_PROGRESS_LIMIT",
        "NEGATIVE_REPAIR_AFTER_STOP", "NEGATIVE_BUDGET_PRECEDENCE",
        "NEGATIVE_NONCANONICAL_SIGNATURE", "NEGATIVE_UNTRUSTED_PROGRESS",
    ),
    "trace-manifest-completeness": (
        "POSITIVE_SUCCESS_TRACE", "POSITIVE_CANCEL_TRACE", "POSITIVE_BUDGET_TRACE",
        "NEGATIVE_EVENT_GAP", "NEGATIVE_EVENT_REORDER", "NEGATIVE_REVISION_DECREASE",
        "NEGATIVE_ACTOR_INVALID", "NEGATIVE_EVIDENCE_DANGLING",
        "NEGATIVE_ARTIFACT_DANGLING", "NEGATIVE_CLEANUP_MISSING",
        "NEGATIVE_TERMINAL_REASON", "NEGATIVE_NEXT_ACTION",
    ),
    "external-write-negative": (
        "POSITIVE_NO_EXTERNAL_WRITE", "NEGATIVE_DIRECT_PUBLISH",
        "NEGATIVE_GATEWAY_BYPASS", "NEGATIVE_REMOTE_TARGET",
        "NEGATIVE_APPROVAL_ABSENT", "NEGATIVE_APPROVAL_MISMATCH",
        "NEGATIVE_DUPLICATE_EFFECT", "NEGATIVE_DENIAL_NOT_TRACED",
        "NEGATIVE_EFFECT_OBSERVED", "NEGATIVE_RAW_SECRET",
    ),
}


class LifecycleTraceContractTests(unittest.TestCase):
    def test_schema_and_exact_catalog_are_closed(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual([], list(Draft202012Validator(schema).iter_errors(suite)))
        expected = tuple(case for cases in COMMAND_CASES.values() for case in cases)
        self.assertEqual(expected, tuple(case["id"] for case in suite["cases"]))
        self.assertEqual(48, len(set(expected)))
        for command, ids in COMMAND_CASES.items():
            self.assertEqual(ids, tuple(c["id"] for c in suite["cases"] if c["command_id"] == command))

    def test_public_result_keeps_os_observations_null(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        result_schema = {"$ref": "#/$defs/publicResult", "$defs": schema["$defs"]}
        result = {
            "result_version": "1.0", "gate_id": "VG-014",
            "profile_id": "forgeops-lifecycle-budget", "command_id": "budget-cancel-negative",
            "status": "PASSED", "evidence_tier": "E2", "observed_at": "2026-08-19T00:00:00Z",
            "input_hashes": {"schema": "a"*64, "suite": "b"*64, "profile_source": "c"*64},
            "summary": {"total": 0, "passed": 0, "failed": 0},
            "effect_counters": {"source_tree_hash_unchanged": True, "unauthorized_dispatches": 0,
                "adapter_cleanup_residues": 0, "external_write_attempts": 0,
                "result_artifact_raw_secret_occurrences": 0, "os_process_tree_residue": None,
                "os_mount_residue": None, "network_calls": None}, "cases": []}
        self.assertEqual([], list(Draft202012Validator(result_schema).iter_errors(result)))
        result["effect_counters"]["network_calls"] = 0
        self.assertTrue(list(Draft202012Validator(result_schema).iter_errors(result)))

    def test_agents_registers_four_commands_and_two_profiles(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        expected = {
            "budget-cancel-negative": "artifacts/verification/vg-014-budget-cancel-result.json",
            "no-progress-stop": "artifacts/verification/vg-014-no-progress-result.json",
            "trace-manifest-completeness": "artifacts/verification/vg-015-trace-manifest-result.json",
            "external-write-negative": "artifacts/verification/vg-015-external-write-result.json",
        }
        positions = []
        for command, path in expected.items():
            marker = f"    - id: {command}\n"
            positions.append(text.index(marker))
            block = text[text.index(marker):text.index(marker)+600]
            self.assertIn("python tools/lifecycle_trace/verify.py", block)
            self.assertIn(f"--result {path}", block)
            self.assertIn("evidence_tier: E2", block)
        self.assertEqual(sorted(positions), positions)
        self.assertIn("        - id: forgeops-lifecycle-budget\n", text)
        self.assertIn("        - id: forgeops-trace-manifest\n", text)

    def test_w8_scope_is_not_completed_early(self):
        wbs = (ROOT / "docs/project/wbs.md").read_text(encoding="utf-8")
        for number in (23, 24, 25):
            line = next(line for line in wbs.splitlines() if line.startswith(f"| WBS-0{number}"))
            self.assertIn("| WBS_NOT_STARTED |", line)
        self.assertIn("W8 lifecycle/trace scope note", wbs)
        self.assertIn("VG-008 E3", wbs)


if __name__ == "__main__":
    unittest.main()
