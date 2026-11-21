import unittest

from ccsync.plugins import build_plugins

SETTINGS = {
    "enabledPlugins": {
        "superpowers@superpowers-marketplace": True,
        "claude-mem@thedotmack": True,
        "old@superpowers-marketplace": False,
    },
    "extraKnownMarketplaces": {
        "superpowers-marketplace": {"source": {"source": "github", "repo": "obra/superpowers-marketplace"}}
    },
}
KNOWN = {
    "superpowers-marketplace": {
        "source": {"source": "github", "repo": "someone/else"},
        "installLocation": r"C:\x",
    },
    "thedotmack": {
        "source": {"source": "github", "repo": "thedotmack/claude-mem"},
        "installLocation": r"C:\Users\x\.claude\plugins\marketplaces\thedotmack",
        "autoUpdate": False,
    },
    "claude-plugins-official": {"source": {"source": "github", "repo": "anthropics/claude-plugins-official"}},
}


class BuildPluginsTest(unittest.TestCase):
    def test_only_enabled_true_plugins_included(self):
        result = build_plugins(SETTINGS, KNOWN)
        self.assertEqual(result["plugins"], ["claude-mem@thedotmack", "superpowers@superpowers-marketplace"])

    def test_marketplace_from_known_marketplaces_when_missing_in_settings(self):
        result = build_plugins(SETTINGS, KNOWN)
        self.assertEqual(result["marketplaces"]["thedotmack"], {"source": "github", "repo": "thedotmack/claude-mem"})

    def test_settings_extraKnownMarketplaces_wins_on_conflict(self):
        result = build_plugins(SETTINGS, KNOWN)
        self.assertEqual(result["marketplaces"]["superpowers-marketplace"]["repo"], "obra/superpowers-marketplace")

    def test_install_location_never_emitted(self):
        self.assertNotIn("installLocation", repr(build_plugins(SETTINGS, KNOWN)))

    def test_plugin_with_unknown_marketplace_raises_ValueError(self):
        settings = {"enabledPlugins": {"x@nowhere": True}}
        with self.assertRaises(ValueError):
            build_plugins(settings, KNOWN)

    def test_official_marketplace_needs_no_entry(self):
        self.assertNotIn("claude-plugins-official", build_plugins(SETTINGS, KNOWN)["marketplaces"])
        settings = {"enabledPlugins": {"foo@claude-plugins-official": True}}
        self.assertEqual(build_plugins(settings, {})["plugins"], ["foo@claude-plugins-official"])


if __name__ == "__main__":
    unittest.main()
