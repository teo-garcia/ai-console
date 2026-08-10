from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_console.config import ConfigError, load_repo_entries
from tests.helpers import make_registry, write_json


class RegistryTests(unittest.TestCase):
    def test_resolves_logical_repo_through_local_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            registry, local = make_registry(root, repo, "semantic")

            entries = load_repo_entries(root, registry, local)

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].name, "fixture")
            self.assertEqual(entries[0].path, repo)
            self.assertEqual(entries[0].mcp_profile, "semantic")

    def test_requires_binding_for_logical_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = root / "registry.json"
            write_json(registry, {"repos": [{"name": "missing"}]})

            with self.assertRaisesRegex(ConfigError, "missing local path binding"):
                load_repo_entries(root, registry, root / "absent.json")

    def test_accepts_legacy_path_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = root / "registry.json"
            repo = root / "legacy"
            write_json(registry, {"repos": [{"path": str(repo)}]})

            entries = load_repo_entries(root, registry, root / "absent.json")

            self.assertEqual(entries[0].name, "legacy")
            self.assertEqual(entries[0].path, repo)

    def test_rejects_unknown_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            registry, local = make_registry(root, repo, "everything")

            with self.assertRaisesRegex(ConfigError, "invalid mcpProfile"):
                load_repo_entries(root, registry, local)


if __name__ == "__main__":
    unittest.main()
