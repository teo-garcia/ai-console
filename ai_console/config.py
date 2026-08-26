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
    mcp_profiles: tuple[str, ...]


def _valid_mcp_profiles(root: Path) -> tuple[str, ...]:
    canonical = load_json(root / "mcp/canonical.json")
    profiles = canonical.get("profiles")
    if not isinstance(profiles, dict) or not all(
        isinstance(name, str) and isinstance(value, dict)
        for name, value in profiles.items()
    ):
        raise ConfigError("canonical profiles must be an object")
    return tuple(profiles)


def _profile_selection(
    value: dict[str, Any],
    fallback: tuple[str, ...],
    valid_profiles: tuple[str, ...],
    context: str,
) -> tuple[str, ...]:
    has_plural = "mcpProfiles" in value
    has_legacy = "mcpProfile" in value
    if has_plural and has_legacy:
        raise ConfigError(f"{context} cannot define both mcpProfiles and mcpProfile")
    if not has_plural and not has_legacy:
        return fallback

    raw = value["mcpProfiles"] if has_plural else value["mcpProfile"]
    if has_plural:
        if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
            raise ConfigError(f"invalid mcpProfiles for {context}; expected a string array")
        selected = raw
    else:
        if not isinstance(raw, str):
            raise ConfigError(f"invalid mcpProfile for {context}; expected a string")
        selected = [] if raw == "lean" else [raw]

    if "lean" in selected:
        raise ConfigError(f"invalid mcpProfiles for {context}; use [] instead of 'lean'")
    if len(selected) != len(set(selected)):
        raise ConfigError(f"duplicate mcpProfiles for {context}")
    unknown = sorted(set(selected) - set(valid_profiles))
    if unknown:
        key = "mcpProfiles" if has_plural else "mcpProfile"
        raise ConfigError(
            f"invalid {key} {unknown!r} for {context}; "
            f"expected values from {', '.join(valid_profiles)}"
        )

    requested = set(selected)
    return tuple(name for name in valid_profiles if name in requested)


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

    valid_profiles = _valid_mcp_profiles(root)
    default_profiles = _profile_selection(
        defaults, (), valid_profiles, "registry defaults"
    )
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
        profiles = _profile_selection(raw, default_profiles, valid_profiles, repr(name))
        if not isinstance(ruleset, str):
            raise ConfigError(f"invalid ruleset for {name!r}")
        entries.append(RepoEntry(name, expand_path(bound_path), ruleset, profiles))
    return entries
