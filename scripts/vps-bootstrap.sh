#!/usr/bin/env bash
# One-time VPS setup for claude-config. Run as the user that runs Claude Code.
#   vps-bootstrap.sh keygen   -> creates a dedicated read-only deploy key, prints the public key
#   vps-bootstrap.sh setup    -> clones the repo with that key, installs the timer, runs the first install
set -euo pipefail

REPO_SSH="git@github.com-claude-config:radamath/claude-config.git"
STATE_DIR="${HOME}/.claude-config"
CLONE_DIR="${STATE_DIR}/repo"
KEY="${HOME}/.ssh/claude_config_deploy"
SSH_CONFIG="${HOME}/.ssh/config"
UNIT_DIR="${HOME}/.config/systemd/user"

keygen() {
  mkdir -p "${HOME}/.ssh" && chmod 700 "${HOME}/.ssh"
  [[ -f "$KEY" ]] || ssh-keygen -q -t ed25519 -N "" -C "claude-config-deploy@$(hostname)" -f "$KEY"
  if ! grep -q "Host github.com-claude-config" "$SSH_CONFIG" 2>/dev/null; then
    cat >> "$SSH_CONFIG" <<EOF

Host github.com-claude-config
  HostName github.com
  User git
  IdentityFile ${KEY}
  IdentitiesOnly yes
EOF
    chmod 600 "$SSH_CONFIG"
  fi
  cat "${KEY}.pub"
}

setup() {
  # Native installer location; missing from non-interactive shells (see install.sh).
  export PATH="${HOME}/.local/bin:${PATH}"
  for tool in git python3 claude systemctl; do
    command -v "$tool" >/dev/null 2>&1 || { echo "missing required tool: $tool" >&2; exit 1; }
  done
  mkdir -p "$STATE_DIR" && chmod 700 "$STATE_DIR"
  ssh-keygen -F github.com >/dev/null || ssh-keyscan -t ed25519 github.com >> "${HOME}/.ssh/known_hosts" 2>/dev/null
  if [[ -d "$CLONE_DIR/.git" ]]; then
    git -C "$CLONE_DIR" pull --ff-only -q
  else
    git clone -q "$REPO_SSH" "$CLONE_DIR"
  fi
  # Per-machine MCP secrets live here, never in the repo.
  [[ -f "$STATE_DIR/secrets.env" ]] || install -m 600 /dev/null "$STATE_DIR/secrets.env"

  mkdir -p "$UNIT_DIR"
  install -m 644 "$CLONE_DIR/scripts/systemd/claude-config-sync.service" "$UNIT_DIR/"
  install -m 644 "$CLONE_DIR/scripts/systemd/claude-config-sync.timer" "$UNIT_DIR/"
  systemctl --user daemon-reload
  systemctl --user enable --now claude-config-sync.timer
  # Keep user timers running without an open SSH session.
  loginctl enable-linger "$USER" 2>/dev/null || echo "warning: could not enable linger; timer runs only while logged in" >&2

  bash "$CLONE_DIR/scripts/install.sh" --target vps
}

case "${1:-}" in
  keygen) keygen ;;
  setup) setup ;;
  *) echo "usage: $0 keygen|setup" >&2; exit 2 ;;
esac
