"""The audit must scale to the real corpus size within the demo's time budget."""

from __future__ import annotations

import time

from provenance.audit.orchestrator import run_audit
from provenance.fixtures.generator import generate


def test_audit_of_150k_rows_completes_under_60s() -> None:
    # ~310 days x 21 covered series ~= 156k readings, the scale of the real export.
    frame, _ = generate(n_days=310)
    assert len(frame) >= 150_000, f"corpus too small: {len(frame)} rows"
    start = time.perf_counter()
    result = run_audit(frame)
    elapsed = time.perf_counter() - start
    assert elapsed < 60.0, f"audit took {elapsed:.1f}s, budget is 60s"
    assert result.meta.n_rows == len(frame)
