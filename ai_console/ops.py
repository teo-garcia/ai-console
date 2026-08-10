from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import ConfigError, ROOT, expand_path, load_json, load_repo_entries


@dataclass
class Runner:
    dry_run: bool = False
    force: bool = False
    messages: list[str] = field(default_factory=list)

    def emit(self, message: str) -> None:
        self.messages.append(message)
        print(message)

    def link(self, source: Path, destination: Path) -> None:
        if not source.exists():
            self.emit(f"skip: missing source {source}")
            return
        if destination.is_symlink() and Path(os.readlink(destination)) == source:
            self.emit(f"unchanged: {destination} -> {source}")
            return
        if destination.exists() and not destination.is_symlink():
            if not self.force:
                self.emit(
                    f"skip: {destination} exists and is not a symlink "
                    "(use --force to replace a file)"
                )
                return
            if destination.is_dir():
                raise ConfigError(
                    f"refusing to replace directory with --force: {destination}"
                )
        action = "would link" if self.dry_run else "linked"
        self.emit(f"{action}: {destination} -> {source}")
        if self.dry_run:
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() or destination.is_symlink():
            destination.unlink()
        destination.symlink_to(source, target_is_directory=source.is_dir())

    def unlink(self, destination: Path) -> None:
        if not destination.is_symlink():
            return
        action = "would unlink" if self.dry_run else "unlinked"
        self.emit(f"{action}: {destination}")
        if not self.dry_run:
            destination.unlink()

    def write(self, destination: Path, content: str, backup: bool = False) -> None:
        current = destination.read_text(encoding="utf-8") if destination.exists() else None
        if current == content:
            self.emit(f"unchanged: {destination}")
            return
        if destination.is_symlink() and not self.force:
            self.emit(
                f"skip: {destination} is a symlink "
                "(use --force to replace the link with a managed file)"
            )
            return
        action = "would write" if self.dry_run else "written"
        self.emit(f"{action}: {destination}")
        if self.dry_run:
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        if backup and destination.exists():
            backup_path = Path(f"{destination}.bak")
            shutil.copy2(destination, backup_path)
            self.emit(f"backup: {backup_path}")
        if destination.is_symlink():
            destination.unlink()
        destination.write_text(content, encoding="utf-8")


def _targets(root: Path) -> dict[str, Any]:
    data = load_json(root / "config/targets.json")
    if not isinstance(data.get("global"), dict) or not isinstance(data.get("repo"), dict):
        raise ConfigError("targets config requires global and repo objects")
    return data


def _managed_servers(root: Path) -> set[str]:
    canonical = load_json(root / "mcp/canonical.json")
    names = canonical.get("managedServers")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise ConfigError("canonical managedServers must be a string array")
    return set(names)


def merge_codex_config(existing: str, managed: set[str], baseline: str) -> str:
    kept: list[str] = []
    inside_managed = False
    header = re.compile(
        r'^\s*\[mcp_servers\.(?:"([^"]+)"|([A-Za-z0-9_-]+))(?:\.|\])'
    )
    any_table = re.compile(r"^\s*\[")
    for line in existing.splitlines(keepends=True):
        if line.strip() == "## Codex MCP servers" or line.startswith(
            "## Managed by ai-console"
        ):
            continue
        match = header.match(line)
        if match:
            name = match.group(1) or match.group(2)
            inside_managed = name in managed
        elif any_table.match(line):
            inside_managed = False
        if not inside_managed:
            kept.append(line)
    prefix = "".join(kept).rstrip()
    return f"{prefix}\n\n{baseline}" if prefix else baseline


def merge_claude_config(
    existing: dict[str, Any], managed: set[str], baseline: dict[str, Any]
) -> dict[str, Any]:
    result = dict(existing)
    current = result.get("mcpServers")
    servers = dict(current) if isinstance(current, dict) else {}
    for name in managed:
        servers.pop(name, None)
    baseline_servers = baseline.get("mcpServers", {})
    if not isinstance(baseline_servers, dict):
        raise ConfigError("Claude baseline mcpServers must be an object")
    servers.update(baseline_servers)
    result["mcpServers"] = servers
    return result


