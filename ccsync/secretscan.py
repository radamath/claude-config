"""Fail-closed secret scanner for the exported config tree."""
import fnmatch
import re
from pathlib import Path
from typing import NamedTuple


class Finding(NamedTuple):
    path: str
    line: int
    pattern: str


CONTENT_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36}"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"xox[abposr]-[A-Za-z0-9-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"CLAUDE_CODE_OAUTH_TOKEN\s*=\s*\S+"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)['\"]?\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    # Secrets in URL query strings and URL userinfo (scheme://user:pass@host).
    re.compile(r"(?i)[?&][a-z0-9_-]*(key|token|secret|password|sig)[a-z0-9_-]*=[^&\s$]{8,}"),
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@$]+:[^/\s@$]+@"),
]

# Filenames that must never be committed, regardless of content.
FORBIDDEN_NAME_GLOBS = [".env", ".env.*", "*.env", "credentials.json", ".credentials.json", "*.pem", "id_rsa*", "id_ed25519*"]

SKIP_DIRS = {".git", ".superpowers", "__pycache__"}


def _load_allowlist(allow_file: Path) -> list:
    """Parse `<path-glob> <regex>  # reason` lines."""
    rules = []
    if not allow_file.exists():
        return rules
    for raw in allow_file.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        path_glob, _, regex = line.partition(" ")
        rules.append((path_glob, re.compile(regex.strip())))
    return rules


def _allowed(rel: str, text: str, rules: list) -> bool:
    return any(fnmatch.fnmatch(rel, g) and rx.search(text) for g, rx in rules)


def _iter_files(root: Path, include=None):
    bases = [root / name for name in include] if include is not None else [root]
    for base in bases:
        candidates = [base] if base.is_file() else sorted(base.rglob("*")) if base.is_dir() else []
        for p in candidates:
            if p.is_file() and not SKIP_DIRS.intersection(p.relative_to(root).parts):
                yield p


def scan(root: Path, allow_file: Path, include=None) -> list:
    """Scan `root` (or only the `include` paths relative to it) for likely secrets."""
    rules = _load_allowlist(allow_file)
    findings = []
    for path in _iter_files(root, include):
        rel = path.relative_to(root).as_posix()
        if path == allow_file:
            continue
        if any(fnmatch.fnmatch(path.name, g) for g in FORBIDDEN_NAME_GLOBS):
            findings.append(Finding(rel, 0, "forbidden-filename"))
            continue
        text = path.read_bytes().decode("utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for rx in CONTENT_PATTERNS:
                match = rx.search(line)
                if match and not _allowed(rel, match.group(0), rules):
                    findings.append(Finding(rel, lineno, rx.pattern))
                    break
    return findings
