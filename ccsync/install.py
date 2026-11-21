"""Linux side: apply the repo to ~/.claude on a target (vps or cloud)."""
import filecmp
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ccsync import manifest
from ccsync.compose import compose, target_overlay_name

CLAUDE_MD = "CLAUDE.md"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _desired_items(repo: Path, excludes: dict) -> list:
    """Relpaths (under ~/.claude) the repo wants installed on this target."""
    items = []
    skills = repo / "skills"
    if skills.is_dir():
        skip = set(excludes.get("exclude_skills", []))
        items += [f"skills/{p.name}" for p in skills.iterdir() if p.is_dir() and p.name not in skip]
    agents = repo / "agents"
    if agents.is_dir():
        skip = set(excludes.get("exclude_agents", []))
        items += [f"agents/{p.name}" for p in agents.iterdir() if p.is_file() and p.stem not in skip]
    commands = repo / "commands"
    if commands.is_dir():
        items += [f"commands/{p.name}" for p in commands.iterdir() if p.is_file()]
    return sorted(items)


def _same_tree(a: Path, b: Path) -> bool:
    if a.is_file() or b.is_file():
        return a.is_file() and b.is_file() and filecmp.cmp(a, b, shallow=False)
    cmp = filecmp.dircmp(a, b)
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(a, b, cmp.common_files, shallow=False)
    if mismatch or errors:
        return False
    return all(_same_tree(a / d, b / d) for d in cmp.common_dirs)


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def _backup(path: Path, rel: str, backup_root: Path) -> None:
    dest = backup_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dest))


def _install_claude_md(repo: Path, claude_home: Path, target: str, owned: set, backup_root: Path) -> None:
    base = (repo / "CLAUDE.base.md").read_text(encoding="utf-8")
    overlay_path = repo / target_overlay_name(target)
    overlay = overlay_path.read_text(encoding="utf-8") if overlay_path.exists() else ""
    composed = compose(base, overlay)
    dst = claude_home / CLAUDE_MD
    if dst.exists():
        if dst.read_text(encoding="utf-8") == composed:
            return
        if CLAUDE_MD not in owned:
            _backup(dst, CLAUDE_MD, backup_root)
    dst.write_text(composed, encoding="utf-8", newline="\n")


def install_files(repo: Path, claude_home: Path, state_dir: Path, target: str, targets_cfg: dict) -> dict:
    manifest_path = claude_home / manifest.MANIFEST_NAME
    data = manifest.load(manifest_path)
    owned = set(data["files"])
    backup_root = state_dir / "backup" / _timestamp()
    desired = _desired_items(repo, targets_cfg.get(target, {}))

    _install_claude_md(repo, claude_home, target, owned, backup_root)

    for rel in desired:
        src, dst = repo / rel, claude_home / rel
        if dst.exists() or dst.is_symlink():
            if rel not in owned:
                _backup(dst, rel, backup_root)
            elif _same_tree(src, dst):
                continue
            else:
                _remove(dst)
        _copy(src, dst)

    for rel in sorted(owned - set(desired) - {CLAUDE_MD}):
        _remove(claude_home / rel)

    data["files"] = sorted([CLAUDE_MD] + desired)
    manifest.save(manifest_path, data)
    return data
