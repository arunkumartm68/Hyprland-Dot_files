"""Editor rows: color, slider, toggle, dropdown, entry."""

from __future__ import annotations

from collections.abc import Callable

from gi.repository import Gdk, Gtk

from ...core.colors import Color, ColorError


def _row_base(title: str, description: str | None = None) -> tuple[Gtk.Box, Gtk.Box]:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    row.add_css_class("ht-row")
    texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, hexpand=True, valign=Gtk.Align.CENTER)
    t = Gtk.Label(label=title, xalign=0)
    t.add_css_class("ht-row-label")
    texts.append(t)
    if description:
        d = Gtk.Label(label=description, xalign=0)
        d.add_css_class("ht-row-desc")
        d.set_ellipsize(3)
        texts.append(d)
    row.append(texts)
    return row, texts


def rgba_to_hex(rgba: Gdk.RGBA) -> str:
    return f"#{round(rgba.red * 255):02X}{round(rgba.green * 255):02X}{round(rgba.blue * 255):02X}"


def hex_to_rgba(value: str) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.parse(Color.parse(value).hex)
    return rgba


class ColorRow(Gtk.Box):
    """Label + swatch button (color picker) + HEX entry + RGB readout."""

    def __init__(self, key: str, title: str, description: str, value: str, on_change: Callable[[str, str], None]):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.key = key
        self.on_change = on_change
        self._updating = False
        self.add_css_class("ht-row")

        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, hexpand=True, valign=Gtk.Align.CENTER)
        t = Gtk.Label(label=title, xalign=0)
        t.add_css_class("ht-row-label")
        d = Gtk.Label(label=description, xalign=0)
        d.add_css_class("ht-row-desc")
        d.set_ellipsize(3)
        texts.append(t)
        texts.append(d)
        self.append(texts)

        self.rgb_label = Gtk.Label(label="", xalign=1)
        self.rgb_label.add_css_class("ht-row-desc")
        self.rgb_label.add_css_class("ht-mono")
        self.rgb_label.set_width_chars(14)
        self.append(self.rgb_label)

        self.entry = Gtk.Entry()
        self.entry.add_css_class("ht-entry")
        self.entry.add_css_class("ht-hex")
        self.entry.set_max_length(9)
        self.entry.set_width_chars(9)
        self.entry.set_valign(Gtk.Align.CENTER)
        self.entry.connect("activate", self._on_entry)
        self.entry.connect("changed", self._on_entry_changed)
        focus = Gtk.EventControllerFocus()
        focus.connect("leave", lambda *_: self._on_entry(self.entry))
        self.entry.add_controller(focus)
        self.append(self.entry)

        dialog = Gtk.ColorDialog(with_alpha=False, title=f"{title} color")
        self.picker = Gtk.ColorDialogButton(dialog=dialog)
        self.picker.add_css_class("ht-color-btn")
        self.picker.set_valign(Gtk.Align.CENTER)
        self.picker.connect("notify::rgba", self._on_picker)
        self.append(self.picker)

        self.set_value(value)

    def set_value(self, value: str) -> None:
        try:
            color = Color.parse(value)
        except ColorError:
            return
        self._updating = True
        try:
            self.entry.set_text(color.hex)
            self.entry.remove_css_class("error")
            self.picker.set_rgba(hex_to_rgba(color.hex))
            self.rgb_label.set_text(f"{color.r:>3} {color.g:>3} {color.b:>3}")
        finally:
            self._updating = False

    def _on_picker(self, *_args) -> None:
        if self._updating:
            return
        value = rgba_to_hex(self.picker.get_rgba())
        self.set_value(value)
        self.on_change(self.key, value)

    def _on_entry_changed(self, entry: Gtk.Entry) -> None:
        if self._updating:
            return
        text = entry.get_text().strip()
        try:
            Color.parse(text)
            entry.remove_css_class("error")
        except ColorError:
            entry.add_css_class("error")

    def _on_entry(self, entry: Gtk.Entry) -> None:
        if self._updating:
            return
        text = entry.get_text().strip()
        try:
            color = Color.parse(text)
        except ColorError:
            entry.add_css_class("error")
            return
        self.set_value(color.hex)
        self.on_change(self.key, color.hex)


