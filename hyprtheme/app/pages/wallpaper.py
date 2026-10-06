"""Wallpaper: library grid, file picker, transition / duration / fit, preview."""

from __future__ import annotations

import threading
from pathlib import Path

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

from ...core import paths
from ...core.generator import resolve_wallpaper
from ...core.theme import WALLPAPER_FIT_MODES, WALLPAPER_TRANSITIONS
from ...core.wallpaper import IMAGE_SUFFIXES, list_wallpapers
from ..components import button, card, clear_children, label
from ..components.rows import DropdownRow, SliderRow
from .base import Page

THUMB_W, THUMB_H = 200, 112


class WallpaperPage(Page):
    key = "wallpaper"
    title = "Wallpaper"
    subtitle = "Wallpapers are set through swww (preferred) or hyprpaper and restored at login. Nothing is assumed to exist."

    def build(self) -> None:
        self._thumb_cache: dict[Path, Gdk.Texture] = {}
        columns = Gtk.Box(spacing=20)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, hexpand=True)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        right.set_size_request(380, -1)
        columns.append(left)
        columns.append(right)
        self.content.append(columns)

        toolbar = Gtk.Box(spacing=8)
        toolbar.append(
            button(
                "ADD TO LIBRARY",
                "ht-add-symbolic",
                primary=True,
                on_click=self._add_to_library,
                tooltip=f"Copy an image into {paths.display_path(paths.user_wallpapers_dir())}",
            )
        )
        toolbar.append(
            button("CHOOSE FILE", "ht-folder-symbolic", on_click=self._choose_file, tooltip="Use an image from anywhere without copying it")
        )
        toolbar.append(button("CLEAR", "ht-delete-symbolic", danger=True, on_click=self._clear))
        toolbar.append(button("RESCAN", "ht-reset-symbolic", on_click=self.refresh_library))
        left.append(toolbar)

        lib, lbody = card("Library")
        self.lib_hint = label("", "ht-muted", "ht-small")
        lbody.append(self.lib_hint)
        self.flow = Gtk.FlowBox()
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow.set_column_spacing(10)
        self.flow.set_row_spacing(10)
        self.flow.set_min_children_per_line(2)
        self.flow.set_max_children_per_line(5)
        self.flow.set_homogeneous(True)
        lbody.append(self.flow)
        left.append(lib)

        pc, pbody = card("Preview")
        self.picture = Gtk.Picture()
        self.picture.add_css_class("ht-wp-preview")
        self.picture.set_content_fit(Gtk.ContentFit.COVER)
        self.picture.set_can_shrink(True)
        self.picture.set_size_request(348, 196)
        pbody.append(self.picture)
        self.path_label = label("No wallpaper selected", "ht-muted", "ht-small", "ht-mono")
        self.path_label.set_ellipsize(3)
        self.path_label.set_selectable(True)
        pbody.append(self.path_label)
        right.append(pc)

        oc, obody = card("Options")
        obody.set_spacing(0)
        wp = self.state.working.wallpaper
        self.transition = DropdownRow(
            "transition",
            "Transition",
            "swww transition style",
            [(t, t) for t in WALLPAPER_TRANSITIONS],
            str(wp.get("transition", "grow")),
            self._on_option,
        )
        self.duration = SliderRow("duration", "Transition duration", 0.0, 10.0, 0.1, "s", float(wp.get("duration", 1.5)), self._on_option)
        fit_labels = {"crop": "crop (fill screen)", "fit": "fit (letterbox)", "no": "no resize (center)", "stretch": "stretch"}
        self.fit = DropdownRow(
            "fit",
            "Fit mode",
            "How the image is scaled to the monitor",
            [(f, fit_labels[f]) for f in WALLPAPER_FIT_MODES],
            str(wp.get("fit", "crop")),
            self._on_option,
        )
        obody.append(self.transition)
        obody.append(self.duration)
        obody.append(self.fit)
        right.append(oc)

        bc, bbody = card("Backend")
        self.backend_label = label("", "ht-small", wrap=True)
        bbody.append(self.backend_label)
        right.append(bc)
        self.refresh_library()
        self.refresh_preview()

    # --- library ---------------------------------------------------------------------

    def refresh_library(self) -> None:
        clear_children(self.flow)
        files = list_wallpapers()
        dirs = ", ".join(
            paths.display_path(d) for d in (paths.user_wallpapers_dir(), paths.pictures_dir() / "Wallpapers", paths.pictures_dir())
        )
        self.lib_hint.set_text(
            f"{len(files)} image(s) found in {dirs}" if files else f"No images found. Looked in {dirs}. Use ADD TO LIBRARY."
        )
        selected = resolve_wallpaper(self.state.working)
        for path in files:
            self.flow.insert(self._thumb(path, selected == path), -1)
        self._update_backend_label()

    def _thumb(self, path: Path, selected: bool) -> Gtk.Button:
        btn = Gtk.Button()
        btn.add_css_class("ht-wp-thumb")
        if selected:
            btn.add_css_class("selected")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        pic = Gtk.Picture()
        pic.set_content_fit(Gtk.ContentFit.COVER)
        pic.set_can_shrink(True)
        pic.set_size_request(THUMB_W, THUMB_H)
        pic.set_overflow(Gtk.Overflow.HIDDEN)
        box.append(pic)
        name = label(path.name, "ht-small", "ht-muted", xalign=0.5)
        name.set_ellipsize(3)
        name.set_max_width_chars(22)
        name.set_margin_bottom(4)
        box.append(name)
        btn.set_child(box)
        btn.set_tooltip_text(str(path))
        btn.connect("clicked", lambda *_: self._select(path))
        self._load_thumb_async(path, pic)
        return btn

    def _load_thumb_async(self, path: Path, picture: Gtk.Picture) -> None:
        cached = self._thumb_cache.get(path)
        if cached is not None:
            picture.set_paintable(cached)
            return

        def work() -> None:
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), THUMB_W * 2, THUMB_H * 2, True)
            except GLib.Error:
                return

            def finish() -> bool:
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                self._thumb_cache[path] = texture
                picture.set_paintable(texture)
                return False

            GLib.idle_add(finish)

        threading.Thread(target=work, daemon=True).start()

    # --- selection -------------------------------------------------------------------

    def _select(self, path: Path) -> None:
        self.state.set_wallpaper(str(path))
        self.state.emit("message", f"Wallpaper set to {path.name} — APPLY to show it", False)

    def _clear(self) -> None:
        self.state.set_wallpaper(None)

    def _on_option(self, key: str, value) -> None:
        self.state.set_wallpaper(**{key: value})

    def _file_dialog(self, title: str):
        dialog = Gtk.FileDialog(title=title)
        flt = Gtk.FileFilter()
        flt.set_name("Images")
        for suffix in IMAGE_SUFFIXES:
            flt.add_suffix(suffix.lstrip("."))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(flt)
        dialog.set_filters(filters)
        dialog.set_default_filter(flt)
        pictures = paths.pictures_dir()
        if pictures.is_dir():
            dialog.set_initial_folder(Gio.File.new_for_path(str(pictures)))
        return dialog

    def _choose_file(self) -> None:
        dialog = self._file_dialog("Choose a wallpaper")

        def done(d: Gtk.FileDialog, result) -> None:
            try:
                f = d.open_finish(result)
            except GLib.Error:
                return
            if f and f.get_path():
                self._select(Path(f.get_path()))

        dialog.open(self.get_root(), None, done)

    def _add_to_library(self) -> None:
        dialog = self._file_dialog("Add a wallpaper to the library")

        def done(d: Gtk.FileDialog, result) -> None:
            try:
                f = d.open_finish(result)
            except GLib.Error:
                return
            if f and f.get_path():
                try:
                    dest = self.state.engine.copy_wallpaper_to_library(Path(f.get_path()))
                except OSError as exc:
                    self.state.emit("message", f"Could not copy wallpaper: {exc}", True)
                    return
                self.refresh_library()
                self._select(dest)

        dialog.open(self.get_root(), None, done)

    # --- preview ---------------------------------------------------------------------

    def refresh_preview(self) -> None:
        path = resolve_wallpaper(self.state.working)
        ref = self.state.working.wallpaper.get("path")
        if path is None:
            self.picture.set_paintable(None)
            self.path_label.set_text(f"Not found: {ref}" if ref else "No wallpaper selected")
            return
        self.path_label.set_text(paths.display_path(path))
        try:
            self.picture.set_paintable(Gdk.Texture.new_from_filename(str(path)))
        except GLib.Error:
            self.picture.set_paintable(None)
        for child in _flow_children(self.flow):
            btn = child.get_child()
            if isinstance(btn, Gtk.Button):
                if btn.get_tooltip_text() == str(path):
                    btn.add_css_class("selected")
                else:
                    btn.remove_css_class("selected")

    def _update_backend_label(self) -> None:
        backend = self.state.engine.wallpapers.backend()
        pref = self.state.settings.wallpaper_backend
        if backend:
            self.backend_label.set_text(
                f"Using {backend} (setting: {pref}). The wallpaper is restored at login via an exec-once line in the generated Hyprland config — no background service."
            )
        elif pref == "off":
            self.backend_label.set_text("Wallpaper management is turned off in Settings.")
        else:
            self.backend_label.set_text(
                "No wallpaper daemon found. Install swww (recommended) or hyprpaper: the theme will still apply, only the wallpaper step is skipped."
            )

    def on_theme_changed(self, what: str) -> None:
        if what in ("wallpaper", "theme"):
            self.refresh_preview()
            wp = self.state.working.wallpaper
            self.transition.set_value(str(wp.get("transition", "grow")))
            self.duration.set_value(float(wp.get("duration", 1.5)))
            self.fit.set_value(str(wp.get("fit", "crop")))

    def on_show(self) -> None:
        self._update_backend_label()


def _flow_children(flow: Gtk.FlowBox):
    child = flow.get_first_child()
    while child is not None:
        yield child
        child = child.get_next_sibling()
