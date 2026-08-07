"""The `prov` command line.

Phase 0 registers the command groups so the shape of the tool is visible from
the start. Subcommands raise a clear "not built yet, see phase N" message rather
than failing obscurely.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from provenance import __version__
from provenance.config import reason_codes

app = typer.Typer(
    name="prov",
    help="Provenance - an AI trust layer for environmental sensor networks.",
    no_args_is_help=True,
    add_completion=False,
)

data_app = typer.Typer(help="Inspect and profile input data.", no_args_is_help=True)
audit_app = typer.Typer(help="Run the audit and render its report.", no_args_is_help=True)
fixtures_app = typer.Typer(help="Generate the seeded synthetic corpus.", no_args_is_help=True)
codes_app = typer.Typer(help="Inspect the reason-code registry.", no_args_is_help=True)

app.add_typer(data_app, name="data")
app.add_typer(audit_app, name="audit")
app.add_typer(fixtures_app, name="fixtures")
app.add_typer(codes_app, name="codes")

console = Console()


def _not_yet(phase: int, what: str) -> None:
    """Exit with a message that says which phase builds this, not a stack trace."""
    console.print(f"[yellow]{what} lands in phase {phase}. Not built yet.[/yellow]")
    raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(__version__)


@codes_app.command("list")
def codes_list(defects_only: bool = typer.Option(False, help="Hide coverage codes.")) -> None:
    """List every reason code the system can emit."""
    table = Table(title="Reason codes", header_style="bold")
    table.add_column("Code")
    table.add_column("Name")
    table.add_column("Category")
    table.add_column("Severity")
    table.add_column("Counts?")
    table.add_column("Phase")
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


@data_app.command("profile")
def data_profile() -> None:
    """Profile an input drop."""
    _not_yet(1, "Data profiling")


@audit_app.command("run")
def audit_run() -> None:
    """Run the audit over a data drop."""
    _not_yet(1, "The audit engine")


@fixtures_app.command("make")
def fixtures_make() -> None:
    """Generate the seeded synthetic corpus used by the test suite."""
    _not_yet(1, "The fixture generator")


if __name__ == "__main__":  # pragma: no cover
    app()
