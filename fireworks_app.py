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
from modes.fireworks_classic import FireworksClassicMixin
from presets_mixin import PresetMixin
from recording import RecordingMixin

class FireworksApp(TunnelModeMixin, UnderwaterModeMixin, MandalaModeMixin, SynaesthesiaModeMixin, FireModeMixin,
                    FireworksClassicMixin, PresetMixin, RecordingMixin):
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
        # Genuine persistent CPU-side EMA smoothing for mid/treble, mirroring the existing
        # react_bass_smooth (which was already proven to work reliably). Previously only bass
        # had this real smoothing while mid/treble were fed raw into the shader, contributing to
        # uneven/jarring behavior between the three bands in the Multi flame mode.
        self.react_mid_smooth = 0.0
        self.react_treble_smooth = 0.0
        
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

        # --- New state for smooth flame height ---
        self._prev_react_bass = 0.0
        self._prev_react_mid = 0.0
        self._prev_react_treble = 0.0

        # Persistent peak-hold/slow-release envelope followers for the Multi flame mode's
        # organic height pulsing. Unlike the CPU->shader uPrev/uCurrent single-frame blend
        # above (which has no real memory beyond one frame), these carry true state across
        # every frame: they rise quickly toward the current reactive level but ease back down
        # slowly, so the flame's height limit reflects recent music energy organically instead
        # of jumping instantly to match every sample.
        self._flame_pulse_bass = 0.0
        self._flame_pulse_mid = 0.0
        self._flame_pulse_treble = 0.0

        # DIAGNOSTIC: throttled console printout of the real bass/mid/treble reactive values so
        # we can directly verify whether genuine per-band differentiation exists at the source
        # (before it ever reaches the shader). If these three numbers stay nearly identical to
        # each other throughout playback, the problem is upstream in the audio-event pipeline,
        # not the shader math.
        self._debug_print_timer = 0.0

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

    def _update_flame_envelope(self, current, target, dt, attack_rate, decay_rate):
        # Asymmetric exponential envelope follower: rises quickly toward `target` when it's
        # above `current` (attack), but eases back down slowly when `target` drops below
        # `current` (decay/release). This gives genuine multi-frame memory, producing an
        # organic "ceiling that slowly relaxes" rather than an instantaneous jump.
        rate = attack_rate if target > current else decay_rate
        factor = 1.0 - math.exp(-rate * dt)
        return current + (target - current) * factor

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
        
        # Boost visualizer envelopes aggressively, but preserve/reinforce whatever bass/mid/
        # treble balance already exists instead of flattening it to an equal split. An equal
        # boost here was actively erasing the Multi flame mode's left=bass/right=treble
        # differentiation every time a climax (or the "Beat Flashpoint" auto-trigger) fired.
        total_react = self.react_bass + self.react_mid + self.react_treble + 1e-4
        bass_share = self.react_bass / total_react
        mid_share = self.react_mid / total_react
        treble_share = self.react_treble / total_react
        self.react_bass = min(1.8, self.react_bass + 1.2 * (0.4 + 0.8 * bass_share))
        self.react_mid = min(1.8, self.react_mid + 1.2 * (0.4 + 0.8 * mid_share))
        self.react_treble = min(1.8, self.react_treble + 1.2 * (0.4 + 0.8 * treble_share))
        
        if self.major_mode == "UNDERWATER Lava":
            self.trigger_climax_underwater(routine_name)
        elif self.major_mode == "TUNNEL Wormhole":
            self.trigger_climax_tunnel(routine_name)
        elif self.major_mode == "MANDALA Sacred":
            self.trigger_climax_mandala(routine_name)
        elif self.major_mode == "SYNAESTHESIA Classic":
            self.trigger_syn_star_burst()
        elif self.major_mode == "FIRE Plasma":
            self.trigger_climax_fire(routine_name)

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
            self.spawn_rarity_fireworks(r_type)
        elif r_type in ("BIRD", "SMOKE", "SUN_BURST", "BUTTERFLY"):
            self.spawn_rarity_mandala(r_type)
        elif r_type in ("SHOOTING_STAR", "BATS", "TUMBLEWEED"):
            self.spawn_rarity_fire(r_type)

    def update_active_rarity(self, dt):
        r = self.active_rarity
        r['life'] -= dt
        if r['life'] <= 0.0:
            self.active_rarity = None
            return
        t_type = r['type']
        if t_type in ("SQUID", "MANTA", "SEAHORSE", "LANTERN_FISH"):
            self.update_rarity_underwater(r, dt)
        elif t_type in ("PLANET", "GALAXY", "ASTEROIDS"):
            self.update_rarity_tunnel(r, dt)
        elif t_type == "CATHERINE_WHEEL":
            self.update_rarity_fireworks(r, dt)
        elif t_type in ("BIRD", "SMOKE", "SUN_BURST", "BUTTERFLY"):
            self.update_rarity_mandala(r, dt)
        elif t_type in ("SHOOTING_STAR", "BATS", "TUMBLEWEED"):
            self.update_rarity_fire(r, dt)

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

        # --- New uniform locations for smooth flame height ---
        self.sky_prev_react_bass_loc = gl.glGetUniformLocation(self.sky_program, "uPrevReactBass")
        self.sky_prev_react_mid_loc = gl.glGetUniformLocation(self.sky_program, "uPrevReactMid")
        self.sky_prev_react_treble_loc = gl.glGetUniformLocation(self.sky_program, "uPrevReactTreble")
        self.sky_delta_time_loc = gl.glGetUniformLocation(self.sky_program, "uDeltaTime")
        self.sky_flame_env_bass_loc = gl.glGetUniformLocation(self.sky_program, "uFlameEnvBass")
        self.sky_flame_env_mid_loc = gl.glGetUniformLocation(self.sky_program, "uFlameEnvMid")
        self.sky_flame_env_treble_loc = gl.glGetUniformLocation(self.sky_program, "uFlameEnvTreble")

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
                gl.glUniform1f(self.sky_react_treble_loc, self.react_treble_smooth)
            if hasattr(self, 'sky_react_mid_loc') and self.sky_react_mid_loc != -1:
                gl.glUniform1f(self.sky_react_mid_loc, self.react_mid_smooth)
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
            # IMPORTANT: this must NOT be nested inside the uColorMode check above — it was
            # previously conditioned on an unrelated uniform, meaning uFlameAlgorithm could
            # silently fail to be set (defaulting to 0.0 / Algorithm "Current") if that other
            # check ever failed, which would explain the Multi mode's per-flame bass/mid/treble
            # differentiation never being visible at all.
            if hasattr(self, 'sky_flame_algo_loc') and self.sky_flame_algo_loc != -1:
                gl.glUniform1f(self.sky_flame_algo_loc, float(self.fire_flame_algorithm))

            # --- Set smooth flame height uniforms ---
            if hasattr(self, 'sky_prev_react_bass_loc') and self.sky_prev_react_bass_loc != -1:
                gl.glUniform1f(self.sky_prev_react_bass_loc, self._prev_react_bass)
            if hasattr(self, 'sky_prev_react_mid_loc') and self.sky_prev_react_mid_loc != -1:
                gl.glUniform1f(self.sky_prev_react_mid_loc, self._prev_react_mid)
            if hasattr(self, 'sky_prev_react_treble_loc') and self.sky_prev_react_treble_loc != -1:
                gl.glUniform1f(self.sky_prev_react_treble_loc, self._prev_react_treble)

            # Compute dt for this render frame (used both for the shader's uDeltaTime uniform
            # and for the Multi flame mode's true persistent envelope follower below).
            now = time.time()
            render_dt = now - self.last_time
            self.last_time = now
            render_dt = min(render_dt, 0.1)
            if hasattr(self, 'sky_delta_time_loc') and self.sky_delta_time_loc != -1:
                gl.glUniform1f(self.sky_delta_time_loc, render_dt)

            # --- Multi flame mode: persistent peak-hold/slow-release envelope follower ---
            # This maintains real state across frames on the CPU (unlike the uPrev/uCurrent
            # shader blend above, which only ever has one frame of memory): it rises fairly
            # quickly toward the current reactive level, then eases back down slowly, so the
            # flames' height limit organically reflects recent music energy instead of jumping
            # to match every instantaneous sample.
            # Split the difference: attack fast enough that hits register clearly, decay slow
            # enough that it still reads as an organic sway rather than a jarring snap.
            self._flame_pulse_bass = self._update_flame_envelope(self._flame_pulse_bass, self.react_bass, render_dt, attack_rate=3.6, decay_rate=0.65)
            self._flame_pulse_mid = self._update_flame_envelope(self._flame_pulse_mid, self.react_mid, render_dt, attack_rate=3.6, decay_rate=0.65)
            self._flame_pulse_treble = self._update_flame_envelope(self._flame_pulse_treble, self.react_treble, render_dt, attack_rate=3.6, decay_rate=0.65)
            if hasattr(self, 'sky_flame_env_bass_loc') and self.sky_flame_env_bass_loc != -1:
                gl.glUniform1f(self.sky_flame_env_bass_loc, self._flame_pulse_bass)
            if hasattr(self, 'sky_flame_env_mid_loc') and self.sky_flame_env_mid_loc != -1:
                gl.glUniform1f(self.sky_flame_env_mid_loc, self._flame_pulse_mid)
            if hasattr(self, 'sky_flame_env_treble_loc') and self.sky_flame_env_treble_loc != -1:
                gl.glUniform1f(self.sky_flame_env_treble_loc, self._flame_pulse_treble)

            # Update previous values for next frame. IMPORTANT: use the already-smoothed CPU
            # EMA values (react_bass_smooth/mid/treble), not the raw, spiky react_bass/mid/
            # treble. Previously this mismatch (smoothed uReactBass vs raw uPrevReactBass) meant
            # the shader's own blend below could snap toward a stale instantaneous spike value
            # for a frame, actively contributing to the jarring, in-time-with-the-beat jumpiness.
            self._prev_react_bass = self.react_bass_smooth
            self._prev_react_mid = self.react_mid_smooth
            self._prev_react_treble = self.react_treble_smooth

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
        # Restored partway from 1.6: combined with the shader's own smoothing blend below,
        # 1.6 here was stacking two independent slow low-pass filters, which blurred out almost
        # all of the actual bass/mid/treble differences before they ever reached the shader.
        self.react_bass_smooth += (self.react_bass - self.react_bass_smooth) * dt * 2.6
        self.react_mid_smooth += (self.react_mid - self.react_mid_smooth) * dt * 2.6
        self.react_treble_smooth += (self.react_treble - self.react_treble_smooth) * dt * 2.6

        # DIAGNOSTIC: print real reactive values once per second while a track plays in FIRE
        # Plasma mode. Watch this in the console during a track with strong, distinct bass/
        # treble moments (e.g. a bass drum hit vs. a cymbal crash) — bass/mid/treble below
        # should visibly diverge from each other at those moments. If they never diverge, the
        # per-band audio event pipeline (not the shader) is the real problem.
        self._debug_print_timer += dt
        if self._debug_print_timer >= 1.0:
            self._debug_print_timer = 0.0
            if self.music_playing and self.major_mode == "FIRE Plasma":
                print(f"[DEBUG Multi Flame] smoothed: bass={self.react_bass_smooth:.3f} mid={self.react_mid_smooth:.3f} treble={self.react_treble_smooth:.3f}  |  raw: bass={self.react_bass:.3f} mid={self.react_mid:.3f} treble={self.react_treble:.3f}  |  script_events={len(self.script_events)}")
        
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
            
            # Sync visualizer reactive spikes to music event types. Prefer the CATEGORICAL
            # band_type ("bass"/"mid"/"treble") that comes directly from which peak-detector
            # actually fired this event: a genuine bass-drum hit should overwhelmingly boost
            # react_bass, a cymbal/hi-hat hit should overwhelmingly boost react_treble, etc.
            # This is far more perceptible than the continuous per-frame spectral ratio
            # (band_bass/mid/treble), which stays close to an even 33/33/33 split during a
            # dense full-band mix (kick+bass+vocals+cymbals all present simultaneously) and so
            # produced an imperceptible left/center/right differentiation in the Multi flame mode.
            total_boost = 1.3
            band_type = event.get("band_type")
            band_bass = event.get("band_bass")
            band_mid = event.get("band_mid")
            band_treble = event.get("band_treble")
            if band_type == "bass":
                self.react_bass = min(1.5, self.react_bass + total_boost * 0.85)
                self.react_mid = min(1.5, self.react_mid + total_boost * 0.10)
                self.react_treble = min(1.5, self.react_treble + total_boost * 0.05)
            elif band_type == "mid":
                self.react_bass = min(1.5, self.react_bass + total_boost * 0.10)
                self.react_mid = min(1.5, self.react_mid + total_boost * 0.80)
                self.react_treble = min(1.5, self.react_treble + total_boost * 0.10)
            elif band_type == "treble":
                self.react_bass = min(1.5, self.react_bass + total_boost * 0.05)
                self.react_mid = min(1.5, self.react_mid + total_boost * 0.10)
                self.react_treble = min(1.5, self.react_treble + total_boost * 0.85)
            elif band_bass is not None and band_mid is not None and band_treble is not None:
                self.react_bass = min(1.5, self.react_bass + total_boost * band_bass)
                self.react_mid = min(1.5, self.react_mid + total_boost * band_mid)
                self.react_treble = min(1.5, self.react_treble + total_boost * band_treble)
            elif fw_type in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]:
                self.react_bass = min(1.5, self.react_bass + 0.6)
                self.react_mid = min(1.5, self.react_mid + 0.4)
                self.react_treble = min(1.5, self.react_treble + 0.3)
            
            fw = Firework(fw_type=fw_type, color=color_rgb, x_offset=x_offset)
            fw.secondary_color = sec_color_rgb
            self.fireworks.append(fw)
            
        elif event_type == "climax":
            intensity = event.get("intensity", 1.5)
            self.trigger_climax_event(intensity=intensity, routine_name="Climax Burst!")
            
        elif event_type == "climax_random_mode_change":
            if getattr(self, 'preset_random_mode', False):
                self.pick_random_preset()
                print(f"[Random Mode] Random preset change triggered by climax at {event.get('climax_time', 0.0):.2f}s")
                
        elif event_type == "section":
            self.current_section_name = event.get("name", "None")
            self.current_section_category = event.get("category", "None")
            self.update_hud_labels()
            if hasattr(self, 'music_section_lbl') and self.music_section_lbl:
                self.music_section_lbl.set_text(f"Section: {self.current_section_name} ({self.current_section_category})")
                
        elif event_type == "key":
            self.current_key = event.get("key", "N/A")
            self.update_hud_labels()
            
        elif event_type == "bpm":
            self.script_bpm = event.get("bpm", 120.0)
            self.update_hud_labels()
            
        elif event_type == "color_hint":
            hint = event.get("hint", "")
            if hint:
                self.color_hints.append(hint)
                
        elif event_type == "routine":
            routine_name = event.get("name", "")
            if routine_name == "American Flag":
                self.trigger_routine("American Flag", self.launch_american_flag)
            elif routine_name == "Liberty Bell":
                self.trigger_routine("Liberty Bell", self.launch_liberty_bell)
            elif routine_name == "Statue of Liberty":
                self.trigger_routine("Statue of Liberty", self.launch_statue_of_liberty)
            elif routine_name == "Flower Bouquet":
                self.trigger_routine("Flower Bouquet", self.launch_flower_bouquet)
            elif routine_name == "The Dragon":
                self.trigger_routine("The Dragon", self.launch_the_dragon)
            elif routine_name == "Supernova":
                self.trigger_routine("Supernova", self.launch_supernova)
            elif routine_name == "Shooting Star":
                self.trigger_routine("Shooting Star", self.launch_shooting_star)
            else:
                print(f"Unknown routine: {routine_name}")

    def on_close_request(self, window):
        self.stop_sync_playback()
        return False
