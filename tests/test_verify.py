from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_console.verify import doctor, verify_templates
from tests.helpers import copy_template_tree, enable_test_profiles, write_json


class TemplateVerificationTests(unittest.TestCase):
    def test_current_templates_pass(self) -> None:
        result = verify_templates()

        self.assertEqual(result.failures, 0, result.payload())

    def test_machine_path_is_detected_outside_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_template_tree(Path(temporary))
            target = root / "mcp/extra.txt"
            target.write_text("/Users/alice/private/tool\n", encoding="utf-8")

            result = verify_templates(root)

            self.assertTrue(
                any(
                    check.status == "fail"
                    and "machine-specific path" in check.message
                    and "mcp/extra.txt" in check.message
                    for check in result.checks
                ),
                result.payload(),
            )

    def test_doctor_reports_effective_additive_mcp_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_template_tree(Path(temporary) / "console")
            enable_test_profiles(root)
            repo = Path(temporary) / "repo"
            repo.mkdir()
            write_json(
                root / "registry/repos.json",
                {
                    "defaults": {"ruleset": "core", "mcpProfiles": []},
                    "repos": [
                        {
                            "name": "fixture",
                            "mcpProfiles": ["work", "ops"],
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
                    and "overrides=ops,work" in check.message
                    and "effective servers=context7,chrome-devtools,datadog,atlassian,circleci,github"
                    in check.message
                    for check in result.checks
                ),
                result.payload(),
            )


if __name__ == "__main__":
    unittest.main()
