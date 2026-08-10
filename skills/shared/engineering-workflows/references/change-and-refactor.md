# Change and refactor workflow

## New behavior

1. Define user-visible behavior, acceptance criteria, non-goals, and failure behavior.
2. Identify integration points, contracts, state transitions, and invariants.
3. Implement the smallest end-to-end slice that is useful without placeholders.
4. Add tests and documentation proportional to the public surface and risk.
5. Verify adjacent behavior and operational signals.

## Behavior-preserving refactor

1. State the external behavior and internal invariants that must remain unchanged.
2. Establish a test or other credible equivalence signal before editing.
3. Separate mechanical movement or renaming from semantic change.
4. Keep dependency direction clear and avoid opportunistic cleanup outside the target.
5. Re-run equivalence checks and inspect the final diff for unintended behavior changes.
