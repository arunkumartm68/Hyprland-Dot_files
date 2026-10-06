"""Components: detection status, per-component enable switches and options, fonts."""

from __future__ import annotations

from gi.repository import Gtk

from ...core.components import COMPONENT_SPECS
from ..components import button, card, label
from ..components.pills import StatusPill
from ..components.rows import DropdownRow, EntryRow, SliderRow, ToggleRow
from .base import EditorPage

THEMEABLE = ("hyprland", "waybar", "kitty", "rofi", "swaync", "hyprlock", "wlogout", "wallpaper")


class ComponentsPage(EditorPage):
    key = "components"
    title = "Components"
    subtitle = "What HyprTheme detected on this system, and per-component options stored in the theme."

    def build(self) -> None:
        editor, _side = self.split()
        self.rows: list = []
        self.pills: dict[str, StatusPill] = {}
        self.version_labels: dict[str, Gtk.Label] = {}

        det, dbody = card("Detected on this system")
        dbody.set_spacing(4)
        for key, lbl, _binary, desc, _req, _proc in COMPONENT_SPECS:
            row = Gtk.Box(spacing=10)
            pill = StatusPill(lbl, "missing", "detecting…")
            pill.set_size_request(130, -1)
            self.pills[key] = pill
            row.append(pill)
            row.append(label(desc, "ht-small", "ht-muted"))
            ver = label("", "ht-small", "ht-muted", "ht-mono", xalign=1)
            ver.set_hexpand(True)
            self.version_labels[key] = ver
            row.append(ver)
            dbody.append(row)
        dbody.append(button("RE-DETECT", "ht-reset-symbolic", on_click=self.state.refresh_components_async))
        editor.append(det)

        comps = self.state.working.components
        f = self.state.working.fonts

        c, body = card("Fonts")
        body.set_spacing(0)
        self._add(body, EntryRow("ui", "UI font", "Waybar, Rofi, SwayNC, Hyprlock", str(f.get("ui", "Inter")), self._on_font))
        self._add(body, EntryRow("mono", "Monospace font", "Terminal and bar fallbacks", str(f.get("mono", "")), self._on_font))
        self._add(body, SliderRow("size", "Base font size", 9, 18, 1, "px", float(f.get("size", 13)), self._on_font))
        editor.append(c)

        c, body = card("Hyprland")
        body.set_spacing(0)
        self._add(
            body,
            ToggleRow(
                "hyprland.enabled",
                "Theme Hyprland",
                "Borders, blur, rounding, gaps, shadows, animations",
                comps["hyprland"].get("enabled", True),
                self._on_comp,
            ),
        )
        self._add(
            body,
            ToggleRow(
                "hyprland.apply_opacity_to_windows",
                "Apply transparency to windows",
                "Use the Transparency slider for active_opacity / inactive_opacity",
                comps["hyprland"].get("apply_opacity_to_windows", False),
                self._on_comp,
            ),
        )
        editor.append(c)

        w = comps["waybar"]
        c, body = card("Waybar")
        body.set_spacing(0)
        self._add(body, ToggleRow("waybar.enabled", "Theme Waybar", None, w.get("enabled", True), self._on_comp))
        self._add(
            body,
            DropdownRow(
                "waybar.position", "Position", None, [("top", "Top"), ("bottom", "Bottom")], str(w.get("position", "top")), self._on_comp
            ),
        )
        self._add(body, SliderRow("waybar.height", "Bar height", 24, 56, 1, "px", float(w.get("height", 36)), self._on_comp))
        self._add(
            body,
            ToggleRow(
                "waybar.floating", "Floating bar", "Margins around the bar (uses Window Gaps)", w.get("floating", True), self._on_comp
            ),
        )
        self._add(body, ToggleRow("waybar.show_launcher", "Launcher button", None, w.get("show_launcher", True), self._on_comp))
        self._add(body, ToggleRow("waybar.show_music", "Music (mpris)", None, w.get("show_music", True), self._on_comp))
        self._add(body, ToggleRow("waybar.show_bluetooth", "Bluetooth", None, w.get("show_bluetooth", True), self._on_comp))
        self._add(
            body,
            ToggleRow(
                "waybar.show_notifications", "Notification bell", "Needs swaync-client", w.get("show_notifications", True), self._on_comp
            ),
        )
        self._add(
            body,
            ToggleRow("waybar.show_system", "System statistics", "CPU, memory, temperature", w.get("show_system", True), self._on_comp),
        )
        self._add(
            body,
            EntryRow(
                "waybar.launcher_command",
                "Launcher command",
                None,
                str(w.get("launcher_command", "rofi -show drun")),
                self._on_comp,
                width_chars=22,
            ),
        )
        self._add(
            body,
            EntryRow(
                "waybar.clock_format",
                "Clock format",
                "strftime format",
                str(w.get("clock_format", "%a %d %b  %I:%M %p")),
                self._on_comp,
                width_chars=22,
            ),
        )
        editor.append(c)

        k = comps["kitty"]
        c, body = card("Kitty")
        body.set_spacing(0)
        self._add(
            body,
            ToggleRow(
                "kitty.enabled", "Theme Kitty", "Colors, ANSI palette, tabs, opacity, padding", k.get("enabled", True), self._on_comp
            ),
        )
        self._add(body, SliderRow("kitty.font_size", "Font size", 8, 20, 0.5, "pt", float(k.get("font_size", 11)), self._on_comp))
        self._add(
            body,
            DropdownRow(
                "kitty.cursor_shape",
                "Cursor shape",
                None,
                [("beam", "Beam"), ("block", "Block"), ("underline", "Underline")],
                str(k.get("cursor_shape", "beam")),
                self._on_comp,
            ),
        )
        editor.append(c)

        r = comps["rofi"]
        c, body = card("Rofi")
        body.set_spacing(0)
        self._add(body, ToggleRow("rofi.enabled", "Theme Rofi", "Centered glass launcher", r.get("enabled", True), self._on_comp))
        self._add(body, SliderRow("rofi.width", "Width", 400, 1000, 10, "px", float(r.get("width", 640)), self._on_comp))
        self._add(body, SliderRow("rofi.lines", "Lines", 4, 14, 1, "", float(r.get("lines", 8)), self._on_comp))
        self._add(body, SliderRow("rofi.columns", "Columns", 1, 3, 1, "", float(r.get("columns", 1)), self._on_comp))
        self._add(body, ToggleRow("rofi.show_icons", "Show icons", None, r.get("show_icons", True), self._on_comp))
        self._add(body, EntryRow("rofi.icon_theme", "Icon theme", None, str(r.get("icon_theme", "Papirus-Dark")), self._on_comp))
        self._add(body, EntryRow("rofi.prompt", "Placeholder", None, str(r.get("prompt", "Search")), self._on_comp))
        editor.append(c)

        s = comps["swaync"]
        c, body = card("SwayNC")
        body.set_spacing(0)
        self._add(
            body, ToggleRow("swaync.enabled", "Theme SwayNC", "Notifications and control center", s.get("enabled", True), self._on_comp)
        )
        self._add(body, SliderRow("swaync.width", "Width", 300, 600, 10, "px", float(s.get("width", 420)), self._on_comp))
        self._add(
            body,
            ToggleRow(
                "swaync.manage_config",
                "Manage config.json",
                "Off: only write config.json when none exists (keeps your widgets)",
                s.get("manage_config", True),
                self._on_comp,
            ),
        )
        editor.append(c)

        h = comps["hyprlock"]
        c, body = card("Hyprlock")
        body.set_spacing(0)
        self._add(
            body,
            ToggleRow(
                "hyprlock.enabled",
                "Theme Hyprlock",
                "Clock, date, password field, user, battery, wallpaper",
                h.get("enabled", True),
                self._on_comp,
            ),
        )
        self._add(body, ToggleRow("hyprlock.clock_24h", "24-hour clock", None, h.get("clock_24h", False), self._on_comp))
        self._add(body, ToggleRow("hyprlock.show_user", "Show user name", None, h.get("show_user", True), self._on_comp))
        self._add(
            body,
            ToggleRow(
                "hyprlock.show_battery",
                "Show battery",
                "Hidden automatically when no battery exists",
                h.get("show_battery", True),
                self._on_comp,
            ),
        )
        self._add(body, ToggleRow("hyprlock.show_music", "Show now playing", "Needs playerctl", h.get("show_music", False), self._on_comp))
        self._add(
            body, SliderRow("hyprlock.blur_passes", "Background blur passes", 0, 4, 1, "", float(h.get("blur_passes", 2)), self._on_comp)
        )
        editor.append(c)

        wl = comps["wlogout"]
        c, body = card("Wlogout")
        body.set_spacing(0)
        self._add(
            body,
            ToggleRow("wlogout.enabled", "Theme Wlogout", "Lock, Logout, Sleep, Restart, Shutdown", wl.get("enabled", True), self._on_comp),
        )
        self._add(
            body, SliderRow("wlogout.button_size", "Button size", 100, 240, 10, "px", float(wl.get("button_size", 150)), self._on_comp)
        )
        self._add(body, EntryRow("wlogout.lock_command", "Lock command", None, str(wl.get("lock_command", "hyprlock")), self._on_comp))
        editor.append(c)

        c, body = card("Wallpaper")
        body.set_spacing(0)
        self._add(
            body,
            ToggleRow(
                "wallpaper.enabled",
                "Manage wallpaper",
                "Set the theme wallpaper on apply and restore it at login",
                comps["wallpaper"].get("enabled", True),
                self._on_comp,
            ),
        )
        editor.append(c)
        self.on_components_changed()

    def _add(self, body: Gtk.Box, row) -> None:
        self.rows.append(row)
        body.append(row)

    def _on_comp(self, key: str, value) -> None:
        comp, opt = key.split(".", 1)
        self.state.set_component(comp, opt, value)

    def _on_font(self, key: str, value) -> None:
        self.state.set_font(key, int(value) if key == "size" else value)

    def on_components_changed(self) -> None:
        for key, pill in self.pills.items():
            info = self.state.components.get(key)
            if info:
                mode = self.state.settings.integration(key) if key in THEMEABLE[:-1] else None
                pill.set_from_info(info, mode)
                self.version_labels[key].set_text(info.version or (info.path or ""))

    def on_theme_changed(self, what: str) -> None:
        super().on_theme_changed(what)
        if what != "theme":
            return
        comps = self.state.working.components
        fonts = self.state.working.fonts
        for row in self.rows:
            key = row.key
            if "." in key:
                comp, opt = key.split(".", 1)
                value = comps.get(comp, {}).get(opt)
            else:
                value = fonts.get(key)
            if value is None:
                continue
            if isinstance(row, SliderRow):
                row.set_value(float(value))
            elif isinstance(row, ToggleRow):
                row.set_value(bool(value))
            else:
                row.set_value(str(value))
