from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import PROJECT_ROOT


class ClaudeStatusLineTests(unittest.TestCase):
    def test_compact_line_uses_shared_information_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "sample-project"
            repo.mkdir()
            subprocess.run(
                ["git", "init", "-q", "-b", "feature/status", str(repo)],
                check=True,
            )
            payload = {
                "model": {"display_name": "Sonnet"},
                "effort": {"level": "high"},
                "workspace": {
                    "current_dir": str(repo),
                    "project_dir": str(repo),
                },
                "context_window": {"remaining_percentage": 73.4},
                "cost": {
                    "total_cost_usd": 0.123,
                    "total_duration_ms": 125000,
                },
            }

            completed = subprocess.run(
                [str(PROJECT_ROOT / "status-lines/claude.sh")],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertEqual(
                completed.stdout.strip(),
                "Sonnet/high · sample-project@feature/status · ctx 73% left · $0.12 · 2m5s",
            )


if __name__ == "__main__":
    unittest.main()
