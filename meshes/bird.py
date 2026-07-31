import numpy as np

def make_solid_bird(center, direction, phase):
    """Generates a highly realistic, detailed 3D bluebird mesh with a rounded head, slender neck, pointed yellow beak, layered flapping wings, and spread tail feathers."""
    b_dir = direction / np.linalg.norm(direction)
    if abs(b_dir[0]) < 0.9:
        b_u = np.cross(b_dir, [1.0, 0.0, 0.0])
    else:
        b_u = np.cross(b_dir, [0.0, 1.0, 0.0])
    b_u /= np.linalg.norm(b_u)
    b_w = np.cross(b_dir, b_u)
    b_w /= np.linalg.norm(b_w)
    
    vertices = []
    colors = []
    
    # Matte plumage colors (non-glowing)
    blue = [0.12, 0.38, 0.78, 1.0]         # Royal bluebird back
    orange_breast = [0.85, 0.40, 0.12, 1.0] # Warm orange breast
    white = [0.92, 0.92, 0.95, 1.0]         # Soft white belly
    dark_slate = [0.20, 0.22, 0.25, 1.0]    # Wing & tail flight feathers
    yellow_beak = [0.95, 0.72, 0.15, 1.0]   # Beak
    
    # 1. Main Body (8 rings, 12 slices)
    rings, slices = 8, 12
    body_len = 0.5
    max_rad = 0.16
    body_pts = []
    body_cols = []
    
    for r in range(rings):
        frac = r / (rings - 1)
        ring_rad = max_rad * np.sin(frac * np.pi)
        node_center = center - b_dir * (body_len * (frac - 0.4))
        
        pts = []
        ring_colors = []
        for s in range(slices):
            ang = (s / slices) * 2.0 * np.pi
            # Local position around body ring
            p = node_center + b_w * (ring_rad * np.cos(ang)) + b_u * (ring_rad * np.sin(ang) * 0.85)
            pts.append(p)
            
            # Realistic plumage color distribution
            is_dorsal = (s <= 2 or s >= 10)  # Top part of body (back)
            is_anterior = (frac < 0.6)       # Front part of body
            
            if is_dorsal:
                col = blue
            elif is_anterior:
                col = orange_breast
            else:
                col = white
            ring_colors.append(col)
            
        body_pts.append(pts)
        body_cols.append(ring_colors)
        
    for r in range(rings - 1):
        for s in range(slices):
            s_next = (s + 1) % slices
            p00, p10, p01, p11 = body_pts[r][s], body_pts[r][s_next], body_pts[r+1][s], body_pts[r+1][s_next]
            col0, col1 = body_cols[r][s], body_cols[r+1][s]
            
            vertices.extend([p00, p11, p10])
            colors.extend([col0, col1, col0])
            vertices.extend([p00, p01, p11])
            colors.extend([col0, col1, col1])
            
    # 2. Rounded Head and Slender Neck Cylinder
    # Slender neck cylinder
    neck_center_base = center + b_dir * (body_len * 0.4)
    neck_center_top = neck_center_base + b_dir * 0.14 + b_u * 0.08
    neck_rad = 0.075
    neck_pts_base, neck_pts_top = [], []
    for s in range(8):
        ang = (s / 8.0) * 2.0 * np.pi
        offset = b_w * np.cos(ang) + b_u * np.sin(ang)
        neck_pts_base.append(neck_center_base + offset * (neck_rad * 1.1))
        neck_pts_top.append(neck_center_top + offset * neck_rad)
        
    for s in range(8):
        s_next = (s + 1) % 8
        vertices.extend([neck_pts_base[s], neck_pts_top[s_next], neck_pts_base[s_next]])
        colors.extend([blue, blue, blue])
        vertices.extend([neck_pts_base[s], neck_pts_top[s], neck_pts_top[s_next]])
        colors.extend([blue, blue, blue])
        
    # Head sphere (4 rings, 8 slices)
    head_center = neck_center_top + b_dir * 0.06
    head_rad = 0.11
    head_pts = []
    for r in range(4):
        frac = r / 3.0
        h_rad = head_rad * np.sin(frac * np.pi) if r > 0 else 0.0
        h_len = head_rad * (1.0 - frac)
        h_center = head_center + b_dir * (h_len - head_rad * 0.5)
        pts = []
        for s in range(8):
            ang = (s / 8.0) * 2.0 * np.pi
            pts.append(h_center + (b_w * np.cos(ang) + b_u * np.sin(ang)) * h_rad)
        head_pts.append(pts)
        
    for r in range(3):
        for s in range(8):
            s_next = (s + 1) % 8
            p00, p10, p01, p11 = head_pts[r][s], head_pts[r][s_next], head_pts[r+1][s], head_pts[r+1][s_next]
            vertices.extend([p00, p11, p10])
            colors.extend([blue, blue, blue])
            vertices.extend([p00, p01, p11])
            colors.extend([blue, blue, blue])
            
    # 3. Pointed Yellow Beak (Pointed forward/downward cone)
    beak_base_center = head_center + b_dir * (head_rad * 0.8)
    beak_tip = beak_base_center + b_dir * 0.16 - b_u * 0.04
    beak_rad = 0.03
    beak_base_pts = []
    for s in range(slices):
        ang = (s / slices) * 2.0 * np.pi
        beak_base_pts.append(beak_base_center + (b_w * np.cos(ang) + b_u * np.sin(ang)) * beak_rad)
        
    for s in range(slices):
        s_next = (s + 1) % slices
        vertices.extend([beak_base_pts[s], beak_tip, beak_base_pts[s_next]])
        colors.extend([yellow_beak, yellow_beak, yellow_beak])
        
    # 4. Layered Dual-Joint Flapping Wings (Shoulder -> Elbow -> Tip)
    # Flapping equations with phase lags
    flap_shoulder = np.sin(phase * 12.0) * 0.42
    flap_elbow = np.sin(phase * 12.0 - 0.5) * 0.65
    
    for side, sign in [('L', 1.0), ('R', -1.0)]:
        # Joint 0: Shoulder (at the body side)
        shoulder = center - b_dir * 0.05 + b_w * (sign * 0.12) + b_u * 0.04
        
        # Joint 1: Elbow (extending outwards, flapping with shoulder angle)
        c_sh, s_sh = np.cos(flap_shoulder), np.sin(flap_shoulder)
        elbow = shoulder + b_w * (sign * 0.35 * c_sh) + b_u * (0.35 * s_sh) - b_dir * 0.04
        
        # Joint 2: Wingtip (extending further, flapping with elbow lag)
        c_el, s_el = np.cos(flap_shoulder + flap_elbow), np.sin(flap_shoulder + flap_elbow)
        wingtip = elbow + b_w * (sign * 0.45 * c_el) + b_u * (0.45 * s_el) - b_dir * 0.12
        
        # Rear wing points (trailing edges) to create 3D surface area
        shoulder_rear = shoulder - b_dir * 0.18
        elbow_rear = elbow - b_dir * 0.22
        
        # Inner Wing Panel (blue/dark slate gradient)
        vertices.extend([shoulder, elbow, elbow_rear])
        colors.extend([blue, blue, dark_slate])
        vertices.extend([shoulder, elbow_rear, shoulder_rear])
        colors.extend([blue, dark_slate, blue])
        
        # Outer Wing Panel (flight feathers)
        vertices.extend([elbow, wingtip, elbow_rear])
        colors.extend([blue, dark_slate, dark_slate])
        
        # Double-sided wing render
        vertices.extend([shoulder, elbow_rear, elbow])
        colors.extend([blue, dark_slate, blue])
        vertices.extend([shoulder, shoulder_rear, elbow_rear])
        colors.extend([blue, blue, dark_slate])
        vertices.extend([elbow, elbow_rear, wingtip])
        colors.extend([blue, dark_slate, dark_slate])
        
    # 5. Realistic Spread Tail Feathers
    tail_base = center - b_dir * (body_len * 0.6)
    tail_width = 0.18
    # Draw 3 distinct overlapping feathers spread out in a fan
    for f in [-1.0, 0.0, 1.0]:
        ang_offset = f * 0.22
        t_dir = -b_dir * np.cos(ang_offset) + b_w * np.sin(ang_offset) * tail_width
        t_tip = tail_base + t_dir * 0.42
        
        t_left = tail_base + t_dir * 0.1 - b_w * 0.03
        t_right = tail_base + t_dir * 0.1 + b_w * 0.03
        
        # Double-sided feathers
        vertices.extend([tail_base, t_tip, t_left])
        colors.extend([dark_slate, dark_slate, dark_slate])
        vertices.extend([tail_base, t_right, t_tip])
        colors.extend([dark_slate, dark_slate, dark_slate])
        
        vertices.extend([tail_base, t_left, t_tip])
        colors.extend([dark_slate, dark_slate, dark_slate])
        vertices.extend([tail_base, t_tip, t_right])
        colors.extend([dark_slate, dark_slate, dark_slate])
        
    # Scale down bluebird 3D geometry robustly to exactly 2/3 size
    scaled_vertices = [center + (v - center) * (2.0 / 3.0) for v in vertices]
    return scaled_vertices, colors
