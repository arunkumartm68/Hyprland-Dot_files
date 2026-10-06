import json
import re
import xml.dom.minidom
from pathlib import Path

import pytest

from hyprtheme.core import paths
from hyprtheme.core.generator import Generator, Injection, build_context, parse_version, resolve_wallpaper
from hyprtheme.core.settings import Settings
from hyprtheme.core.theme import Theme

from .conftest import REPO, wallpaper_file

PRESETS = sorted((REPO / "themes" / "presets").glob("*.json"))


def _settings() -> Settings:
    s = Settings()
    s.set("hyprland_syntax", "modern")
    s.set("hyprpaper_syntax", "modern")
    return s


@pytest.mark.parametrize("preset", PRESETS, ids=lambda p: p.stem)
@pytest.mark.parametrize("syntax", ["legacy", "modern"])
def test_every_preset_renders_every_component(fake_home: Path, preset: Path, syntax: str):
    theme = Theme.load(preset)
    plan = Generator(REPO / "templates", _settings()).plan(theme, hyprland_syntax=syntax)
    comps = set(plan.components())
    assert {"hyprland", "waybar", "kitty", "rofi", "swaync", "hyprlock", "wlogout"} <= comps
    for f in plan.files:
        assert f.content.strip(), f.path
        assert "{{" not in f.content and "{%" not in f.content, f.path
        assert str(fake_home) in str(f.path)
        if f.path.suffix == ".json":
            json.loads(f.content)
        elif f.path.suffix == ".jsonc":
            json.loads(re.sub(r"^\s*//.*$", "", f.content, flags=re.M))
        elif f.path.suffix == ".svg":
            xml.dom.minidom.parseString(f.content)
        elif f.path.name == "layout":
            for chunk in re.findall(r"\{.*?\}", f.content, re.S):
                json.loads(chunk)


def test_hyprland_output_contains_theme_values(fake_home: Path):
    theme = Theme.load(REPO / "themes" / "presets" / "cyan.json")
    theme.effects.update({"gaps_in": 7, "gaps_out": 21, "border_width": 3, "radius": 9})
    plan = Generator(REPO / "templates", _settings()).plan(theme, hyprland_syntax="modern")
    conf = next(f for f in plan.files if f.path.name == "hyprtheme.conf" and "hypr" in f.path.parts)
    assert "gaps_in = 7" in conf.content
    assert "gaps_out = 21" in conf.content
    assert "border_size = 3" in conf.content
    assert "rounding = 9" in conf.content
    assert "rgba(00e5ffff)" in conf.content
    assert "layerrule = match:namespace ^(waybar)$, blur on" in conf.content
    assert "source = " not in conf.content  # the include lives in hyprland.conf, not here


def test_legacy_rule_syntax(fake_home: Path):
    theme = Theme.load(REPO / "themes" / "presets" / "cyan.json")
    plan = Generator(REPO / "templates", _settings()).plan(theme, hyprland_syntax="legacy")
    conf = next(f for f in plan.files if f.path.name == "hyprtheme.conf" and "hypr" in f.path.parts)
    assert "layerrule = blur, waybar" in conf.content
    assert "match:namespace" not in conf.content


def test_rgb_preset_enables_rotating_border(fake_home: Path):
    theme = Theme.load(REPO / "themes" / "presets" / "rgb.json")
    plan = Generator(REPO / "templates", _settings()).plan(theme)
    conf = next(f for f in plan.files if f.path.name == "hyprtheme.conf" and "hypr" in f.path.parts)
    assert "borderangle, 1," in conf.content and "loop" in conf.content
    lua = next(f for f in plan.files if f.path.name == "hyprtheme.lua")
    assert 'leaf = "borderangle", enabled = true' in lua.content


def test_glass_off_disables_blur_and_transparency(fake_home: Path):
    theme = Theme.load(REPO / "themes" / "presets" / "amoled.json")
    assert theme.effects["glass"] is False
    plan = Generator(REPO / "templates", _settings()).plan(theme)
    conf = next(f for f in plan.files if f.path.name == "hyprtheme.conf" and "hypr" in f.path.parts)
    assert "enabled = false" in conf.content  # blur
    assert "layerrule" not in conf.content
    kitty = next(f for f in plan.files if f.path.name == "hyprtheme.conf" and "kitty" in f.path.parts)
    assert "background_opacity    1" in kitty.content


