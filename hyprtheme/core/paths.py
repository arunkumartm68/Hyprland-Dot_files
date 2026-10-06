"""XDG-aware path resolution.

Nothing in HyprTheme hard-codes a home directory.  Every location is derived
from the XDG base-directory environment variables with the standard fallbacks.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_DIRNAME = "hyprtheme"


def _xdg(var: str, fallback: str) -> Path:
    value = os.environ.get(var)
    if value:
        return Path(value).expanduser()
    return Path.home() / fallback


def home() -> Path:
    return Path(os.environ.get("HOME") or Path.home())


def config_home() -> Path:
    """$XDG_CONFIG_HOME (default ~/.config)."""
    return _xdg("XDG_CONFIG_HOME", ".config")


def data_home() -> Path:
    """$XDG_DATA_HOME (default ~/.local/share)."""
    return _xdg("XDG_DATA_HOME", ".local/share")


def state_home() -> Path:
    """$XDG_STATE_HOME (default ~/.local/state)."""
    return _xdg("XDG_STATE_HOME", ".local/state")


def cache_home() -> Path:
    """$XDG_CACHE_HOME (default ~/.cache)."""
    return _xdg("XDG_CACHE_HOME", ".cache")


def pictures_dir() -> Path:
    """The user's pictures directory (XDG user dir or ~/Pictures)."""
    user_dirs = config_home() / "user-dirs.dirs"
    if user_dirs.exists():
        try:
            for line in user_dirs.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("XDG_PICTURES_DIR="):
                    raw = line.split("=", 1)[1].strip().strip('"')
                    return Path(os.path.expandvars(raw)).expanduser()
        except OSError:
            pass
    return home() / "Pictures"


# --- HyprTheme's own directories -------------------------------------------------


def app_config_dir() -> Path:
    """~/.config/hyprtheme - settings, user themes, wallpapers."""
    return config_home() / APP_DIRNAME


def user_themes_dir() -> Path:
    return app_config_dir() / "themes"


def user_wallpapers_dir() -> Path:
    return app_config_dir() / "wallpapers"


def settings_file() -> Path:
    return app_config_dir() / "settings.json"


def app_data_dir() -> Path:
    """~/.local/share/hyprtheme - installed presets, templates, assets."""
    return data_home() / APP_DIRNAME


def app_state_dir() -> Path:
    """~/.local/state/hyprtheme - current theme, backups, logs."""
    return state_home() / APP_DIRNAME


def current_theme_file() -> Path:
    return app_state_dir() / "current.json"


def backups_dir() -> Path:
    return app_state_dir() / "backups"


def history_file() -> Path:
    return app_state_dir() / "history.json"


def wallpaper_state_file() -> Path:
    return app_state_dir() / "wallpaper.json"


# --- Repository / installed resource locations -----------------------------------


def package_root() -> Path:
    """Directory that contains the ``hyprtheme`` python package."""
    return Path(__file__).resolve().parent.parent.parent


def resource_dirs() -> list[Path]:
    """Candidate locations for presets/templates, in priority order.

    1. $HYPRTHEME_RESOURCES (explicit override, used by tests and dev runs)
    2. the source checkout next to this package (running from the repo)
    3. $XDG_DATA_HOME/hyprtheme (user install)
    4. /usr/local/share/hyprtheme and /usr/share/hyprtheme (system install)
    """
    dirs: list[Path] = []
    override = os.environ.get("HYPRTHEME_RESOURCES")
    if override:
        dirs.append(Path(override).expanduser())
    dirs.append(package_root())
    dirs.append(app_data_dir())
    dirs.append(Path("/usr/local/share") / APP_DIRNAME)
    dirs.append(Path("/usr/share") / APP_DIRNAME)
    seen: set[Path] = set()
    unique: list[Path] = []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique


def find_resource_dir(name: str) -> Path | None:
    """Locate a resource directory such as ``templates`` or ``themes/presets``."""
    for base in resource_dirs():
        candidate = base / name
        if candidate.is_dir():
            return candidate
    return None


def presets_dir() -> Path | None:
    return find_resource_dir("themes/presets")


def templates_dir() -> Path | None:
    return find_resource_dir("templates")


def assets_dir() -> Path | None:
    return find_resource_dir("assets")


# --- Target component config locations -------------------------------------------


def hypr_dir() -> Path:
    return config_home() / "hypr"


def waybar_dir() -> Path:
    return config_home() / "waybar"


def kitty_dir() -> Path:
    return config_home() / "kitty"


def rofi_dir() -> Path:
    return config_home() / "rofi"


def swaync_dir() -> Path:
    return config_home() / "swaync"


def wlogout_dir() -> Path:
    return config_home() / "wlogout"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def display_path(path: Path | str) -> str:
    """Render a path with ``~`` for display purposes."""
    p = str(path)
    h = str(home())
    if p.startswith(h):
        return "~" + p[len(h) :]
    return p
