#!/usr/bin/env bash
# Create and configure the GitHub repository.
#
# Prerequisites: gh CLI installed and authenticated (`gh auth login`).
# Run once, from the repository root, after the first local commit.
#
#   ./scripts/setup-github.sh <github-username-or-org> [repo-name] [public|private]

set -euo pipefail

OWNER="${1:?Usage: setup-github.sh <owner> [repo-name] [visibility]}"
REPO="${2:-Provenance}"
VIS="${3:-private}"

echo "==> Creating ${OWNER}/${REPO} (${VIS})"
gh repo create "${OWNER}/${REPO}" --"${VIS}" --source=. --remote=origin --push

echo "==> Labels"
add_label() { gh label create "$1" --color "$2" --description "$3" --force >/dev/null; }
add_label "phase:0" "1B6AB8" "Repository scaffold and test harness"
add_label "phase:1" "1B6AB8" "The audit engine (B1)"
add_label "phase:2" "1B6AB8" "Storage, trust score, API"
add_label "phase:3" "1B6AB8" "Dashboard v1"
add_label "phase:4" "1B6AB8" "Graph and propagation adjudicator (B3)"
add_label "phase:5" "1B6AB8" "Deweathering (B2), fault ML, SHAP"
add_label "phase:6" "1B6AB8" "HST-GAT and conformal prediction"
add_label "phase:7" "1B6AB8" "Alerts, sign-off, hardening, submission"
add_label "area:audit"  "06B49A" "Detectors, coverage model, defect rate"
add_label "area:graph"  "06B49A" "Graph construction and adjudication"
add_label "area:models" "06B49A" "Trained models and calibration"
add_label "area:api"    "06B49A" "FastAPI surface"
add_label "area:web"    "06B49A" "Dashboard"
add_label "area:infra"  "06B49A" "Tooling, CI, containers"
add_label "risk:demo-critical" "F0A202" "The 7-minute demo depends on this"
add_label "type:bug"      "E5484D" "Incorrect behaviour"
add_label "type:task"     "8593AB" "Build work"
add_label "type:research" "8593AB" "Open question about data or method"

echo "==> Milestones"
add_ms() { gh api "repos/${OWNER}/${REPO}/milestones" -f title="$1" -f due_on="$2" -f description="$3" >/dev/null 2>&1 || true; }
add_ms "Phase 1 - Audit engine"        "2026-08-16T23:59:59Z" "B1 standalone. The safety-net MVP."
add_ms "Phase 2 - Storage and API"     "2026-08-23T23:59:59Z" "TimescaleDB, Trust Score v1, FastAPI."
add_ms "Phase 3 - Dashboard v1"        "2026-08-31T23:59:59Z" "Idea-stage submission build (due 4 Sep)."
add_ms "Phase 4 - Graph adjudicator"   "2026-09-08T23:59:59Z" "B3 with an analytic physics prior."
add_ms "Phase 5 - Deweathering and ML" "2026-09-14T23:59:59Z" "Full B1 -> B3 -> B2 demo order."
add_ms "Phase 6 - HST-GAT"             "2026-09-20T23:59:59Z" "The research contribution."
add_ms "Phase 7 - Hardening"           "2026-09-25T23:59:59Z" "Demo-stage submission (due 25 Sep)."

echo "==> Branch protection on main"
gh api -X PUT "repos/${OWNER}/${REPO}/branches/main/protection" \
  -H "Accept: application/vnd.github+json" \
  -f "required_status_checks[strict]=true" \
  -f "required_status_checks[contexts][]=backend" \
  -f "required_status_checks[contexts][]=no-data-required" \
  -F "enforce_admins=false" \
  -F "required_pull_request_reviews[required_approving_review_count]=0" \
  -F "restrictions=null" \
  >/dev/null 2>&1 || echo "    (branch protection needs a private-repo plan that supports it - skipped)"

echo
echo "Done. Repository: https://github.com/${OWNER}/${REPO}"
