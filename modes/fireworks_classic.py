import numpy as np
import random
from firework import Firework
from constants import COLORS


class FireworksClassicMixin:
    def trigger_routine(self, name, launch_func):
        self.routine_queue.clear()
        self.active_routine_name = name
        self.routine_timer = 5.0
        launch_func()

    def launch_american_flag(self):
        # Red stripes
        for x in [-9.0, -3.0, 3.0, 9.0]:
            self.routine_queue.append((0.0, Firework(fw_type=0, color=COLORS["strontium_red"], x_offset=x)))
        # White stripes
        for x in [-6.0, 0.0, 6.0]:
            self.routine_queue.append((0.2, Firework(fw_type=1, color=COLORS["magnesium_white"], x_offset=x)))
        # Blue canton stars
        for x in [-11.0, -7.0]:
            fw = Firework(fw_type=3, color=COLORS["copper_blue"], x_offset=x)
            fw.launch_vel[1] += 3.0
            self.routine_queue.append((0.4, fw))

    def launch_liberty_bell(self):
        # Top of the bell
        top_crown = Firework(fw_type=12, color=COLORS["sodium_gold"], x_offset=0.0)
        top_crown.launch_vel[1] += 4.0
        self.routine_queue.append((0.0, top_crown))
        
        # Sides of the bell fanning down
        left_waterfall = Firework(fw_type=5, color=COLORS["sodium_gold"], x_offset=-4.0)
        left_waterfall.launch_vel[0] = -1.5
        right_waterfall = Firework(fw_type=5, color=COLORS["sodium_gold"], x_offset=4.0)
        right_waterfall.launch_vel[0] = 1.5
        self.routine_queue.append((0.2, left_waterfall))
        self.routine_queue.append((0.2, right_waterfall))
        
        # Clapper at bottom cracking/crackling
        clapper = Firework(fw_type=15, color=COLORS["magnesium_white"], x_offset=0.0)
        clapper.launch_vel[1] -= 2.0
        self.routine_queue.append((0.5, clapper))

    def launch_statue_of_liberty(self):
        # Pedestal/Body (green waterfall)
        body = Firework(fw_type=5, color=COLORS["barium_green"], x_offset=-2.0)
        self.routine_queue.append((0.0, body))
        
        # Crown Rays (radiating green ghost rings)
        for idx, (x, vx) in enumerate([(-6.0, -3.0), (-2.0, -1.0), (2.0, 1.0)]):
            ray = Firework(fw_type=3, color=COLORS["barium_green"], x_offset=x)
            ray.launch_vel[0] = vx
            self.routine_queue.append((0.1 * idx, ray))
            
        # Golden Torch (high up on the right)
        torch = Firework(fw_type=11, color=COLORS["sodium_gold"], x_offset=3.0)
        torch.launch_vel[1] += 5.0
        torch.launch_vel[0] = 1.5
        self.routine_queue.append((0.4, torch))

    def launch_flower_bouquet(self):
        colors = [COLORS["strontium_red"], COLORS["barium_green"], COLORS["potassium_purple"], COLORS["calcium_orange"], COLORS["sodium_gold"]]
        types = [0, 1, 11]
        for idx, x in enumerate([-8.0, -4.0, 0.0, 4.0, 8.0]):
            col = colors[idx % len(colors)]
            t = types[idx % len(types)]
            fw = Firework(fw_type=t, color=col, x_offset=x)
            fw.launch_vel[0] = x * 0.4
            self.routine_queue.append((0.0, fw))

    def launch_the_dragon(self):
        for i in range(12):
            delay = i * 0.15
            x = -12.0 + i * 2.0
            col = COLORS["barium_green"] if i % 2 == 0 else COLORS["sodium_gold"]
            t = 17 if i % 2 == 0 else 6
            fw = Firework(fw_type=t, color=col, x_offset=x)
            fw.launch_vel[0] = -1.0 + (i * 0.2)
            self.routine_queue.append((delay, fw))
            
    def launch_supernova(self):
        fw_center = Firework(fw_type=4, color=COLORS["magnesium_white"], x_offset=0.0)
        fw_center.launch_vel = np.array([0.0, 26.0, 0.0], dtype=np.float32)
        fw_center.star_size = 15.0
        fw_center.secondary_color = COLORS["copper_blue"]
        self.routine_queue.append((0.0, fw_center))
        
        for angle in np.linspace(0, 2 * np.pi, 6, endpoint=False):
            x = 8.0 * np.cos(angle)
            z = 6.0 * np.sin(angle)
            fw_ring = Firework(fw_type=7, color=COLORS["sodium_gold"], x_offset=x)
            fw_ring.launch_pos[2] = z
            fw_ring.launch_vel = np.array([x * 0.15, 23.0, z * 0.15], dtype=np.float32)
            fw_ring.secondary_color = COLORS["potassium_purple"]
            self.routine_queue.append((0.4, fw_ring))
            
        for x in [-5.0, 5.0]:
            fw_crack = Firework(fw_type=15, color=COLORS["magnesium_white"], x_offset=x)
            fw_crack.launch_vel[1] = 24.0
            self.routine_queue.append((1.2, fw_crack))
            
    def launch_shooting_star(self):
        fw_left = Firework(fw_type=18, color=COLORS["magnesium_white"], x_offset=-14.0)
        fw_left.launch_vel = np.array([12.0, 16.0, -2.0], dtype=np.float32)
        fw_left.launch_fuse = 2.0
        fw_left.star_size = 10.0
        fw_left.secondary_color = COLORS["sodium_gold"]
        self.routine_queue.append((0.0, fw_left))
        
        fw_right = Firework(fw_type=18, color=COLORS["magnesium_white"], x_offset=14.0)
        fw_right.launch_vel = np.array([-12.0, 17.0, 2.0], dtype=np.float32)
        fw_right.launch_fuse = 2.0
        fw_right.star_size = 10.0
        fw_right.secondary_color = COLORS["sodium_gold"]
        self.routine_queue.append((0.3, fw_right))
        
        fw_mid = Firework(fw_type=10, color=COLORS["copper_blue"], x_offset=0.0)
        fw_mid.launch_vel = np.array([0.0, 25.0, -1.0], dtype=np.float32)
        fw_mid.secondary_color = COLORS["magnesium_white"]
        self.routine_queue.append((0.6, fw_mid))

    def spawn_rarity_fireworks(self, r_type):
        if r_type == "CATHERINE_WHEEL":
            # Move Catherine Wheel center up to align with screen bottom (Y = -4.5)
            pos = np.array([np.random.uniform(-10.0, 10.0), -4.5, np.random.uniform(-5.0, -1.0)], dtype=np.float32)
            self.active_rarity = {
                'type': 'CATHERINE_WHEEL',
                'pos': pos,
                'phase': 0.0,
                'spin_vel': 18.0,
                'sparks_pos': [],
                'sparks_vel': [],
                'sparks_col': [],
                'sparks_age': [],
                'life': 10.0,
                'max_life': 10.0
            }

    def update_rarity_fireworks(self, r, dt):
        r['phase'] += r['spin_vel'] * dt
        for i in range(4):
            ang = r['phase'] + i * (np.pi / 2.0)
            nozzle_pos = r['pos'] + np.array([np.cos(ang) * 0.5, np.sin(ang) * 0.5, 0.0], dtype=np.float32)
            out_dir = np.array([np.cos(ang), np.sin(ang), np.random.uniform(-0.15, 0.15)], dtype=np.float32)
            tangent_dir = np.array([-np.sin(ang), np.cos(ang), 0.0], dtype=np.float32)
            spark_vel = out_dir * np.random.uniform(6.0, 12.0) + tangent_dir * 8.0
            r['sparks_pos'].append(nozzle_pos)
            r['sparks_vel'].append(spark_vel)
            r['sparks_col'].append(random.choice([
                [1.0, 0.8, 0.1, 1.0],
                [0.9, 0.9, 0.95, 1.0],
                [1.0, 0.3, 0.1, 1.0]
            ]))
            r['sparks_age'].append(0.0)
        rem_pos, rem_vel, rem_col, rem_age = [], [], [], []
        for j in range(len(r['sparks_pos'])):
            r['sparks_age'][j] += dt
            if r['sparks_age'][j] < 0.8:
                r['sparks_vel'][j][1] -= 9.8 * dt # gravity
                next_pos = r['sparks_pos'][j] + r['sparks_vel'][j] * dt
                # Bounce or slide realistically on the floor plane Y = -12.0
                if next_pos[1] < -12.0:
                    next_pos[1] = -12.0
                    r['sparks_vel'][j][1] = -r['sparks_vel'][j][1] * 0.45 # bounce elasticity
                    r['sparks_vel'][j][0] *= 0.85 # friction
                    r['sparks_vel'][j][2] *= 0.85 # friction
                r['sparks_pos'][j] = next_pos
                r['sparks_col'][j][3] = 1.0 - (r['sparks_age'][j] / 0.8)
                rem_pos.append(r['sparks_pos'][j])
                rem_vel.append(r['sparks_vel'][j])
                rem_col.append(r['sparks_col'][j])
                rem_age.append(r['sparks_age'][j])
        r['sparks_pos'] = rem_pos
        r['sparks_vel'] = rem_vel
        r['sparks_col'] = rem_col
        r['sparks_age'] = rem_age
