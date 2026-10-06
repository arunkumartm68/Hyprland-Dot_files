# Theme format

A HyprTheme theme is one JSON document. Presets live in `themes/presets/`, your own themes in `$XDG_CONFIG_HOME/hyprtheme/themes/` (usually `~/.config/hyprtheme/themes/`), and portable exports use the `.hyprtheme` extension (same content wrapped in a small envelope, see below).

Every key is optional except `name`; anything missing is filled from the defaults in `hyprtheme/core/theme.py`, so a minimal theme is just:

```json
{ "name": "Mint", "colors": { "primary": "#3DFFB0" } }
```

## Full structure

```json
{
  "schema": 1,
  "name": "Cyan",
  "id": "cyan",
  "author": "HyprTheme",
  "description": "Futuristic, clean, cyberpunk",
  "tags": ["accent", "cyberpunk"],
  "variant": "dark",
  "preset": true,

  "colors": {
    "primary": "#00E5FF",          "secondary": "#0077FF",      "highlight": "#5CF2FF",
    "background": "#080A0F",       "surface": "#11151D",        "surface2": "#1A2030",
    "text": "#FFFFFF",             "muted": "#8B95A7",
    "border": "#00E5FF",           "glow": "#00E5FF",
    "gradient_start": "#00E5FF",   "gradient_end": "#0077FF",
    "notification": "#00E5FF",     "success": "#4DFF88",        "warning": "#FFD166",   "error": "#FF4D6D",
    "battery": "#4DFF88",          "system": "#00E5FF",         "media": "#FF6AD5",
    "workspace_active": "#00E5FF", "workspace_inactive": "#3A4457",
    "active_border": "#00E5FF",    "inactive_border": "#2A3140"
  },

  "effects": {
    "opacity": 0.85,          "blur": 12,            "border_width": 2,     "radius": 14,
    "glow": 0.6,              "animation_speed": 1.0,
    "window_gaps": 8,         "gaps_out": 16,        "gaps_in": 6,
    "glass": true,            "neon_glow": true,     "animations": true,
    "gradient": true,         "shadows": true,       "rainbow_border": false
  },

  "wallpaper": {
    "path": null,
    "transition": "grow",
    "duration": 1.5,
    "fit": "crop",
    "fill_color": null
  },

  "fonts": { "ui": "Inter", "mono": "JetBrainsMono Nerd Font", "size": 13 },

  "components": {
    "hyprland": { "enabled": true, "apply_opacity_to_windows": false },
    "waybar":   { "enabled": true, "position": "top", "height": 36, "floating": true,
                  "show_launcher": true, "show_music": true, "show_bluetooth": true,
                  "show_system": true, "show_notifications": true,
                  "launcher_icon": "", "launcher_command": "rofi -show drun",
                  "clock_format": "%a %d %b  %I:%M %p" },
    "kitty":    { "enabled": true, "font_size": 11, "cursor_shape": "beam", "ansi": {} },
    "rofi":     { "enabled": true, "width": 640, "lines": 8, "columns": 1,
                  "show_icons": true, "icon_theme": "Papirus-Dark", "prompt": "Search" },
    "swaync":   { "enabled": true, "width": 420, "manage_config": true },
    "hyprlock": { "enabled": true, "clock_24h": false, "show_user": true,
                  "show_battery": true, "show_music": false, "blur_passes": 2 },
    "wlogout":  { "enabled": true, "columns": 5, "button_size": 150, "lock_command": "hyprlock" },
    "wallpaper": { "enabled": true }
  }
}
```

## Colors

All 23 colours are `#RRGGBB` strings (3/4/6/8-digit hex is accepted on input and normalised). Any value works; nothing is restricted to a palette.

