# Code-intelligence pilot result — 2026-09-14

Status: complete; both candidates rejected and removed

Branch: `plan/capability-ecosystem-routing`

## Scope

One outcome-only `symbol-callers` case was run in three cold Codex CLI sessions:
native, Serena Lite `v1.7.0`, and Codebase Memory `v0.10.8`. Each session used
the same implicit Codex service default because the isolated CLI JSONL output did
not expose an exact model identifier.

The final matched evidence set is:

- native and Codebase Memory:
  `evals/runs/20260914-125049-954659-capability-pilot.json`;
- corrected Serena Lite:
  `evals/runs/20260914-125726-397443-capability-pilot.json`.

Raw artifacts are deliberately ignored. They contain complete JSONL events and
answers for local review without permanently tracking machine-specific temporary
paths.

## Result

| Candidate | Correct | MCP calls | Native shell calls | Wall time | Extra cold work | Input / output tokens | Isolated cache |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Native | yes | 0 | 7 | 101.966s | none | 187,622 / 3,386 | 0 bytes |
| Serena Lite | yes | 0 | 4 | 156.290s | included in wall time | 114,475 / 2,901 | 306,233,131 bytes |
| Codebase Memory | yes | 0 | 6 | 115.527s | 26.668s pre-index | 159,811 / 3,623 | 301,243,583 bytes |

All answers found the two direct production call sites in `ai_console/cli.py`
and `ai_console/verify.py`, separated the nine direct tests in
`tests/test_capabilities.py`, identified the indirect `doctor()` path, and did
not treat evaluation fixture strings as executable callers.

All final sessions recorded:

- zero source-repository changes;
- zero disposable-workspace changes;
- zero forbidden repository paths;
- no matching provider process after the bounded shutdown poll.

Token totals are observed CLI usage, not a stable context-size benchmark. The
three stochastic sessions produced different exploration paths, and neither MCP
was called, so token differences cannot be attributed to the providers.

## Operational findings

The initial harness attempts found and corrected two setup defects before the
final comparison:

1. metadata-free disposable copies require Codex's documented
   `--skip-git-repo-check` flag;
2. Serena `v1.7.0` requires `projects: []` in a minimal `serena_config.yml`.

The corrected Serena session initialized and completed. Its project data was
created only under the temporary central `project_serena_folder_location`; no
`.serena` appeared in the repository copy. Codebase Memory indexed with
`persistence=false`, exposed its read-only Scout profile, and created no
`.codebase-memory` artifact.

## Decision

Do not enable either MCP globally or as an opt-in profile.

This pilot reproduced the core usability failure: being installed, reachable,
and present in the session did not make either provider naturally selected. The
current universal instructions prefer native client tools before MCP, which
conflicts with the plan's capability-specific intent for live semantic and graph
tasks. Running the remaining 21 screening sessions unchanged would mostly measure
the same routing failure while paying cold-start and context costs.

The follow-up decision was to stop spending routing and maintenance effort on
providers that had not demonstrated value. Their canonical definitions, profiles,
capability entries, executor, and active evaluation corpus were removed. The raw
ignored runs remain local evidence; this document is the durable audit record.

Reconsider either provider only after new evidence identifies a concrete workflow
that native code/search/LSP tools cannot handle and a small bounded pilot shows a
measurable correctness or latency win without repository state.
