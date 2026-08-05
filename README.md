# ai-console

Central control plane for AI rules, skills, and MCP configs.

## Quick start

1. Edit rule sets in `rulesets/`.
2. Register repos in `registry/repos.json`.
3. Run `scripts/backup-global` to snapshot current global configs.
4. Run `scripts/apply-global` for global instructions, skills, and MCP.
5. Run `scripts/apply-repos` to link repo rules (and optional per-repo MCP).
6. Authenticate OAuth-backed MCP servers (see [Datadog authentication](#datadog-authentication)).
7. Run `scripts/verify` to validate links and config syntax.

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
    "claudeMcp": true,
    "geminiMcp": true
  },
  "repos": [
    {
      "path": "/Users/juan.garcia/Desktop/_/dev/projects/templates",
      "ruleset": "core",
      "claudeMcp": true,
      "geminiMcp": true
    }
  ]
}
```

## Notes

- `scripts/apply-global` and `scripts/apply-repos` use symlinks where the destination is meant to be a linked artifact. If a target exists and is not a symlink, they will skip it unless you pass `--force`.
- `scripts/apply-global` links global instruction files to `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`, and `~/.gemini/GEMINI.md`.
- `scripts/apply-global` merges `mcp/codex.config.toml` into `~/.codex/config.toml` and writes a backup at `~/.codex/config.toml.bak`.
- `scripts/apply-global` links `mcp/cursor.mcp.json` to `~/.cursor/mcp.json`, which is shared by Cursor and Cursor Agent.
- `scripts/apply-global` links `rulesets/core/opencode/opencode.jsonc` to `~/.config/opencode/opencode.jsonc`.
- `scripts/apply-global` merges Claude Code MCP servers into `~/.claude.json` and preserves the rest of Claude's state file.
- Claude Code commands are linked to `~/.claude/commands/`.
- OpenCode skills are linked to `~/.config/opencode/skills/`.
- Gemini MCP config is linked to `~/.gemini/settings.json`.
- Serena is included in the shared MCP baseline via `uvx`. Codex and OpenCode use Serena with `--context codex`; Claude Code, Cursor, and Gemini use `--context ide-assistant`.
- `scripts/sync --verify` runs `apply-repos` and then runs `verify`.
- Codex and OpenCode skills must use `<skill-name>/SKILL.md` structure with YAML frontmatter.
- Cursor rules must be `.mdc` files with metadata headers.
- Cursor MCP is linked globally at `~/.cursor/mcp.json` and per repository at `mcp.json`.
- The shared MCP baseline is `context7`, `datadog`, `chrome-devtools`, `filesystem`, `serena`, and `postgres`. Datadog MCP uses the US5 endpoint at `https://mcp.us5.datadoghq.com/api/unstable/mcp-server/mcp`; GitHub MCP is excluded because GUI clients on macOS do not reliably inherit `GITHUB_PERSONAL_ACCESS_TOKEN`.

## What lives here

- `rulesets/`: Rules grouped by set name for each tool.
  - `{ruleset}/codex/AGENTS.md` - Links to repo root as `AGENTS.md` and to `~/.codex/AGENTS.md`
  - `{ruleset}/claude/CLAUDE.md` - Links to repo root as `CLAUDE.md` and to `~/.claude/CLAUDE.md`
  - `{ruleset}/cursor/rules/` - Links to repo `.cursor/rules/` (must be `.mdc` files)
  - `{ruleset}/opencode/AGENTS.md` - Links to repo root as `AGENTS.md` and to `~/.config/opencode/AGENTS.md`
  - `{ruleset}/gemini/GEMINI.md` - Links to repo root as `GEMINI.md` and to `~/.gemini/GEMINI.md`
- `skills/`: Global commands/skills for tools.
  - `claude/` - Custom slash commands (links to `~/.claude/commands/`)
  - `codex/` - Custom skills in `<name>/SKILL.md` format (links to `~/.codex/skills/`)
  - `opencode/` - Custom skills in `<name>/SKILL.md` format (links to `~/.config/opencode/skills/`)
- `mcp/`: MCP server configurations.
  - `claude.mcp.json` - Claude Code MCP servers, merged into `~/.claude.json` and linked to repo `.mcp.json`
  - `cursor.mcp.json` - Cursor MCP servers, linked to `~/.cursor/mcp.json` and repo `mcp.json`
  - `gemini.settings.json` - Gemini CLI MCP servers, linked to `~/.gemini/settings.json` and repo `.gemini/settings.json`
  - `codex.config.toml` - Codex MCP servers, merged into `~/.codex/config.toml`
  - `rulesets/core/opencode/opencode.jsonc` - OpenCode config, linked to `~/.config/opencode/opencode.jsonc`
- `registry/`: Repository registry mapping repos to rulesets.
- `scripts/`: Symlink management utilities.
