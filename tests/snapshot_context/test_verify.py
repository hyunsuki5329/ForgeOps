import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_SCHEMA_REF = "contracts/forgeops-snapshot-contract/1.0/schema.json"
CONTEXT_SCHEMA_REF = "contracts/forgeops-context-pack/1.0/schema.json"
SNAPSHOT_SUITE_REF = "fixtures/forgeops-snapshot-baseline/suite.json"
CONTEXT_SUITE_REF = "fixtures/forgeops-context-security/suite.json"


def prepare_repository(root: Path) -> None:
    for relative in (
        SNAPSHOT_SCHEMA_REF,
        CONTEXT_SCHEMA_REF,
        SNAPSHOT_SUITE_REF,
        CONTEXT_SUITE_REF,
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)


def namespace(command_id: str, *, result: str | None = None) -> argparse.Namespace:
    context = command_id in ("context-provenance", "injection-negative")
    return argparse.Namespace(
        mode="context" if context else "snapshot-baseline",
        snapshot_schema=SNAPSHOT_SCHEMA_REF,
        context_schema=CONTEXT_SCHEMA_REF,
        suite=CONTEXT_SUITE_REF if context else SNAPSHOT_SUITE_REF,
        result=result
        or {
            "snapshot-identity": "artifacts/verification/vg-010-snapshot-identity-result.json",
            "baseline-retrieval-repeat": "artifacts/verification/vg-010-baseline-retrieval-result.json",
            "context-provenance": "artifacts/verification/vg-011-context-provenance-result.json",
            "injection-negative": "artifacts/verification/vg-011-injection-negative-result.json",
        }[command_id],
        command_id=command_id,
    )


def all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        result = set(value)
        for child in value.values():
            result.update(all_keys(child))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for child in value:
            result.update(all_keys(child))
        return result
    return set()


