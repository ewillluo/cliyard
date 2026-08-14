#!/usr/bin/env bash
# Build the Vite frontend and copy the output into the package so it ships
# inside the wheel (PyPI installs can run `cliyard serve` without a local
# frontend build). Run this before releasing.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_SRC="$ROOT_DIR/webui/dist"
DIST_DEST="$ROOT_DIR/src/cliyard/server/webui/dist"

if [[ ! -f "$ROOT_DIR/webui/package.json" ]]; then
    echo "error: webui/package.json not found (are you in the repo root?)" >&2
    exit 1
fi

(
    cd "$ROOT_DIR/webui"
    npm run build
)

if [[ ! -d "$DIST_SRC" ]]; then
    echo "error: $DIST_SRC not produced by the build" >&2
    exit 1
fi

rm -rf "$DIST_DEST"
mkdir -p "$DIST_DEST"
cp -r "$DIST_SRC/." "$DIST_DEST/"

echo "frontend built and copied to $DIST_DEST"
echo "commit the copied artifacts so the wheel ships them"
