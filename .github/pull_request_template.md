## What this changes

<!-- One or two sentences. Link the phase issue. -->

Phase: <!-- 0-7 -->

## Checklist

- [ ] Tests added or updated for the new behaviour
- [ ] `make check` passes locally (lint + mypy strict + pytest with the coverage gate)
- [ ] No number derived from data is hardcoded anywhere (defect rate, completeness, verdicts)
- [ ] No field name, unit, or station id invented rather than read from the data
- [ ] Structural absences still excluded from the defect rate
- [ ] Any trust score emitted still carries its components and at least one reason code
- [ ] Docs updated as a **new version file**, not edited in place
- [ ] `CHANGELOG.md` entry added
- [ ] ADR added under `docs/decisions/` if this decision would be expensive to reverse

## Demo impact

<!-- Does this touch anything the 7-minute demo depends on? If yes, say what and how it was verified. -->
