#!/usr/bin/env bash
# Removes HyprTheme. Only files created by HyprTheme are touched.
#
#   --purge        also delete your settings, custom themes and wallpapers ($XDG_CONFIG_HOME/hyprtheme)
#   --restore      restore the original (pre-HyprTheme) configuration files first
#   --system       uninstall a --system installation (/usr/local)
#   --yes          do not ask
set -euo pipefail

XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
PURGE=0; RESTORE=0; SYSTEM=0; YES=0
for arg in "$@"; do
  case "$arg" in
    --purge) PURGE=1 ;; --restore) RESTORE=1 ;; --system) SYSTEM=1 ;; --yes|-y) YES=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

if (( SYSTEM )); then
  APP_HOME="/usr/local/share/hyprtheme"; BIN="/usr/local/bin/hyprtheme"; DESKTOP="/usr/local/share/applications/hyprtheme.desktop"; ICON="/usr/local/share/icons/hicolor/scalable/apps/hyprtheme.svg"; SUDO="sudo"
else
  APP_HOME="$XDG_DATA_HOME/hyprtheme"; BIN="$HOME/.local/bin/hyprtheme"; DESKTOP="$XDG_DATA_HOME/applications/hyprtheme.desktop"; ICON="$XDG_DATA_HOME/icons/hicolor/scalable/apps/hyprtheme.svg"; SUDO=""
fi

echo "HyprTheme uninstaller"
echo "  will remove: $APP_HOME, $BIN, $DESKTOP, $ICON"
(( RESTORE )) && echo "  will restore the original configuration from the 'initial' backup first"
(( PURGE ))   && echo "  will also remove $XDG_CONFIG_HOME/hyprtheme (settings, custom themes, wallpapers) and $XDG_STATE_HOME/hyprtheme (backups)"
echo "  generated files (hyprtheme.conf, hyprtheme-colors.css, …) stay in place unless you use --restore"
if (( ! YES )); then
  read -r -p "Continue? [y/N] " answer
  [[ "$answer" =~ ^[Yy] ]] || { echo "aborted"; exit 1; }
fi

if (( RESTORE )) && [[ -x "$BIN" ]]; then
  "$BIN" reset --original || echo "  (no original backup to restore, or restore failed — continuing)"
fi

# Remove the include lines HyprTheme added to user configs (managed blocks only).
strip_block() { # file marker
  local file="$1" marker="$2"
  [[ -f "$file" ]] || return 0
  if grep -q ">>> hyprtheme $marker >>>" "$file"; then
    python3 - "$file" "$marker" <<'PY'
import re, sys
path, marker = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
pattern = re.compile(r"\n?[^\n]*>>> hyprtheme " + re.escape(marker) + r" >>>.*?<<< hyprtheme " + re.escape(marker) + r" <<<\n?", re.DOTALL)
new = pattern.sub("\n", text, count=1)
if new != text:
    open(path, "w", encoding="utf-8").write(new)
    print(f"  removed managed block from {path}")
PY
  fi
}
strip_block "$XDG_CONFIG_HOME/hypr/hyprland.conf" "hyprland.conf"
strip_block "$XDG_CONFIG_HOME/hypr/hyprland.lua" "hyprland.lua"
strip_block "$XDG_CONFIG_HOME/kitty/kitty.conf" "kitty"
strip_block "$XDG_CONFIG_HOME/rofi/config.rasi" "rofi"

# ${VAR:?} aborts if a variable is ever empty, so these can never touch "/".
$SUDO rm -rf "${APP_HOME:?}"
$SUDO rm -f "${BIN:?}" "${DESKTOP:?}" "${ICON:?}"
if command -v update-desktop-database >/dev/null 2>&1; then $SUDO update-desktop-database "$(dirname "$DESKTOP")" >/dev/null 2>&1 || true; fi
echo "  removed application files"

if (( PURGE )); then
  rm -rf "${XDG_CONFIG_HOME:?}/hyprtheme" "${XDG_STATE_HOME:?}/hyprtheme"
  echo "  removed settings, themes, wallpapers and backups"
else
  echo "  kept $XDG_CONFIG_HOME/hyprtheme and $XDG_STATE_HOME/hyprtheme (use --purge to delete them)"
fi
echo "Done."