class SliderRow(Gtk.Box):
    def __init__(
        self,
        key: str,
        title: str,
        lo: float,
        hi: float,
        step: float,
        unit: str,
        value: float,
        on_change: Callable[[str, float], None],
        description: str | None = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.key = key
        self.unit = unit
        self.step = step
        self.on_change = on_change
        self._updating = False
        self.add_css_class("ht-row")

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, hexpand=True)
        t = Gtk.Label(label=title, xalign=0)
        t.add_css_class("ht-row-label")
        texts.append(t)
        if description:
            d = Gtk.Label(label=description, xalign=0)
            d.add_css_class("ht-row-desc")
            texts.append(d)
        top.append(texts)
        self.value_label = Gtk.Label(label="", xalign=1)
        self.value_label.add_css_class("ht-mono")
        self.value_label.add_css_class("ht-accent-text")
        self.value_label.set_width_chars(8)
        top.append(self.value_label)
        self.append(top)

        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
        self.scale.add_css_class("ht-scale")
        self.scale.set_draw_value(False)
        self.scale.set_hexpand(True)
        self.scale.connect("value-changed", self._on_value)
        self.append(self.scale)
        self.set_value(value)

    def _format(self, value: float) -> str:
        if float(self.step).is_integer():
            return f"{round(value)}{self.unit}"
        if self.unit == "":
            return f"{round(value * 100)}%"
        return f"{value:.2f}{self.unit}"

    def set_value(self, value: float) -> None:
        self._updating = True
        try:
            self.scale.set_value(float(value))
            self.value_label.set_text(self._format(float(value)))
        finally:
            self._updating = False

    def _on_value(self, scale: Gtk.Scale) -> None:
        value = scale.get_value()
        self.value_label.set_text(self._format(value))
        if self._updating:
            return
        out: float = round(value) if float(self.step).is_integer() else round(value, 3)
        self.on_change(self.key, out)


class ToggleRow(Gtk.Box):
    def __init__(self, key: str, title: str, description: str | None, value: bool, on_change: Callable[[str, bool], None]):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.key = key
        self.on_change = on_change
        self._updating = False
        self.add_css_class("ht-row")
        row, _texts = _row_base(title, description)
        row.set_hexpand(True)
        row.remove_css_class("ht-row")
        self.append(row)
        self.switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.switch.add_css_class("ht-switch")
        self.switch.connect("notify::active", self._on_toggle)
        self.append(self.switch)
        self.set_value(value)

    def set_value(self, value: bool) -> None:
        self._updating = True
        try:
            self.switch.set_active(bool(value))
        finally:
            self._updating = False

    def _on_toggle(self, *_args) -> None:
        if self._updating:
            return
        self.on_change(self.key, self.switch.get_active())


class DropdownRow(Gtk.Box):
    def __init__(
        self,
        key: str,
        title: str,
        description: str | None,
        options: list[tuple[str, str]],
        value: str,
        on_change: Callable[[str, str], None],
    ):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.key = key
        self.options = options
        self.on_change = on_change
        self._updating = False
        self.add_css_class("ht-row")
        row, _ = _row_base(title, description)
        row.set_hexpand(True)
        row.remove_css_class("ht-row")
        self.append(row)
        self.dropdown = Gtk.DropDown.new_from_strings([lbl for _v, lbl in options])
        self.dropdown.add_css_class("ht-dropdown")
        self.dropdown.set_valign(Gtk.Align.CENTER)
        self.dropdown.connect("notify::selected", self._on_select)
        self.append(self.dropdown)
        self.set_value(value)

    def set_value(self, value: str) -> None:
        self._updating = True
        try:
            for i, (v, _lbl) in enumerate(self.options):
                if v == value:
                    self.dropdown.set_selected(i)
                    break
        finally:
            self._updating = False

    def _on_select(self, *_args) -> None:
        if self._updating:
            return
        idx = self.dropdown.get_selected()
        if 0 <= idx < len(self.options):
            self.on_change(self.key, self.options[idx][0])


class EntryRow(Gtk.Box):
    def __init__(
        self,
        key: str,
        title: str,
        description: str | None,
        value: str,
        on_change: Callable[[str, str], None],
        *,
        width_chars: int = 18,
        numeric: bool = False,
    ):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.key = key
        self.on_change = on_change
        self.numeric = numeric
        self._updating = False
        self.add_css_class("ht-row")
        row, _ = _row_base(title, description)
        row.set_hexpand(True)
        row.remove_css_class("ht-row")
        self.append(row)
        self.entry = Gtk.Entry()
        self.entry.add_css_class("ht-entry")
        self.entry.set_width_chars(width_chars)
        self.entry.set_valign(Gtk.Align.CENTER)
        self.entry.connect("activate", self._commit)
        focus = Gtk.EventControllerFocus()
        focus.connect("leave", lambda *_: self._commit(self.entry))
        self.entry.add_controller(focus)
        self.append(self.entry)
        self.set_value(value)

    def set_value(self, value: str) -> None:
        self._updating = True
        try:
            self.entry.set_text(str(value))
        finally:
            self._updating = False

    def _commit(self, entry: Gtk.Entry) -> None:
        if self._updating:
            return
        text = entry.get_text().strip()
        if self.numeric:
            try:
                float(text)
            except ValueError:
                entry.add_css_class("error")
                return
        entry.remove_css_class("error")
        self.on_change(self.key, text)
