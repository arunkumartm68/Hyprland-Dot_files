"""Reusable widgets for the control center."""

from __future__ import annotations

from collections.abc import Callable

from gi.repository import Gtk


def card(title: str | None = None, *, glow: bool = False, spacing: int = 10) -> tuple[Gtk.Box, Gtk.Box]:
    """A glass card. Returns ``(card, body)`` where ``body`` receives the content."""
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    outer.add_css_class("ht-card")
    if glow:
        outer.add_css_class("ht-card-glow")
    if title:
        label = Gtk.Label(label=title.upper(), xalign=0)
        label.add_css_class("ht-card-title")
        outer.append(label)
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    outer.append(body)
    return outer, body


def button(
    label: str,
    icon: str | None = None,
    *,
    primary: bool = False,
    danger: bool = False,
    on_click: Callable[[], None] | None = None,
    tooltip: str | None = None,
) -> Gtk.Button:
    btn = Gtk.Button()
    content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
    if icon:
        content.append(Gtk.Image.new_from_icon_name(icon))
    content.append(Gtk.Label(label=label))
    btn.set_child(content)
    btn.add_css_class("ht-btn")
    if primary:
        btn.add_css_class("ht-primary")
    if danger:
        btn.add_css_class("ht-danger")
    if tooltip:
        btn.set_tooltip_text(tooltip)
    if on_click:
        btn.connect("clicked", lambda *_: on_click())
    return btn


def icon_button(icon: str, tooltip: str, on_click: Callable[[], None] | None = None) -> Gtk.Button:
    btn = Gtk.Button.new_from_icon_name(icon)
    btn.add_css_class("ht-icon-btn")
    btn.set_tooltip_text(tooltip)
    if on_click:
        btn.connect("clicked", lambda *_: on_click())
    return btn


def heading(text: str) -> Gtk.Label:
    label = Gtk.Label(label=text.upper(), xalign=0)
    label.add_css_class("ht-section-heading")
    return label


def label(text: str, *classes: str, xalign: float = 0.0, wrap: bool = False) -> Gtk.Label:
    lbl = Gtk.Label(label=text, xalign=xalign)
    for cls in classes:
        lbl.add_css_class(cls)
    if wrap:
        lbl.set_wrap(True)
    return lbl


def stat(title: str, value: str) -> tuple[Gtk.Box, Gtk.Label]:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    box.append(label(title.upper(), "ht-stat-label"))
    value_label = label(value, "ht-stat-value")
    value_label.set_ellipsize(3)  # Pango.EllipsizeMode.END
    box.append(value_label)
    return box, value_label


def clear_children(widget: Gtk.Widget) -> None:
    child = widget.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        widget.remove(child)
        child = nxt
