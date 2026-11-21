import json
import os
import time
import unittest

from ccsync.compose import content_hash
from ccsync.export import ExportError, SyncBusy, acquire_lock, export, release_lock
from tests.helpers import make_tree

GH_PAT = "ghp_" + "B" * 36


def windows_home(extra=None):
    settings = {
        "enabledPlugins": {"superpowers@superpowers-marketplace": True},
        "extraKnownMarketplaces": {
            "superpowers-marketplace": {"source": {"source": "github", "repo": "obra/superpowers-marketplace"}}
        },
        "hooks": {"SessionEnd": []},
    }
    files = {
        ".claude/CLAUDE.md": "old global rules\n",
        ".claude/claude-config/CLAUDE.base.md": "# Base\nshared\n",
        ".claude/claude-config/CLAUDE.windows.md": "# Windows\nxampp\n",
        ".claude/claude-config/CLAUDE.linux.md": "# Linux\napt\n",
        ".claude/skills/ship/SKILL.md": "---\nname: ship\n---\n",
        ".claude/skills/synced/abc/SKILL.md": "managed by claude.ai\n",
        ".claude/agents/architect.md": "agent\n",
        ".claude/.credentials.json": json.dumps({"token": "x"}),
        ".claude/history.jsonl": "{}\n",
        ".claude/projects/p/s.jsonl": "{}\n",
        ".claude/settings.json": json.dumps(settings),
        ".claude/plugins/known_marketplaces.json": "{}",
        ".claude.json": json.dumps({"mcpServers": {"api": {"command": "npx", "env": {"KEY": "s3cr3t"}}}}),
        "repo/.secretscan-allow": "",
        "repo/targets.json": "{}",
    }
    files.update(extra or {})
    return make_tree(files)


class ExportTest(unittest.TestCase):
    def run_export(self, root):
        export(root / ".claude", root / ".claude.json", root / "repo", root / "state")

    def test_exports_whitelisted_items_only(self):
        root = windows_home()
        self.run_export(root)
        repo = root / "repo"
        expected = [
            ".secretscan-allow", "targets.json", "CLAUDE.base.md", "CLAUDE.windows.md", "CLAUDE.linux.md",
            "skills", "agents", "plugins.json", "mcp.json",
        ]
        self.assertEqual(sorted(p.name for p in repo.iterdir()), sorted(expected))
        self.assertTrue((repo / "skills/ship/SKILL.md").is_file())
        self.assertTrue((repo / "agents/architect.md").is_file())

    def test_plugins_and_mcp_written_redacted(self):
        root = windows_home()
        self.run_export(root)
        plugins = json.loads((root / "repo/plugins.json").read_text())
        self.assertEqual(plugins["plugins"], ["superpowers@superpowers-marketplace"])
        mcp_text = (root / "repo/mcp.json").read_text()
        self.assertNotIn("s3cr3t", mcp_text)
        self.assertIn("${MCP_API_KEY}", mcp_text)

    def test_skips_synced_skill_dir(self):
        root = windows_home()
        self.run_export(root)
        self.assertFalse((root / "repo/skills/synced").exists())

    def test_symlinked_skill_copied_as_files(self):
        root = windows_home({"elsewhere/find-skills/SKILL.md": "real content\n"})
        link = root / ".claude/skills/find-skills"
        try:
            os.symlink(root / "elsewhere/find-skills", link, target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation not permitted")
        self.run_export(root)
        out = root / "repo/skills/find-skills"
        self.assertFalse(out.is_symlink())
        self.assertEqual((out / "SKILL.md").read_text(), "real content\n")

    @unittest.skipUnless(os.name == "nt", "junctions are Windows-only")
    def test_junctioned_skill_copied_as_files(self):
        import subprocess
        root = windows_home({"elsewhere/find-skills/SKILL.md": "real content\n"})
        link = root / ".claude/skills/find-skills"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(root / "elsewhere/find-skills")],
                       check=True, capture_output=True)
        self.run_export(root)
        out = root / "repo/skills/find-skills"
        self.assertFalse(out.is_symlink() or out.is_junction())
        self.assertEqual((out / "SKILL.md").read_text(), "real content\n")
        self.assertTrue((root / "elsewhere/find-skills/SKILL.md").exists(), "source must survive")

    def test_removes_repo_skill_deleted_on_windows(self):
        root = windows_home({"repo/skills/gone/SKILL.md": "old\n"})
        self.run_export(root)
        self.assertFalse((root / "repo/skills/gone").exists())

    def test_binary_and_crlf_preserved_byte_exact(self):
        blob = bytes(range(256))
        root = windows_home({
            ".claude/skills/bin/asset.bin": blob,
            ".claude/skills/bin/SKILL.md": b"line1\r\nline2\r\n",
        })
        self.run_export(root)
        self.assertEqual((root / "repo/skills/bin/asset.bin").read_bytes(), blob)
        self.assertEqual((root / "repo/skills/bin/SKILL.md").read_bytes(), b"line1\r\nline2\r\n")

    def test_first_run_without_hash_composes_and_stores_hash(self):
        root = windows_home()
        self.run_export(root)
        composed = (root / ".claude/CLAUDE.md").read_text()
        self.assertEqual(composed, "# Base\nshared\n\n# Windows\nxampp\n")
        self.assertEqual((root / "state/composed.sha256").read_text().strip(), content_hash(composed))
        backups = list((root / "state/backup").rglob("CLAUDE.md"))
        self.assertEqual([b.read_text() for b in backups], ["old global rules\n"])

    def test_drift_detected_raises_and_leaves_claude_md_untouched(self):
        root = windows_home()
        self.run_export(root)
        (root / ".claude/CLAUDE.md").write_text("hand edit\n")
        with self.assertRaises(ExportError) as ctx:
            self.run_export(root)
        self.assertIn("CLAUDE.md", str(ctx.exception))
        self.assertEqual((root / ".claude/CLAUDE.md").read_text(), "hand edit\n")

    def test_missing_parts_dir_raises(self):
        root = windows_home()
        for p in (root / ".claude/claude-config").iterdir():
            p.unlink()
        (root / ".claude/claude-config").rmdir()
        with self.assertRaises(ExportError):
            self.run_export(root)
        self.assertEqual((root / ".claude/CLAUDE.md").read_text(), "old global rules\n")

    def test_secret_finding_raises_and_names_file(self):
        root = windows_home({".claude/skills/leak/SKILL.md": f"use {GH_PAT}\n"})
        with self.assertRaises(ExportError) as ctx:
            self.run_export(root)
        self.assertIn("skills/leak/SKILL.md:1", str(ctx.exception))

    def test_lock_blocks_second_export(self):
        root = windows_home()
        self.assertTrue(acquire_lock(root / "state"))
        try:
            with self.assertRaises(SyncBusy):
                self.run_export(root)
        finally:
            release_lock(root / "state")
        self.run_export(root)

    def test_stale_lock_ignored(self):
        root = windows_home()
        state = root / "state"
        state.mkdir()
        lock = state / "sync.lock"
        lock.write_text("old")
        old = time.time() - 11 * 60
        os.utime(lock, (old, old))
        self.run_export(root)
        self.assertFalse(lock.exists())


if __name__ == "__main__":
    unittest.main()
