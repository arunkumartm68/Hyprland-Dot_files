"""Import / export of portable ``.hyprtheme`` files.

A ``.hyprtheme`` file is UTF-8 JSON containing the complete theme definition
plus export metadata.  The wallpaper is stored as a *reference* (file name)
unless the user explicitly asks to embed it, so personal files never leak.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

from .. import __version__
from . import paths
from .generator import resolve_wallpaper
from .theme import Theme, ThemeError, slugify

FORMAT = "hyprtheme"
FORMAT_VERSION = 1
EXTENSION = ".hyprtheme"


class PortableError(ValueError):
    pass


def export_theme(theme: Theme, destination: Path, *, embed_wallpaper: bool = False) -> Path:
    data = theme.to_dict()
    data["preset"] = False
    wallpaper = dict(data.get("wallpaper") or {})
    resolved = resolve_wallpaper(theme)
    embedded: dict[str, Any] | None = None
    if resolved is not None:
        wallpaper["path"] = resolved.name  # reference only, never an absolute personal path
        if embed_wallpaper:
            raw = resolved.read_bytes()
            if len(raw) > 64 * 1024 * 1024:
                raise PortableError("wallpaper is larger than 64 MiB; not embedding")
            embedded = {"name": resolved.name, "data": base64.b64encode(raw).decode("ascii")}
    elif wallpaper.get("path"):
        wallpaper["path"] = Path(str(wallpaper["path"])).name
    data["wallpaper"] = wallpaper
    payload = {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "exported_by": f"HyprTheme {__version__}",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "theme": data,
    }
    if embedded:
        payload["wallpaper_file"] = embedded
    destination = Path(destination)
    if destination.suffix != EXTENSION:
        destination = destination.with_suffix(destination.suffix + EXTENSION) if destination.suffix else destination.with_suffix(EXTENSION)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return destination


def read_portable(source: Path) -> tuple[Theme, dict[str, Any] | None]:
    """Parse a ``.hyprtheme`` (or plain theme.json) file without installing it."""
    try:
        raw = json.loads(Path(source).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortableError(f"cannot read {source}: {exc}") from exc
    if not isinstance(raw, dict):
        raise PortableError("not a theme file")
    if raw.get("format") == FORMAT:
        version = raw.get("format_version", 1)
        if not isinstance(version, int) or version > FORMAT_VERSION:
            raise PortableError(f"unsupported .hyprtheme format version {version!r}")
        theme_data = raw.get("theme")
        wallpaper_file = raw.get("wallpaper_file")
    else:
        theme_data = raw  # a bare theme.json is accepted too
        wallpaper_file = None
    if not isinstance(theme_data, dict):
        raise PortableError("theme file has no theme object")
    try:
        theme = Theme.from_dict(theme_data, strict=True)
    except ThemeError as exc:
        raise PortableError(f"invalid theme: {exc}") from exc
    theme.preset = False
    return theme, wallpaper_file if isinstance(wallpaper_file, dict) else None


def import_theme(source: Path, *, themes_dir: Path | None = None, new_name: str | None = None, overwrite: bool = False) -> Theme:
    theme, wallpaper_file = read_portable(Path(source))
    if new_name:
        theme.name = new_name
        theme.id = slugify(new_name)
    themes_dir = themes_dir or paths.user_themes_dir()
    themes_dir.mkdir(parents=True, exist_ok=True)
    target = themes_dir / f"{theme.id}.json"
    if target.exists() and not overwrite:
        base = theme.id
        counter = 2
        while target.exists():
            theme.id = f"{base}-{counter}"
            target = themes_dir / f"{theme.id}.json"
            counter += 1
    if wallpaper_file and wallpaper_file.get("data") and wallpaper_file.get("name"):
        wp_dir = paths.user_wallpapers_dir()
        wp_dir.mkdir(parents=True, exist_ok=True)
        name = Path(str(wallpaper_file["name"])).name
        dest = wp_dir / name
        if not dest.exists():
            try:
                dest.write_bytes(base64.b64decode(str(wallpaper_file["data"])))
            except (ValueError, OSError) as exc:
                raise PortableError(f"cannot write embedded wallpaper: {exc}") from exc
        theme.wallpaper["path"] = name
    theme.save(target)
    return theme
