from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ConfigError


CORRECTION_PATTERN = re.compile(
    r"^\s*AI-CONSOLE-CORRECTION:\s*(.{8,500})\s*$", re.IGNORECASE | re.MULTILINE
)
SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*\S+"
)


def state_home() -> Path:
    override = os.environ.get("AI_CONSOLE_STATE_HOME")
    return Path(override).expanduser() if override else Path.home() / ".ai-console"


def _private_directory(path: Path) -> None:
    home = state_home()
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(home, 0o700)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    parent = path.parent
    if parent != home and home in parent.parents:
        os.chmod(parent, 0o700)


def read_hook_input(stream: Any = sys.stdin) -> dict[str, Any]:
    content = stream.read(1_000_001)
    if len(content) > 1_000_000:
        raise ConfigError("hook input exceeds 1 MB")
    if not content.strip():
        return {}
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid hook JSON: {exc}") from exc
    return payload if isinstance(payload, dict) else {}


def _git(cwd: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args],
            text=True,
            capture_output=True,
            timeout=1.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def repo_state(cwd: Path) -> dict[str, Any]:
    root_value = _git(cwd, "rev-parse", "--show-toplevel")
    if not root_value:
        return {"cwd": str(cwd), "repository": False}
    root = Path(root_value)
    branch = _git(root, "branch", "--show-current") or "detached"
    status = _git(root, "status", "--short", "--untracked-files=normal") or ""
    changes = [line for line in status.splitlines() if line][:20]
    commits = (_git(root, "log", "-3", "--pretty=format:%h %s") or "").splitlines()
    return {
        "cwd": str(cwd),
        "repository": True,
        "root": str(root),
        "branch": branch,
        "changes": changes,
        "changeCount": len(status.splitlines()) if status else 0,
        "recentCommits": commits,
    }


def _project_key(path: str) -> str:
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]


def _latest_session_for(path: str) -> dict[str, Any] | None:
    sessions = state_home() / "sessions" / _project_key(path)
    if not sessions.is_dir():
        return None
    candidates = sorted(sessions.glob("*.json"), reverse=True)
    for candidate in candidates[:10]:
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


def context_brief(cwd: Path) -> str:
    state = repo_state(cwd)
    lines = ["AI-console workspace brief (runtime facts; repository instructions still govern):"]
    if not state["repository"]:
        lines.append(f"- Working directory: {cwd} (not a Git repository)")
        return "\n".join(lines)
    lines.extend(
        [
            f"- Repository: {state['root']}",
            f"- Branch: {state['branch']}",
            f"- Working tree changes: {state['changeCount']}",
        ]
    )
    for change in state["changes"][:10]:
        lines.append(f"  - {change}")
    if state["recentCommits"]:
        lines.append("- Recent commits:")
        lines.extend(f"  - {commit}" for commit in state["recentCommits"])
    latest = _latest_session_for(str(state["root"]))
    if latest:
        lines.append(
            "- Previous captured lifecycle event: "
            f"{latest.get('client', 'unknown')}/{latest.get('event', 'unknown')} "
            f"at {latest.get('capturedAt', 'unknown')}"
        )
    return "\n".join(lines[:25])


def _safe_text(value: str) -> str:
    cleaned = " ".join(value.split())[:500]
    return SECRET_PATTERN.sub(r"\1=[REDACTED]", cleaned)


def extract_corrections(payload: dict[str, Any]) -> list[str]:
    message = payload.get("last_assistant_message") or payload.get("lastAssistantMessage")
    if not isinstance(message, str):
        return []
    return [_safe_text(match) for match in CORRECTION_PATTERN.findall(message)]


def capture_event(client: str, payload: dict[str, Any], event: str | None = None) -> Path:
    cwd = Path(str(payload.get("cwd") or os.getcwd())).resolve()
    state = repo_state(cwd)
    project = str(state.get("root") or cwd)
    session_id = payload.get("session_id") or payload.get("sessionId")
    record = {
        "version": 1,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "client": client,
        "event": event or payload.get("hook_event_name") or payload.get("hookEventName") or "unknown",
        "reason": payload.get("reason") or payload.get("source"),
        "session": str(session_id) if session_id else None,
        "project": project,
        "branch": state.get("branch"),
        "changeCount": state.get("changeCount"),
        "corrections": extract_corrections(payload),
    }
    directory = state_home() / "sessions" / _project_key(project)
    _private_directory(directory)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = directory / f"{stamp}-{client}.json"
    destination.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.chmod(destination, 0o600)
    return destination


