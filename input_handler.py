import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gdk
from firework import Firework


class InputHandlerMixin:
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
                self.trigger_climax_event(intensity=1.2, routine_name="Geyser Eruption" if self.major_mode == "UNDERWATER Lava" else "Ring Effect" if self.major_mode == "MANDALA Sacred" else "Gravity Surge")
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
                self.trigger_climax_event(intensity=1.3, routine_name="Plankton Surge" if self.major_mode == "UNDERWATER Lava" else "Halo Effect" if self.major_mode == "MANDALA Sacred" else "Stardust Stream")
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
                self.trigger_climax_event(intensity=1.4, routine_name="Deep Vent Blast" if self.major_mode == "UNDERWATER Lava" else "Smoke!" if self.major_mode == "MANDALA Sacred" else "Event Horizon")
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
                self.trigger_climax_event(intensity=1.8, routine_name="Bioluminescent Rainbow" if self.major_mode == "UNDERWATER Lava" else "Star Burst" if self.major_mode == "MANDALA Sacred" else "Lightning Flash")
            return True
        elif key_char == '6':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("Supernova", self.launch_supernova)
            elif self.major_mode == "MANDALA Sacred":
                self.trigger_climax_event(intensity=1.6, routine_name="Starburst Effect")
            elif self.major_mode == "FIRE Plasma":
                pass
            else:
                self.trigger_climax_event(intensity=2.0, routine_name="Supernova")
            return True
        elif key_char == '7':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("Shooting Star", self.launch_shooting_star)
            elif self.major_mode == "MANDALA Sacred":
                self.trigger_climax_event(intensity=1.8, routine_name="Black Hole Effect")
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
        elif keyval in (Gdk.KEY_x, Gdk.KEY_X):
            self.cycle_current_mode_routine()
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
        elif keyval in (Gdk.KEY_j, Gdk.KEY_J):
            self.opt_particle_reactivity = (self.opt_particle_reactivity + 1) % 11
            print(f"Particle Reactivity: {self.opt_particle_reactivity}/10")
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
                "MANDALA Sacred": ["BIRD", "BUTTERFLY"],
                "FIRE Plasma": ["SHOOTING_STAR", "BATS", "TUMBLEWEED"],
                "SPACE INVADERS": ["UFO", "INVADER_SHOOTING_STAR"]
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
