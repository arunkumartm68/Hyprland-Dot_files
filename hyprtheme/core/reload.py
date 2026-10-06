"""Process / reload manager.

After new configs are written the running components are asked to reload
so the desktop changes immediately.  Nothing here is fatal: a component that
is not installed or not running is simply skipped and reported.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field

from .components import hyprland_running, is_process_running


@dataclass
class ReloadResult:
    component: str
    ok: bool
    message: str


@dataclass
class ReloadReport:
    results: list[ReloadResult] = field(default_factory=list)

    def add(self, component: str, ok: bool, message: str) -> None:
        self.results.append(ReloadResult(component, ok, message))

    @property
    def failures(self) -> list[ReloadResult]:
        return [r for r in self.results if not r.ok]


def _run(cmd: list[str], timeout: float = 5.0) -> tuple[bool, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError:
        return False, f"{cmd[0]} not found"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    out = (proc.stdout or proc.stderr or "").strip()
    return proc.returncode == 0, out


def _signal(process: str, signal_name: str) -> tuple[bool, str]:
    if not shutil.which(process):
        return True, f"{process} is not installed"
    if not shutil.which("pkill"):
        return True, f"pkill not available; restart {process} manually"
    ok, out = _run(["pkill", f"-{signal_name}", "-x", process])
    if ok:
        return True, f"sent {signal_name} to {process}"
    return True, out or f"{process} is not running"


def spawn_detached(cmd: list[str]) -> bool:
    """Start a long-running process without tying it to our lifetime."""
    try:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


class ReloadManager:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def reload(self, components: list[str]) -> ReloadReport:
        report = ReloadReport()
        if not self.enabled:
            for comp in components:
                report.add(comp, True, "reload disabled in settings")
            return report
        for comp in components:
            handler = getattr(self, f"_reload_{comp}", None)
            if handler is None:
                report.add(comp, True, "nothing to reload")
                continue
            try:
                ok, msg = handler()
            except Exception as exc:  # pragma: no cover - defensive
                ok, msg = False, str(exc)
            report.add(comp, ok, msg)
        return report

    # -- components ---------------------------------------------------------------

    def _reload_hyprland(self) -> tuple[bool, str]:
        if not hyprland_running():
            return True, "Hyprland is not running (config will load at next login)"
        if not shutil.which("hyprctl"):
            return False, "hyprctl not found"
        ok, out = _run(["hyprctl", "reload"])
        return ok, out or "hyprctl reload"

    def _reload_waybar(self) -> tuple[bool, str]:
        running = is_process_running("waybar")
        if running is False:
            return True, "Waybar is not running"
        return _signal("waybar", "SIGUSR2")

    def _reload_kitty(self) -> tuple[bool, str]:
        running = is_process_running("kitty")
        if running is False:
            return True, "no Kitty instance running (new windows use the theme)"
        return _signal("kitty", "SIGUSR1")

    def _reload_swaync(self) -> tuple[bool, str]:
        if not shutil.which("swaync"):
            return True, "SwayNC is not installed"
        if is_process_running("swaync") is False:
            return True, "SwayNC is not running"
        if not shutil.which("swaync-client"):
            return False, "swaync-client not found"
        ok1, out1 = _run(["swaync-client", "--reload-css"])
        ok2, out2 = _run(["swaync-client", "--reload-config"])
        return ok1 and ok2, (out1 or out2 or "swaync reloaded").strip()

    def _reload_rofi(self) -> tuple[bool, str]:
        return True, "Rofi reads the theme on launch"

    def _reload_hyprlock(self) -> tuple[bool, str]:
        return True, "Hyprlock reads the theme on launch"

    def _reload_wlogout(self) -> tuple[bool, str]:
        return True, "Wlogout reads the theme on launch"

    def _reload_wallpaper(self) -> tuple[bool, str]:
        # Handled by WallpaperManager (needs theme data); nothing to signal here.
        return True, "wallpaper handled separately"


def environment_has_wayland_display() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY"))
