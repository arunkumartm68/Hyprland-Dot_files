"""Detection of the desktop components HyprTheme can theme.

Detection never raises: a missing optional component is reported, not fatal.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field

INSTALLED = "installed"
MISSING = "missing"
ERROR = "error"


@dataclass
class ComponentInfo:
    key: str
    label: str
    binary: str
    description: str
    required: bool = False
    status: str = MISSING
    path: str | None = None
    version: str | None = None
    running: bool | None = None
    message: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def installed(self) -> bool:
        return self.status == INSTALLED

    @property
    def icon(self) -> str:
        return {INSTALLED: "✓", MISSING: "⚠", ERROR: "✕"}[self.status]

    @property
    def status_label(self) -> str:
        if self.status == INSTALLED:
            if self.running is True:
                return "Installed · running"
            if self.running is False:
                return "Installed · not running"
            return "Installed"
        if self.status == MISSING:
            return "Not installed"
        return "Error"


# key, label, binary, description, required, process-name (for running detection)
COMPONENT_SPECS: list[tuple[str, str, str, str, bool, str | None]] = [
    ("hyprland", "Hyprland", "Hyprland", "Wayland compositor", True, "Hyprland"),
    ("waybar", "Waybar", "waybar", "Status bar", False, "waybar"),
    ("kitty", "Kitty", "kitty", "Terminal emulator", False, "kitty"),
    ("rofi", "Rofi", "rofi", "Application launcher (rofi-wayland)", False, None),
    ("swaync", "SwayNC", "swaync", "Notification center", False, "swaync"),
    ("hyprlock", "Hyprlock", "hyprlock", "Lock screen", False, None),
    ("wlogout", "Wlogout", "wlogout", "Logout menu", False, None),
    ("swww", "swww", "swww", "Wallpaper daemon (preferred)", False, "swww-daemon"),
    ("hyprpaper", "Hyprpaper", "hyprpaper", "Wallpaper daemon (fallback)", False, "hyprpaper"),
]


def _run(cmd: list[str], timeout: float = 3.0) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return proc.returncode, (proc.stdout or proc.stderr or "").strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, str(exc)


def is_process_running(name: str) -> bool | None:
    """Best-effort check using ``pgrep``; returns None when it cannot be determined."""
    if not shutil.which("pgrep"):
        return None
    code, _ = _run(["pgrep", "-x", name], timeout=2.0)
    if code == 0:
        return True
    if code == 1:
        return False
    return None


def _version_of(binary: str) -> str | None:
    code, out = _run([binary, "--version"])
    if code != 0 or not out:
        code, out = _run([binary, "-v"])
    if code != 0 or not out:
        return None
    first = out.splitlines()[0].strip()
    return first[:60]


def hyprland_running() -> bool:
    return bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))


def detect(component: str, *, with_version: bool = True) -> ComponentInfo:
    try:
        key, label, binary, description, required, proc = next(spec for spec in COMPONENT_SPECS if spec[0] == component)
    except StopIteration:
        raise KeyError(f"unknown component {component!r}") from None
    info = ComponentInfo(key=key, label=label, binary=binary, description=description, required=required)
    try:
        path = shutil.which(binary)
        if key == "hyprland" and path is None:
            path = shutil.which("hyprland")
        if path is None:
            info.status = MISSING
            info.message = f"'{binary}' not found in PATH"
            if key == "hyprland":
                info.running = hyprland_running()
                if info.running:
                    # Running inside Hyprland but the binary is not on PATH (unusual packaging).
                    info.status = INSTALLED
                    info.message = "detected via HYPRLAND_INSTANCE_SIGNATURE"
            return info
        info.status = INSTALLED
        info.path = path
        if with_version and key not in ("hyprland",):
            info.version = _version_of(binary)
        elif with_version and key == "hyprland" and shutil.which("hyprctl") and hyprland_running():
            code, out = _run(["hyprctl", "version"], timeout=3.0)
            if code == 0:
                for line in out.splitlines():
                    if line.lower().startswith(("tag:", "hyprland")):
                        info.version = line.strip()[:60]
                        break
        if key == "hyprland":
            info.running = hyprland_running()
        elif proc:
            info.running = is_process_running(proc)
    except Exception as exc:  # pragma: no cover - defensive
        info.status = ERROR
        info.message = str(exc)
    return info


def detect_all(*, with_version: bool = True) -> dict[str, ComponentInfo]:
    return {spec[0]: detect(spec[0], with_version=with_version) for spec in COMPONENT_SPECS}


def available_wallpaper_backends() -> list[str]:
    backends: list[str] = []
    if shutil.which("swww"):
        backends.append("swww")
    if shutil.which("hyprpaper"):
        backends.append("hyprpaper")
    return backends
