## Codex

Respect Codex-specific constraints and response style. Share only the solution below, aligned with the same structure used across the other LLM variants.

## Claude

Respect Claude-specific constraints and response style. Share only the solution below, aligned with the same structure used across the other LLM variants.

# Project Improvement Solution

## Given

- The repository is a control plane for AI tool rules, skills, and MCP configuration across four clients (Claude, Cursor, OpenCode, Codex).
- Operational logic lives in Bash with embedded Python for JSON and TOML manipulation.
- Four MCP config files maintain the same server set with minor per-tool variations, all hand-maintained in parallel.
- Machine-specific absolute paths (`/Users/juan.garcia`, `postgresql://...`) are tracked in version control.
- Rule content is duplicated verbatim across `CLAUDE.md`, `AGENTS.md`, and `core.mdc`.
- No schema validation, no dry-run, no drift detection, no test suite, no CI.

## Constraints

- This is an orchestration CLI, not a product. Correctness and maintainability outweigh performance.
- The migration must not break current operator workflows during cutover.
- Machine-local values must be cleanly separated from tracked configuration.
- The solution must be buildable as a self-contained binary requiring no runtime environment at the operator's machine.

## Solution

### 1. Rebuild the operational layer as a typed CLI in Go

Replace `scripts/` with a single compiled binary. Go is the correct choice: no runtime dependency, strong types, `encoding/json` and a TOML library in the dependency tree, and first-class support for the filesystem operations this tool performs.

Retain the existing Bash scripts as thin wrappers that delegate to the binary during the transition window.

Recommended command surface:

- `ai-console apply global [--force] [--dry-run]`
- `ai-console apply repos [--force] [--dry-run]`
- `ai-console render [--dry-run]`
- `ai-console plan [global|repos|all]`
- `ai-console verify [--json]`
- `ai-console doctor [--json]`
- `ai-console backup`
- `ai-console backup restore <timestamp>`
- `ai-console list repos [--json]`
- `ai-console list rulesets [--json]`

### 2. Introduce one canonical MCP model

Replace the four hand-maintained MCP config files with a single source definition and a render step.

```
mcp/
  canonical.json        # server definitions + per-tool profiles with ${VAR} placeholders
  local.json            # machine-local var bindings; git-ignored
  local.example.json    # template for local.json
```

Profile blocks in `canonical.json` bind profile-specific vars (e.g., `SERENA_CONTEXT=ide-assistant` vs `codex`). `local.json` binds machine-specific vars (`FILESYSTEM_ALLOWED_DIR`, `POSTGRES_URL`). Render fails explicitly on any unresolved variable.

`ai-console render` writes the four tool-specific files from this model. Until cutover is validated, generated files remain checked in. After validation, git-ignore them.

### 3. Eliminate ruleset duplication

`CLAUDE.md`, `AGENTS.md`, and `core.mdc` are identical content. `core.mdc` adds only a YAML front-matter block.

Replace with:

```
rulesets/core/
  _source.md            # single source of truth for rule content
  templates/
    claude.tmpl
    codex.tmpl
    cursor.tmpl         # adds YAML front-matter wrapper
```

`ai-console render` generates per-tool ruleset files from `_source.md`. A pre-commit hook or CI check on generated file drift prevents stale copies.

### 4. Split tracked config from machine-local config

`registry/repos.json` currently embeds absolute paths. Move path bindings to `registry/repos.local.json` (git-ignored). The tracked file holds only defaults and named entries without paths.

This directly resolves the `verify` warning about `/Users/` paths in tracked files.

### 5. Make all mutating commands inspectable

- `plan` computes the full operation set without touching the filesystem.
- `--dry-run` on `apply` and `render` prints operations without executing them.
- `--json` on `verify`, `doctor`, and `list` enables machine-parseable output.
- Stable exit codes: 0 success, 1 validation failure, 2 config error, 3 system error.

