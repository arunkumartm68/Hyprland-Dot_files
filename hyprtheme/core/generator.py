"""Config generator: turns a :class:`Theme` into concrete component files.

The generator is *pure*: it computes a :class:`Plan` (files to write and
include-lines to inject) without touching the filesystem.  The engine then
backs up, writes and reloads.  Keeping these apart makes dry-runs, previews
and tests trivial.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import __version__
from . import paths
from .settings import Settings
from .templating import Template, TemplateError
from .theme import Theme

TEMPLATE_SUFFIX = ".tmpl"


class GeneratorError(RuntimeError):
    pass


@dataclass
class GeneratedFile:
    component: str
    path: Path
    content: str
    executable: bool = False
    only_if_missing: bool = False  # install a default once, never overwrite


@dataclass
class Injection:
    """A managed block to ensure inside a user-owned file (never rewrites the rest)."""

    component: str
    path: Path
    lines: list[str]
    marker: str
    comment: str = "#"
    create_if_missing: bool = False
    description: str = ""

    @property
    def begin(self) -> str:
        return f"{self.comment} >>> hyprtheme {self.marker} >>> (managed block, do not edit)"

    @property
    def end(self) -> str:
        return f"{self.comment} <<< hyprtheme {self.marker} <<<"

    def block(self) -> str:
        return "\n".join([self.begin, *self.lines, self.end]) + "\n"

    def apply_to(self, text: str) -> str:
        """Return ``text`` with this block present exactly once (replaced in place or appended)."""
        pattern = re.compile(re.escape(self.begin) + r".*?" + re.escape(self.end) + r"\n?", re.DOTALL)
        block = self.block()
        if pattern.search(text):
            return pattern.sub(lambda _m: block, text, count=1)
        if text and not text.endswith("\n"):
            text += "\n"
        if text and not text.endswith("\n\n"):
            text += "\n"
        return text + block

    def remove_from(self, text: str) -> str:
        pattern = re.compile(r"\n?" + re.escape(self.begin) + r".*?" + re.escape(self.end) + r"\n?", re.DOTALL)
        return pattern.sub("\n", text, count=1)


@dataclass
class Plan:
    theme: Theme
    files: list[GeneratedFile] = field(default_factory=list)
    injections: list[Injection] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)  # component -> reason
    warnings: list[str] = field(default_factory=list)

    def targets(self) -> list[Path]:
        """Every path the plan may modify (for backups)."""
        seen: list[Path] = []
        for f in self.files:
            if f.path not in seen:
                seen.append(f.path)
        for inj in self.injections:
            if inj.path not in seen:
                seen.append(inj.path)
        return seen

    def components(self) -> list[str]:
        out: list[str] = []
        for f in self.files:
            if f.component not in out:
                out.append(f.component)
        for inj in self.injections:
            if inj.component not in out:
                out.append(inj.component)
        return out


# --- version helpers ----------------------------------------------------------------

_VERSION_RE = re.compile(r"v?(\d+)\.(\d+)(?:\.(\d+))?")


def parse_version(text: str) -> tuple[int, int, int] | None:
    for line in text.splitlines():
        if "tag:" in line.lower() or "version" in line.lower() or line.strip().startswith("v"):
            m = _VERSION_RE.search(line)
            if m:
                return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    m = _VERSION_RE.search(text)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    return None


def _run_version(cmd: list[str]) -> tuple[int, int, int] | None:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_version((proc.stdout or "") + "\n" + (proc.stderr or ""))


def detect_hyprland_syntax(settings: Settings | None = None) -> str:
    """``legacy`` (<0.53 hyprlang), ``modern`` (>=0.53 hyprlang) or ``lua``.

    The result only affects rule lines; everything else is identical.
    """
    forced = (settings.get("hyprland_syntax") if settings else None) or "auto"
    if forced in ("legacy", "modern", "lua"):
        return forced
    version = None
    if shutil.which("hyprctl") and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        version = _run_version(["hyprctl", "version"])
    if version is None and shutil.which("Hyprland"):
        version = _run_version(["Hyprland", "--version"])
    if version is None:
        return "modern"
    return "legacy" if version < (0, 53, 0) else "modern"


def detect_hyprpaper_syntax(settings: Settings | None = None) -> str:
    forced = (settings.get("hyprpaper_syntax") if settings else None) or "auto"
    if forced in ("legacy", "modern"):
        return forced
    version = None
    if shutil.which("hyprpaper"):
        version = _run_version(["hyprpaper", "--version"]) or _run_version(["hyprpaper", "-v"])
    if version is None:
        return "modern"
    return "legacy" if version < (0, 8, 0) else "modern"


# --- context ------------------------------------------------------------------------


def _hyprtheme_command() -> str:
    """How generated configs should invoke the CLI."""
    found = shutil.which("hyprtheme")
    if found:
        return "hyprtheme"
    local_bin = paths.home() / ".local" / "bin" / "hyprtheme"
    if local_bin.exists():
        return str(local_bin)
    # Running from a source checkout: call the package through python.
    return f"{shlex.quote(os.environ.get('HYPRTHEME_PYTHON') or 'python3')} -m hyprtheme"


def resolve_wallpaper(theme: Theme) -> Path | None:
    """Resolve the theme's wallpaper reference to an existing file (or None)."""
    ref = theme.wallpaper.get("path")
    if not ref:
        return None
    candidate = Path(os.path.expandvars(str(ref))).expanduser()
    if candidate.is_absolute():
        return candidate if candidate.is_file() else None
    search = [
        paths.user_wallpapers_dir(),
        paths.app_data_dir() / "wallpapers",
        paths.pictures_dir() / "Wallpapers",
        paths.pictures_dir(),
    ]
    assets = paths.assets_dir()
    if assets:
        search.append(assets / "wallpapers")
    if theme.source:
        search.insert(0, theme.source.parent)
    for base in search:
        p = base / candidate
        if p.is_file():
            return p
    return None


