#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
#  screenshot-presets.sh — apply every preset on the real desktop and capture it
#
#  Runs INSIDE a Hyprland session. For each preset it runs `hyprtheme apply`,
#  waits for Hyprland/Waybar/Kitty/SwayNC to reload, takes a screenshot of the
#  whole output, and finally restores the theme you had before.
#
#  Usage:
#    scripts/screenshot-presets.sh [options] [preset ...]
#
#  Options:
#    -o, --out DIR        output directory (default: docs/screenshots/desktop)
#    -d, --delay SEC      seconds to wait after apply before shooting (default: 3)
#    -m, --monitor NAME   capture one monitor (default: the focused one)
#    -w, --wallpaper FILE use this wallpaper for every preset (default: each preset's own)
#        --demo           open a Kitty window running fastfetch, the launcher and a
#                         notification before each shot, close them afterwards
#        --keep           do not restore the previous theme at the end
#        --dry-run        print what would happen, touch nothing
#    -h, --help           this help
#
#  Screenshot tool: grim (preferred), hyprshot or grimblast — whichever is installed.
#  Output: <out>/<preset-id>.png, plus a contact sheet <out>/all.png when
#  ImageMagick's `montage` is available.
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

OUT="$REPO_DIR/docs/screenshots/desktop"
DELAY=3
MONITOR=""
WALLPAPER=""
DEMO=0
KEEP=0
DRY=0
PRESETS=()

while (( $# )); do
  case "$1" in
    -o|--out) OUT="$2"; shift 2 ;;
    -d|--delay) DELAY="$2"; shift 2 ;;
    -m|--monitor) MONITOR="$2"; shift 2 ;;
    -w|--wallpaper) WALLPAPER="$2"; shift 2 ;;
    --demo) DEMO=1; shift ;;
    --keep) KEEP=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '2,27p' "$0"; exit 0 ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) PRESETS+=("$1"); shift ;;
  esac
done

c_accent=$'\e[1;36m'; c_ok=$'\e[1;32m'; c_warn=$'\e[1;33m'; c_err=$'\e[1;31m'; c_reset=$'\e[0m'
say()  { printf '%s▸%s %s\n' "$c_accent" "$c_reset" "$*"; }
ok()   { printf '  %s✓%s %s\n' "$c_ok" "$c_reset" "$*"; }
warn() { printf '  %s⚠%s %s\n' "$c_warn" "$c_reset" "$*"; }
die()  { printf '  %s✕%s %s\n' "$c_err" "$c_reset" "$*" >&2; exit 1; }
run()  { if (( DRY )); then printf '  [dry-run] %s\n' "$*"; else "$@"; fi; }

# ── hyprtheme command: installed launcher, or the checkout ─────────────────────
if command -v hyprtheme >/dev/null 2>&1; then
  HT=(hyprtheme)
else
  HT=(python3 -m hyprtheme)
  export PYTHONPATH="$REPO_DIR${PYTHONPATH:+:$PYTHONPATH}"
  export HYPRTHEME_RESOURCES="${HYPRTHEME_RESOURCES:-$REPO_DIR}"
fi

