#!/usr/bin/env bash
# HyprTheme launcher installed as ~/.local/bin/hyprtheme (or /usr/local/bin/hyprtheme).
# @HYPRTHEME_HOME@ / @HYPRTHEME_PYTHON@ are substituted by install.sh (package location, interpreter with GTK bindings).
HYPRTHEME_HOME="@HYPRTHEME_HOME@"
PYTHON="${HYPRTHEME_PYTHON:-@HYPRTHEME_PYTHON@}"
[[ -x "$PYTHON" ]] || PYTHON="python3"
export PYTHONPATH="${HYPRTHEME_HOME}${PYTHONPATH:+:$PYTHONPATH}"
export HYPRTHEME_RESOURCES="${HYPRTHEME_RESOURCES:-${HYPRTHEME_HOME}}"
exec "$PYTHON" -m hyprtheme "$@"
