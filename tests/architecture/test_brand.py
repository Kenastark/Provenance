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
