# Migration workflow

1. Inventory affected data, callers, contracts, permissions, observability, and rollback constraints.
2. Snapshot current behavior and define preconditions, success metrics, abort thresholds, and a tested rollback path.
3. Prefer expand-and-contract or another staged, backward-compatible sequence.
4. Make repeated execution safe where practical and protect against partial failure, concurrency, and version skew.
5. Validate in a representative environment before rollout.
6. Execute with checkpoints and observable progress; stop at predefined thresholds.
7. Verify data integrity and behavior after each stage, then remove compatibility paths only after evidence supports it.

Never treat a backup as a rollback plan until restoration has been exercised. State irreversible steps explicitly before execution.
