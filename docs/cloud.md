# claude.ai/code cloud setup

Cloud sessions run in a fresh VM and never see the Windows `~/.claude`. The environment's
setup script pulls this repo and installs it into the VM's `~/.claude` before Claude Code starts.

## One-time steps (done by the user in the browser)

1. Nothing to grant on GitHub: the repo is public (see Verification results).
2. claude.ai/code → environment settings → **Setup script**: paste the contents of
   `scripts/cloud-setup.sh`.
3. MCP secrets: add them as **network secrets** on the environment, never as plain environment
   variables (those are readable by everyone using the environment). An MCP whose secret is missing
   is skipped and reported, not installed half-configured.

## Freshness

The setup result is cached as a snapshot for about 7 days. Changes synced from Windows reach cloud
sessions when the snapshot rebuilds. To force it sooner, edit the setup script (bump `# rev N`).

## Not synced to cloud

- `claude-mem` (excluded in `targets.json`): the VM is temporary, there is no memory to keep.

## Verification results (2026-11-21)

- The cloud GitHub proxy injects credentials only for repositories **attached to the session**
  (selected at session start or added with `add_repo`), not for every repository the Claude GitHub
  App can access. A setup script therefore could not clone this repo while it was private
  (`clone failed` in `~/.claude-config/last-install.json`).
- Decision: the repo was made **public**, so the setup script clones it anonymously in every session.
  Secrets never enter the repo (redaction + fail-closed scan on export), so public visibility exposes
  only rules, agents and skills.
- `gh repo clone` does not work in cloud sessions (the proxy blocks GraphQL); use plain `git clone`.
