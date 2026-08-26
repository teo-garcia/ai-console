from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from ai_console.config import ConfigError
from ai_console.ops import (
    Runner,
    apply_global,
    apply_repos,
    backup_global,
    merge_claude_config,
    merge_claude_settings,
    merge_codex_config,
    merge_hook_config,
    restore_backup,
)
from tests.helpers import PROJECT_ROOT, copy_template_tree, make_registry


class RunnerTests(unittest.TestCase):
    def test_dry_run_does_not_mutate_filesystem(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "nested/destination"
            source.write_text("source", encoding="utf-8")

            runner = Runner(dry_run=True)
            runner.link(source, destination)
            runner.write(root / "other/file", "content")

            self.assertFalse(destination.exists())
            self.assertFalse((root / "other").exists())
            self.assertTrue(any(message.startswith("would") for message in runner.messages))

    def test_force_never_replaces_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "destination"
            source.write_text("source", encoding="utf-8")
            destination.mkdir()

            with self.assertRaisesRegex(ConfigError, "refusing to replace directory"):
                Runner(force=True).link(source, destination)

    def test_write_does_not_follow_symlink_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            link = root / "link"
            source.write_text("user-owned\n", encoding="utf-8")
            link.symlink_to(source)

            Runner().write(link, "managed\n")

            self.assertEqual(source.read_text(encoding="utf-8"), "user-owned\n")
            self.assertTrue(link.is_symlink())


class MergeTests(unittest.TestCase):
    def test_codex_merge_replaces_only_managed_server_tables(self) -> None:
        existing = """model = \"custom\"

[mcp_servers.context7]
url = \"stale\"

[mcp_servers.context7.env]
TOKEN = \"stale\"

[mcp_servers.private]
command = \"private-tool\"

[features]
flag = true
"""
        baseline = """## Managed by ai-console

[mcp_servers.context7]
url = \"https://example.test\"
"""

        merged = merge_codex_config(existing, {"context7"}, baseline)

        self.assertIn('model = "custom"', merged)
        self.assertIn("[mcp_servers.private]", merged)
        self.assertIn("[features]", merged)
        self.assertNotIn('TOKEN = "stale"', merged)
        self.assertEqual(merged.count("[mcp_servers.context7]"), 1)

    def test_codex_merge_is_idempotent_and_removes_legacy_markers(self) -> None:
        baseline = """## Managed by ai-console: lean

[mcp_servers.context7]
url = \"https://example.test\"
"""
        existing = """model = \"custom\"

## Codex MCP servers

## Managed by ai-console: stale

[mcp_servers.context7]
url = \"stale\"
"""

        first = merge_codex_config(existing, {"context7"}, baseline)
        second = merge_codex_config(first, {"context7"}, baseline)

        self.assertEqual(first, second)
        self.assertNotIn("## Codex MCP servers", first)
        self.assertEqual(first.count("## Managed by ai-console"), 1)

    def test_claude_merge_preserves_unmanaged_config(self) -> None:
        existing = {
            "theme": "dark",
            "mcpServers": {
                "context7": {"url": "stale"},
                "private": {"command": "private-tool"},
            },
        }
        baseline = {"mcpServers": {"context7": {"url": "fresh"}}}

        merged = merge_claude_config(existing, {"context7"}, baseline)

        self.assertEqual(merged["theme"], "dark")
        self.assertEqual(merged["mcpServers"]["private"]["command"], "private-tool")
        self.assertEqual(merged["mcpServers"]["context7"]["url"], "fresh")

    def test_hook_merge_preserves_other_integrations_and_replaces_ours(self) -> None:
        existing = {
            "version": 1,
            "hooks": {
                "sessionStart": [
                    {"command": "herdr-agent-state.sh"},
                    {"command": "old-ai-console-lifecycle brief cursor"},
                ]
            },
        }
        baseline = {
            "version": 1,
            "hooks": {
                "sessionStart": [
                    {"command": "$HOME/.ai-console/bin/ai-console-lifecycle brief cursor"}
                ],
                "sessionEnd": [
                    {"command": "$HOME/.ai-console/bin/ai-console-lifecycle capture cursor"}
                ],
            },
        }

        merged = merge_hook_config(existing, baseline)

        starts = merged["hooks"]["sessionStart"]
        self.assertEqual(len(starts), 2)
        self.assertEqual(starts[0]["command"], "herdr-agent-state.sh")
        self.assertIn("$HOME/.ai-console", starts[1]["command"])
        self.assertEqual(len(merged["hooks"]["sessionEnd"]), 1)

    def test_claude_settings_merge_adds_safe_default_and_preserves_user_rules(self) -> None:
        existing = {
            "theme": "dark",
            "permissions": {"allow": ["Bash(git status *)"]},
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"command": "ai-console-lifecycle brief claude"}]}
                ]
            },
        }
        baseline = {
            "permissions": {
                "defaultMode": "auto",
                "ask": ["Bash(git push *)"],
                "deny": ["Read(.env)"],
            },
            "hooks": {"SessionStart": [], "Stop": [], "SessionEnd": []},
        }

        merged = merge_claude_settings(existing, baseline)

        self.assertEqual(merged["theme"], "dark")
        self.assertEqual(merged["permissions"]["defaultMode"], "auto")
        self.assertEqual(merged["permissions"]["allow"], ["Bash(git status *)"])
        self.assertEqual(merged["permissions"]["ask"], ["Bash(git push *)"])
        self.assertEqual(merged["permissions"]["deny"], ["Read(.env)"])
        self.assertEqual(merged["hooks"]["SessionStart"], [])


