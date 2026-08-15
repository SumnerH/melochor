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
        self.pond_cloud_drift = 0.0
        self.pond_ripple_seq_idx = 0

        # Ripple algorithm options (cycled with [U]):
        # 0 = Interference Hologram (coherent harmonic interference & Moiré fringes)
        # 1 = Chromatic Caustics (dispersive prism refraction & focused light caustics)
        # 2 = Resonant Cymatics (Default: geometric standing-wave modal patterns)
        # 3 = Capillary Dispersion (multi-scale bass swells & high-frequency capillary chatter)
        # 4 = Neon Phosphor (bioluminescent glowing shockwaves & water illumination)
        self.pond_ripple_algorithm = 2
        self.pond_ripple_names = [
            "Interference Hologram",
            "Chromatic Caustics",
            "Resonant Cymatics",
            "Capillary Dispersion",
            "Neon Phosphor"
        ]

        # Keep two separate distant flocks. They share the pond sky but never
        # use one another as boid neighbors, leaders, or music-turn targets.
        self.pond_flock_count = 2
        self.pond_birds_per_flock = 7
        self.pond_bird_count = self.pond_flock_count * self.pond_birds_per_flock
        self.pond_flocks = []

        flock_specs = (
            {
                "center_x": np.random.uniform(-0.72, -0.30),
                "center_y": np.random.uniform(0.42, 0.67),
                "heading": np.random.uniform(-0.22, 0.28),
                "speed": (0.110, 0.145),
                "bounds": (-0.94, -0.05, 0.20, 0.82),
                "turn_bias": 1.0,
                "response_threshold": 0.18,
            },
            {
                "center_x": np.random.uniform(0.30, 0.72),
                "center_y": np.random.uniform(0.30, 0.58),
                "heading": np.random.uniform(np.pi - 0.28, np.pi + 0.22),
                "speed": (0.120, 0.158),
                "bounds": (0.05, 0.94, 0.16, 0.78),
                "turn_bias": -1.0,
                "response_threshold": 0.25,
            },
        )

        for flock_index, spec in enumerate(flock_specs):
            flock_center = np.array(
                [spec["center_x"], spec["center_y"]],
                dtype=np.float32,
            )
            bird_count = self.pond_birds_per_flock
            flock_heading = np.full(
                bird_count,
                spec["heading"],
                dtype=np.float32,
            ) + np.random.uniform(-0.24, 0.24, bird_count).astype(np.float32)
            speeds = np.random.uniform(
                spec["speed"][0],
                spec["speed"][1],
                (bird_count, 1),
            ).astype(np.float32)

            self.pond_flocks.append({
                "positions": flock_center + np.random.normal(
                    0.0,
                    [0.105, 0.065],
                    (bird_count, 2),
                ).astype(np.float32),
                "velocities": np.column_stack((
                    np.cos(flock_heading),
                    np.sin(flock_heading),
                )).astype(np.float32) * speeds,
                "headings": flock_heading.astype(np.float32),
                "phases": (
                    np.random.uniform(0.0, 2.0 * np.pi, bird_count)
                    + flock_index * 0.91
                ).astype(np.float32),
                "leader": int(np.random.randint(0, bird_count)),
                "leader_heading": float(flock_heading[0]),
                "turn_cooldown": 0.0,
                "bounds": spec["bounds"],
                "turn_bias": spec["turn_bias"],
                "response_threshold": spec["response_threshold"],
                "speed_range": spec["speed"],
                "music_phase": float(np.random.uniform(0.0, 2.0 * np.pi)),
            })

            leader = self.pond_flocks[-1]["leader"]
            self.pond_flocks[-1]["leader_heading"] = float(flock_heading[leader])

        # The renderer uploads one flat array to the existing shader uniforms.
        # These compatibility arrays are refreshed from the independent flocks
        # after every simulation update.
        self._sync_pond_bird_shader_data()

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

    def cycle_pond_ripple_algorithm(self):
        """Cycle through the 5 water ripple algorithms."""
        if not hasattr(self, 'pond_ripple_names'):
            self.pond_ripple_names = [
                "Interference Hologram",
                "Chromatic Caustics",
                "Resonant Cymatics",
                "Capillary Dispersion",
                "Neon Phosphor"
            ]
        self.pond_ripple_algorithm = (getattr(self, 'pond_ripple_algorithm', 0) + 1) % len(self.pond_ripple_names)
        print(f"[Pond Mode] Ripple algorithm: {self.pond_ripple_names[self.pond_ripple_algorithm]}")

    def _sync_pond_bird_shader_data(self):
        """Pack independent flock state into the flat arrays used by the shader."""
        self.pond_bird_pos = np.concatenate(
            [flock["positions"] for flock in self.pond_flocks],
            axis=0,
        ).astype(np.float32)
        self.pond_bird_vel = np.concatenate(
            [flock["velocities"] for flock in self.pond_flocks],
            axis=0,
        ).astype(np.float32)
        self.pond_bird_heading = np.concatenate(
            [flock["headings"] for flock in self.pond_flocks],
            axis=0,
        ).astype(np.float32)
        self.pond_bird_phase = np.concatenate(
            [flock["phases"] for flock in self.pond_flocks],
            axis=0,
        ).astype(np.float32)

    def add_pond_music_ripple(self, event):
        """Inject a broad, music-driven ripple into the shader's water simulation."""
        if not hasattr(self, 'pond_shader_ripples'):
            self.init_pond_mode()
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

        # Golden-ratio low-discrepancy sequence: consecutive beats disperse across
        # the pond rather than clumping onto a single center line.
        phi = 0.618033988749895
        self.pond_ripple_seq_idx = getattr(self, 'pond_ripple_seq_idx', 0) + 1
        seq = self.pond_ripple_seq_idx
        golden_x = (((seq * phi) % 1.0) * 2.0 - 1.0) * 0.65

        # Rhythmic tempo-phase Lissajous sweep: glides back and forth in time with BPM
        tempo_phase = getattr(self, 'tempo_phase', 0.0)
        tempo_sweep = (
            np.sin(tempo_phase * np.pi * 0.5) * 0.38
            + np.sin(tempo_phase * np.pi * 0.25) * 0.18
        )

        # Spectral frequency bias: bass anchors toward left/center, treble toward right
        bass_energy = float(event.get("band_bass", 0.0))
        treble_energy = float(event.get("band_treble", 0.0))
        freq_bias = (treble_energy - bass_energy) * 0.30

        # Stereo panning bias
        x_offset = event.get("x_offset")
        if x_offset is not None:
            pan_val = float(np.clip(float(x_offset) / 6.0, -1.0, 1.0))
        else:
            pan_val = float(np.clip(getattr(self, 'current_stereo_panning', 0.0), -1.0, 1.0))

        raw_x = golden_x * 0.40 + tempo_sweep * 0.30 + pan_val * 0.45 + freq_bias
        x_position = float(np.clip(raw_x, -0.78, 0.78))

        # Foreshortened pond depth mapping: bass spawns in foreground, treble in
        # distant water, modulated by golden-angle vertical phase to avoid flat lines.
        band_y_base = {
            "bass": -0.84,
            "mid": -0.68,
            "treble": -0.52,
        }.get(band_type, -0.68)
        y_jitter = np.sin(seq * 2.399963) * 0.09
        y_position = float(np.clip(band_y_base + y_jitter, -0.96, -0.44))

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
        """Let each flock independently react to an analyzed musical hit."""
        if not hasattr(self, 'pond_flocks'):
            self.init_pond_mode()
        band_type = event.get("band_type")
        band_energy = max(
            float(event.get("band_bass", 0.0)),
            float(event.get("band_mid", 0.0)),
            float(event.get("band_treble", 0.0)),
        )

        if band_energy < 0.18:
            return

        for flock_index, flock in enumerate(self.pond_flocks):
            if flock["turn_cooldown"] > 0.0:
                continue

            # Treble reliably catches both flocks' attention, while mid and bass
            # receive separate per-flock response chances and energy thresholds.
            if band_type == "treble":
                turn_range = (0.34, 0.76)
                response_chance = 0.92
            elif band_type == "mid":
                turn_range = (0.20, 0.52)
                response_chance = 0.64
            elif band_type == "bass" and band_energy > 0.42:
                turn_range = (0.28, 0.66)
                response_chance = 0.74
            else:
                continue

            if band_energy < flock["response_threshold"]:
                continue

            # Each flock makes its own response decision. Stereo direction and
            # opposing flock bias make simultaneous reactions diverge instead of
            # causing a mirrored or rigid whole-sky movement.
            if np.random.random() > response_chance:
                continue

            stereo_direction = (
                -1.0 if self.current_stereo_panning < 0.0 else 1.0
            )
            independent_direction = (
                stereo_direction
                * flock["turn_bias"]
                * (1.0 if np.random.random() < 0.76 else -1.0)
            )
            turn_amount = np.random.uniform(*turn_range) * (
                0.82 + band_energy * 0.34
            )
            flock["leader_heading"] += independent_direction * turn_amount
            flock["music_phase"] += turn_amount * (
                0.50 if flock_index == 0 else -0.58
            )

            leader = flock["leader"]
            leader_speed = np.random.uniform(*flock["speed_range"]) + band_energy * 0.045
            flock["velocities"][leader] = [
                np.cos(flock["leader_heading"]) * leader_speed,
                np.sin(flock["leader_heading"]) * leader_speed,
            ]

            # Separate cooldowns permit one flock to react while the other is
            # still settling from an earlier musical turn.
            flock["turn_cooldown"] = np.random.uniform(0.48, 0.86)

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
        """Send a rain or trout impact directly to the fullscreen ripple shader."""
        # The shader can display eight simultaneous wave sources. Reserve up to
        # four for natural impacts so frequent rain cannot evict music ripples.
        rain_ripples = [
            ripple
            for ripple in self.pond_shader_ripples
            if ripple.get("source") == "rain"
        ]
        if len(rain_ripples) >= 4:
            oldest_rain_ripple = max(
                rain_ripples,
                key=lambda ripple: ripple["age"],
            )
            for index, ripple in enumerate(self.pond_shader_ripples):
                if ripple is oldest_rain_ripple:
                    del self.pond_shader_ripples[index]
                    break

        if len(self.pond_shader_ripples) >= 8:
            non_music_ripples = [
                ripple
                for ripple in self.pond_shader_ripples
                if ripple.get("source") == "rain"
            ]
            if not non_music_ripples:
                return
            oldest_rain_ripple = max(
                non_music_ripples,
                key=lambda ripple: ripple["age"],
            )
            for index, ripple in enumerate(self.pond_shader_ripples):
                if ripple is oldest_rain_ripple:
                    del self.pond_shader_ripples[index]
                    break

        self.pond_shader_ripples.append({
            "position": np.array(
                [
                    np.clip(position[0] / 10.5, -0.82, 0.82),
                    -0.80,
                ],
                dtype=np.float32,
            ),
            "age": 0.0,
            "strength": float(np.clip(0.32 + energy * 0.42, 0.0, 1.0)),
            "source": "rain",
        })

    def _update_pond_flock(self, flock, dt, music_energy):
        """Advance one isolated leader-driven boid flock."""
        flock["turn_cooldown"] = max(0.0, flock["turn_cooldown"] - dt)

        positions = flock["positions"]
        velocities = flock["velocities"]
        leader = flock["leader"]

        offsets = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]
        distances = np.linalg.norm(offsets, axis=2)
        nearby = (distances > 0.0) & (distances < 0.23)
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
            * (distances[..., np.newaxis] < 0.092)
        ).sum(axis=1)

        min_x, max_x, min_y, max_y = flock["bounds"]
        boundary_force = np.zeros_like(positions)
        boundary_force[:, 0] += np.where(positions[:, 0] > max_x, -0.90, 0.0)
        boundary_force[:, 0] += np.where(positions[:, 0] < min_x, 0.90, 0.0)
        boundary_force[:, 1] += np.where(positions[:, 1] > max_y, -0.72, 0.0)
        boundary_force[:, 1] += np.where(positions[:, 1] < min_y, 0.72, 0.0)

        leader_position = positions[leader]
        leader_velocity = velocities[leader].copy()
        follower_force = (
            (neighbor_positions - positions) * 0.090
            + (neighbor_velocities - velocities) * 0.32
            + separation * 0.095
            + (leader_position - positions) * 0.070
            + (leader_velocity - velocities) * 0.25
            + boundary_force
        )
        follower_force[leader] = boundary_force[leader]
        velocities += follower_force * dt

        desired_speed = np.random.uniform(*flock["speed_range"]) + music_energy * 0.045
        speed = np.linalg.norm(velocities, axis=1, keepdims=True)
        velocities *= desired_speed / np.maximum(speed, 1e-5)
        positions += velocities * dt

        flock["headings"] = np.arctan2(velocities[:, 1], velocities[:, 0])
        flock["phases"] += dt * (
            4.4
            + self.react_treble * 4.6
            + self.react_mid * 1.3
            + 0.35 * np.sin(flock["music_phase"])
        )

    def update_pond(self, dt):
        if not hasattr(self, 'pond_flocks'):
            self.init_pond_mode()

        # Visual Vacuum: glass calm surface
        if getattr(self, 'visual_vacuum_timer', 0.0) > 0.0:
            self.pond_rain.clear()
            return

        # Smooth continuous cloud drift with subtle speed modulation from music
        bass_s = getattr(self, 'react_bass_smooth', 0.0)
        mid_s = getattr(self, 'react_mid_smooth', 0.0)
        drift_rate = 0.018 + bass_s * 0.012 + mid_s * 0.006
        self.pond_cloud_drift = getattr(self, 'pond_cloud_drift', 0.0) + drift_rate * dt

        # Anticipatory implosion: flocks spiral inward toward zone center
        if getattr(self, 'drop_anticipation_timer', 0.0) > 0.0:
            is_global = getattr(self, 'drop_anticipation_is_global', False)
            intensity = getattr(self, 'drop_anticipation_intensity', 1.0 if is_global else 0.35)
            progress = 1.0 - (self.drop_anticipation_timer / max(0.1, self.drop_anticipation_duration))
            for flock in self.pond_flocks:
                min_x, max_x, min_y, max_y = flock["bounds"]
                f_center = np.array([(min_x + max_x) * 0.5, (min_y + max_y) * 0.5], dtype=np.float32)
                flock["positions"] += (f_center - flock["positions"]) * min(1.0, dt * (1.2 + progress * 3.5) * intensity)

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

        # All visible ripples are simulated by the fullscreen shader via
        # pond_shader_ripples, including rain and trout impacts.

        # Update each flock separately; no cohesion, alignment, or leader force
        # crosses from one flock to the other.
        for flock in self.pond_flocks:
            self._update_pond_flock(flock, dt, music_energy)
        self._sync_pond_bird_shader_data()

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
        # clouds, rain, ripples, trees, and two independently flocking groups
        # of swallows without dot art.
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
