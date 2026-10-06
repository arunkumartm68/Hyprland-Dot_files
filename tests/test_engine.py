from pathlib import Path

import pytest

from hyprtheme.core import paths
from hyprtheme.core.engine import EngineError, ThemeEngine
from hyprtheme.core.theme import Theme

from .conftest import REPO, wallpaper_file


def test_list_and_find(engine: ThemeEngine):
    refs = engine.list_themes()
    assert len(refs) >= 17
    assert refs[0].id == "cyan"
    assert engine.find("Iron Man").id == "iron-man"
    assert engine.find("iron-man").kind == "preset"
    assert engine.find("nope") is None
    with pytest.raises(EngineError):
        engine.get("nope")


def test_apply_writes_configs_and_includes(engine: ThemeEngine, fake_home: Path):
    hyprland_conf = paths.hypr_dir() / "hyprland.conf"
    before = hyprland_conf.read_text()
    result = engine.apply(engine.get("cyan"))
    assert result.ok and not result.dry_run
    assert (paths.hypr_dir() / "hyprtheme.conf").exists()
    assert (paths.waybar_dir() / "style.css").exists()
    assert (paths.kitty_dir() / "hyprtheme.conf").exists()
    assert (paths.rofi_dir() / "hyprtheme.rasi").exists()
    assert (paths.swaync_dir() / "style.css").exists()
    assert (paths.hypr_dir() / "hyprlock.conf").exists()
    assert (paths.wlogout_dir() / "style.css").exists()
    after = hyprland_conf.read_text()
    assert after.startswith(before)  # user config preserved, block appended
    assert "source = " in after and "hyprtheme.conf" in after
    assert "include hyprtheme.conf" in (paths.kitty_dir() / "kitty.conf").read_text()
    assert '@theme "' in (paths.rofi_dir() / "config.rasi").read_text()
    current = engine.current()
    assert current and current.theme.id == "cyan"
    assert result.backup and result.backup.kind == "apply"
    assert engine.backups.has_initial()


def test_switching_presets_changes_desktop_configs(engine: ThemeEngine):
    engine.apply(engine.get("cyan"))
    conf = (paths.hypr_dir() / "hyprtheme.conf").read_text()
    waybar = (paths.waybar_dir() / "style.css").read_text()
    assert "rgba(00e5ffff)" in conf and "#00E5FF" in waybar
    engine.apply(engine.get("red"))
    conf = (paths.hypr_dir() / "hyprtheme.conf").read_text()
    waybar = (paths.waybar_dir() / "style.css").read_text()
    kitty = (paths.kitty_dir() / "hyprtheme.conf").read_text()
    assert "rgba(ff2e2eff)" in conf and "#FF2E2E" in waybar and "#FF2E2E" in kitty
    assert "00e5ff" not in conf
    assert engine.current().theme.id == "red"
    # second apply only adds one managed block, never duplicates
    assert (paths.hypr_dir() / "hyprland.conf").read_text().count(">>> hyprtheme hyprland.conf >>>") == 1


def test_dry_run_writes_nothing(engine: ThemeEngine):
    result = engine.apply(engine.get("green"), dry_run=True)
    assert result.dry_run and result.plan.files
    assert not (paths.hypr_dir() / "hyprtheme.conf").exists()
    assert engine.current() is None


def test_rollback_restores_previous_theme_and_files(engine: ThemeEngine):
    engine.apply(engine.get("cyan"))
    cyan_style = (paths.waybar_dir() / "style.css").read_text()
    engine.apply(engine.get("red"))
    assert (paths.waybar_dir() / "style.css").read_text() != cyan_style
    backup, previous = engine.rollback()
    assert previous is not None and previous.id == "cyan"
    assert (paths.waybar_dir() / "style.css").read_text() == cyan_style
    assert engine.current().theme.id == "cyan"
    # rolling back again goes further back (to the pre-cyan state)
    backup2, previous2 = engine.rollback()
    assert backup2.id != backup.id
    assert previous2 is None
    assert engine.current() is None
    with pytest.raises(EngineError):
        engine.rollback()


def test_reset_original_restores_pristine_configs(engine: ThemeEngine):
    hyprland_conf = paths.hypr_dir() / "hyprland.conf"
    original = hyprland_conf.read_text()
    engine.apply(engine.get("cyan"))
    assert hyprland_conf.read_text() != original
    engine.reset(original=True)
    assert hyprland_conf.read_text() == original
    assert not (paths.hypr_dir() / "hyprtheme.conf").exists()
    assert not (paths.wlogout_dir() / "style.css").exists()
    assert engine.current() is None


def test_reset_applies_default(engine: ThemeEngine):
    engine.apply(engine.get("red"))
    result = engine.reset()
    assert result.theme.id == "cyan"
    assert engine.current().theme.id == "cyan"


