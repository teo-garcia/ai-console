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
    profile_config_path,
    render_all,
    render_profile_config,
    server_for_client,
)
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

        codex = outputs[Path(__file__).resolve().parent.parent / "mcp/codex.config.toml"]
        self.assertIn('default_tools_approval_mode = "auto"', codex)
        cursor = json.loads(
            outputs[Path(__file__).resolve().parent.parent / "mcp/cursor.mcp.json"]
        )
        self.assertNotIn("context7", cursor["mcpServers"])
        opencode = json.loads(
            outputs[Path(__file__).resolve().parent.parent / "mcp/opencode.jsonc"]
        )
        self.assertEqual(
            opencode["plugin"],
            [["opencode-goal-plugin@0.8.2", {"persistState": False}]],
        )
        self.assertIn("goal", opencode["command"])
        browser = outputs[
            Path(__file__).resolve().parent.parent
            / "mcp/profiles/browser/codex.config.toml"
        ]
        self.assertIn('default_tools_approval_mode = "writes"', browser)

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

    def test_serena_profile_uses_central_cache_without_repo_data(self) -> None:
        root = Path(__file__).resolve().parent.parent
        outputs = expected_outputs(root)

        for client, filename in {
            "codex": "codex.config.toml",
            "claude": "claude.mcp.json",
            "cursor": "cursor.mcp.json",
            "opencode": "opencode.jsonc",
        }.items():
            content = outputs[root / "mcp/profiles/semantic" / filename]
            self.assertIn("SERENA_HOME", content, client)
            self.assertIn("project_serena_folder_location", content, client)
            self.assertIn("--enable-web-dashboard false", content, client)
            self.assertNotIn('$projectDir/.serena', content, client)

    def test_additive_profile_render_unions_servers_without_global_baseline(self) -> None:
        content = render_profile_config(
            Path(__file__).resolve().parent.parent,
            ("browser", "semantic"),
            "codex",
        )

        self.assertIn("[mcp_servers.chrome-devtools]", content)
        self.assertIn("[mcp_servers.serena]", content)
        self.assertNotIn("[mcp_servers.context7]", content)

        opencode = json.loads(
            render_profile_config(
                Path(__file__).resolve().parent.parent,
                ("browser", "semantic"),
                "opencode",
            )
        )
        self.assertNotIn("plugin", opencode)
        self.assertNotIn("command", opencode)

    def test_effective_servers_are_lean_and_profile_compatible(self) -> None:
        root = Path(__file__).resolve().parent.parent

        servers = effective_server_names(root, ("browser", "semantic"))

        self.assertEqual(
            servers,
            (
                "context7",
                "chrome-devtools",
                "serena",
            ),
        )
        self.assertEqual(
            profile_config_path(root, ("browser", "semantic"), "codex"),
            root / "mcp/composed/browser+semantic/codex.config.toml",
        )

    def test_global_catalog_contains_only_the_lean_baseline(self) -> None:
        root = Path(__file__).resolve().parent.parent

        self.assertEqual(
            effective_server_names(root, ()),
            ("context7",),
        )

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
