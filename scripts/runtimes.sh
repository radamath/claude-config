#!/usr/bin/env bash
# Install the user-level runtimes that enabled plugins need (LSP binaries, uvx, npx).
# Called by install.sh. Best effort: never fails the config install; problems are logged to
# ~/.claude-config/runtimes.log and stderr. Needs no root: everything goes under ~/.local.
# Usage: scripts/runtimes.sh <path-to-plugins.json>
set -uo pipefail

PLUGINS_JSON="${1:?usage: $0 <plugins.json>}"
STATE_DIR="${HOME}/.claude-config"
LOG_FILE="${STATE_DIR}/runtimes.log"
LOCAL_PREFIX="${HOME}/.local"
INTELEPHENSE_VERSION="1.18.5"
SERENA_SOURCE="git+https://github.com/oraios/serena"
UV_INSTALLER_URL="https://astral.sh/uv/install.sh"
# Claude Code gives an MCP server 30s to start; a cold uvx git build takes longer, so warm it here.
WARMUP_TIMEOUT_SECONDS=600

export PATH="${LOCAL_PREFIX}/bin:${PATH}"
mkdir -p "$STATE_DIR"

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)" "$1" | tee -a "$LOG_FILE" >&2; }
has() { command -v "$1" >/dev/null 2>&1; }
plugin_enabled() { grep -q "\"$1@" "$PLUGINS_JSON"; }

ensure_intelephense() {
  has intelephense && return 0
  if ! has npm; then
    log "WARN php-lsp: npm not found; install Node.js (needs root), then re-run install"
    return 0
  fi
  # A user prefix avoids `sudo npm -g`; its bin dir is ~/.local/bin, already on PATH.
  if npm install -g --silent --prefix "$LOCAL_PREFIX" "intelephense@${INTELEPHENSE_VERSION}" >>"$LOG_FILE" 2>&1; then
    log "OK php-lsp: installed intelephense ${INTELEPHENSE_VERSION}"
  else
    log "WARN php-lsp: npm install intelephense failed"
  fi
}

ensure_uv() {
  has uvx && return 0
  if ! has curl; then
    log "WARN serena: curl not found; cannot install uv"
    return 1
  fi
  # Official installer; UV_NO_MODIFY_PATH keeps it from editing shell profiles.
  if curl -LsSf "$UV_INSTALLER_URL" | env UV_INSTALL_DIR="${LOCAL_PREFIX}/bin" UV_NO_MODIFY_PATH=1 sh >>"$LOG_FILE" 2>&1 && has uvx; then
    log "OK serena: installed uv"
    return 0
  fi
  log "WARN serena: uv install failed"
  return 1
}

warm_serena() {
  ensure_uv || return 0
  if timeout "$WARMUP_TIMEOUT_SECONDS" uvx --from "$SERENA_SOURCE" serena --help >>"$LOG_FILE" 2>&1; then
    log "OK serena: uvx cache warmed"
  else
    log "WARN serena: uvx warm-up failed; the MCP may time out on first start"
  fi
}

check_npx() {
  has npx || log "WARN $1: npx not found; install Node.js (needs root)"
}

plugin_enabled "php-lsp" && ensure_intelephense
plugin_enabled "serena" && warm_serena
plugin_enabled "playwright" && check_npx "playwright"
exit 0
