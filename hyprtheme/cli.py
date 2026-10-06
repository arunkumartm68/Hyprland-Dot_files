"""Command-line interface.

The CLI and the GUI share :class:`hyprtheme.core.engine.ThemeEngine`, so
``hyprtheme apply cyan`` and clicking APPLY in the app do exactly the same
thing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import paths
from .core.engine import ApplyResult, EngineError, ThemeEngine
from .core.portable import PortableError
from .core.settings import INTEGRATION_MODES, WALLPAPER_BACKENDS, Settings
from .core.theme import COLOR_NAMES, Theme, ThemeError

STATUS_ICON = {"installed": "✓", "missing": "⚠", "error": "✕"}


def _engine() -> ThemeEngine:
    return ThemeEngine()


def _print_apply(result: ApplyResult, verbose: bool = False) -> int:
    print(f"Applied theme: {result.theme.name}")
    print("  " + result.summary())
    if verbose:
        for p in result.written:
            print(f"  wrote     {paths.display_path(p)}")
        for p in result.injected:
            print(f"  included  {paths.display_path(p)}")
    for warning in result.plan.warnings:
        print(f"  warning: {warning}")
    if result.backup:
        print(f"  backup: {result.backup.id}")
    if result.wallpaper:
        mark = "✓" if result.wallpaper.ok else "✕"
        print(f"  wallpaper [{result.wallpaper.backend}] {mark} {result.wallpaper.message}")
    if result.reload:
        for r in result.reload.results:
            mark = "✓" if r.ok else "✕"
            if verbose or not r.ok:
                print(f"  reload {r.component}: {mark} {r.message}")
    return 0 if result.ok else 1


# --- commands -----------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> int:
    engine = _engine()
    current = engine.current()
    refs = engine.list_themes()
    if args.json:
        print(
            json.dumps(
                [{"id": r.id, "name": r.name, "kind": r.kind, "path": str(r.path), "accent": r.theme.colors["primary"]} for r in refs],
                indent=2,
            )
        )
        return 0
    if not refs:
        print("No themes found. Check that presets are installed.")
        return 1
    for ref in refs:
        mark = "●" if current and current.theme.id == ref.id else " "
        print(f"{mark} {ref.id:<16} {ref.name:<16} {ref.theme.colors['primary']}  [{ref.kind}]  {ref.theme.description}")
    return 0


def cmd_current(args: argparse.Namespace) -> int:
    engine = _engine()
    current = engine.current()
    if current is None:
        print("No theme applied yet.")
        return 1
    t = current.theme
    if args.json:
        print(json.dumps({"theme": t.to_dict(), "applied_at": current.applied_at, "backup_id": current.backup_id}, indent=2))
        return 0
    print(f"{t.name} ({t.id})")
    print(f"  accent:     {t.colors['primary']}")
    print(f"  wallpaper:  {t.wallpaper.get('path') or '—'}")
    print(f"  applied:    {current.applied_text}")
    if current.backup_id:
        print(f"  rollback:   backup {current.backup_id}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    engine = _engine()
    theme = engine.get(args.theme)
    print(theme.to_json(), end="")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    engine = _engine()
    theme = engine.get(args.theme)
    if args.wallpaper:
        theme.wallpaper["path"] = str(Path(args.wallpaper).expanduser())
    result = engine.apply(theme, dry_run=args.dry_run, reload=False if args.no_reload else None, set_wallpaper=not args.no_wallpaper)
    if args.dry_run:
        print(f"Dry run for theme: {theme.name}")
        for f in result.plan.files:
            print(f"  would write    {paths.display_path(f.path)}")
        for inj in result.plan.injections:
            print(f"  would include  {paths.display_path(inj.path)}: {inj.lines[0]}")
        for comp, reason in result.plan.skipped.items():
            print(f"  skip {comp}: {reason}")
        return 0
    return _print_apply(result, verbose=args.verbose)


def cmd_save(args: argparse.Namespace) -> int:
    engine = _engine()
    if args.source:
        theme = engine.get(args.source)
    else:
        current = engine.current()
        if current is None:
            print("No theme applied yet; use --from <theme>.", file=sys.stderr)
            return 1
        theme = current.theme
    path = engine.save(theme, args.name, overwrite=args.force or not args.no_overwrite)
    print(f"Saved '{theme.name}' to {paths.display_path(path)}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    engine = _engine()
    path = engine.delete(args.theme)
    print(f"Deleted {paths.display_path(path)}")
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    engine = _engine()
    backup, previous = engine.rollback(reload=False if args.no_reload else None)
    print(f"Rolled back using backup {backup.id} ({backup.label})")
    print(f"  current theme is now: {previous.name if previous else 'none'}")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    engine = _engine()
    if args.original:
        backup = engine.reset(original=True)
        print(f"Restored original configuration from backup {getattr(backup, 'id', '?')}")
        return 0
    result = engine.reset()
    assert isinstance(result, ApplyResult)
    return _print_apply(result, verbose=args.verbose)


def cmd_export(args: argparse.Namespace) -> int:
    engine = _engine()
    if args.theme:
        theme = engine.get(args.theme)
    else:
        current = engine.current()
        if current is None:
            print("No theme applied yet; pass a theme name.", file=sys.stderr)
            return 1
        theme = current.theme
    dest = engine.export(theme, Path(args.destination).expanduser(), embed_wallpaper=args.embed_wallpaper)
    print(f"Exported '{theme.name}' to {paths.display_path(dest)}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    engine = _engine()
    theme = engine.import_file(Path(args.source).expanduser(), new_name=args.name, overwrite=args.force)
    print(f"Imported '{theme.name}' as {theme.id} ({paths.display_path(theme.source) if theme.source else ''})")
    if args.apply:
        return _print_apply(engine.apply(theme), verbose=args.verbose)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    engine = _engine()
    infos = engine.detect_components(with_version=not args.fast)
    if args.json:
        print(json.dumps({k: v.__dict__ for k, v in infos.items()}, indent=2, default=str))
        return 0
    current = engine.current()
    print(f"HyprTheme {__version__}")
    print(f"  current theme: {current.theme.name if current else '—'}")
    print(f"  config dir:    {paths.display_path(paths.app_config_dir())}")
    print(f"  state dir:     {paths.display_path(paths.app_state_dir())}")
    print(f"  wallpaper:     {engine.wallpapers.backend() or 'no daemon found'}")
    print("components:")
    for key, info in infos.items():
        mode = engine.settings.integration(key) if key in ("hyprland", "waybar", "kitty", "rofi", "swaync", "hyprlock", "wlogout") else "-"
        version = f" {info.version}" if info.version else ""
        print(f"  {STATUS_ICON[info.status]} {info.label:<10} {info.status_label:<24} mode={mode:<9}{version}")
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    engine = _engine()
    if args.backup_cmd == "create":
        backup = engine.create_backup(args.label or "manual backup")
        print(f"Created backup {backup.id} with {len(backup.entries)} file(s)")
        return 0
    if args.backup_cmd == "restore":
        backup = engine.restore_backup(args.id)
        print(f"Restored backup {backup.id} ({backup.label})")
        return 0
    if args.backup_cmd == "delete":
        engine.delete_backup(args.id)
        print(f"Deleted backup {args.id}")
        return 0
    backups = engine.list_backups()
    if not backups:
        print("No backups yet.")
        return 0
    for b in backups:
        print(f"{b.id}  {b.created_text}  [{b.kind:<11}] {len(b.entries):>3} file(s)  {b.label}")
    return 0


def cmd_wallpaper(args: argparse.Namespace) -> int:
    engine = _engine()
    if args.wallpaper_cmd == "restore":
        result = engine.wallpapers.restore()
        print(f"[{result.backend}] {result.message}")
        return 0 if result.ok else 1
    if args.wallpaper_cmd == "set":
        path = Path(args.path).expanduser()
        result = engine.wallpapers.set(path, transition=args.transition, duration=args.duration, fit=args.fit)
        if result.ok:
            current = engine.current()
            theme = current.theme if current else engine.default_theme()
            theme.wallpaper["path"] = str(path)
            engine.wallpapers.save_state(theme, path)
        print(f"[{result.backend}] {result.message}")
        return 0 if result.ok else 1
    from .core.wallpaper import list_wallpapers

    for p in list_wallpapers():
        print(paths.display_path(p))
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    settings = Settings.load()
    if args.key is None:
        print(json.dumps(settings.data, indent=2))
        return 0
    if args.value is None:
        print(json.dumps(settings.data.get(args.key) if "." not in args.key else settings.integration(args.key.split(".", 1)[1])))
        return 0
    key, value = args.key, args.value
    if key.startswith("integration."):
        comp = key.split(".", 1)[1]
        if value not in INTEGRATION_MODES:
            print(f"mode must be one of {INTEGRATION_MODES}", file=sys.stderr)
            return 2
        settings.set_integration(comp, value)
    elif key == "wallpaper_backend":
        if value not in WALLPAPER_BACKENDS:
            print(f"backend must be one of {WALLPAPER_BACKENDS}", file=sys.stderr)
            return 2
        settings.wallpaper_backend = value
    elif value.lower() in ("true", "false"):
        settings.set(key, value.lower() == "true")
    elif value.isdigit():
        settings.set(key, int(value))
    else:
        settings.set(key, value)
    settings.save()
    print(f"{key} = {value}")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    engine = _engine()
    base = engine.get(args.base) if args.base else engine.default_theme()
    theme = base.copy()
    theme.preset = False
    for assignment in args.set or []:
        if "=" not in assignment:
            print(f"bad --set value {assignment!r}, expected key=value", file=sys.stderr)
            return 2
        key, value = assignment.split("=", 1)
        if key in COLOR_NAMES:
            try:
                theme.set_color(key, value)
            except (ThemeError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 2
        elif key in theme.effects:
            current = theme.effects[key]
            if isinstance(current, bool):
                theme.effects[key] = value.lower() in ("1", "true", "yes", "on")
            elif isinstance(current, int):
                theme.effects[key] = int(float(value))
            else:
                theme.effects[key] = float(value)
        elif key == "wallpaper":
            theme.wallpaper["path"] = value
        else:
            print(f"unknown key {key!r}", file=sys.stderr)
            return 2
    theme.normalize()
    path = engine.save(theme, args.name)
    print(f"Created '{theme.name}' at {paths.display_path(path)}")
    if args.apply:
        return _print_apply(engine.apply(theme))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        theme = Theme.load(Path(args.file).expanduser(), strict=False)
    except ThemeError as exc:
        print(f"✕ {exc}")
        return 1
    problems = theme.validate()
    if problems:
        for p in problems:
            print(f"✕ {p}")
        return 1
    print(f"✓ {theme.name} is valid")
    return 0


def cmd_gui(_args: argparse.Namespace) -> int:
    try:
        from .app.main import run
    except ImportError as exc:
        print(f"The GUI needs GTK4 and libadwaita (python-gobject): {exc}", file=sys.stderr)
        return 1
    return run()


# --- parser ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hyprtheme", description="HyprTheme — Hyprland Theme Control Center")
    parser.add_argument("--version", action="version", version=f"hyprtheme {__version__}")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("list", help="list available themes")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("current", help="show the currently applied theme")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_current)

    p = sub.add_parser("show", help="print a theme definition as JSON")
    p.add_argument("theme")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("apply", help="apply a theme to the desktop")
    p.add_argument("theme", help="theme id, name or path to a .json/.hyprtheme file")
    p.add_argument("--wallpaper", help="override the wallpaper for this apply")
    p.add_argument("--dry-run", action="store_true", help="show what would be written")
    p.add_argument("--no-reload", action="store_true", help="write configs but do not reload components")
    p.add_argument("--no-wallpaper", action="store_true", help="do not touch the wallpaper")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("save", help="save the current theme under a new name")
    p.add_argument("name")
    p.add_argument("--from", dest="source", help="save this theme instead of the current one")
    p.add_argument("--no-overwrite", action="store_true")
    p.add_argument("-f", "--force", action="store_true")
    p.set_defaults(func=cmd_save)

    p = sub.add_parser("new", help="create a custom theme from a base theme")
    p.add_argument("name")
    p.add_argument("--base", help="base theme (default: cyan)")
    p.add_argument("--set", action="append", metavar="KEY=VALUE", help="override a color/effect, e.g. primary=#FF00AA or blur=20")
    p.add_argument("--apply", action="store_true")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("delete", help="delete a user theme")
    p.add_argument("theme")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("rollback", help="undo the last apply")
    p.add_argument("--no-reload", action="store_true")
    p.set_defaults(func=cmd_rollback)

    p = sub.add_parser("reset", help="reset to the default theme (or --original to restore pre-HyprTheme configs)")
    p.add_argument("--original", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_reset)

    p = sub.add_parser("export", help="export a theme to a portable .hyprtheme file")
    p.add_argument("destination")
    p.add_argument("--theme", help="theme to export (default: current)")
    p.add_argument("--embed-wallpaper", action="store_true", help="embed the wallpaper image in the file")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("import", help="import a .hyprtheme file into your themes")
    p.add_argument("source")
    p.add_argument("--name", help="rename the imported theme")
    p.add_argument("--apply", action="store_true")
    p.add_argument("-f", "--force", action="store_true", help="overwrite an existing theme with the same id")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("status", help="show detected components and integration modes")
    p.add_argument("--json", action="store_true")
    p.add_argument("--fast", action="store_true", help="skip version probing")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("backup", help="manage configuration backups")
    bs = p.add_subparsers(dest="backup_cmd")
    bs.add_parser("list")
    b = bs.add_parser("create")
    b.add_argument("--label")
    b = bs.add_parser("restore")
    b.add_argument("id")
    b = bs.add_parser("delete")
    b.add_argument("id")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("wallpaper", help="wallpaper helpers")
    ws = p.add_subparsers(dest="wallpaper_cmd")
    ws.add_parser("list")
    ws.add_parser("restore", help="re-apply the last wallpaper (used at login)")
    w = ws.add_parser("set")
    w.add_argument("path")
    w.add_argument("--transition", default="grow")
    w.add_argument("--duration", type=float, default=1.5)
    w.add_argument("--fit", default="crop")
    p.set_defaults(func=cmd_wallpaper)

    p = sub.add_parser("config", help="read or change HyprTheme settings")
    p.add_argument("key", nargs="?", help="e.g. integration.waybar, wallpaper_backend, reload_on_apply")
    p.add_argument("value", nargs="?")
    p.set_defaults(func=cmd_config)

    p = sub.add_parser("validate", help="validate a theme file")
    p.add_argument("file")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("gui", help="launch the graphical control center")
    p.set_defaults(func=cmd_gui)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    try:
        return int(args.func(args))
    except (EngineError, PortableError, ThemeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