class RepoApplyTests(unittest.TestCase):
    def test_profile_is_linked_for_all_clients(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = copy_template_tree(temporary_root / "console")
            repo = temporary_root / "repo"
            repo.mkdir()
            (repo / ".claude").mkdir()
            legacy_rules = repo / ".claude/rules"
            legacy_rules.symlink_to(root / "rulesets/core/claude/rules")
            registry, local = make_registry(temporary_root, repo, "semantic")

            apply_repos(root, registry_path=registry, local_path=local)

            expected = {
                repo / ".codex/config.toml": root / "mcp/profiles/semantic/codex.config.toml",
                repo / ".cursor/mcp.json": root / "mcp/profiles/semantic/cursor.mcp.json",
                repo / ".mcp.json": root / "mcp/profiles/semantic/claude.mcp.json",
                repo / "opencode.jsonc": root / "mcp/profiles/semantic/opencode.jsonc",
            }
            for destination, source in expected.items():
                self.assertTrue(destination.is_symlink(), destination)
                self.assertEqual(Path(os.readlink(destination)), source)
            self.assertFalse(legacy_rules.is_symlink())

    def test_additive_profiles_render_and_link_composed_configs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = copy_template_tree(temporary_root / "console")
            repo = temporary_root / "repo"
            repo.mkdir()
            registry, local = make_registry(
                temporary_root, repo, ["semantic", "browser"]
            )

            apply_repos(root, registry_path=registry, local_path=local)

            codex_source = (
                root / "mcp/composed/browser+semantic/codex.config.toml"
            )
            self.assertEqual(
                Path(os.readlink(repo / ".codex/config.toml")), codex_source
            )
            content = codex_source.read_text(encoding="utf-8")
            self.assertIn("[mcp_servers.chrome-devtools]", content)
            self.assertIn("[mcp_servers.serena]", content)

            for destination in (
                repo / ".cursor/mcp.json",
                repo / ".mcp.json",
                repo / "opencode.jsonc",
            ):
                self.assertTrue(destination.is_symlink(), destination)

    def test_additive_profile_dry_run_does_not_write_composed_configs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = copy_template_tree(temporary_root / "console")
            repo = temporary_root / "repo"
            repo.mkdir()
            registry, local = make_registry(
                temporary_root, repo, ["browser", "semantic"]
            )

            runner = apply_repos(
                root,
                dry_run=True,
                registry_path=registry,
                local_path=local,
            )

            self.assertFalse((root / "mcp/composed").exists())
            self.assertFalse((repo / ".codex/config.toml").exists())
            self.assertTrue(
                any("would link" in message for message in runner.messages)
            )


class GlobalApplyTests(unittest.TestCase):
    def test_global_apply_preserves_unmanaged_hooks_and_installs_native_layers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / ".codex").mkdir()
            (home / ".cursor").mkdir()
            (home / ".claude").mkdir()
            (home / ".codex/config.toml").write_text(
                '[mcp_servers.private]\ncommand = "private"\n', encoding="utf-8"
            )
            (home / ".claude.json").write_text(
                json.dumps({"theme": "dark", "mcpServers": {"private": {"command": "x"}}}),
                encoding="utf-8",
            )
            (home / ".codex/hooks.json").write_text(
                json.dumps({"hooks": {"SessionStart": [{"hooks": [{"command": "herdr"}]}]}}),
                encoding="utf-8",
            )
            (home / ".cursor/hooks.json").write_text(
                json.dumps({"version": 1, "hooks": {"sessionStart": [{"command": "herdr"}]}}),
                encoding="utf-8",
            )
            (home / ".claude/settings.json").write_text(
                json.dumps({"theme": "dark"}), encoding="utf-8"
            )
            retired_launcher = home / ".ai-console/bin/ai-console-lifecycle"
            retired_launcher.parent.mkdir(parents=True)
            retired_launcher.symlink_to(PROJECT_ROOT / "scripts/ai-console-lifecycle")
            retired_plugin = home / ".config/opencode/plugins/ai-console-lifecycle.js"
            retired_plugin.parent.mkdir(parents=True)
            retired_plugin.symlink_to(
                PROJECT_ROOT / "hooks/opencode/ai-console-lifecycle.js"
            )

            apply_global(PROJECT_ROOT, home)

            codex_config = (home / ".codex/config.toml").read_text(encoding="utf-8")
            codex_hooks = json.loads((home / ".codex/hooks.json").read_text(encoding="utf-8"))
            cursor_hooks = json.loads((home / ".cursor/hooks.json").read_text(encoding="utf-8"))
            claude_settings = json.loads(
                (home / ".claude/settings.json").read_text(encoding="utf-8")
            )

            self.assertIn("[mcp_servers.private]", codex_config)
            self.assertTrue(
                any("herdr" in json.dumps(item) for item in codex_hooks["hooks"]["SessionStart"])
            )
            self.assertTrue(
                any("herdr" in json.dumps(item) for item in cursor_hooks["hooks"]["sessionStart"])
            )
            self.assertEqual(claude_settings["theme"], "dark")
            self.assertEqual(claude_settings["permissions"]["defaultMode"], "auto")
            self.assertIn(
                "Bash(git push *)", claude_settings["permissions"]["ask"]
            )
            self.assertFalse(retired_launcher.exists())
            self.assertFalse(retired_plugin.exists())
            for client_path in (
                home / ".codex/agents/reviewer.toml",
                home / ".cursor/agents/reviewer.md",
                home / ".claude/agents/reviewer.md",
                home / ".config/opencode/agents/reviewer.md",
            ):
                self.assertTrue(client_path.is_symlink(), client_path)


