"""Color parsing, conversion and manipulation helpers.

Colors inside a theme are always stored as ``#RRGGBB`` hex strings.  This
module converts them into every notation the supported components need
(Hyprland ``rgba(hex)``, CSS ``rgba(r, g, b, a)``, rofi ``#RRGGBBAA`` ...) and
offers simple perceptual manipulation (lighten, darken, mix, contrast).
"""

from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


class ColorError(ValueError):
    """Raised when a color string cannot be parsed."""


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class Color:
    r: int
    g: int
    b: int
    a: float = 1.0

    # --- construction ------------------------------------------------------------

    @classmethod
    def parse(cls, value: str | Color) -> Color:
        """Parse ``#RGB``, ``#RGBA``, ``#RRGGBB``, ``#RRGGBBAA`` (with or without ``#``)."""
        if isinstance(value, Color):
            return value
        if not isinstance(value, str):
            raise ColorError(f"not a color string: {value!r}")
        text = value.strip()
        m = _HEX_RE.match(text)
        if not m:
            raise ColorError(f"invalid hex color: {value!r}")
        digits = m.group(1)
        if len(digits) in (3, 4):
            digits = "".join(ch * 2 for ch in digits)
        r = int(digits[0:2], 16)
        g = int(digits[2:4], 16)
        b = int(digits[4:6], 16)
        a = int(digits[6:8], 16) / 255 if len(digits) == 8 else 1.0
        return cls(r, g, b, a)

    @classmethod
    def from_rgb_floats(cls, r: float, g: float, b: float, a: float = 1.0) -> Color:
        return cls(round(_clamp(r) * 255), round(_clamp(g) * 255), round(_clamp(b) * 255), _clamp(a))

    @classmethod
    def from_hsl(cls, h: float, s: float, lightness: float, a: float = 1.0) -> Color:
        r, g, b = colorsys.hls_to_rgb(h % 1.0, _clamp(lightness), _clamp(s))
        return cls.from_rgb_floats(r, g, b, a)

    # --- properties --------------------------------------------------------------

    @property
    def rf(self) -> float:
        return self.r / 255

    @property
    def gf(self) -> float:
        return self.g / 255

    @property
    def bf(self) -> float:
        return self.b / 255

    def hsl(self) -> tuple[float, float, float]:
        h, lightness, s = colorsys.rgb_to_hls(self.rf, self.gf, self.bf)
        return h, s, lightness

    @property
    def luminance(self) -> float:
        """Relative luminance per WCAG."""

        def chan(c: float) -> float:
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        return 0.2126 * chan(self.rf) + 0.7152 * chan(self.gf) + 0.0722 * chan(self.bf)

    @property
    def is_dark(self) -> bool:
        return self.luminance < 0.4

    def contrast_ratio(self, other: Color) -> float:
        l1, l2 = sorted((self.luminance, other.luminance), reverse=True)
        return (l1 + 0.05) / (l2 + 0.05)

    # --- output formats ----------------------------------------------------------

    @property
    def hex(self) -> str:
        """``#RRGGBB``."""
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    @property
    def hex_lower(self) -> str:
        return self.hex.lower()

    def hexa(self, alpha: float | None = None) -> str:
        """``#RRGGBBAA`` (rofi, GTK CSS)."""
        a = self.a if alpha is None else _clamp(alpha)
        return f"{self.hex}{round(a * 255):02X}"

    def strip(self, alpha: float | None = None) -> str:
        """``RRGGBBAA`` without ``#`` - the notation Hyprland uses inside ``rgba()``."""
        return self.hexa(alpha)[1:].lower()

    def hypr(self, alpha: float | None = None) -> str:
        """Hyprland color literal: ``rgba(rrggbbaa)``."""
        return f"rgba({self.strip(alpha)})"

    def hypr_rgb(self) -> str:
        return f"rgb({self.hex[1:].lower()})"

    def css_rgba(self, alpha: float | None = None) -> str:
        """``rgba(r, g, b, a)`` for GTK CSS."""
        a = self.a if alpha is None else _clamp(alpha)
        return f"rgba({self.r}, {self.g}, {self.b}, {a:.3g})"

    def css_rgb(self) -> str:
        return f"rgb({self.r}, {self.g}, {self.b})"

    def rgb_tuple(self) -> str:
        """``r, g, b`` - handy for swaync's ``rgba(var(--x), alpha)`` pattern."""
        return f"{self.r}, {self.g}, {self.b}"

    def hyprlock(self, alpha: float | None = None) -> str:
        """hyprlock accepts ``rgba(r, g, b, a)``."""
        return self.css_rgba(alpha)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.hex

    # --- manipulation ------------------------------------------------------------

    def with_alpha(self, alpha: float) -> Color:
        return Color(self.r, self.g, self.b, _clamp(alpha))

    def lighten(self, amount: float) -> Color:
        h, s, lightness = self.hsl()
        return Color.from_hsl(h, s, lightness + amount, self.a)

    def darken(self, amount: float) -> Color:
        return self.lighten(-amount)

    def saturate(self, amount: float) -> Color:
        h, s, lightness = self.hsl()
        return Color.from_hsl(h, s + amount, lightness, self.a)

    def mix(self, other: Color, weight: float = 0.5) -> Color:
        w = _clamp(weight)
        return Color(
            round(self.r * (1 - w) + other.r * w),
            round(self.g * (1 - w) + other.g * w),
            round(self.b * (1 - w) + other.b * w),
            self.a * (1 - w) + other.a * w,
        )

    def rotate(self, degrees: float) -> Color:
        h, s, lightness = self.hsl()
        return Color.from_hsl(h + degrees / 360.0, s, lightness, self.a)

    def readable_text(self, light: str = "#FFFFFF", dark: str = "#0B0D12") -> Color:
        """Pick a text color that is readable on top of this color."""
        return Color.parse(dark if self.luminance > 0.45 else light)


