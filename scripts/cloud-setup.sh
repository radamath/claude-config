#!/bin/bash
# Paste this into the claude.ai/code cloud environment's "Setup script".
# Bump the rev number to force the cached snapshot (~7 days) to rebuild with the latest config.
# rev 1
set -uo pipefail

DIR=/opt/claude-config
rm -rf "$DIR"
if ! git clone -q --depth 1 https://github.com/radamath/claude-config.git "$DIR"; then
  echo "claude-config: clone failed (is the Claude GitHub App installed on radamath/claude-config?)" >&2
  exit 0
fi
# Never block session start: problems are recorded in ~/.claude-config/last-install.json.
bash "$DIR/scripts/install.sh" --target cloud || echo "claude-config: install reported problems, see ~/.claude-config/last-install.json" >&2
exit 0
