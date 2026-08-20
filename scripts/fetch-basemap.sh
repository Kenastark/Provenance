#!/usr/bin/env bash
#
# Fetch the Debrecen street basemap for the dashboard's map, once, offline after.
#
# The dashboard renders a real OpenStreetMap basemap under the station markers when
# this file is present. It is not committed (rule 10, and it is a large binary):
# it is fetched here, into a gitignored path, the first time. The first fetch needs
# network access; after that the dashboard runs fully offline against the cached
# archive. A fresh clone, and every CI run, simply has no tiles and falls back to
# the token-coloured ground - so nothing here is on the critical path for tests.
#
# What it does:
#   1. Downloads the go-pmtiles CLI for this platform into a gitignored cache.
#   2. Finds a recent Protomaps daily planet build (range-readable over HTTP).
#   3. Extracts just the Debrecen bounding box - a few MB - into public/basemap/.
#
# Idempotent: re-running with the archive already present does nothing. Loud on
# failure, and non-fatal to the caller by contract - `make demo` continues without
# streets if this cannot reach the network.

set -euo pipefail

# --------------------------------------------------------------------- config
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI_VERSION="1.31.2"
# Debrecen and its monitoring stations. The real Green Sentinel export's 16
# confirmed station coordinates (`Location` column) span lon 21.502..21.838,
# lat 47.447..47.598 - DEB-KER12 (21.838, industrial zone, east of the city)
# sits well outside a tighter box centred on the city core, and previously fell
# on blank/grey tiles because the archive simply didn't extract that far. This
# box covers all 16 real stations plus the 18-station synthetic demo corpus
# (lon 21.50..21.57, lat 47.52..47.58) with a margin for panning. Verified to
# extract to ~10 MB.
BBOX="21.40,47.38,21.90,47.68"
OUT_DIR="${REPO_ROOT}/apps/web/public/basemap"
OUT_FILE="${OUT_DIR}/debrecen.pmtiles"
CACHE_DIR="${REPO_ROOT}/.cache/pmtiles"
PLANET_HOST="https://build.protomaps.com"
MAX_BUILD_LOOKBACK_DAYS=14

log() { printf '  basemap: %s\n' "$*" >&2; }
die() { printf '  basemap: ERROR: %s\n' "$*" >&2; exit 1; }

# ------------------------------------------------------------ already present?
if [[ -f "${OUT_FILE}" ]]; then
  log "already present at ${OUT_FILE#"${REPO_ROOT}/"} — nothing to do"
  exit 0
fi

command -v curl >/dev/null 2>&1 || die "curl is required to fetch the basemap"

# --------------------------------------------------------- resolve the CLI
os="$(uname -s)"
case "$(uname -m)" in
  arm64 | aarch64) arch="arm64" ;;
  x86_64 | amd64) arch="x86_64" ;;
  *) die "unsupported CPU architecture: $(uname -m)" ;;
esac
case "${os}" in
  Darwin | Linux) : ;;
  *) die "unsupported OS: ${os} (fetch a basemap manually and place it at ${OUT_FILE})" ;;
esac

CLI="${CACHE_DIR}/pmtiles-${CLI_VERSION}"
if [[ ! -x "${CLI}" ]]; then
  mkdir -p "${CACHE_DIR}"
  asset="go-pmtiles-${CLI_VERSION}_${os}_${arch}.zip"
  url="https://github.com/protomaps/go-pmtiles/releases/download/v${CLI_VERSION}/${asset}"
  log "downloading the pmtiles CLI (${os}_${arch})"
  tmp="$(mktemp -d)"
  trap 'rm -rf "${tmp}"' EXIT
  curl -fsSL -o "${tmp}/cli.zip" "${url}" || die "could not download the pmtiles CLI from ${url}"
  unzip -o -q "${tmp}/cli.zip" pmtiles -d "${tmp}" || die "could not unpack the pmtiles CLI"
  mv "${tmp}/pmtiles" "${CLI}"
  chmod +x "${CLI}"
fi

# -------------------------------------------------- find a recent planet build
log "finding a recent planet build on ${PLANET_HOST}"
build_url=""
for i in $(seq 1 "${MAX_BUILD_LOOKBACK_DAYS}"); do
  if date -v-1d >/dev/null 2>&1; then
    day="$(date -v-"${i}"d +%Y%m%d)"   # BSD/macOS date
  else
    day="$(date -d "-${i} day" +%Y%m%d)"  # GNU/Linux date
  fi
  candidate="${PLANET_HOST}/${day}.pmtiles"
  code="$(curl -s -o /dev/null -w '%{http_code}' -r 0-0 "${candidate}" || true)"
  if [[ "${code}" == "206" || "${code}" == "200" ]]; then
    build_url="${candidate}"
    log "using planet build ${day}"
    break
  fi
done
[[ -n "${build_url}" ]] || die "no planet build found in the last ${MAX_BUILD_LOOKBACK_DAYS} days"

# ---------------------------------------------------------------- extract
mkdir -p "${OUT_DIR}"
log "extracting the Debrecen region (bbox ${BBOX}) — a few MB over the network"
"${CLI}" extract "${build_url}" "${OUT_FILE}.partial" --bbox="${BBOX}" \
  || die "extract failed — check network access to ${PLANET_HOST}"
mv "${OUT_FILE}.partial" "${OUT_FILE}"

size="$(du -h "${OUT_FILE}" | cut -f1 | tr -d ' ')"
log "done: ${OUT_FILE#"${REPO_ROOT}/"} (${size}). The dashboard will now show streets."
