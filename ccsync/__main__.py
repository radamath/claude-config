"""Command line entry point: python -m ccsync <export|install|status>."""
import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ccsync")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export", help="Windows: export ~/.claude into this repo")
    install = sub.add_parser("install", help="Linux: apply this repo to ~/.claude")
    install.add_argument("--target", choices=["vps", "cloud"], required=True)
    status = sub.add_parser("status", help="Read or write the last run status")
    group = status.add_mutually_exclusive_group(required=True)
    group.add_argument("--notice", action="store_true")
    group.add_argument("--set-ok", action="store_true")
    group.add_argument("--set-fail", metavar="MESSAGE")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    print(f"ccsync: '{args.command}' not implemented yet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
