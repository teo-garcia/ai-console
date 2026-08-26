# ai-console

A portable, deliberately small control plane for Codex, Cursor, Claude Code,
and OpenCode. It keeps shared safety rules testable while leaving models,
verbosity, native tools, plugins, and ordinary permissions to each client.

## Design

- One universal rules source, rendered into each client’s native format.
- One lightweight global MCP server (Context7); optional servers stay off.
- A small general-purpose skill allowlist; deeper playbooks load on demand.
- Installed native tools, skills, plugins, apps, and connectors activate on demand.
- Tracked logical configuration separated from ignored machine-local bindings.
- Dry-run, backup, restore, doctor, deterministic tests, and CI before mutation.
- No ambient lifecycle hook or OpenCode plugin at session startup.
- Compact, client-native status lines with a shared information hierarchy.
- Client-native agents and rules metadata where formats differ.

## Quick start

```sh
git submodule update --init --recursive
cp registry/repos.local.example.json registry/repos.local.json
```

Edit `registry/repos.local.json` with absolute paths for this machine. Keep
logical repo names and rulesets in the tracked `registry/repos.json`.

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
scripts/ai-console doctor [--client <client>] [--repo <name>] [--live] [--json]
scripts/ai-console capabilities [--client <client>] [--repo <name>] [--live] [--json]
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

The core contains universal trust, scope, safety, evidence, and verification
policy plus two operational defaults: stay in the active workspace and prefer
native client tools. The `engineering-workflows` skill is reserved for
incidents, complex migrations, consequential architecture decisions, or an
explicit playbook request. Routine coding work should not load it.

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

## Capability resolution

`config/capabilities.json` is a diagnostic inventory, not a runtime router. It
reports native tools, plugins, MCP servers, and CLI fallbacks without activating
them, starting a server, changing a profile, or promising current-session access.

Inspect what a client can use now:

```sh
scripts/ai-console capabilities --client codex-desktop
scripts/ai-console capabilities --client codex-cli --repo ai-console
scripts/ai-console doctor --client codex-cli --repo ai-console
```

Ask for the outcome directly: “test the login flow” or “trace this symbol.” The
rules tell each client to prefer its native capability. Explicit selectors and
MCP profiles are opt-in overrides. `doctor --live` adds bounded TCP reachability
checks; normal doctor and CI remain network-free.

The resolver reports configuration separately from authentication, reachability,
and current-session activation. It never installs or invokes a tool.

Codex MCP output also renders least-surprising approval defaults from the same
policy: Context7 uses `auto`, browser/code-navigation/index/memory servers use
`writes`, and Datadog uses `prompt`. Capability validation fails if its declared
approval or authentication policy drifts from the canonical MCP definition.

## MCP configuration

`mcp/canonical.json` is the only hand-edited MCP definition. `scripts/render`
generates global configs for all four clients. Only remote Context7 is global.
Chrome DevTools, Codebase Memory, Serena, Basic Memory, and Datadog remain
available as opt-in profiles, but none starts in an ordinary session. Serena's
semantic profile relocates its home and per-project data under the user's cache
directory, so activating it does not create repo-local `.serena` directories.
Rendered files contain no fixed home-directory paths.

MCP is only one capability layer. Native client tools, installed skills,
plugins, apps, and connectors remain available on demand even when their tool
schemas are not preloaded into a new session. Ask for the capability naturally;
an explicit client selector such as `@Browser` is an override, not a requirement.

| Internal bundle | Capability | Intended use |
| --- | --- | --- |
| `browser` | Chrome DevTools | DOM, console, network, screenshots, performance |
| `codebase` | Codebase Memory | Indexed structure and impact analysis |
| `memory` | Basic Memory | Durable cross-client Markdown knowledge |
| `semantic` | Serena | Symbol-aware navigation and refactoring |
| `ops` | Datadog | Operational investigation and observability |

These bundles are explicit compatibility fallbacks, not prerequisites for native
client tools. New repository entries should use no MCP overrides:

