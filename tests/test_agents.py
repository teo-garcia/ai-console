from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from tests.helpers import PROJECT_ROOT


class AgentDefinitionTests(unittest.TestCase):
    def test_codex_agents_are_read_only_and_complete(self) -> None:
        for path in (PROJECT_ROOT / "agents/codex").glob("*.toml"):
            payload = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(payload.get("name"), path)
            self.assertTrue(payload.get("description"), path)
            self.assertTrue(payload.get("developer_instructions"), path)
            self.assertEqual(payload.get("sandbox_mode"), "read-only", path)
            self.assertNotIn("model", payload, path)

    def test_markdown_agents_have_required_frontmatter(self) -> None:
        for client in ("claude", "cursor", "opencode"):
            for path in (PROJECT_ROOT / "agents" / client).glob("*.md"):
                content = path.read_text(encoding="utf-8")
                self.assertTrue(content.startswith("---\n"), path)
                frontmatter = content.split("---", 2)[1]
                self.assertIn("description:", frontmatter, path)
                if client != "opencode":
                    self.assertIn("name:", frontmatter, path)
                else:
                    self.assertIn("mode: subagent", frontmatter, path)
                    self.assertIn("edit: deny", frontmatter, path)

    def test_every_client_has_same_logical_agent_set(self) -> None:
        names: dict[str, set[str]] = {}
        for client in ("codex", "claude", "cursor", "opencode"):
            names[client] = {
                path.stem for path in (PROJECT_ROOT / "agents" / client).glob("*") if path.is_file()
            }

        self.assertTrue(all(value == {"planner", "reviewer"} for value in names.values()))


if __name__ == "__main__":
    unittest.main()
