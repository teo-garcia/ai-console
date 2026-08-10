from __future__ import annotations

import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from ai_console.config import ConfigError
from ai_console.mcp import CLIENTS, expected_outputs, render_all, server_for_client
from ai_console.rules import expected_rule_outputs, render_rules
from tests.helpers import copy_template_tree


class McpRenderingTests(unittest.TestCase):
    def test_all_expected_outputs_parse_and_have_no_placeholders(self) -> None:
        outputs = expected_outputs()

        self.assertGreaterEqual(len(outputs), len(CLIENTS) * 6)
        for path, content in outputs.items():
            self.assertNotIn("${", content, path)
            if path.suffix == ".toml":
                tomllib.loads(content)
            else:
                json.loads(content)

    def test_render_check_detects_and_repairs_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_template_tree(Path(temporary))
            output = root / "mcp/cursor.mcp.json"
            output.write_text("{}\n", encoding="utf-8")

            self.assertIn(output, render_all(root, check=True))
            self.assertIn(output, render_all(root))
            self.assertEqual(render_all(root, check=True), [])

    def test_missing_client_value_is_rejected(self) -> None:
        server = {
            "transport": "local",
            "command": "tool",
            "args": ["${MODE}"],
            "clientValues": {"MODE": {"codex": "codex"}},
        }

        with self.assertRaisesRegex(ConfigError, "missing client value"):
            server_for_client(server, "cursor")

    def test_rules_render_from_one_lean_source_with_cursor_metadata(self) -> None:
        outputs = expected_rule_outputs()
        source = next(
            content
            for path, content in outputs.items()
            if path.name == "AGENTS.md"
        )

        self.assertLess(len(source.splitlines()), 130)
        cursor = next(content for path, content in outputs.items() if path.suffix == ".mdc")
        self.assertTrue(cursor.startswith("---\n"))
        self.assertIn("alwaysApply: true", cursor)

    def test_rule_render_check_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_template_tree(Path(temporary))
            output = root / "rulesets/core/claude/CLAUDE.md"
            output.write_text("drift\n", encoding="utf-8")

            self.assertIn(output, render_rules(root, check=True))
            render_rules(root)
            self.assertEqual(render_rules(root, check=True), [])


if __name__ == "__main__":
    unittest.main()
