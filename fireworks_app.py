import sys
import time
import random
import ctypes
import ctypes.util
import numpy as np
import os
import json
import subprocess
import math
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk, GObject
import OpenGL.GL as gl
import OpenGL.contextdata

# Mock PyOpenGL context
OpenGL.contextdata.getContext = lambda context=None: 1

from presets import active_presets
from constants import (
    RARITY_INTERVAL,
    COLORS,
    COLOR_LIST,
    NEON_PALETTE,
    TRANQUIL_PALETTE,
    METAL_PALETTE,
    SUPPORTED_ROUTINES
)
from shaders import (
    SKY_VERTEX_SHADER,
    SKY_FRAGMENT_SHADER,
    LINE_VERTEX_SHADER,
    LINE_FRAGMENT_SHADER,
    PARTICLE_VERTEX_SHADER,
    PARTICLE_FRAGMENT_SHADER,
    create_program,
    compile_shader
)
from meshes import (
    make_rocky_planet,
    make_3d_asteroid,
    make_solid_squid,
    make_solid_seahorse,
    make_solid_manta,
    make_solid_fish,
    make_solid_bird,
    make_solid_butterfly
)
from firework import Firework
from unified_audio_player import UnifiedAudioPlayer
from helpers import (
    get_palette_colors,
    perspective_matrix,
    look_at_matrix,
    get_meeus_moon_phase
)
from modes import (
    TunnelModeMixin,
    UnderwaterModeMixin,
    MandalaModeMixin,
    SynaesthesiaModeMixin,
    FireModeMixin
)

