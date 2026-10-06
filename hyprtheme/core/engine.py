"""The theme engine facade used by both the GUI and the CLI.

Everything a front-end needs is here: listing themes, applying, saving,
rolling back, importing/exporting and managing backups.  The engine owns no
UI state - it only reads and writes files under the XDG directories.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import paths
from .backup import Backup, BackupManager
from .components import ComponentInfo, detect_all
from .generator import Generator, GeneratorError, Plan
from .portable import export_theme, import_theme
from .reload import ReloadManager, ReloadReport
from .settings import Settings
from .theme import Theme, ThemeError, slugify
from .wallpaper import WallpaperManager, WallpaperResult

DEFAULT_PRESET = "cyan"


class EngineError(RuntimeError):
    pass


@dataclass
class ThemeRef:
    theme: Theme
    kind: str  # preset | user
    path: Path

    @property
    def id(self) -> str:
        return self.theme.id

    @property
    def name(self) -> str:
        return self.theme.name


@dataclass
class ApplyResult:
    theme: Theme
    plan: Plan
    written: list[Path] = field(default_factory=list)
    injected: list[Path] = field(default_factory=list)
    unchanged: list[Path] = field(default_factory=list)
    backup: Backup | None = None
    reload: ReloadReport | None = None
    wallpaper: WallpaperResult | None = None
    dry_run: bool = False

    @property
    def ok(self) -> bool:
        if self.reload and self.reload.failures:
            return False
        return not (self.wallpaper and not self.wallpaper.ok)

    def summary(self) -> str:
        parts = [f"{len(self.written)} file(s) written", f"{len(self.injected)} include line(s) ensured"]
        if self.unchanged:
            parts.append(f"{len(self.unchanged)} unchanged")
        if self.plan.skipped:
            parts.append("skipped: " + ", ".join(f"{k} ({v})" for k, v in self.plan.skipped.items()))
        return "; ".join(parts)


@dataclass
class CurrentState:
    theme: Theme
    applied_at: float
    source: str | None
    backup_id: str | None

    @property
    def applied_text(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.applied_at))


class ThemeEngine:
    def __init__(self, settings: Settings | None = None, *, templates_dir: Path | None = None, presets_dir: Path | None = None):
        self.settings = settings or Settings.load()
        self._templates_dir = templates_dir
        self._presets_dir = presets_dir
        self.backups = BackupManager(limit=self.settings.backup_limit)
        self.wallpapers = WallpaperManager(self.settings)
        self._generator: Generator | None = None

    # -- helpers ---------------------------------------------------------------------

    @property
    def generator(self) -> Generator:
        if self._generator is None:
            try:
                self._generator = Generator(self._templates_dir, self.settings)
            except GeneratorError as exc:
                raise EngineError(str(exc)) from exc
        return self._generator

    def presets_dir(self) -> Path | None:
        return self._presets_dir or paths.presets_dir()

    def user_themes_dir(self) -> Path:
        return paths.ensure_dir(paths.user_themes_dir())

    def detect_components(self, *, with_version: bool = True) -> dict[str, ComponentInfo]:
        return detect_all(with_version=with_version)

    # -- listing ---------------------------------------------------------------------

    def list_themes(self) -> list[ThemeRef]:
        refs: list[ThemeRef] = []
        presets = self.presets_dir()
        if presets and presets.is_dir():
            loaded: list[tuple[int, ThemeRef]] = []
            for p in sorted(presets.glob("*.json")):
                try:
                    theme = Theme.load(p)
                except ThemeError:
                    continue
                theme.preset = True
                order = 0
                with contextlib.suppress(OSError, ValueError, TypeError):
                    order = int(json.loads(p.read_text(encoding="utf-8")).get("order", 0))
                loaded.append((order, ThemeRef(theme, "preset", p)))
            loaded.sort(key=lambda item: (item[0], item[1].name.lower()))
            refs.extend(ref for _, ref in loaded)
        user_dir = self.user_themes_dir()
        for p in sorted(user_dir.glob("*.json"), key=lambda x: x.name.lower()):
            try:
                theme = Theme.load(p)
            except ThemeError:
                continue
            theme.preset = False
            refs.append(ThemeRef(theme, "user", p))
        return refs

    def find(self, query: str) -> ThemeRef | None:
        """Find by id, by name (case-insensitive) or by path."""
        q = query.strip()
        candidate = Path(q).expanduser()
        if candidate.suffix in (".json", ".hyprtheme") and candidate.is_file():
            try:
                theme = Theme.load(candidate)
            except ThemeError as exc:
                raise EngineError(str(exc)) from exc
            return ThemeRef(theme, "user", candidate)
        slug = slugify(q)
        for ref in self.list_themes():
            if ref.id == slug or ref.name.lower() == q.lower():
                return ref
        for ref in self.list_themes():
            if ref.id.startswith(slug):
                return ref
        return None

    def get(self, query: str) -> Theme:
        ref = self.find(query)
        if ref is None:
            raise EngineError(f"theme not found: {query!r}")
        return ref.theme

    def default_theme(self) -> Theme:
        ref = self.find(DEFAULT_PRESET)
        return ref.theme if ref else Theme.default("Default")

    # -- current state ---------------------------------------------------------------

    def current(self) -> CurrentState | None:
        f = paths.current_theme_file()
        if not f.exists():
            return None
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            theme = Theme.from_dict(data["theme"], strict=False)
            source = data.get("source")
            theme.source = Path(source) if source else None
            theme.preset = bool(data["theme"].get("preset", False))
            return CurrentState(theme, float(data.get("applied_at", 0)), source, data.get("backup_id"))
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _write_current(self, theme: Theme, backup_id: str | None) -> None:
        f = paths.current_theme_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "theme": theme.to_dict(),
            "applied_at": time.time(),
            "source": str(theme.source) if theme.source else None,
            "backup_id": backup_id,
        }
        tmp = f.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        tmp.replace(f)

    def _append_history(self, theme: Theme, backup_id: str | None) -> None:
        f = paths.history_file()
        history: list[dict[str, Any]] = []
        if f.exists():
            try:
                history = json.loads(f.read_text(encoding="utf-8"))
                if not isinstance(history, list):
                    history = []
            except (OSError, ValueError):
                history = []
        history.append({"theme": theme.name, "id": theme.id, "applied_at": time.time(), "backup_id": backup_id})
        history = history[-100:]
        f.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")

    def history(self) -> list[dict[str, Any]]:
        f = paths.history_file()
        if not f.exists():
            return []
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    # -- planning / preview ----------------------------------------------------------

    def plan(self, theme: Theme) -> Plan:
        try:
            return self.generator.plan(theme)
        except GeneratorError as exc:
            raise EngineError(str(exc)) from exc

    def preview_file(self, theme: Theme, relative_template: str) -> str:
        try:
            return self.generator.render_component(theme, relative_template)
        except GeneratorError as exc:
            raise EngineError(str(exc)) from exc

    # -- apply -----------------------------------------------------------------------

    def apply(self, theme: Theme, *, dry_run: bool = False, reload: bool | None = None, set_wallpaper: bool = True) -> ApplyResult:
        problems = theme.validate()
        if problems:
            raise EngineError("theme is invalid: " + "; ".join(problems))
        plan = self.plan(theme)
        result = ApplyResult(theme=theme, plan=plan, dry_run=dry_run)
        if dry_run:
            return result

        targets = plan.targets()
        previous = self.current()
        if not self.backups.has_initial():
            # First ever apply: keep a pristine copy of the user's configuration.
            self.backups.create(targets, label="original configuration (before HyprTheme)", kind="initial")
        result.backup = self.backups.create(
            targets,
            label=f"before applying {theme.name}",
            kind="apply",
            theme_name=theme.name,
            theme_id=theme.id,
            previous_theme=previous.theme.to_dict() if previous else None,
        )

        for gen in plan.files:
            if gen.only_if_missing and gen.path.exists():
                result.unchanged.append(gen.path)
                continue
            if gen.path.exists():
                try:
                    if gen.path.read_text(encoding="utf-8") == gen.content:
                        result.unchanged.append(gen.path)
                        continue
                except (OSError, UnicodeDecodeError):
                    pass
            self._write(gen.path, gen.content)
            if gen.executable:
                gen.path.chmod(0o755)
            result.written.append(gen.path)

        for inj in plan.injections:
            if not inj.path.exists():
                if not inj.create_if_missing:
                    plan.warnings.append(f"{inj.path} does not exist; skipped {inj.description}")
                    continue
                text = ""
            else:
                try:
                    text = inj.path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as exc:
                    plan.warnings.append(f"cannot read {inj.path}: {exc}")
                    continue
            updated = inj.apply_to(text)
            if updated != text:
                self._write(inj.path, updated)
                result.injected.append(inj.path)
            else:
                result.unchanged.append(inj.path)

        self._write_current(theme, result.backup.id)
        self._append_history(theme, result.backup.id)

        if set_wallpaper and theme.is_component_enabled("wallpaper") and "wallpaper" not in plan.skipped:
            result.wallpaper = self.wallpapers.apply(theme)
        elif set_wallpaper and "wallpaper" in plan.skipped and theme.wallpaper.get("path"):
            result.wallpaper = WallpaperResult(False, self.wallpapers.backend() or "none", plan.skipped["wallpaper"])

        do_reload = self.settings.reload_on_apply if reload is None else reload
        components = [c for c in plan.components() if c != "wallpaper"]
        result.reload = ReloadManager(enabled=do_reload).reload(components)
        return result

    @staticmethod
    def _write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".hyprtheme-tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)

    # -- saving ----------------------------------------------------------------------

    def save(self, theme: Theme, name: str | None = None, *, overwrite: bool = True) -> Path:
        """Save a theme into the user theme directory (presets are never modified)."""
        copy = theme.copy()
        if name:
            copy.name = name
            copy.id = slugify(name)
        copy.preset = False
        if not copy.id:
            copy.id = slugify(copy.name)
        problems = copy.validate()
        if problems:
            raise EngineError("theme is invalid: " + "; ".join(problems))
        target = self.user_themes_dir() / f"{copy.id}.json"
        presets = self.presets_dir()
        if presets and any(p.stem == copy.id for p in presets.glob("*.json")) and not name:
            # Saving a modified preset without a new name: store it as a user copy.
            copy.id = f"{copy.id}-custom"
            copy.name = f"{copy.name} (custom)"
            target = self.user_themes_dir() / f"{copy.id}.json"
        if target.exists() and not overwrite:
            raise EngineError(f"theme '{copy.name}' already exists")
        copy.save(target)
        theme.source = target
        theme.name, theme.id, theme.preset = copy.name, copy.id, False
        return target

    def delete(self, query: str) -> Path:
        ref = self.find(query)
        if ref is None:
            raise EngineError(f"theme not found: {query!r}")
        if ref.kind == "preset":
            raise EngineError("presets cannot be deleted")
        ref.path.unlink()
        return ref.path

    # -- rollback / reset ------------------------------------------------------------

    def rollback(self, *, reload: bool | None = None) -> tuple[Backup, Theme | None]:
        """Undo the last apply: restore the files it replaced and the previous theme state."""
        backup = self.backups.latest(kind="apply")
        if backup is None:
            raise EngineError("nothing to roll back")
        self.backups.restore(backup)
        previous: Theme | None = None
        if backup.previous_theme:
            try:
                previous = Theme.from_dict(backup.previous_theme, strict=False)
            except ThemeError:
                previous = None
        if previous is not None:
            self._write_current(previous, None)
            if previous.wallpaper.get("path"):
                self.wallpapers.apply(previous)
        else:
            f = paths.current_theme_file()
            if f.exists():
                f.unlink()
        # The restored snapshot is consumed: mark it so a second rollback goes further back.
        backup.kind = "rolled-back"
        (backup.path / "manifest.json").write_text(json.dumps(backup.to_dict(), indent=2) + "\n", encoding="utf-8")
        do_reload = self.settings.reload_on_apply if reload is None else reload
        ReloadManager(enabled=do_reload).reload([e.component for e in self._components_of(backup)])
        return backup, previous

    def _components_of(self, backup: Backup) -> list[Any]:
        class _C:
            def __init__(self, c: str):
                self.component = c

        comps: list[str] = []
        for entry in backup.entries:
            p = str(entry.original)
            for name in ("hypr", "waybar", "kitty", "rofi", "swaync", "wlogout"):
                if f"/{name}/" in p:
                    comp = {"hypr": "hyprland"}.get(name, name)
                    if comp not in comps:
                        comps.append(comp)
        if "hyprland" in comps and "hyprlock" not in comps:
            comps.append("hyprlock")
        return [_C(c) for c in comps]

    def reset(self, *, original: bool = False) -> ApplyResult | Backup:
        """Reset to the default preset, or (``original=True``) restore the pre-HyprTheme configs."""
        if original:
            initial = self.backups.latest(kind="initial")
            if initial is None:
                raise EngineError("no original-configuration backup exists yet")
            self.backups.restore(initial)
            f = paths.current_theme_file()
            if f.exists():
                f.unlink()
            ReloadManager(enabled=self.settings.reload_on_apply).reload(["hyprland", "waybar", "kitty", "swaync"])
            return initial
        return self.apply(self.default_theme())

    # -- import / export -------------------------------------------------------------

    def export(self, theme: Theme, destination: Path, *, embed_wallpaper: bool = False) -> Path:
        return export_theme(theme, destination, embed_wallpaper=embed_wallpaper)

    def import_file(self, source: Path, *, new_name: str | None = None, overwrite: bool = False) -> Theme:
        return import_theme(source, themes_dir=self.user_themes_dir(), new_name=new_name, overwrite=overwrite)

    # -- backups ---------------------------------------------------------------------

    def managed_paths(self, theme: Theme | None = None) -> list[Path]:
        if theme is None:
            current = self.current()
            theme = current.theme if current else self.default_theme()
        return self.plan(theme).targets()

    def create_backup(self, label: str = "manual backup") -> Backup:
        return self.backups.create(self.managed_paths(), label=label, kind="manual")

    def restore_backup(self, backup_id: str) -> Backup:
        backup = self.backups.get(backup_id)
        if backup is None:
            raise EngineError(f"backup not found: {backup_id}")
        self.backups.restore(backup)
        if backup.previous_theme:
            with contextlib.suppress(ThemeError):
                self._write_current(Theme.from_dict(backup.previous_theme, strict=False), None)
        ReloadManager(enabled=self.settings.reload_on_apply).reload([e.component for e in self._components_of(backup)])
        return backup

    def list_backups(self) -> list[Backup]:
        return self.backups.snapshots()

    def delete_backup(self, backup_id: str) -> None:
        self.backups.delete(backup_id)

    # -- misc ------------------------------------------------------------------------

    def copy_wallpaper_to_library(self, source: Path) -> Path:
        dest_dir = paths.ensure_dir(paths.user_wallpapers_dir())
        dest = dest_dir / source.name
        if dest.resolve() != source.resolve():
            shutil.copy2(source, dest)
        return dest
