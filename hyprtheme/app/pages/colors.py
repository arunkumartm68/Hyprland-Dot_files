"""Color editor: every theme colour with picker, HEX field, RGB readout and swatch."""

from __future__ import annotations

from gi.repository import Gtk

from ...core.colors import Color
from ...core.theme import COLOR_KEYS
from ..components import button, card, label
from ..components.rows import ColorRow
from .base import EditorPage

GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("Accent", ("primary", "secondary", "highlight", "glow", "gradient_start", "gradient_end")),
    ("Surfaces", ("background", "surface", "surface2", "border")),
    ("Text", ("text", "muted")),
    ("States", ("notification", "success", "warning", "error")),
    ("Widgets", ("battery", "system", "media", "workspace_active", "workspace_inactive")),
    ("Window borders", ("active_border", "inactive_border")),
]


class ColorsPage(EditorPage):
    key = "colors"
    title = "Colors"
    subtitle = "Any HEX colour works. Changes update the preview instantly; press APPLY to push them to the desktop."

    def build(self) -> None:
        editor, side = self.split()
        tools = Gtk.Box(spacing=8)
        tools.append(
            button(
                "DERIVE FROM PRIMARY",
                "ht-effects-symbolic",
                on_click=self._derive,
                tooltip="Re-generate accent, glow, gradient, border and widget colours from the primary colour",
            )
        )
        tools.append(button("SHIFT HUE +30°", "ht-colors-symbolic", on_click=lambda: self._rotate(30)))
        tools.append(button("SHIFT HUE −30°", "ht-colors-symbolic", on_click=lambda: self._rotate(-30)))
        editor.append(tools)
        meta = {k: (lbl, desc) for k, lbl, desc in COLOR_KEYS}
        self.rows: dict[str, ColorRow] = {}
        for group_title, keys in GROUPS:
            c, body = card(group_title)
            body.set_spacing(0)
            for key in keys:
                lbl, desc = meta[key]
                row = ColorRow(key, lbl, desc, self.state.working.colors[key], self._on_color)
                self.rows[key] = row
                body.append(row)
            editor.append(c)
        tip, tbody = card()
        tbody.append(
            label(
                "Kitty's 16 ANSI colours are derived automatically from these values (red stays red, cyan uses the primary accent, …). Override them per theme in the Components page if needed.",
                "ht-muted",
                "ht-small",
                wrap=True,
            )
        )
        side.append(tip)

    def _on_color(self, key: str, value: str) -> None:
        self.state.set_color(key, value)

    def _derive(self) -> None:
        p = Color.parse(self.state.working.colors["primary"])
        s = self.state
        s.working.colors.update(
            {
                "secondary": p.rotate(-25).darken(0.08).hex,
                "highlight": p.lighten(0.15).hex,
                "glow": p.hex,
                "border": p.hex,
                "gradient_start": p.hex,
                "gradient_end": p.rotate(-35).darken(0.1).hex,
                "notification": p.hex,
                "system": p.hex,
                "workspace_active": p.hex,
                "active_border": p.hex,
                "media": p.rotate(60).hex,
            }
        )
        s.emit("changed", "color")
        s.emit("message", "Accent colours derived from primary", False)

    def _rotate(self, degrees: float) -> None:
        s = self.state
        for key in (
            "primary",
            "secondary",
            "highlight",
            "glow",
            "border",
            "gradient_start",
            "gradient_end",
            "notification",
            "system",
            "media",
            "workspace_active",
            "active_border",
        ):
            s.working.colors[key] = Color.parse(s.working.colors[key]).rotate(degrees).hex
        s.emit("changed", "color")

    def on_theme_changed(self, what: str) -> None:
        super().on_theme_changed(what)
        for key, row in self.rows.items():
            row.set_value(self.state.working.colors[key])
