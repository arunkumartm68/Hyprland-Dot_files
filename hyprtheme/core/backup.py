"""Backup manager.

Every time HyprTheme is about to overwrite a file it stores the current
version in a timestamped snapshot under ``$XDG_STATE_HOME/hyprtheme/backups``.
Snapshots are self-describing (``manifest.json``) so they can be restored by
the GUI, by the CLI or by hand.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import paths

MANIFEST = "manifest.json"
FILES_DIR = "files"


class BackupError(RuntimeError):
    pass


@dataclass
class BackupEntry:
    original: Path
    stored: Path  # relative to snapshot/files
    existed: bool

    def to_dict(self) -> dict[str, Any]:
        return {"original": str(self.original), "stored": str(self.stored), "existed": self.existed}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupEntry:
        return cls(Path(data["original"]), Path(data["stored"]), bool(data.get("existed", True)))


@dataclass
class Backup:
    id: str
    path: Path
    label: str
    created: float
    kind: str = "apply"  # apply | manual | initial
    theme_name: str = ""
    theme_id: str = ""
    previous_theme: dict[str, Any] | None = None
    entries: list[BackupEntry] = field(default_factory=list)

    @property
    def created_text(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.created))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "created": self.created,
            "kind": self.kind,
            "theme_name": self.theme_name,
            "theme_id": self.theme_id,
            "previous_theme": self.previous_theme,
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def load(cls, snapshot_dir: Path) -> Backup:
        manifest = snapshot_dir / MANIFEST
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return cls(
            id=str(data.get("id") or snapshot_dir.name),
            path=snapshot_dir,
            label=str(data.get("label", "")),
            created=float(data.get("created", snapshot_dir.stat().st_mtime)),
            kind=str(data.get("kind", "apply")),
            theme_name=str(data.get("theme_name", "")),
            theme_id=str(data.get("theme_id", "")),
            previous_theme=data.get("previous_theme"),
            entries=[BackupEntry.from_dict(e) for e in data.get("entries", [])],
        )


def _stored_name(original: Path) -> Path:
    """Map an absolute path to a relative, collision free location inside the snapshot."""
    try:
        rel = original.resolve().relative_to(paths.home().resolve())
        return Path("home") / rel
    except ValueError:
        return Path("root") / original.resolve().relative_to("/")


class BackupManager:
    def __init__(self, root: Path | None = None, limit: int = 25):
        self.root = root or paths.backups_dir()
        self.limit = limit

    # --- creation ------------------------------------------------------------------

    def create(
        self,
        files: list[Path],
        *,
        label: str = "",
        kind: str = "apply",
        theme_name: str = "",
        theme_id: str = "",
        previous_theme: dict[str, Any] | None = None,
    ) -> Backup:
        """Snapshot the given files (missing files are recorded so a restore can remove them)."""
        self.root.mkdir(parents=True, exist_ok=True)
        now = time.time()
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
        backup_id = stamp
        snapshot = self.root / backup_id
        counter = 1
        while snapshot.exists():
            counter += 1
            backup_id = f"{stamp}-{counter}"
            snapshot = self.root / backup_id
        (snapshot / FILES_DIR).mkdir(parents=True)
        backup = Backup(
            id=backup_id,
            path=snapshot,
            label=label or kind,
            created=now,
            kind=kind,
            theme_name=theme_name,
            theme_id=theme_id,
            previous_theme=previous_theme,
        )
        seen: set[Path] = set()
        for original in files:
            original = Path(original).expanduser()
            if original in seen:
                continue
            seen.add(original)
            stored = _stored_name(original)
            if original.exists():
                dest = snapshot / FILES_DIR / stored
                dest.parent.mkdir(parents=True, exist_ok=True)
                if original.is_dir():
                    shutil.copytree(original, dest, symlinks=True)
                else:
                    shutil.copy2(original, dest, follow_symlinks=False)
                backup.entries.append(BackupEntry(original, stored, True))
            else:
                backup.entries.append(BackupEntry(original, stored, False))
        (snapshot / MANIFEST).write_text(json.dumps(backup.to_dict(), indent=2) + "\n", encoding="utf-8")
        self.prune()
        return backup

    # --- listing -------------------------------------------------------------------

    def snapshots(self) -> list[Backup]:
        if not self.root.exists():
            return []
        backups: list[Backup] = []
        for entry in self.root.iterdir():
            if entry.is_dir() and (entry / MANIFEST).exists():
                try:
                    backups.append(Backup.load(entry))
                except (OSError, ValueError, KeyError):
                    continue
        backups.sort(key=lambda b: b.created, reverse=True)
        return backups

    def get(self, backup_id: str) -> Backup | None:
        snapshot = self.root / backup_id
        if (snapshot / MANIFEST).exists():
            return Backup.load(snapshot)
        return None

    def latest(self, kind: str | None = None) -> Backup | None:
        for backup in self.snapshots():
            if kind is None or backup.kind == kind:
                return backup
        return None

    # --- restore / delete ----------------------------------------------------------

    def restore(self, backup: Backup | str, *, remove_new_files: bool = True) -> list[Path]:
        """Copy every file of the snapshot back to its original location.

        Files that did not exist when the snapshot was taken are removed again
        (``remove_new_files``), which is what makes a rollback exact.  The
        current versions are themselves snapshotted first, so a restore can be
        undone.
        """
        if isinstance(backup, str):
            found = self.get(backup)
            if found is None:
                raise BackupError(f"backup {backup!r} not found")
            backup = found
        originals = [e.original for e in backup.entries]
        self.create(originals, label=f"before restoring {backup.id}", kind="pre-restore")
        restored: list[Path] = []
        for entry in backup.entries:
            src = backup.path / FILES_DIR / entry.stored
            if entry.existed and src.exists():
                entry.original.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    if entry.original.exists():
                        shutil.rmtree(entry.original)
                    shutil.copytree(src, entry.original, symlinks=True)
                else:
                    shutil.copy2(src, entry.original, follow_symlinks=False)
                restored.append(entry.original)
            elif not entry.existed and remove_new_files and entry.original.exists():
                if entry.original.is_dir():
                    shutil.rmtree(entry.original)
                else:
                    entry.original.unlink()
                restored.append(entry.original)
        return restored

    def delete(self, backup_id: str) -> None:
        snapshot = self.root / backup_id
        if not (snapshot / MANIFEST).exists():
            raise BackupError(f"backup {backup_id!r} not found")
        shutil.rmtree(snapshot)

    def prune(self) -> int:
        """Delete the oldest automatic snapshots beyond the configured limit."""
        removed = 0
        automatic = [b for b in self.snapshots() if b.kind in ("apply", "pre-restore")]
        for backup in automatic[self.limit :]:
            shutil.rmtree(backup.path, ignore_errors=True)
            removed += 1
        return removed

    def has_initial(self) -> bool:
        return any(b.kind == "initial" for b in self.snapshots())
