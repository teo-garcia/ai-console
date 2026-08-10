from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ConfigError, ROOT, load_json


CLIENTS = ("codex", "claude", "cursor", "opencode")


@dataclass(frozen=True)
class Variant:
    name: str
    ruleset: Path


def load_corpus(path: Path) -> dict[str, Any]:
    corpus = load_json(path)
    cases = corpus.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ConfigError(f"eval corpus requires a non-empty cases array: {path}")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ConfigError("eval cases must be objects")
        case_id = case.get("id")
        prompt = case.get("prompt")
        rubric = case.get("rubric")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ConfigError(f"invalid or duplicate eval case id: {case_id!r}")
        if not isinstance(prompt, str) or not prompt:
            raise ConfigError(f"eval case {case_id!r} requires a prompt")
        if not isinstance(rubric, list) or not rubric or not all(
            isinstance(item, str) and item for item in rubric
        ):
            raise ConfigError(f"eval case {case_id!r} requires rubric strings")
        seen.add(case_id)
    return corpus


def parse_variants(values: list[str], base: Path = ROOT) -> list[Variant]:
    variants: list[Variant] = []
    names: set[str] = set()
    for value in values:
        name, separator, raw_path = value.partition("=")
        if not separator or not name or not raw_path:
            raise ConfigError("variants use NAME=RULESET_PATH")
        if name in names:
            raise ConfigError(f"duplicate eval variant: {name}")
        path = Path(raw_path)
        if not path.is_absolute():
            path = base / path
        if not path.is_file():
            raise ConfigError(f"missing eval ruleset: {path}")
        variants.append(Variant(name, path.resolve()))
        names.add(name)
    if len(variants) < 2:
        raise ConfigError("an A/B eval requires at least two --variant values")
    return variants


def _install_ruleset(workspace: Path, client: str, content: str) -> None:
    if client in {"codex", "opencode"}:
        (workspace / "AGENTS.md").write_text(content, encoding="utf-8")
    elif client == "claude":
        (workspace / "CLAUDE.md").write_text(content, encoding="utf-8")
    elif client == "cursor":
        rules = workspace / ".cursor/rules"
        rules.mkdir(parents=True)
        body = content
        if not content.startswith("---\n"):
            body = "---\ndescription: Evaluation ruleset\nalwaysApply: true\n---\n\n" + content
        (rules / "eval.mdc").write_text(body, encoding="utf-8")


def command_for(
    client: str,
    workspace: Path,
    prompt: str,
    output_file: Path,
    model: str | None = None,
) -> list[str]:
    executable = "cursor-agent" if client == "cursor" else client
    if not shutil.which(executable):
        raise ConfigError(f"client command is unavailable: {executable}")
    if client == "codex":
        command = [
            executable,
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "--cd",
            str(workspace),
            "--output-last-message",
            str(output_file),
        ]
        if model:
            command.extend(["--model", model])
        command.append(prompt)
        return command
    if client == "claude":
        command = [
            executable,
            "--print",
            "--output-format",
            "json",
            "--permission-mode",
            "plan",
            "--no-session-persistence",
        ]
        if model:
            command.extend(["--model", model])
        command.append(prompt)
        return command
    if client == "cursor":
        command = [
            executable,
            "--print",
            "--output-format",
            "json",
            "--mode",
            "ask",
            "--workspace",
            str(workspace),
        ]
        if model:
            command.extend(["--model", model])
        command.append(prompt)
        return command
    if client == "opencode":
        command = [
            executable,
            "run",
            "--format",
            "json",
            "--agent",
            "plan",
            "--dir",
            str(workspace),
        ]
        if model:
            command.extend(["--model", model])
        command.append(prompt)
        return command
    raise ConfigError(f"unsupported eval client: {client}")


def _extract_output(client: str, stdout: str, output_file: Path) -> str:
    if client == "codex" and output_file.is_file():
        return output_file.read_text(encoding="utf-8")
    if client in {"claude", "cursor"}:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return stdout
        if isinstance(payload, dict):
            for key in ("result", "text", "message"):
                value = payload.get(key)
                if isinstance(value, str):
                    return value
        return stdout
    if client == "opencode":
        texts: list[str] = []
        for line in stdout.splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            part = payload.get("part")
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
            elif isinstance(payload.get("text"), str):
                texts.append(payload["text"])
        return "".join(texts) or stdout
    return stdout


