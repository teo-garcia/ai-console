from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ConfigError, ROOT, load_json


PLUGIN_CLIENTS = ("codex", "claude", "cursor", "opencode")
PLUGIN_KINDS = {"native", "npm"}
PLUGIN_PRECEDENCE = ("native", "plugin", "mcp", "cli")
PLUGIN_MANAGEMENT = {"runtime", "marketplace", "generated"}
PLUGIN_ACTIVATION = {"global", "lazy"}


def load_plugin_registry(root: Path = ROOT) -> dict[str, Any]:
    registry = load_json(root / "config/plugins.json")
    if registry.get("version") != 1:
        raise ConfigError("plugin registry version must be 1")
    policy = registry.get("policy")
    if not isinstance(policy, dict):
        raise ConfigError("plugin registry requires policy")
    if tuple(policy.get("precedence", ())) != PLUGIN_PRECEDENCE:
        raise ConfigError(
            "plugin precedence must be native, plugin, MCP, then CLI"
        )
    if policy.get("duplicateMcp") != "prefer-plugin-and-disable-standalone":
        raise ConfigError("plugin registry must prohibit duplicate standalone MCP")
    if not isinstance(policy.get("selection"), str):
        raise ConfigError("plugin registry requires a minimal selection policy")
    ownership = registry.get("mcpOwnership")
    if not isinstance(ownership, dict):
        raise ConfigError("plugin registry requires MCP ownership mappings")
    canonical = load_json(root / "mcp/canonical.json")
    servers = canonical.get("servers")
    if not isinstance(servers, dict):
        raise ConfigError("canonical MCP servers must be objects")
    for client, mappings in ownership.items():
        if client not in PLUGIN_CLIENTS or not isinstance(mappings, dict):
            raise ConfigError("plugin MCP ownership has an invalid client mapping")
        for server, plugin in mappings.items():
            if server not in servers or not isinstance(plugin, str):
                raise ConfigError("plugin MCP ownership references an invalid server")
    selected = registry.get("selected")
    if not isinstance(selected, dict) or tuple(selected) != PLUGIN_CLIENTS:
        raise ConfigError("selected plugins must map every client in order")
    selected_names: dict[str, set[str]] = {}
    for client, plugins in selected.items():
        if not isinstance(plugins, list):
            raise ConfigError(f"selected plugins for {client} must be an array")
        names: set[str] = set()
        for plugin in plugins:
            if not isinstance(plugin, dict):
                raise ConfigError(f"selected plugin for {client} must be an object")
            name = plugin.get("name")
            if not isinstance(name, str) or name in names:
                raise ConfigError(f"selected plugin for {client} has invalid name")
            names.add(name)
            if not isinstance(plugin.get("source"), str):
                raise ConfigError(f"selected plugin {name!r} requires source")
            if plugin.get("management") not in PLUGIN_MANAGEMENT:
                raise ConfigError(f"selected plugin {name!r} has invalid management")
            if plugin.get("activation") not in PLUGIN_ACTIVATION:
                raise ConfigError(f"selected plugin {name!r} has invalid activation")
            if not isinstance(plugin.get("capabilities"), list) or not plugin[
                "capabilities"
            ]:
                raise ConfigError(f"selected plugin {name!r} requires capabilities")
            replacement = plugin.get("replacesMcp")
            if replacement is not None and replacement not in servers:
                raise ConfigError(f"selected plugin {name!r} replaces unknown MCP")
            prerequisite = plugin.get("requiresCommand")
            if prerequisite is not None and not isinstance(prerequisite, str):
                raise ConfigError(f"selected plugin {name!r} has invalid prerequisite")
        selected_names[client] = names
    for client, mappings in ownership.items():
        for plugin in mappings.values():
            if plugin not in selected_names[client]:
                raise ConfigError(
                    f"plugin MCP ownership for {client} must reference a selected plugin"
                )
    capabilities = registry.get("capabilities")
    if not isinstance(capabilities, dict) or not capabilities:
        raise ConfigError("plugin registry requires capabilities")

    for capability_name, capability in capabilities.items():
        if not isinstance(capability_name, str) or not isinstance(capability, dict):
            raise ConfigError("plugin capabilities must map names to objects")
        if not isinstance(capability.get("description"), str):
            raise ConfigError(f"plugin capability {capability_name!r} requires description")
        contract = capability.get("contract")
        if not isinstance(contract, dict) or contract.get("repositoryState") is not False:
            raise ConfigError(
                f"plugin capability {capability_name!r} must forbid repository state"
            )
        implementations = capability.get("implementations")
        if not isinstance(implementations, dict) or tuple(implementations) != PLUGIN_CLIENTS:
            raise ConfigError(
                f"plugin capability {capability_name!r} must map every client in order"
            )
        for client, implementation in implementations.items():
            _validate_implementation(capability_name, client, implementation)
    return registry


def plugin_owned_mcp_servers(client: str, root: Path = ROOT) -> dict[str, str]:
    registry = load_plugin_registry(root)
    mappings = registry["mcpOwnership"].get(client, {})
    return dict(mappings)


def _validate_implementation(
    capability_name: str, client: str, implementation: Any
) -> None:
    if not isinstance(implementation, dict):
        raise ConfigError(
            f"plugin capability {capability_name!r} client {client!r} must be an object"
        )
    kind = implementation.get("kind")
    if kind not in PLUGIN_KINDS:
        raise ConfigError(
            f"plugin capability {capability_name!r} client {client!r} has invalid kind"
        )
    if kind == "native":
        if not isinstance(implementation.get("command"), str):
            raise ConfigError(
                f"native plugin capability {capability_name!r}/{client} requires command"
            )
        return
    if client != "opencode":
        raise ConfigError("npm plugins are currently supported only for OpenCode")
    for key in ("package", "version", "source"):
        if not isinstance(implementation.get(key), str):
            raise ConfigError(
                f"npm plugin capability {capability_name!r}/{client} requires {key}"
            )
    options = implementation.get("options")
    if not isinstance(options, dict) or options.get("persistState") is not False:
        raise ConfigError(
            f"npm plugin capability {capability_name!r}/{client} must disable repository persistence"
        )
    command = implementation.get("command")
    if not isinstance(command, dict) or not all(
        isinstance(command.get(key), str)
        for key in ("name", "description", "template", "agent")
    ):
        raise ConfigError(
            f"npm plugin capability {capability_name!r}/{client} has invalid command"
        )


def opencode_plugin_config(root: Path = ROOT) -> dict[str, Any]:
    registry = load_plugin_registry(root)
    plugins: list[Any] = []
    commands: dict[str, Any] = {}
    for capability in registry["capabilities"].values():
        implementation = capability["implementations"]["opencode"]
        if implementation["kind"] != "npm":
            continue
        package = f"{implementation['package']}@{implementation['version']}"
        plugins.append([package, implementation["options"]])
        command = implementation["command"]
        commands[command["name"]] = {
            key: command[key] for key in ("description", "template", "agent")
        }
    return {"plugin": plugins, "command": commands}
