import json
from pathlib import Path

import pytest

from hyprtheme.cli import main
from hyprtheme.core import paths
from hyprtheme.core.settings import Settings


@pytest.fixture(autouse=True)
def _cli_settings(fake_home: Path):
    s = Settings.load()
    s.reload_on_apply = False
    s.set("hyprland_syntax", "modern")
    s.set("hyprpaper_syntax", "modern")
    s.save()


def run(*argv: str, capsys) -> tuple[int, str]:
    code = main(list(argv))
    out = capsys.readouterr()
    return code, out.out + out.err


def test_list_current_apply_flow(capsys):
    code, out = run("list", capsys=capsys)
    assert code == 0 and "cyan" in out and "iron-man" in out
    code, out = run("current", capsys=capsys)
    assert code == 1 and "No theme" in out
    code, out = run("apply", "cyan", capsys=capsys)
    assert code == 0 and "Applied theme: Cyan" in out
    code, out = run("current", capsys=capsys)
    assert code == 0 and "Cyan" in out
    code, out = run("apply", "Iron Man", capsys=capsys)
    assert code == 0 and "Iron Man" in out
    code, out = run("list", "--json", capsys=capsys)
    assert code == 0 and json.loads(out)[0]["id"] == "cyan"


def test_dry_run(capsys):
    code, out = run("apply", "cyan", "--dry-run", capsys=capsys)
    assert code == 0 and "would write" in out
    assert not (paths.hypr_dir() / "hyprtheme.conf").exists()


def test_save_rollback_reset(capsys):
    run("apply", "cyan", capsys=capsys)
    run("apply", "red", capsys=capsys)
    code, out = run("save", "My Theme", capsys=capsys)
    assert code == 0 and (paths.user_themes_dir() / "my-theme.json").exists()
    code, out = run("rollback", capsys=capsys)
    assert code == 0 and "Cyan" in out
    code, out = run("reset", capsys=capsys)
    assert code == 0 and "Cyan" in out
    code, out = run("reset", "--original", capsys=capsys)
    assert code == 0 and "Restored original" in out


def test_new_export_import_delete(capsys, tmp_path: Path):
    code, out = run(
        "new", "Custom One", "--base", "pink", "--set", "primary=#ABCDEF", "--set", "blur=20", "--set", "glass=false", capsys=capsys
    )
    assert code == 0
    data = json.loads((paths.user_themes_dir() / "custom-one.json").read_text())
    assert data["colors"]["primary"] == "#ABCDEF" and data["effects"]["blur"] == 20 and data["effects"]["glass"] is False
    code, out = run("new", "Bad", "--set", "primary=#zz", capsys=capsys)
    assert code == 2
    dest = tmp_path / "custom.hyprtheme"
    code, out = run("export", str(dest), "--theme", "Custom One", capsys=capsys)
    assert code == 0 and dest.exists()
    code, out = run("import", str(dest), "--name", "Imported One", capsys=capsys)
    assert code == 0 and (paths.user_themes_dir() / "imported-one.json").exists()
    code, out = run("validate", str(dest), capsys=capsys)
    assert code == 0 and "valid" in out
    code, out = run("delete", "Imported One", capsys=capsys)
    assert code == 0
    code, out = run("delete", "cyan", capsys=capsys)
    assert code == 1 and "presets cannot be deleted" in out


def test_status_backup_config(capsys):
    code, out = run("status", "--fast", capsys=capsys)
    assert code == 0 and "components:" in out and "Waybar" in out
    code, out = run("status", "--json", "--fast", capsys=capsys)
    assert code == 0 and "hyprland" in json.loads(out)
    run("apply", "cyan", capsys=capsys)
    code, out = run("backup", "create", "--label", "mine", capsys=capsys)
    assert code == 0 and "Created backup" in out
    code, out = run("backup", "list", capsys=capsys)
    assert code == 0 and "mine" in out
    backup_id = out.splitlines()[0].split()[0]
    code, out = run("backup", "restore", backup_id, capsys=capsys)
    assert code == 0
    code, out = run("config", "integration.waybar", "variables", capsys=capsys)
    assert code == 0 and Settings.load().integration("waybar") == "variables"
    code, out = run("config", "integration.waybar", "bogus", capsys=capsys)
    assert code == 2
    code, out = run("config", capsys=capsys)
    assert code == 0 and json.loads(out)["integration"]["waybar"] == "variables"


def test_unknown_theme_errors(capsys):
    code, out = run("apply", "does-not-exist", capsys=capsys)
    assert code == 1 and "theme not found" in out


def test_no_args_prints_help(capsys):
    code, out = run(capsys=capsys)
    assert code == 0 and "usage" in out.lower()