`doctor` extends `verify`: checks for missing binaries (`npx`, `uvx`), broken symlinks, repos registered but not present on disk, and unresolved variables in `canonical.json` given the current `local.json`.

### 6. Add executable verification and CI

- Unit tests for canonical render (golden files per profile and format).
- Integration tests using `t.TempDir()` for symlink and merge behavior, covering force semantics and dry-run accuracy.
- CI runs `go vet`, `go test ./...`, and `ai-console verify` on every push.

Recommended module layout:

```
cmd/ai-console/
internal/
  config/       # types, load, path expansion
  render/       # canonical -> tool-specific formats
  linker/       # symlink and merge operations
  verify/       # validation checks
  backup/       # snapshot and restore
testdata/
  canonical.json
  local.json
  golden/
```

## Verification

- Rendered outputs are byte-stable for identical inputs (confirmed by golden tests).
- `local.json` values do not appear in tracked files (enforced by `verify`).
- Existing Bash workflows remain functional through compatibility wrappers.
- `doctor` correctly identifies a fresh checkout with no `local.json` and explains what is missing.
- `backup restore` returns the system to the state captured at the snapshot timestamp.

## Risks / Assumptions

- Assumption: Go toolchain is present on the development machine.
- Risk: `repos.local.json` must be introduced after the Go CLI ships. The existing Bash scripts will not read it. Sequence matters: ship the CLI before splitting the registry.
- Risk: ruleset template rendering adds a render dependency. Contributors editing `_source.md` must run `ai-console render` before committing. A CI drift check on generated files eliminates this class of error.
- Risk: `render` overwrites `mcp/claude.mcp.json` and siblings. Keep generated files in version control until the team has validated render output across a full cycle, then git-ignore them.

## Recommended Migration Order

1. Add `mcp/canonical.json` and `mcp/local.json` (git-ignored). Keep existing hand-maintained files unchanged.
2. Implement `internal/config`, `internal/render`, and `ai-console render` with golden tests.
3. Implement read-only commands: `plan`, `verify`, `doctor`, `list`.
4. Implement `apply global` and `apply repos` with `--dry-run`. Add integration tests.
5. Implement `backup` and `backup restore`.
6. Split `registry/repos.json` -- add `repos.local.json` support in the CLI before removing paths from the tracked file.
7. Add `_source.md` + ruleset templates; run render to regenerate ruleset files; delete duplicates.
8. Add CI. Replace Bash scripts with thin wrappers calling the binary.
9. Git-ignore the generated MCP config files once render output is validated across a full cycle.

## Composer 2

Respect Composer 2-specific constraints and response style. Share only the solution below, aligned with the same structure used across the other LLM variants.

# Project Improvement Solution

## Given

- The repository is a control plane for rules, skills, and MCP config across Codex, Claude, Cursor, and OpenCode.
- Behavior is split across Bash entry points, duplicated inline Python for JSON load and merge, and awk-based stripping of Codex TOML `[mcp_servers.*]` blocks before append.
- `config/targets.json` and `registry/repos.json` are validated only lightly (`json.tool` in verify); no schema, no dry-run, no shared library for path expansion or symlink policy.
- `verify` couples template checks to this repo’s own symlinks under the operator’s home layout, which is awkward for CI and other machines.
- No `pyproject.toml`, test suite, or CI workflow.

## Constraints

- Orchestration tool, not a shipped product: prioritize correctness, inspectability, and small incremental diffs over a single big-bang rewrite.
- Operator workflows (`scripts/apply-global`, `apply-repos`, `verify`, `backup`) should keep working during migration; thin wrappers are acceptable.
- Raw runtime performance of symlink and small-file I/O is not the bottleneck; faster feedback (validation, plan/dry-run) and safe behavior at scale matter more.

## Solution

### 1. One Python package as the operational core, Bash as shims

