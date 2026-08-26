from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_console.config import ConfigError
from ai_console.plugins import load_plugin_registry, opencode_plugin_config
from tests.helpers import copy_template_tree, write_json


class PluginRegistryTests(unittest.TestCase):
    def test_goal_uses_native_clients_and_one_pinned_opencode_plugin(self) -> None:
        registry = load_plugin_registry()
        self.assertEqual(
            registry["policy"]["precedence"],
            ["native", "plugin", "mcp", "cli"],
        )
        self.assertEqual(
            registry["mcpOwnership"]["cursor"],
            {"context7": "context7-plugin"},
        )
        self.assertEqual(
            [item["name"] for item in registry["selected"]["claude"]],
            ["typescript-lsp"],
        )
        goal = registry["capabilities"]["goal"]

        for client in ("codex", "claude", "cursor"):
            self.assertEqual(goal["implementations"][client]["kind"], "native")
            self.assertEqual(goal["implementations"][client]["command"], "/goal")

        opencode = opencode_plugin_config()
        self.assertEqual(
            opencode["plugin"],
            [["opencode-goal-plugin@0.8.2", {"persistState": False}]],
        )
        self.assertEqual(opencode["command"]["goal"]["template"], "$ARGUMENTS")

    def test_registry_rejects_repository_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_template_tree(Path(temporary))
            path = root / "config/plugins.json"
            registry = load_plugin_registry(root)
            registry["capabilities"]["goal"]["implementations"]["opencode"][
                "options"
            ]["persistState"] = True
            write_json(path, registry)

            with self.assertRaisesRegex(ConfigError, "disable repository persistence"):
                load_plugin_registry(root)


if __name__ == "__main__":
    unittest.main()
