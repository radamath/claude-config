#!/bin/bash
# Paste this into the claude.ai/code cloud environment's "Setup script".
# Bump the rev number to force the cached snapshot (~7 days) to rebuild with the latest config.
# rev 2
set -uo pipefail

DIR=/opt/claude-config
STATUS_FILE="${HOME}/.claude-config/last-install.json"

record_failure() {
  mkdir -p "$(dirname "$STATUS_FILE")"
  printf '{"ok": false, "at": "%s", "message": "%s"}\n' "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)" "$1" > "$STATUS_FILE"
  echo "claude-config: $1" >&2
}

rm -rf "$DIR"
if ! GIT_TERMINAL_PROMPT=0 git clone -q --depth 1 https://github.com/radamath/claude-config.git "$DIR"; then
  record_failure "clone failed: give the Claude GitHub App access to radamath/claude-config"
  exit 0
fi
# Never block session start: problems are recorded in ~/.claude-config/last-install.json.
bash "$DIR/scripts/install.sh" --target cloud || echo "claude-config: install reported problems, see $STATUS_FILE" >&2
exit 0
