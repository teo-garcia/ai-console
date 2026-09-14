# ai-console

A portable, deliberately small control plane for Codex, Cursor, Claude Code,
and OpenCode. It keeps shared safety rules testable while leaving models,
verbosity, native tools, plugins, and ordinary permissions to each client.

## Design

- One universal rules source, rendered into each client’s native format.
- One global capability baseline, with plugin-owned MCP duplicates suppressed.
- A small general-purpose skill allowlist; deeper playbooks load on demand.
- Installed native tools, skills, plugins, apps, and connectors activate on demand.
- Tracked logical configuration separated from ignored machine-local bindings.
- Dry-run, backup, restore, doctor, deterministic tests, and CI before mutation.
- No ambient lifecycle hook; OpenCode loads only the explicitly managed goal plugin.
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

## Standardized plugins

`config/plugins.json` records the minimal selected plugin set and MCP ownership.
Provider precedence applies only after the task has been mapped to a capability:
within that capability, prefer a sufficient native provider, then an installed
plugin, MCP, and CLI fallback. A standardized capability does not imply installing
the same package everywhere. An enabled plugin wins over a duplicate standalone
MCP when the plugin owns that integration.

The selected baseline is client-specific and user-scoped:

| Client | Selected plugins | Why |
| --- | --- | --- |
| Codex | Runtime Browser, Chrome, Computer Use; curated GitHub | Lazy bundles supplied by Codex; Datadog and CircleCI fall back to MCP because the account administrator blocks their curated plugins |
| Claude Code | `typescript-lsp`, Context7, Chrome DevTools, Datadog, Atlassian | Official user-scope plugins replace four duplicate standalone MCP registrations and add focused skills where available |
| Cursor | Context7 installed; Chrome Devtools for Agents, Datadog, Atlassian, CircleCI selected | Context7 replaces its MCP now; the four reviewed marketplace packages remain optional because working MCP fallbacks are already global |
| OpenCode | `opencode-goal-plugin@0.8.2`; Herdr state reporter | No verified ecosystem plugin replaces these five MCPs; Herdr reports pane state without repository files |

Claude's installed plugins own Context7, Chrome DevTools, Datadog, and Atlassian,
so only CircleCI remains in the applied Claude MCP config. Cursor's installed
Context7 plugin owns that integration; the four selected marketplace plugins do
not suppress their MCP fallbacks until installation is verified locally. Datadog's
Claude hooks run only after visualization tools and at
session end; they are not an ambient prompt payload. Authentication stays lazy
and client-local.

Codex uses one MCP configuration for Desktop, CLI, and IDE, but Codex plugins are
not available in the IDE. The five MCP entries therefore remain in the shared
config: Desktop/CLI prefer native or installed plugins, and the IDE retains
working fallbacks. Curated Datadog and CircleCI plugins exist in the catalog but
are disabled by this account's administrator.

The cross-client goal contract is:

| Client | Implementation |
| --- | --- |
| Codex | Native `/goal`; the stable `goals` feature remains enabled |
| Claude Code | Native `/goal` with its session-scoped evaluator |
| Cursor Agent | Native `/goal`; `/loop` remains available for scheduled check-ins |
| OpenCode | Pinned `opencode-goal-plugin@0.8.2` and a native-looking `/goal` command |

OpenCode normally persists this plugin under `.opencode/goals`. The managed
configuration sets `persistState: false`, so it keeps active session state in
memory and never creates goal files in repositories. The package loads at
OpenCode startup but does not auto-continue unless `/goal` is active. OpenCode
installs configured npm plugins into its user cache with Bun; no project package
or repository-local plugin directory is created.

Use the same outcome-oriented prompt in each CLI:

```text
/goal Complete <objective> until <verifiable stopping condition>.
```

