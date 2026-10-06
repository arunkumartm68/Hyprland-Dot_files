# Contributing to HyprTheme

Thanks for helping make HyprTheme better. This page explains how the project is laid out, how to run it from a checkout, and what a good pull request looks like.

## Running from a checkout

```bash
git clone https://github.com/arunkumartm68/Hyprland-Dot_files.git
cd Hyprland-Dot_files
python -m hyprtheme list            # CLI, no install needed
python -m hyprtheme gui             # GUI (needs python-gobject, gtk4, libadwaita)
```

When run from the repository, presets and templates are read from the checkout. Nothing under `~/.config` is touched until you run `apply`.

## Development setup

```bash
sudo pacman -S --needed python python-gobject gtk4 libadwaita python-pytest ruff mypy
# or: pip install -e '.[dev]'
```

Checks that must pass before a pull request is merged:

```bash
ruff check hyprtheme tests
ruff format --check hyprtheme tests
mypy
pytest                              # core, generator, engine and CLI tests
xvfb-run pytest tests/test_gui.py   # drives the real GTK app headlessly
```

The test-suite runs entirely inside a temporary `$HOME`, so it never reads or writes your real configuration.

## Project layout

| Path | Purpose |
| --- | --- |
| `hyprtheme/core/` | Theme engine shared by GUI and CLI. No GTK imports here. |
| `hyprtheme/app/` | GTK4 / libadwaita control center (pages, widgets, live preview). |
| `hyprtheme/cli.py` | Command-line interface. |
| `templates/<component>/` | Config templates rendered from a theme. |
| `themes/presets/` | Built-in presets (plain `theme.json` files). |
| `assets/icons/` | Symbolic UI icons and the application icon. |
| `tests/` | pytest suite. |
| `config/` | The original reference dotfiles this project grew out of. |
| `docs/` | Theme format, architecture, CLI and troubleshooting documentation. |

## Adding a preset

1. Copy `themes/presets/cyan.json` to `themes/presets/<id>.json`.
2. Set `name`, `id` (must equal the file name), `description`, `tags`, `order` and the colours.
3. Run `python -m hyprtheme validate themes/presets/<id>.json` and `pytest tests/test_theme.py tests/test_generator.py` (every preset is rendered through every template).

## Changing a template

Templates live in `templates/<component>/` and use the small engine in `hyprtheme/core/templating.py` (`{{ value | filter }}`, `{% if %}`, `{% for %}`). Unknown variables fail loudly, and `tests/test_generator.py` renders every preset through every template, so a typo is caught immediately. Keep generated files self-describing: the header comment must say the file is generated.

When a component's syntax changes upstream (Hyprland did this in 0.53 and again with the Lua config), prefer detecting the version in `hyprtheme/core/generator.py` and branching in the template over dropping support for older releases.

## Pull requests

* One topic per pull request; keep refactors separate from behaviour changes.
* Add or update tests for anything in `hyprtheme/core`.
* Never hard-code personal paths, user names, monitors, GPUs or wallpapers. Use the helpers in `hyprtheme/core/paths.py`.
* Anything that writes to the user's configuration must go through `ThemeEngine.apply()` so it is backed up first.
* Update `CHANGELOG.md` under *Unreleased*.
