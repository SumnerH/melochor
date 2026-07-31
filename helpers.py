import numpy as np
import datetime
from constants import NEON_PALETTE, TRANQUIL_PALETTE, METAL_PALETTE

def get_palette_colors(mode):
    if mode == 'NEON':
        return NEON_PALETTE
    elif mode == 'TRANQUIL':
        return TRANQUIL_PALETTE
    elif mode == 'METAL':
        return METAL_PALETTE
    return None

def perspective_matrix(fovy, aspect, znear, zfar):
    f = 1.0 / np.tan(fovy * np.pi / 360.0)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = -(zfar + znear) / (zfar - znear)
    m[2, 3] = -(2.0 * zfar * znear) / (zfar - znear)
    m[3, 2] = -1.0
    return m

def look_at_matrix(eye, center, up):
    eye = np.array(eye, dtype=np.float32)
    center = np.array(center, dtype=np.float32)
    up = np.array(up, dtype=np.float32)
    
    f = center - eye
    f /= np.linalg.norm(f)
    
    s = np.cross(f, up)
    s_norm = np.linalg.norm(s)
    if s_norm < 1e-6:
        s = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    else:
        s /= s_norm
        
    u = np.cross(s, f)
    u /= np.linalg.norm(u)
    
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = s[0]
    m[0, 1] = s[1]
    m[0, 2] = s[2]
    m[0, 3] = -np.dot(s, eye)
    
    m[1, 0] = u[0]
    m[1, 1] = u[1]
    m[1, 2] = u[2]
    m[1, 3] = -np.dot(u, eye)
    
    m[2, 0] = -f[0]
    m[2, 1] = -f[1]
    m[2, 2] = -f[2]
    m[2, 3] = np.dot(f, eye)
    
    return m

def get_meeus_moon_phase():
    """
    Calculates the Moon's phase fraction (0.0 to 1.0, where 0=New, 0.5=Crescent/Quarter, 1=Full)
    and whether it is waning (True/False) using Jean Meeus' high-precision series.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # 1. Calculate Julian Date (JD)
    y = now.year
    m = now.month
    d = now.day + (now.hour + now.minute/60.0 + now.second/3600.0) / 24.0
    
    if m <= 2:
        y -= 1
        m += 12
        
    A = int(y / 100)
    B = 2 - A + int(A / 4)
    
    JD = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + B - 1524.5
    
    # 2. Meeus astronomical series variables
    # T = Julian centuries since J2000.0
    T = (JD - 2451545.0) / 36525.0
    
    # Mean elongation of the Moon (D)
    D = 297.8501921 + 445267.1114034 * T - 0.0018819 * T**2 + (T**3) / 113065.0 - (T**4) / 30739000.0
    # Mean anomaly of the Sun (M)
    M = 357.5291092 + 35999.0502909 * T - 0.0001536 * T**2 + (T**3) / 24490000.0
    # Mean anomaly of the Moon (M')
    Mp = 134.9633964 + 477198.8675055 * T + 0.0087414 * T**2 + (T**3) / 69699.0 - (T**4) / 14712000.0
    
    # Convert to radians
    D_rad = np.radians(D % 360)
    M_rad = np.radians(M % 360)
    Mp_rad = np.radians(Mp % 360)
    
    # Approximate phase angle (i) from Chapter 48
    i = 180.0 - (D % 360) - 6.289 * np.sin(Mp_rad) + 2.100 * np.sin(M_rad) - 1.274 * np.sin(2*D_rad - Mp_rad) - 0.658 * np.sin(2*D_rad) - 0.214 * np.sin(2*Mp_rad) - 0.110 * np.sin(D_rad)
    i_rad = np.radians(i % 360)
    
    # Illuminated fraction k
    k = (1.0 + np.cos(i_rad)) / 2.0
    
    # Is waning?
    # Elongation D % 360:
    # 0 to 180 degrees: Waxing
    # 180 to 360 degrees: Waning
    is_waning = (D % 360) > 180.0
    
    return float(k), bool(is_waning)
