import math
import numpy as np

def make_solid_seahorse(center, phase):
    """Generates an organic, beautifully lit, 2.5D classic seahorse profile silhouette with a realistic S-spine, wiggling tail, and elegant highlights."""
    vertices = []
    colors = []
    
    # Deep midnight navy base, sapphire chest, and glowing cyan-blue highlights
    spine_col = [0.02, 0.04, 0.18, 1.0]      # Deep midnight navy base
    chest_col = [0.08, 0.18, 0.48, 1.0]      # Sapphire chest
    cyan_highlight = [0.0, 0.72, 0.95, 1.0]  # Glowing cyan-blue highlights
    
    segments = 16
    nodes = []
    
    # 1. Generate skeleton nodes relative to origin [0,0,0]
    for i in range(segments):
        t = i / (segments - 1)
        
        # Snout (t: 0.0 to 0.15)
        if t <= 0.15:
            frac = t / 0.15
            x = 0.48 - frac * 0.33
            y = 0.65 + frac * 0.08
            
        # Head / Crown (t: 0.15 to 0.28)
        elif t <= 0.28:
            frac = (t - 0.15) / 0.13
            x = 0.15 - 0.20 * math.sin(frac * math.pi * 0.5)
            y = 0.73 + 0.19 * math.sin(frac * math.pi * 0.5)
            
        # Neck / Throat (t: 0.28 to 0.42)
        elif t <= 0.42:
            frac = (t - 0.28) / 0.14
            x = -0.05 - 0.07 * math.sin(frac * math.pi * 0.5)
            y = 0.92 - 0.42 * math.sin(frac * math.pi * 0.5)
            
        # Chest / Trunk (t: 0.42 to 0.65)
        elif t <= 0.65:
            frac = (t - 0.42) / 0.23
            x = -0.12 + 0.20 * math.sin(frac * math.pi)
            y = 0.50 - 0.70 * frac
            
        # Tail Spiral (t: 0.65 to 1.0)
        else:
            frac = (t - 0.65) / 0.35
            c_x, c_y = 0.05, -0.38
            R_start = math.sqrt((-0.12 - c_x)**2 + (-0.20 - c_y)**2)
            theta_start = math.atan2(-0.20 - c_y, -0.12 - c_x)
            
            theta = theta_start - frac * 3.8 * math.pi
            R = R_start * (1.0 - 0.88 * frac) * math.exp(-0.04 * frac * 3.8 * math.pi)
            
            x = c_x + R * math.cos(theta)
            y = c_y + R * math.sin(theta)
            
        # Dynamic wiggling tail physics synchronized with audio bobbing phase
        if t > 0.65:
            x += math.sin(t * 15.0 - phase * 2.5) * 0.04 * (t - 0.65)
            
        nodes.append([x, y])

    # 2. Compute widths (w_front and w_back) for classic profile
    w_front = [0.0] * segments
    w_back = [0.0] * segments
    
    for i in range(segments):
        t = i / (segments - 1)
        
        # Snout (t: 0.0 to 0.15)
        if t <= 0.15:
            w_front[i] = 0.02
            w_back[i] = 0.02
            if t < 0.04:
                flare = 0.025 * (1.0 - t / 0.04)
                w_front[i] += flare * 1.5
                w_back[i] += flare * 0.5
                
        # Head (t: 0.15 to 0.28)
        elif t <= 0.28:
            frac = (t - 0.15) / 0.13
            w_front[i] = 0.02 + 0.055 * math.sin(frac * math.pi)
            w_back[i] = 0.02 + 0.045 * math.sin(frac * math.pi)
            
        # Neck (t: 0.28 to 0.42)
        elif t <= 0.42:
            frac = (t - 0.28) / 0.14
            w_front[i] = 0.04 - 0.015 * math.sin(frac * math.pi)
            w_back[i] = 0.035 - 0.015 * math.sin(frac * math.pi)
            
        # Chest / Trunk (t: 0.42 to 0.65)
        elif t <= 0.65:
            frac = (t - 0.42) / 0.23
            w_front[i] = 0.025 + 0.10 * math.sin(frac * math.pi)
            w_back[i] = 0.02 + 0.04 * math.sin(frac * math.pi)
            
        # Tail (t: 0.65 to 1.0)
        else:
            frac = (t - 0.65) / 0.35
            w_front[i] = max(0.005, 0.028 * (1.0 - frac))
            w_back[i] = max(0.005, 0.024 * (1.0 - frac))
            
        # Bony ridges (sharp spines) along the back/left edge
        if t > 0.20 and t < 0.85:
            spines = max(0.0, math.sin(t * 110.0)) ** 2.5
            w_back[i] += 0.032 * spines
            
        # Add a gorgeous crown (coronet) at the top of the head
        if t >= 0.23 and t <= 0.28:
            crown_frac = (t - 0.23) / 0.05
            w_back[i] += 0.045 * max(0.0, math.sin(crown_frac * math.pi * 3.0)) ** 1.5

    # 3. Light vector L
    Lx, Ly, Lz = 0.6, 0.8, 0.4
    L_len = math.sqrt(Lx*Lx + Ly*Ly + Lz*Lz)
    Lx /= L_len
    Ly /= L_len
    Lz /= L_len
    
    def get_shaded_color(col, nx, ny, nz):
        dot = nx*Lx + ny*Ly + nz*Lz
        shade = 0.25 + 0.75 * max(0.0, dot)
        return [max(0.0, min(1.0, col[0] * shade)),
                max(0.0, min(1.0, col[1] * shade)),
                max(0.0, min(1.0, col[2] * shade)),
                col[3]]

    z_thick = 0.035
    
    for i in range(segments - 1):
        t0 = i / (segments - 1)
        t1 = (i + 1) / (segments - 1)
        
        # Calculate tangent & normal for i
        if i == 0:
            tx = nodes[1][0] - nodes[0][0]
            ty = nodes[1][1] - nodes[0][1]
        else:
            tx = nodes[i+1][0] - nodes[i-1][0]
            ty = nodes[i+1][1] - nodes[i-1][1]
        t_len = math.sqrt(tx*tx + ty*ty)
        if t_len > 1e-4:
            tx /= t_len
            ty /= t_len
        else:
            tx, ty = 0.0, -1.0
        normal0_x = -ty
        normal0_y = tx
        
        # Calculate tangent & normal for i+1
        if i + 1 == segments - 1:
            tx_next = nodes[-1][0] - nodes[-2][0]
            ty_next = nodes[-1][1] - nodes[-2][1]
        else:
            tx_next = nodes[i+2][0] - nodes[i][0]
            ty_next = nodes[i+2][1] - nodes[i][1]
        t_len_next = math.sqrt(tx_next*tx_next + ty_next*ty_next)
        if t_len_next > 1e-4:
            tx_next /= t_len_next
            ty_next /= t_len_next
        else:
            tx_next, ty_next = 0.0, -1.0
        normal1_x = -ty_next
        normal1_y = tx_next
        
        # Front face coordinates (Z = +z_thick)
        p_f_left_top = [nodes[i][0] - w_back[i] * normal0_x, nodes[i][1] - w_back[i] * normal0_y, z_thick]
        p_f_right_top = [nodes[i][0] + w_front[i] * normal0_x, nodes[i][1] + w_front[i] * normal0_y, z_thick]
        p_f_left_bottom = [nodes[i+1][0] - w_back[i+1] * normal1_x, nodes[i+1][1] - w_back[i+1] * normal1_y, z_thick]
        p_f_right_bottom = [nodes[i+1][0] + w_front[i+1] * normal1_x, nodes[i+1][1] + w_front[i+1] * normal1_y, z_thick]
        
        # Back face coordinates (Z = -z_thick)
        p_b_left_top = [p_f_left_top[0], p_f_left_top[1], -z_thick]
        p_b_right_top = [p_f_right_top[0], p_f_right_top[1], -z_thick]
        p_b_left_bottom = [p_f_left_bottom[0], p_f_left_bottom[1], -z_thick]
        p_b_right_bottom = [p_f_right_bottom[0], p_f_right_bottom[1], -z_thick]
        
        col_left_top = cyan_highlight if (t0 >= 0.23 and t0 <= 0.28) else spine_col
        col_left_bottom = cyan_highlight if (t1 >= 0.23 and t1 <= 0.28) else spine_col
        
        col_right_top = cyan_highlight if t0 <= 0.15 else chest_col
        col_right_bottom = cyan_highlight if t1 <= 0.15 else chest_col
        
        if t0 > 0.42 and t0 <= 0.65:
            col_right_top = chest_col
        if t1 > 0.42 and t1 <= 0.65:
            col_right_bottom = chest_col
            
        c_f_lt = get_shaded_color(col_left_top, 0.0, 0.0, 1.0)
        c_f_rt = get_shaded_color(col_right_top, 0.0, 0.0, 1.0)
        c_f_lb = get_shaded_color(col_left_bottom, 0.0, 0.0, 1.0)
        c_f_rb = get_shaded_color(col_right_bottom, 0.0, 0.0, 1.0)
        
        c_b_lt = get_shaded_color(col_left_top, 0.0, 0.0, -1.0)
        c_b_rt = get_shaded_color(col_right_top, 0.0, 0.0, -1.0)
        c_b_lb = get_shaded_color(col_left_bottom, 0.0, 0.0, -1.0)
        c_b_rb = get_shaded_color(col_right_bottom, 0.0, 0.0, -1.0)
        
        # 2. Add Front Face (CCW)
        vertices.extend([p_f_left_top, p_f_right_bottom, p_f_right_top])
        colors.extend([c_f_lt, c_f_rb, c_f_rt])
        vertices.extend([p_f_left_top, p_f_left_bottom, p_f_right_bottom])
        colors.extend([c_f_lt, c_f_lb, c_f_rb])
        
        # 3. Add Back Face (CCW viewed from back)
        vertices.extend([p_b_left_top, p_b_right_top, p_b_right_bottom])
        colors.extend([c_b_lt, c_b_rt, c_b_rb])
        vertices.extend([p_b_left_top, p_b_right_bottom, p_b_left_bottom])
        colors.extend([c_b_lt, c_b_rb, c_b_lb])
        
        # 4. Add Left Side Wall (Spine edge)
        c_l_lt = get_shaded_color(col_left_top, -normal0_x, -normal0_y, 0.0)
        c_l_lb = get_shaded_color(col_left_bottom, -normal1_x, -normal1_y, 0.0)
        
        vertices.extend([p_f_left_top, p_b_left_bottom, p_b_left_top])
        colors.extend([c_l_lt, c_l_lb, c_l_lt])
        vertices.extend([p_f_left_top, p_f_left_bottom, p_b_left_bottom])
        colors.extend([c_l_lt, c_l_lb, c_l_lb])
        
        # 5. Add Right Side Wall (Chest edge)
        c_r_rt = get_shaded_color(col_right_top, normal0_x, normal0_y, 0.0)
        c_r_rb = get_shaded_color(col_right_bottom, normal1_x, normal1_y, 0.0)
        
        vertices.extend([p_f_right_top, p_f_right_bottom, p_b_right_bottom])
        colors.extend([c_r_rt, c_r_rb, c_r_rb])
        vertices.extend([p_f_right_top, p_b_right_bottom, p_b_right_top])
        colors.extend([c_r_rt, c_r_rb, c_r_rt])
        
    # 4. Apply dynamic 3D swimming/bobbing rotations to all vertices relative to origin using vectorized NumPy transformations
    pitch_ang = 0.15 * math.cos(phase * 1.3) + 0.05 * math.sin(phase * 2.5)
    roll_ang = 0.12 * math.sin(phase * 1.1)
    yaw_ang = 0.08 * math.cos(phase * 0.7)
    
    cp, sp = math.cos(pitch_ang), math.sin(pitch_ang)
    cr, sr = math.cos(roll_ang), math.sin(roll_ang)
    cy, sy = math.cos(yaw_ang), math.sin(yaw_ang)
    
    cx, cy, cz = center[0], center[1], center[2]
    
    if len(vertices) > 0:
        v_arr = np.array(vertices, dtype=np.float32)
        x, y, z = v_arr[:, 0], v_arr[:, 1], v_arr[:, 2]
        x1 = cp * x - sp * y
        y1 = sp * x + cp * y
        z1 = z
        
        x2 = x1
        y2 = cr * y1 - sr * z1
        z2 = sr * y1 + cr * z1
        
        x3 = cy * x2 + sy * z2
        y3 = y2
        z3 = -sy * x2 + cy * z2
        
        rotated_vertices = np.stack([x3 + cx, y3 + cy, z3 + cz], axis=1).tolist()
    else:
        rotated_vertices = []
        
    return rotated_vertices, colors
