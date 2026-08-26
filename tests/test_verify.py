from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_console.verify import doctor, verify_templates
from tests.helpers import copy_template_tree, write_json


class TemplateVerificationTests(unittest.TestCase):
    def test_current_templates_pass(self) -> None:
        result = verify_templates()

        self.assertEqual(result.failures, 0, result.payload())

    def test_machine_path_is_detected_outside_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_template_tree(Path(temporary))
            target = root / "mcp/profiles/semantic/extra.txt"
            target.write_text("/Users/alice/private/tool\n", encoding="utf-8")

            result = verify_templates(root)

            self.assertTrue(
                any(
                    check.status == "fail"
                    and "machine-specific path" in check.message
                    and "semantic/extra.txt" in check.message
                    for check in result.checks
                ),
                result.payload(),
            )

    def test_doctor_reports_effective_additive_mcp_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_template_tree(Path(temporary) / "console")
            repo = Path(temporary) / "repo"
            repo.mkdir()
            write_json(
                root / "registry/repos.json",
                {
                    "defaults": {"ruleset": "core", "mcpProfiles": []},
                    "repos": [
                        {
                            "name": "fixture",
                            "mcpProfiles": ["semantic", "browser"],
                        }
                    ],
                },
            )
            write_json(
                root / "registry/repos.local.json",
                {"paths": {"fixture": str(repo)}},
            )

            result = doctor(root)

            self.assertTrue(
                any(
                    check.status == "ok"
                    and "overrides=browser,semantic" in check.message
                    and "effective servers=context7,chrome-devtools,serena"
                    in check.message
                    for check in result.checks
                ),
                result.payload(),
            )


if __name__ == "__main__":
    unittest.main()
