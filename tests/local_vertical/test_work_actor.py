import copy
from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.local_vertical import common, main_actor, part_actor, work_actor


ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "fixtures/forgeops-local-vertical/suite.json"
PRODUCT_SCHEMA = ROOT / "contracts/product-task-contract/1.0/schema.json"


class WorkActorTests(unittest.TestCase):
    def setUp(self):
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        self.fixture = suite["base_fixture"]
        self.task_packet = main_actor.normalize_product_task(
            self.fixture["product_contract"],
            self.fixture["trusted_bridge_context"],
            json.loads(PRODUCT_SCHEMA.read_text(encoding="utf-8")),
            correlation_id="CORR-W6-FIXTURE",
        )
        self.candidate_packet = part_actor.propose_candidates(
            main_actor.build_part_task(self.task_packet),
            self.fixture["snapshot_manifest"],
            self.fixture["context_pack"],
        )
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.workspace = root / "workspace"
        self.source = root / "source"
        for tree in (self.workspace, self.source):
            (tree / "fixture").mkdir(parents=True)
            (tree / "fixture/work-item.txt").write_bytes(b"before\n")

    def approved_context(self):
        return main_actor.approve_candidates(
            self.task_packet,
            self.candidate_packet,
            approved_candidate_ids=["CAND-W6-UPDATE"],
            validation_at="2026-08-02T00:05:00Z",
            human_review_result=None,
        )

    def assert_trees_unchanged(self):
        self.assertEqual(b"before\n", (self.workspace / "fixture/work-item.txt").read_bytes())
        self.assertEqual(b"before\n", (self.source / "fixture/work-item.txt").read_bytes())

    def test_exact_approved_fixture_update_returns_fresh_e2_work_result(self):
        """Break caught: skipping the bounded update or reporting success without fresh E2 evidence."""
        context = self.approved_context()

        result = work_actor.preflight_execute_verify(
            context,
            workspace_root=self.workspace,
            source_root=self.source,
            clock=lambda: "2026-08-02T00:05:00Z",
        )

        self.assertEqual(b"after\n", (self.workspace / "fixture/work-item.txt").read_bytes())
        self.assertEqual(b"before\n", (self.source / "fixture/work-item.txt").read_bytes())
        self.assertEqual("work_result", result["packet_type"])
        self.assertEqual("work", result["actor"])
        self.assertEqual("SUCCEEDED", result["status"])
        self.assertEqual("E2", result["payload"]["evidence"][0]["tier"])
        self.assertEqual("2026-08-02T00:05:00Z", result["payload"]["evidence"][0]["observed_at"])
        self.assertEqual(
            {"passed": 1, "failed": 0, "not_run": 0},
            result["payload"]["validation_summary"],
        )
        self.assertEqual(
            [{"actor": "work", "phase": "VERIFY", "code": "WORK_VERIFICATION_PASSED"}],
            result["payload"]["event_suggestions"],
        )
        self.assertFalse(any(field in result["payload"] for field in ("accepted_state", "revision", "events", "seq")))

    def test_context_is_immutable_and_packet_injection_cannot_shadow_it(self):
        """Break caught: mutable packet claims replacing Main-approved candidate identity."""
        context = self.approved_context()
        with self.assertRaises(TypeError):
            context.approved_candidate_ids[0] = "CAND-INJECTED"
        self.candidate_packet["payload"]["approved_candidate_ids"] = ["CAND-INJECTED"]

        result = work_actor.preflight_execute_verify(
            context,
            workspace_root=self.workspace,
            source_root=self.source,
            clock=lambda: "2026-08-02T00:05:00Z",
        )

        self.assertEqual(["CAND-W6-UPDATE"], result["payload"]["approved_candidate_ids"])

    def test_approval_rejects_unapproved_unknown_or_duplicate_ids(self):
        """Break caught: implicit, unknown, or duplicate candidate approval gaining write authority."""
        for name, ids in (
            ("missing", []),
            ("unknown", ["CAND-UNKNOWN"]),
            ("duplicate", ["CAND-W6-UPDATE", "CAND-W6-UPDATE"]),
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(common.VerticalFlowError, "WORK_APPROVED_ID_INVALID"):
                    main_actor.approve_candidates(
                        self.task_packet,
                        self.candidate_packet,
                        approved_candidate_ids=ids,
                        validation_at="2026-08-02T00:05:00Z",
                        human_review_result=None,
                    )
                self.assert_trees_unchanged()

    def test_approval_rejects_stale_or_cross_task_candidate_envelopes(self):
        """Break caught: approving Part output from another accepted revision or task identity."""
        for field, value in (
            ("base_revision", 0),
            ("task_id", "TASK-OTHER"),
            ("correlation_id", "CORR-OTHER"),
        ):
            with self.subTest(field=field):
                candidate = copy.deepcopy(self.candidate_packet)
                candidate[field] = value
                with self.assertRaisesRegex(common.VerticalFlowError, "WORK_ENVELOPE_INVALID"):
                    main_actor.approve_candidates(
                        self.task_packet,
                        candidate,
                        approved_candidate_ids=["CAND-W6-UPDATE"],
                        validation_at="2026-08-02T00:05:00Z",
                        human_review_result=None,
                    )
                self.assert_trees_unchanged()

    def test_preflight_rejects_explore_mode_unknown_write_capability_or_stale_context(self):
        """Break caught: Work mutating without EXECUTE, AVAILABLE write capability, and current revision."""
        context = self.approved_context()
        cases = []
        explore_task = common.thaw_json(context.task_packet)
        explore_task["payload"]["control"]["operation_mode"] = "EXPLORE"
        cases.append(("explore", replace(context, task_packet=explore_task), "WORK_OPERATION_MODE_INVALID"))
        unknown_task = common.thaw_json(context.task_packet)
        unknown_task["payload"]["capabilities"]["filesystem_write"] = "UNKNOWN"
        cases.append(("unknown", replace(context, task_packet=unknown_task), "WORK_CAPABILITY_DENIED"))
        cases.append(("stale", replace(context, current_revision=2), "WORK_REVISION_STALE"))

        for name, mutated, code in cases:
            with self.subTest(name=name):
                with self.assertRaisesRegex(common.VerticalFlowError, code):
                    work_actor.preflight_execute_verify(
                        mutated,
                        workspace_root=self.workspace,
                        source_root=self.source,
                        clock=lambda: "2026-08-02T00:05:00Z",
                    )
                self.assert_trees_unchanged()

    def test_preflight_rejects_named_authority_miss_and_invalid_project_effect_scopes(self):
        """Break caught: unrelated named access or project-wide command/network scope authorizing a write."""
        context = self.approved_context()
        cases = []
        named_miss = common.thaw_json(context.authority)
        named_miss["write_resources"] = ["fixture/other.txt"]
        cases.append(("named-miss", named_miss, "WORK_WRITE_AUTHORITY_DENIED"))
        project_execute = common.thaw_json(context.authority)
        project_execute["execute_scope"] = "PROJECT"
        cases.append(("project-execute", project_execute, "AUTHORITY_EXECUTE_SCOPE_INVALID"))
        project_network = common.thaw_json(context.authority)
        project_network["network_scope"] = "PROJECT"
        cases.append(("project-network", project_network, "AUTHORITY_NETWORK_SCOPE_INVALID"))

        for name, authority, code in cases:
            with self.subTest(name=name):
                mutated = replace(context, authority=authority)
                with self.assertRaisesRegex(common.VerticalFlowError, code):
                    work_actor.preflight_execute_verify(
                        mutated,
                        workspace_root=self.workspace,
                        source_root=self.source,
                        clock=lambda: "2026-08-02T00:05:00Z",
                    )
                self.assert_trees_unchanged()

    def test_approval_rejects_wildcard_traversal_and_hybrid_resource_identity(self):
        """Break caught: normalization or hybrid identity turning an out-of-scope path into authority."""
        for name, resource_ref, extra in (
            ("wildcard", "fixture/*.txt", {}),
            ("traversal", "fixture/../work-item.txt", {}),
            ("hybrid", "fixture/work-item.txt", {"command_id": "main-part-work-main"}),
        ):
            with self.subTest(name=name):
                candidate = copy.deepcopy(self.candidate_packet)
                record = candidate["payload"]["candidates"][0]
                record["resource_ref"] = resource_ref
                record["scope"] = [resource_ref]
                record["action_identity"] = {
                    "identity_kind": "RESOURCE",
                    "resource_ref": resource_ref,
                    **extra,
                }
                with self.assertRaisesRegex(common.VerticalFlowError, "WORK_ACTION_IDENTITY_INVALID"):
                    main_actor.approve_candidates(
                        self.task_packet,
                        candidate,
                        approved_candidate_ids=["CAND-W6-UPDATE"],
                        validation_at="2026-08-02T00:05:00Z",
                        human_review_result=None,
                    )
                self.assert_trees_unchanged()

    def test_approval_rejects_protected_fixture_target(self):
        """Break caught: approving a resource after its trusted profile marks it protected."""
        task = copy.deepcopy(self.task_packet)
        task["payload"]["project_profile"]["protected_resources"].append("fixture/work-item.txt")

        with self.assertRaisesRegex(common.VerticalFlowError, "WORK_PROTECTED_RESOURCE_DENIED"):
            main_actor.approve_candidates(
                task,
                self.candidate_packet,
                approved_candidate_ids=["CAND-W6-UPDATE"],
                validation_at="2026-08-02T00:05:00Z",
                human_review_result=None,
            )
        self.assert_trees_unchanged()

    def test_source_root_target_is_rejected_before_open(self):
        """Break caught: treating the source tree itself as the verifier-owned workspace."""
        context = self.approved_context()

        with self.assertRaisesRegex(common.VerticalFlowError, "WORK_SOURCE_TARGET_FORBIDDEN"):
            work_actor.preflight_execute_verify(
                context,
                workspace_root=self.source,
                source_root=self.source,
                clock=lambda: "2026-08-02T00:05:00Z",
            )

        self.assert_trees_unchanged()

    def test_workspace_symlink_escape_is_rejected_before_external_target_open(self):
        """Break caught: a verifier workspace symlink redirecting the approved path outside its root."""
        escaped = Path(self.temporary.name) / "escaped.txt"
        escaped.write_bytes(b"before\n")
        target = self.workspace / "fixture/work-item.txt"
        target.unlink()
        try:
            target.symlink_to(escaped)
        except OSError as exc:
            self.skipTest(f"file symlink unavailable: {exc}")

        with self.assertRaisesRegex(common.VerticalFlowError, "WORK_TARGET_ESCAPE"):
            work_actor.preflight_execute_verify(
                self.approved_context(),
                workspace_root=self.workspace,
                source_root=self.source,
                clock=lambda: "2026-08-02T00:05:00Z",
            )

        self.assertEqual(b"before\n", escaped.read_bytes())
        self.assertEqual(b"before\n", (self.source / "fixture/work-item.txt").read_bytes())

    def test_approval_rejects_unsupported_command_or_network_candidate(self):
        """Break caught: the bounded W6 adapter executing command or network candidates."""
        for action_type, identity in (
            ("RUN_COMMAND", {"identity_kind": "COMMAND", "command_id": "main-part-work-main"}),
            ("NETWORK_REQUEST", {"identity_kind": "NETWORK", "network_host": "api.example.com"}),
        ):
            with self.subTest(action_type=action_type):
                candidate = copy.deepcopy(self.candidate_packet)
                record = candidate["payload"]["candidates"][0]
                record["action_type"] = action_type
                record["action_identity"] = identity
                record["resource_ref"] = None
                with self.assertRaisesRegex(common.VerticalFlowError, "WORK_ACTION_TYPE_UNSUPPORTED"):
                    main_actor.approve_candidates(
                        self.task_packet,
                        candidate,
                        approved_candidate_ids=["CAND-W6-UPDATE"],
                        validation_at="2026-08-02T00:05:00Z",
                        human_review_result=None,
                    )
                self.assert_trees_unchanged()

    def test_approval_rejects_untrusted_control_and_candidate_state_ownership(self):
        """Break caught: Part injecting trusted approval/time or authoritative state and sequence fields."""
        cases = (
            ("approved", "approved_candidate_ids", ["CAND-W6-UPDATE"], "WORK_APPROVED_ID_INVALID"),
            ("validation", "validationAt", "2026-08-02T00:05:00Z", "WORK_VALIDATION_AT_UNTRUSTED"),
            ("state", "accepted_state", {"revision": 2}, "WORK_STATE_OWNERSHIP_FORBIDDEN"),
            ("revision", "revision", 2, "WORK_STATE_OWNERSHIP_FORBIDDEN"),
        )
        for name, field, value, code in cases:
            with self.subTest(name=name):
                candidate = copy.deepcopy(self.candidate_packet)
                candidate["payload"][field] = value
                with self.assertRaisesRegex(common.VerticalFlowError, code):
                    main_actor.approve_candidates(
                        self.task_packet,
                        candidate,
                        approved_candidate_ids=["CAND-W6-UPDATE"],
                        validation_at="2026-08-02T00:05:00Z",
                        human_review_result=None,
                    )
                self.assert_trees_unchanged()

        candidate = copy.deepcopy(self.candidate_packet)
        candidate["payload"]["event_suggestions"][0]["seq"] = 7
        with self.assertRaisesRegex(common.VerticalFlowError, "WORK_STATE_OWNERSHIP_FORBIDDEN"):
            main_actor.approve_candidates(
                self.task_packet,
                candidate,
                approved_candidate_ids=["CAND-W6-UPDATE"],
                validation_at="2026-08-02T00:05:00Z",
                human_review_result=None,
            )
        self.assert_trees_unchanged()

    def test_approval_rejects_dangling_or_duplicate_candidate_evidence_references(self):
        """Break caught: approving a candidate whose supporting evidence cannot resolve exactly once."""
        for name, refs in (
            ("dangling", ["EVID-UNKNOWN"]),
            ("duplicate", ["EVID-PART-CONTEXT", "EVID-PART-CONTEXT"]),
        ):
            with self.subTest(name=name):
                candidate = copy.deepcopy(self.candidate_packet)
                candidate["payload"]["candidates"][0]["evidence_refs"] = refs
                with self.assertRaisesRegex(common.VerticalFlowError, "WORK_CANDIDATE_EVIDENCE_INVALID"):
                    main_actor.approve_candidates(
                        self.task_packet,
                        candidate,
                        approved_candidate_ids=["CAND-W6-UPDATE"],
                        validation_at="2026-08-02T00:05:00Z",
                        human_review_result=None,
                    )
                self.assert_trees_unchanged()

    def test_approval_rejects_forged_part_event_or_evidence_provenance(self):
        """Break caught: freezing forged Part metadata that Main will later treat as trusted input."""
        for name, mutate in (
            (
                "event-actor",
                lambda packet: packet["payload"]["event_suggestions"][0].update(
                    actor="main"
                ),
            ),
            (
                "evidence-source",
                lambda packet: packet["payload"]["evidence"][0].update(source="README.md"),
            ),
        ):
            with self.subTest(name=name):
                candidate = copy.deepcopy(self.candidate_packet)
                mutate(candidate)
                with self.assertRaisesRegex(
                    common.VerticalFlowError, "WORK_CANDIDATE_PACKET_INVALID"
                ):
                    main_actor.approve_candidates(
                        self.task_packet,
                        candidate,
                        approved_candidate_ids=["CAND-W6-UPDATE"],
                        validation_at="2026-08-02T00:05:00Z",
                        human_review_result=None,
                    )
                self.assert_trees_unchanged()

    def test_preflight_rejects_non_utc_runtime_observation_before_effect(self):
        """Break caught: accepting forged or noncanonical runtime evidence time."""
        context = self.approved_context()

        with self.assertRaisesRegex(common.VerticalFlowError, "WORK_OBSERVED_AT_INVALID"):
            work_actor.preflight_execute_verify(
                context,
                workspace_root=self.workspace,
                source_root=self.source,
                clock=lambda: "2026-08-02T00:05:00+00:00",
            )

        self.assert_trees_unchanged()


if __name__ == "__main__":
    unittest.main()
