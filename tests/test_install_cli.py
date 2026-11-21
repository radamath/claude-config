import json
import subprocess
import unittest

from ccsync.install import install_mcps, install_plugins

PLUGINS = {
    "marketplaces": {
        "superpowers-marketplace": {"source": "github", "repo": "obra/superpowers-marketplace"},
        "thedotmack": {"source": "github", "repo": "thedotmack/claude-mem"},
    },
    "plugins": ["claude-mem@thedotmack", "superpowers@superpowers-marketplace"],
}
MCP = {
    "api": {"command": "cmd", "args": ["/c", "npx", "api-mcp"], "env": {"KEY": "${MCP_API_KEY}"}},
    "docs": {"type": "http", "url": "https://example.com/mcp"},
}


class FakeRunner:
    def __init__(self, installed=(), markets=(), fail=()):
        self.installed, self.markets, self.fail = list(installed), list(markets), set(fail)
        self.calls = []

    def __call__(self, args, input=None):
        self.calls.append((args, input))
        out = ""
        if args[1:] == ["plugin", "list", "--json"]:
            out = json.dumps([{"id": i, "enabled": True} for i in self.installed])
        elif args[1:] == ["plugin", "marketplace", "list", "--json"]:
            out = json.dumps([{"name": m} for m in self.markets])
        code = 1 if any(f in args for f in self.fail) else 0
        return subprocess.CompletedProcess(args, code, stdout=out, stderr="boom" if code else "")

    def commands(self):
        return [a for a, _ in self.calls if "list" not in a]


def manifest(plugins=(), mcps=None):
    return {"files": [], "plugins": list(plugins), "mcps": dict(mcps or {})}


class InstallPluginsTest(unittest.TestCase):
    def test_installs_missing_plugin_and_marketplace(self):
        run = FakeRunner(installed=["superpowers@superpowers-marketplace"], markets=["superpowers-marketplace"])
        m = manifest()
        errors = install_plugins(PLUGINS, "vps", {}, m, run)
        self.assertEqual(errors, [])
        self.assertEqual(run.commands(), [
            ["claude", "plugin", "marketplace", "add", "thedotmack/claude-mem"],
            ["claude", "plugin", "install", "claude-mem@thedotmack", "--scope", "user"],
        ])
        self.assertEqual(m["plugins"], ["claude-mem@thedotmack", "superpowers@superpowers-marketplace"])

    def test_skips_already_installed(self):
        run = FakeRunner(installed=PLUGINS["plugins"], markets=PLUGINS["marketplaces"])
        install_plugins(PLUGINS, "vps", {}, manifest(), run)
        self.assertEqual(run.commands(), [])

    def test_uninstalls_manifest_owned_removed_plugin(self):
        run = FakeRunner(installed=PLUGINS["plugins"] + ["old@x"], markets=PLUGINS["marketplaces"])
        m = manifest(plugins=["old@x"])
        install_plugins(PLUGINS, "vps", {}, m, run)
        self.assertEqual(run.commands(), [["claude", "plugin", "uninstall", "old@x", "--scope", "user"]])
        self.assertNotIn("old@x", m["plugins"])

    def test_never_uninstalls_unowned_plugin(self):
        run = FakeRunner(installed=PLUGINS["plugins"] + ["mine@x"], markets=PLUGINS["marketplaces"])
        install_plugins(PLUGINS, "vps", {}, manifest(), run)
        self.assertEqual(run.commands(), [])

    def test_cloud_excludes_claude_mem(self):
        run = FakeRunner(markets=PLUGINS["marketplaces"])
        m = manifest()
        install_plugins(PLUGINS, "cloud", {"cloud": {"exclude_plugins": ["claude-mem@thedotmack"]}}, m, run)
        self.assertEqual(run.commands(), [
            ["claude", "plugin", "install", "superpowers@superpowers-marketplace", "--scope", "user"],
        ])
        self.assertEqual(m["plugins"], ["superpowers@superpowers-marketplace"])

    def test_failed_install_reported_and_not_owned(self):
        run = FakeRunner(markets=PLUGINS["marketplaces"], fail=["claude-mem@thedotmack"])
        m = manifest()
        errors = install_plugins(PLUGINS, "vps", {}, m, run)
        self.assertEqual(len(errors), 1)
        self.assertIn("claude-mem@thedotmack", errors[0])
        self.assertNotIn("claude-mem@thedotmack", m["plugins"])


class InstallMcpsTest(unittest.TestCase):
    def test_mcp_skipped_when_secret_missing(self):
        run = FakeRunner()
        m = manifest()
        skipped = install_mcps(MCP, {}, "vps", {}, m, run)
        self.assertEqual(skipped, ["api"])
        added = [a for a in run.commands() if "add-json" in a]
        self.assertEqual([a[5] for a in added], ["docs"])

    def test_secret_passed_via_stdin_not_args(self):
        run = FakeRunner()
        install_mcps(MCP, {"MCP_API_KEY": "s3cr3t"}, "vps", {}, manifest(), run)
        add = [(a, i) for a, i in run.calls if "add-json" in a and "api" in a][0]
        self.assertEqual(add[0], ["claude", "mcp", "add-json", "-s", "user", "api", "-"])
        self.assertNotIn("s3cr3t", " ".join(add[0]))
        sent = json.loads(add[1])
        self.assertEqual(sent["env"], {"KEY": "s3cr3t"})
        self.assertEqual(sent["command"], "npx")

    def test_mcp_readded_only_when_changed(self):
        m = manifest()
        install_mcps(MCP, {"MCP_API_KEY": "k"}, "vps", {}, m, FakeRunner())
        run = FakeRunner()
        install_mcps(MCP, {"MCP_API_KEY": "k"}, "vps", {}, m, run)
        self.assertEqual(run.commands(), [])
        run = FakeRunner()
        install_mcps(MCP, {"MCP_API_KEY": "k2"}, "vps", {}, m, run)
        self.assertEqual(run.commands(), [
            ["claude", "mcp", "remove", "-s", "user", "api"],
            ["claude", "mcp", "add-json", "-s", "user", "api", "-"],
        ])

    def test_removes_owned_mcp_no_longer_in_repo(self):
        m = manifest(mcps={"gone": "h", "docs": "x"})
        run = FakeRunner()
        install_mcps({"docs": MCP["docs"]}, {}, "vps", {}, m, run)
        self.assertIn(["claude", "mcp", "remove", "-s", "user", "gone"], run.commands())
        self.assertNotIn("gone", m["mcps"])

    def test_commands_are_arg_lists_not_strings(self):
        run = FakeRunner()
        install_plugins(PLUGINS, "vps", {}, manifest(), run)
        install_mcps(MCP, {"MCP_API_KEY": "k"}, "vps", {}, manifest(), run)
        self.assertTrue(all(isinstance(a, list) and all(isinstance(x, str) for x in a) for a, _ in run.calls))


if __name__ == "__main__":
    unittest.main()
