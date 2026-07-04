import sys
import time
import random
import ctypes
import numpy as np

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk, GObject

import OpenGL.GL as gl
import OpenGL.contextdata
# Bypass PyOpenGL GLX/EGL detection mismatch by mocking context getter
OpenGL.contextdata.getContext = lambda context=None: 1

# Vibrant emission spectra colors corresponding to real-world metal salts
COLORS = {
    "strontium_red": (1.0, 0.15, 0.1, 1.0),
    "barium_green": (0.1, 1.0, 0.25, 1.0),
    "copper_blue": (0.15, 0.45, 1.0, 1.0),
    "sodium_gold": (1.0, 0.65, 0.05, 1.0),
    "calcium_orange": (1.0, 0.35, 0.05, 1.0),
    "potassium_purple": (0.85, 0.1, 1.0, 1.0),
    "magnesium_white": (0.95, 0.95, 1.0, 1.0)
}

COLOR_LIST = list(COLORS.values())

# Modern CPU-side matrix helper functions
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

# Modern Shader Sources (GLSL ES 3.00)
SKY_VERTEX_SHADER = """#version 300 es
layout (location = 0) in vec2 aPos;
out vec2 vPos;
void main() {
    vPos = aPos;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

SKY_FRAGMENT_SHADER = """#version 300 es
precision mediump float;
in vec2 vPos;
out vec4 FragColor;
void main() {
    float t = (vPos.y + 1.0) * 0.5;
    vec3 col_bottom = vec3(0.005, 0.005, 0.04);
    vec3 col_top = vec3(0.0, 0.0, 0.005);
    FragColor = vec4(mix(col_bottom, col_top, t), 1.0);
}
"""

LINE_VERTEX_SHADER = """#version 300 es
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec4 aColor;
out vec4 vColor;
uniform mat4 projection;
uniform mat4 view;
void main() {
    vColor = aColor;
    gl_Position = projection * view * vec4(aPos, 1.0);
}
"""

LINE_FRAGMENT_SHADER = """#version 300 es
precision mediump float;
in vec4 vColor;
out vec4 FragColor;
void main() {
    FragColor = vColor;
}
"""

PARTICLE_VERTEX_SHADER = """#version 300 es
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec4 aColor;
layout (location = 2) in float aSize;

out vec4 vColor;
out float vRand;

uniform mat4 projection;
uniform mat4 view;

// High quality GPU hash function to generate a stable random seed [0, 1] per particle
float hash3(vec3 p) {
    return fract(sin(dot(p, vec3(12.9898, 78.233, 45.164))) * 43758.5453123);
}

void main() {
    vColor = aColor;
    vRand = hash3(aPos);
    
    vec4 mvPos = view * vec4(aPos, 1.0);
    gl_Position = projection * mvPos;
    float dist = max(0.1, -mvPos.z);
    // Slightly scale up to compensate for organic star profile bounds
    gl_PointSize = aSize * (42.0 / dist);
}
"""

PARTICLE_FRAGMENT_SHADER = """#version 300 es
precision mediump float;
in vec4 vColor;
in float vRand;
out vec4 FragColor;