def record_correction(text: str, target: str, source: str = "manual") -> Path:
    safe = _safe_text(text)
    if len(safe) < 8:
        raise ConfigError("correction must contain at least 8 characters")
    allowed_targets = {"rules", "skill", "hook", "test", "mcp", "unsure"}
    if target not in allowed_targets:
        raise ConfigError(f"learning target must be one of: {', '.join(sorted(allowed_targets))}")
    directory = state_home() / "corrections"
    _private_directory(directory)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = directory / f"{stamp}.json"
    payload = {
        "version": 1,
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "correction": safe,
        "target": target,
        "source": _safe_text(source),
    }
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.chmod(destination, 0o600)
    return destination


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def draft_learning(minimum_occurrences: int = 2) -> Path:
    if minimum_occurrences < 2:
        raise ConfigError("minimum occurrences must be at least 2")
    observations: list[dict[str, str]] = []
    corrections_dir = state_home() / "corrections"
    for path in sorted(corrections_dir.glob("*.json")) if corrections_dir.is_dir() else []:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("correction"), str):
            observations.append(
                {
                    "text": payload["correction"],
                    "target": str(payload.get("target") or "unsure"),
                    "evidence": str(path),
                }
            )
    sessions_dir = state_home() / "sessions"
    for path in sorted(sessions_dir.glob("*/*.json")) if sessions_dir.is_dir() else []:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        for correction in payload.get("corrections", []):
            if isinstance(correction, str):
                observations.append(
                    {"text": correction, "target": "unsure", "evidence": str(path)}
                )

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for observation in observations:
        groups[_normalized(observation["text"])].append(observation)
    repeated = [items for items in groups.values() if len(items) >= minimum_occurrences]

    lines = [
        "# AI-console learning review",
        "",
        "This is a draft only. Verify each observation, choose the durable layer, run evals, and review the diff before committing.",
        "",
    ]
    if not repeated:
        lines.append(f"No correction appeared at least {minimum_occurrences} times.")
    for index, items in enumerate(sorted(repeated, key=lambda item: item[0]["text"]), 1):
        targets = sorted({item["target"] for item in items})
        lines.extend(
            [
                f"## Candidate {index}",
                "",
                f"- Correction: {items[0]['text']}",
                f"- Occurrences: {len(items)}",
                f"- Suggested layer(s): {', '.join(targets)}",
                "- Evidence:",
                *[f"  - {item['evidence']}" for item in items],
                "",
                "### Review checklist",
                "",
                "- [ ] Confirm the correction is stable and not project-specific.",
                "- [ ] Choose rules, skill, hook, test, or MCP configuration as the narrowest durable layer.",
                "- [ ] Draft the smallest change and evaluate it against the relevant corpus cases.",
                "- [ ] Apply only after human review.",
                "",
            ]
        )
    directory = state_home() / "drafts"
    _private_directory(directory)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = directory / f"{stamp}.md"
    destination.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    os.chmod(destination, 0o600)
    return destination


def lifecycle_main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if len(args) < 2 or args[0] not in {"brief", "capture"}:
        print("usage: ai-console-lifecycle brief|capture CLIENT [EVENT]", file=sys.stderr)
        return 2
    action, client = args[:2]
    try:
        payload = read_hook_input()
        if action == "brief":
            cwd = Path(str(payload.get("cwd") or os.getcwd())).resolve()
            brief = context_brief(cwd)
            if client == "cursor":
                print(json.dumps({"additional_context": brief}))
            else:
                print(brief)
        else:
            capture_event(client, payload, args[2] if len(args) > 2 else None)
        return 0
    except Exception as exc:  # Hooks must fail open.
        print(f"ai-console lifecycle warning: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(lifecycle_main())
