"""The central theme definition.

One :class:`Theme` describes the whole desktop.  Every component config
(Hyprland, Waybar, Kitty, Rofi, SwayNC, Hyprlock, Wlogout, wallpaper daemon)
is generated from it, so this is the only thing a user ever edits.

The on-disk representation is plain JSON (``theme.json``, or ``.hyprtheme``
for portable exports) with the layout documented in ``docs/THEME_FORMAT.md``.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .colors import Color, ColorError, derive_ansi, is_valid_hex, normalize_hex

SCHEMA_VERSION = 1

# Ordered list of (key, label, description) for every themeable color.
COLOR_KEYS: list[tuple[str, str, str]] = [
    ("primary", "Primary", "Main accent used for borders, highlights and icons"),
    ("secondary", "Secondary", "Secondary accent used for gradients and hover states"),
    ("highlight", "Highlight", "Selection / focused item highlight"),
    ("background", "Background", "Desktop and window background"),
    ("surface", "Surface", "Panels, cards and bar background"),
    ("surface2", "Surface 2", "Raised elements on top of surfaces"),
    ("text", "Text", "Primary text color"),
    ("muted", "Muted Text", "Secondary / dimmed text"),
    ("border", "Border", "Panel and widget borders"),
    ("glow", "Glow", "Neon glow / shadow color"),
    ("gradient_start", "Gradient Start", "First stop of accent gradients"),
    ("gradient_end", "Gradient End", "Last stop of accent gradients"),
    ("notification", "Notification", "Notification accent"),
    ("success", "Success", "Positive state (connected, charged)"),
    ("warning", "Warning", "Warning state"),
    ("error", "Error", "Error / critical state"),
    ("battery", "Battery", "Battery widget accent"),
    ("system", "System", "System statistics accent"),
    ("media", "Media", "Music / media accent"),
    ("workspace_active", "Workspace Active", "Active workspace indicator"),
    ("workspace_inactive", "Workspace Inactive", "Inactive workspace indicator"),
    ("active_border", "Active Window Border", "Border of the focused window"),
    ("inactive_border", "Inactive Window Border", "Border of unfocused windows"),
]

COLOR_NAMES = [k for k, _, _ in COLOR_KEYS]

# Sliders: key, label, min, max, step, unit
EFFECT_SLIDERS: list[tuple[str, str, float, float, float, str]] = [
    ("opacity", "Transparency", 0.3, 1.0, 0.01, ""),
    ("blur", "Blur", 0, 40, 1, "px"),
    ("border_width", "Border Width", 0, 8, 1, "px"),
    ("radius", "Corner Radius", 0, 32, 1, "px"),
    ("glow", "Glow Intensity", 0.0, 1.0, 0.01, ""),
    ("animation_speed", "Animation Speed", 0.25, 3.0, 0.05, "x"),
    ("window_gaps", "Window Gaps", 0, 24, 1, "px"),
    ("gaps_out", "Outer Gaps", 0, 60, 1, "px"),
    ("gaps_in", "Inner Gaps", 0, 30, 1, "px"),
]

EFFECT_TOGGLES: list[tuple[str, str, str]] = [
    ("glass", "Glass Effect", "Translucent, blurred panel backgrounds"),
    ("neon_glow", "Neon Glow", "Glowing shadows around accents and windows"),
    ("animations", "Animations", "Enable Hyprland and widget animations"),
    ("gradient", "Gradient", "Use gradient accents (window borders, buttons)"),
    ("shadows", "Window Shadows", "Drop shadows under windows"),
    ("rainbow_border", "Rainbow Border", "Rotate the active-border gradient continuously"),
]

WALLPAPER_TRANSITIONS = ["simple", "fade", "left", "right", "top", "bottom", "wipe", "wave", "grow", "center", "any", "outer", "random"]
WALLPAPER_FIT_MODES = ["crop", "fit", "no", "stretch"]
COMPONENT_NAMES = ["hyprland", "waybar", "kitty", "rofi", "swaync", "hyprlock", "wlogout", "wallpaper"]

DEFAULT_COLORS: dict[str, str] = {
    "primary": "#00E5FF",
    "secondary": "#0077FF",
    "highlight": "#5CF2FF",
    "background": "#080A0F",
    "surface": "#11151D",
    "surface2": "#1A2030",
    "text": "#FFFFFF",
    "muted": "#8B95A7",
    "border": "#00E5FF",
    "glow": "#00E5FF",
    "gradient_start": "#00E5FF",
    "gradient_end": "#0077FF",
    "notification": "#00E5FF",
    "success": "#4DFF88",
    "warning": "#FFD166",
    "error": "#FF4D6D",
    "battery": "#4DFF88",
    "system": "#00E5FF",
    "media": "#FF6AD5",
    "workspace_active": "#00E5FF",
    "workspace_inactive": "#3A4457",
    "active_border": "#00E5FF",
    "inactive_border": "#2A3140",
}

DEFAULT_EFFECTS: dict[str, Any] = {
    "opacity": 0.85,
    "blur": 12,
    "border_width": 2,
    "radius": 14,
    "glow": 0.6,
    "animation_speed": 1.0,
    "window_gaps": 8,
    "gaps_out": 16,
    "gaps_in": 6,
    "glass": True,
    "neon_glow": True,
    "animations": True,
    "gradient": True,
    "shadows": True,
    "rainbow_border": False,
}

DEFAULT_WALLPAPER: dict[str, Any] = {
    "path": None,
    "transition": "grow",
    "duration": 1.5,
    "fit": "crop",
    "fill_color": None,
}

DEFAULT_FONTS: dict[str, Any] = {
    "ui": "Inter",
    "mono": "JetBrainsMono Nerd Font",
    "size": 13,
}

DEFAULT_COMPONENTS: dict[str, dict[str, Any]] = {
    "hyprland": {"enabled": True},
    "waybar": {
        "enabled": True,
        "position": "top",
        "height": 36,
        "margin": 8,
        "floating": True,
        "show_launcher": True,
        "show_music": True,
        "show_bluetooth": True,
        "show_system": True,
        "show_notifications": True,
        "launcher_icon": "",
        "launcher_command": "rofi -show drun",
        "clock_format": "%a %d %b  %I:%M %p",
    },
    "kitty": {
        "enabled": True,
        "font_size": 11,
        "cursor_shape": "beam",
        "ansi": {},
    },
    "rofi": {
        "enabled": True,
        "width": 640,
        "lines": 8,
        "columns": 1,
        "show_icons": True,
        "icon_theme": "Papirus-Dark",
        "prompt": "Search",
    },
    "swaync": {
        "enabled": True,
        "width": 420,
        "manage_config": True,
    },
    "hyprlock": {
        "enabled": True,
        "clock_24h": False,
        "show_user": True,
        "show_battery": True,
        "show_music": False,
        "blur_passes": 2,
    },
    "wlogout": {
        "enabled": True,
        "columns": 5,
        "button_size": 150,
    },
    "wallpaper": {"enabled": True},
}

_ID_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    slug = _ID_RE.sub("-", name.strip().lower()).strip("-")
    return slug or "theme"


class ThemeError(ValueError):
    """Raised for an invalid theme definition."""


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


@dataclass
class Theme:
    name: str = "Untitled"
    id: str = ""
    author: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    variant: str = "dark"
    preset: bool = False
    colors: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_COLORS))
    effects: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_EFFECTS))
    wallpaper: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_WALLPAPER))
    fonts: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_FONTS))
    components: dict[str, dict[str, Any]] = field(default_factory=lambda: copy.deepcopy(DEFAULT_COMPONENTS))
    source: Path | None = field(default=None, compare=False, repr=False)

    # --- construction ------------------------------------------------------------

    def __post_init__(self) -> None:
        if not self.id:
            self.id = slugify(self.name)

    @classmethod
    def default(cls, name: str = "Custom") -> Theme:
        return cls(name=name)

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, source: Path | None = None, strict: bool = True) -> Theme:
        if not isinstance(data, dict):
            raise ThemeError("theme must be a JSON object")
        schema = data.get("schema", SCHEMA_VERSION)
        if not isinstance(schema, int) or schema > SCHEMA_VERSION:
            raise ThemeError(f"unsupported theme schema version: {schema!r}")

        name = str(data.get("name") or "Untitled")
        colors = _deep_merge(DEFAULT_COLORS, {k: v for k, v in (data.get("colors") or {}).items()})
        effects = _deep_merge(DEFAULT_EFFECTS, data.get("effects") or {})
        wallpaper = _deep_merge(DEFAULT_WALLPAPER, data.get("wallpaper") or {})
        fonts = _deep_merge(DEFAULT_FONTS, data.get("fonts") or {})
        components = _deep_merge(DEFAULT_COMPONENTS, data.get("components") or {})

        theme = cls(
            name=name,
            id=str(data.get("id") or slugify(name)),
            author=str(data.get("author") or ""),
            description=str(data.get("description") or ""),
            tags=[str(t) for t in (data.get("tags") or [])],
            variant=str(data.get("variant") or "dark"),
            preset=bool(data.get("preset", False)),
            colors=colors,
            effects=effects,
            wallpaper=wallpaper,
            fonts=fonts,
            components=components,
            source=source,
        )
        problems = theme.validate()
        if problems and strict:
            raise ThemeError("; ".join(problems))
        theme.normalize()
        return theme

    @classmethod
    def load(cls, path: Path | str, *, strict: bool = True) -> Theme:
        p = Path(path)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ThemeError(f"{p}: invalid JSON ({exc})") from exc
        except OSError as exc:
            raise ThemeError(f"{p}: {exc}") from exc
        return cls.from_dict(data, source=p, strict=strict)

    # --- serialisation -----------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "name": self.name,
            "id": self.id,
            "author": self.author,
            "description": self.description,
            "tags": list(self.tags),
            "variant": self.variant,
            "preset": self.preset,
            "colors": dict(self.colors),
            "effects": copy.deepcopy(self.effects),
            "wallpaper": copy.deepcopy(self.wallpaper),
            "fonts": copy.deepcopy(self.fonts),
            "components": copy.deepcopy(self.components),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"

    def save(self, path: Path | str) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(self.to_json(), encoding="utf-8")
        tmp.replace(p)
        self.source = p
        return p

    def copy(self) -> Theme:
        clone = copy.deepcopy(self)
        clone.source = self.source
        return clone

    # --- validation --------------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of human readable problems (empty when valid)."""
        problems: list[str] = []
        if not self.name.strip():
            problems.append("name must not be empty")
        for key in COLOR_NAMES:
            value = self.colors.get(key)
            if not is_valid_hex(value):
                problems.append(f"colors.{key}: invalid hex color {value!r}")
        for key, _label, lo, hi, _step, _unit in EFFECT_SLIDERS:
            value = self.effects.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                problems.append(f"effects.{key}: expected a number, got {value!r}")
            elif not (lo <= float(value) <= hi):
                problems.append(f"effects.{key}: {value} is outside {lo}..{hi}")
        for key, _label, _desc in EFFECT_TOGGLES:
            if not isinstance(self.effects.get(key), bool):
                problems.append(f"effects.{key}: expected true/false")
        transition = self.wallpaper.get("transition")
        if transition not in WALLPAPER_TRANSITIONS:
            problems.append(f"wallpaper.transition: unknown transition {transition!r}")
        if self.wallpaper.get("fit") not in WALLPAPER_FIT_MODES:
            problems.append(f"wallpaper.fit: unknown fit mode {self.wallpaper.get('fit')!r}")
        duration = self.wallpaper.get("duration")
        if not isinstance(duration, (int, float)) or duration < 0 or duration > 30:
            problems.append("wallpaper.duration: expected 0..30 seconds")
        path = self.wallpaper.get("path")
        if path is not None and not isinstance(path, str):
            problems.append("wallpaper.path: expected a string or null")
        for comp in COMPONENT_NAMES:
            cfg = self.components.get(comp)
            if not isinstance(cfg, dict):
                problems.append(f"components.{comp}: expected an object")
            elif not isinstance(cfg.get("enabled", True), bool):
                problems.append(f"components.{comp}.enabled: expected true/false")
        ansi = self.components.get("kitty", {}).get("ansi", {})
        if isinstance(ansi, dict):
            for key, value in ansi.items():
                if not is_valid_hex(value):
                    problems.append(f"components.kitty.ansi.{key}: invalid hex color {value!r}")
        return problems

    def normalize(self) -> None:
        """Canonicalise colors to ``#RRGGBB`` and clamp numeric effects."""
        for key in COLOR_NAMES:
            try:
                self.colors[key] = normalize_hex(self.colors[key])
            except (ColorError, KeyError):
                self.colors[key] = DEFAULT_COLORS[key]
        for key, _label, lo, hi, step, _unit in EFFECT_SLIDERS:
            value = float(self.effects.get(key, DEFAULT_EFFECTS[key]))
            value = max(lo, min(hi, value))
            self.effects[key] = round(value) if float(step).is_integer() else round(value, 3)
        if not self.id:
            self.id = slugify(self.name)

    # --- convenience -------------------------------------------------------------

    def color(self, key: str) -> Color:
        return Color.parse(self.colors[key])

    def is_component_enabled(self, component: str) -> bool:
        return bool(self.components.get(component, {}).get("enabled", True))

    def set_color(self, key: str, value: str) -> None:
        if key not in COLOR_NAMES:
            raise ThemeError(f"unknown color key: {key}")
        self.colors[key] = normalize_hex(value)

    def ansi_palette(self) -> dict[str, str]:
        """The 16 ANSI colors: derived from the theme, overridable per theme."""
        palette = derive_ansi(self.colors)
        overrides = self.components.get("kitty", {}).get("ansi") or {}
        for key, value in overrides.items():
            if key in palette and is_valid_hex(value):
                palette[key] = normalize_hex(value)
        return palette

    def summary_accent(self) -> str:
        return self.colors.get("primary", DEFAULT_COLORS["primary"])

    def fingerprint(self) -> str:
        """Stable hash of the themeable content (ignores name/metadata)."""
        import hashlib

        payload = json.dumps(
            {
                "colors": self.colors,
                "effects": self.effects,
                "wallpaper": self.wallpaper,
                "fonts": self.fonts,
                "components": self.components,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
