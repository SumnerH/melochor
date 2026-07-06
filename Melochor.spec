# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import shutil

block_cipher = None

# Let's dynamically find Gtk binaries and schemas depending on the OS
binaries = []
datas = []

# Add ffmpeg binary
if sys.platform == 'win32':
    if os.path.exists('ffmpeg.exe'):
        binaries.append(('ffmpeg.exe', '.'))
elif sys.platform == 'darwin':
    if os.path.exists('ffmpeg'):
        binaries.append(('ffmpeg', '.'))

if sys.platform == 'win32':
    # On Windows (MSYS2), we can find mingw64 prefix
    mingw_prefix = os.environ.get('MINGW_PREFIX', '/mingw64')
    if not os.path.exists(mingw_prefix):
        mingw_prefix = 'C:/msys64/mingw64' # fallback
    
    # 1. Gather all core GTK4 DLLs and their dependencies using a recursive dependency searcher
    dll_dir = os.path.join(mingw_prefix, 'bin')
    
    core_prefixes = [
        'libgtk-4',
        'libgdk',
        'libgsk-4',
        'libgirepository',
        'libpango',
        'libcairo',
        'libgraphene',
        'libepoxy',
        'libglib',
        'libgobject',
        'libgio',
        'libgmodule',
    ]
    
    core_dlls = []
    if os.path.exists(dll_dir):
        for f in os.listdir(dll_dir):
            if f.endswith('.dll'):
                for prefix in core_prefixes:
                    if f.lower().startswith(prefix.lower()):
                        core_dlls.append(f)
                        break
                        
    import subprocess
    visited = set()
    to_visit = [os.path.join(dll_dir, d) for d in core_dlls if os.path.exists(os.path.join(dll_dir, d))]
    
    while to_visit:
        curr = to_visit.pop(0)
        if curr in visited:
            continue
        visited.add(curr)
        try:
            # Under MSYS2, we can run ldd
            out = subprocess.check_output(['ldd', curr], stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
            for line in out.splitlines():
                if '=>' in line:
                    parts = line.split('=>')
                    if len(parts) > 1:
                        path_part = parts[1].strip()
                        if path_part:
                            p = path_part.split()[0]
                            # Clean up and check if it's in the mingw64 directory
                            if os.path.exists(p) and p.lower().startswith(mingw_prefix.lower()):
                                if p not in visited and p not in to_visit:
                                    to_visit.append(p)
        except Exception as e:
            print(f"Error tracing {curr}: {e}")
            
    for dll in sorted(visited):
        binaries.append((dll, '.'))
        print(f"Bundling DLL: {dll}")
        
    # 2. Add compiled GSettings schemas
    schemas_src = os.path.join(mingw_prefix, 'share/glib-2.0/schemas')
    if os.path.exists(schemas_src):
        datas.append((schemas_src, 'share/glib-2.0/schemas'))
        print(f"Bundling GSettings schemas from {schemas_src}")

    # 3. Explicitly bundle all typelibs to bypass any buggy PyInstaller gi hooks on MSYS2
    typelibs_src = os.path.join(mingw_prefix, 'lib/girepository-1.0')
    if os.path.exists(typelibs_src):
        datas.append((typelibs_src, 'gi_typelibs'))
        print(f"Bundling GI typelibs from {typelibs_src}")

elif sys.platform == 'darwin':
    # On macOS, we can find brew prefix
    brew_prefixes = ['/opt/homebrew', '/usr/local']
    brew_prefix = None
    for p in brew_prefixes:
        if os.path.exists(p):
            brew_prefix = p
            break
            
    if brew_prefix:
        lib_dir = os.path.join(brew_prefix, 'lib')
        
        core_prefixes = [
            'libgtk-4',
            'libgdk',
            'libgsk-4',
            'libgirepository',
            'libpango',
            'libcairo',
            'libgraphene',
            'libepoxy',
            'libglib',
            'libgobject',
            'libgio',
            'libgmodule',
        ]
        
        core_dylibs = []
        if os.path.exists(lib_dir):
            for f in os.listdir(lib_dir):
                if f.endswith('.dylib'):
                    for prefix in core_prefixes:
                        if f.lower().startswith(prefix.lower()):
                            core_dylibs.append(f)
                            break
                            
        import subprocess
        visited = set()
        to_visit = [os.path.join(lib_dir, d) for d in core_dylibs if os.path.exists(os.path.join(lib_dir, d))]
        
        while to_visit:
            curr = to_visit.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            try:
                out = subprocess.check_output(['otool', '-L', curr], stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
                for line in out.splitlines():
                    line = line.strip()
                    if line and not line.endswith(':'):
                        p = line.split()[0]
                        if p.startswith(brew_prefix):
                            if os.path.exists(p) and p not in visited and p not in to_visit:
                                to_visit.append(p)
            except Exception as e:
                print(f"Error tracing {curr}: {e}")
                
        for dylib in sorted(visited):
            binaries.append((dylib, '.'))
            print(f"Bundling dylib: {dylib}")
            
        # Add compiled GSettings schemas
        schemas_src = os.path.join(brew_prefix, 'share/glib-2.0/schemas')
        if os.path.exists(schemas_src):
            datas.append((schemas_src, 'share/glib-2.0/schemas'))
            print(f"Bundling GSettings schemas from {schemas_src}")

        # Explicitly bundle all typelibs on macOS too!
        typelibs_src = os.path.join(brew_prefix, 'lib/girepository-1.0')
        if os.path.exists(typelibs_src):
            datas.append((typelibs_src, 'gi_typelibs'))
            print(f"Bundling GI typelibs from {typelibs_src}")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'gi',
        'gi.repository.Gtk',
        'gi.repository.Gdk',
        'gi.repository.GLib',
        'gi.repository.GObject',
        'gi.repository.Pango',
        'gi.repository.Gsk',
        'gi.repository.GdkPixbuf',
    ],
    hookspath=[],
    hooksconfig={
        "gi": {
            "icons": ["Adwaita", "hicolor"],
            "themes": ["Adwaita"],
            "languages": ["en_US", "en_GB"],
        }
    },
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Melochor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Melochor',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Melochor.app',
        icon=None,
        bundle_identifier='org.melochor.visualizer',
    )
