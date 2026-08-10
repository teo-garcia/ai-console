from __future__ import annotations

import unittest

from ai_console.policy import TASK_ROUTES, route_policy


class ModelPolicyTests(unittest.TestCase):
    def test_every_task_class_has_a_route(self) -> None:
        for task in TASK_ROUTES:
            route = route_policy(task, "medium")
            self.assertIn("qualityTier", route)
            self.assertIn("reasoning", route)
            self.assertNotIn("model", route)

    def test_high_risk_overrides_normal_task_route(self) -> None:
        route = route_policy("feature", "high")

        self.assertEqual(route["route"], "highRisk")
        self.assertTrue(route["humanCheckpoint"])


if __name__ == "__main__":
    unittest.main()
