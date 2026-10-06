import pytest

from hyprtheme.core.colors import Color, ColorError, derive_ansi, is_valid_hex, normalize_hex


def test_parse_variants():
    assert Color.parse("#00E5FF").hex == "#00E5FF"
    assert Color.parse("00e5ff").hex == "#00E5FF"
    assert Color.parse("#0EF").hex == "#00EEFF"
    assert Color.parse("#00E5FF80").a == pytest.approx(0.5, abs=0.01)


def test_invalid_colors():
    for bad in ("", "#xyz", "#12345", "not a color", 123, None):
        assert not is_valid_hex(bad)
    with pytest.raises(ColorError):
        Color.parse("#12345")


def test_output_formats():
    c = Color.parse("#00E5FF")
    assert c.hypr() == "rgba(00e5ffff)"
    assert c.hypr(0.5) == "rgba(00e5ff80)"
    assert c.hypr_rgb() == "rgb(00e5ff)"
    assert c.css_rgba(0.25) == "rgba(0, 229, 255, 0.25)"
    assert c.css_rgb() == "rgb(0, 229, 255)"
    assert c.hexa(1.0) == "#00E5FFFF"
    assert c.rgb_tuple() == "0, 229, 255"
    assert c.hyprlock(0.3) == "rgba(0, 229, 255, 0.3)"


def test_manipulation():
    c = Color.parse("#0077FF")
    assert c.lighten(0.2).luminance > c.luminance
    assert c.darken(0.2).luminance < c.luminance
    assert c.mix(Color.parse("#FFFFFF"), 1.0).hex == "#FFFFFF"
    assert c.readable_text().hex == "#FFFFFF"
    assert Color.parse("#FFFFFF").readable_text().hex == "#0B0D12"
    assert Color.parse("#FFFFFF").contrast_ratio(Color.parse("#000000")) == pytest.approx(21.0, abs=0.1)


def test_normalize_and_ansi():
    assert normalize_hex("fff") == "#FFFFFF"
    ansi = derive_ansi({"background": "#080A0F", "text": "#FFFFFF", "primary": "#00E5FF", "error": "#FF0000"})
    assert set(ansi) == {f"color{i}" for i in range(16)}
    assert ansi["color1"] == "#FF0000"
    assert ansi["color15"] == "#FFFFFF"
    for v in ansi.values():
        assert is_valid_hex(v)
