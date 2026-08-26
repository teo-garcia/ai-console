from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .capabilities import (
    CAPABILITY_CLIENTS,
    format_capability_report,
    resolve_capabilities,
)
from .config import ConfigError, ROOT
from .evals import parse_variants, ratings_template, run_eval, score_run, write_run
from .lifecycle import draft_learning, record_correction
from .mcp import render_all
from .ops import apply_global, apply_repos, backup_global, restore_backup
from .policy import TASK_ROUTES, route_policy
from .rules import render_rules
from .verify import doctor, verify_install, verify_templates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-console")
    subparsers = parser.add_subparsers(dest="command", required=True)

    render = subparsers.add_parser("render", help="render tracked MCP configs")
    render.add_argument("--check", action="store_true", help="fail on generated drift")

    apply_parser = subparsers.add_parser("apply", help="apply managed configuration")
    apply_subparsers = apply_parser.add_subparsers(dest="apply_scope", required=True)
    for scope in ("global", "repos"):
        apply_command = apply_subparsers.add_parser(scope)
        apply_command.add_argument("--dry-run", action="store_true")
        apply_command.add_argument("--force", action="store_true")

    plan = subparsers.add_parser("plan", help="preview managed changes")
    plan.add_argument("scope", choices=("global", "repos", "all"), default="all", nargs="?")

    verify = subparsers.add_parser("verify", help="verify templates or installation")
    verify.add_argument("--scope", choices=("templates", "install", "all"), default="all")
    verify.add_argument("--json", action="store_true", dest="json_output")

    doctor_parser = subparsers.add_parser("doctor", help="diagnose local prerequisites")
    doctor_parser.add_argument("--json", action="store_true", dest="json_output")
    doctor_parser.add_argument("--live", action="store_true")
    doctor_parser.add_argument("--client", choices=CAPABILITY_CLIENTS, default="codex-desktop")
    doctor_parser.add_argument("--repo")

    capability_parser = subparsers.add_parser(
        "capabilities", help="resolve capability implementations and fallbacks"
    )
    capability_parser.add_argument(
        "--client", choices=CAPABILITY_CLIENTS, default="codex-desktop"
    )
    capability_parser.add_argument("--repo")
    capability_parser.add_argument(
        "--with-profile",
        action="append",
        default=[],
        help="preview an additional temporary MCP profile",
    )
    capability_parser.add_argument("--live", action="store_true")
    capability_parser.add_argument("--json", action="store_true", dest="json_output")

    subparsers.add_parser("backup", help="snapshot global installation")
    restore = subparsers.add_parser("restore", help="restore a global snapshot")
    restore.add_argument("timestamp")
    restore.add_argument("--force", action="store_true")

    eval_parser = subparsers.add_parser("eval", help="run and score ruleset evaluations")
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command", required=True)
    eval_run = eval_subparsers.add_parser("run", help="execute or plan an A/B eval")
    eval_run.add_argument("--client", choices=("codex", "claude", "cursor", "opencode"), required=True)
    eval_run.add_argument("--variant", action="append", required=True)
    eval_run.add_argument("--case", action="append", dest="cases")
    eval_run.add_argument("--repeat", type=int, default=1)
    eval_run.add_argument("--model")
    eval_run.add_argument("--timeout", type=int, default=300)
    eval_run.add_argument("--dry-run", action="store_true")
    eval_template = eval_subparsers.add_parser(
        "ratings-template", help="create a human-rating template for a run"
    )
    eval_template.add_argument("run")
    eval_score = eval_subparsers.add_parser("score", help="aggregate calibrated ratings")
    eval_score.add_argument("run")
    eval_score.add_argument("ratings")

    learn = subparsers.add_parser("learn", help="record and review recurring corrections")
    learn_subparsers = learn.add_subparsers(dest="learn_command", required=True)
    learn_record = learn_subparsers.add_parser("record", help="record one correction")
    learn_record.add_argument("correction")
    learn_record.add_argument(
        "--target",
        choices=("rules", "skill", "hook", "test", "mcp", "unsure"),
        default="unsure",
    )
    learn_record.add_argument("--source", default="manual")
    learn_draft = learn_subparsers.add_parser("draft", help="draft repeated corrections for review")
    learn_draft.add_argument("--minimum", type=int, default=2)

    route = subparsers.add_parser("route", help="recommend an abstract model and budget route")
    route.add_argument("--task", choices=tuple(TASK_ROUTES), required=True)
    route.add_argument("--risk", choices=("low", "medium", "high"), required=True)
    return parser


