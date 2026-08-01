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
        self.fire_spark_hue = np.zeros(N_sparks, dtype=np.float32)  # For beautiful individual color variations
        self.fire_spark_plume = np.zeros(N_sparks, dtype=np.int32)  # Tracks which of the 3 independent flames a particle belongs to
        self.next_fire_spark_idx = 0

        # Flame algorithm selection:
        # 0 = Current (original 3-plume noise-based campfire)
        # 1 = Gas Jet (intense, focused, blue-white core)
        # 2 = Bonfire (wide, roaring, red/orange dominant)
        # 3 = Candle (steady, tall, narrow, warm yellow)
        # 4 = Vortex (swirling, tornado-like flame with helical motion)
        # 5 = Game-style (modern adaptive heat haze + edge glow)
        # 6 = Multi (5 vortex plumes, independent flicker, spatial reactivity)
        self.fire_flame_algorithm = 6   # Multi is the default
        self.fire_flame_names = ["Current", "Gas Jet", "Bonfire", "Candle", "Vortex", "Game", "Multi"]

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

    def spawn_flame_current(self, count):
        """Same as existing batch_spawn_fire_sparks (call it directly)"""
        self.batch_spawn_fire_sparks(count)

    def spawn_flame_candle(self, count):
        """Tall, dense candle flame core: much larger bright yellow particles, almost no smoke."""
        if count <= 0:
            return
        N = len(self.fire_spark_pos)
        idx_start = self.next_fire_spark_idx
        if idx_start + count > N:
            count = min(count, N - idx_start)
        indices = np.arange(idx_start, idx_start + count, dtype=np.int32)
        self.next_fire_spark_idx = (idx_start + count) % N
        n = count

        # Slightly tighter base and lower starting Y to give a tall appearance
        x = np.random.uniform(-0.008, 0.008, size=n).astype(np.float32)
        z = np.random.uniform(-0.008, 0.008, size=n).astype(np.float32)
        y = np.random.uniform(-0.86, -0.74, size=n).astype(np.float32)
        self.fire_spark_pos[indices] = np.column_stack([x, y, z])

        # Increased upward velocity and very narrow spread for a tall candle core
        theta = np.random.uniform(-0.06, 0.06, size=n).astype(np.float32)
        phi = np.random.uniform(np.radians(80), np.radians(89), size=n).astype(np.float32)
        speed = np.random.uniform(0.9, 1.6, size=n).astype(np.float32) * (1.0 + self.react_bass * 0.4)
        sin_phi = np.sin(phi)
        cos_phi = np.cos(phi)
        vx = speed * sin_phi * np.sin(theta)
        vy = speed * cos_phi
        vz = speed * sin_phi * np.cos(theta)
        self.fire_spark_vel[indices] = np.column_stack([vx, vy, vz])

        # Very little smoke for candle (2%)
        is_smoke = np.random.uniform(0.0, 1.0, size=n) < 0.02
        size_arr = np.zeros(n, dtype=np.float32)
        col_arr = np.zeros((n, 4), dtype=np.float32)
        hue_arr = np.zeros(n, dtype=np.float32)
        max_life_arr = np.zeros(n, dtype=np.float32)

        # Smoke particles keep original look
        if np.any(is_smoke):
            cnt = np.sum(is_smoke)
            size_arr[is_smoke] = -np.random.uniform(4.0, 8.0, size=cnt).astype(np.float32)
            col_arr[is_smoke, :3] = np.array([0.18, 0.18, 0.20], dtype=np.float32)
            col_arr[is_smoke, 3] = np.random.uniform(0.06, 0.14, size=cnt).astype(np.float32)
            max_life_arr[is_smoke] = np.random.uniform(2.5, 4.0, size=cnt).astype(np.float32)
            hue_arr[is_smoke] = -1.0

        # Candle core sparks: large, bright, highly opaque yellow
        spark_mask = ~is_smoke
        if np.any(spark_mask):
            cnt = np.sum(spark_mask)
            size_arr[spark_mask] = np.random.uniform(4.0, 8.0, size=cnt).astype(np.float32)
            col_arr[spark_mask, :3] = np.array([1.0, 0.95, 0.4], dtype=np.float32)
            col_arr[spark_mask, 3] = 1.0
            max_life_arr[spark_mask] = np.random.uniform(2.0, 4.0, size=cnt).astype(np.float32)
            hue_arr[spark_mask] = np.random.uniform(0.05, 0.12, size=cnt).astype(np.float32)

        self.fire_spark_size[indices] = size_arr
        self.fire_spark_col[indices] = col_arr
        self.fire_spark_hue[indices] = hue_arr
        self.fire_spark_life[indices] = max_life_arr
        self.fire_spark_max_life[indices] = max_life_arr
        self.fire_spark_active[indices] = True
        # center plume for candle
        self.fire_spark_plume[indices] = 1

    def spawn_flame_bonfire(self, count):
        """Wide chaotic bonfire core: larger deep-red embers while keeping smoke behavior intact."""
        if count <= 0:
            return
        N = len(self.fire_spark_pos)
        idx_start = self.next_fire_spark_idx
        if idx_start + count > N:
            count = min(count, N - idx_start)
        indices = np.arange(idx_start, idx_start + count, dtype=np.int32)
        self.next_fire_spark_idx = (idx_start + count) % N
        n = count

        # Very wide spread to create a big bonfire silhouette
        x = np.random.uniform(-0.5, 0.5, size=n).astype(np.float32)
        z = np.random.uniform(-0.5, 0.5, size=n).astype(np.float32)
        y = np.random.uniform(-0.84, -0.60, size=n).astype(np.float32)
        self.fire_spark_pos[indices] = np.column_stack([x, y, z])

        # Wide-angle emission and higher speeds to fling big embers outward
        theta = np.random.uniform(0.0, 2.0 * np.pi, size=n).astype(np.float32)
        phi = np.random.uniform(np.radians(8), np.radians(75), size=n).astype(np.float32)
        speed = np.random.uniform(0.6, 1.6, size=n).astype(np.float32) * (1.0 + self.react_bass * 0.8)
        sin_phi = np.sin(phi)
        cos_phi = np.cos(phi)
        vx = speed * sin_phi * np.sin(theta)
        vy = speed * cos_phi
        vz = speed * sin_phi * np.cos(theta)
        self.fire_spark_vel[indices] = np.column_stack([vx, vy, vz])

        # Smoke fraction kept as original behavior
        is_smoke = np.random.uniform(0.0, 1.0, size=n) < 0.40
        size_arr = np.zeros(n, dtype=np.float32)
        col_arr = np.zeros((n, 4), dtype=np.float32)
        hue_arr = np.zeros(n, dtype=np.float32)
        max_life_arr = np.zeros(n, dtype=np.float32)

        # Smoke: large, dark, long-lived (unchanged)
        if np.any(is_smoke):
            cnt = np.sum(is_smoke)
            size_arr[is_smoke] = -np.random.uniform(8.0, 26.0, size=cnt).astype(np.float32)
            col_arr[is_smoke, :3] = np.array([0.22, 0.22, 0.25], dtype=np.float32)
            col_arr[is_smoke, 3] = np.random.uniform(0.12, 0.36, size=cnt).astype(np.float32)
            max_life_arr[is_smoke] = np.random.uniform(3.0, 6.0, size=cnt).astype(np.float32)
            hue_arr[is_smoke] = -1.0

        # Bonfire embers/core: much larger and deep red/orange
        spark_mask = ~is_smoke
        if np.any(spark_mask):
            cnt = np.sum(spark_mask)
            size_arr[spark_mask] = np.random.uniform(6.0, 12.0, size=cnt).astype(np.float32) * (1.0 + self.react_bass * 0.3)
            col_arr[spark_mask, :3] = np.array([1.0, 0.20, 0.0], dtype=np.float32)
            col_arr[spark_mask, 3] = np.random.uniform(0.85, 1.0, size=cnt).astype(np.float32)
            max_life_arr[spark_mask] = np.random.uniform(2.0, 4.0, size=cnt).astype(np.float32)
            hue_arr[spark_mask] = np.random.uniform(0.0, 0.15, size=cnt).astype(np.float32)

        self.fire_spark_size[indices] = size_arr
        self.fire_spark_col[indices] = col_arr
        self.fire_spark_hue[indices] = hue_arr
        self.fire_spark_life[indices] = max_life_arr
        self.fire_spark_max_life[indices] = max_life_arr
        self.fire_spark_active[indices] = True
        self.fire_spark_plume[indices] = np.random.randint(0, 3, size=n).astype(np.int32)

    def spawn_flame_gas_jet(self, count):
        """Intense gas jet core: larger bright blue/white particles, very high upward speed."""
        if count <= 0:
            return
        N = len(self.fire_spark_pos)
        idx_start = self.next_fire_spark_idx
        if idx_start + count > N:
            count = min(count, N - idx_start)
        indices = np.arange(idx_start, idx_start + count, dtype=np.int32)
        self.next_fire_spark_idx = (idx_start + count) % N
        n = count

        # Very tight cluster around the nozzle
        x = np.random.uniform(-0.02, 0.02, size=n).astype(np.float32)
        z = np.random.uniform(-0.02, 0.02, size=n).astype(np.float32)
        y = np.random.uniform(-0.84, -0.80, size=n).astype(np.float32)
        self.fire_spark_pos[indices] = np.column_stack([x, y, z])

        # Very high upward velocity, even narrower cone to make a jet-like appearance
        theta = np.random.uniform(-0.04, 0.04, size=n).astype(np.float32)
        phi = np.random.uniform(np.radians(86), np.radians(89), size=n).astype(np.float32)
        speed = np.random.uniform(1.6, 3.2, size=n).astype(np.float32) * (1.0 + self.react_bass * 0.6)
        sin_phi = np.sin(phi)
        cos_phi = np.cos(phi)
        vx = speed * sin_phi * np.sin(theta)
        vy = speed * cos_phi
        vz = speed * sin_phi * np.cos(theta)
        self.fire_spark_vel[indices] = np.column_stack([vx, vy, vz])

        # Almost no smoke for gas jet; primarily bright blue/white sparks (1% smoke)
        is_smoke = np.random.uniform(0.0, 1.0, size=n) < 0.01
        size_arr = np.zeros(n, dtype=np.float32)
        col_arr = np.zeros((n, 4), dtype=np.float32)
        hue_arr = np.zeros(n, dtype=np.float32)
        max_life_arr = np.zeros(n, dtype=np.float32)

        # Tiny faint smoke (unchanged style)
        if np.any(is_smoke):
            cnt = np.sum(is_smoke)
            size_arr[is_smoke] = -np.random.uniform(4.0, 8.0, size=cnt).astype(np.float32)
            col_arr[is_smoke, :3] = np.array([0.15, 0.15, 0.18], dtype=np.float32)
            col_arr[is_smoke, 3] = np.random.uniform(0.05, 0.12, size=cnt).astype(np.float32)
            max_life_arr[is_smoke] = np.random.uniform(2.0, 3.0, size=cnt).astype(np.float32)
            hue_arr[is_smoke] = -1.0

        # Jet core: larger bright blue/white particles
        spark_mask = ~is_smoke
        if np.any(spark_mask):
            cnt = np.sum(spark_mask)
            size_arr[spark_mask] = np.random.uniform(3.0, 6.0, size=cnt).astype(np.float32)
            col_arr[spark_mask, :3] = np.array([0.5, 0.8, 1.0], dtype=np.float32)
            col_arr[spark_mask, 3] = np.random.uniform(0.95, 1.0, size=cnt).astype(np.float32)
            max_life_arr[spark_mask] = np.random.uniform(1.5, 3.0, size=cnt).astype(np.float32)
            hue_arr[spark_mask] = np.random.uniform(0.55, 0.65, size=cnt).astype(np.float32)

        self.fire_spark_size[indices] = size_arr
        self.fire_spark_col[indices] = col_arr
        self.fire_spark_hue[indices] = hue_arr
        self.fire_spark_life[indices] = max_life_arr
        self.fire_spark_max_life[indices] = max_life_arr
        self.fire_spark_active[indices] = True
        self.fire_spark_plume[indices] = 1

    # ---------------------------
    # Algorithm 1: Fluid Advection (Lite)
    # ---------------------------
    def _init_fluid_advection(self):
        # Small 2D CPU grid controlling temperature/density/vel that spawns particles
        Gx, Gy = 28, 14
        state = {}
        state['Gx'] = Gx
        state['Gy'] = Gy
        state['temp'] = np.zeros((Gy, Gx), dtype=np.float32)
        state['dens'] = np.zeros((Gy, Gx), dtype=np.float32)
        # simple velocity field (x,y)
        state['vx'] = np.zeros((Gy, Gx), dtype=np.float32)
        state['vy'] = np.zeros((Gy, Gx), dtype=np.float32)
        state['time'] = 0.0
        self._fire_algo_fluid = state

    def _update_fluid_advection(self, dt):
        s = self._fire_algo_fluid
        if s is None:
            self._init_fluid_advection()
            s = self._fire_algo_fluid

        s['time'] += dt
        Gx, Gy = s['Gx'], s['Gy']

        # Heat source near center-bottom
        cx = Gx // 2
        for dx in (-1, 0, 1):
            x = cx + dx
            if 0 <= x < Gx:
                s['temp'][-2, x] += 30.0 * dt  # hearth boost

        # Simple upward advection: roll temperature upward and mix
        s['temp'] = 0.92 * s['temp'] + 0.08 * np.roll(s['temp'], -1, axis=0)

        # Diffuse / cool
        s['temp'] *= np.exp(-0.6 * dt)
        s['dens'] = np.clip(s['temp'] * 0.06, 0.0, 1.0)

        # Compute velocity from temperature gradient (buoyancy)
        grad_y = np.diff(s['temp'], axis=0, append=s['temp'][-1:, :])
        s['vy'] = np.clip(0.5 * grad_y, -1.0, 3.0)
        s['vx'] = np.tile(np.sin((np.arange(Gx) + s['time'] * 3.0) * 0.3) * 0.02, (Gy, 1))

        # Spawn particles from hot cells
        hot_cells = np.argwhere(s['temp'] > 1.0)
        if hot_cells.size == 0:
            return

        spawn_budget = min(120, int(len(hot_cells) * 1.6))
        picks = hot_cells[np.random.choice(len(hot_cells), spawn_budget, replace=True)]
        N = len(picks)
        if N == 0:
            return

        # Map grid coords to world-space around nozzle center
        gx = picks[:, 1].astype(np.float32)
        gy = picks[:, 0].astype(np.float32)
        x_world = (gx / (Gx - 1) - 0.5) * 0.9  # horizontal spread
        y_world = -0.86 + (gy / (Gy - 1)) * 0.32  # from -0.86 -> -0.54
        z_world = np.random.uniform(-0.06, 0.06, size=N).astype(np.float32)

        # Velocity from local vy + jitter
        vy_local = s['vy'][picks[:, 0], picks[:, 1]]
        vx_local = s['vx'][picks[:, 0], picks[:, 1]]
        speed_up = np.clip(0.6 + vy_local * 0.6, 0.08, 2.4)
        vx = vx_local + np.random.uniform(-0.06, 0.06, size=N).astype(np.float32)
        vy = speed_up + np.random.uniform(-0.08, 0.12, size=N).astype(np.float32)
        vz = np.random.uniform(-0.04, 0.04, size=N).astype(np.float32)

        # Sizes and colors: hotter -> brighter small sparks; cooler -> smoke (negative size)
        temps = s['temp'][picks[:, 0], picks[:, 1]]
        is_smoke = temps < 2.2
        sizes = np.where(is_smoke, -np.random.uniform(6.0, 18.0, size=N).astype(np.float32),
                         np.random.uniform(2.0, 6.0, size=N).astype(np.float32))
        cols = np.zeros((N, 4), dtype=np.float32)
        cols[~is_smoke, :3] = np.stack([np.clip(1.0 - (temps[~is_smoke] * 0.05), 0.5, 1.0),
                                        np.clip(0.85 - (temps[~is_smoke] * 0.03), 0.4, 1.0),
                                        0.45 * np.ones(np.sum(~is_smoke))], axis=1)
        cols[~is_smoke, 3] = np.clip(0.7 + temps[~is_smoke] * 0.06, 0.45, 1.0)
        cols[is_smoke, :3] = 0.22
        cols[is_smoke, 3] = np.random.uniform(0.08, 0.28, size=np.sum(is_smoke)).astype(np.float32)

        # Vectorized assignment into particle arrays
        N_total = len(self.fire_spark_pos)
        idx = np.arange(self.next_fire_spark_idx, self.next_fire_spark_idx + N, dtype=np.int32) % N_total
        self.next_fire_spark_idx = (self.next_fire_spark_idx + N) % N_total

        self.fire_spark_pos[idx, 0] = x_world
        self.fire_spark_pos[idx, 1] = y_world
        self.fire_spark_pos[idx, 2] = z_world
        self.fire_spark_vel[idx, 0] = vx
        self.fire_spark_vel[idx, 1] = vy
        self.fire_spark_vel[idx, 2] = vz
        self.fire_spark_size[idx] = sizes
        self.fire_spark_col[idx] = cols
        self.fire_spark_hue[idx] = np.random.uniform(0.0, 1.0, size=N).astype(np.float32)
        self.fire_spark_life[idx] = np.random.uniform(1.0, 3.5, size=N).astype(np.float32)
        self.fire_spark_max_life[idx] = self.fire_spark_life[idx].copy()
        self.fire_spark_active[idx] = True

    # ---------------------------
    # Algorithm 2: Cellular Automata (Fuel/Burning/Ember/Ash)
    # ---------------------------
    def _init_cellular_automata(self):
        Wx, Wy = 36, 18
        state = {}
        state['Wx'] = Wx
        state['Wy'] = Wy
        # 0=EMPTY,1=FUEL,2=BURNING,3=EMBER,4=ASH
        state['cells'] = np.zeros((Wy, Wx), dtype=np.int32)
        state['timer'] = np.zeros((Wy, Wx), dtype=np.float32)
        # initialize a ring of fuel near the center bottom
        cx = Wx // 2
        for x in range(Wx):
            if abs(x - cx) < Wx * 0.25:
                state['cells'][-2, x] = 1
                state['cells'][-3, x] = 1
        self._fire_algo_ca = state

    def _update_cellular_automata(self, dt):
        s = self._fire_algo_ca
        if s is None:
            self._init_cellular_automata()
            s = self._fire_algo_ca

        cells = s['cells']
        timer = s['timer']
        Wy, Wx = s['Wy'], s['Wx']

        # Random ignition seeds
        if np.random.uniform() < 0.06:
            x = np.random.randint(Wx//2 - 3, Wx//2 + 3)
            cells[-2, x] = 2
            timer[-2, x] = 0.0

        # Spread rules
        new_cells = cells.copy()
        new_timer = timer.copy()
        for y in range(Wy):
            for x in range(Wx):
                state = cells[y, x]
                if state == 1 and np.any(cells[max(0, y-1):min(Wy, y+2), max(0, x-1):min(Wx, x+2)] == 2):
                    # neighbor burning can ignite fuel
                    if np.random.uniform() < 0.25:
                        new_cells[y, x] = 2
                        new_timer[y, x] = 0.0
                elif state == 2:
                    # burning ages into ember
                    new_timer[y, x] += dt
                    if new_timer[y, x] > 0.18 + np.random.uniform(0.0, 0.12):
                        new_cells[y, x] = 3
                        new_timer[y, x] = 0.0
                elif state == 3:
                    # ember -> ash
                    new_timer[y, x] += dt
                    if new_timer[y, x] > 0.9 + np.random.uniform(0.0, 0.8):
                        new_cells[y, x] = 4
                        new_timer[y, x] = 0.0
                elif state == 4:
                    # ash slowly falls / disappears
                    if np.random.uniform() < 0.002:
                        new_cells[y, x] = 0

        s['cells'] = new_cells
        s['timer'] = new_timer

        # Spawn particles at burning and ember cells
        burning = np.argwhere(new_cells == 2)
        ember = np.argwhere(new_cells == 3)
        total_spawn = min(160, len(burning) * 3 + len(ember) * 2)
        if total_spawn == 0:
            return

        picks_b = burning[np.random.choice(len(burning), min(len(burning), total_spawn), replace=True)] if len(burning) > 0 else np.empty((0,2),dtype=int)
        picks_e = ember[np.random.choice(len(ember), max(0, total_spawn - len(picks_b)), replace=True)] if len(ember) > 0 else np.empty((0,2),dtype=int)
        picks = np.vstack([picks_b, picks_e]) if picks_b.size or picks_e.size else np.empty((0,2),dtype=int)
        if picks.size == 0:
            return

        N = len(picks)
        # Map picks to world coordinates
        gx = picks[:,1].astype(np.float32)
        gy = picks[:,0].astype(np.float32)
        x_world = (gx / (Wx - 1) - 0.5) * 1.0
        y_world = -0.86 + (gy / (Wy - 1)) * 0.32
        z_world = np.random.uniform(-0.08, 0.08, size=N).astype(np.float32)
        # velocity: burning stronger upward
        is_burning_vec = np.array([1 if new_cells[p[0],p[1]]==2 else 0 for p in picks], dtype=np.float32)
        vy = 0.7 + is_burning_vec * 1.0 + np.random.uniform(-0.08, 0.22, size=N).astype(np.float32)
        vx = np.random.uniform(-0.14, 0.14, size=N).astype(np.float32)
        vz = np.random.uniform(-0.06, 0.06, size=N).astype(np.float32)

        sizes = np.where(is_burning_vec==1, np.random.uniform(3.0, 7.0, size=N).astype(np.float32),
                         -np.random.uniform(6.0, 18.0, size=N).astype(np.float32))

        cols = np.zeros((N,4), dtype=np.float32)
        cols[is_burning_vec==1, :3] = np.stack([1.0 - 0.05*np.random.rand(np.sum(is_burning_vec==1)),
                                               0.82 - 0.08*np.random.rand(np.sum(is_burning_vec==1)),
                                               0.4*np.ones(np.sum(is_burning_vec==1))], axis=1)
        cols[is_burning_vec==1, 3] = 0.7 + 0.2 * np.random.rand(np.sum(is_burning_vec==1))
        cols[is_burning_vec==0, :3] = 0.22
        cols[is_burning_vec==0, 3] = 0.06 + 0.18 * np.random.rand(np.sum(is_burning_vec==0))

        # Write into particle arrays
        N_total = len(self.fire_spark_pos)
        idx = np.arange(self.next_fire_spark_idx, self.next_fire_spark_idx + N, dtype=np.int32) % N_total
        self.next_fire_spark_idx = (self.next_fire_spark_idx + N) % N_total

        self.fire_spark_pos[idx, 0] = x_world
        self.fire_spark_pos[idx, 1] = y_world
        self.fire_spark_pos[idx, 2] = z_world
        self.fire_spark_vel[idx, 0] = vx
        self.fire_spark_vel[idx, 1] = vy
        self.fire_spark_vel[idx, 2] = vz
        self.fire_spark_size[idx] = sizes
        self.fire_spark_col[idx] = cols
        self.fire_spark_hue[idx] = np.random.uniform(0.0, 1.0, size=N).astype(np.float32)
        self.fire_spark_life[idx] = np.random.uniform(1.2, 3.8, size=N).astype(np.float32)
        self.fire_spark_max_life[idx] = self.fire_spark_life[idx].copy()
        self.fire_spark_active[idx] = True

    # ---------------------------
    # Algorithm 3: Noise-Driven Flames (multi-octave procedural noise)
    # ---------------------------
    def _init_noise_driven(self):
        state = {}
        state['seed'] = np.random.randint(0, 10000)
        state['time'] = 0.0
        state['scale'] = 2.4
        state['octaves'] = 3
        state['threshold'] = 0.48
        self._fire_algo_noise = state

    def _value_noise(self, x, y, seed=0):
        # cheap hash-based pseudo noise (not Perlin, but good enough and fast)
        n = (x * 374761393 + y * 668265263 + seed * 0x9e3779b97f4a7c15) & 0xFFFFFFFF
        n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
        return ((n >> 16) & 0xFFFF) / 65535.0

    def _fractal_noise(self, x, y, state):
        val = 0.0
        amp = 1.0
        freq = 1.0
        for o in range(state['octaves']):
            vx = x * freq
            vy = y * freq
            val += amp * self._value_noise(int(vx + state['seed']), int(vy + state['seed']), state['seed'])
            freq *= 2.1
            amp *= 0.55
        return val

    def _update_noise_driven(self, dt):
        s = self._fire_algo_noise
        if s is None:
            self._init_noise_driven()
            s = self._fire_algo_noise

        s['time'] += dt * 0.9
        # sample several points above the nozzle
        sample_count = 160 + int(self.react_bass * 80)
        xs = np.random.uniform(-0.6, 0.6, size=sample_count).astype(np.float32)
        ys = np.random.uniform(-0.86, -0.46, size=sample_count).astype(np.float32)
        zs = np.random.uniform(-0.12, 0.12, size=sample_count).astype(np.float32)

        # compute noise intensity per sample
        coords_x = xs * s['scale'] + s['time'] * 0.6
        coords_y = (ys + 1.0) * s['scale']
        intens = np.array([self._fractal_noise(cx * 10.0, cy * 10.0, s) for cx, cy in zip(coords_x, coords_y)], dtype=np.float32)
        # normalize
        intens = (intens - intens.min()) / max(1e-6, (intens.max() - intens.min()))
        mask = intens > s['threshold']
        if not np.any(mask):
            return
        sel = np.where(mask)[0]
        N = len(sel)
        idx = np.arange(self.next_fire_spark_idx, self.next_fire_spark_idx + N, dtype=np.int32) % len(self.fire_spark_pos)
        self.next_fire_spark_idx = (self.next_fire_spark_idx + N) % len(self.fire_spark_pos)

        x_world = xs[sel]
        y_world = ys[sel]
        z_world = zs[sel]
        base_speed = 0.6 + intens[sel] * 1.4
        jitter = np.random.uniform(-0.08, 0.08, size=N).astype(np.float32)
        vx = jitter * 0.6
        vy = base_speed + np.random.uniform(-0.08, 0.18, size=N).astype(np.float32)
        vz = np.random.uniform(-0.04, 0.04, size=N).astype(np.float32)

        sizes = np.where(intens[sel] > 0.75, np.random.uniform(3.0, 8.0, size=N).astype(np.float32),
                         np.random.uniform(1.2, 3.2, size=N).astype(np.float32))
        smoke_mask = intens[sel] < 0.55
        sizes[smoke_mask] *= -np.random.uniform(2.0, 6.0, size=np.sum(smoke_mask))

        cols = np.zeros((N,4), dtype=np.float32)
        cols[:, :3] = np.stack([np.clip(0.9 + intens[sel]*0.1, 0.2, 1.0),
                                np.clip(0.7 + intens[sel]*0.2, 0.1, 1.0),
                                np.clip(0.3 + (1.0 - intens[sel])*0.4, 0.0, 1.0)], axis=1)
        cols[:, 3] = np.clip(0.5 + intens[sel]*0.6, 0.05, 1.0)

        self.fire_spark_pos[idx, 0] = x_world
        self.fire_spark_pos[idx, 1] = y_world
        self.fire_spark_pos[idx, 2] = z_world
        self.fire_spark_vel[idx, 0] = vx
        self.fire_spark_vel[idx, 1] = vy
        self.fire_spark_vel[idx, 2] = vz
        self.fire_spark_size[idx] = sizes
        self.fire_spark_col[idx] = cols
        self.fire_spark_hue[idx] = np.random.uniform(0.0, 1.0, size=N).astype(np.float32)
        self.fire_spark_life[idx] = np.random.uniform(0.8, 3.4, size=N).astype(np.float32)
        self.fire_spark_max_life[idx] = self.fire_spark_life[idx].copy()
        self.fire_spark_active[idx] = True

    # ---------------------------
    # Algorithm 4: Vortex / Swirl (interacting vortex rings)
    # ---------------------------
    def _init_vortex_swirl(self):
        # vortex list: each vortex is dict {cx, cy, radius, strength, rise_speed}
        vortices = []
        for i in range(3):
            vortices.append({
                'cx': np.random.uniform(-0.06, 0.06),
                'cy': -0.75 - i * 0.02,
                'radius': 0.08 + 0.02 * i,
                'strength': 0.6 + 0.6 * np.random.uniform(),
                'rise': 0.02 + 0.01 * i,
                'phase': np.random.uniform(0.0, 2*np.pi)
            })
        state = {'vortices': vortices, 'time': 0.0}
        self._fire_algo_vortex = state

    def _update_vortex_swirl(self, dt):
        s = self._fire_algo_vortex
        if s is None:
            self._init_vortex_swirl()
            s = self._fire_algo_vortex

        s['time'] += dt
        vort = s['vortices']

        # gently evolve vortices
        for v in vort:
            v['phase'] += dt * (0.8 + 0.5 * np.random.uniform())
            v['cy'] += v['rise'] * dt
            v['radius'] *= 1.0 + 0.02 * (np.sin(s['time'] * 0.6 + v['phase']) * dt)
            # occasional strength modulation
            v['strength'] *= 0.999 + 0.002 * (np.random.uniform() - 0.5)

        # spawn particles along vortex cores
        spawn_per_v = 60
        pieces = []
        for v in vort:
            thetas = np.linspace(0, 2*np.pi, spawn_per_v, endpoint=False) + np.random.uniform(0.0, 0.4)
            xs = v['cx'] + v['radius'] * np.cos(thetas) + np.random.uniform(-0.01, 0.01, size=spawn_per_v)
            ys = v['cy'] + v['radius'] * np.sin(thetas) + np.random.uniform(-0.01, 0.01, size=spawn_per_v)
            zs = np.random.uniform(-0.06, 0.06, size=spawn_per_v)
            strengths = v['strength'] * (0.6 + 0.8 * np.abs(np.sin(thetas + v['phase'])))
            pieces.append((xs.astype(np.float32), ys.astype(np.float32), zs.astype(np.float32), strengths.astype(np.float32)))

        all_x = np.concatenate([p[0] for p in pieces]).astype(np.float32)
        all_y = np.concatenate([p[1] for p in pieces]).astype(np.float32)
        all_z = np.concatenate([p[2] for p in pieces]).astype(np.float32)
        all_s = np.concatenate([p[3] for p in pieces]).astype(np.float32)
        N = len(all_x)
        if N == 0:
            return

        # compute swirling velocity: tangential + upward
        vx = - (all_s * np.sin(np.linspace(0, 2*np.pi, N, endpoint=False))).astype(np.float32) * 0.4 + np.random.uniform(-0.06, 0.06, size=N).astype(np.float32)
        vy = (0.6 + all_s * 1.3 + np.random.uniform(-0.1, 0.2, size=N)).astype(np.float32)
        vz = (all_s * np.cos(np.linspace(0, 2*np.pi, N, endpoint=False)) * 0.4 + np.random.uniform(-0.06, 0.06, size=N)).astype(np.float32)

        sizes = np.random.uniform(2.0, 8.0, size=N).astype(np.float32)
        # a fraction are smoke (larger negative sizes)
        smoke_mask = np.random.uniform(0.0, 1.0, size=N) < 0.22
        sizes[smoke_mask] *= -np.random.uniform(2.0, 3.6, size=np.sum(smoke_mask))

        cols = np.zeros((N,4), dtype=np.float32)
        cols[:, :3] = np.stack([np.clip(0.9 - all_s*0.25, 0.2, 1.0),
                                np.clip(0.6 - all_s*0.18, 0.05, 1.0),
                                np.clip(0.35 + all_s*0.25, 0.0, 1.0)], axis=1)
        cols[:, 3] = np.clip(0.5 + all_s*0.45, 0.04, 1.0)

        # write into particle buffers (vectorized)
        N_total = len(self.fire_spark_pos)
        idx = np.arange(self.next_fire_spark_idx, self.next_fire_spark_idx + N, dtype=np.int32) % N_total
        self.next_fire_spark_idx = (self.next_fire_spark_idx + N) % N_total

        self.fire_spark_pos[idx, 0] = all_x
        self.fire_spark_pos[idx, 1] = all_y
        self.fire_spark_pos[idx, 2] = all_z
        self.fire_spark_vel[idx, 0] = vx
        self.fire_spark_vel[idx, 1] = vy
        self.fire_spark_vel[idx, 2] = vz
        self.fire_spark_size[idx] = sizes
        self.fire_spark_col[idx] = cols
        self.fire_spark_hue[idx] = np.random.uniform(0.0, 1.0, size=N).astype(np.float32)
        self.fire_spark_life[idx] = np.random.uniform(1.2, 4.0, size=N).astype(np.float32)
        self.fire_spark_max_life[idx] = self.fire_spark_life[idx].copy()
        self.fire_spark_active[idx] = True

    def cycle_flame_algorithm(self):
        # Rotate flame algorithm index and clear particles so the shader-only change is visible.
        self.fire_flame_algorithm = (self.fire_flame_algorithm + 1) % len(self.fire_flame_names)
        print(f"Flame algorithm: {self.fire_flame_names[self.fire_flame_algorithm]}")
        if hasattr(self, 'fire_spark_active'):
            self.fire_spark_active[:] = False

        # Spawn a visible burst using the standard particle spawner (same behavior for all algorithms).
        burst_count = min(1000, len(self.fire_spark_pos))
        if burst_count > 0:
            self.batch_spawn_fire_sparks(burst_count)

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

        # --- Always use the same particle spawning (smoke/sparks unchanged) ---
        n_bass = int(self.react_bass * 4) + 1
        n_mid  = int(self.react_mid * 3)  + 1
        n_treb = int(self.react_treble * 3) + 1
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
