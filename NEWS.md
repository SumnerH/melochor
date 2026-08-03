# News

Major changes are listed by tagged release, newest first.

## v0.2.16

- Improved Wormhole routines with distinct Spark Explosion, Rainbow Tunnel, Aurora Borealis, and Lightning Flash effects.

## v0.2.15

- Added and refined Fire Plasma flames, including improved music reactivity.
- Added shuffle playback support.
- Added sequential routine cycling with the `X` command.
- Added particle-reactivity settings to presets and made fireworks react to music by default.
- Added Space Invaders and Pond visualizer modes.
- Expanded Pond with swamp lights, multiple flocks, and improved routine and lightning behavior.
- Expanded Mandala with black-hole, halo, and other routines.
- Improved audio-analysis and fire-particle performance through vectorization and batching.
- Refactored the application into dedicated modules for modes, meshes, shaders, presets, and application components.

## v0.2.14

- Added the Fire Plasma mode and delivered initial fire-mode fixes.
- Fixed Windows packaging.

## v0.2.13

- Fixed macOS packaging.

## v0.2.12

- Fixed macOS packaging.

## v0.2.11

- Fixed macOS packaging.

## v0.2.10

- Fixed macOS packaging.

## v0.2.9

- Fixed a macOS packaging issue.

## v0.2.8

- Fixed a case-sensitivity issue affecting packaging.

## v0.2.7

- Fixed macOS packaging.

## v0.2.6

- Fixed macOS packaging.

## v0.2.5

- Fixed macOS packaging.

## v0.2.4

- Fixed macOS packaging.

## v0.2.3

- Fixed macOS packaging.

## v0.2.2

- Fixed macOS packaging.

## v0.2.1

- Fixed macOS packaging.

## v0.2.0

- Made underwater algae more responsive to stereo position and frequency bands.
- Made wormhole travel more responsive to track tempo.
- Enhanced the heads-up display.

## v0.1.9

- In random-preset mode, allow a mode change immediately before an eligible climax when no section change follows within 30 seconds.
- Included portability and build-process improvements.

## v0.1.8

- Forced the Windows PyOpenGL backend to WGL (`nt`) and removed leaked display environment variables to avoid Wine and GLX conflicts.

## v0.1.7

- Forced a Windows PyOpenGL platform backend to prevent GLX loading failures under Windows and Wine.

## v0.1.6

- Added required PyOpenGL platform and array hidden imports to prevent packaged startup crashes.

## v0.1.5

- Explicitly bundled Gtk 4 typelibs and dynamically detected prefixed GTK libraries.

## v0.1.4

- Added the unified `Melochor.spec` PyInstaller configuration.
- Automatically collected GTK library dependencies and GSettings schemas for packaged builds.

## v0.1.3

- Bundled all GObject Introspection resources in Windows and macOS PyInstaller builds.

## v0.1.2

- Added GCC to the MSYS2 Windows packaging workflow to build `audioop-lts`.

## v0.1.1

- Fixed Windows CI with MSYS2.
- Corrected macOS Python setup in the packaging workflow.

## v0.1.0

- Initial tagged release.
