## Codex

Respect Codex-specific constraints and response style. Share only the solution below, aligned with the same structure used across the other LLM variants.

## Claude

Respect Claude-specific constraints and response style. Share only the solution below, aligned with the same structure used across the other LLM variants.

# Project Improvement Solution

## Given

- The repository is a control plane for AI tool rules, skills, and MCP configuration across four clients (Claude, Cursor, Gemini, Codex).
- Operational logic lives in Bash with embedded Python for JSON and TOML manipulation.
- Four MCP config files maintain the same server set with minor per-tool variations, all hand-maintained in parallel.
- Machine-specific absolute paths (`/Users/juan.garcia`, `postgresql://...`) are tracked in version control.
- Rule content is duplicated verbatim across `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, and `core.mdc`.
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
  gemini.base.json      # non-MCP Gemini settings (theme, retention, auth)
  local.json            # machine-local var bindings; git-ignored
  local.example.json    # template for local.json
```

Profile blocks in `canonical.json` bind profile-specific vars (e.g., `SERENA_CONTEXT=ide-assistant` vs `codex`). `local.json` binds machine-specific vars (`FILESYSTEM_ALLOWED_DIR`, `POSTGRES_URL`). Render fails explicitly on any unresolved variable.

`ai-console render` writes the four tool-specific files from this model. Until cutover is validated, generated files remain checked in. After validation, git-ignore them.

### 3. Eliminate ruleset duplication

`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, and `core.mdc` are identical content. `core.mdc` adds only a YAML front-matter block.

Replace with:

```
rulesets/core/
  _source.md            # single source of truth for rule content
  templates/
    claude.tmpl
    codex.tmpl
    gemini.tmpl
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

- The repository is a control plane for rules, skills, and MCP config across Codex, Claude, Cursor, and Gemini.
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

