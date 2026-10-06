import json
from pathlib import Path

import pytest

from hyprtheme.core.theme import COLOR_NAMES, DEFAULT_COLORS, Theme, ThemeError, slugify

PRESETS = Path(__file__).resolve().parent.parent / "themes" / "presets"


def test_defaults_are_valid():
    t = Theme.default("X")
    assert t.validate() == []
    assert t.id == "x"
    assert set(t.colors) == set(COLOR_NAMES)


def test_roundtrip(tmp_path: Path):
    t = Theme.default("Round Trip")
    t.colors["primary"] = "#ABCDEF"
    t.effects["blur"] = 20
    path = t.save(tmp_path / "rt.json")
    loaded = Theme.load(path)
    assert loaded == t
    assert loaded.fingerprint() == t.fingerprint()
    assert loaded.source == path


def test_validation_errors():
    t = Theme.default("Bad")
    t.colors["primary"] = "#xyz"
    t.effects["blur"] = 999
    t.effects["glass"] = "yes"
    t.wallpaper["transition"] = "teleport"
    problems = t.validate()
    assert any("colors.primary" in p for p in problems)
    assert any("effects.blur" in p for p in problems)
    assert any("effects.glass" in p for p in problems)
    assert any("wallpaper.transition" in p for p in problems)
    with pytest.raises(ThemeError):
        Theme.from_dict(t.to_dict())


def test_partial_dict_is_filled_with_defaults():
    t = Theme.from_dict({"name": "Mini", "colors": {"primary": "#123456"}})
    assert t.colors["primary"] == "#123456"
    assert t.colors["background"] == DEFAULT_COLORS["background"]
    assert t.effects["radius"] == 14
    assert t.components["waybar"]["enabled"] is True


def test_normalize_clamps_and_canonicalises():
    t = Theme.from_dict({"name": "n", "colors": {"primary": "abc"}, "effects": {"blur": 1000}}, strict=False)
    assert t.colors["primary"] == "#AABBCC"
    assert t.effects["blur"] == 40


def test_unsupported_schema():
    with pytest.raises(ThemeError):
        Theme.from_dict({"schema": 99, "name": "future"})


def test_slugify():
    assert slugify("Iron Man") == "iron-man"
    assert slugify("  Spider-Man!! ") == "spider-man"
    assert slugify("") == "theme"


@pytest.mark.parametrize("path", sorted(PRESETS.glob("*.json")), ids=lambda p: p.stem)
def test_presets_are_valid(path: Path):
    raw = json.loads(path.read_text())
    t = Theme.load(path)
    assert t.validate() == []
    assert t.preset is True
    assert raw["id"] == path.stem
    assert t.name


def test_all_required_presets_exist():
    expected = {
        "cyan",
        "red",
        "green",
        "orange",
        "ice-blue",
        "pink",
        "white",
        "yellow",
        "rgb",
        "amoled",
        "cyberpunk",
        "matrix",
        "iron-man",
        "spider-man",
        "ocean",
        "sunset",
        "ben-10",
    }
    assert expected <= {p.stem for p in PRESETS.glob("*.json")}


def test_ansi_override():
    t = Theme.default("A")
    t.components["kitty"]["ansi"] = {"color1": "#111111", "bogus": "#222222"}
    palette = t.ansi_palette()
    assert palette["color1"] == "#111111"
    assert "bogus" not in palette
