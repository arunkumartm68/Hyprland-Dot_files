"""Common page scaffolding."""

from __future__ import annotations

from gi.repository import Gtk

from ..components.preview import DesktopPreview
from ..state import AppState


class Page(Gtk.ScrolledWindow):
    key = "page"
    title = "Page"
    subtitle = ""

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.content.add_css_class("ht-page")
        self.set_child(self.content)
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        t = Gtk.Label(label=self.title, xalign=0)
        t.add_css_class("ht-page-title")
        header.append(t)
        if self.subtitle:
            s = Gtk.Label(label=self.subtitle, xalign=0)
            s.add_css_class("ht-page-subtitle")
            s.set_wrap(True)
            header.append(s)
        self.content.append(header)
        self.build()
        self.state.connect("changed", lambda _s, what: self.on_theme_changed(what))
        self.state.connect("applied", lambda _s: self.on_applied())
        self.state.connect("themes-changed", lambda _s: self.on_themes_changed())
        self.state.connect("components-changed", lambda _s: self.on_components_changed())

    # hooks
    def build(self) -> None:  # pragma: no cover - UI
        pass

    def on_theme_changed(self, what: str) -> None:  # pragma: no cover - UI
        pass

    def on_applied(self) -> None:  # pragma: no cover - UI
        pass

    def on_themes_changed(self) -> None:  # pragma: no cover - UI
        pass

    def on_components_changed(self) -> None:  # pragma: no cover - UI
        pass

    def on_show(self) -> None:  # pragma: no cover - UI
        pass


class EditorPage(Page):
    """Two-column layout: editor on the left, sticky live preview on the right."""

    preview_width = 560

    def __init__(self, state: AppState):
        self.preview: DesktopPreview | None = None
        super().__init__(state)

    def split(self) -> tuple[Gtk.Box, Gtk.Box]:
        columns = Gtk.Box(spacing=20)
        editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, hexpand=True)
        editor.set_size_request(420, -1)
        columns.append(editor)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.START)
        self.preview = DesktopPreview(width=self.preview_width)
        self.preview.update(self.state.working)
        side.append(self.preview)
        hint = Gtk.Label(label="Live preview — reflects the working theme in real time", xalign=0.5)
        hint.add_css_class("ht-muted")
        hint.add_css_class("ht-small")
        side.append(hint)
        columns.append(side)
        self.content.append(columns)
        return editor, side

    def on_theme_changed(self, what: str) -> None:
        if self.preview is not None:
            self.preview.update(self.state.working)
