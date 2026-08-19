# Update 1 — lockup

Branch: `update-1-lockup`. Tag: `v1.0.2-update`.

## What was built

Two independent fixes to the top-bar lockup, one PR.

**Fix A — the dark-mode lockup did not render at all.** Diagnosis verified before
any change was made:

```
$ python3 -c "import xml.etree.ElementTree as ET; ET.parse('apps/web/public/provenance-lockup-horizontal-reversed.svg')"
Traceback (most recent call last):
  ...
xml.etree.ElementTree.ParseError: not well-formed (invalid token): line 4, column 36
```

Line 4 of the file read:

```
       with the wordmark inked in --prov-white so it stays legible on the dark
```

Column 36 lands exactly on the `--` in `--prov-white` — a double hyphen inside an
XML comment (`<!-- ... -->`), which the XML spec forbids anywhere in a comment's
body. Browsers parsing SVG-in-`<img>` are strict XML parsers and reject the whole
file, so the dashboard's default (dark) theme rendered a broken image where the
lockup belongs. The light theme was unaffected — it serves the unreversed asset,
whose comment never mentions `--prov-white`.

Fixed at the source: reworded the `_NOTE` string in `scripts/gen_reversed_lockup.py`
("inked in the prov-white token" instead of "inked in --prov-white"), then
regenerated both `design/logo/provenance-lockup-horizontal-reversed.svg` and its
`apps/web/public/` mirror with `python scripts/gen_reversed_lockup.py`. Both files
now parse cleanly under `xml.etree.ElementTree`. No artwork, geometry, or fill
changed — confirmed by diff (only the comment text differs) and by the existing
`test_reversed_lockup_differs_from_the_original_only_in_the_wordmark_ink` test,
which still passes.

Added a permanent guard: `test_logo_svgs_are_well_formed_xml` in
`tests/architecture/test_brand.py`, parametrized over every `.svg` under
`design/logo/` and `apps/web/public/` (discovered by glob, not hand-listed), each
parsed with `xml.etree.ElementTree` and failed with the file's own `ParseError` on
mismatch.

**Visual baselines were captured with the logo already broken.** Read back the
pre-fix `map-dark-chromium-darwin.png` and `timeline-dark-chromium-linux.png`
baselines: both show the standard broken-image glyph in the top-left where the
lockup belongs, on every dark-theme screen, on both platforms. The light-theme
baselines render the lockup correctly — the bug is dark-only, matching the
diagnosis. The visual-regression gate had been blessing this bug for a full phase
plus sixteen baseline captures, not catching it, because a byte-identical broken
image compares equal to itself on every subsequent run.

**Fix B — the lockup rendered too small.** Doubled the `<img>` in
`apps/web/src/features/shell/TopBar.tsx` from 28px to 56px (both the `height` prop
and the inline `style`). Raised `--prov-topbar-height` 56px → 72px in both
`design/tokens/tokens.css` and its `apps/web/src/styles/tokens.css` mirror (copied
byte-for-byte, per `test_token_files_are_byte_identical`) so the larger lockup sits
with 8px of breathing room top and bottom rather than touching both edges.
Grepped the frontend for other things pinned to the old 56px bar height (`h-14`,
`56px`, `topbar` outside `TopBar.tsx`/the token files) and for hardcoded viewport
math in `App.tsx` — found none; the shell below the header is `flex-1 min-h-0` and
absorbs the extra 16px without any other change. No artwork, gradient, or palette
value touched.

## Test gate

- `make check` (ruff, ruff format, mypy strict, pytest, contract-drift check):
  green. 651 passed, 90.58% coverage (floor 88%). Frontend contract current.
- `make web-lint` (eslint + tsc --noEmit): green, no findings.
- `make web-test` (vitest + coverage): green. 192 passed;
  `features/shell/TopBar.tsx` at 100% statement/branch coverage.
- All sixteen visual baselines regenerated: `pnpm e2e:update` (darwin, 50/50
  e2e tests passed) and `make web-visual-linux` (the pinned
  `mcr.microsoft.com/playwright:v1.62.1-noble` container, 8/8 passed). Twelve of
  the sixteen files changed — the six screens whose screenshot includes the top
  bar (`map`, `station-detail`, `timeline`, dark + light), on both platforms:
  - `map-dark-chromium-darwin.png`, `map-dark-chromium-linux.png`
  - `map-light-chromium-darwin.png`, `map-light-chromium-linux.png`
  - `station-detail-dark-chromium-darwin.png`, `station-detail-dark-chromium-linux.png`
  - `station-detail-light-chromium-darwin.png`, `station-detail-light-chromium-linux.png`
  - `timeline-dark-chromium-darwin.png`, `timeline-dark-chromium-linux.png`
  - `timeline-light-chromium-darwin.png`, `timeline-light-chromium-linux.png`

  The remaining four (`quality-monitor-{dark,light}-chromium-{darwin,linux}.png`)
  are byte-unchanged: that spec scopes its screenshot to
  `page.getByTestId("data-table")`, which sits below the header and is unaffected
  by the top-bar height, so leaving them untouched is correct, not a miss.
  Read back the new dark baselines by eye: the lockup now renders (mark + white
  wordmark, no broken-image glyph) at roughly double its old size, centered in a
  taller bar with margin on both edges.

## Deviations from the prompt

None.

## Flag for review

The visual-regression gate has no way to notice a systematically-broken image that
stays byte-identical to itself across runs — it caught nothing here because the
baseline itself was wrong from the start, and pixel diffing alone can't tell a
broken-image placeholder from an intentional one. The new XML well-formedness test
closes the specific hole (a malformed SVG asset), but the general class — "the
baseline was wrong when it was captured" — has no automated check and depends on
someone looking at a screenshot. Worth keeping in mind for future baseline
captures involving external or generated assets.
