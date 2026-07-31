import numpy as np

def make_solid_squid(center, direction, phase, react_bass, react_mid, react_treble):
    """Generates an opaque, matte deep-maroon 3D squid mantle with broader side fins, siphon, black eyes, wiggling arms, and extra-long tentacles."""
    sq_dir = direction / np.linalg.norm(direction)
    if abs(sq_dir[0]) < 0.9:
        sq_u = np.cross(sq_dir, [1.0, 0.0, 0.0])
    else:
        sq_u = np.cross(sq_dir, [0.0, 1.0, 0.0])
    sq_u /= np.linalg.norm(sq_u)
    sq_w = np.cross(sq_dir, sq_u)
    sq_w /= np.linalg.norm(sq_w)
    
    vertices = []
    colors = []
    
    # Matte deep maroon (completely non-glowing)
    maroon = [0.32, 0.06, 0.09, 1.0]
    dark_maroon = [0.24, 0.04, 0.06, 1.0]
    
    # Cone Mantle (12 rings, 16 slices for higher polygon smoothness)
    rings = 12
    slices = 16
    mantle_len = 1.8
    max_rad = 0.35
    
    mantle_vertices = []
    mantle_colors = []
    
    for r in range(rings):
        frac = r / (rings - 1)
        # Bullet/cone shape
        ring_rad = max_rad * np.sin(frac * np.pi * 0.5) if r > 0 else 0.0
        ring_len = mantle_len * (1.0 - frac)
        
        # Muted shade gradient along the body
        ring_col = [maroon[0] * (0.7 + 0.3 * frac), maroon[1], maroon[2], 1.0]
        
        for s in range(slices):
            ang = (s / slices) * 2.0 * np.pi
            offset = (sq_u * np.cos(ang) + sq_w * np.sin(ang)) * ring_rad - sq_dir * ring_len
            mantle_vertices.append(center + offset)
            mantle_colors.append(ring_col)
            
    # Stitch mantle
    for r in range(rings - 1):
        for s in range(slices):
            s_next = (s + 1) % slices
            i00 = r * slices + s
            i10 = r * slices + s_next
            i01 = (r + 1) * slices + s
            i11 = (r + 1) * slices + s_next
            
            vertices.extend([mantle_vertices[i00], mantle_vertices[i11], mantle_vertices[i10]])
            colors.extend([mantle_colors[i00], mantle_colors[i11], mantle_colors[i10]])
            vertices.extend([mantle_vertices[i00], mantle_vertices[i01], mantle_vertices[i11]])
            colors.extend([mantle_colors[i00], mantle_colors[i01], mantle_colors[i11]])
            
    # Broad side fins (diamond-shaped, wrapping around the mantle sides)
    # Fins run along the rear 60% of the mantle
    for side in [-1.0, 1.0]:
        for r in range(rings // 2, rings - 1):
            frac_curr = r / (rings - 1)
            frac_next = (r + 1) / (rings - 1)
            
            rad_curr = max_rad * np.sin(frac_curr * np.pi * 0.5)
            rad_next = max_rad * np.sin(frac_next * np.pi * 0.5)
            
            # Width peaks near the rear tip
            width_curr = 0.7 * np.sin((frac_curr - 0.5) / 0.5 * np.pi * 0.5) * mantle_len
            width_next = 0.7 * np.sin((frac_next - 0.5) / 0.5 * np.pi * 0.5) * mantle_len
            
            p_base_curr = center + sq_w * (side * rad_curr) - sq_dir * (mantle_len * (1.0 - frac_curr))
            p_tip_curr = p_base_curr + sq_w * (side * width_curr)
            
            p_base_next = center + sq_w * (side * rad_next) - sq_dir * (mantle_len * (1.0 - frac_next))
            p_tip_next = p_base_next + sq_w * (side * width_next)
            
            # Double-sided fin quads
            vertices.extend([p_base_curr, p_tip_next, p_tip_curr])
            colors.extend([maroon, maroon, maroon])
            vertices.extend([p_base_curr, p_base_next, p_tip_next])
            colors.extend([maroon, maroon, maroon])
            
            vertices.extend([p_base_curr, p_tip_curr, p_tip_next])
            colors.extend([maroon, maroon, maroon])
            vertices.extend([p_base_curr, p_tip_next, p_base_next])
            colors.extend([maroon, maroon, maroon])
            
    # Siphon / Funnel on underside (e.g. opposite of the up direction sq_u)
    siphon_base = center - sq_u * 0.22 - sq_dir * 0.1
    siphon_tip = siphon_base - sq_dir * 0.45 - sq_u * 0.1
    siphon_rad = 0.08
    for s in range(8):
        ang_curr = (s / 8.0) * 2.0 * np.pi
        ang_next = ((s + 1) / 8.0) * 2.0 * np.pi
        p_bc = siphon_base + (sq_w * np.cos(ang_curr) + sq_u * np.sin(ang_curr)) * siphon_rad
        p_bn = siphon_base + (sq_w * np.cos(ang_next) + sq_u * np.sin(ang_next)) * siphon_rad
        p_tc = siphon_tip + (sq_w * np.cos(ang_curr) + sq_u * np.sin(ang_curr)) * (siphon_rad * 0.5)
        p_tn = siphon_tip + (sq_w * np.cos(ang_next) + sq_u * np.sin(ang_next)) * (siphon_rad * 0.5)
        
        vertices.extend([p_bc, p_tn, p_bn])
        colors.extend([dark_maroon, dark_maroon, dark_maroon])
        vertices.extend([p_bc, p_tc, p_tn])
        colors.extend([dark_maroon, dark_maroon, dark_maroon])

    # Black Octahedron Eyes
    eye_col = [0.03, 0.03, 0.03, 1.0]
    for side in [-1.0, 1.0]:
        eye_pos = center + sq_w * (side * 0.32) + sq_u * 0.12
        d_x, u_x, w_x = sq_dir * 0.1, sq_u * 0.1, sq_w * 0.1
        pts = [eye_pos + d_x, eye_pos - d_x, eye_pos + u_x, eye_pos - u_x, eye_pos + w_x, eye_pos - w_x]
        eye_tris = [(0, 2, 4), (0, 4, 3), (0, 3, 5), (0, 5, 2), (1, 2, 5), (1, 5, 3), (1, 3, 4), (1, 4, 2)]
        for t0, t1, t2 in eye_tris:
            vertices.extend([pts[t0], pts[t1], pts[t2]])
            colors.extend([eye_col, eye_col, eye_col])
            
    # 8 Long wiggling Arms (7 segments, length 0.28, total length ~2.0, organic sinusoidal motion)
    for i_arm in range(8):
        arm_ang = i_arm * (2.0 * np.pi / 8.0)
        arm_dir = sq_u * np.cos(arm_ang) + sq_w * np.sin(arm_ang)
        arm_start = center + arm_dir * 0.16
        prev_pt = arm_start
        prev_w = sq_w * 0.05
        
        for s in range(7):
            dist = s * 0.28
            wave_ph = phase * 2.2 - s * 0.75 + i_arm
            # Organic side-to-side and up-down wiggling
            ripple = sq_u * np.sin(wave_ph) * 0.07 * (s + 1) + sq_w * np.cos(wave_ph * 1.1) * 0.07 * (s + 1)
            curr_center = arm_start - sq_dir * dist + ripple
            curr_w = sq_w * (0.05 * (1.0 - s/7.0))
            
            vertices.extend([prev_pt - prev_w, prev_pt + prev_w, curr_center + curr_w])
            colors.extend([maroon, maroon, maroon])
            vertices.extend([prev_pt - prev_w, curr_center + curr_w, curr_center - curr_w])
            colors.extend([maroon, maroon, maroon])
            prev_pt, prev_w = curr_center, curr_w
            
    # 2 Extra-Long Feeding Tentacles with highly emphasized 3D Clubs (12 segments, length 0.48, total length ~5.8)
    for i_tent in range(2):
        tent_ang = i_tent * np.pi + np.pi/4.0
        tent_dir = sq_u * np.cos(tent_ang) + sq_w * np.sin(tent_ang)
        tent_start = center + tent_dir * 0.18
        prev_pt = tent_start
        prev_w = sq_w * 0.04
        
        for s in range(12):
            dist = s * 0.48
            wave_ph = phase * 1.6 - s * 0.45 + i_tent * np.pi
            ripple = sq_u * np.sin(wave_ph) * 0.11 * (s + 1) + sq_w * np.cos(wave_ph * 1.1) * 0.11 * (s + 1)
            curr_center = tent_start - sq_dir * dist + ripple
            
            if s < 10:
                # Slender shaft
                curr_w = sq_w * (0.04 * (1.0 - s/11.0))
                col = maroon
            elif s == 10:
                # Expanding club start
                curr_w = sq_w * 0.14
                col = dark_maroon
            else:
                # Club tip tapering back
                curr_w = sq_w * 0.06
                col = dark_maroon
                
            vertices.extend([prev_pt - prev_w, prev_pt + prev_w, curr_center + curr_w])
            colors.extend([col, col, col])
            vertices.extend([prev_pt - prev_w, curr_center + curr_w, curr_center - curr_w])
            colors.extend([col, col, col])
            prev_pt, prev_w = curr_center, curr_w
            
    return vertices, colors
