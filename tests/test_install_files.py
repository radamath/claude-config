import os
import time
import unittest

from ccsync import manifest
from ccsync.install import install_files
from tests.helpers import make_tree

REPO = {
    "repo/CLAUDE.base.md": "# Base\n",
    "repo/CLAUDE.windows.md": "# Win\n",
    "repo/CLAUDE.linux.md": "# Linux\n",
    "repo/skills/ship/SKILL.md": "ship v1\n",
    "repo/skills/ship/ref/notes.md": "notes\n",
    "repo/skills/bug-hunt/SKILL.md": "bug\n",
    "repo/agents/architect.md": "architect\n",
}
NO_EXCLUDES = {"vps": {}, "cloud": {}}


class InstallFilesTest(unittest.TestCase):
    def setUp(self):
        self.root = make_tree(REPO)
        self.repo, self.home, self.state = self.root / "repo", self.root / ".claude", self.root / ".claude-config"
        self.home.mkdir()

    def install(self, target="vps", cfg=NO_EXCLUDES):
        return install_files(self.repo, self.home, self.state, target, cfg)

    def backups(self):
        base = self.state / "backup"
        return sorted(p.relative_to(base).as_posix().split("/", 1)[1] for p in base.rglob("*") if p.is_file()) \
            if base.exists() else []

    def test_fresh_install_copies_and_records_manifest(self):
        result = self.install()
        self.assertEqual((self.home / "skills/ship/ref/notes.md").read_text(), "notes\n")
        self.assertEqual((self.home / "agents/architect.md").read_text(), "architect\n")
        self.assertEqual(result["files"], ["CLAUDE.md", "agents/architect.md", "skills/bug-hunt", "skills/ship"])
        self.assertEqual(manifest.load(self.home / manifest.MANIFEST_NAME)["files"], result["files"])

    def test_claude_md_composed_with_linux_overlay(self):
        self.install()
        self.assertEqual((self.home / "CLAUDE.md").read_text(), "# Base\n\n# Linux\n")

    def test_collision_backed_up_then_adopted(self):
        (self.home / "skills/ship").mkdir(parents=True)
        (self.home / "skills/ship/SKILL.md").write_text("hand made\n")
        (self.home / "CLAUDE.md").write_text("vps rules\n")
        result = self.install()
        self.assertEqual((self.home / "skills/ship/SKILL.md").read_text(), "ship v1\n")
        self.assertIn("skills/ship", result["files"])
        self.assertEqual(self.backups(), ["CLAUDE.md", "skills/ship/SKILL.md"])

    def test_user_item_not_in_repo_untouched(self):
        (self.home / "skills/mine").mkdir(parents=True)
        (self.home / "skills/mine/SKILL.md").write_text("mine\n")
        self.install()
        self.repo.joinpath("skills/ship/SKILL.md").write_text("ship v2\n")
        self.install()
        self.assertEqual((self.home / "skills/mine/SKILL.md").read_text(), "mine\n")
        self.assertEqual(self.backups(), [])

    def test_removed_from_repo_deleted_if_manifest_owned(self):
        self.install()
        for p in (self.repo / "skills/bug-hunt").iterdir():
            p.unlink()
        (self.repo / "skills/bug-hunt").rmdir()
        result = self.install()
        self.assertFalse((self.home / "skills/bug-hunt").exists())
        self.assertNotIn("skills/bug-hunt", result["files"])

    def test_target_exclusion_removes_previously_installed(self):
        self.install()
        cfg = {"cloud": {"exclude_skills": ["bug-hunt"], "exclude_agents": ["architect"]}}
        result = self.install(target="cloud", cfg=cfg)
        self.assertFalse((self.home / "skills/bug-hunt").exists())
        self.assertFalse((self.home / "agents/architect.md").exists())
        self.assertEqual(result["files"], ["CLAUDE.md", "skills/ship"])

    def test_updated_repo_content_replaces_owned_copy(self):
        self.install()
        (self.repo / "skills/ship/ref/notes.md").unlink()
        (self.repo / "skills/ship/SKILL.md").write_text("ship v2\n")
        self.install()
        self.assertEqual((self.home / "skills/ship/SKILL.md").read_text(), "ship v2\n")
        self.assertFalse((self.home / "skills/ship/ref/notes.md").exists())

    def test_idempotent_second_run_no_changes(self):
        self.install()
        files = [p for p in self.home.rglob("*") if p.is_file() and p.name != manifest.MANIFEST_NAME]
        old = time.time() - 3600
        for p in files:
            os.utime(p, (old, old))
        self.install()
        self.assertTrue(all(abs(p.stat().st_mtime - old) < 1 for p in files))

    def test_preserves_plugins_and_mcps_in_manifest(self):
        manifest.save(self.home / manifest.MANIFEST_NAME, {"files": [], "plugins": ["a@b"], "mcps": {"x": "h"}})
        result = self.install()
        self.assertEqual(result["plugins"], ["a@b"])
        self.assertEqual(result["mcps"], {"x": "h"})


if __name__ == "__main__":
    unittest.main()
