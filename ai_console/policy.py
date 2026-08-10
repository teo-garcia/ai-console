from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ConfigError, ROOT, load_json


TASK_ROUTES = {
    "explanation": "triage",
    "research": "exploration",
    "bug": "implementation",
    "feature": "implementation",
    "refactor": "implementation",
    "review": "review",
    "migration": "highRisk",
    "incident": "highRisk",
    "security": "highRisk",
    "architecture": "highRisk",
    "evaluation": "evaluation",
}


def route_policy(task: str, risk: str, root: Path = ROOT) -> dict[str, Any]:
    policy = load_json(root / "config/model-policy.json")
    route_name = "highRisk" if risk == "high" else TASK_ROUTES.get(task)
    if not route_name:
        raise ConfigError(f"unknown task class: {task}")
    routes = policy.get("routes")
    if not isinstance(routes, dict) or not isinstance(routes.get(route_name), dict):
        raise ConfigError(f"model policy is missing route: {route_name}")
    return {
        "task": task,
        "risk": risk,
        "route": route_name,
        **routes[route_name],
        "note": "Resolve the abstract tier to a current model in the active client; do not persist a stale cross-client model ID.",
    }
