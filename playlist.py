import os
import time
import json
import random
import numpy as np
from gi.repository import GLib
from constants import COLORS, COLOR_LIST
from firework import Firework


class PlaylistMixin:
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
            
            self.inject_spatial_audio_event(event)
            if self.major_mode == "POND":
                self.add_pond_music_ripple(event)
                self._steer_pond_flock(event)

            fw = Firework(fw_type=fw_type, color=color_rgb, x_offset=x_offset)
            fw.secondary_color = sec_color_rgb
            self.fireworks.append(fw)
            
        elif event_type == "climax":
            intensity = event.get("intensity", 1.5)
            self.trigger_climax_event(intensity=intensity, routine_name="Climax Burst!")
            
        elif event_type == "mode_routine":
            # Analyzer-generated climax cue: choose an appropriate routine at
            # playback time so the same track works naturally in every mode.
            self.trigger_random_current_mode_routine()
            
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