class FireworksApp(TunnelModeMixin, UnderwaterModeMixin, MandalaModeMixin, SynaesthesiaModeMixin, FireModeMixin):
    def __init__(self, record_path=None, audio_path=None, playlist_files=None, random_mode=False, tmp_dir=None, shuffle_mode=False):
        import tempfile
        self.tmp_dir = tmp_dir if tmp_dir else tempfile.gettempdir()
        self.audio_player = UnifiedAudioPlayer()
        # Default flame algorithm names (may be overridden by init_fire_mode when FIRE Plasma initializes)
        self.fire_flame_algorithm = 0
        self.fire_flame_names = ["Current", "Candle", "Bonfire", "Gas Jet"]
        Firework.app = self
        self.shuffle_mode = shuffle_mode
        self.opt_trailers = 0        # 0: off, 1..10 range
        self.opt_gravity = 1.0       # 0.0 to 10.0 range
        self.opt_star_shape = 0      # 0: default, 1..6 shapes
        self.opt_color_mode = 'REALISTIC' # 'REALISTIC', 'NEON', 'TRANQUIL', 'METAL'
        self.opt_height_restrict = True
        self.mandala_slices = 12
        self.active_presets = active_presets
        
        self.preset_idx = 0
        self.preset_random_mode = random_mode
        self.preset_random_timer = 0.0
        
        self.syn_star_size = 0.5
        self.syn_fade_mode = "Stars"

        self.record_path = record_path
        self.is_recording = record_path is not None
        self.record_time = 0.0
        self.record_fps = 30
        self.record_dt = 1.0 / self.record_fps
        self.ffmpeg_process = None
        self.temp_video_path = "temp_recording.mp4"
        
        # Configure dynamic audio & display script path
        raw_paths = []
        if audio_path:
            raw_paths.append(audio_path)
        if playlist_files:
            raw_paths.extend(playlist_files)
            
        self.playlist = self.load_playlist_files(raw_paths) if raw_paths else []
        self.playlist_idx = 0
        self.audio_path = self.playlist[self.playlist_idx] if self.playlist else ""
        self.audio_explicit = bool(raw_paths)
        self.script_path = self.get_mangled_script_path(self.audio_path)
        
        self.show_rockets = True
        self.show_legend = True

        self.fireworks = []
        self.routine_queue = []
        self.active_routine_name = ""
        self.routine_timer = 0.0
        
        self.camera_dist = 26.0
        self.camera_theta = 0.0
        self.camera_phi = 0.25
        self.auto_rotate = False
        
        self.start_time = time.time()
        self.last_time = time.time()
        self.react_bass_smooth = 0.0
        
        self.auto_launch = True
        self.launch_timer = 0.0
        self.next_launch_interval = 0.8
        
        self.fps = 60.0
        self.fps_filter = 0.95
        
        self.is_fullscreen = False
        
        self.drag_base_theta = 0.0
        self.drag_base_phi = 0.0
        
        # VAO / VBO / Shader Program references
        self.sky_program = None
        self.moon_texture_id = None
        self.line_program = None
        self.particle_program = None
        self.hood_vao = None
        self.hood_pos_vbo = None
        self.hood_col_vbo = None

        # Music Sync Playback State
        self.music_playing = False
        self.music_process = None
        self.playback_start_time = 0.0
        self.script_events = []
        self.next_event_idx = 0
        self.loaded_script_name = "None"
        self.script_duration = 0.0
        self.script_bpm = 120.0
        self.current_key = "N/A"
        self.current_section_name = "None"
        self.current_section_category = "None"
        self.script_total_events = 0
        self.color_hints = []
        self.saved_auto_launch = True

        # Dynamic Psychedelic Modes
        self.modes = ["FIREWORKS", "TUNNEL Wormhole", "MANDALA Sacred", "UNDERWATER Lava", "SYNAESTHESIA Classic", "FIRE Plasma"]
        self.major_mode_idx = 0
        self.major_mode = self.modes[self.major_mode_idx]
        self.react_bass = 0.0
        self.react_mid = 0.0
        self.react_treble = 0.0
        self.current_stereo_panning = 0.0
        self.procedural_beat_timer = 0.0
        
        # Climax Events and BPM phase
        self.climax_flash = 0.0
        self.last_climax_trigger_time = 0.0
        self.tempo_phase = 0.0
        
        # Rarity system properties
        self.rarity_cooldown = random.randint(0, int(RARITY_INTERVAL))
        self.rarity_queued_type = None
        self.active_rarity = None
        self.current_rarity_cycle_name = "None"
        self.rarity_cycle_list = [
            "SQUID", "MANTA", "SEAHORSE", "LANTERN_FISH",
            "PLANET", "GALAXY", "ASTEROIDS",
            "CATHERINE_WHEEL",
            "BIRD", "SMOKE", "SUN_BURST", "BUTTERFLY"
        ]
        self.rarity_cycle_idx = -1
        self.lightning_active_timer = 0.0
        self.active_lightning_bolts = []
        self.wormhole_supernova_age = 0.0
        self.wormhole_supernova_active = False
        self.wormhole_shooting_star_active = False
        self.wormhole_shooting_star_x = 0.0
        self.wormhole_shooting_star_y = 0.0
        self.wormhole_shooting_star_z = 0.0
        self.peace_symbol_timer = 0.0
        self.halo_timer = 0.0
        
        # Meeus Moon Phase state variables
        self.moon_illumed = 0.5
        self.moon_is_waning = False
        self.last_moon_update_time = 0.0
        self.recalculate_moon_phase()

    def recalculate_moon_phase(self):
        try:
            fraction, is_waning = get_meeus_moon_phase()
            self.moon_illumed = fraction
            self.moon_is_waning = is_waning
            print(f"Meeus Moon Phase calculated at startup / 12h tick: Illuminated: {fraction * 100:.2f}%, Waning: {is_waning}")
        except Exception as e:
            print(f"Error calculating Meeus moon phase, using fallback waning crescent: {e}")
            self.moon_illumed = 0.16
            self.moon_is_waning = True

    def generate_lightning_bolt(self, start, end, depth=0, max_depth=3, branch_prob=0.18):
        # Generates a list of line segments: (pt0, pt1, depth)
        segments = []
        
        # Calculate steps based on distance
        dist = np.linalg.norm(np.array(end) - np.array(start))
        steps = int(max(5, dist * 18))
        
        current_pt = np.array(start, dtype=np.float32)
        target_pt = np.array(end, dtype=np.float32)
        
        for i in range(1, steps + 1):
            t = i / steps
            # Interp point
            next_pt = current_pt + (target_pt - current_pt) * (1.0 / (steps - i + 1))
            
            # Add jaggedness (perpendicular to direction)
            if i < steps:
                dir_vec = target_pt - current_pt
                perp = np.array([-dir_vec[1], dir_vec[0], 0.0], dtype=np.float32)
                perp_len = np.linalg.norm(perp)
                if perp_len > 0.001:
                    perp /= perp_len
                # Jaggedness scale decreases near the end point (strikes the ground precisely!)
                jagged_scale = 0.065 * (1.0 - t) * np.random.uniform(-1.0, 1.0)
                next_pt += perp * jagged_scale
                
            # Line segment from current_pt to next_pt
            segments.append((current_pt.copy(), next_pt.copy(), depth))
            
            # Occasional branching!
            if depth < max_depth and np.random.uniform(0.0, 1.0) < branch_prob and i < steps - 1:
                # Spawn a branch going downwards-sideways
                branch_dir = (next_pt - current_pt)
                angle = np.random.uniform(-0.7, 0.7)
                # Rotate branch_dir
                c, s = np.cos(angle), np.sin(angle)
                bx = branch_dir[0] * c - branch_dir[1] * s
                by = branch_dir[0] * s + branch_dir[1] * c
                branch_end = next_pt + np.array([bx, by, 0.0], dtype=np.float32) * np.random.uniform(0.7, 1.3)
                segments.extend(self.generate_lightning_bolt(next_pt.copy(), branch_end, depth + 1, max_depth, branch_prob))
                
            current_pt = next_pt
            
        return segments

    def get_mangled_script_path(self, audio_path):
        if not audio_path:
            return ""
        import hashlib
        abs_path = os.path.abspath(audio_path)
        path_hash = hashlib.sha256(abs_path.encode('utf-8')).hexdigest()
        h1 = path_hash[0:2]
        h2 = path_hash[2:4]
        base_name = os.path.splitext(os.path.basename(abs_path))[0]
        safe_base = "".join(c if c.isalnum() or c in ('-', '_') else "_" for c in base_name)
        cached_dir = os.path.join(self.tmp_dir, "fireworks_cache", h1, h2)
        os.makedirs(cached_dir, exist_ok=True)
        return os.path.join(cached_dir, f"{safe_base}_{path_hash}.json")

    def load_playlist_files(self, paths):
        resolved = []
        audio_exts = ('.mp3', '.wav', '.ogg', '.opus', '.flac', '.m4a', '.aac')
        for p in paths:
            if not p or p.lower().endswith('.json'):
                continue
            if os.path.isdir(p):
                try:
                    for root, dirs, files in os.walk(p):
                        files.sort()
                        for f in files:
                            if f.lower().endswith(audio_exts):
                                resolved.append(os.path.join(root, f))
                except Exception as e:
                    print(f"Error scanning directory {p}: {e}")
            elif p.lower().endswith('.m3u'):
                if os.path.exists(p):
                    m3u_dir = os.path.dirname(os.path.abspath(p))
                    try:
                        with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith('#'):
                                    if not os.path.isabs(line):
                                        full_path = os.path.abspath(os.path.join(m3u_dir, line))
                                    else:
                                        full_path = line
                                    resolved.append(full_path)
                    except Exception as e:
                        print(f"Error reading playlist file {p}: {e}")
                else:
                    print(f"Playlist file {p} not found!")
            else:
                resolved.append(p)
        if self.shuffle_mode:
            random.shuffle(resolved)
        return resolved

    def load_and_play_track(self):
        if getattr(self, 'preset_random_mode', False) and getattr(self, 'preset_random_timer', 0.0) >= 45.0:
            print(f"[Random Mode] Triggering preset switch at start of track: {os.path.basename(self.audio_path) if self.audio_path else 'None'}")
            self.pick_random_preset()

        # 1. Stop current sync playback
        self.stop_sync_playback()
        
        # Clear existing visualizer events
        self.script_events = []
        self.next_event_idx = 0
        self.loaded_script_name = "None"
        self.update_legend_labels()
        
        if not self.audio_path or not os.path.exists(self.audio_path):
            print(f"Audio file not found: {self.audio_path}")
            return
            
        print(f"Loading and playing track: {self.audio_path}")
        
        # 2. Check if JSON script exists and is up-to-date
        json_exists = False
        import audio_analyzer
        if os.path.exists(self.script_path):
            try:
                with open(self.script_path, 'r') as f:
                    data = json.load(f)
                ver = data.get("metadata", {}).get("analyzer_version", 0)
                if ver >= audio_analyzer.ANALYZER_VERSION:
                    json_exists = True
            except Exception as e:
                print(f"Error checking JSON validity: {e}")
                
        # 3. Play audio IMMEDIATELY
        self.saved_auto_launch = self.auto_launch
        self.auto_launch = False
        self.fireworks.clear()
        
        try:
            if self.audio_player.play(self.audio_path):
                self.music_playing = True
                self.playback_start_time = time.time()
            else:
                raise RuntimeError("UnifiedAudioPlayer failed to play track")
        except Exception as e:
            print(f"Failed to start audio playback: {e}")
            self.auto_launch = self.saved_auto_launch
            self.update_legend_labels()
            return

        # 4. If JSON is valid, load it immediately and start sync
        if json_exists:
            print("Up-to-date JSON found. Loading immediately...")
            self.load_sync_script(self.script_path)
            self.next_event_idx = 0
            self.check_pregenerate_next_track()
        else:
            # 5. Otherwise, start asynchronous background generation
            print("No up-to-date JSON found. Starting background analysis thread...")
            import threading
            threading.Thread(target=self.async_analyze_and_activate, daemon=True).start()

    def async_analyze_and_activate(self):
        try:
            import audio_analyzer
            print(f"[Async Analyzer] Analyzing {self.audio_path} in background...")
            hints = getattr(self, 'color_hints', None) or ["strontium_red", "magnesium_white", "copper_blue"]
            script = audio_analyzer.analyze_audio(self.audio_path, hints)
            
            with open(self.script_path, 'w') as f:
                json.dump(script, f, indent=2)
            print(f"[Async Analyzer] Background analysis completed and saved to {self.script_path}")
            
            GLib.idle_add(self.activate_async_json, self.script_path)
        except Exception as e:
            print(f"[Async Analyzer] Error in background analysis: {e}")

    def activate_async_json(self, filepath):
        expected_script_path = self.get_mangled_script_path(self.audio_path)
        if filepath != expected_script_path:
            print(f"Background analysis finished for {filepath}, but active track has changed. Ignoring.")
            return False
            
        print(f"Activating asynchronously generated JSON: {filepath}")
        if self.load_sync_script(filepath):
            elapsed = time.time() - self.playback_start_time
            idx = 0
            while idx < len(self.script_events) and self.script_events[idx].get("time", 0.0) < elapsed:
                idx += 1
            self.next_event_idx = idx
            print(f"Choreography synced to elapsed play time: {elapsed:.2f}s (starting at event index {idx})")
            
            self.check_pregenerate_next_track()
            
        return False

    def check_pregenerate_next_track(self):
        if not self.playlist or len(self.playlist) <= 1:
            return
            
        next_idx = (self.playlist_idx + 1) % len(self.playlist)
        next_audio_path = self.playlist[next_idx]
        next_script_path = self.get_mangled_script_path(next_audio_path)
        
        json_exists = False
        import audio_analyzer
        if os.path.exists(next_script_path):
            try:
                with open(next_script_path, 'r') as f:
                    data = json.load(f)
                ver = data.get("metadata", {}).get("analyzer_version", 0)
                if ver >= audio_analyzer.ANALYZER_VERSION:
                    json_exists = True
            except Exception:
                pass
                
        if not json_exists:
            print(f"Pre-emptive Cache: Next track '{os.path.basename(next_audio_path)}' has no up-to-date JSON.")
            print(f"Starting pre-emptive background analysis for next track...")
            import threading
            threading.Thread(target=self.async_pregenerate_track, args=(next_audio_path, next_script_path), daemon=True).start()
        else:
            print(f"Pre-emptive Cache: Next track '{os.path.basename(next_audio_path)}' already has up-to-date JSON.")

    def async_pregenerate_track(self, audio_path, script_path):
        try:
            import audio_analyzer
            print(f"[Pre-emptive Analyzer] Pre-generating JSON for {audio_path} in background...")
            hints = ["strontium_red", "magnesium_white", "copper_blue"]
            script = audio_analyzer.analyze_audio(audio_path, hints)
            with open(script_path, 'w') as f:
                json.dump(script, f, indent=2)
            print(f"[Pre-emptive Analyzer] Finished pre-generating JSON for {audio_path}.")
        except Exception as e:
            print(f"[Pre-emptive Analyzer] Error pre-generating JSON for {audio_path}: {e}")

    def play_next_track(self):
        if not self.playlist:
            return
        next_idx = (self.playlist_idx + 1) % len(self.playlist)
        self.playlist_idx = next_idx
        self.audio_path = self.playlist[self.playlist_idx]
        self.script_path = self.get_mangled_script_path(self.audio_path)
        self.load_and_play_track()

    def play_previous_track(self):
        if not self.playlist:
            return
        prev_idx = (self.playlist_idx - 1) % len(self.playlist)
        self.playlist_idx = prev_idx
        self.audio_path = self.playlist[self.playlist_idx]
        self.script_path = self.get_mangled_script_path(self.audio_path)
        self.load_and_play_track()

    def apply_preset(self, idx):
        self.preset_idx = idx
        preset = self.active_presets[idx]
        
        if preset.get("random_preset"):
            self.preset_random_mode = True
            self.preset_random_timer = 0.0
            self.pick_random_preset()
        else:
            self.preset_random_mode = False
            self.apply_preset_settings(preset)

    def apply_preset_settings(self, preset):
        # Clear any active or queued rarity from previous modes
        self.active_rarity = None
        self.rarity_queued_type = None
        
        self.major_mode = preset["major_mode"]
        if self.major_mode in self.modes:
            self.major_mode_idx = self.modes.index(self.major_mode)
            
        if self.major_mode != "FIREWORKS":
            self.fireworks.clear()
            
        self.show_rockets = preset["show_rockets"]
        self.opt_color_mode = preset["opt_color_mode"]
        self.opt_trailers = preset["opt_trailers"]
        self.opt_gravity = preset["opt_gravity"]
        self.opt_height_restrict = preset["opt_height_restrict"]
        self.opt_star_shape = preset["opt_star_shape"]
        
        if self.major_mode == "SYNAESTHESIA Classic":
            if self.opt_star_shape in (1, 2, 3):
                self.syn_points_are_diamonds = True
            elif self.opt_star_shape in (4, 5, 6):
                self.syn_points_are_diamonds = False
        
        if "syn_star_size" in preset:
            self.syn_star_size = preset["syn_star_size"]
        if "syn_fade_mode" in preset:
            self.syn_fade_mode = preset["syn_fade_mode"]
            
        self.mandala_slices = preset.get("mandala_slices", 12)
        self.update_legend_labels()

    def pick_random_preset(self):
        self.preset_random_timer = 0.0
        candidates = list(range(len(self.active_presets) - 1))
        if hasattr(self, 'last_random_preset_idx') and self.last_random_preset_idx in candidates and len(candidates) > 1:
            candidates.remove(self.last_random_preset_idx)
        chosen_idx = random.choice(candidates)
        self.last_random_preset_idx = chosen_idx
        
        preset = self.active_presets[chosen_idx]
        print(f"RANDOM PRESET SWITCH: Switching to {preset['name']}!")
        self.apply_preset_settings(preset)

    def update_preset_random_timer(self, dt):
        if hasattr(self, 'preset_random_mode') and self.preset_random_mode:
            self.preset_random_timer += dt

    def get_sim_time(self):
        if hasattr(self, 'is_recording') and self.is_recording:
            return self.record_time
        return time.time() - self.start_time

    def load_css(self):
        css_data = """
        .hud-title {
            font-family: 'Outfit', 'Inter', 'Sans-Serif', sans-serif;
            font-size: 16px;
            font-weight: bold;
            color: #e6f0ff;
        }
        .hud-subtitle {
            font-family: 'Outfit', 'Inter', 'Sans-Serif', sans-serif;
            font-size: 10px;
            color: #96b4dc;
        }
        .hud-stats-fps {
            font-family: 'Inter', 'Monospace', monospace;
            font-size: 11px;
            font-weight: bold;
            color: #64e696;
            margin-bottom: 2px;
        }
        .hud-stats {
            font-family: 'Inter', 'Monospace', monospace;
            font-size: 10px;
            color: #c8dcff;
        }
        .hud-routine {
            font-family: 'Inter', 'Sans-Serif', sans-serif;
            font-size: 11px;
            font-weight: bold;
            color: #ffa834;
            margin-top: 3px;
        }
        .hud-legend {
            background-color: rgba(10, 10, 25, 0.65);
            border: 1px solid rgba(130, 150, 180, 0.2);
            border-radius: 6px;
            padding: 12px;
        }
        .hud-legend-title {
            font-family: 'Outfit', 'Inter', sans-serif;
            font-weight: bold;
            color: #e2e6ff;
            font-size: 10px;
            margin-bottom: 6px;
        }
        .hud-legend label {
            font-family: 'Inter', 'Monospace', monospace;
            font-size: 9px;
            color: #b4c8f0;
        }
        .hud-music-time {
            font-family: 'Inter', 'Monospace', monospace;
            font-size: 11px;
            font-weight: bold;
            color: #34c7f3;
            margin-top: 2px;
        }
        """
        provider = Gtk.CssProvider()
        if hasattr(provider, 'load_from_string'):
            provider.load_from_string(css_data)
        else:
            provider.load_from_data(css_data.encode('utf-8'))
        
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_activate(self, app):
        self.win = Gtk.ApplicationWindow(application=app)
        self.win.set_title("Melochor: 3D OpenGL Audio Visualizer")
        self.win.set_default_size(1280, 720)
        
        self.load_css()
        
        overlay = Gtk.Overlay()
        
        self.gl_area = Gtk.GLArea()
        self.gl_area.set_required_version(3, 2)
        self.gl_area.set_has_depth_buffer(True)
        self.gl_area.connect("realize", self.on_realize)
        self.gl_area.connect("render", self.on_render)
        overlay.set_child(self.gl_area)
        
        self.hud_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.hud_box.set_valign(Gtk.Align.START)
        self.hud_box.set_halign(Gtk.Align.START)
        self.hud_box.set_margin_start(20)
        self.hud_box.set_margin_top(20)
        
        title_lbl = Gtk.Label(label="MELOCHOR 3D")
        title_lbl.add_css_class("hud-title")
        title_lbl.set_halign(Gtk.Align.START)
        self.hud_box.append(title_lbl)
        
        sub_lbl = Gtk.Label(label="Interactive OpenGL Audio Visualizer & Screensaver")
        sub_lbl.add_css_class("hud-subtitle")
        sub_lbl.set_halign(Gtk.Align.START)
        self.hud_box.append(sub_lbl)
        
        stats_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        stats_box.set_margin_top(15)
        stats_box.set_halign(Gtk.Align.START)
        
        self.fps_lbl = Gtk.Label(label="FPS: 60.0")
        self.fps_lbl.add_css_class("hud-stats-fps")
        self.fps_lbl.set_halign(Gtk.Align.START)
        stats_box.append(self.fps_lbl)

        self.hud_bpm_lbl = Gtk.Label(label="BPM: 120.0")
        self.hud_bpm_lbl.add_css_class("hud-stats")
        self.hud_bpm_lbl.set_halign(Gtk.Align.START)
        stats_box.append(self.hud_bpm_lbl)

        self.hud_key_lbl = Gtk.Label(label="Key: N/A")
        self.hud_key_lbl.add_css_class("hud-stats")
        self.hud_key_lbl.set_halign(Gtk.Align.START)
        stats_box.append(self.hud_key_lbl)

        self.hud_sec_name_lbl = Gtk.Label(label="Section: None")
        self.hud_sec_name_lbl.add_css_class("hud-stats")
        self.hud_sec_name_lbl.set_halign(Gtk.Align.START)
        stats_box.append(self.hud_sec_name_lbl)

        self.hud_sec_cat_lbl = Gtk.Label(label="Category: None")
        self.hud_sec_cat_lbl.add_css_class("hud-stats")
        self.hud_sec_cat_lbl.set_halign(Gtk.Align.START)
        stats_box.append(self.hud_sec_cat_lbl)
        
        self.shell_lbl = Gtk.Label(label="Active Shells: 0")
        self.shell_lbl.add_css_class("hud-stats")
        self.shell_lbl.set_halign(Gtk.Align.START)
        stats_box.append(self.shell_lbl)
        
        self.part_lbl = Gtk.Label(label="Simulated Particles: 0")
        self.part_lbl.add_css_class("hud-stats")
        self.part_lbl.set_halign(Gtk.Align.START)
        stats_box.append(self.part_lbl)
        
        self.routine_lbl = Gtk.Label(label="Routine: None")
        self.routine_lbl.add_css_class("hud-routine")
        self.routine_lbl.set_halign(Gtk.Align.START)
        stats_box.append(self.routine_lbl)
        
        self.hud_box.append(stats_box)

        # Beautiful Music Sync Panel
        music_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        music_box.set_margin_top(15)
        music_box.set_halign(Gtk.Align.START)
        
        music_hdr = Gtk.Label(label="MUSIC SYNCHRONIZER:")
        music_hdr.add_css_class("hud-legend-title")
        music_hdr.set_halign(Gtk.Align.START)
        music_box.append(music_hdr)
        
        self.music_track_lbl = Gtk.Label(label="Track: None")
        self.music_track_lbl.add_css_class("hud-stats")
        self.music_track_lbl.set_halign(Gtk.Align.START)
        music_box.append(self.music_track_lbl)
        
        self.music_time_lbl = Gtk.Label(label="Time: 00:00 / 00:00")
        self.music_time_lbl.add_css_class("hud-music-time")
        self.music_time_lbl.set_halign(Gtk.Align.START)
        music_box.append(self.music_time_lbl)
        
        self.music_section_lbl = Gtk.Label(label="Section: None")
        self.music_section_lbl.add_css_class("hud-stats")
        self.music_section_lbl.set_halign(Gtk.Align.START)
        music_box.append(self.music_section_lbl)
        
        self.hud_box.append(music_box)

        overlay.add_overlay(self.hud_box)
        
        self.legend_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.legend_box.add_css_class("hud-legend")
        self.legend_box.set_valign(Gtk.Align.END)
        self.legend_box.set_halign(Gtk.Align.START)
        self.legend_box.set_margin_start(20)
        self.legend_box.set_margin_bottom(20)
        
        leg_title = Gtk.Label(label="KEYBOARD CONTROLS:")
        leg_title.add_css_class("hud-legend-title")
        leg_title.set_halign(Gtk.Align.START)
        self.legend_box.append(leg_title)
        
        lbl_space = Gtk.Label(label="[SPACE]  - Play/Pause Sync Playback")
        lbl_space.set_halign(Gtk.Align.START)
        self.legend_box.append(lbl_space)

        lbl_return = Gtk.Label(label="[ENTER]  - Launch Manual Shell")
        lbl_return.set_halign(Gtk.Align.START)
        self.legend_box.append(lbl_return)
        
        self.lbl_auto_launch = Gtk.Label()
        self.lbl_auto_launch.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_auto_launch)
        
        self.lbl_auto_rotate = Gtk.Label()
        self.lbl_auto_rotate.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_auto_rotate)
        
        self.lbl_music = Gtk.Label()
        self.lbl_music.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_music)
        
        self.lbl_rockets_toggle = Gtk.Label()
        self.lbl_rockets_toggle.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_rockets_toggle)
        
        self.lbl_legend_toggle = Gtk.Label()
        self.lbl_legend_toggle.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_legend_toggle)

        self.lbl_mode_toggle = Gtk.Label()
        self.lbl_mode_toggle.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_mode_toggle)
        
        self.lbl_rarity_cycle = Gtk.Label()
        self.lbl_rarity_cycle.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_rarity_cycle)

        lbl_tweaks_title = Gtk.Label(label="\nOPTIONAL TWEAKS:")
        lbl_tweaks_title.add_css_class("hud-legend-title")
        lbl_tweaks_title.set_halign(Gtk.Align.START)
        self.legend_box.append(lbl_tweaks_title)
        
        self.lbl_opt_color = Gtk.Label()
        self.lbl_opt_color.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_opt_color)

        self.lbl_opt_shape = Gtk.Label()
        self.lbl_opt_shape.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_opt_shape)

        self.lbl_opt_gravity = Gtk.Label()
        self.lbl_opt_gravity.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_opt_gravity)

        self.lbl_opt_trailers = Gtk.Label()
        self.lbl_opt_trailers.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_opt_trailers)
        
        self.lbl_opt_height = Gtk.Label()
        self.lbl_opt_height.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_opt_height)
        
        # Flame algorithm label (U to cycle)
        self.lbl_flame_algo = Gtk.Label()
        self.lbl_flame_algo.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_flame_algo)
        
        self.lbl_mandala_slices = Gtk.Label()
        self.lbl_mandala_slices.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_mandala_slices)
        
        self.update_legend_labels()
        
        lbl_clear = Gtk.Label(label="[C]      - Clear Active Particles")
        lbl_clear.set_halign(Gtk.Align.START)
        self.legend_box.append(lbl_clear)
        
        lbl_fs = Gtk.Label(label="[F]      - Toggle Fullscreen")
        lbl_fs.set_halign(Gtk.Align.START)
        self.legend_box.append(lbl_fs)
        
        lbl_quit = Gtk.Label(label="[ESC/Q]  - Quit Screensaver")
        lbl_quit.set_halign(Gtk.Align.START)
        self.legend_box.append(lbl_quit)
        
        lbl_routines_title = Gtk.Label(label="\nCHOREOGRAPHED ROUTINES:")
        lbl_routines_title.add_css_class("hud-legend-title")
        lbl_routines_title.set_halign(Gtk.Align.START)
        self.legend_box.append(lbl_routines_title)
        
        self.lbl_r1 = Gtk.Label(label="[1]  - American Flag")
        self.lbl_r1.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_r1)
        
        self.lbl_r2 = Gtk.Label(label="[2]  - Liberty Bell")
        self.lbl_r2.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_r2)
        
        self.lbl_r3 = Gtk.Label(label="[3]  - Statue of Liberty")
        self.lbl_r3.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_r3)
        
        self.lbl_r4 = Gtk.Label(label="[4]  - Flower Bouquet")
        self.lbl_r4.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_r4)
        
        self.lbl_r5 = Gtk.Label(label="[5]  - The Dragon")
        self.lbl_r5.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_r5)
        
        self.lbl_r6 = Gtk.Label(label="[6]  - Supernova")
        self.lbl_r6.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_r6)
        
        self.lbl_r7 = Gtk.Label(label="[7]  - Shooting Star")
        self.lbl_r7.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_r7)
        
        overlay.add_overlay(self.legend_box)
        
        self.win.set_child(overlay)
        
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.win.add_controller(key_controller)
        
        drag_gesture = Gtk.GestureDrag()
        drag_gesture.connect("drag-begin", self.on_drag_begin)
        drag_gesture.connect("drag-update", self.on_drag_update)
        self.gl_area.add_controller(drag_gesture)
        
        scroll_controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_controller.connect("scroll", self.on_scroll)
        self.gl_area.add_controller(scroll_controller)

        # File Drag and Drop Support
        try:
            drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
            drop_target.connect("drop", self.on_file_drop)
            self.win.add_controller(drop_target)
        except Exception as e:
            print(f"Failed to initialize Drag & Drop: {e}")

        # Context Menu Right-Click Gestures
        right_click = Gtk.GestureClick.new()
        right_click.set_button(3) # Right mouse button
        right_click.connect("pressed", self.on_right_click)
        self.gl_area.add_controller(right_click)
        
        GLib.timeout_add(16, self.on_tick)
        
        # Connect close-request signal to cleanly terminate background music
        self.win.connect("close-request", self.on_close_request)
        
        # Explicit audio script parsing & auto-start
        if self.preset_random_mode:
            self.apply_preset(len(self.active_presets) - 1)

        if self.is_recording:
            if not os.path.exists(self.script_path):
                print(f"No display script found for recording. Generating synchronously: {self.script_path}...")
                try:
                    import audio_analyzer
                    script = audio_analyzer.analyze_audio(self.audio_path, ["strontium_red", "magnesium_white", "copper_blue"])
                    with open(self.script_path, 'w') as f:
                        json.dump(script, f, indent=2)
                except Exception as e:
                    print(f"Failed to generate script for recording: {e}")
                    sys.exit(1)
            self.load_sync_script(self.script_path)
        else:
            # Play first track immediately (analyzes asynchronously in background if needed)
            GLib.idle_add(self.load_and_play_track)
            
        self.win.present()
        
        if self.audio_explicit:
            self.win.fullscreen()
            self.is_fullscreen = True
 
    def update_hud_labels(self):
        if hasattr(self, 'hud_bpm_lbl') and self.hud_bpm_lbl:
            bpm_val = getattr(self, 'script_bpm', 120.0)
            self.hud_bpm_lbl.set_text(f"BPM: {bpm_val:.1f}")
        if hasattr(self, 'hud_key_lbl') and self.hud_key_lbl:
            key_val = getattr(self, 'current_key', "N/A")
            self.hud_key_lbl.set_text(f"Key: {key_val}")
        if hasattr(self, 'hud_sec_name_lbl') and self.hud_sec_name_lbl:
            sec_val = getattr(self, 'current_section_name', "None")
            self.hud_sec_name_lbl.set_text(f"Section: {sec_val}")
        if hasattr(self, 'hud_sec_cat_lbl') and self.hud_sec_cat_lbl:
            cat_val = getattr(self, 'current_section_category', "None")
            self.hud_sec_cat_lbl.set_text(f"Category: {cat_val}")

    def update_legend_labels(self):
        if hasattr(self, 'lbl_opt_color') and self.lbl_opt_color:
            self.lbl_opt_color.set_text(f"[O]      - Color Mode: {self.opt_color_mode}")
        if hasattr(self, 'lbl_opt_shape') and self.lbl_opt_shape:
            shapes_desc = {0: "Default", 1: "Circles", 2: "Small Diamonds", 3: "Larger Diamonds", 4: "4-Pt Stars", 5: "5-Pt Stars", 6: "6-Pt Stars"}
            self.lbl_opt_shape.set_text(f"[P]      - Star Shape: {shapes_desc.get(self.opt_star_shape, 'Default')}")
        if hasattr(self, 'lbl_opt_gravity') and self.lbl_opt_gravity:
            grav_desc = "OFF" if self.opt_gravity == 0.0 else f"{self.opt_gravity}x"
            self.lbl_opt_gravity.set_text(f"[G]      - Gravity: {grav_desc}")
        if hasattr(self, 'lbl_opt_trailers') and self.lbl_opt_trailers:
            trail_desc = "OFF" if self.opt_trailers == 0 else f"Len {self.opt_trailers}"
            self.lbl_opt_trailers.set_text(f"[L]      - Trailers: {trail_desc}")
        if hasattr(self, 'lbl_opt_height') and self.lbl_opt_height:
            height_desc = "ON" if self.opt_height_restrict else "OFF"
            self.lbl_opt_height.set_text(f"[Y]      - Height Restriction: {height_desc}")
        if hasattr(self, 'lbl_flame_algo') and self.lbl_flame_algo:
            algo_name = self.fire_flame_names[self.fire_flame_algorithm] if hasattr(self, 'fire_flame_names') else "Current"
            self.lbl_flame_algo.set_text(f"[U]      - Flame Algorithm: {algo_name}")
        if hasattr(self, 'lbl_mandala_slices') and self.lbl_mandala_slices:
            self.lbl_mandala_slices.set_text(f"[S]      - Mandala Slices: {self.mandala_slices}")

        self.lbl_auto_launch.set_text(f"[A]      - Toggle Auto-Launcher ({'ON' if self.auto_launch else 'OFF'})")
        self.lbl_auto_rotate.set_text(f"[R]      - Toggle Camera Auto-Rotation ({'ON' if self.auto_rotate else 'OFF'})")
        if self.music_playing:
            self.lbl_music.set_text("[M]      - Toggle Music Sync (PLAYING)")
        elif len(self.script_events) > 0:
            self.lbl_music.set_text("[M]      - Toggle Music Sync (READY)")
        else:
            self.lbl_music.set_text("[M]      - Toggle Music Sync (NO SCRIPT)")
            
        if hasattr(self, 'lbl_rockets_toggle') and self.lbl_rockets_toggle:
            self.lbl_rockets_toggle.set_text(f"[T]      - Toggle Rockets ({'ON' if self.show_rockets else 'OFF'})")
        if hasattr(self, 'lbl_legend_toggle') and self.lbl_legend_toggle:
            self.lbl_legend_toggle.set_text("[H]      - Toggle Keyboard Controls HUD")
        if hasattr(self, 'lbl_mode_toggle') and self.lbl_mode_toggle:
            preset_name = self.active_presets[self.preset_idx]["name"]
            if getattr(self, 'preset_random_mode', False) and hasattr(self, 'last_random_preset_idx'):
                cur_preset = self.active_presets[self.last_random_preset_idx]["name"]
                self.lbl_mode_toggle.set_text(f"[V]      - Cycle Visual Mode: {preset_name} ({cur_preset})")
            else:
                self.lbl_mode_toggle.set_text(f"[V]      - Cycle Visual Mode: {preset_name}")
        if hasattr(self, 'lbl_rarity_cycle') and self.lbl_rarity_cycle:
            rarity_name = getattr(self, 'current_rarity_cycle_name', 'None')
            self.lbl_rarity_cycle.set_text(f"[K]      - Cycle Rarities ({rarity_name})")
            
        if hasattr(self, 'lbl_r1'):
            if self.major_mode == "FIREWORKS":
                self.lbl_r1.set_text("[1]  - American Flag")
                self.lbl_r2.set_text("[2]  - Liberty Bell")
                self.lbl_r3.set_text("[3]  - Statue of Liberty")
                self.lbl_r4.set_text("[4]  - Flower Bouquet")
                self.lbl_r5.set_text("[5]  - The Dragon")
            elif self.major_mode == "TUNNEL Wormhole":
                self.lbl_r1.set_text("[1]  - Plasma Burst")
                self.lbl_r2.set_text("[2]  - Gravity Surge")
                self.lbl_r3.set_text("[3]  - Stardust Stream")
                self.lbl_r4.set_text("[4]  - Event Horizon")
                self.lbl_r5.set_text("[5]  - Lightning Flash")
            elif self.major_mode == "UNDERWATER Lava":
                self.lbl_r1.set_text("[1]  - Coral Pulse")
                self.lbl_r2.set_text("[2]  - Geyser Eruption")
                self.lbl_r3.set_text("[3]  - Plankton Surge")
                self.lbl_r4.set_text("[4]  - Deep Vent Blast")
                self.lbl_r5.set_text("[5]  - Bioluminescent Rainbow")
            elif self.major_mode == "MANDALA Sacred":
                self.lbl_r1.set_text("[1]  - Lotus Bloom")
                self.lbl_r2.set_text("[2]  - Cosmic Spin")
                self.lbl_r3.set_text("[3]  - Infinite Pulse")
                self.lbl_r4.set_text("[4]  - Geometric Collapse")
                self.lbl_r5.set_text("[5]  - Astral Projection")
            elif self.major_mode == "SYNAESTHESIA Classic":
                shape_name = "Diamond" if getattr(self, 'syn_points_are_diamonds', True) else "Star"
                self.lbl_r1.set_text(f"[1]  - Shape: {shape_name}")
                self.lbl_r2.set_text(f"[2]  - Star Size: {getattr(self, 'syn_star_size', 0.5)}")
                self.lbl_r3.set_text(f"[3]  - Brightness: {getattr(self, 'syn_brightness', 0.35)}")
                self.lbl_r4.set_text(f"[4]  - Fade Mode: {getattr(self, 'syn_fade_mode', 'Stars')}")
                self.lbl_r5.set_text("[5]  - Trigger Star Burst")
            elif self.major_mode == "FIRE Plasma":
                self.lbl_r1.set_text("[1]  - Flame Flare (Bass)")
                self.lbl_r2.set_text("[2]  - Flame Wave (Mid)")
                self.lbl_r3.set_text("[3]  - Treble Spark Shower")
                self.lbl_r4.set_text("[4]  - Fire Eruption")
                self.lbl_r5.set_text("[5]  - Lightning Strike")
                
        if hasattr(self, 'lbl_r6'):
            if self.major_mode == "MANDALA Sacred":
                self.lbl_r6.set_text("[6]  - Peace Symbol")
            elif self.major_mode in ("SYNAESTHESIA Classic", "FIRE Plasma"):
                self.lbl_r6.set_text("")
            else:
                self.lbl_r6.set_text("[6]  - Supernova")
        if hasattr(self, 'lbl_r7'):
            if self.major_mode == "MANDALA Sacred":
                self.lbl_r7.set_text("[7]  - Halo & Outward Sparks")
            elif self.major_mode in ("SYNAESTHESIA Classic", "FIRE Plasma"):
                self.lbl_r7.set_text("")
            else:
                self.lbl_r7.set_text("[7]  - Shooting Star")















                


            



    def trigger_climax_event(self, intensity=1.5, routine_name=""):
        # Setup climax properties
        self.climax_flash = intensity
        self.active_routine_name = routine_name or "Climax Burst!"
        self.routine_timer = 5.0
        
        # Boost visualizer envelopes aggressively
        self.react_bass = min(1.8, self.react_bass + 1.2)
        self.react_mid = min(1.8, self.react_mid + 1.2)
        self.react_treble = min(1.8, self.react_treble + 1.2)
        
        if self.major_mode == "UNDERWATER Lava":
            if routine_name == "Supernova":
                # Giant white-hot supernova eruption from all vents!
                for _ in range(240):
                    idx = self.next_bubble_idx
                    v_idx = random.randint(0, 2)
                    v_loc = self.vent_locs[v_idx]
                    self.bubble_pos[idx] = [v_loc[0], v_loc[1] + 1.75, v_loc[2]] + np.random.uniform([-0.5, 0.0, -0.5], [0.5, 0.25, 0.5])
                    self.bubble_size[idx] = np.random.uniform(4.0, 8.0)
                    self.bubble_vel[idx] = [np.random.uniform(-2.5, 2.5), np.random.uniform(4.0, 8.0), np.random.uniform(-2.5, 2.5)]
                    self.bubble_col[idx] = [1.0, 0.95, 0.8, 1.0]
                    self.bubble_active[idx] = True
                    self.bubble_is_fragment[idx] = False
                    self.next_bubble_idx = (self.next_bubble_idx + 1) % len(self.bubble_pos)
                if self.active_rarity is not None and self.active_rarity['type'] == 'SQUID':
                    self.squid_vel = self.squid_dir * 2.0 # slowed down to 1/4 from 8.0
                    self.squid_phase = 0.0
            elif routine_name == "Shooting Star":
                # Underwater shooting stars: cyan bioluminescent trails streaking horizontally
                for i in range(120):
                    idx = self.next_bubble_idx
                    self.bubble_pos[idx] = [-15.0 + i * 0.1, np.random.uniform(0.0, 8.0), np.random.uniform(0.0, 6.0)]
                    self.bubble_vel[idx] = [np.random.uniform(8.0, 15.0), np.random.uniform(-0.4, 0.4), np.random.uniform(-0.4, 0.4)]
                    self.bubble_size[idx] = np.random.uniform(2.0, 4.0)
                    self.bubble_col[idx] = [0.1, 0.85, 1.0, 0.95]
                    self.bubble_active[idx] = True
                    self.bubble_is_fragment[idx] = False
                    self.next_bubble_idx = (self.next_bubble_idx + 1) % len(self.bubble_pos)
            else:
                for _ in range(180):
                    idx = self.next_bubble_idx
                    v_idx = random.randint(0, 2)
                    v_loc = self.vent_locs[v_idx]
                    self.bubble_pos[idx] = [v_loc[0], v_loc[1] + 1.75, v_loc[2]] + np.random.uniform([-0.35, 0.0, -0.35], [0.35, 0.25, 0.35])
                    self.bubble_size[idx] = np.random.uniform(2.5, 6.0)
                    rise_speed = np.random.uniform(2.5, 5.5)
                    self.bubble_vel[idx] = [np.random.uniform(-1.5, 1.5), rise_speed, np.random.uniform(-1.5, 1.5)]
                    self.bubble_col[idx] = [random.choice([0.9, 0.1, 0.0]), random.choice([0.1, 0.9, 0.8]), random.choice([0.9, 0.1, 1.0]), np.random.uniform(0.7, 1.0)]
                    self.bubble_active[idx] = True
                    self.bubble_is_fragment[idx] = False
                    self.next_bubble_idx = (self.next_bubble_idx + 1) % len(self.bubble_pos)
                    
            for i in range(self.num_jelly):
                self.jelly_phase[i] = 0.0
                self.jelly_vel[i] = self.jelly_dir[i] * 5.0
                self.jelly_col[i, 3] = 1.0
                
        elif self.major_mode == "TUNNEL Wormhole":
            get_bend_offsets = self.get_bend_offsets
            if routine_name == "Lightning Flash":
                self.lightning_active_timer = 0.4
                self.active_lightning_bolts = []
                for _ in range(2):
                    bolt = []
                    bx, by = get_bend_offsets(-55.0)
                    bolt.append([np.random.uniform(-2.5, 2.5) + bx, np.random.uniform(-2.5, 2.5) + by + 4.0, -55.0])
                    for z_coord in np.linspace(-50.0, 0.0, 15):
                        bx, by = get_bend_offsets(z_coord)
                        bolt.append([np.random.uniform(-2.5, 2.5) + bx, np.random.uniform(-2.5, 2.5) + by + 4.0, z_coord])
                    self.active_lightning_bolts.append(bolt)
            if routine_name == "Supernova":
                self.wormhole_supernova_active = True
                self.wormhole_supernova_age = 0.0
                for k in range(120):
                    idx = self.next_spark_idx
                    self.spark_pos[idx] = [0.0, 0.0, -15.0]
                    theta_v = np.random.uniform(0.0, 2.0 * np.pi)
                    phi_v = np.random.uniform(-np.pi / 2.0, np.pi / 2.0)
                    speed_v = np.random.uniform(10.0, 20.0)
                    vx = speed_v * np.cos(phi_v) * np.cos(theta_v)
                    vy = speed_v * np.cos(phi_v) * np.sin(theta_v)
                    vz = speed_v * np.sin(phi_v)
                    
                    self.spark_vel[idx] = [vx, vy, vz]
                    self.spark_col[idx] = [1.0, 0.9, 0.7, 1.0] if k % 2 == 0 else [0.2, 0.8, 1.0, 1.0]
                    self.spark_size[idx] = np.random.uniform(9.0, 15.0)
                    self.spark_age[idx] = 0.0
                    self.spark_max_age[idx] = np.random.uniform(1.2, 2.0)
                    self.spark_active[idx] = True
                    self.next_spark_idx = (self.next_spark_idx + 1) % len(self.spark_pos)
            elif routine_name == "Shooting Star":
                self.wormhole_shooting_star_active = True
                self.wormhole_shooting_star_z = -55.0
                self.wormhole_shooting_star_x = np.random.uniform(-3.0, 3.0)
                self.wormhole_shooting_star_y = np.random.uniform(-3.0, 3.0)
                for ss in range(6):
                    ss_x = np.random.uniform(-5.0, 5.0)
                    ss_y = np.random.uniform(-5.0, 5.0)
                    ss_z = -55.0
                    for k in range(15):
                        idx = self.next_spark_idx
                        self.spark_pos[idx] = [ss_x, ss_y, ss_z - k * 0.8]
                        self.spark_vel[idx] = [0.0, 0.0, 35.0]
                        self.spark_col[idx] = [1.0, 0.95, 0.8, 1.0]
                        self.spark_size[idx] = np.random.uniform(8.0, 12.0) - k * 0.4
                        self.spark_age[idx] = 0.0
                        self.spark_max_age[idx] = np.random.uniform(1.5, 2.2)
                        self.spark_active[idx] = True
                        self.next_spark_idx = (self.next_spark_idx + 1) % len(self.spark_pos)
            else:
                near_gems = np.where((self.gem_z < 0.0) & (self.gem_z > -50.0))[0]
                if len(near_gems) > 0:
                    for _ in range(25):
                        g_idx = random.choice(near_gems)
                        self.spawn_gem_sparks(g_idx)
                        for s_offset in range(6):
                            s_idx = (self.next_spark_idx - s_offset - 1) % len(self.spark_pos)
                            if self.spark_active[s_idx]:
                                self.spark_vel[s_idx] *= 1.8
                                self.spark_size[s_idx] *= 1.6
                                
        elif self.major_mode == "MANDALA Sacred":
            if routine_name == "Peace Symbol":
                self.peace_symbol_timer = 5.0
                for idx in range(len(self.mandala_base_pos)):
                    self.mandala_base_pos[idx] = [0.0, 4.0, 0.0]
                    angle = (idx / len(self.mandala_base_pos)) * 2.0 * np.pi
                    speed = np.random.uniform(9.0, 14.0)
                    self.mandala_base_vel[idx, 0] = speed * np.cos(angle)
                    self.mandala_base_vel[idx, 1] = speed * np.sin(angle)
                    self.mandala_base_vel[idx, 2] = np.random.uniform(-0.5, 0.5)
                    self.mandala_base_ages[idx] = 0.0
                    self.mandala_base_max_ages[idx] = np.random.uniform(2.0, 3.0)
                    self.mandala_base_col[idx] = [1.0, 0.8, 0.1, 1.0] if idx % 2 == 0 else [1.0, 0.3, 0.2, 1.0]
                    self.mandala_base_size[idx] = np.random.uniform(10.0, 16.0)
            elif routine_name == "Halo Effect":
                self.halo_timer = 5.0
                for idx in range(len(self.mandala_base_pos)):
                    self.mandala_base_pos[idx] = [0.0, 4.0, 0.0]
                    angle = (idx / len(self.mandala_base_pos)) * 2.0 * np.pi
                    speed = np.random.uniform(11.0, 17.0)
                    self.mandala_base_vel[idx, 0] = speed * np.cos(angle)
                    self.mandala_base_vel[idx, 1] = speed * np.sin(angle)
                    self.mandala_base_vel[idx, 2] = np.random.uniform(-0.5, 0.5)
                    self.mandala_base_ages[idx] = 0.0
                    self.mandala_base_max_ages[idx] = np.random.uniform(2.2, 3.5)
                    self.mandala_base_col[idx] = [0.15, 0.85, 1.0, 1.0] if idx % 2 == 0 else [0.9, 0.15, 0.5, 1.0]
                    self.mandala_base_size[idx] = np.random.uniform(12.0, 20.0)
            elif routine_name == "Supernova":
                # Explode all mandala particles radially
                for idx in range(len(self.mandala_base_pos)):
                    self.mandala_base_pos[idx] = [0.0, 4.0, 0.0]
                    angle = (idx / len(self.mandala_base_pos)) * 2.0 * np.pi
                    speed = np.random.uniform(10.0, 15.0)
                    self.mandala_base_vel[idx, 0] = speed * np.cos(angle)
                    self.mandala_base_vel[idx, 1] = speed * np.sin(angle)
                    self.mandala_base_vel[idx, 2] = np.random.uniform(-1.0, 1.0)
                    self.mandala_base_ages[idx] = 0.0
                    self.mandala_base_max_ages[idx] = np.random.uniform(2.2, 3.5)
                    self.mandala_base_col[idx] = [1.0, 0.95, 0.8, 1.0] if idx % 2 == 0 else [0.95, 0.25, 0.85, 1.0]
                    self.mandala_base_size[idx] = np.random.uniform(14.0, 22.0)
            elif routine_name == "Shooting Star":
                # Contracting cosmic shooting stars inwards
                for idx in range(100):
                    angle = np.random.uniform(0.0, 2 * np.pi)
                    rad = 12.0
                    self.mandala_base_pos[idx] = [rad * np.cos(angle), 4.0 + rad * np.sin(angle), np.random.uniform(-0.5, 0.5)]
                    speed = -np.random.uniform(6.0, 10.0)
                    self.mandala_base_vel[idx, 0] = speed * np.cos(angle)
                    self.mandala_base_vel[idx, 1] = speed * np.sin(angle)
                    self.mandala_base_vel[idx, 2] = np.random.uniform(-0.1, 0.1)
                    self.mandala_base_ages[idx] = 0.0
                    self.mandala_base_max_ages[idx] = np.random.uniform(1.8, 2.8)
                    self.mandala_base_col[idx] = [0.1, 0.9, 1.0, 1.0]
                    self.mandala_base_size[idx] = np.random.uniform(8.0, 14.0)
        elif self.major_mode == "SYNAESTHESIA Classic":
            self.trigger_syn_star_burst()
        elif self.major_mode == "FIRE Plasma":
            if routine_name == "Flame Flare":
                for _ in range(160):
                    self.spawn_differentiated_spark('FLARE')
            elif routine_name == "Flame Wave":
                for _ in range(180):
                    self.spawn_differentiated_spark('WAVE')
            elif routine_name == "Treble Spark Shower":
                for _ in range(250):
                    self.spawn_differentiated_spark('SHOWER')
            elif routine_name == "Fire Eruption":
                for _ in range(300):
                    self.spawn_differentiated_spark('ERUPTION')
            elif routine_name in ("Lotus Bloom", "Coral Pulse", "Plasma Burst"):
                for _ in range(120):
                    self.spawn_fire_spark("bass", 1.8)
            elif routine_name in ("Cosmic Spin", "Geyser Eruption", "Gravity Surge"):
                for _ in range(120):
                    self.spawn_fire_spark("mid", 1.8)
            elif routine_name in ("Infinite Pulse", "Plankton Surge", "Stardust Stream"):
                for _ in range(120):
                    self.spawn_fire_spark("treble", 1.8)
            elif routine_name in ("Geometric Collapse", "Deep Vent Blast", "Event Horizon"):
                for _ in range(200):
                    band = random.choice(["bass", "mid", "treble"])
                    self.spawn_fire_spark(band, 2.0)
            elif routine_name == "Lightning Strike":
                # Procedural lightning-strike trigger (Upgraded to 1-4 random bolts with dynamic branching intricacy!)
                if not hasattr(self, 'fire_lightning_bolts'):
                    self.fire_lightning_bolts = []
                
                num_bolts = np.random.randint(1, 5)
                for _ in range(num_bolts):
                    start_x = np.random.uniform(-0.85, 0.85)
                    end_x = np.random.uniform(-0.35, 0.35) # Strike inside or near the hearth ring
                    start_pt = [start_x, 1.0, 0.0]
                    end_pt = [end_x, -0.82, 0.0]
                    
                    # Randomize intricacy and branching probability per bolt
                    is_intricate = np.random.uniform(0.0, 1.0) < 0.45
                    max_d = np.random.randint(4, 6) if is_intricate else np.random.randint(2, 4)
                    b_prob = np.random.uniform(0.24, 0.34) if is_intricate else np.random.uniform(0.12, 0.18)
                    
                    segments = self.generate_lightning_bolt(start_pt, end_pt, max_depth=max_d, branch_prob=b_prob)
                    
                    # Randomize bolt lifetime slightly so they don't fade at the exact same millisecond
                    b_life = np.random.uniform(0.18, 0.32)
                    self.fire_lightning_bolts.append({
                        'segments': segments,
                        'life': b_life,
                        'max_life': b_life
                    })
                
                # Dynamic sky strobe flash
                self.climax_flash = 1.0
                
                # Electric blue/white spark shower explosion at the striking points!
                for _ in range(120):
                    idx = self.next_fire_spark_idx
                    self.next_fire_spark_idx = (self.next_fire_spark_idx + 1) % len(self.fire_spark_pos)
                    strike_x = np.random.uniform(-0.35, 0.35)
                    self.fire_spark_pos[idx] = [strike_x, -0.82, np.random.uniform(-0.05, 0.05)]
                    theta = np.random.uniform(0.0, 2.0 * np.pi)
                    phi = np.random.uniform(np.radians(10.0), np.radians(80.0))
                    speed = np.random.uniform(1.2, 3.2)
                    self.fire_spark_vel[idx] = [speed * np.sin(phi) * np.sin(theta), speed * np.cos(phi), speed * np.sin(phi) * np.cos(theta)]
                    self.fire_spark_col[idx] = [0.85, 0.95, 1.0, 1.0] # Electric blueish-white!
                    self.fire_spark_size[idx] = np.random.uniform(3.0, 7.0)
                    max_life = np.random.uniform(0.6, 1.5)
                    self.fire_spark_life[idx] = max_life
                    self.fire_spark_max_life[idx] = max_life
                    self.fire_spark_hue[idx] = 0.82 # Blueish hue range
                    self.fire_spark_active[idx] = True
            elif routine_name in ("Thermal Flare", "Astral Projection", "Bioluminescent Rainbow", "Lightning Flash"):
                for _ in range(250):
                    self.spawn_fire_spark("treble", 2.2)
            elif routine_name == "Supernova":
                for _ in range(250):
                    idx = self.next_fire_spark_idx
                    self.next_fire_spark_idx = (self.next_fire_spark_idx + 1) % len(self.fire_spark_pos)
                    self.fire_spark_pos[idx] = [np.random.uniform(-2.0, 2.0), np.random.uniform(-1.0, 1.0), np.random.uniform(-1.0, 1.0)]
                    angle = np.random.uniform(0.0, 2.0 * np.pi)
                    speed = np.random.uniform(4.0, 10.0)
                    self.fire_spark_vel[idx] = [speed * np.cos(angle), np.random.uniform(3.0, 10.0), speed * np.sin(angle)]
                    self.fire_spark_col[idx] = [1.0, np.random.uniform(0.3, 0.9), np.random.uniform(0.0, 0.5), 1.0]
                    self.fire_spark_size[idx] = np.random.uniform(6.0, 15.0)
                    max_life = np.random.uniform(2.0, 4.0)
                    self.fire_spark_life[idx] = max_life
                    self.fire_spark_max_life[idx] = max_life
                    self.fire_spark_active[idx] = True
            elif routine_name == "Shooting Star":
                for _ in range(15):
                    idx = self.next_fire_spark_idx
                    self.next_fire_spark_idx = (self.next_fire_spark_idx + 1) % len(self.fire_spark_pos)
                    self.fire_spark_pos[idx] = [np.random.uniform(-6.0, 6.0), -1.0, np.random.uniform(-2.0, 2.0)]
                    self.fire_spark_vel[idx] = [np.random.uniform(-1.0, 1.0), np.random.uniform(12.0, 18.0), np.random.uniform(-1.0, 1.0)]
                    self.fire_spark_col[idx] = [1.0, np.random.uniform(0.8, 1.0), np.random.uniform(0.5, 0.8), 1.0]
                    self.fire_spark_size[idx] = np.random.uniform(12.0, 20.0)
                    max_life = np.random.uniform(3.0, 4.5)
                    self.fire_spark_life[idx] = max_life
                    self.fire_spark_max_life[idx] = max_life
                    self.fire_spark_active[idx] = True

    def spawn_rarity(self, r_type):
        print(f"SPAWNING RARITY: {r_type}!")
        if r_type == "SQUID":
            pos = np.array([np.random.uniform(-4.0, 4.0), np.random.uniform(1.0, 2.5), np.random.uniform(0.0, 4.0)], dtype=np.float32)
            # Restrict squid direction vector to within 30 degrees of camera-perpendicular X-Y plane
            theta = np.random.uniform(0.0, 2.0 * np.pi)
            dx = np.cos(theta)
            dy = np.sin(theta)
            dz = np.random.uniform(-0.45, 0.45)
            direction = np.array([dx, dy, dz], dtype=np.float32)
            direction /= np.linalg.norm(direction)
            self.squid_pos = pos
            self.squid_dir = direction
            self.squid_vel = direction * 1.0 # slowed down to 1/4 from 4.0
            self.squid_phase = 0.0
            self.active_rarity = {
                'type': 'SQUID',
                'life': 30.0,
                'max_life': 30.0
            }
        elif r_type == "MANTA":
            # Expand spawn starting point to -24.0 for full screen boundary clearance
            pos = np.array([-24.0, np.random.uniform(2.0, 7.0), np.random.uniform(0.0, 6.0)], dtype=np.float32)
            direction = np.array([1.0, np.random.uniform(-0.1, 0.1), np.random.uniform(-0.1, 0.1)], dtype=np.float32)
            direction /= np.linalg.norm(direction)
            self.active_rarity = {
                'type': 'MANTA',
                'pos': pos,
                'dir': direction,
                'vel': direction * 1.75,
                'phase': 0.0,
                'life': 25.0,
                'max_life': 25.0
            }
        elif r_type == "SEAHORSE":
            # Spawn just below seabed (Y=-6.0) so it rises into view quickly
            pos = np.array([np.random.uniform(-4.0, 4.0), -6.0, np.random.uniform(1.0, 5.0)], dtype=np.float32)
            direction = np.array([np.random.uniform(-0.15, 0.15), 1.0, np.random.uniform(-0.15, 0.15)], dtype=np.float32)
            direction /= np.linalg.norm(direction)
            self.active_rarity = {
                'type': 'SEAHORSE',
                'pos': pos,
                'dir': direction,
                'vel': direction * 1.15, # majestic upward swim speed
                'phase': 0.0,
                'life': 30.0,
                'max_life': 30.0
            }
        elif r_type == "LANTERN_FISH":
            # Spawn at -24.0 horizontally and keep deep in background (Z in [-15.0, -13.0])
            pos = np.array([-24.0, np.random.uniform(1.0, 7.0), np.random.uniform(-15.0, -13.0)], dtype=np.float32)
            direction = np.array([1.0, np.random.uniform(-0.1, 0.1), np.random.uniform(-0.1, 0.1)], dtype=np.float32)
            direction /= np.linalg.norm(direction)
            offsets = [np.array([np.random.uniform(-1.5, 1.5), np.random.uniform(-1.2, 1.2), np.random.uniform(-1.0, 1.0)], dtype=np.float32) for _ in range(8)]
            self.active_rarity = {
                'type': 'LANTERN_FISH',
                'pos': pos,
                'dir': direction,
                'vel': direction * 1.4, # slowed from 2.2 to 1.4
                'offsets': offsets,
                'life': 30.0,
                'max_life': 30.0
            }
        elif r_type == "PLANET":
            # Gas giant planet initialization
            ang = np.random.uniform(0.0, 2 * np.pi)
            r_dist = 13.0
            pos = np.array([r_dist * np.cos(ang), r_dist * np.sin(ang), -55.0], dtype=np.float32)
            style = "NEPTUNE"
            self.active_rarity = {
                'type': 'PLANET',
                'pos': pos,
                'vel': np.array([0.0, 0.0, 15.0], dtype=np.float32),
                'phase': 0.0,
                'style': style,
                'life': 7.0,
                'max_life': 7.0
            }
        elif r_type == "GALAXY":
            # Move Galaxy farther away in background
            ang = np.random.uniform(0.0, 2 * np.pi)
            r_dist = 22.0
            pos = np.array([r_dist * np.cos(ang), r_dist * np.sin(ang), -85.0], dtype=np.float32)
            self.active_rarity = {
                'type': 'GALAXY',
                'pos': pos,
                'vel': np.array([0.0, 0.0, 3.2], dtype=np.float32),
                'phase': 0.0,
                'life': 31.0,
                'max_life': 31.0
            }
        elif r_type == "ASTEROIDS":
            pos = np.array([0.0, 0.0, -55.0], dtype=np.float32)
            offsets = [np.random.uniform(-15.0, 15.0, 3) for _ in range(10)]
            for ao in offsets:
                ao[2] = np.random.uniform(-8.0, 8.0)
                ao[0] = np.sign(ao[0]) * max(11.0, abs(ao[0]))
                ao[1] = np.sign(ao[1]) * max(11.0, abs(ao[1]))
            self.active_rarity = {
                'type': 'ASTEROIDS',
                'pos': pos,
                'vel': np.array([0.0, 0.0, 23.0], dtype=np.float32),
                'offsets': offsets,
                'rotations': [np.random.uniform(0.0, 2*np.pi) for _ in range(10)],
                'rot_vels': [np.random.uniform(0.5, 2.5) for _ in range(10)],
                'life': 5.0,
                'max_life': 5.0
            }

        elif r_type == "CATHERINE_WHEEL":
            # Move Catherine Wheel center up to align with screen bottom (Y = -4.5)
            pos = np.array([np.random.uniform(-10.0, 10.0), -4.5, np.random.uniform(-5.0, -1.0)], dtype=np.float32)
            self.active_rarity = {
                'type': 'CATHERINE_WHEEL',
                'pos': pos,
                'phase': 0.0,
                'spin_vel': 18.0,
                'sparks_pos': [],
                'sparks_vel': [],
                'sparks_col': [],
                'sparks_age': [],
                'life': 10.0,
                'max_life': 10.0
            }
        elif r_type == "BIRD":
            self.active_rarity = {
                'type': 'BIRD',
                'pos': np.array([0.0, 4.0, 0.0], dtype=np.float32),
                'ang': np.random.uniform(0.0, 2*np.pi),
                'phase': 0.0,
                'life': 12.0,
                'max_life': 12.0
            }
        elif r_type == "SMOKE":
            self.active_rarity = {
                'type': 'SMOKE',
                'particles_pos': [],
                'particles_ang': [],
                'particles_rad': [],
                'life': 6.0,
                'max_life': 6.0
            }
        elif r_type == "SUN_BURST":
            self.active_rarity = {
                'type': 'SUN_BURST',
                'phase': 0.0,
                'life': 3.5,
                'max_life': 3.5
            }
        elif r_type == "BUTTERFLY":
            self.active_rarity = {
                'type': 'BUTTERFLY',
                'pos': np.array([0.0, 4.0, 0.0], dtype=np.float32),
                'ang': np.random.uniform(0.0, 2*np.pi),
                'phase': 0.0,
                'life': 15.0,
                'max_life': 15.0
            }
        elif r_type == "SHOOTING_STAR":
            fly_right = np.random.choice([True, False])
            if fly_right:
                # Spawn on left, fly right
                start_x = np.random.uniform(-0.8, -0.2)
                vel_x = np.random.uniform(0.15, 0.35)
            else:
                # Spawn on right, fly left
                start_x = np.random.uniform(0.2, 0.8)
                vel_x = np.random.uniform(-0.35, -0.15)
                
            start_pt = np.array([start_x, 1.0], dtype=np.float32)
            # Randomized angle/vertical speed
            vel_y = np.random.uniform(-0.3, -0.15)
            vel = np.array([vel_x, vel_y], dtype=np.float32)
            
            self.active_rarity = {
                'type': 'SHOOTING_STAR',
                'pos': start_pt,
                'vel': vel,
                'trail': [start_pt.copy()],
                'life': 18.0,
                'max_life': 18.0
            }
        elif r_type == "BATS":
            bats = []
            num_bats = np.random.randint(6, 11)
            for _ in range(num_bats):
                ox = np.random.uniform(-0.18, 0.18)
                oy = np.random.uniform(-0.15, 0.15)
                b_pos = np.array([-1.2 + ox, 0.18 + oy], dtype=np.float32)
                # Velocity is 1/5 of previous speed
                b_vel = np.array([np.random.uniform(0.076, 0.096), np.random.uniform(0.016, 0.032)], dtype=np.float32)
                bats.append({
                    'pos': b_pos,
                    'vel': b_vel,
                    'phase': np.random.uniform(0.0, 2.0 * np.pi)
                })
            self.active_rarity = {
                'type': 'BATS',
                'bats': bats,
                'life': 35.0, # Increased lifetime since they move 1/5 speed
                'max_life': 35.0
            }
        elif r_type == "TUMBLEWEED":
            spawn_left = np.random.choice([True, False])
            x_start = -1.2 if spawn_left else 1.2
            # Speed is halved again!
            speed_val = np.random.uniform(0.04, 0.07)
            vx = speed_val if spawn_left else -speed_val
            
            # Depth displacement (forward-back from current location)
            depth_offset = np.random.uniform(-0.06, 0.06)
            base_y = -0.58 + depth_offset
            radius = 0.022 + depth_offset * 0.22 # Scale size with physical depth
            
            self.active_rarity = {
                'type': 'TUMBLEWEED',
                'x': x_start,
                'base_y': base_y,
                'y': base_y,
                'vel_x': vx,
                'radius': radius,
                'rotation': 0.0,
                'rot_vel': vx / radius,
                'bounce_phase': 0.0,
                'hop_y': 0.0,
                'hop_vy': 0.0,
                'life': 55.0,
                'max_life': 55.0
            }

    def update_active_rarity(self, dt):
        r = self.active_rarity
        r['life'] -= dt
        if r['life'] <= 0.0:
            self.active_rarity = None
            return
        t_type = r['type']
        if t_type == "SQUID":
            # Squid is updated inside update_underwater_mode
            pass
        elif t_type == "MANTA":
            r['pos'] += r['vel'] * dt
            # Precisely match the wing flap to the music track's BPM (1 flap every 8 beats)
            r['phase'] += dt * (self.script_bpm / 60.0) * 0.25 * np.pi
            # Fully swims off the screen boundaries before deactivating
            if r['pos'][0] > 24.0:
                self.active_rarity = None
        elif t_type == "SEAHORSE":
            r['pos'] += r['vel'] * dt
            # Bobbing phase synchronized with audio
            r['phase'] += dt * (2.5 + self.react_bass * 5.0)
            # Add horizontal/vertical bobbing physics synchronized with audio
            bob_h = np.sin(r['phase'] * 1.2) * 0.8 * (1.0 + self.react_bass * 1.5)
            bob_v = np.cos(r['phase'] * 0.8) * 0.65 * (1.0 + self.react_bass * 1.5)
            r['pos'][0] += bob_h * dt
            r['pos'][1] += bob_v * dt
            # Fully bob/swim off screen boundaries before deactivating
            if r['pos'][1] > 11.0:
                self.active_rarity = None
        elif t_type == "LANTERN_FISH":
            r['pos'] += r['vel'] * dt
            # Fully swims off screen boundaries before deactivating
            if r['pos'][0] > 24.0:
                self.active_rarity = None
        elif t_type == "PLANET":
            r['pos'] += r['vel'] * dt
            r['phase'] += dt * 0.75
            if r['pos'][2] > 18.0:
                self.active_rarity = None
        elif t_type == "GALAXY":
            r['pos'] += r['vel'] * dt
            r['phase'] += dt * 0.5
            if r['pos'][2] > 18.0:
                self.active_rarity = None
        elif t_type == "ASTEROIDS":
            r['pos'] += r['vel'] * dt
            for i in range(len(r['rotations'])):
                r['rotations'][i] += r['rot_vels'][i] * dt
            if r['pos'][2] > 18.0:
                self.active_rarity = None

        elif t_type == "CATHERINE_WHEEL":
            r['phase'] += r['spin_vel'] * dt
            for i in range(4):
                ang = r['phase'] + i * (np.pi / 2.0)
                nozzle_pos = r['pos'] + np.array([np.cos(ang) * 0.5, np.sin(ang) * 0.5, 0.0], dtype=np.float32)
                out_dir = np.array([np.cos(ang), np.sin(ang), np.random.uniform(-0.15, 0.15)], dtype=np.float32)
                tangent_dir = np.array([-np.sin(ang), np.cos(ang), 0.0], dtype=np.float32)
                spark_vel = out_dir * np.random.uniform(6.0, 12.0) + tangent_dir * 8.0
                r['sparks_pos'].append(nozzle_pos)
                r['sparks_vel'].append(spark_vel)
                r['sparks_col'].append(random.choice([
                    [1.0, 0.8, 0.1, 1.0],
                    [0.9, 0.9, 0.95, 1.0],
                    [1.0, 0.3, 0.1, 1.0]
                ]))
                r['sparks_age'].append(0.0)
            rem_pos, rem_vel, rem_col, rem_age = [], [], [], []
            for j in range(len(r['sparks_pos'])):
                r['sparks_age'][j] += dt
                if r['sparks_age'][j] < 0.8:
                    r['sparks_vel'][j][1] -= 9.8 * dt # gravity
                    next_pos = r['sparks_pos'][j] + r['sparks_vel'][j] * dt
                    # Bounce or slide realistically on the floor plane Y = -12.0
                    if next_pos[1] < -12.0:
                        next_pos[1] = -12.0
                        r['sparks_vel'][j][1] = -r['sparks_vel'][j][1] * 0.45 # bounce elasticity
                        r['sparks_vel'][j][0] *= 0.85 # friction
                        r['sparks_vel'][j][2] *= 0.85 # friction
                    r['sparks_pos'][j] = next_pos
                    r['sparks_col'][j][3] = 1.0 - (r['sparks_age'][j] / 0.8)
                    rem_pos.append(r['sparks_pos'][j])
                    rem_vel.append(r['sparks_vel'][j])
                    rem_col.append(r['sparks_col'][j])
                    rem_age.append(r['sparks_age'][j])
            r['sparks_pos'] = rem_pos
            r['sparks_vel'] = rem_vel
            r['sparks_col'] = rem_col
            r['sparks_age'] = rem_age
        elif t_type == "BIRD":
            r['phase'] += dt * 15.0
            speed = 4.2 * (1.0 + self.react_mid * 0.5)
            r['pos'][0] += np.cos(r['ang']) * speed * dt
            r['pos'][1] += np.sin(r['ang']) * speed * dt
            # Fully flies off screen boundaries before deactivating
            if np.linalg.norm(r['pos'] - np.array([0.0, 4.0, 0.0])) > 24.0:
                self.active_rarity = None
        elif t_type == "SMOKE":
            # Spawn 4 smoke particles per frame at slightly offset spiral progression angles
            for step in range(4):
                ang = (r['life'] * 3.5 + step * 0.15) % (2.0 * np.pi)
                r['particles_pos'].append(np.array([0.0, 4.0, 0.0], dtype=np.float32))
                r['particles_ang'].append(ang)
                r['particles_rad'].append(0.0)
            rem_pos, rem_ang, rem_rad = [], [], []
            for j in range(len(r['particles_pos'])):
                r['particles_rad'][j] += dt * 2.8 * (1.0 + self.react_mid * 0.4)
                r['particles_ang'][j] += dt * 3.0
                rad = r['particles_rad'][j]
                theta = r['particles_ang'][j]
                r['particles_pos'][j] = np.array([rad * np.cos(theta), 4.0 + rad * np.sin(theta), np.sin(theta * 2.0) * 0.15], dtype=np.float32)
                if rad < 12.0:
                    rem_pos.append(r['particles_pos'][j])
                    rem_ang.append(r['particles_ang'][j])
                    rem_rad.append(r['particles_rad'][j])
            r['particles_pos'] = rem_pos
            r['particles_ang'] = rem_ang
            r['particles_rad'] = rem_rad
        elif t_type == "SUN_BURST":
            r['phase'] += dt * 0.4
        elif t_type == "BUTTERFLY":
            # Music-modulated wing flap rate
            flap_rate = 24.0 + self.react_treble * 35.0
            r['phase'] += dt * flap_rate
            # Music-modulated turning angles/speeds
            erratic_factor = 6.0 + self.react_bass * 12.0
            r['ang'] += np.random.uniform(-1.8, 1.8) * dt * erratic_factor
            # Music-modulated speed and bobbing amplitude
            speed = 3.6 + self.react_mid * 5.0
            bob_amp = 1.5 + self.react_bass * 4.0
            r['pos'][0] += (np.cos(r['ang']) * speed + np.sin(r['phase'] * 3.0) * bob_amp) * dt
            r['pos'][1] += (np.sin(r['ang']) * speed + np.cos(r['phase'] * 3.5) * bob_amp) * dt
            # Fully flies off screen boundaries before deactivating
            if np.linalg.norm(r['pos'] - np.array([0.0, 4.0, 0.0])) > 24.0:
                self.active_rarity = None
        elif t_type == "SHOOTING_STAR":
            r['pos'] += r['vel'] * dt
            r['trail'].append(r['pos'].copy())
            if len(r['trail']) > 8:
                r['trail'].pop(0)
            if r['pos'][1] < -0.38:
                self.active_rarity = None
        elif t_type == "BATS":
            all_off_screen = True
            for b in r['bats']:
                b['pos'] += b['vel'] * dt
                if b['pos'][0] < 1.2:
                    all_off_screen = False
            if all_off_screen:
                self.active_rarity = None
        elif t_type == "TUMBLEWEED":
            r['x'] += r['vel_x'] * dt
            r['rotation'] += r['rot_vel'] * dt
            
            # Constant rolling rhythm bobbing
            r['bounce_phase'] += dt * 6.0
            base_bob = abs(np.sin(r['bounce_phase'])) * 0.003
            
            # Big beat detection (using self.react_bass > 0.54)
            if self.react_bass > 0.54:
                # Upward jump velocity scaled by bass power
                r['hop_vy'] = max(r.get('hop_vy', 0.0), self.react_bass * 0.18)
                
            # Physics loop for the big hops
            r['hop_y'] += r['hop_vy'] * dt
            r['hop_vy'] -= 0.65 * dt # Gravity pulling downwards
            
            # Ground collision check
            if r['hop_y'] <= 0.0:
                r['hop_y'] = 0.0
                if abs(r['hop_vy']) > 0.04:
                    r['hop_vy'] = -r['hop_vy'] * 0.42 # Elastic bounce!
                else:
                    r['hop_vy'] = 0.0
                    
            r['y'] = r['base_y'] + base_bob + r['hop_y']
            if (r['vel_x'] > 0 and r['x'] > 1.2) or (r['vel_x'] < 0 and r['x'] < -1.2):
                self.active_rarity = None

    def update_rarity_system(self, dt):
        if self.active_rarity is None and self.rarity_queued_type is None:
            self.rarity_cooldown += dt
            if self.rarity_cooldown >= RARITY_INTERVAL:
                if self.major_mode == "UNDERWATER Lava":
                    self.rarity_queued_type = random.choice(["SQUID", "MANTA", "SEAHORSE", "LANTERN_FISH"])
                elif self.major_mode == "TUNNEL Wormhole":
                    self.rarity_queued_type = random.choice(["PLANET", "GALAXY", "ASTEROIDS"])
                elif self.major_mode == "FIREWORKS":
                    self.rarity_queued_type = "CATHERINE_WHEEL" 
                elif self.major_mode == "MANDALA Sacred":
                    self.rarity_queued_type = random.choice(["BIRD", "SMOKE", "SUN_BURST", "BUTTERFLY"])
                elif self.major_mode == "FIRE Plasma":
                    self.rarity_queued_type = random.choice(["SHOOTING_STAR", "BATS", "TUMBLEWEED"])
                if self.rarity_queued_type is not None:
                    print(f"Rarity queued: {self.rarity_queued_type}. Waiting for significant beat...")
                    self.rarity_cooldown = 0.0
        if self.rarity_queued_type is not None:
            if self.react_bass > .54:
                self.spawn_rarity(self.rarity_queued_type)
                self.rarity_queued_type = None
        if self.active_rarity is not None:
            self.update_active_rarity(dt)

    def trigger_routine(self, name, launch_func):
        self.routine_queue.clear()
        self.active_routine_name = name
        self.routine_timer = 5.0
        launch_func()

    def launch_american_flag(self):
        # Red stripes
        for x in [-9.0, -3.0, 3.0, 9.0]:
            self.routine_queue.append((0.0, Firework(fw_type=0, color=COLORS["strontium_red"], x_offset=x)))
        # White stripes
        for x in [-6.0, 0.0, 6.0]:
            self.routine_queue.append((0.2, Firework(fw_type=1, color=COLORS["magnesium_white"], x_offset=x)))
        # Blue canton stars
        for x in [-11.0, -7.0]:
            fw = Firework(fw_type=3, color=COLORS["copper_blue"], x_offset=x)
            fw.launch_vel[1] += 3.0
            self.routine_queue.append((0.4, fw))

    def launch_liberty_bell(self):
        # Top of the bell
        top_crown = Firework(fw_type=12, color=COLORS["sodium_gold"], x_offset=0.0)
        top_crown.launch_vel[1] += 4.0
        self.routine_queue.append((0.0, top_crown))
        
        # Sides of the bell fanning down
        left_waterfall = Firework(fw_type=5, color=COLORS["sodium_gold"], x_offset=-4.0)
        left_waterfall.launch_vel[0] = -1.5
        right_waterfall = Firework(fw_type=5, color=COLORS["sodium_gold"], x_offset=4.0)
        right_waterfall.launch_vel[0] = 1.5
        self.routine_queue.append((0.2, left_waterfall))
        self.routine_queue.append((0.2, right_waterfall))
        
        # Clapper at bottom cracking/crackling
        clapper = Firework(fw_type=15, color=COLORS["magnesium_white"], x_offset=0.0)
        clapper.launch_vel[1] -= 2.0
        self.routine_queue.append((0.5, clapper))

    def launch_statue_of_liberty(self):
        # Pedestal/Body (green waterfall)
        body = Firework(fw_type=5, color=COLORS["barium_green"], x_offset=-2.0)
        self.routine_queue.append((0.0, body))
        
        # Crown Rays (radiating green ghost rings)
        for idx, (x, vx) in enumerate([(-6.0, -3.0), (-2.0, -1.0), (2.0, 1.0)]):
            ray = Firework(fw_type=3, color=COLORS["barium_green"], x_offset=x)
            ray.launch_vel[0] = vx
            self.routine_queue.append((0.1 * idx, ray))
            
        # Golden Torch (high up on the right)
        torch = Firework(fw_type=11, color=COLORS["sodium_gold"], x_offset=3.0)
        torch.launch_vel[1] += 5.0
        torch.launch_vel[0] = 1.5
        self.routine_queue.append((0.4, torch))

    def launch_flower_bouquet(self):
        colors = [COLORS["strontium_red"], COLORS["barium_green"], COLORS["potassium_purple"], COLORS["calcium_orange"], COLORS["sodium_gold"]]
        types = [0, 1, 11]
        for idx, x in enumerate([-8.0, -4.0, 0.0, 4.0, 8.0]):
            col = colors[idx % len(colors)]
            t = types[idx % len(types)]
            fw = Firework(fw_type=t, color=col, x_offset=x)
            fw.launch_vel[0] = x * 0.4
            self.routine_queue.append((0.0, fw))

    def launch_the_dragon(self):
        for i in range(12):
            delay = i * 0.15
            x = -12.0 + i * 2.0
            col = COLORS["barium_green"] if i % 2 == 0 else COLORS["sodium_gold"]
            t = 17 if i % 2 == 0 else 6
            fw = Firework(fw_type=t, color=col, x_offset=x)
            fw.launch_vel[0] = -1.0 + (i * 0.2)
            self.routine_queue.append((delay, fw))
            
    def launch_supernova(self):
        fw_center = Firework(fw_type=4, color=COLORS["magnesium_white"], x_offset=0.0)
        fw_center.launch_vel = np.array([0.0, 26.0, 0.0], dtype=np.float32)
        fw_center.star_size = 15.0
        fw_center.secondary_color = COLORS["copper_blue"]
        self.routine_queue.append((0.0, fw_center))
        
        for angle in np.linspace(0, 2 * np.pi, 6, endpoint=False):
            x = 8.0 * np.cos(angle)
            z = 6.0 * np.sin(angle)
            fw_ring = Firework(fw_type=7, color=COLORS["sodium_gold"], x_offset=x)
            fw_ring.launch_pos[2] = z
            fw_ring.launch_vel = np.array([x * 0.15, 23.0, z * 0.15], dtype=np.float32)
            fw_ring.secondary_color = COLORS["potassium_purple"]
            self.routine_queue.append((0.4, fw_ring))
            
        for x in [-5.0, 5.0]:
            fw_crack = Firework(fw_type=15, color=COLORS["magnesium_white"], x_offset=x)
            fw_crack.launch_vel[1] = 24.0
            self.routine_queue.append((1.2, fw_crack))
            
    def launch_shooting_star(self):
        fw_left = Firework(fw_type=18, color=COLORS["magnesium_white"], x_offset=-14.0)
        fw_left.launch_vel = np.array([12.0, 16.0, -2.0], dtype=np.float32)
        fw_left.launch_fuse = 2.0
        fw_left.star_size = 10.0
        fw_left.secondary_color = COLORS["sodium_gold"]
        self.routine_queue.append((0.0, fw_left))
        
        fw_right = Firework(fw_type=18, color=COLORS["magnesium_white"], x_offset=14.0)
        fw_right.launch_vel = np.array([-12.0, 17.0, 2.0], dtype=np.float32)
        fw_right.launch_fuse = 2.0
        fw_right.star_size = 10.0
        fw_right.secondary_color = COLORS["sodium_gold"]
        self.routine_queue.append((0.3, fw_right))
        
        fw_mid = Firework(fw_type=10, color=COLORS["copper_blue"], x_offset=0.0)
        fw_mid.launch_vel = np.array([0.0, 25.0, -1.0], dtype=np.float32)
        fw_mid.secondary_color = COLORS["magnesium_white"]
        self.routine_queue.append((0.6, fw_mid))

    def on_realize(self, area):
        area.make_current()
        if area.get_error() is not None:
            print("GLArea realize error:", area.get_error())
            return
             
        gl.glClearColor(0.01, 0.01, 0.05, 1.0)
        
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LEQUAL)
        
        try:
            gl.glEnable(gl.GL_PROGRAM_POINT_SIZE)
        except Exception:
            pass
            
        # Modern Shader Programs Compilation and Linking
        try:
            self.sky_program = create_program(SKY_VERTEX_SHADER, SKY_FRAGMENT_SHADER)
            self.line_program = create_program(LINE_VERTEX_SHADER, LINE_FRAGMENT_SHADER)
            self.particle_program = create_program(PARTICLE_VERTEX_SHADER, PARTICLE_FRAGMENT_SHADER)
        except Exception as e:
            print("Shader initialization failed:", e)
            return
        
        # Compile sky fullscreen quad VBO
        self.sky_vao = gl.glGenVertexArrays(1)
        self.sky_vbo = gl.glGenBuffers(1)
        sky_vertices = np.array([
            -1.0, -1.0,
             1.0, -1.0,
             1.0,  1.0,
            -1.0,  1.0
        ], dtype=np.float32)
        
        gl.glBindVertexArray(self.sky_vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.sky_vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, sky_vertices.nbytes, sky_vertices, gl.GL_STATIC_DRAW)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        gl.glBindVertexArray(0)
        
        # Dynamic Line Buffers Setup
        self.line_vao = gl.glGenVertexArrays(1)
        self.line_pos_vbo, self.line_col_vbo = gl.glGenBuffers(2)
        
        gl.glBindVertexArray(self.line_vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.line_pos_vbo)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.line_col_vbo)
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 4, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        gl.glBindVertexArray(0)
        
        # Dynamic Jellyfish Hood Buffers Setup
        self.hood_vao = gl.glGenVertexArrays(1)
        self.hood_pos_vbo, self.hood_col_vbo = gl.glGenBuffers(2)
        
        gl.glBindVertexArray(self.hood_vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.hood_pos_vbo)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.hood_col_vbo)
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 4, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        gl.glBindVertexArray(0)
        
        # Dynamic Particle Buffers Setup
        self.particle_vao = gl.glGenVertexArrays(1)
        self.particle_pos_vbo, self.particle_col_vbo, self.particle_size_vbo = gl.glGenBuffers(3)
        
        gl.glBindVertexArray(self.particle_vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.particle_pos_vbo)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.particle_col_vbo)
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 4, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.particle_size_vbo)
        gl.glEnableVertexAttribArray(2)
        gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        gl.glBindVertexArray(0)
        
        # Query program uniform locations
        self.line_proj_loc = gl.glGetUniformLocation(self.line_program, "projection")
        self.line_view_loc = gl.glGetUniformLocation(self.line_program, "view")
        self.line_fire_mode_loc = gl.glGetUniformLocation(self.line_program, "uFireMode")
        
        self.part_proj_loc = gl.glGetUniformLocation(self.particle_program, "projection")
        self.part_view_loc = gl.glGetUniformLocation(self.particle_program, "view")
        self.part_star_shape_loc = gl.glGetUniformLocation(self.particle_program, "uStarShape")
        self.part_fire_mode_loc = gl.glGetUniformLocation(self.particle_program, "uFireMode")
        self.sky_time_loc = gl.glGetUniformLocation(self.sky_program, "uTime")
        self.sky_ripple_loc = gl.glGetUniformLocation(self.sky_program, "uRipple")
        self.sky_climax_flash_loc = gl.glGetUniformLocation(self.sky_program, "uClimaxFlash")
        self.sky_bend_x_loc = gl.glGetUniformLocation(self.sky_program, "uWormholeBendX")
        self.sky_bend_y_loc = gl.glGetUniformLocation(self.sky_program, "uWormholeBendY")
        self.sky_phase_x_loc = gl.glGetUniformLocation(self.sky_program, "uWormholePhaseX")
        self.sky_phase_y_loc = gl.glGetUniformLocation(self.sky_program, "uWormholePhaseY")
        self.sky_react_bass_loc = gl.glGetUniformLocation(self.sky_program, "uReactBass")
        self.sky_react_treble_loc = gl.glGetUniformLocation(self.sky_program, "uReactTreble")
        self.sky_react_mid_loc = gl.glGetUniformLocation(self.sky_program, "uReactMid")
        self.sky_stereo_panning_loc = gl.glGetUniformLocation(self.sky_program, "uStereoPanning")
        self.sky_wormhole_speed_factor_loc = gl.glGetUniformLocation(self.sky_program, "uWormholeSpeedFactor")
        self.sky_aspect_loc = gl.glGetUniformLocation(self.sky_program, "uAspect")
        self.sky_inv_vp_loc = gl.glGetUniformLocation(self.sky_program, "uInvVP")
        self.sky_moon_tex_loc = gl.glGetUniformLocation(self.sky_program, "uMoonTex")
        self.sky_has_moon_tex_loc = gl.glGetUniformLocation(self.sky_program, "uHasMoonTex")
        self.sky_wind_gust_loc = gl.glGetUniformLocation(self.sky_program, "uWindGust")
        self.sky_moon_illumed_loc = gl.glGetUniformLocation(self.sky_program, "uMoonIllumed")
        self.sky_moon_is_waning_loc = gl.glGetUniformLocation(self.sky_program, "uMoonIsWaning")
        self.sky_color_mode_loc = gl.glGetUniformLocation(self.sky_program, "uColorMode")
        self.sky_flame_algo_loc = gl.glGetUniformLocation(self.sky_program, "uFlameAlgorithm")

        # Clarification note:
        # If you encountered the term "dff" in discussion, it's almost certainly a typo
        # for "diff". There's no special "dff" concept here.
        # The relevant new addition is the shader uniform 'uFlameAlgorithm' above.
        # That uniform selects which procedural flame the fragment shader draws:
        #   0 = Current (original shader flame)
        #   1 = Gas Jet (narrow blue/white jet)
        #   2 = Bonfire (wide chaotic red/orange)
        #   3 = Candle (tall, narrow yellow core)
        #
        # The application-side value is provided by FireModeMixin.fire_flame_algorithm,
        # which is cycled by FireModeMixin.cycle_flame_algorithm() when you press 'U'.
        # So pressing 'U' should visibly change the sky/fire shader rendering.

    def on_render(self, area, context):
        get_bend_offsets = self.get_bend_offsets
        if self.sky_program is None:
            return False
            
        w = area.get_width()
        h = area.get_height()
        scale = area.get_scale_factor()
        w_phys = w * scale
        h_phys = h * scale
        aspect = w_phys / h_phys if h_phys > 0 else 1.0
        
        # Compute CPU Projection and View Matrices early so the fullscreen background shader can perform world-space tracking
        proj_matrix = perspective_matrix(50.0, aspect, 0.1, 150.0)
        cx = self.camera_dist * np.cos(self.camera_phi) * np.sin(self.camera_theta)
        cy = self.camera_dist * np.sin(self.camera_phi)
        cz = self.camera_dist * np.cos(self.camera_phi) * np.cos(self.camera_theta)
        view_matrix = look_at_matrix([cx, cy, cz], [0.0, 4.0, 0.0], [0.0, 1.0, 0.0])
        
        # Ensure active mode is initialized before rendering or binding uniforms
        if self.major_mode == "TUNNEL Wormhole":
            if not hasattr(self, 'gem_z'):
                self.init_tunnel_mode()
        elif self.major_mode == "UNDERWATER Lava":
            if not hasattr(self, 'bubble_pos'):
                self.init_underwater_mode()
        elif self.major_mode == "MANDALA Sacred":
            if not hasattr(self, 'mandala_base_pos'):
                self.init_mandala_mode()
        elif self.major_mode == "FIRE Plasma":
            if not hasattr(self, 'fire_spark_pos'):
                self.init_fire_mode()
        
        # Open recording process if first frame
        if hasattr(self, 'is_recording') and self.is_recording and self.ffmpeg_process is None:
            self.start_recording_process(w_phys, h_phys)
            
        # If we are recording, run the tick update first to compute the state at self.record_time
        if hasattr(self, 'is_recording') and self.is_recording:
            self.on_recording_tick()
        
        gl.glViewport(0, 0, w_phys, h_phys)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        
        # 1. Draw Fullscreen Sky Gradient or Raymarched Plasma Wormhole (Depth Testing Off)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glUseProgram(self.sky_program)
        if hasattr(self, 'sky_time_loc') and self.sky_time_loc != -1:
            gl.glUniform1f(self.sky_time_loc, self.get_sim_time())
            
        if hasattr(self, 'sky_climax_flash_loc') and self.sky_climax_flash_loc != -1:
            gl.glUniform1f(self.sky_climax_flash_loc, self.climax_flash)
            
        if hasattr(self, 'sky_ripple_loc') and self.sky_ripple_loc != -1:
            if self.major_mode == "UNDERWATER Lava":
                gl.glUniform1f(self.sky_ripple_loc, 1.0)
            elif self.major_mode == "TUNNEL Wormhole":
                gl.glUniform1f(self.sky_ripple_loc, 2.0)
            elif self.major_mode == "FIRE Plasma":
                gl.glUniform1f(self.sky_ripple_loc, 3.0)
            else:
                gl.glUniform1f(self.sky_ripple_loc, 0.0)
                
        # Send full coordinates and audio parameters for continuous GPU raymarching/effects
        if self.major_mode in ("TUNNEL Wormhole", "FIRE Plasma"):
            bpm = self.script_bpm if (hasattr(self, 'script_bpm') and self.script_bpm > 0.0) else 40.0
            bpm = np.clip(bpm, 40.0, 240.0)
            
            # Pronounced non-linear scaling: floor of 0.15 at 40 BPM, nominal 1.0 at 120 BPM, and cap of 4.0 at 240 BPM
            if bpm <= 120.0:
                speed_factor = 0.15 + 0.85 * ((bpm - 40.0) / 80.0) ** 1.8
            else:
                speed_factor = 1.0 + 3.0 * ((bpm - 120.0) / 120.0) ** 1.5
                
            if hasattr(self, 'sky_wormhole_speed_factor_loc') and self.sky_wormhole_speed_factor_loc != -1:
                gl.glUniform1f(self.sky_wormhole_speed_factor_loc, speed_factor)
                
            if hasattr(self, 'sky_bend_x_loc') and self.sky_bend_x_loc != -1:
                gl.glUniform1f(self.sky_bend_x_loc, self.wormhole_bend_x if hasattr(self, 'wormhole_bend_x') else 0.0)
            if hasattr(self, 'sky_bend_y_loc') and self.sky_bend_y_loc != -1:
                gl.glUniform1f(self.sky_bend_y_loc, self.wormhole_bend_y if hasattr(self, 'wormhole_bend_y') else 0.0)
            if hasattr(self, 'sky_phase_x_loc') and self.sky_phase_x_loc != -1:
                gl.glUniform1f(self.sky_phase_x_loc, self.wormhole_phase_x if hasattr(self, 'wormhole_phase_x') else 0.0)
            if hasattr(self, 'sky_phase_y_loc') and self.sky_phase_y_loc != -1:
                gl.glUniform1f(self.sky_phase_y_loc, self.wormhole_phase_y if hasattr(self, 'wormhole_phase_y') else 0.0)
            if hasattr(self, 'sky_react_bass_loc') and self.sky_react_bass_loc != -1:
                gl.glUniform1f(self.sky_react_bass_loc, self.react_bass_smooth)
            if hasattr(self, 'sky_react_treble_loc') and self.sky_react_treble_loc != -1:
                gl.glUniform1f(self.sky_react_treble_loc, self.react_treble)
            if hasattr(self, 'sky_react_mid_loc') and self.sky_react_mid_loc != -1:
                gl.glUniform1f(self.sky_react_mid_loc, self.react_mid)
            if hasattr(self, 'sky_stereo_panning_loc') and self.sky_stereo_panning_loc != -1:
                gl.glUniform1f(self.sky_stereo_panning_loc, self.current_stereo_panning)
            if hasattr(self, 'sky_aspect_loc') and self.sky_aspect_loc != -1:
                gl.glUniform1f(self.sky_aspect_loc, aspect)
            if hasattr(self, 'sky_inv_vp_loc') and self.sky_inv_vp_loc != -1:
                vp = proj_matrix @ view_matrix
                inv_vp = np.linalg.inv(vp)
                gl.glUniformMatrix4fv(self.sky_inv_vp_loc, 1, gl.GL_TRUE, inv_vp)
            if hasattr(self, 'sky_wind_gust_loc') and self.sky_wind_gust_loc != -1:
                gl.glUniform1f(self.sky_wind_gust_loc, self.fire_wind_gust if hasattr(self, 'fire_wind_gust') else 0.0)
            if hasattr(self, 'sky_moon_illumed_loc') and self.sky_moon_illumed_loc != -1:
                gl.glUniform1f(self.sky_moon_illumed_loc, self.moon_illumed if hasattr(self, 'moon_illumed') else 0.5)
            if hasattr(self, 'sky_moon_is_waning_loc') and self.sky_moon_is_waning_loc != -1:
                gl.glUniform1f(self.sky_moon_is_waning_loc, 1.0 if (hasattr(self, 'moon_is_waning') and self.moon_is_waning) else 0.0)
            if hasattr(self, 'sky_color_mode_loc') and self.sky_color_mode_loc != -1:
                c_mode = 0
                if hasattr(self, 'opt_color_mode'):
                    if self.opt_color_mode == 'NEON': c_mode = 1
                    elif self.opt_color_mode == 'TRANQUIL': c_mode = 2
                    elif self.opt_color_mode == 'METAL': c_mode = 3
                gl.glUniform1i(self.sky_color_mode_loc, c_mode)
                if hasattr(self, 'sky_flame_algo_loc') and self.sky_flame_algo_loc != -1:
                    gl.glUniform1f(self.sky_flame_algo_loc, float(self.fire_flame_algorithm))

            # Ensure moon texture is loaded and bind it for Fire mode
            if self.major_mode == "FIRE Plasma":
                if not hasattr(self, 'moon_texture_id') or self.moon_texture_id is None:
                    self.init_moon_texture()
                if hasattr(self, 'moon_texture_id') and self.moon_texture_id is not None and self.moon_texture_id > 0:
                    gl.glActiveTexture(gl.GL_TEXTURE0)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, self.moon_texture_id)
                    if hasattr(self, 'sky_moon_tex_loc') and self.sky_moon_tex_loc != -1:
                        gl.glUniform1i(self.sky_moon_tex_loc, 0)
                    if hasattr(self, 'sky_has_moon_tex_loc') and self.sky_has_moon_tex_loc != -1:
                        gl.glUniform1f(self.sky_has_moon_tex_loc, 1.0)
                else:
                    if hasattr(self, 'sky_has_moon_tex_loc') and self.sky_has_moon_tex_loc != -1:
                        gl.glUniform1f(self.sky_has_moon_tex_loc, 0.0)
            else:
                if hasattr(self, 'sky_has_moon_tex_loc') and self.sky_has_moon_tex_loc != -1:
                    gl.glUniform1f(self.sky_has_moon_tex_loc, 0.0)
                
        gl.glBindVertexArray(self.sky_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_FAN, 0, 4)
        gl.glBindVertexArray(0)
        
        # Enable Depth Testing and Blending for World Render (Standard alpha blending for high-fidelity silhouettes and lines)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        
        # 2. Gather, Buffer and Render All Line Geometries (Ground Grid & Rocket Trails)
        line_pos = []
        line_col = []
        
        # Draw Jagged Lightning Bolts down the Tunnel during Lightning Flash event
        if self.major_mode == "TUNNEL Wormhole" and self.lightning_active_timer > 0.0:
            # Jagged paths in line segments
            for bolt in self.active_lightning_bolts:
                if len(bolt) > 1:
                    for idx in range(len(bolt) - 1):
                        line_pos.append(bolt[idx])
                        line_pos.append(bolt[idx + 1])
                        # strobe color
                        line_col.append([0.85, 0.95, 1.0, 1.0])
                        line_col.append([0.85, 0.95, 1.0, 1.0])
                        
        # Draw Campfire Lightning Bolts in FIRE Plasma mode
        if self.major_mode == "FIRE Plasma" and hasattr(self, 'fire_lightning_bolts'):
            for bolt in self.fire_lightning_bolts:
                frac = bolt['life'] / bolt['max_life']
                # Stroboscopic lightning flickering intensity
                strobe = 1.0 if (int(frac * 30.0) % 2 == 0) else 0.15
                alpha = frac * strobe
                
                for pt0, pt1, depth in bolt['segments']:
                    line_pos.append(pt0)
                    line_pos.append(pt1)
                    
                    # Main trunk is thick white-blue, branches are thinner blueish
                    if depth == 0:
                        col = [0.92, 0.96, 1.0, alpha * 0.95]
                    else:
                        col = [0.35, 0.65, 1.0, alpha * 0.55 * (1.0 / (depth + 1))]
                    line_col.append(col)
                    line_col.append(col)
                    
        # Draw Scenic FIRE Plasma Mode Rarities (Shooting Star, Bats, Tumbleweed)
        if self.major_mode == "FIRE Plasma" and self.active_rarity is not None:
            r = self.active_rarity
            if r['type'] == 'SHOOTING_STAR' and 'trail' in r:
                for idx in range(len(r['trail']) - 1):
                    pt0 = r['trail'][idx]
                    pt1 = r['trail'][idx + 1]
                    alpha = (idx + 1) / len(r['trail'])
                    line_pos.append([pt0[0], pt0[1], 0.0])
                    line_pos.append([pt1[0], pt1[1], 0.0])
                    # Beautiful blazing white-gold trail
                    line_col.append([1.0, 0.90, 0.65, alpha * 0.95])
                    line_col.append([1.0, 0.90, 0.65, alpha * 0.95])
            elif r['type'] == 'BATS' and 'bats' in r:
                span = 0.024 # Wider wing span for striking silhouette visibility
                t_val = self.get_sim_time()
                for b in r['bats']:
                    bp = b['pos']
                    flap = np.sin(t_val * 24.0 + b['phase']) * 0.015
                    col = [0.0, 0.0, 0.0, 0.98] # Solid black silhouette
                    
                    # Wing Left
                    line_pos.append([bp[0], bp[1], 0.0])
                    line_pos.append([bp[0] - span, bp[1] + flap, 0.0])
                    # Wing Right
                    line_pos.append([bp[0], bp[1], 0.0])
                    line_pos.append([bp[0] + span, bp[1] + flap, 0.0])
                    # Body/Head
                    line_pos.append([bp[0], bp[1] + 0.006, 0.0])
                    line_pos.append([bp[0], bp[1] - 0.008, 0.0])
                    for _ in range(6):
                        line_col.append(col)
            elif r['type'] == 'TUMBLEWEED':
                tx = r['x']
                ty = r['y']
                rad = r['radius']
                rot = r['rotation']
                col = [0.08, 0.05, 0.03, 0.90] # Twiggy dark brown branches
                
                # Render a highly detailed tangled branch ball
                num_loops = 10
                for i_loop in range(num_loops):
                    # Rotate each loop plane
                    loop_ang = i_loop * (np.pi / num_loops) + rot
                    c_l, s_l = np.cos(loop_ang), np.sin(loop_ang)
                    
                    segments = 6
                    # Vary radius slightly to create fuzzy/tangled twig density
                    loop_rad = rad * (0.85 + 0.25 * np.sin(i_loop * 4.3))
                    
                    p_prev = None
                    for j_seg in range(segments + 1):
                        a0 = j_seg * (2.0 * np.pi / segments)
                        # Add jagged offset to make the branches look twiggy and rough
                        jag_r = loop_rad * (1.0 + 0.12 * np.sin(j_seg * 5.7 + i_loop))
                        
                        p_local = np.array([jag_r * np.cos(a0), jag_r * 0.5 * np.sin(a0)])
                        p_rot = [p_local[0] * c_l - p_local[1] * s_l, p_local[0] * s_l + p_local[1] * c_l]
                        
                        if p_prev is not None:
                            line_pos.append([tx + p_prev[0], ty + p_prev[1], 0.0])
                            line_pos.append([tx + p_rot[0], ty + p_rot[1], 0.0])
                            line_col.append(col)
                            line_col.append(col)
                        p_prev = p_rot
                        
                # Draw 8 cross-cutting core branches for a beautifully tangled inner ball center
                for k in range(8):
                    ang_c = k * 1.7 + rot
                    pt0 = [tx + rad * 0.8 * np.cos(ang_c), ty + rad * 0.4 * np.sin(ang_c)]
                    pt1 = [tx - rad * 0.8 * np.cos(ang_c), ty - rad * 0.4 * np.sin(ang_c)]
                    line_pos.append([pt0[0], pt0[1], 0.0])
                    line_pos.append([pt1[0], pt1[1], 0.0])
                    line_col.append(col)
                    line_col.append(col)
                        
        # Draw massive, central fly-by Shooting Star trail inside Wormhole
        if self.major_mode == "TUNNEL Wormhole" and self.wormhole_shooting_star_active:
            # Create dynamic segment lines representing a trail behind the star
            head_z = self.wormhole_shooting_star_z
            for t_seg in range(12):
                z0 = head_z - t_seg * 1.5
                z1 = head_z - (t_seg + 1) * 1.5
                bx0, by0 = get_bend_offsets(z0)
                bx1, by1 = get_bend_offsets(z1)
                line_pos.append([self.wormhole_shooting_star_x + bx0, self.wormhole_shooting_star_y + by0 + 4.0, z0])
                line_pos.append([self.wormhole_shooting_star_x + bx1, self.wormhole_shooting_star_y + by1 + 4.0, z1])
                alpha = np.clip((1.0 - t_seg / 12.0) * ((z0 + 50.0)/50.0), 0.0, 1.0)
                line_col.append([0.15, 0.85, 1.0, alpha])
                line_col.append([0.15, 0.85, 1.0, alpha])
        
        # Draw Reference Ground Grid (unless in Underwater Mode)
        if self.major_mode != "UNDERWATER Lava":
            grid_y = -12.0
            grid_range = 30.0
            steps = 10
            for i in range(steps + 1):
                val = -grid_range + (2.0 * grid_range / steps) * i
                grid_alpha = 0.08 + self.react_bass * 0.15
                grid_col = (0.15, 0.15, 0.3 + self.react_bass * 0.4, grid_alpha)
                
                line_pos.append([val, grid_y, -grid_range])
                line_pos.append([val, grid_y, grid_range])
                line_col.append(grid_col)
                line_col.append(grid_col)
                
                line_pos.append([-grid_range, grid_y, val])
                line_pos.append([grid_range, grid_y, val])
                line_col.append(grid_col)
                line_col.append(grid_col)
            
        # Add Rocket Launch Trails to Line Buffer
        if self.show_rockets and self.major_mode == "FIREWORKS":
            for fw in self.fireworks:
                if fw.state == 'LAUNCH' and len(fw.launch_trail) > 1:
                    for idx in range(len(fw.launch_trail) - 1):
                        pt0 = fw.launch_trail[idx]
                        pt1 = fw.launch_trail[idx + 1]
                        alpha0 = idx / len(fw.launch_trail)
                        alpha1 = (idx + 1) / len(fw.launch_trail)
                        
                        line_pos.append(pt0)
                        line_pos.append(pt1)
                        line_col.append((1.0, 0.45, 0.1, alpha0 * 0.5))
                        line_col.append((1.0, 0.45, 0.1, alpha1 * 0.5))
                    
        if len(line_pos) > 0:
            line_pos_arr = np.array(line_pos, dtype=np.float32)
            line_col_arr = np.array(line_col, dtype=np.float32)
            
            gl.glUseProgram(self.line_program)
            gl.glUniformMatrix4fv(self.line_proj_loc, 1, gl.GL_TRUE, proj_matrix)
            gl.glUniformMatrix4fv(self.line_view_loc, 1, gl.GL_TRUE, view_matrix)
            if hasattr(self, 'line_fire_mode_loc') and self.line_fire_mode_loc != -1:
                gl.glUniform1i(self.line_fire_mode_loc, 1 if self.major_mode == "FIRE Plasma" else 0)
            
            gl.glBindVertexArray(self.line_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.line_pos_vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, line_pos_arr.nbytes, line_pos_arr, gl.GL_DYNAMIC_DRAW)
            
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.line_col_vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, line_col_arr.nbytes, line_col_arr, gl.GL_DYNAMIC_DRAW)
            
            gl.glLineWidth(1.0)
            gl.glDrawArrays(gl.GL_LINES, 0, len(line_pos_arr))
            gl.glBindVertexArray(0)
            
        # Restore additive blending for brilliant glowing particle stars and sparks!
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
        
        # 3. Gather, Buffer and Render All Points (Launcher Heads, Sparks and Particle Trails)
        part_pos = []
        part_col = []
        part_size = []
        
        if self.major_mode == "FIREWORKS":
            for fw in self.fireworks:
                if fw.state == 'LAUNCH':
                    if self.show_rockets:
                        part_pos.append(fw.launch_pos)
                        part_col.append((1.0, 0.8, 0.5, 1.0))
                        part_size.append(10.0)
                elif fw.state == 'EXPLODE' and fw.positions is not None:
                    num_pts = len(fw.positions)
                    if num_pts == 0:
                        continue
                    # Primary bright exploding stars
                    part_pos.append(fw.positions)
                    part_col.append(fw.colors)
                    part_size.append(np.full(num_pts, fw.star_size, dtype=np.float32))
                    
                    # Particle trails history step-down fading
                    if fw.history_len > 1 and fw.history is not None:
                        for h in range(fw.history_len):
                            trail_factor = 1.0 - (h / fw.history_len)
                            step_colors = fw.colors.copy()
                            step_colors[:, 3] *= trail_factor * 0.45
                            step_sizes = np.full(num_pts, max(1.0, (fw.star_size * 0.65) * trail_factor), dtype=np.float32)
                            
                            part_pos.append(fw.history[h])
                            part_col.append(step_colors)
                            part_size.append(step_sizes)
                            

            # Draw Catherine Wheel Nozzle sparks & Pinwheel
            if self.active_rarity is not None and self.active_rarity['type'] == 'CATHERINE_WHEEL':
                r = self.active_rarity
                # Removed central star at the middle completely!
                if len(r['sparks_pos']) > 0:
                    part_pos.append(r['sparks_pos'])
                    part_col.append(r['sparks_col'])
                    part_size.append(np.full(len(r['sparks_pos']), 4.5, dtype=np.float32))
        elif self.major_mode == "TUNNEL Wormhole":
            if not hasattr(self, 'gem_z'):
                self.init_tunnel_mode()
            t_pos, t_col, t_size, h_pos, h_col = self.render_tunnel()
            part_pos.append(t_pos)
            part_col.append(t_col)
            part_size.append(t_size)
        elif self.major_mode == "UNDERWATER Lava":
            if not hasattr(self, 'bubble_pos'):
                self.init_underwater_mode()
            u_pos, u_col, u_size, h_pos, h_col = self.render_underwater()
            part_pos.append(u_pos)
            part_col.append(u_col)
            part_size.append(u_size)
        elif self.major_mode == "MANDALA Sacred":
            if not hasattr(self, 'mandala_base_pos'):
                self.init_mandala_mode()
            m_pos, m_col, m_size, h_pos, h_col = self.render_mandala()
            part_pos.append(m_pos)
            part_col.append(m_col)
            part_size.append(m_size)
        elif self.major_mode == "SYNAESTHESIA Classic":
            if not hasattr(self, 'syn_stars'):
                self.init_synaesthesia_mode()
            s_pos, s_col, s_size, h_pos, h_col = self.render_synaesthesia()
            part_pos.append(s_pos)
            part_col.append(s_col)
            part_size.append(s_size)
        elif self.major_mode == "FIRE Plasma":
            if not hasattr(self, 'fire_spark_pos'):
                self.init_fire_mode()
            f_pos, f_col, f_size, h_pos, h_col = self.render_fire()
            part_pos.append(f_pos)
            part_col.append(f_col)
            part_size.append(f_size)
        else:
            h_pos = np.zeros((0, 3), dtype=np.float32)
            h_col = np.zeros((0, 4), dtype=np.float32)
                        
        if len(part_pos) > 0:
            try:
                norm_pos = []
                norm_col = []
                norm_size = []
                
                for p in part_pos:
                    p_arr = np.asarray(p, dtype=np.float32)
                    norm_pos.append(p_arr if p_arr.ndim == 2 else p_arr[np.newaxis, :])
                    
                for c in part_col:
                    c_arr = np.asarray(c, dtype=np.float32)
                    norm_col.append(c_arr if c_arr.ndim == 2 else c_arr[np.newaxis, :])
                    
                for s in part_size:
                    s_arr = np.asarray(s, dtype=np.float32)
                    norm_size.append(s_arr if s_arr.ndim == 1 else s_arr[np.newaxis])
                
                pos_arr = np.concatenate(norm_pos, axis=0).astype(np.float32)
                col_arr = np.concatenate(norm_col, axis=0).astype(np.float32)
                size_arr = np.concatenate(norm_size, axis=0).astype(np.float32)
                
                gl.glUseProgram(self.particle_program)
                gl.glUniformMatrix4fv(self.part_proj_loc, 1, gl.GL_TRUE, proj_matrix)
                gl.glUniformMatrix4fv(self.part_view_loc, 1, gl.GL_TRUE, view_matrix)
                gl.glUniform1i(self.part_star_shape_loc, self.opt_star_shape)
                if hasattr(self, 'part_fire_mode_loc') and self.part_fire_mode_loc != -1:
                    gl.glUniform1i(self.part_fire_mode_loc, 1 if self.major_mode == "FIRE Plasma" else 0)
                
                gl.glBindVertexArray(self.particle_vao)
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.particle_pos_vbo)
                gl.glBufferData(gl.GL_ARRAY_BUFFER, pos_arr.nbytes, pos_arr, gl.GL_DYNAMIC_DRAW)
                
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.particle_col_vbo)
                gl.glBufferData(gl.GL_ARRAY_BUFFER, col_arr.nbytes, col_arr, gl.GL_DYNAMIC_DRAW)
                
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.particle_size_vbo)
                gl.glBufferData(gl.GL_ARRAY_BUFFER, size_arr.nbytes, size_arr, gl.GL_DYNAMIC_DRAW)
                
                gl.glDrawArrays(gl.GL_POINTS, 0, len(pos_arr))
                gl.glBindVertexArray(0)
                
                # Draw Solid/Translucent 3D Meshes across ALL major visualizer modes
                if 'h_pos' in locals() and h_pos is not None and len(h_pos) > 0:
                    gl.glUseProgram(self.line_program)
                    gl.glUniformMatrix4fv(self.line_proj_loc, 1, gl.GL_TRUE, proj_matrix)
                    gl.glUniformMatrix4fv(self.line_view_loc, 1, gl.GL_TRUE, view_matrix)
                    
                    gl.glBindVertexArray(self.hood_vao)
                    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.hood_pos_vbo)
                    gl.glBufferData(gl.GL_ARRAY_BUFFER, h_pos.nbytes, h_pos, gl.GL_DYNAMIC_DRAW)
                    
                    gl.glBindVertexArray(self.hood_vao)
                    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.hood_col_vbo)
                    gl.glBufferData(gl.GL_ARRAY_BUFFER, h_col.nbytes, h_col, gl.GL_DYNAMIC_DRAW)
                    
                    gl.glDisable(gl.GL_CULL_FACE)
                    # Switch to matte standard alpha blending for solid meshes
                    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
                    gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(h_pos))
                    # Restore back to additive blending
                    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
                    gl.glBindVertexArray(0)
            except Exception as e:
                import traceback
                traceback.print_exc()
                
        if hasattr(self, 'is_recording') and self.is_recording and self.ffmpeg_process:
            self.capture_recording_frame(w_phys, h_phys)
            # Pump the default GLib MainContext to process keyboard, mouse, and resize events during fast recording loop
            while GLib.MainContext.default().iteration(False):
                pass
            # Schedule next frame draw with a tiny timeout to let GTK do layout/allocation
            GLib.timeout_add(1, self.gl_area.queue_draw)
                 
        return True

    def on_tick(self):
        if hasattr(self, 'is_recording') and self.is_recording:
            return True
            
        now = time.time()
        dt = now - self.last_time
        self.last_time = now
        dt = min(dt, 0.1)
        self.update_preset_random_timer(dt)
        
        # Recalculate moon phase every 12 hours (43200 seconds)
        self.last_moon_update_time += dt
        if self.last_moon_update_time >= 43200.0:
            self.last_moon_update_time = 0.0
            self.recalculate_moon_phase()
        
        # Decay envelopes
        decay_rate = 5.0
        self.react_bass = max(0.0, self.react_bass - decay_rate * dt)
        self.react_mid = max(0.0, self.react_mid - decay_rate * dt)
        self.react_treble = max(0.0, self.react_treble - decay_rate * dt)
        self.react_bass_smooth += (self.react_bass - self.react_bass_smooth) * dt * 3.5
        
        # Smoothly decay current panning towards center over time
        self.current_stereo_panning -= self.current_stereo_panning * dt * 1.5
        
        # Decay climax flash and advance tempo phase
        self.climax_flash = max(0.0, self.climax_flash - 2.0 * dt)
        self.tempo_phase += dt * (self.script_bpm / 60.0)
        
        # Update active timers and state variables
        if self.lightning_active_timer > 0.0:
            self.lightning_active_timer -= dt
            if self.lightning_active_timer <= 0.0:
                self.active_lightning_bolts = []
        if self.peace_symbol_timer > 0.0:
            self.peace_symbol_timer = max(0.0, self.peace_symbol_timer - dt)
        if self.halo_timer > 0.0:
            self.halo_timer = max(0.0, self.halo_timer - dt)
        
        # Check for implicit/proactive real-time climax peak (flash point)
        if self.music_playing and self.major_mode != "FIREWORKS":
            now_sec = time.time()
            if self.react_bass > 1.35 and (now_sec - self.last_climax_trigger_time > 8.0):
                self.last_climax_trigger_time = now_sec
                self.trigger_climax_event(intensity=1.2, routine_name="Beat Flashpoint")
        
        # Playback sync event handler
        elapsed = 0.0
        if self.music_playing:
            # Check if player has stopped or finished
            if not self.audio_player.is_playing():
                if self.playlist and len(self.playlist) > 0:
                    self.play_next_track()
                else:
                    self.stop_sync_playback()
            else:
                elapsed = self.audio_player.get_elapsed_time()
                if self.script_events and self.script_duration > 0 and elapsed >= self.script_duration:
                    if self.playlist and len(self.playlist) > 0:
                        self.play_next_track()
                    else:
                        self.stop_sync_playback()
                else:
                    while (self.next_event_idx < len(self.script_events) and 
                           self.script_events[self.next_event_idx]["time"] <= elapsed):
                        event = self.script_events[self.next_event_idx]
                        self.trigger_script_event(event)
                        self.next_event_idx += 1

        # Update scheduled routine queue
        if len(self.routine_queue) > 0:
            remaining_queue = []
            for delay, fw in self.routine_queue:
                delay -= dt
                if delay <= 0:
                    self.fireworks.append(fw)
                else:
                    remaining_queue.append((delay, fw))
            self.routine_queue = remaining_queue
            
        if self.active_routine_name:
            self.routine_timer -= dt
            if self.routine_timer <= 0:
                self.active_routine_name = ""
        
        measured_fps = 1.0 / dt if dt > 0 else 60.0
        self.fps = self.fps * self.fps_filter + measured_fps * (1.0 - self.fps_filter)
        
        if self.auto_rotate:
            self.camera_theta += 0.15 * dt
            if self.camera_theta > 2 * np.pi:
                self.camera_theta -= 2 * np.pi
                
        if self.auto_launch or (self.music_playing and not getattr(self, 'script_events', None)):
            self.launch_timer += dt
            if self.launch_timer >= self.next_launch_interval:
                self.launch_timer = 0.0
                self.next_launch_interval = random.uniform(0.6, 1.3)
                if self.major_mode == "FIREWORKS":
                    self.fireworks.append(Firework())
                else:
                    # Trigger beat-synced artificial reactive envelopes
                    r = random.random()
                    if r < 0.33:
                        self.react_bass = min(1.5, self.react_bass + 0.8)
                    elif r < 0.66:
                        self.react_mid = min(1.5, self.react_mid + 0.8)
                    else:
                        self.react_treble = min(1.5, self.react_treble + 0.8)
                        
        # Background pulse
        self.procedural_beat_timer += dt
        if self.procedural_beat_timer >= 60.0 / 120.0:
            self.procedural_beat_timer = 0.0
            if not self.music_playing:
                self.react_bass = min(1.5, self.react_bass + 0.4)
                
        if self.major_mode == "FIREWORKS":
            for fw in self.fireworks:
                fw.update(dt)
            self.fireworks = [fw for fw in self.fireworks if fw.state != 'DEAD']
        elif self.major_mode == "TUNNEL Wormhole":
            if not hasattr(self, 'gem_z'):
                self.init_tunnel_mode()
            self.update_tunnel(dt)
            if self.wormhole_supernova_active:
                self.wormhole_supernova_age += dt
                if self.wormhole_supernova_age > 3.5:
                    self.wormhole_supernova_active = False
            if self.wormhole_shooting_star_active:
                self.wormhole_shooting_star_z += dt * 45.0
                if self.wormhole_shooting_star_z > 10.0:
                    self.wormhole_shooting_star_active = False
        elif self.major_mode == "UNDERWATER Lava":
            if not hasattr(self, 'bubble_pos'):
                self.init_underwater_mode()
            self.update_underwater(dt)
        elif self.major_mode == "MANDALA Sacred":
            if not hasattr(self, 'mandala_base_pos'):
                self.init_mandala_mode()
            self.update_mandala(dt)
        elif self.major_mode == "SYNAESTHESIA Classic":
            if not hasattr(self, 'syn_stars'):
                self.init_synaesthesia_mode()
            self.update_synaesthesia(dt)
        elif self.major_mode == "FIRE Plasma":
            if not hasattr(self, 'fire_spark_pos'):
                self.init_fire_mode()
            self.update_fire(dt)
            
        self.update_rarity_system(dt)
        
        self.fps_lbl.set_text(f"FPS: {self.fps:.1f}")
        self.update_hud_labels()
        if self.active_routine_name:
            self.routine_lbl.set_text(f"Routine: {self.active_routine_name}")
        else:
            self.routine_lbl.set_text("Routine: None")
            
        if self.music_playing:
            if self.script_events:
                self.music_track_lbl.set_text(f"Track: {self.loaded_script_name} ({self.script_bpm:.1f} BPM)")
            else:
                self.music_track_lbl.set_text(f"Track: {os.path.basename(self.audio_path)} (Analyzing...)")
            m_sec = int(elapsed) % 60
            m_min = int(elapsed) // 60
            if self.script_duration > 0:
                total_sec = int(self.script_duration) % 60
                total_min = int(self.script_duration) // 60
                self.music_time_lbl.set_text(f"Time: {m_min:02d}:{m_sec:02d} / {total_min:02d}:{total_sec:02d}")
            else:
                self.music_time_lbl.set_text(f"Time: {m_min:02d}:{m_sec:02d} / --:--")
        else:
            if len(self.script_events) > 0:
                self.music_track_lbl.set_text(f"Track: {self.loaded_script_name} (Ready)")
            else:
                self.music_track_lbl.set_text("Track: None (Press M to generate)")
            self.music_time_lbl.set_text("Time: 00:00 / 00:00")
            
        active_stars = 0
        active_rockets = 0
        if self.major_mode == "FIREWORKS":
            active_stars = sum(len(fw.positions) for fw in self.fireworks if fw.positions is not None)
            active_rockets = sum(1 for fw in self.fireworks if fw.state == 'LAUNCH')
        elif self.major_mode == "TUNNEL Wormhole":
            active_stars = len(self.gem_z) + 20 + np.sum(self.spark_active) if hasattr(self, 'gem_z') else 0
        elif self.major_mode == "UNDERWATER Lava":
            active_stars = ((np.sum(self.bubble_active) if hasattr(self, 'bubble_active') else 0) + 
                            (len(self.algae_pos) if hasattr(self, 'algae_pos') else 0) + 
                            (self.num_vent_pts if hasattr(self, 'num_vent_pts') else 0) + 
                            (self.num_jelly * 46 if hasattr(self, 'num_jelly') else 0))
        elif self.major_mode == "MANDALA Sacred":
            active_stars = len(self.mandala_base_pos) * self.mandala_slices if hasattr(self, 'mandala_base_pos') else 0
        elif self.major_mode == "SYNAESTHESIA Classic":
            active_stars = len(self.syn_stars) * 20 + 300 if hasattr(self, 'syn_stars') else 0
        elif self.major_mode == "FIRE Plasma":
            active_stars = np.sum(self.fire_spark_active) if hasattr(self, 'fire_spark_active') else 0
            
        self.shell_lbl.set_text(f"Active Shells: {active_rockets}")
        self.part_lbl.set_text(f"Simulated Particles: {active_stars:,}")
        
        self.gl_area.queue_draw()
        return True

    def on_key_pressed(self, controller, keyval, keycode, state):
        is_control = (state & Gdk.ModifierType.CONTROL_MASK) != 0
        if is_control:
            if keyval in (Gdk.KEY_f, Gdk.KEY_F, Gdk.KEY_o, Gdk.KEY_O):
                self.show_file_chooser()
                return True
            return False

        unicode_val = Gdk.keyval_to_unicode(keyval)
        key_char = chr(unicode_val) if unicode_val > 0 else ""
        
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q, Gdk.KEY_Q):
            self.win.close()
            return True
        elif keyval in (Gdk.KEY_space, getattr(Gdk, 'KEY_AudioPlay', -1), getattr(Gdk, 'KEY_AudioPlayPause', -1)):
            self.toggle_sync_playback()
            return True
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.fireworks.append(Firework())
            return True
        elif key_char == '1':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("American Flag", self.launch_american_flag)
            elif self.major_mode == "SYNAESTHESIA Classic":
                self.syn_points_are_diamonds = not self.syn_points_are_diamonds
                self.opt_star_shape = 2 if self.syn_points_are_diamonds else 5
                print(f"Synaesthesia Shape changed. Diamonds: {self.syn_points_are_diamonds}")
                self.update_legend_labels()
            elif self.major_mode == "FIRE Plasma":
                self.trigger_climax_event(intensity=1.1, routine_name="Flame Flare")
            else:
                self.trigger_climax_event(intensity=1.1, routine_name="Coral Pulse" if self.major_mode == "UNDERWATER Lava" else "Lotus Bloom" if self.major_mode == "MANDALA Sacred" else "Plasma Burst")
            return True
        elif key_char == '2':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("Liberty Bell", self.launch_liberty_bell)
            elif self.major_mode == "SYNAESTHESIA Classic":
                sizes = [0.1, 0.25, 0.5, 0.75, 1.0]
                idx = sizes.index(self.syn_star_size) if self.syn_star_size in sizes else 2
                self.syn_star_size = sizes[(idx + 1) % len(sizes)]
                print(f"Synaesthesia Star Size: {self.syn_star_size}")
                self.update_legend_labels()
            elif self.major_mode == "FIRE Plasma":
                self.trigger_climax_event(intensity=1.2, routine_name="Flame Wave")
            else:
                self.trigger_climax_event(intensity=1.2, routine_name="Geyser Eruption" if self.major_mode == "UNDERWATER Lava" else "Cosmic Spin" if self.major_mode == "MANDALA Sacred" else "Gravity Surge")
            return True
        elif key_char == '3':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("Statue of Liberty", self.launch_statue_of_liberty)
            elif self.major_mode == "SYNAESTHESIA Classic":
                brights = [0.1, 0.25, 0.35, 0.5, 0.7, 1.0]
                idx = brights.index(self.syn_brightness) if self.syn_brightness in brights else 2
                self.syn_brightness = brights[(idx + 1) % len(brights)]
                print(f"Synaesthesia Brightness: {self.syn_brightness}")
                self.update_legend_labels()
            elif self.major_mode == "FIRE Plasma":
                self.trigger_climax_event(intensity=1.3, routine_name="Treble Spark Shower")
            else:
                self.trigger_climax_event(intensity=1.3, routine_name="Plankton Surge" if self.major_mode == "UNDERWATER Lava" else "Infinite Pulse" if self.major_mode == "MANDALA Sacred" else "Stardust Stream")
            return True
        elif key_char == '4':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("Flower Bouquet", self.launch_flower_bouquet)
            elif self.major_mode == "SYNAESTHESIA Classic":
                modes = ["Stars", "Wave", "Flame"]
                idx = modes.index(self.syn_fade_mode) if self.syn_fade_mode in modes else 0
                self.syn_fade_mode = modes[(idx + 1) % len(modes)]
                print(f"Synaesthesia Fade Mode: {self.syn_fade_mode}")
                self.update_legend_labels()
            elif self.major_mode == "FIRE Plasma":
                self.trigger_climax_event(intensity=1.4, routine_name="Fire Eruption")
            else:
                self.trigger_climax_event(intensity=1.4, routine_name="Deep Vent Blast" if self.major_mode == "UNDERWATER Lava" else "Geometric Collapse" if self.major_mode == "MANDALA Sacred" else "Event Horizon")
            return True
        elif key_char == '5':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("The Dragon", self.launch_the_dragon)
            elif self.major_mode == "SYNAESTHESIA Classic":
                self.trigger_syn_star_burst()
                self.update_legend_labels()
            elif self.major_mode == "FIRE Plasma":
                self.trigger_climax_event(intensity=1.8, routine_name="Lightning Strike")
            else:
                self.trigger_climax_event(intensity=1.8, routine_name="Bioluminescent Rainbow" if self.major_mode == "UNDERWATER Lava" else "Astral Projection" if self.major_mode == "MANDALA Sacred" else "Lightning Flash")
            return True
        elif key_char == '6':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("Supernova", self.launch_supernova)
            elif self.major_mode == "MANDALA Sacred":
                self.trigger_climax_event(intensity=1.6, routine_name="Peace Symbol")
            elif self.major_mode == "FIRE Plasma":
                pass
            else:
                self.trigger_climax_event(intensity=2.0, routine_name="Supernova")
            return True
        elif key_char == '7':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("Shooting Star", self.launch_shooting_star)
            elif self.major_mode == "MANDALA Sacred":
                self.trigger_climax_event(intensity=1.8, routine_name="Halo Effect")
            elif self.major_mode == "FIRE Plasma":
                pass
            else:
                self.trigger_climax_event(intensity=1.6, routine_name="Shooting Star")
            return True
        elif keyval in (Gdk.KEY_v, Gdk.KEY_V):
            next_idx = (self.preset_idx + 1) % len(self.active_presets)
            self.apply_preset(next_idx)
            return True
        elif keyval in (Gdk.KEY_y, Gdk.KEY_Y):
            self.opt_height_restrict = not self.opt_height_restrict
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_a, Gdk.KEY_A):
            self.auto_launch = not self.auto_launch
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_r, Gdk.KEY_R):
            self.auto_rotate = not self.auto_rotate
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_c, Gdk.KEY_C):
            self.fireworks.clear()
            return True
        elif keyval in (Gdk.KEY_m, Gdk.KEY_M):
            self.toggle_sync_playback()
            return True
        elif keyval in (Gdk.KEY_o, Gdk.KEY_O):
            modes = ['REALISTIC', 'NEON', 'TRANQUIL', 'METAL']
            idx = modes.index(self.opt_color_mode)
            self.opt_color_mode = modes[(idx + 1) % len(modes)]
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_p, Gdk.KEY_P):
            self.opt_star_shape = (self.opt_star_shape + 1) % 7
            if self.major_mode == "SYNAESTHESIA Classic":
                if self.opt_star_shape in (1, 2, 3):
                    self.syn_points_are_diamonds = True
                elif self.opt_star_shape in (4, 5, 6):
                    self.syn_points_are_diamonds = False
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_g, Gdk.KEY_G):
            gravs = [0.0, 0.5, 1.0, 2.0, 5.0, 10.0]
            idx = gravs.index(self.opt_gravity) if self.opt_gravity in gravs else 2
            self.opt_gravity = gravs[(idx + 1) % len(gravs)]
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_l, Gdk.KEY_L):
            self.opt_trailers = (self.opt_trailers + 1) % 11
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_t, Gdk.KEY_T):
            self.show_rockets = not self.show_rockets
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_s, Gdk.KEY_S):
            slices_options = [3, 4, 5, 6, 8, 12, 18, 24]
            idx = slices_options.index(self.mandala_slices) if self.mandala_slices in slices_options else 5
            self.mandala_slices = slices_options[(idx + 1) % len(slices_options)]
            print(f"Mandala Slices: {self.mandala_slices}")
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_u, Gdk.KEY_U):
            # Cycle flame algorithm when FIRE Plasma mode is active (method is supplied by FireModeMixin)
            if hasattr(self, 'cycle_flame_algorithm'):
                try:
                    self.cycle_flame_algorithm()
                except Exception as e:
                    print(f"Error cycling flame algorithm: {e}")
                self.update_legend_labels()
            return True
        elif keyval == Gdk.KEY_Left or keyval == getattr(Gdk, 'KEY_AudioPrev', -1):
            self.play_previous_track()
            return True
        elif keyval == Gdk.KEY_Right or keyval == getattr(Gdk, 'KEY_AudioNext', -1):
            self.play_next_track()
            return True
        elif keyval in (Gdk.KEY_h, Gdk.KEY_H):
            self.show_legend = not self.show_legend
            if hasattr(self, 'legend_box') and self.legend_box:
                self.legend_box.set_visible(self.show_legend)
            if hasattr(self, 'hud_box') and self.hud_box:
                self.hud_box.set_visible(self.show_legend)
            return True
        elif keyval in (Gdk.KEY_f, Gdk.KEY_F):
            if self.is_fullscreen:
                self.win.unfullscreen()
                self.is_fullscreen = False
            else:
                self.win.fullscreen()
                self.is_fullscreen = True
            return True
        elif keyval in (Gdk.KEY_k, Gdk.KEY_K):
            mode_rarities = {
                "UNDERWATER Lava": ["SQUID", "MANTA", "SEAHORSE", "LANTERN_FISH"],
                "TUNNEL Wormhole": ["PLANET", "GALAXY", "ASTEROIDS"],
                "FIREWORKS": ["CATHERINE_WHEEL"],
                "MANDALA Sacred": ["BIRD", "SMOKE", "SUN_BURST", "BUTTERFLY"],
                "FIRE Plasma": ["SHOOTING_STAR", "BATS", "TUMBLEWEED"]
            }
            if self.major_mode in mode_rarities:
                r_list = mode_rarities[self.major_mode]
                if not hasattr(self, 'mode_rarity_indices'):
                    self.mode_rarity_indices = {}
                
                # Retrieve last-spawned index for this major mode, defaulting to -1
                curr_idx = self.mode_rarity_indices.get(self.major_mode, -1)
                next_idx = (curr_idx + 1) % len(r_list)
                self.mode_rarity_indices[self.major_mode] = next_idx
                
                next_type = r_list[next_idx]
                print(f"Cycling current mode rarity to: {next_type} (index {next_idx})")
                self.active_rarity = None
                self.rarity_queued_type = None
                self.spawn_rarity(next_type)
                self.update_legend_labels()
            return True
        return False

    def on_drag_begin(self, gesture, x, y):
        self.drag_base_theta = self.camera_theta
        self.drag_base_phi = self.camera_phi

    def on_drag_update(self, gesture, offset_x, offset_y):
        self.camera_theta = self.drag_base_theta - offset_x * 0.007
        self.camera_phi = np.clip(self.drag_base_phi + offset_y * 0.007, 0.02, np.pi / 2.0 - 0.02)

    def on_scroll(self, controller, dx, dy):
        self.camera_dist = np.clip(self.camera_dist + dy * 1.5, 10.0, 80.0)
        return True

    def on_file_drop(self, target, value, x, y):
        if isinstance(value, Gdk.FileList):
            files = value.get_files()
            paths = []
            for f in files:
                path = f.get_path()
                if path:
                    paths.append(path)
            if paths:
                print(f"Drag & Drop files received: {paths}")
                self.playlist = self.load_playlist_files(paths)
                self.playlist_idx = 0
                if self.playlist:
                    self.audio_path = self.playlist[self.playlist_idx]
                    self.script_path = self.get_mangled_script_path(self.audio_path)
                    self.load_and_play_track()
                return True
        return False

    def show_file_chooser(self):
        dialog = Gtk.FileChooserNative.new(
            title="Open Audio File",
            parent=self.win,
            action=Gtk.FileChooserAction.OPEN,
            accept_label="_Open",
            cancel_label="_Cancel"
        )
        
        filter_audio = Gtk.FileFilter()
        filter_audio.set_name("Audio Files")
        filter_audio.add_mime_type("audio/*")
        for ext in ["mp3", "wav", "ogg", "opus", "flac", "m4a", "aac"]:
            filter_audio.add_pattern(f"*.{ext}")
            filter_audio.add_pattern(f"*.{ext.upper()}")
        dialog.add_filter(filter_audio)
        
        filter_m3u = Gtk.FileFilter()
        filter_m3u.set_name("Playlists (*.m3u)")
        filter_m3u.add_pattern("*.m3u")
        filter_m3u.add_pattern("*.M3U")
        dialog.add_filter(filter_m3u)
        
        filter_all = Gtk.FileFilter()
        filter_all.set_name("All Files")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                file_obj = dialog.get_file()
                if file_obj:
                    path = file_obj.get_path()
                    if path:
                        print(f"File dialog selected: {path}")
                        self.playlist = self.load_playlist_files([path])
                        self.playlist_idx = 0
                        if self.playlist:
                            self.audio_path = self.playlist[self.playlist_idx]
                            self.script_path = self.get_mangled_script_path(self.audio_path)
                            self.load_and_play_track()
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def on_right_click(self, gesture, n_press, x, y):
        # Create a Popover
        popover = Gtk.Popover()
        popover.set_parent(self.gl_area)
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        popover.set_has_arrow(False)
        
        # Build menu content
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        menu_box.set_margin_start(8)
        menu_box.set_margin_end(8)
        menu_box.set_margin_top(8)
        menu_box.set_margin_bottom(8)
        menu_box.add_css_class("hud-legend")
        
        # Helper to create buttons
        def make_menu_item(label, callback):
            btn = Gtk.Button(label=label)
            btn.set_has_frame(False)
            btn.set_halign(Gtk.Align.FILL)
            # Create a left-aligned label style inside the button
            child = btn.get_child()
            if isinstance(child, Gtk.Label):
                child.set_xalign(0.0)
            btn.connect("clicked", lambda b: (popover.popdown(), callback()))
            return btn
            
        # File Open
        menu_box.append(make_menu_item("📂 Open Audio...", self.show_file_chooser))
        
        # Play / Pause
        play_label = "⏸ Pause Sync" if self.music_playing else "▶ Play Sync"
        menu_box.append(make_menu_item(play_label, self.toggle_sync_playback))
        
        # Next / Prev Track
        menu_box.append(make_menu_item("⏭ Next Track", self.play_next_track))
        menu_box.append(make_menu_item("⏮ Previous Track", self.play_previous_track))
        
        # Separator
        sep1 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep1.set_margin_top(4)
        sep1.set_margin_bottom(4)
        menu_box.append(sep1)
        
        # Preset Mode list
        modes_label = Gtk.Label(label="VISUALIZATION MODES:")
        modes_label.add_css_class("hud-legend-title")
        modes_label.set_halign(Gtk.Align.START)
        modes_label.set_margin_start(4)
        menu_box.append(modes_label)
        
        # Add preset buttons
        for idx, preset in enumerate(self.active_presets):
            name = preset["name"]
            # Highlight current active preset
            active_marker = "● " if (idx == self.preset_idx and not getattr(self, 'preset_random_mode', False)) else "  "
            menu_box.append(make_menu_item(f"{active_marker}{name}", lambda i=idx: self.apply_preset(i)))
            
        # Random Mode button
        random_marker = "● " if getattr(self, 'preset_random_mode', False) else "  "
        menu_box.append(make_menu_item(f"{random_marker}Random Mode", lambda: self.apply_preset(len(self.active_presets) - 1)))
        
        # Separator
        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep2.set_margin_top(4)
        sep2.set_margin_bottom(4)
        menu_box.append(sep2)
        
        # Exit
        menu_box.append(make_menu_item("❌ Exit Screensaver", self.win.close))
        
        popover.set_child(menu_box)
        popover.popup()

    def load_sync_script(self, filepath):
        import audio_analyzer
        if os.path.exists(filepath):
            need_regenerate = False
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                ver = data.get("metadata", {}).get("analyzer_version", 0)
                if ver < audio_analyzer.ANALYZER_VERSION:
                    print(f"JSON file {filepath} is outdated (version {ver} < {audio_analyzer.ANALYZER_VERSION}). Deleting and re-analyzing...")
                    need_regenerate = True
            except Exception as e:
                print(f"Error reading JSON file {filepath} for version check: {e}. Deleting and re-analyzing...")
                need_regenerate = True
                
            if need_regenerate:
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"Failed to remove outdated JSON {filepath}: {e}")
                    
                if os.path.exists(self.audio_path):
                    print(f"Auto-regenerating up-to-date JSON for {self.audio_path}...")
                    try:
                        hints = getattr(self, 'color_hints', None) or ["strontium_red", "magnesium_white", "copper_blue"]
                        script = audio_analyzer.analyze_audio(self.audio_path, hints)
                        with open(filepath, 'w') as f:
                            json.dump(script, f, indent=2)
                        print(f"Regenerated {filepath} successfully.")
                    except Exception as e:
                        print(f"Failed to auto-generate JSON: {e}")
                else:
                    print(f"Cannot regenerate, audio file {self.audio_path} not found!")
                    
        try:
            with open(filepath, 'r') as f:
                script = json.load(f)
            self.script_events = script.get("events", [])
            
            # Post-process to find climax events eligible for random mode changes.
            # An eligible climax has no "section" event within 30 seconds after it.
            # "Just before" means 0.05 seconds before the climax.
            if self.script_events:
                new_events = list(self.script_events)
                climax_times = [ev["time"] for ev in self.script_events if ev.get("type") == "climax"]
                section_times = [ev["time"] for ev in self.script_events if ev.get("type") == "section"]
                
                for c_time in climax_times:
                    has_section_after = False
                    for s_time in section_times:
                        if c_time < s_time <= c_time + 30.0:
                            has_section_after = True
                            break
                    if not has_section_after:
                        trigger_time = max(0.0, c_time - 0.05)
                        new_events.append({
                            "time": trigger_time,
                            "type": "climax_random_mode_change",
                            "climax_time": c_time
                        })
                        print(f"[Random Mode Plan] Scheduled a random mode change at {trigger_time:.2f}s just before climax at {c_time:.2f}s (no section change within 30s after)")
                
                new_events.sort(key=lambda x: x.get("time", 0.0))
                self.script_events = new_events

            metadata = script.get("metadata", {})
            self.loaded_script_name = os.path.basename(filepath)
            self.script_duration = metadata.get("duration", 0.0)
            self.script_bpm = metadata.get("bpm", 120.0)
            self.current_key = "N/A"
            self.current_section_name = "None"
            self.current_section_category = "None"
            self.update_hud_labels()
            self.script_total_events = metadata.get("total_events", len(self.script_events))
            self.color_hints = metadata.get("color_hints", [])
            print(f"Loaded sync script {filepath} successfully. Events: {len(self.script_events)}")
            self.update_legend_labels()
            return True
        except Exception as e:
            print(f"Failed to load sync script {filepath}: {e}")
            return False

    def start_sync_playback(self):
        if not self.script_events:
            print("No synchronized script loaded!")
            return
            
        self.stop_sync_playback()
        
        music_file = self.audio_path
        if not os.path.exists(music_file):
            print(f"Could not find music file: {music_file}")
            return
            
        print(f"Starting synchronized playback for: {music_file}")
        self.saved_auto_launch = self.auto_launch
        self.auto_launch = False
        self.update_legend_labels()
        
        self.fireworks.clear()
        
        try:
            if self.audio_player.play(music_file):
                self.music_playing = True
                self.playback_start_time = time.time()
                self.next_event_idx = 0
                print("Audio player started successfully.")
            else:
                raise RuntimeError("UnifiedAudioPlayer failed to play track")
        except Exception as e:
            print(f"Failed to start audio playback: {e}")
            self.auto_launch = self.saved_auto_launch
            self.update_legend_labels()

    def stop_sync_playback(self):
        if self.music_playing:
            self.music_playing = False
            self.audio_player.stop()
            self.music_process = None
            
            self.auto_launch = self.saved_auto_launch
            self.update_legend_labels()
            self.current_key = "N/A"
            self.current_section_name = "None"
            self.current_section_category = "None"
            self.update_hud_labels()
            if hasattr(self, 'music_section_lbl') and self.music_section_lbl:
                self.music_section_lbl.set_text("Section: None")
            print("Synchronized playback stopped.")

    def toggle_sync_playback(self):
        if self.music_playing:
            self.stop_sync_playback()
        else:
            # If no script loaded, try auto-generating one
            if not self.script_events:
                print(f"No display script loaded. Attempting to auto-analyze {self.audio_path}...")
                if os.path.exists(self.audio_path):
                    try:
                        import audio_analyzer
                        script_data = audio_analyzer.analyze_audio(self.audio_path, ["strontium_red", "magnesium_white", "copper_blue"])
                        with open(self.script_path, 'w') as f:
                            json.dump(script_data, f, indent=2)
                        self.load_sync_script(self.script_path)
                    except Exception as e:
                        print(f"Failed auto-analysis: {e}")
                        return
                else:
                    print(f"Could not find {self.audio_path} in current directory!")
                    return
            self.start_sync_playback()

    def trigger_script_event(self, event):
        event_type = event.get("type")
        if event_type == "firework":
            fw_type = event.get("fw_type")
            color_key = event.get("color")
            sec_color_key = event.get("secondary_color")
            x_offset = event.get("x_offset", 0.0)
            self.current_stereo_panning = np.clip(x_offset / 6.0, -1.0, 1.0)
            
            color_rgb = COLORS.get(color_key, random.choice(COLOR_LIST))
            sec_color_rgb = COLORS.get(sec_color_key, random.choice(COLOR_LIST))
            
            # Sync visualizer reactive spikes to music event types
            if fw_type in [0, 2, 7, 8, 11, 12, 13]:
                self.react_bass = min(1.5, self.react_bass + 0.6)
            elif fw_type in [6, 14, 15, 17]:
                self.react_treble = min(1.5, self.react_treble + 0.6)
            else:
                self.react_mid = min(1.5, self.react_mid + 0.6)
            
            fw = Firework(fw_type=fw_type, color=color_rgb, x_offset=x_offset)
            fw.secondary_color = sec_color_rgb
            self.fireworks.append(fw)
            
        elif event_type == "routine":
            name = event.get("name")
            supported = SUPPORTED_ROUTINES.get(self.major_mode, [])
            if supported and name not in supported:
                old_name = name
                name = random.choice(supported)
                print(f"[Fallback] Routine '{old_name}' not supported in {self.major_mode}. Selected random fallback: '{name}'")
                
            if self.major_mode == "FIREWORKS":
                routines_map = {
                    "American Flag": self.launch_american_flag,
                    "Liberty Bell": self.launch_liberty_bell,
                    "Statue of Liberty": self.launch_statue_of_liberty,
                    "Flower Bouquet": self.launch_flower_bouquet,
                    "The Dragon": self.launch_the_dragon,
                    "Supernova": self.launch_supernova,
                    "Shooting Star": self.launch_shooting_star
                }
                if name in routines_map:
                    self.trigger_routine(name, routines_map[name])
            else:
                self.trigger_climax_event(intensity=1.5, routine_name=name)
                
        elif event_type == "climax":
            intensity = event.get("intensity", 1.5)
            if self.major_mode != "FIREWORKS":
                self.trigger_climax_event(intensity=intensity, routine_name="Climax Burst!")
                
        elif event_type == "key_change":
            key_name = event.get("key", "Unknown")
            self.current_key = key_name
            self.react_mid = min(1.5, self.react_mid + 0.6)
            self.react_treble = min(1.5, self.react_treble + 0.5)
            if hasattr(self, 'music_section_lbl') and self.music_section_lbl:
                self.music_section_lbl.set_text(f"Key Shift: {key_name}")
                
        elif event_type == "dynamics":
            direction = event.get("direction", "none")
            if direction == "crescendo":
                self.react_bass = min(1.4, self.react_bass + 0.3)
                self.react_mid = min(1.4, self.react_mid + 0.3)
                self.procedural_beat_timer = 0.0
                
        elif event_type == "section":
            name = event.get("name", "Unknown")
            category = event.get("category", "Unknown")
            self.current_section_name = name
            self.current_section_category = category
            if hasattr(self, 'music_section_lbl') and self.music_section_lbl:
                self.music_section_lbl.set_text(f"Section: {name}")
            if getattr(self, 'preset_random_mode', False) and getattr(self, 'preset_random_timer', 0.0) >= 45.0:
                print(f"[Random Mode] Triggering preset switch at start of section: {name}")
                self.pick_random_preset()
                
        elif event_type == "climax_random_mode_change":
            if getattr(self, 'preset_random_mode', False):
                climax_time = event.get("climax_time", 0.0)
                print(f"[Random Mode] Triggering preset switch just before climax at {climax_time:.2f}s (trigger time: {event.get('time', 0.0):.2f}s)")
                self.pick_random_preset()

    def start_recording_process(self, w, h):
        if w % 2 != 0:
            w = (w // 2) * 2
        if h % 2 != 0:
            h = (h // 2) * 2
            
        print(f"\nStarting offline H.264 recording of fireworks performance...")
        print(f"Target file: {self.record_path}")
        print(f"Resolution: {w}x{h} @ {self.record_fps} FPS")
        
        import audio_analyzer
        ffmpeg_bin = audio_analyzer.find_ffmpeg_binary()
        if not ffmpeg_bin:
            print("ERROR: FFmpeg binary not found on this system. Recording is not supported on this platform without FFmpeg.")
            self.is_recording = False
            return
            
        cmd = [
            ffmpeg_bin, '-y',
            '-f', 'rawvideo', '-vcodec', 'rawvideo',
            '-s', f'{w}x{h}', '-pix_fmt', 'rgba', '-r', str(self.record_fps),
            '-i', '-',
            '-vf', 'vflip',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'ultrafast',
            self.temp_video_path
        ]
        
        try:
            creationflags = 0x08000000 if sys.platform == 'win32' else 0
            self.ffmpeg_process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=creationflags)
            print("Successfully opened FFmpeg libx264 encoding process pipe.")
            self.auto_launch = False
            self.auto_rotate = False
            self.playback_start_time = 0.0
            self.record_time = 0.0
            self.next_event_idx = 0
            self.fireworks.clear()
            self.routine_queue.clear()
            
            # Start real-time music audio playback for live monitoring during recording
            music_file = self.audio_path
            if os.path.exists(music_file):
                try:
                    if self.audio_player.play(music_file):
                        self.music_playing = True
                        print(f"Started real-time music audio playback ({music_file}) for live monitoring.")
                    else:
                        raise RuntimeError("UnifiedAudioPlayer failed to start playback")
                except Exception as ex:
                    print(f"Failed to start live audio playback: {ex}")
        except Exception as e:
            print(f"Failed to start recording FFmpeg process: {e}")
            self.is_recording = False

    def on_recording_tick(self):
        dt = self.record_dt
        self.update_preset_random_timer(dt)
        elapsed = self.record_time
        
        # Decay envelopes in recording
        decay_rate = 5.0
        self.react_bass = max(0.0, self.react_bass - decay_rate * dt)
        self.react_mid = max(0.0, self.react_mid - decay_rate * dt)
        self.react_treble = max(0.0, self.react_treble - decay_rate * dt)
        self.react_bass_smooth += (self.react_bass - self.react_bass_smooth) * dt * 3.5
        
        # Decay climax flash and advance tempo phase in recording
        self.climax_flash = max(0.0, self.climax_flash - 2.0 * dt)
        self.tempo_phase += dt * (self.script_bpm / 60.0)
        
        # Check for implicit/proactive climax in offline recording
        if self.major_mode != "FIREWORKS":
            if self.react_bass > 1.35 and (elapsed - self.last_climax_trigger_time > 8.0):
                self.last_climax_trigger_time = elapsed
                self.trigger_climax_event(intensity=1.2, routine_name="Beat Flashpoint")
        
        if elapsed >= self.script_duration:
            self.finish_recording()
            return
            
        while (self.next_event_idx < len(self.script_events) and 
               self.script_events[self.next_event_idx]["time"] <= elapsed):
            event = self.script_events[self.next_event_idx]
            self.trigger_script_event(event)
            self.next_event_idx += 1
            
        # Update scheduled routine queue
        if len(self.routine_queue) > 0:
            remaining_queue = []
            for delay, fw in self.routine_queue:
                delay -= dt
                if delay <= 0:
                    self.fireworks.append(fw)
                else:
                    remaining_queue.append((delay, fw))
            self.routine_queue = remaining_queue
            
        if self.active_routine_name:
            self.routine_timer -= dt
            if self.routine_timer <= 0:
                self.active_routine_name = ""

        self.record_time += dt
        
        if self.auto_rotate:
            self.camera_theta += 0.15 * dt
            if self.camera_theta > 2 * np.pi:
                self.camera_theta -= 2 * np.pi
                
        if self.major_mode == "FIREWORKS":
            for fw in self.fireworks:
                fw.update(dt)
            self.fireworks = [fw for fw in self.fireworks if fw.state != 'DEAD']
        elif self.major_mode == "TUNNEL Wormhole":
            if not hasattr(self, 'gem_z'):
                self.init_tunnel_mode()
            self.update_tunnel(dt)
        elif self.major_mode == "UNDERWATER Lava":
            if not hasattr(self, 'bubble_pos'):
                self.init_underwater_mode()
            self.update_underwater(dt)
        elif self.major_mode == "MANDALA Sacred":
            if not hasattr(self, 'mandala_base_pos'):
                self.init_mandala_mode()
            self.update_mandala(dt)
        elif self.major_mode == "SYNAESTHESIA Classic":
            if not hasattr(self, 'syn_stars'):
                self.init_synaesthesia_mode()
            self.update_synaesthesia(dt)
        elif self.major_mode == "FIRE Plasma":
            if not hasattr(self, 'fire_spark_pos'):
                self.init_fire_mode()
            self.update_fire(dt)

        self.fps_lbl.set_text(f"FPS: RECORDING ({self.record_fps} FPS)")
        self.update_hud_labels()
        if self.active_routine_name:
            self.routine_lbl.set_text(f"Routine: {self.active_routine_name}")
        else:
            self.routine_lbl.set_text("Routine: None")
            
        self.music_track_lbl.set_text(f"Recording: {self.loaded_script_name}")
        m_sec = int(elapsed) % 60
        m_min = int(elapsed) // 60
        total_sec = int(self.script_duration) % 60
        total_min = int(self.script_duration) // 60
        self.music_time_lbl.set_text(f"Time: {m_min:02d}:{m_sec:02d} / {total_min:02d}:{total_sec:02d}")
        
        if self.major_mode == "FIREWORKS":
            active_stars = sum(len(fw.positions) for fw in self.fireworks if fw.positions is not None)
            active_rockets = sum(1 for fw in self.fireworks if fw.state == 'LAUNCH')
        elif self.major_mode == "TUNNEL Wormhole":
            active_stars = len(self.gem_z) + 100 + np.sum(self.spark_active) if hasattr(self, 'gem_z') else 0
            active_rockets = 0
        elif self.major_mode == "UNDERWATER Lava":
            active_stars = ((np.sum(self.bubble_active) if hasattr(self, 'bubble_active') else 0) + 
                            (len(self.algae_pos) if hasattr(self, 'algae_pos') else 0) + 
                            (self.num_vent_pts if hasattr(self, 'num_vent_pts') else 0) + 
                            (self.num_jelly * 46 if hasattr(self, 'num_jelly') else 0))
            active_rockets = 0
        elif self.major_mode == "MANDALA Sacred":
            active_stars = len(self.mandala_base_pos) * self.mandala_slices if hasattr(self, 'mandala_base_pos') else 0
            active_rockets = 0
        elif self.major_mode == "SYNAESTHESIA Classic":
            active_stars = len(self.syn_stars) * 20 + 300 if hasattr(self, 'syn_stars') else 0
            active_rockets = 0
        elif self.major_mode == "FIRE Plasma":
            active_stars = np.sum(self.fire_spark_active) if hasattr(self, 'fire_spark_active') else 0
            active_rockets = 0
            
        self.shell_lbl.set_text(f"Active Shells: {active_rockets}")
        self.part_lbl.set_text(f"Simulated Particles: {active_stars:,}")

    def capture_recording_frame(self, w, h):
        try:
            # Query GTK's offscreen draw framebuffer and bind it as the active read target
            fb = gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, fb)
            
            if fb > 0:
                gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0)
            else:
                gl.glReadBuffer(gl.GL_BACK)
                
            gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
            pixels = gl.glReadPixels(0, 0, w, h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            
            self.ffmpeg_process.stdin.write(pixels)
            
            if int(self.record_time * self.record_fps) % (self.record_fps * 5) == 0:
                print(f"Recorded frame: {self.record_time:.2f}s / {self.script_duration:.2f}s...")
        except Exception as e:
            print(f"Recording frame capture failed: {e}")
            self.is_recording = False
            if self.ffmpeg_process:
                self.ffmpeg_process.stdin.close()
                self.ffmpeg_process.wait()
                self.ffmpeg_process = None

    def finish_recording(self, close_window=True):
        if not self.is_recording:
            return
            
        self.is_recording = False
        print("\nFireworks offline recording render complete!")
        
        if self.ffmpeg_process:
            print("Closing video encoding pipe...")
            self.ffmpeg_process.stdin.close()
            self.ffmpeg_process.wait()
            self.ffmpeg_process = None
            
        music_file = self.audio_path
        if os.path.exists(music_file):
            print(f"Multiplexing audio track '{music_file}' into output file '{self.record_path}' using copy/copy stream mapping...")
            
            import audio_analyzer
            ffmpeg_bin = audio_analyzer.find_ffmpeg_binary() or "ffmpeg"
            
            cmd = [
                ffmpeg_bin, '-y',
                '-i', self.temp_video_path,
                '-i', music_file,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-shortest',
                self.record_path
            ]
            
            try:
                creationflags = 0x08000000 if sys.platform == 'win32' else 0
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags)
                stdout, stderr = p.communicate()
                if p.returncode == 0:
                    print(f"\nSuccessfully generated finalized H.264 MP4 movie with audio at: {self.record_path}")
                else:
                    err = stderr.decode('utf-8', errors='ignore')[-300:]
                    print(f"Error multiplexing audio: {err}")
            except Exception as e:
                print(f"Failed to run multiplexer subprocess: {e}")
        else:
            print(f"Warning: Audio file '{music_file}' not found. Leaving silent video at '{self.temp_video_path}'.")
            os.rename(self.temp_video_path, self.record_path)
            print(f"Renamed silent video to: {self.record_path}")
            
        if os.path.exists(self.temp_video_path):
            try:
                os.remove(self.temp_video_path)
            except Exception:
                pass
                
        if close_window:
            self.win.close()

    def on_close_request(self, win):
        self.stop_sync_playback()
        if self.is_recording:
            self.finish_recording(close_window=False)
            return True
        return False





















            

            









