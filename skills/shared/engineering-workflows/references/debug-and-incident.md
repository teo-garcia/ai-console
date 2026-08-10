# Debug and incident workflow

1. Reproduce the failure or localize it with direct runtime, test, log, or source evidence.
2. Separate the observed symptom, known-good behavior, hypotheses, and confirmed root cause.
3. Trace the failing path across boundaries; inspect adjacent callers and error handling only as evidence expands the blast radius.
4. Fix the smallest correct layer. Avoid stacking defensive patches around an unknown cause.
5. Add or update a regression test when practical.
6. Re-run the failing path, the regression test, and adjacent risk checks.

For an active incident, first protect data and reduce impact with a reversible mitigation. Preserve useful evidence, establish a rollback condition, and record observable recovery criteria. Do not let the mitigation substitute for root-cause follow-up.

Report the observed failure, root cause evidence, change, verification, and any residual risk separately.
