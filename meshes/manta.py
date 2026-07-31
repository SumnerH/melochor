import numpy as np

def make_solid_manta(center, direction, phase):
    """Generates a high-poly smooth solid manta ray (dark matte slate dorsal, off-white ventral) swimming horizontally, flapping wings vertically with realistic lighting."""
    m_dir = direction / np.linalg.norm(direction)
    
    # Wings span horizontally, perpendicular to flight direction and world vertical
    if abs(m_dir[1]) > 0.95:
        m_w = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    else:
        m_w = np.cross(m_dir, [0.0, 1.0, 0.0])
        m_w /= np.linalg.norm(m_w)
        
    # Local up vector is perpendicular to wing span and flight direction
    m_u = np.cross(m_w, m_dir)
    m_u /= np.linalg.norm(m_u)
    
    vertices = []
    colors = []
    
    dorsal_col = [0.11, 0.12, 0.13, 1.0]  # Matte dark slate/black
    ventral_col = [0.88, 0.88, 0.90, 1.0] # Opaque off-white
    
    u_steps, w_steps = 11, 14
    top_grid, bot_grid = {}, {}
    u_vals = np.linspace(-1.2, 1.2, u_steps)
    w_vals = np.linspace(-2.2, 2.2, w_steps)
    
    for i_u, u_local in enumerate(u_vals):
        wing_span = 2.2 * (1.0 - abs(u_local) / 1.2)
        for i_w, w_local in enumerate(w_vals):
            if abs(w_local) > wing_span:
                continue
            
            # Elegant wave-like wing flap propagation
            y_flap = np.sin(phase - abs(w_local) * 1.4 + u_local * 0.25) * 0.55 * (abs(w_local) / 2.2)
            sweep_back = -0.38 * (abs(w_local) / 2.2) ** 1.8
            u_swept = u_local + sweep_back
            bend_down = -0.15 * (abs(w_local) / 2.2) ** 2
            
            thickness = 0.15 * (1.0 - abs(w_local) / max(0.1, wing_span)) * (1.0 - (u_local/1.2)**2)
            thickness = max(0.005, thickness)
            
            p_c = center + m_dir * u_swept + m_w * w_local + m_u * (y_flap + bend_down)
            top_grid[(i_u, i_w)] = p_c + m_u * thickness
            bot_grid[(i_u, i_w)] = p_c - m_u * thickness
            
    # Light source
    L = np.array([0.7, 0.6, -0.4], dtype=np.float32)
    L /= np.linalg.norm(L)
    
    def add_shaded_triangle(p0, p1, p2, base_col):
        v1 = p1 - p0
        v2 = p2 - p0
        cross = np.cross(v1, v2)
        norm_val = np.linalg.norm(cross)
        n = cross / norm_val if norm_val > 1e-6 else m_u
        
        dot = np.dot(n, L)
        shade = 0.22 + 0.78 * max(0.0, dot)
        col = [np.clip(base_col[0] * shade, 0.0, 1.0),
               np.clip(base_col[1] * shade, 0.0, 1.0),
               np.clip(base_col[2] * shade, 0.0, 1.0),
               base_col[3]]
        vertices.extend([p0, p1, p2])
        colors.extend([col, col, col])

    # Stitch grids
    for i_u in range(u_steps - 1):
        for i_w in range(w_steps - 1):
            idx00, idx10, idx01, idx11 = (i_u, i_w), (i_u + 1, i_w), (i_u, i_w + 1), (i_u + 1, i_w + 1)
            if idx00 in top_grid and idx10 in top_grid and idx01 in top_grid and idx11 in top_grid:
                add_shaded_triangle(top_grid[idx00], top_grid[idx11], top_grid[idx10], dorsal_col)
                add_shaded_triangle(top_grid[idx00], top_grid[idx01], top_grid[idx11], dorsal_col)
                add_shaded_triangle(bot_grid[idx00], bot_grid[idx10], bot_grid[idx11], ventral_col)
                add_shaded_triangle(bot_grid[idx00], bot_grid[idx11], bot_grid[idx01], ventral_col)
                
                for neighbor, is_border_check in [((i_u, i_w + 1), (i_u + 1, i_w + 1)), ((i_u, i_w - 1), (i_u + 1, i_w - 1))]:
                    if neighbor not in top_grid or is_border_check not in top_grid:
                        p0_t, p1_t = top_grid[idx00], top_grid[idx10]
                        p0_b, p1_b = bot_grid[idx00], bot_grid[idx10]
                        add_shaded_triangle(p0_t, p1_b, p1_t, dorsal_col)
                        add_shaded_triangle(p0_t, p0_b, p1_b, ventral_col)
                        
    # Cephalic Horns
    front_u_idx = u_steps - 1
    front_w_center = w_steps // 2
    for side in [-1, 1]:
        w_idx = front_w_center + side * 1
        if (front_u_idx, w_idx) in top_grid:
            p_base_t = top_grid[(front_u_idx, w_idx)]
            p_base_b = bot_grid[(front_u_idx, w_idx)]
            prev_t, prev_b = p_base_t, p_base_b
            for seg in range(3):
                frac = (seg + 1) / 3.0
                curl_fwd = 0.15 * frac
                curl_in = -side * 0.08 * (frac ** 1.5)
                curl_dn = -0.05 * frac
                
                curr_t = p_base_t + m_dir * curl_fwd + m_w * curl_in + m_u * curl_dn
                curr_b = p_base_b + m_dir * curl_fwd + m_w * curl_in + m_u * curl_dn
                add_shaded_triangle(prev_t, curr_b, curr_t, dorsal_col)
                add_shaded_triangle(prev_t, prev_b, curr_b, ventral_col)
                prev_t, prev_b = curr_t, curr_b
                
    # Whip tail
    back_u_idx, back_w_idx = 0, w_steps // 2
    if (back_u_idx, back_w_idx) in top_grid:
        prev_pt = (top_grid[(back_u_idx, back_w_idx)] + bot_grid[(back_u_idx, back_w_idx)]) * 0.5
        tail_segments = 16
        for t_idx in range(tail_segments):
            t_frac = t_idx / (tail_segments - 1)
            p_curr = prev_pt + m_dir * (-0.12 - t_frac * 3.2) + m_u * (np.sin(phase - t_frac * 5.0) * 0.12)
            thickness = 0.02 * (1.0 - t_frac)
            thickness = max(0.003, thickness)
            p0_p, p1_p = prev_pt - m_w * thickness, prev_pt + m_w * thickness
            p0_c, p1_c = p_curr - m_w * thickness, p_curr + m_w * thickness
            add_shaded_triangle(p0_p, p1_p, p1_c, dorsal_col)
            add_shaded_triangle(p0_p, p1_c, p0_c, dorsal_col)
            prev_pt = p_curr
            
    return vertices, colors
