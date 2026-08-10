from __future__ import annotations

import json
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def copy_template_tree(destination: Path) -> Path:
    """Copy the tracked inputs needed by renderer and verifier tests."""
    for relative in ("config", "mcp", "registry", "rulesets", "scripts"):
        source = PROJECT_ROOT / relative
        target = destination / relative
        if source.is_dir():
            shutil.copytree(source, target, symlinks=True)
        elif source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return destination


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def make_registry(root: Path, repo: Path, profile: str = "lean") -> tuple[Path, Path]:
    registry = root / "registry.json"
    local = root / "registry.local.json"
    write_json(
        registry,
        {
            "defaults": {"ruleset": "core", "mcpProfile": "lean"},
            "repos": [{"name": "fixture", "mcpProfile": profile}],
        },
    )
    write_json(local, {"paths": {"fixture": str(repo)}})
    return registry, local