Consolidate `apply-global`, `apply-repos`, `backup-global`, `verify`, and `sync` into a single module (for example `src/ai_console/` or `python/ai_console/`) invoked as `python -m ai_console …`. Keep existing `scripts/*` as one-line `exec` wrappers to the same entry point.

Use `typer` or `argparse` with subcommands: `apply global`, `apply repos`, `backup`, `verify`, `sync`. Optional `--json` on verify and list-style commands for automation.

Rationale: the repo already depends on `python3` for JSON and merges; a typed Python layer removes triplicated `load_targets`-style logic without forcing a Go toolchain on every contributor.

### 2. Replace awk Codex TOML merge with a real TOML library

Parse `~/.codex/config.toml` (and repo equivalents if any) with `tomlkit` or `rtoml`, remove or replace the `mcp_servers` subtree, merge in `mcp/codex.config.toml`, write back. Add unit tests with fixture files covering multiple tables and edge cases.

This directly addresses the highest-risk maintenance point in the current shell implementation.

### 3. Typed config loading and a single implementation of symlink rules

Load `config/targets.json` and `registry/repos.json` with Pydantic models or `jsonschema`. Centralize `~` expansion, `--force` semantics, and “skip if exists and not a symlink” in one linker module so `apply-global` and `apply-repos` cannot drift.

Add `--dry-run` that prints planned operations without mutating the filesystem.

### 4. Split `verify` into portable vs machine-local checks

- **Templates** (or `verify repo`): JSON/TOML validity, placeholder tokens, presence of `rulesets/core/*`, MCP templates under `mcp/`. Suitable for CI on any runner.
- **Install** (or `verify home`): optional pass that resolves `targets.json` and checks symlinks under `$HOME` / registered repos, similar to today’s self-referential checks.

### 5. Tests and CI before optional compilation

- `pytest` for JSON merge (Claude `mcpServers`), TOML merge, path expansion, and linker decision tables.
- Golden files for small render or merge outputs if you add generation later.

Add CI: lint (`ruff`), `pytest`, and `verify` using the templates-only mode so it does not assume this checkout is already linked on the runner.

### 6. Canonical MCP and ruleset generation (later, if duplication hurts)

The Go proposals’ `canonical.json` plus `render` step is compatible with a Python CLI; defer until maintaining four MCP files becomes painful. Same for single `_source.md` to regenerate `CLAUDE.md` / `AGENTS.md` / `core.mdc`.

### 7. Scale and performance only when measured

If `registry/repos.json` grows large, parallelize independent `link` operations with a bounded worker pool and aggregate errors. Until then, avoid complexity.

### 8. Go or Rust (optional later)

If you later need a single static binary with zero runtime, port the tested Python semantics to Go or Rust. The migration path above keeps behavior specified in tests first so a rewrite is verification-driven rather than speculative.

## Verification

- `pytest` passes for merge, expand_path, and symlink policy.
- `ai-console apply global --dry-run` matches actual applies on a temp HOME fixture.
- Codex TOML merge round-trips fixtures without corrupting non-`mcp_servers` sections.
- CI runs templates-only verify green on a clean clone without symlinks.

## Risks / assumptions

- Assumption: Python 3.11+ (or project-chosen floor) is available where operators run scripts; if not, wrappers can call `uv run` or document a venv.
- Risk: introducing `pip install -e .` friction; mitigate with `uv`/`pipx` one-liner in README or a bootstrap script.
- Risk: splitting verify changes habits; document `verify --all` vs `verify --templates` clearly.

## Recommended migration order

1. Add package skeleton and one command (`verify` templates-only) with tests; wire `scripts/verify` to call it.
2. Implement linker + `apply global` / `apply repos` with `--dry-run`; port inline Python and awk TOML logic into the package.
3. Port `backup-global` and `sync`; delete duplicate `load_targets` from shell.
4. Add CI (ruff, pytest, verify templates).
5. Optionally add canonical MCP render or ruleset generation once duplication cost is clear.
6. Revisit Go/Rust only if binary distribution becomes a hard requirement.
