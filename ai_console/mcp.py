from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from .config import ConfigError, ROOT, load_json


CLIENTS = ("codex", "claude", "cursor", "opencode")
MCP_APPROVAL_MODES = {"auto", "prompt", "writes", "approve"}
PROFILE_FILENAMES = {
    "codex": "codex.config.toml",
    "claude": "claude.mcp.json",
    "cursor": "cursor.mcp.json",
    "opencode": "opencode.jsonc",
}


def _replace_client_values(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        for key, replacement in replacements.items():
            value = value.replace(f"${{{key}}}", replacement)
        return value
    if isinstance(value, list):
        return [_replace_client_values(item, replacements) for item in value]
    if isinstance(value, dict):
        return {
            key: _replace_client_values(item, replacements)
            for key, item in value.items()
            if key != "clientValues"
        }
    return value


def server_for_client(server: dict[str, Any], client: str) -> dict[str, Any]:
    raw_values = server.get("clientValues", {})
    replacements: dict[str, str] = {}
    if raw_values:
        if not isinstance(raw_values, dict):
            raise ConfigError("clientValues must be an object")
        for key, mapping in raw_values.items():
            if not isinstance(mapping, dict) or not isinstance(mapping.get(client), str):
                raise ConfigError(f"missing client value {key!r} for {client}")
            replacements[key] = mapping[client]
    rendered = _replace_client_values(copy.deepcopy(server), replacements)
    unresolved = re.findall(r"\$\{[A-Z0-9_]+\}", json.dumps(rendered))
    if unresolved:
        raise ConfigError(f"unresolved MCP variables for {client}: {sorted(set(unresolved))}")
    return rendered


def _json_server(server: dict[str, Any]) -> dict[str, Any]:
    if server["transport"] == "remote":
        return {"type": "http", "url": server["url"]}
    result: dict[str, Any] = {
        "command": server["command"],
        "args": server.get("args", []),
    }
    if server.get("env"):
        result["env"] = server["env"]
    return result


def _opencode_server(server: dict[str, Any]) -> dict[str, Any]:
    if server["transport"] == "remote":
        return {"type": "remote", "url": server["url"], "enabled": True}
    result: dict[str, Any] = {
        "type": "local",
        "command": [server["command"], *server.get("args", [])],
        "enabled": True,
    }
    if server.get("env"):
        result["env"] = server["env"]
    return result


def _toml_server(name: str, server: dict[str, Any]) -> str:
    lines = [f"[mcp_servers.{name}]"]
    if server["transport"] == "remote":
        lines.append(f"url = {json.dumps(server['url'])}")
        if server.get("auth"):
            lines.append(f"auth = {json.dumps(server['auth'])}")
    else:
        if server.get("startupTimeoutSec") is not None:
            lines.append(f"startup_timeout_sec = {int(server['startupTimeoutSec'])}")
        lines.append(f"command = {json.dumps(server['command'])}")
        if server.get("env"):
            env_items = ", ".join(
                f"{key} = {json.dumps(value)}" for key, value in server["env"].items()
            )
            lines.append(f"env = {{ {env_items} }}")
        lines.append(f"args = {json.dumps(server.get('args', []))}")
    approval_mode = server.get("approvalMode")
    if approval_mode is not None and approval_mode not in MCP_APPROVAL_MODES:
        raise ConfigError(f"invalid approval mode for MCP server {name!r}")
    if approval_mode:
        lines.append(
            "default_tools_approval_mode = "
            f"{json.dumps(approval_mode)}"
        )
    return "\n".join(lines)


def render_client(
    canonical: dict[str, Any], server_names: list[str], client: str, label: str
) -> str:
    raw_servers = canonical.get("servers")
    if not isinstance(raw_servers, dict):
        raise ConfigError("canonical MCP servers must be an object")
    selected: dict[str, dict[str, Any]] = {}
    for name in server_names:
        raw = raw_servers.get(name)
        if not isinstance(raw, dict):
            raise ConfigError(f"unknown MCP server {name!r}")
        selected[name] = server_for_client(raw, client)

    if client == "codex":
        blocks = [_toml_server(name, server) for name, server in selected.items()]
        return f"## Managed by ai-console: {label}\n\n" + "\n\n".join(blocks) + "\n"
    if client in {"claude", "cursor"}:
        payload = {"mcpServers": {name: _json_server(server) for name, server in selected.items()}}
        return json.dumps(payload, indent=2) + "\n"
    if client == "opencode":
        payload = {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {name: _opencode_server(server) for name, server in selected.items()},
        }
        return json.dumps(payload, indent=2) + "\n"
    raise ConfigError(f"unsupported client: {client}")


def profile_server_names(
    canonical: dict[str, Any], profile_names: tuple[str, ...]
) -> list[str]:
    profiles = canonical.get("profiles")
    if not isinstance(profiles, dict):
        raise ConfigError("canonical profiles must be an object")
    selected: list[str] = []
    for profile_name in profile_names:
        profile = profiles.get(profile_name)
        if not isinstance(profile, dict) or not isinstance(profile.get("servers"), list):
            raise ConfigError(f"profile {profile_name!r} requires servers array")
        for server_name in profile["servers"]:
            if not isinstance(server_name, str):
                raise ConfigError(f"profile {profile_name!r} server names must be strings")
            if server_name not in selected:
                selected.append(server_name)
    return selected


def effective_server_names(
    root: Path, profile_names: tuple[str, ...]
) -> tuple[str, ...]:
    canonical = load_json(root / "mcp/canonical.json")
    global_config = canonical.get("global")
    if not isinstance(global_config, dict) or not isinstance(
        global_config.get("servers"), list
    ):
        raise ConfigError("canonical global.servers must be an array")
    selected: list[str] = []
    for name in [*global_config["servers"], *profile_server_names(canonical, profile_names)]:
        if not isinstance(name, str):
            raise ConfigError("MCP server names must be strings")
        if name not in selected:
            selected.append(name)
    return tuple(selected)


def profile_config_path(root: Path, profile_names: tuple[str, ...], client: str) -> Path:
    try:
        filename = PROFILE_FILENAMES[client]
    except KeyError as exc:
        raise ConfigError(f"unsupported client: {client}") from exc
    if not profile_names:
        raise ConfigError("an empty profile selection has no project MCP config")
    if len(profile_names) == 1:
        return root / "mcp/profiles" / profile_names[0] / filename
    return root / "mcp/composed" / "+".join(profile_names) / filename


def render_profile_config(
    root: Path, profile_names: tuple[str, ...], client: str
) -> str:
    if not profile_names:
        raise ConfigError("cannot render an empty project MCP profile selection")
    canonical = load_json(root / "mcp/canonical.json")
    label = " + ".join(profile_names)
    return render_client(
        canonical,
        profile_server_names(canonical, profile_names),
        client,
        f"{label} MCP profile set",
    )


def expected_outputs(root: Path = ROOT) -> dict[Path, str]:
    canonical = load_json(root / "mcp/canonical.json")
    global_config = canonical.get("global", {})
    if not isinstance(global_config, dict) or not isinstance(
        global_config.get("servers"), list
    ):
        raise ConfigError("canonical global.servers must be an array")

    outputs: dict[Path, str] = {}
    global_paths = {
        "codex": root / "mcp/codex.config.toml",
        "claude": root / "mcp/claude.mcp.json",
        "cursor": root / "mcp/cursor.mcp.json",
        "opencode": root / "mcp/opencode.jsonc",
    }
    for client, path in global_paths.items():
        outputs[path] = render_client(
            canonical, global_config["servers"], client, "lean global MCP baseline"
        )

    profiles = canonical.get("profiles")
    if not isinstance(profiles, dict):
        raise ConfigError("canonical profiles must be an object")
    for profile_name, profile in profiles.items():
        if not isinstance(profile, dict) or not isinstance(profile.get("servers"), list):
            raise ConfigError(f"profile {profile_name!r} requires servers array")
        for client, filename in PROFILE_FILENAMES.items():
            path = root / "mcp/profiles" / profile_name / filename
            outputs[path] = render_client(
                canonical,
                profile["servers"],
                client,
                f"{profile_name} MCP profile",
            )
    return outputs


def render_all(root: Path = ROOT, check: bool = False) -> list[Path]:
    changed: list[Path] = []
    for path, content in expected_outputs(root).items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        changed.append(path)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    return changed
