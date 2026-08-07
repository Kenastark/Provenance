# Property tests

Hypothesis-driven invariants. These are where the audit's correctness actually
lives, because they hold for *any* corpus rather than for one hand-picked example.

Phase 1 adds, at minimum:

- Reindexing never invents an observed reading: `observed ⊆ expected` always.
- `expected == observed + absent + structurally_excluded`, exactly.
- R09 raises zero flags on any corpus where `pm25 <= pm10` by construction.
- The defect rate is in `[0, 1]` for every generated corpus, and is monotonic in
  the number of injected defects.
