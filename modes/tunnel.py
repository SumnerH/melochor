import numpy as np
import random
from meshes import make_rocky_planet, make_3d_asteroid

class TunnelModeMixin:
    # MODE 2: COSMIC WORMHOLE TUNNEL (Winding Plasma Tunnel Overhaul)
    # =========================================================================
    def init_tunnel_mode(self):
        # Curved path dynamics (serpentine tunnel path)
        self.wormhole_bend_x = 0.0
        self.wormhole_bend_y = 0.0
        self.target_bend_x = 0.0
        self.target_bend_y = 0.0
        self.wormhole_phase_x = 0.0
        self.wormhole_phase_y = 0.0
        self.tunnel_change_timer = 0.0

        # WALL GEMS (glowing crystal nodules - heavily reduced)
        N_gems = 15
        self.gem_z = np.random.uniform(-60.0, 10.0, N_gems).astype(np.float32)
        self.gem_angle = np.random.uniform(0.0, 2 * np.pi, N_gems).astype(np.float32)
        self.gem_base_radius = np.random.uniform(7.5, 9.5, N_gems).astype(np.float32)
        self.gem_col = np.zeros((N_gems, 4), dtype=np.float32)
        for i in range(N_gems):
            self.gem_col[i] = random.choice([
                (1.0, 0.2, 0.2, 1.0),   # Ruby
                (0.2, 1.0, 0.4, 1.0),   # Emerald
                (0.15, 0.5, 1.0, 1.0),  # Sapphire
                (0.95, 0.95, 1.0, 1.0), # Diamond
                (1.0, 0.75, 0.05, 1.0)  # Topaz
            ])
        self.gem_size = np.random.uniform(11.0, 17.0, N_gems).astype(np.float32)

        # WALL GEMS SPARKS SYSTEM (Preallocated spark particle pool)
        N_sparks = 900
        self.spark_pos = np.zeros((N_sparks, 3), dtype=np.float32)
        self.spark_vel = np.zeros((N_sparks, 3), dtype=np.float32)
        self.spark_col = np.zeros((N_sparks, 4), dtype=np.float32)
        self.spark_size = np.zeros(N_sparks, dtype=np.float32)
        self.spark_age = np.zeros(N_sparks, dtype=np.float32)
        self.spark_max_age = np.ones(N_sparks, dtype=np.float32)
        self.spark_active = np.zeros(N_sparks, dtype=np.bool_)
        self.next_spark_idx = 0

    def update_tunnel(self, dt):
        # Calculate dynamic tempo speed factor with floor at 40.0 and cap at 240.0 BPM
        bpm = self.script_bpm if (hasattr(self, 'script_bpm') and self.script_bpm > 0.0) else 40.0
        bpm = np.clip(bpm, 40.0, 240.0)
        
        # Pronounced non-linear scaling: floor of 0.15 at 40 BPM, nominal 1.0 at 120 BPM, and cap of 4.0 at 240 BPM
        if bpm <= 120.0:
            speed_factor = 0.15 + 0.85 * ((bpm - 40.0) / 80.0) ** 1.8
        else:
            speed_factor = 1.0 + 3.0 * ((bpm - 120.0) / 120.0) ** 1.5
        
        # Constant, elegant forward travel camera speed, scaled dynamically and non-linearly by tempo BPM
        speed = 8.5 * speed_factor * dt
        self.gem_z += speed
        
        gem_passed = self.gem_z > 10.0
        num_gem_passed = np.sum(gem_passed)
        if num_gem_passed > 0:
            self.gem_z[gem_passed] = np.random.uniform(-60.0, -50.0, num_gem_passed).astype(np.float32)
            self.gem_angle[gem_passed] = np.random.uniform(0.0, 2 * np.pi, num_gem_passed).astype(np.float32)
            
        # Smooth wall spin speed
        spin_speed = (0.12 + self.react_mid * 0.4) * dt
        self.gem_angle += spin_speed * 0.8
        
        # Update curving serpentine bend coordinates
        self.wormhole_phase_x += (0.4 + self.react_bass * 0.5) * dt
        self.wormhole_phase_y += (0.25 + self.react_mid * 0.3) * dt
        
        # Music drops trigger gentle serpentine shifting
        self.tunnel_change_timer += dt
        if (self.react_bass > 1.25 and random.random() < 0.12) or self.tunnel_change_timer > 5.5:
            self.tunnel_change_timer = 0.0
            self.target_bend_x = np.random.uniform(-3.0, 3.0)
            self.target_bend_y = np.random.uniform(-3.0, 3.0)
            
        # Smooth transitions
        self.wormhole_bend_x += (self.target_bend_x - self.wormhole_bend_x) * dt * 1.5
        self.wormhole_bend_y += (self.target_bend_y - self.wormhole_bend_y) * dt * 1.5
        
        # Audio frequency hits trigger gem spark burst emissions on all bands
        if self.react_bass > 1.0 or self.react_mid > 0.75 or self.react_treble > 0.4 or random.random() < 0.15:
            near_gems = np.where((self.gem_z < -5.0) & (self.gem_z > -45.0))[0]
            if len(near_gems) > 0:
                g_idx = random.choice(near_gems)
                self.spawn_gem_sparks(g_idx)
                
        # Update Sparks
        active_sparks = self.spark_active
        if np.any(active_sparks):
            self.spark_pos[active_sparks] += self.spark_vel[active_sparks] * dt
            self.spark_age[active_sparks] += dt
            
            expired = (self.spark_age >= self.spark_max_age) & active_sparks
            self.spark_active[expired] = False
            
            self.spark_col[active_sparks, 3] = np.clip(
                1.0 - self.spark_age[active_sparks] / self.spark_max_age[active_sparks], 0.0, 1.0
            )

    def spawn_gem_sparks(self, g_idx):
        gz = self.gem_z[g_idx]
        g_angle = self.gem_angle[g_idx]
        g_rad = self.gem_base_radius[g_idx]
        g_color = self.gem_col[g_idx]
        
        gx = g_rad * np.cos(g_angle)
        gy = g_rad * np.sin(g_angle)
        
        num_sparks_spawn = 6
        for _ in range(num_sparks_spawn):
            idx = self.next_spark_idx
            self.spark_pos[idx] = [gx, gy, gz]
            
            rad_speed = np.random.uniform(-14.0, -3.0)
            tan_speed = np.random.uniform(-5.0, 5.0)
            z_speed = np.random.uniform(-18.0, 6.0)
            
            cos_a = np.cos(g_angle)
            sin_a = np.sin(g_angle)
            
            vx = rad_speed * cos_a - tan_speed * sin_a
            vy = rad_speed * sin_a + tan_speed * cos_a
            vz = z_speed
            
            self.spark_vel[idx] = [vx, vy, vz]
            
            # Determine normalized center-of-mass frequency index of current audio frame (f_avg between 0.0 and 1.0)
            total_e = self.react_bass + self.react_mid + self.react_treble + 1e-5
            f_avg = (self.react_bass * 0.10 + self.react_mid * 0.50 + self.react_treble * 0.90) / total_e
            
            # Spread sparks slightly across spectrum around f_avg
            f_spark = np.clip(f_avg + np.random.uniform(-0.18, 0.18), 0.0, 1.0)
            
            # Continuous color mapping:
            # 0.0: low bass (dark purple [0.45, 0.0, 0.70]) -> 0.33: mid-low (dark blue [0.0, 0.15, 0.65])
            # -> 0.66: midranges (medium green [0.10, 0.68, 0.22]) -> 1.0: trebles (medium yellow [0.72, 0.72, 0.08])
            if f_spark < 0.33:
                frac = f_spark / 0.33
                col_r = 0.45 * (1.0 - frac) + 0.0 * frac
                col_g = 0.0 * (1.0 - frac) + 0.15 * frac
                col_b = 0.70 * (1.0 - frac) + 0.65 * frac
            elif f_spark < 0.66:
                frac = (f_spark - 0.33) / 0.33
                col_r = 0.0 * (1.0 - frac) + 0.10 * frac
                col_g = 0.15 * (1.0 - frac) + 0.68 * frac
                col_b = 0.65 * (1.0 - frac) + 0.22 * frac
            else:
                frac = (f_spark - 0.66) / 0.34
                col_r = 0.10 * (1.0 - frac) + 0.72 * frac
                col_g = 0.68 * (1.0 - frac) + 0.72 * frac
                col_b = 0.22 * (1.0 - frac) + 0.08 * frac
                
            self.spark_col[idx] = [col_r, col_g, col_b, 1.0]
            self.spark_size[idx] = np.random.uniform(5.0, 9.0)
            self.spark_age[idx] = 0.0
            self.spark_max_age[idx] = np.random.uniform(0.4, 0.9)
            self.spark_active[idx] = True
            
            self.next_spark_idx = (self.next_spark_idx + 1) % len(self.spark_pos)

    def get_bend_offsets(self, z_arr):
        bx = self.wormhole_bend_x * np.sin(z_arr * 0.06 + self.wormhole_phase_x)
        by = self.wormhole_bend_y * np.cos(z_arr * 0.06 + self.wormhole_phase_y)
        return bx, by

    def render_tunnel(self):
        get_bend_offsets = self.get_bend_offsets
            
        hood_tri_pos = []
        hood_tri_col = []
        
        # Render Gems with fog
        gbx, gby = get_bend_offsets(self.gem_z)
        gx = self.gem_base_radius * np.cos(self.gem_angle) + gbx
        gy = self.gem_base_radius * np.sin(self.gem_angle) + gby + 4.0
        gz = self.gem_z
        
        gem_col_arr = self.gem_col.copy()
        gem_col_arr[:, 3] *= np.clip((gz + 60.0) / 60.0, 0.0, 1.0)
        
        # Render active sparks
        active_mask = self.spark_active
        num_act = np.sum(active_mask)
        
        # Gather additional backdrop particles (Aurora, Planet, Galaxy, Asteroids, Supernova)
        aurora_pos = []
        aurora_col = []
        aurora_size = []
        time_val = self.get_sim_time()
        
        # 1. CONTINUOUS BACKGROUND AURORA BOREALIS OUTSIDE TUNNEL WALLS (extremely transparent)
        for i_strip in range(15):
            ang = (i_strip / 14.0) * np.pi * 0.8 + np.pi * 0.1 # cover top half & sides
            for p_idx in range(25):
                z_coord = -55.0 + p_idx * 2.5
                bx, by = get_bend_offsets(z_coord)
                R_aur = 11.5 + np.sin(ang * 4.0 + time_val * 1.5) * np.cos(z_coord * 0.07 - time_val * 0.8) * 1.3
                px = R_aur * np.cos(ang) + bx
                py = R_aur * np.sin(ang) + by + 4.0
                pz = z_coord
                
                ang_f = abs(ang - np.pi / 2.0) / (np.pi / 2.0)
                # Blend from vibrant neon emerald-green to purple-pink outer sheets
                col_r = 0.1 * (1.0 - ang_f) + 0.75 * ang_f
                col_g = 0.95 * (1.0 - ang_f) + 0.1 * ang_f
                col_b = 0.35 * (1.0 - ang_f) + 0.9 * ang_f
                
                fog_factor = np.clip((z_coord + 50.0) / 50.0, 0.0, 1.0)
                alpha = 0.32 * fog_factor * (0.32 + self.react_mid * 0.68) * (1.0 - ang_f * 0.2)
                
                aurora_pos.append([px, py, pz])
                aurora_col.append([col_r, col_g, col_b, alpha])
                aurora_size.append(5.0)
                
        # 2. PLANET RARITY (solid 3D rocky sphere with tilting rings)
        if self.active_rarity is not None and self.active_rarity['type'] == 'PLANET':
            r = self.active_rarity
            p_pts, p_cols = make_rocky_planet(r['pos'], 2.3, r['phase'], r.get('style', 'JUPITER'))
            # Apply bend offsets to planet triangles before buffering
            bent_pts = []
            for pt in p_pts:
                bx, by = get_bend_offsets(pt[2])
                bent_pts.append([pt[0] + bx, pt[1] + by + 4.0, pt[2]])
            hood_tri_pos.extend(bent_pts)
            hood_tri_col.extend(p_cols)
                
        # 3. GALAXY RARITY (spiral structure outside tunnel)
        if self.active_rarity is not None and self.active_rarity['type'] == 'GALAXY':
            r = self.active_rarity
            center = r['pos']
            for i_g in range(160):
                t_frac = i_g / 160.0
                rad = 0.3 + t_frac * 4.5
                arm_ang = t_frac * 16.0 + (np.pi if i_g % 2 == 0 else 0.0) + r['phase']
                rx = rad * np.cos(arm_ang)
                ry = rad * np.sin(arm_ang) * 0.4
                rz = np.sin(arm_ang * 2.0) * 0.2
                p_world = center + np.array([rx, ry, rz])
                bx, by = get_bend_offsets(p_world[2])
                px = p_world[0] + bx
                py = p_world[1] + by + 4.0
                pz = p_world[2]
                # Adjust fog boundary specifically for Galaxy since it starts at Z = -85.0
                fog_factor = np.clip((pz + 85.0) / 60.0, 0.0, 1.0)
                alpha = (1.0 - t_frac * 0.5) * (0.6 + np.sin(time_val * 6.0 + i_g) * 0.3) * fog_factor
                if t_frac < 0.15:
                    col = [1.0, 0.85, 1.0, alpha] # Core starburst
                    size_pt = 12.0
                elif i_g % 2 == 0:
                    col = [0.15, 0.7, 1.0, alpha] # Cyan spiral arm
                    size_pt = 6.0
                else:
                    col = [0.95, 0.2, 0.75, alpha] # Magenta spiral arm
                    size_pt = 6.0
                aurora_pos.append([px, py, pz])
                aurora_col.append(col)
                aurora_size.append(size_pt)
                
        # 4. ASTEROIDS RARITY (tumbling rocks drifting past as solid 3D meshes)
        if self.active_rarity is not None and self.active_rarity['type'] == 'ASTEROIDS':
            r = self.active_rarity
            center = r['pos']
            for k in range(len(r['offsets'])):
                ast_pos = center + r['offsets'][k]
                rot = r['rotations'][k]
                rad_ast = 0.55 + 0.15 * np.sin(k * 4.0)
                a_pts, a_cols = make_3d_asteroid(ast_pos, rad_ast, rot)
                for pt, col in zip(a_pts, a_cols):
                    bx, by = get_bend_offsets(pt[2])
                    px = pt[0] + bx
                    py = pt[1] + by + 4.0
                    pz = pt[2]
                    fog_factor = np.clip((pz + 50.0) / 50.0, 0.0, 1.0)
                    c_fog = [col[0], col[1], col[2], col[3] * fog_factor]
                    hood_tri_pos.append([px, py, pz])
                    hood_tri_col.append(c_fog)
                    
        # 5. REAL SUPERNOVA SHOCKWAVE EXPANSION SHELL (Blinding core with filaments)
        if self.wormhole_supernova_active:
            r_shock = self.wormhole_supernova_age * 16.0
            center_z = -50.0
            for i_sn in range(160):
                lat = (i_sn / 160.0) * np.pi - np.pi / 2.0
                lon = (i_sn * 2.39996) % (2.0 * np.pi)
                turb = 1.0 + 0.12 * np.sin(lon * 5.0 + self.wormhole_supernova_age * 12.0)
                
                lx = np.cos(lat) * np.cos(lon) * turb
                ly = np.cos(lat) * np.sin(lon) * turb
                lz = np.sin(lat) * turb
                p_world = np.array([lx, ly, lz]) * r_shock
                p_world[2] += center_z
                
                bx, by = get_bend_offsets(p_world[2])
                px = p_world[0] + bx
                py = p_world[1] + by + 4.0
                pz = p_world[2]
                
                alpha = np.clip(1.0 - (self.wormhole_supernova_age / 3.5), 0.0, 1.0)
                if self.wormhole_supernova_age < 0.6:
                    col = [1.0, 0.95, 0.85, alpha] # Blinding hot white core flash
                    size_pt = 14.0
                elif i_sn % 3 == 0:
                    col = [1.0, 0.5, 0.1, alpha] # Fiery orange expanding shell gas
                    size_pt = 10.0
                elif i_sn % 3 == 1:
                    col = [0.1, 0.85, 1.0, alpha] # Cyan shock border
                    size_pt = 8.0
                else:
                    col = [0.95, 0.15, 0.5, alpha] # Magenta glowing filaments
                    size_pt = 9.0
                aurora_pos.append([px, py, pz])
                aurora_col.append(col)
                aurora_size.append(size_pt)
                
        # 6. MASSIVE FLY-BY SHOOTING STAR HEAD
        if self.wormhole_shooting_star_active:
            bx, by = get_bend_offsets(self.wormhole_shooting_star_z)
            px = self.wormhole_shooting_star_x + bx
            py = self.wormhole_shooting_star_y + by + 4.0
            pz = self.wormhole_shooting_star_z
            fog_factor = np.clip((pz + 50.0) / 50.0, 0.0, 1.0)
            aurora_pos.append([px, py, pz])
            aurora_col.append([1.0, 1.0, 1.0, 1.0 * fog_factor])
            aurora_size.append(16.0)
            
        if num_act > 0:
            sp_pos = self.spark_pos[active_mask].copy()
            sbx, sby = get_bend_offsets(sp_pos[:, 2])
            sp_pos[:, 0] += sbx
            sp_pos[:, 1] += sby + 4.0
            
            sp_col = self.spark_col[active_mask]
            sp_size = self.spark_size[active_mask]
            
            pos_combined = np.concatenate([
                np.stack([gx, gy, gz], axis=1),
                sp_pos
            ], axis=0).astype(np.float32)
            
            col_combined = np.concatenate([
                gem_col_arr,
                sp_col
            ], axis=0).astype(np.float32)
            
            size_combined = np.concatenate([
                self.gem_size * (1.1 + self.react_treble * 0.8),
                sp_size
            ], axis=0).astype(np.float32)
        else:
            pos_combined = np.stack([gx, gy, gz], axis=1).astype(np.float32)
            col_combined = gem_col_arr.astype(np.float32)
            size_combined = (self.gem_size * (1.1 + self.react_treble * 0.8)).astype(np.float32)
            
        if len(aurora_pos) > 0:
            pos_combined = np.concatenate([pos_combined, np.array(aurora_pos, dtype=np.float32)], axis=0)
            col_combined = np.concatenate([col_combined, np.array(aurora_col, dtype=np.float32)], axis=0)
            size_combined = np.concatenate([size_combined, np.array(aurora_size, dtype=np.float32)], axis=0)
            
        return pos_combined, col_combined, size_combined, np.array(hood_tri_pos, dtype=np.float32), np.array(hood_tri_col, dtype=np.float32)
