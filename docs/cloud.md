# claude.ai/code cloud setup

Cloud sessions run in a fresh VM and never see the Windows `~/.claude`. The environment's
setup script pulls this repo and installs it into the VM's `~/.claude` before Claude Code starts.

## One-time steps (done by the user in the browser)

1. Install the Claude GitHub App on `radamath/claude-config` (GitHub → Settings → Applications →
   Claude → Repository access → add `claude-config`).
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

## Verification results

Filled in after the first cloud session test (see plan Task 11).
