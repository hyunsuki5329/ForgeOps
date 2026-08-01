from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator

from tools.snapshot_context.baseline import run_baseline, validate_profile
from tools.snapshot_context.model import SnapshotError, canonical_json_bytes, sha256_bytes


ROOT = Path(__file__).resolve().parents[2]


def empty_manifest() -> dict[str, object]:
    body = {
        "snapshot_version": "1.0",
        "source": {
            "repository_label": "baseline-fixture",
            "head_sha": "a" * 40,
            "git_state_sha256": "b" * 64,
        },
        "dirty": False,
        "entries": [],
        "deleted_paths": [],
    }
    digest = sha256_bytes(canonical_json_bytes(body))
    return {**body, "snapshot_id": f"sha256:{digest}", "manifest_sha256": digest}


def command(command_id: str, code: str, **overrides) -> dict[str, object]:
    value = {
        "command_id": command_id,
        "argv": [sys.executable, "-c", code],
        "cwd": ".",
        "timeout_seconds": 10,
        "max_output_bytes": 4096,
    }
    value.update(overrides)
    return value


def profile(*commands: dict[str, object]) -> dict[str, object]:
    return {
        "profile_id": "fixture-baseline",
        "profile_version": "1.0",
        "commands": list(commands),
    }


def recursive_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        result = set(value)
        for child in value.values():
            result.update(recursive_keys(child))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for child in value:
            result.update(recursive_keys(child))
        return result
    return set()


class BaselineRunnerTests(unittest.TestCase):
    def test_profile_validation_accepts_ordered_commands(self):
        commands = validate_profile(profile(command("one", "pass"), command("two", "pass")))
        self.assertEqual(["one", "two"], [item["command_id"] for item in commands])

    def test_profile_validation_rejects_malformed_or_unsafe_values(self):
        invalid_profiles = []
        unknown = profile(command("one", "pass"))
        unknown["authority"] = "PROJECT"
        invalid_profiles.append(unknown)
        invalid_profiles.append(profile(command("same", "pass"), command("same", "pass")))
        invalid_profiles.append(profile({**command("one", "pass"), "argv": "python -c pass"}))
        invalid_profiles.append(profile({**command("one", "pass"), "argv": []}))
        invalid_profiles.append(profile(command("one", "pass", cwd="../escape")))
        invalid_profiles.append(profile(command("one", "pass", cwd=str(Path.cwd().anchor))))
        invalid_profiles.append(profile(command("one", "pass", timeout_seconds=0)))
        invalid_profiles.append(profile(command("one", "pass", timeout_seconds=301)))
        invalid_profiles.append(profile(command("one", "pass", max_output_bytes=1023)))
        invalid_profiles.append(profile(command("one", "pass", max_output_bytes=1048577)))
        invalid_profiles.append(profile({**command("one", "pass"), "argv": ["python|shell", "x"]}))
        invalid_profiles.append(profile({**command("one", "pass"), "shell": True}))
        for index, candidate in enumerate(invalid_profiles):
            with self.subTest(index=index), self.assertRaisesRegex(
                SnapshotError, "BASELINE_PROFILE_INVALID"
            ):
                validate_profile(candidate)

    def test_pass_nonzero_and_schema_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            artifact = run_baseline(
                workspace,
                empty_manifest(),
                profile(command("pass", "print('ok')"), command("fail", "raise SystemExit(7)")),
            )
        self.assertEqual("BASELINE_UNHEALTHY", artifact["status"])
        self.assertEqual(["PASSED", "BASELINE_UNHEALTHY"], [item["status"] for item in artifact["commands"]])
        self.assertEqual(7, artifact["commands"][1]["exit_code"])
        self.assertEqual({"total": 2, "passed": 1, "failed": 1, "not_run": 0}, artifact["summary"])
        schema = json.loads(
            (ROOT / "contracts/forgeops-snapshot-contract/1.0/schema.json").read_text(encoding="utf-8")
        )["$defs"]["baseline_artifact"]
        self.assertEqual([], list(Draft202012Validator(schema).iter_errors(artifact)))

    def test_timeout_stops_following_command(self):
        with tempfile.TemporaryDirectory() as folder:
            artifact = run_baseline(
                Path(folder),
                empty_manifest(),
                profile(
                    command("slow", "import time; time.sleep(3)", timeout_seconds=1),
                    command("never", "pass"),
                ),
            )
        self.assertEqual("BASELINE_TIMEOUT", artifact["status"])
        self.assertEqual(["BASELINE_TIMEOUT", "NOT_RUN"], [item["status"] for item in artifact["commands"]])
        self.assertEqual(1, artifact["summary"]["not_run"])

    def test_missing_executable_is_runner_error_and_public_safe(self):
        missing = command("missing", "pass")
        missing["argv"] = ["forgeops-command-that-does-not-exist"]
        with tempfile.TemporaryDirectory() as folder:
            artifact = run_baseline(Path(folder), empty_manifest(), profile(missing))
        self.assertEqual("BASELINE_RUNNER_ERROR", artifact["status"])
        self.assertIsNone(artifact["commands"][0]["exit_code"])
        forbidden = {"stdout", "stderr", "output", "environment", "env", "absolute_path"}
        self.assertFalse(forbidden & recursive_keys(artifact))

    def test_output_is_counted_but_never_retained(self):
        noisy = "import sys; sys.stdout.write('x'*5000); sys.stderr.write('y'*17)"
        with tempfile.TemporaryDirectory() as folder:
            artifact = run_baseline(
                Path(folder), empty_manifest(), profile(command("noisy", noisy, max_output_bytes=1024))
            )
        result = artifact["commands"][0]
        self.assertEqual("PASSED", result["status"])
        self.assertGreaterEqual(result["stdout_bytes_seen"], 5000)
        self.assertGreaterEqual(result["stderr_bytes_seen"], 17)
        self.assertTrue(result["output_truncated"])

    def test_clock_is_injectable_and_utc_serialized(self):
        moments = iter(
            [
                datetime(2026, 8, 1, 1, 2, 3, tzinfo=timezone.utc),
                datetime(2026, 8, 1, 1, 2, 4, tzinfo=timezone.utc),
            ]
        )
        with tempfile.TemporaryDirectory() as folder:
            artifact = run_baseline(
                Path(folder), empty_manifest(), profile(command("pass", "pass")), clock=lambda: next(moments)
            )
        self.assertEqual("2026-08-01T01:02:03Z", artifact["started_at"])
        self.assertEqual("2026-08-01T01:02:04Z", artifact["completed_at"])


if __name__ == "__main__":
    unittest.main()
