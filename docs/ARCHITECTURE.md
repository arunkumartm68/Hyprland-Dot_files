# Architecture

```
GUI (GTK4 / libadwaita)          CLI (argparse)
        │                              │
        └──────────┬───────────────────┘
                   ▼
          ThemeEngine  (hyprtheme/core/engine.py)
                   │
   ┌───────────────┼──────────────────┬──────────────────┐
   ▼               ▼                  ▼                  ▼
 Theme          Generator         BackupManager     WallpaperManager
 (theme.py)     (generator.py)    (backup.py)       (wallpaper.py)
                   │
            Template engine (templating.py)
                   │
     templates/<component>/*.tmpl
                   │
   ┌────┬─────┬────┴────┬───────┬────────┬────────┬──────────┐
   ▼    ▼     ▼         ▼       ▼        ▼        ▼          ▼
 Hyprland Waybar Kitty  Rofi  SwayNC  Hyprlock  Wlogout  hyprpaper/swww
```

## Core (`hyprtheme/core`)

The core has **no GTK dependency** and only uses the Python standard library, so the CLI works on a minimal system and the test-suite runs without a display.

| Module | Responsibility |
| --- | --- |
| `paths.py` | XDG base-directory resolution. Every location (config, data, state, cache, pictures, resource lookup) comes from here; nothing else builds paths from `$HOME`. |
| `colors.py` | `Color` value type: parsing, conversion to every notation the components need (`rgba(hex)` for Hyprland, CSS `rgba()`, `#RRGGBBAA` for rofi, `rgba(r, g, b, a)` for hyprlock), mixing/lightening, contrast, and ANSI palette derivation. |
| `theme.py` | The `Theme` dataclass: schema, defaults, validation, normalisation, (de)serialisation, fingerprint. |
| `templating.py` | Tiny Jinja-like engine (`{{ }}`, filters, `{% if %}`, `{% for %}`) with strict unknown-variable errors. |
| `settings.py` | Application settings (integration modes, wallpaper backend, reload behaviour). |
| `generator.py` | Builds the template context from a theme + settings, detects Hyprland/hyprpaper syntax versions, and produces a `Plan` (files to write + include lines to inject) without touching the filesystem. |
| `backup.py` | Timestamped snapshots with a manifest, exact restore (files that did not exist are removed again), pruning. |
| `portable.py` | `.hyprtheme` export/import. |
| `components.py` | Detection of installed/running components. Never raises. |
| `reload.py` | Asks running components to reload (`hyprctl reload`, SIGUSR2 → Waybar, SIGUSR1 → Kitty, `swaync-client --reload-css/--reload-config`). |
| `wallpaper.py` | swww / hyprpaper backends, login restore, library scanning. |
| `engine.py` | The facade used by both front-ends: list/find themes, apply, save, delete, rollback, reset, import/export, backups, history. |

### Apply sequence

1. `Theme.validate()` – refuse invalid themes.
2. `Generator.plan()` – render every enabled component into a `Plan`. Components switched off in the theme or in settings are listed in `plan.skipped`.
3. `BackupManager.create()` – snapshot every target path (an `initial` snapshot of the untouched configs is taken the very first time).
4. Write generated files atomically (temp file + rename); unchanged files are left alone.
5. Ensure the include lines inside user-owned files (`hyprland.conf` → `source = …`, `kitty.conf` → `include …`, `config.rasi` → `@theme …`). These live in a marked block that is replaced in place, so the user's file is never rewritten.
6. Persist `current.json` and append to `history.json` under `$XDG_STATE_HOME/hyprtheme`.
7. Set the wallpaper through the selected backend and remember it for login restore.
8. Reload running components.

### Integration modes

Each component (except the wallpaper) has a mode in settings:

* **managed** – HyprTheme owns the component's main config (`style.css`, `hyprlock.conf`, …) and keeps it in sync. For Hyprland, Kitty and Rofi "managed" only means one include line is added to the user's main file.
* **variables** – only a colours/variables file is written (`hyprtheme-colors.css`, `hyprtheme.rasi`, `hyprlock-hyprtheme.conf`, …) for users who keep their own layouts.
* **off** – the component is never touched.

### Hyprland syntax support

Hyprland changed its rule syntax in 0.53 and introduced a Lua configuration after that. The generator detects the running version (`hyprctl version`) and writes legacy or `match:` style layer rules accordingly; it also always writes `hyprtheme.lua` and hooks it with `pcall(require, "hyprtheme")` when a `hyprland.lua` exists. The choice can be forced in Settings (`hyprland_syntax`).

## GUI (`hyprtheme/app`)

* `state.py` – `AppState`, a `GObject` holding the engine and the *working* theme. Pages mutate it through setters and listen to `changed`, `applied`, `themes-changed`, `components-changed`, `busy` and `message`. Long operations (apply, rollback, detection) run in a thread and report back on the main loop.
* `window.py` – sidebar + header actions + page stack + toasts + dialogs. Pages request window-level actions (apply, save-as dialog, confirmations) through sentinel messages so all dialogs live in one place.
* `components/preview.py` – the live desktop preview. It is a set of GTK widgets (bar, terminal, launcher, file manager, system/music/battery widgets, notification) styled by CSS that is regenerated from the theme on every change, so colours, radius, border width, opacity, glow and gaps are all real.
* `components/rows.py` – colour rows (picker + HEX + RGB), sliders, toggles, dropdowns, entries.
* `pages/` – one module per sidebar entry.
* `style.css` – the application's own AMOLED/glass look; accent colours are injected at runtime from the working theme.

## Persistence

Themes persist because the generated files persist: Hyprland sources `hyprtheme.conf` at every start, Waybar/SwayNC/Rofi/Kitty/Hyprlock/Wlogout read their generated files when they launch, and the wallpaper is restored by a single `exec-once = hyprtheme wallpaper restore` line in the generated Hyprland config. No daemon, timer or service is installed.
