"""Wallpaper daemon management (swww preferred, hyprpaper fallback).

Wallpapers are never assumed to exist: every operation checks the file and
reports instead of failing hard.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .components import is_process_running
from .generator import detect_hyprpaper_syntax, resolve_wallpaper
from .reload import spawn_detached
from .settings import Settings
from .theme import Theme

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".jxl", ".bmp", ".gif", ".avif"}


@dataclass
class WallpaperResult:
    ok: bool
    backend: str
    message: str


def _run(cmd: list[str], timeout: float = 10.0) -> tuple[bool, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError:
        return False, f"{cmd[0]} not found"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    return proc.returncode == 0, (proc.stdout or proc.stderr or "").strip()


def is_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES


def wallpaper_search_dirs() -> list[Path]:
    dirs = [paths.user_wallpapers_dir(), paths.app_data_dir() / "wallpapers", paths.pictures_dir() / "Wallpapers", paths.pictures_dir()]
    assets = paths.assets_dir()
    if assets:
        dirs.append(assets / "wallpapers")
    out: list[Path] = []
    for d in dirs:
        if d.is_dir() and d not in out:
            out.append(d)
    return out


def list_wallpapers(extra_dirs: list[Path] | None = None) -> list[Path]:
    found: list[Path] = []
    for d in [*(extra_dirs or []), *wallpaper_search_dirs()]:
        try:
            for p in sorted(d.iterdir()):
                if is_image(p) and p not in found:
                    found.append(p)
        except OSError:
            continue
    return found


class WallpaperManager:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()

    # -- backend selection -----------------------------------------------------------

    def backend(self) -> str | None:
        pref = self.settings.wallpaper_backend
        if pref == "off":
            return None
        if pref in ("swww", "hyprpaper"):
            return pref if shutil.which(pref) else None
        if shutil.which("swww"):
            return "swww"
        if shutil.which("hyprpaper"):
            return "hyprpaper"
        return None

    # -- state -----------------------------------------------------------------------

    def save_state(self, theme: Theme, path: Path) -> None:
        state = {
            "path": str(path),
            "transition": theme.wallpaper.get("transition", "grow"),
            "duration": theme.wallpaper.get("duration", 1.5),
            "fit": theme.wallpaper.get("fit", "crop"),
            "fill_color": theme.wallpaper.get("fill_color"),
            "theme": theme.id,
            "set_at": time.time(),
        }
        f = paths.wallpaper_state_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def load_state(self) -> dict | None:
        f = paths.wallpaper_state_file()
        if not f.exists():
            return None
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    # -- apply -----------------------------------------------------------------------

    def apply(self, theme: Theme) -> WallpaperResult:
        backend = self.backend()
        if backend is None:
            if self.settings.wallpaper_backend == "off":
                return WallpaperResult(True, "none", "wallpaper backend disabled")
            return WallpaperResult(False, "none", "no wallpaper daemon found (install swww or hyprpaper)")
        path = resolve_wallpaper(theme)
        if path is None:
            ref = theme.wallpaper.get("path")
            if not ref:
                return WallpaperResult(True, backend, "theme has no wallpaper")
            return WallpaperResult(False, backend, f"wallpaper not found: {ref}")
        result = self.set(
            path,
            backend=backend,
            transition=str(theme.wallpaper.get("transition", "grow")),
            duration=float(theme.wallpaper.get("duration", 1.5)),
            fit=str(theme.wallpaper.get("fit", "crop")),
            fill_color=theme.wallpaper.get("fill_color"),
        )
        if result.ok:
            self.save_state(theme, path)
        return result

    def restore(self) -> WallpaperResult:
        """Re-apply the last wallpaper (used by the login hook)."""
        state = self.load_state()
        if not state or not state.get("path"):
            return WallpaperResult(True, "none", "no wallpaper to restore")
        backend = self.backend()
        if backend is None:
            return WallpaperResult(False, "none", "no wallpaper daemon found")
        path = Path(state["path"])
        if not path.is_file():
            return WallpaperResult(False, backend, f"wallpaper missing: {path}")
        return self.set(
            path,
            backend=backend,
            transition="simple",
            duration=0.0,
            fit=str(state.get("fit", "crop")),
            fill_color=state.get("fill_color"),
            quiet=True,
        )

    def set(
        self,
        path: Path,
        *,
        backend: str | None = None,
        transition: str = "grow",
        duration: float = 1.5,
        fit: str = "crop",
        fill_color: str | None = None,
        quiet: bool = False,
    ) -> WallpaperResult:
        backend = backend or self.backend()
        if backend is None:
            return WallpaperResult(False, "none", "no wallpaper daemon found")
        if not path.is_file():
            return WallpaperResult(False, backend, f"not a file: {path}")
        if backend == "swww":
            return self._set_swww(path, transition, duration, fit, fill_color)
        return self._set_hyprpaper(path, fit)

    # -- swww ------------------------------------------------------------------------

    def _ensure_swww_daemon(self) -> bool:
        ok, _ = _run(["swww", "query"], timeout=3)
        if ok:
            return True
        if not shutil.which("swww-daemon"):
            return False
        spawn_detached(["swww-daemon"])
        for _ in range(20):
            time.sleep(0.1)
            ok, _ = _run(["swww", "query"], timeout=3)
            if ok:
                return True
        return False

    def _set_swww(self, path: Path, transition: str, duration: float, fit: str, fill_color: str | None) -> WallpaperResult:
        if not self._ensure_swww_daemon():
            return WallpaperResult(False, "swww", "could not start swww-daemon (is a Wayland session running?)")
        cmd = ["swww", "img", str(path), "--resize", fit if fit in ("crop", "fit", "no", "stretch") else "crop"]
        if transition == "simple" or duration <= 0:
            cmd += ["--transition-type", "simple", "--transition-step", "255"]
        else:
            cmd += ["--transition-type", transition, "--transition-duration", f"{duration:g}", "--transition-fps", "60"]
        if fill_color:
            cmd += ["--fill-color", fill_color.lstrip("#")]
        ok, out = _run(cmd, timeout=15)
        return WallpaperResult(ok, "swww", out or " ".join(shlex.quote(c) for c in cmd))

    # -- hyprpaper -------------------------------------------------------------------

    def _set_hyprpaper(self, path: Path, fit: str) -> WallpaperResult:
        if is_process_running("hyprpaper") is False:
            spawn_detached(["hyprpaper"])
            time.sleep(0.5)
        if not shutil.which("hyprctl"):
            return WallpaperResult(False, "hyprpaper", "hyprctl not found")
        syntax = detect_hyprpaper_syntax(self.settings)
        if syntax == "legacy":
            _run(["hyprctl", "hyprpaper", "unload", "all"], timeout=5)
            ok, out = _run(["hyprctl", "hyprpaper", "preload", str(path)], timeout=15)
            if not ok:
                return WallpaperResult(False, "hyprpaper", out)
            ok, out = _run(["hyprctl", "hyprpaper", "wallpaper", f",{path}"], timeout=10)
            return WallpaperResult(ok, "hyprpaper", out or "wallpaper set")
        fit_mode = {"crop": "cover", "fit": "contain", "no": "fill", "stretch": "fill"}.get(fit, "cover")
        ok, out = _run(["hyprctl", "hyprpaper", "wallpaper", f", {path}, {fit_mode}"], timeout=15)
        return WallpaperResult(ok, "hyprpaper", out or "wallpaper set")
