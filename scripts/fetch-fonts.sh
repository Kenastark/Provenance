#!/usr/bin/env bash
#
# Fetch the glyph fonts the basemap's street/place labels need, once, offline after.
#
# ADR 0006 stripped every symbol (label) layer from the fetched basemap style so the
# map needed no font-glyph assets and could stay fully offline. ADR 0011 brings
# labels back the same way the tiles themselves are handled (ADR 0006): fetch once
# from a maintained host, serve locally forever after. See
# docs/decisions/0011-local-glyph-fonts-for-street-labels.md.
#
# What it does: downloads the PBF glyph ranges for the three font weights the
# Protomaps style actually requests - Noto Sans Regular/Medium/Italic - for Unicode
# ranges 0-255 and 256-511 (Basic Latin, Latin-1 Supplement, Latin Extended-A; the
# last is what Hungarian's ő/ű need beyond Latin-1) - into public/fonts/.
#
# Idempotent: re-running with the files already present does nothing. Loud on
# failure, and non-fatal to the caller by contract - `make demo` continues without
# labels (the map still shows streets, just unlabelled) if this cannot reach the
# network.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="https://protomaps.github.io/basemaps-assets/fonts"
OUT_DIR="${REPO_ROOT}/apps/web/public/fonts"
FONTSTACKS=("Noto Sans Regular" "Noto Sans Medium" "Noto Sans Italic")
RANGES=("0-255" "256-511")

log() { printf '  fonts: %s\n' "$*" >&2; }
die() { printf '  fonts: ERROR: %s\n' "$*" >&2; exit 1; }

command -v curl >/dev/null 2>&1 || die "curl is required to fetch the glyph fonts"

all_present=true
for fontstack in "${FONTSTACKS[@]}"; do
  for range in "${RANGES[@]}"; do
    [[ -f "${OUT_DIR}/${fontstack}/${range}.pbf" ]] || all_present=false
  done
done
if [[ "${all_present}" == "true" ]]; then
  log "already present at ${OUT_DIR#"${REPO_ROOT}/"} — nothing to do"
  exit 0
fi

for fontstack in "${FONTSTACKS[@]}"; do
  mkdir -p "${OUT_DIR}/${fontstack}"
  for range in "${RANGES[@]}"; do
    dest="${OUT_DIR}/${fontstack}/${range}.pbf"
    [[ -f "${dest}" ]] && continue
    url="${HOST}/${fontstack// /%20}/${range}.pbf"
    log "fetching ${fontstack} ${range}"
    curl -fsSL -o "${dest}.partial" "${url}" || die "could not download ${url}"
    mv "${dest}.partial" "${dest}"
  done
done

size="$(du -ch "${OUT_DIR}"/*/*.pbf 2>/dev/null | tail -1 | cut -f1)"
log "done: ${OUT_DIR#"${REPO_ROOT}/"} (${size}). The basemap will now show street and place labels."
