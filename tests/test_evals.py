from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_console.config import ConfigError
from ai_console.evals import (
    Variant,
    command_for,
    load_corpus,
    ratings_template,
    run_eval,
    score_run,
)
from tests.helpers import PROJECT_ROOT, write_json


class EvalCorpusTests(unittest.TestCase):
    def test_system_behavior_corpus_is_valid(self) -> None:
        corpus = load_corpus(PROJECT_ROOT / "evals/cases.json")

        self.assertGreaterEqual(len(corpus["cases"]), 10)
        self.assertEqual(len({case["id"] for case in corpus["cases"]}), len(corpus["cases"]))

    def test_each_adapter_uses_noninteractive_constrained_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            with patch("ai_console.evals.shutil.which", return_value="/bin/client"):
                commands = {
                    client: command_for(client, workspace, "prompt", workspace / "out")
                    for client in ("codex", "claude", "cursor", "opencode")
                }

        self.assertIn("read-only", commands["codex"])
        self.assertIn("plan", commands["claude"])
        self.assertIn("ask", commands["cursor"])
        self.assertIn("plan", commands["opencode"])
        for command in commands.values():
            self.assertNotIn("--dangerously-skip-permissions", command)
            self.assertNotIn("--auto", command)
            self.assertNotIn("--force", command)

    def test_dry_run_plans_every_variant_case_without_client_execution(self) -> None:
        rules = PROJECT_ROOT / "rulesets/core/codex/AGENTS.md"
        variants = [Variant("a", rules), Variant("b", rules)]
        with patch("ai_console.evals.shutil.which", return_value="/bin/codex"):
            payload = run_eval(
                "codex",
                variants,
                case_ids=["diagnose-without-editing"],
                dry_run=True,
            )

        self.assertEqual(len(payload["results"]), 2)
        self.assertTrue(all(item["status"] == "planned" for item in payload["results"]))


class EvalScoringTests(unittest.TestCase):
    def test_ratings_template_and_score(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_path = root / "run.json"
            write_json(
                run_path,
                {
                    "variants": [{"name": "a"}, {"name": "b"}],
                    "results": [
                        {
                            "variant": "a",
                            "case": "diagnose-without-editing",
                            "attempt": 1,
                            "status": "completed",
                            "durationSeconds": 2.0,
                        },
                        {
                            "variant": "b",
                            "case": "diagnose-without-editing",
                            "attempt": 1,
                            "status": "completed",
                            "durationSeconds": 1.0,
                        },
                    ],
                },
            )
            template = ratings_template(run_path)
            for rating in template["ratings"]:
                value = 3 if rating["variant"] == "a" else 5
                rating["scores"] = {key: value for key in rating["scores"]}
            ratings_path = root / "ratings.json"
            write_json(ratings_path, template)

            scored = score_run(run_path, ratings_path)

            self.assertEqual(scored["summary"]["a"]["meanRubricScore"], 3.0)
            self.assertEqual(scored["summary"]["b"]["meanRubricScore"], 5.0)
            self.assertEqual(scored["summary"]["b"]["meanDurationSeconds"], 1.0)

    def test_incomplete_ratings_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_path = root / "run.json"
            ratings_path = root / "ratings.json"
            write_json(
                run_path,
                {
                    "variants": [{"name": "a"}],
                    "results": [{"variant": "a", "case": "case", "attempt": 1}],
                },
            )
            write_json(
                ratings_path,
                {
                    "ratings": [
                        {
                            "variant": "a",
                            "case": "case",
                            "attempt": 1,
                            "scores": {"criterion": None},
                        }
                    ]
                },
            )

            with self.assertRaisesRegex(ConfigError, "numbers from 1 to 5"):
                score_run(run_path, ratings_path)


if __name__ == "__main__":
    unittest.main()