The mapping follows the official [Codex goal](https://learn.chatgpt.com/use-cases/follow-goals),
[Claude goal](https://code.claude.com/docs/en/goal),
[Cursor goal](https://prod.cursor.com/docs/agent/overview), and
[OpenCode plugin](https://opencode.ai/docs/plugins) contracts. The OpenCode
implementation is pinned to the reviewed
[`opencode-goal-plugin`](https://github.com/willytop8/OpenCode-goal-plugin)
release instead of floating to the latest package at session startup.

## Capability resolution

`config/capabilities.json` reports native tools, plugins, MCP servers, and CLI
fallbacks without invoking a tool or promising authentication or current-session
access. Selection is ranked by capability kind instead of JSON list order, so an
enabled plugin cannot accidentally lose to a duplicate MCP merely because the
MCP was declared first. Reports show lower-priority active implementations as
shadowed and warn when a plugin and the MCP it supersedes are both active.

Inspect what a client can use now:

```sh
scripts/ai-console capabilities --client codex-desktop
scripts/ai-console capabilities --client codex-cli --repo ai-console
scripts/ai-console doctor --client codex-cli --repo ai-console
```

Ask for the outcome directly: “test the login flow” or “trace this symbol.” The
rules tell each client to prefer its native capability or installed plugin, then
the globally configured MCP fallback. No profile name is required. Explicit
selectors are optional overrides. `doctor --live` adds bounded TCP reachability
checks; normal doctor and CI remain network-free.

The resolver reports configuration separately from authentication, reachability,
and current-session activation. It never installs or invokes a tool. Serena and
Codebase Memory were evaluated and retired after neither was naturally selected,
both added cold-start/cache cost, and neither improved the successful native
result. The measured decision is preserved in
`docs/plans/capability-pilot-2026-09-14.md`.

The inventory is outcome-oriented and preserves each client's native path:
Claude web and optional LSP plugins, Cursor code intelligence and built-in review,
OpenCode web/custom tools and in-process plugins, and Codex plugin bundles and
connectors. Skills and subagents are represented as lazy native capabilities;
worktree isolation remains task-specific rather than a global default.

Plugin discovery is local and client-specific. Codex manifests, Claude plugin
settings/manifests, Cursor Plugin and Agent Plugin manifests, and OpenCode file or
package plugins are reported under the same `discoveredPlugins` field. Discovery
does not load plugin code, contact a marketplace, or enable anything.
The client-specific claims track the current official documentation for
[Codex plugins](https://learn.chatgpt.com/docs/plugins),
[Claude extensions](https://code.claude.com/docs/en/features-overview),
[Cursor customization](https://prod.cursor.com/docs/customize-cursor), and
[OpenCode tools](https://opencode.ai/docs/tools).

Codex MCP output also renders least-surprising approval defaults from the same
policy: Context7 uses `auto`, Chrome DevTools and GitHub use `writes`, and remote
service integrations use `prompt`. Capability validation fails if its declared
approval or authentication policy drifts from the canonical MCP definition.

## MCP configuration

`mcp/canonical.json` is the only hand-edited MCP definition. `scripts/render`
generates a global baseline for all four clients: Context7, Chrome DevTools,
Datadog, Atlassian, and CircleCI. The tracked outputs deliberately retain all
five portable fallbacks. `scripts/apply-global` then discovers enabled plugins on
the current computer and suppresses only the MCPs those plugins are proven to
own. On this computer, Claude receives only CircleCI, Cursor receives every MCP
except Context7, and OpenCode receives all five. Codex retains all five because
its shared config also serves the plugin-less IDE; Desktop and CLI still prefer
their native or installed plugins.
Rendered files contain no fixed home-directory paths or credentials. OAuth and
service approval stay client-local.

On another computer, clone the repository and run `scripts/apply-global`: every
fallback is immediately available even if no marketplace plugin has been
installed. Install any optional client plugin later and rerun the same command;
only its now-redundant MCP is removed. No capability profile or repository-local
state is required.

GitHub is immediately available through Codex's installed GitHub plugin and the
authenticated `gh` CLI in every client. The hosted GitHub MCP is not baseline:
live client checks showed that its endpoint requires a PAT header or a host-owned
OAuth app, so generic MCP OAuth fails in Claude, Cursor, and OpenCode. AI-console
does not copy a GitHub token into generated configuration merely to force MCP
packaging.

MCP is only one capability layer. Native client tools, installed skills,
plugins, apps, and connectors remain available on demand even when their tool
schemas are not preloaded into a new session. Ask for the capability naturally;
an explicit client selector such as `@Browser` is an override, not a requirement.

These integrations are configured globally, but clients invoke tools only when
the task needs them. A remote service may request one-time OAuth or server
approval on first use. Chrome DevTools can launch its own isolated browser; a
signed-in existing Chrome session still uses the client's native integration
where supported. New repository entries need no MCP overrides:

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

The generic `mcpProfile` and `mcpProfiles` mechanism remains available for a
future project-specific target or authority boundary, but this repository ships
no named profiles. Duplicate, unknown, or mixed singular/plural selections fail
before anything is applied. Normal repositories leave `mcpProfiles` empty.

For backwards compatibility, non-empty selections still render portable client
configs under the ignored `mcp/composed/` cache. Applying repositories also
removes the obsolete managed `.claude/rules` link; `CLAUDE.md` remains the
canonical Claude instruction file.

Client implementations intentionally differ:

| Client | Native path |
| --- | --- |
| Codex | `codex plugin add`, `/plugins`, `--search`, Browser/Chrome/Computer Use plugins, and built-in subagents |
| Claude Code | Web tools, `--chrome`, `/agents`, official marketplace plugins, and classifier-backed `auto` permissions |
| Cursor Agent | Built-in code/web tools, Customize or IDE `/add-plugin`, `--auto-review`, optional sandbox, and explicit `--worktree` |
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

The verifier scans canonical, global, and any future profile output for machine
home paths and fails on generated drift.

Profiles are reserved infrastructure for future project-specific targets or
authority—not a prerequisite the user must name in a prompt. The normal baseline
is global.

Herdr is a separate cross-client terminal orchestrator, not an MCP server. The
shared rules tell every client it is available for persistent workspaces,
coordinated panes, agent sessions, worktrees, and handoffs when that complexity
materially helps. OpenCode's global `herdr-agent-state` plugin only synchronizes
working, blocked, and idle state with the owning pane; it does not replace the
Herdr CLI or write repository state. Ordinary single-agent work stays direct.

PostgreSQL is intentionally not a global MCP integration. The former MCP project
server is archived, database targets and credentials are project-specific, and
the local `psql` fallback is used only after the user names an authorized target
with least-privilege credentials. Add a database MCP later only as a target-bound,
reviewed profile—not as ambient global context.

### Datadog authentication

Datadog targets US5. Authentication remains client-local, so first use may
require the active client's plugin setup or MCP login:

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
registry binding, dry-run immutability, merge preservation, global all-client
integrations, generic scoped overrides, native agents, routing, and backup/restore
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
