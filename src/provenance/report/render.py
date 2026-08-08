"""Rendering the audit into the three artefacts the phase ships.

* ``audit.json`` - the machine record, the full :class:`AuditResult`.
* ``audit.md`` - the human record, and the file the golden test snapshots, so it
  is built deterministically with no incidental ordering.
* ``audit.html`` - a self-contained, printable report with no external requests;
  the design tokens are inlined from the one source of truth so the report wears
  the same palette as the app without a second copy of the colours.

All three are deterministic given a fixed ``generated_at``: sorted keys, stable
float formatting, sorted table rows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from provenance.audit.result import AuditResult
from provenance.config import reason_codes

_TEMPLATES = Path(__file__).resolve().parent / "templates"
_TOKENS_CSS = Path(__file__).resolve().parents[3] / "design" / "tokens" / "tokens.css"


def render_json(result: AuditResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_markdown(result: AuditResult) -> str:
    r = result
    cov = r.coverage
    dr = r.defect_rate
    lines: list[str] = []
    add = lines.append

    add("# Provenance audit")
    add("")
    add(f"- Code version: `{r.meta.code_version}`")
    add(f"- Config hash: `{r.meta.config_hash}`")
    add(f"- Data checksum: `{r.meta.data_checksum}`")
    add(f"- Window: {cov.window_start} to {cov.window_end}")
    add("")

    add("## Headline")
    add("")
    add(f"- Readings ingested: **{r.meta.n_rows:,}**")
    add(
        f"- Conventional completeness (non-null share): **{cov.conventional_completeness_pct:.4f}%**"
    )
    add(f"- Grid completeness (observed / covered cells): **{cov.grid_completeness_pct:.4f}%**")
    add(f"- Defective cells: **{dr.n_defective_cells:,}** of {dr.n_covered_cells:,} covered")
    add(f"- **Defect rate: {dr.percent:.4f}%**")
    add("")
    add(f"> {dr.definition}")
    add("")

    add("## Defects by reason code")
    add("")
    add("| Code | Name | Category | Counts toward rate | Count |")
    add("| --- | --- | --- | --- | ---: |")
    for code in sorted(r.defects_by_code):
        rc = reason_codes.get(code)
        add(
            f"| {code} | {rc.name} | {rc.category} | "
            f"{'yes' if rc.counts_toward_defect_rate else 'no'} | {r.defects_by_code[code]:,} |"
        )
    add("")

    add("## Coverage")
    add("")
    add("| Quantity | Cells |")
    add("| --- | ---: |")
    add(f"| Observed | {cov.n_observed_cells:,} |")
    add(f"| Absent (R01) | {cov.n_absent_cells:,} |")
    add(f"| Covered (observed + absent) | {cov.n_covered_cells:,} |")
    add(f"| Structurally excluded | {cov.n_structurally_excluded_cells:,} |")
    add(f"| Expected (covered + structural) | {cov.n_expected_cells:,} |")
    add("")

    add("## Structural absences (coverage facts, not defects)")
    add("")
    if r.structural_absences:
        add("| Station | Parameter | Domain | Code | Excluded cells |")
        add("| --- | --- | --- | --- | ---: |")
        for s in r.structural_absences:
            add(
                f"| {s.station_id} | {s.parameter} | {s.domain} | {s.reason_code} | "
                f"{s.excluded_cells:,} |"
            )
    else:
        add("_None._")
    add("")

    add("## Notable events")
    add("")
    if r.notable_events:
        add("| Rank | Code | Station | Parameter | Timestamp | What |")
        add("| ---: | --- | --- | --- | --- | --- |")
        for e in r.notable_events:
            add(
                f"| {e.rank} | {e.reason_code} | {e.station_id} | {e.parameter} | "
                f"{e.timestamp_utc} | {e.headline} |"
            )
    else:
        add("_None._")
    add("")

    add("## Defects by station")
    add("")
    add("| Station | Defective flags |")
    add("| --- | ---: |")
    for station in sorted(r.defects_by_station):
        add(f"| {station} | {r.defects_by_station[station]:,} |")
    add("")

    add("## Appendix: thresholds used")
    add("")
    add("```yaml")
    add(_thresholds_yaml(r.thresholds))
    add("```")
    add("")
    return "\n".join(lines)


def _thresholds_yaml(thresholds: dict[str, Any]) -> str:
    import yaml

    return yaml.safe_dump(
        thresholds, sort_keys=True, allow_unicode=True, default_flow_style=False
    ).strip()


def render_html(result: AuditResult) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("audit.html.j2")
    tokens_css = _TOKENS_CSS.read_text(encoding="utf-8")
    return template.render(
        r=result,
        cov=result.coverage,
        dr=result.defect_rate,
        codes=reason_codes.REASON_CODES,
        tokens_css=tokens_css,
    )


def write_reports(result: AuditResult, out_dir: Path) -> dict[str, Path]:
    """Write audit.json, audit.md, and audit.html into ``out_dir``. Deterministic."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": out_dir / "audit.json",
        "md": out_dir / "audit.md",
        "html": out_dir / "audit.html",
    }
    paths["json"].write_text(render_json(result), encoding="utf-8")
    paths["md"].write_text(render_markdown(result), encoding="utf-8")
    paths["html"].write_text(render_html(result), encoding="utf-8")
    return paths
