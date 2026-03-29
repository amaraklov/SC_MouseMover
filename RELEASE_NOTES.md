# Release Notes

## 2026-03-29

### Added

- Interactive HUD controls for multiple motion parameters:
  - DIST (0-255 px)
  - MOVES
  - SMOOTH
  - MOVE SEC
  - KEY SEC
- Telemetry strip showing live values.
- Notices log panel for runtime events.

### Changed

- Reworked HUD layout to integrate the notices area into the main visual shell.
- Improved left/right control grouping (mouse-focused controls left, key-focused controls right).
- Updated key heading label to `[ Key Loop`.
- Adjusted ship placement to better center between meter groups.
- Improved label readability (including moving SMOOTH label above the bar).
- Increased app window height to reduce lower-area clipping.

### Fixed

- MOVE SEC scale labels were overlapping/jumbled and are now positioned for readability.
- Mouse movement distance is constrained to 0-255 px.
- Zero-distance movement handling avoids forced drift when distance is set to zero.

### Build

- EXE compiled with PyInstaller:
  - `dist/MouseDriftHUD/MouseDriftHUD.exe`
