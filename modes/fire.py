import numpy as np
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
        N_sparks = 800  # reduced from 1500 for performance
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
        self.fire_wind_gusts = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.fire_wind_timers = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.fire_wind_targets = np.array([0.0, 0.0, 0.0], dtype=np.float32)

        # lightning bolts list (kept as list of dicts, small)
        self.fire_lightning_bolts = []

    def spawn_differentiated_spark(self, s_type):
        # unchanged – used by other routines
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

    # -------------------------------------------------------------------------
    # Batch spawn (replaces old spawn_fire_spark)
    # -------------------------------------------------------------------------
    def batch_spawn_fire_sparks(self, count):
        """Spawn `count` sparks using vectorized numpy operations."""
        if count <= 0:
            return
        N = len(self.fire_spark_pos)
        idx_start = self.next_fire_spark_idx
        # wrap around if needed
        if idx_start + count > N:
            # spawn in two batches to avoid overflow; for simplicity limit to available
            count = min(count, N - idx_start)
        indices = np.arange(idx_start, idx_start + count, dtype=np.int32)
        self.next_fire_spark_idx = (idx_start + count) % N

        n = count
        # --- Position ---
        # Choose plume index (0,1,2) uniformly
        plume_choice = np.random.randint(0, 3, size=n).astype(np.int32)
        # plume centers (x,z)
        plume_centers_x = np.array([-0.11, 0.0, 0.11], dtype=np.float32)
        plume_centers_z = np.array([-0.04, 0.04, -0.04], dtype=np.float32)
        fx = plume_centers_x[plume_choice]
        fz = plume_centers_z[plume_choice]
        x = fx + np.random.uniform(-0.035, 0.035, size=n).astype(np.float32)
        z = fz + np.random.uniform(-0.035, 0.035, size=n).astype(np.float32)
        y = np.random.uniform(-0.84, -0.74, size=n).astype(np.float32)
        self.fire_spark_pos[indices] = np.column_stack([x, y, z])

        # --- Velocity ---
        theta = np.random.uniform(0.0, 2.0 * np.pi, size=n).astype(np.float32)
        phi = np.random.uniform(np.radians(15.0), np.radians(80.0), size=n).astype(np.float32)
        # Use average reaction for speed scaling (bass is most prominent)
        speed = np.random.uniform(0.12, 0.45, size=n).astype(np.float32) * (1.0 + self.react_bass * 0.4)
        sin_phi = np.sin(phi)
        cos_phi = np.cos(phi)
        vx = speed * sin_phi * np.sin(theta)
        vy = speed * cos_phi
        vz = speed * sin_phi * np.cos(theta)
        self.fire_spark_vel[indices] = np.column_stack([vx, vy, vz])

        # --- Size, color, life ---
        # 35% chance smoke (size negative)
        is_smoke = np.random.uniform(0.0, 1.0, size=n) < 0.35
        # For smoke, 40% chance columnar (narrow, fast)
        is_column = np.random.uniform(0.0, 1.0, size=n) < 0.40
        # Pre-allocate arrays
        size_arr = np.zeros(n, dtype=np.float32)
        col_arr = np.zeros((n, 4), dtype=np.float32)
        hue_arr = np.zeros(n, dtype=np.float32)
        max_life_arr = np.zeros(n, dtype=np.float32)

        # Smoke particles
        smoke_mask = is_smoke
        col_smoke = np.array([0.26, 0.27, 0.30], dtype=np.float32)  # base grey
        # columnar smoke
        col_mask = is_column & smoke_mask
        not_col_mask = (~is_column) & smoke_mask
        # columnar
        if np.any(col_mask):
            size_arr[col_mask] = -np.random.uniform(7.0, 15.0, size=np.sum(col_mask)).astype(np.float32) * (1.0 + self.react_bass * 0.2)
            col_arr[col_mask, :3] = np.array([0.23, 0.24, 0.26], dtype=np.float32)
            col_arr[col_mask, 3] = np.random.uniform(0.12, 0.30, size=np.sum(col_mask)).astype(np.float32)
            max_life_arr[col_mask] = np.random.uniform(3.5, 5.5, size=np.sum(col_mask)).astype(np.float32)
            hue_arr[col_mask] = -2.0
            # override velocity for columnar smoke (straight up)
            self.fire_spark_vel[indices[col_mask], 0] = np.random.uniform(-0.02, 0.02, size=np.sum(col_mask)).astype(np.float32)
            self.fire_spark_vel[indices[col_mask], 1] = np.random.uniform(0.65, 0.95, size=np.sum(col_mask)).astype(np.float32) * (1.0 + self.react_bass * 0.3)
            self.fire_spark_vel[indices[col_mask], 2] = np.random.uniform(-0.02, 0.02, size=np.sum(col_mask)).astype(np.float32)
        # non-columnar smoke
        if np.any(not_col_mask):
            size_arr[not_col_mask] = -np.random.uniform(8.0, 24.0, size=np.sum(not_col_mask)).astype(np.float32) * (1.0 + self.react_bass * 0.3)
            col_arr[not_col_mask, :3] = col_smoke
            col_arr[not_col_mask, 3] = np.random.uniform(0.10, 0.25, size=np.sum(not_col_mask)).astype(np.float32)
            max_life_arr[not_col_mask] = np.random.uniform(2.5, 4.8, size=np.sum(not_col_mask)).astype(np.float32)
            hue_arr[not_col_mask] = -1.0

        # Spark particles (non-smoke)
        spark_mask = ~smoke_mask
        if np.any(spark_mask):
            size_arr[spark_mask] = np.random.uniform(1.8, 4.5, size=np.sum(spark_mask)).astype(np.float32) * (1.0 + self.react_bass * 0.25)
            col_arr[spark_mask, :3] = np.array([1.0, 0.95, 0.65], dtype=np.float32)
            col_arr[spark_mask, 3] = np.random.uniform(0.75, 1.0, size=np.sum(spark_mask)).astype(np.float32)
            max_life_arr[spark_mask] = np.random.uniform(1.8, 3.8, size=np.sum(spark_mask)).astype(np.float32)
            hue_arr[spark_mask] = np.random.uniform(0.0, 1.0, size=np.sum(spark_mask)).astype(np.float32)

        # Assign to arrays
        self.fire_spark_size[indices] = size_arr
        self.fire_spark_col[indices] = col_arr
        self.fire_spark_hue[indices] = hue_arr
        self.fire_spark_life[indices] = max_life_arr
        self.fire_spark_max_life[indices] = max_life_arr
        self.fire_spark_active[indices] = True
        self.fire_spark_plume[indices] = plume_choice

    # -------------------------------------------------------------------------
    # Update
    # -------------------------------------------------------------------------
    def update_fire(self, dt):
        # Update lightning bolts
        active_bolts = []
        for bolt in self.fire_lightning_bolts:
            bolt['life'] -= dt
            if bolt['life'] > 0.0:
                active_bolts.append(bolt)
        self.fire_lightning_bolts = active_bolts

        # Update 3 independent wind gust variables
        for p in range(3):
            self.fire_wind_timers[p] += dt
            if self.fire_wind_timers[p] > np.random.uniform(4.0, 8.0):
                self.fire_wind_timers[p] = 0.0
                self.fire_wind_targets[p] = np.random.choice([-1.0, 1.0]) * np.random.uniform(0.6, 1.2)
            # Interpolate
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
            
            # PHYSICAL BOUNDARY CONTAINMENT
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
                    if gr2 > 0.0324: # 0.18 squared
                        scale = np.sqrt(0.0324 / gr2)
                        self.fire_spark_pos[real_idx, 0] *= scale
                        self.fire_spark_pos[real_idx, 2] *= scale
                        self.fire_spark_vel[real_idx, 0] *= -0.2
                        self.fire_spark_vel[real_idx, 2] *= -0.2
            
            # --- PHYSICAL AIR RESISTANCE & DRAFT FLUID DRAG ---
            self.fire_spark_vel[active_mask, 0] *= np.exp(-1.4 * dt)
            self.fire_spark_vel[active_mask, 1] *= np.exp(-1.0 * dt)
            self.fire_spark_vel[active_mask, 2] *= np.exp(-1.4 * dt)
            
            # --- CONVECTIVE DRIFT & SWIRLING EDDIES ---
            time_val = self.get_sim_time()
            y_pos = self.fire_spark_pos[active_mask, 1]
            x_pos = self.fire_spark_pos[active_mask, 0]
            z_pos = self.fire_spark_pos[active_mask, 2]
            
            # Distance from the 3 independent flame centers
            r2_left = (x_pos + 0.18)**2 + (z_pos + 0.05)**2
            r2_center = (x_pos)**2 + (z_pos - 0.05)**2
            r2_right = (x_pos - 0.18)**2 + (z_pos + 0.05)**2
            
            # 1. Thermal Heat Loft
            plume_factor = np.exp(-r2_left / 0.015) + np.exp(-r2_center / 0.015) + np.exp(-r2_right / 0.015)
            heat_loft = plume_factor * (0.24 + 0.12 * self.react_bass)
            self.fire_spark_pos[active_mask, 1] += heat_loft * dt
            
            # 2. Sideways Draft & Wind Sway
            crosswind = np.sin(time_val * 1.4 + y_pos * 1.2) * 0.045
            self.fire_spark_pos[active_mask, 0] += crosswind * dt
            
            # 3. Turbulent Swirling Eddies
            vortex_x = np.sin(time_val * 3.2 + y_pos * 2.5 + z_pos * 1.5) * 0.055
            vortex_z = np.cos(time_val * 2.8 + y_pos * 2.2 + x_pos * 1.5) * 0.055
            self.fire_spark_pos[active_mask, 0] += vortex_x * dt
            self.fire_spark_pos[active_mask, 2] += vortex_z * dt
            
            # --- 4. REAL-TIME WIND GUST FORCES ---
            height_factor = np.clip(y_pos - (-0.84), 0.0, 2.0)
            p_indices = self.fire_spark_plume[active_mask]
            # build gust array per particle
            gust_arr = np.array([self.fire_wind_gusts[p] for p in p_indices], dtype=np.float32)
            wind_push = gust_arr * 0.42 * height_factor * dt
            self.fire_spark_pos[active_mask, 0] += wind_push
            
            # Smoke extra push
            is_smoke_mask = self.fire_spark_size[active_mask] < 0.0
            smoke_extra_push = is_smoke_mask.astype(np.float32) * gust_arr * 0.18 * height_factor * dt
            self.fire_spark_pos[active_mask, 0] += smoke_extra_push
            
            # Decrease life
            self.fire_spark_life[active_mask] -= dt
            expired = self.fire_spark_life <= 0.0
            self.fire_spark_active[expired] = False
            
            # --- VECTORIZED COLOR UPDATE ---
            still_active = np.where(self.fire_spark_active)[0]
            if len(still_active) > 0:
                frac = self.fire_spark_life[still_active] / self.fire_spark_max_life[still_active]
                hue = self.fire_spark_hue[still_active]
                size = self.fire_spark_size[still_active]
                color_mode = getattr(self, 'opt_color_mode', 'REALISTIC')
                
                # Pre-allocate
                r = np.zeros_like(frac)
                g = np.zeros_like(frac)
                b = np.zeros_like(frac)
                alpha = np.zeros_like(frac)
                
                # Smoke particles (size < 0)
                smoke_mask = size < 0.0
                if np.any(smoke_mask):
                    r[smoke_mask] = 0.22
                    g[smoke_mask] = 0.23
                    b[smoke_mask] = 0.25
                    # expand size
                    self.fire_spark_size[still_active[smoke_mask]] -= np.random.uniform(5.5, 11.0, size=np.sum(smoke_mask)).astype(np.float32) * dt
                    shimmer = 0.85 + 0.15 * np.sin(time_val * np.random.uniform(5.0, 15.0, size=np.sum(smoke_mask)).astype(np.float32) + still_active[smoke_mask].astype(np.float32))
                    alpha[smoke_mask] = frac[smoke_mask] * shimmer * 0.22
                
                # Non-smoke particles
                non_smoke = ~smoke_mask
                if np.any(non_smoke):
                    hue_ns = hue[non_smoke]
                    frac_ns = frac[non_smoke]
                    # Compute base color based on color_mode
                    if color_mode == 'NEON':
                        # simplified neon mapping
                        r[non_smoke] = np.where(hue_ns < 0.30, 1.0 * frac_ns, np.where(hue_ns > 0.75, 0.0, 0.5 * frac_ns))
                        g[non_smoke] = np.where(hue_ns < 0.30, 0.0, np.where(hue_ns > 0.75, 1.0 * frac_ns, 0.0))
                        b[non_smoke] = np.where(hue_ns < 0.30, 0.5 + 0.5 * (1.0 - frac_ns), np.where(hue_ns > 0.75, 1.0, 1.0))
                    elif color_mode == 'TRANQUIL':
                        r[non_smoke] = np.where(hue_ns < 0.30, 0.0, np.where(hue_ns > 0.75, 0.5 * frac_ns, 0.1 * frac_ns))
                        g[non_smoke] = np.where(hue_ns < 0.30, 0.6 * (1.0 - frac_ns), np.where(hue_ns > 0.75, 0.2 * frac_ns, 0.7 * frac_ns))
                        b[non_smoke] = np.where(hue_ns < 0.30, 0.8, np.where(hue_ns > 0.75, 0.7, 0.4 + 0.4 * (1.0 - frac_ns)))
                    elif color_mode == 'METAL':
                        r[non_smoke] = np.where(hue_ns < 0.30, 0.8 * frac_ns, np.where(hue_ns > 0.75, 1.0, 0.9 * frac_ns + 0.1))
                        g[non_smoke] = np.where(hue_ns < 0.30, 0.5 * frac_ns * frac_ns, np.where(hue_ns > 0.75, 0.8 * frac_ns + 0.2, 0.9 * frac_ns + 0.1))
                        b[non_smoke] = np.where(hue_ns < 0.30, 0.2 * frac_ns * frac_ns, np.where(hue_ns > 0.75, 0.2 * frac_ns, 0.95 * frac_ns + 0.1))
                    else:  # REALISTIC
                        # simplified realistic cooling
                        r[non_smoke] = np.where(hue_ns < 0.30, 0.88 * frac_ns, np.where(hue_ns > 0.75, np.where(frac_ns > 0.75, 1.0, 1.0), np.where(frac_ns > 0.80, 1.0, np.where(frac_ns > 0.35, 0.98, 0.35 + 0.63 * (frac_ns / 0.35)))))
                        g[non_smoke] = np.where(hue_ns < 0.30, 0.14 * frac_ns * frac_ns, np.where(hue_ns > 0.75, np.where(frac_ns > 0.75, 0.90, 0.40 * (frac_ns / 0.75) + 0.50 * (frac_ns / 0.75)**2), np.where(frac_ns > 0.80, 0.75, np.where(frac_ns > 0.35, 0.28 + 0.47 * ((frac_ns - 0.35) / 0.45), 0.03 * (frac_ns / 0.35)))))
                        b[non_smoke] = np.where(hue_ns < 0.30, 0.02 * frac_ns * frac_ns * frac_ns, np.where(hue_ns > 0.75, np.where(frac_ns > 0.75, 0.50, 0.04 * (frac_ns / 0.75)), np.where(frac_ns > 0.80, 0.35, np.where(frac_ns > 0.35, 0.02 + 0.33 * ((frac_ns - 0.35) / 0.45), 0.01 * (frac_ns / 0.35)))))
                    
                    # Music modulation
                    bass = self.react_bass
                    treble = self.react_mid * 0.4 + self.react_treble * 0.6
                    r[non_smoke] = r[non_smoke] * (1.0 + treble * 0.2) + bass * 0.1
                    g[non_smoke] = g[non_smoke] * (1.0 - bass * 0.6) + treble * 0.3
                    b[non_smoke] = b[non_smoke] * (1.0 - bass * 0.8)
                    np.clip(r[non_smoke], 0, 1, out=r[non_smoke])
                    np.clip(g[non_smoke], 0, 1, out=g[non_smoke])
                    np.clip(b[non_smoke], 0, 1, out=b[non_smoke])
                    
                    # Shimmer and alpha
                    shimmer = 0.5 + 0.5 * np.sin(time_val * np.random.uniform(25.0, 45.0, size=np.sum(non_smoke)).astype(np.float32) + still_active[non_smoke].astype(np.float32))
                    music_pulse = 0.7 + bass * 0.4 + treble * 0.2
                    alpha[non_smoke] = np.clip(frac_ns * shimmer * music_pulse, 0.0, 1.0)
                
                # Assign colors
                self.fire_spark_col[still_active] = np.column_stack([r, g, b, alpha])
                
                # Trailers (optional, kept simple)
                opt_tr = getattr(self, 'opt_trailers', 0)
                if opt_tr > 0:
                    # only for non-smoke particles with enough life
                    trail_candidates = still_active[(size >= 0.0) & (self.fire_spark_max_life[still_active] > 0.5)]
                    if len(trail_candidates) > 0:
                        # random subset
                        n_trail = min(len(trail_candidates), int(opt_tr * 0.1))  # approximate
                        if n_trail > 0:
                            chosen = np.random.choice(trail_candidates, size=n_trail, replace=False)
                            for idx in chosen:
                                t_idx = self.next_fire_spark_idx
                                self.next_fire_spark_idx = (self.next_fire_spark_idx + 1) % len(self.fire_spark_pos)
                                self.fire_spark_pos[t_idx] = self.fire_spark_pos[idx].copy()
                                self.fire_spark_vel[t_idx] = self.fire_spark_vel[idx] * 0.15
                                self.fire_spark_size[t_idx] = self.fire_spark_size[idx] * 0.52
                                trail_life = np.random.uniform(0.12, 0.42)
                                self.fire_spark_life[t_idx] = trail_life
                                self.fire_spark_max_life[t_idx] = trail_life
                                self.fire_spark_col[t_idx] = [self.fire_spark_col[idx, 0], self.fire_spark_col[idx, 1], self.fire_spark_col[idx, 2], self.fire_spark_col[idx, 3] * 0.35]
                                self.fire_spark_hue[t_idx] = self.fire_spark_hue[idx]
                                self.fire_spark_active[t_idx] = True

        # --- Batch spawn based on music ---
        n_bass = int(self.react_bass * 8) if self.react_bass > 0.4 else 0
        n_mid  = int(self.react_mid * 6)  if self.react_mid > 0.4 else 0
        n_treb = int(self.react_treble * 6) if self.react_treble > 0.4 else 0
        total = n_bass + n_mid + n_treb
        if total > 0:
            self.batch_spawn_fire_sparks(total)

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
