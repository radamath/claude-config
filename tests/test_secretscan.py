import unittest
from pathlib import Path

from ccsync.secretscan import scan
from tests.helpers import make_tree

GH_PAT = "ghp_" + "A" * 36


class SecretScanTest(unittest.TestCase):
    def scan_files(self, files, allow=""):
        root = make_tree(files)
        allow_file = root / ".secretscan-allow"
        allow_file.write_text(allow, encoding="utf-8")
        return scan(root, allow_file)

    def test_detects_github_pat(self):
        findings = self.scan_files({"skills/a/SKILL.md": f"token {GH_PAT}\n"})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].path, "skills/a/SKILL.md")
        self.assertEqual(findings[0].line, 1)

    def test_detects_private_key_header(self):
        findings = self.scan_files({"a.md": "x\n-----BEGIN OPENSSH PRIVATE KEY-----\n"})
        self.assertEqual([f.line for f in findings], [2])

    def test_detects_oauth_token_assignment(self):
        findings = self.scan_files({"a.md": "CLAUDE_CODE_OAUTH_TOKEN=abc\n"})
        self.assertEqual(len(findings), 1)

    def test_flags_env_and_credentials_filenames(self):
        findings = self.scan_files({".env": "", "x/credentials.json": "{}"})
        self.assertEqual(sorted(f.path for f in findings), [".env", "x/credentials.json"])

    def test_allowlist_suppresses_matching_path_and_pattern(self):
        findings = self.scan_files(
            {"skills/sec/SKILL.md": "look for -----BEGIN RSA PRIVATE KEY----- in code\n"},
            allow="skills/sec/* BEGIN  # security skill documents the pattern\n",
        )
        self.assertEqual(findings, [])

    def test_allowlist_does_not_suppress_other_paths(self):
        findings = self.scan_files(
            {"skills/other/SKILL.md": "-----BEGIN RSA PRIVATE KEY-----\n"},
            allow="skills/sec/* BEGIN  # only sec\n",
        )
        self.assertEqual(len(findings), 1)

    def test_ignores_dot_git_dir(self):
        findings = self.scan_files({".git/config": f"{GH_PAT}\n", ".superpowers/x": f"{GH_PAT}\n"})
        self.assertEqual(findings, [])

    def test_placeholder_not_flagged(self):
        findings = self.scan_files({"mcp.json": '{"env": {"API_TOKEN": "${MCP_X_API_TOKEN}"}}\n'})
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
