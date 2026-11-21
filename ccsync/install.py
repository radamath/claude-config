"""Linux side: apply the repo to ~/.claude on a target (vps or cloud)."""
import filecmp
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ccsync import manifest
from ccsync.compose import compose, target_overlay_name
from ccsync.mcp import expand, load_env_file, strip_windows_wrapper

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


CLAUDE = "claude"


def _excluded(targets_cfg: dict, target: str, key: str) -> set:
    return set(targets_cfg.get(target, {}).get(key, []))


def _list_json(run, args: list) -> list:
    result = run([CLAUDE] + args)
    if result.returncode != 0:
        raise RuntimeError(f"`claude {' '.join(args)}` failed: {result.stderr.strip()}")
    return json.loads(result.stdout or "[]")


def _marketplace_ref(source: dict) -> str:
    return source.get("repo") or source.get("url") or source.get("path") or ""


def install_plugins(plugins_cfg: dict, target: str, targets_cfg: dict, data: dict, run) -> list:
    """Mirror the repo's plugin list; only uninstalls plugins this tool installed. Returns errors."""
    errors = []
    installed = {p["id"] for p in _list_json(run, ["plugin", "list", "--json"])}
    markets = {m["name"] for m in _list_json(run, ["plugin", "marketplace", "list", "--json"])}
    wanted = [p for p in plugins_cfg.get("plugins", []) if p not in _excluded(targets_cfg, target, "exclude_plugins")]
    owned = set(data.get("plugins", []))
    now_owned = set()

    for pid in wanted:
        if pid in installed:
            now_owned.add(pid)
            continue
        market = pid.partition("@")[2]
        source = plugins_cfg.get("marketplaces", {}).get(market)
        if source and market not in markets:
            result = run([CLAUDE, "plugin", "marketplace", "add", _marketplace_ref(source)])
            if result.returncode != 0:
                errors.append(f"marketplace {market}: {result.stderr.strip()}")
                continue
            markets.add(market)
        result = run([CLAUDE, "plugin", "install", pid, "--scope", "user"])
        if result.returncode != 0:
            errors.append(f"plugin {pid}: {result.stderr.strip()}")
            continue
        now_owned.add(pid)

    for pid in sorted(owned - set(wanted)):
        if pid in installed:
            result = run([CLAUDE, "plugin", "uninstall", pid, "--scope", "user"])
            if result.returncode != 0:
                errors.append(f"uninstall {pid}: {result.stderr.strip()}")
                now_owned.add(pid)

    data["plugins"] = sorted(now_owned)
    return errors


def _config_hash(server: dict) -> str:
    return hashlib.sha256(json.dumps(server, sort_keys=True).encode("utf-8")).hexdigest()


def install_mcps(mcp_cfg: dict, env: dict, target: str, targets_cfg: dict, data: dict, run) -> list:
    """Mirror user-scope MCP servers. Returns names skipped for missing secrets."""
    skipped = []
    owned = dict(data.get("mcps", {}))
    wanted = {n: s for n, s in mcp_cfg.items() if n not in _excluded(targets_cfg, target, "exclude_mcps")}

    for name, server in sorted(wanted.items()):
        resolved = expand(strip_windows_wrapper(server), env)
        if resolved is None:
            skipped.append(name)
            continue
        digest = _config_hash(resolved)
        if owned.get(name) == digest:
            continue
        run([CLAUDE, "mcp", "remove", "-s", "user", name])
        # Config goes through stdin so secrets never appear in the process list.
        result = run([CLAUDE, "mcp", "add-json", "-s", "user", name, "-"], input=json.dumps(resolved))
        if result.returncode == 0:
            owned[name] = digest
        else:
            skipped.append(name)

    for name in sorted(set(owned) - set(wanted)):
        run([CLAUDE, "mcp", "remove", "-s", "user", name])
        del owned[name]

    data["mcps"] = owned
    return skipped


def _subprocess_runner(args: list, input=None):
    return subprocess.run(args, input=input, capture_output=True, text=True, check=False)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def run_install(repo: Path, home: Path, target: str, run=_subprocess_runner) -> list:
    """Apply files, plugins and MCPs. Returns human-readable problems (empty = clean run)."""
    claude_home, state_dir = home / ".claude", home / ".claude-config"
    targets_cfg = _read_json(repo / "targets.json")
    data = install_files(repo, claude_home, state_dir, target, targets_cfg)

    problems = install_plugins(_read_json(repo / "plugins.json"), target, targets_cfg, data, run)
    env = {**os.environ, **load_env_file(state_dir / "secrets.env")}
    skipped = install_mcps(_read_json(repo / "mcp.json"), env, target, targets_cfg, data, run)
    problems += [f"mcp {n} skipped: missing secret(s) in ~/.claude-config/secrets.env" for n in skipped]

    manifest.save(claude_home / manifest.MANIFEST_NAME, data)
    return problems
