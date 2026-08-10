from __future__ import annotations

from pathlib import Path

from .config import ROOT


def expected_rule_outputs(root: Path = ROOT) -> dict[Path, str]:
    source = (root / "rulesets/core/source.md").read_text(encoding="utf-8").rstrip() + "\n"
    cursor = (
        "---\n"
        "description: Universal coding agent core\n"
        "alwaysApply: true\n"
        "---\n\n"
        + source
    )
    return {
        root / "rulesets/core/codex/AGENTS.md": source,
        root / "rulesets/core/claude/CLAUDE.md": source,
        root / "rulesets/core/cursor/rules/core.mdc": cursor,
        root / "rulesets/core/opencode/AGENTS.md": source,
    }


def render_rules(root: Path = ROOT, check: bool = False) -> list[Path]:
    changed: list[Path] = []
    for path, content in expected_rule_outputs(root).items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        changed.append(path)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    return changed