def is_valid_hex(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX_RE.match(value.strip()))


def normalize_hex(value: str) -> str:
    """Normalise any accepted hex notation to ``#RRGGBB`` (alpha is dropped)."""
    return Color.parse(value).hex


def derive_ansi(colors: dict[str, str]) -> dict[str, str]:
    """Build a 16-color ANSI palette that harmonises with the theme.

    The palette keeps the semantic hue of each ANSI slot (red stays red-ish)
    but shifts saturation/lightness so it looks right against the theme's
    background, and uses the theme's own accent for blue/cyan/magenta where it
    makes sense.
    """
    bg = Color.parse(colors.get("background", "#0B0D12"))
    fg = Color.parse(colors.get("text", "#FFFFFF"))
    primary = Color.parse(colors.get("primary", "#00E5FF"))
    secondary = Color.parse(colors.get("secondary", "#0077FF"))
    highlight = Color.parse(colors.get("highlight", primary.hex))
    error = Color.parse(colors.get("error", "#FF4D6D"))
    success = Color.parse(colors.get("success", "#4DFF88"))
    warning = Color.parse(colors.get("warning", "#FFD166"))
    muted = Color.parse(colors.get("muted", "#8B95A7"))

    black = bg.lighten(0.08)
    bright_black = muted.darken(0.15)
    white = fg.darken(0.12)
    bright_white = fg

    palette = {
        "color0": black.hex,
        "color1": error.hex,
        "color2": success.hex,
        "color3": warning.hex,
        "color4": secondary.hex,
        "color5": highlight.hex,
        "color6": primary.hex,
        "color7": white.hex,
        "color8": bright_black.hex,
        "color9": error.lighten(0.1).hex,
        "color10": success.lighten(0.1).hex,
        "color11": warning.lighten(0.1).hex,
        "color12": secondary.lighten(0.1).hex,
        "color13": highlight.lighten(0.1).hex,
        "color14": primary.lighten(0.1).hex,
        "color15": bright_white.hex,
    }
    return palette
