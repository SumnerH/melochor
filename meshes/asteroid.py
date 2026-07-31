import numpy as np

def make_3d_asteroid(center, radius, phase):
    """Generates a beautifully lit solid irregular 3D rocky asteroid with deep craters, surface deformation, and shadows."""
    lats = 8
    lons = 12
    vertices = []
    colors = []
    
    def get_height_offset(theta, phi):
        h = np.sin(theta * 4.0) * np.cos(phi * 4.0) * 0.18
        h += np.sin(theta * 11.0 + phi * 9.0) * 0.06
        dist_to_crater1 = np.sin(theta * 3.0 - phi * 2.0)
        if dist_to_crater1 > 0.7:
            h -= 0.25
        dist_to_crater2 = np.cos(theta * 2.0 + phi * 4.0)
        if dist_to_crater2 > 0.75:
            h -= 0.20
        return h

    L = np.array([0.7, 0.6, -0.4], dtype=np.float32)
    L /= np.linalg.norm(L)

    def get_asteroid_vertex(lat, lon):
        nx = np.cos(lat) * np.cos(lon)
        ny = np.cos(lat) * np.sin(lon)
        nz = np.sin(lat)
        norm = np.array([nx, ny, nz], dtype=np.float32)
        
        h = get_height_offset(lat, lon)
        r = radius * (1.0 + h)
        p = center + norm * r
        
        base_col = np.array([0.38, 0.38, 0.40, 1.0], dtype=np.float32) if h > -0.05 else np.array([0.22, 0.22, 0.24, 1.0], dtype=np.float32)
        dot = np.dot(norm, L)
        shade = 0.18 + 0.82 * max(0.0, dot)
        col = [np.clip(base_col[0] * shade, 0.0, 1.0),
               np.clip(base_col[1] * shade, 0.0, 1.0),
               np.clip(base_col[2] * shade, 0.0, 1.0),
               1.0]
        return p, col

    for i in range(lats):
        lat0 = -np.pi/2.0 + (i / lats) * np.pi
        lat1 = -np.pi/2.0 + ((i + 1) / lats) * np.pi
        
        for j in range(lons):
            lon0 = (j / lons) * 2.0 * np.pi + phase
            lon1 = ((j + 1) / lons) * 2.0 * np.pi + phase
            
            p00, c00 = get_asteroid_vertex(lat0, lon0)
            p10, c10 = get_asteroid_vertex(lat1, lon0)
            p01, c01 = get_asteroid_vertex(lat0, lon1)
            p11, c11 = get_asteroid_vertex(lat1, lon1)
            
            vertices.extend([p00, p10, p11])
            colors.extend([c00, c10, c11])
            vertices.extend([p00, p11, p01])
            colors.extend([c00, c11, c01])
            
    return vertices, colors
