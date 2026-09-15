# Global instruction core

Status: implemented

## Decision

The shared instruction source is a small global behavioral baseline, not a
complete coding handbook. It explicitly requires independent judgment: user
claims and proposed solutions are hypotheses, factual conclusions follow the
evidence, and the agent must neither agree for approval nor invent objections
when the user is correct.

The content is divided by durability and enforcement:

| Concern | Durable layer |
| --- | --- |
| Truthfulness, scope, evidence, safety, reporting | global instruction core |
| Project commands, architecture, conventions, gotchas | project-owned instructions |
| Client capabilities and fallback routing | capability registry |
| Conditional multi-step workflows | skills |
| Deterministic enforcement | settings, hooks, tests |

## Research basis

- [OpenAI's Model Spec](https://github.com/openai/model_spec/blob/main/model_spec.md)
  treats truth-seeking and non-sycophantic behavior as distinct from simply
  satisfying the user. OpenAI's
  [sycophancy postmortem](https://openai.com/index/sycophancy-in-gpt-4o/)
  also shows that immediate user approval is not a sufficient quality signal.
- [OpenAI's harness engineering report](https://openai.com/index/harness-engineering/)
  recommends a short `AGENTS.md` as a map to deeper sources of truth, because a
  monolithic manual consumes context, becomes stale, and is difficult to verify.
- [Claude Code best practices](https://code.claude.com/docs/en/best-practices)
  recommends keeping always-loaded instructions short, broadly applicable, and
  limited to facts the model cannot infer. Conditional workflows belong in
  skills and deterministic behavior belongs in hooks.
- [Cursor's CLI documentation](https://docs.cursor.com/en/cli/using) confirms
  that project `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules` are loaded together.
  Installing the same core in more than one of those paths duplicates context.
- [Cursor's rules documentation](https://docs.cursor.com/context/rules-for-ai)
  describes global User Rules as a settings feature and `.cursor/rules` as the
  project format. The installed Cursor Agent CLI exposes rule generation but no
  supported global User Rules import command or configuration key.
- [OpenCode's rules documentation](https://opencode.ai/docs/rules/) provides a
  documented global `~/.config/opencode/AGENTS.md` path, so a second managed
  project copy is unnecessary.

## Installation behavior

`apply-global` links the generated core to Codex, Claude Code, and OpenCode's
documented user-level locations and removes the older managed `~/AGENTS.md`
duplicate. Cursor remains the one exception: because its CLI has no supported
global import surface, `apply-repos` installs exactly one Cursor project rule.

For every registered repository, `apply-repos` removes only instruction
symlinks that point into this repository's managed `rulesets/` tree. It never
removes or overwrites project-owned instruction files. Verification fails if a
legacy managed repository duplicate remains.

## Validation

Tests assert that the core includes both anti-sycophancy and anti-contrarian
language, remains under 60 lines, removes legacy managed duplicates, preserves
project-owned instructions, and retains Cursor's single project overlay.