# ── checks ─────────────────────────────────────────────────────────────────────
say "Checking the session"
if [[ -z "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]]; then
  (( DRY )) || die "not inside a Hyprland session (HYPRLAND_INSTANCE_SIGNATURE is unset)"
  warn "not inside Hyprland; continuing because of --dry-run"
fi

SHOT=()
if command -v grim >/dev/null 2>&1; then
  SHOT=(grim)
elif command -v hyprshot >/dev/null 2>&1; then
  SHOT=(hyprshot)
elif command -v grimblast >/dev/null 2>&1; then
  SHOT=(grimblast)
else
  (( DRY )) || die "no screenshot tool found; install grim (sudo pacman -S grim), hyprshot or grimblast"
  warn "no screenshot tool found"
fi
ok "screenshot tool: ${SHOT[0]:-none}"

if [[ -z "$MONITOR" ]] && command -v hyprctl >/dev/null 2>&1 && [[ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]]; then
  MONITOR="$(hyprctl monitors -j 2>/dev/null | python3 -c 'import json,sys
try:
    mons = json.load(sys.stdin)
    focused = [m for m in mons if m.get("focused")] or mons
    print(focused[0]["name"] if focused else "")
except Exception:
    print("")' 2>/dev/null || true)"
fi
ok "monitor: ${MONITOR:-all}"

if (( ${#PRESETS[@]} == 0 )); then
  mapfile -t PRESETS < <("${HT[@]}" list --json | python3 -c 'import json,sys; [print(t["id"]) for t in json.load(sys.stdin) if t["kind"] == "preset"]')
fi
(( ${#PRESETS[@]} )) || die "no presets found"
ok "${#PRESETS[@]} preset(s): ${PRESETS[*]}"

# ── remember the current theme so it can be restored ───────────────────────────
PREVIOUS=""
STATE_FILE="$(mktemp --suffix=.json)"
trap 'rm -f "$STATE_FILE"' EXIT
if "${HT[@]}" current --json >"$STATE_FILE" 2>/dev/null; then
  PREVIOUS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["theme"]["name"])' "$STATE_FILE" 2>/dev/null || true)"
  # `hyprtheme apply` accepts a theme file, so store just the theme object
  python3 - "$STATE_FILE" <<'PY'
import json, sys
path = sys.argv[1]
data = json.load(open(path))
json.dump(data["theme"], open(path, "w"), indent=2)
PY
  ok "current theme: $PREVIOUS (will be restored)"
else
  PREVIOUS=""
  warn "no theme applied yet; the last preset stays applied (use 'hyprtheme reset --original' to undo)"
fi

mkdir -p "$OUT"

# ── demo helpers ───────────────────────────────────────────────────────────────
DEMO_PIDS=()
open_demo() {
  (( DEMO )) || return 0
  if command -v kitty >/dev/null 2>&1; then
    local cmd="clear; (fastfetch || neofetch || echo HyprTheme) 2>/dev/null; sleep 600"
    kitty --title "kitty — fastfetch" sh -c "$cmd" >/dev/null 2>&1 &
    DEMO_PIDS+=("$!")
  fi
  if command -v notify-send >/dev/null 2>&1; then
    notify-send -a HyprTheme "HyprTheme" "Theme applied — desktop updated" >/dev/null 2>&1 || true
  fi
  sleep 1
  if command -v rofi >/dev/null 2>&1; then
    rofi -show drun >/dev/null 2>&1 &
    DEMO_PIDS+=("$!")
  fi
}
close_demo() {
  (( DEMO )) || return 0
  for pid in "${DEMO_PIDS[@]:-}"; do
    [[ -n "$pid" ]] && kill "$pid" >/dev/null 2>&1 || true
  done
  DEMO_PIDS=()
  command -v swaync-client >/dev/null 2>&1 && swaync-client -C >/dev/null 2>&1 || true
}

shoot() { # file
  local file="$1"
  case "${SHOT[0]:-}" in
    grim)      if [[ -n "$MONITOR" ]]; then run grim -o "$MONITOR" "$file"; else run grim "$file"; fi ;;
    hyprshot)  if [[ -n "$MONITOR" ]]; then run hyprshot -s -m output -m "$MONITOR" -o "$(dirname "$file")" -f "$(basename "$file")"; else run hyprshot -s -m output -m active -o "$(dirname "$file")" -f "$(basename "$file")"; fi ;;
    grimblast) run grimblast save output "$file" ;;
    *)         if (( DRY )); then printf '  [dry-run] screenshot -> %s\n' "$file"; else return 1; fi ;;
  esac
}

# ── main loop ───────────────────────────────────────────────────────────────────
say "Capturing ${#PRESETS[@]} preset(s) into $OUT (delay ${DELAY}s)"
FAILED=()
for preset in "${PRESETS[@]}"; do
  id="$(printf '%s' "$preset" | tr '[:upper:] ' '[:lower:]-')"
  file="$OUT/$id.png"
  printf '  %s%-14s%s ' "$c_accent" "$preset" "$c_reset"
  apply=("${HT[@]}" apply "$preset")
  [[ -n "$WALLPAPER" ]] && apply+=(--wallpaper "$WALLPAPER")
  if ! run "${apply[@]}" >/dev/null 2>&1; then
    printf '%s✕ apply failed%s\n' "$c_err" "$c_reset"
    FAILED+=("$preset")
    continue
  fi
  (( DRY )) || sleep "$DELAY"
  open_demo
  (( DRY )) || sleep 1.5
  if shoot "$file"; then
    printf '%s✓%s %s\n' "$c_ok" "$c_reset" "$file"
  else
    printf '%s✕ screenshot failed%s\n' "$c_err" "$c_reset"
    FAILED+=("$preset")
  fi
  close_demo
done

# ── contact sheet ───────────────────────────────────────────────────────────────
if command -v montage >/dev/null 2>&1 && (( ! DRY )); then
  shots=("$OUT"/*.png)
  shots=("${shots[@]/$OUT\/all.png/}")
  if (( ${#shots[@]} > 1 )); then
    montage "${shots[@]}" -tile 3x -geometry 640x360+8+8 -background '#07090D' "$OUT/all.png" 2>/dev/null && ok "contact sheet: $OUT/all.png"
  fi
fi

# ── restore ─────────────────────────────────────────────────────────────────────
if (( KEEP )); then
  warn "--keep: the last preset stays applied"
elif [[ -n "$PREVIOUS" ]]; then
  say "Restoring previous theme: $PREVIOUS"
  run "${HT[@]}" apply "$STATE_FILE" >/dev/null 2>&1 && ok "restored" || warn "could not restore automatically; run: hyprtheme rollback"
fi

if (( ${#FAILED[@]} )); then
  warn "failed: ${FAILED[*]}"
  exit 1
fi
printf '\n%s  Done.%s %d screenshot(s) in %s\n' "$c_ok" "$c_reset" "$(( ${#PRESETS[@]} - ${#FAILED[@]} ))" "$OUT"
