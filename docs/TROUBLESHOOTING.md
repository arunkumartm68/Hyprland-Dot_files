# Troubleshooting

### The GUI does not start: "The GUI needs GTK4 and libadwaita"

Install the bindings and run again:

```bash
sudo pacman -S --needed python-gobject gtk4 libadwaita
```

If you have several Python versions, the launcher created by `install.sh` records the interpreter that has the bindings. Override it with `HYPRTHEME_PYTHON=/usr/bin/python3.12 hyprtheme gui` if needed.

### I applied a theme but nothing changed on the desktop

* Run `hyprtheme status`. A component shown as *Not installed* is skipped on purpose.
* Run `hyprtheme apply <theme> -v` to see the reload results per component.
* **Hyprland:** make sure `~/.config/hypr/hyprland.conf` contains the managed block with `source = ~/.config/hypr/hyprtheme.conf` (added automatically in *managed* mode). Hyprland reloads on file change; `hyprctl reload` forces it.
* **Waybar:** HyprTheme sends `SIGUSR2`; very old Waybar builds need a restart (`pkill waybar; waybar &`). If you start Waybar with `-c`/`-s` pointing at other files, switch Waybar to *variables* mode in Settings and `@import url("hyprtheme-colors.css");` from your own stylesheet.
* **Kitty:** only new windows pick up the theme unless Kitty supports `SIGUSR1` reload (0.23+). Check that `kitty.conf` ends with the managed `include hyprtheme.conf` block.
* **Rofi:** `config.rasi` must contain `@theme "~/.config/rofi/hyprtheme.rasi"` (added in managed mode). The last `@theme` line wins.
* **SwayNC:** restart it once if it was started before the first apply (`swaync-client --reload-css` is used afterwards).

### Hyprland shows a config error after applying

Hyprland changed its rule syntax in 0.53 (and later moved to Lua). HyprTheme auto-detects the running version, but if you apply a theme while Hyprland is not running it assumes a current release. Force the dialect in **Settings → Hyprland rule syntax** (`modern`, `legacy` or `lua`) or with `hyprtheme config hyprland_syntax legacy`, then apply again.

### The wallpaper is not set

* `hyprtheme status` shows the wallpaper backend. Install `swww` (recommended) or `hyprpaper`.
* The file must exist; relative names are searched in `~/.config/hyprtheme/wallpapers`, `~/Pictures/Wallpapers` and `~/Pictures`.
* If your `hyprland.conf` also starts `hyprpaper`, `waypaper --restore` or another wallpaper tool, they will fight. Either remove those lines (HyprTheme restores the wallpaper with its own `exec-once` line) or set the backend to *Off*.
* hyprpaper 0.8 changed its config format; HyprTheme detects the version, override with `hyprtheme config hyprpaper_syntax legacy|modern`.

### Icons in Waybar / Hyprlock show as boxes

Install a Nerd Font and set it as the monospace font on the Components page: `sudo pacman -S ttf-jetbrains-mono-nerd`. The UI font defaults to *Inter* (`inter-font`); any installed font works.

### I want my old configuration back

```bash
hyprtheme rollback          # one step back
hyprtheme reset --original  # everything back to the state before the first apply
```

Snapshots are plain folders under `~/.local/state/hyprtheme/backups/<id>/files/`, so you can also copy files back by hand. `./uninstall.sh --restore` removes HyprTheme and restores the originals in one go.

### `hyprtheme` command not found after installing

`~/.local/bin` is not on your `PATH`. Add `export PATH="$HOME/.local/bin:$PATH"` to your shell profile, or install system-wide with `./install.sh --system`.

### Running from the git checkout

`python -m hyprtheme …` works without installing; presets and templates are read from the checkout. The headless GUI test (`xvfb-run python -m pytest tests/test_gui.py`) is the quickest way to confirm the GTK stack works on your machine.
