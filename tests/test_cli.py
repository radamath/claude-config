import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from ccsync import __main__ as cli
from ccsync.export import ExportError, SyncBusy
from tests.helpers import make_tree


def run(argv, home):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(cli.Path, "home", return_value=home), redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class CliTest(unittest.TestCase):
    def setUp(self):
        self.home = make_tree({})

    def test_export_success_returns_0(self):
        with mock.patch.object(cli, "export") as exp:
            code, _, _ = run(["export"], self.home)
        self.assertEqual(code, 0)
        args = exp.call_args.args
        self.assertEqual(args[0], self.home / ".claude")
        self.assertEqual(args[1], self.home / ".claude.json")
        self.assertEqual(args[3], self.home / ".claude-config")

    def test_export_busy_returns_3(self):
        with mock.patch.object(cli, "export", side_effect=SyncBusy("busy")):
            code, _, _ = run(["export"], self.home)
        self.assertEqual(code, cli.EXIT_BUSY)

    def test_export_error_returns_1_and_prints_message(self):
        with mock.patch.object(cli, "export", side_effect=ExportError("secret in x:1")):
            code, _, err = run(["export"], self.home)
        self.assertEqual(code, 1)
        self.assertIn("secret in x:1", err)

    def test_status_set_fail_then_notice(self):
        self.assertEqual(run(["status", "--set-fail", "push rejected"], self.home)[0], 0)
        code, out, _ = run(["status", "--notice"], self.home)
        self.assertEqual(code, 0)
        self.assertIn("push rejected", out)

    def test_status_notice_silent_when_ok(self):
        run(["status", "--set-ok"], self.home)
        self.assertEqual(run(["status", "--notice"], self.home)[1], "")


if __name__ == "__main__":
    unittest.main()
