import unittest

from ccsync.mcp import expand, load_env_file, redact, strip_windows_wrapper
from tests.helpers import make_tree

SERVERS = {
    "my-api": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "my-api-mcp"],
        "env": {"x.token": "real-secret-value", "MODE": "prod"},
    },
    "remote": {"type": "http", "url": "https://mcp.example.com/mcp", "headers": {"Authorization": "Bearer abc"}},
}


class McpTest(unittest.TestCase):
    def test_redact_env_values(self):
        env = redact(SERVERS)["my-api"]["env"]
        self.assertEqual(env, {"x.token": "${MCP_MY_API_X_TOKEN}", "MODE": "${MCP_MY_API_MODE}"})

    def test_redact_header_values(self):
        self.assertEqual(redact(SERVERS)["remote"]["headers"], {"Authorization": "${MCP_REMOTE_AUTHORIZATION}"})

    def test_redact_leaves_command_args_url(self):
        out = redact(SERVERS)
        self.assertEqual(out["my-api"]["args"], ["-y", "my-api-mcp"])
        self.assertEqual(out["remote"]["url"], "https://mcp.example.com/mcp")
        self.assertNotIn("real-secret-value", repr(out))
        self.assertEqual(SERVERS["my-api"]["env"]["x.token"], "real-secret-value", "input must not be mutated")

    def test_placeholder_name_sanitized(self):
        self.assertIn("${MCP_MY_API_X_TOKEN}", redact(SERVERS)["my-api"]["env"].values())

    def test_expand_fills_all(self):
        server = redact(SERVERS)["my-api"]
        out = expand(server, {"MCP_MY_API_X_TOKEN": "t", "MCP_MY_API_MODE": "prod"})
        self.assertEqual(out["env"], {"x.token": "t", "MODE": "prod"})

    def test_expand_returns_none_on_missing(self):
        server = redact(SERVERS)["my-api"]
        self.assertIsNone(expand(server, {"MCP_MY_API_X_TOKEN": "t"}))

    def test_strip_cmd_c_wrapper(self):
        server = {"command": "cmd", "args": ["/c", "npx", "-y", "pkg"]}
        self.assertEqual(strip_windows_wrapper(server), {"command": "npx", "args": ["-y", "pkg"]})

    def test_strip_noop_for_linux_command(self):
        server = {"command": "npx", "args": ["-y", "pkg"]}
        self.assertEqual(strip_windows_wrapper(server), server)

    def test_load_env_file_ignores_comments_and_blank(self):
        root = make_tree({"s.env": "# c\n\nA=1\nB = two=2\n  C=$HOME\n"})
        self.assertEqual(load_env_file(root / "s.env"), {"A": "1", "B": "two=2", "C": "$HOME"})

    def test_load_env_file_missing_returns_empty(self):
        root = make_tree({})
        self.assertEqual(load_env_file(root / "nope.env"), {})


if __name__ == "__main__":
    unittest.main()
