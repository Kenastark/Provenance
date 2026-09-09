# Update 33 — PM2.5 wasn't in the deweather model's pollutant list

Date: 2026-09-09 · Branch: `update-33-deweather-pm25-coverage` ·
Tag: `v1.0.33-update`

## The report

Viewing evidence for DEB-KER06 and DEB-KER04 events, the "Feature attribution
(SHAP)" and "Deweathered residual" cards both read as unavailable ("PM2.5 is
not covered by the deweather model (CO, CO2, NO2, O3, PM10); the deterministic
reason is shown." / "Not yet computed"), while other stations' evidence loaded
normally.

## Diagnosis

A training-config gap, the same class of bug as update 16's CO2 fix, not a
wiring bug: `explain/service.py::explain_defect` correctly returns `method:
"rule"` with an honest note whenever `ref.parameter not in
deweather.regressors` (standing rule 6 working as designed) - the cards were
never broken, they were accurately reporting that no PM2.5 model exists.

`PM2.5` is a confirmed real parameter (`schema_assumptions.yaml`'s
`known_parameters`), imputation already trains it
(`imputation-PM2.5-v1-8f8efeed.card.json` exists), and it is dispersion-driven
exactly like PM10 - its own strict physical subset, per `thresholds.yaml`'s R09
basis note - yet `config/models.yaml`'s `deweather.pollutants` list was
`[PM10, NO2, O3, CO, CO2]`, never `PM2.5`. `explain/service.py`'s own
`_METADATA_ONLY_CODES` comment says explicitly that R07-R09 (the
physical-impossibility rules) are exactly the codes where a weather
explanation *is* informative - and R09 (`PM2.5 exceeds PM10`) is
overwhelmingly what DEB-KER06/04 were flagged for
(`docs/updates/u22-headline-reconciliation.md`: R09 is 100% PM2.5, 45% of it
one station, KER06). The two stations in the report are exactly the two
heaviest R09 offenders - not a coincidence, the reason the gap was visible
there first.

## Fix

`config/models.yaml`: added `PM2.5` to `deweather.pollutants`, following the
same precedent and reasoning update 16 used for CO2. Retrained against the
real drop and restored residuals:

    prov models train --source data/raw
    prov models residuals --source data/raw

Same data, same checksum, same deweather/fault version strings as before
(`deweather-v1-8f8efeed`, `fault-v1-c40c8de5`) - this only added a sixth
regressor, consistent with update 16's CO2 addition leaving the other four
undisturbed (standing rule 8, determinism).

**Honest number, not hidden:** PM2.5's held-out CV R² is **-0.39**, below the
configured floor (0.15) - the model is not capturing meteorology for PM2.5 on
the real network, same as CO (-0.15), NO2 (0.11) and PM10 (-1.96), all
already in the list and already below the floor (flagged, unresolved, in
update 16). This is a pre-existing, broader finding about the feature set on
this real network (see that update's "Flag for review"), not something this
change fixes or should be read as claiming to fix - PM2.5 joins three other
pollutants already shipped in this same state. What this change buys is not
"weather explains PM2.5 well"; it is "the Evidence tab shows the real
(honest, if weak) model attribution and residual instead of silently falling
back to the rule sentence", which is what the architecture's own R07-R09
handling says should happen for a covered pollutant.

**A caveat this surfaced, not fixed here:** the deweather/fault artefact
version string is a hash of the *training data's* checksum only
(`observe(frame).checksum`), not of `config/models.yaml` - so a config-only
change like this one (same data, new pollutant list) does not change the
version string (`deweather-v1-8f8efeed` before and after). This has two
consequences applied by hand this session: (1) the CLI's own `train` command
was already correct - it always retrains unless `--skip-if-cached` is
passed, which nothing here used, so the artefact on disk was rebuilt
correctly; (2) the **running API process** still had the *old* bundle
in-memory (`registry.load_bundle_cached()` never re-checks disk once
warmed - by design, see that module's docstring), so the fix was invisible
against the live app until the API process was restarted (`.demo-api.pid`
killed, `make api-bg` again) - verified via `GET /v1/explain/19679` returning
`method: "rule"` before the restart and `method: "model"` with real
attributions after, against the same on-disk artefact the whole time. Anyone
picking up this change only needs to restart their own local API process (or
redeploy, in a real environment) - nothing about the fix itself requires a
DB reload or touches `data/raw`.

## Verification

Live against the running API and the real 16-station drop (already loaded,
per Rule 0 - never reloaded, never touched):

- `GET /v1/explain/19679` (DEB-KER06, PM2.5, R09, 2026-06-02T01:00): `method`
  flipped from `"rule"` to `"model"`, with real SHAP attributions
  (`boundary_layer_proxy`, `humidity`, `wind_speed`, ... ) and
  `residual: -1.1799`.
- `GET /v1/explain/13263` (DEB-KER04, PM2.5, R09, 2026-06-02T04:00): same,
  `method: "model"`, `residual: -1.4596`.
- `GET /v1/deweather/DEB-KER06?parameter=PM2.5` and
  `GET /v1/deweather/DEB-KER01?parameter=PM2.5`: `degraded: false`, real
  actual/predicted/residual series across the window - not station-specific,
  every station carrying PM2.5 is now covered.

## Test gate

`make check` (lint + mypy strict + full suite + coverage gate) run clean on
the branch; no test hardcoded the old five-pollutant list (checked). No new
test added - this is a config value plus a retrain against real data, the
same shape update 16 was, and (per standing rule 7) the suite runs only
against the synthetic fixture corpus, which already exercises
`deweather.pollutants` generically rather than pinning its contents.

## Deviations from what was asked

None - fixed the reported symptom at its root cause (the config gap), matching
the precedent update 16 set for the same class of issue, rather than only
reworking the fallback message.

## Flag for review

- **PM2.5's R² (-0.39) joins CO/NO2/PM10 already outside the sanity band** -
  four of six deweathered pollutants now sit below the 0.15 floor on the real
  network. This was already flagged as unresolved in update 16 and remains
  out of scope here; it is a modeling-quality question (is the feature set -
  imputed temperature/precipitation, a boundary-layer proxy, imputed traffic
  - too weak, or is hourly real-network variance in these pollutants
  genuinely not weather-driven), not something a config-list edit can answer.
- **The version-string/config mismatch above** is a real gap: nothing catches
  "the artefact on disk was retrained under new config but a running process
  still holds the old one in memory" automatically. Today this is caught only
  by a human noticing stale evidence and restarting the API - there is no
  automated check that a config change should reasonably force a bundle
  cache invalidation. Worth a human decision on whether that is worth
  building (e.g., a config hash folded into the cache key, or the admin
  `/v1/admin/model-drift` surface health-checking this) versus staying a
  documented operational step.
