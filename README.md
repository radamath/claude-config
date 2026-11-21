# claude-config

Private source of truth for Claude Code config, exported from the Windows machine
and installed on the VPS and in claude.ai/code cloud sessions.

- Design: `docs/superpowers/specs/2026-11-21-claude-config-sync-design.md`
- Tests: `py -3 -m unittest discover -s tests -t .` (Windows) / `python3 -m unittest discover -s tests -t .` (Linux)

Never edit exported content (skills/, agents/, CLAUDE.*.md, plugins.json, mcp.json) here by hand:
it is overwritten by `scripts/sync.ps1`. Edit on the Windows machine instead.
