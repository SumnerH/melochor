import random
import numpy as np
from constants import COLOR_LIST, COLORS
from helpers import get_palette_colors

class Firework:
    app = None
    def __init__(self, fw_type=None, color=None, x_offset=None):
        self.type = random.randint(0, 18) if fw_type is None else fw_type
        self.color = random.choice(COLOR_LIST) if color is None else color
        self.secondary_color = random.choice(COLOR_LIST)
        
        self.state = 'LAUNCH'
        
        if x_offset is None:
            x_offset = random.uniform(-10.0, 10.0)
        self.launch_pos = np.array([x_offset, -12.0, random.uniform(-6.0, 6.0)], dtype=np.float32)
        if Firework.app and Firework.app.opt_height_restrict:
            y_vel = random.uniform(21.0, 26.0)
        else:
            y_vel = random.uniform(10.0, 26.0)
            
        self.launch_vel = np.array([
            random.uniform(-2.0, 2.0),
            y_vel,
            random.uniform(-2.0, 2.0)
        ], dtype=np.float32)
        
        self.launch_age = 0.0
        self.launch_fuse = 999.0
        
        self.launch_trail = []
        self.launch_trail_max = 15

        self.stage = 1  # Multi-stage track (e.g., Crossette stage 1 vs 2)

        self.positions = None
        self.velocities = None
        self.colors = None
        self.ages = None
        self.max_ages = None
        self.history = None
        self.history_len = 0
        self.drag = 1.0
        self.star_size = 8.0
        self.gravity = 5.0
        
    def explode(self):
        self.state = 'EXPLODE'
        
        if self.type == 0:  # Peony
            num_particles = random.randint(500, 700)
            self.drag = 1.6
            self.history_len = 2
            min_life, max_life = 1.0, 1.6
        elif self.type == 1:  # Chrysanthemum
            num_particles = random.randint(600, 800)
            self.drag = 1.1
            self.history_len = 6
            min_life, max_life = 1.2, 1.8
        elif self.type == 2:  # Willow
            num_particles = random.randint(400, 600)
            self.drag = 0.45
            self.history_len = 10
            min_life, max_life = 2.4, 3.4
            if random.random() < 0.7:
                self.color = COLORS["sodium_gold"]
                self.secondary_color = COLORS["calcium_orange"]
        elif self.type == 3:  # Ghost Ring
            num_particles = random.randint(400, 500)
            self.drag = 1.3
            self.history_len = 4
            min_life, max_life = 1.2, 1.7
        elif self.type == 4:  # Pistil / Double Shell
            num_particles = random.randint(700, 900)
            self.drag = 1.3
            self.history_len = 5
            min_life, max_life = 1.3, 1.9
        elif self.type == 5:  # Waterfall / Horsetail
            num_particles = random.randint(350, 500)
            self.drag = 0.35
            self.history_len = 12
            min_life, max_life = 2.8, 3.8
            self.color = COLORS["sodium_gold"] if random.random() < 0.8 else COLORS["strontium_red"]
            self.secondary_color = COLORS["calcium_orange"]
        elif self.type == 6:  # Swarm / Bees / Fish
            num_particles = random.randint(180, 260)
            self.drag = 0.4
            self.history_len = 8
            min_life, max_life = 1.8, 2.5
        elif self.type == 7:  # Saturn Ring (Sphere + Outer Ring)
            num_particles = random.randint(700, 900)
            self.drag = 1.2
            self.history_len = 5
            min_life, max_life = 1.4, 2.0
        elif self.type == 8:  # Crossette (2-Stage Splitting Break)
            num_particles = 120  # Keep starting size modest so splitting doesn't overload
            self.drag = 1.0
            self.history_len = 5
            min_life, max_life = 1.4, 1.8
        elif self.type == 9:  # Rainbow Bouquet (Multicolored)
            num_particles = random.randint(750, 950)
            self.drag = 1.2
            self.history_len = 4
            min_life, max_life = 1.3, 1.9
        elif self.type == 10:  # Multi-Stage Ring
            num_particles = 150
            self.drag = 1.3
            self.history_len = 4
            min_life, max_life = 1.3, 1.7
        elif self.type == 11:  # Dahlia
            num_particles = random.randint(80, 110)
            self.drag = 0.75
            self.history_len = 8
            min_life, max_life = 1.5, 2.2
            self.star_size = 14.0
        elif self.type == 12:  # Diadem / Crown
            num_particles = random.randint(600, 800)
            self.drag = 1.1
            self.history_len = 8
            min_life, max_life = 1.6, 2.4
            self.color = COLORS["sodium_gold"]
        elif self.type == 13:  # Palm Tree
            num_particles = 200
            self.drag = 0.5
            self.history_len = 10
            min_life, max_life = 1.8, 2.6
            self.color = COLORS["sodium_gold"]
            self.star_size = 11.0
        elif self.type == 14:  # Spider
            num_particles = random.randint(250, 350)
            self.drag = 0.25
            self.history_len = 2
            min_life, max_life = 0.6, 0.9
            self.color = COLORS["magnesium_white"] if random.random() < 0.5 else COLORS["sodium_gold"]
            self.star_size = 7.0
        elif self.type == 15:  # Time Rain (Glitter Crackle)
            num_particles = random.randint(300, 400)
            self.drag = 0.65
            self.history_len = 6
            min_life, max_life = 1.8, 2.6
            self.color = COLORS["sodium_gold"]
        elif self.type == 16:  # Farfalle (Fluttering Butterflies)
            num_particles = random.randint(200, 300)
            self.drag = 0.8
            self.history_len = 6
            min_life, max_life = 1.5, 2.2
        elif self.type == 17:  # Tourbillon (Spiraling Vortex)
            num_particles = random.randint(180, 250)
            self.drag = 0.6
            self.history_len = 8
            min_life, max_life = 1.6, 2.4
        else:  # Type 18: Multi-Break Ring to Fish Swarm
            num_particles = 150
            self.drag = 1.2
            self.history_len = 5
            min_life, max_life = 1.4, 2.0

        self.positions = np.zeros((num_particles, 3), dtype=np.float32)
        self.positions[:] = self.launch_pos
        
        self.velocities = np.zeros((num_particles, 3), dtype=np.float32)
        self.colors = np.zeros((num_particles, 4), dtype=np.float32)
        self.ages = np.zeros(num_particles, dtype=np.float32)
        self.max_ages = np.random.uniform(min_life, max_life, num_particles).astype(np.float32)

        if self.type == 3:  # Ring
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            speed = np.random.uniform(7.0, 9.0, num_particles)
            vx = speed * np.cos(theta)
            vy = speed * np.sin(theta)
            vz = np.random.uniform(-0.6, 0.6, num_particles)
            local_vel = np.stack([vx, vy, vz], axis=1)
            
            rx = np.random.uniform(0, 2 * np.pi)
            ry = np.random.uniform(0, 2 * np.pi)
            cx, sx = np.cos(rx), np.sin(rx)
            cy, sy = np.cos(ry), np.sin(ry)
            RotX = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float32)
            RotY = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float32)
            R = RotX @ RotY
            self.velocities = local_vel @ R.T
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 4:  # Pistil / Double Shell
            half = num_particles // 2
            # Outer shell spherical (faster)
            theta_o = np.random.uniform(0, 2 * np.pi, half)
            phi_o = np.arccos(np.random.uniform(-1, 1, half))
            speed_o = np.random.uniform(7.5, 9.5, half)
            
            self.velocities[:half, 0] = speed_o * np.sin(phi_o) * np.cos(theta_o)
            self.velocities[:half, 1] = speed_o * np.sin(phi_o) * np.sin(theta_o)
            self.velocities[:half, 2] = speed_o * np.cos(phi_o)
            
            self.colors[:half, 0] = np.clip(self.color[0] + np.random.uniform(-0.08, 0.08, half), 0.0, 1.0)
            self.colors[:half, 1] = np.clip(self.color[1] + np.random.uniform(-0.08, 0.08, half), 0.0, 1.0)
            self.colors[:half, 2] = np.clip(self.color[2] + np.random.uniform(-0.08, 0.08, half), 0.0, 1.0)
            
            # Inner shell spherical (slower)
            theta_i = np.random.uniform(0, 2 * np.pi, num_particles - half)
            phi_i = np.arccos(np.random.uniform(-1, 1, num_particles - half))
            speed_i = np.random.uniform(3.5, 4.5, num_particles - half)
            
            self.velocities[half:, 0] = speed_i * np.sin(phi_i) * np.cos(theta_i)
            self.velocities[half:, 1] = speed_i * np.sin(phi_i) * np.sin(theta_i)
            self.velocities[half:, 2] = speed_i * np.cos(phi_i)
            
            self.colors[half:, 0] = np.clip(self.secondary_color[0] + np.random.uniform(-0.08, 0.08, num_particles - half), 0.0, 1.0)
            self.colors[half:, 1] = np.clip(self.secondary_color[1] + np.random.uniform(-0.08, 0.08, num_particles - half), 0.0, 1.0)
            self.colors[half:, 2] = np.clip(self.secondary_color[2] + np.random.uniform(-0.08, 0.08, num_particles - half), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 5:  # Waterfall / Horsetail
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-0.1, 0.4, num_particles))
            speed = np.random.uniform(1.5, 4.0, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta) * 0.4
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta) + np.random.uniform(2.0, 4.0, num_particles)
            self.velocities[:, 2] = speed * np.cos(phi) * 0.4
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 6:  # Bees / Swarm / Fish
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(3.0, 5.0, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 7:  # Saturn Ring
            sphere_pts = int(num_particles * 0.55)
            ring_pts = num_particles - sphere_pts
            
            # Central sphere
            theta_s = np.random.uniform(0, 2 * np.pi, sphere_pts)
            phi_s = np.arccos(np.random.uniform(-1, 1, sphere_pts))
            speed_s = np.random.uniform(4.5, 6.0, sphere_pts)
            
            self.velocities[:sphere_pts, 0] = speed_s * np.sin(phi_s) * np.cos(theta_s)
            self.velocities[:sphere_pts, 1] = speed_s * np.sin(phi_s) * np.sin(theta_s)
            self.velocities[:sphere_pts, 2] = speed_s * np.cos(phi_s)
            
            self.colors[:sphere_pts, 0] = np.clip(self.color[0] + np.random.uniform(-0.08, 0.08, sphere_pts), 0.0, 1.0)
            self.colors[:sphere_pts, 1] = np.clip(self.color[1] + np.random.uniform(-0.08, 0.08, sphere_pts), 0.0, 1.0)
            self.colors[:sphere_pts, 2] = np.clip(self.color[2] + np.random.uniform(-0.08, 0.08, sphere_pts), 0.0, 1.0)
            
            # Concentric ring
            theta_r = np.random.uniform(0, 2 * np.pi, ring_pts)
            speed_r = np.random.uniform(8.0, 10.0, ring_pts)
            vx_r = speed_r * np.cos(theta_r)
            vy_r = speed_r * np.sin(theta_r)
            vz_r = np.random.uniform(-0.4, 0.4, ring_pts)
            local_vel_r = np.stack([vx_r, vy_r, vz_r], axis=1)
            
            rx = np.random.uniform(0, 2 * np.pi)
            ry = np.random.uniform(0, 2 * np.pi)
            cx, sx = np.cos(rx), np.sin(rx)
            cy, sy = np.cos(ry), np.sin(ry)
            RotX = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float32)
            RotY = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float32)
            R = RotX @ RotY
            self.velocities[sphere_pts:] = local_vel_r @ R.T
            
            self.colors[sphere_pts:, 0] = np.clip(self.secondary_color[0] + np.random.uniform(-0.08, 0.08, ring_pts), 0.0, 1.0)
            self.colors[sphere_pts:, 1] = np.clip(self.secondary_color[1] + np.random.uniform(-0.08, 0.08, ring_pts), 0.0, 1.0)
            self.colors[sphere_pts:, 2] = np.clip(self.secondary_color[2] + np.random.uniform(-0.08, 0.08, ring_pts), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 9:  # Rainbow Bouquet (Full spectrum vectorized colorization)
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(5.5, 8.5, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            # Highly optimized vectorized selection from the color list per particle
            indices = np.random.randint(0, len(COLOR_LIST), num_particles)
            base_cols = np.array(COLOR_LIST, dtype=np.float32)[indices]
            self.colors[:, :3] = np.clip(base_cols[:, :3] + np.random.uniform(-0.05, 0.05, (num_particles, 3)), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 10:  # Multi-Stage Ring
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            speed = np.random.uniform(7.0, 8.5, num_particles)
            vx = speed * np.cos(theta)
            vy = speed * np.sin(theta)
            vz = np.random.uniform(-0.5, 0.5, num_particles)
            local_vel = np.stack([vx, vy, vz], axis=1)
            
            rx = np.random.uniform(0, 2 * np.pi)
            ry = np.random.uniform(0, 2 * np.pi)
            cx, sx = np.cos(rx), np.sin(rx)
            cy, sy = np.cos(ry), np.sin(ry)
            RotX = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float32)
            RotY = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float32)
            R = RotX @ RotY
            self.velocities = local_vel @ R.T
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 11:  # Dahlia (High intensity, slow-burning, wide expand)
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(7.5, 10.0, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 12:  # Diadem / Crown
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(5.5, 8.5, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 13:  # Palm Tree (Golden fronds + Contrasting Coconuts)
            half = int(num_particles * 0.92)
            theta = np.random.uniform(0, 2 * np.pi, half)
            phi = np.arccos(np.random.uniform(-0.2, 0.8, half))  # Upward-outward arcs
            speed = np.random.uniform(6.5, 9.5, half)
            
            self.velocities[:half, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:half, 1] = speed * np.sin(phi) * np.sin(theta) + 3.0
            self.velocities[:half, 2] = speed * np.cos(phi)
            
            self.colors[:half, 0] = np.clip(self.color[0] + np.random.uniform(-0.05, 0.05, half), 0.0, 1.0)
            self.colors[:half, 1] = np.clip(self.color[1] + np.random.uniform(-0.05, 0.05, half), 0.0, 1.0)
            self.colors[:half, 2] = np.clip(self.color[2] + np.random.uniform(-0.05, 0.05, half), 0.0, 1.0)
            
            coconuts = num_particles - half
            theta_c = np.random.uniform(0, 2 * np.pi, coconuts)
            phi_c = np.arccos(np.random.uniform(-0.5, 0.5, coconuts))
            speed_c = np.random.uniform(9.0, 11.5, coconuts)
            
            self.velocities[half:, 0] = speed_c * np.sin(phi_c) * np.cos(theta_c)
            self.velocities[half:, 1] = speed_c * np.sin(phi_c) * np.sin(theta_c)
            self.velocities[half:, 2] = speed_c * np.cos(phi_c)
            
            coconut_col = COLORS["barium_green"] if random.random() < 0.5 else COLORS["potassium_purple"]
            self.colors[half:, 0] = coconut_col[0]
            self.colors[half:, 1] = coconut_col[1]
            self.colors[half:, 2] = coconut_col[2]
            self.colors[:, 3] = 1.0
            
        elif self.type == 14:  # Spider (Sharp, fast straight-line gold break)
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(13.0, 17.5, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.08, 0.08, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.08, 0.08, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.08, 0.08, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 15:  # Time Rain (Drifting gold)
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(5.5, 8.0, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 16:  # Farfalle (Butterfly flight flutter)
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(5.0, 7.5, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 17:  # Tourbillon (Spiraling whirlwind)
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(4.5, 7.0, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        else:  # Type 18: Multi-Break Ring to Swarm
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            speed = np.random.uniform(6.5, 8.0, num_particles)
            vx = speed * np.cos(theta)
            vy = speed * np.sin(theta)
            vz = np.random.uniform(-0.5, 0.5, num_particles)
            local_vel = np.stack([vx, vy, vz], axis=1)
            
            rx = np.random.uniform(0, 2 * np.pi)
            ry = np.random.uniform(0, 2 * np.pi)
            cx, sx = np.cos(rx), np.sin(rx)
            cy, sy = np.cos(ry), np.sin(ry)
            RotX = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float32)
            RotY = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float32)
            R = RotX @ RotY
            self.velocities = local_vel @ R.T
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0

        # Custom gravity profiles per shell type to simulate natural air buoyancy and drag
        gravity_map = {
            0: 5.5,   # Peony
            2: 4.5,   # Willow (floats elegantly)
            3: 4.5,   # Ghost Ring
            5: 3.5,   # Waterfall (graceful descent)
            6: 3.0,   # Swarm/Bees
            8: 5.5,   # Crossette
            10: 4.5,  # Multi-Stage Ring
            11: 4.0,  # Dahlia (slow burning pellets)
            12: 4.5,  # Diadem / Crown
            13: 4.5,  # Palm Tree
            14: 5.5,  # Spider (sharp fast needle break)
            15: 3.5,  # Time Rain (slow glittering drift)
            16: 4.0,  # Farfalle
            17: 4.0,  # Tourbillon
            18: 4.5   # Ring to Swarm
        }
        self.gravity = gravity_map.get(self.type, 5.0)

        # Dynamic trailer override
        if Firework.app and Firework.app.opt_trailers > 0:
            self.history_len = Firework.app.opt_trailers * 3

        # Color palette override mapping
        if Firework.app and Firework.app.opt_color_mode != 'REALISTIC':
            pal = get_palette_colors(Firework.app.opt_color_mode)
            if pal:
                c1 = pal[random.randint(0, len(pal)-1)]
                c2 = pal[random.randint(0, len(pal)-1)]
                orig_c1 = np.array(self.color[:3], dtype=np.float32)
                orig_c2 = np.array(self.secondary_color[:3], dtype=np.float32)
                self.color = c1
                self.secondary_color = c2
                
                # Relabel colors already instantiated inside the type blocks
                if self.colors is not None:
                    diff1 = np.sum((self.colors[:, :3] - orig_c1)**2, axis=1)
                    diff2 = np.sum((self.colors[:, :3] - orig_c2)**2, axis=1)
                    closer_to_1 = diff1 <= diff2
                    noise = np.random.uniform(-0.05, 0.05, (len(self.colors), 3))
                    self.colors[closer_to_1, :3] = np.clip(np.array(c1[:3], dtype=np.float32) + noise[closer_to_1], 0.0, 1.0)
                    self.colors[~closer_to_1, :3] = np.clip(np.array(c2[:3], dtype=np.float32) + noise[~closer_to_1], 0.0, 1.0)
                    self.colors[:, 3] = 1.0

        self.history = np.zeros((self.history_len, num_particles, 3), dtype=np.float32)
        for h in range(self.history_len):
            self.history[h] = self.positions

    def update(self, dt):
        if self.state == 'DEAD':
            return
            
        if self.state == 'EXPLODE':
            # Adapt history on-the-fly to real-time keystroke switches
            if Firework.app and Firework.app.opt_trailers > 0:
                target_len = Firework.app.opt_trailers * 3
                if self.history_len != target_len or self.history is None or len(self.history) != target_len:
                    self.history_len = target_len
                    self.history = np.zeros((self.history_len, len(self.positions), 3), dtype=np.float32)
                    for h in range(self.history_len):
                        self.history[h] = self.positions

        if self.state == 'LAUNCH':
            self.launch_age += dt
            self.launch_vel[1] -= 9.8 * dt
            self.launch_vel -= self.launch_vel * 0.15 * dt
            self.launch_pos += self.launch_vel * dt
            
            self.launch_trail.append(self.launch_pos.copy())
            if len(self.launch_trail) > self.launch_trail_max:
                self.launch_trail.pop(0)
                
            if self.launch_vel[1] < 1.0 or self.launch_age >= self.launch_fuse:
                self.explode()
                
        elif self.state == 'EXPLODE':
            self.positions += self.velocities * dt
            
            # Farfalle oscillation
            if self.type == 16:
                perp = np.zeros_like(self.velocities)
                perp[:, 0] = -self.velocities[:, 1]
                perp[:, 1] = self.velocities[:, 0]
                norms = np.linalg.norm(perp, axis=1, keepdims=True) + 1e-6
                perp /= norms
                osc = np.sin(self.ages[:, np.newaxis] * 24.0) * 0.45 * perp
                self.positions += osc * dt
                
            # Tourbillon spiral 
            if self.type == 17:
                v = self.velocities
                u = np.cross(v, np.array([0.0, 1.0, 0.0], dtype=np.float32))
                norms_u = np.linalg.norm(u, axis=1, keepdims=True) + 1e-6
                u /= norms_u
                w = np.cross(v, u)
                norms_w = np.linalg.norm(w, axis=1, keepdims=True) + 1e-6
                w /= norms_w
                
                angle = self.ages * 28.0
                radius = 0.08 + self.ages * 0.6
                spiral = (np.cos(angle)[:, np.newaxis] * u + np.sin(angle)[:, np.newaxis] * w) * (radius[:, np.newaxis])
                self.positions += spiral * dt
                
            # Multi-Stage Ring Split (Stage 1 -> Stage 2)
            if self.type == 10 and self.stage == 1 and np.any(self.ages >= 0.55):
                N = len(self.positions)
                if N > 0:
                    self.stage = 2
                    new_positions = np.repeat(self.positions, 3, axis=0)
                    new_velocities = np.repeat(self.velocities, 3, axis=0)
                    
                    theta_s = np.array([0.0, 2*np.pi/3, 4*np.pi/3], dtype=np.float32)
                    offsets_local = np.stack([np.cos(theta_s), np.sin(theta_s), np.zeros(3, dtype=np.float32)], axis=1) * 3.0
                    offsets = np.tile(offsets_local, (N, 1))
                    
                    new_velocities += offsets
                    new_colors = np.repeat(self.colors, 3, axis=0)
                    new_colors[:, :3] = np.array(self.secondary_color[:3], dtype=np.float32)
                    
                    new_ages = np.zeros(3 * N, dtype=np.float32)
                    new_max_ages = np.random.uniform(0.6, 1.0, 3 * N).astype(np.float32)
                    
                    self.history_len = Firework.app.opt_trailers * 3 if (Firework.app and Firework.app.opt_trailers > 0) else 3
                    self.history = np.zeros((self.history_len, 3 * N, 3), dtype=np.float32)
                    for h in range(self.history_len):
                        self.history[h] = new_positions
                        
                    self.positions = new_positions
                    self.velocities = new_velocities
                    self.colors = new_colors
                    self.ages = new_ages
                    self.max_ages = new_max_ages
                    self.drag = 1.6
                    self.gravity = 4.0
                    
            # Multi-Break Ring to Swarm Split (Stage 1 -> Stage 2)
            if self.type == 18 and self.stage == 1 and np.any(self.ages >= 0.55):
                N = len(self.positions)
                if N > 0:
                    self.stage = 2
                    self.type = 6  # Becomes Swarm/Fish (inherits wiggle force below)
                    new_positions = np.repeat(self.positions, 3, axis=0)
                    new_velocities = np.repeat(self.velocities, 3, axis=0)
                    
                    fish_vel = 3.5
                    theta_f = np.random.uniform(0, 2 * np.pi, 3 * N)
                    phi_f = np.arccos(np.random.uniform(-1, 1, 3 * N))
                    offsets = np.stack([
                        fish_vel * np.sin(phi_f) * np.cos(theta_f),
                        fish_vel * np.sin(phi_f) * np.sin(theta_f),
                        fish_vel * np.cos(phi_f)
                    ], axis=1).astype(np.float32)
                    new_velocities += offsets
                    
                    new_colors = np.repeat(self.colors, 3, axis=0)
                    new_colors[:, :3] = np.array(self.secondary_color[:3], dtype=np.float32)
                    
                    new_ages = np.zeros(3 * N, dtype=np.float32)
                    new_max_ages = np.random.uniform(1.2, 1.8, 3 * N).astype(np.float32)
                    
                    self.history_len = Firework.app.opt_trailers * 3 if (Firework.app and Firework.app.opt_trailers > 0) else 8
                    self.history = np.zeros((self.history_len, 3 * N, 3), dtype=np.float32)
                    for h in range(self.history_len):
                        self.history[h] = new_positions
                        
                    self.positions = new_positions
                    self.velocities = new_velocities
                    self.colors = new_colors
                    self.ages = new_ages
                    self.max_ages = new_max_ages
                    self.drag = 0.5
                    self.gravity = 3.0

            # Crossette Splitting (Stage 1 -> Stage 2 transition)
            if self.type == 8 and self.stage == 1 and np.any(self.ages >= 0.55):
                N = len(self.positions)
                if N > 0:
                    self.stage = 2
                    
                    # 1. Expand arrays 4x
                    new_positions = np.repeat(self.positions, 4, axis=0)
                    new_velocities = np.repeat(self.velocities, 4, axis=0)
                    
                    # 2. Add high-speed right-angle offsets for 3D cross pattern
                    cross_vel = 4.8
                    offsets = np.array([
                        [ cross_vel,  0.0,  0.0],
                        [-cross_vel,  0.0,  0.0],
                        [ 0.0,  cross_vel,  0.0],
                        [ 0.0, -cross_vel,  0.0]
                    ], dtype=np.float32)
                    new_velocities += np.tile(offsets, (N, 1))
                    
                    # 3. Repeat and transition colors (hot-gold to brilliant secondary color)
                    new_colors = np.repeat(self.colors, 4, axis=0)
                    new_colors[:, :3] = np.array(self.secondary_color[:3], dtype=np.float32)
                    
                    # 4. Refresh lifespans for secondary spark stage
                    new_ages = np.zeros(4 * N, dtype=np.float32)
                    new_max_ages = np.random.uniform(0.7, 1.1, 4 * N).astype(np.float32)
                    
                    # 5. Clear and set new short history trails
                    self.history_len = Firework.app.opt_trailers * 3 if (Firework.app and Firework.app.opt_trailers > 0) else 3
                    self.history = np.zeros((self.history_len, 4 * N, 3), dtype=np.float32)
                    for h in range(self.history_len):
                        self.history[h] = new_positions
                        
                    self.positions = new_positions
                    self.velocities = new_velocities
                    self.colors = new_colors
                    self.ages = new_ages
                    self.max_ages = new_max_ages
                    self.drag = 1.8  # Increase air drag on tiny sub-sparks
                    self.gravity = 4.5
            
            # Chaotic wiggling forces for swarming/bees type
            if self.type == 6:
                perturbation = np.random.uniform(-18.0, 18.0, (len(self.positions), 3)).astype(np.float32)
                self.velocities += perturbation * dt
            
            grav_scale = Firework.app.opt_gravity if Firework.app else 1.0
            self.velocities[:, 1] -= self.gravity * grav_scale * dt
            self.velocities -= self.velocities * self.drag * dt
            
            self.ages += dt
            
            life_ratio = self.ages / self.max_ages
            
            # Chemical dual-color transition over lifetime
            if self.type == 12:  # Diadem: keep gold for first 70% then transition to secondary colored tip
                ratio_col = np.clip((life_ratio - 0.7) / 0.3, 0.0, 1.0)[:, np.newaxis]
            else:
                ratio_col = np.clip((life_ratio - 0.3) / 0.7, 0.0, 1.0)[:, np.newaxis]
            p_col = np.array(self.color[:3], dtype=np.float32)
            s_col = np.array(self.secondary_color[:3], dtype=np.float32)
            self.colors[:, :3] = (1.0 - ratio_col) * p_col + ratio_col * s_col
            
            fade = np.clip(1.0 - life_ratio, 0.0, 1.0)
            flicker = np.ones_like(fade)
            twinkle_mask = life_ratio > 0.4
            flicker[twinkle_mask] = np.where(
                np.random.rand(np.sum(twinkle_mask)) < 0.15,
                0.2,
                1.0
            )
            self.colors[:, 3] = fade * flicker
            
            # Delay Crackle Time Rain physics / strobe
            if self.type == 15:
                crackle_mask = life_ratio > 0.45
                num_crackle = np.sum(crackle_mask)
                if num_crackle > 0:
                    # High-frequency position jitter 
                    jitter = np.random.uniform(-0.15, 0.15, (num_crackle, 3)).astype(np.float32)
                    self.positions[crackle_mask] += jitter
                    
                    # Magnesium strobe white colors
                    strobe = np.random.rand(num_crackle) < 0.45
                    self.colors[crackle_mask, :3] = np.where(
                        strobe[:, np.newaxis],
                        np.array([1.0, 1.0, 0.95], dtype=np.float32),
                        np.array(self.color[:3], dtype=np.float32)
                    )
                    flicker[crackle_mask] = np.where(strobe, 1.0, 0.15)
                    self.colors[crackle_mask, 3] = fade[crackle_mask] * flicker[crackle_mask]

            if self.history_len > 1:
                self.history[1:] = self.history[:-1]
                self.history[0] = self.positions.copy()
                
            alive = self.ages < self.max_ages
            if np.any(alive):
                self.positions = self.positions[alive]
                self.velocities = self.velocities[alive]
                self.colors = self.colors[alive]
                self.ages = self.ages[alive]
                self.max_ages = self.max_ages[alive]
                if self.history_len > 1:
                    self.history = self.history[:, alive]
            else:
                self.state = 'DEAD'
