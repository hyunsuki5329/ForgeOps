import copy
from pathlib import Path
import tempfile
import unittest

from tests.phase1_safety.test_gate import _prepared
from tests.phase1_safety.test_freshness import NOW
from tools.phase1_safety.audit import decide_phase1_safety
from tools.phase1_safety.model import SafetyError
from tools.phase1_safety.scorecard import (
    atomic_publish_scorecard,
    render_scorecard_html,
    render_scorecard_markdown,
)


class Phase1ScorecardTests(unittest.TestCase):
    def _decision(self, root: Path) -> dict:
        _identity, _runner, kwargs = _prepared(root)
        return decide_phase1_safety(root, **kwargs)

    def test_markdown_and_html_are_static_public_deterministic_views(self):
        with tempfile.TemporaryDirectory() as directory:
            decision = self._decision(Path(directory))
            markdown = render_scorecard_markdown(decision)
            html = render_scorecard_html(decision)

        self.assertEqual(markdown, render_scorecard_markdown(decision))
        self.assertEqual(html, render_scorecard_html(decision))
        self.assertEqual(19, markdown.count("| VG-"))
        self.assertEqual(19, html.count("<tr><td>VG-"))
        for forbidden in ("<script", "<form", "javascript:", "file://", "http://", "https://", "onload=", "onclick="):
            self.assertNotIn(forbidden, markdown.lower())
            self.assertNotIn(forbidden, html.lower())
        self.assertNotIn('"cases"', markdown)
        self.assertNotIn('"cases"', html)

    def test_renderer_rejects_noncanonical_row_count(self):
        with tempfile.TemporaryDirectory() as directory:
            decision = self._decision(Path(directory))
            decision["gates"].pop()
            with self.assertRaises(SafetyError):
                render_scorecard_markdown(decision)

    def test_mid_publish_failure_invalidates_all_three_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = self._decision(root)
            targets = (
                root / "artifacts/verification/phase-1-safety-gate-result.json",
                root / "artifacts/reviews/phase-1-safety-scorecard.md",
                root / "artifacts/reviews/phase-1-safety-scorecard.html",
            )
            for target in targets:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("old-generation", encoding="utf-8")
            calls = 0

            def fail_second(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected")
                return __import__("os").replace(source, target)

            with self.assertRaisesRegex(SafetyError, "SCORECARD_WRITE_FAILED"):
                atomic_publish_scorecard(*targets, decision, replacer=fail_second)
            self.assertFalse(any(target.exists() for target in targets))


if __name__ == "__main__":
    unittest.main()
