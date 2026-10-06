"""Navigation sidebar with the brand header."""

from __future__ import annotations

from collections.abc import Callable

from gi.repository import Gtk

from ... import __version__

NAV_ITEMS: list[tuple[str, str, str]] = [
    ("dashboard", "Dashboard", "ht-dashboard-symbolic"),
    ("themes", "Themes", "ht-themes-symbolic"),
    ("colors", "Colors", "ht-colors-symbolic"),
    ("effects", "Effects", "ht-effects-symbolic"),
    ("wallpaper", "Wallpaper", "ht-wallpaper-symbolic"),
    ("components", "Components", "ht-components-symbolic"),
    ("backup", "Backup & Restore", "ht-backup-symbolic"),
    ("settings", "Settings", "ht-settings-symbolic"),
]


class Sidebar(Gtk.Box):
    def __init__(self, on_navigate: Callable[[str], None]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("ht-sidebar")
        self.on_navigate = on_navigate

        brand = Gtk.Box(spacing=10)
        brand.add_css_class("ht-brand")
        icon = Gtk.Image.new_from_icon_name("hyprtheme")
        icon.add_css_class("ht-brand-icon")
        icon.set_pixel_size(34)
        brand.append(icon)
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        title = Gtk.Label(label="HYPRTHEME", xalign=0)
        title.add_css_class("ht-brand-title")
        sub = Gtk.Label(label="CONTROL CENTER", xalign=0)
        sub.add_css_class("ht-brand-sub")
        texts.append(title)
        texts.append(sub)
        brand.append(texts)
        self.append(brand)

        self.list = Gtk.ListBox()
        self.list.add_css_class("ht-nav")
        self.list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._rows: dict[str, Gtk.ListBoxRow] = {}
        for key, label, icon_name in NAV_ITEMS:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(spacing=12)
            box.add_css_class("ht-nav-row")
            img = Gtk.Image.new_from_icon_name(icon_name)
            img.add_css_class("ht-nav-icon")
            box.append(img)
            lbl = Gtk.Label(label=label, xalign=0)
            lbl.add_css_class("ht-nav-label")
            box.append(lbl)
            row.set_child(box)
            row.key = key
            self.list.append(row)
            self._rows[key] = row
        self.list.connect("row-selected", self._on_row)
        self.append(self.list)

        spacer = Gtk.Box(vexpand=True)
        self.append(spacer)
        footer = Gtk.Label(label=f"v{__version__} · Wayland native", xalign=0)
        footer.add_css_class("ht-sidebar-footer")
        self.append(footer)

    def _on_row(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is not None:
            self.on_navigate(row.key)

    def select(self, key: str) -> None:
        row = self._rows.get(key)
        if row is not None and self.list.get_selected_row() is not row:
            self.list.select_row(row)
