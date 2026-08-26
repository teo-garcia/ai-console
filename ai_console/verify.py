from __future__ import annotations

import json
import re
import shutil
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from .capabilities import load_capability_registry, resolve_capabilities
from .config import ConfigError, ROOT, load_json, load_repo_entries
from .mcp import (
    PROFILE_FILENAMES,
    effective_server_names,
    expected_outputs,
    profile_config_path,
    render_all,
    render_profile_config,
)
from .ops import (
    _managed_servers,
    merge_claude_config,
    merge_claude_settings,
    merge_codex_config,
    merge_codex_status_line,
    merge_hook_config,
    merge_nested_config,
)
from .rules import render_rules


@dataclass(frozen=True)
class Check:
    status: str
    message: str


class Verifier:
    def __init__(self) -> None:
        self.checks: list[Check] = []

    def ok(self, message: str) -> None:
        self.checks.append(Check("ok", message))

    def warn(self, message: str) -> None:
        self.checks.append(Check("warn", message))

    def fail(self, message: str) -> None:
        self.checks.append(Check("fail", message))

    @property
    def failures(self) -> int:
        return sum(check.status == "fail" for check in self.checks)

    @property
    def warnings(self) -> int:
        return sum(check.status == "warn" for check in self.checks)

    def payload(self) -> dict[str, object]:
        return {
            "failures": self.failures,
            "warnings": self.warnings,
            "checks": [asdict(check) for check in self.checks],
        }


