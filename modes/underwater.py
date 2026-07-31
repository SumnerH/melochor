import numpy as np
import random
from meshes import (
    make_solid_squid,
    make_solid_manta,
    make_solid_seahorse,
    make_solid_fish
)

class UnderwaterModeMixin:
    def get_tangential_jelly_dir(self, pos):
        # Calculate camera look/position to target [0, 4, 0]
        cx = self.camera_dist * np.cos(self.camera_phi) * np.sin(self.camera_theta)
        cy = self.camera_dist * np.sin(self.camera_phi)
        cz = self.camera_dist * np.cos(self.camera_phi) * np.cos(self.camera_theta)
        cam_pos = np.array([cx, cy, cz], dtype=np.float32)
        v_view = pos - cam_pos
        dist = np.linalg.norm(v_view)
        if dist < 1e-4:
            v_view = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        else:
            v_view = v_view / dist
        
        # Perpendicular vector 1
        if abs(v_view[0]) > 0.9:
            v_perp1 = np.array([v_view[1], -v_view[0], 0.0], dtype=np.float32)
        else:
            v_perp1 = np.array([0.0, v_view[2], -v_view[1]], dtype=np.float32)
        v_perp1 /= np.linalg.norm(v_perp1)
        
        # Perpendicular vector 2
        v_perp2 = np.cross(v_view, v_perp1)
        v_perp2 /= np.linalg.norm(v_perp2)
        
        # Angle in the plane perpendicular to view
        alpha = np.random.uniform(0.0, 2 * np.pi)
        # Angle out of plane (clamped to 30 degrees = pi / 6)
        beta = np.random.uniform(-np.pi / 6.0, np.pi / 6.0)
        
        v_plane = np.cos(alpha) * v_perp1 + np.sin(alpha) * v_perp2
        jelly_dir = v_plane * np.cos(beta) + v_view * np.sin(beta)
        
        # Ensure the jellyfish swims generally upwards (positive y)
        if jelly_dir[1] < 0:
            jelly_dir = -jelly_dir
            
        jelly_dir /= np.linalg.norm(jelly_dir)
        return jelly_dir

    # =========================================================================
    # MODE 3: BIOLUMINESCENT UNDERWATER DEEP-SEA LAVA LAMP
    # =========================================================================
    def init_underwater_mode(self):
        N_bubbles = 2500
        self.bubble_pos = np.zeros((N_bubbles, 3), dtype=np.float32)
        self.bubble_vel = np.zeros((N_bubbles, 3), dtype=np.float32)
        self.bubble_col = np.zeros((N_bubbles, 4), dtype=np.float32)
        self.bubble_size = np.zeros(N_bubbles, dtype=np.float32)
        self.bubble_phase = np.zeros(N_bubbles, dtype=np.float32)
        self.bubble_active = np.zeros(N_bubbles, dtype=np.bool_)
        self.bubble_is_fragment = np.zeros(N_bubbles, dtype=np.bool_)
        self.next_bubble_idx = 0
        self.vent_locs = [
            [-3.0, -2.5, 6.0],   # Left Foreground Vent (raised and brought closer)
            [0.0, -2.5, 4.0],    # Center Foreground Vent (raised and brought closer)
            [3.0, -2.5, 7.0]     # Right Foreground Vent (raised and brought closer)
        ]

        N_algae = 1500
        self.algae_pos = np.random.uniform(
            [-10.0, -2.5, -5.0], [10.0, 9.0, 12.0], (N_algae, 3)
        ).astype(np.float32)
        self.algae_phase = np.random.uniform(0.0, 2 * np.pi, (N_algae, 3)).astype(np.float32)
        self.algae_col = np.zeros((N_algae, 4), dtype=np.float32)
        for i in range(N_algae):
            self.algae_col[i] = random.choice([
                (0.1, 0.95, 0.4, 0.5), # Emerald Green
                (0.1, 0.7, 1.0, 0.5),  # Cyan
                (0.35, 0.15, 1.0, 0.5) # Neon Violet
            ])
        self.algae_size = np.random.uniform(2.5, 6.0, N_algae).astype(np.float32)

        # Irregular Stalagmites Volcanic Vents 3D Geometry Setup (Taller and rugged)
        # 3 vents, 6 rings of height, 4 points per ring = 72 points
        self.num_vent_pts = 72
        self.vent_pts_pos = np.zeros((self.num_vent_pts, 3), dtype=np.float32)
        self.vent_pts_col = np.zeros((self.num_vent_pts, 4), dtype=np.float32)
        self.vent_pts_size = np.zeros(self.num_vent_pts, dtype=np.float32)
        
        idx = 0
        for v_loc in self.vent_locs:
            ruggedness_seed = [np.random.uniform(0.8, 1.2, 4) for _ in range(6)]
            for ring in range(6):
                y_offset = ring * 0.35 # Height off seabed
                rad = 1.05 - ring * 0.17 # Stalagmite chimney tapers upward
                if ring == 5:
                    rad = 0.3 # narrow crater opening
                    
                num_ring_pts = 4
                for p in range(num_ring_pts):
                    angle = (p * 2 * np.pi / num_ring_pts) + ring * 0.4
                    r_jit = rad * ruggedness_seed[ring][p]
                    vx = v_loc[0] + r_jit * np.cos(angle) + np.random.uniform(-0.06, 0.06)
                    vy = v_loc[1] + y_offset + np.random.uniform(-0.04, 0.04)
                    vz = v_loc[2] + r_jit * np.sin(angle) + np.random.uniform(-0.06, 0.06)
                    
                    self.vent_pts_pos[idx] = [vx, vy, vz]
                    if ring == 5:
                        self.vent_pts_col[idx] = [0.1, 0.95, 1.0, 0.95] # Hot cyan lip
                        self.vent_pts_size[idx] = 13.0
                    else:
                        self.vent_pts_col[idx] = [0.10, 0.14, 0.20, 0.85]
                        self.vent_pts_size[idx] = 18.0 - ring * 2.2
                    idx += 1

        # Textured Sandy/Rocky Sea Floor Setup (Replacing computer grid lines)
        self.num_seabed_pts = 1500
        self.seabed_pos = np.zeros((self.num_seabed_pts, 3), dtype=np.float32)
        self.seabed_col = np.zeros((self.num_seabed_pts, 4), dtype=np.float32)
        self.seabed_size = np.zeros(self.num_seabed_pts, dtype=np.float32)
        
        self.seabed_pos[:, 0] = np.random.uniform(-16.0, 16.0, self.num_seabed_pts)
        self.seabed_pos[:, 1] = -2.5 + np.random.uniform(-0.15, 0.15, self.num_seabed_pts)
        self.seabed_pos[:, 2] = np.random.uniform(-5.0, 15.0, self.num_seabed_pts)
        
        for i in range(self.num_seabed_pts):
            self.seabed_col[i] = random.choice([
                (0.24, 0.18, 0.12, 0.75),  # Deep sand gold-brown
                (0.32, 0.26, 0.18, 0.70),  # Soft sandy beige
                (0.12, 0.14, 0.18, 0.85),  # Dark basalt stone
                (0.10, 0.22, 0.14, 0.65)   # Moss/Algae-covered rock
            ])
            self.seabed_size[i] = np.random.uniform(-4.0, -12.0)

        # Bioluminescent Waving Seaweed / Marine Plants Setup
        self.num_plants = 20
        self.plant_base = np.random.uniform([-10.0, -2.5, -5.0], [10.0, -2.5, 12.0], (self.num_plants, 3)).astype(np.float32)
        self.plant_phase = np.random.uniform(0.0, 2 * np.pi, self.num_plants).astype(np.float32)
        self.plant_color = np.zeros((self.num_plants, 3), dtype=np.float32)
        for i in range(self.num_plants):
            self.plant_color[i] = random.choice([
                (0.12, 0.90, 0.35), # Emerald Mint Seaweed
                (0.05, 0.75, 0.85), # Glowing Teal Seaweed
                (0.70, 0.95, 0.15)  # Neon Yellow-Green Kelp
            ])

        # Overhauled Pulsing 3D Jellyfish (Halved to 5 individuals representing Moon and Crystal)
        self.num_jelly = 5
        self.jelly_pos = np.zeros((self.num_jelly, 3), dtype=np.float32)
        self.jelly_dir = np.zeros((self.num_jelly, 3), dtype=np.float32)
        self.jelly_vel = np.zeros((self.num_jelly, 3), dtype=np.float32)
        self.jelly_col = np.zeros((self.num_jelly, 4), dtype=np.float32)
        self.jelly_size = np.zeros(self.num_jelly, dtype=np.float32)
        self.jelly_phase = np.zeros(self.num_jelly, dtype=np.float32)
        self.jelly_species = np.array([i % 2 for i in range(self.num_jelly)], dtype=np.int32)
        
        for i in range(self.num_jelly):
            self.jelly_pos[i] = [
                np.random.uniform(-6.0, 6.0),
                np.random.uniform(-1.5, 8.0),
                np.random.uniform(-2.0, 12.0)
            ]
            # Restrict swimming direction to 90 degrees +/- 30 degrees relative to camera view
            self.jelly_dir[i] = self.get_tangential_jelly_dir(self.jelly_pos[i])
            
            sp = self.jelly_species[i]
            if sp == 0:     # Moon Jelly (lavender-pink translucent)
                self.jelly_col[i] = (0.85, 0.65, 0.95, 1.0)
                self.jelly_size[i] = np.random.uniform(22.0, 28.0)
            else:           # Crystal Jelly (cyan-blue highly transparent)
                self.jelly_col[i] = (0.0, 0.85, 1.0, 1.0)
                self.jelly_size[i] = np.random.uniform(20.0, 26.0)
                
            self.jelly_phase[i] = np.random.uniform(0.0, 2 * np.pi)
            
        # Glowing 3D Animated Squid initialization
        self.squid_pos = np.array([0.0, 3.0, 5.0], dtype=np.float32)
        self.squid_dir = np.array([1.0, 0.1, 0.0], dtype=np.float32)
        self.squid_dir /= np.linalg.norm(self.squid_dir)
        self.squid_vel = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.squid_phase = 0.0
        self.squid_jet_cooldown = 0.0
            
        # Initialize plankton and seabed phosphorescence twinkling states
        self.algae_twinkle_phase = np.random.uniform(0.0, 2 * np.pi, N_algae).astype(np.float32)
        self.algae_random_rates = np.random.uniform(0.8, 1.5, N_algae).astype(np.float32)
        self.seabed_twinkle_phase = np.random.uniform(0.0, 2 * np.pi, self.num_seabed_pts).astype(np.float32)
        self.seabed_is_glowing = (np.random.rand(self.num_seabed_pts) < 0.28) # 28% of seabed points glow


    def update_underwater(self, dt):
        # Spawn bubbles based on volume hits and frequencies
        num_to_spawn = 0
        is_treble_heavy = False
        
        # Determine peak activity
        max_react = max(self.react_bass, self.react_mid, self.react_treble)
        
        if max_react > 0.3:
            # High volume hit: release significantly more bubbles!
            if self.react_treble > self.react_bass:
                is_treble_heavy = True
                # Treble hit: spawn MANY tiny, fast bubbles (up to 32 bubbles for intense peaks)
                num_to_spawn = int(2 + (self.react_treble ** 1.8) * 30.0)
            else:
                # Bass hit: spawn FEWER giant, slow bubbles (up to 10 bubbles)
                num_to_spawn = int(1 + (self.react_bass ** 1.8) * 9.0)
                
            # Add some randomness to keep the pattern uneven
            if random.random() > 0.85:
                num_to_spawn = int(num_to_spawn * 0.5)
        else:
            # Occasional light trickle when music is quiet
            if random.random() < 0.12:
                num_to_spawn = random.choice([1, 2])
                is_treble_heavy = random.random() < 0.5
                    
        num_to_spawn = min(num_to_spawn, 35) # Cap to avoid overloading
        
        for _ in range(num_to_spawn):
            idx = self.next_bubble_idx
            
            # Determine spout index biased by stereo panning
            p = getattr(self, 'current_stereo_panning', 0.0)
            p_left = max(0.05, 0.33 - 0.5 * p)
            p_right = max(0.05, 0.33 + 0.5 * p)
            p_center = max(0.05, 1.0 - p_left - p_right)
            total = p_left + p_center + p_right
            probs = [p_left / total, p_center / total, p_right / total]
            v_idx = np.random.choice([0, 1, 2], p=probs)
            v_loc = self.vent_locs[v_idx]
            
            # Bubbles rise directly from the open stalagmite mouths (y_offset=1.75)
            self.bubble_pos[idx] = [v_loc[0], v_loc[1] + 1.75, v_loc[2]] + np.random.uniform([-0.25, 0.0, -0.25], [0.25, 0.15, 0.25])
            
            # Compute a frequency-dependent reactive color
            tot_energy = self.react_bass + self.react_mid + self.react_treble + 1e-5
            fb = self.react_bass / tot_energy
            fm = self.react_mid / tot_energy
            ft = self.react_treble / tot_energy
            
            # Blend colors: Bass (deep blue/magenta), Mid (teal/green), Treble (cyan/white)
            r_c = fb * 0.05 + fm * 0.1 + ft * 0.7
            g_c = fb * 0.35 + fm * 0.9 + ft * 0.9
            b_c = fb * 1.0 + fm * 0.5 + ft * 1.0
            r_c = np.clip(r_c + np.random.uniform(-0.05, 0.05), 0.0, 1.0)
            g_c = np.clip(g_c + np.random.uniform(-0.05, 0.05), 0.0, 1.0)
            b_c = np.clip(b_c + np.random.uniform(-0.05, 0.05), 0.0, 1.0)
            alpha = np.clip(0.3 * fb + 0.6 * fm + 0.85 * ft + np.random.uniform(-0.1, 0.1), 0.25, 0.95)

            if is_treble_heavy:
                # Treble: tiny, fast bubbles
                self.bubble_size[idx] = np.random.uniform(1.2, 2.5)
                rise_speed = np.random.uniform(1.6, 2.8) * (1.0 + self.react_treble * 0.3)
                self.bubble_vel[idx] = [
                    np.random.uniform(-0.5, 0.5),
                    rise_speed,
                    np.random.uniform(-0.5, 0.5)
                ]
                # Frequency-reactive bubble color
                self.bubble_col[idx] = [r_c, g_c, b_c, alpha]
            else:
                # Bass: fewer, bigger, slower bubbles
                self.bubble_size[idx] = np.random.uniform(5.5, 9.0)
                rise_speed = np.random.uniform(0.6, 1.2) * (1.0 + self.react_bass * 0.2)
                self.bubble_vel[idx] = [
                    np.random.uniform(-0.2, 0.2),
                    rise_speed,
                    np.random.uniform(-0.2, 0.2)
                ]
                # Frequency-reactive bubble color
                self.bubble_col[idx] = [r_c, g_c, b_c, alpha]
                
            self.bubble_phase[idx] = np.random.uniform(0.0, 2 * np.pi)
            self.bubble_active[idx] = True
            self.bubble_is_fragment[idx] = False # Spawned bubbles are not fragments
            self.next_bubble_idx = (self.next_bubble_idx + 1) % len(self.bubble_pos)
            
        # Burst a small proportion of active normal bubbles on big volume hits
        if max_react > 0.8 and random.random() < 0.25:
            active_normal_indices = np.where(self.bubble_active & ~self.bubble_is_fragment)[0]
            if len(active_normal_indices) > 0:
                # Burst up to ~6% of active normal bubbles
                num_burst = max(1, int(len(active_normal_indices) * 0.06))
                burst_indices = np.random.choice(active_normal_indices, size=min(num_burst, len(active_normal_indices)), replace=False)
                for b_idx in burst_indices:
                    # Deactivate the original bubble
                    self.bubble_active[b_idx] = False
                    # Spawn 4 to 6 micro fragments
                    num_frags = random.randint(4, 6)
                    for _ in range(num_frags):
                        f_idx = self.next_bubble_idx
                        # Position is close to the original bubble's position
                        self.bubble_pos[f_idx] = self.bubble_pos[b_idx] + np.random.uniform(-0.05, 0.05, 3)
                        # Speed: shooting outwards
                        theta = np.random.uniform(0.0, 2 * np.pi)
                        phi = np.random.uniform(-np.pi/2, np.pi/2)
                        speed = np.random.uniform(1.5, 3.5)
                        self.bubble_vel[f_idx] = [
                            speed * np.cos(phi) * np.cos(theta),
                            speed * np.sin(phi) + 0.5, # slight upward bias
                            speed * np.cos(phi) * np.sin(theta)
                        ]
                        # Color: bright cyan-white
                        self.bubble_col[f_idx] = [0.6, 0.9, 1.0, 1.0]
                        self.bubble_size[f_idx] = np.random.uniform(0.7, 1.4)
                        self.bubble_phase[f_idx] = np.random.uniform(0.0, 2 * np.pi)
                        self.bubble_active[f_idx] = True
                        self.bubble_is_fragment[f_idx] = True
                        self.next_bubble_idx = (self.next_bubble_idx + 1) % len(self.bubble_pos)
            
        # Update Bubbles
        active = self.bubble_active
        if np.any(active):
            self.bubble_pos[active] += self.bubble_vel[active] * dt
            t = self.get_sim_time() * 3.5
            self.bubble_pos[active, 0] += np.sin(t + self.bubble_phase[active]) * dt * 0.55
            
            # Growth/Shrinkage
            self.bubble_size[active & ~self.bubble_is_fragment] += dt * 0.5
            self.bubble_size[active & self.bubble_is_fragment] -= dt * 3.0
            
            # Decay alpha for fragments
            self.bubble_col[active & self.bubble_is_fragment, 3] -= dt * 3.0
            
            # Apply height-based fade to normal active bubbles
            normal_active = active & ~self.bubble_is_fragment
            if np.any(normal_active):
                norm_heights = self.bubble_pos[normal_active, 1]
                norm_fade = np.clip((15.0 - norm_heights) / 5.0, 0.0, 1.0)
                self.bubble_col[normal_active, 3] *= norm_fade
                
            # Deactivate bubbles that are too high, shrunk too small, or faded completely
            too_high = (self.bubble_pos[:, 1] > 15.0) & active
            self.bubble_active[too_high] = False
            
            shrunk_too_small = (self.bubble_size <= 0.1) & active
            self.bubble_active[shrunk_too_small] = False
            
            faded_out = (self.bubble_col[:, 3] <= 0.0) & active
            self.bubble_active[faded_out] = False

        # Plankton drift
        t_val = self.get_sim_time()
        self.algae_pos[:, 0] += np.sin(t_val * 0.45 + self.algae_phase[:, 0]) * dt * 0.25
        self.algae_pos[:, 1] += np.cos(t_val * 0.35 + self.algae_phase[:, 1]) * dt * 0.18
        self.algae_pos[:, 2] += np.sin(t_val * 0.25 + self.algae_phase[:, 2]) * dt * 0.10
        
        x_out = self.algae_pos[:, 0] > 15.0
        self.algae_pos[x_out, 0] = -15.0
        x_out_neg = self.algae_pos[:, 0] < -15.0
        self.algae_pos[x_out_neg, 0] = 15.0
        
        y_out = self.algae_pos[:, 1] > 9.0
        self.algae_pos[y_out, 1] = -2.5
        y_out_neg = self.algae_pos[:, 1] < -2.5
        self.algae_pos[y_out_neg, 1] = 9.0
        
        # Individual plankton (algae) twinkling, modulated by the music
        # 1. Map depth-gradient (vertical spectral blending weights)
        y_norm = np.clip((self.algae_pos[:, 1] + 2.5) / 11.5, 0.0, 1.0)
        w_bass = (1.0 - y_norm) ** 2
        w_treble = y_norm ** 2
        w_mid = 1.0 - w_bass - w_treble

        # 2. Localized spectral energy per particle
        e_local = (w_bass * self.react_bass + 
                   w_mid * self.react_mid + 
                   w_treble * self.react_treble)

        # 3. Map horizontal stereo soundstage scale
        x_norm = np.clip(self.algae_pos[:, 0] / 15.0, -1.0, 1.0)
        s_coeff = 1.0 + 0.8 * (x_norm * self.current_stereo_panning)

        # 4. Compute final spatial-audio reaction factor
        r_local = e_local * s_coeff

        # 5. Tick individual phases forward (using self.algae_random_rates for flicker-free variation)
        self.algae_twinkle_phase += (1.5 + r_local * 6.0) * dt * self.algae_random_rates

        # 6. Apply to brightness (alpha)
        algae_twinkle = np.sin(self.algae_twinkle_phase) * 0.5 + 0.5
        self.algae_col[:, 3] = (0.15 + r_local * 0.85) * (0.2 + 0.8 * algae_twinkle)

        # Seabed bioluminescent phosphorescence twinkling
        self.seabed_twinkle_phase += (1.2 + self.react_bass * 5.0) * dt * np.random.uniform(0.7, 1.4, self.num_seabed_pts)
        for i in range(self.num_seabed_pts):
            if self.seabed_is_glowing[i]:
                twinkle_val = np.sin(self.seabed_twinkle_phase[i]) * 0.5 + 0.5
                self.seabed_col[i, 3] = (0.25 + self.react_bass * 0.75) * (0.15 + 0.85 * twinkle_val)

        # Update Jellyfish pulsing and movement physics
        for i in range(self.num_jelly):
            # Phase-locked directly to global tempo_phase to prevent drift and lock strictly on beat
            pulse_rate = 0.5 if (i % 2 == 1) else 1.0
            stagger = i * 0.25
            self.jelly_phase[i] = 2.0 * np.pi * (self.tempo_phase * pulse_rate + stagger)
            
            cos_val = np.cos(self.jelly_phase[i])
            if cos_val > 0.0:
                # Thrust synchronized directly with beat and amplified by real-time bass reactions
                thrust = 3.2 * cos_val * (1.0 + self.react_bass * 2.2)
                self.jelly_vel[i] += self.jelly_dir[i] * thrust * dt
            else:
                drag = 1.0
                self.jelly_vel[i] -= self.jelly_vel[i] * drag * dt
                
            # Apply position update
            self.jelly_pos[i] += self.jelly_vel[i] * dt
            
            # Gentle ambient upward buoyancy drift
            self.jelly_pos[i, 1] += 0.22 * dt
            
            # Reset jellyfish if they exit the water ceiling (expanded height limit to match bubbles)
            if self.jelly_pos[i, 1] > 16.0:
                self.jelly_pos[i, 1] = -11.0 # travel completely off-screen from bottom to top
                self.jelly_pos[i, 0] = np.random.uniform(-10.0, 10.0)
                self.jelly_pos[i, 2] = np.random.uniform(-4.0, 12.0)
                self.jelly_vel[i] = [0.0, 0.0, 0.0]
                self.jelly_dir[i] = self.get_tangential_jelly_dir(self.jelly_pos[i])
                
        # Update Glowing Squid Rarity pulsing, jet propulsion, and movement physics if active
        if self.active_rarity is not None and self.active_rarity['type'] == 'SQUID':
            bpm_rate = self.script_bpm / 60.0
            self.squid_phase += (bpm_rate * 0.7 + self.react_bass * 7.0) * dt
            cos_sq = np.cos(self.squid_phase)
            
            # Cooldown ticks down
            if not hasattr(self, 'squid_jet_cooldown'):
                self.squid_jet_cooldown = 0.0
            if self.squid_jet_cooldown > 0.0:
                self.squid_jet_cooldown -= dt

            # Big beat hit -> jet ink and speed off!
            if self.react_bass > 0.85 and self.squid_jet_cooldown <= 0.0:
                self.squid_vel += self.squid_dir * 18.0
                self.squid_jet_cooldown = 1.2
                
                # Jet ink: spawn a burst of dark ink bubbles behind the squid
                for _ in range(18):
                    idx = self.next_bubble_idx
                    self.bubble_pos[idx] = self.squid_pos - self.squid_dir * 1.5 + np.random.uniform(-0.35, 0.35, 3)
                    self.bubble_size[idx] = np.random.uniform(5.5, 10.0)
                    self.bubble_vel[idx] = -self.squid_dir * np.random.uniform(2.0, 5.0) + np.random.uniform(-0.6, 0.6, 3)
                    self.bubble_col[idx] = [0.01, 0.005, 0.03, 0.95] # dark ink
                    self.bubble_phase[idx] = np.random.uniform(0.0, 2.0 * np.pi)
                    self.bubble_active[idx] = True
                    self.bubble_is_fragment[idx] = False
                    self.next_bubble_idx = (self.next_bubble_idx + 1) % len(self.bubble_pos)

            if cos_sq > 0.0:
                # Cruising speed slowed down to 1/4 (thrust is scaled down from 4.5 to 1.125)
                sq_thrust = 1.125 * cos_sq * (1.0 + self.react_bass * 1.5)
                self.squid_vel += self.squid_dir * sq_thrust * dt
            
            # Drag is applied continuously to make impulse and cruising velocity decay naturally
            sq_drag = 1.2 if cos_sq <= 0.0 else 0.4
            self.squid_vel -= self.squid_vel * sq_drag * dt
            self.squid_pos += self.squid_vel * dt
            target_dir = np.array([-self.squid_pos[0]*0.1, 0.1, 4.0 - self.squid_pos[2]*0.2], dtype=np.float32)
            if np.linalg.norm(target_dir) > 1e-4:
                target_dir /= np.linalg.norm(target_dir)
                self.squid_dir = 0.95 * self.squid_dir + 0.05 * target_dir
                # Restrict squid direction vector to within 30 degrees of camera-perpendicular X-Y plane
                self.squid_dir[2] = np.clip(self.squid_dir[2], -0.45, 0.45)
                self.squid_dir /= np.linalg.norm(self.squid_dir)
            if self.squid_pos[1] > 18.0 or self.squid_pos[1] < -18.0 or abs(self.squid_pos[0]) > 24.0 or self.squid_pos[2] < -18.0 or self.squid_pos[2] > 24.0:
                self.squid_pos = np.array([np.random.uniform(-12.0, 12.0), np.random.uniform(-12.0, -4.0), np.random.uniform(-6.0, 8.0)], dtype=np.float32)
                self.squid_vel = np.array([0.0, 0.0, 0.0], dtype=np.float32)
                self.squid_dir = np.array([np.random.uniform(-1.0, 1.0), np.random.uniform(-0.2, 0.2), np.random.uniform(-0.45, 0.45)], dtype=np.float32)
                self.squid_dir /= np.linalg.norm(self.squid_dir)

    def render_underwater(self):
        act_mask = self.bubble_active
        if np.any(act_mask):
            b_pos = self.bubble_pos[act_mask]
            b_col = self.bubble_col[act_mask]
            b_size = -self.bubble_size[act_mask]
        else:
            b_pos = np.zeros((0, 3), dtype=np.float32)
            b_col = np.zeros((0, 4), dtype=np.float32)
            b_size = np.zeros(0, dtype=np.float32)
            
        a_pos = self.algae_pos
        a_col = self.algae_col
        a_size = -self.algae_size * (1.0 + self.react_treble * 0.4)
        
        # Render irregular Stalagmite Vents on seabed
        v_pos = self.vent_pts_pos
        v_col = self.vent_pts_col.copy()
        v_size = -self.vent_pts_size.copy()
        for i in range(self.num_vent_pts):
            if i % 24 >= 20: # Glowing crater mouths
                v_col[i, 3] = 0.5 + self.react_bass * 0.5
                v_size[i] *= (1.0 + self.react_bass * 0.4)
                
        # Render Sandy/Rocky Sea Floor Points
        seabed_pos = self.seabed_pos
        seabed_col = self.seabed_col
        seabed_size = self.seabed_size

        # Render Bioluminescent Seaweed / Waving Marine Plants
        plant_pos_list = []
        plant_col_list = []
        plant_size_list = []
        t_val = self.get_sim_time()
        
        for p in range(self.num_plants):
            base_col = self.plant_color[p]
            base_pos = self.plant_base[p]
            p_phase = self.plant_phase[p]
            
            for s in range(8):
                dist = s * 0.38
                y = base_pos[1] + dist
                sway = np.sin(2.0 * np.pi * self.tempo_phase + p_phase + s * 0.45) * 0.08 * (s + 1.0)
                x = base_pos[0] + sway
                z = base_pos[2]
                
                plant_pos_list.append([x, y, z])
                plant_col_list.append([
                    base_col[0], base_col[1], base_col[2],
                    0.65 * (1.0 - s * 0.09) * (0.5 + self.react_mid * 0.5)
                ])
                plant_size_list.append(-8.0 * (1.1 - s * 0.08))

        # Render Overhauled Moon and Crystal Jellyfish
        j_pos_list = []
        j_col_list = []
        j_size_list = []
        
        hood_tri_pos = []
        hood_tri_col = []
        
        for i in range(self.num_jelly):
            species = self.jelly_species[i] # 0 = Moon Jelly, 1 = Crystal Jelly
            base_col = self.jelly_col[i]
            base_size = self.jelly_size[i]
            pos = self.jelly_pos[i]
            dir_vec = self.jelly_dir[i]
            
            cos_val = np.cos(self.jelly_phase[i])
            
            # Setup dynamic local 3D orientation frame
            dx, dy, dz = dir_vec
            if abs(dx) < 0.9:
                u = np.cross(dir_vec, [1.0, 0.0, 0.0])
            else:
                u = np.cross(dir_vec, [0.0, 1.0, 0.0])
            u /= np.linalg.norm(u)
            w = np.cross(dir_vec, u)
            
            # HIGH-FIDELITY PARABOLOID DOME MESH MODEL (5 rings of 12 vertices = 60 vertices)
            # Dynamic deformation: contracts (elongates & pinches) on thrust, relaxes (shortens & widens) on glide
            if species == 0:     # Moon Jelly: round, flatter profile
                base_radius = 1.15
                base_height = 0.65
            else:               # Crystal Jelly: taller conical profile
                base_radius = 0.90
                base_height = 0.95
                
            deform_radius = base_radius * (1.0 - (0.22 + 0.08 * self.react_bass) * max(0.0, cos_val))
            deform_height = base_height * (1.0 + (0.28 + 0.12 * self.react_bass) * max(0.0, cos_val))
            
            # Generate the 60 bell dome coordinates
            v_coords = []
            v_cols = []
            for ring in range(5):
                h_frac = ring / 4.0 # 0.0 at apex, 1.0 at rim
                r_frac = np.sin(h_frac * np.pi / 2.0)
                
                ring_radius = deform_radius * r_frac
                ring_height = deform_height * (1.0 - h_frac)
                
                # Dynamic saucer-like contraction folding for Moon Jelly margin
                if species == 0 and ring >= 3:
                    pinch = 1.0 - 0.18 * max(0.0, cos_val) * (h_frac - 0.5)
                    ring_radius *= pinch
                
                # Glowing transparency profiles (increased opacity for gorgeous translucent bells)
                if species == 0:     # Moon Jelly: round, flatter profile
                    alpha_val = (0.16 - h_frac * 0.08) * (0.35 + self.react_treble * 0.85)
                else:               # Crystal Jelly: taller conical profile
                    alpha_val = (0.11 - h_frac * 0.05) * (0.35 + self.react_treble * 0.85)
                
                col = [base_col[0], base_col[1], base_col[2], alpha_val]
                
                for k in range(12):
                    ang = k * 2.0 * np.pi / 12.0
                    
                    # 8 shallow lobes along the bell rim for Moon Jelly
                    if species == 0 and ring == 4:
                        ring_radius_mod = ring_radius * (1.0 + 0.06 * np.cos(8.0 * ang))
                    else:
                        ring_radius_mod = ring_radius
                        
                    offset = (u * np.cos(ang) + w * np.sin(ang)) * ring_radius_mod + dir_vec * ring_height
                    jelly_v_pos = pos + offset
                    
                    v_coords.append(jelly_v_pos)
                    v_cols.append(col)
                    
                    # Fluorescent GFP margin organs: bright neon-green/teal points on the rim for Crystal Jelly
                    if species == 1 and ring == 4:
                        col_pt = [0.1, 0.95, 0.25, 0.85 * (0.8 + self.react_treble * 0.4)]
                        size_pt = -base_size * 0.25
                        j_pos_list.append(jelly_v_pos)
                        j_col_list.append(col_pt)
                        j_size_list.append(size_pt)
                    elif species == 1 and k % 3 == 0:
                        # Radial canals (ribs)
                        col_pt = [0.0, 0.95, 0.6, 0.45 * (0.8 + self.react_treble * 0.4)] # Glowing neon emerald-green rib
                        size_pt = -base_size * 0.12
                        j_pos_list.append(jelly_v_pos)
                        j_col_list.append(col_pt)
                        j_size_list.append(size_pt)
            
            # Build seamless triangle mesh quads connecting the 5 concentric rings (12 columns)
            for ring in range(4):
                for k in range(12):
                    k_next = (k + 1) % 12
                    i00 = ring * 12 + k
                    i10 = ring * 12 + k_next
                    i01 = (ring + 1) * 12 + k
                    i11 = (ring + 1) * 12 + k_next
                    
                    hood_tri_pos.append(v_coords[i00])
                    hood_tri_pos.append(v_coords[i10])
                    hood_tri_pos.append(v_coords[i11])
                    hood_tri_col.append(v_cols[i00])
                    hood_tri_col.append(v_cols[i10])
                    hood_tri_col.append(v_cols[i11])
                    
                    hood_tri_pos.append(v_coords[i00])
                    hood_tri_pos.append(v_coords[i11])
                    hood_tri_pos.append(v_coords[i01])
                    hood_tri_col.append(v_cols[i00])
                    hood_tri_col.append(v_cols[i11])
                    hood_tri_col.append(v_cols[i01])
            
            # SPECIES-SPECIFIC BIOLUMINESCENT ANATOMY DETAILS
            if species == 0:
                # 1. MOON JILLYFISH: 4 Glowing clover/horseshoe-shaped reproductive organ cores (each built of 3 small points to form a crescent)
                for k in range(4):
                    ang_base = k * 2.0 * np.pi / 4.0
                    # Create a horseshoe crescent loop
                    for sub in [-0.2, 0.0, 0.2]:
                        ang = ang_base + sub
                        rad_factor = 0.26 * (1.0 - 0.12 * abs(sub))
                        c_offset = (u * np.cos(ang) + w * np.sin(ang)) * rad_factor * deform_radius
                        c_pos = pos + dir_vec * (0.32 + 0.05 * np.cos(sub * 2.0)) * deform_height + c_offset
                        j_pos_list.append(c_pos)
                        j_col_list.append([1.0, 0.15, 0.65, 0.70 * (0.8 + self.react_mid * 0.4)])
                        j_size_list.append(-base_size * 0.32)
                    
                # 2. MOON JILLYFISH: 4 central frilly lavender-pink flowing oral arms
                for arm in range(4):
                    ang = arm * 2.0 * np.pi / 4.0
                    arm_anchor = pos + (u * np.cos(ang) + w * np.sin(ang)) * 0.15
                    for s in range(8):
                        dist = s * 0.22
                        wave_phase = self.jelly_phase[i] - s * 0.6 - t_val * 2.5
                        ripple = u * np.sin(wave_phase) * 0.06 * (s + 1.0) + w * np.cos(wave_phase * 1.2) * 0.04 * (s + 1.0)
                        arm_pos = arm_anchor - dir_vec * dist + ripple
                        
                        j_pos_list.append(arm_pos)
                        j_col_list.append([0.95, 0.25, 0.80, 0.45 * (1.0 - 0.11 * s) * (0.8 + self.react_mid * 0.4)])
                        j_size_list.append(-base_size * 0.45 * (1.0 - 0.08 * s))
                        
                # 3. MOON JILLYFISH: Fine fringe of short pink tentacles along the bell rim
                for k in range(12):
                    ang = k * 2.0 * np.pi / 12.0
                    rim_anchor = pos + (u * np.cos(ang) + w * np.sin(ang)) * deform_radius
                    for s in range(3):
                        dist = s * 0.12
                        wave_phase = self.jelly_phase[i] - s * 0.8 - t_val * 3.0
                        ripple = u * np.sin(wave_phase) * 0.03 + w * np.cos(wave_phase) * 0.03
                        ten_pos = rim_anchor - dir_vec * dist + ripple
                        
                        j_pos_list.append(ten_pos)
                        j_col_list.append([0.90, 0.35, 0.75, 0.30 * (1.0 - 0.25 * s) * (0.8 + self.react_treble * 0.4)])
                        j_size_list.append(-base_size * 0.15 * (1.0 - 0.15 * s))
                        
            else:
                # 1. CRYSTAL JELLYFISH: Glowing neon-cyan/white inner mouth core
                for k in range(3):
                    c_pos = pos + dir_vec * (0.2 + k * 0.18) * deform_height
                    j_pos_list.append(c_pos)
                    j_col_list.append([0.0, 0.85, 1.0, 0.65 * (0.8 + self.react_mid * 0.4)])
                    j_size_list.append(-base_size * 0.45)
                    
                # 2. CRYSTAL JELLYFISH: Exceptionally long, thin trailing bioluminescent neon-blue tentacles
                num_t = 12
                for k in range(num_t):
                    ang = k * 2.0 * np.pi / num_t
                    rim_anchor = pos + (u * np.cos(ang) + w * np.sin(ang)) * deform_radius
                    for s in range(14): # Very long, majestic trailing lines
                        dist = s * 0.45
                        wave_phase = self.jelly_phase[i] - s * 0.42 - t_val * 2.2
                        wave_amp = 0.13 * (s + 1.0)
                        ripple = u * np.sin(wave_phase) * wave_amp + w * np.cos(wave_phase * 1.15) * wave_amp * 0.65
                        ten_pos = rim_anchor - dir_vec * dist + ripple
                        
                        j_pos_list.append(ten_pos)
                        # Fade out to deep bioluminescent blue at the tips
                        alpha_fade = 0.55 * (1.0 - 0.06 * s) * (0.8 + self.react_treble * 0.4)
                        gfp_blend = max(0.0, 1.0 - s * 0.15) # Green near the base rim, blending to blue tips
                        col_r = 0.0
                        col_g = 0.55 * gfp_blend + 0.1 * (1.0 - gfp_blend)
                        col_b = 1.0
                        j_col_list.append([col_r, col_g, col_b, alpha_fade])
                        j_size_list.append(-base_size * 0.16 * (1.0 - 0.04 * s))
                        
            # Draw Squid, Manta, Seahorse, or Lantern Fish Rarity as solid 3D triangle meshes
            if self.active_rarity is not None and self.active_rarity['type'] == 'SQUID':
                sq_pts, sq_cols = make_solid_squid(self.squid_pos, self.squid_dir, self.squid_phase, self.react_bass, self.react_mid, self.react_treble)
                hood_tri_pos.extend(sq_pts)
                hood_tri_col.extend(sq_cols)
                
            if self.active_rarity is not None and self.active_rarity['type'] == 'MANTA':
                m_pts, m_cols = make_solid_manta(self.active_rarity['pos'], self.active_rarity['dir'], self.active_rarity['phase'])
                hood_tri_pos.extend(m_pts)
                hood_tri_col.extend(m_cols)
                
            if self.active_rarity is not None and self.active_rarity['type'] == 'SEAHORSE':
                sh_pts, sh_cols = make_solid_seahorse(self.active_rarity['pos'], self.active_rarity['phase'])
                hood_tri_pos.extend(sh_pts)
                hood_tri_col.extend(sh_cols)
                
            if self.active_rarity is not None and self.active_rarity['type'] == 'LANTERN_FISH':
                r = self.active_rarity
                center = r['pos']
                for k in range(len(r['offsets'])):
                    fish_pos = center + r['offsets'][k]
                    fish_pos[1] += np.sin(self.get_sim_time() * 8.0 + k) * 0.15
                    # Recolor fish bodies to beautiful matte deep purple-blue and indigo
                    col_fish = [0.18, 0.15, 0.45, 1.0] if k % 2 == 0 else [0.08, 0.05, 0.32, 1.0]
                    lf_pts, lf_cols = make_solid_fish(fish_pos, r['dir'], self.get_sim_time() + k, col_fish)
                    hood_tri_pos.extend(lf_pts)
                    hood_tri_col.extend(lf_cols)
                    
        j_pos_arr = np.array(j_pos_list, dtype=np.float32) if len(j_pos_list) > 0 else np.zeros((0, 3), dtype=np.float32)
        j_col_arr = np.array(j_col_list, dtype=np.float32) if len(j_col_list) > 0 else np.zeros((0, 4), dtype=np.float32)
        j_size_arr = np.array(j_size_list, dtype=np.float32) if len(j_size_list) > 0 else np.zeros(0, dtype=np.float32)

        # Convert seaweed plant lists to NumPy arrays
        p_pos_arr = np.array(plant_pos_list, dtype=np.float32) if len(plant_pos_list) > 0 else np.zeros((0, 3), dtype=np.float32)
        p_col_arr = np.array(plant_col_list, dtype=np.float32) if len(plant_col_list) > 0 else np.zeros((0, 4), dtype=np.float32)
        p_size_arr = np.array(plant_size_list, dtype=np.float32) if len(plant_size_list) > 0 else np.zeros(0, dtype=np.float32)

        # Concatenate all visual elements into unified arrays for high-performance rendering
        pos_combined = np.concatenate([b_pos, a_pos, v_pos, seabed_pos, p_pos_arr, j_pos_arr], axis=0).astype(np.float32)
        col_combined = np.concatenate([b_col, a_col, v_col, seabed_col, p_col_arr, j_col_arr], axis=0).astype(np.float32)
        size_combined = np.concatenate([b_size, a_size, v_size, seabed_size, p_size_arr, j_size_arr], axis=0).astype(np.float32)

        return pos_combined, col_combined, size_combined, np.array(hood_tri_pos, dtype=np.float32), np.array(hood_tri_col, dtype=np.float32)
