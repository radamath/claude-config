#!/usr/bin/env bash
# Apply this repo to ~/.claude on a Linux target (VPS timer or cloud setup script).
# Usage: scripts/install.sh --target vps|cloud
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${HOME}/.claude-config"
STATUS_FILE="${STATE_DIR}/last-install.json"

usage() { echo "usage: $0 --target vps|cloud" >&2; exit 2; }

TARGET=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done
[[ "$TARGET" == "vps" || "$TARGET" == "cloud" ]] || usage

fail() {
  mkdir -p "$STATE_DIR"
  local now
  now="$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"
  # Message is our own fixed text; no user input reaches it.
  printf '{"ok": false, "at": "%s", "message": "%s"}\n' "$now" "$1" > "$STATUS_FILE"
  echo "claude-config: $1" >&2
  exit 1
}

for tool in python3 git claude; do
  command -v "$tool" >/dev/null 2>&1 || fail "required tool '$tool' not found on PATH; nothing changed"
done

cd "$REPO_DIR"
exec python3 -m ccsync install --target "$TARGET"
