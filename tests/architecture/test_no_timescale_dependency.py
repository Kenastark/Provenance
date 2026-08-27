"""No migration may reintroduce a TimescaleDB dependency (ADR 0012).

The schema is plain PostgreSQL 16 with PostGIS so it can run on managed Postgres
(Cloud SQL), which offers PostGIS but not the Timescale extension. Two things make
that easy to lose without noticing:

* the local Compose database is still ``timescale/timescaledb-ha:pg16`` — a fine
  multi-arch pg16 build, but one where ``CREATE EXTENSION timescaledb`` and
  ``create_hypertable`` both *succeed*, so a reintroduced hypertable would work
  perfectly on every developer machine and only fail on the deployment target;
* the ORM is dialect-neutral, so nothing in the model layer would complain either.

This test is the cheap half of the guard and runs in the default gate with no
database at all: it reads the migration sources and fails if any of them names
Timescale. The expensive half is the CI ``e2e`` job, whose ``db`` service is the
plain PostGIS image — an engine where the extension genuinely does not exist, so
the migrations, the loader and the audit are proven against it on every PR.

Deliberately a source-text check rather than an import or an AST walk: the calls
that matter live inside ``op.execute`` string literals, where an AST gives no more
certainty than the text does, and a future migration might build its SQL any way
at all. Any mention is worth a human look.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_DIR = REPO_ROOT / "infra" / "alembic" / "versions"

# Word-boundary so ordinary prose ("this table used to be chunked") does not trip the
# gate, while any real call or extension name does.
FORBIDDEN = re.compile(r"\b(timescaledb|create_hypertable|time_bucket)\b", re.IGNORECASE)


def _migration_files() -> list[Path]:
    return sorted(p for p in VERSIONS_DIR.glob("*.py") if p.name != "__init__.py")


def test_there_are_migrations_to_check() -> None:
    # Guards the guard: a glob that silently matches nothing would make every
    # assertion below vacuously true.
    assert _migration_files(), f"No migrations found under {VERSIONS_DIR}."


@pytest.mark.parametrize("path", _migration_files(), ids=lambda p: p.name)
def test_migration_names_no_timescale_feature(path: Path) -> None:
    hits = sorted(
        {m.group(0).lower() for m in FORBIDDEN.finditer(path.read_text(encoding="utf-8"))}
    )
    assert not hits, (
        f"{path.name} references {hits}. The schema is plain PostgreSQL 16 + PostGIS "
        "(ADR 0012) because managed Postgres does not offer the Timescale extension. "
        "This passes locally regardless, since the Compose image ships Timescale — "
        "which is exactly why this test exists. If the dependency is being taken back "
        "on deliberately, supersede ADR 0012 first."
    )
