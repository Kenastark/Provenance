"""Brand invariants.

The palette is fixed and lives in exactly one place. These checks stop it from
quietly splitting into two sources of truth, which is how a design system rots:
one file gets edited, the other drifts, and nobody notices until the demo.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# scripts/ is not a package on the path by default; the brand generators live there.
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# The design file is the source of truth; the app copy is derived from it.
DESIGN_TOKENS = REPO / "design" / "tokens" / "tokens.css"
APP_TOKENS = REPO / "apps" / "web" / "src" / "styles" / "tokens.css"


def test_token_files_are_byte_identical() -> None:
    """apps/web's token file must be a byte-for-byte copy of the design source.

    If this fails, the app copy has drifted from design/tokens/tokens.css. The
    design file is authoritative: copy it over the app file, do not edit the app
    file to match.
    """
    design = DESIGN_TOKENS.read_bytes()
    app = APP_TOKENS.read_bytes()
    assert design == app, (
        f"{APP_TOKENS.relative_to(REPO)} has drifted from the design source "
        f"{DESIGN_TOKENS.relative_to(REPO)}. The design file is authoritative; "
        "regenerate the app copy from it rather than editing the copy."
    )


# The logo assets the dashboard serves are copies of the design originals, for the
# same reason the tokens are: two files, one truth.
DESIGN_LOGO = REPO / "design" / "logo"
APP_PUBLIC = REPO / "apps" / "web" / "public"

SERVED_LOGO_ASSETS = (
    "provenance-lockup-horizontal.svg",
    "provenance-lockup-horizontal-reversed.svg",
    "provenance-mark-16.svg",
    "provenance-mark.svg",
)


@pytest.mark.parametrize("name", SERVED_LOGO_ASSETS)
def test_served_logo_assets_match_the_design_originals(name: str) -> None:
    """Every logo the app serves is byte-identical to the one in design/logo."""
    design = DESIGN_LOGO / name
    served = APP_PUBLIC / name
    assert design.exists(), f"{name} is missing from design/logo."
    assert served.exists(), (
        f"{name} is missing from apps/web/public. The dashboard serves it, so it has "
        "to be there; copy it from design/logo rather than drawing a new one."
    )
    assert design.read_bytes() == served.read_bytes(), (
        f"apps/web/public/{name} has drifted from design/logo/{name}. The design "
        "directory is authoritative."
    )


def test_reversed_lockup_differs_from_the_original_only_in_the_wordmark_ink() -> None:
    """The dark-theme lockup is the approved artwork, re-inked and nothing else.

    The default theme is dark, and the approved lockup's wordmark is the brand's
    near-black — invisible on it. The reversed asset fixes that by substituting the
    wordmark's fill for ``--prov-white`` and changing nothing else: same geometry,
    same mark, same gradient. This asserts that, so "reversed lockup" can never
    quietly become "a second, different logo".
    """
    original = (DESIGN_LOGO / "provenance-lockup-horizontal.svg").read_text("utf-8")
    reversed_ = (DESIGN_LOGO / "provenance-lockup-horizontal-reversed.svg").read_text("utf-8")

    # Normalise the one intended difference and the title/comment that documents it.
    normalised = reversed_.replace('fill="#FFFFFF"', 'fill="#031436"')
    normalised = re.sub(r"<title>.*?</title>\s*(<!--.*?-->)?", "", normalised, flags=re.DOTALL)
    baseline = re.sub(r"<title>.*?</title>", "", original, flags=re.DOTALL)

    assert normalised.split() == baseline.split(), (
        "The reversed lockup differs from the approved lockup by more than the "
        "wordmark's ink. Regenerate it: python scripts/gen_reversed_lockup.py"
    )


def test_reversed_lockup_is_not_stale() -> None:
    """The generated asset matches what the generator would produce today."""
    from scripts.gen_reversed_lockup import main

    assert main(["--check"]) == 0


# Colour lives in CSS. Classes composed at runtime are invisible to Tailwind's
# content scanner, so the ones the UI builds from a state name must be safelisted
# or the rules are stripped from the bundle - which is how a whole trust state
# silently loses its colour on the map.
TAILWIND_CONFIG = REPO / "apps" / "web" / "tailwind.config.ts"
RUNTIME_STATE_CLASSES = (
    "prov-state-verified",
    "prov-state-degraded",
    "prov-state-fault",
    "prov-state-unknown",
)


@pytest.mark.parametrize("class_name", RUNTIME_STATE_CLASSES)
def test_runtime_state_classes_are_safelisted(class_name: str) -> None:
    config = TAILWIND_CONFIG.read_text("utf-8")
    assert f'"{class_name}"' in config, (
        f"{class_name} is composed at runtime as `prov-state-${{state}}` and is not in "
        "tailwind.config.ts's safelist, so Tailwind will strip its rule and that state "
        "will render with no colour at all."
    )


# The generated frontend client is a second copy of the API schema, the reason-code
# registry and the design tokens. Its drift check is only a guarantee if it cannot
# be skipped, which means it must live in a workflow with no `paths:` filter.
WORKFLOWS = REPO / ".github" / "workflows"


def _workflow(name: str) -> dict:
    import yaml

    return yaml.safe_load((WORKFLOWS / name).read_text("utf-8"))


def test_contract_drift_check_runs_in_an_unfiltered_workflow() -> None:
    """The contract check must not sit behind a path filter.

    A filter only protects against the changes someone thought to list. Editing
    ``trust/score.py``'s ``to_dict`` or a repository row builder changes the served
    contract without touching any frontend path, and the dashboard would then
    describe a system that no longer exists with CI green.
    """
    hosts = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        config = _workflow(path.name)
        jobs = config.get("jobs", {})
        if "contract" not in jobs:
            continue
        # PyYAML parses a bare `on:` key as the boolean True.
        triggers = config.get(True) or config.get("on") or {}
        pull_request = triggers.get("pull_request") or {}
        filtered = isinstance(pull_request, dict) and bool(pull_request.get("paths"))
        hosts.append((path.name, filtered))

    assert hosts, "No workflow defines a `contract` job; the drift check is not wired up."
    unfiltered = [name for name, filtered in hosts if not filtered]
    assert unfiltered, (
        "Every workflow defining the `contract` job filters by path "
        f"({[n for n, _ in hosts]}). Move it to one that always runs."
    )


# `make demo` is the documented one-command path to a working demo. It once brought
# up Postgres, loaded and audited the corpus, and opened the dashboard against
# nothing, because the API was never started - and no test could notice, since CI
# started the API its own way.
MAKEFILE = REPO / "Makefile"


def _recipe(target: str) -> list[str]:
    """The lines of one Makefile target's recipe."""
    lines = MAKEFILE.read_text("utf-8").splitlines()
    out: list[str] = []
    collecting = False
    for line in lines:
        if line.startswith(f"{target}:"):
            collecting = True
            continue
        if collecting:
            if line.startswith("\t"):
                out.append(line.strip())
            elif line.strip() and not line.startswith("#"):
                break
    return out


def test_make_demo_starts_every_service_the_dashboard_needs() -> None:
    """The demo target must bring up the stack, the data, the API and the dashboard.

    Each of these is a thing the dashboard renders an empty state for when it is
    missing, which is why omitting one produced a demo that looked plausible and
    showed nothing.
    """
    recipe = " ".join(_recipe("demo"))
    for needed, why in [
        ("up", "the database and cache"),
        ("demo-data", "the corpus and the audit run"),
        ("api-bg", "the API the dashboard reads from"),
        ("web", "the dashboard itself"),
    ]:
        assert needed in recipe, (
            f"`make demo` no longer starts {why} (missing `{needed}`). Every screen "
            "would render its empty state against a stack that looks healthy."
        )


def test_ci_starts_the_api_through_the_documented_target() -> None:
    """CI must exercise `make api-bg`, not a private uvicorn invocation.

    If CI starts the API its own way, a broken `make demo` passes every check.
    """
    workflow = (WORKFLOWS / "frontend.yml").read_text("utf-8")
    assert "make api-bg" in workflow, (
        "The e2e workflow starts the API by hand instead of through `make api-bg`, "
        "so nothing exercises the command the documentation tells a person to run."
    )
