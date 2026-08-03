import numpy as np
import random
from constants import COLORS
from helpers import get_palette_colors
from meshes import make_solid_bird, make_solid_butterfly

class MandalaModeMixin:
    def init_mandala_mode(self):
        M = 250
        if not hasattr(self, 'mandala_slices'):
            self.mandala_slices = 12
        self.mandala_base_pos = np.zeros((M, 3), dtype=np.float32)
        self.mandala_base_pos[:, 1] = 4.0
        self.mandala_base_vel = np.zeros((M, 3), dtype=np.float32)
        self.mandala_base_ages = np.zeros(M, dtype=np.float32)
        self.mandala_base_max_ages = np.zeros(M, dtype=np.float32)
        self.mandala_base_col = np.zeros((M, 4), dtype=np.float32)
        self.mandala_base_size = np.zeros(M, dtype=np.float32)
        
        for i in range(M):
            self.reset_mandala_particle(i)

    def _launch_mandala_burst(self, speed_range=(10.0, 16.0)):
        center = np.array([0.0, 4.0, 0.0], dtype=np.float32)
        particle_count = len(self.mandala_base_pos)
        self.mandala_base_pos[:] = center
        angles = np.linspace(0.0, 2.0 * np.pi, particle_count, endpoint=False)
        angles += np.random.uniform(-0.08, 0.08, particle_count)
        speeds = np.random.uniform(*speed_range, particle_count)
        self.mandala_base_vel[:, 0] = np.cos(angles) * speeds
        self.mandala_base_vel[:, 1] = np.sin(angles) * speeds
        self.mandala_base_vel[:, 2] = np.random.uniform(-0.6, 0.6, particle_count)
        self.mandala_base_ages[:] = 0.0
        self.mandala_base_max_ages[:] = np.random.uniform(2.2, 3.6, particle_count)

    def reset_mandala_particle(self, idx):
        self.mandala_base_pos[idx] = [0.0, 4.0, 0.0]
        angle = np.random.uniform(0.0, 2 * np.pi)
        speed = np.random.uniform(1.5, 4.5)
        self.mandala_base_vel[idx, 0] = speed * np.cos(angle)
        self.mandala_base_vel[idx, 1] = speed * np.sin(angle)
        self.mandala_base_vel[idx, 2] = np.random.uniform(-0.2, 0.2)
        
        self.mandala_base_ages[idx] = 0.0
        self.mandala_base_max_ages[idx] = np.random.uniform(1.8, 3.2)
        if self.opt_color_mode != 'REALISTIC':
            pal = get_palette_colors(self.opt_color_mode)
            col_choice = random.choice(pal)
        else:
            col_choice = random.choice([
                COLORS["sodium_gold"],
                COLORS["strontium_red"],
                COLORS["potassium_purple"],
                COLORS["copper_blue"],
                COLORS["magnesium_white"]
            ])
        self.mandala_base_col[idx] = col_choice
        self.mandala_base_col[idx, 3] = np.random.uniform(0.6, 1.0)
        self.mandala_base_size[idx] = np.random.uniform(5.0, 11.0)

    def update_mandala(self, dt):
        if self.mandala_fog_halo_timer > 0.0:
            self.mandala_fog_halo_timer = max(0.0, self.mandala_fog_halo_timer - dt)
        if self.mandala_squiggle_timer > 0.0:
            self.mandala_squiggle_timer = max(0.0, self.mandala_squiggle_timer - dt)
        if self.mandala_starburst_rebirth_timer > 0.0:
            self.mandala_starburst_rebirth_timer -= dt
            if self.mandala_starburst_rebirth_timer <= 0.0:
                self._launch_mandala_burst((12.0, 19.0))
        if self.mandala_black_hole_timer > 0.0:
            self.mandala_black_hole_timer -= dt
            center = np.array([0.0, 4.0, 0.0], dtype=np.float32)
            self.mandala_base_pos += (center - self.mandala_base_pos) * min(1.0, dt * 7.0)
            self.mandala_base_vel *= max(0.0, 1.0 - dt * 8.0)
            self.mandala_base_ages[:] = 0.0
            if self.mandala_black_hole_timer <= 0.0:
                self._launch_mandala_burst((12.0, 19.0))
            return

        speed_factor = 1.0 + self.react_bass * 2.5
        if self.opt_gravity > 0.0:
            self.mandala_base_vel[:, 1] -= 9.81 * self.opt_gravity * dt
        self.mandala_base_pos += self.mandala_base_vel * speed_factor * dt

        if self.opt_trailers > 0:
            target_history_len = self.opt_trailers * 2
            if not hasattr(self, 'mandala_history') or self.mandala_history is None:
                self.mandala_history = []
            self.mandala_history.append((self.mandala_base_pos.copy(), self.mandala_base_col.copy(), self.mandala_base_ages.copy(), self.mandala_base_max_ages.copy()))
            while len(self.mandala_history) > target_history_len:
                self.mandala_history.pop(0)
        else:
            self.mandala_history = None
        
        center = np.array([0.0, 4.0, 0.0], dtype=np.float32)
        to_center = center[np.newaxis, :] - self.mandala_base_pos
        dist_c = np.linalg.norm(to_center, axis=1, keepdims=True) + 1e-6
        
        tangent_x = -to_center[:, 1] / dist_c[:, 0]
        tangent_y = to_center[:, 0] / dist_c[:, 0]
        self.mandala_base_pos[:, 0] += tangent_x * (0.8 + self.react_mid * 2.0) * dt
        self.mandala_base_pos[:, 1] += tangent_y * (0.8 + self.react_mid * 2.0) * dt
        
        self.mandala_base_ages += dt
        expired = self.mandala_base_ages >= self.mandala_base_max_ages
        for idx in np.where(expired)[0]:
            self.reset_mandala_particle(idx)

    def render_mandala(self):
        pal = get_palette_colors(self.opt_color_mode) if self.opt_color_mode != 'REALISTIC' else None
        M = len(self.mandala_base_pos)
        S = self.mandala_slices
        angles = np.arange(S) * (2 * np.pi / S) + (self.get_sim_time() * (0.15 + self.react_mid * 0.6))
        shifted = self.mandala_base_pos - np.array([0.0, 4.0, 0.0])
        
        x = shifted[:, 0][:, np.newaxis]
        y = shifted[:, 1][:, np.newaxis]
        z = shifted[:, 2][:, np.newaxis]
        
        cos_a = np.cos(angles)[np.newaxis, :]
        sin_a = np.sin(angles)[np.newaxis, :]
        
        rot_x = x * cos_a - y * sin_a
        rot_y = x * sin_a + y * cos_a
        rot_z = np.tile(z, (1, S))
        
        rot_pos = np.stack([rot_x, rot_y + 4.0, rot_z], axis=2)
        pos_arr = rot_pos.reshape(-1, 3).astype(np.float32)
        col_arr = np.repeat(self.mandala_base_col, S, axis=0).copy()
        
        # Apply current life ratio fade to current colors before historical appending
        ages_rep = np.repeat(self.mandala_base_ages, S)
        max_ages_rep = np.repeat(self.mandala_base_max_ages, S)
        life_ratio = ages_rep / max_ages_rep
        col_arr[:, 3] *= np.clip(1.0 - life_ratio, 0.0, 1.0)
        
        reactivity = self.opt_particle_reactivity / 10.0
        beat_level = np.clip(max(self.react_bass, self.react_mid, self.react_treble), 0.0, 1.5)
        particle_pulse = 1.0 + reactivity * beat_level * 1.5
        current_size_arr = np.repeat(self.mandala_base_size, S) * particle_pulse
        
        all_pos_list = [pos_arr]
        all_col_list = [col_arr]
        all_size_list = [current_size_arr]

        if hasattr(self, 'mandala_history') and self.mandala_history is not None and len(self.mandala_history) > 0:
            hist_len = len(self.mandala_history)
            for h_idx, (h_pos, h_col, h_ages, h_max_ages) in enumerate(self.mandala_history):
                fade_factor = (h_idx + 1) / (hist_len + 1)
                shifted_h = h_pos - np.array([0.0, 4.0, 0.0])
                hx = shifted_h[:, 0][:, np.newaxis]
                hy = shifted_h[:, 1][:, np.newaxis]
                hz = shifted_h[:, 2][:, np.newaxis]
                
                h_rot_x = hx * cos_a - hy * sin_a
                h_rot_y = hx * sin_a + hy * cos_a
                h_rot_z = np.tile(hz, (1, S))
                
                h_rot_pos = np.stack([h_rot_x, h_rot_y + 4.0, h_rot_z], axis=2)
                h_pos_arr = h_rot_pos.reshape(-1, 3).astype(np.float32)
                
                h_col_arr = np.repeat(h_col, S, axis=0).copy()
                h_ages_rep = np.repeat(h_ages, S)
                h_max_rep = np.repeat(h_max_ages, S)
                h_ratio = h_ages_rep / h_max_rep
                
                h_col_arr[:, 3] *= np.clip(1.0 - h_ratio, 0.0, 1.0) * fade_factor * 0.45
                h_size_arr = np.repeat(self.mandala_base_size, S) * particle_pulse * (0.4 + 0.6 * fade_factor)
                
                all_pos_list.append(h_pos_arr)
                all_col_list.append(h_col_arr)
                all_size_list.append(h_size_arr)
                
        pos_arr = np.concatenate(all_pos_list, axis=0)
        col_arr = np.concatenate(all_col_list, axis=0)
        size_arr = np.concatenate(all_size_list, axis=0)
        
        mandala_tri_pos = []
        mandala_tri_col = []
        
        # Render the Halo Effect as one continuous, ethereal golden fog band.
        # Closely spaced overlapping annuli approximate a smooth Gaussian density profile:
        # its brightness peaks at the center, then disappears softly into the black background.
        if self.mandala_fog_halo_timer > 0.0:
            center = np.array([0.0, 4.0, 0.35], dtype=np.float32)
            lifetime_progress = np.clip(self.mandala_fog_halo_timer / 5.0, 0.0, 1.0)
            fade = min(1.0, lifetime_progress * 3.0, (1.0 - lifetime_progress) * 4.0 + 0.25)
            breathe = 1.0 + np.sin(self.get_sim_time() * 1.4) * 0.035
            base_radius = 5.0 * breathe
            segments = 128
            fog_layers = 41
            fog_half_width = 1.8
            annulus_width = fog_half_width * 0.14

            for layer in range(fog_layers):
                offset = -fog_half_width + (2.0 * fog_half_width * layer / (fog_layers - 1))
                normalized_offset = offset / fog_half_width
                density = np.exp(-4.5 * normalized_offset * normalized_offset)
                radius = base_radius + offset
                alpha = 0.032 * density * fade
                gold = [1.0, 0.72 + density * 0.16, 0.16 + density * 0.12]

                for idx in range(segments):
                    a0 = 2.0 * np.pi * idx / segments
                    a1 = 2.0 * np.pi * (idx + 1) / segments
                    inner0 = center + np.array([(radius - annulus_width) * np.cos(a0), (radius - annulus_width) * np.sin(a0), 0.0])
                    outer0 = center + np.array([(radius + annulus_width) * np.cos(a0), (radius + annulus_width) * np.sin(a0), 0.0])
                    inner1 = center + np.array([(radius - annulus_width) * np.cos(a1), (radius - annulus_width) * np.sin(a1), 0.0])
                    outer1 = center + np.array([(radius + annulus_width) * np.cos(a1), (radius + annulus_width) * np.sin(a1), 0.0])
                    mandala_tri_pos.extend((inner0, outer0, outer1, inner0, outer1, inner1))
                    mandala_tri_col.extend([gold + [alpha]] * 6)
        
        # Render Peace Symbol Overlay in central space (Un-sliced to remain perfectly legible)
        if self.peace_symbol_timer > 0.0:
            peace_pos, peace_col, peace_size = [], [], []
            R = 3.6 + np.sin(self.get_sim_time() * 6.0) * 0.15
            center = np.array([0.0, 4.0, 0.0], dtype=np.float32)
            alpha_p = np.clip(self.peace_symbol_timer / 1.0, 0.0, 1.0) * (0.65 + self.react_mid * 0.35)
            p_col_rgb = list(pal[0][:3]) if pal else [1.0, 0.82, 0.1]
            for k_pt in range(60):
                ang = k_pt * 2.0 * np.pi / 60.0
                pt = center + np.array([R * np.cos(ang), R * np.sin(ang), 0.0], dtype=np.float32)
                peace_pos.append(pt)
                peace_col.append(p_col_rgb + [alpha_p])
                peace_size.append(10.0 + np.sin(self.get_sim_time() * 12.0 + k_pt) * 4.0)
            for y_pt in np.linspace(-R, R, 20):
                pt = center + np.array([0.0, y_pt, 0.0], dtype=np.float32)
                peace_pos.append(pt)
                peace_col.append([1.0, 0.82, 0.1, alpha_p])
                peace_size.append(10.0)
            for r_pt in np.linspace(0.0, R, 15):
                pt = center + np.array([r_pt * np.cos(5.0 * np.pi / 4.0), r_pt * np.sin(5.0 * np.pi / 4.0), 0.0], dtype=np.float32)
                peace_pos.append(pt)
                peace_col.append([1.0, 0.82, 0.1, alpha_p])
                peace_size.append(10.0)
            for r_pt in np.linspace(0.0, R, 15):
                pt = center + np.array([r_pt * np.cos(7.0 * np.pi / 4.0), r_pt * np.sin(7.0 * np.pi / 4.0), 0.0], dtype=np.float32)
                peace_pos.append(pt)
                peace_col.append([1.0, 0.82, 0.1, alpha_p])
                peace_size.append(10.0)
            pos_arr = np.concatenate([pos_arr, np.array(peace_pos, dtype=np.float32)], axis=0)
            col_arr = np.concatenate([col_arr, np.array(peace_col, dtype=np.float32)], axis=0)
            size_arr = np.concatenate([size_arr, np.array(peace_size, dtype=np.float32)], axis=0)
            
        # Render the particle-based Ring Effect with outward firing sparks.
        if self.ring_effect_timer > 0.0:
            halo_pos, halo_col, halo_size = [], [], []
            R_halo = 5.2 + self.react_bass * 1.5 + np.sin(self.get_sim_time() * 5.0) * 0.25
            center = np.array([0.0, 4.0, 0.0], dtype=np.float32)
            alpha_h = np.clip(self.ring_effect_timer / 1.0, 0.0, 1.0)
            for i_h in range(80):
                ang = i_h * 2.0 * np.pi / 80.0 + self.get_sim_time() * 1.5
                pt = center + np.array([R_halo * np.cos(ang), R_halo * np.sin(ang), 0.0], dtype=np.float32)
                halo_pos.append(pt)
                halo_col.append([0.1, 0.85, 1.0, alpha_h])
                halo_size.append(12.0)
                if i_h % 4 == 0 and random.random() < 0.28:
                    spark_r = R_halo + np.random.uniform(0.1, 1.8)
                    spark_ang = ang + np.random.uniform(-0.1, 0.1)
                    s_pt = center + np.array([spark_r * np.cos(spark_ang), spark_r * np.sin(spark_ang), np.random.uniform(-0.1, 0.1)], dtype=np.float32)
                    halo_pos.append(s_pt)
                    h_col_rgb = list(pal[1 % len(pal)][:3]) if pal else [0.9, 0.15, 0.5]
                    halo_col.append(h_col_rgb + [alpha_h * 0.6])
                    halo_size.append(6.0)
            pos_arr = np.concatenate([pos_arr, np.array(halo_pos, dtype=np.float32)], axis=0)
            col_arr = np.concatenate([col_arr, np.array(halo_col, dtype=np.float32)], axis=0)
            size_arr = np.concatenate([size_arr, np.array(halo_size, dtype=np.float32)], axis=0)
            
        # Render Mandala Mode Symmetrical Rarities (Bird, Smoke, Sun Burst, Butterfly)
        if self.active_rarity is not None:
            r = self.active_rarity
            r_pos_list, r_col_list, r_size_list = [], [], []
            if r['type'] == 'BIRD':
                # Render high-quality 3D Bird singleton directly as solid asymmetric (no pairs!)
                b_pts, b_cols = make_solid_bird(r['pos'], np.array([np.cos(r['ang']), np.sin(r['ang']), 0.0]), r['phase'])
                mandala_tri_pos.extend(b_pts)
                mandala_tri_col.extend(b_cols)
            elif r['type'] == 'SMOKE':
                for j in range(len(r['particles_pos'])):
                    pt_relative = r['particles_pos'][j] - np.array([0.0, 4.0, 0.0])
                    r_pos_list.append(pt_relative)
                    rad = r['particles_rad'][j]
                    alpha = 0.72 * (1.0 - rad / 12.0)
                    c1 = list(pal[0][:3]) if pal else [0.15, 0.85, 0.92]
                    c2 = list(pal[2 % len(pal)][:3]) if pal else [0.75, 0.12, 0.92]
                    col = c1 + [alpha] if j % 2 == 0 else c2 + [alpha]
                    r_col_list.append(col)
                    r_size_list.append(18.0 + rad * 3.5) # made smoke highly visible
            elif r['type'] == 'SUN_BURST':
                # Sunburst overhaul: 16 spokes, 24 points per spoke, golden-orange gradients, larger points
                for i_sp in range(16):
                    spoke_ang = i_sp * (np.pi / 8.0) + r['phase']
                    max_rad = (3.5 - r['life']) * 4.5
                    for j_pt in range(24):
                        pt_frac = j_pt / 23.0
                        rad = pt_frac * max_rad
                        pt_relative = np.array([rad * np.cos(spoke_ang), rad * np.sin(spoke_ang), 0.0])
                        r_pos_list.append(pt_relative)
                        alpha = 0.8 * (1.0 - pt_frac) * np.clip(r['life'] / 1.0, 0.0, 1.0)
                        if pal:
                            c_mix = (1.0 - pt_frac) * np.array(pal[0][:3]) + pt_frac * np.array(pal[2 % len(pal)][:3])
                            r_col_list.append(list(c_mix) + [alpha])
                        else:
                            r_col_list.append([1.0, 0.4 + 0.55 * (1.0 - pt_frac), 0.0, alpha])
                        r_size_list.append(16.0 * (1.0 - pt_frac * 0.3))
            elif r['type'] == 'BUTTERFLY':
                # Render high-quality 3D Butterfly singleton directly as solid asymmetric (no pairs!)
                bf_pts, bf_cols = make_solid_butterfly(r['pos'], np.array([np.cos(r['ang']), np.sin(r['ang']), 0.0]), r['phase'])
                if pal:
                    for idx_c in range(len(bf_cols)):
                        bf_cols[idx_c] = list(pal[idx_c % len(pal)][:3]) + [bf_cols[idx_c][3]]
                mandala_tri_pos.extend(bf_pts)
                mandala_tri_col.extend(bf_cols)
            if r['type'] == 'BIRD' and pal:
                for idx_c in range(len(mandala_tri_col)):
                    mandala_tri_col[idx_c] = list(pal[idx_c % len(pal)][:3]) + [mandala_tri_col[idx_c][3]]
                
            if len(r_pos_list) > 0:
                sym_pos, sym_col, sym_size = [], [], []
                angles_s = np.arange(S) * (2 * np.pi / S)
                r_pos_arr = np.array(r_pos_list)
                r_col_arr = np.array(r_col_list)
                r_size_arr = np.array(r_size_list)
                for ang_s in angles_s:
                    cos_s = np.cos(ang_s)
                    sin_s = np.sin(ang_s)
                    rot_x = r_pos_arr[:, 0] * cos_s - r_pos_arr[:, 1] * sin_s
                    rot_y = r_pos_arr[:, 0] * sin_s + r_pos_arr[:, 1] * cos_s
                    rot_z = r_pos_arr[:, 2]
                    for idx_pt in range(len(r_pos_arr)):
                        sym_pos.append([rot_x[idx_pt], rot_y[idx_pt] + 4.0, rot_z[idx_pt]])
                        sym_col.append(r_col_arr[idx_pt])
                        sym_size.append(r_size_arr[idx_pt])
                pos_arr = np.concatenate([pos_arr, np.array(sym_pos, dtype=np.float32)], axis=0)
                col_arr = np.concatenate([col_arr, np.array(sym_col, dtype=np.float32)], axis=0)
                size_arr = np.concatenate([size_arr, np.array(sym_size, dtype=np.float32)], axis=0)
                
        return pos_arr, col_arr, size_arr, np.array(mandala_tri_pos, dtype=np.float32), np.array(mandala_tri_col, dtype=np.float32)

    def get_mandala_lines(self):
        if self.mandala_squiggle_timer <= 0.0:
            return [], []

        line_pos = []
        line_col = []
        center = np.array([0.0, 4.0, 0.0], dtype=np.float32)
        palette = get_palette_colors(self.opt_color_mode) if self.opt_color_mode != 'REALISTIC' else None
        lifetime = 5.0
        progress = 1.0 - np.clip(self.mandala_squiggle_timer / lifetime, 0.0, 1.0)
        ray_length = 2.0 + progress * 10.0
        segments = 36

        for sector in range(self.mandala_slices):
            base_angle = 2.0 * np.pi * sector / self.mandala_slices
            color = list(palette[sector % len(palette)][:3]) if palette else [1.0, 0.72, 0.2]
            previous = center.copy()
            for idx in range(1, segments + 1):
                fraction = idx / segments
                radius = ray_length * fraction
                wobble = np.sin(fraction * 8.0 * np.pi - self.get_sim_time() * 2.0 + sector * 0.7) * 0.18 * fraction
                angle = base_angle + wobble
                current = center + np.array([radius * np.cos(angle), radius * np.sin(angle), 0.05], dtype=np.float32)
                alpha = (1.0 - fraction * 0.45) * np.clip(self.mandala_squiggle_timer, 0.0, 1.0)
                line_pos.extend((previous, current))
                line_col.extend((color + [alpha], color + [alpha]))
                previous = current

        return line_pos, line_col

    def spawn_rarity_mandala(self, r_type):
        if r_type == "BIRD":
            self.active_rarity = {
                'type': 'BIRD',
                'pos': np.array([0.0, 4.0, 0.0], dtype=np.float32),
                'ang': np.random.uniform(0.0, 2*np.pi),
                'phase': 0.0,
                'life': 12.0,
                'max_life': 12.0
            }
        elif r_type == "SMOKE":
            self.active_rarity = {
                'type': 'SMOKE',
                'particles_pos': [],
                'particles_ang': [],
                'particles_rad': [],
                'life': 6.0,
                'max_life': 6.0
            }
        elif r_type == "SUN_BURST":
            self.active_rarity = {
                'type': 'SUN_BURST',
                'phase': 0.0,
                'life': 3.5,
                'max_life': 3.5
            }
        elif r_type == "BUTTERFLY":
            self.active_rarity = {
                'type': 'BUTTERFLY',
                'pos': np.array([0.0, 4.0, 0.0], dtype=np.float32),
                'ang': np.random.uniform(0.0, 2*np.pi),
                'phase': 0.0,
                'life': 15.0,
                'max_life': 15.0
            }

    def update_rarity_mandala(self, r, dt):
        t_type = r['type']
        if t_type == "BIRD":
            r['phase'] += dt * 15.0
            speed = 4.2 * (1.0 + self.react_mid * 0.5)
            r['pos'][0] += np.cos(r['ang']) * speed * dt
            r['pos'][1] += np.sin(r['ang']) * speed * dt
            # Fully flies off screen boundaries before deactivating
            if np.linalg.norm(r['pos'] - np.array([0.0, 4.0, 0.0])) > 24.0:
                self.active_rarity = None
        elif t_type == "SMOKE":
            # Spawn 4 smoke particles per frame at slightly offset spiral progression angles
            for step in range(4):
                ang = (r['life'] * 3.5 + step * 0.15) % (2.0 * np.pi)
                r['particles_pos'].append(np.array([0.0, 4.0, 0.0], dtype=np.float32))
                r['particles_ang'].append(ang)
                r['particles_rad'].append(0.0)
            rem_pos, rem_ang, rem_rad = [], [], []
            for j in range(len(r['particles_pos'])):
                r['particles_rad'][j] += dt * 2.8 * (1.0 + self.react_mid * 0.4)
                r['particles_ang'][j] += dt * 3.0
                rad = r['particles_rad'][j]
                theta = r['particles_ang'][j]
                r['particles_pos'][j] = np.array([rad * np.cos(theta), 4.0 + rad * np.sin(theta), np.sin(theta * 2.0) * 0.15], dtype=np.float32)
                if rad < 12.0:
                    rem_pos.append(r['particles_pos'][j])
                    rem_ang.append(r['particles_ang'][j])
                    rem_rad.append(r['particles_rad'][j])
            r['particles_pos'] = rem_pos
            r['particles_ang'] = rem_ang
            r['particles_rad'] = rem_rad
        elif t_type == "SUN_BURST":
            r['phase'] += dt * 0.4
        elif t_type == "BUTTERFLY":
            # Music-modulated wing flap rate
            flap_rate = 24.0 + self.react_treble * 35.0
            r['phase'] += dt * flap_rate
            # Music-modulated turning angles/speeds
            erratic_factor = 6.0 + self.react_bass * 12.0
            r['ang'] += np.random.uniform(-1.8, 1.8) * dt * erratic_factor
            # Music-modulated speed and bobbing amplitude
            speed = 3.6 + self.react_mid * 5.0
            bob_amp = 1.5 + self.react_bass * 4.0
            r['pos'][0] += (np.cos(r['ang']) * speed + np.sin(r['phase'] * 3.0) * bob_amp) * dt
            r['pos'][1] += (np.sin(r['ang']) * speed + np.cos(r['phase'] * 3.5) * bob_amp) * dt
            # Fully flies off screen boundaries before deactivating
            if np.linalg.norm(r['pos'] - np.array([0.0, 4.0, 0.0])) > 24.0:
                self.active_rarity = None

    def trigger_climax_mandala(self, routine_name):
        if routine_name == "Peace Symbol":
            self.peace_symbol_timer = 5.0
            for idx in range(len(self.mandala_base_pos)):
                self.mandala_base_pos[idx] = [0.0, 4.0, 0.0]
                angle = (idx / len(self.mandala_base_pos)) * 2.0 * np.pi
                speed = np.random.uniform(9.0, 14.0)
                self.mandala_base_vel[idx, 0] = speed * np.cos(angle)
                self.mandala_base_vel[idx, 1] = speed * np.sin(angle)
                self.mandala_base_vel[idx, 2] = np.random.uniform(-0.5, 0.5)
                self.mandala_base_ages[idx] = 0.0
                self.mandala_base_max_ages[idx] = np.random.uniform(2.0, 3.0)
                self.mandala_base_col[idx] = [1.0, 0.8, 0.1, 1.0] if idx % 2 == 0 else [1.0, 0.3, 0.2, 1.0]
                self.mandala_base_size[idx] = np.random.uniform(10.0, 16.0)
        elif routine_name == "Ring Effect":
            self.ring_effect_timer = 5.0
            self._launch_mandala_burst((11.0, 17.0))
        elif routine_name == "Halo Effect":
            self.mandala_fog_halo_timer = 5.0
        elif routine_name == "Smoke!":
            self.active_rarity = None
            self.spawn_rarity_mandala("SMOKE")
        elif routine_name == "Star Burst":
            self.active_rarity = None
            self.spawn_rarity_mandala("SUN_BURST")
        elif routine_name == "Starburst Effect":
            center = np.array([0.0, 4.0, 0.0], dtype=np.float32)
            outward = self.mandala_base_pos - center
            distances = np.linalg.norm(outward[:, :2], axis=1)
            angles = np.arctan2(outward[:, 1], outward[:, 0])
            angles[distances < 0.01] = np.random.uniform(0.0, 2.0 * np.pi, np.count_nonzero(distances < 0.01))
            speeds = np.random.uniform(12.0, 20.0, len(self.mandala_base_pos))
            self.mandala_base_vel[:, 0] = np.cos(angles) * speeds
            self.mandala_base_vel[:, 1] = np.sin(angles) * speeds
            self.mandala_base_vel[:, 2] = np.random.uniform(-0.8, 0.8, len(self.mandala_base_pos))
            self.mandala_base_ages[:] = 0.0
            self.mandala_base_max_ages[:] = 0.8
            self.mandala_starburst_rebirth_timer = 0.65
        elif routine_name == "Black Hole Effect":
            self.mandala_black_hole_timer = 1.25
        elif routine_name == "Squiggles":
            self.mandala_squiggle_timer = 5.0
