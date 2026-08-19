# ADR 0010 — The sign-off gate and four-role RBAC (phase 7)

Status: accepted (phase 7).
Supersedes: extends ADR 0004 (phase-2 API auth), which deferred exactly this.

## Context

Phase 7 adds the operational surface: a maintenance queue, an Alert Centre, and — the
part with real-world consequences — the ability to **dispatch a public-facing alert**
(webhook / email / SMS). Two decisions here are expensive to reverse, so they are
recorded before the code.

## Decision 1 — the human sign-off gate is a static call-graph invariant, not a runtime check

Standing rule 5 and Never-do #8 forbid any code path publishing a public alert without a
recorded human sign-off. We make that **mechanical**:

- The channel senders (`send_webhook`/`send_email`/`send_sms`) live in one module and are
  callable from **exactly one place** — `api/decision/gate.dispatch`.
- `gate.dispatch` validates a sign-off (`validate_signoff`) *before* it ever calls the
  sender.
- `tests/architecture/test_signoff_gate.py` walks the whole package's AST and fails the
  build if (a) any module outside `channels.py` calls a sender, (b) anything outside
  `gate.py` calls `deliver`, or (c) the delivering function doesn't call the validator.

Why static and not only runtime: a runtime check can be bypassed by a new code path that
simply doesn't call it. A call-graph assertion fails the build the moment such a path is
introduced. This is the ethical commitment made un-bypassable.

A sign-off records **who, when, the evidence hash they saw, and the model version**, and
it **expires** — a stale token cannot authorise a fresh dispatch. Dispatch is idempotent
on `(event_id, channel, signoff_id)`: the key is reserved with a unique row *before* the
send, so a retry — sequential or concurrent — loses the race and never double-sends.

## Decision 2 — four roles, an OIDC-shaped model behind static keys

ADR 0004 shipped three roles (`public_read` < `researcher` < `operator`) behind static
API keys, deferring OIDC. Phase 7 adds **`admin`** (model versions, retraining triggers,
config hashes, export history, the model-drift monitor) and the operator **write** surface
(maintenance transitions, sign-off, dispatch).

We keep the **static-key transport** for now but fix the **role model** to exactly what an
OIDC `roles` claim would carry, and pin it with a full RBAC matrix test (every endpoint ×
every role). The eventual OIDC swap is therefore a **transport change, not a policy
change**: the dependency `require(Role.X)` and the matrix test are unchanged; only how a
request proves its role changes.

## Consequences

- The sign-off gate is enforced by a test that will fail loudly on any future refactor that
  routes a dispatch around it — which is the point.
- Adding a fifth role or a new endpoint means extending the RBAC matrix test; a missed
  entry is a failing test, not a silent hole.
- The offline demo never sends anything: the channel senders append to a local outbox and
  perform no network egress, which is also what lets the whole suite run with the network
  blocked.
