from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_console.capabilities import (
    discover_codex_plugins,
    format_capability_report,
    load_capability_registry,
    resolve_capabilities,
)
from ai_console.config import ConfigError
from tests.helpers import copy_template_tree, write_json


class CapabilityRegistryTests(unittest.TestCase):
    def test_registry_is_valid_and_references_canonical_mcp_policy(self) -> None:
        registry = load_capability_registry()

        self.assertEqual(registry["version"], 1)
        self.assertIn("browser-testing", registry["capabilities"])
        self.assertIn("github-workflow", registry["capabilities"])

    def test_registry_rejects_mcp_approval_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_template_tree(Path(temporary))
            path = root / "config/capabilities.json"
            registry = load_capability_registry(root)
            registry["capabilities"]["library-docs"]["implementations"][0][
                "approval"
            ] = "prompt"
            write_json(path, registry)

            with self.assertRaisesRegex(ConfigError, "approval does not match"):
                load_capability_registry(root)


class CapabilityResolutionTests(unittest.TestCase):
    def _install_plugin(self, home: Path, name: str, version: str = "1.0.0") -> None:
        write_json(
            home
            / f".codex/plugins/cache/test/{name}/{version}/.codex-plugin/plugin.json",
            {"name": name, "version": version},
        )

    def _enable_plugins(self, home: Path, *names: str) -> None:
        config = home / ".codex/config.toml"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(
            "\n".join(
                f'[plugins."{name}@test"]\nenabled = true' for name in names
            )
            + "\n",
            encoding="utf-8",
        )

    def test_codex_clients_prefer_enabled_lazy_plugins_without_claiming_session(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            self._install_plugin(home, "browser", "2.0.0")
            self._install_plugin(home, "chrome")
            self._install_plugin(home, "github")
            self._install_plugin(home, "computer-use")
            self._install_plugin(home, "documents")
            self._enable_plugins(home, "browser", "chrome", "github", "computer-use")

            for client in ("codex-desktop", "codex-cli"):
                with self.subTest(client=client):
                    payload = resolve_capabilities(client=client, home=home)

                    by_name = {
                        item["name"]: item for item in payload["capabilities"]
                    }
                    browser = by_name["browser-testing"]
                    self.assertEqual(browser["preferred"], "browser-plugin")
                    self.assertEqual(
                        browser["implementations"][0]["state"], "enabled"
                    )
                    self.assertIs(browser["implementations"][0]["enabled"], True)
                    self.assertIsNone(browser["implementations"][0]["usableNow"])
                    self.assertEqual(
                        browser["implementations"][0]["session"], "unknown"
                    )
                    self.assertEqual(
                        by_name["observability"]["implementations"][0]["state"],
                        "available-profile",
                    )
                    self.assertEqual(
                        by_name["desktop-control"]["preferred"],
                        "computer-use-plugin",
                    )
                    self.assertEqual(
                        payload["discoveredCodexPlugins"]["browser"]["versions"],
                        ["2.0.0"],
                    )
                    self.assertIs(
                        payload["discoveredCodexPlugins"]["browser"]["enabled"],
                        True,
                    )
                    self.assertIn("documents", payload["unmappedCodexPlugins"])

    def test_cli_compatibility_profile_preview_does_not_change_ambient_mcp(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)

            payload = resolve_capabilities(
                client="codex-cli",
                additional_profiles=("browser", "semantic"),
                home=home,
            )

            self.assertEqual(payload["profiles"], [])
            self.assertEqual(payload["previewProfiles"], ["browser", "semantic"])
            self.assertEqual(
                payload["effectiveMcpServers"],
                ["context7"],
            )
            self.assertEqual(
                payload["previewMcpServers"],
                ["context7", "chrome-devtools", "serena"],
            )
            by_name = {item["name"]: item for item in payload["capabilities"]}
            self.assertEqual(
                by_name["browser-testing"]["implementations"][1]["state"],
                "planned-profile",
            )
            self.assertIsNone(by_name["browser-testing"]["preferred"])
            self.assertEqual(
                by_name["browser-testing"]["previewPreferred"],
                "chrome-devtools",
            )
            self.assertEqual(by_name["code-navigation"]["preferred"], "ripgrep")

    def test_disabled_plugin_is_not_selected_as_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            self._install_plugin(home, "browser")
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                '[plugins."browser@test"]\nenabled = false\n', encoding="utf-8"
            )

            payload = resolve_capabilities(home=home)

            browser = next(
                item
                for item in payload["capabilities"]
                if item["name"] == "browser-testing"
            )
            self.assertIsNone(browser["preferred"])
            self.assertEqual(browser["implementations"][0]["state"], "disabled")
            self.assertIs(browser["implementations"][0]["enabled"], False)
            self.assertEqual(
                browser["implementations"][1]["state"], "available-profile"
            )

    def test_unknown_temporary_profile_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigError, "unknown temporary MCP profiles"):
            resolve_capabilities(additional_profiles=("everything",))

    def test_plugin_discovery_ignores_invalid_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            invalid = (
                home
                / ".codex/plugins/cache/test/broken/1/.codex-plugin/plugin.json"
            )
            invalid.parent.mkdir(parents=True)
            invalid.write_text("not json", encoding="utf-8")

            self.assertEqual(discover_codex_plugins(home), {})

    def test_human_report_exposes_fallback_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload = resolve_capabilities(
                client="codex-cli", home=Path(temporary)
            )

            report = format_capability_report(payload)

            self.assertIn("browser-testing", report)
            self.assertIn("chrome-devtools: available-profile", report)
            self.assertIn(
                "browser-testing [interactive/lazy] preferred=unavailable", report
            )

    @patch("ai_console.capabilities.socket.create_connection")
    def test_live_check_reports_remote_socket_reachability(
        self, create_connection: MagicMock
    ) -> None:
        create_connection.return_value.__enter__.return_value = object()

        payload = resolve_capabilities(
            client="codex-cli", home=Path("/nonexistent"), live=True
        )

        docs = next(
            item for item in payload["capabilities"] if item["name"] == "library-docs"
        )
        self.assertEqual(
            docs["implementations"][0]["reachable"], "reachable"
        )
        self.assertEqual(create_connection.call_count, 1)


if __name__ == "__main__":
    unittest.main()
