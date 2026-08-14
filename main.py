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

    # 3. Make bundled DLLs visible both to Windows LoadLibrary and to
    # ctypes.util.find_library(). The latter is used by sounddevice to locate
    # the bundled libportaudio-2.dll; add_dll_directory() alone is insufficient.
    if sys.platform == 'win32':
        internal_dir = os.path.join(base_dir, '_internal')
        dll_dirs = [base_dir]
        if os.path.exists(internal_dir):
            dll_dirs.append(internal_dir)

        os.environ["PATH"] = os.pathsep.join(
            dll_dirs + [os.environ.get("PATH", "")]
        )
        if hasattr(os, 'add_dll_directory'):
            for dll_dir in dll_dirs:
                try:
                    os.add_dll_directory(dll_dir)
                except OSError:
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
    parser.add_argument("--kodi", action="store_true", default=False, help="Connect to Kodi JSON-RPC to visualize music playing in Kodi")
    parser.add_argument("--kodi-host", type=str, default="127.0.0.1", help="Kodi JSON-RPC hostname or IP (default: 127.0.0.1)")
    parser.add_argument("--kodi-port", type=int, default=8080, help="Kodi JSON-RPC HTTP port (default: 8080)")
    parser.add_argument("playlist_files", nargs="*", help="Audio files or m3u playlist to play")
    args, unknown = parser.parse_known_args()
    
    app = Gtk.Application(application_id="org.melochor.visualizer")
    pyro_app = FireworksApp(
        record_path=args.record,
        audio_path=args.audio,
        playlist_files=args.playlist_files,
        random_mode=args.random,
        tmp_dir=args.tmpdir,
        shuffle_mode=args.shuffle,
        kodi_mode=args.kodi,
        kodi_host=args.kodi_host,
        kodi_port=args.kodi_port
    )
    app.connect("activate", pyro_app.on_activate)
    
    gtk_args = [sys.argv[0]] + unknown
    app.run(gtk_args)
