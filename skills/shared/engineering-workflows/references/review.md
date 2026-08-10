# Review workflow

1. Establish the base and scope of the diff. Read the changed code in its calling and test context.
2. Prioritize correctness, security, regressions, data loss, concurrency, contract changes, and missing tests.
3. Verify each finding against source or runtime evidence; do not report speculative style preferences as defects.
4. For every finding, cite the exact location, trigger conditions, user impact, and smallest credible correction.
5. Order findings by severity. Keep summaries secondary to actionable defects.
6. If no defects are found, say so and name meaningful residual test or coverage gaps.

Do not modify code during a review unless the request explicitly includes fixes.
