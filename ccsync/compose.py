"""Build a target's CLAUDE.md from the shared base and a per-platform overlay."""
import hashlib

OVERLAY_BY_TARGET = {
    "windows": "CLAUDE.windows.md",
    "linux": "CLAUDE.linux.md",
    "vps": "CLAUDE.linux.md",
    "cloud": "CLAUDE.linux.md",
}


def target_overlay_name(target: str) -> str:
    try:
        return OVERLAY_BY_TARGET[target]
    except KeyError:
        raise ValueError(f"unknown target: {target!r}") from None


def compose(base: str, overlay: str) -> str:
    parts = [p.strip("\r\n") for p in (base, overlay) if p.strip()]
    return "\n\n".join(parts) + "\n"


def content_hash(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
