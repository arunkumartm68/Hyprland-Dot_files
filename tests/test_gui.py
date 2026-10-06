"""Functional GUI test: drives the real GTK application headlessly.

Runs only when PyGObject + GTK4 + libadwaita are importable and a display is
available (``xvfb-run python -m pytest tests/test_gui.py``).  It exercises the
GUI → AppState → ThemeEngine → generated-config chain end to end.

Set ``HYPRTHEME_TEST_SCREENSHOTS=<dir>`` to also render every page to PNG.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from .conftest import REPO

pytestmark = pytest.mark.gui

gi = pytest.importorskip("gi", exc_type=ImportError)
try:
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import GLib
except (ValueError, ImportError) as exc:  # pragma: no cover - environment dependent
    pytest.skip(f"GTK4/libadwaita not available: {exc}", allow_module_level=True)

if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):  # pragma: no cover
    pytest.skip("no display (run under xvfb-run)", allow_module_level=True)

SCREENSHOT_DIR = Path(os.environ.get("HYPRTHEME_TEST_SCREENSHOTS", ""))
PAGES = ("dashboard", "themes", "colors", "effects", "wallpaper", "components", "backup", "settings")


def test_gui_end_to_end(fake_home: Path, monkeypatch: pytest.MonkeyPatch):
    from hyprtheme.app.main import HyprThemeApp
    from hyprtheme.core import paths
    from hyprtheme.core.settings import Settings

    settings = Settings.load()
    settings.reload_on_apply = False
    settings.set("hyprland_syntax", "modern")
    settings.set("hyprpaper_syntax", "modern")
    settings.save()
    wp_dir = paths.user_wallpapers_dir()
    wp_dir.mkdir(parents=True, exist_ok=True)
    src = REPO / "Background" / "illust_116916742_20240328_013832.jpg"
    if src.exists():
        shutil.copy2(src, wp_dir / "sakura.jpg")

    app = HyprThemeApp()
    results: dict[str, object] = {}
    errors: list[str] = []

    def step(fn: Callable[[], None]) -> bool:
        try:
            fn()
        except Exception as exc:
            errors.append(f"{fn.__name__}: {exc!r}")
            app.quit()
        return False

    def when_idle(fn: Callable[[], None], interval: int = 100) -> None:
        def poll() -> bool:
            if app.state is not None and app.state.busy:
                return True
            GLib.idle_add(step, fn)
            return False

        GLib.timeout_add(interval, poll)

    def shoot_pages(pages: list[str], prefix: str, then: Callable[[], None]) -> None:
        """Navigate to each page, give GTK time to lay it out, render it, then continue."""
        if not SCREENSHOT_DIR.name:
            GLib.idle_add(step, then)
            return
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        if not pages:
            GLib.idle_add(step, then)
            return
        page, rest = pages[0], pages[1:]
        assert app.window is not None
        app.window.navigate(page)
        app.window.sidebar.select(page)

        attempts = {"n": 0}

        def capture() -> bool:
            assert app.window is not None
            target = SCREENSHOT_DIR / f"{prefix}{page}.png"
            app.window.do_screenshot(target)
            attempts["n"] += 1
            if not target.exists() and attempts["n"] < 5:
                return True  # page not laid out yet: try again on the next tick
            if not target.exists():
                errors.append(f"screenshot of {page} was not written")
            shoot_pages(rest, prefix, then)
            return False

        GLib.timeout_add(700, capture)

    def s1_load_red() -> None:
        win = app.window
        state = app.state
        assert win is not None and state is not None
        assert set(win.pages) == set(PAGES)
        red = next(r for r in state.themes() if r.id == "red")
        win.pages["themes"]._select(red)
        assert state.working.id == "red"
        assert state.working.colors["primary"] == "#FF2E2E"
        css = win.pages["colors"].preview._css(state.working)
        assert "#FF2E2E" in css
        if src.exists():
            win.pages["wallpaper"]._select(wp_dir / "sakura.jpg")
        state.apply()
        when_idle(s2_check_applied)

    def s2_check_applied() -> None:
        state = app.state
        assert state is not None
        current = state.applied()
        assert current is not None and current.theme.id == "red"
        conf = (paths.hypr_dir() / "hyprtheme.conf").read_text()
        assert "rgba(ff2e2eff)" in conf
        assert "#FF2E2E" in (paths.waybar_dir() / "style.css").read_text()
        assert ">>> hyprtheme hyprland.conf >>>" in (paths.hypr_dir() / "hyprland.conf").read_text()
        if src.exists():
            assert str(wp_dir / "sakura.jpg") in (paths.hypr_dir() / "hyprlock.conf").read_text()
        shoot_pages(list(PAGES), "", s3_edit_and_save)

    def s3_edit_and_save() -> None:
        win = app.window
        state = app.state
        assert win is not None and state is not None
        rows = win.pages["colors"].rows
        rows["primary"].entry.set_text("#ABCDEF")
        rows["primary"]._on_entry(rows["primary"].entry)
        assert state.working.colors["primary"] == "#ABCDEF"
        assert rows["primary"].rgb_label.get_text().split() == ["171", "205", "239"]
        assert state.dirty
        css = win.pages["colors"].preview._css(state.working)
        assert ".pv-launcher-btn { color: #ABCDEF;" in css
        assert ".pv-vol { color: #ABCDEF;" in css
        slider = win.pages["effects"].sliders["blur"]
        slider.scale.set_value(25)
        assert state.working.effects["blur"] == 25
        toggle = win.pages["effects"].toggles["glass"]
        toggle.switch.set_active(False)
        assert state.working.effects["glass"] is False
        rows["secondary"].entry.set_text("not-a-color")
        rows["secondary"]._on_entry(rows["secondary"].entry)
        assert rows["secondary"].entry.has_css_class("error")
        assert state.working.colors["secondary"] == "#FF7A00"
        win._save_with_name("GUI Custom")
        saved = paths.user_themes_dir() / "gui-custom.json"
        assert saved.exists()
        assert not state.dirty
        assert any(r.id == "gui-custom" and r.kind == "user" for r in state.themes())
        dest = state.export_file(fake_home / "exported")
        assert dest is not None and dest.suffix == ".hyprtheme" and dest.exists()
        imported = state.import_file(dest)
        assert imported is not None and imported.name == "GUI Custom" and imported.id == "gui-custom-2"
        shoot_pages(["themes", "colors"], "custom-", s4_rollback)

    def s4_rollback() -> None:
        assert app.state is not None
        app.state.rollback()
        when_idle(s5_check_rollback)

    def s5_check_rollback() -> None:
        state = app.state
        assert state is not None
        assert state.applied() is None
        assert not (paths.hypr_dir() / "hyprtheme.conf").exists()
        assert ">>> hyprtheme" not in (paths.hypr_dir() / "hyprland.conf").read_text()
        results["done"] = True
        app.quit()

    GLib.timeout_add(800, step, s1_load_red)
    GLib.timeout_add(90000, lambda: (errors.append("timeout"), app.quit(), False)[2])
    app.run([])
    assert not errors, errors
    assert results.get("done") is True
