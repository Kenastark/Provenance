"""The `prov` command line.

Phase 1 turns the placeholder subcommands into the real audit workflow:

    prov data profile    - what is in a data drop
    prov schema observe  - record the observed schema as a manifest
    prov fixtures make    - write the seeded synthetic corpus
    prov audit run        - run the audit and write the three reports
    prov audit report     - print a written audit back to the terminal

The CLI is a presentation layer: it loads data, calls the audit, and renders. It
holds no detection logic of its own.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from provenance import __version__
from provenance.config import reason_codes
from provenance.config.settings import REPO_ROOT

app = typer.Typer(
    name="prov",
    help="Provenance - an AI trust layer for environmental sensor networks.",
    no_args_is_help=True,
    add_completion=False,
)

data_app = typer.Typer(help="Inspect and profile input data.", no_args_is_help=True)
schema_app = typer.Typer(help="Observe and record the input schema.", no_args_is_help=True)
audit_app = typer.Typer(help="Run the audit and render its report.", no_args_is_help=True)
fixtures_app = typer.Typer(help="Generate the seeded synthetic corpus.", no_args_is_help=True)
codes_app = typer.Typer(help="Inspect the reason-code registry.", no_args_is_help=True)
db_app = typer.Typer(help="Manage the database schema and load data.", no_args_is_help=True)

app.add_typer(data_app, name="data")
app.add_typer(schema_app, name="schema")
app.add_typer(audit_app, name="audit")
app.add_typer(fixtures_app, name="fixtures")
app.add_typer(codes_app, name="codes")
app.add_typer(db_app, name="db")

console = Console()

_DATA_DEFAULT = REPO_ROOT / "data" / "raw"
_REPORTS_DEFAULT = REPO_ROOT / "reports"
_MANIFESTS_DEFAULT = REPO_ROOT / "data" / "manifests"


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(__version__)


# --------------------------------------------------------------------- codes
@codes_app.command("list")
def codes_list(defects_only: bool = typer.Option(False, help="Hide coverage codes.")) -> None:
    """List every reason code the system can emit."""
    table = Table(title="Reason codes", header_style="bold")
    for col in ("Code", "Name", "Category", "Severity", "Counts?", "Phase"):
        table.add_column(col)
    codes = (
        reason_codes.defect_codes() if defects_only else tuple(reason_codes.REASON_CODES.values())
    )
    for rc in sorted(codes, key=lambda c: c.code):
        table.add_row(
            rc.code,
            rc.name,
            str(rc.category),
            str(rc.severity),
            "yes" if rc.counts_toward_defect_rate else "no",
            str(rc.implemented_in_phase),
        )
    console.print(table)


@codes_app.command("show")
def codes_show(code: str) -> None:
    """Show one reason code and the sentence an operator would read."""
    rc = reason_codes.get(code.upper())
    console.print(f"[bold]{rc.code} {rc.name}[/bold]")
    console.print(rc.sentence)
    if rc.notes:
        console.print(f"[dim]{rc.notes}[/dim]")


# ---------------------------------------------------------------------- data
@data_app.command("profile")
def data_profile(
    data: Path = typer.Option(_DATA_DEFAULT, "--data", help="Data drop to profile."),
) -> None:
    """Profile a data drop: parameters, units, ranges, stations."""
    from provenance.io import loaders
    from provenance.schema.observe import observe

    frame = loaders.load_data(data)
    obs = observe(frame)
    console.print(
        f"[bold]{obs.n_rows:,}[/bold] readings across [bold]{len(obs.stations)}[/bold] stations, "
        f"[bold]{len(obs.parameters)}[/bold] parameters"
    )
    console.print(f"window {obs.timestamp_min} -> {obs.timestamp_max}  checksum {obs.checksum}")
    table = Table(title="Parameters", header_style="bold")
    for col in ("Parameter", "Units", "Readings", "Distinct", "Min", "Max"):
        table.add_column(col)
    for p in obs.parameter_profiles:
        table.add_row(
            p.parameter,
            ", ".join(p.units),
            f"{p.n_readings:,}",
            f"{p.n_distinct_values:,}",
            "-" if p.value_min is None else f"{p.value_min:g}",
            "-" if p.value_max is None else f"{p.value_max:g}",
        )
    console.print(table)


# -------------------------------------------------------------------- schema
@schema_app.command("observe")
def schema_observe(
    data: Path = typer.Option(_DATA_DEFAULT, "--data", help="Data drop to read."),
    manifests: Path = typer.Option(_MANIFESTS_DEFAULT, "--manifests", help="Where to write."),
) -> None:
    """Read the real schema and write an observed-schema manifest."""
    from provenance.io import loaders
    from provenance.schema.observe import observe, write_manifest

    frame = loaders.load_data(data)
    obs = observe(frame)
    path = write_manifest(obs, manifests)
    console.print(f"[green]Wrote[/green] {path}")


# --------------------------------------------------------------------- audit
@audit_app.command("run")
def audit_run(
    data: Path = typer.Option(_DATA_DEFAULT, "--data", help="Data drop to audit."),
    out: Path = typer.Option(_REPORTS_DEFAULT, "--out", help="Report output directory."),
) -> None:
    """Run the audit over a data drop and write audit.json / .md / .html."""
    from provenance.audit.orchestrator import run_audit
    from provenance.io import loaders
    from provenance.report.render import write_reports

    frame = loaders.load_data(data)
    result = run_audit(frame)
    paths = write_reports(result, out)
    dr = result.defect_rate
    console.print(
        f"[bold]{result.meta.n_rows:,}[/bold] readings  "
        f"conventional completeness [bold]{result.coverage.conventional_completeness_pct:.4f}%[/bold]"
    )
    console.print(
        f"[bold red]{dr.n_defective_cells:,}[/bold red] defective cells  "
        f"defect rate [bold red]{dr.percent:.4f}%[/bold red]"
    )
    for code in sorted(result.defects_by_code):
        console.print(
            f"  {code}  {reason_codes.get(code).name:<28} {result.defects_by_code[code]:,}"
        )
    console.print(f"[green]Wrote[/green] {paths['json']}, {paths['md']}, {paths['html']}")


@audit_app.command("report")
def audit_report(
    out: Path = typer.Option(_REPORTS_DEFAULT, "--out", help="Directory holding audit.md."),
) -> None:
    """Print a written audit (audit.md) back to the terminal."""
    md = Path(out) / "audit.md"
    if not md.exists():
        console.print(f"[red]No audit.md in {out}. Run `prov audit run` first.[/red]")
        raise typer.Exit(code=1)
    console.print(md.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ fixtures
@fixtures_app.command("make")
def fixtures_make(
    out: Path = typer.Option(REPO_ROOT / "tests" / "fixtures", "--out", help="Output directory."),
    seed: int = typer.Option(20260907, "--seed", help="Corpus seed."),
    days: int = typer.Option(14, "--days", help="Days of hourly data."),
    stations: int = typer.Option(
        4,
        "--stations",
        min=4,
        help="Station count. The four injected stations are always present; extra ones are clean.",
    ),
) -> None:
    """Generate the seeded synthetic corpus used by the test suite."""
    from provenance.fixtures.generator import write_corpus

    paths = write_corpus(out, seed=seed, n_days=days, n_stations=stations)
    console.print(
        f"[green]Wrote[/green] {paths['corpus']}, {paths['ledger']} and {paths['stations']} "
        f"({stations} stations)"
    )


# ------------------------------------------------------------------------- db
@db_app.command("upgrade")
def db_upgrade() -> None:
    """Bring the database schema up to head (Alembic on Postgres, ORM on SQLite)."""
    from provenance.io.db import migrate

    migrate.upgrade()
    console.print("[green]Schema at head.[/green]")


@db_app.command("reset")
def db_reset(
    yes: bool = typer.Option(False, "--yes", help="Confirm the destructive rebuild."),
) -> None:
    """Drop every table and rebuild the schema. Destructive."""
    from provenance.io.db import migrate

    if not yes:
        console.print("[red]Refusing to reset without --yes (this drops all data).[/red]")
        raise typer.Exit(code=1)
    migrate.reset()
    console.print("[green]Schema reset and at head.[/green]")


@db_app.command("load")
def db_load(
    source: Path = typer.Option(_DATA_DEFAULT, "--source", help="Data drop to load."),
) -> None:
    """Load a data drop into the database, idempotently."""
    from provenance.io.db import migrate

    report = migrate.load(source)
    if report.already_loaded:
        console.print(
            f"[yellow]Already loaded[/yellow] (batch {report.ingest_batch_id}); nothing changed."
        )
        return
    console.print(
        f"[green]Loaded[/green] {report.readings_inserted:,} readings, "
        f"{report.defects_inserted:,} defects, {report.trust_scores_inserted:,} trust scores "
        f"(run {report.audit_run_id})."
    )


if __name__ == "__main__":  # pragma: no cover
    app()
