# Ruleset evaluations

This corpus tests system-level agent behavior, not framework knowledge. Each case
uses three human-scored criteria on a 1–5 anchored scale.

Prepare an A/B run without spending model tokens:

```bash
scripts/ai-console eval run --client codex \
  --variant current=rulesets/core/codex/AGENTS.md \
  --variant candidate=/path/to/candidate.md \
  --dry-run
```

Remove `--dry-run` to execute. Runs are written to the ignored `evals/runs/`
directory. The harness uses a temporary, disposable workspace and read-only or
planning modes where each client exposes one. It never enables bypass or auto
approval flags.

Create and fill the ratings template, then score it:

```bash
scripts/ai-console eval ratings-template evals/runs/<run>.json
scripts/ai-console eval score evals/runs/<run>.json \
  evals/runs/<run>.ratings.json
```

Use the same client, model, repeat count, and corpus for both variants. Treat
latency and completion rate as measurements; treat rubric scores as calibrated
human judgments. Keep the raw run artifact when reporting a comparison.
