"""Focused conformance tests for the durable event wrapper record boundary."""

from __future__ import annotations

import importlib
import inspect
import json
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts" / "forgeops-event" / "1.0" / "schema.json"
SUITE_PATH = ROOT / "fixtures" / "forgeops-event-contract" / "suite.json"
MODULE_PATH = ROOT / "tools" / "interface_contract" / "event_contract.py"


class EventRecordTests(unittest.TestCase):
    def _runtime(self):
        self.assertTrue(MODULE_PATH.is_file(), "event validator is not implemented")
        module = importlib.import_module("tools.interface_contract.event_contract")
        self.assertTrue(hasattr(module, "validate_event_record"))
        return module

    def _catalog(self):
        self.assertTrue(SCHEMA_PATH.is_file(), "event schema is not implemented")
        self.assertTrue(SUITE_PATH.is_file(), "event fixture suite is not implemented")
        return (
            json.loads(SCHEMA_PATH.read_text(encoding="utf-8")),
            json.loads(SUITE_PATH.read_text(encoding="utf-8")),
        )

    @staticmethod
    def _case_by_id(suite, case_id):
        return next(case for case in suite["positive"] if case["id"] == case_id)

    def _negative_record(self, suite, case):
        record = deepcopy(self._case_by_id(suite, case["base_case"])["records"][0])
        target = record
        path = case["mutation"]["path"]
        for segment in path[:-1]:
            target = target[segment]
        leaf = path[-1]
        if case["mutation"]["operation"] == "remove":
            target.pop(leaf)
        else:
            target[leaf] = deepcopy(case["mutation"]["value"])
        return record

    def test_valid_main_decision_wrapper(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        record = self._case_by_id(suite, "first-append")["records"][0]

        runtime.validate_event_record(record, schema)

    def test_part_suggestion_cannot_be_durable_source(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        record = deepcopy(self._case_by_id(suite, "first-append")["records"][0])
        record["provenance"]["source_kind"] = "PART_SUGGESTION"

        with self.assertRaisesRegex(runtime.ContractError, "EVENT_OWNER_INVALID"):
            runtime.validate_event_record(record, schema)

    def test_wrapper_and_canonical_identity_are_exact(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        record = deepcopy(self._case_by_id(suite, "first-append")["records"][0])
        record["canonical_event"]["task_id"] = "TASK-case-variant"

        with self.assertRaisesRegex(runtime.ContractError, "EVENT_IDENTITY_MISMATCH"):
            runtime.validate_event_record(record, schema)

    def test_phase_catalog_is_exact(self):
        _, schema = self._runtime(), self._catalog()[0]

        self.assertEqual(
            ["NORMALIZE", "DISCOVER", "EXECUTE", "VERIFY", "DECIDE", "GATE"],
            schema["properties"]["canonical_event"]["properties"]["phase"]["enum"],
        )

    def test_normalize_phase_is_valid(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        record = deepcopy(self._case_by_id(suite, "first-append")["records"][0])
        record["canonical_event"]["phase"] = "NORMALIZE"

        try:
            runtime.validate_event_record(record, schema)
        except runtime.ContractError as exc:
            self.fail(f"NORMALIZE must be valid, got {exc.code}")

    def test_evidence_reference_grammar_is_bounded_and_opaque(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        self.assertIn("evidence_reference", schema["$defs"])
        definition = schema["$defs"]["evidence_reference"]
        self.assertEqual(128, definition["maxLength"])
        self.assertEqual(
            "^EVID-[A-Za-z0-9][A-Za-z0-9._:-]{0,122}$", definition["pattern"]
        )
        base = self._case_by_id(suite, "first-append")["records"][0]
        invalid_references = (
            "EVID-has space",
            "EVID-" + "A" * 124,
            "raw prompt content",
            "stdout\nstderr",
            "private:customer-record",
        )

        for reference in invalid_references:
            record = deepcopy(base)
            record["canonical_event"]["evidence_refs"] = [reference]
            with self.subTest(reference=reference[:24]):
                with self.assertRaisesRegex(
                    runtime.ContractError, "EVENT_REFERENCE_INVALID"
                ):
                    runtime.validate_event_record(record, schema)

    def test_source_main_decision_hash_mismatch_is_provenance_invalid(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        self.assertIn(
            "source_main_decisions",
            inspect.signature(runtime.validate_event_record).parameters,
        )
        case = self._case_by_id(suite, "first-append")
        source_context = deepcopy(case["source_main_decisions"])
        source_context["MDEC-first"]["content_sha256"] = "b" * 64

        with self.assertRaisesRegex(runtime.ContractError, "EVENT_PROVENANCE_INVALID"):
            runtime.validate_event_record(
                case["records"][0],
                schema,
                source_main_decisions=source_context,
            )

    def test_fixture_positive_records_are_accepted(self):
        runtime = self._runtime()
        schema, suite = self._catalog()

        for case in suite["positive"]:
            for record in case["records"]:
                with self.subTest(case=case["id"], event_id=record["event_id"]):
                    runtime.validate_event_record(record, schema)

    def test_fixture_negative_records_return_stable_errors(self):
        runtime = self._runtime()
        schema, suite = self._catalog()

        for case in suite["negative_records"]:
            with self.subTest(case=case["id"]):
                with self.assertRaises(runtime.ContractError) as caught:
                    runtime.validate_event_record(self._negative_record(suite, case), schema)
                self.assertEqual(case["expected_error"], caught.exception.code)

    def test_schema_is_closed_at_every_object_boundary(self):
        _, schema = self._runtime(), self._catalog()[0]

        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["canonical_event"]["additionalProperties"])
        self.assertFalse(schema["properties"]["provenance"]["additionalProperties"])


class EventStreamTests(unittest.TestCase):
    def _runtime(self):
        module = importlib.import_module("tools.interface_contract.event_contract")
        self.assertTrue(hasattr(module, "AppendSpy"))
        self.assertTrue(hasattr(module, "validate_event_stream"))
        return module

    def _catalog(self):
        return (
            json.loads(SCHEMA_PATH.read_text(encoding="utf-8")),
            json.loads(SUITE_PATH.read_text(encoding="utf-8")),
        )

    @staticmethod
    def _positive_case(suite, case_id):
        return next(case for case in suite["positive"] if case["id"] == case_id)

    def _materialize_stream_case(self, suite, case):
        base = self._positive_case(suite, case["base_case"])
        records = deepcopy(base["records"])
        source_revisions = deepcopy(base["source_revisions"])
        for event_id, revision in case.get("source_revision_overrides", {}).items():
            source_revisions[event_id] = revision
        for mutation in case["mutations"]:
            target = records[mutation["record_index"]]
            for segment in mutation["path"][:-1]:
                target = target[segment]
            target[mutation["path"][-1]] = deepcopy(mutation["value"])
        return records, source_revisions

    def test_positive_fixture_streams_are_accepted_without_rewriting_sequence(self):
        runtime = self._runtime()
        schema, suite = self._catalog()

        for case in suite["positive"]:
            records = deepcopy(case["records"])
            before = [record["canonical_event"]["seq"] for record in records]
            spy = runtime.AppendSpy()
            with self.subTest(case=case["id"]):
                self.assertEqual(
                    "PASSED",
                    runtime.validate_event_stream(
                        records, schema, case["source_revisions"], spy
                    ),
                )
                self.assertEqual(len(records), spy.calls)
                self.assertEqual(
                    before,
                    [record["canonical_event"]["seq"] for record in records],
                )

    def test_negative_stream_catalog_returns_stable_error_without_append(self):
        runtime = self._runtime()
        schema, suite = self._catalog()

        for case in suite["negative_streams"]:
            records, source_revisions = self._materialize_stream_case(suite, case)
            spy = runtime.AppendSpy()
            with self.subTest(case=case["id"]):
                with self.assertRaises(runtime.ContractError) as caught:
                    runtime.validate_event_stream(
                        records, schema, source_revisions, spy
                    )
                self.assertEqual(case["expected_error"], caught.exception.code)
                self.assertEqual(case["expected_append_calls"], spy.calls)

    def test_stream_sequence_starts_at_one_and_has_no_gap(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        cases = {case["id"]: case for case in suite["negative_streams"]}

        for case_id in ("stream-seq-reuse", "stream-seq-skip", "stream-seq-decrease"):
            records, source_revisions = self._materialize_stream_case(
                suite, cases[case_id]
            )
            with self.subTest(case=case_id):
                with self.assertRaisesRegex(
                    runtime.ContractError, "EVENT_STREAM_OUT_OF_ORDER"
                ):
                    runtime.validate_event_stream(records, schema, source_revisions)

    def test_stream_identity_tuple_is_exact_and_never_appends_on_mismatch(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        cases = {case["id"]: case for case in suite["negative_streams"]}

        for case_id in ("task-mix", "correlation-mix"):
            records, source_revisions = self._materialize_stream_case(
                suite, cases[case_id]
            )
            spy = runtime.AppendSpy()
            with self.subTest(case=case_id):
                with self.assertRaisesRegex(
                    runtime.ContractError, "EVENT_IDENTITY_MISMATCH"
                ):
                    runtime.validate_event_stream(records, schema, source_revisions, spy)
                self.assertEqual(0, spy.calls)

    def test_canonical_sequence_is_strictly_monotonic_and_never_reassigned(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        cases = {case["id"]: case for case in suite["negative_streams"]}

        for case_id in ("canonical-seq-reuse", "canonical-seq-decrease"):
            records, source_revisions = self._materialize_stream_case(
                suite, cases[case_id]
            )
            before = [record["canonical_event"]["seq"] for record in records]
            with self.subTest(case=case_id):
                with self.assertRaisesRegex(
                    runtime.ContractError, "EVENT_CANONICAL_SEQUENCE_INVALID"
                ):
                    runtime.validate_event_stream(records, schema, source_revisions)
                self.assertEqual(
                    before,
                    [record["canonical_event"]["seq"] for record in records],
                )

    def test_source_revision_must_be_exact_and_never_decrease(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        cases = {case["id"]: case for case in suite["negative_streams"]}

        for case_id in ("stale-revision", "revision-decrease"):
            records, source_revisions = self._materialize_stream_case(
                suite, cases[case_id]
            )
            with self.subTest(case=case_id):
                with self.assertRaisesRegex(
                    runtime.ContractError, "EVENT_REVISION_MISMATCH"
                ):
                    runtime.validate_event_stream(records, schema, source_revisions)

    def test_state_accepted_code_occurs_at_most_once_per_revision(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        case = self._positive_case(suite, "revision-increase")
        records = deepcopy(case["records"])
        for record in records:
            record["canonical_event"]["code"] = "STATE_ACCEPTED"

        self.assertEqual(
            "PASSED",
            runtime.validate_event_stream(records, schema, case["source_revisions"]),
        )

    def test_duplicate_or_non_main_state_accepted_is_rejected_without_append(self):
        runtime = self._runtime()
        schema, suite = self._catalog()
        cases = {case["id"]: case for case in suite["negative_streams"]}

        expected = {
            "duplicate-state-accepted": "EVENT_REVISION_MISMATCH",
            "work-owned-state-accepted": "EVENT_OWNER_INVALID",
        }
        for case_id, error_code in expected.items():
            records, source_revisions = self._materialize_stream_case(
                suite, cases[case_id]
            )
            spy = runtime.AppendSpy()
            with self.subTest(case=case_id):
                with self.assertRaisesRegex(runtime.ContractError, error_code):
                    runtime.validate_event_stream(records, schema, source_revisions, spy)
                self.assertEqual(0, spy.calls)


if __name__ == "__main__":
    unittest.main()
