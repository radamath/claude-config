"""Command line entry point: python -m ccsync <export|install|status>."""
import argparse
import json
import sys
from pathlib import Path

from ccsync import status
from ccsync.export import ExportError, SyncBusy, export
from ccsync.install import run_install

EXIT_BUSY = 3
REPO_DIR = Path(__file__).resolve().parent.parent
STATE_DIR_NAME = ".claude-config"
# Windows records sync results, Linux targets record install results.
SYNC_STATUS = "last-sync.json"
INSTALL_STATUS = "last-install.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ccsync")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export", help="Windows: export ~/.claude into this repo")
    install = sub.add_parser("install", help="Linux: apply this repo to ~/.claude")
    install.add_argument("--target", choices=["vps", "cloud"], required=True)
    st = sub.add_parser("status", help="Read or write the last run status")
    st.add_argument("--file", default=SYNC_STATUS, help="status file name inside ~/.claude-config")
    group = st.add_mutually_exclusive_group(required=True)
    group.add_argument("--notice", action="store_true")
    group.add_argument("--set-ok", action="store_true")
    group.add_argument("--set-fail", metavar="MESSAGE")
    st.add_argument("--hook", action="store_true", help="with --notice: print SessionStart hook JSON")
    return parser


def cmd_export(home: Path) -> int:
    try:
        export(home / ".claude", home / ".claude.json", REPO_DIR, home / STATE_DIR_NAME)
    except SyncBusy as exc:
        print(f"ccsync: {exc}", file=sys.stderr)
        return EXIT_BUSY
    except ExportError as exc:
        print(f"ccsync: export failed: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_install(home: Path, target: str) -> int:
    status_path = home / STATE_DIR_NAME / INSTALL_STATUS
    try:
        problems = run_install(REPO_DIR, home, target)
    except (RuntimeError, OSError, ValueError) as exc:
        problems = [f"install aborted: {exc}"]
    if problems:
        for problem in problems:
            print(f"ccsync: {problem}", file=sys.stderr)
        status.write(status_path, False, "; ".join(problems))
        return 1
    status.write(status_path, True, "ok")
    return 0


def cmd_status(home: Path, args) -> int:
    path = home / STATE_DIR_NAME / args.file
    if args.notice:
        message = status.notice(path)
        if message and args.hook:
            print(json.dumps({
                "systemMessage": message,
                "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": message},
            }, ensure_ascii=False))
        elif message:
            print(message)
    elif args.set_ok:
        status.write(path, True, "ok")
    else:
        status.write(path, False, args.set_fail)
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    home = Path.home()
    if args.command == "export":
        return cmd_export(home)
    if args.command == "status":
        return cmd_status(home, args)
    return cmd_install(home, args.target)


if __name__ == "__main__":
    sys.exit(main())
