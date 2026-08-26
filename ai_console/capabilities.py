from __future__ import annotations

import json
import shutil
import socket
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import ConfigError, ROOT, load_json, load_repo_entries
from .mcp import effective_server_names


CAPABILITY_CLIENTS = (
    "codex-desktop",
    "codex-cli",
    "codex-ide",
    "claude",
    "cursor",
    "opencode",
)
CAPABILITY_KINDS = {"native", "plugin", "mcp", "cli"}
CAPABILITY_KIND_PRIORITY = {
    "native": 0,
    "plugin": 1,
    "mcp": 2,
    "cli": 3,
}
CAPABILITY_RISKS = {"read-only", "interactive", "write", "external-write"}
CAPABILITY_ACTIVATIONS = {"global", "lazy", "repository", "on-demand"}
APPROVAL_MODES = {"auto", "writes", "prompt", "approve"}


def load_capability_registry(root: Path = ROOT) -> dict[str, Any]:
    registry = load_json(root / "config/capabilities.json")
    if registry.get("version") != 1:
        raise ConfigError("capability registry version must be 1")
    clients = registry.get("clients")
    if clients != list(CAPABILITY_CLIENTS):
        raise ConfigError(
            "capability registry clients must match the supported client order"
        )

    canonical = load_json(root / "mcp/canonical.json")
    servers = canonical.get("servers")
    profiles = canonical.get("profiles")
    if not isinstance(servers, dict) or not isinstance(profiles, dict):
        raise ConfigError("canonical MCP servers and profiles must be objects")

    capabilities = registry.get("capabilities")
    if not isinstance(capabilities, dict) or not capabilities:
        raise ConfigError("capability registry requires a capabilities object")
    for capability_name, capability in capabilities.items():
        if not isinstance(capability_name, str) or not isinstance(capability, dict):
            raise ConfigError("capabilities must map names to objects")
        if not isinstance(capability.get("description"), str):
            raise ConfigError(f"capability {capability_name!r} requires description")
        if capability.get("risk") not in CAPABILITY_RISKS:
            raise ConfigError(f"capability {capability_name!r} has invalid risk")
        if capability.get("activation") not in CAPABILITY_ACTIVATIONS:
            raise ConfigError(f"capability {capability_name!r} has invalid activation")
        implementations = capability.get("implementations")
        if not isinstance(implementations, list) or not implementations:
            raise ConfigError(
                f"capability {capability_name!r} requires implementations"
            )
        seen_ids: set[str] = set()
        for implementation in implementations:
            _validate_implementation(
                capability_name, implementation, clients, servers, profiles
            )
            implementation_id = implementation["id"]
            if implementation_id in seen_ids:
                raise ConfigError(
                    f"capability {capability_name!r} has duplicate implementation "
                    f"{implementation_id!r}"
                )
            seen_ids.add(implementation_id)
    return registry


