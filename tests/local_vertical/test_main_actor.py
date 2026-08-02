import copy
from dataclasses import fields
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MappingProxyType
import unittest

from tools.local_vertical import common, main_actor, part_actor, work_actor


ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "fixtures/forgeops-local-vertical/suite.json"
PRODUCT_SCHEMA = ROOT / "contracts/product-task-contract/1.0/schema.json"


class MainNormalizationTests(unittest.TestCase):
    def setUp(self):
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        self.contract = suite["base_fixture"]["product_contract"]
        self.bridge_context = suite["base_fixture"]["trusted_bridge_context"]
        self.product_schema = json.loads(PRODUCT_SCHEMA.read_text(encoding="utf-8"))

    def packet(self):
        return main_actor.normalize_product_task(
            self.contract,
            self.bridge_context,
            self.product_schema,
            correlation_id="CORR-W6-FIXTURE",
        )

    def test_change_normalizes_to_part_explore_task(self):
        """Break caught: dropping the Main envelope or routing this change directly to Work."""
        packet = self.packet()

        self.assertEqual("2.0", packet["protocol_version"])
        self.assertEqual("task", packet["packet_type"])
        self.assertEqual("main", packet["actor"])
        self.assertEqual(1, packet["base_revision"])
        self.assertEqual("PART_THEN_WORK", packet["payload"]["control"]["route"])
        self.assertEqual("EXPLORE", packet["payload"]["control"]["operation_mode"])
        self.assertEqual([], packet["payload"]["request"]["assumptions"])

    def test_missing_safety_capability_becomes_unknown(self):
        """Break caught: treating omitted trusted capability data as available."""
        del self.bridge_context["canonical_control"]["capabilities"]["network"]

        packet = self.packet()

        self.assertEqual("UNKNOWN", packet["payload"]["capabilities"]["network"])

    def test_invalid_safety_capability_becomes_unknown_without_losing_delegation_enum(self):
        """Break caught: accepting a delegation-only enum for network or discarding valid delegation."""
        capabilities = self.bridge_context["canonical_control"]["capabilities"]
        capabilities["network"] = "NONE"
        capabilities["delegation"] = "SEQUENTIAL"

        packet = self.packet()

        self.assertEqual("UNKNOWN", packet["payload"]["capabilities"]["network"])
        self.assertEqual("SEQUENTIAL", packet["payload"]["capabilities"]["delegation"])

    def test_unknown_protocol_fails_closed(self):
        """Break caught: accepting a Product Contract version the W1 bridge does not support."""
        self.contract["schema_version"] = "9.0"

        with self.assertRaisesRegex(common.VerticalFlowError, "MAIN_CONTRACT_VERSION_UNSUPPORTED"):
            self.packet()

    def test_authority_companion_lists_are_closed_and_canonical(self):
        """Break caught: granting authority from malformed, wildcard, or inconsistent companion lists."""
        cases = (
            ("duplicate", "write_resources", ["fixture/work-item.txt", "fixture/work-item.txt"], "AUTHORITY_RESOURCE_DUPLICATE"),
            ("wildcard", "write_resources", ["fixture/*.txt"], "AUTHORITY_RESOURCE_NONCANONICAL"),
            ("traversal", "write_resources", ["fixture/../work-item.txt"], "AUTHORITY_RESOURCE_NONCANONICAL"),
            ("project-list", "read_resources", ["fixture/work-item.txt"], "AUTHORITY_RESOURCE_LIST_FORBIDDEN"),
        )
        for name, field, value, code in cases:
            with self.subTest(name=name):
                authority = copy.deepcopy(self.bridge_context["canonical_control"]["authority"])
                authority[field] = value
                with self.assertRaisesRegex(common.VerticalFlowError, code):
                    common.validate_authority(authority)

    def test_resource_pattern_metacharacters_are_not_canonical_resource_refs(self):
        """Break caught: interpreting glob patterns as named resource authority."""
        for resource_ref in ("fixture/?.txt", "fixture/[ab].txt", "fixture/a].txt"):
            with self.subTest(resource_ref=resource_ref):
                with self.assertRaisesRegex(
                    common.VerticalFlowError, "RESOURCE_IDENTITY_NONCANONICAL"
                ):
                    common.canonical_resource_ref(resource_ref)

    def test_network_hosts_require_canonical_lower_case_dns_with_optional_valid_port(self):
        """Break caught: treating URLs, malformed DNS names, or invalid ports as named hosts."""
        invalid_hosts = (
            "API.EXAMPLE.COM:0",
            "https://api.example.com",
            "api.example.com/path",
            "api.example.com?query",
            "api.example.com#fragment",
            "user@api.example.com",
            "api..example.com",
            "-api.example.com",
            "api-.example.com",
            "api.example.com:65536",
            "api.example.com:1:2",
            "api.example.com:port",
            "api.example.com:0",
            " api.example.com",
        )
        for host in invalid_hosts:
            with self.subTest(host=host):
                authority = copy.deepcopy(self.bridge_context["canonical_control"]["authority"])
                authority["network_scope"] = "NAMED_HOSTS"
                authority["network_hosts"] = [host]
                with self.assertRaisesRegex(common.VerticalFlowError, "AUTHORITY_NETWORK_VALUE_INVALID"):
                    common.validate_authority(authority)

        authority = copy.deepcopy(self.bridge_context["canonical_control"]["authority"])
        authority["network_scope"] = "NAMED_HOSTS"
        authority["network_hosts"] = ["api.example.com:443"]
        self.assertEqual(["api.example.com:443"], common.validate_authority(authority)["network_hosts"])

    def test_overlong_numeric_network_port_is_a_closed_authority_error(self):
        """Break caught: letting a numeric conversion exception escape host authority validation."""
        authority = copy.deepcopy(self.bridge_context["canonical_control"]["authority"])
        authority["network_scope"] = "NAMED_HOSTS"
        authority["network_hosts"] = ["api.example.com:" + "9" * 5000]

        with self.assertRaisesRegex(common.VerticalFlowError, "AUTHORITY_NETWORK_VALUE_INVALID"):
            common.validate_authority(authority)

    def test_non_string_effect_flags_are_closed_errors(self):
        """Break caught: leaking a runtime TypeError from an unhashable effect flag."""
        for field in ("destructive_actions", "external_side_effects"):
            with self.subTest(field=field):
                authority = copy.deepcopy(self.bridge_context["canonical_control"]["authority"])
                authority[field] = []
                with self.assertRaisesRegex(common.VerticalFlowError, "AUTHORITY_EFFECT_FLAG_INVALID"):
                    common.validate_authority(authority)

    def test_project_execute_or_network_scope_fails_closed(self):
        """Break caught: treating PROJECT as executable or network authority."""
        for field, code in (
            ("execute_scope", "AUTHORITY_EXECUTE_SCOPE_INVALID"),
            ("network_scope", "AUTHORITY_NETWORK_SCOPE_INVALID"),
        ):
            with self.subTest(field=field):
                authority = copy.deepcopy(self.bridge_context["canonical_control"]["authority"])
                authority[field] = "PROJECT"
                with self.assertRaisesRegex(common.VerticalFlowError, code):
                    common.validate_authority(authority)

    def test_malformed_correlation_id_is_rejected(self):
        """Break caught: emitting a packet whose correlation identifier is not a canonical ID."""
        with self.assertRaises(common.VerticalFlowError):
            main_actor.normalize_product_task(
                self.contract,
                self.bridge_context,
                self.product_schema,
                correlation_id=" CORR-W6-FIXTURE ",
            )

    def test_returned_packet_is_isolated_from_later_input_mutation(self):
        """Break caught: retaining caller-owned mutable Contract or bridge context objects in TaskPacket."""
        packet = self.packet()
        self.contract["intent"]["summary"] = "caller mutation"
        self.bridge_context["canonical_control"]["authority"]["write_resources"][0] = "fixture/other.txt"

        self.assertEqual("Change fixture/work-item.txt from before to after.", packet["payload"]["request"]["objective"])
        self.assertEqual(["fixture/work-item.txt"], packet["payload"]["authority"]["write_resources"])

    def test_build_part_task_preserves_revision_and_only_forces_exploration_route(self):
        """Break caught: Part routing altering accepted revision or unrelated Main packet fields."""
        task = self.packet()
        task["payload"]["control"]["route"] = "DIRECT"
        task["payload"]["control"]["operation_mode"] = "EXECUTE"
        routed = main_actor.build_part_task(task)

        self.assertEqual(1, routed["base_revision"])
        self.assertEqual("PART_THEN_WORK", routed["payload"]["control"]["route"])
        self.assertEqual("EXPLORE", routed["payload"]["control"]["operation_mode"])
        self.assertEqual("main", routed["actor"])
        self.assertEqual("DIRECT", task["payload"]["control"]["route"])

    def test_freeze_and_thaw_make_json_values_immutable_without_aliasing(self):
        """Break caught: mutating a frozen trusted context or leaking its nested references on thaw."""
        frozen = common.freeze_json({"items": [{"id": "A"}]})
        self.assertIsInstance(frozen, MappingProxyType)
        with self.assertRaises(TypeError):
            frozen["items"] = ()
        thawed = common.thaw_json(frozen)
        thawed["items"][0]["id"] = "B"
        self.assertEqual("A", frozen["items"][0]["id"])

    def test_approval_builds_an_immutable_non_packet_work_context(self):
        """Break caught: letting packet fields or caller-owned values become Work authority."""
        self.assertTrue(
            hasattr(main_actor, "approve_candidates"),
            "Main approval API is not implemented",
        )
        task = self.packet()
        fixture = json.loads(SUITE.read_text(encoding="utf-8"))["base_fixture"]
        candidate = part_actor.propose_candidates(
            main_actor.build_part_task(task),
            fixture["snapshot_manifest"],
            fixture["context_pack"],
        )

        context = main_actor.approve_candidates(
            task,
            candidate,
            approved_candidate_ids=["CAND-W6-UPDATE"],
            validation_at="2026-08-02T00:05:00Z",
            human_review_result=None,
        )

        self.assertEqual(
            {
                "task_packet",
                "candidate_packet",
                "current_revision",
                "approved_candidate_ids",
                "approved_candidates",
                "authority",
                "candidate_evidence_floor",
                "acceptance_criteria",
                "validation_at",
                "human_review_result",
            },
            {field.name for field in fields(context)},
        )
        self.assertFalse(
            any(
                hasattr(context, field)
                for field in ("protocol_version", "packet_type", "actor", "status")
            )
        )
        routed = common.thaw_json(context.task_packet)
        self.assertEqual("WORK_ONLY", routed["payload"]["control"]["route"])
        self.assertEqual("EXECUTE", routed["payload"]["control"]["operation_mode"])
        self.assertEqual(("CAND-W6-UPDATE",), context.approved_candidate_ids)
        with self.assertRaises(TypeError):
            context.approved_candidates[0]["candidate_id"] = "CAND-INJECTED"

    def test_only_main_can_construct_and_validate_a_trusted_context(self):
        """Break caught: treating any caller-constructed ten-field dataclass as Main-issued trust."""
        context = self.packet()
        fixture = json.loads(SUITE.read_text(encoding="utf-8"))["base_fixture"]
        candidate = part_actor.propose_candidates(
            main_actor.build_part_task(context),
            fixture["snapshot_manifest"],
            fixture["context_pack"],
        )
        issued = main_actor.approve_candidates(
            context,
            candidate,
            approved_candidate_ids=["CAND-W6-UPDATE"],
            validation_at="2026-08-02T00:05:00Z",
            human_review_result=None,
        )

        direct_values = {
            field.name: getattr(issued, field.name) for field in fields(issued)
        }
        with self.assertRaises(TypeError):
            common.TrustedExecutionContext(**direct_values)
        self.assertIsNone(main_actor.validate_main_issued_context(issued))

    def test_approval_rejects_invalid_runtime_timestamp(self):
        """Break caught: freezing a non-UTC or normalized validator time into trusted context."""
        task = self.packet()
        fixture = json.loads(SUITE.read_text(encoding="utf-8"))["base_fixture"]
        candidate = part_actor.propose_candidates(
            main_actor.build_part_task(task),
            fixture["snapshot_manifest"],
            fixture["context_pack"],
        )

        for value in ("2026-08-02T00:05:00+00:00", "2026-08-02 00:05:00Z", "invalid"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    common.VerticalFlowError, "MAIN_VALIDATION_AT_INVALID"
                ):
                    main_actor.approve_candidates(
                        task,
                        candidate,
                        approved_candidate_ids=["CAND-W6-UPDATE"],
                        validation_at=value,
                        human_review_result=None,
                    )


