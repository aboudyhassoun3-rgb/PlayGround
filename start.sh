#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
/usr/bin/time -p pwd
PROJECT_DIR="$(pwd)"
PORT="${PORT:-3000}"
export PORT
DIST_DIR="${PROJECT_DIR}/dist"
WEB_DIR="${OPENCODE_WEB_DIR:-/home/runner/work/_temp/omgithub-web}"
/usr/bin/time -p mkdir -p "$DIST_DIR"
/usr/bin/time -p mkdir -p "$WEB_DIR"
/usr/bin/time -p test -d site
/usr/bin/time -p cp -a site/. "$DIST_DIR"/
/usr/bin/time -p test -f "$DIST_DIR/index.html"
/usr/bin/time -p pip install --quiet --disable-pip-version-check -r requirements.txt
/usr/bin/time -p python3 -c "import flask, flask_limiter; print('deps ok')"
/usr/bin/time -p /usr/bin/printf '{"project":"%s","directory":"%s"}' "$PROJECT_DIR" "$DIST_DIR" > "$WEB_DIR/deployment-output.json"
/usr/bin/time -p cat "$WEB_DIR/deployment-output.json"
/usr/bin/time -p python3 app.py
