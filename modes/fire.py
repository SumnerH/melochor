import numpy as np
import random
import os
import OpenGL.GL as gl

class FireModeMixin:
    def init_moon_texture(self):
        try:
            from PIL import Image
            base_dir = os.path.dirname(os.path.abspath(__file__))
            # Go up one level to look for moon.png in the project root
            project_root = os.path.dirname(base_dir)
            
            # Paths to search for moon.png: 1) CWD, 2) project root, 3) relative path
            paths_to_try = [
                os.path.join(os.getcwd(), "moon.png"),
                os.path.join(project_root, "moon.png"),
                "moon.png"
            ]
            
            moon_path = None
            for p in paths_to_try:
                if os.path.exists(p):
                    moon_path = p
                    break
                    
            if moon_path is not None:
                img = Image.open(moon_path).convert("RGBA")
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
                w, h = img.size
                pixels = img.tobytes("raw", "RGBA")
                
                self.moon_texture_id = gl.glGenTextures(1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self.moon_texture_id)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
                
                gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
                gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, w, h, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, pixels)
                gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
                print(f"SUCCESS: Loaded moon texture using Pillow from {moon_path} ({w}x{h})")
            else:
                print(f"Warning: moon.png not found in search paths: {paths_to_try}")
                self.moon_texture_id = 0
        except Exception as e:
            print(f"Error loading moon.png with Pillow: {e}")
            self.moon_texture_id = 0

    # =========================================================================
    # MODE 6: FIRE PLASMA (Procedural flames with persistent reactive sparks)
    # =========================================================================
    def init_fire_mode(self):
        N_sparks = 1500
        self.fire_spark_pos = np.zeros((N_sparks, 3), dtype=np.float32)
        self.fire_spark_vel = np.zeros((N_sparks, 3), dtype=np.float32)
        self.fire_spark_col = np.zeros((N_sparks, 4), dtype=np.float32)
        self.fire_spark_size = np.zeros(N_sparks, dtype=np.float32)
        self.fire_spark_life = np.zeros(N_sparks, dtype=np.float32)
        self.fire_spark_max_life = np.zeros(N_sparks, dtype=np.float32)
        self.fire_spark_active = np.zeros(N_sparks, dtype=np.bool_)
        self.fire_spark_hue = np.zeros(N_sparks, dtype=np.float32) # For beautiful individual color variations
        self.fire_spark_plume = np.zeros(N_sparks, dtype=np.int32) # Tracks which of the 3 independent flames a particle belongs to
        self.next_fire_spark_idx = 0
        
        # 3 independent wind gust variables (for Left, Center, Right flames)
        self.fire_wind_gusts = [0.0, 0.0, 0.0]
        self.fire_wind_timers = [0.0, 0.0, 0.0]
        self.fire_wind_targets = [0.0, 0.0, 0.0]

    def spawn_differentiated_spark(self, s_type):
        idx = self.next_fire_spark_idx
        self.next_fire_spark_idx = (self.next_fire_spark_idx + 1) % len(self.fire_spark_pos)
        
        if s_type == 'FLARE':
            # Flame Flare: Massive white-hot sparks rising straight up
            x = np.random.uniform(-0.12, 0.12)
            y = np.random.uniform(-0.84, -0.78)
            z = np.random.uniform(-0.15, 0.15)
            self.fire_spark_pos[idx] = [x, y, z]
            
            vx = np.random.uniform(-0.06, 0.06)
            vy = np.random.uniform(0.75, 1.3)
            vz = np.random.uniform(-0.06, 0.06)
            self.fire_spark_vel[idx] = [vx, vy, vz]
            
            is_smoke = np.random.uniform(0.0, 1.0) < 0.25
            if is_smoke:
                self.fire_spark_size[idx] = -np.random.uniform(12.0, 26.0)
                # Orange-tinted glowing smoke
                self.fire_spark_col[idx] = [0.42, 0.22, 0.08, np.random.uniform(0.12, 0.28)]
                self.fire_spark_hue[idx] = -1.0
                max_life = np.random.uniform(2.8, 4.5)
            else:
                self.fire_spark_size[idx] = np.random.uniform(7.5, 15.0)
                self.fire_spark_col[idx] = [1.0, 0.98, 0.82, np.random.uniform(0.85, 1.0)]
                self.fire_spark_hue[idx] = np.random.uniform(0.1, 0.2)
                max_life = np.random.uniform(2.2, 3.8)
                
        elif s_type == 'WAVE':
            # Flame Wave: Rolling sweeping sideways embers
            sweep_dir = np.random.choice([-1.0, 1.0])
            # Spawn on the opposite side to sweep across
            x = -0.38 if sweep_dir > 0 else 0.38
            y = np.random.uniform(-0.84, -0.74)
            z = np.random.uniform(-0.25, 0.25)
            self.fire_spark_pos[idx] = [x, y, z]
            
            vx = sweep_dir * np.random.uniform(0.65, 1.15)
            vy = np.random.uniform(0.16, 0.36)
            vz = np.random.uniform(-0.1, 0.1)
            self.fire_spark_vel[idx] = [vx, vy, vz]
            
            self.fire_spark_size[idx] = np.random.uniform(4.0, 7.5)
            # Vibrant neon orange/red embers
            self.fire_spark_col[idx] = [1.0, np.random.uniform(0.15, 0.42), 0.0, np.random.uniform(0.8, 1.0)]
            self.fire_spark_hue[idx] = np.random.uniform(0.02, 0.1)
            max_life = np.random.uniform(1.8, 3.4)
            
        elif s_type == 'SHOWER':
            # Treble Spark Shower: Tiny gold embers drifting down from upper sky
            x = np.random.uniform(-0.95, 0.95)
            y = np.random.uniform(0.35, 0.92)
            z = np.random.uniform(-0.15, 0.15)
            self.fire_spark_pos[idx] = [x, y, z]
            
            vx = np.random.uniform(-0.12, 0.12)
            vy = -np.random.uniform(0.08, 0.22)
            vz = np.random.uniform(-0.06, 0.06)
            self.fire_spark_vel[idx] = [vx, vy, vz]
            
            self.fire_spark_size[idx] = np.random.uniform(1.0, 2.2)
            # Twinkling golden yellow colors
            self.fire_spark_col[idx] = [1.0, np.random.uniform(0.78, 0.98), 0.15, np.random.uniform(0.75, 1.0)]
            self.fire_spark_hue[idx] = np.random.uniform(0.12, 0.22)
            max_life = np.random.uniform(3.2, 5.8)
            
        elif s_type == 'ERUPTION':
            # Fire Eruption: Outward radial volcanic explosion
            self.fire_spark_pos[idx] = [0.0, -0.84, np.random.uniform(-0.1, 0.1)]
            
            theta = np.random.uniform(0.0, 2.0 * np.pi)
            phi = np.random.uniform(np.radians(12.0), np.radians(82.0))
            speed = np.random.uniform(0.68, 1.68)
            
            vx = speed * np.sin(phi) * np.sin(theta)
            vy = speed * np.cos(phi)
            vz = speed * np.sin(phi) * np.cos(theta)
            self.fire_spark_vel[idx] = [vx, vy, vz]
            
            self.fire_spark_size[idx] = np.random.uniform(2.8, 8.8)
            # Multicolored fiery sparks (white, gold, magenta-red)
            c_type = np.random.choice([0, 1, 2])
            if c_type == 0:
                self.fire_spark_col[idx] = [1.0, 0.95, 0.72, 1.0] # White-hot
                self.fire_spark_hue[idx] = 0.16
            elif c_type == 1:
                self.fire_spark_col[idx] = [1.0, 0.55, 0.05, 1.0] # Golden-orange
                self.fire_spark_hue[idx] = 0.08
            else:
                self.fire_spark_col[idx] = [1.0, 0.05, 0.22, 1.0] # Fiery red-pink
                self.fire_spark_hue[idx] = 0.95
                
            max_life = np.random.uniform(1.3, 2.8)
            
        self.fire_spark_life[idx] = max_life
        self.fire_spark_max_life[idx] = max_life
        self.fire_spark_active[idx] = True

    def spawn_fire_spark(self, band, reaction_val):
        idx = self.next_fire_spark_idx
        self.next_fire_spark_idx = (self.next_fire_spark_idx + 1) % len(self.fire_spark_pos)
        
        # Position: Distributed throughout the screen-space base of the campfire
        y = np.random.uniform(-0.84, -0.74) # Spawn strictly at the base of the fire
        
        # Divide the campfire into 3 independent flames for dynamic realism!
        # Compacted centers (radius < 0.12) to keep them strictly inside the stone ring (radius < 0.18)
        flame_centers = [
            (-0.11, -0.04),  # Left flame plume (index 0)
            (0.0, 0.04),     # Center flame plume (index 1)
            (0.11, -0.04)    # Right flame plume (index 2)
        ]
        plume_idx = random.choice([0, 1, 2])
        fx, fz = flame_centers[plume_idx]
        self.fire_spark_plume[idx] = plume_idx
        
        # Spawn with a tight horizontal spread around the chosen plume center (radius <= 0.15 max)
        x = fx + np.random.uniform(-0.035, 0.035)
        z = fz + np.random.uniform(-0.035, 0.035)
        self.fire_spark_pos[idx] = [x, y, z]
        
        # Velocity: Wide-angle pop trajectory, scaled down for screen-space coordinate system
        theta = np.random.uniform(0.0, 2.0 * np.pi)
        phi = np.random.uniform(np.radians(15.0), np.radians(80.0))
        
        sin_phi = np.sin(phi)
        cos_phi = np.cos(phi)
        
        # Speed scaled down for screen-space (0.12 to 0.45 screen units per second)
        speed = np.random.uniform(0.12, 0.45) * (1.0 + reaction_val * 0.4)
        
        vx = speed * sin_phi * np.sin(theta)
        vy = speed * cos_phi
        vz = speed * sin_phi * np.cos(theta)
        self.fire_spark_vel[idx] = [vx, vy, vz]
        
        # Determine whether to spawn a Spark (65% chance) or a delicate Smoke Puff (35% chance)
        is_smoke = np.random.uniform(0.0, 1.0) < 0.35
        
        if is_smoke:
            is_column = np.random.uniform(0.0, 1.0) < 0.40 # 40% chance of a brief columnar plume
            if is_column:
                # Gaseous Smoke Column/Plume (Narrow, fast-rising, longer life)
                self.fire_spark_size[idx] = -np.random.uniform(7.0, 15.0) * (1.0 + reaction_val * 0.2)
                self.fire_spark_col[idx] = [0.23, 0.24, 0.26, np.random.uniform(0.12, 0.30)]
                max_life = np.random.uniform(3.5, 5.5) # Rises higher
                self.fire_spark_hue[idx] = -2.0 # Hue -2.0 is columnar smoke
                
                # Straight upward velocity profile
                self.fire_spark_vel[idx, 0] = np.random.uniform(-0.02, 0.02)
                self.fire_spark_vel[idx, 1] = np.random.uniform(0.65, 0.95) * (1.0 + reaction_val * 0.3)
                self.fire_spark_vel[idx, 2] = np.random.uniform(-0.02, 0.02)
            else:
                # Gaseous Smoke Puff (Negative size represents gaseous style in particle shader!)
                self.fire_spark_size[idx] = -np.random.uniform(8.0, 24.0) * (1.0 + reaction_val * 0.3)
                # Translucent wispy charcoal smoke color
                self.fire_spark_col[idx] = [0.26, 0.27, 0.30, np.random.uniform(0.10, 0.25)]
                max_life = np.random.uniform(2.5, 4.8) # Smoke lives slightly longer and rises higher
                self.fire_spark_hue[idx] = -1.0 # Hue <= -0.5 is reserved for Smoke in update loop
        else:
            # Bright Spark/Ember (Positive size)
            self.fire_spark_size[idx] = np.random.uniform(1.8, 4.5) * (1.0 + reaction_val * 0.25)
            # Initial color is white-hot/yellow-orange
            self.fire_spark_col[idx] = [1.0, 0.95, 0.65, np.random.uniform(0.75, 1.0)]
            max_life = np.random.uniform(1.8, 3.8)
            self.fire_spark_hue[idx] = np.random.uniform(0.0, 1.0)
            
        self.fire_spark_life[idx] = max_life
        self.fire_spark_max_life[idx] = max_life
        self.fire_spark_active[idx] = True

    def update_fire(self, dt):
        if not hasattr(self, 'fire_wind_timer'):
            self.fire_wind_gust = 0.0
            self.fire_wind_timer = 0.0
            self.fire_wind_target = 0.0
            
        # Update lightning bolts
        if not hasattr(self, 'fire_lightning_bolts'):
            self.fire_lightning_bolts = []
        active_bolts = []
        for bolt in self.fire_lightning_bolts:
            bolt['life'] -= dt
            if bolt['life'] > 0.0:
                active_bolts.append(bolt)
        self.fire_lightning_bolts = active_bolts

        # Update 3 independent wind gust variables for Left, Center, and Right plumes!
        if not hasattr(self, 'fire_wind_gusts'):
            self.fire_wind_gusts = [0.0, 0.0, 0.0]
            self.fire_wind_timers = [0.0, 0.0, 0.0]
            self.fire_wind_targets = [0.0, 0.0, 0.0]
            
        for p in range(3):
            self.fire_wind_timers[p] += dt
            # Randomly trigger separate winds for each plume every 4-8 seconds
            if self.fire_wind_timers[p] > np.random.uniform(4.0, 8.0):
                self.fire_wind_timers[p] = 0.0
                self.fire_wind_targets[p] = np.random.choice([-1.0, 1.0]) * np.random.uniform(0.6, 1.2)
                
            # Interpolate wind gusts individually towards targets
            if abs(self.fire_wind_targets[p]) > 0.01:
                self.fire_wind_gusts[p] += (self.fire_wind_targets[p] - self.fire_wind_gusts[p]) * 2.8 * dt
                if abs(self.fire_wind_gusts[p] - self.fire_wind_targets[p]) < 0.1:
                    self.fire_wind_targets[p] = 0.0
            else:
                self.fire_wind_gusts[p] += (0.0 - self.fire_wind_gusts[p]) * 0.85 * dt

        active_mask = self.fire_spark_active
        if np.any(active_mask):
            # Apply velocity translation
            self.fire_spark_pos[active_mask] += self.fire_spark_vel[active_mask] * dt
            
            # PHYSICAL BOUNDARY CONTAINMENT: Keep ash and embers strictly contained within the inner edge of the stones (radius < 0.18) while near the ground
            y_pos_all = self.fire_spark_pos[active_mask, 1]
            x_pos_all = self.fire_spark_pos[active_mask, 0]
            z_pos_all = self.fire_spark_pos[active_mask, 2]
            
            near_ground = y_pos_all < -0.55
            if np.any(near_ground):
                active_indices = np.where(active_mask)[0]
                ground_sub_indices = np.where(near_ground)[0]
                for g_idx in ground_sub_indices:
                    real_idx = active_indices[g_idx]
                    gx = self.fire_spark_pos[real_idx, 0]
                    gz = self.fire_spark_pos[real_idx, 2]
                    gr2 = gx*gx + gz*gz
                    if gr2 > 0.0324: # 0.18 squared (strictly inside the stones!)
                        # Scale back inside the stones
                        scale = np.sqrt(0.0324 / gr2)
                        self.fire_spark_pos[real_idx, 0] *= scale
                        self.fire_spark_pos[real_idx, 2] *= scale
                        # Bounce velocity inwards slightly
                        self.fire_spark_vel[real_idx, 0] *= -0.2
                        self.fire_spark_vel[real_idx, 2] *= -0.2
            
            # --- PHYSICAL AIR RESISTANCE & DRAFT FLUID DRAG ---
            self.fire_spark_vel[active_mask, 0] *= np.exp(-1.4 * dt)
            self.fire_spark_vel[active_mask, 1] *= np.exp(-1.0 * dt)
            self.fire_spark_vel[active_mask, 2] *= np.exp(-1.4 * dt)
            
            # --- CONVECTIVE DRIFT & SWIRLING EDDIES (ASHES BEHAVIOR) ---
            time_val = self.get_sim_time()
            y_pos = self.fire_spark_pos[active_mask, 1]
            x_pos = self.fire_spark_pos[active_mask, 0]
            z_pos = self.fire_spark_pos[active_mask, 2]
            
            # Distance from the 3 independent flame centers for separate rising convective plumes
            r2_left = (x_pos + 0.18)**2 + (z_pos + 0.05)**2
            r2_center = (x_pos)**2 + (z_pos - 0.05)**2
            r2_right = (x_pos - 0.18)**2 + (z_pos + 0.05)**2
            
            # 1. Thermal Heat Loft: Compute combined thermal loft columns
            plume_factor = np.exp(-r2_left / 0.015) + np.exp(-r2_center / 0.015) + np.exp(-r2_right / 0.015)
            heat_loft = plume_factor * (0.24 + 0.12 * self.react_bass)
            self.fire_spark_pos[active_mask, 1] += heat_loft * dt
            
            # 2. Sideways Draft & Wind Sway: Gentle swaying crosswinds (scaled for screen-space)
            crosswind = np.sin(time_val * 1.4 + y_pos * 1.2) * 0.045
            self.fire_spark_pos[active_mask, 0] += crosswind * dt
            
            # 3. Turbulent Swirling Eddies: 3D corkscrew currents that make the ashes curl and float (scaled for screen-space)
            vortex_x = np.sin(time_val * 3.2 + y_pos * 2.5 + z_pos * 1.5) * 0.055
            vortex_z = np.cos(time_val * 2.8 + y_pos * 2.2 + x_pos * 1.5) * 0.055
            
            self.fire_spark_pos[active_mask, 0] += vortex_x * dt
            self.fire_spark_pos[active_mask, 2] += vortex_z * dt
            
            # --- 4. REAL-TIME WIND GUST FORCES ---
            # Blows sparks and smoke sideways depending on altitude (zero push at fire base)
            height_factor = np.clip(y_pos - (-0.84), 0.0, 2.0)
            
            # Map each active particle's plume index to its corresponding plume wind gust!
            p_indices = self.fire_spark_plume[active_mask]
            p_gusts = np.array([self.fire_wind_gusts[p] for p in p_indices], dtype=np.float32)
            
            # Basic wind force push for all particles
            wind_push = p_gusts * 0.42 * height_factor * dt
            self.fire_spark_pos[active_mask, 0] += wind_push
            
            # Smoke particles have more surface area and are lighter, so they get pushed extra sideways!
            is_smoke_mask = self.fire_spark_size[active_mask] < 0.0
            smoke_extra_push = is_smoke_mask.astype(np.float32) * p_gusts * 0.18 * height_factor * dt
            self.fire_spark_pos[active_mask, 0] += smoke_extra_push
            
            # Decrease life
            self.fire_spark_life[active_mask] -= dt
            
            expired = self.fire_spark_life <= 0.0
            self.fire_spark_active[expired] = False
            
            # Thermochromatic cooling and micro-shimmering for still active sparks
            still_active = np.where(self.fire_spark_active)[0]
            if len(still_active) > 0:
                color_mode = getattr(self, 'opt_color_mode', 'REALISTIC')
                for idx in still_active:
                    frac = self.fire_spark_life[idx] / self.fire_spark_max_life[idx]
                    hue = self.fire_spark_hue[idx]
                    
                    if hue < -0.5:
                        # 4. Gaseous Smoke Puff (Expands and fades out smoothly to translucent charcoal grey)
                        self.fire_spark_size[idx] -= np.random.uniform(5.5, 11.0) * dt # Expands diameter
                        r, g, b = 0.22, 0.23, 0.25 # Wispy soot grey
                        
                        # Soft alpha fade as life expires
                        shimmer = 0.85 + 0.15 * np.sin(time_val * np.random.uniform(5.0, 15.0) + idx)
                        alpha = frac * shimmer * 0.22
                    else:
                        # Dynamic multi-class cooling based on color mode
                        if color_mode == 'NEON':
                            if hue < 0.30:
                                # Neon Pink cooling to Purple
                                r = 1.0 * frac
                                g = 0.0
                                b = 0.5 + 0.5 * (1.0 - frac)
                            elif hue > 0.75:
                                # Neon Cyan cooling to Deep Blue
                                r = 0.0
                                g = 1.0 * frac
                                b = 1.0
                            else:
                                # Purple cooling to Dark Blue
                                r = 0.5 * frac
                                g = 0.0
                                b = 1.0
                        elif color_mode == 'TRANQUIL':
                            if hue < 0.30:
                                # Deep Blue cooling to Teal
                                r = 0.0
                                g = 0.6 * (1.0 - frac)
                                b = 0.8
                            elif hue > 0.75:
                                # Lavender cooling to Dark Purple
                                r = 0.5 * frac
                                g = 0.2 * frac
                                b = 0.7
                            else:
                                # Soft Emerald cooling to Dark Blue
                                r = 0.1 * frac
                                g = 0.7 * frac
                                b = 0.4 + 0.4 * (1.0 - frac)
                        elif color_mode == 'METAL':
                            if hue < 0.30:
                                # Warm Bronze cooling to Dark Red
                                r = 0.8 * frac
                                g = 0.5 * frac * frac
                                b = 0.2 * frac * frac
                            elif hue > 0.75:
                                # Radiant Gold cooling to Amber
                                r = 1.0
                                g = 0.8 * frac + 0.2
                                b = 0.2 * frac
                            else:
                                # Bright Silver cooling to Slate Grey
                                r = 0.9 * frac + 0.1
                                g = 0.9 * frac + 0.1
                                b = 0.95 * frac + 0.1
                        else: # REALISTIC
                            # Individualized Multi-Class Thermochromatic Cooling Curves (Real Campfire Color Temperature)
                            if hue < 0.30:
                                # 1. Deep Crimson / Burgundy Glowing Coals (Ruby-red cooling to dark charcoal)
                                r = 0.88 * frac
                                g = 0.14 * frac * frac
                                b = 0.02 * frac * frac * frac
                            elif hue > 0.75:
                                # 2. Hot Blazing Gold / Amber Embers (White-gold cooling to beautiful copper yellow)
                                if frac > 0.75:
                                    r, g, b = 1.0, 0.90, 0.50
                                else:
                                    t = frac / 0.75
                                    r = 1.0
                                    g = 0.40 * t + 0.50 * t * t
                                    b = 0.04 * t
                            else:
                                # 3. Sizzling Copper Orange Sparks (White-hot orange to fiery copper and warm brick red)
                                if frac > 0.80:
                                    r, g, b = 1.0, 0.75, 0.35
                                elif frac > 0.35:
                                    t = (frac - 0.35) / 0.45
                                    r = 0.98
                                    g = 0.28 + 0.47 * t
                                    b = 0.02 + 0.33 * t
                                else:
                                    t = frac / 0.35
                                    r = 0.35 + 0.63 * t
                                    g = 0.03 * t
                                    b = 0.01 * t
                                    
                        # Dynamic music-reactive coloring:
                        # 1. Dark red with bass (reduce green and blue, enhance red slightly)
                        # 2. Orange with treble (add green/yellow to red)
                        bass_factor = self.react_bass
                        treble_factor = self.react_mid * 0.4 + self.react_treble * 0.6
                        
                        r_shaded = r * (1.0 + treble_factor * 0.2) + bass_factor * 0.1
                        g_shaded = g * (1.0 - bass_factor * 0.6) + treble_factor * 0.3
                        b_shaded = b * (1.0 - bass_factor * 0.8)
                        
                        r = np.clip(r_shaded, 0.0, 1.0)
                        g = np.clip(g_shaded, 0.0, 1.0)
                        b = np.clip(b_shaded, 0.0, 1.0)
                        
                        # Dynamic multi-color variation: Mix a tiny bit of individual hue color shift
                        # to ensure embers are multi-colored and never a solid flat color!
                        col_hue = (hue + time_val * 0.2) % 1.0
                        if col_hue < 0.33:
                            # Shift towards deeper crimson
                            r = np.clip(r * 1.0, 0.0, 1.0)
                            g = np.clip(g * 0.8, 0.0, 1.0)
                            b = np.clip(b * 0.7, 0.0, 1.0)
                        elif col_hue > 0.66:
                            # Shift towards warmer amber/orange
                            r = np.clip(r * 1.0, 0.0, 1.0)
                            g = np.clip(g * 1.1, 0.0, 1.0)
                            b = np.clip(b * 0.6, 0.0, 1.0)
                            
                        # Realistic rapid micro-shimmering pulsing with the music!
                        shimmer = 0.50 + 0.50 * np.sin(time_val * np.random.uniform(25.0, 45.0) + idx)
                        # The alpha glow pulses dynamically with the music beats
                        music_pulse = 0.7 + self.react_bass * 0.4 + self.react_treble * 0.2
                        alpha = np.clip(frac * shimmer * music_pulse, 0.0, 1.0)
                    
                    self.fire_spark_col[idx] = [r, g, b, alpha]
                    
                    # Respect opt_trailers on sparks! (Short-lived sparks do not generate trails to prevent runaway feedback)
                    opt_tr = getattr(self, 'opt_trailers', 0)
                    if opt_tr > 0 and hue >= 0.0 and self.fire_spark_max_life[idx] > 0.5:
                        if np.random.uniform(0.0, 10.0) < opt_tr:
                            t_idx = self.next_fire_spark_idx
                            self.next_fire_spark_idx = (self.next_fire_spark_idx + 1) % len(self.fire_spark_pos)
                            
                            self.fire_spark_pos[t_idx] = self.fire_spark_pos[idx].copy()
                            self.fire_spark_vel[t_idx] = list(np.array(self.fire_spark_vel[idx]) * 0.15)
                            self.fire_spark_size[t_idx] = self.fire_spark_size[idx] * 0.52
                            
                            trail_life = np.random.uniform(0.12, 0.42)
                            self.fire_spark_life[t_idx] = trail_life
                            self.fire_spark_max_life[t_idx] = trail_life
                            self.fire_spark_col[t_idx] = [r, g, b, alpha * 0.35]
                            self.fire_spark_hue[t_idx] = hue
                            self.fire_spark_active[t_idx] = True

        # Spawn sparks based on real-time frequency reactions
        if self.react_bass > 0.4:
            count = int(self.react_bass * 8)
            for _ in range(count):
                self.spawn_fire_spark("bass", self.react_bass)
                
        if self.react_mid > 0.4:
            count = int(self.react_mid * 6)
            for _ in range(count):
                self.spawn_fire_spark("mid", self.react_mid)
                
        if self.react_treble > 0.4:
            count = int(self.react_treble * 6)
            for _ in range(count):
                self.spawn_fire_spark("treble", self.react_treble)
                
        if self.active_rarity is not None:
            self.update_active_rarity(dt)

    def render_fire(self):
        act_mask = self.fire_spark_active
        if np.any(act_mask):
            pos_combined = self.fire_spark_pos[act_mask]
            col_combined = self.fire_spark_col[act_mask]
            size_combined = self.fire_spark_size[act_mask]
        else:
            pos_combined = np.zeros((0, 3), dtype=np.float32)
            col_combined = np.zeros((0, 4), dtype=np.float32)
            size_combined = np.zeros(0, dtype=np.float32)
            
        return pos_combined, col_combined, size_combined, np.zeros((0, 3), dtype=np.float32), np.zeros((0, 4), dtype=np.float32)
