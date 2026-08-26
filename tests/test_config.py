from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_console.config import ConfigError, load_repo_entries
from tests.helpers import copy_template_tree, make_registry, write_json


class RegistryTests(unittest.TestCase):
    def test_resolves_logical_repo_through_local_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_template_tree(Path(temporary))
            repo = root / "repo"
            registry, local = make_registry(root, repo, "semantic")

            entries = load_repo_entries(root, registry, local)

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].name, "fixture")
            self.assertEqual(entries[0].path, repo)
            self.assertEqual(entries[0].mcp_profiles, ("semantic",))

    def test_resolves_additive_profiles_in_canonical_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_template_tree(Path(temporary))
            repo = root / "repo"
            registry, local = make_registry(
                root, repo, ["semantic", "browser"]
            )

            entries = load_repo_entries(root, registry, local)

            self.assertEqual(entries[0].mcp_profiles, ("browser", "semantic"))

    def test_requires_binding_for_logical_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_template_tree(Path(temporary))
            registry = root / "registry.json"
            write_json(registry, {"repos": [{"name": "missing"}]})

            with self.assertRaisesRegex(ConfigError, "missing local path binding"):
                load_repo_entries(root, registry, root / "absent.json")

    def test_accepts_legacy_path_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_template_tree(Path(temporary))
            registry = root / "registry.json"
            repo = root / "legacy"
            write_json(registry, {"repos": [{"path": str(repo)}]})

            entries = load_repo_entries(root, registry, root / "absent.json")

            self.assertEqual(entries[0].name, "legacy")
            self.assertEqual(entries[0].path, repo)

    def test_rejects_unknown_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_template_tree(Path(temporary))
            repo = root / "repo"
            registry, local = make_registry(root, repo, "everything")

            with self.assertRaisesRegex(ConfigError, "invalid mcpProfile"):
                load_repo_entries(root, registry, local)

    def test_rejects_duplicate_additive_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_template_tree(Path(temporary))
            repo = root / "repo"
            registry, local = make_registry(root, repo, ["browser", "browser"])

            with self.assertRaisesRegex(ConfigError, "duplicate mcpProfiles"):
                load_repo_entries(root, registry, local)

    def test_rejects_mixed_legacy_and_additive_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_template_tree(Path(temporary))
            repo = root / "repo"
            registry = root / "registry.json"
            local = root / "registry.local.json"
            write_json(
                registry,
                {
                    "repos": [
                        {
                            "name": "fixture",
                            "mcpProfile": "browser",
                            "mcpProfiles": ["semantic"],
                        }
                    ]
                },
            )
            write_json(local, {"paths": {"fixture": str(repo)}})

            with self.assertRaisesRegex(ConfigError, "cannot define both"):
                load_repo_entries(root, registry, local)


if __name__ == "__main__":
    unittest.main()
