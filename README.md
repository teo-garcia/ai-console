# ai-console

A portable control plane for Codex, Cursor, Claude Code, and OpenCode. It keeps
the always-on surface small, renders client configs from canonical sources,
installs native lifecycle and agent layers, and makes ruleset changes testable.

## Design

- One lean universal rules source, rendered into each client’s native format.
- One global MCP server (Context7) plus one focused project profile at a time.
- A small general-purpose skill allowlist; deeper playbooks load on demand.
- Tracked logical configuration separated from ignored machine-local bindings.
- Dry-run, backup, restore, doctor, deterministic tests, and CI before mutation.
- Privacy-safe lifecycle notes and human-reviewed learning candidates.
- Client-native hooks, agents, rules metadata, and plugins where formats differ.

## Quick start

```sh
git submodule update --init --recursive
cp registry/repos.local.example.json registry/repos.local.json
```

Edit `registry/repos.local.json` with absolute paths for this machine. Keep
logical repo names, rulesets, and profiles in the tracked `registry/repos.json`.

Then inspect and apply:

```sh
scripts/ai-console doctor
scripts/ai-console plan all
scripts/backup-global
scripts/apply-global
scripts/apply-repos
scripts/verify
```

`apply-global` merges managed Codex, Claude, and hook entries while preserving
unmanaged config. It links artifacts that are fully owned by the console.
Existing non-symlink rule or agent targets are skipped unless `--force` is
explicitly supplied. Directories are never force-replaced.

## Operator commands

```text
scripts/ai-console render [--check]
scripts/ai-console plan global|repos|all
scripts/ai-console apply global|repos [--dry-run] [--force]
scripts/ai-console verify --scope templates|install|all [--json]
scripts/ai-console doctor [--json]
scripts/ai-console backup
scripts/ai-console restore <timestamp> [--force]
scripts/ai-console route --task <class> --risk low|medium|high
scripts/ai-console learn record <correction> --target <layer>
scripts/ai-console learn draft [--minimum 2]
scripts/ai-console eval run ...
scripts/ai-console eval ratings-template <run.json>
scripts/ai-console eval score <run.json> <ratings.json>
```

Legacy convenience wrappers (`apply-global`, `apply-repos`, `backup-global`,
`render`, `restore`, `test`, and `verify`) delegate to the same Python core.

## Rules and skills

Edit `rulesets/core/source.md`, then run `scripts/render`. The renderer produces:

- `rulesets/core/codex/AGENTS.md`
- `rulesets/core/claude/CLAUDE.md`
- `rulesets/core/cursor/rules/core.mdc`, including required Cursor metadata
- `rulesets/core/opencode/AGENTS.md`

The core contains only universal trust, scope, safety, evidence, verification,
and learning policy. Task procedures live in the `engineering-workflows` skill,
whose router loads only the relevant reference for debugging, changes, reviews,
migrations, or architecture decisions.

Globally linked general-purpose skills:

- `engineering-workflows`
- Matt Pocock’s `grill-me`
- Matt Pocock’s `grill-with-docs`

Vendored but not globally linked:

- `vercel-labs/agent-skills`
- `shadcn-ui/ui`
- `shadcn/improve`

Enable `shadcn/improve` only for the task that needs it:

```sh
scripts/toggle-skill enable improve
scripts/toggle-skill status improve
scripts/toggle-skill disable improve
```

Never install `garrytan/gstack` or `obra/superpowers` permanently. Pull either
on demand and remove it after the task.

## MCP configuration

`mcp/canonical.json` is the only hand-edited MCP definition. `scripts/render`
generates global and profile configs for all four clients. Rendered files use
portable executable names (`npx`, `uvx`) and contain no home-directory paths.

| Profile | Capability | Intended use |
| --- | --- | --- |
| `lean` | Context7 only | Default; current library documentation |
| `browser` | Chrome DevTools | DOM, console, network, screenshots, performance |
| `codebase` | Codebase Memory | Indexed structure and impact analysis |
| `memory` | Basic Memory | Durable cross-client Markdown knowledge |
| `semantic` | Serena | Symbol-aware navigation and refactoring |
| `ops` | Datadog | Operational investigation and observability |

Profiles are deliberately mutually exclusive. Choose the smallest profile that
adds a distinct capability instead of composing a permanent tool catalog.

Registry example:

```json
{
  "defaults": {
    "ruleset": "core",
    "mcpProfile": "lean"
  },
  "repos": [
    {
      "name": "my-service",
      "ruleset": "core",
      "mcpProfile": "codebase"
    }
  ]
}
```

Local binding, stored only in ignored `registry/repos.local.json`:

