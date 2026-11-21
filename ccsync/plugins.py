"""Derive a portable plugin list from Windows Claude Code settings."""

# Built into Claude Code; never needs `marketplace add` on a target.
BUILTIN_MARKETPLACES = {"claude-plugins-official"}


def _marketplace_source(name: str, settings: dict, known: dict) -> dict:
    extra = settings.get("extraKnownMarketplaces", {})
    for table in (extra, known):
        entry = table.get(name)
        if entry and "source" in entry:
            return dict(entry["source"])
    raise ValueError(f"no source known for marketplace {name!r}")


def build_plugins(settings: dict, known_marketplaces: dict) -> dict:
    plugins = sorted(pid for pid, on in settings.get("enabledPlugins", {}).items() if on is True)
    marketplaces = {}
    for pid in plugins:
        _, _, market = pid.partition("@")
        if market in BUILTIN_MARKETPLACES or market in marketplaces:
            continue
        marketplaces[market] = _marketplace_source(market, settings, known_marketplaces)
    return {"marketplaces": marketplaces, "plugins": plugins}
