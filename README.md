# ai-console

Central control plane for AI rules, skills, and MCP configs.

## Quick start

1. Run `git submodule update --init --recursive` to fetch the pinned skill sources.
2. Edit rule sets in `rulesets/`.
3. Register repos in `registry/repos.json`.
4. Run `scripts/backup-global` to snapshot current global configs.
5. Run `scripts/apply-global` for global instructions, portable skills, and MCP.
6. Run `scripts/apply-gstack` for gstack's generated skills and runtime.
7. Run `scripts/apply-repos` to link repo rules (and optional per-repo MCP).
8. Authenticate OAuth-backed MCP servers (see [Datadog authentication](#datadog-authentication)).
9. Run `scripts/verify` to validate links and config syntax.

## Datadog authentication

`scripts/apply-global` installs the shared Datadog MCP endpoint, but OAuth credentials are stored by each client and are not committed to this repository. Authenticate Codex and Cursor Agent separately:

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
    "claudeMcp": true
  },
  "repos": [
    {
      "path": "/Users/juan.garcia/Desktop/_/dev/projects/templates",
      "ruleset": "core",
      "claudeMcp": true
    }
  ]
}
```

## Notes

- `scripts/apply-global` and `scripts/apply-repos` use symlinks where the destination is meant to be a linked artifact. If a target exists and is not a symlink, they will skip it unless you pass `--force`.
- `scripts/apply-global` links global instruction files to `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`, and `~/.config/opencode/AGENTS.md`.
- `scripts/apply-global` merges `mcp/codex.config.toml` into `~/.codex/config.toml` and writes a backup at `~/.codex/config.toml.bak`.
- `scripts/apply-global` links `mcp/cursor.mcp.json` to `~/.cursor/mcp.json`, which is shared by Cursor and Cursor Agent.
- `scripts/apply-global` links `rulesets/core/opencode/opencode.jsonc` to `~/.config/opencode/opencode.jsonc`.
- `scripts/apply-global` merges Claude Code MCP servers into `~/.claude.json` and preserves the rest of Claude's state file.
- Claude Code commands are linked to `~/.claude/commands/` and portable skills to `~/.claude/skills/`.
- Portable skills are linked to Codex, Cursor, Claude Code, and OpenCode from the pinned sources under `vendor/`.
- Matt Pocock's `grill-me` and `grill-with-docs` are included because the upstream README identifies them as its most popular skills.
- Superpowers provides the shared `test-driven-development` skill; the duplicate from Addy Osmani's pack is intentionally not linked.
- `scripts/apply-gstack` uses gstack's native generators for Claude Code, Codex, Cursor, and OpenCode.
- Serena is pinned to a reviewed upstream revision and runs through `uvx`. Codex uses `--context=codex`, Claude Code uses `--context=claude-code`, and Cursor and OpenCode use `--context=ide`.
- Codebase Memory is pinned to npm package `codebase-memory-mcp@0.9.0`; `npx` downloads its platform binary on first start.
- `scripts/sync --verify` runs `apply-repos` and then runs `verify`.
- Codex and OpenCode skills must use `<skill-name>/SKILL.md` structure with YAML frontmatter.
- Cursor rules must be `.mdc` files with metadata headers.
- Cursor MCP is linked globally at `~/.cursor/mcp.json` and per repository at `mcp.json`.
- The shared MCP baseline is `context7`, `datadog`, `chrome-devtools`, `filesystem`, `serena`, `codebase-memory`, and `postgres`. Datadog MCP uses the US5 endpoint at `https://mcp.us5.datadoghq.com/api/unstable/mcp-server/mcp`; GitHub MCP is excluded because GUI clients on macOS do not reliably inherit `GITHUB_PERSONAL_ACCESS_TOKEN`.

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
- `vendor/`: Pinned Git submodules for third-party skill collections and gstack's runtime.
- `mcp/`: MCP server configurations.
  - `claude.mcp.json` - Claude Code MCP servers, merged into `~/.claude.json` and linked to repo `.mcp.json`
  - `cursor.mcp.json` - Cursor MCP servers, linked to `~/.cursor/mcp.json` and repo `mcp.json`
  - `codex.config.toml` - Codex MCP servers, merged into `~/.codex/config.toml`
  - `rulesets/core/opencode/opencode.jsonc` - OpenCode config, linked to `~/.config/opencode/opencode.jsonc`
- `registry/`: Repository registry mapping repos to rulesets.
- `scripts/`: Symlink management utilities.
