import numpy as np

def get_gas_giant_color(lat, lon, phase, style):
    # Simplify waves: reduce perturbation for a smoother, elegant gas giant look
    perturb = np.sin(lat * 6.0 + phase) * 0.06 + np.sin(lon * 4.0 - phase * 1.2) * 0.03
    y_band = lat + perturb
    band_val = 0.5 + 0.5 * np.sin(y_band * 10.0)
    band_val += 0.08 * np.cos(y_band * 24.0)
    band_val = np.clip(band_val, 0.0, 1.0)

    # Low contrast, subtle Neptune-esque banding for all style options
    if style == "NEPTUNE":
        col0 = np.array([0.05, 0.12, 0.38, 1.0]) # Deep cobalt blue
        col1 = np.array([0.08, 0.18, 0.50, 1.0]) # Royal blue
        col2 = np.array([0.12, 0.25, 0.62, 1.0]) # Sapphire/cyan blue
    elif style == "JUPITER":
        col0 = np.array([0.42, 0.22, 0.14, 1.0]) # Deep terracotta reddish-brown
        col1 = np.array([0.46, 0.26, 0.18, 1.0]) # Muted copper/bronze
        col2 = np.array([0.50, 0.30, 0.22, 1.0]) # Soft warm tan
    elif style == "GREEN":
        col0 = np.array([0.02, 0.22, 0.14, 1.0]) # Deep pine green
        col1 = np.array([0.04, 0.26, 0.18, 1.0]) # Rich emerald green
        col2 = np.array([0.06, 0.32, 0.24, 1.0]) # Dark tealy seafoam
    elif style == "GREEN_YELLOW":
        col0 = np.array([0.18, 0.24, 0.08, 1.0]) # Deep olive green
        col1 = np.array([0.22, 0.28, 0.10, 1.0]) # Golden moss
        col2 = np.array([0.26, 0.32, 0.12, 1.0]) # Subtle warm chartreuse
    else: # ORANGE style
        col0 = np.array([0.40, 0.18, 0.06, 1.0]) # Deep mahogany orange
        col1 = np.array([0.44, 0.22, 0.08, 1.0]) # Rich dark amber
        col2 = np.array([0.48, 0.26, 0.12, 1.0]) # Soft subtle peach

    if band_val < 0.45:
        frac = band_val / 0.45
        base_col = col0 * (1.0 - frac) + col1 * frac
    else:
        frac = (band_val - 0.45) / 0.55
        base_col = col1 * (1.0 - frac) + col2 * frac

    return base_col


def make_rocky_planet(center, radius, phase, style="JUPITER"):
    """Generates a beautifully lit, shaded smooth solid gas giant spherical mesh (latitude-longitude grid) with dynamic cloud-banding wave patterns."""
    lats = 24
    lons = 36
    vertices = []
    colors = []
    
    L = np.array([0.7, 0.6, -0.4], dtype=np.float32)
    L /= np.linalg.norm(L)
    
    def get_vertex_data(lat, lon):
        nx = np.cos(lat) * np.cos(lon)
        ny = np.sin(lat)
        nz = np.cos(lat) * np.sin(lon)
        norm = np.array([nx, ny, nz], dtype=np.float32)
        
        p = center + norm * radius
        base_col = get_gas_giant_color(lat, lon, phase, style)
        
        dot = np.dot(norm, L)
        shade = 0.16 + 0.84 * max(0.0, dot)
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
            
            p00, c00 = get_vertex_data(lat0, lon0)
            p10, c10 = get_vertex_data(lat1, lon0)
            p01, c01 = get_vertex_data(lat0, lon1)
            p11, c11 = get_vertex_data(lat1, lon1)
            
            vertices.extend([p00, p10, p11])
            colors.extend([c00, c10, c11])
            vertices.extend([p00, p11, p01])
            colors.extend([c00, c11, c01])
            
    return vertices, colors
