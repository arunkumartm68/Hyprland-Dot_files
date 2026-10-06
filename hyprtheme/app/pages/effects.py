"""Effects: sliders and toggles for transparency, blur, borders, radius, glow, gaps…"""

from __future__ import annotations

from ...core.theme import EFFECT_SLIDERS, EFFECT_TOGGLES
from ..components import card
from ..components.rows import SliderRow, ToggleRow
from .base import EditorPage

SLIDER_HELP = {
    "opacity": "Panel / bar / launcher opacity (and windows if enabled in Components → Hyprland)",
    "blur": "Blur strength behind translucent surfaces (Hyprland layer blur, Kitty background blur)",
    "border_width": "Border width for windows, bars and cards",
    "radius": "Corner radius for windows, bars, launcher and widgets",
    "glow": "Neon glow strength around accents and borders",
    "animation_speed": "Higher is faster (Hyprland animations, CSS transitions)",
    "window_gaps": "Padding inside bars, launcher and widgets; Waybar margins",
    "gaps_out": "Hyprland gaps between windows and the screen edge",
    "gaps_in": "Hyprland gaps between tiled windows",
}


class EffectsPage(EditorPage):
    key = "effects"
    title = "Effects"
    subtitle = "Shape the look: glass, blur, borders, radius, glow and gaps. The preview updates as you drag."

    def build(self) -> None:
        editor, _side = self.split()
        c, body = card("Sliders")
        body.set_spacing(0)
        self.sliders: dict[str, SliderRow] = {}
        for key, lbl, lo, hi, step, unit in EFFECT_SLIDERS:
            row = SliderRow(key, lbl, lo, hi, step, unit, float(self.state.working.effects[key]), self._on_effect, SLIDER_HELP.get(key))
            self.sliders[key] = row
            body.append(row)
        editor.append(c)
        c, body = card("Toggles")
        body.set_spacing(0)
        self.toggles: dict[str, ToggleRow] = {}
        for key, lbl, desc in EFFECT_TOGGLES:
            row = ToggleRow(key, lbl, desc, bool(self.state.working.effects[key]), self._on_effect)
            self.toggles[key] = row
            body.append(row)
        editor.append(c)

    def _on_effect(self, key: str, value) -> None:
        self.state.set_effect(key, value)

    def on_theme_changed(self, what: str) -> None:
        super().on_theme_changed(what)
        for key, row in self.sliders.items():
            row.set_value(float(self.state.working.effects[key]))
        for key, row in self.toggles.items():
            row.set_value(bool(self.state.working.effects[key]))
