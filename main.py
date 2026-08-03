import sys
import os
import ctypes
import ctypes.util

# --- macOS PyOpenGL DYLD Shared Cache Monkeypatch ---
if sys.platform == 'darwin':
    orig_find_library = ctypes.util.find_library
    def new_find_library(name):
        if name in ('OpenGL', 'GL'):
            return '/System/Library/Frameworks/OpenGL.framework/OpenGL'
        if name in ('GLUT', 'glut'):
            return '/System/Library/Frameworks/GLUT.framework/GLUT'
        return orig_find_library(name)
    ctypes.util.find_library = new_find_library

# --- MELOCHOR RUNTIME BOOTSTRAPPER FOR PYINSTALLER STANDALONE PORTABILITY ---
if sys.platform == 'win32':
    # Force PyOpenGL to use the Windows 'nt' (WGL) platform plugin
    os.environ['PYOPENGL_PLATFORM'] = 'nt'
    # Clear host environment leaks when running under Wine
    for var in ['XDG_SESSION_TYPE', 'WAYLAND_DISPLAY', 'DISPLAY']:
        os.environ.pop(var, None)

if getattr(sys, 'frozen', False):
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    
    # 1. Set GI_TYPELIB_PATH so PyGObject can locate Gtk/Gdk/Gsk/Pango typelibs
    possible_typelib_paths = [
        os.path.join(base_dir, 'gi_typelibs'),
        os.path.join(base_dir, '_internal', 'gi_typelibs'),
        os.path.join(base_dir, 'lib', 'girepository-1.0'),
    ]
    for path in possible_typelib_paths:
        if os.path.exists(path):
            os.environ['GI_TYPELIB_PATH'] = path
            break
            
    # 2. Set GSETTINGS_SCHEMA_DIR so GIO can find compiled schemas
    possible_schema_paths = [
        os.path.join(base_dir, 'share', 'glib-2.0', 'schemas'),
        os.path.join(base_dir, '_internal', 'share', 'glib-2.0', 'schemas'),
    ]
    for path in possible_schema_paths:
        if os.path.exists(path):
            os.environ['GSETTINGS_SCHEMA_DIR'] = path
            break

    # 3. Add base_dir and _internal to DLL search path on Windows for ctypes/LoadLibrary
    if sys.platform == 'win32' and hasattr(os, 'add_dll_directory'):
        try:
            os.add_dll_directory(base_dir)
        except Exception:
            pass
        internal_dir = os.path.join(base_dir, '_internal')
        if os.path.exists(internal_dir):
            try:
                os.add_dll_directory(internal_dir)
            except Exception:
                pass

    # 4. Set GDK_PIXBUF_MODULE_FILE so GdkPixbuf can find bundled image loaders (PNG, SVG, etc.)
    possible_loaders_paths = [
        os.path.join(base_dir, 'lib', 'gdk-pixbuf-2.0', '2.10.0', 'loaders.cache'),
        os.path.join(base_dir, '_internal', 'lib', 'gdk-pixbuf-2.0', '2.10.0', 'loaders.cache'),
    ]
    for path in possible_loaders_paths:
        if os.path.exists(path):
            os.environ['GDK_PIXBUF_MODULE_FILE'] = path
            break

    # 5. Set GIO_EXTRA_MODULES so GIO can find bundled modules (like TLS / network)
    possible_gio_paths = [
        os.path.join(base_dir, 'lib', 'gio', 'modules'),
        os.path.join(base_dir, '_internal', 'lib', 'gio', 'modules'),
    ]
    for path in possible_gio_paths:
        if os.path.exists(path):
            os.environ['GIO_EXTRA_MODULES'] = path
            break
# ----------------------------------------------------------------------------

# The configured desktop theme contains GTK 3-only CSS. Force GTK 4's native
# Adwaita theme before importing GI so GTK does not parse that incompatible CSS.
os.environ["GTK_THEME"] = "Adwaita"

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

import OpenGL.contextdata
# Bypass PyOpenGL GLX/EGL detection mismatch by mocking context getter
OpenGL.contextdata.getContext = lambda context=None: 1


from fireworks_app import FireworksApp
from firework import Firework


if __name__ == "__main__":
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Melochor: 3D OpenGL Audio Visualizer & Screensaver")
    parser.add_argument("--random", action="store_true", default=False, help="Start in random mode immediately")
    parser.add_argument("--shuffle", action="store_true", default=False, help="Start in shuffle mode immediately")
    parser.add_argument("--record", type=str, default=None, help="Output file path to record the MP4 to")
    parser.add_argument("--audio", type=str, default=None, help="Audio file to run against")
    parser.add_argument("--tmpdir", type=str, default=None, help="Optional custom temporary directory for display scripts")
    parser.add_argument("playlist_files", nargs="*", help="Audio files or m3u playlist to play")
    args, unknown = parser.parse_known_args()
    
    app = Gtk.Application(application_id="org.melochor.visualizer")
    pyro_app = FireworksApp(record_path=args.record, audio_path=args.audio, playlist_files=args.playlist_files, random_mode=args.random, tmp_dir=args.tmpdir, shuffle_mode=args.shuffle)
    app.connect("activate", pyro_app.on_activate)
    
    gtk_args = [sys.argv[0]] + unknown
    app.run(gtk_args)
