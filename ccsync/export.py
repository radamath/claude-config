"""Windows side: export a whitelisted subset of ~/.claude into the repo."""
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from ccsync.compose import compose, content_hash, target_overlay_name
from ccsync.mcp import redact
from ccsync.plugins import build_plugins
from ccsync.secretscan import scan

PARTS_DIR = "claude-config"
CLAUDE_PARTS = ("CLAUDE.base.md", "CLAUDE.windows.md", "CLAUDE.linux.md")
MIRRORED_DIRS = ("skills", "agents", "commands")
# Managed by claude.ai skill sync on each machine; never distribute.
EXCLUDED_SKILLS = {"synced"}
LOCK_NAME = "sync.lock"
LOCK_STALE_SECONDS = 10 * 60
HASH_NAME = "composed.sha256"


class ExportError(Exception):
    pass


class SyncBusy(ExportError):
    """Another sync holds the lock; not a failure."""


def acquire_lock(state_dir: Path) -> bool:
    state_dir.mkdir(parents=True, exist_ok=True)
    lock = state_dir / LOCK_NAME
    if lock.exists() and time.time() - lock.stat().st_mtime > LOCK_STALE_SECONDS:
        lock.unlink()
    try:
        with open(lock, "x", encoding="utf-8") as fh:
            fh.write(str(time.time()))
    except FileExistsError:
        return False
    return True


def release_lock(state_dir: Path) -> None:
    (state_dir / LOCK_NAME).unlink(missing_ok=True)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _compose_claude_md(claude_home: Path, state_dir: Path) -> None:
    parts_dir = claude_home / PARTS_DIR
    missing = [p for p in CLAUDE_PARTS if not (parts_dir / p).is_file()]
    if missing:
        raise ExportError(f"missing CLAUDE parts in {parts_dir}: {', '.join(missing)}")

    target = claude_home / "CLAUDE.md"
    hash_file = state_dir / HASH_NAME
    current = target.read_text(encoding="utf-8") if target.exists() else None
    if current is not None:
        if hash_file.exists():
            if content_hash(current) != hash_file.read_text().strip():
                raise ExportError(
                    "CLAUDE.md edited directly; move the changes into "
                    f"{parts_dir}/CLAUDE.*.md, then re-run sync"
                )
        else:
            backup = state_dir / "backup" / _timestamp()
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup / "CLAUDE.md")

    read = lambda name: (parts_dir / name).read_text(encoding="utf-8")
    composed = compose(read("CLAUDE.base.md"), read(target_overlay_name("windows")))
    target.write_text(composed, encoding="utf-8", newline="\n")
    hash_file.write_text(content_hash(composed) + "\n")


def _mirror_dir(src: Path, dst: Path, exclude=frozenset()) -> None:
    """Make dst an exact copy of src; follows symlinks so linked skills ship real files."""
    if dst.exists():
        shutil.rmtree(dst)
    if not src.is_dir():
        return
    dst.mkdir(parents=True)
    for entry in sorted(src.iterdir()):
        if entry.name in exclude:
            continue
        if entry.is_dir():
            shutil.copytree(entry, dst / entry.name, symlinks=False)
        else:
            shutil.copy2(entry, dst / entry.name)


def export(claude_home: Path, claude_json: Path, repo: Path, state_dir: Path) -> None:
    if not acquire_lock(state_dir):
        raise SyncBusy("another sync is running")
    try:
        _compose_claude_md(claude_home, state_dir)
        for name in CLAUDE_PARTS:
            shutil.copy2(claude_home / PARTS_DIR / name, repo / name)
        for name in MIRRORED_DIRS:
            exclude = EXCLUDED_SKILLS if name == "skills" else frozenset()
            _mirror_dir(claude_home / name, repo / name, exclude)

        settings = _read_json(claude_home / "settings.json")
        known = _read_json(claude_home / "plugins" / "known_marketplaces.json")
        try:
            _write_json(repo / "plugins.json", build_plugins(settings, known))
        except ValueError as exc:
            raise ExportError(str(exc)) from exc
        _write_json(repo / "mcp.json", redact(_read_json(claude_json).get("mcpServers", {})))

        findings = scan(repo, repo / ".secretscan-allow")
        if findings:
            listed = "; ".join(f"{f.path}:{f.line}" for f in findings)
            raise ExportError(f"possible secrets found, nothing committed: {listed}")
    finally:
        release_lock(state_dir)
