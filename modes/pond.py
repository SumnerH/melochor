import numpy as np


class PondModeMixin:
    """Music-reactive evening pond rendered in a flat, full-screen playfield."""

    def init_pond_mode(self):
        self.pond_rain = []
        self.pond_ripples = []
        self.pond_shader_ripples = []
        self.pond_leaves = []
        self.pond_lightning = []
        self.pond_fish = None
        self.pond_leaf_vortex_timer = 0.0
        self.pond_leaf_vortex_center_x = 0.0
        self.pond_lightning_timer = 0.0
        self.pond_rain_spawn_accumulator = 0.0

        # Distant birds use a conventional boids flock. Keep their starting
        # formation compact enough to read as a flock, but spaced apart enough
        # that the small silhouettes never merge into a single large shape.
        self.pond_bird_count = 14
        flock_center = np.array([
            np.random.uniform(-0.45, 0.45),
            np.random.uniform(0.38, 0.66),
        ], dtype=np.float32)
        self.pond_bird_pos = flock_center + np.random.normal(
            0.0, [0.16, 0.09], (self.pond_bird_count, 2)
        ).astype(np.float32)
        flock_heading = np.full(
            self.pond_bird_count,
            np.random.choice((0.0, np.pi)),
            dtype=np.float32,
        ) + np.random.uniform(-0.24, 0.24, self.pond_bird_count)
        self.pond_bird_vel = np.column_stack((
            np.cos(flock_heading),
            np.sin(flock_heading),
        )).astype(np.float32) * np.random.uniform(
            0.115, 0.155, (self.pond_bird_count, 1)
        ).astype(np.float32)
        self.pond_bird_heading = flock_heading.astype(np.float32)
        self.pond_bird_phase = np.random.uniform(
            0.0, 2.0 * np.pi, self.pond_bird_count
        ).astype(np.float32)
        self.pond_bird_leader = 0
        self.pond_bird_leader_heading = float(flock_heading[0])
        self.pond_bird_turn_cooldown = 0.0

        cloud_count = 65
        self.pond_cloud_pos = np.column_stack((
            np.random.uniform(-10.0, 10.0, cloud_count),
            np.random.uniform(5.4, 8.8, cloud_count),
            np.zeros(cloud_count),
        )).astype(np.float32)
        self.pond_cloud_size = np.random.uniform(
            16.0, 42.0, cloud_count
        ).astype(np.float32)

        pond_x, pond_y = np.meshgrid(
            np.linspace(-10.5, 10.5, 48),
            np.linspace(-4.75, -1.25, 16),
        )
        self.pond_surface_pos = np.column_stack((
            pond_x.ravel(),
            pond_y.ravel(),
            np.zeros(pond_x.size),
        )).astype(np.float32)

    def add_pond_music_ripple(self, event):
        """Inject a broad, music-driven ripple into the shader's water simulation."""
        band_type = event.get("band_type")
        band_energy = max(
            float(event.get("band_bass", 0.0)),
            float(event.get("band_mid", 0.0)),
            float(event.get("band_treble", 0.0)),
        )

        # Bass events and sufficiently energetic spectral events form prominent,
        # expanding rings. Treble-led events remain represented by the rain layer.
        if band_type != "bass" and band_energy < 0.55:
            return

        x_offset = event.get("x_offset")
        if x_offset is None:
            x_position = float(
                np.clip(self.current_stereo_panning, -0.82, 0.82)
            )
        else:
            x_position = float(np.clip(float(x_offset) / 11.0, -0.82, 0.82))

        # These positions correspond to the lowered, foreshortened pond surface
        # in screen space, keeping new music rings on the water plane.
        band_y_positions = {
            "bass": -0.86,
            "mid": -0.70,
            "treble": -0.54,
        }
        y_position = band_y_positions.get(
            band_type,
            float(np.random.uniform(-1.00, -0.44)),
        )
        strength = float(np.clip(0.65 + band_energy * 0.55, 0.0, 1.4))

        self.pond_shader_ripples.append(
            {
                "position": np.array(
                    [
                        x_position + np.random.uniform(-0.035, 0.035),
                        y_position + np.random.uniform(-0.025, 0.025),
                    ],
                    dtype=np.float32,
                ),
                "age": 0.0,
                "strength": strength * np.random.uniform(0.82, 1.08),
            }
        )
        self.pond_shader_ripples = self.pond_shader_ripples[-8:]

    def _steer_pond_flock(self, event):
        """Turn the distant flock together in response to analyzed musical hits."""
        if self.pond_bird_turn_cooldown > 0.0:
            return

        band_type = event.get("band_type")
        band_energy = max(
            float(event.get("band_bass", 0.0)),
            float(event.get("band_mid", 0.0)),
            float(event.get("band_treble", 0.0)),
        )
        if band_energy < 0.20:
            return

        if band_type == "treble":
            turn_amount = np.random.uniform(0.45, 0.85)
        elif band_type == "mid":
            turn_amount = np.random.uniform(0.25, 0.55)
        elif band_type == "bass" and band_energy > 0.45:
            turn_amount = np.random.uniform(0.35, 0.70)
        else:
            return

        direction = -1.0 if self.current_stereo_panning < 0.0 else 1.0
        self.pond_bird_leader_heading += direction * turn_amount
        leader_speed = 0.115 + band_energy * 0.050
        leader = self.pond_bird_leader
        self.pond_bird_vel[leader] = [
            np.cos(self.pond_bird_leader_heading) * leader_speed,
            np.sin(self.pond_bird_leader_heading) * leader_speed,
        ]

        # Only the leader receives the abrupt music-driven turn. The remaining
        # birds change course through alignment and cohesion in update_pond().
        self.pond_bird_turn_cooldown = 0.65

    def _spawn_pond_raindrop(self, band_energy):
        x = np.clip(
            self.current_stereo_panning * 6.5 + np.random.uniform(-4.5, 4.5),
            -9.8,
            9.8,
        )
        self.pond_rain.append({
            "pos": np.array([x, np.random.uniform(5.0, 8.8), 0.0], dtype=np.float32),
            "speed": np.random.uniform(5.5, 8.5) * (1.0 + band_energy * 0.35),
            "energy": band_energy,
        })

    def _add_pond_ripple(self, position, energy):
        self.pond_ripples.append({
            "pos": np.array([position[0], -1.28, 0.0], dtype=np.float32),
            "radius": 0.05,
            "speed": 1.4 + energy * 1.7,
            "life": 1.8 + energy * 0.7,
            "max_life": 1.8 + energy * 0.7,
            "energy": energy,
        })

    def update_pond(self, dt):
        active_shader_ripples = []
        for ripple in self.pond_shader_ripples:
            ripple["age"] += dt
            if ripple["age"] < 2.8:
                active_shader_ripples.append(ripple)
        self.pond_shader_ripples = active_shader_ripples

        music_energy = np.clip(
            max(self.react_bass, self.react_mid, self.react_treble),
            0.0,
            1.5,
        )
        self.pond_rain_spawn_accumulator += dt * (3.0 + music_energy * 19.0)
        while self.pond_rain_spawn_accumulator >= 1.0:
            self.pond_rain_spawn_accumulator -= 1.0
            self._spawn_pond_raindrop(music_energy)

        remaining_rain = []
        for drop in self.pond_rain:
            drop["pos"][1] -= drop["speed"] * dt
            if drop["pos"][1] <= -1.25:
                self._add_pond_ripple(drop["pos"], drop["energy"])
            else:
                remaining_rain.append(drop)
        self.pond_rain = remaining_rain

        remaining_ripples = []
        for ripple in self.pond_ripples:
            ripple["radius"] += ripple["speed"] * dt
            ripple["life"] -= dt
            if ripple["life"] > 0.0 and ripple["radius"] < 5.2:
                remaining_ripples.append(ripple)
        self.pond_ripples = remaining_ripples

        self.pond_bird_turn_cooldown = max(
            0.0, self.pond_bird_turn_cooldown - dt
        )

        # A leader-driven boids flock. The designated lead bird receives musical
        # turns; nearby followers align with its new trajectory over successive
        # frames, creating a visible travelling turn instead of a simultaneous
        # whole-flock rotation.
        positions = self.pond_bird_pos
        velocities = self.pond_bird_vel
        leader = self.pond_bird_leader
        offsets = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]
        distances = np.linalg.norm(offsets, axis=2)
        nearby = (distances > 0.0) & (distances < 0.26)
        neighbor_count = np.maximum(nearby.sum(axis=1, keepdims=True), 1)

        neighbor_positions = (
            nearby[..., np.newaxis] * positions[np.newaxis, :, :]
        ).sum(axis=1) / neighbor_count
        neighbor_velocities = (
            nearby[..., np.newaxis] * velocities[np.newaxis, :, :]
        ).sum(axis=1) / neighbor_count
        separation = (
            -offsets
            / np.maximum(distances[..., np.newaxis], 0.022) ** 2
            * (distances[..., np.newaxis] < 0.105)
        ).sum(axis=1)

        boundary_force = np.zeros_like(positions)
        boundary_force[:, 0] += np.where(positions[:, 0] > 0.92, -0.90, 0.0)
        boundary_force[:, 0] += np.where(positions[:, 0] < -0.92, 0.90, 0.0)
        boundary_force[:, 1] += np.where(positions[:, 1] > 0.82, -0.72, 0.0)
        boundary_force[:, 1] += np.where(positions[:, 1] < 0.18, 0.72, 0.0)

        leader_position = positions[leader]
        leader_velocity = velocities[leader].copy()
        follower_force = (
            (neighbor_positions - positions) * 0.08
            + (neighbor_velocities - velocities) * 0.30
            + separation * 0.090
            + (leader_position - positions) * 0.065
            + (leader_velocity - velocities) * 0.24
            + boundary_force
        )
        follower_force[leader] = boundary_force[leader]
        velocities += follower_force * dt

        desired_speed = 0.115 + music_energy * 0.050
        speed = np.linalg.norm(velocities, axis=1, keepdims=True)
        velocities *= desired_speed / np.maximum(speed, 1e-5)
        positions += velocities * dt
        self.pond_bird_heading = np.arctan2(velocities[:, 1], velocities[:, 0])
        self.pond_bird_phase += dt * (
            5.0 + self.react_treble * 5.0 + self.react_mid * 1.5
        )

        # Leaf, lightning, and trout routines are rendered entirely by the
        # fullscreen shader. Avoid particle approximations that read as dots.
        self.pond_leaf_vortex_timer = max(0.0, self.pond_leaf_vortex_timer - dt)
        self.pond_leaves.clear()
        self.pond_lightning_timer = max(0.0, self.pond_lightning_timer - dt)
        self.pond_lightning.clear()

        if self.pond_fish is not None:
            fish = self.pond_fish
            fish["time"] += dt
            if fish["time"] >= 1.55:
                self._add_pond_ripple(fish["pos"], 1.5)
                self.pond_fish = None

    def trigger_climax_pond(self, routine_name):
        if routine_name == "Leaf Vortex":
            # Root the vortex at the distant bank behind the pond, rather than
            # over the near water or foreground grass.
            self.pond_leaf_vortex_center_x = float(
                np.random.choice((-0.68, 0.68))
            )
            self.pond_leaf_vortex_timer = 4.5
            self.pond_leaves.clear()
        elif routine_name == "Lightning Strike":
            # The shader renders a branching, briefly afterglowing bolt while
            # the shared climax flash supplies the thunderclap illumination.
            self.pond_lightning_timer = 0.55
            self.climax_flash = max(self.climax_flash, 1.8)
        elif routine_name == "Fish Splash":
            direction = 1.0 if np.random.random() < 0.5 else -1.0
            self.pond_fish = {
                "pos": np.array(
                    [np.random.uniform(-3.0, 3.0), -1.25, 0.0],
                    dtype=np.float32,
                ),
                "velocity": np.array([direction * 2.1, 0.0, 0.0], dtype=np.float32),
                "time": 0.0,
                "direction": direction,
            }

    def render_pond(self):
        positions, colors, sizes = [], [], []

        # The fullscreen pond shader renders the water surface, grass banks,
        # clouds, rain, ripples, trees, and flocking swallows without dot art.
        # Keep only routine effects below as foreground accents.
        # The fullscreen pond shader renders layered storm clouds, physical rain
        # streaks, water reflections, and continuous ripples. Keep the routine
        # effects below as foreground accents rather than duplicating the scene
        # with low-resolution point-sprite cloud and water-dot art.

        # The fullscreen shader renders the natural leaf vortex, trout, and splash
        # as coherent scenic effects rather than as foreground point sprites.
        # Animated swallows are rendered as anti-aliased procedural silhouettes
        # in the fullscreen pond shader rather than three-point bird glyphs.

        return (
            np.asarray(positions, dtype=np.float32).reshape(-1, 3),
            np.asarray(colors, dtype=np.float32).reshape(-1, 4),
            np.asarray(sizes, dtype=np.float32),
            np.zeros((0, 3), dtype=np.float32),
            np.zeros((0, 4), dtype=np.float32),
        )
