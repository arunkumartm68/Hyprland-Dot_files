# Command-line interface

The CLI and the GUI use the same engine, so everything you can click can also be scripted.

```
hyprtheme list [--json]                 list presets and your themes (● marks the applied one)
hyprtheme current [--json]              show the applied theme
hyprtheme show <theme>                  print a theme definition as JSON
hyprtheme apply <theme> [options]       generate, back up, write and reload
hyprtheme save <name> [--from <theme>]  save the current (or given) theme under a new name
hyprtheme new <name> [--base <theme>] [--set key=value ...] [--apply]
hyprtheme delete <theme>                delete one of your themes (presets are protected)
hyprtheme rollback [--no-reload]        undo the last apply
hyprtheme reset [--original]            apply the default preset, or restore the pre-HyprTheme configs
hyprtheme export <file> [--theme <theme>] [--embed-wallpaper]
hyprtheme import <file> [--name <name>] [--apply] [--force]
hyprtheme status [--json] [--fast]      detected components and integration modes
hyprtheme backup list|create|restore <id>|delete <id>
hyprtheme wallpaper list|set <path>|restore
hyprtheme config [key [value]]          read or change settings
hyprtheme validate <file>               validate a theme file
hyprtheme gui                           start the control center
```

`<theme>` accepts an id (`iron-man`), a display name (`"Iron Man"`) or a path to a `.json` / `.hyprtheme` file.

## Examples

```bash
hyprtheme apply cyan                      # the desktop becomes cyan
hyprtheme apply "Iron Man" --no-wallpaper # keep the current wallpaper
hyprtheme apply ocean --dry-run           # show what would be written, touch nothing

hyprtheme new "My Theme" --base pink --set primary=#ABCDEF --set blur=20 --set glass=false --apply
hyprtheme save "Evening"                  # snapshot the applied theme under a new name

hyprtheme export ~/evening.hyprtheme --theme Evening
hyprtheme import ~/friend.hyprtheme --name "Friend's rice" --apply

hyprtheme rollback                        # back to the previous theme and files
hyprtheme reset --original                # undo everything HyprTheme ever wrote

hyprtheme config integration.waybar variables   # keep your own Waybar CSS, only get colours
hyprtheme config wallpaper_backend hyprpaper
hyprtheme config reload_on_apply false
```

### `--set` keys for `hyprtheme new`

Any colour key (`primary`, `secondary`, `highlight`, `background`, `surface`, `surface2`, `text`, `muted`, `border`, `glow`, `gradient_start`, `gradient_end`, `notification`, `success`, `warning`, `error`, `battery`, `system`, `media`, `workspace_active`, `workspace_inactive`, `active_border`, `inactive_border`), any effect key (`opacity`, `blur`, `border_width`, `radius`, `glow`, `animation_speed`, `window_gaps`, `gaps_out`, `gaps_in`, `glass`, `neon_glow`, `animations`, `gradient`, `shadows`, `rainbow_border`) and `wallpaper=<path>`.

## Exit codes

`0` success, `1` an operation failed (details on stderr), `2` bad arguments.

## Files

| Path | Content |
| --- | --- |
| `~/.config/hyprtheme/settings.json` | settings |
| `~/.config/hyprtheme/themes/*.json` | your themes |
| `~/.config/hyprtheme/wallpapers/` | wallpaper library |
| `~/.local/state/hyprtheme/current.json` | applied theme |
| `~/.local/state/hyprtheme/history.json` | apply history |
| `~/.local/state/hyprtheme/wallpaper.json` | wallpaper to restore at login |
| `~/.local/state/hyprtheme/backups/<id>/` | snapshots (`manifest.json` + files) |

(`~/.config` and `~/.local/state` follow `$XDG_CONFIG_HOME` and `$XDG_STATE_HOME`.)