class BackupRestoreTests(unittest.TestCase):
    def test_backup_and_restore_round_trip_file_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = copy_template_tree(temporary_root / "console")
            home = temporary_root / "home"
            home.mkdir()
            codex = home / ".codex"
            codex.mkdir()
            config = codex / "config.toml"
            config.write_text("before\n", encoding="utf-8")
            instructions = codex / "AGENTS.md"
            instructions.symlink_to(PROJECT_ROOT / "rulesets/core/codex/AGENTS.md")

            snapshot = backup_global(root, home)
            config.write_text("after\n", encoding="utf-8")
            instructions.unlink()
            instructions.write_text("replacement\n", encoding="utf-8")
            agents = home / ".codex/agents"
            agents.mkdir()
            (agents / "new.toml").write_text("new\n", encoding="utf-8")

            preview = restore_backup(snapshot.name, root, home=home)
            self.assertEqual(config.read_text(encoding="utf-8"), "after\n")
            self.assertTrue(any(message.startswith("would restore") for message in preview.messages))
            self.assertTrue(any(message.startswith("would remove") for message in preview.messages))

            restore_backup(snapshot.name, root, home=home, dry_run=False, force=True)
            self.assertEqual(config.read_text(encoding="utf-8"), "before\n")
            self.assertTrue(instructions.is_symlink())
            self.assertFalse(agents.exists())
            manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], 1)

    def test_restore_rejects_source_outside_managed_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = copy_template_tree(temporary_root / "console")
            snapshot = root / "backups/test"
            snapshot.mkdir(parents=True)
            (snapshot / "manifest.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": [
                            {
                                "source": str(temporary_root / "unmanaged"),
                                "backup": "codex/config.toml",
                                "exists": False,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "outside managed targets"):
                restore_backup("test", root, home=temporary_root / "home")

    def test_restore_rejects_parent_backup_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = copy_template_tree(temporary_root / "console")
            home = temporary_root / "home"
            snapshot = root / "backups/test"
            snapshot.mkdir(parents=True)
            (snapshot / "manifest.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": [
                            {
                                "source": str(home / ".codex/config.toml"),
                                "backup": "../outside",
                                "exists": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "invalid backup path"):
                restore_backup("test", root, home=home)


if __name__ == "__main__":
    unittest.main()
