import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "contracts/forgeops-local-vertical/1.0/schema.json"
SUITE = ROOT / "fixtures/forgeops-local-vertical/suite.json"
WBS_COLUMNS = (
    "id", "phase", "week", "status", "person_day", "predecessor",
    "prd_ids", "deliverable", "definition_of_done", "vg_ids", "evidence_types",
)

CASE_IDS = (
    "POSITIVE_MAIN_PART_WORK_MAIN",
    "POSITIVE_GATE_WAITING",
    "NEGATIVE_MAIN_PROTOCOL",
    "NEGATIVE_PART_ENVELOPE_MISMATCH",
    "NEGATIVE_PART_READ_NONE",
    "NEGATIVE_CONTEXT_HASH_MISMATCH",
    "NEGATIVE_PART_STATE_OWNERSHIP",
    "NEGATIVE_PROTECTED_NO_APPROVAL",
    "NEGATIVE_APPROVAL_WITHOUT_AUTHORITY",
    "NEGATIVE_HYBRID_IDENTITY",
    "NEGATIVE_SCOPE_LIST_MISMATCH",
    "NEGATIVE_WORK_ENVELOPE_MISMATCH",
    "NEGATIVE_WORK_MODE_EXPLORE",
    "NEGATIVE_WORK_CAPABILITY_UNKNOWN",
    "NEGATIVE_TRUST_APPROVED_ID_INJECTION",
    "NEGATIVE_TRUST_VALIDATION_AT_INJECTION",
    "NEGATIVE_PROJECT_EXECUTE_SCOPE",
    "NEGATIVE_WILDCARD_COMPANION",
    "NEGATIVE_RESOURCE_TRAVERSAL",
    "NEGATIVE_UNSUPPORTED_COMMAND",
    "NEGATIVE_WORK_STALE_REVISION",
    "NEGATIVE_WORK_STATE_OWNERSHIP",
    "NEGATIVE_EVIDENCE_DANGLING",
    "NEGATIVE_EVIDENCE_STALE",
    "NEGATIVE_EVIDENCE_FUTURE",
    "NEGATIVE_EVIDENCE_LOW_TIER",
    "NEGATIVE_CANDIDATE_COVERAGE",
    "NEGATIVE_CRITERION_COVERAGE",
    "NEGATIVE_SUMMARY_MISMATCH",
    "NEGATIVE_MAIN_ACTOR_OWNERSHIP",
)


