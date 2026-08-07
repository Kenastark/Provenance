# 0002 - Licensing

**Status:** Provisional (2026-08-07)

## Context

Provenance is a competition build for the DEIK.AI Challenge 2026. A licence has
to be on file from phase 0 so that every commit has clear terms, but the entry
was made before the competition's rules on intellectual property, redistribution,
and any post-competition commercial path were fully settled. Choosing a
permissive default now and recording what would force a change is cheaper than
either leaving the repository unlicensed or committing hard to terms that a rule
or a buyer conversation could later contradict.

## Decision

**The licence is MIT, and it is explicitly provisional.** `LICENSE` carries the
MIT text with a closing note that points here, and this ADR is the record that
the choice is not yet final.

MIT is the default because it is the least surprising permissive licence, it
imposes no obligation on a municipal evaluator or a teammate reading the code,
and it keeps the dependency story simple: the Python and JavaScript stack is
overwhelmingly permissive (MIT/BSD/Apache-2.0), so MIT introduces no
compatibility friction. The stack pulls in no strong-copyleft (GPL/AGPL) runtime
dependency that would force a share-alike term; if one is ever added, that is
itself a trigger to revisit this decision.

## What would force a change

- **Competition rules.** If the DEIK.AI Challenge terms require a specific
  licence, assign IP to the organisers, or restrict redistribution, those terms
  override MIT and this decision is superseded.
- **A commercial arrangement.** If Provenance moves toward a municipal buyer or
  any paid deployment, a dual-licence or a proprietary/commercial term may be
  warranted, and the permissive default would be reconsidered before that
  conversation, not after.
- **A copyleft dependency.** Introducing a GPL/AGPL-licensed runtime dependency
  would create obligations MIT cannot satisfy and forces a re-evaluation.
- **Data and model terms.** This licence covers the source code only. The Green
  Sentinel dataset, HungaroMet weather data, and any third-party model weights
  carry their own terms and are out of scope here; a conflict surfaced there is a
  trigger to record a separate decision.

## Who decides

The repository owner (project lead, `kenastark`) decides, and for anything driven
by competition rules, in consultation with the DEIK.AI Challenge organisers.

## Consequences

- Every commit ships under clear, permissive terms from phase 0 onward.
- The provisional status is recorded rather than implied, so a later change is a
  documented supersession, not a silent relicensing.
- Per standing rule 10, a change to these terms is a **new** ADR (`0003-...`) that
  states what it supersedes; the `LICENSE` file and its pointer are updated in the
  same change. This file is not edited in place to reflect a different decision.
