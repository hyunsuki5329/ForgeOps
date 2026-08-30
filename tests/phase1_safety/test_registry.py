import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.phase1_safety.model import SafetyError, SourceIdentity, validate_source_identity
from tools.phase1_safety.registry import load_registry, resolve_committed_sha256


ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "fixtures/forgeops-phase1-safety/suite.json"


class Phase1SafetyRegistryTests(unittest.TestCase):
    def setUp(self):
        self.suite = json.loads(SUITE.read_text(encoding="utf-8"))

    def test_load_registry_returns_exact_immutable_registrations(self):
        registrations = load_registry(self.suite)
        self.assertEqual(23, len(registrations))
        self.assertEqual("resource-authority-negative", registrations[0].command_id)
        self.assertEqual("extension-provenance", registrations[-1].command_id)
        self.assertEqual("E3", registrations[4].required_tier)
        self.assertIsInstance(registrations, tuple)
        self.assertIsInstance(registrations[0].input_refs, tuple)

    def test_registry_rejects_coverage_and_identity_mutations(self):
        mutations = []

        missing = copy.deepcopy(self.suite)
        missing["registrations"].pop()
        mutations.append(missing)

        duplicate = copy.deepcopy(self.suite)
        duplicate["registrations"][-1] = copy.deepcopy(duplicate["registrations"][0])
        mutations.append(duplicate)

        reordered = copy.deepcopy(self.suite)
        reordered["registrations"][0], reordered["registrations"][1] = (
            reordered["registrations"][1],
            reordered["registrations"][0],
        )
        mutations.append(reordered)

        traversal = copy.deepcopy(self.suite)
        traversal["registrations"][0]["artifact_ref"] = "../result.json"
        mutations.append(traversal)

        substituted_artifact = copy.deepcopy(self.suite)
        substituted_artifact["registrations"][0]["artifact_ref"] = "artifacts/verification/substitute.json"
        mutations.append(substituted_artifact)

        substituted_field = copy.deepcopy(self.suite)
        substituted_field["registrations"][0]["input_bindings"][0]["field"] = "other_sha256"
        mutations.append(substituted_field)

        wildcard = copy.deepcopy(self.suite)
        wildcard["registrations"][0]["input_bindings"][0]["refs"][0] = "contracts/*.json"
        mutations.append(wildcard)

        wrong_subset = copy.deepcopy(self.suite)
        wrong_subset["subsets"]["security_negative"][0] = "snapshot-identity"
        mutations.append(wrong_subset)

        for index, value in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(SafetyError):
                load_registry(value)

    def test_source_identity_is_exact_and_source_bound(self):
        value = {
            "repository": "example/forgeops",
            "repository_id": "123",
            "default_branch": "main",
            "workflow_ref": "refs/heads/main",
            "source_sha": "a" * 40,
            "workflow_sha": "a" * 40,
            "run_id": "1001",
            "run_attempt": 1,
        }
        identity = validate_source_identity(value)
        self.assertEqual(SourceIdentity(**value), identity)

        for key, replacement in (
            ("workflow_ref", "refs/tags/main"),
            ("workflow_sha", "b" * 40),
            ("source_sha", "A" * 40),
            ("run_id", "run-1001"),
            ("run_attempt", 0),
        ):
            invalid = dict(value)
            invalid[key] = replacement
            with self.subTest(key=key), self.assertRaises(SafetyError):
                validate_source_identity(invalid)

    def test_committed_hash_accepts_crlf_checkout_but_rejects_dirty_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            source = root / "sample.txt"
            source.write_bytes(b"alpha\nbeta\n")
            subprocess.run(["git", "-C", str(root), "add", "sample.txt"], check=True)
            subprocess.run(
                [
                    "git", "-C", str(root), "-c", "user.name=ForgeOps Test",
                    "-c", "user.email=forgeops@example.invalid", "commit", "-qm", "fixture",
                ],
                check=True,
            )
            expected = hashlib.sha256(b"alpha\nbeta\n").hexdigest()

            source.write_bytes(b"alpha\r\nbeta\r\n")
            self.assertEqual(expected, resolve_committed_sha256(root, "sample.txt"))

            source.write_bytes(b"alpha\r\nchanged\r\n")
            with self.assertRaisesRegex(SafetyError, "^SOURCE_HASH_MISMATCH$"):
                resolve_committed_sha256(root, "sample.txt")

    def test_committed_hash_rejects_missing_git_and_unsafe_refs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.txt").write_text("alpha\n", encoding="utf-8")
            with self.assertRaisesRegex(SafetyError, "^SOURCE_IDENTITY_UNAVAILABLE$"):
                resolve_committed_sha256(root, "sample.txt")

        for ref in ("../sample.txt", "C:/sample.txt", "sample\\file", "*.json", "sample?.txt"):
            with self.subTest(ref=ref), self.assertRaises(SafetyError):
                resolve_committed_sha256(ROOT, ref)


if __name__ == "__main__":
    unittest.main()
