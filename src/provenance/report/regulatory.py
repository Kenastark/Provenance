"""The regulator-facing audit-trail export (§2), completed for phase 7.

For one reporting period (an audit run) this assembles a single, self-consistent
bundle: the reading accounting (how many readings were used and how many were excluded
or flagged, and why), the itemised defects, the structural exclusions, the model
versions in force, the sign-off records for any public alerts, and a **verification
hash** over the deterministic content so a regulator can prove two exports of the same
period are identical and untampered.

Three renderings share the one bundle — CSV (the itemised ledger), JSON (the full
structured record), and a printable one-page PDF summary — so a figure can never
disagree between formats: they are the same object serialised three ways.

The bundle is a pure value object: the router reads the database and hands the rows in,
and everything here — the ordering, the hash, the three renderings — is deterministic
and needs no database, which is what makes the hash reproducible and the renderings
testable.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass, field
from typing import Any

_CSV_COLUMNS = [
    "record_type",
    "station_id",
    "parameter",
    "timestamp_utc",
    "reason_code",
    "severity",
    "counts_toward_rate",
    "excluded_cells",
    "evidence",
]


@dataclass(frozen=True, slots=True)
class RegulatoryExport:
    """One reporting period, ready to render three ways and to verify."""

    run: dict[str, Any]
    definition: str
    accounting: dict[str, Any]
    defects: list[dict[str, Any]]
    structural_exclusions: list[dict[str, Any]]
    model_versions: dict[str, str]
    signoffs: list[dict[str, Any]] = field(default_factory=list)
    dispatches: list[dict[str, Any]] = field(default_factory=list)

    # ---- verification ----------------------------------------------------
    def verification_payload(self) -> dict[str, Any]:
        """The deterministic content the hash certifies.

        Covers the measured record — run identity, the reading accounting, and the
        itemised defect and exclusion ledgers, plus the model versions that produced
        them. It deliberately excludes the sign-off / dispatch appendix and any
        wall-clock of *when the export was generated*: those are provenance metadata,
        not the data being certified, and including them would make the hash change
        every time an alert is dispatched. The run's own ``generated_at`` (stable per
        run) is kept, so the hash still binds to a specific audit.
        """
        return {
            "run": {
                k: self.run.get(k)
                for k in (
                    "id",
                    "code_version",
                    "config_hash",
                    "data_checksum",
                    "generated_at",
                    "n_rows",
                )
            },
            "definition": self.definition,
            "accounting": self.accounting,
            "defects": self.defects,
            "structural_exclusions": self.structural_exclusions,
            "model_versions": self.model_versions,
        }

    def verification_hash(self) -> str:
        canonical = json.dumps(
            self.verification_payload(), sort_keys=True, ensure_ascii=False, default=str
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # ---- renderings ------------------------------------------------------
    def to_json_dict(self) -> dict[str, Any]:
        return {
            "audit_run_id": self.run.get("id"),
            "definition": self.definition,
            "accounting": self.accounting,
            "defects": self.defects,
            "structural_exclusions": self.structural_exclusions,
            "model_versions": self.model_versions,
            "signoffs": self.signoffs,
            "dispatches": self.dispatches,
            "reconciliation": {
                "n_defect_rows": len(self.defects),
                "n_structural_exclusions": len(self.structural_exclusions),
                "n_readings": self.accounting.get("n_readings"),
            },
            "verification_hash": self.verification_hash(),
        }

    def to_csv(self) -> str:
        buf = io.StringIO(newline="")
        writer = csv.DictWriter(buf, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for d in self.defects:
            writer.writerow(
                {
                    "record_type": "defect",
                    "station_id": d["station_id"],
                    "parameter": d["parameter"],
                    "timestamp_utc": d["timestamp_utc"],
                    "reason_code": d["reason_code"],
                    "severity": d["severity"],
                    "counts_toward_rate": d["counts_toward_rate"],
                    "excluded_cells": "",
                    "evidence": json.dumps(
                        d.get("evidence") or {}, sort_keys=True, ensure_ascii=False
                    ),
                }
            )
        for c in self.structural_exclusions:
            writer.writerow(
                {
                    "record_type": "structural_exclusion",
                    "station_id": c["station_id"],
                    "parameter": c["parameter"],
                    "timestamp_utc": "",
                    "reason_code": c["reason_code"],
                    "severity": "info",
                    "counts_toward_rate": False,
                    "excluded_cells": c["excluded_cells"],
                    "evidence": json.dumps(
                        {"domain": c["domain"]}, sort_keys=True, ensure_ascii=False
                    ),
                }
            )
        return buf.getvalue().replace("\r\n", "\n")

    def summary_lines(self) -> list[str]:
        """The printable summary, as text lines (also the PDF's content)."""
        acc = self.accounting
        top = _top_codes(self.defects)
        lines = [
            "PROVENANCE — Regulatory Audit-Trail Export",
            "",
            f"Reporting period (audit run): {self.run.get('id')}",
            f"Generated at:                 {self.run.get('generated_at')}",
            f"Code version / config hash:   {self.run.get('code_version')} / {self.run.get('config_hash')}",
            f"Data checksum:                {self.run.get('data_checksum')}",
            "",
            "Reading accounting",
            f"  Readings in period:         {acc.get('n_readings')}",
            f"  Covered cells:              {acc.get('n_covered_cells')}",
            f"  Defective cells (counted):  {acc.get('n_defective_cells')}",
            f"  Structural exclusions:      {acc.get('n_structural_exclusions')} (not in the rate)",
            f"  Defect rate:                {acc.get('defect_rate')}",
            f"  Conventional completeness:  {acc.get('conventional_completeness_pct')}%",
            "",
            "Top defect reason codes",
        ]
        lines += [f"  {code:<6} {n}" for code, n in top] or ["  (none)"]
        lines += [
            "",
            "Model versions",
        ]
        lines += [f"  {k}: {v}" for k, v in sorted(self.model_versions.items())]
        lines += [
            "",
            f"Public-alert sign-offs in period: {len(self.signoffs)}",
            f"Dispatches in period:             {len(self.dispatches)}",
            "",
            "Verification hash (SHA-256 over the certified content):",
            f"  {self.verification_hash()}",
            "",
            "Two exports of this period are identical iff this hash matches.",
        ]
        return lines

    def to_pdf(self) -> bytes:
        return _simple_pdf(self.summary_lines())


def _top_codes(defects: list[dict[str, Any]], *, limit: int = 8) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for d in defects:
        counts[d["reason_code"]] = counts.get(d["reason_code"], 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]


# ---------------------------------------------------------------------------
# A tiny, dependency-free, deterministic single-page PDF writer. A "printable
# summary" needs a real PDF, but not a whole rendering stack; this emits a valid
# PDF-1.4 with the standard Courier font and correct cross-reference offsets. No
# dates or randomness enter the bytes, so the same summary produces the same file.
# ---------------------------------------------------------------------------
def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _simple_pdf(lines: list[str], *, font_size: int = 9, leading: int = 12) -> bytes:
    # Build the text-drawing content stream (Courier, top-left origin, one line each).
    parts = ["BT", f"/F1 {font_size} Tf", "1 0 0 1 50 770 Tm", f"{leading} TL"]
    for i, line in enumerate(lines[:60]):  # a summary fits one Letter page
        parts.append(f"({_escape_pdf_text(line)}) Tj")
        if i != len(lines[:60]) - 1:
            parts.append("T*")
    parts.append("ET")
    content = "\n".join(parts).encode("latin-1", "replace")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n".encode()
    out += b"%%EOF"
    return bytes(out)