```json
{
  "defaults": {
    "ruleset": "core",
    "mcpProfiles": []
  },
  "repos": [
    {
      "name": "my-service",
      "ruleset": "core",
      "mcpProfiles": []
    }
  ]
}
```

Legacy `mcpProfile` and `mcpProfiles` keys are still accepted for existing
installations. Duplicate, unknown, or mixed singular/plural selections fail
before anything is applied. Leave `mcpProfiles` empty unless a repository
explicitly needs one optional MCP fallback.

For backwards compatibility, non-empty selections still render portable client
configs under the ignored `mcp/composed/` cache. Applying repositories also
removes the obsolete managed `.claude/rules` link; `CLAUDE.md` remains the
canonical Claude instruction file.

Client implementations intentionally differ:

| Client | Native path |
| --- | --- |
| Codex | `codex plugin`, `/plugins`, `--search`, Browser/Chrome/Computer Use plugins, and built-in subagents |
| Claude Code | Web tools, `--chrome`, `/agents`, `claude plugin`, and classifier-backed `auto` permissions |
| Cursor Agent | Built-in code/web tools, `cursor-agent plugin`, `--auto-review`, optional sandbox, and explicit `--worktree` |
| OpenCode | Built-in web/LSP/skills/agents and `opencode plugin <module>`; there is no `/plugin` slash command |

## Status lines

Status lines prioritize the same information in the same order without adding a
cross-client daemon: model and effort, project and branch, then context. Claude
also shows its native estimated cost and elapsed session time. Cursor's native
footer is retained with running time enabled. OpenCode's built-in footer is
retained because its current TUI schema does not expose status-line composition.

The Claude formatter is event-driven, plain text, and performs only one JSON
parse and one read-only branch lookup per refresh. It has no polling timer and
does not write into a repository.

Worktrees and sandboxes are opt-in. The shared rules do not move ordinary work
out of the active checkout merely to use a subagent or tool.

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

Profiles are compatibility packaging, not a prerequisite the user must name in
their prompt. Bind a profile only for repositories that actually need its MCP
integration; otherwise each client should prefer its native capability.

### Datadog authentication

Datadog is not ambient. If the `ops` profile is deliberately selected,
the endpoint targets US5 and OAuth credentials remain client-local:

```sh
codex mcp login datadog
cursor-agent mcp login datadog
```

Change the endpoint in `mcp/canonical.json` before rendering if a different
Datadog site is required.

## Permissions and lifecycle

`apply-global` sets Claude Code's user-level permission mode to `auto`. Claude's
safety classifier handles routine local actions while explicit `ask` rules keep
human checkpoints for pushes, PR/issue creation, destructive shell commands,
Terraform apply/destroy, and Kubernetes apply/delete. Explicit `deny` rules
protect common environment, secret, SSH, and AWS credential paths. Existing
user permission rules are preserved.

AI-console lifecycle hooks are disabled by default. `apply-global` removes its
old SessionStart/Stop/SessionEnd entries, launcher link, and OpenCode lifecycle
plugin while preserving unrelated hooks and plugins. The `learn` and lifecycle
scripts remain available for explicit operator use, but they do not run when a
client starts.

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

Model, reasoning, effort, and verbosity preferences remain native user settings.
For example, Codex supports `model_verbosity`, but AI-console does not overwrite
it or the existing model selection. Codex multi-agent is enabled by default in
current releases; the shared rules now request delegation when work is genuinely
parallel instead of forcing it for every task.

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
links, disabled startup integrations, native agents, routing, and backup/restore
round trips. `.github/workflows/verify.yml` runs the same core checks on pushes
and pull requests.

Relevant native references:

- [Codex hooks](https://learn.chatgpt.com/docs/hooks)
- [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Claude Code hooks](https://code.claude.com/docs/en/hooks)
- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents)
- [Claude Code permissions](https://code.claude.com/docs/en/permissions)
- [Cursor Agent permissions](https://docs.cursor.com/cli/reference/permissions)
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