def verify_templates(root: Path = ROOT) -> Verifier:
    result = Verifier()
    required = [
        root / "mcp/canonical.json",
        root / "config/targets.json",
        root / "registry/repos.json",
        root / "registry/repos.local.example.json",
        root / "rulesets/core/codex/AGENTS.md",
        root / "rulesets/core/claude/CLAUDE.md",
        root / "rulesets/core/cursor/rules/core.mdc",
        root / "rulesets/core/opencode/AGENTS.md",
        root / "scripts/ai-console",
        root / "scripts/ai-console-lifecycle",
        root / "hooks/codex/hooks.json",
        root / "hooks/claude/settings.json",
        root / "hooks/cursor/hooks.json",
        root / "hooks/opencode/ai-console-lifecycle.js",
        root / "status-lines/codex.json",
        root / "status-lines/cursor.json",
        root / "status-lines/claude.sh",
        root / "config/model-policy.json",
        root / "config/capabilities.json",
    ]
    for path in required:
        if path.exists():
            result.ok(f"exists {path.relative_to(root)}")
        else:
            result.fail(f"missing {path.relative_to(root)}")

    try:
        load_capability_registry(root)
        result.ok("capability registry references valid clients, profiles, and tools")
    except ConfigError as exc:
        result.fail(str(exc))

    try:
        drift = render_all(root, check=True) + render_rules(root, check=True)
        if drift:
            for path in drift:
                result.fail(f"generated drift {path.relative_to(root)}")
        else:
            result.ok("generated MCP configs and client rules match canonical sources")
    except ConfigError as exc:
        result.fail(str(exc))
        return result

    for path in expected_outputs(root):
        try:
            if path.suffix == ".toml":
                tomllib.loads(path.read_text(encoding="utf-8"))
            else:
                json.loads(path.read_text(encoding="utf-8"))
            result.ok(f"valid config {path.relative_to(root)}")
        except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
            result.fail(f"invalid config {path.relative_to(root)}: {exc}")

    for path in sorted((root / "hooks").rglob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
            result.ok(f"valid hook config {path.relative_to(root)}")
        except (OSError, ValueError) as exc:
            result.fail(f"invalid hook config {path.relative_to(root)}: {exc}")

    portability_paths = [
        root / "mcp",
        root / "registry/repos.json",
        root / "config",
        root / "hooks",
        root / "status-lines",
    ]
    machine_pattern = re.compile(r"/Users/[^/\s]+|/home/[^/\s]+")
    for base in portability_paths:
        files = [base] if base.is_file() else [path for path in base.rglob("*") if path.is_file()]
        for path in files:
            if machine_pattern.search(path.read_text(encoding="utf-8")):
                result.fail(f"machine-specific path in {path.relative_to(root)}")
    if not any("machine-specific path" in check.message for check in result.checks):
        result.ok("tracked configuration contains no home-directory bindings")
    return result


def verify_install(root: Path = ROOT, home: Path | None = None) -> Verifier:
    active_home = home or Path.home()
    result = Verifier()
    expected_links = {
        active_home / ".codex/AGENTS.md": root / "rulesets/core/codex/AGENTS.md",
        active_home / ".claude/CLAUDE.md": root / "rulesets/core/claude/CLAUDE.md",
        active_home / ".claude/commands": root / "skills/claude",
        active_home / ".config/opencode/AGENTS.md": root
        / "rulesets/core/opencode/AGENTS.md",
        active_home / "AGENTS.md": root / "rulesets/core/opencode/AGENTS.md",
        root / "AGENTS.md": root / "rulesets/core/codex/AGENTS.md",
        root / "CLAUDE.md": root / "rulesets/core/claude/CLAUDE.md",
        root / ".cursor/rules": root / "rulesets/core/cursor/rules",
        active_home / ".cursor/mcp.json": root / "mcp/cursor.mcp.json",
        active_home / ".config/opencode/opencode.jsonc": root / "mcp/opencode.jsonc",
        active_home / ".claude/ai-console-statusline.sh": root
        / "status-lines/claude.sh",
    }
    skill_sources = {
        "engineering-workflows": root / "skills/shared/engineering-workflows",
        "grill-me": root / "vendor/mattpocock-skills/skills/productivity/grill-me",
        "grill-with-docs": root
        / "vendor/mattpocock-skills/skills/engineering/grill-with-docs",
    }
    for skills_dir in (
        active_home / ".codex/skills",
        active_home / ".cursor/skills",
        active_home / ".claude/skills",
        active_home / ".config/opencode/skills",
    ):
        for name, source in skill_sources.items():
            expected_links[skills_dir / name] = source
    for client, base in (
        ("codex", active_home / ".codex/agents"),
        ("cursor", active_home / ".cursor/agents"),
        ("claude", active_home / ".claude/agents"),
        ("opencode", active_home / ".config/opencode/agents"),
    ):
        for source in sorted((root / "agents" / client).glob("*")):
            if source.is_file():
                expected_links[base / source.name] = source
    for path, expected in expected_links.items():
        if not path.is_symlink():
            result.fail(f"not a symlink {path}")
        elif Path(path.readlink()) != expected:
            result.fail(f"unexpected symlink {path} -> {path.readlink()}")
        elif not path.exists():
            result.fail(f"broken symlink {path}")
        else:
            result.ok(f"installed {path}")

    codex_config = active_home / ".codex/config.toml"
    try:
        codex_text = codex_config.read_text(encoding="utf-8")
        tomllib.loads(codex_text)
        baseline = (root / "mcp/codex.config.toml").read_text(encoding="utf-8")
        merged = merge_codex_config(codex_text, _managed_servers(root), baseline)
        status_items = load_json(root / "status-lines/codex.json").get("items")
        if not isinstance(status_items, list):
            raise ConfigError("Codex status line config requires an items array")
        if merge_codex_status_line(merged, status_items) == codex_text:
            result.ok(f"managed Codex config is current {codex_config}")
        else:
            result.fail(f"managed Codex config has drift {codex_config}")
    except (ConfigError, OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        result.fail(f"invalid installed Codex config {codex_config}: {exc}")

    claude_config = active_home / ".claude.json"
    try:
        claude_data = load_json(claude_config)
        baseline_data = load_json(root / "mcp/claude.mcp.json")
        if (
            merge_claude_config(claude_data, _managed_servers(root), baseline_data)
            == claude_data
        ):
            result.ok(f"managed Claude config is current {claude_config}")
        else:
            result.fail(f"managed Claude config has drift {claude_config}")
    except ConfigError as exc:
        result.fail(str(exc))

    cursor_config = active_home / ".cursor/cli-config.json"
    try:
        cursor_data = load_json(cursor_config)
        cursor_baseline = load_json(root / "status-lines/cursor.json")
        if merge_nested_config(cursor_data, cursor_baseline) == cursor_data:
            result.ok(f"managed Cursor display settings are current {cursor_config}")
        else:
            result.fail(f"managed Cursor display settings have drift {cursor_config}")
    except ConfigError as exc:
        result.fail(str(exc))

    for hook_path, baseline_path, merge in (
        (
            active_home / ".codex/hooks.json",
            root / "hooks/codex/hooks.json",
            merge_hook_config,
        ),
        (
            active_home / ".cursor/hooks.json",
            root / "hooks/cursor/hooks.json",
            merge_hook_config,
        ),
        (
            active_home / ".claude/settings.json",
            root / "hooks/claude/settings.json",
            merge_claude_settings,
        ),
    ):
        try:
            installed = load_json(hook_path)
            baseline = load_json(baseline_path)
            if merge(installed, baseline) == installed:
                result.ok(f"managed native settings are current {hook_path}")
            else:
                result.fail(f"managed native settings have drift {hook_path}")
        except ConfigError as exc:
            result.fail(str(exc))

    retired_links = {
        active_home / ".ai-console/bin/ai-console-lifecycle": root
        / "scripts/ai-console-lifecycle",
        active_home / ".config/opencode/plugins/ai-console-lifecycle.js": root
        / "hooks/opencode/ai-console-lifecycle.js",
    }
    for path, retired_target in retired_links.items():
        if path.is_symlink() and Path(path.readlink()) == retired_target:
            result.fail(f"retired startup integration remains {path}")
        else:
            result.ok(f"retired startup integration is inactive {path}")

    try:
        repo_entries = load_repo_entries(root)
    except ConfigError as exc:
        result.fail(str(exc))
        return result
    repo_targets = load_json(root / "config/targets.json")["repo"]
    for entry in repo_entries:
        repo = entry.path
        if not repo.is_dir():
            result.warn(f"registered repo is unavailable {entry.name} -> {repo}")
            continue
        rule_links = {
            repo / repo_targets["codex"]["rules"]: root
            / f"rulesets/{entry.ruleset}/codex/AGENTS.md",
            repo / repo_targets["cursor"]["rules"]: root
            / f"rulesets/{entry.ruleset}/cursor/rules",
            repo / repo_targets["claude"]["rules"]: root
            / f"rulesets/{entry.ruleset}/claude/CLAUDE.md",
        }
        for path, expected in rule_links.items():
            if path.is_symlink() and Path(path.readlink()) == expected and path.exists():
                result.ok(f"repo rule installed {path}")
            elif path.exists():
                result.warn(f"repo rule is user-owned and was preserved {path}")
            else:
                result.fail(f"repo rule missing {path}")
        legacy_claude_rules = repo / ".claude/rules"
        if legacy_claude_rules.is_symlink():
            try:
                Path(legacy_claude_rules.readlink()).relative_to(
                    root / f"rulesets/{entry.ruleset}/claude/rules"
                )
            except ValueError:
                pass
            else:
                result.fail(f"legacy managed repo rule remains {legacy_claude_rules}")
        if entry.mcp_profiles:
            for client in PROFILE_FILENAMES:
                destination = repo / repo_targets[client]["mcpConfig"]
                expected = profile_config_path(root, entry.mcp_profiles, client)
                if not (
                    destination.is_symlink()
                    and Path(destination.readlink()) == expected
                    and destination.exists()
                ):
                    result.fail(f"repo MCP profile missing or unexpected {destination}")
                    continue
                if len(entry.mcp_profiles) > 1 and expected.read_text(
                    encoding="utf-8"
                ) != render_profile_config(root, entry.mcp_profiles, client):
                    result.fail(f"repo MCP profile has drift {destination}")
                else:
                    result.ok(f"repo MCP profile installed {destination}")
        else:
            for client in PROFILE_FILENAMES:
                destination = repo / repo_targets[client]["mcpConfig"]
                if not destination.is_symlink():
                    continue
                try:
                    Path(destination.readlink()).relative_to(root / "mcp")
                except ValueError:
                    continue
                result.fail(f"unexpected managed repo MCP profile {destination}")
    return result


def doctor(
    root: Path = ROOT,
    home: Path | None = None,
    *,
    client: str = "codex-desktop",
    repo_name: str | None = None,
    live: bool = False,
) -> Verifier:
    result = verify_templates(root)
    for command in ("git", "python3", "npx", "uvx"):
        if shutil.which(command):
            result.ok(f"command available {command}")
        else:
            result.fail(f"missing command {command}")
    try:
        entries = load_repo_entries(root)
        for entry in entries:
            if entry.path.is_dir():
                result.ok(f"repo binding {entry.name} -> {entry.path}")
            else:
                result.warn(f"repo path missing {entry.name} -> {entry.path}")
            profiles = ",".join(entry.mcp_profiles) or "none"
            servers = ",".join(effective_server_names(root, entry.mcp_profiles))
            result.ok(
                f"repo MCP capabilities {entry.name}: "
                f"overrides={profiles}; effective servers={servers}"
            )
    except ConfigError as exc:
        result.fail(str(exc))
    try:
        payload = resolve_capabilities(
            root,
            client=client,
            repo_name=repo_name,
            home=home,
            live=live,
        )
        result.ok(
            f"capability resolution client={client} "
            f"repo={repo_name or '-'} "
            f"overrides={','.join(payload['profiles']) or 'none'}"
        )
        for capability in payload["capabilities"]:
            preferred = capability["preferred"]
            states = ",".join(
                f"{item['id']}={item['state']}"
                for item in capability["implementations"]
            )
            if preferred:
                result.ok(
                    f"capability {capability['name']}: preferred={preferred}; {states}"
                )
            elif any(
                item["state"] in {"available-profile", "planned-profile"}
                for item in capability["implementations"]
            ):
                result.ok(
                    f"capability {capability['name']}: inactive repository profile; "
                    f"{states}"
                )
            else:
                result.warn(f"capability {capability['name']}: unavailable; {states}")
            if live:
                for item in capability["implementations"]:
                    if item["state"] == "configured" and item["reachable"] in {
                        "unreachable",
                        "invalid-url",
                    }:
                        result.warn(
                            f"capability runtime unreachable "
                            f"{capability['name']}/{item['id']}"
                        )
    except ConfigError as exc:
        result.fail(str(exc))
    return result
