"""Dashboard: current theme, component status, quick actions, preview."""

from __future__ import annotations

from gi.repository import Gtk

from ...core import paths
from ...core.components import COMPONENT_SPECS
from ..components import button, card, label, stat
from ..components.pills import StatusPill, Swatches
from ..components.preview import DesktopPreview
from .base import Page


class DashboardPage(Page):
    key = "dashboard"
    title = "Dashboard"
    subtitle = "Overview of the applied theme and the state of your desktop components."

    def build(self) -> None:
        top = Gtk.Box(spacing=16)
        hero, body = card(glow=True)
        hero.set_hexpand(True)
        self.hero_name = label("—", "ht-hero-name")
        self.hero_sub = label("", "ht-muted", "ht-small")
        body.append(label("CURRENT THEME", "ht-card-title"))
        body.append(self.hero_name)
        body.append(self.hero_sub)
        self.swatches = Swatches(self.state.working, size=22)
        body.append(self.swatches)
        grid = Gtk.Grid(column_spacing=24, row_spacing=12, margin_top=8)
        self.stat_accent_box, self.stat_accent = stat("Accent", "—")
        self.stat_wall_box, self.stat_wall = stat("Wallpaper", "—")
        self.stat_applied_box, self.stat_applied = stat("Applied", "—")
        self.stat_working_box, self.stat_working = stat("Working copy", "—")
        grid.attach(self.stat_accent_box, 0, 0, 1, 1)
        grid.attach(self.stat_wall_box, 1, 0, 1, 1)
        grid.attach(self.stat_applied_box, 0, 1, 1, 1)
        grid.attach(self.stat_working_box, 1, 1, 1, 1)
        body.append(grid)
        actions = Gtk.Box(spacing=8, margin_top=12)
        actions.append(button("APPLY", "ht-apply-symbolic", primary=True, on_click=lambda: self.state.emit("message", "__apply__", False)))
        actions.append(button("SAVE", "ht-save-symbolic", on_click=lambda: self.state.emit("message", "__save__", False)))
        actions.append(button("SAVE AS", "ht-save-as-symbolic", on_click=lambda: self.state.emit("message", "__save_as__", False)))
        actions.append(button("ROLLBACK", "ht-rollback-symbolic", on_click=lambda: self.state.emit("message", "__rollback__", False)))
        actions.append(button("RESET", "ht-reset-symbolic", danger=True, on_click=lambda: self.state.emit("message", "__reset__", False)))
        body.append(actions)
        top.append(hero)

        status, sbody = card("Components")
        status.set_size_request(300, -1)
        self.pills: dict[str, StatusPill] = {}
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(2)
        flow.set_min_children_per_line(2)
        flow.set_column_spacing(6)
        flow.set_row_spacing(6)
        for key, lbl, _bin, _desc, _req, _proc in COMPONENT_SPECS:
            pill = StatusPill(lbl, "missing", "detecting…")
            pill.set_halign(Gtk.Align.START)
            self.pills[key] = pill
            flow.insert(pill, -1)
        sbody.append(flow)
        self.paths_label = label(
            f"themes: {paths.display_path(paths.user_themes_dir())}\nstate: {paths.display_path(paths.app_state_dir())}",
            "ht-muted",
            "ht-small",
            "ht-mono",
        )
        self.paths_label.set_margin_top(8)
        sbody.append(self.paths_label)
        top.append(status)
        self.content.append(top)

        pcard, pbody = card("Live preview")
        self.preview = DesktopPreview(width=820)
        self.preview.set_halign(Gtk.Align.START)
        pbody.append(self.preview)
        self.content.append(pcard)

        hist, hbody = card("Recent activity")
        self.history_box = hbody
        self.content.append(hist)
        self.refresh()

    def refresh(self) -> None:
        current = self.state.applied()
        working = self.state.working
        if current:
            self.hero_name.set_text(current.theme.name)
            self.hero_sub.set_text(current.theme.description or ("preset" if current.theme.preset else "custom theme"))
            self.stat_accent.set_text(current.theme.colors["primary"])
            wp = current.theme.wallpaper.get("path")
            self.stat_wall.set_text(paths.display_path(wp) if wp else "none")
            self.stat_applied.set_text(current.applied_text)
            self.swatches.update(current.theme)
        else:
            self.hero_name.set_text("No theme applied")
            self.hero_sub.set_text("Pick a preset on the Themes page and press APPLY.")
            self.stat_accent.set_text(working.colors["primary"])
            self.stat_wall.set_text("none")
            self.stat_applied.set_text("never")
            self.swatches.update(working)
        self.stat_working.set_text(f"{working.name}{'  (modified)' if self.state.dirty else ''}")
        self.preview.update(working)
        # history
        child = self.history_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.history_box.remove(child)
            child = nxt
        entries = list(reversed(self.state.engine.history()))[:6]
        if not entries:
            self.history_box.append(label("No themes applied yet.", "ht-muted", "ht-small"))
        import time as _t

        for h in entries:
            when = _t.strftime("%Y-%m-%d %H:%M", _t.localtime(float(h.get("applied_at", 0))))
            row = Gtk.Box(spacing=10)
            row.append(label(when, "ht-muted", "ht-small", "ht-mono"))
            row.append(label(f"applied {h.get('theme', '?')}", "ht-small"))
            self.history_box.append(row)
        self.on_components_changed()

    def on_components_changed(self) -> None:
        for key, pill in self.pills.items():
            info = self.state.components.get(key)
            if info:
                mode = (
                    self.state.settings.integration(key)
                    if key in ("hyprland", "waybar", "kitty", "rofi", "swaync", "hyprlock", "wlogout")
                    else None
                )
                pill.set_from_info(info, mode)

    def on_theme_changed(self, what: str) -> None:
        self.stat_working.set_text(f"{self.state.working.name}{'  (modified)' if self.state.dirty else ''}")
        self.preview.update(self.state.working)

    def on_applied(self) -> None:
        self.refresh()

    def on_show(self) -> None:
        self.refresh()