def _print_verifier(result: object, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.payload(), indent=2))
    else:
        for check in result.checks:
            print(f"{check.status}: {check.message}")
        print(
            f"verify: complete (failures={result.failures} warnings={result.warnings})"
        )
    return 1 if result.failures else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "render":
            changed = render_all(ROOT, check=args.check) + render_rules(ROOT, check=args.check)
            if changed:
                action = "drift" if args.check else "rendered"
                for path in changed:
                    print(f"{action}: {path.relative_to(ROOT)}")
                return 1 if args.check else 0
            print("render: up to date")
            return 0
        if args.command == "apply":
            if args.apply_scope == "global":
                apply_global(ROOT, dry_run=args.dry_run, force=args.force)
            else:
                apply_repos(ROOT, dry_run=args.dry_run, force=args.force)
            return 0
        if args.command == "plan":
            if args.scope in {"global", "all"}:
                apply_global(ROOT, dry_run=True)
            if args.scope in {"repos", "all"}:
                apply_repos(ROOT, dry_run=True)
            return 0
        if args.command == "verify":
            template_result = verify_templates(ROOT)
            if args.scope == "templates":
                return _print_verifier(template_result, args.json_output)
            install_result = verify_install(ROOT)
            if args.scope == "install":
                return _print_verifier(install_result, args.json_output)
            template_result.checks.extend(install_result.checks)
            return _print_verifier(template_result, args.json_output)
        if args.command == "doctor":
            return _print_verifier(
                doctor(
                    ROOT,
                    client=args.client,
                    repo_name=args.repo,
                    live=args.live,
                ),
                args.json_output,
            )
        if args.command == "capabilities":
            additional_profiles = tuple(
                profile
                for value in args.with_profile
                for profile in value.split(",")
                if profile
            )
            payload = resolve_capabilities(
                ROOT,
                client=args.client,
                repo_name=args.repo,
                additional_profiles=additional_profiles,
                live=args.live,
            )
            if args.json_output:
                print(json.dumps(payload, indent=2))
            else:
                print(format_capability_report(payload))
            return 0
        if args.command == "backup":
            backup_global(ROOT)
            return 0
        if args.command == "restore":
            restore_backup(
                args.timestamp,
                ROOT,
                dry_run=not args.force,
                force=args.force,
            )
            if not args.force:
                print("restore preview only; rerun with --force to apply")
            return 0
        if args.command == "eval":
            if args.eval_command == "run":
                payload = run_eval(
                    args.client,
                    parse_variants(args.variant),
                    case_ids=args.cases,
                    repeat=args.repeat,
                    model=args.model,
                    timeout_seconds=args.timeout,
                    dry_run=args.dry_run,
                )
                destination = write_run(payload)
                print(f"eval run: {destination}")
                return 0
            if args.eval_command == "ratings-template":
                run_path = Path(args.run).resolve()
                destination = run_path.with_suffix(".ratings.json")
                destination.write_text(
                    json.dumps(ratings_template(run_path), indent=2) + "\n",
                    encoding="utf-8",
                )
                print(f"ratings template: {destination}")
                return 0
            if args.eval_command == "score":
                payload = score_run(Path(args.run).resolve(), Path(args.ratings).resolve())
                print(json.dumps(payload, indent=2))
                return 0
        if args.command == "learn":
            if args.learn_command == "record":
                destination = record_correction(args.correction, args.target, args.source)
                print(f"correction recorded: {destination}")
                return 0
            destination = draft_learning(args.minimum)
            print(f"learning draft: {destination}")
            return 0
        if args.command == "route":
            print(json.dumps(route_policy(args.task, args.risk), indent=2))
            return 0
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
