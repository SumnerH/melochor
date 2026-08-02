import random


class PresetMixin:
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