```json
{
  "paths": {
    "my-service": "/absolute/path/on/this/machine"
  }
}
```

The verifier scans canonical, global, and every profile output for machine home
paths and fails on generated drift.

### Datadog authentication

The `ops` profile targets Datadog US5. OAuth credentials remain client-local and
are never committed:

```sh
codex mcp login datadog
cursor-agent mcp login datadog
```

Change the endpoint in `mcp/canonical.json` before rendering if a different
Datadog site is required.

## Lifecycle and learning

`apply-global` installs a small launcher at
`~/.ai-console/bin/ai-console-lifecycle` and merges native adapters:

- Codex: `~/.codex/hooks.json`
- Claude Code: `~/.claude/settings.json`
- Cursor: `~/.cursor/hooks.json`
- OpenCode: `~/.config/opencode/plugins/ai-console-lifecycle.js`

Startup context is capped at 25 lines and contains only repository facts:
branch, dirty-file summary, recent commits, and the previous captured lifecycle
event. Hook failures are advisory and fail open.

Session captures live under `~/.ai-console/sessions/` with mode `0600`. They do
not copy prompts, transcripts, tool output, or full assistant messages. A Stop
hook extracts only a line explicitly formatted as:

```text
AI-CONSOLE-CORRECTION: stable correction to review
```

Corrections can also be recorded manually. `learn draft` groups exact normalized
repeats and writes a review checklist under `~/.ai-console/drafts/`; it never
edits rules, skills, hooks, tests, or MCP configuration and never commits.

## Evaluations

`evals/cases.json` contains twelve client-neutral system-behavior cases with
anchored 1–5 rubrics. The runner supports Codex, Claude, Cursor, and OpenCode,
uses disposable workspaces, and selects read-only or planning modes without
bypass or auto-approval flags.

Example A/B plan (no model call):

```sh
scripts/ai-console eval run --client codex \
  --variant current=rulesets/core/codex/AGENTS.md \
  --variant candidate=/path/to/candidate.md \
  --dry-run
```

Remove `--dry-run` only after choosing a fixed client/model and spend ceiling.
Raw runs are ignored under `evals/runs/`. See `evals/README.md` for calibrated
human scoring.

## Native agents and model policy

The console installs read-only `reviewer` and `planner` agents in each native
format under `agents/{client}/`. Their models are intentionally inherited from
the active client so a tracked file cannot become stale or reference an
unavailable entitlement.

`config/model-policy.json` routes task and risk classes to abstract quality,
reasoning, budget, and checkpoint requirements. Resolve those tiers to current
models in the active client. High-risk routes always require a human checkpoint;
evaluation routes require fixed settings for both variants.

The stable canonical rules prefix plus separately injected volatile brief is
designed to support client prompt caching. Cache benefit remains a measurement,
not an assumption; use repeated-run latency or client-reported metrics.

## Backup and restore

`scripts/backup-global` snapshots managed global files, links, skill directories,
agents, hooks, and OpenCode plugins into ignored `backups/<timestamp>/` with a
machine-readable manifest.

Restore is preview-only unless forced:

```sh
scripts/restore <timestamp>
scripts/restore <timestamp> --force
```

Restore replaces exactly the paths listed in that snapshot’s manifest. Review
the preview before applying it.

## Verification and CI

```sh
scripts/test
scripts/render --check
scripts/verify --scope templates
scripts/verify --scope install
```

The standard-library test suite covers canonical rendering, portability,
registry binding, dry-run immutability, merge preservation, all-client profile
links, lifecycle privacy, learning drafts, native agents, routing, and
backup/restore round trips. `.github/workflows/verify.yml` runs the same core
checks on pushes and pull requests.

Codex hook commands require one-time trust after their definition changes; use
`/hooks` to review them. Relevant native references:

- [Codex hooks](https://learn.chatgpt.com/docs/hooks)
- [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Claude Code hooks](https://code.claude.com/docs/en/hooks)
- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents)
- [OpenCode plugins](https://opencode.ai/docs/plugins/)
- [OpenCode agents](https://opencode.ai/docs/agents)

## Repository layout

- `ai_console/`: standard-library operational core
- `agents/`: native reviewer and planner definitions
- `config/`: targets and abstract model policy
- `evals/`: corpus, scoring instructions, ignored run artifacts
- `hooks/`: native lifecycle adapters
- `mcp/`: canonical and rendered MCP configuration
- `registry/`: tracked logical repos and ignored local bindings
- `rulesets/`: canonical core and rendered client instructions
- `skills/`: console-owned skills and commands
- `vendor/`: pinned third-party skill sources
- `scripts/`: stable operator entry points
