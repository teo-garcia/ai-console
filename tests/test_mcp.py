from __future__ import annotations

import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from ai_console.config import ConfigError
from ai_console.mcp import (
    CLIENTS,
    effective_server_names,
    expected_outputs,
    render_all,
    server_for_client,
)
from ai_console.rules import expected_rule_outputs, render_rules
from tests.helpers import copy_template_tree


class McpRenderingTests(unittest.TestCase):
    def test_global_outputs_parse_and_expose_the_capability_baseline(self) -> None:
        root = Path(__file__).resolve().parent.parent
        outputs = expected_outputs(root)

        global_outputs = [path for path in outputs if "profiles" not in path.parts]
        self.assertEqual(len(global_outputs), len(CLIENTS))
        for path, content in outputs.items():
            self.assertNotIn("${", content, path)
            if path.suffix == ".toml":
                tomllib.loads(content)
            else:
                json.loads(content)

        codex = outputs[root / "mcp/codex.config.toml"]
        self.assertIn("[mcp_servers.context7]", codex)
        self.assertIn("[mcp_servers.chrome-devtools]", codex)
        self.assertNotIn("[mcp_servers.atlassian]", codex)
        self.assertNotIn("[mcp_servers.github]", codex)
        self.assertNotIn("GITHUB_PAT_TOKEN", codex)

        claude = json.loads(outputs[root / "mcp/claude.mcp.json"])
        self.assertEqual(
            list(claude["mcpServers"]),
            ["context7", "chrome-devtools"],
        )
        cursor = json.loads(outputs[root / "mcp/cursor.mcp.json"])
        self.assertEqual(
            list(cursor["mcpServers"]),
            ["context7", "chrome-devtools"],
        )

        opencode = json.loads(outputs[root / "mcp/opencode.jsonc"])
        self.assertEqual(
            opencode["plugin"],
            [["opencode-goal-plugin@0.8.2", {"persistState": False}]],
        )
        self.assertIn("goal", opencode["command"])
        self.assertEqual(opencode["permission"]["bash"]["*"], "allow")
        self.assertEqual(opencode["permission"]["bash"]["git push*"], "ask")
        self.assertEqual(
            set(opencode["mcp"]),
            {"context7", "chrome-devtools"},
        )

        work_claude = json.loads(outputs[root / "mcp/profiles/work/claude.mcp.json"])
        self.assertEqual(
            list(work_claude["mcpServers"]), ["datadog", "atlassian", "circleci"]
        )
        work_codex = outputs[root / "mcp/profiles/work/codex.config.toml"]
        self.assertIn("[mcp_servers.atlassian]", work_codex)

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

    def test_portable_templates_keep_fallbacks_without_runtime_plugin_evidence(self) -> None:
        root = Path(__file__).resolve().parent.parent
        personal = ("context7", "chrome-devtools")
        with_work = (*personal, "datadog", "atlassian", "circleci")

        self.assertEqual(effective_server_names(root, ()), personal)
        self.assertEqual(effective_server_names(root, ("work",)), with_work)
        for client in ("codex", "claude", "cursor"):
            self.assertEqual(effective_server_names(root, (), client=client), personal)
            self.assertEqual(
                effective_server_names(root, ("work",), client=client), with_work
            )

    def test_runtime_plugin_evidence_suppresses_only_proven_owners(self) -> None:
        root = Path(__file__).resolve().parent.parent

        self.assertEqual(
            effective_server_names(
                root,
                ("work",),
                client="cursor",
                enabled_plugins={"context7-plugin", "devtools-for-agents"},
            ),
            ("datadog", "atlassian", "circleci"),
        )
        self.assertEqual(
            effective_server_names(
                root,
                ("work",),
                client="cursor",
                enabled_plugins={
                    "context7-plugin",
                    "devtools-for-agents",
                    "datadog",
                    "atlassian",
                    "circleci",
                },
            ),
            (),
        )
        self.assertEqual(
            effective_server_names(
                root,
                ("work",),
                client="claude",
                enabled_plugins={"context7", "chrome-devtools-mcp"},
            ),
            ("datadog", "atlassian", "circleci"),
        )

    def test_rules_render_from_one_source_with_cursor_metadata(self) -> None:
        outputs = expected_rule_outputs()
        source = next(
            content for path, content in outputs.items() if path.name == "AGENTS.md"
        )

        self.assertLess(len(source.splitlines()), 60)
        self.assertIn("Do not agree merely to be agreeable", source)
        self.assertIn("Do not manufacture objections", source)
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
