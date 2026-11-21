import unittest

from ccsync.compose import compose, content_hash, target_overlay_name


class ComposeTest(unittest.TestCase):
    def test_compose_joins_with_blank_line(self):
        self.assertEqual(compose("# Base\nrule\n", "# Win\nx\n"), "# Base\nrule\n\n# Win\nx\n")

    def test_compose_empty_overlay_returns_base_with_single_trailing_newline(self):
        self.assertEqual(compose("# Base\n\n\n", "  \n"), "# Base\n")

    def test_overlay_name_maps_vps_and_cloud_to_linux(self):
        self.assertEqual(target_overlay_name("vps"), "CLAUDE.linux.md")
        self.assertEqual(target_overlay_name("cloud"), "CLAUDE.linux.md")
        self.assertEqual(target_overlay_name("linux"), "CLAUDE.linux.md")
        self.assertEqual(target_overlay_name("windows"), "CLAUDE.windows.md")

    def test_overlay_name_rejects_unknown(self):
        with self.assertRaises(ValueError):
            target_overlay_name("mac")

    def test_hash_ignores_crlf_vs_lf(self):
        self.assertEqual(content_hash("a\r\nb\r\n"), content_hash("a\nb\n"))
        self.assertNotEqual(content_hash("a\nb\n"), content_hash("a\nc\n"))


if __name__ == "__main__":
    unittest.main()
