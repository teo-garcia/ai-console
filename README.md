# ai-console

Central control plane for AI rules, skills, and MCP configs.

## Quick start

1. Edit rule sets in `rulesets/`.
2. Register repos in `registry/repos.json`.
3. Run `scripts/backup-global` to snapshot current global configs.
4. Run `scripts/apply-global` for global instructions, skills, and MCP.
5. Run `scripts/apply-repos` to link repo rules (and optional per-repo MCP).
6. Run `scripts/verify` to validate links and config syntax.

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
- `scripts/apply-global` links global instruction files to `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`, and `~/.gemini/GEMINI.md`.
- `scripts/apply-global` merges `mcp/codex.config.toml` into `~/.codex/config.toml` and writes a backup at `~/.codex/config.toml.bak`.
- `scripts/apply-global` merges Claude Code MCP servers into `~/.claude.json` and preserves the rest of Claude's state file.
- Claude Code commands are linked to `~/.claude/commands/`.
- Gemini MCP config is linked to `~/.gemini/settings.json`.
- `scripts/sync --verify` runs `apply-repos` and then runs `verify`.
- Codex skills must use `<skill-name>/SKILL.md` structure with YAML frontmatter.
- Cursor rules must be `.mdc` files with metadata headers.
- Cursor project MCP is linked at `mcp.json`. This repo no longer treats `~/.cursor/mcp.json` as the source of truth.
- The shared MCP baseline is intentionally limited to `context7`, `chrome-devtools`, `filesystem`, and `postgres`. GitHub MCP is excluded because GUI clients on macOS do not reliably inherit `GITHUB_PERSONAL_ACCESS_TOKEN`.

## What lives here

- `rulesets/`: Rules grouped by set name for each tool.
  - `{ruleset}/codex/AGENTS.md` - Links to repo root as `AGENTS.md` and to `~/.codex/AGENTS.md`
  - `{ruleset}/claude/CLAUDE.md` - Links to repo root as `CLAUDE.md` and to `~/.claude/CLAUDE.md`
  - `{ruleset}/cursor/rules/` - Links to repo `.cursor/rules/` (must be `.mdc` files)
  - `{ruleset}/gemini/GEMINI.md` - Links to repo root as `GEMINI.md` and to `~/.gemini/GEMINI.md`
- `skills/`: Global commands/skills for tools.
  - `claude/` - Custom slash commands (links to `~/.claude/commands/`)
  - `codex/` - Custom skills in `<name>/SKILL.md` format (links to `~/.codex/skills/`)
- `mcp/`: MCP server configurations.
  - `claude.mcp.json` - Claude Code MCP servers, merged into `~/.claude.json` and linked to repo `.mcp.json`
  - `cursor.mcp.json` - Cursor MCP servers, linked to repo `mcp.json`
  - `gemini.settings.json` - Gemini CLI MCP servers, linked to `~/.gemini/settings.json` and repo `.gemini/settings.json`
  - `codex.config.toml` - Codex MCP servers, merged into `~/.codex/config.toml`
- `registry/`: Repository registry mapping repos to rulesets.
- `scripts/`: Symlink management utilities.
