"""API-key authentication with three roles.

Phase 2 uses static API keys mapped to roles, not full OIDC — a deliberate,
recorded deferral (see ``docs/decisions/0004-api-auth-phase2.md``). The three
roles form a strict hierarchy of read access:

* ``public_read`` — the public trust product: stations, trust scores, quality
  summary, events, and the meta endpoints.
* ``researcher`` — everything public plus the raw and quality-flagged readings,
  the defect ledger, audit runs, and the regulator-facing audit-trail export.
* ``operator`` — everything a researcher can see; the role that will carry the
  write and sign-off surface added in phase 7.

Keys come from ``PROVENANCE_API_KEYS`` (a JSON ``{key: role}`` map) when set, else
the documented local-dev defaults below. The meta endpoints (health, readiness,
version) are unauthenticated so orchestration can probe them without a key.
"""

from __future__ import annotations

import json
from enum import StrEnum

from fastapi import Request
from fastapi.security import APIKeyHeader

from provenance.config.settings import get_settings

API_KEY_HEADER = "X-API-Key"
api_key_scheme = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


class Role(StrEnum):
    PUBLIC_READ = "public_read"
    RESEARCHER = "researcher"
    OPERATOR = "operator"


# Read access each role is granted, resolved transitively below.
_GRANTS: dict[Role, set[Role]] = {
    Role.PUBLIC_READ: {Role.PUBLIC_READ},
    Role.RESEARCHER: {Role.PUBLIC_READ, Role.RESEARCHER},
    Role.OPERATOR: {Role.PUBLIC_READ, Role.RESEARCHER, Role.OPERATOR},
}

# Local-dev keys. Override in any real environment via PROVENANCE_API_KEYS.
_DEFAULT_KEYS: dict[str, Role] = {
    "prov-operator-key": Role.OPERATOR,
    "prov-researcher-key": Role.RESEARCHER,
    "prov-public-key": Role.PUBLIC_READ,
}


def load_api_keys() -> dict[str, Role]:
    """Resolve the key→role map from settings, falling back to dev defaults."""
    raw = getattr(get_settings(), "api_keys_json", "") or ""
    if raw.strip():
        parsed = json.loads(raw)
        return {str(k): Role(v) for k, v in parsed.items()}
    return dict(_DEFAULT_KEYS)


def role_for_key(key: str | None) -> Role | None:
    if not key:
        return None
    return load_api_keys().get(key)


def role_satisfies(role: Role, required: Role) -> bool:
    """True when ``role`` is granted at least the access ``required`` implies."""
    return required in _GRANTS[role]


async def api_key_header(request: Request) -> str | None:
    return await api_key_scheme(request)