class SnapshotContextVerifierTests(unittest.TestCase):
    def test_registered_identity_catalog_is_exact(self):
        from tools.snapshot_context import verify

        self.assertEqual(
            {
                "snapshot-identity",
                "baseline-retrieval-repeat",
                "context-provenance",
                "injection-negative",
            },
            set(verify.TRUSTED_COMMANDS),
        )

    def test_snapshot_verification_writes_closed_public_result_atomically(self):
        from tools.snapshot_context import verify

        with tempfile.TemporaryDirectory() as folder:
            repository = Path(folder)
            prepare_repository(repository)
            args = namespace("snapshot-identity")
            result_path = repository / args.result
            result_path.parent.mkdir(parents=True)
            result_path.write_text("old incomplete result", encoding="utf-8")

            exit_code = verify.run(args, repository_root=repository)
            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        self.assertEqual(
            {
                "result_version",
                "gate_id",
                "profile_id",
                "command_id",
                "status",
                "evidence_tier",
                "observed_at",
                "input_hashes",
                "summary",
                "effect_counters",
                "cases",
            },
            set(result),
        )
        self.assertEqual("PASSED", result["status"])
        self.assertEqual("E2", result["evidence_tier"])
        self.assertEqual(0, result["summary"]["failed"])
        self.assertEqual(
            {"source_writes": 0, "protected_reads": None, "network_calls": None, "external_writes": None},
            result["effect_counters"],
        )
        forbidden = {"stdout", "stderr", "environment", "secret", "credential", "authority", "approval"}
        self.assertFalse(forbidden & all_keys(result))
        self.assertIsNone(re.search(r"[A-Za-z]:[\\/]", json.dumps(result)))

    def test_result_hashes_match_raw_inputs(self):
        from tools.snapshot_context import verify

        with tempfile.TemporaryDirectory() as folder:
            repository = Path(folder)
            prepare_repository(repository)
            args = namespace("context-provenance")
            self.assertEqual(0, verify.run(args, repository_root=repository))
            result = json.loads((repository / args.result).read_text(encoding="utf-8"))
            expected = {
                "snapshot_schema_sha256": hashlib.sha256((repository / SNAPSHOT_SCHEMA_REF).read_bytes()).hexdigest(),
                "context_schema_sha256": hashlib.sha256((repository / CONTEXT_SCHEMA_REF).read_bytes()).hexdigest(),
                "suite_sha256": hashlib.sha256((repository / CONTEXT_SUITE_REF).read_bytes()).hexdigest(),
            }
        self.assertEqual(expected, result["input_hashes"])

    def test_wrong_command_result_pair_is_rejected_before_write(self):
        from tools.snapshot_context import verify

        with tempfile.TemporaryDirectory() as folder:
            repository = Path(folder)
            prepare_repository(repository)
            args = namespace(
                "snapshot-identity",
                result="artifacts/verification/vg-010-baseline-retrieval-result.json",
            )
            with self.assertRaisesRegex(verify.VerificationError, "VERIFIER_IDENTITY_INVALID"):
                verify.run(args, repository_root=repository)
            self.assertFalse((repository / args.result).exists())

    def test_runtime_rejects_reordered_or_open_fixture_catalog(self):
        from tools.snapshot_context import verify

        with tempfile.TemporaryDirectory() as folder:
            repository = Path(folder)
            prepare_repository(repository)
            suite_path = repository / SNAPSHOT_SUITE_REF
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["cases"] = list(reversed(suite["cases"]))
            suite["cases"][0]["authority"] = "PROJECT"
            suite_path.write_text(json.dumps(suite), encoding="utf-8")
            args = namespace("snapshot-identity")
            with self.assertRaisesRegex(verify.VerificationError, "VERIFIER_INPUT_INVALID"):
                verify.run(args, repository_root=repository)
            self.assertFalse((repository / args.result).exists())

    def test_baseline_retrieval_command_runs_integrated_repeat_probe(self):
        from tools.snapshot_context import verify

        suite = json.loads((ROOT / SNAPSHOT_SUITE_REF).read_text(encoding="utf-8"))
        audit = verify.EffectAudit()
        with mock.patch.object(verify, "_baseline_retrieval_repeat_probe") as probe:
            verify._evaluate_suite("snapshot-baseline", suite, "baseline-retrieval-repeat", audit)
        probe.assert_called_once()

    def test_effect_counters_come_from_audit_object(self):
        from tools.snapshot_context import verify

        audit = verify.EffectAudit()
        audit.source_writes = 2
        audit.observe_read(Path("fixture") / ".env")
        audit.observe_read(Path("fixture") / "api-credential.txt")
        audit.observe_read(Path("fixture") / "secret-note.txt")
        self.assertEqual(
            {
                "source_writes": 2,
                "protected_reads": None,
                "network_calls": None,
                "external_writes": None,
            },
            audit.as_dict(),
        )
        self.assertEqual(3, audit.protected_reads_observed)

    def test_source_write_audit_detects_provider_regression(self):
        from tools.snapshot_context import verify

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source"
            source.mkdir()
            tracked = source / "tracked.txt"
            tracked.write_text("before", encoding="utf-8")
            audit = verify.EffectAudit()

            def mutating_provider(*args, **kwargs):
                tracked.write_text("after provider write", encoding="utf-8")
                return object()

            with mock.patch.object(verify, "create_snapshot", side_effect=mutating_provider):
                verify._create_audited_snapshot(
                    source, Path(folder) / "bundle", "fixture", audit
                )
            self.assertEqual(1, audit.source_writes)

    def test_runner_failure_returns_two_without_replacing_result(self):
        from tools.snapshot_context import verify

        with tempfile.TemporaryDirectory() as folder:
            repository = Path(folder)
            prepare_repository(repository)
            args = namespace("context-provenance")
            result_path = repository / args.result
            result_path.parent.mkdir(parents=True)
            result_path.write_text("preserve", encoding="utf-8")
            with mock.patch.object(verify, "_evaluate_suite", side_effect=RuntimeError("boom")):
                exit_code = verify.main(
                    [
                        args.mode,
                        "--snapshot-schema", args.snapshot_schema,
                        "--context-schema", args.context_schema,
                        "--suite", args.suite,
                        "--result", args.result,
                        "--command-id", args.command_id,
                    ],
                    repository_root=repository,
                )
            self.assertEqual(2, exit_code)
            self.assertEqual("preserve", result_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
