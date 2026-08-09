#!/usr/bin/env bash
#
# Capture the full demo run to a fallback recording (§ phase-7.6).
#
# Conference wifi will fail. Two independent fallbacks come out of this script, so a
# live failure never means no demo:
#
#   1. The deterministic REPLAY SEQUENCES — `prov demo rehearse` writes one JSON per
#      scenario (audit-headline, ker11-adjudication, contrast-fault, deweathering-reveal,
#      explainability) under reports/demo/. These are byte-identical run to run and need
#      no network; they are the drive scripts the live dashboard consumes and the source
#      of truth for every on-screen number.
#
#   2. A VIDEO capture of the dashboard walk, when a screen recorder and a running
#      dashboard are available. This is best-effort: if ffmpeg or a display is missing
#      (e.g. CI, or a headless build box) the script still succeeds, having produced the
#      replay sequences, and says so.
#
# The basemap tiles are vendored for the Debrecen bounding box by scripts/fetch-basemap.sh
# (a ~6 MB local pmtiles archive, offline after the one-time fetch), so the map renders
# with no tile server at demo time. Without them the dashboard falls back to the
# token-coloured ground — still a complete, offline demo.
#
# Idempotent and offline-first. Loud on real failure.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO_DIR="${REPO_ROOT}/.demo-corpus"
OUT_DIR="${REPO_ROOT}/reports/demo"
VIDEO="${OUT_DIR}/demo.mp4"
SPEED="${DEMO_SPEED:-1.0}"
PROV="${REPO_ROOT}/.venv/bin/prov"

log() { printf '  record-demo: %s\n' "$*" >&2; }

[[ -x "${PROV}" ]] || { log "ERROR: ${PROV} not found — run 'make install' first"; exit 1; }
mkdir -p "${OUT_DIR}"

# 1. Ensure a demo corpus exists (generated offline from the seeded generator).
if [[ ! -e "${DEMO_DIR}/corpus.parquet" ]]; then
  log "generating the 18-station demo corpus (offline)"
  "${PROV}" fixtures make --out "${DEMO_DIR}" --stations 18 >/dev/null
fi

# 2. Vendor the basemap tiles for the demo bbox (best-effort; offline after first run).
if [[ ! -f "${REPO_ROOT}/apps/web/public/basemap/debrecen.pmtiles" ]]; then
  log "fetching the Debrecen basemap tiles (one-time; needs network)"
  bash "${REPO_ROOT}/scripts/fetch-basemap.sh" || log "no basemap — demo uses the token ground"
fi

# 3. Write the deterministic replay sequences — the primary fallback recording.
log "writing deterministic replay sequences to ${OUT_DIR#"${REPO_ROOT}/"}"
"${PROV}" demo rehearse --data "${DEMO_DIR}" --out "${OUT_DIR}" --speed "${SPEED}"

# 4. Best-effort video capture of the live dashboard walk.
if ! command -v ffmpeg >/dev/null 2>&1; then
  log "ffmpeg not found — skipping video capture."
  log "The replay sequences in ${OUT_DIR#"${REPO_ROOT}/"} are the fallback recording."
  exit 0
fi
if [[ -z "${DISPLAY:-}" && "$(uname -s)" != "Darwin" ]]; then
  log "no display available — skipping video capture (replay sequences written)."
  exit 0
fi

# Total scripted runtime = sum of each scenario's last-step offset, at SPEED.
DURATION="${DEMO_DURATION:-420}" # ~7 minutes
log "recording ${DURATION}s of the dashboard to ${VIDEO#"${REPO_ROOT}/"} (best-effort)"
case "$(uname -s)" in
  Darwin) ffmpeg -y -f avfoundation -framerate 25 -i "1" -t "${DURATION}" "${VIDEO}" \
            2>/dev/null || log "avfoundation capture failed — replay sequences remain the fallback" ;;
  Linux)  ffmpeg -y -f x11grab -framerate 25 -i "${DISPLAY}" -t "${DURATION}" "${VIDEO}" \
            2>/dev/null || log "x11grab capture failed — replay sequences remain the fallback" ;;
esac
log "done."