def _validate_implementation(
    capability_name: str,
    implementation: Any,
    clients: list[str],
    servers: dict[str, Any],
    profiles: dict[str, Any],
) -> None:
    if not isinstance(implementation, dict):
        raise ConfigError(
            f"capability {capability_name!r} implementations must be objects"
        )
    implementation_id = implementation.get("id")
    kind = implementation.get("kind")
    supported = implementation.get("clients")
    if not isinstance(implementation_id, str):
        raise ConfigError(f"capability {capability_name!r} implementation requires id")
    if kind not in CAPABILITY_KINDS:
        raise ConfigError(f"implementation {implementation_id!r} has invalid kind")
    if not isinstance(supported, list) or not supported or not all(
        isinstance(client, str) and client in clients for client in supported
    ):
        raise ConfigError(f"implementation {implementation_id!r} has invalid clients")
    if len(supported) != len(set(supported)):
        raise ConfigError(f"implementation {implementation_id!r} repeats a client")
    if implementation.get("approval") not in APPROVAL_MODES:
        raise ConfigError(f"implementation {implementation_id!r} has invalid approval")
    if not isinstance(implementation.get("useWhen"), str):
        raise ConfigError(f"implementation {implementation_id!r} requires useWhen")
    if "requires" in implementation and not isinstance(
        implementation.get("requires"), str
    ):
        raise ConfigError(f"implementation {implementation_id!r} has invalid requires")

    required_key = {
        "plugin": "pluginName",
        "mcp": "mcpServer",
        "cli": "command",
    }.get(kind)
    if required_key and not isinstance(implementation.get(required_key), str):
        raise ConfigError(
            f"implementation {implementation_id!r} requires {required_key}"
        )
    if kind == "mcp":
        server_name = implementation["mcpServer"]
        if server_name not in servers:
            raise ConfigError(
                f"implementation {implementation_id!r} references unknown MCP server"
            )
        profile_name = implementation.get("profile")
        if profile_name is not None:
            profile = profiles.get(profile_name)
            if not isinstance(profile, dict) or server_name not in profile.get(
                "servers", []
            ):
                raise ConfigError(
                    f"implementation {implementation_id!r} has invalid profile mapping"
                )
        server_approval = servers[server_name].get("approvalMode")
        if server_approval != implementation["approval"]:
            raise ConfigError(
                f"implementation {implementation_id!r} approval does not match "
                f"MCP server {server_name!r}"
            )
        server_auth = servers[server_name].get("auth")
        if server_auth != implementation.get("auth"):
            raise ConfigError(
                f"implementation {implementation_id!r} auth does not match "
                f"MCP server {server_name!r}"
            )
    supersedes_mcp = implementation.get("supersedesMcp")
    if supersedes_mcp is not None:
        if kind != "plugin" or not isinstance(supersedes_mcp, str):
            raise ConfigError(
                f"implementation {implementation_id!r} has invalid MCP supersession"
            )
        if supersedes_mcp not in servers:
            raise ConfigError(
                f"implementation {implementation_id!r} supersedes unknown MCP server"
            )
        replaced = servers[supersedes_mcp]
        if replaced.get("approvalMode") != implementation["approval"]:
            raise ConfigError(
                f"implementation {implementation_id!r} approval does not match "
                f"superseded MCP server {supersedes_mcp!r}"
            )
        if replaced.get("auth") != implementation.get("auth"):
            raise ConfigError(
                f"implementation {implementation_id!r} auth does not match "
                f"superseded MCP server {supersedes_mcp!r}"
            )


def discover_codex_plugins(home: Path | None = None) -> dict[str, dict[str, Any]]:
    active_home = home or Path.home()
    cache = active_home / ".codex/plugins/cache"
    discovered: dict[str, dict[str, Any]] = {}
    if not cache.is_dir():
        return discovered
    for manifest in sorted(cache.rglob(".codex-plugin/plugin.json")):
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        name = payload.get("name")
        version = payload.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            continue
        current = discovered.setdefault(name, {"versions": [], "sources": []})
        if version not in current["versions"]:
            current["versions"].append(version)
            current["versions"].sort()
        current["sources"].append(str(manifest))
    config_path = active_home / ".codex/config.toml"
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, tomllib.TOMLDecodeError):
        config = {}
    configured_plugins = config.get("plugins")
    if isinstance(configured_plugins, dict):
        for qualified_name, value in configured_plugins.items():
            if not isinstance(qualified_name, str) or not isinstance(value, dict):
                continue
            name = qualified_name.split("@", 1)[0]
            if name in discovered and isinstance(value.get("enabled"), bool):
                discovered[name]["enabled"] = value["enabled"]
    return discovered


def _record_plugin(
    discovered: dict[str, dict[str, Any]],
    name: str,
    source: Path | str,
    *,
    version: str | None = None,
    enabled: bool | None = None,
) -> None:
    current = discovered.setdefault(name, {"versions": [], "sources": []})
    source_value = str(source)
    if source_value not in current["sources"]:
        current["sources"].append(source_value)
    if version and version not in current["versions"]:
        current["versions"].append(version)
        current["versions"].sort()
    if enabled is not None:
        current["enabled"] = enabled


def _manifest_plugins(
    manifests: list[Path], manifest_dir: str
) -> dict[str, dict[str, Any]]:
    discovered: dict[str, dict[str, Any]] = {}
    for manifest in manifests:
        if manifest.parent.name != manifest_dir:
            continue
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        name = payload.get("name")
        version = payload.get("version")
        if not isinstance(name, str):
            continue
        _record_plugin(
            discovered,
            name,
            manifest,
            version=version if isinstance(version, str) else None,
        )
    return discovered


def _configured_plugin_name(value: str) -> str:
    if value.startswith("@") and value.count("@") > 1:
        return value.rsplit("@", 1)[0]
    return value.split("@", 1)[0]


def discover_claude_plugins(home: Path | None = None) -> dict[str, dict[str, Any]]:
    active_home = home or Path.home()
    plugins_root = active_home / ".claude/plugins"
    manifests = (
        sorted(plugins_root.rglob("plugin.json")) if plugins_root.is_dir() else []
    )
    discovered = _manifest_plugins(manifests, ".claude-plugin")
    settings_path = active_home / ".claude/settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        settings = {}
    enabled_plugins = settings.get("enabledPlugins")
    if isinstance(enabled_plugins, dict):
        for qualified_name, enabled in enabled_plugins.items():
            if not isinstance(qualified_name, str) or not isinstance(enabled, bool):
                continue
            name = _configured_plugin_name(qualified_name)
            _record_plugin(discovered, name, settings_path, enabled=enabled)
    return discovered


