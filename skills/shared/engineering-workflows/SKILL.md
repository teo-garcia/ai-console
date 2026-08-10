---
name: engineering-workflows
description: Apply evidence-driven, technology-neutral workflows for bug fixes and incidents, feature implementation and refactoring, code review, high-risk migrations, and consequential architecture decisions. Use when a software task needs a repeatable discovery, execution, risk, or verification playbook rather than framework-specific advice.
---

# Engineering Workflows

Use only the reference matching the current task. Do not load every playbook.

## Route the task

- For a bug, failing test, regression, or incident, read [debug-and-incident.md](references/debug-and-incident.md).
- For new behavior or a behavior-preserving refactor, read [change-and-refactor.md](references/change-and-refactor.md).
- For reviewing code, a diff, or a pull request, read [review.md](references/review.md).
- For data, API, authentication, infrastructure, or other risky migrations, read [migration.md](references/migration.md).
- For a consequential design choice, read [architecture.md](references/architecture.md).

If a task spans workflows, start with the highest-risk reference and load one additional reference only when its acceptance criteria materially differ.

## Shared discipline

1. Establish the requested outcome, non-goals, risk, and evidence needed to claim completion.
2. Inspect the narrowest relevant source, configuration, callers, tests, and runtime behavior.
3. State invariants before changing behavior and preserve unrelated user work.
4. Implement the smallest complete slice at the root-cause layer.
5. Validate in proportion to the blast radius and report exact evidence and remaining uncertainty.