def parse_wbs_rows() -> dict[str, dict[str, str]]:
    records = {}
    for line in (ROOT / "docs/project/wbs.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("| WBS-"):
            continue
        values = tuple(value.strip() for value in line.strip("|").split("|"))
        if len(values) == len(WBS_COLUMNS):
            record = dict(zip(WBS_COLUMNS, values, strict=True))
            records[record["id"]] = record
    return records


def comma_ids(raw: str) -> tuple[str, ...]:
    return tuple(value.strip() for value in raw.split(",") if value.strip())


class LocalVerticalContractTests(unittest.TestCase):
    def test_schema_and_suite_are_closed_and_exact(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
        self.assertFalse(schema["additionalProperties"])
        Draft202012Validator.check_schema(schema)
        self.assertEqual([], list(Draft202012Validator(schema).iter_errors(suite)))
        self.assertEqual(CASE_IDS, tuple(case["id"] for case in suite["cases"]))
        self.assertEqual(len(CASE_IDS), len(set(CASE_IDS)))

    def test_suite_enforces_the_referenced_product_contract_closure(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        suite["base_fixture"]["product_contract"]["repository"]["unexpected"] = True
        errors = list(Draft202012Validator(schema).iter_errors(suite))
        self.assertTrue(errors)

    def test_suite_enforces_snapshot_entry_source_state_constraints(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        suite["base_fixture"]["snapshot_manifest"]["entries"][0]["source_states"] = []
        errors = list(Draft202012Validator(schema).iter_errors(suite))
        self.assertTrue(errors)

    def test_suite_enforces_context_query_token_constraints(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        suite["base_fixture"]["context_pack"]["query_tokens"] = []
        errors = list(Draft202012Validator(schema).iter_errors(suite))
        self.assertTrue(errors)

    def test_authority_uses_the_canonical_allowed_flag(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        authority = suite["base_fixture"]["trusted_bridge_context"]["canonical_control"]["authority"]
        authority["destructive_actions"] = "ALLOWED"
        authority["external_side_effects"] = "ALLOWED"
        self.assertEqual([], list(Draft202012Validator(schema).iter_errors(suite)))

    def test_authority_rejects_the_legacy_available_flag(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        authority = suite["base_fixture"]["trusted_bridge_context"]["canonical_control"]["authority"]
        authority["destructive_actions"] = "AVAILABLE"
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(suite)))

    def test_suite_enforces_snapshot_path_maximum_length(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        suite["base_fixture"]["snapshot_manifest"]["entries"][0]["path"] = "a" * 4097
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(suite)))

    def test_suite_enforces_snapshot_repository_label_maximum_length(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        suite["base_fixture"]["snapshot_manifest"]["source"]["repository_label"] = "a" * 201
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(suite)))

    def test_suite_enforces_context_media_type_maximum_length(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        suite["base_fixture"]["context_pack"]["items"][0]["media_type"] = "a" * 201
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(suite)))

    def test_suite_rejects_undeclared_trusted_control_claims(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        for field in ("project_profile", "capabilities", "control", "budgets", "tool_schema"):
            with self.subTest(field=field):
                suite = json.loads(SUITE.read_text(encoding="utf-8"))
                controls = suite["base_fixture"]["trusted_bridge_context"]["canonical_control"]
                controls[field]["undeclared_claim"] = "ALLOWED"
                self.assertTrue(list(Draft202012Validator(schema).iter_errors(suite)))

    def test_public_result_requires_unobserved_external_surfaces_to_be_null(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        public_result_schema = {"$ref": "#/$defs/public_result", "$defs": schema["$defs"]}
        result = {
            "result_version": "1.0", "gate_id": "VG-012",
            "profile_id": "forgeops-local-vertical", "command_id": "main-part-work-main",
            "status": "PASSED", "evidence_tier": "E2", "observed_at": "2026-08-02T00:05:00Z",
            "input_hashes": {key: "a" * 64 for key in ("schema", "product_schema", "snapshot_schema", "context_schema", "suite")},
            "summary": {"total": 30, "passed": 30, "failed": 0},
            "effect_counters": {
                "source_tree_hash_unchanged": True, "unauthorized_fixture_effects": 0,
                "result_artifact_raw_secret_occurrences": 0, "protected_reads": None,
                "network_calls": None, "external_writes": None,
            },
            "cases": [],
        }
        for field in ("protected_reads", "network_calls", "external_writes"):
            with self.subTest(field=field):
                invalid = json.loads(json.dumps(result))
                invalid["effect_counters"][field] = 0
                self.assertTrue(list(Draft202012Validator(public_result_schema).iter_errors(invalid)))

    def test_wbs_rows_reassign_exact_contract_ownership_to_w6_and_w7(self):
        rows = parse_wbs_rows()
        self.assertEqual("WBS_DONE", rows["WBS-014"]["status"])
        self.assertEqual(("PRD-FR-008", "PRD-NFR-001"), comma_ids(rows["WBS-014"]["prd_ids"]))
        self.assertEqual(("VG-010",), comma_ids(rows["WBS-014"]["vg_ids"]))
        self.assertEqual(
            ("PRD-FR-010", "PRD-NFR-002", "PRD-NFR-003"),
            comma_ids(rows["WBS-018"]["prd_ids"]),
        )
        self.assertEqual(
            ("VG-005", "VG-006", "VG-012"),
            comma_ids(rows["WBS-018"]["vg_ids"]),
        )
        self.assertEqual(("VG-013",), comma_ids(rows["WBS-021"]["vg_ids"]))
        self.assertEqual(("VG-013",), comma_ids(rows["WBS-022"]["vg_ids"]))
