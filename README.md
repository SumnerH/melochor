# Melochor: Yet another Audio Visualizer

Melochor is a 3D audio visualizer/screensaver built using **Python**, **GTK 4**, **PyOpenGL**, **NumPy**, and **FFmpeg**. 

Its sole purpose is to put cool graphics on the screen that respond to the music you're playing (similar to old WinAmp plugins, cthugha, synaesthesia, etc)

---

## Features

- **Holistic Track Analysis**: It's not just a frequency analyzer on the fly, Melochor runs on the whole track and does BPM detection, key change detection, etc to try to isolate different parts/segments of the song and locate peak moments for big visual events
- **Multiple Modes**: Fireworks, spinning mandalas, wormholes in space, underwater vents, simple starfields, and more
- **Playlist and audio support**: Drag and drop .m3u playlists, or mp3/flac/ogg/opus/wav/etc files.
- **Overlay HUD**: HUD should show you all the keyboard commands
- **Translucent Context Menu**: Right-click (or whatever you do on Mac) in the viewport for a simple menu. Bare-bones but it's there.

---

## Installation & Setup

### Linux (Debian/Ubuntu)
Install system GTK 4 and OpenGL drivers, then set up the python environment:

```bash
# Install GTK 4, OpenGL, and FFmpeg (for audio analysis)
sudo apt update
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 libgirepository1.0-dev ffmpeg mpv

# Set up virtual environment
python3 -m venv venv --system-site-packages
source venv/bin/activate

# Install Python requirements
pip install -r requirements.txt
```

### macOS
Make sure you have [Homebrew](https://brew.sh/) installed, then run:

```bash
# Install GTK 4, FFmpeg, and MPV
brew install gtk4 pygobject3 ffmpeg mpv

# Create virtual environment (allow system site-packages to inherit pygobject if needed)
python3 -m venv venv --system-site-packages
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### Windows
1. Install [Python 3.10+](https://www.python.org/downloads/).
2. Install [FFmpeg](https://ffmpeg.org/download.html) and add its `/bin` directory to your System PATH variables.
3. Install [GTK 4 for Windows](https://www.gtk.org/docs/installations/windows/) (e.g., via MSYS2 or standalone installer) to acquire GObject Introspection bindings.
4. Set up your environment and install Python requirements:

```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## How to Run

Launch Melochor by providing files, directories, playlists, or starting with interactive audio selections:

```bash
# 1. Run with default test flac (launches immediately)
python main.py

# 2. Open a specific audio track
python main.py --audio path/to/song.mp3

# 3. Load an entire folder or .m3u playlist on startup
python main.py path/to/playlist.m3u path/to/music_folder/

# 4. Start in random preset cycle mode immediately
python main.py --random --audio path/to/song.flac

# 5. Specify a custom cache directory for analyzer scripts
python main.py --tmpdir ./my_cache_dir --audio path/to/song.ogg
```

---

## Interactive Controls

### Keyboard Shortcuts
| Shortcut | Action |
| :--- | :--- |
| `[Spacebar]` / `[Media Play/Pause]` | Toggle music and choreography Play / Pause |
| `[Return / KP_Enter]` | Force launch a manual firework shell |
| `[Ctrl + F]` / `[Ctrl + O]` | Open File Dialog to load new music, folder, or playlist |
| `[F]` | Toggle Fullscreen Mode |
| `[V]` | Cycle through visualization presets |
| `[A]` | Toggle Auto-Launcher (automatically launches random shells) |
| `[R]` | Toggle 3D Camera Auto-Rotation |
| `[Y]` | Toggle firework height limits (allows shells to explode at any elevation) |
| `[C]` | Clear all active visual particles |
| `[H]` | Hide / Show HUD |
| `[Left Arrow]` / `[Media Prev]` | Previous track |
| `[Right Arrow]` / `[Media Next]` | Next track |
| `[ESC]` / `[Q]` | Exit |

### Mouse Controls
- **Right-Click**: Opens the translucent Popover Menu
- **Left-Click + Drag**: Rotate and tilt the 3D camera orbit.
- **Scroll Wheel**: Zoom the camera closer to or further from the center.

---

## Bundling with PyInstaller (Offline Portable Executable)

We package **Melochor** with static FFmpeg binaries to allow users to run visualizer analysis without requiring system FFmpeg installations.

```bash
# Build standalone frozen binary
pyinstaller --clean -y Melochor.spec
```
The output executable will be generated inside the `dist/` directory.

Enjoy the show!
