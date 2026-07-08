# validate_bundle.py
import sys
import os
import subprocess
import glob

def run_cmd(cmd, env=None, check=True):
    print(f"Running command: {' '.join(cmd)}")
    res = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and res.returncode != 0:
        print(f"ERROR: Command failed with code {res.returncode}")
        print(f"STDOUT:\n{res.stdout}")
        print(f"STDERR:\n{res.stderr}")
        sys.exit(res.returncode)
    return res

def sanitize_loaders_cache(cache_file):
    print(f"\n--- SANITIZATION: Sanitizing loaders.cache paths in {cache_file} ---")
    with open(cache_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    updated_lines = []
    rewrote_count = 0
    for line in lines:
        if 'libpixbufloader' in line:
            parts = line.split('"')
            if len(parts) >= 3:
                path = parts[1]
                filename = os.path.basename(path)
                # Rewriting absolute paths to be bundle-relative (relative to loaders.cache folder)
                new_path = f"loaders/{filename}"
                parts[1] = new_path
                line = '"'.join(parts)
                print(f"  Rewrote loader path: {path} -> {new_path}")
                rewrote_count += 1
        updated_lines.append(line)

    with open(cache_file, 'w', encoding='utf-8') as f:
        f.writelines(updated_lines)
    print(f"SUCCESS: Sanitized loaders.cache successfully (modified {rewrote_count} paths).")

def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_bundle.py <bundle_dir>")
        sys.exit(1)

    bundle_dir = os.path.abspath(sys.argv[1])
    print(f"Validating bundle at: {bundle_dir}")

    # Determine if it is Windows or macOS
    is_windows = sys.platform == 'win32'
    is_mac = sys.platform == 'darwin'

    # Check if we are inside a macOS .app bundle
    app_dir = None
    parts = bundle_dir.split(os.sep)
    for i, part in enumerate(parts):
        if part.endswith('.app'):
            app_dir = os.sep.join(parts[:i+1])
            break

    if app_dir:
        # Under PyInstaller 6+ macOS App Bundle structure:
        # Contents/MacOS contains the executable
        # Contents/Resources contains the data files
        # Contents/Frameworks contains the binary libraries (dylibs)
        contents_dir = os.path.join(app_dir, "Contents")
        macos_dir = os.path.join(contents_dir, "MacOS")
        resources_dir = os.path.join(contents_dir, "Resources")
        frameworks_dir = os.path.join(contents_dir, "Frameworks")
        
        # Data files are placed in Contents/Resources
        internal_dir = resources_dir
        binary_search_dir = app_dir
        print(f"Detected macOS split App Bundle layout.")
        print(f"  App directory: {app_dir}")
        print(f"  Executable directory: {macos_dir}")
        print(f"  Resources directory (data files): {resources_dir}")
        print(f"  Frameworks directory (binaries): {frameworks_dir}")
    else:
        # Locate _internal folder (PyInstaller 6 layout on Windows/Linux)
        internal_dir = os.path.join(bundle_dir, "_internal")
        if not os.path.exists(internal_dir):
            # Fall back to root folder for flat or older layouts
            internal_dir = bundle_dir
        binary_search_dir = bundle_dir
        print(f"Found _internal directory at: {internal_dir}")

    # 0. Sanitize loaders.cache to be bundle-relative before validating
    cache_file = os.path.join(internal_dir, "lib", "gdk-pixbuf-2.0", "2.10.0", "loaders.cache")
    if os.path.exists(cache_file):
        sanitize_loaders_cache(cache_file)
    else:
        print(f"Warning: loaders.cache not found at expected location: {cache_file}")

    # 1. Verify existence of required GTK and GDK runtime assets
    required_paths = [
        os.path.join(internal_dir, "share", "glib-2.0", "schemas", "gschemas.compiled"),
        os.path.join(internal_dir, "lib", "gdk-pixbuf-2.0", "2.10.0", "loaders.cache"),
        os.path.join(internal_dir, "gi_typelibs", "Gtk-4.0.typelib")
    ]

    print("\n--- CHECK 1: Verifying required GTK/GDK files ---")
    for path in required_paths:
        if os.path.exists(path):
            print(f"SUCCESS: Found required asset: {path}")
        else:
            print(f"FAIL: Missing required asset: {path}")
            sys.exit(1)

    # 2. Verify bundled FFmpeg executable
    print("\n--- CHECK 2: Verifying bundled FFmpeg ---")
    ffmpeg_names = ["ffmpeg.exe", "ffmpeg"]
    ffmpeg_path = None
    
    search_bases = []
    if app_dir:
        search_bases = [macos_dir, frameworks_dir, resources_dir, app_dir]
    else:
        search_bases = [bundle_dir, internal_dir]

    for name in ffmpeg_names:
        for base in search_bases:
            p = os.path.join(base, name)
            if os.path.exists(p):
                ffmpeg_path = p
                break
        if ffmpeg_path:
            break

    if not ffmpeg_path:
        print("FAIL: Bundled FFmpeg binary not found!")
        sys.exit(1)

    print(f"Found FFmpeg at: {ffmpeg_path}")
    res = run_cmd([ffmpeg_path, "-version"])
    if "ffmpeg version" in res.stdout.lower() or "ffmpeg version" in res.stderr.lower():
        print("SUCCESS: FFmpeg runs and reports version.")
    else:
        print("FAIL: FFmpeg failed to report version correctly!")
        sys.exit(1)

    # 3. Verify no leaked build-time references (Homebrew / MSYS2) and missing DLLs
    print("\n--- CHECK 3: Verifying binary path references (leaks) ---")
    binary_files = []
    for ext in ["*.dylib", "*.so", "Melochor", "*.dll", "Melochor.exe"]:
        binary_files.extend(glob.glob(os.path.join(binary_search_dir, "**", ext), recursive=True))

    # Gather a set of all filenames (lowercase) bundled inside the package
    # This helps us differentiate between system path resolution on MSYS2 GHA runner and actual missing dependencies
    bundled_filenames = set()
    for root, dirs, files in os.walk(binary_search_dir):
        for f in files:
            bundled_filenames.add(f.lower())

    leaks_found = 0
    forbidden_prefixes = []
    if is_mac:
        forbidden_prefixes = ["/opt/homebrew", "/usr/local"]
    elif is_windows:
        forbidden_prefixes = ["/mingw64", "/c/msys64", "c:/msys64"]

    for bin_file in binary_files:
        # Ignore pyconfig.h or non-binary matches
        if bin_file.endswith(".h") or os.path.isdir(bin_file):
            continue
            
        if is_mac:
            # Inspection via otool -L
            res = subprocess.run(["otool", "-L", bin_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    for prefix in forbidden_prefixes:
                        if prefix in line:
                            print(f"LEAK DETECTED: Binary '{os.path.basename(bin_file)}' references build path '{line.strip()}'")
                            leaks_found += 1
        elif is_windows:
            # Inspection via ldd inside MSYS2
            # Since MSYS2 environment is available on GHA, we can call ldd
            try:
                res = subprocess.run(["ldd", bin_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        if '=>' in line:
                            parts = line.split('=>')
                            dep_name = parts[0].strip().lower()
                            dep_path_part = parts[1].strip()
                            if dep_path_part:
                                p = dep_path_part.split()[0]
                                # If a dependency says "not found", it is a critical failure!
                                if p.lower() == "not":
                                    print(f"MISSING DEPENDENCY: Binary '{os.path.basename(bin_file)}' requires '{dep_name}' which is NOT FOUND!")
                                    leaks_found += 1
                                else:
                                    # If it resolved to MSYS2 system directory, verify if we have it bundled
                                    p_norm = os.path.abspath(p).replace('\\', '/').lower()
                                    if any(prefix in p_norm for prefix in ["/mingw64", "/msys64"]):
                                        if dep_name not in bundled_filenames:
                                            print(f"LEAK/MISSING DEPENDENCY: Binary '{os.path.basename(bin_file)}' resolved '{dep_name}' to system '{p}' but it is NOT bundled!")
                                            leaks_found += 1
            except FileNotFoundError:
                pass

    if leaks_found > 0:
        print(f"FAIL: Found {leaks_found} absolute path leak(s) or missing dependency error(s) in binaries!")
        sys.exit(1)
    else:
        print("SUCCESS: No absolute build-path leaks or missing dependencies found in binaries.")

    # 3.5. Verify no leaked build-time references in loaders.cache
    print("\n--- CHECK 3.5: Scanning loaders.cache for absolute path leaks ---")
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_content = f.read()
        
        leaks_in_cache = 0
        # Check for any forbidden absolute prefixes
        for prefix in ["/opt/homebrew", "/usr/local", "/mingw64", "/msys64"]:
            if prefix in cache_content.lower():
                print(f"LEAK IN CACHE: loaders.cache still contains absolute build path reference: '{prefix}'")
                leaks_in_cache += 1
                leaks_found += 1
        if leaks_in_cache == 0:
            print("SUCCESS: No absolute path leaks found in loaders.cache.")
        else:
            print(f"FAIL: Found {leaks_in_cache} absolute path leak(s) inside loaders.cache!")
            sys.exit(1)
    else:
        print("Warning: loaders.cache not found for leak check.")

    # 4. Verify imports inside frozen package environment
    print("\n--- CHECK 4: Verifying Python environment and GTK importability ---")
    
    # We want to run a brief python check that mimics the frozen app startup
    # We configure environment variables pointing to the bundle's assets
    test_env = os.environ.copy()
    test_env["GI_TYPELIB_PATH"] = os.path.join(internal_dir, "gi_typelibs")
    test_env["GSETTINGS_SCHEMA_DIR"] = os.path.join(internal_dir, "share", "glib-2.0", "schemas")
    test_env["GDK_PIXBUF_MODULE_FILE"] = os.path.join(internal_dir, "lib", "gdk-pixbuf-2.0", "2.10.0", "loaders.cache")
    
    # Add DLL directories for ctypes on Windows
    if is_windows:
        test_env["PATH"] = f"{bundle_dir};{internal_dir};{test_env.get('PATH', '')}"

    # Verify we can import gi and load Gtk-4.0 without crashing
    py_code = """
import sys
import os
print("Python interpreter:", sys.executable)
print("PATH:", os.environ.get("PATH"))
print("GI_TYPELIB_PATH:", os.environ.get("GI_TYPELIB_PATH"))
print("GSETTINGS_SCHEMA_DIR:", os.environ.get("GSETTINGS_SCHEMA_DIR"))
print("GDK_PIXBUF_MODULE_FILE:", os.environ.get("GDK_PIXBUF_MODULE_FILE"))

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, GObject, GdkPixbuf
print("SUCCESS: Successfully imported gi and Gtk/Gdk/GLib/GObject/GdkPixbuf in bundled context!")
"""

    # Run python in the context of the workflow
    res = run_cmd([sys.executable, "-c", py_code], env=test_env)
    print(res.stdout)
    
    print("\n--- ALL CHECKS PASSED SUCCESSFULLY! ---")

if __name__ == "__main__":
    main()
