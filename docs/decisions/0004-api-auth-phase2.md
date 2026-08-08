# 0004 - API authentication for phase 2 (API keys now, OIDC deferred)

**Status:** Accepted (2026-08-08)

## Context

The phase-2 API exposes readings, defects, audit runs, trust scores, and a
regulator-facing audit-trail export to three distinct consumers — operators,
researchers/agencies, and public read clients (`docs/api/README.md`). Those
consumers need different access, so the API needs authentication and role-based
authorization from the moment it is real. Full identity management — OpenID
Connect, an IdP, token refresh, per-user provisioning — is a phase-7 concern
(hardening, RBAC, monitoring) and would be premature scaffolding now: it adds an
external dependency and operational surface with no consumer yet asking for it.

## Decision

**Phase 2 authenticates with static API keys mapped to one of three roles**, and
**full OIDC is explicitly deferred to phase 7.**

- Roles form a strict hierarchy: `public_read` ⊂ `researcher` ⊂ `operator`
  (`api/auth.py`). Public endpoints (stations, trust, quality summary, events, the
  meta endpoints) need any valid key; readings, defects, audit runs, and the
  audit-trail export require `researcher`; `operator` is the superset that will
  carry the phase-7 write and public-alert sign-off surface.
- Keys arrive in an `X-API-Key` header. The key→role map comes from
  `PROVENANCE_API_KEYS` (a JSON object) in any real environment; documented
  local-dev keys are the fallback so the stack runs out of the box.
- The meta endpoints (`/healthz`, `/readyz`, `/version`) are unauthenticated so
  orchestration can probe them without a key.
- Every allow/deny is asserted by an endpoint × role matrix test
  (`tests/integration/test_api_auth.py`); denials are RFC 7807 problem documents.

## What phase 7 changes

- OIDC/JWT bearer auth backed by an IdP, replacing static keys for human users;
  service-to-service may retain keys or move to mTLS.
- The role model here (`public_read`/`researcher`/`operator`) is the seam OIDC
  claims map onto, so the *authorization* logic — `require(role)` on each route —
  is expected to survive; only *authentication* (how a caller proves who they are)
  changes.
- The public-alert dispatch path (standing rule 5) lands with sign-off records and
  is gated on `operator`; it is not reachable in phase 2.

## Consequences

- The API is usable and safely scoped now, with no premature identity
  infrastructure.
- The deferral is recorded, not implied: phase 7 replacing authentication is a
  documented supersession (a new ADR), not a silent change of terms.
- Static keys are a real secret-management responsibility in the interim — they
  live in `PROVENANCE_API_KEYS`, never in git, and the dev defaults are clearly
  marked local-only in `api/auth.py`.
