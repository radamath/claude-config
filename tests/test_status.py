import unittest

from ccsync import status
from tests.helpers import make_tree


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.path = make_tree({}) / "state" / "last-sync.json"

    def test_read_missing_returns_none(self):
        self.assertIsNone(status.read(self.path))

    def test_write_then_read_roundtrip(self):
        status.write(self.path, False, "push rejected")
        data = status.read(self.path)
        self.assertFalse(data["ok"])
        self.assertEqual(data["message"], "push rejected")
        self.assertIn("T", data["at"])

    def test_status_notice_only_when_failed(self):
        self.assertIsNone(status.notice(self.path))
        status.write(self.path, True, "ok")
        self.assertIsNone(status.notice(self.path))
        status.write(self.path, False, "secret found in skills/x/SKILL.md:3\nsecond line")
        msg = status.notice(self.path)
        self.assertIn("secret found in skills/x/SKILL.md:3", msg)
        self.assertNotIn("\n", msg)


if __name__ == "__main__":
    unittest.main()
