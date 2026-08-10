from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_console.lifecycle import capture_event, context_brief, draft_learning, record_correction


class LifecycleTests(unittest.TestCase):
    def test_brief_is_bounded_and_contains_repo_state(self) -> None:
        state = {
            "repository": True,
            "root": "/work/repo",
            "branch": "feature/test",
            "changes": [f" M file-{index}.txt" for index in range(30)],
            "changeCount": 30,
            "recentCommits": ["abc123 first", "def456 second"],
        }
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {"AI_CONSOLE_STATE_HOME": temporary}), patch(
                "ai_console.lifecycle.repo_state", return_value=state
            ):
                brief = context_brief(Path("/work/repo"))

        self.assertIn("feature/test", brief)
        self.assertIn("Working tree changes: 30", brief)
        self.assertLessEqual(len(brief.splitlines()), 25)

    def test_capture_stores_only_structured_marker_not_raw_message(self) -> None:
        state = {
            "repository": True,
            "root": "/work/repo",
            "branch": "main",
            "changeCount": 1,
        }
        payload = {
            "cwd": "/work/repo",
            "session_id": "session-1",
            "last_assistant_message": (
                "private transcript text\n"
                "AI-CONSOLE-CORRECTION: verify every generated profile password=hidden"
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {"AI_CONSOLE_STATE_HOME": temporary}), patch(
                "ai_console.lifecycle.repo_state", return_value=state
            ):
                destination = capture_event("codex", payload, "stop")
                saved = destination.read_text(encoding="utf-8")
                mode = destination.stat().st_mode & 0o777
                state_mode = Path(temporary).stat().st_mode & 0o777
                sessions_mode = (Path(temporary) / "sessions").stat().st_mode & 0o777

        self.assertNotIn("private transcript text", saved)
        self.assertNotIn("hidden", saved)
        self.assertIn("[REDACTED]", saved)
        self.assertEqual(mode, 0o600)
        self.assertEqual(state_mode, 0o700)
        self.assertEqual(sessions_mode, 0o700)

    def test_repeated_manual_corrections_create_review_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {"AI_CONSOLE_STATE_HOME": temporary}):
                record_correction(
                    "Verify profile paths, not only baseline paths.", "test", "session-a"
                )
                record_correction(
                    "Verify profile paths, not only baseline paths.", "test", "session-b"
                )
                destination = draft_learning()
                content = destination.read_text(encoding="utf-8")

        self.assertIn("Occurrences: 2", content)
        self.assertIn("Apply only after human review", content)
        self.assertIn("Suggested layer(s): test", content)


if __name__ == "__main__":
    unittest.main()