def discover_cursor_plugins(home: Path | None = None) -> dict[str, dict[str, Any]]:
    active_home = home or Path.home()
    plugins_root = active_home / ".cursor/plugins"
    manifests = (
        sorted(plugins_root.rglob("plugin.json")) if plugins_root.is_dir() else []
    )
    discovered = _manifest_plugins(manifests, ".cursor-plugin")
    for name, metadata in _manifest_plugins(manifests, ".claude-plugin").items():
        for source in metadata["sources"]:
            _record_plugin(
                discovered,
                name,
                source,
                version=metadata["versions"][0] if metadata["versions"] else None,
                enabled=True,
            )
    for manifest in manifests:
        if manifest.parent.name == ".cursor-plugin":
            continue
        try:
            relative = manifest.relative_to(plugins_root)
        except ValueError:
            continue
        if len(relative.parts) not in {2, 3}:
            continue
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        name = payload.get("name")
        version = payload.get("version")
        if isinstance(name, str):
            _record_plugin(
                discovered,
                name,
                manifest,
                version=version if isinstance(version, str) else None,
            )
    return discovered


def discover_opencode_plugins(home: Path | None = None) -> dict[str, dict[str, Any]]:
    active_home = home or Path.home()
    config_root = active_home / ".config/opencode"
    discovered: dict[str, dict[str, Any]] = {}
    plugins_root = config_root / "plugins"
    if plugins_root.is_dir():
        for plugin in sorted(plugins_root.iterdir()):
            if plugin.is_file() and plugin.suffix in {".js", ".ts", ".mjs", ".cjs"}:
                _record_plugin(discovered, plugin.stem, plugin, enabled=True)
    config_path = config_root / "opencode.jsonc"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        config = {}
    configured_plugins = config.get("plugin")
    if isinstance(configured_plugins, list):
        for value in configured_plugins:
            package = value[0] if isinstance(value, list) and value else value
            if isinstance(package, str):
                _record_plugin(
                    discovered,
                    _configured_plugin_name(package),
                    config_path,
                    enabled=True,
                )
    return discovered


def discover_client_plugins(
    client: str, home: Path | None = None
) -> dict[str, dict[str, Any]]:
    if client.startswith("codex-"):
        return discover_codex_plugins(home)
    discoverer = {
        "claude": discover_claude_plugins,
        "cursor": discover_cursor_plugins,
        "opencode": discover_opencode_plugins,
    }[client]
    return discoverer(home)


def _normalize_profiles(
    root: Path, selected: tuple[str, ...], additional: tuple[str, ...]
) -> tuple[str, ...]:
    canonical = load_json(root / "mcp/canonical.json")
    profiles = canonical.get("profiles")
    if not isinstance(profiles, dict):
        raise ConfigError("canonical profiles must be an object")
    unknown = sorted(set(additional) - set(profiles))
    if unknown:
        raise ConfigError(f"unknown temporary MCP profiles: {', '.join(unknown)}")
    requested = set(selected) | set(additional)
    return tuple(name for name in profiles if name in requested)


def _selected_repo_profiles(root: Path, repo_name: str | None) -> tuple[str, ...]:
    if repo_name is None:
        return ()
    matches = [entry for entry in load_repo_entries(root) if entry.name == repo_name]
    if not matches:
        raise ConfigError(f"unknown registered repo {repo_name!r}")
    return matches[0].mcp_profiles


def _socket_reachability(host: str, port: int, timeout: float = 1.0) -> str:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return "reachable"
    except OSError:
        return "unreachable"


