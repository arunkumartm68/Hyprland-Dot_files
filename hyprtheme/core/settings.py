"""Application settings (``~/.config/hyprtheme/settings.json``).

Settings control *how* HyprTheme integrates with each component, not what
the theme looks like - that lives in the theme itself.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import paths

# Integration modes:
#   managed   - HyprTheme writes the component's full configuration (after a backup)
#   variables - HyprTheme only writes a colors/variables file that the user can
#               include from their own configuration
#   off       - component is never touched
INTEGRATION_MODES = ["managed", "variables", "off"]
WALLPAPER_BACKENDS = ["auto", "swww", "hyprpaper", "off"]

DEFAULT_SETTINGS: dict[str, Any] = {
    "integration": {
        "hyprland": "managed",
        "waybar": "managed",
        "kitty": "managed",
        "rofi": "managed",
        "swaync": "managed",
        "hyprlock": "managed",
        "wlogout": "managed",
    },
    "wallpaper_backend": "auto",
    "reload_on_apply": True,
    "backup_limit": 25,
    "confirm_apply": False,
    "preview_scale": 1.0,
    "last_page": "dashboard",
}


@dataclass
class Settings:
    data: dict[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULT_SETTINGS))
    path: Path = field(default_factory=paths.settings_file)

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        p = path or paths.settings_file()
        data = copy.deepcopy(DEFAULT_SETTINGS)
        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for key, value in raw.items():
                        if key == "integration" and isinstance(value, dict):
                            for comp, mode in value.items():
                                if mode in INTEGRATION_MODES and comp in data["integration"]:
                                    data["integration"][comp] = mode
                        else:
                            data[key] = value
            except (OSError, json.JSONDecodeError):
                pass
        if data.get("wallpaper_backend") not in WALLPAPER_BACKENDS:
            data["wallpaper_backend"] = "auto"
        return cls(data=data, path=p)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    # --- accessors ---------------------------------------------------------------

    def integration(self, component: str) -> str:
        if component == "wallpaper":
            return "off" if self.data.get("wallpaper_backend") == "off" else "managed"
        return str(self.data.get("integration", {}).get(component, "managed"))

    def set_integration(self, component: str, mode: str) -> None:
        if mode not in INTEGRATION_MODES:
            raise ValueError(f"unknown integration mode {mode!r}")
        self.data.setdefault("integration", {})[component] = mode

    @property
    def wallpaper_backend(self) -> str:
        return str(self.data.get("wallpaper_backend", "auto"))

    @wallpaper_backend.setter
    def wallpaper_backend(self, value: str) -> None:
        if value not in WALLPAPER_BACKENDS:
            raise ValueError(f"unknown wallpaper backend {value!r}")
        self.data["wallpaper_backend"] = value

    @property
    def reload_on_apply(self) -> bool:
        return bool(self.data.get("reload_on_apply", True))

    @reload_on_apply.setter
    def reload_on_apply(self, value: bool) -> None:
        self.data["reload_on_apply"] = bool(value)

    @property
    def backup_limit(self) -> int:
        try:
            return max(1, int(self.data.get("backup_limit", 25)))
        except (TypeError, ValueError):
            return 25

    @backup_limit.setter
    def backup_limit(self, value: int) -> None:
        self.data["backup_limit"] = max(1, int(value))

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
