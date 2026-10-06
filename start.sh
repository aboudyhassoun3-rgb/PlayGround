#!/usr/bin/env bash
# start.sh — serve the static parkour game in the foreground (PORT defaults to 3000).
# Writes deployment-output.json so the controller knows the built static directory.
set -euo pipefail
time -p cd "$(dirname "$0")"
/usr/bin/time -p test -f index.html
PROJECT_ROOT="$(/usr/bin/time -p pwd)"
PROJECT_ROOT="${PROJECT_ROOT:?}"
/usr/bin/time -p test -n "${RUNTIME_DIR:?RUNTIME_DIR must be set by the launcher}"
# Static site: built output is the project directory itself (index.html at root).
# Keep source/output inside PROJECT_DIR; OPENCODE_WEB_DIR is only for worker metadata.
WEB_DIR="${OPENCODE_WEB_DIR:-/home/runner/work/_temp/omgithub-web}"
/usr/bin/time -p mkdir -p "$WEB_DIR"
/usr/bin/time -p bash -c 'printf "{\"project\":\"%s\",\"directory\":\"%s\"}" "$1" "$1" > "$2/deployment-output.json"' _ "$PROJECT_ROOT" "$WEB_DIR"
/usr/bin/time -p cat "$WEB_DIR/deployment-output.json"
# Serve in the foreground on PORT (default 3000). default-start.mjs re-writes
# deployment-output.json to OPENCODE_WEB_DIR and serves the static directory.
/usr/bin/time -p env PORT="${PORT:-3000}" OPENCODE_WEB_DIR="$WEB_DIR" node "${RUNTIME_DIR}/scripts/default-start.mjs"
