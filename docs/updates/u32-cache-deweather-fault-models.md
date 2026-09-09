# Update 32 — cache the deweather + fault models across `make demo-real` re-runs

Date: 2026-09-09 · Branch: `update-32-cache-deweather-fault-models` ·
Tag: `v1.0.32-update`

## The gap

`make demo-real` already treats HST-GAT and the per-parameter imputation models
as cached: `prov models train-hstgat`/`train-imputation` are called with
`--skip-if-cached`, so a re-run against an unchanged `data/raw` drop reuses the
already-trained, card-verified artefact instead of paying the training cost
again. `prov models train` (the deweather regressors + fault classifier) had no
such flag - it always retrained both from scratch on every `make demo-real`,
even when nothing about the underlying drop had changed since the previous run.
Flagged as an open item while working the previous branch; fixed here as its
own update, as recommended at the time (no ADR - this is a mechanical extension
of an existing, already-reviewed caching mechanism, not a new one).

## The fix

`prov models train` gained `--skip-if-cached/--no-skip-if-cached`
(`cli/main.py::models_train`), same contract as the other two commands: before
training, compute the expected versioned stem for the exact data drop and try
to load it; train only on a miss. Deweather and fault are checked
**independently** - either can be reused while the other retrains - because
their checksums are not the same computation:

- Deweather's version is `deweather-v1-<checksum[:8]>` where the checksum is
  `observe(frame).checksum` on the raw loaded frame, exactly like HST-GAT and
  imputation.
- Fault's version is `fault-v1-<checksum[:8]>` where the checksum is of the
  **labeled** frame - the clean data plus the four synthetic fault signatures
  injected deterministically under a fixed seed (`fault/signatures.py`) - not
  the raw frame. The pre-check reproduces that labeled frame
  (`build_labeled_corpus`, cheap pandas/numpy row injection, no model fit) to
  compute the same checksum a real training run would land on, rather than
  inventing a second, looser cache key. The seed the pre-check and the real
  training call both use was pulled into one constant,
  `fault.signatures.DEFAULT_SEED`, replacing a literal (`20260907`) that was
  previously duplicated between `signatures.py`'s and `classify.py`'s own
  default parameters - harmless as long as they agreed, but exactly the kind of
  duplication that silently drifts.

`Makefile`'s `demo-real` target now passes `--skip-if-cached` to
`prov models train`. A new `demo-real-models` target (mirroring
`demo-real-hstgat`/`demo-real-imputation`) forces a fresh retrain of just this
pair when needed (a model-code or config change the checksum-based cache can't
see, same caveat as the other two).

`prov models residuals`, which writes deweathered residuals tied to the
*current* audit run, is unaffected and still runs unconditionally after
training/skip - it is not itself a training step, and `demo-real` resets and
reloads the DB (a fresh audit run) on every invocation regardless of whether
the models were retrained.

## Verifying "all models load fast, live"

Checked what actually gates dashboard responsiveness after a page load, not
just training cost:

- **HST-GAT** and **deweather + fault** are both warmed once at API startup
  (`api/app.py::_warm_model_caches`, calling
  `hstgat.store.load_latest_cached()` and `models.registry.load_bundle_cached()`
  respectively) - no request pays a disk/joblib load.
- **Imputation** models are loaded only inside `ImputationLookup.build`
  (`trust/imputation.py`), which runs once per `prov db load`/`db rescore` call
  to precompute and persist `TrustScore` rows (`io/db/loader.py`) - never on a
  live request path. The dashboard reads the persisted score, so imputation's
  load cost was already off the request path before this change; nothing here
  needed to move.

No change was needed on the serving side - the gap was entirely "does training
re-run needlessly," now closed the same way it already was for the other two
model families.

## Test gate

`tests/unit/test_models_cli.py::test_models_train_skip_if_cached_reuses_matching_artefacts`,
mirroring the existing HST-GAT/imputation skip-if-cached tests: trains once,
confirms a `--skip-if-cached` re-run reuses both artefacts unchanged
(unmodified mtimes, "already cached" for both), and confirms the flag's
absence always retrains both. `make check` (lint + mypy strict + full suite +
coverage gate) run clean on the branch.

## Deviations from what was asked

None beyond adding `demo-real-models`, which the prompt didn't name explicitly
- added for symmetry with the two existing force-retrain targets and mentioned
alongside them in `demo-real`'s own completion output, so "how do I force a
retrain" stays answerable the same way for every model family.

## Flag for review

Fault's cache pre-check pays the cost of `build_labeled_corpus` (signature
injection) even on a cache hit, since that's the only way to know the correct
checksum without training. That's cheap relative to the LightGBM CV+fit it's
skipping, but it is not free the way the HST-GAT/imputation pre-checks are
(theirs need only the raw frame's checksum, no derived-frame work). If profiling
ever shows this pre-check costing real time on the full real drop, the fix
would be to key the fault artefact on the raw frame's checksum too (a
versioning-scheme change, out of scope here) rather than optimizing the
pre-check further.
