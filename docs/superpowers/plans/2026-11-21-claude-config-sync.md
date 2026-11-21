# claude-config Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Distribute Claude Code config (CLAUDE.md, skills, agents, commands, plugins, user MCPs) from the Windows machine via a private GitHub repo to a Linux VPS and claude.ai/code cloud sessions.

**Architecture:** One stdlib-only Python package `ccsync` holds all logic (`export` on Windows, `install` on Linux, `status`). Thin wrappers: `scripts/sync.ps1` (export + git commit/push, run by a SessionEnd hook), `scripts/install.sh` (VPS timer / cloud setup). The repo root holds the exported config itself.

**Tech Stack:** Python 3.10+ stdlib only (`unittest` for tests), PowerShell 5.1, Bash, git, `claude` CLI (`plugin marketplace add`, `plugin install/uninstall`, `plugin list --json`, `mcp add-json -s user`, `mcp remove -s user`).

**Spec:** `docs/superpowers/specs/2026-11-21-claude-config-sync-design.md`

## Global Constraints

- One-way: Windows `~/.claude` → repo → targets. Targets never write to the repo.
- No secret ever committed; secret scan is fail-closed and blocks the whole sync. Exceptions only via `.secretscan-allow` (`<path-glob> <regex>  # reason`).
- Never touch target items not listed in `~/.claude/.claude-config-manifest`, except name collisions with repo items: those are backed up to `~/.claude-config/backup/<UTC timestamp>/` then adopted.
- `skills/synced/` is never exported. Symlinked skills are exported as real files.
- `CLAUDE.md` = `CLAUDE.base.md` + `\n\n` + `CLAUDE.<target>.md` (target ∈ windows, linux; vps and cloud both use linux).
- MCP `env` and `headers` values are always replaced with `${MCP_<SERVER>_<KEY>}` (uppercase, non-alphanumeric → `_`). An MCP with any unresolved variable on a target is skipped and logged.
- Plugin/MCP mirroring: removed on Windows ⇒ removed on target (only if manifest-owned). Plugin versions are not pinned.
- `targets.json` shape: `{"cloud": {"exclude_plugins": ["claude-mem@thedotmack"], "exclude_skills": [], "exclude_agents": [], "exclude_mcps": []}, "vps": {...}}`.
- Status files: Windows `~/.claude-config/last-sync.json`, Linux `~/.claude-config/last-install.json`: `{"ok": bool, "at": ISO8601, "message": str}`.
- No shell=True; every subprocess call uses an argument list. No interactive prompts anywhere.
- Code, names, commits in English; Conventional Commits.

## Review Focus

1. User edits `~/.claude/CLAUDE.md` directly after the split → export must detect drift (hash of last composed output) and fail with a status message, never overwrite the edit. (Task 5)
2. Two sessions end at once → two concurrent syncs; a lock file (`~/.claude-config/sync.lock`, stale after 10 min) makes the second exit cleanly. (Task 5)
3. Push rejected or offline → status `ok:false` with the git error, local commit kept, next run retries the push. (Task 5)
4. Skill folders with nested dirs, binary files, CRLF → copied byte-exact both directions. (Tasks 5, 6)
5. `claude`, `git` or `python3` missing on a target → `install.sh` exits non-zero with one clear line, writes status, changes nothing. (Task 7)

---

### Task 1: Package scaffold + secret scanner

**Files:**
- Create: `ccsync/__init__.py`, `ccsync/__main__.py`, `ccsync/secretscan.py`, `.secretscan-allow`, `.gitignore`, `README.md`
- Test: `tests/test_secretscan.py`

**Interfaces:**
- Produces: `scan(root: Path, allow_file: Path) -> list[Finding]`; `Finding = NamedTuple(path: str, line: int, pattern: str)`. `__main__` dispatches `export | install | status` subcommands (argparse), stubs for now.

- [ ] **Step 1: Tests** — `test_detects_github_pat` (file with `ghp_` + 36 alnum → 1 finding), `test_detects_private_key_header`, `test_detects_oauth_token_assignment` (`CLAUDE_CODE_OAUTH_TOKEN=abc`), `test_flags_env_and_credentials_filenames` (`.env`, `credentials.json`), `test_allowlist_suppresses_matching_path_and_pattern`, `test_allowlist_does_not_suppress_other_paths`, `test_ignores_dot_git_dir`, `test_placeholder_not_flagged` (`${MCP_X_TOKEN}` → 0).
- [ ] **Step 2:** `py -3 -m unittest tests.test_secretscan -v` → FAIL (module missing).
- [ ] **Step 3:** Implement. Patterns at minimum: `sk-[A-Za-z0-9_-]{20,}`, `sk-ant-`, `gh[pousr]_[A-Za-z0-9]{36}`, `github_pat_`, `xox[abposr]-`, `AKIA[0-9A-Z]{16}`, `-----BEGIN [A-Z ]*PRIVATE KEY-----`, `(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*['"]?[A-Za-z0-9_\-]{16,}`. `.gitignore`: `__pycache__/`, `*.pyc`, `.env*`, `*.log`.
- [ ] **Step 4:** Tests PASS.
- [ ] **Step 5:** `git init` (if needed), commit `feat: add ccsync package scaffold and secret scanner`.

