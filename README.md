# Pyro-Engine 3D: High-Performance GTK 4 & OpenGL Fireworks

An elegant, real-time, hardware-accelerated 3D fireworks screensaver and interactive demo built using **Python**, **GTK 4**, **PyOpenGL**, and **NumPy**.

## Performance Optimizations
- **NumPy Vectorization**: All particle physics updates (3D trajectory, velocity gravity offsets, drag coefficients, and alpha-fading schedules) are simulated in vectorized, C-speed array operations rather than nested python loops. This easily permits simulating **10,000+ simultaneous sparks at 60–120+ FPS** even on standard integrated laptop graphics.
- **`Gtk.GLArea`**: Provides hardware-accelerated 3D viewport context, natively managed by GTK 4's rapid rendering pipeline.
- **`Gtk.Overlay` with Custom CSS**: Rather than drawing raw 2D texts over the OpenGL buffer, we overlay native GTK 4 widgets styled with premium CSS rules (giving them translucent dark panels, subtle border outlines, and beautiful modern fonts). This ensures perfect, subpixel font anti-aliasing.
- **Volumetric Blending**: Uses OpenGL additive blending (`GL_SRC_ALPHA`, `GL_ONE`) to naturally make overlapping sparks look hotter, denser, and brighter at explosion centers.
- **Procedural Point Sprites**: Generates a smooth radial gradient texture on startup and binds it to point-replaced sprites (`GL_POINT_SPRITE`), transforming flat blocky points into soft, fluffy glowing stars.
- **Rolling Trail Buffer**: Rather than updating thousands of trail particles, each firework keeps a rolling 3D matrix of its recent positions, allowing instant rendering of trailing embers with negligible cost.

---

## How to Run

Execute the program using your workspace python virtual environment interpreter:

```bash
/home/sumner/src/sumner_venv/bin/python main.py
```

---

## Interactive Controls

### Keyboard Controls
- `[SPACE]` : Instantly launch a manual shell with random properties.
- `[A]` : Toggle the **Auto-Launcher** (on by default, schedules random launches every ~1 sec).
- `[R]` : Toggle **3D Camera Auto-Rotation** (on by default, slowly pans around the sky).
- `[F]` : Toggle **Fullscreen Mode** (borderless, perfect for a screensaver).
- `[C]` : Clear all active particles from the sky immediately.
- `[ESC]` or `[Q]` : Safely close and exit the screensaver.

### Mouse Navigation
- **Left-Click + Drag** : Rotate and tilt the 3D perspective camera around the center (uses drag-begin/drag-update differentials for ultimate smoothness).
- **Scroll Wheel** : Zoom the camera closer to or further from the explosions.
