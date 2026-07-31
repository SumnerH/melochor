import numpy as np

def make_solid_butterfly(center, direction, phase):
    """Generates a highly realistic 3D Monarch butterfly with a detailed segmented body, curling antennae, and 4 high-resolution wings (large curved forewings, rounded hindwings) featuring matte orange centers and thick black borders."""
    bf_dir = direction / np.linalg.norm(direction)
    if abs(bf_dir[0]) < 0.9:
        bf_u = np.cross(bf_dir, [1.0, 0.0, 0.0])
    else:
        bf_u = np.cross(bf_dir, [0.0, 1.0, 0.0])
    bf_u /= np.linalg.norm(bf_u)
    bf_w = np.cross(bf_dir, bf_u)
    bf_w /= np.linalg.norm(bf_w)
    
    vertices = []
    colors = []
    
    # Matte colors (non-glowing)
    black = [0.03, 0.03, 0.03, 1.0]
    orange = [0.95, 0.38, 0.02, 1.0]
    
    # 1. Segmented Body (Head, Thorax, Abdomen)
    body_rings = 9
    body_slices = 8
    body_len = 0.32
    body_pts = []
    for r in range(body_rings):
        frac = r / (body_rings - 1)
        # Abdomen, Thorax, Head thickness profile
        if frac < 0.15:
            b_rad = 0.02 * (frac / 0.15) # Head tip
        elif frac < 0.35:
            b_rad = 0.035 # Thorax
        else:
            b_rad = 0.026 * (1.0 - (frac - 0.35) / 0.65) # Abdomen tapering
            
        b_rad = max(0.005, b_rad)
        node_center = center + bf_dir * (body_len * (0.5 - frac))
        pts = []
        for s in range(body_slices):
            ang = (s / body_slices) * 2.0 * np.pi
            pts.append(node_center + (bf_w * np.cos(ang) + bf_u * np.sin(ang)) * b_rad)
        body_pts.append(pts)
        
    for r in range(body_rings - 1):
        for s in range(body_slices):
            s_next = (s + 1) % body_slices
            p00, p10, p01, p11 = body_pts[r][s], body_pts[r][s_next], body_pts[r+1][s], body_pts[r+1][s_next]
            vertices.extend([p00, p11, p10])
            colors.extend([black, black, black])
            vertices.extend([p00, p01, p11])
            colors.extend([black, black, black])
            
    # Thin Curling Antennae (two antennae curling forward-outwards from head)
    for side in [-1.0, 1.0]:
        a_start = center + bf_dir * 0.16 + bf_w * (side * 0.015) + bf_u * 0.01
        prev_pt = a_start
        for seg in range(4):
            frac = (seg + 1) / 4.0
            # Curl forward, outward, and slightly upward
            offset_fwd = 0.12 * frac
            offset_out = side * 0.06 * (frac ** 1.8)
            offset_up = 0.03 * np.sin(frac * np.pi * 0.5)
            curr_pt = a_start + bf_dir * offset_fwd + bf_w * offset_out + bf_u * offset_up
            
            # Simple line thickness quad
            p0_p, p1_p = prev_pt - bf_w * 0.003, prev_pt + bf_w * 0.003
            p0_c, p1_c = curr_pt - bf_w * 0.003, curr_pt + bf_w * 0.003
            vertices.extend([p0_p, p1_p, p1_c])
            colors.extend([black, black, black])
            vertices.extend([p0_p, p1_c, p0_c])
            colors.extend([black, black, black])
            prev_pt = curr_pt
            
    # 2. Layered Forewings and Hindwings
    # Flapping wing angle
    flap_ang = np.sin(phase * 16.0) * 0.65
    cos_f, sin_f = np.cos(flap_ang), np.sin(flap_ang)
    
    for sign in [1.0, -1.0]:
        # Local wing axes (sweeping upward as they flap)
        w_local = bf_w * (sign * cos_f) + bf_u * sin_f
        dir_local = bf_dir
        
        # Wing root is at the thorax
        root = center + bf_dir * 0.04
        
        # --- FOREWING (Large, curved) ---
        pA = root + dir_local * 0.15 + w_local * 0.12
        pB = root + dir_local * 0.22 + w_local * 0.58
        pC = root - dir_local * 0.12 + w_local * 0.50
        pD = root - dir_local * 0.15 + w_local * 0.18
        
        # Orange Interior
        p_mid = root + w_local * 0.12
        vertices.extend([root, p_mid, pA])
        colors.extend([orange, orange, orange])
        vertices.extend([p_mid, pC, pB])
        colors.extend([orange, orange, orange])
        vertices.extend([p_mid, pB, pA])
        colors.extend([orange, orange, orange])
        vertices.extend([root, pD, p_mid])
        colors.extend([orange, orange, orange])
        vertices.extend([p_mid, pD, pC])
        colors.extend([orange, orange, orange])
        
        # Thick Black Outer Borders
        p_border_tip = pB + w_local * 0.05 + dir_local * 0.02
        p_border_mid = pC + w_local * 0.04 - dir_local * 0.03
        
        vertices.extend([pA, p_border_tip, pB])
        colors.extend([black, black, black])
        vertices.extend([pB, p_border_tip, p_border_mid])
        colors.extend([black, black, black])
        vertices.extend([pB, p_border_mid, pC])
        colors.extend([black, black, black])
        vertices.extend([pC, p_border_mid, pD])
        colors.extend([black, black, black])
        
        # Double-sided forewing
        vertices.extend([root, pA, p_mid])
        colors.extend([orange, orange, orange])
        vertices.extend([p_mid, pB, pC])
        colors.extend([orange, orange, orange])
        vertices.extend([p_mid, pA, pB])
        colors.extend([orange, orange, orange])
        vertices.extend([root, p_mid, pD])
        colors.extend([orange, orange, orange])
        vertices.extend([p_mid, pC, pD])
        colors.extend([orange, orange, orange])
        
        vertices.extend([pA, pB, p_border_tip])
        colors.extend([black, black, black])
        vertices.extend([pB, p_border_mid, p_border_tip])
        colors.extend([black, black, black])
        vertices.extend([pB, pC, p_border_mid])
        colors.extend([black, black, black])
        vertices.extend([pC, p_D if 'p_D' in locals() else pD, p_border_mid])
        colors.extend([black, black, black])
        
        # --- HINDWING (Smaller, rounded) ---
        root_h = center - bf_dir * 0.04
        pH_A = root_h + dir_local * 0.02 + w_local * 0.22
        pH_B = root_h - dir_local * 0.15 + w_local * 0.42
        pH_C = root_h - dir_local * 0.35 + w_local * 0.32
        pH_D = root_h - dir_local * 0.28 + w_local * 0.10
        
        # Orange Interior
        pH_mid = root_h - dir_local * 0.12 + w_local * 0.15
        vertices.extend([root_h, pH_mid, pH_A])
        colors.extend([orange, orange, orange])
        vertices.extend([pH_mid, pH_B, pH_A])
        colors.extend([orange, orange, orange])
        vertices.extend([pH_mid, pH_C, pH_B])
        colors.extend([orange, orange, orange])
        vertices.extend([root_h, pH_D, pH_mid])
        colors.extend([orange, orange, orange])
        vertices.extend([pH_mid, pH_D, pH_C])
        colors.extend([orange, orange, orange])
        
        # Black border for hindwing
        pH_border_outer = pH_B + w_local * 0.04 - dir_local * 0.02
        pH_border_rear = pH_C + w_local * 0.02 - dir_local * 0.04
        
        vertices.extend([pH_A, pH_border_outer, pH_B])
        colors.extend([black, black, black])
        vertices.extend([pH_B, pH_border_outer, pH_border_rear])
        colors.extend([black, black, black])
        vertices.extend([pH_B, pH_border_rear, pH_C])
        colors.extend([black, black, black])
        vertices.extend([pH_C, pH_border_rear, pH_D])
        colors.extend([black, black, black])
        
        # Double-sided hindwing
        vertices.extend([root_h, pH_A, pH_mid])
        colors.extend([orange, orange, orange])
        vertices.extend([pH_mid, pH_A, pH_B])
        colors.extend([orange, orange, orange])
        vertices.extend([pH_mid, pH_B, pH_C])
        colors.extend([orange, orange, orange])
        vertices.extend([root_h, pH_mid, pH_D])
        colors.extend([orange, orange, orange])
        vertices.extend([pH_mid, pH_C, pH_D])
        colors.extend([orange, orange, orange])
        
        vertices.extend([pH_A, pH_B, pH_border_outer])
        colors.extend([black, black, black])
        vertices.extend([pH_B, pH_border_rear, pH_border_outer])
        colors.extend([black, black, black])
        vertices.extend([pH_B, pH_C, pH_border_rear])
        colors.extend([black, black, black])
        vertices.extend([pH_C, pH_D, pH_border_rear])
        colors.extend([black, black, black])
        
    return vertices, colors
