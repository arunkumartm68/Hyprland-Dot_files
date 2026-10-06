"""``python -m hyprtheme`` entry point: runs the CLI (``hyprtheme gui`` starts the app)."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
