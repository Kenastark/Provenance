"""The reason-code registry carries two standing rules. These tests are the rules."""

from __future__ import annotations

import pytest

from provenance.config import reason_codes as rc


def test_codes_are_unique() -> None:
    codes = [c.code for c in rc.REASON_CODES.values()]
    assert len(codes) == len(set(codes))


def test_every_code_has_an_operator_sentence() -> None:
    # A bare code is never shown to a human. Every code must carry plain language.
    for code in rc.REASON_CODES.values():
        assert code.sentence.strip()
        assert code.sentence[0].isupper()
        assert code.sentence.rstrip().endswith(".")


def test_coverage_codes_never_count_toward_the_defect_rate() -> None:
    # Structural absence is a fact about the network, not a broken reading.
    # Counting it would inflate the headline statistic.
    for code in rc.coverage_codes():
        assert code.counts_toward_defect_rate is False


def test_structural_absence_codes_are_coverage_not_defects() -> None:
    for code_id in ("R18", "R19"):
        assert rc.get(code_id).counts_toward_defect_rate is False


def test_anchor_codes_are_not_renumbered() -> None:
    # The dashboard mockups reference these two by number.
    assert rc.get("R07").name == "EXCEEDS_PHYSICAL_MAX"
    assert rc.get("R12").name == "ZERO_VARIANCE"


def test_defect_and_coverage_codes_partition_the_registry() -> None:
    assert len(rc.defect_codes()) + len(rc.coverage_codes()) == len(rc.REASON_CODES)


def test_unknown_code_raises_a_useful_error() -> None:
    with pytest.raises(KeyError, match="Known codes"):
        rc.get("R99")


def test_render_substitutes_evidence() -> None:
    rendered = rc.get("R12").render(duration="40 minutes")
    assert "40 minutes" in rendered


def test_render_degrades_gracefully_without_evidence() -> None:
    # A partially populated evidence dict must still produce something readable.
    assert rc.get("R12").render() == rc.get("R12").sentence


def test_codes_for_phase_is_cumulative() -> None:
    assert set(rc.codes_for_phase(1)).issubset(set(rc.codes_for_phase(5)))
    assert rc.get("R17") not in rc.codes_for_phase(1)
    assert rc.get("R17") in rc.codes_for_phase(4)
