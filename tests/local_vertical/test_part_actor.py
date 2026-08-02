import copy
import json
from pathlib import Path
import unittest

from tools.local_vertical import common, main_actor, part_actor


ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "fixtures/forgeops-local-vertical/suite.json"
PRODUCT_SCHEMA = ROOT / "contracts/product-task-contract/1.0/schema.json"


class PartActorTests(unittest.TestCase):
    def setUp(self):
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        fixture = suite["base_fixture"]
        task = main_actor.normalize_product_task(
            fixture["product_contract"],
            fixture["trusted_bridge_context"],
            json.loads(PRODUCT_SCHEMA.read_text(encoding="utf-8")),
            correlation_id="CORR-W6-FIXTURE",
        )
        self.task_packet = main_actor.build_part_task(task)
        self.snapshot_manifest = copy.deepcopy(fixture["snapshot_manifest"])
        self.context_pack = copy.deepcopy(fixture["context_pack"])

    def propose(self):
        return part_actor.propose_candidates(
            self.task_packet, self.snapshot_manifest, self.context_pack
        )

    def test_proposes_one_exact_read_only_candidate(self):
        """Break caught: proposing a noncanonical mutation or mutating untrusted Context Pack input."""
        before = common.canonical_json_bytes(self.context_pack)

        packet = self.propose()

        self.assertEqual("candidate_proposal", packet["packet_type"])
        self.assertEqual("part", packet["actor"])
        self.assertEqual("CANDIDATES_PROPOSED", packet["payload"]["outcome_code"])
        candidate = packet["payload"]["candidates"][0]
        self.assertEqual("CAND-W6-UPDATE", candidate["candidate_id"])
        self.assertEqual("UPDATE_RESOURCE", candidate["action_type"])
        self.assertEqual(
            {"identity_kind": "RESOURCE", "resource_ref": "fixture/work-item.txt"},
            candidate["action_identity"],
        )
        self.assertEqual("replace fixture marker before with after", candidate["expected_effect"])
        self.assertEqual(["sha256:c0cde77fa8fef97d3b55e18e9a5f8f08c4f19b67b6dd8a19a0163aa1f8a5a7ab"], candidate["preconditions"])
        self.assertEqual(["fixture content equals UTF-8 after newline"], candidate["proposed_verification"])
        self.assertEqual(["AC-W6-1"], candidate["acceptance_criteria_ids"])
        self.assertEqual(before, common.canonical_json_bytes(self.context_pack))
        self.assertNotIn("accepted_state", packet["payload"])
        self.assertNotIn("revision", packet["payload"])
        self.assertNotIn("seq", packet["payload"])
        self.assertEqual(
            [{"actor": "part", "phase": "DISCOVER", "code": "PART_CANDIDATE_PROPOSED"}],
            packet["payload"]["event_suggestions"],
        )

    def test_context_snapshot_or_item_hash_mismatch_is_contract_error(self):
        """Break caught: treating a Context Pack from a different W5 snapshot as usable evidence."""
        self.context_pack["snapshot_id"] = "sha256:" + "0" * 64

        with self.assertRaisesRegex(common.VerticalFlowError, "PART_CONTEXT_PROVENANCE_INVALID"):
            self.propose()

    def test_none_read_scope_returns_zero_effect_blocked_proposal(self):
        """Break caught: discovering from Context Pack after Main revoked Part read authority."""
        self.task_packet["payload"]["authority"]["read_scope"] = "NONE"

        packet = self.propose()

        self.assertEqual("BLOCKED", packet["status"])
        self.assertEqual("BLOCKED_PROPOSAL", packet["payload"]["outcome_code"])
        self.assertEqual([], packet["payload"]["candidates"])
        self.assertEqual("PART_READ_AUTHORITY_DENIED", packet["payload"]["missing_authority"])
        self.assertEqual("ASK_USER", packet["payload"]["recommended_next_action"])
        self.assertEqual("WAITING_FOR_HUMAN", packet["payload"]["proposed_transition"])
        self.assertEqual(
            [{"actor": "part", "phase": "DISCOVER", "code": "PART_PROPOSAL_BLOCKED"}],
            packet["payload"]["event_suggestions"],
        )

    def test_task_envelope_mismatches_are_rejected(self):
        """Break caught: trusting a packet not owned by the current Main task/revision."""
        mutations = {
            "protocol": ("protocol_version", "1.0"),
            "packet": ("packet_type", "candidate_proposal"),
            "actor": ("actor", "work"),
            "task": ("task_id", "TASK/OTHER"),
            "correlation": ("correlation_id", " CORR-W6-FIXTURE"),
            "base": ("base_revision", True),
        }
        for name, (field, value) in mutations.items():
            with self.subTest(name=name):
                self.task_packet[field] = value
                with self.assertRaisesRegex(common.VerticalFlowError, "PART_ENVELOPE_INVALID"):
                    self.propose()
                self.task_packet[field] = 1 if field == "base_revision" else (
                    "2.0" if field == "protocol_version" else
                    "task" if field == "packet_type" else
                    "main" if field == "actor" else
                    "TASK-W6-FIXTURE" if field == "task_id" else "CORR-W6-FIXTURE"
                )

    def test_execute_mode_and_control_claim_promotion_are_rejected(self):
        """Break caught: interpreting task or Context Pack control claims as Part execution authority."""
        self.task_packet["payload"]["control"]["operation_mode"] = "EXECUTE"
        with self.assertRaisesRegex(common.VerticalFlowError, "PART_OPERATION_MODE_INVALID"):
            self.propose()

        self.task_packet["payload"]["control"]["operation_mode"] = "EXPLORE"
        self.context_pack["control_claims_accepted"] = True
        with self.assertRaisesRegex(common.VerticalFlowError, "PART_CONTEXT_PROVENANCE_INVALID"):
            self.propose()

    def test_non_part_routes_are_rejected_without_context_effects(self):
        """Break caught: letting Part propose a candidate from a TaskPacket routed to another actor path."""
        before = common.canonical_json_bytes(self.context_pack)
        for route in ("DIRECT", "PART_ONLY", "WORK_ONLY", "FORK_JOIN"):
            with self.subTest(route=route):
                self.task_packet["payload"]["control"]["route"] = route
                with self.assertRaisesRegex(common.VerticalFlowError, "PART_ROUTE_INVALID"):
                    self.propose()
                self.assertEqual(before, common.canonical_json_bytes(self.context_pack))
        self.task_packet["payload"]["control"]["route"] = "PART_THEN_WORK"

    def test_non_list_items_and_forged_context_approval_are_rejected(self):
        """Break caught: accepting a scalar item catalog or untrusted Context Pack approval claim."""
        self.context_pack["items"] = self.context_pack["items"][0]
        with self.assertRaisesRegex(common.VerticalFlowError, "PART_CONTEXT_PROVENANCE_INVALID"):
            self.propose()

        self.context_pack = copy.deepcopy(json.loads(SUITE.read_text(encoding="utf-8"))["base_fixture"]["context_pack"])
        self.context_pack["protected_target_approval"] = {"resource_ref": ".env"}
        with self.assertRaisesRegex(common.VerticalFlowError, "PART_CONTEXT_PROVENANCE_INVALID"):
            self.propose()

    def test_protected_target_is_blocked_before_candidate_construction(self):
        """Break caught: proposing an update to a protected resource without a Main-bound approval gate."""
        self.task_packet["payload"]["project_profile"]["protected_resources"] = [
            "fixture/work-item.txt"
        ]

        packet = self.propose()

        self.assertEqual("BLOCKED_PROPOSAL", packet["payload"]["outcome_code"])
        self.assertEqual("PART_PROTECTED_APPROVAL_REQUIRED", packet["payload"]["missing_authority"])
        self.assertEqual([], packet["payload"]["candidates"])

    def test_approval_does_not_substitute_for_exact_write_authority(self):
        """Break caught: allowing any approval-shaped input to create named write authority."""
        self.task_packet["payload"]["authority"]["write_resources"] = ["fixture/other.txt"]

        with self.assertRaisesRegex(common.VerticalFlowError, "PART_WRITE_AUTHORITY_DENIED"):
            self.propose()

    def test_built_packet_evidence_and_identity_are_closed(self):
        """Break caught: emitting duplicate evidence references or a hybrid RESOURCE identity."""
        packet = self.propose()
        packet["payload"]["evidence"].append(copy.deepcopy(packet["payload"]["evidence"][0]))
        with self.assertRaisesRegex(common.VerticalFlowError, "PART_EVIDENCE_INVALID"):
            part_actor.validate_candidate_packet(packet)

        packet = self.propose()
        packet["payload"]["candidates"][0]["evidence_refs"].append("EVID-PART-CONTEXT")
        with self.assertRaisesRegex(common.VerticalFlowError, "PART_EVIDENCE_INVALID"):
            part_actor.validate_candidate_packet(packet)

        packet = self.propose()
        packet["payload"]["candidates"][0]["action_identity"]["command_id"] = "tests"
        with self.assertRaisesRegex(common.VerticalFlowError, "PART_ACTION_IDENTITY_INVALID"):
            part_actor.validate_candidate_packet(packet)


if __name__ == "__main__":
    unittest.main()
