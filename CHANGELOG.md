# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `scripts/screenshot-presets.sh`: applies every preset on a live Hyprland session, captures the real desktop with grim/hyprshot/grimblast, builds a contact sheet and restores the previous theme.

## [1.0.0] - 2026-10-06

The repository turned from a personal dotfiles collection into **HyprTheme**, a Hyprland theme control center.

### Added
- Central theme engine (`hyprtheme/core`): one `theme.json` drives every component, with validation, normalisation and a stable fingerprint.
- Config generator with a dependency-free template engine; templates for Hyprland (hyprlang legacy, hyprlang 0.53+ and Lua), Waybar, Kitty, Rofi, SwayNC, Hyprlock, Wlogout and hyprpaper.
- 17 presets: Cyan, Red, Green, Orange, Ice Blue, Pink, White, Yellow, RGB, AMOLED, Cyberpunk, Matrix, Iron Man, Spider-Man, Ocean, Sunset, Ben 10.
- GTK4 / libadwaita control center with Dashboard, Themes, Colors, Effects, Wallpaper, Components, Backup & Restore and Settings pages, and a live desktop preview driven by the real theme values.
- `hyprtheme` CLI sharing the engine: `list`, `current`, `show`, `apply`, `save`, `new`, `delete`, `rollback`, `reset`, `export`, `import`, `status`, `backup`, `wallpaper`, `config`, `validate`, `gui`.
- Backup manager: automatic snapshot before every apply, a pristine "initial" snapshot, manual snapshots, exact rollback, restore of the original configuration.
- Portable `.hyprtheme` import/export (wallpaper stored as a reference; embedding is opt-in).
- Component detection with graceful handling of missing components; per-component integration modes (managed / variables / off).
- Wallpaper management through swww (preferred) or hyprpaper, restored at login through a generated `exec-once` line (no background service).
- `install.sh` / `uninstall.sh`, desktop entry, application icon, pytest suite (core + headless GUI), ruff and mypy configuration.

### Changed
- The original dotfiles are kept under `config/` as the reference base configuration.