def test_variables_mode_only_writes_variable_files(fake_home: Path):
    s = _settings()
    for comp in ("waybar", "kitty", "rofi", "swaync", "hyprlock", "wlogout"):
        s.set_integration(comp, "variables")
    theme = Theme.load(REPO / "themes" / "presets" / "cyan.json")
    plan = Generator(REPO / "templates", s).plan(theme)
    names = {f.path.name for f in plan.files}
    assert "style.css" not in names and "config.jsonc" not in names and "hyprlock.conf" not in names
    assert "hyprtheme-colors.css" in names and "hyprtheme.rasi" in names
    assert [i.component for i in plan.injections] == ["hyprland"]


def test_off_mode_and_disabled_component_skip(fake_home: Path):
    s = _settings()
    s.set_integration("waybar", "off")
    theme = Theme.load(REPO / "themes" / "presets" / "cyan.json")
    theme.components["kitty"]["enabled"] = False
    plan = Generator(REPO / "templates", s).plan(theme)
    assert "waybar" not in plan.components()
    assert "kitty" not in plan.components()
    assert plan.skipped["waybar"] == "integration turned off in settings"
    assert plan.skipped["kitty"] == "disabled in theme"


def test_wallpaper_resolution_and_hyprpaper(fake_home: Path):
    theme = Theme.load(REPO / "themes" / "presets" / "ocean.json")
    assert resolve_wallpaper(theme) is None
    wp = wallpaper_file(fake_home)
    theme.wallpaper["path"] = "test.png"  # relative reference resolved in the wallpaper library
    assert resolve_wallpaper(theme) == wp
    s = _settings()
    s.wallpaper_backend = "hyprpaper"
    plan = Generator(REPO / "templates", s).plan(theme)
    hp = next(f for f in plan.files if f.path.name == "hyprpaper.conf")
    assert f"path = {wp}" in hp.content and "fit_mode = cover" in hp.content
    legacy = Generator(REPO / "templates", s).plan(theme, hyprpaper_syntax="legacy")
    hp = next(f for f in legacy.files if f.path.name == "hyprpaper.conf")
    assert f"preload = {wp}" in hp.content
    conf = next(f for f in plan.files if f.path.name == "hyprtheme.conf" and "hypr" in f.path.parts)
    assert "exec-once = " in conf.content and "wallpaper restore" in conf.content
    lock = next(f for f in plan.files if f.path.name == "hyprlock.conf")
    assert f"path = {wp}" in lock.content


def test_injection_block_is_idempotent_and_removable():
    inj = Injection("kitty", Path("/x/kitty.conf"), ["include hyprtheme.conf"], marker="kitty")
    original = "font_size 10\n"
    once = inj.apply_to(original)
    twice = inj.apply_to(once)
    assert once == twice
    assert once.count("include hyprtheme.conf") == 1
    assert once.startswith(original)
    changed = Injection("kitty", Path("/x/kitty.conf"), ["include other.conf"], marker="kitty").apply_to(once)
    assert "include other.conf" in changed and "include hyprtheme.conf" not in changed
    assert inj.remove_from(once).strip() == original.strip()


def test_lua_injection_when_hyprland_lua_exists(fake_home: Path):
    (paths.hypr_dir() / "hyprland.lua").write_text("-- lua config\n")
    theme = Theme.load(REPO / "themes" / "presets" / "cyan.json")
    plan = Generator(REPO / "templates", _settings()).plan(theme)
    targets = {i.path.name: i for i in plan.injections}
    assert 'pcall(require, "hyprtheme")' in targets["hyprland.lua"].lines
    assert "hyprland.conf" in targets  # the existing .conf is still handled


def test_parse_version():
    assert parse_version("Hyprland 0.53.1 built from branch main\nTag: v0.53.1") == (0, 53, 1)
    assert parse_version("hyprpaper v0.7.6") == (0, 7, 6)
    assert parse_version("nothing here") is None


def test_context_derivations(fake_home: Path):
    theme = Theme.default("ctx")
    theme.effects.update({"opacity": 0.5, "glass": True, "neon_glow": False, "blur": 0})
    ctx = build_context(theme, _settings(), hyprland_syntax="modern", hyprpaper_syntax="modern")
    assert ctx["derived"]["panel_alpha"] == 0.5
    assert ctx["derived"]["blur_enabled"] is False
    assert ctx["derived"]["glow_alpha"] == pytest.approx(0.15)
    theme.effects["glass"] = False
    ctx = build_context(theme, _settings(), hyprland_syntax="modern", hyprpaper_syntax="modern")
    assert ctx["derived"]["panel_alpha"] == 1.0
