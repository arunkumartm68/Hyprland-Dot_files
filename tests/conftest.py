"""Shared fixtures: every test runs against an isolated fake $HOME."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / ".local" / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / ".cache"))
    monkeypatch.setenv("HYPRTHEME_RESOURCES", str(REPO))
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    # Seed the fake home with the repository's reference dotfiles.
    for sub in ("hypr", "kitty", "waybar", "rofi", "swaync"):
        src = REPO / "config" / sub
        if src.is_dir():
            shutil.copytree(src, home / ".config" / sub)
    return home


@pytest.fixture()
def engine(fake_home: Path):
    from hyprtheme.core.engine import ThemeEngine
    from hyprtheme.core.settings import Settings

    settings = Settings.load()
    settings.reload_on_apply = False
    settings.set("hyprland_syntax", "modern")
    settings.set("hyprpaper_syntax", "modern")
    return ThemeEngine(settings)


@pytest.fixture()
def no_binaries(monkeypatch: pytest.MonkeyPatch):
    """Simulate a system where no themeable component is installed."""
    monkeypatch.setattr(shutil, "which", lambda *_a, **_k: None)
    monkeypatch.setenv("PATH", "")
    return None


def wallpaper_file(home: Path) -> Path:
    wp = home / ".config" / "hyprtheme" / "wallpapers"
    wp.mkdir(parents=True, exist_ok=True)
    f = wp / "test.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    return f


os.environ.setdefault("HYPRTHEME_TESTING", "1")
