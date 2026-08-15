import os
import sys
import time
import json
import numpy as np
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk


class UIMixin:
    def load_css(self):
        css_data = """
        .hud-title {
            font-family: 'Outfit', 'Inter', 'Sans-Serif', sans-serif;
            font-size: 20px;
            font-weight: bold;
            color: #e6f0ff;
        }
        .hud-subtitle {
            font-family: 'Outfit', 'Inter', 'Sans-Serif', sans-serif;
            font-size: 12px;
            color: #96b4dc;
        }
        .hud-stats-fps {
            font-family: 'Inter', 'Monospace', monospace;
            font-size: 13px;
            font-weight: bold;
            color: #64e696;
            margin-bottom: 2px;
        }
        .hud-stats {
            font-family: 'Inter', 'Monospace', monospace;
            font-size: 12px;
            color: #c8dcff;
        }
        .hud-routine {
            font-family: 'Inter', 'Sans-Serif', sans-serif;
            font-size: 13px;
            font-weight: bold;
            color: #ffa834;
            margin-top: 3px;
        }
        .hud-legend {
            background-color: rgba(10, 10, 25, 0.65);
            border: 1px solid rgba(130, 150, 180, 0.2);
            border-radius: 6px;
            padding: 14px;
        }
        .hud-legend-title {
            font-family: 'Outfit', 'Inter', sans-serif;
            font-weight: bold;
            color: #e2e6ff;
            font-size: 12px;
            margin-bottom: 6px;
        }
        .hud-legend label {
            font-family: 'Inter', 'Monospace', monospace;
            font-size: 11px;
            color: #b4c8f0;
        }
        .hud-music-time {
            font-family: 'Inter', 'Monospace', monospace;
            font-size: 13px;
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
        
        sub_text = "Kodi Live Follower Visualizer" if getattr(self, 'kodi_mode', False) else "Interactive OpenGL Audio Visualizer & Screensaver"
        sub_lbl = Gtk.Label(label=sub_text)
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
        
        hdr_text = "KODI MUSIC SYNCHRONIZER:" if getattr(self, 'kodi_mode', False) else "MUSIC SYNCHRONIZER:"
        music_hdr = Gtk.Label(label=hdr_text)
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
        
        lbl_space = Gtk.Label(label="[SPACE]  - Kodi Play/Pause" if getattr(self, 'kodi_mode', False) else "[SPACE]  - Play/Pause Sync Playback")
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
        
        key_controller = Gtk.EventControllerKey.new()
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.win.add_controller(key_controller)
        
        motion_controller = Gtk.EventControllerMotion.new()
        motion_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        motion_controller.connect("motion", self.on_mouse_motion)
        self.win.add_controller(motion_controller)

        self.gl_area.set_focusable(True)
        self.gl_area.grab_focus()

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

        if getattr(self, 'kodi_mode', False):
            self.start_kodi_sync()
        elif self.is_recording:
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
        
        if getattr(self, 'kodi_mode', False):
            if getattr(self, 'kodi_is_playing', False):
                self.lbl_music.set_text("[M/SPACE]- Kodi Playback: PLAYING")
            elif getattr(self, 'kodi_connected', False):
                self.lbl_music.set_text("[M/SPACE]- Kodi Playback: PAUSED/IDLE")
            else:
                self.lbl_music.set_text(f"[M/SPACE]- Kodi Status: CONNECTING ({self.kodi_host}:{self.kodi_port})")
        elif self.music_playing:
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
                self.lbl_r2.set_text("[2]  - Ring Effect")
                self.lbl_r3.set_text("[3]  - Halo Effect")
                self.lbl_r4.set_text("[4]  - Smoke!")
                self.lbl_r5.set_text("[5]  - Star Burst")
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
                self.lbl_r7.set_text("[7]  - Ring Outward Sparks")
            elif self.major_mode in ("SYNAESTHESIA Classic", "FIRE Plasma"):
                self.lbl_r7.set_text("")
            else:
                self.lbl_r7.set_text("[7]  - Shooting Star")

    def on_mouse_motion(self, controller, x, y):
        self.last_mouse_move_time = time.time()
        if getattr(self, 'cursor_hidden', False):
            self.cursor_hidden = False
            if hasattr(self, 'win') and self.win:
                self.win.set_cursor(None)

    def on_drag_begin(self, gesture, x, y):
        self.last_mouse_move_time = time.time()
        if getattr(self, 'cursor_hidden', False):
            self.cursor_hidden = False
            if hasattr(self, 'win') and self.win:
                self.win.set_cursor(None)
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
            
        if getattr(self, 'kodi_mode', False):
            kodi_lbl = Gtk.Label(label="KODI CONTROLS:")
            kodi_lbl.add_css_class("hud-legend-title")
            kodi_lbl.set_halign(Gtk.Align.START)
            kodi_lbl.set_margin_start(4)
            menu_box.append(kodi_lbl)
            
            play_label = "⏸ Pause Kodi" if getattr(self, 'kodi_is_playing', False) else "▶ Play Kodi"
            menu_box.append(make_menu_item(play_label, self.kodi_play_pause))
            menu_box.append(make_menu_item("⏭ Next Kodi Track", self.kodi_next_track))
            menu_box.append(make_menu_item("⏮ Previous Kodi Track", self.kodi_previous_track))
        else:
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