def test_save_custom_theme_and_modified_preset(engine: ThemeEngine):
    theme = engine.get("pink").copy()
    theme.colors["primary"] = "#123456"
    path = engine.save(theme, "My Theme")
    assert path == paths.user_themes_dir() / "my-theme.json"
    ref = engine.find("My Theme")
    assert ref and ref.kind == "user" and ref.theme.colors["primary"] == "#123456"
    assert ref.theme.preset is False
    # saving a preset without renaming never touches the preset file
    preset_path = REPO / "themes" / "presets" / "pink.json"
    before = preset_path.read_text()
    p2 = engine.save(engine.get("pink"))
    assert p2.name == "pink-custom.json"
    assert preset_path.read_text() == before
    # user theme can be applied and deleted; presets cannot be deleted
    engine.apply(ref.theme)
    assert engine.current().theme.name == "My Theme"
    engine.delete("My Theme")
    assert engine.find("My Theme") is None
    with pytest.raises(EngineError):
        engine.delete("cyan")


def test_save_rejects_invalid_theme(engine: ThemeEngine):
    theme = Theme.default("broken")
    theme.colors["primary"] = "#nope"
    with pytest.raises(EngineError):
        engine.save(theme, "broken")
    with pytest.raises(EngineError):
        engine.apply(theme)


def test_export_import_roundtrip(engine: ThemeEngine, fake_home: Path, tmp_path: Path):
    theme = engine.get("sunset").copy()
    theme.colors["highlight"] = "#ABCDEF"
    theme.effects["blur"] = 33
    wp = wallpaper_file(fake_home)
    theme.wallpaper["path"] = str(wp)
    dest = engine.export(theme, tmp_path / "sunset-custom")
    assert dest.suffix == ".hyprtheme"
    text = dest.read_text()
    assert str(fake_home) not in text  # no personal paths leak
    assert '"path": "test.png"' in text
    imported = engine.import_file(dest, new_name="Sunset Custom")
    assert imported.id == "sunset-custom"
    assert imported.colors["highlight"] == "#ABCDEF" and imported.effects["blur"] == 33
    assert imported.preset is False
    assert (paths.user_themes_dir() / "sunset-custom.json").exists()
    # importing again without overwrite yields a unique id
    again = engine.import_file(dest, new_name="Sunset Custom")
    assert again.id == "sunset-custom-2"
    # embedded wallpaper roundtrip
    dest2 = engine.export(theme, tmp_path / "with-wp", embed_wallpaper=True)
    wp.unlink()
    imported2 = engine.import_file(dest2, new_name="With WP")
    assert (paths.user_wallpapers_dir() / "test.png").read_bytes().startswith(b"\x89PNG")
    assert imported2.wallpaper["path"] == "test.png"


def test_import_rejects_garbage(engine: ThemeEngine, tmp_path: Path):
    from hyprtheme.core.portable import PortableError

    bad = tmp_path / "bad.hyprtheme"
    bad.write_text("{not json")
    with pytest.raises(PortableError):
        engine.import_file(bad)
    bad.write_text('{"format": "hyprtheme", "format_version": 99, "theme": {}}')
    with pytest.raises(PortableError):
        engine.import_file(bad)


def test_manual_backup_and_restore(engine: ThemeEngine):
    engine.apply(engine.get("cyan"))
    style = paths.waybar_dir() / "style.css"
    backup = engine.create_backup("before experiment")
    assert backup.kind == "manual"
    style.write_text("/* user hack */")
    engine.restore_backup(backup.id)
    assert "user hack" not in style.read_text()
    ids = [b.id for b in engine.list_backups()]
    assert backup.id in ids
    engine.delete_backup(backup.id)
    assert backup.id not in [b.id for b in engine.list_backups()]


def test_backup_limit_prunes_old_apply_snapshots(engine: ThemeEngine):
    engine.settings.backup_limit = 3
    engine.backups.limit = 3
    for name in ("cyan", "red", "green", "pink", "white"):
        engine.apply(engine.get(name))
    kinds = [b.kind for b in engine.list_backups()]
    assert kinds.count("apply") == 3
    assert kinds.count("initial") == 1  # the pristine snapshot is never pruned


def test_missing_components_do_not_crash(engine: ThemeEngine, no_binaries):
    infos = engine.detect_components(with_version=False)
    assert all(i.status == "missing" for i in infos.values())
    assert all(i.icon == "⚠" for i in infos.values())
    result = engine.apply(engine.get("matrix"), reload=True)
    assert result.ok
    assert result.reload and not result.reload.failures
    assert engine.wallpapers.backend() is None
    theme = engine.get("ocean").copy()
    theme.wallpaper["path"] = "/does/not/exist.png"
    result = engine.apply(theme)
    assert result.wallpaper is not None and not result.wallpaper.ok
    assert "not found" in result.wallpaper.message
    assert (paths.hypr_dir() / "hyprtheme.conf").exists()  # everything else still applied


def test_history_records_applies(engine: ThemeEngine):
    engine.apply(engine.get("cyan"))
    engine.apply(engine.get("red"))
    history = engine.history()
    assert [h["id"] for h in history] == ["cyan", "red"]