def _contains_managed_hook(value: Any) -> bool:
    if isinstance(value, str):
        return "ai-console-lifecycle" in value
    if isinstance(value, list):
        return any(_contains_managed_hook(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_managed_hook(item) for item in value.values())
    return False


def merge_hook_config(
    existing: dict[str, Any], baseline: dict[str, Any]
) -> dict[str, Any]:
    """Replace only ai-console hook entries while preserving other integrations."""
    result = dict(existing)
    current_hooks = result.get("hooks")
    hooks = dict(current_hooks) if isinstance(current_hooks, dict) else {}
    baseline_hooks = baseline.get("hooks")
    if not isinstance(baseline_hooks, dict):
        raise ConfigError("hook baseline requires a hooks object")
    for event, managed_entries in baseline_hooks.items():
        if not isinstance(managed_entries, list):
            raise ConfigError(f"hook event {event} must be an array")
        existing_entries = hooks.get(event)
        kept = (
            [entry for entry in existing_entries if not _contains_managed_hook(entry)]
            if isinstance(existing_entries, list)
            else []
        )
        hooks[event] = [*kept, *managed_entries]
    result["hooks"] = hooks
    if "version" in baseline:
        result["version"] = baseline["version"]
    return result


def _link_skill(runner: Runner, source: Path, skills_dir: Path) -> None:
    if not (source / "SKILL.md").is_file():
        runner.emit(f"skip: missing skill {source / 'SKILL.md'}")
        return
    runner.link(source, skills_dir / source.name)


def _remove_managed_non_global_skills(
    runner: Runner, root: Path, skills_dir: Path
) -> None:
    if not skills_dir.is_dir():
        return
    vendor_roots = (
        root / "vendor/vercel-labs-agent-skills",
        root / "vendor/shadcn-ui",
        root / "vendor/shadcn-improve",
    )
    for candidate in skills_dir.iterdir():
        if not candidate.is_symlink():
            continue
        raw_target = Path(os.readlink(candidate))
        for vendor_root in vendor_roots:
            try:
                raw_target.relative_to(vendor_root)
            except ValueError:
                continue
            runner.unlink(candidate)
            break


def apply_global(
    root: Path = ROOT,
    home: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> Runner:
    active_home = home or Path.home()
    targets = _targets(root)["global"]
    runner = Runner(dry_run=dry_run, force=force)

    def target(client: str, key: str) -> Path:
        value = targets.get(client, {}).get(key)
        if not isinstance(value, str):
            raise ConfigError(f"missing global target {client}.{key}")
        return expand_path(value, active_home)

    codex_skills = target("codex", "skillsDir")
    cursor_skills = target("cursor", "skillsDir")
    claude_skills = target("claude", "skillsDir")
    opencode_skills = target("opencode", "skillsDir")

    runner.link(root / "rulesets/core/codex/AGENTS.md", target("codex", "instructions"))
    runner.link(root / "rulesets/core/claude/CLAUDE.md", target("claude", "instructions"))
    runner.link(root / "skills/claude", target("claude", "commandsDir"))
    runner.link(
        root / "rulesets/core/opencode/AGENTS.md", target("opencode", "instructions")
    )
    runner.link(root / "rulesets/core/opencode/AGENTS.md", active_home / "AGENTS.md")

    for client_dir, skills_dir in (
        (root / "skills/codex", codex_skills),
        (root / "skills/opencode", opencode_skills),
    ):
        if client_dir.is_dir():
            for skill in sorted(client_dir.iterdir()):
                if skill.is_dir():
                    _link_skill(runner, skill, skills_dir)

    shared_skills = root / "skills/shared"
    if shared_skills.is_dir():
        for skill in sorted(shared_skills.iterdir()):
            if not skill.is_dir():
                continue
            for skills_dir in (
                codex_skills,
                cursor_skills,
                claude_skills,
                opencode_skills,
            ):
                _link_skill(runner, skill, skills_dir)

    for skills_dir in (codex_skills, cursor_skills, claude_skills, opencode_skills):
        _remove_managed_non_global_skills(runner, root, skills_dir)
        _link_skill(
            runner,
            root / "vendor/mattpocock-skills/skills/productivity/grill-me",
            skills_dir,
        )
        _link_skill(
            runner,
            root / "vendor/mattpocock-skills/skills/engineering/grill-with-docs",
            skills_dir,
        )

    managed = _managed_servers(root)
    codex_destination = target("codex", "mcpConfig")
    codex_existing = (
        codex_destination.read_text(encoding="utf-8")
        if codex_destination.exists()
        else ""
    )
    codex_baseline = (root / "mcp/codex.config.toml").read_text(encoding="utf-8")
    runner.write(
        codex_destination,
        merge_codex_config(codex_existing, managed, codex_baseline),
        backup=True,
    )

    claude_destination = target("claude", "mcpConfig")
    claude_existing = load_json(claude_destination) if claude_destination.exists() else {}
    claude_baseline = load_json(root / "mcp/claude.mcp.json")
    claude_merged = merge_claude_config(claude_existing, managed, claude_baseline)
    runner.write(
        claude_destination,
        json.dumps(claude_merged, indent=2) + "\n",
        backup=True,
    )

    runner.link(root / "mcp/cursor.mcp.json", target("cursor", "mcpConfig"))
    runner.link(root / "mcp/opencode.jsonc", target("opencode", "mcpConfig"))

    launcher = active_home / ".ai-console/bin/ai-console-lifecycle"
    runner.link(root / "scripts/ai-console-lifecycle", launcher)
    for client, key, baseline_path in (
        ("codex", "hooksConfig", root / "hooks/codex/hooks.json"),
        ("cursor", "hooksConfig", root / "hooks/cursor/hooks.json"),
        ("claude", "settingsConfig", root / "hooks/claude/settings.json"),
    ):
        destination = target(client, key)
        existing = load_json(destination) if destination.exists() else {}
        baseline = load_json(baseline_path)
        merged = merge_hook_config(existing, baseline)
        runner.write(destination, json.dumps(merged, indent=2) + "\n", backup=True)
    runner.link(
        root / "hooks/opencode/ai-console-lifecycle.js",
        target("opencode", "pluginsDir") / "ai-console-lifecycle.js",
    )
    agent_extensions = {
        "codex": ".toml",
        "cursor": ".md",
        "claude": ".md",
        "opencode": ".md",
    }
    for client, extension in agent_extensions.items():
        agents_dir = target(client, "agentsDir")
        for source in sorted((root / "agents" / client).glob(f"*{extension}")):
            runner.link(source, agents_dir / source.name)
    return runner


def _unlink_managed_mcp(runner: Runner, root: Path, destination: Path) -> None:
    if not destination.is_symlink():
        return
    target = Path(os.readlink(destination))
    try:
        target.relative_to(root / "mcp")
    except ValueError:
        return
    runner.unlink(destination)


def apply_repos(
    root: Path = ROOT,
    dry_run: bool = False,
    force: bool = False,
    registry_path: Path | None = None,
    local_path: Path | None = None,
) -> Runner:
    targets = _targets(root)["repo"]
    entries = load_repo_entries(root, registry_path, local_path)
    runner = Runner(dry_run=dry_run, force=force)

    def target(client: str, key: str) -> str:
        value = targets.get(client, {}).get(key)
        if not isinstance(value, str):
            raise ConfigError(f"missing repo target {client}.{key}")
        return value

    for entry in entries:
        repo = entry.path
        if not repo.is_dir():
            runner.emit(f"skip: repo not found {repo}")
            continue
        codex_rules = target("codex", "rules")
        opencode_rules = target("opencode", "rules")
        runner.link(root / f"rulesets/{entry.ruleset}/codex/AGENTS.md", repo / codex_rules)
        runner.link(
            root / f"rulesets/{entry.ruleset}/cursor/rules",
            repo / target("cursor", "rules"),
        )
        runner.link(
            root / f"rulesets/{entry.ruleset}/claude/CLAUDE.md",
            repo / target("claude", "rules"),
        )
        if opencode_rules == codex_rules:
            runner.emit(f"shared: {repo / codex_rules} is used by Codex and OpenCode")
        else:
            runner.link(
                root / f"rulesets/{entry.ruleset}/opencode/AGENTS.md",
                repo / opencode_rules,
            )

        _unlink_managed_mcp(runner, root, repo / "mcp.json")
        profile_files = {
            "codex": "codex.config.toml",
            "cursor": "cursor.mcp.json",
            "claude": "claude.mcp.json",
            "opencode": "opencode.jsonc",
        }
        for client, filename in profile_files.items():
            destination = repo / target(client, "mcpConfig")
            if entry.mcp_profile == "lean":
                _unlink_managed_mcp(runner, root, destination)
            else:
                runner.link(
                    root / "mcp/profiles" / entry.mcp_profile / filename,
                    destination,
                )
    return runner


def _copy_snapshot(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        destination.symlink_to(os.readlink(source))
    elif source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
    else:
        shutil.copy2(source, destination)


def backup_global(root: Path = ROOT, home: Path | None = None) -> Path:
    active_home = home or Path.home()
    targets = _targets(root)["global"]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination_root = root / "backups" / stamp
    destination_root.mkdir(parents=True)

    def target(client: str, key: str) -> Path:
        value = targets.get(client, {}).get(key)
        if not isinstance(value, str):
            raise ConfigError(f"missing global target {client}.{key}")
        return expand_path(value, active_home)

    sources = {
        "codex/AGENTS.md": target("codex", "instructions"),
        "codex/config.toml": target("codex", "mcpConfig"),
        "codex/hooks.json": target("codex", "hooksConfig"),
        "codex/skills": target("codex", "skillsDir"),
        "codex/agents": target("codex", "agentsDir"),
        "cursor/mcp.json": target("cursor", "mcpConfig"),
        "cursor/hooks.json": target("cursor", "hooksConfig"),
        "cursor/skills": target("cursor", "skillsDir"),
        "cursor/agents": target("cursor", "agentsDir"),
        "claude/CLAUDE.md": target("claude", "instructions"),
        "claude/claude.json": target("claude", "mcpConfig"),
        "claude/settings.json": target("claude", "settingsConfig"),
        "claude/commands": target("claude", "commandsDir"),
        "claude/skills": target("claude", "skillsDir"),
        "claude/agents": target("claude", "agentsDir"),
        "opencode/AGENTS.md": target("opencode", "instructions"),
        "opencode/opencode.jsonc": target("opencode", "mcpConfig"),
        "opencode/plugins": target("opencode", "pluginsDir"),
        "opencode/skills": target("opencode", "skillsDir"),
        "opencode/agents": target("opencode", "agentsDir"),
    }
    manifest: list[dict[str, str | bool]] = []
    text_lines: list[str] = []
    for relative, source in sources.items():
        backup_path = destination_root / relative
        exists = source.exists() or source.is_symlink()
        manifest.append(
            {"source": str(source), "backup": relative, "exists": exists}
        )
        if exists:
            _copy_snapshot(source, backup_path)
            text_lines.append(f"{source} -> {backup_path}")
        else:
            text_lines.append(f"missing: {source}")
    (destination_root / "manifest.json").write_text(
        json.dumps({"version": 1, "entries": manifest}, indent=2) + "\n",
        encoding="utf-8",
    )
    (destination_root / "manifest.txt").write_text(
        "\n".join(text_lines) + "\n", encoding="utf-8"
    )
    print(f"backup complete: {destination_root}")
    return destination_root


def restore_backup(
    timestamp: str,
    root: Path = ROOT,
    home: Path | None = None,
    dry_run: bool = True,
    force: bool = False,
) -> Runner:
    active_home = home or Path.home()
    backup_root = root / "backups" / timestamp
    manifest_path = backup_root / "manifest.json"
    if not manifest_path.is_file():
        raise ConfigError(f"restore requires manifest.json: {manifest_path}")
    manifest = load_json(manifest_path)
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ConfigError(f"invalid restore manifest: {manifest_path}")
    if not dry_run and not force:
        raise ConfigError("restore requires --force; run without --force to preview")
    runner = Runner(dry_run=dry_run, force=force)
    targets = _targets(root)["global"]
    allowed_sources = {active_home / "AGENTS.md"}
    for client_targets in targets.values():
        if not isinstance(client_targets, dict):
            continue
        for value in client_targets.values():
            if isinstance(value, str):
                allowed_sources.add(expand_path(value, active_home))
    for raw in entries:
        if not isinstance(raw, dict):
            raise ConfigError(f"invalid restore entry in {manifest_path}")
        source = Path(str(raw.get("source")))
        if source not in allowed_sources:
            raise ConfigError(f"restore source is outside managed targets: {source}")
        relative_backup = Path(str(raw.get("backup")))
        if relative_backup.is_absolute() or ".." in relative_backup.parts:
            raise ConfigError(f"invalid backup path in restore manifest: {relative_backup}")
        backup = backup_root / relative_backup
        if not raw.get("exists"):
            if not source.exists() and not source.is_symlink():
                continue
            action = "would remove" if dry_run else "removed"
            runner.emit(f"{action}: {source} (absent in snapshot)")
            if dry_run:
                continue
            if source.is_symlink() or source.is_file():
                source.unlink()
            elif source.is_dir():
                shutil.rmtree(source)
            continue
        if not backup.exists() and not backup.is_symlink():
            raise ConfigError(f"missing backup artifact: {backup}")
        action = "would restore" if dry_run else "restored"
        runner.emit(f"{action}: {source} <- {backup}")
        if dry_run:
            continue
        if source.is_symlink() or source.is_file():
            source.unlink()
        elif source.is_dir():
            shutil.rmtree(source)
        _copy_snapshot(backup, source)
    return runner
