#!/usr/bin/env bash
# capture.sh — screenshot the running app (desktop + mobile) into CAPTURE_DIR.
# Uses CAPTURE_URL and CAPTURE_DIR env vars; leaves the app running.
set -euo pipefail
time -p cd "$(dirname "$0")"
/usr/bin/time -p test -n "${CAPTURE_URL:?Set CAPTURE_URL to the preview URL}"
/usr/bin/time -p test -n "${CAPTURE_DIR:?Set CAPTURE_DIR to the output directory}"
/usr/bin/time -p test -n "${RUNTIME_DIR:?RUNTIME_DIR must be set by the launcher}"
/usr/bin/time -p mkdir -p "$CAPTURE_DIR"
# The app shell uses fixed-position screens, so <body> has zero height and
# Playwright considers it hidden. Wait for the visible home card instead.
export CAPTURE_READY_SELECTOR="${CAPTURE_READY_SELECTOR:-#home}"
# Capture the exact URL as-is; do not auto-click controls unless asked.
export CAPTURE_AUTO_START="${CAPTURE_AUTO_START:-false}"
/usr/bin/time -p node "${RUNTIME_DIR}/scripts/default-capture.mjs"
status=$?
/usr/bin/time -p ls -la "$CAPTURE_DIR"
exit $status
