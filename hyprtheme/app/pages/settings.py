"""Settings: integration modes, wallpaper backend, reload behaviour, backups, about."""

from __future__ import annotations

import subprocess

from gi.repository import Gtk

from ... import __version__
from ...core import paths
from ...core.settings import INTEGRATION_MODES
from ..components import button, card, label
from ..components.rows import DropdownRow, SliderRow, ToggleRow
from .base import Page

MODE_LABELS = {
    "managed": "Managed — HyprTheme writes the full config",
    "variables": "Variables only — I include the colours myself",
    "off": "Off — never touch this component",
}
COMPONENTS = [
    (
        "hyprland",
        "Hyprland",
        "Managed: adds one source= line to hyprland.conf (or a require() to hyprland.lua). Your config is never rewritten.",
    ),
    ("waybar", "Waybar", "Managed: style.css + config.jsonc. Variables: only hyprtheme-colors.css."),
    ("kitty", "Kitty", "Managed: adds one include line to kitty.conf. Variables: only hyprtheme.conf is written."),
    ("rofi", "Rofi", "Managed: adds an @theme line to config.rasi. Variables: only hyprtheme.rasi is written."),
    ("swaync", "SwayNC", "Managed: style.css (+ config.json). Variables: only hyprtheme-colors.css."),
    ("hyprlock", "Hyprlock", "Managed: hyprlock.conf. Variables: only hyprlock-hyprtheme.conf ($ht_* variables)."),
    ("wlogout", "Wlogout", "Managed: style.css + layout + icons. Variables: only hyprtheme-colors.css."),
]


class SettingsPage(Page):
    key = "settings"
    title = "Settings"
    subtitle = "How HyprTheme integrates with each component. Themes decide what things look like; settings decide what gets written."

    def build(self) -> None:
        s = self.state.settings
        c, body = card("Integration per component")
        body.set_spacing(0)
        for key, lbl, desc in COMPONENTS:
            body.append(DropdownRow(key, lbl, desc, [(m, MODE_LABELS[m]) for m in INTEGRATION_MODES], s.integration(key), self._on_mode))
        self.content.append(c)

        c, body = card("Behaviour")
        body.set_spacing(0)
        body.append(
            DropdownRow(
                "wallpaper_backend",
                "Wallpaper backend",
                "auto prefers swww, then hyprpaper",
                [("auto", "Auto"), ("swww", "swww"), ("hyprpaper", "hyprpaper"), ("off", "Off")],
                s.wallpaper_backend,
                self._on_setting,
            )
        )
        body.append(
            ToggleRow(
                "reload_on_apply",
                "Reload components on apply",
                "hyprctl reload, SIGUSR2 to Waybar, SIGUSR1 to Kitty, swaync-client reload",
                s.reload_on_apply,
                self._on_setting,
            )
        )
        body.append(
            SliderRow(
                "backup_limit",
                "Automatic backups to keep",
                3,
                100,
                1,
                "",
                float(s.backup_limit),
                self._on_setting,
                "Older apply snapshots are pruned; manual and original snapshots are kept",
            )
        )
        body.append(
            DropdownRow(
                "hyprland_syntax",
                "Hyprland rule syntax",
                "auto detects the running version (0.53+ uses match: rules)",
                [("auto", "Auto"), ("modern", "Modern (0.53+)"), ("legacy", "Legacy (< 0.53)"), ("lua", "Lua")],
                str(s.get("hyprland_syntax", "auto")),
                self._on_setting,
            )
        )
        body.append(
            DropdownRow(
                "hyprpaper_syntax",
                "hyprpaper config syntax",
                "auto detects the installed version (0.8+ uses wallpaper {} blocks)",
                [("auto", "Auto"), ("modern", "Modern (0.8+)"), ("legacy", "Legacy")],
                str(s.get("hyprpaper_syntax", "auto")),
                self._on_setting,
            )
        )
        self.content.append(c)

        c, body = card("Locations")
        for title, p in (
            ("Settings", paths.settings_file()),
            ("Themes", paths.user_themes_dir()),
            ("Wallpapers", paths.user_wallpapers_dir()),
            ("State & backups", paths.app_state_dir()),
            ("Templates", paths.templates_dir() or "not found"),
            ("Presets", paths.presets_dir() or "not found"),
        ):
            row = Gtk.Box(spacing=12)
            row.append(label(title, "ht-row-label"))
            v = label(paths.display_path(p), "ht-mono", "ht-small", "ht-muted", xalign=1)
            v.set_hexpand(True)
            v.set_selectable(True)
            row.append(v)
            body.append(row)
        body.append(button("OPEN CONFIG FOLDER", "ht-folder-symbolic", on_click=self._open_folder))
        self.content.append(c)

        c, body = card("About")
        body.append(label(f"HyprTheme {__version__} — Hyprland Theme Control Center", "ht-row-label"))
        body.append(
            label(
                "One theme definition drives Hyprland, Waybar, Kitty, Rofi, SwayNC, Hyprlock, Wlogout and the wallpaper daemon. The GUI and the `hyprtheme` CLI share the same engine.",
                "ht-muted",
                "ht-small",
                wrap=True,
            )
        )
        body.append(
            label(
                "CLI: hyprtheme list · current · apply <theme> · save <name> · rollback · export <file> · import <file> · reset",
                "ht-mono",
                "ht-small",
                "ht-muted",
                wrap=True,
            )
        )
        self.content.append(c)

    def _on_mode(self, key: str, value: str) -> None:
        self.state.settings.set_integration(key, value)
        self.state.save_settings()
        self.state.emit("components-changed")

    def _on_setting(self, key: str, value) -> None:
        s = self.state.settings
        if key == "wallpaper_backend":
            s.wallpaper_backend = value
        elif key == "reload_on_apply":
            s.reload_on_apply = bool(value)
        elif key == "backup_limit":
            s.backup_limit = int(value)
        else:
            s.set(key, value)
        self.state.save_settings()

    def _open_folder(self) -> None:
        folder = paths.ensure_dir(paths.app_config_dir())
        try:
            subprocess.Popen(["xdg-open", str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            self.state.emit("message", f"Could not open folder: {exc}", True)
