"""One shared CSS provider for per-widget dynamic rules (swatches, theme cards).

GTK 4.10 deprecated per-widget style providers, so widgets instead get a
unique CSS class and register their rules here; the provider is reloaded
whenever a new rule set appears.
"""

from __future__ import annotations

import re

from gi.repository import Gdk, Gtk

_rules: dict[str, str] = {}
_provider: Gtk.CssProvider | None = None


def _ensure_provider() -> Gtk.CssProvider:
    global _provider
    if _provider is None:
        _provider = Gtk.CssProvider()
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(display, _provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
    return _provider


def _reload() -> None:
    _ensure_provider().load_from_string("\n".join(_rules.values()))


def set_rules(key: str, css: str) -> None:
    """Register (or replace) a block of CSS identified by ``key``."""
    if _rules.get(key) == css:
        return
    _rules[key] = css
    _reload()


def bg_class(color: str) -> str:
    """Return a CSS class whose background is ``color`` (``#RRGGBB``)."""
    slug = re.sub(r"[^0-9a-fA-F]", "", color).lower()
    cls = f"ht-bg-{slug}"
    if cls not in _rules:
        _rules[cls] = f".{cls} {{ background: #{slug}; }}"
        _reload()
    return cls


def safe_class(prefix: str, raw: str) -> str:
    return prefix + re.sub(r"[^a-zA-Z0-9_-]", "-", raw)