def build_context(
    theme: Theme, settings: Settings | None = None, *, hyprland_syntax: str | None = None, hyprpaper_syntax: str | None = None
) -> dict[str, Any]:
    settings = settings or Settings()
    e = theme.effects
    c = theme.colors
    opacity = float(e["opacity"])
    glass = bool(e["glass"])
    panel_alpha = round(opacity if glass else 1.0, 3)
    glow = float(e["glow"]) if e["neon_glow"] else 0.0
    radius = int(e["radius"])
    blur = int(e["blur"])
    blur_enabled = glass and blur > 0
    gaps = int(e["window_gaps"])
    speed = float(e["animation_speed"]) or 1.0
    hypr_cfg = theme.components.get("hyprland", {})
    windows_use_opacity = bool(hypr_cfg.get("apply_opacity_to_windows", False))
    window_active = round(opacity, 2) if (windows_use_opacity and glass) else 1.0
    window_inactive = round(max(0.3, window_active - 0.05), 2) if windows_use_opacity and glass else 1.0

    wallpaper_path = resolve_wallpaper(theme)
    wallpaper_cfg = theme.wallpaper
    fit = str(wallpaper_cfg.get("fit", "crop"))
    hyprpaper_fit = {"crop": "cover", "fit": "contain", "no": "fill", "stretch": "fill"}.get(fit, "cover")
    wallpaper_enabled = theme.is_component_enabled("wallpaper") and settings.integration("wallpaper") != "off"

    hyprtheme_cmd = _hyprtheme_command()
    wlogout_icons = paths.wlogout_dir() / "hyprtheme-icons"
    power_menu = "wlogout" if theme.is_component_enabled("wlogout") else "hyprctl dispatch exit"

    wl = dict(theme.components.get("wlogout", {}))
    wl.setdefault("lock_command", "hyprlock" if theme.is_component_enabled("hyprlock") else "loginctl lock-session")

    components = {k: dict(v) for k, v in theme.components.items()}
    components["wlogout"] = wl

    derived = {
        "panel_alpha": panel_alpha,
        "card_alpha": round(min(1.0, panel_alpha * 0.9 + 0.08), 3),
        "overlay_alpha": round(min(1.0, panel_alpha * 0.85), 3),
        "terminal_opacity": round(opacity if glass else 1.0, 2),
        "border_alpha": round(0.55 + 0.45 * glow, 3) if e["neon_glow"] else 0.75,
        "card_border_alpha": 0.25,
        "glow_alpha": round(0.15 + 0.6 * glow, 3),
        "glow_px": round(6 + 22 * glow),
        "shadow_alpha": round(0.25 + 0.55 * glow, 3) if e["neon_glow"] else 0.6,
        "shadow_range": round(6 + 26 * glow) if e["neon_glow"] else 8,
        "blur_enabled": blur_enabled,
        "blur_size": max(1, round(blur / 3)) if blur_enabled else 1,
        "blur_passes": 1 if blur < 8 else (2 if blur < 20 else 3),
        "radius_xs": max(0, round(radius * 0.4)),
        "radius_sm": max(0, round(radius * 0.7)),
        "radius_lg": radius,
        "radius_xl": round(radius * 1.3),
        "pad_xs": max(2, round(gaps * 0.35)),
        "pad_sm": max(4, round(gaps * 0.6)),
        "pad_md": max(6, gaps),
        "pad_lg": max(8, round(gaps * 1.6)),
        "pad_x": max(6, gaps + 2),
        "pad_y": max(2, round(gaps * 0.5)),
        "module_gap": max(2, round(gaps * 0.45)),
        "bar_margin_top": gaps if components["waybar"].get("position", "top") == "top" else 0,
        "bar_margin_bottom": gaps if components["waybar"].get("position", "top") == "bottom" else 0,
        "anim_ms": round(250 / speed) if e["animations"] else 0,
        "window_opacity_active": window_active,
        "window_opacity_inactive": window_inactive,
    }

    return {
        "theme": {
            "name": theme.name,
            "id": theme.id,
            "author": theme.author,
            "description": theme.description,
            "variant": theme.variant,
        },
        "colors": dict(c),
        "effects": dict(e),
        "fonts": dict(theme.fonts),
        "components": components,
        "ansi": theme.ansi_palette(),
        "wallpaper": {
            "has": wallpaper_path is not None and wallpaper_enabled,
            "path": str(wallpaper_path) if wallpaper_path else "",
            "transition": wallpaper_cfg.get("transition", "grow"),
            "duration": wallpaper_cfg.get("duration", 1.5),
            "fit": fit,
            "hyprpaper_fit": hyprpaper_fit,
            "hyprpaper_syntax": hyprpaper_syntax or detect_hyprpaper_syntax(settings),
            "restore_on_login": wallpaper_path is not None and wallpaper_enabled,
        },
        "hyprland": {"syntax": hyprland_syntax or detect_hyprland_syntax(settings)},
        "derived": derived,
        "paths": {
            "config_home": str(paths.config_home()),
            "hypr_dir": str(paths.hypr_dir()),
            "hyprtheme_conf": str(paths.hypr_dir() / "hyprtheme.conf"),
            "hyprtheme_lua": str(paths.hypr_dir() / "hyprtheme.lua"),
            "hyprlock_vars": str(paths.hypr_dir() / "hyprlock-hyprtheme.conf"),
            "wlogout_icons": str(wlogout_icons),
            "wallpaper_restore_cmd": f"{hyprtheme_cmd} wallpaper restore",
            "power_menu_cmd": power_menu,
            "hyprtheme_cmd": hyprtheme_cmd,
        },
        "meta": {
            "version": __version__,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "lit": {"open": "{{", "close": "}}"},
    }


# --- generator ----------------------------------------------------------------------


class Generator:
    def __init__(self, templates_dir: Path | None = None, settings: Settings | None = None):
        resolved = templates_dir or paths.templates_dir()
        if resolved is None or not resolved.is_dir():
            raise GeneratorError("templates directory not found (is HyprTheme installed?)")
        self.templates_dir: Path = resolved
        self.settings = settings or Settings()
        self._cache: dict[Path, Template] = {}

    # -- template access -----------------------------------------------------------

    def template(self, relative: str) -> Template:
        path = self.templates_dir / (relative + TEMPLATE_SUFFIX)
        if path not in self._cache:
            try:
                source = path.read_text(encoding="utf-8")
            except OSError as exc:
                raise GeneratorError(f"template missing: {path} ({exc})") from exc
            self._cache[path] = Template(source, name=str(path))
        return self._cache[path]

    def render(self, relative: str, ctx: dict[str, Any]) -> str:
        try:
            return self.template(relative).render(ctx)
        except TemplateError as exc:
            raise GeneratorError(f"{relative}: {exc}") from exc

    # -- planning --------------------------------------------------------------------

    def plan(self, theme: Theme, *, hyprland_syntax: str | None = None, hyprpaper_syntax: str | None = None) -> Plan:
        ctx = build_context(theme, self.settings, hyprland_syntax=hyprland_syntax, hyprpaper_syntax=hyprpaper_syntax)
        plan = Plan(theme=theme)
        for component in ("hyprland", "waybar", "kitty", "rofi", "swaync", "hyprlock", "wlogout", "wallpaper"):
            mode = self.settings.integration(component)
            if not theme.is_component_enabled(component):
                plan.skipped[component] = "disabled in theme"
                continue
            if mode == "off":
                plan.skipped[component] = "integration turned off in settings"
                continue
            getattr(self, f"_plan_{component}")(plan, ctx, mode)
        return plan

    # -- per component ---------------------------------------------------------------

    def _plan_hyprland(self, plan: Plan, ctx: dict[str, Any], mode: str) -> None:
        hypr = paths.hypr_dir()
        conf = hypr / "hyprtheme.conf"
        lua = hypr / "hyprtheme.lua"
        plan.files.append(GeneratedFile("hyprland", conf, self.render("hyprland/hyprtheme.conf", ctx)))
        plan.files.append(GeneratedFile("hyprland", lua, self.render("hyprland/hyprtheme.lua", ctx)))
        if mode != "managed":
            return
        main_conf = hypr / "hyprland.conf"
        main_lua = hypr / "hyprland.lua"
        if main_lua.exists():
            plan.injections.append(
                Injection(
                    "hyprland",
                    main_lua,
                    ['pcall(require, "hyprtheme")'],
                    marker="hyprland.lua",
                    comment="--",
                    description="load the generated theme module",
                )
            )
        if main_conf.exists() or not main_lua.exists():
            plan.injections.append(
                Injection(
                    "hyprland",
                    main_conf,
                    [f"source = {conf}"],
                    marker="hyprland.conf",
                    create_if_missing=True,
                    description="source the generated theme file",
                )
            )

    def _plan_waybar(self, plan: Plan, ctx: dict[str, Any], mode: str) -> None:
        d = paths.waybar_dir()
        plan.files.append(GeneratedFile("waybar", d / "hyprtheme-colors.css", self.render("waybar/colors.css", ctx)))
        if mode == "managed":
            plan.files.append(GeneratedFile("waybar", d / "style.css", self.render("waybar/style.css", ctx)))
            plan.files.append(GeneratedFile("waybar", d / "config.jsonc", self.render("waybar/config.jsonc", ctx)))

    def _plan_kitty(self, plan: Plan, ctx: dict[str, Any], mode: str) -> None:
        d = paths.kitty_dir()
        theme_file = d / "hyprtheme.conf"
        plan.files.append(GeneratedFile("kitty", theme_file, self.render("kitty/hyprtheme.conf", ctx)))
        if mode == "managed":
            plan.injections.append(
                Injection(
                    "kitty",
                    d / "kitty.conf",
                    ["include hyprtheme.conf"],
                    marker="kitty",
                    create_if_missing=True,
                    description="include the generated theme (later lines win, so this goes last)",
                )
            )

    def _plan_rofi(self, plan: Plan, ctx: dict[str, Any], mode: str) -> None:
        d = paths.rofi_dir()
        theme_file = d / "hyprtheme.rasi"
        plan.files.append(GeneratedFile("rofi", theme_file, self.render("rofi/hyprtheme.rasi", ctx)))
        if mode == "managed":
            plan.injections.append(
                Injection(
                    "rofi",
                    d / "config.rasi",
                    [f'@theme "{theme_file}"'],
                    marker="rofi",
                    comment="//",
                    create_if_missing=True,
                    description="select the generated theme (the last @theme wins)",
                )
            )

    def _plan_swaync(self, plan: Plan, ctx: dict[str, Any], mode: str) -> None:
        d = paths.swaync_dir()
        plan.files.append(GeneratedFile("swaync", d / "hyprtheme-colors.css", self.render("swaync/colors.css", ctx)))
        if mode == "managed":
            plan.files.append(GeneratedFile("swaync", d / "style.css", self.render("swaync/style.css", ctx)))
            manage_config = bool(ctx["components"]["swaync"].get("manage_config", True))
            plan.files.append(
                GeneratedFile("swaync", d / "config.json", self.render("swaync/config.json", ctx), only_if_missing=not manage_config)
            )

    def _plan_hyprlock(self, plan: Plan, ctx: dict[str, Any], mode: str) -> None:
        hypr = paths.hypr_dir()
        plan.files.append(GeneratedFile("hyprlock", hypr / "hyprlock-hyprtheme.conf", self.render("hyprlock/hyprlock-hyprtheme.conf", ctx)))
        if mode == "managed":
            plan.files.append(GeneratedFile("hyprlock", hypr / "hyprlock.conf", self.render("hyprlock/hyprlock.conf", ctx)))

    def _plan_wlogout(self, plan: Plan, ctx: dict[str, Any], mode: str) -> None:
        d = paths.wlogout_dir()
        plan.files.append(GeneratedFile("wlogout", d / "hyprtheme-colors.css", self.render("wlogout/colors.css", ctx)))
        icons = d / "hyprtheme-icons"
        for name in ("lock", "logout", "suspend", "reboot", "shutdown"):
            for variant in (name, f"{name}-hover"):
                plan.files.append(GeneratedFile("wlogout", icons / f"{variant}.svg", self.render(f"wlogout/icons/{variant}.svg", ctx)))
        if mode == "managed":
            plan.files.append(GeneratedFile("wlogout", d / "style.css", self.render("wlogout/style.css", ctx)))
            plan.files.append(GeneratedFile("wlogout", d / "layout", self.render("wlogout/layout", ctx)))

    def _plan_wallpaper(self, plan: Plan, ctx: dict[str, Any], mode: str) -> None:
        backend = self.settings.wallpaper_backend
        if backend == "off":
            plan.skipped["wallpaper"] = "wallpaper backend turned off"
            return
        if not ctx["wallpaper"]["has"]:
            ref = plan.theme.wallpaper.get("path")
            plan.skipped["wallpaper"] = f"wallpaper file not found: {ref}" if ref else "no wallpaper selected"
            return
        # hyprpaper reads its config at start, so keep it in sync whenever it is the
        # backend (explicitly, or as the auto fallback when swww is absent).
        uses_hyprpaper = backend == "hyprpaper" or (backend == "auto" and not shutil.which("swww") and shutil.which("hyprpaper"))
        if uses_hyprpaper:
            plan.files.append(GeneratedFile("wallpaper", paths.hypr_dir() / "hyprpaper.conf", self.render("wallpaper/hyprpaper.conf", ctx)))

    # -- preview helpers -------------------------------------------------------------

    def render_component(self, theme: Theme, relative: str) -> str:
        return self.render(relative, build_context(theme, self.settings))