| Key | Used for |
| --- | --- |
| `primary` | Main accent: bar highlights, launcher prompt, icons, cursor, Waybar workspace, Kitty cursor |
| `secondary` | Gradients, hover states, Bluetooth, URL colour, ANSI blue |
| `highlight` | Selected launcher row, Kitty selection, ANSI magenta |
| `background` | Desktop/window background, Waybar bar, Kitty background |
| `surface` / `surface2` | Panels, cards, module backgrounds, tabs |
| `text` / `muted` | Primary and dimmed text |
| `border` | Bar, launcher, notification, lock-screen card borders |
| `glow` | Neon glow / shadow colour |
| `gradient_start` / `gradient_end` | Active-border gradient, buttons, sliders |
| `notification` | SwayNC accent and the Waybar bell |
| `success` / `warning` / `error` | State colours, network, battery states, power button, ANSI red/green/yellow |
| `battery` / `system` / `media` | Waybar battery, CPU/RAM/temperature, mpris widget |
| `workspace_active` / `workspace_inactive` | Workspace indicator |
| `active_border` / `inactive_border` | Hyprland window borders |

Kitty's 16 ANSI colours are derived automatically (`hyprtheme/core/colors.py::derive_ansi`); set `components.kitty.ansi.colorN` to override individual slots.

## Effects

| Key | Range | Effect |
| --- | --- | --- |
| `opacity` | 0.3 – 1.0 | Panel/bar/launcher/notification opacity (only when `glass` is on); Kitty `background_opacity`; Hyprland window opacity if `components.hyprland.apply_opacity_to_windows` |
| `blur` | 0 – 40 px | Hyprland blur size/passes and layer blur, Kitty `background_blur`, hyprlock background blur |
| `border_width` | 0 – 8 px | Hyprland `border_size`, CSS borders, rofi border |
| `radius` | 0 – 32 px | Hyprland `rounding` and every CSS border-radius |
| `glow` | 0 – 1 | Neon glow strength (box-shadows, Hyprland shadow range/alpha) |
| `animation_speed` | 0.25 – 3 | Divides Hyprland animation durations; scales CSS transitions |
| `window_gaps` | 0 – 24 px | Padding inside bars/launcher/widgets, Waybar margins, Kitty padding |
| `gaps_out` / `gaps_in` | px | Hyprland `gaps_out` / `gaps_in` |
| `glass` | bool | Translucent panels + blur |
| `neon_glow` | bool | Glow shadows on/off |
| `animations` | bool | Hyprland and CSS animations |
| `gradient` | bool | Gradient active border and accent gradients |
| `shadows` | bool | Hyprland window shadows |
| `rainbow_border` | bool | Continuously rotating border gradient (`borderangle … loop`; costs battery) |

## Wallpaper

`path` is either an absolute path or a bare file name that is looked up in `~/.config/hyprtheme/wallpapers`, `$XDG_DATA_HOME/hyprtheme/wallpapers`, `~/Pictures/Wallpapers` and `~/Pictures`. A missing file is reported and skipped; it never breaks an apply. `transition` is any swww transition (`simple`, `fade`, `left`, `right`, `top`, `bottom`, `wipe`, `wave`, `grow`, `center`, `any`, `outer`, `random`), `fit` is `crop`, `fit`, `no` or `stretch` (mapped to hyprpaper's `cover` / `contain` / `fill`).

## Portable `.hyprtheme` files

```json
{
  "format": "hyprtheme",
  "format_version": 1,
  "exported_by": "HyprTheme 1.0.0",
  "exported_at": "2026-10-06T12:00:00",
  "theme": { "...the theme as above..." },
  "wallpaper_file": { "name": "sakura.jpg", "data": "<base64>" }
}
```

`wallpaper.path` is reduced to the file name on export so personal paths never leak. `wallpaper_file` is only present when exporting with `--embed-wallpaper` (or the equivalent GUI option) and is written to `~/.config/hyprtheme/wallpapers/` on import. A bare `theme.json` can be imported too.

## Validation

`hyprtheme validate <file>` (or `Theme.validate()`) checks every colour, the ranges above, transition/fit names and component objects. Invalid themes are refused by `apply` and `save`.
