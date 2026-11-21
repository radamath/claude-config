"""Last-run status file, so silent background syncs can surface failures later."""
import json
from datetime import datetime, timezone
from pathlib import Path


def write(path: Path, ok: bool, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"ok": ok, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "message": message}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def notice(path: Path):
    """One-line warning if the last run failed, else None."""
    data = read(path)
    if not data or data.get("ok"):
        return None
    first_line = (data.get("message") or "unknown error").splitlines()[0]
    return f"claude-config sync failed at {data.get('at')}: {first_line} (see ~/.claude-config/sync.log)"
