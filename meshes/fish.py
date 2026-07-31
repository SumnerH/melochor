import numpy as np

def make_solid_fish(center, direction, phase, color):
    """Generates a small solid 3D fish with a flapping tail and glowing lantern antenna tip."""
    f_dir = direction / np.linalg.norm(direction)
    if abs(f_dir[0]) < 0.9:
        f_u = np.cross(f_dir, [1.0, 0.0, 0.0])
    else:
        f_u = np.cross(f_dir, [0.0, 1.0, 0.0])
    f_u /= np.linalg.norm(f_u)
    f_w = np.cross(f_dir, f_u)
    f_w /= np.linalg.norm(f_w)
    
    vertices = []
    colors = []
    
    rings, slices = 6, 8
    fish_len, max_rad = 0.42, 0.12
    ring_pts = []
    
    for r in range(rings):
        frac = r / (rings - 1)
        ring_rad = max_rad * np.sin(frac * np.pi)
        wag = np.sin(phase * 12.0 - r * 0.8) * 0.07 * (r - 2) if r >= 3 else 0.0
        node_center = center + f_dir * (fish_len * (0.5 - frac)) + f_w * wag
        
        pts = []
        for s in range(slices):
            ang = (s / slices) * 2.0 * np.pi
            pts.append(node_center + f_u * (ring_rad * np.cos(ang) * 1.3) + f_w * (ring_rad * np.sin(ang)))
        ring_pts.append(pts)
        
    # Stitch rings
    for r in range(rings - 1):
        for s in range(slices):
            s_next = (s + 1) % slices
            p00, p10, p01, p11 = ring_pts[r][s], ring_pts[r][s_next], ring_pts[r+1][s], ring_pts[r+1][s_next]
            vertices.extend([p00, p11, p10])
            colors.extend([color, color, color])
            vertices.extend([p00, p01, p11])
            colors.extend([color, color, color])
            
    # Tail Fin
    tail_center = np.mean(ring_pts[-1], axis=0)
    tail_t, tail_b = tail_center - f_dir * 0.18 + f_u * 0.12 + f_w * np.sin(phase*12.0 - 5.0)*0.18, tail_center - f_dir * 0.18 - f_u * 0.12 + f_w * np.sin(phase*12.0 - 5.0)*0.18
    vertices.extend([tail_center, tail_t, tail_b])
    colors.extend([color, color, color])
    vertices.extend([tail_center, tail_b, tail_t])
    colors.extend([color, color, color])
    
    # Lantern Antenna and Glowing Bulb
    head_center = np.mean(ring_pts[0], axis=0)
    bulb_center = head_center + f_u * 0.22 + f_dir * 0.22
    bulb_col = [1.0, 0.95, 0.1, 1.0]
    bd, bu, bw = f_dir * 0.02, f_u * 0.02, f_w * 0.02
    pts_bulb = [bulb_center + bd, bulb_center - bd, bulb_center + bu, bulb_center - bu, bulb_center + bw, bulb_center - bw]
    for t0, t1, t2 in [(0, 2, 4), (0, 4, 3), (0, 3, 5), (0, 5, 2), (1, 2, 5), (1, 5, 3), (1, 3, 4), (1, 4, 2)]:
        vertices.extend([pts_bulb[t0], pts_bulb[t1], pts_bulb[t2]])
        colors.extend([bulb_col, bulb_col, bulb_col])
        
    return vertices, colors
