"""Status pills and theme cards."""

from __future__ import annotations

from collections.abc import Callable

from gi.repository import Gtk

from ...core.components import ComponentInfo
from ...core.theme import Theme
from . import dyncss

STATUS_ICONS = {"installed": "ht-check-symbolic", "missing": "ht-warning-symbolic", "error": "ht-error-symbolic"}


class StatusPill(Gtk.Box):
    def __init__(self, label: str, status: str = "missing", detail: str = ""):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.add_css_class("ht-pill")
        self.icon = Gtk.Image.new_from_icon_name(STATUS_ICONS.get(status, "ht-warning-symbolic"))
        self.label = Gtk.Label(label=label)
        self.append(self.icon)
        self.append(self.label)
        self.set_status(status, detail)

    def set_status(self, status: str, detail: str = "") -> None:
        for cls in ("installed", "missing", "error", "off"):
            self.remove_css_class(cls)
        self.add_css_class(status if status in ("installed", "missing", "error") else "off")
        self.icon.set_from_icon_name(STATUS_ICONS.get(status, "ht-warning-symbolic"))
        if detail:
            self.set_tooltip_text(detail)

    def set_from_info(self, info: ComponentInfo, mode: str | None = None) -> None:
        text = info.status_label
        if mode == "off":
            text += " · off"
        self.set_status(info.status if mode != "off" else "off", f"{info.label}: {text}\n{info.message or info.path or ''}".strip())
        self.label.set_text(info.label)


class Swatches(Gtk.Box):
    """A row of colour swatches summarising a theme."""

    def __init__(
        self, theme: Theme, keys: tuple[str, ...] = ("primary", "secondary", "highlight", "surface", "background"), size: int = 18
    ):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.size = size
        self.keys = keys
        self._boxes: list[Gtk.Box] = []
        for _ in keys:
            b = Gtk.Box()
            b.set_size_request(size, size)
            b.add_css_class("ht-swatch")
            self._boxes.append(b)
            self.append(b)
        self.update(theme)

    def update(self, theme: Theme) -> None:
        for box, key in zip(self._boxes, self.keys, strict=True):
            color = theme.colors.get(key, "#000000")
            for cls in list(box.get_css_classes()):
                if cls.startswith("ht-bg-"):
                    box.remove_css_class(cls)
            box.add_css_class(dyncss.bg_class(color))


class ThemeCard(Gtk.Button):
    def __init__(self, theme: Theme, kind: str, *, applied: bool, selected: bool, on_select: Callable[[], None]):
        super().__init__()
        self.theme_id = theme.id
        self.add_css_class("ht-theme-card")
        if selected:
            self.add_css_class("selected")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Preview strip: gradient + mini "bar" and "window" drawn with CSS.
        strip = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        strip.set_size_request(-1, 86)
        c = theme.colors
        scope = dyncss.safe_class("ht-tc-", f"{theme.id}-{theme.fingerprint()}")
        self.add_css_class(scope)
        css = f"""
        .{scope} box.strip {{
          background: linear-gradient(135deg, {c["background"]} 0%, {c["surface"]} 55%, {c["gradient_end"]} 160%);
          border-radius: 15px 15px 0 0;
          padding: 10px;
        }}
        .{scope} box.mini-bar {{
          background: alpha({c["surface"]}, 0.9);
          border: 1px solid alpha({c["border"]}, 0.7);
          border-radius: {max(3, theme.effects["radius"] // 2)}px;
          min-height: 10px;
          box-shadow: 0 0 8px alpha({c["glow"]}, {0.5 if theme.effects["neon_glow"] else 0});
        }}
        .{scope} box.mini-win {{
          background: alpha({c["surface2"]}, 0.9);
          border: 1px solid {c["active_border"]};
          border-radius: {max(3, theme.effects["radius"] // 2)}px;
          min-height: 34px;
        }}
        .{scope} box.mini-win2 {{
          background: alpha({c["surface"]}, 0.9);
          border: 1px solid alpha({c["inactive_border"]}, 0.9);
          border-radius: {max(3, theme.effects["radius"] // 2)}px;
          min-height: 34px;
        }}
        .{scope} box.mini-dot {{ background: {c["workspace_active"]}; border-radius: 99px; min-width: 6px; min-height: 6px; margin: 2px; }}
        .{scope} box.mini-dot2 {{ background: {c["workspace_inactive"]}; border-radius: 99px; min-width: 6px; min-height: 6px; margin: 2px; }}
        """
        dyncss.set_rules(scope, css)
        strip.add_css_class("strip")
        bar = Gtk.Box(spacing=4)
        bar.add_css_class("mini-bar")
        for cls in ("mini-dot", "mini-dot2", "mini-dot2"):
            dot = Gtk.Box(valign=Gtk.Align.CENTER)
            dot.add_css_class(cls)
            bar.append(dot)
        strip.append(bar)
        wins = Gtk.Box(spacing=6, margin_top=6)
        for cls in ("mini-win", "mini-win2"):
            w = Gtk.Box(hexpand=True)
            w.add_css_class(cls)
            wins.append(w)
        strip.append(wins)
        box.append(strip)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_top=10, margin_bottom=12, margin_start=12, margin_end=12)
        top = Gtk.Box(spacing=6)
        name = Gtk.Label(label=theme.name, xalign=0, hexpand=True)
        name.add_css_class("ht-theme-card-name")
        name.set_ellipsize(3)
        top.append(name)
        if applied:
            badge = Gtk.Label(label="APPLIED")
            badge.add_css_class("ht-theme-card-badge")
            badge.add_css_class("applied")
            top.append(badge)
        badge = Gtk.Label(label="PRESET" if kind == "preset" else "CUSTOM")
        badge.add_css_class("ht-theme-card-badge")
        top.append(badge)
        body.append(top)
        desc = Gtk.Label(label=theme.description or " ", xalign=0)
        desc.add_css_class("ht-theme-card-desc")
        desc.set_ellipsize(3)
        body.append(desc)
        bottom = Gtk.Box(spacing=8, margin_top=4)
        bottom.append(Swatches(theme, size=14))
        hexl = Gtk.Label(label=theme.colors["primary"], xalign=1, hexpand=True)
        hexl.add_css_class("ht-theme-card-desc")
        hexl.add_css_class("ht-mono")
        bottom.append(hexl)
        body.append(bottom)
        box.append(body)
        self.set_child(box)
        self.connect("clicked", lambda *_: on_select())
