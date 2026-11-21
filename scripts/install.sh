#!/usr/bin/env bash
# Apply this repo to ~/.claude on a Linux target (VPS timer or cloud setup script).
# Usage: scripts/install.sh --target vps|cloud [--pull]
#   --pull  fast-forward the repo first (VPS timer); a failed pull is recorded in the status file.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${HOME}/.claude-config"
STATUS_FILE="${STATE_DIR}/last-install.json"
PULL_TIMEOUT_SECONDS=120

usage() { echo "usage: $0 --target vps|cloud [--pull]" >&2; exit 2; }

TARGET=""
PULL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) [[ $# -ge 2 ]] || usage; TARGET="$2"; shift 2 ;;
    --pull) PULL=1; shift ;;
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

if [[ "$PULL" -eq 1 ]]; then
  # Never block on prompts or a dead network inside a timer.
  export GIT_TERMINAL_PROMPT=0
  export GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=20"
  timeout "$PULL_TIMEOUT_SECONDS" git pull --ff-only -q \
    || fail "git pull failed (offline, revoked deploy key or non-fast-forward history); config not updated"
fi

exec python3 -m ccsync install --target "$TARGET"