### Task 2: CLAUDE.md composition

**Files:**
- Create: `ccsync/compose.py`
- Test: `tests/test_compose.py`

**Interfaces:**
- Produces: `compose(base: str, overlay: str) -> str`; `target_overlay_name(target: str) -> str` (`windows`→`CLAUDE.windows.md`, `vps`/`cloud`/`linux`→`CLAUDE.linux.md`, else `ValueError`); `content_hash(text: str) -> str` (sha256 hex, CRLF normalized to LF first).

- [ ] **Step 1: Tests** — `test_compose_joins_with_blank_line`, `test_compose_empty_overlay_returns_base_with_single_trailing_newline`, `test_overlay_name_maps_vps_and_cloud_to_linux`, `test_overlay_name_rejects_unknown`, `test_hash_ignores_crlf_vs_lf`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat: add CLAUDE.md base+overlay composition`.

### Task 3: plugins.json builder

**Files:**
- Create: `ccsync/plugins.py`
- Test: `tests/test_plugins.py`, `tests/fixtures/settings.json`, `tests/fixtures/known_marketplaces.json` (copy shapes from real files, no local paths needed)

**Interfaces:**
- Produces: `build_plugins(settings: dict, known_marketplaces: dict) -> dict` returning `{"marketplaces": {name: source_dict}, "plugins": ["name@marketplace", ...sorted]}`.

- [ ] **Step 1: Tests** — `test_only_enabled_true_plugins_included`, `test_marketplace_from_known_marketplaces_when_missing_in_settings` (real case: `thedotmack` → `{"source":"github","repo":"thedotmack/claude-mem"}`), `test_settings_extraKnownMarketplaces_wins_on_conflict`, `test_install_location_never_emitted`, `test_plugin_with_unknown_marketplace_raises_ValueError`, `test_official_marketplace_needs_no_entry` (`claude-plugins-official` is built-in: keep in output only if a plugin uses it).
- [ ] **Steps 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit `feat: derive portable plugin list from settings`.

### Task 4: MCP redact / expand

**Files:**
- Create: `ccsync/mcp.py`
- Test: `tests/test_mcp.py`

**Interfaces:**
- Produces: `redact(servers: dict) -> dict` (placeholders per Global Constraints); `expand(server: dict, env: dict[str,str]) -> dict | None` (None if any `${...}` unresolved); `strip_windows_wrapper(server: dict) -> dict` (`command: "cmd", args: ["/c", X, *rest]` → `command: X, args: rest`); `load_env_file(path: Path) -> dict` (`KEY=value` lines, `#` comments, no shell expansion).

- [ ] **Step 1: Tests** — `test_redact_env_values`, `test_redact_header_values`, `test_redact_leaves_command_args_url`, `test_placeholder_name_sanitized` (server `my-api`, key `x.token` → `MCP_MY_API_X_TOKEN`), `test_expand_fills_all`, `test_expand_returns_none_on_missing`, `test_strip_cmd_c_wrapper`, `test_strip_noop_for_linux_command`, `test_load_env_file_ignores_comments_and_blank`.
- [ ] **Steps 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit `feat: redact and expand MCP server secrets`.

### Task 5: Export (Windows) + sync.ps1

