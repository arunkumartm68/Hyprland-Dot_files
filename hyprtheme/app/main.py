"""Application entry point: ``hyprtheme gui`` / ``hyprtheme-gui`` / the desktop entry."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .. import APP_ID, __version__  # noqa: E402
from ..core import paths  # noqa: E402
from ..core.engine import EngineError, ThemeEngine  # noqa: E402
from .state import AppState  # noqa: E402
from .window import MainWindow  # noqa: E402


class HyprThemeApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.window: MainWindow | None = None
        self.state: AppState | None = None

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        display = Gdk.Display.get_default()
        icons = paths.assets_dir()
        if display is not None and icons is not None:
            Gtk.IconTheme.get_for_display(display).add_search_path(str(icons / "icons"))
        css = Gtk.CssProvider()
        css.load_from_path(str(Path(__file__).with_name("style.css")))
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self) -> None:
        if self.window is None:
            try:
                engine = ThemeEngine()
                engine.generator  # noqa: B018 - validate templates early
            except EngineError as exc:
                self._fatal(str(exc))
                return
            self.state = AppState(engine)
            self.window = MainWindow(self, self.state)
            shot = os.environ.get("HYPRTHEME_SCREENSHOT")
            if shot:
                self._schedule_screenshots(shot)
        self.window.present()

    def do_shutdown(self) -> None:
        if self.state is not None:
            self.state.save_settings()
        Adw.Application.do_shutdown(self)

    def _fatal(self, message: str) -> None:
        dialog = Adw.AlertDialog.new("HyprTheme cannot start", message)
        dialog.add_response("ok", "Quit")
        win = Gtk.Window(application=self)
        dialog.connect("response", lambda *_: self.quit())
        dialog.present(win)

    def _schedule_screenshots(self, spec: str) -> None:
        """HYPRTHEME_SCREENSHOT=dir[:page1,page2] renders pages to PNG files and quits."""
        target, _, pages_spec = spec.partition(":")
        out = Path(target)
        out.mkdir(parents=True, exist_ok=True)
        pages = [p for p in pages_spec.split(",") if p] or ["dashboard"]

        def shoot(index: int) -> bool:
            window = self.window
            assert window is not None
            if index >= len(pages):
                self.quit()
                return False
            page = pages[index]
            window.navigate(page)
            window.sidebar.select(page)

            def capture() -> bool:
                window.do_screenshot(out / f"{page}.png")
                GLib.timeout_add(200, lambda: shoot(index + 1))
                return False

            GLib.timeout_add(900, capture)
            return False

        GLib.timeout_add(1500, lambda: shoot(0))


def run(argv: list[str] | None = None) -> int:
    app = HyprThemeApp()
    return app.run(argv if argv is not None else [sys.argv[0]])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())


__all__ = ["HyprThemeApp", "__version__", "run"]
