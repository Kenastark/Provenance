"""Brand invariants.

The palette is fixed and lives in exactly one place. These checks stop it from
quietly splitting into two sources of truth, which is how a design system rots:
one file gets edited, the other drifts, and nobody notices until the demo.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

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
