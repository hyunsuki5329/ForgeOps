import copy
import json
from pathlib import Path
from types import MappingProxyType
import unittest

from tools.local_vertical import common, main_actor


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
