#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
#  HyprTheme installer — Arch Linux + Hyprland
#
#  Installs the application into XDG directories (no root needed):
#    $XDG_DATA_HOME/hyprtheme      package, presets, templates, assets
#    ~/.local/bin/hyprtheme        CLI launcher (also used by the .desktop file)
#    $XDG_DATA_HOME/applications   desktop entry
#    $XDG_CONFIG_HOME/hyprtheme    settings, your themes, your wallpapers
#
#  Options:
#    --system        install under /usr/local instead of ~/.local (needs sudo)
#    --no-deps       do not install packages with pacman
#    --with-optional also install optional components (waybar, kitty, rofi …)
#    --apply THEME   apply a preset right after installing (e.g. --apply cyan)
#    --yes           do not ask for confirmation
#    --uninstall     remove HyprTheme (same as ./uninstall.sh)
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"

SYSTEM=0
INSTALL_DEPS=1
WITH_OPTIONAL=0
APPLY_THEME=""
ASSUME_YES=0
APPLY_NEXT=0

for arg in "$@"; do
  case "$arg" in
    --system) SYSTEM=1 ;;
    --no-deps) INSTALL_DEPS=0 ;;
    --with-optional) WITH_OPTIONAL=1 ;;
    --apply=*) APPLY_THEME="${arg#--apply=}" ;;
    --apply) APPLY_NEXT=1 ;;
    --yes|-y) ASSUME_YES=1 ;;
    --uninstall) exec "$SCRIPT_DIR/uninstall.sh" ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    *)
      if (( APPLY_NEXT )); then APPLY_THEME="$arg"; APPLY_NEXT=0; else echo "unknown option: $arg" >&2; exit 2; fi ;;
  esac
done

if (( SYSTEM )); then
  PREFIX="/usr/local"
  APP_HOME="$PREFIX/share/hyprtheme"
  BIN_DIR="$PREFIX/bin"
  APPS_DIR="$PREFIX/share/applications"
  ICON_DIR="$PREFIX/share/icons/hicolor/scalable/apps"
  SUDO="sudo"
else
  APP_HOME="$XDG_DATA_HOME/hyprtheme"
  BIN_DIR="$HOME/.local/bin"
  APPS_DIR="$XDG_DATA_HOME/applications"
  ICON_DIR="$XDG_DATA_HOME/icons/hicolor/scalable/apps"
  SUDO=""
fi

c_accent=$'\e[1;36m'; c_ok=$'\e[1;32m'; c_warn=$'\e[1;33m'; c_err=$'\e[1;31m'; c_dim=$'\e[2m'; c_reset=$'\e[0m'
say()  { printf '%s▸%s %s\n' "$c_accent" "$c_reset" "$*"; }
ok()   { printf '  %s✓%s %s\n' "$c_ok" "$c_reset" "$*"; }
warn() { printf '  %s⚠%s %s\n' "$c_warn" "$c_reset" "$*"; }
die()  { printf '  %s✕%s %s\n' "$c_err" "$c_reset" "$*" >&2; exit 1; }

printf '\n%s  HYPRTHEME%s — Hyprland Theme Control Center installer\n\n' "$c_accent" "$c_reset"

# 1. Detect Arch Linux ---------------------------------------------------------
say "Checking the system"
IS_ARCH=0
if [[ -f /etc/os-release ]] && grep -qiE '^(ID|ID_LIKE)=.*arch' /etc/os-release; then
  IS_ARCH=1; ok "Arch Linux (or derivative) detected"
else
  warn "This does not look like Arch Linux. Packages will not be installed automatically; make sure the dependencies below are present."
  INSTALL_DEPS=0
fi

# 2. Detect Hyprland -----------------------------------------------------------
if command -v Hyprland >/dev/null 2>&1 || command -v hyprland >/dev/null 2>&1; then
  ok "Hyprland is installed"
elif [[ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]]; then
  ok "Running inside Hyprland"
else
  warn "Hyprland not found on PATH. HyprTheme still installs; themes are generated into ~/.config/hypr for when Hyprland is set up."
fi
[[ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]] && ok "Hyprland session is active — themes can be applied live"

# 3. Dependencies --------------------------------------------------------------
say "Checking dependencies"
OPTIONAL_PKGS=(waybar kitty rofi-wayland swaync hyprlock wlogout swww ttf-jetbrains-mono-nerd inter-font papirus-icon-theme)
MISSING_REQ=()
MISSING_OPT=()

have_pkg() { pacman -Qi "$1" >/dev/null 2>&1; }

# Pick the interpreter that has GTK4 + libadwaita bindings (distros sometimes ship
# several pythons; the bindings only exist for the one python-gobject was built for).
PYTHON_BIN=""
GUI_OK=0
for candidate in python3 python3.14 python3.13 python3.12 python3.11; do
  command -v "$candidate" >/dev/null 2>&1 || continue
  "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null || continue
  [[ -z "$PYTHON_BIN" ]] && PYTHON_BIN="$candidate"
  if "$candidate" -c 'import gi; gi.require_version("Gtk","4.0"); gi.require_version("Adw","1"); from gi.repository import Gtk, Adw' >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"; GUI_OK=1; break
  fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  MISSING_REQ+=(python)
else
  ok "$PYTHON_BIN $("$PYTHON_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
fi
if (( GUI_OK )); then
  ok "GTK4 + libadwaita python bindings"
elif (( INSTALL_DEPS )); then
  MISSING_REQ+=(python-gobject gtk4 libadwaita)
else
  warn "GTK4/libadwaita python bindings not found: the CLI works, the GUI needs python-gobject gtk4 libadwaita"
fi

if (( IS_ARCH )); then
  for p in "${OPTIONAL_PKGS[@]}"; do have_pkg "$p" || MISSING_OPT+=("$p"); done
