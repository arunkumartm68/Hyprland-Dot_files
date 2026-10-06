"""Observable application state shared by every page.

The state owns one :class:`ThemeEngine` and a *working* theme (the editable
copy shown in the preview).  Pages mutate the working theme through the
setters here and react to the ``changed`` signal; nothing else is shared.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gi.repository import GLib, GObject

from ..core.components import ComponentInfo
from ..core.engine import ApplyResult, EngineError, ThemeEngine, ThemeRef
from ..core.settings import Settings
from ..core.theme import COLOR_NAMES, Theme, ThemeError


class AppState(GObject.Object):
    __gsignals__ = {
        # the working theme changed (arg: what changed - "color", "effect", "wallpaper", "component", "theme", "font")
        "changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        # a theme was applied / rolled back / reset: the desktop state changed
        "applied": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # the list of saved themes changed
        "themes-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # component detection finished
        "components-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # a long operation started / finished (arg: busy)
        "busy": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
        # user facing message (arg: text, is_error)
        "message": (GObject.SignalFlags.RUN_FIRST, None, (str, bool)),
    }

    def __init__(self, engine: ThemeEngine | None = None):
        super().__init__()
        self.engine = engine or ThemeEngine()
        self.settings: Settings = self.engine.settings
        self.components: dict[str, ComponentInfo] = {}
        current = self.engine.current()
        base = current.theme if current else self.engine.default_theme()
        self.working: Theme = base.copy()
        self.base_fingerprint = base.fingerprint()
        self.base_name = base.name
        self._busy = False
        self.refresh_components_async()

    # --- derived -------------------------------------------------------------------

    @property
    def dirty(self) -> bool:
        return self.working.fingerprint() != self.base_fingerprint or self.working.name != self.base_name

    @property
    def busy(self) -> bool:
        return self._busy

    def applied(self):
        return self.engine.current()

    def themes(self) -> list[ThemeRef]:
        return self.engine.list_themes()

    # --- working theme edits -------------------------------------------------------

    def load_theme(self, theme: Theme) -> None:
        self.working = theme.copy()
        self.base_fingerprint = theme.fingerprint()
        self.base_name = theme.name
        self.emit("changed", "theme")

    def set_color(self, key: str, value: str) -> bool:
        if key not in COLOR_NAMES:
            return False
        try:
            self.working.set_color(key, value)
        except (ThemeError, ValueError):
            return False
        self.emit("changed", "color")
        return True

    def set_effect(self, key: str, value: Any) -> None:
        if self.working.effects.get(key) == value:
            return
        self.working.effects[key] = value
        self.emit("changed", "effect")

    def set_wallpaper(self, path: str | None = None, **options: Any) -> None:
        if path is not None or "path" in options:
            self.working.wallpaper["path"] = path if path is not None else options.pop("path")
        for key, value in options.items():
            self.working.wallpaper[key] = value
        self.emit("changed", "wallpaper")

    def set_component(self, component: str, key: str, value: Any) -> None:
        self.working.components.setdefault(component, {})[key] = value
        self.emit("changed", "component")

    def set_font(self, key: str, value: Any) -> None:
        self.working.fonts[key] = value
        self.emit("changed", "font")

    def set_name(self, name: str) -> None:
        self.working.name = name
        self.emit("changed", "theme")

    # --- engine operations ---------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.emit("busy", busy)

    def _run_async(self, work: Callable[[], Any], done: Callable[[Any, Exception | None], None]) -> None:
        self._set_busy(True)

        def runner() -> None:
            result: Any = None
            error: Exception | None = None
            try:
                result = work()
            except Exception as exc:
                error = exc

            def finish() -> bool:
                self._set_busy(False)
                done(result, error)
                return False

            GLib.idle_add(finish)

        threading.Thread(target=runner, daemon=True).start()

    def apply(self, on_done: Callable[[ApplyResult | None, Exception | None], None] | None = None) -> None:
        theme = self.working.copy()

        def done(result: ApplyResult | None, error: Exception | None) -> None:
            if error is None and result is not None:
                self.base_fingerprint = theme.fingerprint()
                self.base_name = theme.name
                self.working.source = theme.source
                self.emit("applied")
                summary = result.summary()
                if result.wallpaper and not result.wallpaper.ok:
                    self.emit("message", f"Applied {theme.name}, but wallpaper failed: {result.wallpaper.message}", True)
                elif result.reload and result.reload.failures:
                    failed = ", ".join(f"{r.component}: {r.message}" for r in result.reload.failures)
                    self.emit("message", f"Applied {theme.name}; reload issues: {failed}", True)
                else:
                    self.emit("message", f"Applied {theme.name} — {summary}", False)
            else:
                self.emit("message", f"Apply failed: {error}", True)
            if on_done:
                on_done(result, error)

        self._run_async(lambda: self.engine.apply(theme), done)

    def save(self, name: str | None = None) -> Path | None:
        try:
            path = self.engine.save(self.working, name)
        except EngineError as exc:
            self.emit("message", str(exc), True)
            return None
        self.base_fingerprint = self.working.fingerprint()
        self.base_name = self.working.name
        self.emit("themes-changed")
        self.emit("changed", "theme")
        self.emit("message", f"Saved theme '{self.working.name}'", False)
        return path

    def delete_theme(self, ref: ThemeRef) -> None:
        try:
            self.engine.delete(ref.id)
        except EngineError as exc:
            self.emit("message", str(exc), True)
            return
        self.emit("themes-changed")
        self.emit("message", f"Deleted '{ref.name}'", False)

    def rollback(self) -> None:
        def done(result: Any, error: Exception | None) -> None:
            if error:
                self.emit("message", f"Rollback failed: {error}", True)
                return
            _backup, previous = result
            base = previous or self.engine.default_theme()
            self.load_theme(base)
            self.emit("applied")
            self.emit("message", f"Rolled back to {previous.name if previous else 'the previous configuration'}", False)

        self._run_async(self.engine.rollback, done)

    def reset_working(self) -> None:
        """Discard edits: reload the applied theme (or the default preset)."""
        current = self.engine.current()
        base = current.theme if current else self.engine.default_theme()
        self.load_theme(base)
        self.emit("message", "Discarded unsaved changes", False)

    def reset_desktop(self, original: bool = False) -> None:
        def done(result: Any, error: Exception | None) -> None:
            if error:
                self.emit("message", f"Reset failed: {error}", True)
                return
            current = self.engine.current()
            self.load_theme(current.theme if current else self.engine.default_theme())
            self.emit("applied")
            self.emit("message", "Restored the original configuration" if original else "Reset to the default theme", False)

        self._run_async(lambda: self.engine.reset(original=original), done)

    def import_file(self, path: Path) -> Theme | None:
        try:
            theme = self.engine.import_file(path)
        except Exception as exc:
            self.emit("message", f"Import failed: {exc}", True)
            return None
        self.emit("themes-changed")
        self.load_theme(theme)
        self.emit("message", f"Imported '{theme.name}'", False)
        return theme

    def export_file(self, path: Path, embed_wallpaper: bool = False) -> Path | None:
        try:
            dest = self.engine.export(self.working, path, embed_wallpaper=embed_wallpaper)
        except Exception as exc:
            self.emit("message", f"Export failed: {exc}", True)
            return None
        self.emit("message", f"Exported to {dest.name}", False)
        return dest

    def restore_backup(self, backup_id: str) -> None:
        def done(_result: Any, error: Exception | None) -> None:
            if error:
                self.emit("message", f"Restore failed: {error}", True)
                return
            current = self.engine.current()
            if current:
                self.load_theme(current.theme)
            self.emit("applied")
            self.emit("message", f"Restored backup {backup_id}", False)

        self._run_async(lambda: self.engine.restore_backup(backup_id), done)

    def create_backup(self, label: str) -> None:
        try:
            backup = self.engine.create_backup(label)
        except Exception as exc:
            self.emit("message", f"Backup failed: {exc}", True)
            return
        self.emit("applied")
        self.emit("message", f"Created backup {backup.id}", False)

    def delete_backup(self, backup_id: str) -> None:
        try:
            self.engine.delete_backup(backup_id)
        except Exception as exc:
            self.emit("message", f"Delete failed: {exc}", True)
            return
        self.emit("applied")

    def refresh_components_async(self) -> None:
        def done(result: Any, error: Exception | None) -> None:
            if error is None and result:
                self.components = result
                self.emit("components-changed")

        self._run_async(lambda: self.engine.detect_components(with_version=True), done)

    def save_settings(self) -> None:
        try:
            self.settings.save()
            self.engine.backups.limit = self.settings.backup_limit
            self.engine._generator = None  # settings affect generation; rebuild lazily
        except OSError as exc:
            self.emit("message", f"Could not save settings: {exc}", True)
