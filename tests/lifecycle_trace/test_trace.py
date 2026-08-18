import unittest

from tools.lifecycle_trace.model import LifecycleError
from tools.lifecycle_trace.trace import ExternalWriteGate, TraceManifest, render_trace_html


def valid_manifest():
    trace = TraceManifest(
        {"task_id": "TASK-W8-001", "run_id": "RUN-W8-001", "correlation_id": "CORR-W8-001"},
        evidence_catalog=("EVID-W8-TASK",), artifact_catalog=("ART-W8-DIFF",),
    )
    trace.append("MAIN", "TASK_ACCEPTED", 1, evidence_refs=("EVID-W8-TASK",))
    trace.append("WORK", "CLEANUP_VERIFIED", 2, artifact_refs=("ART-W8-DIFF",))
    trace.finalize("SUCCESS", ("CLOSE",), {"remaining": {
        "processes": 0, "mounts": 0, "leases": 0,
        "transient_secrets": 0, "workspaces": 0}})
    return trace


class TraceManifestTests(unittest.TestCase):
    def test_valid_trace_is_closed_and_rendered_without_script(self):
        trace = valid_manifest()
        manifest = trace.validate()
        self.assertEqual([1, 2], [event["seq"] for event in manifest["events"]])
        html = render_trace_html(manifest)
        self.assertIn("ForgeOps W8 Trace", html)
        self.assertIn("CLEANUP_VERIFIED", html)
        self.assertNotIn("<script", html.lower())

    def test_sequence_gap_and_reorder_are_rejected(self):
        for seqs in ((1, 3), (2, 1)):
            with self.subTest(seqs=seqs):
                trace = valid_manifest()
                for event, seq in zip(trace.events, seqs):
                    event["seq"] = seq
                with self.assertRaisesRegex(LifecycleError, "TRACE_SEQUENCE_INVALID"):
                    trace.validate()

    def test_revision_decrease_and_actor_are_rejected(self):
        trace = valid_manifest()
        trace.events[1]["revision"] = 0
        with self.assertRaisesRegex(LifecycleError, "TRACE_REVISION_INVALID"):
            trace.validate()
        trace = valid_manifest()
        trace.events[0]["actor"] = "ROOT"
        with self.assertRaisesRegex(LifecycleError, "TRACE_ACTOR_INVALID"):
            trace.validate()

    def test_dangling_evidence_or_artifact_is_rejected(self):
        for field, value in (("evidence_refs", ["EVID-MISSING"]),
                             ("artifact_refs", ["ART-MISSING"])):
            with self.subTest(field=field):
                trace = valid_manifest()
                trace.events[0][field] = value
                with self.assertRaisesRegex(LifecycleError, "TRACE_REFERENCE_INVALID"):
                    trace.validate()

    def test_cleanup_terminal_and_next_action_are_closed(self):
        trace = valid_manifest()
        trace.cleanup = None
        with self.assertRaisesRegex(LifecycleError, "TRACE_CLEANUP_INVALID"):
            trace.validate()
        trace = valid_manifest()
        trace.terminal["reason"] = ""
        with self.assertRaisesRegex(LifecycleError, "TRACE_TERMINAL_INVALID"):
            trace.validate()
        trace = valid_manifest()
        trace.terminal["next_actions"] = ["RETRY_REPAIR"]
        with self.assertRaisesRegex(LifecycleError, "TRACE_NEXT_ACTION_INVALID"):
            trace.validate()

    def test_html_escapes_untrusted_text(self):
        trace = valid_manifest()
        trace.events[0]["event_type"] = "<img src=x onerror=alert(1)>"
        html = render_trace_html(trace.to_dict())
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)


class ExternalWriteGateTests(unittest.TestCase):
    def setUp(self):
        self.gate = ExternalWriteGate(expected_approval="APPROVAL-W8", allowed_target="github:forgeops")

    def test_no_external_write_is_safe(self):
        self.assertEqual("PASSED", self.gate.authorize("NONE", None, False, None, None))

    def test_action_gateway_target_and_approval_are_closed(self):
        cases = (
            (("PUBLISH", "github:forgeops", True, "APPROVAL-W8", "EFFECT-1"), "EXTERNAL_ACTION_FORBIDDEN"),
            (("APPROVED_EXTERNAL_WRITE", "github:forgeops", False, "APPROVAL-W8", "EFFECT-1"), "EXTERNAL_GATEWAY_REQUIRED"),
            (("APPROVED_EXTERNAL_WRITE", "https://example.test", True, "APPROVAL-W8", "EFFECT-1"), "EXTERNAL_TARGET_INVALID"),
            (("APPROVED_EXTERNAL_WRITE", "github:forgeops", True, None, "EFFECT-1"), "EXTERNAL_APPROVAL_REQUIRED"),
            (("APPROVED_EXTERNAL_WRITE", "github:forgeops", True, "WRONG", "EFFECT-1"), "EXTERNAL_APPROVAL_INVALID"),
        )
        for args, code in cases:
            with self.subTest(code=code):
                with self.assertRaisesRegex(LifecycleError, code):
                    self.gate.authorize(*args)

    def test_effect_identity_is_single_use(self):
        args = ("APPROVED_EXTERNAL_WRITE", "github:forgeops", True, "APPROVAL-W8", "EFFECT-1")
        self.assertEqual("AUTHORIZED", self.gate.authorize(*args))
        with self.assertRaisesRegex(LifecycleError, "EXTERNAL_EFFECT_DUPLICATE"):
            self.gate.authorize(*args)

    def test_denial_effect_and_secret_audits_fail_closed(self):
        with self.assertRaisesRegex(LifecycleError, "EXTERNAL_DENIAL_TRACE_MISSING"):
            self.gate.audit(denial_required=True, denial_traced=False, effect_observed=False, public_text="safe")
        with self.assertRaisesRegex(LifecycleError, "EXTERNAL_EFFECT_OBSERVED"):
            self.gate.audit(denial_required=False, denial_traced=True, effect_observed=True, public_text="safe")
        with self.assertRaisesRegex(LifecycleError, "RESULT_SECRET_DETECTED"):
            self.gate.audit(denial_required=False, denial_traced=True, effect_observed=False,
                            public_text="token=ghp_12345678901234567890")


if __name__ == "__main__":
    unittest.main()
