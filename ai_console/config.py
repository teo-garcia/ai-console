from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent


class ConfigError(ValueError):
    """Raised when tracked or local configuration is invalid."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"missing config: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"expected JSON object in {path}")
    return data


def expand_path(value: str, home: Path | None = None) -> Path:
    active_home = home or Path.home()
    if value == "~":
        return active_home
    if value.startswith("~/"):
        return active_home / value[2:]
    return Path(value)


@dataclass(frozen=True)
class RepoEntry:
    name: str
    path: Path
    ruleset: str
    mcp_profile: str


def load_repo_entries(
    root: Path = ROOT,
    registry_path: Path | None = None,
    local_path: Path | None = None,
) -> list[RepoEntry]:
    selected_registry = registry_path or Path(
        os.environ.get("AI_CONSOLE_REGISTRY", root / "registry/repos.json")
    )
    data = load_json(selected_registry)
    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ConfigError("registry defaults must be an object")

    selected_local = local_path or Path(
        os.environ.get(
            "AI_CONSOLE_REGISTRY_LOCAL", root / "registry/repos.local.json"
        )
    )
    local_paths: dict[str, str] = {}
    if selected_local.exists():
        local_data = load_json(selected_local)
        raw_paths = local_data.get("paths", {})
        if not isinstance(raw_paths, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in raw_paths.items()
        ):
            raise ConfigError(f"paths must be a string map in {selected_local}")
        local_paths = raw_paths

    valid_profiles = {"lean", "browser", "codebase", "memory", "semantic", "ops"}
    entries: list[RepoEntry] = []
    raw_entries = data.get("repos", [])
    if not isinstance(raw_entries, list):
        raise ConfigError("registry repos must be an array")

    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, dict):
            raise ConfigError(f"registry entry {index} must be an object")
        name = raw.get("name")
        legacy_path = raw.get("path")
        if not isinstance(name, str):
            if isinstance(legacy_path, str):
                name = Path(legacy_path).name
            else:
                raise ConfigError(f"registry entry {index} requires a name")
        bound_path = legacy_path if isinstance(legacy_path, str) else local_paths.get(name)
        if not bound_path:
            raise ConfigError(
                f"missing local path binding for repo {name!r}; "
                f"copy registry/repos.local.example.json to {selected_local}"
            )
        ruleset = raw.get("ruleset", defaults.get("ruleset", "core"))
        profile = raw.get("mcpProfile", defaults.get("mcpProfile", "lean"))
        if not isinstance(ruleset, str):
            raise ConfigError(f"invalid ruleset for {name!r}")
        if profile not in valid_profiles:
            raise ConfigError(
                f"invalid mcpProfile {profile!r} for {name!r}; "
                f"expected one of {', '.join(sorted(valid_profiles))}"
            )
        entries.append(RepoEntry(name, expand_path(bound_path), ruleset, profile))
    return entries
