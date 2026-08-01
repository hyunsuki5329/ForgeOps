import json
from pathlib import Path
import os
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tools.snapshot_context.model import (
    SnapshotError,
    canonical_json_bytes,
    canonical_relative_path,
    sha256_bytes,
)
from tools.snapshot_context.snapshot import (
    _read_stable_regular_file,
    create_snapshot,
    verify_snapshot,
)


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def make_repository(root: Path) -> None:
    git(root, "init", "-q")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "user.name", "ForgeOps Fixture")
    (root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    (root / "both.txt").write_text("base\n", encoding="utf-8")
    (root / "deleted.txt").write_text("delete me\n", encoding="utf-8")
    git(root, "add", "--", "alpha.txt", "both.txt", "deleted.txt")
    git(root, "commit", "-qm", "fixture")


class SnapshotProviderTests(unittest.TestCase):
    def test_clean_snapshot_is_repeatable_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "source"
            source.mkdir()
            make_repository(source)
            before_status = git(source, "status", "--porcelain=v2", "-z", "--untracked-files=all")
            before = (source / "alpha.txt").read_bytes()

            first = create_snapshot(source, base / "bundle-a", "fixture")
            second = create_snapshot(source, base / "bundle-b", "fixture")

            self.assertEqual(first.manifest, second.manifest)
            self.assertEqual(before, (source / "alpha.txt").read_bytes())
            self.assertEqual(before_status, git(source, "status", "--porcelain=v2", "-z", "--untracked-files=all"))
            self.assertNotEqual(first.snapshot_root, first.workspace_root)
            verify_snapshot(first.snapshot_root, first.manifest)

    def test_dirty_states_deleted_and_workspace_separation(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "source"
            source.mkdir()
            make_repository(source)
            (source / "both.txt").write_text("staged\n", encoding="utf-8")
            git(source, "add", "--", "both.txt")
            (source / "both.txt").write_text("staged then modified\n", encoding="utf-8")
            (source / "alpha.txt").write_text("modified\n", encoding="utf-8")
            (source / "new.txt").write_text("untracked\n", encoding="utf-8")
            (source / "deleted.txt").unlink()
            expected_modified = (source / "alpha.txt").read_bytes()

            bundle = create_snapshot(source, base / "bundle", "fixture")
            entries = {item["path"]: item for item in bundle.manifest["entries"]}

            self.assertEqual(["tracked", "staged", "modified"], entries["both.txt"]["source_states"])
            self.assertEqual(["tracked", "modified"], entries["alpha.txt"]["source_states"])
            self.assertEqual(["untracked"], entries["new.txt"]["source_states"])
            self.assertEqual(["deleted.txt"], bundle.manifest["deleted_paths"])
            (bundle.workspace_root / "alpha.txt").write_text("workspace only\n", encoding="utf-8")
            self.assertEqual(expected_modified, (bundle.snapshot_root / "alpha.txt").read_bytes())
            self.assertEqual(expected_modified, (source / "alpha.txt").read_bytes())

    def test_non_git_source_and_existing_destination_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "source"
            source.mkdir()
            with self.assertRaisesRegex(SnapshotError, "SNAPSHOT_SOURCE_INVALID"):
                create_snapshot(source, base / "bundle", "fixture")
            self.assertFalse((base / "bundle").exists())

            make_repository(source)
            (base / "occupied").mkdir()
            with self.assertRaisesRegex(SnapshotError, "SNAPSHOT_DESTINATION_INVALID"):
                create_snapshot(source, base / "occupied", "fixture")

    def test_destination_inside_source_is_rejected_without_dirtying_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source"
            source.mkdir()
            make_repository(source)
            before = git(source, "status", "--porcelain=v2", "-z", "--untracked-files=all")

            with self.assertRaisesRegex(SnapshotError, "SNAPSHOT_DESTINATION_INVALID"):
                create_snapshot(source, source / "bundle", "fixture")

            self.assertEqual(
                before,
                git(source, "status", "--porcelain=v2", "-z", "--untracked-files=all"),
            )
            self.assertFalse((source / "bundle").exists())

    def test_canonical_path_rejects_escape_and_git_metadata(self):
        for raw in ("", "/absolute", "../escape", "a/../../escape", "a\\b", "a//b", ".git/config"):
            with self.subTest(raw=raw), self.assertRaisesRegex(SnapshotError, "SNAPSHOT_PATH_INVALID"):
                canonical_relative_path(raw)

    def test_protected_file_is_rejected_before_materialization(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "source"
            source.mkdir()
            make_repository(source)
            (source / ".env").write_text("DO_NOT_READ=value\n", encoding="utf-8")
            destination = base / "bundle"
            with self.assertRaisesRegex(SnapshotError, "SNAPSHOT_PATH_INVALID"):
                create_snapshot(source, destination, "fixture")
            self.assertFalse(destination.exists())

    @unittest.skipIf(os.name == "nt", "Windows symlink creation requires optional privilege")
    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "source"
            source.mkdir()
            make_repository(source)
            os.symlink("alpha.txt", source / "link.txt")
            destination = base / "bundle"
            with self.assertRaisesRegex(SnapshotError, "SNAPSHOT_FILE_TYPE_FORBIDDEN"):
                create_snapshot(source, destination, "fixture")
            self.assertFalse(destination.exists())

    def test_injected_traversal_inventory_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "source"
            source.mkdir()

            def runner(argv, **kwargs):
                if "rev-parse" in argv and "--is-inside-work-tree" in argv:
                    return SimpleNamespace(returncode=0, stdout=b"true\n", stderr=b"")
                if "rev-parse" in argv and "--verify" in argv:
                    return SimpleNamespace(returncode=1, stdout=b"", stderr=b"")
                if "ls-files" in argv and "-s" not in argv:
                    return SimpleNamespace(returncode=0, stdout=b"../escape\0", stderr=b"")
                return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

            with self.assertRaisesRegex(SnapshotError, "SNAPSHOT_PATH_INVALID"):
                create_snapshot(source, base / "bundle", "fixture", runner=runner)

    def test_verify_detects_content_change_and_manifest_is_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "source"
            source.mkdir()
            make_repository(source)
            bundle = create_snapshot(source, base / "bundle", "fixture")
            manifest_path = base / "bundle" / "manifest.json"
            self.assertEqual(bundle.manifest, json.loads(manifest_path.read_text(encoding="utf-8")))
            (bundle.snapshot_root / "alpha.txt").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(SnapshotError, "SNAPSHOT_CONTENT_CHANGED"):
                verify_snapshot(bundle.snapshot_root, bundle.manifest)

    def test_verify_rejects_unknown_manifest_field_and_extra_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "source"
            source.mkdir()
            make_repository(source)
            bundle = create_snapshot(source, base / "bundle", "fixture")

            unknown = json.loads(json.dumps(bundle.manifest))
            unknown["authority"] = {"write_scope": "PROJECT"}
            body = {
                key: value
                for key, value in unknown.items()
                if key not in ("snapshot_id", "manifest_sha256")
            }
            digest = sha256_bytes(canonical_json_bytes(body))
            unknown["snapshot_id"] = f"sha256:{digest}"
            unknown["manifest_sha256"] = digest
            with self.assertRaisesRegex(SnapshotError, "SNAPSHOT_CONTENT_CHANGED"):
                verify_snapshot(bundle.snapshot_root, unknown)

            (bundle.snapshot_root / "unexpected-empty-directory").mkdir()
            with self.assertRaisesRegex(SnapshotError, "SNAPSHOT_CONTENT_CHANGED"):
                verify_snapshot(bundle.snapshot_root, bundle.manifest)

    @unittest.skipIf(os.name == "nt", "Windows symlink creation requires optional privilege")
    def test_verify_rejects_extra_directory_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "source"
            source.mkdir()
            make_repository(source)
            bundle = create_snapshot(source, base / "bundle", "fixture")
            outside = base / "outside"
            outside.mkdir()
            os.symlink(outside, bundle.snapshot_root / "external-directory")
            with self.assertRaisesRegex(SnapshotError, "SNAPSHOT_CONTENT_CHANGED"):
                verify_snapshot(bundle.snapshot_root, bundle.manifest)

    @unittest.skipIf(os.name == "nt", "Windows symlink creation requires optional privilege")
    def test_verify_rejects_symlinked_snapshot_root(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "source"
            source.mkdir()
            make_repository(source)
            bundle = create_snapshot(source, base / "bundle", "fixture")
            alias = base / "snapshot-alias"
            os.symlink(bundle.snapshot_root, alias)
            with self.assertRaisesRegex(SnapshotError, "SNAPSHOT_CONTENT_CHANGED"):
                verify_snapshot(alias, bundle.manifest)

    def test_stable_reader_rejects_descriptor_swap_before_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            safe = root / "safe.txt"
            outside = root / "outside.txt"
            safe.write_bytes(b"safe")
            outside.write_bytes(b"private")
            outside_descriptor = os.open(outside, os.O_RDONLY)
            with mock.patch(
                "tools.snapshot_context.snapshot.os.open",
                return_value=outside_descriptor,
            ), mock.patch("tools.snapshot_context.snapshot.os.fdopen") as fdopen:
                with self.assertRaisesRegex(SnapshotError, "SNAPSHOT_CONTENT_CHANGED"):
                    _read_stable_regular_file(root, Path("safe.txt"))
                fdopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
