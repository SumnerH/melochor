import numpy as np
import random
from helpers import get_palette_colors

class SynaesthesiaModeMixin:
    def init_synaesthesia_mode(self):
        if not hasattr(self, 'syn_points_are_diamonds'):
            self.syn_points_are_diamonds = True
        if not hasattr(self, 'syn_star_size'):
            self.syn_star_size = 0.5
        if not hasattr(self, 'syn_brightness'):
            self.syn_brightness = 0.35
        if not hasattr(self, 'syn_fade_mode'):
            self.syn_fade_mode = "Stars"
        if not hasattr(self, 'syn_fg_red_slider'):
            self.syn_fg_red_slider = 0.0
        if not hasattr(self, 'syn_fg_green_slider'):
            self.syn_fg_green_slider = 0.5
        if not hasattr(self, 'syn_bg_red_slider'):
            self.syn_bg_red_slider = 0.75
        if not hasattr(self, 'syn_bg_green_slider'):
            self.syn_bg_green_slider = 0.4
        self.syn_stars = []

    def update_synaesthesia(self, dt):
        # Move and filter active stars
        active_stars = []
        for star in self.syn_stars:
            # Smoothly transition existing particles if user toggles fade mode in real-time
            if self.syn_fade_mode == "Stars":
                star['vel'] = np.array([0.0, 0.0, 0.0], dtype=np.float32)
            elif self.syn_fade_mode == "Flame":
                if np.all(star['vel'] == 0.0) or star['vel'][1] <= 0.0:
                    star['vel'] = np.array([np.random.uniform(-0.15, 0.15), np.random.uniform(1.2, 1.8), 0.0], dtype=np.float32)
            elif self.syn_fade_mode == "Wave":
                if np.all(star['vel'] == 0.0) or (star['vel'][0] == 0.0 and star['vel'][1] == 0.0):
                    theta = np.random.uniform(0.0, 2.0 * np.pi)
                    star['vel'] = np.array([np.cos(theta) * 1.5, np.sin(theta) * 1.5, 0.0], dtype=np.float32)
            
            star['pos'] += star['vel'] * dt
            star['life'] -= dt
            
            # Record position history for trailers if enabled
            if self.opt_trailers > 0:
                if 'history' not in star or star['history'] is None:
                    star['history'] = []
                star['history'].append(star['pos'].copy())
                # Limit history to match the trailers range
                target_len = self.opt_trailers * 2 + 1
                while len(star['history']) > target_len:
                    star['history'].pop(0)
            else:
                if 'history' in star:
                    star['history'] = None

            if star['life'] > 0.0:
                active_stars.append(star)
        self.syn_stars = active_stars

        # Spawn stars based on real-time frequency reactions
        if self.react_bass > 0.15:
            count = int(self.react_bass * 4)
            for _ in range(count):
                self.spawn_syn_star("bass", self.react_bass)

        if self.react_mid > 0.15:
            count = int(self.react_mid * 3)
            for _ in range(count):
                self.spawn_syn_star("mid", self.react_mid)

        if self.react_treble > 0.15:
            count = int(self.react_treble * 3)
            for _ in range(count):
                self.spawn_syn_star("treble", self.react_treble)

        if self.active_rarity is not None:
            self.update_active_rarity(dt)

    def spawn_syn_star(self, band, reaction_val):
        pan_x = self.current_stereo_panning * 8.0

        if band == "bass":
            y = np.random.uniform(0.5, 2.5)
            f_intensity = np.random.uniform(180.0, 255.0) * min(2.0, reaction_val)
            b_intensity = np.random.uniform(120.0, 255.0) * min(2.0, reaction_val)
            size_coef = np.random.uniform(1.2, 1.8)
        elif band == "mid":
            y = np.random.uniform(2.5, 5.5)
            f_intensity = np.random.uniform(150.0, 240.0) * min(2.0, reaction_val)
            b_intensity = np.random.uniform(100.0, 220.0) * min(2.0, reaction_val)
            size_coef = np.random.uniform(0.9, 1.3)
        else:  # treble
            y = np.random.uniform(5.5, 7.5)
            f_intensity = np.random.uniform(120.0, 220.0) * min(2.0, reaction_val)
            b_intensity = np.random.uniform(80.0, 180.0) * min(2.0, reaction_val)
            size_coef = np.random.uniform(0.6, 1.0)

        z = 0.0
        x = pan_x + np.random.uniform(-1.5, 1.5)

        if self.syn_fade_mode == "Flame":
            vx = np.random.uniform(-0.15, 0.15)
            vy = np.random.uniform(1.2, 1.8)
        elif self.syn_fade_mode == "Wave":
            theta = np.random.uniform(0.0, 2.0 * np.pi)
            vx = np.cos(theta) * 1.5
            vy = np.sin(theta) * 1.5
        else:  # "Stars"
            vx = 0.0
            vy = 0.0
        vz = 0.0

        self.syn_stars.append({
            'pos': np.array([x, y, z], dtype=np.float32),
            'vel': np.array([vx, vy, vz], dtype=np.float32),
            'f_intensity': f_intensity,
            'b_intensity': b_intensity,
            'life': np.random.uniform(2.2, 3.5),
            'size_coef': size_coef
        })

    def trigger_syn_star_burst(self):
        print("TRIGGERING SYNAESTHESIA STAR BURST!")
        for _ in range(45):
            angle = np.random.uniform(0.0, 2.0 * np.pi)
            r_dist = np.random.uniform(0.0, 3.5)
            x = r_dist * np.cos(angle)
            y = 4.0 + r_dist * np.sin(angle)
            z = 0.0

            speed = np.random.uniform(1.5, 3.2)
            vx = np.cos(angle) * speed
            vy = np.sin(angle) * speed
            vz = 0.0

            self.syn_stars.append({
                'pos': np.array([x, y, z], dtype=np.float32),
                'vel': np.array([vx, vy, vz], dtype=np.float32),
                'f_intensity': np.random.uniform(220.0, 255.0),
                'b_intensity': np.random.uniform(180.0, 255.0),
                'life': np.random.uniform(2.5, 4.0),
                'size_coef': np.random.uniform(1.3, 2.2)
            })

    def render_synaesthesia(self):
        pts = []
        cols = []
        sizes = []

        fade_fudge = 0.78
        if self.syn_fade_mode == "Wave":
            fade_fudge = 0.4
        elif self.syn_fade_mode == "Flame":
            fade_fudge = 0.6

        size = self.syn_star_size
        if self.opt_trailers > 0:
            decay_scale = 1.0 - min(0.9, self.opt_trailers * 0.08)
            factor = 256.0 - (256.0 - (min(255.0, np.exp(np.log(fade_fudge) / (size * 8.0)) * 255.0) if size > 0.0 else 0.0)) * decay_scale
        else:
            factor = min(255.0, np.exp(np.log(fade_fudge) / (size * 8.0)) * 255.0) if size > 0.0 else 0.0

        fgRed = self.syn_fg_red_slider
        fgGreen = self.syn_fg_green_slider
        if self.opt_color_mode != 'REALISTIC':
            pal = get_palette_colors(self.opt_color_mode)
            c1, c2 = pal[0], pal[1 % len(pal)]
            fgRed, fgGreen, fgBlue = c1[0], c1[1], c1[2]
            bgRed, bgGreen, bgBlue = c2[0], c2[1], c2[2]
            fg_s = fgRed + fgGreen + fgBlue
            if fg_s > 0.0:
                fgRed, fgGreen, fgBlue = (fgRed/fg_s)*2.0, (fgGreen/fg_s)*2.0, (fgBlue/fg_s)*2.0
            bg_s = bgRed + bgGreen + bgBlue
            if bg_s > 0.0:
                bgRed, bgGreen, bgBlue = (bgRed/bg_s)*2.0, (bgGreen/bg_s)*2.0, (bgBlue/bg_s)*2.0
        else:
            fgBlue = 1.0 - max(fgRed, fgGreen)
            bgRed = self.syn_bg_red_slider
            bgGreen = self.syn_bg_green_slider
            bgBlue = 1.0 - max(bgRed, bgGreen)
        
        fg_scale = (fgRed + fgGreen + fgBlue) / 2.0
        if fg_scale > 0.0:
            fgRed /= fg_scale
            fgGreen /= fg_scale
            fgBlue /= fg_scale
        bg_scale = (bgRed + bgGreen + bgBlue) / 2.0
        if bg_scale > 0.0:
            bgRed /= bg_scale
            bgGreen /= bg_scale
            bgBlue /= bg_scale

        def map_color(f, b):
            red = b * bgRed + f * fgRed
            green = b * bgGreen + f * fgGreen
            blue = b * bgBlue + f * fgBlue

            excess = 0.0
            for _ in range(5):
                red += excess / 3.0
                green += excess / 3.0
                blue += excess / 3.0
                excess = 0.0
                if red > 255.0:
                    excess += (red - 255.0)
                    red = 255.0
                if green > 255.0:
                    excess += (green - 255.0)
                    green = 255.0
                if blue > 255.0:
                    excess += (blue - 255.0)
                    blue = 255.0

            scale_col = (0.5 + (red + green + blue) / 768.0) / 1.5
            red *= scale_col
            green *= scale_col
            blue *= scale_col

            return [
                min(1.0, max(0.0, red / 255.0)),
                min(1.0, max(0.0, green / 255.0)),
                min(1.0, max(0.0, blue / 255.0)),
                1.0
            ]

        for star in self.syn_stars:
            cx, cy, cz = star['pos']
            f = star['f_intensity']
            b = star['b_intensity']

            pts.append([cx, cy, cz])
            cols.append(map_color(f, b))
            sizes.append(5.0 * self.syn_brightness * star.get('size_coef', 1.0))

            curr_f = f
            curr_b = b
            step_size = 0.09 * self.syn_star_size * star.get('size_coef', 1.0)

            # Draw base star with constant trail range (9) so size remains constant
            trail_range = 9
            for j in range(1, trail_range):
                curr_f = curr_f * factor / 256.0
                curr_b = curr_b * factor / 256.0
                if curr_f < 3.0 and curr_b < 3.0:
                    break

                color = map_color(curr_f, curr_b)
                life_frac = star['life'] / 3.5
                color[3] = min(1.0, max(0.0, life_frac))

                if self.syn_points_are_diamonds:
                    for k in range(j):
                        pts.append([cx + (-j + k) * step_size, cy - k * step_size, cz])
                        pts.append([cx + k * step_size, cy - (j - k) * step_size, cz])
                        pts.append([cx + (j - k) * step_size, cy + k * step_size, cz])
                        pts.append([cx - k * step_size, cy + (j - k) * step_size, cz])
                        for _ in range(4):
                            cols.append(color)
                            sizes.append(4.0 * self.syn_brightness * star.get('size_coef', 1.0))
                else:
                    pts.append([cx + j * step_size, cy, cz])
                    pts.append([cx, cy + j * step_size, cz])
                    pts.append([cx - j * step_size, cy, cz])
                    pts.append([cx, cy - j * step_size, cz])
                    for _ in range(4):
                        cols.append(color)
                        sizes.append(4.0 * self.syn_brightness * star.get('size_coef', 1.0))

            # Draw trailers along movement history if enabled
            if self.opt_trailers > 0 and 'history' in star and star['history']:
                history_list = star['history']
                num_trailers = self.opt_trailers
                for i in range(1, num_trailers + 1):
                    # We space them out backward (e.g. 2 steps per trailer level)
                    idx = -1 - i * 2
                    if abs(idx) <= len(history_list):
                        tcx, tcy, tcz = history_list[idx]
                        
                        # Decay factor for this trailer level
                        trail_decay = (1.0 - (i / (num_trailers + 1.0)))
                        tf = f * trail_decay
                        tb = b * trail_decay
                        
                        # Draw center of the trailer point
                        t_color = map_color(tf, tb)
                        life_frac = star['life'] / 3.5
                        t_color[3] = min(1.0, max(0.0, life_frac)) * trail_decay
                        pts.append([tcx, tcy, tcz])
                        cols.append(t_color)
                        sizes.append(4.0 * self.syn_brightness * star.get('size_coef', 1.0) * trail_decay)
                        
                        # Draw a smaller cross/diamond around the trailer point for a smooth glow
                        t_step_size = 0.09 * self.syn_star_size * star.get('size_coef', 1.0) * trail_decay
                        for tj in range(1, 3):
                            t_curr_f = tf * (0.6 ** tj)
                            t_curr_b = tb * (0.6 ** tj)
                            t_color_j = map_color(t_curr_f, t_curr_b)
                            t_color_j[3] = min(1.0, max(0.0, life_frac)) * trail_decay
                            
                            if self.syn_points_are_diamonds:
                                for tk in range(tj):
                                    pts.append([tcx + (-tj + tk) * t_step_size, tcy - tk * t_step_size, tcz])
                                    pts.append([tcx + tk * t_step_size, tcy - (tj - tk) * t_step_size, tcz])
                                    pts.append([tcx + (tj - tk) * t_step_size, tcy + tk * t_step_size, tcz])
                                    pts.append([tcx - tk * t_step_size, tcy + (tj - tk) * t_step_size, tcz])
                                    for _ in range(4):
                                        cols.append(t_color_j)
                                        sizes.append(3.0 * self.syn_brightness * star.get('size_coef', 1.0) * trail_decay)
                            else:
                                pts.append([tcx + tj * t_step_size, tcy, tcz])
                                pts.append([tcx, tcy + tj * t_step_size, tcz])
                                pts.append([tcx - tj * t_step_size, tcy, tcz])
                                pts.append([tcx, tcy - tj * t_step_size, tcz])
                                for _ in range(4):
                                    cols.append(t_color_j)
                                    sizes.append(3.0 * self.syn_brightness * star.get('size_coef', 1.0) * trail_decay)

        if not hasattr(self, 'syn_bg_particles'):
            self.syn_bg_particles = []
            for _ in range(300):
                self.syn_bg_particles.append({
                    'pos': np.array([np.random.uniform(-25.0, 25.0), np.random.uniform(-10.0, 18.0), -5.0], dtype=np.float32),
                    'col': [np.random.uniform(0.0, 0.25), np.random.uniform(0.1, 0.35), np.random.uniform(0.2, 0.6), np.random.uniform(0.25, 0.55)],
                    'size': np.random.uniform(1.5, 3.5),
                    'phase': np.random.uniform(0.0, 2.0 * np.pi),
                    'speed': np.random.uniform(1.0, 3.5)
                })

        for p in self.syn_bg_particles:
            # Twinkle individually over time
            p['phase'] += 0.016 * p['speed']
            if p['phase'] > 2.0 * np.pi:
                p['phase'] -= 2.0 * np.pi

            pts.append(p['pos'])
            col = p['col'].copy()
            twinkle = 0.5 + 0.5 * np.sin(p['phase'])
            col[3] *= (0.3 + 0.7 * twinkle) * (0.4 + self.react_mid * 0.6)
            if self.opt_color_mode != 'REALISTIC':
                pal = get_palette_colors(self.opt_color_mode)
                c_bg = pal[2 % len(pal)]
                col[:3] = c_bg[:3]
            cols.append(col)
            sizes.append(p['size'])

        h_pos = np.zeros((0, 3), dtype=np.float32)
        h_col = np.zeros((0, 4), dtype=np.float32)
        return pts, cols, sizes, h_pos, h_col
