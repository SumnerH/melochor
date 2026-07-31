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
        speed_factor = 1.0 + self.react_bass * 2.5
        if self.opt_gravity > 0.0:
            self.mandala_base_vel[:, 1] -= 3.0 * self.opt_gravity * dt
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
        
        current_size_arr = np.repeat(self.mandala_base_size, S) * (1.0 + self.react_treble * 0.5)
        
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
                h_size_arr = np.repeat(self.mandala_base_size, S) * (1.0 + self.react_treble * 0.5) * (0.4 + 0.6 * fade_factor)
                
                all_pos_list.append(h_pos_arr)
                all_col_list.append(h_col_arr)
                all_size_list.append(h_size_arr)
                
        pos_arr = np.concatenate(all_pos_list, axis=0)
        col_arr = np.concatenate(all_col_list, axis=0)
        size_arr = np.concatenate(all_size_list, axis=0)
        
        mandala_tri_pos = []
        mandala_tri_col = []
        
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
            
        # Render Pulsing Halo Effect with outward firing sparks (Un-sliced circle with scattered sparks)
        if self.halo_timer > 0.0:
            halo_pos, halo_col, halo_size = [], [], []
            R_halo = 5.2 + self.react_bass * 1.5 + np.sin(self.get_sim_time() * 5.0) * 0.25
            center = np.array([0.0, 4.0, 0.0], dtype=np.float32)
            alpha_h = np.clip(self.halo_timer / 1.0, 0.0, 1.0)
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
