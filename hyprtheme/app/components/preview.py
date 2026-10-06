"""Live desktop preview.

A realistic mock-up of a Hyprland desktop (Waybar, terminal, launcher,
notification, system/music/battery widgets, file manager) built from GTK
widgets and styled with CSS generated from the *actual* theme values, so
every colour, radius, border, opacity and glow change is reflected instantly.
"""

from __future__ import annotations

from pathlib import Path

from gi.repository import Gdk, GLib, Gtk, Pango

from ...core.colors import Color
from ...core.generator import resolve_wallpaper
from ...core.theme import Theme
from . import dyncss

DESIGN_W, DESIGN_H = 800, 450


def _rgba(hex_color: str, alpha: float) -> str:
    return Color.parse(hex_color).css_rgba(alpha)


class DesktopPreview(Gtk.Box):
    def __init__(self, width: int = 760):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.scale = width / DESIGN_W
        self.width = width
        self.height = int(DESIGN_H * self.scale)
        self.add_css_class("ht-preview")
        self.set_size_request(self.width, self.height)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.START)
        self.set_overflow(Gtk.Overflow.HIDDEN)

        self._provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self._provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2)
        self._wallpaper_path: Path | None = None

        self.overlay = Gtk.Overlay()
        self.overlay.set_size_request(self.width, self.height)
        self.append(self.overlay)

        self.backdrop = Gtk.Box()
        self.backdrop.add_css_class("pv-desktop")
        self.backdrop.set_size_request(self.width, self.height)
        self.overlay.set_child(self.backdrop)

        self.picture = Gtk.Picture()
        self.picture.set_content_fit(Gtk.ContentFit.COVER)
        self.picture.set_can_shrink(True)
        self.picture.set_size_request(self.width, self.height)
        self.picture.set_visible(False)
        self.overlay.add_overlay(self.picture)

        self.fixed = Gtk.Fixed()
        self.fixed.set_size_request(self.width, self.height)
        self.overlay.add_overlay(self.fixed)

        self._build_bar()
        self._build_terminal()
        self._build_launcher()
        self._build_files()
        self._build_widgets()

    # --- geometry helpers ------------------------------------------------------------

    def _put(self, widget: Gtk.Widget, x: int, y: int, w: int, h: int) -> None:
        widget.set_size_request(int(w * self.scale), int(h * self.scale))
        widget.set_overflow(Gtk.Overflow.HIDDEN)
        self.fixed.put(widget, int(x * self.scale), int(y * self.scale))

    def _lbl(self, text: str, *classes: str, markup: bool = False, xalign: float = 0.0) -> Gtk.Label:
        lbl = Gtk.Label(xalign=xalign)
        if markup:
            lbl.set_markup(text)
        else:
            lbl.set_text(text)
        for c in classes:
            lbl.add_css_class(c)
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        return lbl

    def _window(self, title: str, cls: str) -> tuple[Gtk.Box, Gtk.Box]:
        win = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        win.add_css_class("pv-window")
        win.add_css_class(cls)
        titlebar = Gtk.Box(spacing=5)
        titlebar.add_css_class("pv-titlebar")
        for dot in ("pv-dot-r", "pv-dot-y", "pv-dot-g"):
            d = Gtk.Box(valign=Gtk.Align.CENTER)
            d.add_css_class("pv-dot")
            d.add_css_class(dot)
            titlebar.append(d)
        t = self._lbl(title, "pv-title")
        t.set_margin_start(6)
        titlebar.append(t)
        win.append(titlebar)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.add_css_class("pv-body")
        body.set_vexpand(True)
        win.append(body)
        return win, body

    # --- sections ----------------------------------------------------------------------

    def _build_bar(self) -> None:
        bar = Gtk.CenterBox()
        bar.add_css_class("pv-bar")
        left = Gtk.Box(spacing=5)
        launcher = self._lbl("◈", "pv-module", "pv-launcher-btn")
        left.append(launcher)
        ws = Gtk.Box(spacing=3)
        ws.add_css_class("pv-module")
        for i in range(1, 6):
            pill = self._lbl(str(i), "pv-ws", "pv-ws-active" if i == 1 else "pv-ws-inactive", xalign=0.5)
            ws.append(pill)
        left.append(ws)
        bar.set_start_widget(left)

        center = Gtk.Box(spacing=5)
        center.append(self._lbl("Mon 06 Oct  09:47 PM", "pv-module", "pv-clock"))
        center.append(self._lbl("♫ After Dark · Mr.Kitty", "pv-module", "pv-media"))
        bar.set_center_widget(center)

        right = Gtk.Box(spacing=5)
        for text, cls in (
            ("WIFI", "pv-net"),
            ("BT", "pv-bt"),
            ("VOL 64%", "pv-vol"),
            ("BAT 87%", "pv-bat"),
            ("● 2", "pv-notif"),
            ("CPU 23%  RAM 48%", "pv-sys"),
        ):
            right.append(self._lbl(text, "pv-module", cls))
        right.append(self._lbl("⏻", "pv-module", "pv-power"))
        bar.set_end_widget(right)
        self._put(bar, 8, 8, DESIGN_W - 16, 30)

    def _build_terminal(self) -> None:
        win, body = self._window("kitty — fastfetch", "pv-term")
        body.set_orientation(Gtk.Orientation.HORIZONTAL)
        body.set_spacing(10)
        logo = self._lbl(
            "\n".join(
                [
                    "        ▲        ",
                    "       ▲▲▲       ",
                    "      ▲▲▲▲▲      ",
                    "     ▲▲▲▲▲▲▲     ",
                    "    ▲▲▲   ▲▲▲    ",
                    "   ▲▲▲  ▲  ▲▲▲   ",
                    "  ▲▲▲▲▲▲ ▲▲▲▲▲▲  ",
                    " ▲▲▲         ▲▲▲ ",
                ]
            ),
            "pv-mono",
            "pv-logo",
        )
        logo.set_ellipsize(Pango.EllipsizeMode.NONE)
        body.append(logo)
        self.term_text = Gtk.Label(xalign=0, yalign=0)
        self.term_text.add_css_class("pv-mono")
        self.term_text.set_ellipsize(Pango.EllipsizeMode.END)
        body.append(self.term_text)
        self._put(win, 16, 50, 384, 192)

    def _build_launcher(self) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        box.add_css_class("pv-launcher")
        search = self._lbl("⌕  Search…", "pv-search")
        box.append(search)
        apps = [
            ("Firefox", "#FF7139"),
            ("VS Code", "#3B82F6"),
            ("Files", None),
            ("Terminal", None),
            ("Discord", "#5865F2"),
            ("Spotify", "#1DB954"),
            ("Settings", None),
        ]
        for i, (name, color) in enumerate(apps):
            row = Gtk.Box(spacing=7)
            row.add_css_class("pv-app")
            if i == 0:
                row.add_css_class("pv-app-selected")
            icon = Gtk.Box(valign=Gtk.Align.CENTER)
            icon.add_css_class("pv-app-icon")
            if color:
                icon.add_css_class(dyncss.bg_class(color))
            else:
                icon.add_css_class("pv-app-icon-accent")
            row.append(icon)
            row.append(self._lbl(name, "pv-app-name"))
            box.append(row)
        self._put(box, 16, 252, 236, 184)

    def _build_files(self) -> None:
        win, body = self._window("Files — ~", "pv-files")
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, column_homogeneous=True)
        names = ["Desktop", "Documents", "Downloads", "Music", "Pictures", "Projects", "Videos", "Templates"]
        for i, name in enumerate(names):
            cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, halign=Gtk.Align.CENTER)
            folder = Gtk.Box(halign=Gtk.Align.CENTER)
            folder.add_css_class("pv-folder")
            cell.append(folder)
            cell.append(self._lbl(name, "pv-file-name", xalign=0.5))
            grid.attach(cell, i % 4, i // 4, 1, 1)
        body.append(grid)
        self._put(win, 264, 252, 312, 184)

    def _progress(self, cls: str, fraction: float, width: int) -> Gtk.Box:
        track = Gtk.Box()
        track.add_css_class("pv-track")
        track.set_size_request(int(width * self.scale), int(5 * self.scale))
        fill = Gtk.Box()
        fill.add_css_class("pv-fill")
        fill.add_css_class(cls)
        fill.set_size_request(int(width * fraction * self.scale), int(5 * self.scale))
        track.append(fill)
        return track

    def _widget(self, title: str) -> tuple[Gtk.Box, Gtk.Box]:
        w = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        w.add_css_class("pv-widget")
        w.append(self._lbl(title, "pv-widget-title"))
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        w.append(body)
        return w, body

    def _build_widgets(self) -> None:
        # System
        w, body = self._widget("System")
        for name, pct, cls in (
            ("CPU", 0.23, "pv-fill-system"),
            ("RAM", 0.48, "pv-fill-system"),
            ("GPU", 0.37, "pv-fill-secondary"),
            ("TEMP 47°", 0.47, "pv-fill-warning"),
        ):
            row = Gtk.Box(spacing=6)
            lbl = self._lbl(name, "pv-widget-text")
            lbl.set_size_request(int(52 * self.scale), -1)
            row.append(lbl)
            row.append(self._progress(cls, pct, 118))
            body.append(row)
        self._put(w, 588, 50, 196, 100)

        # Music
        w, body = self._widget("Music")
        row = Gtk.Box(spacing=8)
        art = Gtk.Box(valign=Gtk.Align.CENTER)
        art.add_css_class("pv-art")
        row.append(art)
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, valign=Gtk.Align.CENTER)
        texts.append(self._lbl("After Dark", "pv-widget-text", "pv-strong"))
        texts.append(self._lbl("Mr.Kitty", "pv-widget-muted"))
        texts.append(self._lbl("◀   ❚❚   ▶", "pv-widget-text", "pv-media-ctl"))
        row.append(texts)
        body.append(row)
        body.append(self._progress("pv-fill-media", 0.62, 176))
        self._put(w, 588, 158, 196, 92)

        # Notification
        n = Gtk.Box(spacing=8)
        n.add_css_class("pv-notification")
        dot = Gtk.Box(valign=Gtk.Align.START)
        dot.add_css_class("pv-notif-icon")
        n.append(dot)
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, hexpand=True)
        head = Gtk.Box()
        head.append(self._lbl("HyprTheme", "pv-widget-text", "pv-strong"))
        now = self._lbl("now", "pv-widget-muted", xalign=1)
        now.set_hexpand(True)
        head.append(now)
        texts.append(head)
        texts.append(self._lbl("Theme applied — desktop updated", "pv-widget-muted"))
        n.append(texts)
        self._put(n, 588, 258, 196, 56)

        # Battery
        w, body = self._widget("Battery")
        row = Gtk.Box(spacing=8)
        row.append(self._lbl("87%", "pv-widget-text", "pv-strong", "pv-battery-pct"))
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER, hexpand=True)
        col.append(self._lbl("3h 22m remaining", "pv-widget-muted"))
        col.append(self._progress("pv-fill-battery", 0.87, 120))
        row.append(col)
        body.append(row)
        self._put(w, 588, 322, 196, 62)

        # Workspace indicator (bottom-left floating pill)
        ws = Gtk.Box(spacing=4)
        ws.add_css_class("pv-ws-float")
        for i in range(1, 6):
            d = Gtk.Box(valign=Gtk.Align.CENTER)
            d.add_css_class("pv-ws-dot")
            d.add_css_class("pv-ws-dot-active" if i == 1 else "pv-ws-dot-inactive")
            ws.append(d)
        self._put(ws, 588, 396, 196, 40)

    # --- updating ----------------------------------------------------------------------

    def update(self, theme: Theme) -> None:
        self._provider.load_from_string(self._css(theme))
        self._update_terminal_text(theme)
        self._update_wallpaper(theme)

    def _update_terminal_text(self, theme: Theme) -> None:
        c = theme.colors
        ansi = theme.ansi_palette()
        pal = "".join(f'<span foreground="{ansi[f"color{i}"]}">█</span>' for i in range(8))
        lines = [
            f'<span foreground="{c["primary"]}"><b>arunkumar</b></span><span foreground="{c["muted"]}">@</span><span foreground="{c["secondary"]}"><b>hyprland</b></span>',
            f'<span foreground="{c["muted"]}">─────────────────────</span>',
        ]
        for k, v in (
            ("OS", "Arch Linux"),
            ("WM", "Hyprland"),
            ("Shell", "zsh 5.9"),
            ("Kernel", "6.18.0-arch1"),
            ("Uptime", "2h 14m"),
            ("Packages", "1034 (pacman)"),
            ("Terminal", "kitty"),
            ("Theme", theme.name),
        ):
            lines.append(
                f'<span foreground="{c["primary"]}"><b>{k:<9}</b></span><span foreground="{c["text"]}">{GLib.markup_escape_text(v)}</span>'
            )
        lines.append(pal)
        self.term_text.set_markup("\n".join(lines))

    def _update_wallpaper(self, theme: Theme) -> None:
        path = resolve_wallpaper(theme)
        if path == self._wallpaper_path:
            return
        self._wallpaper_path = path
        if path is None:
            self.picture.set_visible(False)
            self.picture.set_paintable(None)
            return
        try:
            texture = Gdk.Texture.new_from_filename(str(path))
        except GLib.Error:
            self.picture.set_visible(False)
            return
        self.picture.set_paintable(texture)
        self.picture.set_visible(True)

    def _css(self, theme: Theme) -> str:
        c = theme.colors
        e = theme.effects
        s = self.scale
        glass = bool(e["glass"])
        panel_a = float(e["opacity"]) if glass else 1.0
        glow = float(e["glow"]) if e["neon_glow"] else 0.0
        glow_px = int((4 + 18 * glow) * s)
        radius = int(e["radius"] * s)
        r_sm = max(2, int(radius * 0.7))
        bw = max(1, int(e["border_width"] * s)) if e["border_width"] > 0 else 0
        gap = int(e["window_gaps"] * s)
        fs = max(8, int(10 * s))
        fs_sm = max(7, int(9 * s))
        anim = f"{int(200 / float(e['animation_speed']))}ms" if e["animations"] else "0ms"
        grad = f"linear-gradient(135deg, {c['gradient_start']}, {c['gradient_end']})" if e["gradient"] else c["primary"]
        active_border = f"{c['active_border']}"
        shadow = f"0 {int(6 * s)}px {int(20 * s)}px rgba(0,0,0,0.45)" if e["shadows"] else "none"
        glow_shadow = f"0 0 {glow_px}px {_rgba(c['glow'], 0.15 + 0.55 * glow)}" if glow > 0 else "none"
        panel_bg = _rgba(c["surface"], panel_a)
        bar_bg = _rgba(c["background"], panel_a)
        on_accent = Color.parse(c["workspace_active"]).readable_text().hex
        on_highlight = Color.parse(c["highlight"]).readable_text().hex
        bg = Color.parse(c["background"])
        bg2 = bg.mix(Color.parse(c["gradient_end"]), 0.35).hex
        bg3 = bg.mix(Color.parse(c["gradient_start"]), 0.25).hex
        return f"""
.ht-preview {{ border-radius: {int(14 * s)}px; border: 1px solid {_rgba(c["border"], 0.35)}; background: {c["background"]}; }}
.ht-preview .pv-desktop {{ background: radial-gradient(circle at 20% 15%, {bg3} 0%, {c["background"]} 45%, {bg2} 100%); }}
.ht-preview label {{ color: {c["text"]}; font-size: {fs}px; font-family: "Inter", "Cantarell", sans-serif; }}
.ht-preview .pv-mono {{ font-family: "JetBrainsMono Nerd Font", "JetBrains Mono", "DejaVu Sans Mono", monospace; font-size: {fs_sm}px; }}
.ht-preview .pv-logo {{ color: {c["primary"]}; font-size: {max(6, int(7 * s))}px; }}

.ht-preview .pv-bar {{ background: {bar_bg}; border: {bw}px solid {_rgba(c["border"], 0.6 + 0.4 * glow)}; border-radius: {r_sm}px; padding: 0 {int(6 * s)}px; box-shadow: {glow_shadow}; transition: all {anim} ease; }}
.ht-preview .pv-module {{ background: {_rgba(c["surface"], min(1.0, panel_a * 0.9 + 0.08))}; border: 1px solid {_rgba(c["border"], 0.25)}; border-radius: {max(2, int(r_sm * 0.75))}px; padding: {int(2 * s)}px {int(6 * s)}px; font-size: {fs_sm}px; font-weight: 600; }}
.ht-preview .pv-launcher-btn {{ color: {c["primary"]}; font-size: {fs + 2}px; }}
.ht-preview .pv-clock {{ font-weight: 700; }}
.ht-preview .pv-media {{ color: {c["media"]}; }}
.ht-preview .pv-net {{ color: {c["success"]}; }}
.ht-preview .pv-bt {{ color: {c["secondary"]}; }}
.ht-preview .pv-vol {{ color: {c["primary"]}; }}
.ht-preview .pv-bat {{ color: {c["battery"]}; }}
.ht-preview .pv-notif {{ color: {c["notification"]}; }}
.ht-preview .pv-sys {{ color: {c["system"]}; }}
.ht-preview .pv-power {{ color: {c["error"]}; }}
.ht-preview .pv-ws {{ min-width: {int(12 * s)}px; padding: 0 {int(4 * s)}px; border-radius: {max(2, int(r_sm * 0.6))}px; font-size: {fs_sm}px; font-weight: 700; }}
.ht-preview .pv-ws-active {{ background: {grad}; color: {on_accent}; box-shadow: 0 0 {int(glow_px * 0.6)}px {_rgba(c["workspace_active"], 0.6 * glow)}; }}
.ht-preview .pv-ws-inactive {{ color: {c["workspace_inactive"]}; }}

.ht-preview .pv-window {{ background: {panel_bg}; border: {bw}px solid {active_border}; border-radius: {radius}px; box-shadow: {shadow}{", " + glow_shadow if glow > 0 else ""}; transition: all {anim} ease; }}
.ht-preview .pv-files {{ border-color: {_rgba(c["inactive_border"], 0.9)}; box-shadow: {shadow}; }}
.ht-preview .pv-titlebar {{ padding: {int(5 * s)}px {int(8 * s)}px; border-bottom: 1px solid {_rgba(c["border"], 0.18)}; }}
.ht-preview .pv-title {{ color: {c["muted"]}; font-size: {fs_sm}px; }}
.ht-preview .pv-dot {{ min-width: {int(7 * s)}px; min-height: {int(7 * s)}px; border-radius: 99px; }}
.ht-preview .pv-dot-r {{ background: {c["error"]}; }}
.ht-preview .pv-dot-y {{ background: {c["warning"]}; }}
.ht-preview .pv-dot-g {{ background: {c["success"]}; }}
.ht-preview .pv-body {{ padding: {int(6 * s)}px {int(8 * s)}px; }}

.ht-preview .pv-launcher {{ background: {panel_bg}; border: {bw}px solid {_rgba(c["border"], 0.6 + 0.4 * glow)}; border-radius: {radius}px; padding: {int(8 * s)}px; box-shadow: {glow_shadow}; transition: all {anim} ease; }}
.ht-preview .pv-search {{ background: {_rgba(c["surface2"], 0.9)}; border-bottom: 2px solid {c["primary"]}; border-radius: {r_sm}px; padding: {int(4 * s)}px {int(8 * s)}px; color: {c["muted"]}; margin-bottom: {int(4 * s)}px; }}
.ht-preview .pv-app {{ padding: {int(2 * s)}px {int(6 * s)}px; border-radius: {r_sm}px; }}
.ht-preview .pv-app-selected {{ background: {grad if e["gradient"] else c["highlight"]}; }}
.ht-preview .pv-app-selected label {{ color: {on_highlight}; font-weight: 700; }}
.ht-preview .pv-app-name {{ font-size: {fs_sm}px; }}
.ht-preview .pv-app-icon {{ min-width: {int(11 * s)}px; min-height: {int(11 * s)}px; border-radius: {max(2, int(3 * s))}px; background: {c["muted"]}; }}
.ht-preview .pv-app-icon-accent {{ background: {c["primary"]}; }}

.ht-preview .pv-folder {{ min-width: {int(26 * s)}px; min-height: {int(20 * s)}px; border-radius: {max(2, int(4 * s))}px; background: {grad}; box-shadow: 0 0 {int(glow_px * 0.5)}px {_rgba(c["glow"], 0.5 * glow)}; }}
.ht-preview .pv-file-name {{ font-size: {max(6, int(8 * s))}px; color: {c["muted"]}; }}

.ht-preview .pv-widget {{ background: {panel_bg}; border: {bw}px solid {_rgba(c["border"], 0.45 + 0.4 * glow)}; border-radius: {radius}px; padding: {int(7 * s)}px {int(9 * s)}px; box-shadow: {glow_shadow}; transition: all {anim} ease; }}
.ht-preview .pv-widget-title {{ font-size: {fs_sm}px; font-weight: 800; letter-spacing: 1px; color: {c["primary"]}; }}
.ht-preview .pv-widget-text {{ font-size: {fs_sm}px; }}
.ht-preview .pv-strong {{ font-weight: 700; }}
.ht-preview .pv-widget-muted {{ font-size: {max(6, int(8 * s))}px; color: {c["muted"]}; }}
.ht-preview .pv-track {{ background: {_rgba(c["surface2"], 0.95)}; border-radius: 99px; }}
.ht-preview .pv-fill {{ border-radius: 99px; }}
.ht-preview .pv-fill-system {{ background: {c["system"]}; }}
.ht-preview .pv-fill-secondary {{ background: {c["secondary"]}; }}
.ht-preview .pv-fill-warning {{ background: {c["warning"]}; }}
.ht-preview .pv-fill-media {{ background: {c["media"]}; }}
.ht-preview .pv-fill-battery {{ background: {c["battery"]}; }}
.ht-preview .pv-art {{ min-width: {int(34 * s)}px; min-height: {int(34 * s)}px; border-radius: {r_sm}px; background: linear-gradient(135deg, {c["media"]}, {c["gradient_end"]}); }}
.ht-preview .pv-media-ctl {{ color: {c["media"]}; }}
.ht-preview .pv-battery-pct {{ font-size: {fs + 6}px; color: {c["battery"]}; }}

.ht-preview .pv-notification {{ background: {panel_bg}; border: {bw}px solid {_rgba(c["notification"], 0.7 + 0.3 * glow)}; border-radius: {radius}px; padding: {int(7 * s)}px {int(9 * s)}px; box-shadow: 0 0 {glow_px}px {_rgba(c["notification"], 0.15 + 0.5 * glow)}; transition: all {anim} ease; }}
.ht-preview .pv-notif-icon {{ min-width: {int(14 * s)}px; min-height: {int(14 * s)}px; border-radius: 99px; background: {c["notification"]}; margin-top: {int(2 * s)}px; }}

.ht-preview .pv-ws-float {{ background: {panel_bg}; border: {bw}px solid {_rgba(c["border"], 0.4)}; border-radius: 99px; padding: {int(4 * s)}px {int(12 * s)}px; }}
.ht-preview .pv-ws-dot {{ min-width: {int(8 * s)}px; min-height: {int(8 * s)}px; border-radius: 99px; margin: {int(3 * s)}px; }}
.ht-preview .pv-ws-dot-active {{ background: {c["workspace_active"]}; min-width: {int(20 * s)}px; box-shadow: 0 0 {int(glow_px * 0.6)}px {_rgba(c["workspace_active"], 0.7 * glow)}; }}
.ht-preview .pv-ws-dot-inactive {{ background: {c["workspace_inactive"]}; }}
.ht-preview .pv-term .pv-body {{ padding-left: {int(gap * 0.5 + 6 * s)}px; }}
"""
