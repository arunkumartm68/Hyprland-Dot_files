"""Backup & Restore: snapshots, rollback, restore original configuration."""

from __future__ import annotations

from gi.repository import Gtk

from ...core import paths
from ..components import button, card, clear_children, icon_button, label
from .base import Page


class BackupPage(Page):
    key = "backup"
    title = "Backup & Restore"
    subtitle = "Every apply snapshots the files it replaces. Nothing of yours is ever deleted without a backup."

    def build(self) -> None:
        actions = Gtk.Box(spacing=8)
        actions.append(button("CREATE BACKUP", "ht-add-symbolic", primary=True, on_click=self._create))
        actions.append(
            button("ROLLBACK LAST CHANGE", "ht-rollback-symbolic", on_click=lambda: self.state.emit("message", "__rollback__", False))
        )
        actions.append(
            button(
                "RESTORE ORIGINAL CONFIGS",
                "ht-reset-symbolic",
                danger=True,
                on_click=lambda: self.state.emit("message", "__reset_original__", False),
                tooltip="Put back the configuration files exactly as they were before HyprTheme first touched them",
            )
        )
        self.content.append(actions)

        info, ibody = card("Where backups live")
        ibody.append(label(paths.display_path(paths.backups_dir()), "ht-mono", "ht-small"))
        ibody.append(
            label(
                "Each snapshot is a folder with a manifest.json and the original files, so you can also restore by hand.",
                "ht-muted",
                "ht-small",
                wrap=True,
            )
        )
        self.content.append(info)

        lc, lbody = card("Snapshots")
        self.list = Gtk.ListBox()
        self.list.add_css_class("ht-list")
        self.list.set_selection_mode(Gtk.SelectionMode.NONE)
        lbody.append(self.list)
        self.empty = label("No backups yet.", "ht-muted", "ht-small")
        lbody.append(self.empty)
        self.content.append(lc)
        self.refresh()

    def refresh(self) -> None:
        clear_children(self.list)
        backups = self.state.engine.list_backups()
        self.empty.set_visible(not backups)
        for b in backups:
            row = Gtk.ListBoxRow()
            row.set_activatable(False)
            box = Gtk.Box(spacing=12)
            texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
            head = Gtk.Box(spacing=8)
            head.append(label(b.label or b.kind, "ht-row-label"))
            kind = label(b.kind.upper(), "ht-theme-card-badge")
            head.append(kind)
            texts.append(head)
            texts.append(
                label(
                    f"{b.created_text}  ·  {b.id}  ·  {len(b.entries)} file(s)" + (f"  ·  theme: {b.theme_name}" if b.theme_name else ""),
                    "ht-row-desc",
                    "ht-mono",
                )
            )
            box.append(texts)
            box.append(icon_button("ht-rollback-symbolic", "Restore this snapshot", on_click=self._restorer(b.id)))
            if b.kind != "initial":
                box.append(icon_button("ht-delete-symbolic", "Delete this snapshot", on_click=self._deleter(b.id)))
            row.set_child(box)
            self.list.append(row)

    def _restorer(self, backup_id: str):
        def restore() -> None:
            self.state.emit("message", f"__restore__:{backup_id}", False)

        return restore

    def _deleter(self, backup_id: str):
        def delete() -> None:
            self.state.delete_backup(backup_id)

        return delete

    def _create(self) -> None:
        self.state.create_backup("manual backup")

    def on_applied(self) -> None:
        self.refresh()

    def on_show(self) -> None:
        self.refresh()