class MainDecisionTests(unittest.TestCase):
    def setUp(self):
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        self.fixture = suite["base_fixture"]
        task = main_actor.normalize_product_task(
            self.fixture["product_contract"],
            self.fixture["trusted_bridge_context"],
            json.loads(PRODUCT_SCHEMA.read_text(encoding="utf-8")),
            correlation_id="CORR-W6-FIXTURE",
        )
        self.candidate = part_actor.propose_candidates(
            main_actor.build_part_task(task),
            self.fixture["snapshot_manifest"],
            self.fixture["context_pack"],
        )
        self.context = main_actor.approve_candidates(
            task,
            self.candidate,
            approved_candidate_ids=["CAND-W6-UPDATE"],
            validation_at=self.fixture["validation_at"],
            human_review_result=None,
        )
        self.accepted_state = copy.deepcopy(self.fixture["accepted_state"])
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        workspace = root / "workspace"
        source = root / "source"
        for tree in (workspace, source):
            (tree / "fixture").mkdir(parents=True)
            (tree / "fixture/work-item.txt").write_bytes(b"before\n")
        self.work_result = work_actor.preflight_execute_verify(
            self.context,
            workspace_root=workspace,
            source_root=source,
            clock=lambda: self.fixture["validation_at"],
        )

    def decide(self, result=None):
        return main_actor.validate_and_decide(
            self.work_result if result is None else result,
            self.context,
            self.accepted_state,
        )

    def test_fresh_complete_work_result_is_the_only_success_path(self):
        decision = self.decide()
        self.assertEqual("main_decision", decision["packet_type"])
        self.assertEqual("main", decision["actor"])
        accepted = decision["payload"]["accepted_state"]
        self.assertEqual(2, accepted["revision"])
        self.assertEqual("SUCCEEDED", accepted["status"])
        self.assertEqual(9, accepted["next_seq"])
        self.assertEqual([7, 8], [event["seq"] for event in decision["payload"]["events"]])
        self.assertEqual("ACCEPT", decision["payload"]["decision"])
        self.assertTrue(accepted["accepted_payload_ref"].startswith("sha256:"))
        self.assertEqual(1, self.accepted_state["revision"])

    def test_stale_or_invalid_result_has_zero_accepted_effect(self):
        self.work_result["base_revision"] = 0
        before = common.canonical_json_bytes(self.accepted_state)
        with self.assertRaisesRegex(common.VerticalFlowError, "MAIN_WORK_REVISION_STALE"):
            self.decide()
        self.assertEqual(before, common.canonical_json_bytes(self.accepted_state))

    def test_blocked_part_proposal_can_gate_waiting_for_human(self):
        task = common.thaw_json(self.context.task_packet)
        task["payload"]["control"]["route"] = "PART_THEN_WORK"
        task["payload"]["control"]["operation_mode"] = "EXPLORE"
        task["payload"]["authority"]["read_scope"] = "NONE"
        task["payload"]["authority"]["read_resources"] = []
        blocked = part_actor.propose_candidates(
            task, self.fixture["snapshot_manifest"], self.fixture["context_pack"]
        )
        decision = main_actor.decide_candidate_gate(blocked, self.accepted_state)
        self.assertEqual("GATE", decision["payload"]["decision"])
        self.assertEqual("WAITING_FOR_HUMAN", decision["payload"]["accepted_state"]["status"])
        self.assertEqual(2, decision["payload"]["accepted_state"]["revision"])
        self.assertEqual([7], [event["seq"] for event in decision["payload"]["events"]])
        self.assertEqual(1, self.accepted_state["revision"])

    def test_envelope_identity_and_work_state_ownership_are_closed(self):
        for field, value, code in (
            ("actor", "part", "MAIN_WORK_ENVELOPE_INVALID"),
            ("task_id", "TASK-OTHER", "MAIN_WORK_IDENTITY_INVALID"),
            ("correlation_id", "CORR-OTHER", "MAIN_WORK_IDENTITY_INVALID"),
        ):
            with self.subTest(field=field):
                result = copy.deepcopy(self.work_result)
                result[field] = value
                with self.assertRaisesRegex(common.VerticalFlowError, code):
                    self.decide(result)
        for field, value in (("accepted_state", {}), ("revision", 2), ("events", []), ("seq", 7)):
            with self.subTest(field=field):
                result = copy.deepcopy(self.work_result)
                result["payload"][field] = value
                with self.assertRaisesRegex(common.VerticalFlowError, "WORK_STATE_OWNERSHIP_FORBIDDEN"):
                    self.decide(result)

    def test_candidate_and_criterion_coverage_are_exact_raw_arrays(self):
        mutations = (
            ("candidate scalar", lambda p: p.update(candidate_results="CAND-W6-UPDATE"), "MAIN_CANDIDATE_COVERAGE_INVALID"),
            ("candidate missing", lambda p: p.update(candidate_results=[]), "MAIN_CANDIDATE_COVERAGE_INVALID"),
            ("candidate duplicate", lambda p: p["candidate_results"].append(copy.deepcopy(p["candidate_results"][0])), "MAIN_CANDIDATE_COVERAGE_INVALID"),
            ("candidate unknown", lambda p: p["candidate_results"][0].update(candidate_id="CAND-UNKNOWN"), "MAIN_CANDIDATE_COVERAGE_INVALID"),
            ("criterion scalar", lambda p: p.update(acceptance_results="AC-W6-1"), "MAIN_CRITERION_COVERAGE_INVALID"),
            ("criterion missing", lambda p: p.update(acceptance_results=[]), "MAIN_CRITERION_COVERAGE_INVALID"),
            ("criterion duplicate", lambda p: p["acceptance_results"].append(copy.deepcopy(p["acceptance_results"][0])), "MAIN_CRITERION_COVERAGE_INVALID"),
            ("criterion unknown", lambda p: p["acceptance_results"][0].update(criterion_id="AC-UNKNOWN"), "MAIN_CRITERION_COVERAGE_INVALID"),
        )
        for name, mutate, code in mutations:
            with self.subTest(name=name):
                result = copy.deepcopy(self.work_result)
                mutate(result["payload"])
                with self.assertRaisesRegex(common.VerticalFlowError, code):
                    self.decide(result)

    def test_evidence_refs_freshness_tier_and_summary_are_closed(self):
        mutations = (
            ("dangling", lambda p: p["candidate_results"][0].update(evidence_refs=["UNKNOWN"]), "MAIN_EVIDENCE_REFERENCE_INVALID"),
            ("duplicate", lambda p: p["candidate_results"][0].update(evidence_refs=["EVID-WORK-FIXTURE-TEST"] * 2), "MAIN_EVIDENCE_REFERENCE_INVALID"),
            ("scalar", lambda p: p["candidate_results"][0].update(evidence_refs="EVID-WORK-FIXTURE-TEST"), "MAIN_EVIDENCE_REFERENCE_INVALID"),
            ("wrong mode", lambda p: p["evidence"][0].update(observed_revision=1), "MAIN_EVIDENCE_FRESHNESS_INVALID"),
            ("before-anchor", lambda p: p["evidence"][0].update(observed_at="2026-08-02T00:04:59Z"), "MAIN_EVIDENCE_FRESHNESS_INVALID"),
            ("stale", lambda p: p["evidence"][0].update(observed_at="2026-08-02T00:10:01Z"), "MAIN_EVIDENCE_FRESHNESS_INVALID"),
            ("tier", lambda p: p["evidence"][0].update(tier="E1"), "MAIN_EVIDENCE_TIER_INVALID"),
            ("summary", lambda p: p.update(validation_summary={"passed": 0, "failed": 0, "not_run": 0}), "MAIN_SUMMARY_INVALID"),
        )
        for name, mutate, code in mutations:
            with self.subTest(name=name):
                result = copy.deepcopy(self.work_result)
                mutate(result["payload"])
                with self.assertRaisesRegex(common.VerticalFlowError, code):
                    self.decide(result)