// Simple 2D hash for micro-turbulent edge burning noise
float hash2(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

void main() {
    vec2 coord = gl_PointCoord - vec2(0.5);
    float r = length(coord);
    if (r > 0.5) {
        discard;
    }
    
    // Convert to polar coordinates
    float theta = atan(coord.y, coord.x);
    
    // 1. Multi-pointed organic flare shape
    float spikes = 4.0 + floor(vRand * 4.0); // Randomly 4, 5, 6, or 7 pointed spark
    float rotation = vRand * 6.28318;        // Random rotation
    
    float flare1 = cos(theta * spikes + rotation);
    float flare2 = sin(theta * (spikes + 2.0) - rotation * 1.5);
    float flare_profile = 0.35 + 0.15 * flare1 + 0.05 * flare2;
    
    // High-frequency turbulent edge noise
    float edge_noise = hash2(coord * (10.0 + vRand * 50.0)) * 0.07;
    float max_r = flare_profile - edge_noise;
    
    if (r > max_r) {
        discard;
    }
    
    // 2. Compute bright white core intensity (highest at center)
    float t = r / max_r;
    float core = pow(1.0 - t, 4.0);
    
    // Main alpha falloff
    float alpha = pow(1.0 - t, 1.5) * vColor.a;
    
    // Blend chemical color with incandescent white-hot core
    vec3 spark_color = mix(vColor.rgb, vec3(1.0, 1.0, 0.95), core * 0.85);
    spark_color += vec3(core * 0.40); // extra bright glow boost
    
    FragColor = vec4(spark_color, alpha);
}
"""

def compile_shader(shader_type, source):
    shader = gl.glCreateShader(shader_type)
    gl.glShaderSource(shader, source)
    gl.glCompileShader(shader)
    status = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)
    if not status:
        error = gl.glGetShaderInfoLog(shader).decode()
        gl.glDeleteShader(shader)
        raise RuntimeError(f"Shader compilation failed: {error}")
    return shader

def create_program(vertex_source, fragment_source):
    vs = compile_shader(gl.GL_VERTEX_SHADER, vertex_source)
    fs = compile_shader(gl.GL_FRAGMENT_SHADER, fragment_source)
    program = gl.glCreateProgram()
    gl.glAttachShader(program, vs)
    gl.glAttachShader(program, fs)
    gl.glLinkProgram(program)
    gl.glDeleteShader(vs)
    gl.glDeleteShader(fs)
    status = gl.glGetProgramiv(program, gl.GL_LINK_STATUS)
    if not status:
        error = gl.glGetProgramInfoLog(program).decode()
        gl.glDeleteProgram(program)
        raise RuntimeError(f"Program linking failed: {error}")
    return program

class Firework:
    def __init__(self, fw_type=None, color=None, x_offset=None):
        self.type = random.randint(0, 18) if fw_type is None else fw_type
        self.color = random.choice(COLOR_LIST) if color is None else color
        self.secondary_color = random.choice(COLOR_LIST)
        
        self.state = 'LAUNCH'
        
        if x_offset is None:
            x_offset = random.uniform(-10.0, 10.0)
        self.launch_pos = np.array([x_offset, -12.0, random.uniform(-6.0, 6.0)], dtype=np.float32)
        self.launch_vel = np.array([
            random.uniform(-2.0, 2.0),
            random.uniform(22.0, 27.0),
            random.uniform(-2.0, 2.0)
        ], dtype=np.float32)
        
        self.launch_age = 0.0
        self.launch_fuse = random.uniform(1.3, 1.6)
        
        self.launch_trail = []
        self.launch_trail_max = 15

        self.stage = 1  # Multi-stage track (e.g., Crossette stage 1 vs 2)

        self.positions = None
        self.velocities = None
        self.colors = None
        self.ages = None
        self.max_ages = None
        self.history = None
        self.history_len = 0
        self.drag = 1.0
        self.star_size = 8.0
        self.gravity = 5.0
        
    def explode(self):
        self.state = 'EXPLODE'
        
        if self.type == 0:  # Peony
            num_particles = random.randint(500, 700)
            self.drag = 1.6
            self.history_len = 2
            min_life, max_life = 1.0, 1.6
        elif self.type == 1:  # Chrysanthemum
            num_particles = random.randint(600, 800)
            self.drag = 1.1
            self.history_len = 6
            min_life, max_life = 1.2, 1.8
        elif self.type == 2:  # Willow
            num_particles = random.randint(400, 600)
            self.drag = 0.45
            self.history_len = 10
            min_life, max_life = 2.4, 3.4
            if random.random() < 0.7:
                self.color = COLORS["sodium_gold"]
                self.secondary_color = COLORS["calcium_orange"]
        elif self.type == 3:  # Ghost Ring
            num_particles = random.randint(400, 500)
            self.drag = 1.3
            self.history_len = 4
            min_life, max_life = 1.2, 1.7
        elif self.type == 4:  # Pistil / Double Shell
            num_particles = random.randint(700, 900)
            self.drag = 1.3
            self.history_len = 5
            min_life, max_life = 1.3, 1.9
        elif self.type == 5:  # Waterfall / Horsetail
            num_particles = random.randint(350, 500)
            self.drag = 0.35
            self.history_len = 12
            min_life, max_life = 2.8, 3.8
            self.color = COLORS["sodium_gold"] if random.random() < 0.8 else COLORS["strontium_red"]
            self.secondary_color = COLORS["calcium_orange"]
        elif self.type == 6:  # Swarm / Bees / Fish
            num_particles = random.randint(180, 260)
            self.drag = 0.4
            self.history_len = 8
            min_life, max_life = 1.8, 2.5
        elif self.type == 7:  # Saturn Ring (Sphere + Outer Ring)
            num_particles = random.randint(700, 900)
            self.drag = 1.2
            self.history_len = 5
            min_life, max_life = 1.4, 2.0
        elif self.type == 8:  # Crossette (2-Stage Splitting Break)
            num_particles = 120  # Keep starting size modest so splitting doesn't overload
            self.drag = 1.0
            self.history_len = 5
            min_life, max_life = 1.4, 1.8
        elif self.type == 9:  # Rainbow Bouquet (Multicolored)
            num_particles = random.randint(750, 950)
            self.drag = 1.2
            self.history_len = 4
            min_life, max_life = 1.3, 1.9
        elif self.type == 10:  # Multi-Stage Ring
            num_particles = 150
            self.drag = 1.3
            self.history_len = 4
            min_life, max_life = 1.3, 1.7
        elif self.type == 11:  # Dahlia
            num_particles = random.randint(80, 110)
            self.drag = 0.75
            self.history_len = 8
            min_life, max_life = 1.5, 2.2
            self.star_size = 14.0
        elif self.type == 12:  # Diadem / Crown
            num_particles = random.randint(600, 800)
            self.drag = 1.1
            self.history_len = 8
            min_life, max_life = 1.6, 2.4
            self.color = COLORS["sodium_gold"]
        elif self.type == 13:  # Palm Tree
            num_particles = 200
            self.drag = 0.5
            self.history_len = 10
            min_life, max_life = 1.8, 2.6
            self.color = COLORS["sodium_gold"]
            self.star_size = 11.0
        elif self.type == 14:  # Spider
            num_particles = random.randint(250, 350)
            self.drag = 0.25
            self.history_len = 2
            min_life, max_life = 0.6, 0.9
            self.color = COLORS["magnesium_white"] if random.random() < 0.5 else COLORS["sodium_gold"]
            self.star_size = 7.0
        elif self.type == 15:  # Time Rain (Glitter Crackle)
            num_particles = random.randint(300, 400)
            self.drag = 0.65
            self.history_len = 6
            min_life, max_life = 1.8, 2.6
            self.color = COLORS["sodium_gold"]
        elif self.type == 16:  # Farfalle (Fluttering Butterflies)
            num_particles = random.randint(200, 300)
            self.drag = 0.8
            self.history_len = 6
            min_life, max_life = 1.5, 2.2
        elif self.type == 17:  # Tourbillon (Spiraling Vortex)
            num_particles = random.randint(180, 250)
            self.drag = 0.6
            self.history_len = 8
            min_life, max_life = 1.6, 2.4
        else:  # Type 18: Multi-Break Ring to Fish Swarm
            num_particles = 150
            self.drag = 1.2
            self.history_len = 5
            min_life, max_life = 1.4, 2.0

        self.positions = np.zeros((num_particles, 3), dtype=np.float32)
        self.positions[:] = self.launch_pos
        
        self.velocities = np.zeros((num_particles, 3), dtype=np.float32)
        self.colors = np.zeros((num_particles, 4), dtype=np.float32)
        self.ages = np.zeros(num_particles, dtype=np.float32)
        self.max_ages = np.random.uniform(min_life, max_life, num_particles).astype(np.float32)

        if self.type == 3:  # Ring
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            speed = np.random.uniform(7.0, 9.0, num_particles)
            vx = speed * np.cos(theta)
            vy = speed * np.sin(theta)
            vz = np.random.uniform(-0.6, 0.6, num_particles)
            local_vel = np.stack([vx, vy, vz], axis=1)
            
            rx = np.random.uniform(0, 2 * np.pi)
            ry = np.random.uniform(0, 2 * np.pi)
            cx, sx = np.cos(rx), np.sin(rx)
            cy, sy = np.cos(ry), np.sin(ry)
            RotX = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float32)
            RotY = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float32)
            R = RotX @ RotY
            self.velocities = local_vel @ R.T
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 4:  # Pistil / Double Shell
            half = num_particles // 2
            # Outer shell spherical (faster)
            theta_o = np.random.uniform(0, 2 * np.pi, half)
            phi_o = np.arccos(np.random.uniform(-1, 1, half))
            speed_o = np.random.uniform(7.5, 9.5, half)
            
            self.velocities[:half, 0] = speed_o * np.sin(phi_o) * np.cos(theta_o)
            self.velocities[:half, 1] = speed_o * np.sin(phi_o) * np.sin(theta_o)
            self.velocities[:half, 2] = speed_o * np.cos(phi_o)
            
            self.colors[:half, 0] = np.clip(self.color[0] + np.random.uniform(-0.08, 0.08, half), 0.0, 1.0)
            self.colors[:half, 1] = np.clip(self.color[1] + np.random.uniform(-0.08, 0.08, half), 0.0, 1.0)
            self.colors[:half, 2] = np.clip(self.color[2] + np.random.uniform(-0.08, 0.08, half), 0.0, 1.0)
            
            # Inner shell spherical (slower)
            theta_i = np.random.uniform(0, 2 * np.pi, num_particles - half)
            phi_i = np.arccos(np.random.uniform(-1, 1, num_particles - half))
            speed_i = np.random.uniform(3.5, 4.5, num_particles - half)
            
            self.velocities[half:, 0] = speed_i * np.sin(phi_i) * np.cos(theta_i)
            self.velocities[half:, 1] = speed_i * np.sin(phi_i) * np.sin(theta_i)
            self.velocities[half:, 2] = speed_i * np.cos(phi_i)
            
            self.colors[half:, 0] = np.clip(self.secondary_color[0] + np.random.uniform(-0.08, 0.08, num_particles - half), 0.0, 1.0)
            self.colors[half:, 1] = np.clip(self.secondary_color[1] + np.random.uniform(-0.08, 0.08, num_particles - half), 0.0, 1.0)
            self.colors[half:, 2] = np.clip(self.secondary_color[2] + np.random.uniform(-0.08, 0.08, num_particles - half), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 5:  # Waterfall / Horsetail
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-0.1, 0.4, num_particles))
            speed = np.random.uniform(1.5, 4.0, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta) * 0.4
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta) + np.random.uniform(2.0, 4.0, num_particles)
            self.velocities[:, 2] = speed * np.cos(phi) * 0.4
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 6:  # Bees / Swarm / Fish
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(3.0, 5.0, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 7:  # Saturn Ring
            sphere_pts = int(num_particles * 0.55)
            ring_pts = num_particles - sphere_pts
            
            # Central sphere
            theta_s = np.random.uniform(0, 2 * np.pi, sphere_pts)
            phi_s = np.arccos(np.random.uniform(-1, 1, sphere_pts))
            speed_s = np.random.uniform(4.5, 6.0, sphere_pts)
            
            self.velocities[:sphere_pts, 0] = speed_s * np.sin(phi_s) * np.cos(theta_s)
            self.velocities[:sphere_pts, 1] = speed_s * np.sin(phi_s) * np.sin(theta_s)
            self.velocities[:sphere_pts, 2] = speed_s * np.cos(phi_s)
            
            self.colors[:sphere_pts, 0] = np.clip(self.color[0] + np.random.uniform(-0.08, 0.08, sphere_pts), 0.0, 1.0)
            self.colors[:sphere_pts, 1] = np.clip(self.color[1] + np.random.uniform(-0.08, 0.08, sphere_pts), 0.0, 1.0)
            self.colors[:sphere_pts, 2] = np.clip(self.color[2] + np.random.uniform(-0.08, 0.08, sphere_pts), 0.0, 1.0)
            
            # Concentric ring
            theta_r = np.random.uniform(0, 2 * np.pi, ring_pts)
            speed_r = np.random.uniform(8.0, 10.0, ring_pts)
            vx_r = speed_r * np.cos(theta_r)
            vy_r = speed_r * np.sin(theta_r)
            vz_r = np.random.uniform(-0.4, 0.4, ring_pts)
            local_vel_r = np.stack([vx_r, vy_r, vz_r], axis=1)
            
            rx = np.random.uniform(0, 2 * np.pi)
            ry = np.random.uniform(0, 2 * np.pi)
            cx, sx = np.cos(rx), np.sin(rx)
            cy, sy = np.cos(ry), np.sin(ry)
            RotX = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float32)
            RotY = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float32)
            R = RotX @ RotY
            self.velocities[sphere_pts:] = local_vel_r @ R.T
            
            self.colors[sphere_pts:, 0] = np.clip(self.secondary_color[0] + np.random.uniform(-0.08, 0.08, ring_pts), 0.0, 1.0)
            self.colors[sphere_pts:, 1] = np.clip(self.secondary_color[1] + np.random.uniform(-0.08, 0.08, ring_pts), 0.0, 1.0)
            self.colors[sphere_pts:, 2] = np.clip(self.secondary_color[2] + np.random.uniform(-0.08, 0.08, ring_pts), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 9:  # Rainbow Bouquet (Full spectrum vectorized colorization)
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(5.5, 8.5, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            # Highly optimized vectorized selection from the color list per particle
            indices = np.random.randint(0, len(COLOR_LIST), num_particles)
            base_cols = np.array(COLOR_LIST, dtype=np.float32)[indices]
            self.colors[:, :3] = np.clip(base_cols[:, :3] + np.random.uniform(-0.05, 0.05, (num_particles, 3)), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 10:  # Multi-Stage Ring
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            speed = np.random.uniform(7.0, 8.5, num_particles)
            vx = speed * np.cos(theta)
            vy = speed * np.sin(theta)
            vz = np.random.uniform(-0.5, 0.5, num_particles)
            local_vel = np.stack([vx, vy, vz], axis=1)
            
            rx = np.random.uniform(0, 2 * np.pi)
            ry = np.random.uniform(0, 2 * np.pi)
            cx, sx = np.cos(rx), np.sin(rx)
            cy, sy = np.cos(ry), np.sin(ry)
            RotX = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float32)
            RotY = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float32)
            R = RotX @ RotY
            self.velocities = local_vel @ R.T
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 11:  # Dahlia (High intensity, slow-burning, wide expand)
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(7.5, 10.0, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 12:  # Diadem / Crown
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(5.5, 8.5, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 13:  # Palm Tree (Golden fronds + Contrasting Coconuts)
            half = int(num_particles * 0.92)
            theta = np.random.uniform(0, 2 * np.pi, half)
            phi = np.arccos(np.random.uniform(-0.2, 0.8, half))  # Upward-outward arcs
            speed = np.random.uniform(6.5, 9.5, half)
            
            self.velocities[:half, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:half, 1] = speed * np.sin(phi) * np.sin(theta) + 3.0
            self.velocities[:half, 2] = speed * np.cos(phi)
            
            self.colors[:half, 0] = np.clip(self.color[0] + np.random.uniform(-0.05, 0.05, half), 0.0, 1.0)
            self.colors[:half, 1] = np.clip(self.color[1] + np.random.uniform(-0.05, 0.05, half), 0.0, 1.0)
            self.colors[:half, 2] = np.clip(self.color[2] + np.random.uniform(-0.05, 0.05, half), 0.0, 1.0)
            
            coconuts = num_particles - half
            theta_c = np.random.uniform(0, 2 * np.pi, coconuts)
            phi_c = np.arccos(np.random.uniform(-0.5, 0.5, coconuts))
            speed_c = np.random.uniform(9.0, 11.5, coconuts)
            
            self.velocities[half:, 0] = speed_c * np.sin(phi_c) * np.cos(theta_c)
            self.velocities[half:, 1] = speed_c * np.sin(phi_c) * np.sin(theta_c)
            self.velocities[half:, 2] = speed_c * np.cos(phi_c)
            
            coconut_col = COLORS["barium_green"] if random.random() < 0.5 else COLORS["potassium_purple"]
            self.colors[half:, 0] = coconut_col[0]
            self.colors[half:, 1] = coconut_col[1]
            self.colors[half:, 2] = coconut_col[2]
            self.colors[:, 3] = 1.0
            
        elif self.type == 14:  # Spider (Sharp, fast straight-line gold break)
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(13.0, 17.5, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.08, 0.08, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.08, 0.08, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.08, 0.08, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 15:  # Time Rain (Drifting gold)
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(5.5, 8.0, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.05, 0.05, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 16:  # Farfalle (Butterfly flight flutter)
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(5.0, 7.5, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        elif self.type == 17:  # Tourbillon (Spiraling whirlwind)
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            phi = np.arccos(np.random.uniform(-1, 1, num_particles))
            speed = np.random.uniform(4.5, 7.0, num_particles)
            
            self.velocities[:, 0] = speed * np.sin(phi) * np.cos(theta)
            self.velocities[:, 1] = speed * np.sin(phi) * np.sin(theta)
            self.velocities[:, 2] = speed * np.cos(phi)
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0
            
        else:  # Type 18: Multi-Break Ring to Swarm
            theta = np.random.uniform(0, 2 * np.pi, num_particles)
            speed = np.random.uniform(6.5, 8.0, num_particles)
            vx = speed * np.cos(theta)
            vy = speed * np.sin(theta)
            vz = np.random.uniform(-0.5, 0.5, num_particles)
            local_vel = np.stack([vx, vy, vz], axis=1)
            
            rx = np.random.uniform(0, 2 * np.pi)
            ry = np.random.uniform(0, 2 * np.pi)
            cx, sx = np.cos(rx), np.sin(rx)
            cy, sy = np.cos(ry), np.sin(ry)
            RotX = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float32)
            RotY = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float32)
            R = RotX @ RotY
            self.velocities = local_vel @ R.T
            
            self.colors[:, 0] = np.clip(self.color[0] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 1] = np.clip(self.color[1] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 2] = np.clip(self.color[2] + np.random.uniform(-0.1, 0.1, num_particles), 0.0, 1.0)
            self.colors[:, 3] = 1.0

        # Custom gravity profiles per shell type to simulate natural air buoyancy and drag
        gravity_map = {
            0: 5.5,   # Peony
            2: 4.5,   # Willow (floats elegantly)
            3: 4.5,   # Ghost Ring
            5: 3.5,   # Waterfall (graceful descent)
            6: 3.0,   # Swarm/Bees
            8: 5.5,   # Crossette
            10: 4.5,  # Multi-Stage Ring
            11: 4.0,  # Dahlia (slow burning pellets)
            12: 4.5,  # Diadem / Crown
            13: 4.5,  # Palm Tree
            14: 5.5,  # Spider (sharp fast needle break)
            15: 3.5,  # Time Rain (slow glittering drift)
            16: 4.0,  # Farfalle
            17: 4.0,  # Tourbillon
            18: 4.5   # Ring to Swarm
        }
        self.gravity = gravity_map.get(self.type, 5.0)

        self.history = np.zeros((self.history_len, num_particles, 3), dtype=np.float32)
        for h in range(self.history_len):
            self.history[h] = self.positions

    def update(self, dt):
        if self.state == 'DEAD':
            return
            
        if self.state == 'LAUNCH':
            self.launch_age += dt
            self.launch_vel[1] -= 9.8 * dt
            self.launch_vel -= self.launch_vel * 0.15 * dt
            self.launch_pos += self.launch_vel * dt
            
            self.launch_trail.append(self.launch_pos.copy())
            if len(self.launch_trail) > self.launch_trail_max:
                self.launch_trail.pop(0)
                
            if self.launch_vel[1] < 1.0 or self.launch_age >= self.launch_fuse:
                self.explode()
                
        elif self.state == 'EXPLODE':
            self.positions += self.velocities * dt
            
            # Farfalle oscillation
            if self.type == 16:
                perp = np.zeros_like(self.velocities)
                perp[:, 0] = -self.velocities[:, 1]
                perp[:, 1] = self.velocities[:, 0]
                norms = np.linalg.norm(perp, axis=1, keepdims=True) + 1e-6
                perp /= norms
                osc = np.sin(self.ages[:, np.newaxis] * 24.0) * 0.45 * perp
                self.positions += osc * dt
                
            # Tourbillon spiral 
            if self.type == 17:
                v = self.velocities
                u = np.cross(v, np.array([0.0, 1.0, 0.0], dtype=np.float32))
                norms_u = np.linalg.norm(u, axis=1, keepdims=True) + 1e-6
                u /= norms_u
                w = np.cross(v, u)
                norms_w = np.linalg.norm(w, axis=1, keepdims=True) + 1e-6
                w /= norms_w
                
                angle = self.ages * 28.0
                radius = 0.08 + self.ages * 0.6
                spiral = (np.cos(angle)[:, np.newaxis] * u + np.sin(angle)[:, np.newaxis] * w) * (radius[:, np.newaxis])
                self.positions += spiral * dt
                
            # Multi-Stage Ring Split (Stage 1 -> Stage 2)
            if self.type == 10 and self.stage == 1 and np.any(self.ages >= 0.55):
                N = len(self.positions)
                if N > 0:
                    self.stage = 2
                    new_positions = np.repeat(self.positions, 3, axis=0)
                    new_velocities = np.repeat(self.velocities, 3, axis=0)
                    
                    theta_s = np.array([0.0, 2*np.pi/3, 4*np.pi/3], dtype=np.float32)
                    offsets_local = np.stack([np.cos(theta_s), np.sin(theta_s), np.zeros(3, dtype=np.float32)], axis=1) * 3.0
                    offsets = np.tile(offsets_local, (N, 1))
                    
                    new_velocities += offsets
                    new_colors = np.repeat(self.colors, 3, axis=0)
                    new_colors[:, :3] = np.array(self.secondary_color[:3], dtype=np.float32)
                    
                    new_ages = np.zeros(3 * N, dtype=np.float32)
                    new_max_ages = np.random.uniform(0.6, 1.0, 3 * N).astype(np.float32)
                    
                    self.history_len = 3
                    self.history = np.zeros((self.history_len, 3 * N, 3), dtype=np.float32)
                    for h in range(self.history_len):
                        self.history[h] = new_positions
                        
                    self.positions = new_positions
                    self.velocities = new_velocities
                    self.colors = new_colors
                    self.ages = new_ages
                    self.max_ages = new_max_ages
                    self.drag = 1.6
                    self.gravity = 4.0
                    
            # Multi-Break Ring to Swarm Split (Stage 1 -> Stage 2)
            if self.type == 18 and self.stage == 1 and np.any(self.ages >= 0.55):
                N = len(self.positions)
                if N > 0:
                    self.stage = 2
                    self.type = 6  # Becomes Swarm/Fish (inherits wiggle force below)
                    new_positions = np.repeat(self.positions, 3, axis=0)
                    new_velocities = np.repeat(self.velocities, 3, axis=0)
                    
                    fish_vel = 3.5
                    theta_f = np.random.uniform(0, 2 * np.pi, 3 * N)
                    phi_f = np.arccos(np.random.uniform(-1, 1, 3 * N))
                    offsets = np.stack([
                        fish_vel * np.sin(phi_f) * np.cos(theta_f),
                        fish_vel * np.sin(phi_f) * np.sin(theta_f),
                        fish_vel * np.cos(phi_f)
                    ], axis=1).astype(np.float32)
                    new_velocities += offsets
                    
                    new_colors = np.repeat(self.colors, 3, axis=0)
                    new_colors[:, :3] = np.array(self.secondary_color[:3], dtype=np.float32)
                    
                    new_ages = np.zeros(3 * N, dtype=np.float32)
                    new_max_ages = np.random.uniform(1.2, 1.8, 3 * N).astype(np.float32)
                    
                    self.history_len = 8
                    self.history = np.zeros((self.history_len, 3 * N, 3), dtype=np.float32)
                    for h in range(self.history_len):
                        self.history[h] = new_positions
                        
                    self.positions = new_positions
                    self.velocities = new_velocities
                    self.colors = new_colors
                    self.ages = new_ages
                    self.max_ages = new_max_ages
                    self.drag = 0.5
                    self.gravity = 3.0

            # Crossette Splitting (Stage 1 -> Stage 2 transition)
            if self.type == 8 and self.stage == 1 and np.any(self.ages >= 0.55):
                N = len(self.positions)
                if N > 0:
                    self.stage = 2
                    
                    # 1. Expand arrays 4x
                    new_positions = np.repeat(self.positions, 4, axis=0)
                    new_velocities = np.repeat(self.velocities, 4, axis=0)
                    
                    # 2. Add high-speed right-angle offsets for 3D cross pattern
                    cross_vel = 4.8
                    offsets = np.array([
                        [ cross_vel,  0.0,  0.0],
                        [-cross_vel,  0.0,  0.0],
                        [ 0.0,  cross_vel,  0.0],
                        [ 0.0, -cross_vel,  0.0]
                    ], dtype=np.float32)
                    new_velocities += np.tile(offsets, (N, 1))
                    
                    # 3. Repeat and transition colors (hot-gold to brilliant secondary color)
                    new_colors = np.repeat(self.colors, 4, axis=0)
                    new_colors[:, :3] = np.array(self.secondary_color[:3], dtype=np.float32)
                    
                    # 4. Refresh lifespans for secondary spark stage
                    new_ages = np.zeros(4 * N, dtype=np.float32)
                    new_max_ages = np.random.uniform(0.7, 1.1, 4 * N).astype(np.float32)
                    
                    # 5. Clear and set new short history trails
                    self.history_len = 3
                    self.history = np.zeros((self.history_len, 4 * N, 3), dtype=np.float32)
                    for h in range(self.history_len):
                        self.history[h] = new_positions
                        
                    self.positions = new_positions
                    self.velocities = new_velocities
                    self.colors = new_colors
                    self.ages = new_ages
                    self.max_ages = new_max_ages
                    self.drag = 1.8  # Increase air drag on tiny sub-sparks
                    self.gravity = 4.5
            
            # Chaotic wiggling forces for swarming/bees type
            if self.type == 6:
                perturbation = np.random.uniform(-18.0, 18.0, (len(self.positions), 3)).astype(np.float32)
                self.velocities += perturbation * dt
            
            self.velocities[:, 1] -= self.gravity * dt
            self.velocities -= self.velocities * self.drag * dt
            
            self.ages += dt
            
            life_ratio = self.ages / self.max_ages
            
            # Chemical dual-color transition over lifetime
            if self.type == 12:  # Diadem: keep gold for first 70% then transition to secondary colored tip
                ratio_col = np.clip((life_ratio - 0.7) / 0.3, 0.0, 1.0)[:, np.newaxis]
            else:
                ratio_col = np.clip((life_ratio - 0.3) / 0.7, 0.0, 1.0)[:, np.newaxis]
            p_col = np.array(self.color[:3], dtype=np.float32)
            s_col = np.array(self.secondary_color[:3], dtype=np.float32)
            self.colors[:, :3] = (1.0 - ratio_col) * p_col + ratio_col * s_col
            
            fade = np.clip(1.0 - life_ratio, 0.0, 1.0)
            flicker = np.ones_like(fade)
            twinkle_mask = life_ratio > 0.4
            flicker[twinkle_mask] = np.where(
                np.random.rand(np.sum(twinkle_mask)) < 0.15,
                0.2,
                1.0
            )
            self.colors[:, 3] = fade * flicker
            
            # Delay Crackle Time Rain physics / strobe
            if self.type == 15:
                crackle_mask = life_ratio > 0.45
                num_crackle = np.sum(crackle_mask)
                if num_crackle > 0:
                    # High-frequency position jitter 
                    jitter = np.random.uniform(-0.15, 0.15, (num_crackle, 3)).astype(np.float32)
                    self.positions[crackle_mask] += jitter
                    
                    # Magnesium strobe white colors
                    strobe = np.random.rand(num_crackle) < 0.45
                    self.colors[crackle_mask, :3] = np.where(
                        strobe[:, np.newaxis],
                        np.array([1.0, 1.0, 0.95], dtype=np.float32),
                        np.array(self.color[:3], dtype=np.float32)
                    )
                    flicker[crackle_mask] = np.where(strobe, 1.0, 0.15)
                    self.colors[crackle_mask, 3] = fade[crackle_mask] * flicker[crackle_mask]
            
            if self.history_len > 1:
                self.history[1:] = self.history[:-1]
                self.history[0] = self.positions.copy()
                
            alive = self.ages < self.max_ages
            if np.any(alive):
                self.positions = self.positions[alive]
                self.velocities = self.velocities[alive]
                self.colors = self.colors[alive]
                self.ages = self.ages[alive]
                self.max_ages = self.max_ages[alive]
                if self.history_len > 1:
                    self.history = self.history[:, alive]
            else:
                self.state = 'DEAD'


class FireworksApp:
    def __init__(self):
        self.fireworks = []
        
        self.camera_dist = 26.0
        self.camera_theta = 0.0
        self.camera_phi = 0.25
        self.auto_rotate = True
        
        self.last_time = time.time()
        
        self.auto_launch = True
        self.launch_timer = 0.0
        self.next_launch_interval = 0.8
        
        self.fps = 60.0
        self.fps_filter = 0.95
        
        self.is_fullscreen = False
        
        self.drag_base_theta = 0.0
        self.drag_base_phi = 0.0
        
        # VAO / VBO / Shader Program references
        self.sky_program = None
        self.line_program = None
        self.particle_program = None

    def load_css(self):
        css_data = """
        .hud-title {
            font-family: 'Outfit', 'Inter', 'Sans-Serif', sans-serif;
            font-size: 16px;
            font-weight: bold;
            color: #e6f0ff;
        }
        .hud-subtitle {
            font-family: 'Outfit', 'Inter', 'Sans-Serif', sans-serif;
            font-size: 10px;
            color: #96b4dc;
        }
        .hud-stats-fps {
            font-family: 'Inter', 'Monospace', monospace;
            font-size: 11px;
            font-weight: bold;
            color: #64e696;
            margin-bottom: 2px;
        }
        .hud-stats {
            font-family: 'Inter', 'Monospace', monospace;
            font-size: 10px;
            color: #c8dcff;
        }
        .hud-legend {
            background-color: rgba(10, 10, 25, 0.65);
            border: 1px solid rgba(130, 150, 180, 0.2);
            border-radius: 6px;
            padding: 12px;
        }
        .hud-legend-title {
            font-family: 'Outfit', 'Inter', sans-serif;
            font-weight: bold;
            color: #e2e6ff;
            font-size: 10px;
            margin-bottom: 6px;
        }
        .hud-legend label {
            font-family: 'Inter', 'Monospace', monospace;
            font-size: 9px;
            color: #b4c8f0;
        }
        """
        provider = Gtk.CssProvider()
        if hasattr(provider, 'load_from_string'):
            provider.load_from_string(css_data)
        else:
            provider.load_from_data(css_data.encode('utf-8'))
        
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_activate(self, app):
        self.win = Gtk.ApplicationWindow(application=app)
        self.win.set_title("3D OpenGL Fireworks Demo")
        self.win.set_default_size(1280, 720)
        
        self.load_css()
        
        overlay = Gtk.Overlay()
        
        self.gl_area = Gtk.GLArea()
        self.gl_area.set_required_version(3, 2)
        self.gl_area.set_has_depth_buffer(True)
        self.gl_area.connect("realize", self.on_realize)
        self.gl_area.connect("render", self.on_render)
        overlay.set_child(self.gl_area)
        
        hud_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        hud_box.set_valign(Gtk.Align.START)
        hud_box.set_halign(Gtk.Align.START)
        hud_box.set_margin_start(20)
        hud_box.set_margin_top(20)
        
        title_lbl = Gtk.Label(label="PYRO-ENGINE 3D")
        title_lbl.add_css_class("hud-title")
        title_lbl.set_halign(Gtk.Align.START)
        hud_box.append(title_lbl)
        
        sub_lbl = Gtk.Label(label="High-Performance OpenGL Screensaver")
        sub_lbl.add_css_class("hud-subtitle")
        sub_lbl.set_halign(Gtk.Align.START)
        hud_box.append(sub_lbl)
        
        stats_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        stats_box.set_margin_top(15)
        stats_box.set_halign(Gtk.Align.START)
        
        self.fps_lbl = Gtk.Label(label="FPS: 60.0")
        self.fps_lbl.add_css_class("hud-stats-fps")
        self.fps_lbl.set_halign(Gtk.Align.START)
        stats_box.append(self.fps_lbl)
        
        self.shell_lbl = Gtk.Label(label="Active Shells: 0")
        self.shell_lbl.add_css_class("hud-stats")
        self.shell_lbl.set_halign(Gtk.Align.START)
        stats_box.append(self.shell_lbl)
        
        self.part_lbl = Gtk.Label(label="Simulated Particles: 0")
        self.part_lbl.add_css_class("hud-stats")
        self.part_lbl.set_halign(Gtk.Align.START)
        stats_box.append(self.part_lbl)
        
        hud_box.append(stats_box)
        overlay.add_overlay(hud_box)
        
        legend_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        legend_box.add_css_class("hud-legend")
        legend_box.set_valign(Gtk.Align.END)
        legend_box.set_halign(Gtk.Align.START)
        legend_box.set_margin_start(20)
        legend_box.set_margin_bottom(20)
        
        leg_title = Gtk.Label(label="KEYBOARD CONTROLS:")
        leg_title.add_css_class("hud-legend-title")
        leg_title.set_halign(Gtk.Align.START)
        legend_box.append(leg_title)
        
        lbl_space = Gtk.Label(label="[SPACE]  - Launch Manual Shell")
        lbl_space.set_halign(Gtk.Align.START)
        legend_box.append(lbl_space)
        
        self.lbl_auto_launch = Gtk.Label()
        self.lbl_auto_launch.set_halign(Gtk.Align.START)
        legend_box.append(self.lbl_auto_launch)
        
        self.lbl_auto_rotate = Gtk.Label()
        self.lbl_auto_rotate.set_halign(Gtk.Align.START)
        legend_box.append(self.lbl_auto_rotate)
        
        self.update_legend_labels()
        
        lbl_clear = Gtk.Label(label="[C]      - Clear Active Particles")
        lbl_clear.set_halign(Gtk.Align.START)
        legend_box.append(lbl_clear)
        
        lbl_fs = Gtk.Label(label="[F]      - Toggle Fullscreen")
        lbl_fs.set_halign(Gtk.Align.START)
        legend_box.append(lbl_fs)
        
        lbl_quit = Gtk.Label(label="[ESC/Q]  - Quit Screensaver")
        lbl_quit.set_halign(Gtk.Align.START)
        legend_box.append(lbl_quit)
        
        overlay.add_overlay(legend_box)
        
        self.win.set_child(overlay)
        
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.win.add_controller(key_controller)
        
        drag_gesture = Gtk.GestureDrag()
        drag_gesture.connect("drag-begin", self.on_drag_begin)
        drag_gesture.connect("drag-update", self.on_drag_update)
        self.gl_area.add_controller(drag_gesture)
        
        scroll_controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_controller.connect("scroll", self.on_scroll)
        self.gl_area.add_controller(scroll_controller)
        
        GLib.timeout_add(16, self.on_tick)
        
        self.win.present()
 
    def update_legend_labels(self):
        self.lbl_auto_launch.set_text(f"[A]      - Toggle Auto-Launcher ({'ON' if self.auto_launch else 'OFF'})")
        self.lbl_auto_rotate.set_text(f"[R]      - Toggle Camera Auto-Rotation ({'ON' if self.auto_rotate else 'OFF'})")
 
    def on_realize(self, area):
        area.make_current()
        if area.get_error() is not None:
            print("GLArea realize error:", area.get_error())
            return
             
        gl.glClearColor(0.01, 0.01, 0.05, 1.0)
        
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LEQUAL)
        
        try:
            gl.glEnable(gl.GL_PROGRAM_POINT_SIZE)
        except Exception:
            pass
            
        # Modern Shader Programs Compilation and Linking
        try:
            self.sky_program = create_program(SKY_VERTEX_SHADER, SKY_FRAGMENT_SHADER)
            self.line_program = create_program(LINE_VERTEX_SHADER, LINE_FRAGMENT_SHADER)
            self.particle_program = create_program(PARTICLE_VERTEX_SHADER, PARTICLE_FRAGMENT_SHADER)
        except Exception as e:
            print("Shader initialization failed:", e)
            return
        
        # Compile sky fullscreen quad VBO
        self.sky_vao = gl.glGenVertexArrays(1)
        self.sky_vbo = gl.glGenBuffers(1)
        sky_vertices = np.array([
            -1.0, -1.0,
             1.0, -1.0,
             1.0,  1.0,
            -1.0,  1.0
        ], dtype=np.float32)
        
        gl.glBindVertexArray(self.sky_vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.sky_vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, sky_vertices.nbytes, sky_vertices, gl.GL_STATIC_DRAW)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        gl.glBindVertexArray(0)
        
        # Dynamic Line Buffers Setup
        self.line_vao = gl.glGenVertexArrays(1)
        self.line_pos_vbo, self.line_col_vbo = gl.glGenBuffers(2)
        
        gl.glBindVertexArray(self.line_vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.line_pos_vbo)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.line_col_vbo)
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 4, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        gl.glBindVertexArray(0)
        
        # Dynamic Particle Buffers Setup
        self.particle_vao = gl.glGenVertexArrays(1)
        self.particle_pos_vbo, self.particle_col_vbo, self.particle_size_vbo = gl.glGenBuffers(3)
        
        gl.glBindVertexArray(self.particle_vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.particle_pos_vbo)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.particle_col_vbo)
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 4, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.particle_size_vbo)
        gl.glEnableVertexAttribArray(2)
        gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        gl.glBindVertexArray(0)
        
        # Query program uniform locations
        self.line_proj_loc = gl.glGetUniformLocation(self.line_program, "projection")
        self.line_view_loc = gl.glGetUniformLocation(self.line_program, "view")
        
        self.part_proj_loc = gl.glGetUniformLocation(self.particle_program, "projection")
        self.part_view_loc = gl.glGetUniformLocation(self.particle_program, "view")

    def on_render(self, area, context):
        if self.sky_program is None:
            return False
            
        w = area.get_width()
        h = area.get_height()
        aspect = w / h if h > 0 else 1.0
        
        gl.glViewport(0, 0, w, h)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        
        # 1. Draw Fullscreen Sky Gradient (Depth Testing Off)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glUseProgram(self.sky_program)
        gl.glBindVertexArray(self.sky_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_FAN, 0, 4)
        gl.glBindVertexArray(0)
        
        # Enable Depth Testing and Additive Blending for World Render
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
        
        # Compute CPU Projection and View Matrices
        proj_matrix = perspective_matrix(50.0, aspect, 0.1, 150.0)
        cx = self.camera_dist * np.cos(self.camera_phi) * np.sin(self.camera_theta)
        cy = self.camera_dist * np.sin(self.camera_phi)
        cz = self.camera_dist * np.cos(self.camera_phi) * np.cos(self.camera_theta)
        view_matrix = look_at_matrix([cx, cy, cz], [0.0, 4.0, 0.0], [0.0, 1.0, 0.0])
        
        # 2. Gather, Buffer and Render All Line Geometries (Ground Grid & Rocket Trails)
        line_pos = []
        line_col = []
        
        # Draw Reference Ground Grid
        grid_y = -12.0
        grid_range = 30.0
        steps = 10
        for i in range(steps + 1):
            val = -grid_range + (2.0 * grid_range / steps) * i
            grid_col = (0.15, 0.15, 0.3, 0.08)
            
            line_pos.append([val, grid_y, -grid_range])
            line_pos.append([val, grid_y, grid_range])
            line_col.append(grid_col)
            line_col.append(grid_col)
            
            line_pos.append([-grid_range, grid_y, val])
            line_pos.append([grid_range, grid_y, val])
            line_col.append(grid_col)
            line_col.append(grid_col)
            
        # Add Rocket Launch Trails to Line Buffer
        for fw in self.fireworks:
            if fw.state == 'LAUNCH' and len(fw.launch_trail) > 1:
                for idx in range(len(fw.launch_trail) - 1):
                    pt0 = fw.launch_trail[idx]
                    pt1 = fw.launch_trail[idx + 1]
                    alpha0 = idx / len(fw.launch_trail)
                    alpha1 = (idx + 1) / len(fw.launch_trail)
                    
                    line_pos.append(pt0)
                    line_pos.append(pt1)
                    line_col.append((1.0, 0.45, 0.1, alpha0 * 0.5))
                    line_col.append((1.0, 0.45, 0.1, alpha1 * 0.5))
                    
        if len(line_pos) > 0:
            line_pos_arr = np.array(line_pos, dtype=np.float32)
            line_col_arr = np.array(line_col, dtype=np.float32)
            
            gl.glUseProgram(self.line_program)
            gl.glUniformMatrix4fv(self.line_proj_loc, 1, gl.GL_TRUE, proj_matrix)
            gl.glUniformMatrix4fv(self.line_view_loc, 1, gl.GL_TRUE, view_matrix)
            
            gl.glBindVertexArray(self.line_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.line_pos_vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, line_pos_arr.nbytes, line_pos_arr, gl.GL_DYNAMIC_DRAW)
            
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.line_col_vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, line_col_arr.nbytes, line_col_arr, gl.GL_DYNAMIC_DRAW)
            
            gl.glLineWidth(1.0)
            gl.glDrawArrays(gl.GL_LINES, 0, len(line_pos_arr))
            gl.glBindVertexArray(0)
            
        # 3. Gather, Buffer and Render All Points (Launcher Heads, Sparks and Particle Trails)
        part_pos = []
        part_col = []
        part_size = []
        
        for fw in self.fireworks:
            if fw.state == 'LAUNCH':
                part_pos.append(fw.launch_pos)
                part_col.append((1.0, 0.8, 0.5, 1.0))
                part_size.append(10.0)
            elif fw.state == 'EXPLODE' and fw.positions is not None:
                num_pts = len(fw.positions)
                if num_pts == 0:
                    continue
                # Primary bright exploding stars
                part_pos.append(fw.positions)
                part_col.append(fw.colors)
                part_size.append(np.full(num_pts, fw.star_size, dtype=np.float32))
                
                # Particle trails history step-down fading
                if fw.history_len > 1 and fw.history is not None:
                    for h in range(fw.history_len):
                        trail_factor = 1.0 - (h / fw.history_len)
                        step_colors = fw.colors.copy()
                        step_colors[:, 3] *= trail_factor * 0.45
                        step_sizes = np.full(num_pts, max(1.0, (fw.star_size * 0.65) * trail_factor), dtype=np.float32)
                        
                        part_pos.append(fw.history[h])
                        part_col.append(step_colors)
                        part_size.append(step_sizes)
                        
        if len(part_pos) > 0:
            try:
                norm_pos = []
                norm_col = []
                norm_size = []
                
                for p in part_pos:
                    p_arr = np.asarray(p, dtype=np.float32)
                    norm_pos.append(p_arr if p_arr.ndim == 2 else p_arr[np.newaxis, :])
                    
                for c in part_col:
                    c_arr = np.asarray(c, dtype=np.float32)
                    norm_col.append(c_arr if c_arr.ndim == 2 else c_arr[np.newaxis, :])
                    
                for s in part_size:
                    s_arr = np.asarray(s, dtype=np.float32)
                    norm_size.append(s_arr if s_arr.ndim == 1 else s_arr[np.newaxis])
                
                pos_arr = np.concatenate(norm_pos, axis=0).astype(np.float32)
                col_arr = np.concatenate(norm_col, axis=0).astype(np.float32)
                size_arr = np.concatenate(norm_size, axis=0).astype(np.float32)
                
                gl.glUseProgram(self.particle_program)
                gl.glUniformMatrix4fv(self.part_proj_loc, 1, gl.GL_TRUE, proj_matrix)
                gl.glUniformMatrix4fv(self.part_view_loc, 1, gl.GL_TRUE, view_matrix)
                
                gl.glBindVertexArray(self.particle_vao)
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.particle_pos_vbo)
                gl.glBufferData(gl.GL_ARRAY_BUFFER, pos_arr.nbytes, pos_arr, gl.GL_DYNAMIC_DRAW)
                
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.particle_col_vbo)
                gl.glBufferData(gl.GL_ARRAY_BUFFER, col_arr.nbytes, col_arr, gl.GL_DYNAMIC_DRAW)
                
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.particle_size_vbo)
                gl.glBufferData(gl.GL_ARRAY_BUFFER, size_arr.nbytes, size_arr, gl.GL_DYNAMIC_DRAW)
                
                gl.glDrawArrays(gl.GL_POINTS, 0, len(pos_arr))
                gl.glBindVertexArray(0)
            except Exception as e:
                import traceback
                traceback.print_exc()
                
        return True

    def on_tick(self):
        now = time.time()
        dt = now - self.last_time
        self.last_time = now
        dt = min(dt, 0.1)
        
        measured_fps = 1.0 / dt if dt > 0 else 60.0
        self.fps = self.fps * self.fps_filter + measured_fps * (1.0 - self.fps_filter)
        
        if self.auto_rotate:
            self.camera_theta += 0.15 * dt
            if self.camera_theta > 2 * np.pi:
                self.camera_theta -= 2 * np.pi
                
        if self.auto_launch:
            self.launch_timer += dt
            if self.launch_timer >= self.next_launch_interval:
                self.launch_timer = 0.0
                self.next_launch_interval = random.uniform(0.6, 1.3)
                self.fireworks.append(Firework())
                
        for fw in self.fireworks:
            fw.update(dt)
            
        self.fireworks = [fw for fw in self.fireworks if fw.state != 'DEAD']
        
        self.fps_lbl.set_text(f"FPS: {self.fps:.1f}")
        active_stars = sum(len(fw.positions) for fw in self.fireworks if fw.positions is not None)
        active_rockets = sum(1 for fw in self.fireworks if fw.state == 'LAUNCH')
        
        self.shell_lbl.set_text(f"Active Shells: {active_rockets}")
        self.part_lbl.set_text(f"Simulated Particles: {active_stars:,}")
        
        self.gl_area.queue_draw()
        return True

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q, Gdk.KEY_Q):
            self.win.close()
            return True
        elif keyval == Gdk.KEY_space:
            self.fireworks.append(Firework())
            return True
        elif keyval in (Gdk.KEY_a, Gdk.KEY_A):
            self.auto_launch = not self.auto_launch
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_r, Gdk.KEY_R):
            self.auto_rotate = not self.auto_rotate
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_c, Gdk.KEY_C):
            self.fireworks.clear()
            return True
        elif keyval in (Gdk.KEY_f, Gdk.KEY_F):
            if self.is_fullscreen:
                self.win.unfullscreen()
                self.is_fullscreen = False
            else:
                self.win.fullscreen()
                self.is_fullscreen = True
            return True
        return False

    def on_drag_begin(self, gesture, x, y):
        self.drag_base_theta = self.camera_theta
        self.drag_base_phi = self.camera_phi

    def on_drag_update(self, gesture, offset_x, offset_y):
        self.camera_theta = self.drag_base_theta - offset_x * 0.007
        self.camera_phi = np.clip(self.drag_base_phi + offset_y * 0.007, 0.02, np.pi / 2.0 - 0.02)

    def on_scroll(self, controller, dx, dy):
        self.camera_dist = np.clip(self.camera_dist + dy * 1.5, 10.0, 80.0)
        return True


if __name__ == "__main__":
    app = Gtk.Application(application_id="org.fireworks.demo")
    pyro_app = FireworksApp()
    app.connect("activate", pyro_app.on_activate)
    app.run(sys.argv)
