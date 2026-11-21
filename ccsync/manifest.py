"""Record of what ccsync installed on a target, so it only ever touches its own items."""
import json
from pathlib import Path

MANIFEST_NAME = ".claude-config-manifest"


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    # files: relpaths under ~/.claude; hashes: relpath -> content hash as installed (detects local edits);
    # plugins: plugin ids; mcps: server name -> config hash
    return {
        "files": data.get("files", []),
        "hashes": data.get("hashes", {}),
        "plugins": data.get("plugins", []),
        "mcps": data.get("mcps", {}),
    }


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
