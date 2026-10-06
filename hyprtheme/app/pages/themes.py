"""Themes: presets and custom themes, create / import / export / delete."""

from __future__ import annotations

from gi.repository import Gtk

from ..components import button, card, clear_children, heading
from ..components.pills import ThemeCard
from .base import Page


class ThemesPage(Page):
    key = "themes"
    title = "Themes"
    subtitle = "Pick a preset to load it into the editor, tweak it on the Colors and Effects pages, then APPLY or SAVE AS."

    def build(self) -> None:
        toolbar = Gtk.Box(spacing=8)
        toolbar.append(
            button(
                "CREATE THEME",
                "ht-add-symbolic",
                primary=True,
                on_click=lambda: self.state.emit("message", "__save_as__", False),
                tooltip="Save the working theme under a new name",
            )
        )
        toolbar.append(button("IMPORT", "ht-import-symbolic", on_click=lambda: self.state.emit("message", "__import__", False)))
        toolbar.append(button("EXPORT", "ht-export-symbolic", on_click=lambda: self.state.emit("message", "__export__", False)))
        self.delete_btn = button("DELETE", "ht-delete-symbolic", danger=True, on_click=self._delete_selected)
        toolbar.append(self.delete_btn)
        self.content.append(toolbar)

        self.content.append(heading("Presets"))
        self.preset_flow = self._flow()
        self.content.append(self.preset_flow)
        self.content.append(heading("Your themes"))
        self.user_flow = self._flow()
        self.content.append(self.user_flow)
        self.empty_card, ebody = card()
        ebody.append(Gtk.Label(label="No custom themes yet. Modify a preset and use CREATE THEME (or SAVE AS) to keep it.", xalign=0))
        self.content.append(self.empty_card)
        self.refresh()

    def _flow(self) -> Gtk.FlowBox:
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_homogeneous(True)
        flow.set_column_spacing(12)
        flow.set_row_spacing(12)
        flow.set_min_children_per_line(2)
        flow.set_max_children_per_line(6)
        return flow

    def refresh(self) -> None:
        clear_children(self.preset_flow)
        clear_children(self.user_flow)
        current = self.state.applied()
        applied_id = current.theme.id if current else None
        working_id = self.state.working.id
        user_count = 0
        for ref in self.state.themes():
            card_widget = ThemeCard(
                ref.theme, ref.kind, applied=ref.id == applied_id, selected=ref.id == working_id, on_select=self._selector(ref)
            )
            if ref.kind == "preset":
                self.preset_flow.insert(card_widget, -1)
            else:
                self.user_flow.insert(card_widget, -1)
                user_count += 1
        self.empty_card.set_visible(user_count == 0)
        self.user_flow.set_visible(user_count > 0)
        self.delete_btn.set_sensitive(self._working_ref() is not None)

    def _working_ref(self):
        for ref in self.state.themes():
            if ref.kind == "user" and ref.id == self.state.working.id:
                return ref
        return None

    def _selector(self, ref):
        def select() -> None:
            self._select(ref)

        return select

    def _select(self, ref) -> None:
        self.state.load_theme(ref.theme)
        self.state.emit("message", f"Loaded '{ref.name}' — press APPLY to use it", False)
        self.refresh()

    def _delete_selected(self) -> None:
        ref = self._working_ref()
        if ref is None:
            self.state.emit("message", "Select one of your own themes to delete it (presets cannot be deleted).", True)
            return
        self.state.emit("message", f"__delete__:{ref.id}", False)

    def on_themes_changed(self) -> None:
        self.refresh()

    def on_applied(self) -> None:
        self.refresh()

    def on_theme_changed(self, what: str) -> None:
        if what == "theme":
            self.refresh()
