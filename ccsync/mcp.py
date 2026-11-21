"""Keep MCP secrets out of the repo: redact on export, expand on install."""
import copy
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

DICT_SECRET_FIELDS = ("env", "headers")
PLACEHOLDER = re.compile(r"\$\{([A-Z0-9_]+)\}")
# CLI flags whose value is treated as secret, e.g. --api-key X or --token=X.
SECRET_FLAG = re.compile(r"^--?([A-Za-z0-9_-]*(?:key|token|secret|password|auth)[A-Za-z0-9_-]*)$", re.IGNORECASE)


def _var_name(*parts: str) -> str:
    return "MCP_" + re.sub(r"[^A-Z0-9]", "_", "_".join(parts).upper())


def _ph(*parts: str) -> str:
    return "${" + _var_name(*parts) + "}"


def _redact_args(name: str, args: list) -> list:
    out, hide_next = [], None
    for arg in args:
        if hide_next:
            out.append(_ph(name, "ARG", hide_next))
            hide_next = None
            continue
        flag, sep, _ = arg.partition("=")
        match = SECRET_FLAG.match(flag)
        if match and sep:
            out.append(f"{flag}={_ph(name, 'ARG', match.group(1))}")
        else:
            if match:
                hide_next = match.group(1)
            out.append(arg)
    return out


def _redact_url(name: str, url: str) -> str:
    parts = urlsplit(url)
    netloc = parts.netloc
    if "@" in netloc:
        netloc = _ph(name, "URL", "USERINFO") + "@" + netloc.rpartition("@")[2]
    query = "&".join(
        f"{key}={_ph(name, 'URL', key)}" if sep else key
        for key, sep, _ in (pair.partition("=") for pair in parts.query.split("&") if pair)
    )
    return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))


def redact(servers: dict) -> dict:
    out = copy.deepcopy(servers)
    for name, server in out.items():
        for field in DICT_SECRET_FIELDS:
            if server.get(field):
                server[field] = {k: _ph(name, k) for k in server[field]}
        if server.get("args"):
            server["args"] = _redact_args(name, server["args"])
        if server.get("url"):
            server["url"] = _redact_url(name, server["url"])
    return out


def _fill(value: str, env: dict):
    if any(v not in env for v in PLACEHOLDER.findall(value)):
        return None
    return PLACEHOLDER.sub(lambda m: env[m.group(1)], value)


def expand(server: dict, env: dict):
    """Fill placeholders; return None if any variable is missing (never install half-configured)."""
    out = copy.deepcopy(server)
    for field in DICT_SECRET_FIELDS:
        for key, value in out.get(field, {}).items():
            filled = _fill(value, env)
            if filled is None:
                return None
            out[field][key] = filled
    if "args" in out:
        filled_args = [_fill(a, env) for a in out["args"]]
        if None in filled_args:
            return None
        out["args"] = filled_args
    if "url" in out:
        out["url"] = _fill(out["url"], env)
        if out["url"] is None:
            return None
    return out


def strip_windows_wrapper(server: dict) -> dict:
    args = server.get("args", [])
    if server.get("command", "").lower() == "cmd" and len(args) >= 2 and args[0].lower() == "/c":
        out = dict(server)
        out["command"], out["args"] = args[1], list(args[2:])
        return out
    return server


def load_env_file(path: Path) -> dict:
    """Parse KEY=value lines literally (no shell expansion)."""
    if not path.exists():
        return {}
    env = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env