def _remote_reachability(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.hostname:
        return "invalid-url"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return _socket_reachability(parsed.hostname, port)


def _mcp_runtime(
    server: dict[str, Any], configured: bool, live: bool
) -> tuple[str, str]:
    if server.get("transport") == "local":
        command = server.get("command")
        if not isinstance(command, str) or shutil.which(command) is None:
            return "missing-prerequisite", "unreachable"
        if not configured or not live:
            return "available", "not-checked"
        env = server.get("env", {})
        port_value = env.get("CHROME_DEBUG_PORT") if isinstance(env, dict) else None
        if isinstance(port_value, str) and port_value.isdigit():
            return "available", _socket_reachability("127.0.0.1", int(port_value))
        return "available", "not-checked"
    url = server.get("url")
    if not configured or not live or not isinstance(url, str):
        return "available", "not-checked"
    return "available", _remote_reachability(url)


def resolve_capabilities(
    root: Path = ROOT,
    *,
    client: str = "codex-desktop",
    repo_name: str | None = None,
    additional_profiles: tuple[str, ...] = (),
    home: Path | None = None,
    live: bool = False,
) -> dict[str, Any]:
    if client not in CAPABILITY_CLIENTS:
        raise ConfigError(f"unsupported capability client {client!r}")
    registry = load_capability_registry(root)
    mcp_client = "codex" if client.startswith("codex-") else client
    base_profiles = _selected_repo_profiles(root, repo_name)
    profiles = _normalize_profiles(root, base_profiles, additional_profiles)
    active_servers = set(
        effective_server_names(root, base_profiles, client=mcp_client)
    )
    preview_servers = set(effective_server_names(root, profiles, client=mcp_client))
    canonical = load_json(root / "mcp/canonical.json")
    servers = canonical["servers"]
    plugins = discover_client_plugins(client, home)
    registered_plugins = {
        implementation["pluginName"]
        for capability in registry["capabilities"].values()
        for implementation in capability["implementations"]
        if implementation["kind"] == "plugin"
        and client in implementation["clients"]
    }
    resolved_capabilities: list[dict[str, Any]] = []

    for capability_name, capability in registry["capabilities"].items():
        resolved_implementations: list[dict[str, Any]] = []
        for implementation in capability["implementations"]:
            if client not in implementation["clients"]:
                continue
            resolved = _resolve_implementation(
                implementation,
                servers,
                active_servers,
                preview_servers,
                plugins,
                live,
            )
            resolved_implementations.append(resolved)
        if not resolved_implementations:
            continue
        preferred = _preferred_implementation(
            resolved_implementations,
            {"available", "enabled", "installed", "configured"},
        )
        preview_preferred = _preferred_implementation(
            resolved_implementations,
            {
                "available",
                "available-on-demand",
                "enabled",
                "installed",
                "configured",
                "planned-profile",
            },
        )
        for implementation in resolved_implementations:
            if (
                preferred is not None
                and implementation["id"] != preferred
                and implementation["state"]
                in {"available", "enabled", "installed", "configured"}
            ):
                implementation["shadowedBy"] = preferred
        duplicate_mcp = sorted(
            {
                implementation["supersedesMcp"]
                for implementation in resolved_implementations
                if implementation.get("supersedesMcp")
                and implementation["state"] == "enabled"
                and any(
                    candidate.get("mcpServer") == implementation["supersedesMcp"]
                    and candidate["state"] == "configured"
                    for candidate in resolved_implementations
                )
            }
        )
        resolved_capabilities.append(
            {
                "name": capability_name,
                "description": capability["description"],
                "risk": capability["risk"],
                "activation": capability["activation"],
                "preferred": preferred,
                "previewPreferred": preview_preferred,
                "duplicateMcpServers": duplicate_mcp,
                "implementations": resolved_implementations,
            }
        )
    return {
        "client": client,
        "repo": repo_name,
        "profiles": list(base_profiles),
        "previewProfiles": list(profiles),
        "temporaryProfiles": list(additional_profiles),
        "effectiveMcpServers": list(
            effective_server_names(root, base_profiles, client=mcp_client)
        ),
        "previewMcpServers": list(
            effective_server_names(root, profiles, client=mcp_client)
        ),
        "capabilities": resolved_capabilities,
        "discoveredPlugins": {
            name: {
                "versions": value["versions"],
                "enabled": value.get("enabled", "unknown"),
                "sources": value["sources"],
            }
            for name, value in sorted(plugins.items())
        },
        "unmappedPlugins": {
            name: {
                "versions": value["versions"],
                "enabled": value.get("enabled", "unknown"),
                "sources": value["sources"],
            }
            for name, value in sorted(plugins.items())
            if name not in registered_plugins
        },
        "liveChecks": live,
        "preferencePolicy": list(CAPABILITY_KIND_PRIORITY),
    }


def _preferred_implementation(
    implementations: list[dict[str, Any]], states: set[str]
) -> str | None:
    candidates = [
        (CAPABILITY_KIND_PRIORITY[implementation["kind"]], index, implementation["id"])
        for index, implementation in enumerate(implementations)
        if implementation["state"] in states
    ]
    return min(candidates)[2] if candidates else None


def _resolve_implementation(
    implementation: dict[str, Any],
    servers: dict[str, Any],
    active_servers: set[str],
    preview_servers: set[str],
    plugins: dict[str, dict[str, Any]],
    live: bool,
) -> dict[str, Any]:
    kind = implementation["kind"]
    state: str
    reachable = "not-checked"
    session = "not-applicable"
    version: str | None = None
    if kind == "native":
        state = "available-on-demand" if implementation.get("requires") else "available"
        session = "unknown"
        enabled: bool | str = False if implementation.get("requires") else "unknown"
    elif kind == "plugin":
        plugin = plugins.get(implementation["pluginName"])
        if plugin and plugin.get("enabled") is True:
            state = "enabled"
        elif plugin and plugin.get("enabled") is False:
            state = "disabled"
        elif plugin:
            state = "discovered-local"
        else:
            state = "not-installed"
        version = ",".join(plugin["versions"]) if plugin else None
        session = "unknown"
        enabled = plugin.get("enabled", "unknown") if plugin else False
    elif kind == "cli":
        path = shutil.which(implementation["command"])
        state = "installed" if path else "not-installed"
        reachable = "available" if path else "unreachable"
        enabled = bool(path)
    else:
        server_name = implementation["mcpServer"]
        configured = server_name in active_servers
        planned = server_name in preview_servers
        runtime, reachable = _mcp_runtime(servers[server_name], configured, live)
        if runtime == "missing-prerequisite":
            state = runtime
        elif configured:
            state = "configured"
        elif planned:
            state = "planned-profile"
        elif implementation.get("profile"):
            state = "available-profile"
        else:
            state = "available"
        session = "unknown" if configured else "not-active"
        enabled = configured

    auth = implementation.get("auth")
    auth_state = "not-required" if auth is None else "required-unverified"
    usable: bool | None
    if kind in {"native", "plugin"} and state in {"available", "enabled"}:
        usable = None
    else:
        usable = state in {"installed", "configured"}
    result = {
        "id": implementation["id"],
        "kind": kind,
        "state": state,
        "usableNow": usable,
        "enabled": enabled,
        "session": session,
        "auth": auth_state,
        "approval": implementation["approval"],
        "reachable": reachable,
        "useWhen": implementation["useWhen"],
    }
    for key in (
        "selector",
        "profile",
        "mcpServer",
        "command",
        "pluginName",
        "requires",
        "supersedesMcp",
    ):
        if key in implementation:
            result[key] = implementation[key]
    if version is not None:
        result["version"] = version
    return result


def format_capability_report(payload: dict[str, Any]) -> str:
    profiles = ",".join(payload["profiles"]) or "none"
    preview_profiles = ",".join(payload["previewProfiles"]) or "none"
    lines = [
        f"client: {payload['client']}",
        f"repo: {payload['repo'] or '-'}",
        f"repository MCP overrides: {profiles}",
        f"effective MCP: {','.join(payload['effectiveMcpServers'])}",
        f"preference: {' > '.join(payload['preferencePolicy'])}",
    ]
    if preview_profiles != profiles:
        lines.append(f"compatibility preview overrides: {preview_profiles}")
        lines.append(f"preview MCP: {','.join(payload['previewMcpServers'])}")
    for capability in payload["capabilities"]:
        preferred = capability["preferred"] or "unavailable"
        summary = (
            f"{capability['name']} [{capability['risk']}/{capability['activation']}] "
            f"preferred={preferred}"
        )
        if capability["previewPreferred"] != capability["preferred"]:
            summary += f"; preview={capability['previewPreferred'] or 'unavailable'}"
        lines.append(summary)
        if capability["duplicateMcpServers"]:
            lines.append(
                "  duplicate MCP (disable standalone): "
                + ",".join(capability["duplicateMcpServers"])
            )
        for implementation in capability["implementations"]:
            enabled = str(implementation["enabled"]).lower()
            detail = (
                f"  {implementation['id']}: {implementation['state']}; "
                f"enabled={enabled}; "
                f"auth={implementation['auth']}; session={implementation['session']}; "
                f"reachable={implementation['reachable']}"
            )
            if implementation.get("selector"):
                detail += f"; selector={implementation['selector']}"
            if implementation.get("profile"):
                detail += f"; profile={implementation['profile']}"
            if implementation.get("requires"):
                detail += f"; requires={implementation['requires']}"
            if implementation.get("shadowedBy"):
                detail += f"; shadowed-by={implementation['shadowedBy']}"
            lines.append(detail)
    if payload["unmappedPlugins"]:
        lines.append(
            f"other discovered {payload['client']} plugins: "
            + ",".join(payload["unmappedPlugins"])
        )
    return "\n".join(lines)
