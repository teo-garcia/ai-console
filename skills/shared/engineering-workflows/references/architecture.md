# Architecture decision workflow

1. State the decision, constraints, required capabilities, non-goals, and expected lifetime.
2. Generate two or three viable designs, including the simplest credible option.
3. Compare complexity, failure modes, security, migration cost, operational burden, observability, reversibility, and fit with existing conventions.
4. Identify assumptions that would reverse the ranking and gather evidence for the most consequential ones.
5. Recommend one design and explain concretely why the others lose in this context.
6. Define the smallest validation spike or decision checkpoint when uncertainty remains.

Prefer the simplest design that preserves required extensibility. Do not build speculative abstractions for uncommitted future needs.