The Go proposals’ `canonical.json` plus `render` step is compatible with a Python CLI; defer until maintaining four MCP files becomes painful. Same for single `_source.md` to regenerate `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `core.mdc`.

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

## Gemini 3 Lite

Respect Gemini 3 Lite-specific constraints and response style. Share only the solution below, aligned with the same structure used across the other LLM variants.

# Project Improvement Solution

## Given

- The repository acts as a control plane for rules, skills, and MCP configuration.
- Operational behavior is implemented through shell scripts with embedded Python.
- MCP definitions are duplicated across client-specific files.
- Machine-specific paths are stored in tracked configuration.
- The repository is both the source of truth and one of the managed targets.
- Verification exists, but there is no typed application layer, no real test suite, and no CI workflow.

## Constraints

- The project is an orchestration CLI, not a product application.
- The main bottlenecks are maintainability, correctness, portability, and operational clarity more than raw CPU usage.
- The migration path should preserve current behavior while reducing script sprawl and duplication.
- The target state should favor stronger typing, deterministic generation, and better operator interfaces.

## Solution

### 1. Rebuild the operational layer as a typed CLI

- Replace the shell-plus-inline-Python implementation with a single compiled CLI.
- Use Go as the primary implementation language.
- Keep Bash only as temporary compatibility wrappers during migration.

Recommended command surface:

- `ai-console apply global`
- `ai-console apply repos`
- `ai-console backup`
- `ai-console verify`
- `ai-console plan`
- `ai-console doctor`

### 2. Introduce one canonical configuration model

- Stop maintaining four parallel MCP definitions by hand.
- Store one canonical MCP model in a portable declarative format.
- Generate Codex, Claude, Composer, Cursor, and Gemini client outputs from that model.
- Split tracked defaults from local machine overrides.

Recommended split:

- Tracked: portable defaults, schemas, templates, rulesets
- Ignored local overrides: workstation paths, local repo registry entries, local credentials, local database URLs

### 3. Separate source-of-truth from generated artifacts

- Treat this repository only as the controller.
- Do not rely on this same repo being a managed target for its own generated links.
- Keep source definitions under stable directories and generate target-facing artifacts explicitly.

Recommended modules:

- `cmd/ai-console/`
- `internal/config/`
- `internal/render/`
- `internal/linker/`
- `internal/merge/`
- `internal/verify/`
- `internal/backup/`
- `testdata/`

### 4. Make operations deterministic and inspectable

- Add `--dry-run` and `--json` output to every mutating command.
- Add `plan` to show file mutations before applying them.
- Add `doctor` to explain drift, broken symlinks, invalid config, and missing dependencies.
- Use structured error messages and stable exit codes.

### 5. Replace prose-only confidence with executable verification

- Add unit tests for parsing, rendering, and merge logic.
- Add golden tests for generated client config files.
- Add temp-directory integration tests for symlink behavior and force semantics.
- Add CI to run verification and tests on every change.

### 6. Normalize repository layout

Recommended top-level shape:

- `cmd/`
- `internal/`
- `config/`
- `rulesets/`
- `skills/`
- `templates/`
- `testdata/`
- `scripts/` for thin compatibility wrappers only

## Verification

- Confirm generated outputs are byte-stable for the same input.
- Confirm local overrides do not leak into tracked defaults.
- Confirm existing workflows still work through compatibility wrappers until cutover is complete.
- Confirm the repository can manage external targets without depending on self-referential symlinks.

## Risks / assumptions

- Assumption: Go is acceptable as the primary implementation language.
- Risk: migrating too much at once will break current operator workflows.
- Risk: if machine-local values remain mixed with tracked config, portability problems will persist.
- Risk: adding more clients before canonical generation is in place will increase duplication further.

## Recommended migration order

1. Define canonical schemas and local override strategy.
2. Implement read-only `plan`, `verify`, and `doctor` in Go.
3. Implement config generation from one canonical MCP model.
4. Implement `apply global`, `apply repos`, and `backup`.
5. Add CI and golden tests.
6. Remove embedded Python and retire most shell logic.

## Gemini CLI

Respect Gemini CLI-specific constraints and response style. Share only the solution below, aligned with the same structure used across the other LLM variants.

# Project Improvement Solution

## Given

- The project is a configuration management hub for AI development rules and MCP settings across multiple clients (Claude, Cursor, Gemini, Codex).
- The implementation is a hybrid of Bash orchestration and Python-based JSON/TOML processing via heredocs.
- Redundancy exists in ruleset files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `core.mdc`) and parallel MCP configuration files.
- Configuration includes machine-specific absolute paths, causing environment drift and portability issues.
- The system lacks a formal test suite, schema validation, and automated CI.

## Constraints

- Maintain the current "operator-first" utility nature of the tool; keep it lightweight.
- Ensure zero downtime for existing developer workflows during the transition.
- Decouple environment-specific paths from tracked version-controlled configuration.
- The final tool should be easily distributable and require minimal external dependencies.

## Solution

### 1. Unified CLI Core (Go)

Replace the fragmented `scripts/` directory with a single, statically compiled Go binary (`ai-console`). Go provides a "zero-runtime" distribution model, strong typing for complex config merges, and excellent performance for filesystem-heavy tasks.

Key Command Interface:
- `ai-console sync [--global|--repos] [--force] [--dry-run]`
- `ai-console plan`: View pending symlink and merge operations.
- `ai-console doctor`: Validate environment health (binaries, paths, symlink integrity).
- `ai-console register`: Interactively add/manage repositories.
- `ai-console backup`: Snapshot current global and repo configurations.

### 2. Declarative Config & Local Overrides

Implement a strict separation between *what* should be configured and *where* it lives on a specific machine.

- **Tracked (`config/targets.json`):** Logic definitions and relative source paths.
- **Local (`config/local.yaml`):** Machine-specific path bindings (e.g., `home_dir: /Users/juan.garcia`). This file is git-ignored.
- **Environment Variables:** Allow `${VAR}` interpolation in all configuration files to handle dynamic paths.

### 3. Canonical Ruleset & MCP Templates

Eliminate verbatim duplication by moving to a "Source + Template" model.

- **Source:** Maintain a single `rulesets/core/source.md`.
- **Templates:** Use Go's `text/template` or simple wrappers to generate client-specific files (`.md`, `.mdc`) with appropriate headers/front-matter.
- **MCP Hub:** Define one `mcp/servers.yaml` that generates the final JSON/TOML files for each AI client.

### 4. Deterministic State Management

- **Dry-Run Mode:** Every command must support `--dry-run` to output a diff or list of actions without modifying the disk.
- **Atomic Operations:** Use temporary files for merges to ensure that a failed write doesn't leave configurations in a corrupted state.
- **Validation Layer:** Use Pydantic-like validation (via Go structs) to ensure `targets.json` and `repos.json` conform to the expected schema before execution.

### 5. Automated Verification & CI

- **Unit Tests:** Test the path expansion and JSON/TOML merging logic in isolation.
- **Integration Tests:** Use a temporary directory as a mock `$HOME` to verify the end-to-end `apply` flow.
- **CI Pipeline:** Run `go fmt`, `go vet`, and `go test` on every PR. Add a "drift check" to ensure generated files match the canonical source.

## Verification

- `ai-console sync --dry-run` accurately predicts all required changes.
- Machine-specific paths are entirely absent from the `git status` diff of tracked JSON files.
- `ai-console doctor` correctly identifies missing local path bindings or broken symlinks.
- Generated `CLAUDE.md` and `AGENTS.md` are identical when rendered from the same source.

## Risks / Assumptions

- **Assumption:** The operator has the Go toolchain available for initial build, or we provide pre-compiled binaries.
- **Risk:** Transitioning to `local.yaml` requires a one-time migration of existing absolute paths out of `repos.json`.
- **Risk:** Automated TOML merging for Codex is inherently more complex than JSON; requires robust parser-based manipulation rather than line-based edits.

## Recommended Migration Order

1. **Bootstrap:** Create the Go CLI skeleton and implement `doctor` and `plan` (read-only).
2. **Path Abstraction:** Introduce `local.yaml` and update the CLI to resolve paths dynamically.
3. **Template Engine:** Move rulesets to a single source and implement the `render` command.
4. **Execution Layer:** Implement `apply` with atomic writes and `--force` support.
5. **Wrapper Cutover:** Replace `scripts/*.sh` with simple `ai-console` calls.
6. **Cleanup:** Remove duplicated ruleset files and absolute paths from version control.
