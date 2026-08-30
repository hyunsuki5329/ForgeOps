import copy
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator
import yaml


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "contracts/forgeops-phase1-safety/1.0/schema.json"
SUITE = ROOT / "fixtures/forgeops-phase1-safety/suite.json"

EXPECTED_COMMANDS = (
    "resource-authority-negative",
    "protected-read-negative",
    "command-network-negative",
    "approval-negative-fixture",
    "image-provenance-negative",
    "containment-egress-negative",
    "teardown-negative",
    "secret-surface-negative",
    "artifact-isolation-negative",
    "snapshot-identity",
    "baseline-retrieval-repeat",
    "context-provenance",
    "injection-negative",
    "main-part-work-main",
    "task-checks",
    "regression-checks",
    "verification-anti-tamper",
    "budget-cancel-negative",
    "no-progress-stop",
    "trace-manifest-completeness",
    "external-write-negative",
    "evidence-positive-negative",
    "extension-provenance",
)

SECURITY_NEGATIVE = tuple(
    command
    for command in EXPECTED_COMMANDS
    if command not in {"snapshot-identity", "baseline-retrieval-repeat", "main-part-work-main"}
)

REQUIRED_EVIDENCE = tuple(
    command
    for command in EXPECTED_COMMANDS
    if command
    not in {
        "resource-authority-negative",
        "protected-read-negative",
        "command-network-negative",
        "approval-negative-fixture",
    }
)


def _assert_closed_objects(test: unittest.TestCase, node: object, location: str = "$") -> None:
    if isinstance(node, dict):
        node_type = node.get("type")
        if node_type == "object" or "properties" in node:
            test.assertIs(node.get("additionalProperties"), False, location)
        for key, value in node.items():
            _assert_closed_objects(test, value, f"{location}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _assert_closed_objects(test, value, f"{location}[{index}]")


def _project_profile() -> dict:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    fenced = text.split("~~~yaml\n", 1)[1].split("\n~~~", 1)[0]
    return yaml.safe_load(fenced)


class Phase1SafetyContractTests(unittest.TestCase):
    def test_schema_is_closed_and_accepts_exact_suite(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        suite = json.loads(SUITE.read_text(encoding="utf-8"))

        Draft202012Validator.check_schema(schema)
        _assert_closed_objects(self, schema)
        self.assertEqual([], list(Draft202012Validator(schema).iter_errors(suite)))

    def test_registry_and_subsets_have_exact_order_and_cardinality(self):
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        commands = tuple(item["command_id"] for item in suite["registrations"])

        self.assertEqual(EXPECTED_COMMANDS, commands)
        self.assertEqual(23, len(set(commands)))
        self.assertEqual(SECURITY_NEGATIVE, tuple(suite["subsets"]["security_negative"]))
        self.assertEqual(20, len(suite["subsets"]["security_negative"]))
        self.assertEqual(REQUIRED_EVIDENCE, tuple(suite["subsets"]["required_evidence"]))
        self.assertEqual(19, len(suite["subsets"]["required_evidence"]))
        for item in suite["registrations"]:
            expected_time_field = "time" if item["gate_id"] == "VG-008" else "observed_at"
            self.assertEqual(expected_time_field, item["observed_at_field"])

    def test_schema_rejects_unknown_suite_and_result_fields(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        suite["unknown"] = True
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(suite)))

        result_schema = {"$ref": "#/$defs/gateResult", "$defs": schema["$defs"]}
        result = {
            "result_version": "1.0",
            "phase_id": "phase-1-safety",
            "profile_id": "forgeops-phase1-safety",
            "command_id": "phase1-safety-gate",
            "status": "NOT_READY",
            "evidence_tier": "E3",
            "source_identity": {
                "repository": "example/forgeops",
                "repository_id": "123",
                "default_branch": "main",
                "workflow_ref": "refs/heads/main",
                "source_sha": "a" * 40,
                "workflow_sha": "a" * 40,
                "run_id": "1001",
                "run_attempt": 1,
            },
            "validated_at": "2026-08-29T00:00:00Z",
            "registry_sha256": "b" * 64,
            "summary": {"total": 19, "passed": 0, "failed": 19, "blockers": 1},
            "effect_counters": {
                "unauthorized_executions": 0,
                "approval_bypasses": 0,
                "containment_or_egress_escapes": 0,
                "injection_acceptances": 0,
                "raw_secret_occurrences": 0,
                "cleanup_failures": 0,
                "evidence_integrity_failures": 0,
                "external_writes": 0,
            },
            "gates": [
                {
                    "gate_id": "VG-008",
                    "profile_id": "forgeops-sandbox-security",
                    "command_id": "teardown-negative",
                    "artifact_ref": "artifacts/verification/vg-008-teardown-result.json",
                    "required_tier": "E3",
                    "observed_tier": None,
                    "status": "NOT_RUN",
                    "observed_at": None,
                    "source_current": True,
                    "public_safe": False,
                    "blocker_codes": ["ARTIFACT_MISSING"],
                }
                for _ in range(19)
            ],
            "blockers": [
                {"gate_id": "VG-008", "command_id": "teardown-negative", "reason_code": "ARTIFACT_MISSING"}
            ],
        }
        self.assertEqual([], list(Draft202012Validator(result_schema).iter_errors(result)))
        result["unknown"] = True
        self.assertTrue(list(Draft202012Validator(result_schema).iter_errors(result)))

    def test_agents_registers_exact_w9_profile_and_commands(self):
        profile = _project_profile()["project_profile"]
        commands = {item["id"]: item for item in profile["validation_commands"]}
        expected = {
            "phase1-security-negative": "artifacts/verification/phase-1-security-negative-result.json",
            "phase1-evidence-freshness": "artifacts/verification/phase-1-evidence-freshness-result.json",
            "phase1-safety-gate": "artifacts/verification/phase-1-safety-gate-result.json",
        }
        for command_id, result_ref in expected.items():
            command = commands[command_id]
            self.assertIn("python tools/phase1_safety/verify.py", command["command"])
            self.assertIn(f"--result {result_ref}", command["command"])
            self.assertEqual("E3", command["evidence_tier"])
            self.assertTrue(command["required"])
        profiles = profile["extensions"]["forgeops"]["verification_profiles"]
        selected = [item for item in profiles if item["id"] == "forgeops-phase1-safety"]
        self.assertEqual(1, len(selected))
        self.assertEqual(list(expected), selected[0]["command_ids"])

    def test_stage_a_docs_keep_w9_incomplete_until_protected_main_evidence_import(self):
        documents = {
            relative: (ROOT / relative).read_text(encoding="utf-8")
            for relative in (
                "docs/project/wbs.md",
                "docs/project/requirements-traceability-matrix.md",
                "docs/quality/verification-and-evaluation-plan.md",
                "docs/architecture/system-architecture.md",
                "docs/security/threat-model.md",
            )
        }
        wbs = documents["docs/project/wbs.md"]
        for wbs_id in ("WBS-026", "WBS-027", "WBS-028"):
            row = next(line for line in wbs.splitlines() if line.startswith(f"| {wbs_id} |"))
            self.assertIn("| WBS_NOT_STARTED |", row)
        combined = "\n".join(documents.values())
        for required in (
            "23개",
            "20개",
            "19개",
            "protected `main`",
            "2-job",
            "evidence-only PR",
            "VG-024",
            "Phase 1 Exit",
        ):
            self.assertIn(required, combined)
        self.assertIn("E3 5개", combined)
        self.assertIn("E2 이상 14개", combined)
        self.assertIn("8개 normalized effect counter", combined)

if __name__ == "__main__":
    unittest.main()
