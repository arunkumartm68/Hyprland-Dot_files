"""Main window: sidebar + header actions + page stack + toasts + dialogs."""

from __future__ import annotations

import os
from pathlib import Path

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from ..core import paths
from ..core.colors import Color
from .components import button
from .components.sidebar import Sidebar
from .pages.backup import BackupPage
from .pages.base import Page
from .pages.colors import ColorsPage
from .pages.components import ComponentsPage
from .pages.dashboard import DashboardPage
from .pages.effects import EffectsPage
from .pages.settings import SettingsPage
from .pages.themes import ThemesPage
from .pages.wallpaper import WallpaperPage
from .state import AppState

PAGE_CLASSES: list[type[Page]] = [
    DashboardPage,
    ThemesPage,
    ColorsPage,
    EffectsPage,
    WallpaperPage,
    ComponentsPage,
    BackupPage,
    SettingsPage,
]


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, state: AppState):
        super().__init__(application=app, title="HyprTheme")
        self.state = state
        self.set_default_size(1380, 880)
        self.set_size_request(1024, 640)
        self.add_css_class("ht-window")
        self.set_icon_name("hyprtheme")

        self._accent_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._accent_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
        )
        self._update_accent()

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.toasts.set_child(root)

        self.sidebar = Sidebar(self.navigate)
        root.append(self.sidebar)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        root.append(main)

        header = Adw.HeaderBar()
        header.add_css_class("ht-header")
        header.set_show_end_title_buttons(True)
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        self.title_label = Gtk.Label(label="HyprTheme", xalign=0)
        self.title_label.add_css_class("ht-header-title")
        self.sub_label = Gtk.Label(label="", xalign=0)
        self.sub_label.add_css_class("ht-header-sub")
        titles.append(self.title_label)
        titles.append(self.sub_label)
        header.set_title_widget(titles)

        actions = Gtk.Box(spacing=6)
        self.apply_btn = button(
            "APPLY",
            "ht-apply-symbolic",
            primary=True,
            on_click=self.do_apply,
            tooltip="Generate configs, back up, write and reload (Ctrl+Return)",
        )
        actions.append(self.apply_btn)
        actions.append(button("SAVE", "ht-save-symbolic", on_click=self.do_save, tooltip="Save the working theme (Ctrl+S)"))
        actions.append(button("SAVE AS", "ht-save-as-symbolic", on_click=self.do_save_as, tooltip="Save under a new name (Ctrl+Shift+S)"))
        actions.append(button("ROLLBACK", "ht-rollback-symbolic", on_click=self.do_rollback, tooltip="Undo the last apply"))
        actions.append(
            button("RESET", "ht-reset-symbolic", danger=True, on_click=self.do_reset, tooltip="Discard edits or reset the desktop")
        )
        header.pack_end(actions)
        main.append(header)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(160)
        self.stack.set_vexpand(True)
        self.pages: dict[str, Page] = {}
        for cls in PAGE_CLASSES:
            page = cls(state)
            self.pages[cls.key] = page
            self.stack.add_named(page, cls.key)
        main.append(self.stack)

        state.connect("changed", lambda *_: self._update_header())
        state.connect("changed", lambda *_: self._update_accent())
        state.connect("applied", lambda *_: self._update_header())
        state.connect("busy", lambda _s, busy: self.apply_btn.set_sensitive(not busy))
        state.connect("message", self._on_message)
        self._update_header()
        self._install_shortcuts()
        start = str(state.settings.get("last_page", "dashboard"))
        self.navigate(start if start in self.pages else "dashboard")
        self.sidebar.select(self.stack.get_visible_child_name() or "dashboard")

    # --- navigation ---------------------------------------------------------------

    def navigate(self, key: str) -> None:
        if key not in self.pages:
            return
        self.stack.set_visible_child_name(key)
        self.pages[key].on_show()
        self.state.settings.set("last_page", key)

    def _install_shortcuts(self) -> None:
        controller = Gtk.ShortcutController()
        controller.set_scope(Gtk.ShortcutScope.GLOBAL)

        def wrap(fn):
            def callback(*_args) -> bool:
                fn()
                return True

            return callback

        def goto(key: str):
            def callback(*_args) -> bool:
                self.navigate(key)
                self.sidebar.select(key)
                return True

            return callback

        for trigger, fn in (
            ("<Control>Return", self.do_apply),
            ("<Control>s", self.do_save),
            ("<Control><Shift>s", self.do_save_as),
            ("<Control>z", self.do_rollback),
            ("<Control>q", self.get_application().quit),
        ):
            controller.add_shortcut(Gtk.Shortcut.new(Gtk.ShortcutTrigger.parse_string(trigger), Gtk.CallbackAction.new(wrap(fn))))
        for i, key in enumerate(self.pages):
            controller.add_shortcut(Gtk.Shortcut.new(Gtk.ShortcutTrigger.parse_string(f"<Alt>{i + 1}"), Gtk.CallbackAction.new(goto(key))))
        self.add_controller(controller)

    # --- header / accent ------------------------------------------------------------

    def _update_header(self) -> None:
        w = self.state.working
        current = self.state.applied()
        dirty = self.state.dirty
        self.title_label.set_text(f"{w.name}{' •' if dirty else ''}")
        applied = f"applied: {current.theme.name}" if current else "nothing applied yet"
        self.sub_label.set_text(f"{'modified, not applied' if dirty else 'working theme'}  ·  {applied}")
        self.set_title(f"HyprTheme — {w.name}")

    def _update_accent(self) -> None:
        c = self.state.working.colors
        on_accent = Color.parse(c["primary"]).readable_text().hex
        css = "\n".join(
            [
                "@define-color ht_bg #050609;",
                "@define-color ht_surface #0E1118;",
                "@define-color ht_surface2 #161B26;",
                "@define-color ht_text #F2F5FA;",
                "@define-color ht_muted #8791A3;",
                f"@define-color ht_accent {c['primary']};",
                f"@define-color ht_glow {c['glow']};",
                f"@define-color ht_gradient_start {c['gradient_start']};",
                f"@define-color ht_gradient_end {c['gradient_end']};",
                f"@define-color ht_success {c['success']};",
                f"@define-color ht_warning {c['warning']};",
                f"@define-color ht_error {c['error']};",
                f"@define-color ht_on_accent {on_accent};",
            ]
        )
        self._accent_provider.load_from_string(css)

    # --- messages & actions ---------------------------------------------------------

    def _on_message(self, _state: AppState, text: str, is_error: bool) -> None:
        # Pages ask the window to run actions through sentinel messages so dialogs live in one place.
        if text.startswith("__"):
            cmd, _, arg = text[2:].partition(":")
            cmd = cmd.rstrip("_")
            handlers = {
                "apply": self.do_apply,
                "save": self.do_save,
                "save_as": self.do_save_as,
                "rollback": self.do_rollback,
                "reset": self.do_reset,
                "reset_original": self.do_reset_original,
                "import": self.do_import,
                "export": self.do_export,
                "delete": lambda: self.do_delete(arg),
                "restore": lambda: self.do_restore(arg),
            }
            fn = handlers.get(cmd)
            if fn:
                fn()
            return
        toast = Adw.Toast.new(text)
        toast.set_timeout(5 if is_error else 3)
        self.toasts.add_toast(toast)

    def do_apply(self) -> None:
        if self.state.busy:
            return
        problems = self.state.working.validate()
        if problems:
            self._on_message(self.state, "Theme is invalid: " + problems[0], True)
            return
        self._on_message(self.state, f"Applying {self.state.working.name}…", False)
        self.state.apply()

    def do_save(self) -> None:
        w = self.state.working
        if w.preset or w.source is None or w.source.parent != paths.user_themes_dir():
            self.do_save_as()
            return
        self.state.save()

    def do_save_as(self) -> None:
        self._name_dialog(
            "Save theme as",
            "Theme name",
            self.state.working.name if not self.state.working.preset else f"{self.state.working.name} Custom",
            self._save_with_name,
        )

    def _save_with_name(self, name: str) -> None:
        if not name.strip():
            return
        self.state.save(name.strip())

    def do_rollback(self) -> None:
        self._confirm(
            "Roll back the last change?",
            "Files replaced by the last apply are restored from their backup and the previous theme becomes current.",
            "Roll back",
            self.state.rollback,
        )

    def do_reset(self) -> None:
        dialog = Adw.AlertDialog.new("Reset", "Discard your unsaved edits, or reset the desktop itself?")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("discard", "Discard edits")
        dialog.add_response("default", "Apply default theme")
        dialog.add_response("original", "Restore original configs")
        dialog.set_response_appearance("original", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("discard")
        dialog.set_close_response("cancel")

        def on_response(_d, response: str) -> None:
            if response == "discard":
                self.state.reset_working()
            elif response == "default":
                self.state.reset_desktop(original=False)
            elif response == "original":
                self.state.reset_desktop(original=True)

        dialog.connect("response", on_response)
        dialog.present(self)

    def do_reset_original(self) -> None:
        self._confirm(
            "Restore the original configuration?",
            "Every file HyprTheme has managed is put back exactly as it was before the first apply. Your saved themes are kept.",
            "Restore",
            lambda: self.state.reset_desktop(original=True),
            destructive=True,
        )

    def do_delete(self, theme_id: str) -> None:
        ref = next((r for r in self.state.themes() if r.id == theme_id and r.kind == "user"), None)
        if ref is None:
            return
        self._confirm(
            f"Delete '{ref.name}'?",
            "The theme file is removed from your themes folder. Applied configs stay as they are.",
            "Delete",
            lambda: self.state.delete_theme(ref),
            destructive=True,
        )

    def do_restore(self, backup_id: str) -> None:
        self._confirm(
            f"Restore backup {backup_id}?",
            "The current files are snapshotted first, so this can be undone.",
            "Restore",
            lambda: self.state.restore_backup(backup_id),
        )

    def do_import(self) -> None:
        dialog = Gtk.FileDialog(title="Import theme")
        flt = Gtk.FileFilter()
        flt.set_name("HyprTheme files")
        flt.add_suffix("hyprtheme")
        flt.add_suffix("json")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(flt)
        dialog.set_filters(filters)

        def done(d: Gtk.FileDialog, result) -> None:
            try:
                f = d.open_finish(result)
            except GLib.Error:
                return
            if f and f.get_path():
                self.state.import_file(Path(f.get_path()))

        dialog.open(self, None, done)

    def do_export(self) -> None:
        dialog = Gtk.FileDialog(title="Export theme")
        dialog.set_initial_name(f"{self.state.working.id}.hyprtheme")
        home = paths.home()
        if home.is_dir():
            dialog.set_initial_folder(Gio.File.new_for_path(str(home)))

        def done(d: Gtk.FileDialog, result) -> None:
            try:
                f = d.save_finish(result)
            except GLib.Error:
                return
            if f and f.get_path():
                self.state.export_file(Path(f.get_path()))

        dialog.save(self, None, done)

    # --- dialogs ----------------------------------------------------------------------

    def _confirm(self, heading: str, body: str, ok_label: str, on_ok, *, destructive: bool = False) -> None:
        dialog = Adw.AlertDialog.new(heading, body)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("ok", ok_label)
        if destructive:
            dialog.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
        else:
            dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("ok")
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda _d, r: on_ok() if r == "ok" else None)
        dialog.present(self)

    def _name_dialog(self, heading: str, placeholder: str, initial: str, on_ok) -> None:
        dialog = Adw.AlertDialog.new(heading, "Saved to " + paths.display_path(paths.user_themes_dir()))
        entry = Gtk.Entry()
        entry.add_css_class("ht-entry")
        entry.set_placeholder_text(placeholder)
        entry.set_text(initial)
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("ok", "Save")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("ok")
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda _d, r: on_ok(entry.get_text()) if r == "ok" else None)
        dialog.present(self)
        entry.grab_focus()

    def do_screenshot(self, path: Path, page: str | None = None) -> None:
        """Render the window to a PNG (used for docs and the headless smoke test)."""
        if page:
            self.navigate(page)
            self.sidebar.select(page)
        paintable = Gtk.WidgetPaintable.new(self)
        snapshot = Gtk.Snapshot()
        w, h = self.get_width(), self.get_height()
        paintable.snapshot(snapshot, w, h)
        node = snapshot.to_node()
        if node is None:
            return
        renderer = self.get_native().get_renderer()
        texture = renderer.render_texture(node, None)
        texture.save_to_png(str(path))


def is_wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY"))
