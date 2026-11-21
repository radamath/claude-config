"""Keep MCP secrets out of the repo: redact on export, expand on install."""
import copy
import re
from pathlib import Path

SECRET_FIELDS = ("env", "headers")
PLACEHOLDER = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _var_name(server: str, key: str) -> str:
    return "MCP_" + re.sub(r"[^A-Z0-9]", "_", f"{server}_{key}".upper())


def redact(servers: dict) -> dict:
    out = copy.deepcopy(servers)
    for name, server in out.items():
        for field in SECRET_FIELDS:
            values = server.get(field)
            if values:
                server[field] = {k: "${" + _var_name(name, k) + "}" for k in values}
    return out


def expand(server: dict, env: dict):
    """Fill placeholders; return None if any variable is missing (never install half-configured)."""
    out = copy.deepcopy(server)
    for field in SECRET_FIELDS:
        for key, value in out.get(field, {}).items():
            missing = [v for v in PLACEHOLDER.findall(value) if v not in env]
            if missing:
                return None
            out[field][key] = PLACEHOLDER.sub(lambda m: env[m.group(1)], value)
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
