# ai-console

Central control plane for AI rules, skills, and MCP configs.

## Quick start

1. Edit rule sets in `rulesets/`.
2. Register repos in `registry/repos.json`.
3. Run `scripts/backup-global` to snapshot current global configs.
4. Run `scripts/apply-global` for global skills and MCP.
5. Run `scripts/apply-repos` to link repo rules (and optional per-repo MCP).
6. Run `scripts/verify` to validate links and config syntax.

## Registry format

```json
{
  "defaults": {
    "ruleset": "core",
    "claudeMcp": false,
    "geminiMcp": false
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

- `scripts/apply-global` and `scripts/apply-repos` use symlinks. If a target exists and is not a symlink, they will skip it unless you pass `--force`.
- `scripts/apply-global` merges `mcp/codex.config.toml` into `~/.codex/config.toml` and writes a backup at `~/.codex/config.toml.bak`.
- Claude Code commands are linked to `~/.claude/commands/`.
- Gemini MCP config is linked to `~/.gemini/settings.json`.
- `scripts/sync --verify` runs `apply-repos` and then runs `verify`.
- Codex skills must use `<skill-name>/SKILL.md` structure with YAML frontmatter.
- Cursor rules must be `.mdc` files with metadata headers.

## What lives here

- `rulesets/`: Rules grouped by set name for each tool.
  - `{ruleset}/codex/AGENTS.md` - Links to repo root as `AGENTS.md`
  - `{ruleset}/cursor/rules/` - Links to repo `.cursor/rules/` (must be `.mdc` files)
  - `{ruleset}/claude/rules/` - Links to repo `.claude/rules/` (`.md` files)
  - `{ruleset}/gemini/GEMINI.md` - Links to repo root as `GEMINI.md`
- `skills/`: Global commands/skills for tools.
  - `claude/` - Custom slash commands (links to `~/.claude/commands/`)
  - `codex/` - Custom skills in `<name>/SKILL.md` format (links to `~/.codex/skills/`)
- `mcp/`: MCP server configurations.
  - `claude.mcp.json` - Claude Code MCP servers
  - `cursor.mcp.json` - Cursor MCP servers
  - `gemini.settings.json` - Gemini CLI MCP servers
  - `codex.config.toml` - Codex MCP servers (merged into `~/.codex/config.toml`)
- `registry/`: Repository registry mapping repos to rulesets.
- `scripts/`: Symlink management utilities.
