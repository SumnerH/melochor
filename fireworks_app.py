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
    FireModeMixin,
    SpaceInvadersModeMixin,
    PondModeMixin
)
from modes.fireworks_classic import FireworksClassicMixin
from presets_mixin import PresetMixin
from recording import RecordingMixin
from playlist import PlaylistMixin
from ui import UIMixin
from input_handler import InputHandlerMixin

class FireworksApp(TunnelModeMixin, UnderwaterModeMixin, MandalaModeMixin, SynaesthesiaModeMixin, FireModeMixin,
                    SpaceInvadersModeMixin, PondModeMixin, FireworksClassicMixin, PresetMixin, RecordingMixin, PlaylistMixin,
                    UIMixin, InputHandlerMixin):
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
        self.opt_particle_reactivity = 0  # 0: off, 1..10: beat-driven particle pulsing
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
        self.mode_routine_indices = {}
        
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
        self.modes = ["FIREWORKS", "TUNNEL Wormhole", "MANDALA Sacred", "UNDERWATER Lava", "SYNAESTHESIA Classic", "FIRE Plasma", "SPACE INVADERS", "POND"]
        self.major_mode_idx = 0
        self.major_mode = self.modes[self.major_mode_idx]
        self.react_bass = 0.0
        self.react_mid = 0.0
        self.react_treble = 0.0
        self.current_stereo_panning = 0.0
        self.procedural_beat_timer = 0.0

        # Low-resolution screen-space audio field. Its RGB channels retain
        # localized bass, mid, and treble energy for regional shader effects.
        self.spatial_audio_zone_cols = 8
        self.spatial_audio_zone_rows = 5
        self.spatial_audio_zones = np.zeros(
            (self.spatial_audio_zone_rows, self.spatial_audio_zone_cols, 3),
            dtype=np.float32,
        )
        
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
            "BIRD", "BUTTERFLY"
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
        self.ring_effect_timer = 0.0
        self.mandala_fog_halo_timer = 0.0
        self.mandala_squiggle_timer = 0.0
        self.mandala_starburst_rebirth_timer = 0.0
        self.mandala_black_hole_timer = 0.0
        
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

    def _update_flame_envelope(self, current, target, dt, attack_rate, decay_rate):
        # Asymmetric exponential envelope follower: rises quickly toward `target` when it's
        # above `current` (attack), but eases back down slowly when `target` drops below
        # `current` (decay/release). This gives genuine multi-frame memory, producing an
        # organic "ceiling that slowly relaxes" rather than an instantaneous jump.
        rate = attack_rate if target > current else decay_rate
        factor = 1.0 - math.exp(-rate * dt)
        return current + (target - current) * factor

    def inject_spatial_audio_event(self, event):
        """Add an analyzed audio event to the regional screen-space audio field."""
        band_indices = {"bass": 0, "mid": 1, "treble": 2}
        dominant_index = band_indices.get(event.get("band_type"), 1)
        bands = np.array(
            [
                event.get("band_bass", 0.0),
                event.get("band_mid", 0.0),
                event.get("band_treble", 0.0),
            ],
            dtype=np.float32,
        )
        bands[dominant_index] += 0.85
        bands /= max(float(np.max(bands)), 1e-6)

        # Analyzed shell placement corresponds to stereo panning. Bass regions
        # occupy the lower sky, mids the center, and trebles the upper sky.
        x_offset = event.get("x_offset")
        if x_offset is None:
            x_norm = np.clip(self.current_stereo_panning, -1.0, 1.0)
        else:
            x_norm = np.clip(float(x_offset) / 11.0, -1.0, 1.0)
        y_norm = (0.24, 0.50, 0.80)[dominant_index]

        zone_x = (x_norm * 0.5 + 0.5) * (self.spatial_audio_zone_cols - 1)
        zone_y = y_norm * (self.spatial_audio_zone_rows - 1)
        grid_y, grid_x = np.mgrid[
            0:self.spatial_audio_zone_rows,
            0:self.spatial_audio_zone_cols,
        ]
        distance_sq = (grid_x - zone_x) ** 2 + (grid_y - zone_y) ** 2
        influence = np.exp(-distance_sq / 1.4).astype(np.float32)[..., np.newaxis]

        self.spatial_audio_zones += influence * bands[np.newaxis, np.newaxis, :] * 0.75
        np.clip(self.spatial_audio_zones, 0.0, 1.5, out=self.spatial_audio_zones)

    def update_spatial_audio_zones(self, dt):
        """Diffuse and fade regional energy between analyzed music events."""
        zones = self.spatial_audio_zones
        padded = np.pad(zones, ((1, 1), (1, 1), (0, 0)), mode="edge")
        neighbor_average = (
            padded[:-2, 1:-1]
            + padded[2:, 1:-1]
            + padded[1:-1, :-2]
            + padded[1:-1, 2:]
        ) * 0.25

        zones += (neighbor_average - zones) * min(1.0, dt * 4.0)
        zones *= math.exp(-1.7 * dt)

    def get_sim_time(self):
        if hasattr(self, 'is_recording') and self.is_recording:
            return self.record_time
        return time.time() - self.start_time

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
        elif self.major_mode == "SPACE INVADERS":
            self.trigger_climax_space_invaders(routine_name)
        elif self.major_mode == "POND":
            self.trigger_climax_pond(routine_name)

    def cycle_current_mode_routine(self):
        routines_by_mode = {
            "FIREWORKS": [
                ("American Flag", lambda: self.trigger_routine("American Flag", self.launch_american_flag)),
                ("Liberty Bell", lambda: self.trigger_routine("Liberty Bell", self.launch_liberty_bell)),
                ("Statue of Liberty", lambda: self.trigger_routine("Statue of Liberty", self.launch_statue_of_liberty)),
                ("Flower Bouquet", lambda: self.trigger_routine("Flower Bouquet", self.launch_flower_bouquet)),
                ("The Dragon", lambda: self.trigger_routine("The Dragon", self.launch_the_dragon)),
                ("Supernova", lambda: self.trigger_routine("Supernova", self.launch_supernova)),
                ("Shooting Star", lambda: self.trigger_routine("Shooting Star", self.launch_shooting_star)),
            ],
            "TUNNEL Wormhole": [
                ("Plasma Burst", lambda: self.trigger_climax_event(1.1, "Plasma Burst")),
                ("Gravity Surge", lambda: self.trigger_climax_event(1.2, "Gravity Surge")),
                ("Stardust Stream", lambda: self.trigger_climax_event(1.3, "Stardust Stream")),
                ("Event Horizon", lambda: self.trigger_climax_event(1.4, "Event Horizon")),
                ("Lightning Flash", lambda: self.trigger_climax_event(1.8, "Lightning Flash")),
                ("Supernova", lambda: self.trigger_climax_event(2.0, "Supernova")),
                ("Shooting Star", lambda: self.trigger_climax_event(1.6, "Shooting Star")),
            ],
            "UNDERWATER Lava": [
                ("Coral Pulse", lambda: self.trigger_climax_event(1.1, "Coral Pulse")),
                ("Geyser Eruption", lambda: self.trigger_climax_event(1.2, "Geyser Eruption")),
                ("Plankton Surge", lambda: self.trigger_climax_event(1.3, "Plankton Surge")),
                ("Deep Vent Blast", lambda: self.trigger_climax_event(1.4, "Deep Vent Blast")),
                ("Bioluminescent Rainbow", lambda: self.trigger_climax_event(1.8, "Bioluminescent Rainbow")),
                ("Supernova", lambda: self.trigger_climax_event(2.0, "Supernova")),
                ("Shooting Star", lambda: self.trigger_climax_event(1.6, "Shooting Star")),
            ],
            "MANDALA Sacred": [
                ("Lotus Bloom", lambda: self.trigger_climax_event(1.1, "Lotus Bloom")),
                ("Cosmic Spin", lambda: self.trigger_climax_event(1.2, "Cosmic Spin")),
                ("Ring Effect", lambda: self.trigger_climax_event(1.3, "Ring Effect")),
                ("Halo Effect", lambda: self.trigger_climax_event(1.4, "Halo Effect")),
                ("Smoke!", lambda: self.trigger_climax_event(1.5, "Smoke!")),
                ("Star Burst", lambda: self.trigger_climax_event(1.6, "Star Burst")),
                ("Starburst Effect", lambda: self.trigger_climax_event(1.7, "Starburst Effect")),
                ("Black Hole Effect", lambda: self.trigger_climax_event(1.8, "Black Hole Effect")),
                ("Peace Symbol", lambda: self.trigger_climax_event(1.6, "Peace Symbol")),
                ("Squiggles", lambda: self.trigger_climax_event(1.4, "Squiggles")),
            ],
            "SYNAESTHESIA Classic": [
                ("Star Burst", self.trigger_syn_star_burst),
            ],
            "FIRE Plasma": [
                ("Flame Flare", lambda: self.trigger_climax_event(1.1, "Flame Flare")),
                ("Flame Wave", lambda: self.trigger_climax_event(1.2, "Flame Wave")),
                ("Treble Spark Shower", lambda: self.trigger_climax_event(1.3, "Treble Spark Shower")),
                ("Fire Eruption", lambda: self.trigger_climax_event(1.4, "Fire Eruption")),
                ("Lightning Strike", lambda: self.trigger_climax_event(1.8, "Lightning Strike")),
            ],
            "SPACE INVADERS": [
                ("Alien Barrage", lambda: self.trigger_climax_event(1.3, "Alien Barrage")),
                ("Side Bomb", lambda: self.trigger_climax_event(1.4, "Side Bomb")),
                ("Supernova", lambda: self.trigger_climax_event(1.8, "Supernova")),
                ("Alien Glow", lambda: self.trigger_climax_event(1.2, "Alien Glow")),
                ("Defender Reset", lambda: self.trigger_climax_event(1.8, "Defender Reset")),
            ],
            "POND": [
                ("Leaf Vortex", lambda: self.trigger_climax_event(1.3, "Leaf Vortex")),
                ("Lightning Strike", lambda: self.trigger_climax_event(1.8, "Lightning Strike")),
                ("Fish Splash", lambda: self.trigger_climax_event(1.5, "Fish Splash")),
            ],
        }
        routines = routines_by_mode.get(self.major_mode, [])
        if not routines:
            return

        routine_idx = (self.mode_routine_indices.get(self.major_mode, -1) + 1) % len(routines)
        self.mode_routine_indices[self.major_mode] = routine_idx
        routine_name, trigger = routines[routine_idx]
        print(f"Cycling {self.major_mode} routine to: {routine_name}")
        trigger()

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
        elif r_type in ("BIRD", "BUTTERFLY"):
            self.spawn_rarity_mandala(r_type)
        elif r_type in ("SHOOTING_STAR", "BATS", "TUMBLEWEED"):
            self.spawn_rarity_fire(r_type)
        elif r_type in ("UFO", "INVADER_SHOOTING_STAR"):
            self.spawn_rarity_space_invaders(
                "SHOOTING_STAR" if r_type == "INVADER_SHOOTING_STAR" else r_type
            )

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
        elif t_type in ("BIRD", "BUTTERFLY"):
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
                    self.rarity_queued_type = random.choice(["BIRD", "BUTTERFLY"])
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
        self.sky_spatial_audio_enabled_loc = gl.glGetUniformLocation(
            self.sky_program, "uSpatialAudioEnabled"
        )
        self.sky_spatial_audio_zones_loc = gl.glGetUniformLocation(
            self.sky_program, "uSpatialAudioZones[0]"
        )
        self.sky_pond_ripples_loc = gl.glGetUniformLocation(
            self.sky_program, "uPondRipples[0]"
        )
        self.sky_pond_birds_loc = gl.glGetUniformLocation(
            self.sky_program, "uPondBirds[0]"
        )
        self.sky_pond_leaf_vortex_loc = gl.glGetUniformLocation(
            self.sky_program, "uPondLeafVortex"
        )
        self.sky_pond_lightning_loc = gl.glGetUniformLocation(
            self.sky_program, "uPondLightning"
        )
        self.sky_pond_trout_loc = gl.glGetUniformLocation(
            self.sky_program, "uPondTrout"
        )

    def on_render(self, area, context):
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
        elif self.major_mode == "SPACE INVADERS":
            if not hasattr(self, 'invader_alive'):
                self.init_space_invaders_mode()
        elif self.major_mode == "POND":
            if not hasattr(self, 'pond_rain'):
                self.init_pond_mode()
        
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
            elif self.major_mode == "POND":
                gl.glUniform1f(self.sky_ripple_loc, 4.0)
            else:
                gl.glUniform1f(self.sky_ripple_loc, 0.0)
                
        # Send full coordinates and audio parameters for continuous GPU raymarching/effects
        if self.major_mode in ("TUNNEL Wormhole", "FIRE Plasma", "POND"):
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
            if hasattr(self, 'sky_spatial_audio_enabled_loc') and self.sky_spatial_audio_enabled_loc != -1:
                gl.glUniform1f(
                    self.sky_spatial_audio_enabled_loc,
                    1.0 if self.major_mode == "FIRE Plasma" else 0.0,
                )
            if hasattr(self, 'sky_spatial_audio_zones_loc') and self.sky_spatial_audio_zones_loc != -1:
                gl.glUniform3fv(
                    self.sky_spatial_audio_zones_loc,
                    self.spatial_audio_zone_cols * self.spatial_audio_zone_rows,
                    self.spatial_audio_zones.reshape(-1, 3),
                )
            if hasattr(self, 'sky_pond_ripples_loc') and self.sky_pond_ripples_loc != -1:
                pond_ripple_data = np.zeros((8, 4), dtype=np.float32)
                if self.major_mode == "POND":
                    for index, ripple in enumerate(self.pond_shader_ripples[-8:]):
                        pond_ripple_data[index] = (
                            ripple["position"][0],
                            ripple["position"][1],
                            ripple["age"],
                            ripple["strength"],
                        )
                gl.glUniform4fv(
                    self.sky_pond_ripples_loc,
                    len(pond_ripple_data),
                    pond_ripple_data,
                )
            if hasattr(self, 'sky_pond_birds_loc') and self.sky_pond_birds_loc != -1:
                pond_bird_data = np.zeros((14, 4), dtype=np.float32)
                if self.major_mode == "POND":
                    bird_count = min(len(self.pond_bird_pos), len(pond_bird_data))
                    pond_bird_data[:bird_count, :2] = self.pond_bird_pos[:bird_count]
                    pond_bird_data[:bird_count, 2] = self.pond_bird_heading[:bird_count]
                    pond_bird_data[:bird_count, 3] = self.pond_bird_phase[:bird_count]
                gl.glUniform4fv(
                    self.sky_pond_birds_loc,
                    len(pond_bird_data),
                    pond_bird_data,
                )
            if hasattr(self, 'sky_pond_leaf_vortex_loc') and self.sky_pond_leaf_vortex_loc != -1:
                leaf_vortex_data = np.zeros(2, dtype=np.float32)
                if self.major_mode == "POND":
                    leaf_vortex_data[:] = (
                        self.pond_leaf_vortex_center_x,
                        self.pond_leaf_vortex_timer,
                    )
                gl.glUniform2fv(self.sky_pond_leaf_vortex_loc, 1, leaf_vortex_data)
            if hasattr(self, 'sky_pond_lightning_loc') and self.sky_pond_lightning_loc != -1:
                lightning_time = (
                    self.pond_lightning_timer if self.major_mode == "POND" else 0.0
                )
                gl.glUniform1f(self.sky_pond_lightning_loc, lightning_time)
            if hasattr(self, 'sky_pond_trout_loc') and self.sky_pond_trout_loc != -1:
                trout_data = np.zeros(4, dtype=np.float32)
                if self.major_mode == "POND" and self.pond_fish is not None:
                    trout_data[:] = (
                        self.pond_fish["pos"][0] / 10.5,
                        self.pond_fish["time"],
                        self.pond_fish["direction"],
                        1.0,
                    )
                gl.glUniform4fv(self.sky_pond_trout_loc, 1, trout_data)
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
        
        # Gather mode-specific line geometry (lightning bolts, shooting star trails,
        # rarity silhouettes) from the owning mode mixin, keeping this code isolated
        # per-mode instead of inline here.
        if self.major_mode == "TUNNEL Wormhole":
            t_line_pos, t_line_col = self.get_tunnel_lines()
            line_pos.extend(t_line_pos)
            line_col.extend(t_line_col)
        elif self.major_mode == "MANDALA Sacred":
            m_line_pos, m_line_col = self.get_mandala_lines()
            line_pos.extend(m_line_pos)
            line_col.extend(m_line_col)
        elif self.major_mode == "FIRE Plasma":
            f_line_pos, f_line_col = self.get_fire_lines()
            line_pos.extend(f_line_pos)
            line_col.extend(f_line_col)
        
        # Draw the reference grid only in 3D modes that use it as a spatial aid.
        if self.major_mode not in ("UNDERWATER Lava", "SPACE INVADERS", "POND"):
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

                    # Use the same live audio envelope as Mandala. Do not hold this
                    # value between frames: reactivity must visibly rise and fall with
                    # each beat rather than becoming a near-constant glow.
                    reactivity = self.opt_particle_reactivity / 10.0
                    beat_level = np.clip(
                        max(self.react_bass, self.react_mid, self.react_treble),
                        0.0,
                        1.5,
                    )
                    pulse_strength = reactivity * beat_level * 0.5
                    particle_pulse = 1.0 + pulse_strength * 1.5

                    # Apply the beat response after Firework.update() has calculated
                    # chemical color and lifetime fading. This affects the render buffer
                    # only, so it cannot interfere with particle simulation or fading.
                    reactive_colors = fw.colors.copy()
                    reactive_colors[:, :3] += (
                        1.0 - reactive_colors[:, :3]
                    ) * min(1.0, pulse_strength * 0.7)
                    reactive_colors[:, 3] += (
                        1.0 - reactive_colors[:, 3]
                    ) * min(1.0, pulse_strength)

                    # Current explosion sparks, including post-explosion falling sparks.
                    part_pos.append(fw.positions)
                    part_col.append(reactive_colors)
                    part_size.append(
                        np.full(num_pts, fw.star_size * particle_pulse, dtype=np.float32)
                    )

                    # Trails are historical positions of those same sparks. Apply the
                    # same live pulse so each complete falling streak brightens together.
                    if fw.history_len > 1 and fw.history is not None:
                        for h in range(fw.history_len):
                            trail_factor = 1.0 - (h / fw.history_len)
                            step_colors = fw.colors.copy()
                            step_colors[:, :3] += (
                                1.0 - step_colors[:, :3]
                            ) * min(1.0, pulse_strength * 0.7)
                            normal_alpha = step_colors[:, 3] * trail_factor * 0.45
                            pulse_alpha = min(1.0, pulse_strength) * trail_factor * 0.55
                            step_colors[:, 3] = np.maximum(normal_alpha, pulse_alpha)
                            step_sizes = np.full(
                                num_pts,
                                max(1.0, (fw.star_size * 0.65) * trail_factor)
                                * particle_pulse,
                                dtype=np.float32,
                            )

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
        elif self.major_mode == "SPACE INVADERS":
            if not hasattr(self, 'invader_alive'):
                self.init_space_invaders_mode()
            i_pos, i_col, i_size, h_pos, h_col = self.render_space_invaders()
            part_pos.append(i_pos)
            part_col.append(i_col)
            part_size.append(i_size)
        elif self.major_mode == "POND":
            if not hasattr(self, 'pond_rain'):
                self.init_pond_mode()
            p_pos, p_col, p_size, h_pos, h_col = self.render_pond()
            part_pos.append(p_pos)
            part_col.append(p_col)
            part_size.append(p_size)
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
                    gl.glUniform1i(
                        self.part_fire_mode_loc,
                        1 if self.major_mode == "FIRE Plasma"
                        else 2 if self.major_mode == "SPACE INVADERS"
                        else 3 if self.major_mode == "POND"
                        else 0,
                    )
                
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
        self.update_spatial_audio_zones(dt)

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
        if self.ring_effect_timer > 0.0:
            self.ring_effect_timer = max(0.0, self.ring_effect_timer - dt)
        
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
        elif self.major_mode == "SPACE INVADERS":
            if not hasattr(self, 'invader_alive'):
                self.init_space_invaders_mode()
            self.update_space_invaders(dt)
        elif self.major_mode == "POND":
            if not hasattr(self, 'pond_rain'):
                self.init_pond_mode()
            self.update_pond(dt)
            
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
        elif self.major_mode == "SPACE INVADERS":
            active_stars = int(np.sum(self.invader_alive)) if hasattr(self, 'invader_alive') else 0
            
        self.shell_lbl.set_text(f"Active Shells: {active_rockets}")
        self.part_lbl.set_text(f"Simulated Particles: {active_stars:,}")
        
        self.gl_area.queue_draw()
        return True

    def on_close_request(self, window):
        self.stop_sync_playback()
        return False
