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
graph_app = typer.Typer(
    help="Wind-conditioned graph and the propagation adjudicator.", no_args_is_help=True
)
models_app = typer.Typer(
    help="Train and apply the deweather and fault models (phase 5).", no_args_is_help=True
)
demo_app = typer.Typer(help="Deterministic, offline demo replay (phase 7).", no_args_is_help=True)

app.add_typer(data_app, name="data")
app.add_typer(schema_app, name="schema")
app.add_typer(audit_app, name="audit")
app.add_typer(fixtures_app, name="fixtures")
app.add_typer(codes_app, name="codes")
app.add_typer(db_app, name="db")
app.add_typer(graph_app, name="graph")
app.add_typer(models_app, name="models")
app.add_typer(demo_app, name="demo")

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
    with_weather: bool = typer.Option(
        False,
        "--with-weather/--no-with-weather",
        help="OPT-IN. Add Wind_Speed/Wind_Direction (one station lacks them, mirroring the "
        "real network's KER15 gap) and couple PM10 to wind speed so the deweather model has "
        "a real signal. The default corpus is unaffected either way.",
    ),
    with_plume: bool = typer.Option(
        False,
        "--with-plume/--no-with-plume",
        help="OPT-IN, requires --with-weather. Plant one wind-corroborated NO plume and one "
        "isolated, uncorroborated spike of the same magnitude, so the graph adjudicator has a "
        "GENUINE_EVENT and a LIKELY_FAULT to find on evidence.",
    ),
) -> None:
    """Generate the seeded synthetic corpus used by the test suite.

    The default output (no flags) is byte-identical to always: it is pinned by the
    golden recovery ledger (tests/integration/test_golden_recovery.py). --with-weather
    and --with-plume are additive, opt-in demo scenarios; see
    provenance.fixtures.demo_scenario for what each adds.
    """
    from provenance.fixtures.generator import write_corpus

    if with_plume and not with_weather:
        console.print(
            "[red]--with-plume requires --with-weather (a plume needs a wind field).[/red]"
        )
        raise typer.Exit(code=1)

    paths = write_corpus(
        out,
        seed=seed,
        n_days=days,
        n_stations=stations,
        with_weather=with_weather,
        with_plume=with_plume,
    )
    extra = []
    if with_weather:
        extra.append("weather")
    if with_plume:
        extra.append("plume")
    suffix = f" (+{', '.join(extra)})" if extra else ""
    console.print(
        f"[green]Wrote[/green] {paths['corpus']}, {paths['ledger']} and {paths['stations']} "
        f"({stations} stations){suffix}"
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


# ---------------------------------------------------------------------- graph
_ADJ_DEFAULT = REPO_ROOT / "reports" / "adjudications"

_VERDICT_STYLE = {
    "GENUINE_EVENT": "bold green",
    "LIKELY_FAULT": "bold red",
    "AMBIGUOUS": "bold yellow",
}


@graph_app.command("adjudicate")
def graph_adjudicate(
    data: Path = typer.Option(_DATA_DEFAULT, "--data", help="Data drop to adjudicate."),
    out: Path = typer.Option(_ADJ_DEFAULT, "--out", help="Where to write evidence bundles."),
    limit: int = typer.Option(10, "--limit", help="How many top-ranked events to adjudicate."),
    learned: bool = typer.Option(
        False,
        "--learned/--analytic",
        help="Use the HST-GAT forecast as the expectation (falls back to analytic if no "
        "artefact). Default is the phase-4 analytic prior.",
    ),
) -> None:
    """Rank the corpus's candidate events, adjudicate each, and write evidence bundles.

    Nothing about the outcome is assumed: the top event is whatever ranks highest by
    magnitude, and its verdict is whatever the adjudicator returns. With ``--learned``
    the expectation each neighbour is judged against comes from the HST-GAT (§6.4); if
    no artefact is present it degrades to the analytic prior and the bundle says so.
    """
    from provenance.graph.replay import replay_path

    factory = _learned_factory(data) if learned else None
    if learned and factory is None:
        console.print(
            "[yellow]--learned requested but no HST-GAT artefact loaded; "
            "using the analytic prior (recorded in each bundle).[/yellow]"
        )
    adjudications = replay_path(data, out, limit=limit, expectation_factory=factory)
    if not adjudications:
        console.print("[yellow]No candidate events found to adjudicate.[/yellow]")
        raise typer.Exit(code=0)

    table = Table(title="Adjudicated events (ranked by magnitude)", header_style="bold")
    for col in ("Rank", "Station", "Parameter", "Timestamp", "Excess", "Verdict", "Confidence"):
        table.add_column(col)
    for rank, adj in enumerate(adjudications, start=1):
        ev = adj.event
        style = _VERDICT_STYLE.get(adj.verdict.value, "")
        table.add_row(
            str(rank),
            ev.station_id,
            ev.parameter,
            ev.timestamp.isoformat(),
            f"{ev.excess:,.1f} {ev.unit}".strip(),
            f"[{style}]{adj.verdict.value}[/{style}]" if style else adj.verdict.value,
            f"{adj.confidence:.2f} ({adj.confidence_band.value})",
        )
    console.print(table)

    review = [a for a in adjudications if a.routes_to_review]
    if review:
        console.print(
            f"[yellow]{len(review)} event(s) routed to human review (AMBIGUOUS).[/yellow]"
        )
    console.print(f"[green]Wrote[/green] {len(adjudications)} bundle(s) and an index to {out}")

    # Learned mode with a loaded model also exports the attention overlay for the map —
    # "which neighbours most influenced this call" (§8) — for the top-ranked event.
    if learned and factory is not None:
        from provenance.config.loading import load_graph_config
        from provenance.graph.build import station_points_from_metadata
        from provenance.graph.wind import WindField
        from provenance.io import loaders
        from provenance.models.hstgat.attention import write_overlay_for_drop

        frame = loaders.load_data(data)
        pts = station_points_from_metadata(dict(loaders.load_station_metadata(data)))
        overlay_path = write_overlay_for_drop(
            frame,
            pts,
            WindField.from_frame(frame),
            load_graph_config(),
            out,
            at_time=adjudications[0].event.timestamp,
        )
        if overlay_path is not None:
            console.print(f"[green]Wrote attention overlay[/green] {overlay_path}")


@graph_app.command("adjudicate-db")
def graph_adjudicate_db(
    source: Path = typer.Option(
        _DATA_DEFAULT, "--source", help="Data drop already loaded to the DB."
    ),
) -> None:
    """Adjudicate the events stored in the database and write their verdicts back.

    Run after ``prov db load``: it fills the ``verdict`` the audit left null, so the
    dashboard timeline shows a plume/fault/ambiguous label per event.
    """
    import asyncio

    from provenance.graph.persist import adjudicate_stored_events
    from provenance.io import loaders
    from provenance.io.db.engine import make_engine, make_sessionmaker

    frame = loaders.load_data(source)
    station_meta = loaders.load_station_metadata(source)

    async def _run() -> int:
        from provenance.config.settings import get_settings

        engine = make_engine(get_settings().database_url)
        sm = make_sessionmaker(engine)
        try:
            async with sm() as session:
                return await adjudicate_stored_events(session, frame, dict(station_meta))
        finally:
            await engine.dispose()

    updated = asyncio.run(_run())
    console.print(f"[green]Adjudicated[/green] {updated} stored event(s); verdicts written.")


@graph_app.command("snapshot")
def graph_snapshot(
    data: Path = typer.Option(_DATA_DEFAULT, "--data", help="Data drop to build the graph from."),
    at: str = typer.Option(
        "", "--at", help="Timestamp (ISO-8601). Defaults to the latest reading time."
    ),
) -> None:
    """Build one graph snapshot and print its node/edge shape."""
    import pandas as pd

    from provenance.graph.build import build_snapshot, station_points_from_metadata
    from provenance.graph.wind import WindField
    from provenance.io import loaders

    frame = loaders.load_data(data)
    meta = loaders.load_station_metadata(data)
    points = station_points_from_metadata(dict(meta))
    if not points:
        console.print("[red]No station coordinates in this drop; cannot build a graph.[/red]")
        raise typer.Exit(code=1)
    from provenance.config.loading import load_graph_config
    from provenance.schema import canonical as C

    when = pd.Timestamp(at) if at else pd.Timestamp(frame[C.TIMESTAMP].max())
    wind = WindField.from_frame(frame)
    snap = build_snapshot(points, wind, when, load_graph_config())
    summary = snap.summary()
    console.print(f"[bold]Snapshot at {summary['timestamp']}[/bold]")
    console.print(f"wind available: {snap.meta.get('wind_available')}")
    console.print("nodes:", summary["nodes"])
    console.print("edges:", summary["edges"])


# ------------------------------------------------------------------- models
@models_app.command("train")
def models_train(
    demo: bool = typer.Option(
        True, "--demo/--no-demo", help="Train on the seeded weather-coupled demo corpus."
    ),
    source: Path | None = typer.Option(
        None, "--source", help="Real data drop to train on (implies --no-demo)."
    ),
    stations: int = typer.Option(6, "--stations", min=4, help="Demo corpus station count."),
    days: int = typer.Option(30, "--days", help="Demo corpus days of hourly data."),
) -> None:
    """Train the deweather and fault models and save their artefacts and cards.

    A model without a card cannot load (§5); training writes both the artefact and its
    card sidecar, plus a human-readable card under docs/model-cards/.
    """
    from provenance.fixtures.weather import generate_weather_corpus
    from provenance.models import registry
    from provenance.models.deweather import train_deweather
    from provenance.models.fault import train_fault_classifier

    if not demo and source is None:
        console.print("[red]--no-demo requires --source pointing at a real data drop.[/red]")
        raise typer.Exit(code=1)

    if source is not None:
        from provenance.io import loaders

        frame = loaders.load_data(source)
        weather = None  # HungaroMet feed is unconfirmed; in-situ meteorology only.
        console.print(f"Training on real drop {source} ({len(frame):,} readings, in-situ weather).")
    else:
        frame, weather = generate_weather_corpus(n_stations=stations, n_days=days)
        console.print(f"Training on the seeded demo corpus ({stations} stations, {days} days).")

    dw = train_deweather(frame, weather=weather)
    console.print(
        f"[green]Deweather[/green] {dw.version}: "
        + ", ".join(f"{p} R²={dw.metrics[p].cv_r2_mean:.2f}" for p in dw.pollutants)
    )
    fc = train_fault_classifier(frame, dw, weather=weather)
    console.print(
        f"[green]Fault[/green] {fc.version}: recall "
        + ", ".join(f"{k}={v:.2f}" for k, v in sorted(fc.signature_recall.items()))
        + f" | meteo precision {fc.meteo_precision:.2f}"
    )
    dw_paths = registry.save_model(dw)
    fc_paths = registry.save_model(fc)
    console.print(f"[green]Saved[/green] {dw_paths['model'].name}, card {dw_paths['doc']}")
    console.print(f"[green]Saved[/green] {fc_paths['model'].name}, card {fc_paths['doc']}")
    console.print(
        "[dim]No headline accuracy is reported for the classifier (standing rule 4).[/dim]"
    )


def _learned_factory(data: Path):  # type: ignore[no-untyped-def]
    """Build a per-event learned expectation factory for ``data``, or None if no artefact.

    Lives in the CLI (which may import ``models``) so the ``graph`` layer never does; the
    graph adjudicator only ever sees the injected factory (dependency injection).
    """
    from provenance.config.loading import load_graph_config
    from provenance.graph.adjudicate import AdjudicatorParams
    from provenance.graph.build import station_points_from_metadata
    from provenance.graph.wind import WindField
    from provenance.io import loaders
    from provenance.models.hstgat.forecast import learned_provider_factory
    from provenance.models.hstgat.store import load_latest

    if load_latest() is None:
        return None
    frame = loaders.load_data(data)
    meta = loaders.load_station_metadata(data)
    points = station_points_from_metadata(dict(meta))
    cfg = load_graph_config()
    window = AdjudicatorParams.from_config(cfg).baseline_window_hours
    wind = WindField.from_frame(frame)
    return learned_provider_factory(frame, points, wind, cfg, baseline_window_hours=window)


@models_app.command("train-hstgat")
def models_train_hstgat(
    source: Path = typer.Option(
        _DATA_DEFAULT, "--source", help="Data drop with station coordinates to train on."
    ),
    target: str = typer.Option("PM10", "--target", help="Target pollutant to reconstruct."),
    epochs: int = typer.Option(0, "--epochs", help="Override configured epochs (0 = use config)."),
    baseline: bool = typer.Option(
        True,
        "--baseline/--no-baseline",
        help="Also train the GCN baseline for the card comparison.",
    ),
) -> None:
    """Train the HST-GAT (§6.4), calibrate a conformal interval, and save it with a card.

    The artefact is gitignored and reproducible from this command; the model card records
    the parameter count, the achieved conformal coverage and the GCN-baseline comparison —
    never a propagation accuracy figure (standing rule 4).
    """
    from provenance.config.loading import config_hash, load_graph_config, load_models_config
    from provenance.graph.build import station_points_from_metadata
    from provenance.graph.wind import WindField
    from provenance.io import loaders
    from provenance.models.hstgat import store
    from provenance.models.hstgat.conformalize import calibrate_and_coverage
    from provenance.models.hstgat.data import build_batch
    from provenance.models.hstgat.train import train_model
    from provenance.schema.observe import observe

    frame = loaders.load_data(source)
    meta = loaders.load_station_metadata(source)
    points = station_points_from_metadata(dict(meta))
    if not points:
        console.print(
            "[red]No station coordinates in this drop; cannot train the graph model.[/red]"
        )
        raise typer.Exit(code=1)

    gcfg = load_graph_config()
    mcfg = load_models_config()
    wind = WindField.from_frame(frame)
    checksum = observe(frame).checksum
    try:
        batch = build_batch(frame, points, wind, gcfg, target_parameter=target)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    ep = epochs if epochs > 0 else None
    console.print(f"Training HST-GAT on {batch.n_env} stations x {batch.n_times} hours ({target}).")
    trained = train_model(batch, kind="hstgat", cfg=mcfg, epochs=ep, data_checksum=checksum)
    console.print(
        f"[green]HST-GAT[/green] {trained.version}: {trained.parameter_count} parameters."
    )

    baseline_metrics = None
    if baseline:
        gcn = train_model(batch, kind="gcn", cfg=mcfg, epochs=ep, data_checksum=checksum)
        baseline_metrics = gcn.metrics
        console.print(f"[green]GCN baseline[/green] {gcn.parameter_count} parameters (comparison).")

    conf_cfg = mcfg.get("conformal", {})
    conformal, coverage = calibrate_and_coverage(
        trained.model,
        trained.mean,
        trained.std,
        batch,
        alpha=float(conf_cfg.get("alpha", 0.1)),
        n_splits=int(mcfg["hstgat"]["n_splits"]),
        min_calibration=int(conf_cfg.get("min_calibration", 20)),
    )
    if coverage.get("calibrated"):
        console.print(
            f"[green]Conformal[/green] nominal {coverage['nominal_coverage']} → "
            f"empirical {coverage['empirical_coverage']} (n={coverage['n_calibration']})."
        )
    else:
        console.print(f"[yellow]Conformal not calibrated:[/yellow] {coverage.get('reason')}")

    # Persist the calibrator itself (not just its coverage): the q travels with the
    # artefact so the learned adjudication can attach a calibrated interval per event.
    conformal_dict = conformal.to_dict() if conformal is not None else None
    paths = store.save_model(
        trained,
        config_hash=config_hash(),
        coverage=coverage,
        baseline=baseline_metrics,
        conformal=conformal_dict,
    )
    console.print(f"[green]Saved[/green] {paths['model'].name}, card {paths['doc']}")
    console.print("[dim]No propagation accuracy/F1 is reported (standing rule 4).[/dim]")


@models_app.command("residuals")
def models_residuals(
    source: Path = typer.Option(_DATA_DEFAULT, "--source", help="Data drop already loaded to DB."),
) -> None:
    """Compute deweathered residuals for a loaded drop and store them with the model version."""
    import asyncio

    from provenance.io import loaders
    from provenance.io.db import repository as repo
    from provenance.io.db.engine import make_engine, make_sessionmaker
    from provenance.models import registry
    from provenance.models.deweather import store_residuals

    bundle = registry.load_bundle()
    if bundle is None:
        console.print("[red]No trained models found. Run `prov models train` first.[/red]")
        raise typer.Exit(code=1)
    frame = loaders.load_data(source)

    async def _run() -> int:
        from provenance.config.settings import get_settings

        engine = make_engine(get_settings().database_url)
        sm = make_sessionmaker(engine)
        try:
            async with sm() as session:
                run = await repo.latest_audit_run(session)
                return await store_residuals(
                    session,
                    bundle.deweather,
                    frame,
                    audit_run_id=run.id if run is not None else None,
                )
        finally:
            await engine.dispose()

    n = asyncio.run(_run())
    console.print(f"[green]Stored[/green] {n:,} residuals under model {bundle.deweather.version}.")


# --------------------------------------------------------------------- demo
_DEMO_DEFAULT = REPO_ROOT / ".demo-corpus"


def _load_demo_drop(data: Path):  # type: ignore[no-untyped-def]
    """Load the demo corpus frame + station metadata, failing loudly if it is absent."""
    from provenance.io import loaders

    data = Path(data)
    has_corpus = (data / "corpus.parquet").exists() or any(data.glob("**/DEB-KER*"))
    if not has_corpus:
        console.print(
            f"[red]No demo corpus at {data}.[/red] Generate one first, offline, with:\n"
            f"  prov fixtures make --out {data} --stations 18"
        )
        raise typer.Exit(code=1)
    frame = loaders.load_data(data)
    meta = dict(loaders.load_station_metadata(data))
    return frame, meta


@demo_app.command("list")
def demo_list() -> None:
    """List the demo scenarios."""
    from provenance.ops import demo as demo_mod

    table = Table(title="Demo scenarios", header_style="bold")
    table.add_column("Scenario")
    for name in demo_mod.available_scenarios():
        table.add_row(name)
    console.print(table)


@demo_app.command("run")
def demo_run(
    scenario: str = typer.Option(..., "--scenario", help="Which scenario to replay."),
    data: Path = typer.Option(_DEMO_DEFAULT, "--data", help="Demo corpus directory."),
    speed: float = typer.Option(1.0, "--speed", min=0.1, help="Playback speed multiplier."),
    out: Path | None = typer.Option(None, "--out", help="Write the replay sequence as JSON."),
) -> None:
    """Replay one scenario deterministically. Prints the timed screen sequence.

    The sequence is a pure function of the seeded corpus — two runs are byte-identical —
    and needs no network: it is the drive script the live dashboard consumes.
    """
    import json

    from provenance.ops import demo as demo_mod

    if scenario not in demo_mod.available_scenarios():
        console.print(
            f"[red]Unknown scenario {scenario!r}.[/red] Options: "
            f"{', '.join(demo_mod.available_scenarios())}"
        )
        raise typer.Exit(code=1)
    frame, meta = _load_demo_drop(data)
    sc = demo_mod.build_scenario(scenario, frame, meta, speed=speed)

    console.print(f"[bold]{sc.title}[/bold]  ({sc.window['start']} → {sc.window['end']})")
    table = Table(title=f"{scenario} @ {speed}x", header_style="bold")
    for col in ("t+ms", "Screen", "Headline", "Numbers"):
        table.add_column(col)
    for step in sc.steps:
        nums = ", ".join(f"{k}={v}" for k, v in step.numbers.items())
        table.add_row(str(step.at_offset_ms), step.screen, step.headline, nums[:60])
    console.print(table)
    if out is not None:
        Path(out).write_text(
            json.dumps(sc.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        console.print(f"[green]Wrote[/green] {out}")


@demo_app.command("rehearse")
def demo_rehearse(
    data: Path = typer.Option(_DEMO_DEFAULT, "--data", help="Demo corpus directory."),
    out: Path = typer.Option(
        REPO_ROOT / "reports" / "demo", "--out", help="Directory for the replay JSON."
    ),
    speed: float = typer.Option(1.0, "--speed", min=0.1, help="Playback speed multiplier."),
) -> None:
    """Build every scenario (the full 7-minute script) and write the replay sequences.

    Deterministic and offline; ``scripts/record-demo.sh`` calls this to drive the
    fallback recording.
    """
    import json

    from provenance.ops import demo as demo_mod

    frame, meta = _load_demo_drop(data)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    scenarios = demo_mod.build_all(frame, meta, speed=speed)
    index = []
    for name, sc in scenarios.items():
        path = out / f"{name}.json"
        path.write_text(
            json.dumps(sc.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        index.append({"scenario": name, "file": path.name, "n_steps": len(sc.steps)})
    (out / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    console.print(f"[green]Wrote[/green] {len(scenarios)} scenario(s) and an index to {out}")


if __name__ == "__main__":  # pragma: no cover
    app()