fi

if (( ${#MISSING_REQ[@]} )); then
  warn "Missing required packages: ${MISSING_REQ[*]}"
  if (( INSTALL_DEPS )); then
    say "Installing required packages with pacman"
    sudo pacman -S --needed --noconfirm "${MISSING_REQ[@]}" || die "pacman failed; install ${MISSING_REQ[*]} manually and re-run"
  else
    die "Install them and re-run: sudo pacman -S --needed ${MISSING_REQ[*]}"
  fi
fi
if (( ${#MISSING_OPT[@]} )); then
  warn "Optional components not installed: ${MISSING_OPT[*]}"
  if (( INSTALL_DEPS && WITH_OPTIONAL )); then
    say "Installing optional components"
    sudo pacman -S --needed --noconfirm "${MISSING_OPT[@]}" || warn "some optional packages failed to install (not fatal)"
  else
    printf '  %s(HyprTheme skips components that are not installed; add them later with: sudo pacman -S --needed %s)%s\n' "$c_dim" "${MISSING_OPT[*]}" "$c_reset"
  fi
fi

# 4. Confirm -------------------------------------------------------------------
say "Install plan"
printf '  package + presets + templates  → %s\n  launcher                       → %s/hyprtheme\n  desktop entry                  → %s/hyprtheme.desktop\n  your themes & settings         → %s/hyprtheme\n' "$APP_HOME" "$BIN_DIR" "$APPS_DIR" "$XDG_CONFIG_HOME"
if (( ! ASSUME_YES )); then
  read -r -p "  Continue? [Y/n] " answer
  [[ -z "$answer" || "$answer" =~ ^[Yy] ]] || { echo "aborted"; exit 1; }
fi

# 5. Install files -------------------------------------------------------------
say "Installing HyprTheme"
$SUDO mkdir -p "${APP_HOME:?}" "${BIN_DIR:?}" "${APPS_DIR:?}" "${ICON_DIR:?}"
for item in hyprtheme themes templates assets; do
  # ${VAR:?} aborts if a variable is ever empty, so this can never touch "/".
  $SUDO rm -rf "${APP_HOME:?}/${item:?}"
  $SUDO cp -r "$SCRIPT_DIR/$item" "${APP_HOME:?}/$item"
done
$SUDO find "${APP_HOME:?}" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
$SUDO cp "$SCRIPT_DIR/README.md" "$SCRIPT_DIR/LICENSE" "${APP_HOME:?}/" 2>/dev/null || true
ok "files copied to $APP_HOME"

# 6. XDG directories -------------------------------------------------------------
mkdir -p "$XDG_CONFIG_HOME/hyprtheme/themes" "$XDG_CONFIG_HOME/hyprtheme/wallpapers" "$XDG_STATE_HOME/hyprtheme/backups"
ok "created $XDG_CONFIG_HOME/hyprtheme and $XDG_STATE_HOME/hyprtheme"

# 7. CLI launcher ----------------------------------------------------------------
PYTHON_PATH="$(command -v "${PYTHON_BIN:-python3}")"
sed "s|@HYPRTHEME_HOME@|$APP_HOME|; s|@HYPRTHEME_PYTHON@|$PYTHON_PATH|" "$SCRIPT_DIR/data/hyprtheme.sh" | $SUDO tee "${BIN_DIR:?}/hyprtheme" >/dev/null
$SUDO chmod +x "${BIN_DIR:?}/hyprtheme"
ok "launcher installed: $BIN_DIR/hyprtheme"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "$BIN_DIR is not in your PATH. Add  export PATH=\"$BIN_DIR:\$PATH\"  to your shell profile." ;;
esac

# 8. Desktop entry + icon ---------------------------------------------------------
sed "s|^Exec=.*|Exec=$BIN_DIR/hyprtheme gui|; s|^TryExec=.*|TryExec=$BIN_DIR/hyprtheme|" "$SCRIPT_DIR/data/hyprtheme.desktop" | $SUDO tee "${APPS_DIR:?}/hyprtheme.desktop" >/dev/null
$SUDO cp "$SCRIPT_DIR/assets/icons/hyprtheme.svg" "${ICON_DIR:?}/hyprtheme.svg"
if command -v update-desktop-database >/dev/null 2>&1; then $SUDO update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true; fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then $SUDO gtk-update-icon-cache -q -t "$(dirname "$(dirname "$(dirname "$ICON_DIR")")")" 2>/dev/null || true; fi
ok "desktop entry installed (HyprTheme appears in your application menu)"

# 9. Verify ----------------------------------------------------------------------
say "Verifying"
if "$BIN_DIR/hyprtheme" list >/dev/null 2>&1; then
  ok "$("$BIN_DIR/hyprtheme" list | wc -l) themes available"
else
  die "hyprtheme list failed — run '$BIN_DIR/hyprtheme list' to see the error"
fi
"$BIN_DIR/hyprtheme" status --fast | sed 's/^/  /'

# 10. Optional first apply (always backed up) ---------------------------------------
if [[ -n "$APPLY_THEME" ]]; then
  say "Applying theme '$APPLY_THEME' (your current configs are backed up first)"
  "$BIN_DIR/hyprtheme" apply "$APPLY_THEME" || warn "apply reported a problem; see above"
fi

printf '\n%s  Done.%s  Launch %sHyprTheme%s from your app menu or run:  hyprtheme gui\n' "$c_ok" "$c_reset" "$c_accent" "$c_reset"
printf '  CLI: hyprtheme list · hyprtheme apply cyan · hyprtheme rollback · hyprtheme export my.hyprtheme\n'
printf '  %sNothing in ~/.config is modified until you apply a theme, and every apply creates a backup first.%s\n\n' "$c_dim" "$c_reset"