def run_eval(
    client: str,
    variants: list[Variant],
    case_ids: list[str] | None = None,
    repeat: int = 1,
    model: str | None = None,
    timeout_seconds: int = 300,
    dry_run: bool = False,
    root: Path = ROOT,
    corpus_path: Path | None = None,
) -> dict[str, Any]:
    if client not in CLIENTS:
        raise ConfigError(f"unsupported eval client: {client}")
    if repeat < 1:
        raise ConfigError("eval repeat must be at least 1")
    selected_corpus_path = corpus_path or root / "evals/cases.json"
    corpus = load_corpus(selected_corpus_path)
    all_cases = {case["id"]: case for case in corpus["cases"]}
    selected_ids = case_ids or list(all_cases)
    unknown = sorted(set(selected_ids) - set(all_cases))
    if unknown:
        raise ConfigError(f"unknown eval cases: {', '.join(unknown)}")

    results: list[dict[str, Any]] = []
    for variant in variants:
        ruleset = variant.ruleset.read_text(encoding="utf-8")
        for case_id in selected_ids:
            case = all_cases[case_id]
            for attempt in range(1, repeat + 1):
                with tempfile.TemporaryDirectory(prefix="ai-console-eval-") as temporary:
                    workspace = Path(temporary)
                    (workspace / ".git").mkdir()
                    _install_ruleset(workspace, client, ruleset)
                    output_file = workspace / "last-message.txt"
                    command = command_for(client, workspace, case["prompt"], output_file, model)
                    record: dict[str, Any] = {
                        "variant": variant.name,
                        "case": case_id,
                        "attempt": attempt,
                        "command": command,
                    }
                    if dry_run:
                        record.update({"status": "planned", "durationSeconds": 0.0})
                    else:
                        started = time.perf_counter()
                        try:
                            completed = subprocess.run(
                                command,
                                cwd=workspace,
                                text=True,
                                capture_output=True,
                                timeout=timeout_seconds,
                                check=False,
                            )
                            duration = time.perf_counter() - started
                            record.update(
                                {
                                    "status": "completed" if completed.returncode == 0 else "failed",
                                    "exitCode": completed.returncode,
                                    "durationSeconds": round(duration, 3),
                                    "output": _extract_output(client, completed.stdout, output_file),
                                    "stdout": completed.stdout,
                                    "stderr": completed.stderr,
                                }
                            )
                        except subprocess.TimeoutExpired as exc:
                            record.update(
                                {
                                    "status": "timeout",
                                    "durationSeconds": float(timeout_seconds),
                                    "stdout": exc.stdout or "",
                                    "stderr": exc.stderr or "",
                                }
                            )
                    results.append(record)
    return {
        "version": 1,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "client": client,
        "model": model,
        "corpus": str(selected_corpus_path),
        "repeat": repeat,
        "dryRun": dry_run,
        "variants": [
            {"name": variant.name, "ruleset": str(variant.ruleset)} for variant in variants
        ],
        "results": results,
    }


def write_run(payload: dict[str, Any], root: Path = ROOT) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = root / "evals/runs" / f"{stamp}-{payload['client']}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination


def ratings_template(run_path: Path, corpus_path: Path | None = None) -> dict[str, Any]:
    run = load_json(run_path)
    corpus = load_corpus(corpus_path or ROOT / "evals/cases.json")
    rubrics = {case["id"]: case["rubric"] for case in corpus["cases"]}
    ratings = []
    for result in run.get("results", []):
        if not isinstance(result, dict):
            continue
        case_id = result.get("case")
        if case_id not in rubrics:
            raise ConfigError(f"run references unknown case: {case_id!r}")
        ratings.append(
            {
                "variant": result.get("variant"),
                "case": case_id,
                "attempt": result.get("attempt"),
                "scores": {criterion: None for criterion in rubrics[case_id]},
                "notes": "",
            }
        )
    return {"version": 1, "run": str(run_path), "ratings": ratings}


def score_run(run_path: Path, ratings_path: Path) -> dict[str, Any]:
    run = load_json(run_path)
    ratings = load_json(ratings_path).get("ratings")
    if not isinstance(ratings, list):
        raise ConfigError("ratings file requires a ratings array")
    result_keys = {
        (item.get("variant"), item.get("case"), item.get("attempt"))
        for item in run.get("results", [])
        if isinstance(item, dict)
    }
    totals: dict[str, list[float]] = {}
    for rating in ratings:
        if not isinstance(rating, dict):
            raise ConfigError("ratings entries must be objects")
        key = (rating.get("variant"), rating.get("case"), rating.get("attempt"))
        if key not in result_keys:
            raise ConfigError(f"rating does not match a run result: {key}")
        scores = rating.get("scores")
        if not isinstance(scores, dict) or not scores:
            raise ConfigError(f"rating {key} requires scores")
        values = list(scores.values())
        if not all(isinstance(value, (int, float)) and 1 <= value <= 5 for value in values):
            raise ConfigError(f"rating {key} scores must all be numbers from 1 to 5")
        totals.setdefault(str(key[0]), []).extend(float(value) for value in values)

    run_results = [item for item in run.get("results", []) if isinstance(item, dict)]
    summary: dict[str, Any] = {}
    for variant in (item["name"] for item in run.get("variants", [])):
        selected = [item for item in run_results if item.get("variant") == variant]
        durations = [
            float(item["durationSeconds"])
            for item in selected
            if isinstance(item.get("durationSeconds"), (int, float))
        ]
        completed = sum(item.get("status") == "completed" for item in selected)
        scores = totals.get(variant, [])
        summary[variant] = {
            "results": len(selected),
            "completionRate": completed / len(selected) if selected else 0.0,
            "meanDurationSeconds": sum(durations) / len(durations) if durations else None,
            "meanRubricScore": sum(scores) / len(scores) if scores else None,
            "scoredCriteria": len(scores),
        }
    return {"version": 1, "run": str(run_path), "summary": summary}