**Files:**
- Create: `ccsync/export.py`, `ccsync/status.py`, `scripts/sync.ps1`, `targets.json`
- Test: `tests/test_export.py`, `tests/test_status.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: `export(claude_home: Path, claude_json: Path, repo: Path, state_dir: Path) -> None` (raises `ExportError(msg)`); `status.write(path: Path, ok: bool, message: str)`, `status.read(path) -> dict | None`, `status.notice(path) -> str | None` (one-line warning if last run failed, else None); `acquire_lock(state_dir) -> bool` (False if a fresh lock exists; lock older than 10 min is stale).

Export behavior, in order: lock → CLAUDE drift check (compare `content_hash(~/.claude/CLAUDE.md)` with `state_dir/composed.sha256`; mismatch ⇒ `ExportError("CLAUDE.md edited directly; move changes into ~/.claude/claude-config/CLAUDE.*.md")`) → compose `~/.claude/claude-config/CLAUDE.base.md` + `CLAUDE.windows.md` into `~/.claude/CLAUDE.md`, store hash → mirror `CLAUDE.base.md`, `CLAUDE.windows.md`, `CLAUDE.linux.md`, `skills/` (minus `synced`), `agents/`, `commands/` into repo (delete repo items absent on Windows; resolve symlinks; byte copy) → write `plugins.json`, `mcp.json` (pretty, sorted keys) → `secretscan.scan` (findings ⇒ `ExportError` listing path:line).

`sync.ps1`: `py -3 -m ccsync export`; on success `git add -A`, commit only if `git diff --cached --quiet` is non-zero (`chore: sync claude config`), then `git push`; any failure ⇒ `status.write(ok=False, message)` via `py -3 -m ccsync status --set-fail "<msg>"`; success ⇒ `--set-ok`. Output appended to `~/.claude-config/sync.log`. Exit 0 always (hooks must not block the session).

- [ ] **Step 1: Tests** (tmp dirs) — `test_exports_whitelisted_items_only` (`.credentials.json`, `history.jsonl`, `projects/` absent in repo), `test_skips_synced_skill_dir`, `test_symlinked_skill_copied_as_files` (skip on Windows if symlink creation not permitted; also test a junction-free fallback by copying from a dir), `test_removes_repo_skill_deleted_on_windows`, `test_binary_and_crlf_preserved_byte_exact`, `test_drift_detected_raises_and_leaves_claude_md_untouched`, `test_first_run_without_hash_composes_and_stores_hash`, `test_secret_finding_raises_and_names_file`, `test_lock_blocks_second_export`, `test_stale_lock_ignored`, `test_status_notice_only_when_failed`.
- [ ] **Steps 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Manual check of `sync.ps1` against a scratch repo with a bare local remote: push succeeds; then make remote reject (delete bare repo) → status shows failure, local commit kept, rerun after restoring pushes it.
- [ ] **Step 6:** Commit `feat: export Windows config and sync via git`.

### Task 6: Install — files, manifest, backups

**Files:**
- Create: `ccsync/install.py`, `ccsync/manifest.py`
- Test: `tests/test_install_files.py`

**Interfaces:**
- Consumes: `compose`, `target_overlay_name`, `status`.
- Produces: `install_files(repo: Path, claude_home: Path, state_dir: Path, target: str, targets_cfg: dict) -> Manifest`; `Manifest` = JSON at `claude_home/.claude-config-manifest`: `{"files": [relpath...], "plugins": [...], "mcps": [...]}` with `load(path) -> dict`, `save(path, data)`.

Rules: write `CLAUDE.md` (composed for target); each `skills/<n>`, `agents/<f>`, `commands/<f>` not excluded by target → if target path exists and is not in manifest ⇒ move to backup then copy; manifest items no longer in repo (or now excluded) ⇒ delete; anything else untouched. Existing non-manifest `CLAUDE.md` is backed up once before first overwrite.

- [ ] **Step 1: Tests** — `test_fresh_install_copies_and_records_manifest`, `test_collision_backed_up_then_adopted`, `test_user_item_not_in_repo_untouched`, `test_removed_from_repo_deleted_if_manifest_owned`, `test_target_exclusion_removes_previously_installed`, `test_idempotent_second_run_no_changes` (mtimes unchanged), `test_claude_md_composed_with_linux_overlay`.
- [ ] **Steps 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit `feat: install config files with manifest and backups`.

### Task 7: Install — plugins & MCPs + install.sh

**Files:**
- Modify: `ccsync/install.py`
- Create: `scripts/install.sh`
- Test: `tests/test_install_cli.py`

**Interfaces:**
- Produces: `install_plugins(plugins_cfg: dict, target: str, targets_cfg: dict, manifest: dict, run: Callable[[list[str]], CompletedProcess]) -> None`; `install_mcps(mcp_cfg: dict, env: dict, target: str, targets_cfg: dict, manifest: dict, run) -> list[str]` (returns skipped server names). `run` is injected so tests use a fake recorder.

Plugins: installed set from `claude plugin list --json` (verify actual JSON shape against the real CLI first and adapt the parser). Add each needed marketplace (`claude plugin marketplace add <owner/repo>` for github sources, URL otherwise) if missing; `claude plugin install <id> --scope user` for missing; `claude plugin uninstall <id>` for manifest-owned plugins no longer wanted. MCPs: `strip_windows_wrapper` → `expand` with env from `~/.claude-config/secrets.env` plus `os.environ` → `claude mcp remove -s user <n>` then `claude mcp add-json -s user <n> <json>` when content hash changed vs manifest; remove manifest-owned MCPs no longer in repo.

`install.sh [--target vps|cloud]`: check `python3`, `git`, `claude` on PATH (missing ⇒ one line + exit 1 + status), then `python3 -m ccsync install --target "$TARGET"` from the repo dir.

- [ ] **Step 1: Tests** — `test_installs_missing_plugin_and_marketplace`, `test_skips_already_installed`, `test_uninstalls_manifest_owned_removed_plugin`, `test_never_uninstalls_unowned_plugin`, `test_cloud_excludes_claude_mem`, `test_mcp_skipped_when_secret_missing`, `test_mcp_readded_only_when_changed`, `test_commands_are_arg_lists_not_strings`.
- [ ] **Steps 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Docker-free smoke test on Windows via Git Bash is not representative — defer real run to Task 10.
- [ ] **Step 6:** Commit `feat: mirror plugins and MCP servers on targets`.

### Task 8: Windows hooks + CLAUDE.md split (user approval)

**Files:**
- Create: `~/.claude/claude-config/CLAUDE.base.md`, `CLAUDE.windows.md`, `CLAUDE.linux.md`
- Modify: `~/.claude/settings.json` (add `hooks.SessionEnd` → hidden detached `powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/alpay.catal/claude-config/scripts/sync.ps1`; `hooks.SessionStart` → `py -3 -m ccsync status --notice` with cwd/`PYTHONPATH` at the repo)

- [ ] **Step 1:** Split current `~/.claude/CLAUDE.md`: XAMPP/PHP-on-Windows/PowerShell/log-path specifics → windows; Linux equivalents (only where needed) → linux; rest → base. Verify `compose(base, windows)` keeps every original rule (diff by rule lines).
- [ ] **Step 2:** **Show the three files to the user and wait for approval.** No hooks before approval.
- [ ] **Step 3:** Back up `settings.json` to `~/.claude-config/backup/`, add hooks, validate JSON parses.
- [ ] **Step 4:** Verify: start a new `claude -p "hi"` session → SessionStart prints nothing when status ok; force `--set-fail test` → warning appears; reset.

### Task 9: GitHub repo + first sync

- [ ] **Step 1:** `gh repo create radamath/claude-config --private --source C:/Users/alpay.catal/claude-config --remote origin` (no README init).
- [ ] **Step 2:** Run `sync.ps1` manually. Verify on GitHub: `gh api repos/radamath/claude-config/contents` lists only expected top-level entries; `gh repo view --json visibility` = PRIVATE; secret scan passed.
- [ ] **Step 3:** Verify `plugins.json` includes `thedotmack` marketplace.

### Task 10: VPS bootstrap (needs user input)

**Files:**
- Create: `scripts/vps-bootstrap.sh`, `scripts/systemd/claude-config-sync.service`, `scripts/systemd/claude-config-sync.timer` (user units, `OnUnitActiveSec=15min`)

- [ ] **Step 1:** Ask user: SSH host/user, OS, whether Claude Code is installed and logged in.
- [ ] **Step 2:** Generate read-only deploy key on VPS, add via `gh repo deploy-key add --title vps` (read-only), clone to `~/.claude-config/repo`.
- [ ] **Step 3:** `touch ~/.claude-config/secrets.env && chmod 600`.
- [ ] **Step 4:** Run `install.sh --target vps`; verify `claude plugin list`, `ls ~/.claude/skills`, `head ~/.claude/CLAUDE.md` show linux overlay.
- [ ] **Step 5:** Enable timer (`systemctl --user enable --now`, `loginctl enable-linger`); verify `systemctl --user list-timers` and second run idempotent.
- [ ] **Step 6:** End-to-end: add a dummy skill on Windows → session end → within 15 min present on VPS → delete → removed. Commit scripts `feat: add VPS bootstrap and sync timer`.

### Task 11: Cloud setup + spike

**Files:**
- Create: `scripts/cloud-setup.sh` (clone via `https://github.com/radamath/claude-config` through the GitHub proxy into `/opt/claude-config`, run `install.sh --target cloud`), `docs/cloud.md` (user steps)

- [ ] **Step 1:** User installs Claude GitHub App on `claude-config` and pastes `cloud-setup.sh` into the environment's setup script. `docs/cloud.md` states the ~7-day snapshot lag and how to force a rerun (edit the setup script, e.g. bump a `# rev N` comment).
- [ ] **Step 2:** Spike in a cloud session: check `/root/.claude/skills`, `/root/.claude/CLAUDE.md`, `claude plugin list`, and whether the skills/plugins actually load (`/skills`). Record results in `docs/cloud.md`.
- [ ] **Step 3:** If plugins don't load in cloud: set `targets.json` cloud `exclude_plugins` to all, document limitation; report to user.
- [ ] **Step 4:** Commit `feat: add cloud environment setup script`.
