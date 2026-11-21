"""Shared test helpers."""
import tempfile
from pathlib import Path


def make_tree(files: dict) -> Path:
    """Create a temp dir with {relpath: str|bytes} files and return its path."""
    root = Path(tempfile.mkdtemp(prefix="ccsync-test-"))
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8", newline="")
    return root
