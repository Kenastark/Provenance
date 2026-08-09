"""The regulatory export bundle: reproducible hash, three consistent renderings (§2)."""

from __future__ import annotations

import pytest

from provenance.report.regulatory import RegulatoryExport

pytestmark = pytest.mark.unit


def _export(**overrides) -> RegulatoryExport:
    base: dict = {
        "run": {
            "id": "ar_demo",
            "code_version": "1.0.0",
            "config_hash": "abc123",
            "data_checksum": "def456",
            "generated_at": "2026-06-19T00:00:00",
            "n_rows": 1000,
        },
        "definition": "the defect rate is ...",
        "accounting": {
            "n_readings": 1000,
            "n_covered_cells": 900,
            "n_defective_cells": 12,
            "n_structural_exclusions": 2,
            "defect_rate": 1.33,
            "conventional_completeness_pct": 99.9,
        },
        "defects": [
            {
                "station_id": "STA-02",
                "parameter": "PM10",
                "timestamp_utc": "2026-06-02T20:00:00",
                "reason_code": "R07",
                "severity": "critical",
                "counts_toward_rate": True,
                "evidence": {"value": 4100.7},
            },
            {
                "station_id": "STA-01",
                "parameter": "NO",
                "timestamp_utc": "2026-06-01T00:00:00",
                "reason_code": "R11",
                "severity": "medium",
                "counts_toward_rate": True,
                "evidence": {},
            },
        ],
        "structural_exclusions": [
            {
                "station_id": "STA-03",
                "parameter": "wind_speed",
                "domain": "meteorology",
                "reason_code": "C01",
                "excluded_cells": 336,
            }
        ],
        "model_versions": {"trust_score": "v1"},
    }
    base.update(overrides)
    return RegulatoryExport(**base)


def test_verification_hash_is_reproducible() -> None:
    assert _export().verification_hash() == _export().verification_hash()


def test_signoff_appendix_does_not_change_the_verification_hash() -> None:
    # The hash certifies the measured record, not the dispatch appendix.
    without = _export()
    with_signoff = _export(
        signoffs=[{"signoff_id": "so_1", "event_id": 1, "operator": "op"}],
        dispatches=[{"dispatch_id": "dsp_1", "event_id": 1}],
    )
    assert without.verification_hash() == with_signoff.verification_hash()


def test_changing_a_defect_changes_the_hash() -> None:
    a = _export()
    tampered = _export(defects=[{**a.defects[0], "severity": "low"}, a.defects[1]])
    assert a.verification_hash() != tampered.verification_hash()


def test_csv_has_one_row_per_defect_and_exclusion() -> None:
    csv_text = _export().to_csv()
    lines = [ln for ln in csv_text.split("\n") if ln]
    assert lines[0].startswith("record_type,")
    assert sum(1 for ln in lines if ln.startswith("defect,")) == 2
    assert sum(1 for ln in lines if ln.startswith("structural_exclusion,")) == 1


def test_json_reconciliation_matches_the_ledgers() -> None:
    payload = _export().to_json_dict()
    assert payload["reconciliation"]["n_defect_rows"] == 2
    assert payload["reconciliation"]["n_structural_exclusions"] == 1
    assert payload["reconciliation"]["n_readings"] == 1000
    assert payload["verification_hash"]


def test_pdf_is_a_valid_reproducible_document() -> None:
    a = _export().to_pdf()
    b = _export().to_pdf()
    assert a == b  # deterministic bytes
    assert a.startswith(b"%PDF-1.4")
    assert a.rstrip().endswith(b"%%EOF")
    assert b"xref" in a
    # The verification hash is printed on the summary page.
    assert _export().verification_hash().encode() in a
