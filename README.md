# ai-console

Central control plane for AI rules, skills, and MCP configs.

## Quick start

1. Run `git submodule update --init --recursive` to fetch the pinned skill sources.
2. Edit rule sets in `rulesets/`.
3. Register repos in `registry/repos.json`.
4. Run `scripts/backup-global` to snapshot current global configs.
5. Run `scripts/apply-global` for global instructions, the general-purpose skill allowlist, and the lean MCP baseline.
6. Choose an `mcpProfile` for each repository.
7. Run `scripts/apply-repos` to link repo rules and the selected MCP profile across Codex, Cursor, Claude Code, and OpenCode.
8. Authenticate OAuth-backed profile servers when needed (see [Datadog authentication](#datadog-authentication)).
9. Run `scripts/verify` to validate links and config syntax.

## Skill sources policy

Only general-purpose reasoning workflows are linked globally:

**Global allowlist**:
- Matt Pocock's `grill-me`
- Matt Pocock's `grill-with-docs`

**Vendored, not linked globally**:
- `vercel-labs/agent-skills`
- `shadcn-ui/ui`
- `shadcn/improve`

Enable `shadcn/improve` across all four clients only while using it:

```sh
scripts/toggle-skill enable improve
scripts/toggle-skill status improve
scripts/toggle-skill disable improve
```

**Do not install permanently**:
- `garrytan/gstack`
- `obra/superpowers`

Never add `garrytan/gstack` or `obra/superpowers` back as permanent skill sources. If a task requires one, pull it on demand and remove it afterwards.

## Datadog authentication

The `ops` MCP profile installs the shared Datadog endpoint, but OAuth credentials are stored by each client and are not committed to this repository. Authenticate Codex and Cursor Agent separately:

```sh
codex mcp login datadog
cursor-agent mcp login datadog
```

Complete each browser flow, restart the clients, and verify the connections:

```sh
codex mcp get datadog
cursor-agent mcp list
cursor-agent mcp list-tools datadog
```

The configured endpoint targets Datadog US5. Anyone using a different Datadog site must update the endpoint before authenticating.

## Registry format

```json
{
  "defaults": {
    "ruleset": "core",
    "mcpProfile": "lean"
  },
  "repos": [
    {
      "path": "/Users/juan.garcia/Desktop/_/dev/projects/templates",
      "ruleset": "core",
      "mcpProfile": "codebase"
    }
  ]
}
```

Available profiles:

- `lean`: Context7 only, inherited from the global baseline.
- `browser`: Chrome DevTools in slim mode.
- `codebase`: Codebase Memory for structural and impact analysis.
- `memory`: Basic Memory for durable, cross-client Markdown knowledge.
- `semantic`: Serena for symbol-aware navigation and refactoring.
- `ops`: Datadog for observability work.

Profiles are deliberately mutually exclusive. Select the smallest tool surface that fits the repository's current work instead of composing a large permanent catalog.

## Notes

- `scripts/apply-global` and `scripts/apply-repos` use symlinks where the destination is meant to be a linked artifact. If a target exists and is not a symlink, they will skip it unless you pass `--force`.
- `scripts/apply-global` links global instruction files to `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`, and `~/.config/opencode/AGENTS.md`.
- `scripts/apply-global` merges `mcp/codex.config.toml` into `~/.codex/config.toml` and writes a backup at `~/.codex/config.toml.bak`.
- `scripts/apply-global` links `mcp/cursor.mcp.json` to `~/.cursor/mcp.json`, which is shared by Cursor and Cursor Agent.
- `scripts/apply-global` links `rulesets/core/opencode/opencode.jsonc` to `~/.config/opencode/opencode.jsonc`.
- `scripts/apply-global` merges Claude Code MCP servers into `~/.claude.json` and preserves the rest of Claude's state file.
- Claude Code commands are linked to `~/.claude/commands/` and portable skills to `~/.claude/skills/`.
- The same allowlisted skills are linked to Codex, Cursor, Claude Code, and OpenCode.
- Matt Pocock's `grill-me` and `grill-with-docs` are included because the upstream README identifies them as its most popular skills.
- `scripts/apply-global` removes only managed symlinks for non-global Vercel and shadcn skills; it never deletes unmanaged skill directories.
- `scripts/apply-repos` links repo rules and one project-scoped MCP profile for every client. Codex and OpenCode share the repository-root `AGENTS.md` policy surface.
- Serena is pinned to a reviewed upstream revision and runs through `uvx`. Codex uses `--context=codex`, Claude Code uses `--context=claude-code`, and Cursor and OpenCode use `--context=ide`.
- Codebase Memory is pinned to npm package `codebase-memory-mcp@0.9.0`; `npx` downloads its platform binary on first start.
- Basic Memory is pinned to `0.22.1` and remains project-selected rather than global; all clients use the same local knowledge store configured by Basic Memory.
- Chrome DevTools MCP is pinned to `1.2.0` and uses its slim tool surface.
- `scripts/sync --verify` runs `apply-repos` and then runs `verify`.
- Codex and OpenCode skills must use `<skill-name>/SKILL.md` structure with YAML frontmatter.
- Cursor rules must be `.mdc` files with metadata headers.
- Cursor MCP is linked globally at `~/.cursor/mcp.json`; project profiles use `.cursor/mcp.json`.
- The shared global MCP baseline is Context7 only. Filesystem and the archived PostgreSQL reference server are intentionally excluded.
- GitHub MCP remains excluded because the native `git` and `gh` tools cover the common workflow with a smaller tool surface.

## What lives here

- `rulesets/`: Rules grouped by set name for each tool.
  - `{ruleset}/codex/AGENTS.md` - Links to repo root as `AGENTS.md` and to `~/.codex/AGENTS.md`
  - `{ruleset}/claude/CLAUDE.md` - Links to repo root as `CLAUDE.md` and to `~/.claude/CLAUDE.md`
  - `{ruleset}/cursor/rules/` - Links to repo `.cursor/rules/` (must be `.mdc` files)
  - `{ruleset}/opencode/AGENTS.md` - Links to repo root as `AGENTS.md` and to `~/.config/opencode/AGENTS.md`
- `skills/`: Global commands/skills for tools.
  - `claude/` - Custom slash commands (links to `~/.claude/commands/`)
  - `codex/` - Custom skills in `<name>/SKILL.md` format (links to `~/.codex/skills/`)
  - `opencode/` - Custom skills in `<name>/SKILL.md` format (links to `~/.config/opencode/skills/`)
- `vendor/`: Pinned third-party skill sources; only the global allowlist is linked automatically.
- `mcp/`: MCP server configurations.
  - `claude.mcp.json` - Lean Claude Code baseline merged into `~/.claude.json`
  - `cursor.mcp.json` - Lean Cursor baseline linked to `~/.cursor/mcp.json`
  - `codex.config.toml` - Lean Codex baseline merged into `~/.codex/config.toml`
  - `profiles/` - Project-scoped MCP configurations for all four clients
  - `rulesets/core/opencode/opencode.jsonc` - Lean OpenCode baseline linked to `~/.config/opencode/opencode.jsonc`
- `registry/`: Repository registry mapping repos to rulesets.
- `scripts/`: Symlink management utilities.
