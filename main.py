import sys
import time
import random
import ctypes
import numpy as np
import os
import json
import subprocess
import math

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk, GObject

# Suppress verbose and deprecation-related GTK theme/parsing warnings
def gtk_log_writer_func(log_level, fields, *args):
    try:
        log_domain = ""
        for field in fields:
            if field.key == "GLIB_DOMAIN":
                log_domain = field.value
                break
        is_warning_or_lower = not (log_level & (GLib.LogLevelFlags.LEVEL_ERROR | GLib.LogLevelFlags.LEVEL_CRITICAL))
        if log_domain in ("Gtk", "Gdk") and is_warning_or_lower:
            return GLib.LogWriterOutput.HANDLED
    except Exception:
        pass
    user_data = args[-1] if args else None
    return GLib.log_writer_default(log_level, fields, user_data)

try:
    GLib.log_set_writer_func(gtk_log_writer_func, None)
except Exception:
    pass

import OpenGL.GL as gl
import OpenGL.contextdata
# Bypass PyOpenGL GLX/EGL detection mismatch by mocking context getter
OpenGL.contextdata.getContext = lambda context=None: 1

RARITY_INTERVAL = 60.0

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

# Curated Color Palettes for the Optional Color Modes
NEON_PALETTE = [
    (1.0, 0.0, 0.5, 1.0),   # Neon Pink
    (0.0, 1.0, 1.0, 1.0),   # Neon Cyan
    (0.5, 0.0, 1.0, 1.0),   # Neon Purple
    (1.0, 1.0, 0.0, 1.0),   # Neon Yellow
    (0.0, 1.0, 0.0, 1.0)    # Neon Green
]

TRANQUIL_PALETTE = [
    (0.0, 0.3, 0.8, 1.0),   # Deep Blue
    (0.0, 0.6, 0.5, 1.0),   # Calming Teal
    (0.1, 0.7, 0.4, 1.0),   # Soft Emerald Green
    (0.5, 0.2, 0.7, 1.0),   # Lavender/Lilac
    (0.3, 0.4, 0.9, 1.0)    # Periwinkle Blue
]

METAL_PALETTE = [
    (0.9, 0.9, 0.95, 1.0),  # Bright Silver
    (1.0, 0.8, 0.2, 1.0),   # Radiant Gold
    (0.8, 0.5, 0.2, 1.0),   # Warm Bronze
    (0.7, 0.7, 0.75, 1.0),  # Slate Platinum
    (0.85, 0.65, 0.35, 1.0) # Burnished Brass
]

def get_palette_colors(mode):
    if mode == 'NEON':
        return NEON_PALETTE
    elif mode == 'TRANQUIL':
        return TRANQUIL_PALETTE
    elif mode == 'METAL':
        return METAL_PALETTE
    return None

SUPPORTED_ROUTINES = {
    "FIREWORKS": [
        "American Flag", "Liberty Bell", "Statue of Liberty",
        "Flower Bouquet", "The Dragon", "Supernova", "Shooting Star"
    ],
    "TUNNEL Wormhole": [
        "Lightning Flash", "Supernova", "Shooting Star"
    ],
    "UNDERWATER Lava": [
        "Supernova", "Shooting Star"
    ],
    "MANDALA Sacred": [
        "Peace Symbol", "Halo Effect", "Supernova", "Shooting Star"
    ],
    "SYNAESTHESIA Classic": [
        "Star Burst"
    ]
}

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

uniform float uTime;
uniform float uRipple; // 0.0 = normal, 1.0 = Underwater, 2.0 = Tunnel
uniform float uClimaxFlash; // Climax event flash intensity

// Fullscreen rendering uniforms for Tunnel Mode
uniform float uWormholeBendX;
uniform float uWormholeBendY;
uniform float uWormholePhaseX;
uniform float uWormholePhaseY;
uniform float uReactBass;
uniform float uReactTreble;
uniform float uReactMid;
uniform float uAspect;
uniform mat4 uInvVP;

// Noise helper functions for high-fidelity procedurals
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i + vec2(0.0,0.0)), hash(i + vec2(1.0,0.0)), u.x),
               mix(hash(i + vec2(0.0,1.0)), hash(i + vec2(1.0,1.0)), u.x), u.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    vec2 shift = vec2(100.0);
    mat2 rot = mat2(cos(0.5), sin(0.5), -sin(0.5), cos(0.5));
    for (int i = 0; i < 4; ++i) {
        v += a * noise(p);
        p = rot * p * 2.0 + shift;
        a *= 0.5;
    }
    return v;
}

float pattern(vec2 p, out vec2 q, out vec2 r) {
    q = vec2(fbm(p + vec2(0.0, 0.0)), fbm(p + vec2(5.2, 1.3)));
    r = vec2(fbm(p + 4.0 * q + vec2(1.7, 9.2)), fbm(p + 4.0 * q + vec2(8.3, 2.8)));
    return fbm(p + 4.0 * r);
}

vec2 get_bend(float z) {
    float bx = uWormholeBendX * sin(z * 0.06 + uWormholePhaseX);
    float by = uWormholeBendY * cos(z * 0.06 + uWormholePhaseY);
    return vec2(bx, by);
}

float sdTunnel(vec3 p) {
    // High-amplitude organic peristalsis wave traveling along the z-axis, enhanced with a base offset and bass hits
    float wave = sin(p.z * 0.18 - uTime * 2.5) * 0.95;
    float peristalsis = (0.15 + uReactBass * 0.70) * (sin(p.z * 0.22 - uTime * 6.5) * 0.5 + 0.5);
    float radius = (8.0 + wave) * (1.0 - peristalsis);

    // Structural warp/lightning bend: during climax/lightning flash, crackle the tunnel coordinates!
    vec2 warp = vec2(0.0);
    if (uClimaxFlash > 0.05) {
        float crackle = sin(p.z * 0.8 + uTime * 25.0) * cos(p.z * 1.5 - uTime * 30.0);
        warp += vec2(crackle, -crackle) * uClimaxFlash * 1.8;
    }

    float dist_to_axis = length(p.xy + warp - (get_bend(p.z) + vec2(0.0, 4.0)));
    return abs(dist_to_axis - radius);
}

void main() {
    float t_gradient = (vPos.y + 1.0) * 0.5;
    vec3 col_bottom = vec3(0.005, 0.005, 0.04);
    vec3 col_top = vec3(0.0, 0.0, 0.005);
    vec3 base_color = mix(col_bottom, col_top, t_gradient);
    
    // Multi-stroke stroboscopic lightning flash background glow (grand event)
    if (uClimaxFlash > 0.05) {
        float strobes = step(0.4, sin(uTime * 45.0) * cos(uTime * 30.0) * 0.5 + 0.5);
        base_color += vec3(0.75, 0.90, 1.0) * uClimaxFlash * strobes * 0.55;
    }
    
    // Twinkling procedural deep space starfield
    vec2 star_uv = vec2(vPos.x * uAspect, vPos.y) * 15.0;
    vec2 star_id = floor(star_uv);
    vec2 star_f = fract(star_uv) - 0.5;
    float star_h = hash(star_id);
    if (star_h > 0.982) {
        // Twinkle frequency and phase are randomized, and modulated by the music (uReactTreble)
        float freq = 2.0 + star_h * 5.0;
        float music_shift = uReactTreble * (2.0 + star_h * 10.0);
        float twinkle = sin(uTime * freq + star_h * 6.28 + music_shift) * 0.5 + 0.5;
        float dist = length(star_f);
        float star_p = smoothstep(0.08, 0.0, dist) * 0.4 + smoothstep(0.02, 0.0, dist) * 0.6;
        base_color += vec3(0.85, 0.92, 1.0) * star_p * (0.15 + 0.85 * twinkle * (1.0 + uReactTreble * 0.5));
    }
    
    if (uRipple > 0.5 && uRipple < 1.5) {
        // High-end ambient Underwater Caustics & God Rays (subtle & darker)
        // 1. Shifting vertical light beams
        float rays = sin(vPos.x * 2.0 + uTime * 0.5) * sin(vPos.x * 1.0 - uTime * 0.3) * 0.5 + 0.5;
        rays += sin(vPos.x * 5.0 + uTime * 0.8) * 0.2;
        float ray_fade = clamp(vPos.y + 0.5, 0.0, 1.0);
        vec3 ray_color = vec3(0.005, 0.04, 0.07) * rays * ray_fade;
        
        // 2. Beautiful overlapping caustic waves
        vec2 uv_c = vPos * 2.0;
        uv_c.y += sin(uv_c.x + uTime) * 0.1;
        float c1 = noise(uv_c * 3.0 + vec2(0.0, uTime * 0.6));
        float c2 = noise(uv_c * 5.0 - vec2(uTime * 0.4, 0.0));
        float caustics = min(c1, c2);
        caustics = pow(caustics, 3.0) * 1.0;
        vec3 caustic_color = vec3(0.004, 0.02, 0.05) * caustics * (vPos.y + 1.2);
        
        // 3. Screen-filling plankton bloom glow during climax
        vec3 bloom_color = vec3(0.012, 0.42, 0.88) * uClimaxFlash;
        
        base_color += ray_color + caustic_color + bloom_color;
    } 
    else if (uRipple > 1.5) {
        // 100% continuous, smoky, raymarched plasma tunnel
        vec4 target = uInvVP * vec4(vPos, 1.0, 1.0);
        vec4 origin = uInvVP * vec4(vPos, -1.0, 1.0);
        origin /= origin.w;
        target /= target.w;
        
        vec3 ro = origin.xyz;
        vec3 rd = normalize(target.xyz - origin.xyz);
        
        float t = 0.1;
        bool hit = false;
        vec3 p = ro;
        
        for (int i = 0; i < 48; i++) {
            p = ro + t * rd;
            float d = sdTunnel(p);
            if (d < 0.01) {
                hit = true;
                break;
            }
            t += d;
            if (t > 120.0) break;
        }
        
        if (hit) {
            vec2 bend = get_bend(p.z);
            float angle = atan(p.y - (bend.y + 4.0), p.x - bend.x);
            
            // 100% continuous circular mapping (erases the left-hand seam completely!)
            vec2 uv = vec2(cos(angle) * 1.8 + p.z * 0.02, sin(angle) * 1.8 - uTime * 0.9 + p.z * 0.045);
            
            vec2 q, r;
            float f = pattern(uv, q, r);
            
            // Generate glowing base color from mid audio-frequencies
            float t_val = uTime * 0.35 + uReactMid * 0.7;
            float depth_offset = p.z * 0.04;
            vec3 tunnel_base = vec3(
                0.5 + 0.5 * sin(t_val + depth_offset),
                0.5 + 0.5 * sin(t_val + depth_offset + 2.094),
                0.5 + 0.5 * sin(t_val + depth_offset + 4.188)
            );
            
            // Dynamic, music-driven subtle color shift / glow
            float color_shift = uTime * 0.22 + uReactBass * 0.35;
            vec3 subtle_glow = vec3(
                0.08 * sin(color_shift),
                0.08 * sin(color_shift + 2.094),
                0.08 * sin(color_shift + 4.188)
            ) * (1.0 + uReactMid * 0.8);
            
            float smoke_mask = smoothstep(0.18, 0.82, f);
            vec3 col = tunnel_base + subtle_glow;
            col += vec3(0.12, 0.32, 0.58) * q.x; // cyan smoke filament
            col += vec3(0.62, 0.12, 0.38) * r.y; // magenta smoke filament
            
            // The walls of the wormhole get significantly brighter/darker with the music (glowing/fading with the beat)
            float wall_brightness = 0.8 + uReactBass * 1.6 + uReactMid * 0.8 + uReactTreble * 0.4;
            col *= wall_brightness;
            
            // Elegant depth fog
            float fog = clamp((p.z + 60.0) / 60.0, 0.0, 1.0);
            vec3 tunnel_color = mix(vec3(0.005, 0.005, 0.02), col, fog);
            
            // Blend with background based on smoke_mask density for translucency/transparency
            // Reduced maximum opacity even further (0.08) to let deep space background and stars show through beautifully (extremely transparent!)
            // Climax flash dynamically increases tunnel plasma opacity and glows with white hot light
            // Under music, the walls get more opaque/solid on the beat, then fade back to faint transparency during silence
            float base_opacity = 0.04 + uReactBass * 0.16 + uReactMid * 0.08;
            float opacity = smoke_mask * fog * (base_opacity + uClimaxFlash * 0.38);
            vec3 flash_col = tunnel_color + vec3(0.82, 0.92, 1.0) * uClimaxFlash * 0.7;
            base_color = mix(base_color, flash_col, opacity);
            
            // Climax background deep space flare
            base_color += vec3(0.38, 0.58, 0.95) * uClimaxFlash * 0.22;
            
            // Multi-stroke stroboscopic lightning flash overlay on tunnel surface (grand event)
            if (uClimaxFlash > 0.05) {
                float strobes = step(0.4, sin(uTime * 45.0) * cos(uTime * 30.0) * 0.5 + 0.5);
                base_color += vec3(0.85, 0.95, 1.0) * uClimaxFlash * strobes * 0.45;
            }
        }
    }
    
    FragColor = vec4(base_color, 1.0);
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
out float vStyle; // 0.0 = Star/Spark, 1.0 = Smooth Gaseous Puff

uniform mat4 projection;
uniform mat4 view;

// High quality GPU hash function to generate a stable random seed [0, 1] per particle
float hash3(vec3 p) {
    return fract(sin(dot(p, vec3(12.9898, 78.233, 45.164))) * 43758.5453123);
}

void main() {
    vColor = aColor;
    vRand = hash3(aPos);
    vStyle = aSize < 0.0 ? 1.0 : 0.0;
    
    vec4 mvPos = view * vec4(aPos, 1.0);
    gl_Position = projection * mvPos;
    float dist = max(0.1, -mvPos.z);
    gl_PointSize = abs(aSize) * (42.0 / dist);
}
"""

PARTICLE_FRAGMENT_SHADER = """#version 300 es
precision mediump float;
in vec4 vColor;
in float vRand;
in float vStyle;
out vec4 FragColor;

uniform int uStarShape;

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
    
    if (vStyle > 0.5) {
        // Smooth gaseous puff with turbulent noise to form continuous smoke/clouds
        float t = r / 0.5;
        float noise = hash2(gl_PointCoord * (14.0 + vRand * 10.0) + vec2(vRand)) * 0.12;
        float alpha = pow(max(0.0, 1.0 - (r + noise) / 0.5), 2.2) * vColor.a;
        FragColor = vec4(vColor.rgb, alpha);
    } else {
        // Star/Spark style
        // Convert to polar coordinates
        float theta = atan(coord.y, coord.x);
        
        float max_r = 0.48;
        if (uStarShape == 1) {
            max_r = 0.48;
        } else if (uStarShape == 2 || uStarShape == 3) {
            float d_limit = (uStarShape == 2) ? 0.32 : 0.48;
            max_r = d_limit / (abs(cos(theta)) + abs(sin(theta)));
        } else if (uStarShape >= 4 && uStarShape <= 6) {
            float spikes_n = float(uStarShape);
            max_r = 0.28 + 0.20 * cos(spikes_n * (theta - 1.5707963));
        } else {
            // Default uStarShape == 0 (original organic spark)
            float spikes = 4.0 + floor(vRand * 4.0);
            float rotation = vRand * 6.28318;
            float flare1 = cos(theta * spikes + rotation);
            float flare2 = sin(theta * (spikes + 2.0) - rotation * 1.5);
            float flare_profile = 0.35 + 0.15 * flare1 + 0.05 * flare2;
            float edge_noise = hash2(coord * (10.0 + vRand * 50.0)) * 0.07;
            max_r = flare_profile - edge_noise;
        }
        
        if (r > max_r) {
            discard;
        }
        
        float t = r / max_r;
        float core = pow(1.0 - t, 4.0);
        float alpha = pow(1.0 - t, 1.5) * vColor.a;
        vec3 spark_color = mix(vColor.rgb, vec3(1.0, 1.0, 0.95), core * 0.85);
        spark_color += vec3(core * 0.40);
        FragColor = vec4(spark_color, alpha);
    }
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
    app = None
    def __init__(self, fw_type=None, color=None, x_offset=None):
        self.type = random.randint(0, 18) if fw_type is None else fw_type
        self.color = random.choice(COLOR_LIST) if color is None else color
        self.secondary_color = random.choice(COLOR_LIST)
        
        self.state = 'LAUNCH'
        
        if x_offset is None:
            x_offset = random.uniform(-10.0, 10.0)
        self.launch_pos = np.array([x_offset, -12.0, random.uniform(-6.0, 6.0)], dtype=np.float32)
        if Firework.app and Firework.app.opt_height_restrict:
            y_vel = random.uniform(21.0, 26.0)
        else:
            y_vel = random.uniform(10.0, 26.0)
            
        self.launch_vel = np.array([
            random.uniform(-2.0, 2.0),
            y_vel,
            random.uniform(-2.0, 2.0)
        ], dtype=np.float32)
        
        self.launch_age = 0.0
        self.launch_fuse = 999.0
        
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

        # Dynamic trailer override
        if Firework.app and Firework.app.opt_trailers > 0:
            self.history_len = Firework.app.opt_trailers * 3

        # Color palette override mapping
        if Firework.app and Firework.app.opt_color_mode != 'REALISTIC':
            pal = get_palette_colors(Firework.app.opt_color_mode)
            if pal:
                c1 = pal[random.randint(0, len(pal)-1)]
                c2 = pal[random.randint(0, len(pal)-1)]
                orig_c1 = np.array(self.color[:3], dtype=np.float32)
                orig_c2 = np.array(self.secondary_color[:3], dtype=np.float32)
                self.color = c1
                self.secondary_color = c2
                
                # Relabel colors already instantiated inside the type blocks
                if self.colors is not None:
                    diff1 = np.sum((self.colors[:, :3] - orig_c1)**2, axis=1)
                    diff2 = np.sum((self.colors[:, :3] - orig_c2)**2, axis=1)
                    closer_to_1 = diff1 <= diff2
                    noise = np.random.uniform(-0.05, 0.05, (len(self.colors), 3))
                    self.colors[closer_to_1, :3] = np.clip(np.array(c1[:3], dtype=np.float32) + noise[closer_to_1], 0.0, 1.0)
                    self.colors[~closer_to_1, :3] = np.clip(np.array(c2[:3], dtype=np.float32) + noise[~closer_to_1], 0.0, 1.0)
                    self.colors[:, 3] = 1.0

        self.history = np.zeros((self.history_len, num_particles, 3), dtype=np.float32)
        for h in range(self.history_len):
            self.history[h] = self.positions

    def update(self, dt):
        if self.state == 'DEAD':
            return
            
        if self.state == 'EXPLODE':
            # Adapt history on-the-fly to real-time keystroke switches
            if Firework.app and Firework.app.opt_trailers > 0:
                target_len = Firework.app.opt_trailers * 3
                if self.history_len != target_len or self.history is None or len(self.history) != target_len:
                    self.history_len = target_len
                    self.history = np.zeros((self.history_len, len(self.positions), 3), dtype=np.float32)
                    for h in range(self.history_len):
                        self.history[h] = self.positions

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
                    
                    self.history_len = Firework.app.opt_trailers * 3 if (Firework.app and Firework.app.opt_trailers > 0) else 3
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
                    
                    self.history_len = Firework.app.opt_trailers * 3 if (Firework.app and Firework.app.opt_trailers > 0) else 8
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
                    self.history_len = Firework.app.opt_trailers * 3 if (Firework.app and Firework.app.opt_trailers > 0) else 3
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
            
            grav_scale = Firework.app.opt_gravity if Firework.app else 1.0
            self.velocities[:, 1] -= self.gravity * grav_scale * dt
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



# =========================================================================
# Helper 3D Solid Mesh Generators for Visualizer Rarities
# =========================================================================

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


class UnifiedAudioPlayer:
    def __init__(self):
        self.mpv_process = None
        self.player_type = None # 'mpv' or 'sounddevice'
        self.start_time = 0.0
        self.audio_path = None
        self.sd_playing = False
        self.sd_duration = 0.0
        
    def play(self, filepath):
        self.stop()
        self.audio_path = filepath
        
        # 1. Try playing with MPV
        import shutil
        has_mpv = shutil.which("mpv") or os.path.exists("/usr/bin/mpv")
        if has_mpv:
            try:
                cmd = ["mpv" if shutil.which("mpv") else "/usr/bin/mpv", "--no-video", "--volume=100", filepath]
                self.mpv_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.player_type = 'mpv'
                self.start_time = time.time()
                print(f"Started playback of {filepath} using MPV subprocess.")
                return True
            except Exception as e:
                print(f"Failed to start mpv playback, falling back to sounddevice: {e}")
                
        # 2. Fall back to sounddevice + soundfile/audioread
        try:
            print(f"Decoding {filepath} for sounddevice playback...")
            import audio_analyzer
            data, fs = audio_analyzer.decode_audio(filepath)
            
            import sounddevice as sd
            sd.play(data, fs)
            self.player_type = 'sounddevice'
            self.start_time = time.time()
            self.sd_duration = len(data) / fs
            self.sd_playing = True
            print(f"Started playback of {filepath} using sounddevice backend.")
            return True
        except Exception as e:
            print(f"Failed to play audio with sounddevice: {e}")
            return False
            
    def stop(self):
        if self.player_type == 'mpv':
            if self.mpv_process:
                try:
                    self.mpv_process.terminate()
                    self.mpv_process.wait(timeout=1.0)
                except Exception:
                    try:
                        self.mpv_process.kill()
                    except Exception:
                        pass
                self.mpv_process = None
        elif self.player_type == 'sounddevice':
            try:
                import sounddevice as sd
                sd.stop()
            except Exception:
                pass
            self.sd_playing = False
        self.player_type = None
        self.start_time = 0.0
        
    def is_playing(self):
        if self.player_type == 'mpv':
            return self.mpv_process is not None and self.mpv_process.poll() is None
        elif self.player_type == 'sounddevice':
            if self.sd_playing:
                elapsed = time.time() - self.start_time
                if elapsed >= self.sd_duration:
                    self.sd_playing = False
                return self.sd_playing
            return False
        return False

    def get_elapsed_time(self):
        if self.player_type in ('mpv', 'sounddevice') and self.start_time > 0.0:
            return time.time() - self.start_time
        return 0.0


class FireworksApp:
    def __init__(self, record_path=None, audio_path=None, playlist_files=None, random_mode=False, tmp_dir=None):
        import tempfile
        self.tmp_dir = tmp_dir if tmp_dir else tempfile.gettempdir()
        self.audio_player = UnifiedAudioPlayer()
        Firework.app = self
        self.opt_trailers = 0        # 0: off, 1..10 range
        self.opt_gravity = 1.0       # 0.0 to 10.0 range
        self.opt_star_shape = 0      # 0: default, 1..6 shapes
        self.opt_color_mode = 'REALISTIC' # 'REALISTIC', 'NEON', 'TRANQUIL', 'METAL'
        self.opt_height_restrict = True
        self.mandala_slices = 12
        
        self.active_presets = [
            {
                "name": "Fireworks",
                "major_mode": "FIREWORKS",
                "show_rockets": True,
                "opt_color_mode": "REALISTIC",
                "opt_trailers": 0,
                "opt_gravity": 1.0,
                "opt_height_restrict": True,
                "opt_star_shape": 0
            },
            {
                "name": "Glory",
                "major_mode": "FIREWORKS",
                "show_rockets": False,
                "opt_color_mode": "NEON",
                "opt_trailers": 10,
                "opt_gravity": 0.0,
                "opt_height_restrict": False,
                "opt_star_shape": 2 # small diamonds
            },
            {
                "name": "Wormhole",
                "major_mode": "TUNNEL Wormhole",
                "show_rockets": True,
                "opt_color_mode": "REALISTIC",
                "opt_trailers": 0,
                "opt_gravity": 1.0,
                "opt_height_restrict": True,
                "opt_star_shape": 0
            },
            {
                "name": "Mandala",
                "major_mode": "MANDALA Sacred",
                "show_rockets": True,
                "opt_color_mode": "REALISTIC",
                "opt_trailers": 0,
                "opt_gravity": 1.0,
                "opt_height_restrict": True,
                "opt_star_shape": 0,
                "mandala_slices": 12
            },
            {
                "name": "Trance",
                "major_mode": "MANDALA Sacred",
                "show_rockets": True,
                "opt_color_mode": "TRANQUIL",
                "opt_trailers": 10,
                "opt_gravity": 0.5,
                "opt_height_restrict": False,
                "opt_star_shape": 2, # larger diamonds
                "mandala_slices": 4
            },
            {
                "name": "Underwater",
                "major_mode": "UNDERWATER Lava",
                "show_rockets": True,
                "opt_color_mode": "REALISTIC",
                "opt_trailers": 0,
                "opt_gravity": 1.0,
                "opt_height_restrict": True,
                "opt_star_shape": 0
            },
            {
                "name": "Synaesthesia",
                "major_mode": "SYNAESTHESIA Classic",
                "show_rockets": True,
                "opt_color_mode": "REALISTIC",
                "opt_trailers": 0,
                "opt_gravity": 1.0,
                "opt_height_restrict": True,
                "opt_star_shape": 5, # shape star (5 points)
                "syn_star_size": 0.25,
                "syn_fade_mode": "Wave"
            },
            {
                "name": "Random",
                "major_mode": None,
                "random_preset": True
            }
        ]
        self.preset_idx = 0
        self.preset_random_mode = random_mode
        self.preset_random_timer = 0.0
        
        self.syn_star_size = 0.5
        self.syn_fade_mode = "Stars"

        self.record_path = record_path
        self.is_recording = record_path is not None
        self.record_time = 0.0
        self.record_fps = 60
        self.record_dt = 1.0 / self.record_fps
        self.ffmpeg_process = None
        self.temp_video_path = "temp_recording.mp4"
        
        # Configure dynamic audio & display script path
        raw_paths = []
        if audio_path:
            raw_paths.append(audio_path)
        if playlist_files:
            raw_paths.extend(playlist_files)
            
        self.playlist = self.load_playlist_files(raw_paths) if raw_paths else ["01.Come Together - The Beatles.flac"]
        self.playlist_idx = 0
        self.audio_path = self.playlist[self.playlist_idx] if self.playlist else "01.Come Together - The Beatles.flac"
        self.audio_explicit = bool(raw_paths)
        self.script_path = self.get_mangled_script_path(self.audio_path)
        
        self.show_rockets = True
        self.show_legend = True

        self.fireworks = []
        self.routine_queue = []
        self.active_routine_name = ""
        self.routine_timer = 0.0
        
        self.camera_dist = 26.0
        self.camera_theta = 0.0
        self.camera_phi = 0.25
        self.auto_rotate = False
        
        self.start_time = time.time()
        self.last_time = time.time()
        self.react_bass_smooth = 0.0
        
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
        self.hood_vao = None
        self.hood_pos_vbo = None
        self.hood_col_vbo = None

        # Music Sync Playback State
        self.music_playing = False
        self.music_process = None
        self.playback_start_time = 0.0
        self.script_events = []
        self.next_event_idx = 0
        self.loaded_script_name = "None"
        self.script_duration = 0.0
        self.script_bpm = 120.0
        self.script_total_events = 0
        self.color_hints = []
        self.saved_auto_launch = True

        # Dynamic Psychedelic Modes
        self.modes = ["FIREWORKS", "TUNNEL Wormhole", "MANDALA Sacred", "UNDERWATER Lava", "SYNAESTHESIA Classic"]
        self.major_mode_idx = 0
        self.major_mode = self.modes[self.major_mode_idx]
        self.react_bass = 0.0
        self.react_mid = 0.0
        self.react_treble = 0.0
        self.current_stereo_panning = 0.0
        self.procedural_beat_timer = 0.0
        
        # Climax Events and BPM phase
        self.climax_flash = 0.0
        self.last_climax_trigger_time = 0.0
        self.tempo_phase = 0.0
        
        # Rarity system properties
        self.rarity_cooldown = random.randint(0, int(RARITY_INTERVAL))
        self.rarity_queued_type = None
        self.active_rarity = None
        self.current_rarity_cycle_name = "None"
        self.rarity_cycle_list = [
            "SQUID", "MANTA", "SEAHORSE", "LANTERN_FISH",
            "PLANET", "GALAXY", "ASTEROIDS",
            "CATHERINE_WHEEL",
            "BIRD", "SMOKE", "SUN_BURST", "BUTTERFLY"
        ]
        self.rarity_cycle_idx = -1
        self.lightning_active_timer = 0.0
        self.active_lightning_bolts = []
        self.wormhole_supernova_age = 0.0
        self.wormhole_supernova_active = False
        self.wormhole_shooting_star_active = False
        self.wormhole_shooting_star_x = 0.0
        self.wormhole_shooting_star_y = 0.0
        self.wormhole_shooting_star_z = 0.0
        self.peace_symbol_timer = 0.0
        self.halo_timer = 0.0

    def get_mangled_script_path(self, audio_path):
        if not audio_path:
            return ""
        import hashlib
        abs_path = os.path.abspath(audio_path)
        path_hash = hashlib.sha256(abs_path.encode('utf-8')).hexdigest()
        h1 = path_hash[0:2]
        h2 = path_hash[2:4]
        base_name = os.path.splitext(os.path.basename(abs_path))[0]
        safe_base = "".join(c if c.isalnum() or c in ('-', '_') else "_" for c in base_name)
        cached_dir = os.path.join(self.tmp_dir, "fireworks_cache", h1, h2)
        os.makedirs(cached_dir, exist_ok=True)
        return os.path.join(cached_dir, f"{safe_base}_{path_hash}.json")

    def load_playlist_files(self, paths):
        resolved = []
        audio_exts = ('.mp3', '.wav', '.ogg', '.opus', '.flac', '.m4a', '.aac')
        for p in paths:
            if not p or p.lower().endswith('.json'):
                continue
            if os.path.isdir(p):
                try:
                    for root, dirs, files in os.walk(p):
                        files.sort()
                        for f in files:
                            if f.lower().endswith(audio_exts):
                                resolved.append(os.path.join(root, f))
                except Exception as e:
                    print(f"Error scanning directory {p}: {e}")
            elif p.lower().endswith('.m3u'):
                if os.path.exists(p):
                    m3u_dir = os.path.dirname(os.path.abspath(p))
                    try:
                        with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith('#'):
                                    if not os.path.isabs(line):
                                        full_path = os.path.abspath(os.path.join(m3u_dir, line))
                                    else:
                                        full_path = line
                                    resolved.append(full_path)
                    except Exception as e:
                        print(f"Error reading playlist file {p}: {e}")
                else:
                    print(f"Playlist file {p} not found!")
            else:
                resolved.append(p)
        return resolved

    def load_and_play_track(self):
        if getattr(self, 'preset_random_mode', False) and getattr(self, 'preset_random_timer', 0.0) >= 45.0:
            print(f"[Random Mode] Triggering preset switch at start of track: {os.path.basename(self.audio_path) if self.audio_path else 'None'}")
            self.pick_random_preset()

        # 1. Stop current sync playback
        self.stop_sync_playback()
        
        # Clear existing visualizer events
        self.script_events = []
        self.next_event_idx = 0
        self.loaded_script_name = "None"
        self.update_legend_labels()
        
        if not self.audio_path or not os.path.exists(self.audio_path):
            print(f"Audio file not found: {self.audio_path}")
            return
            
        print(f"Loading and playing track: {self.audio_path}")
        
        # 2. Check if JSON script exists and is up-to-date
        json_exists = False
        import audio_analyzer
        if os.path.exists(self.script_path):
            try:
                with open(self.script_path, 'r') as f:
                    data = json.load(f)
                ver = data.get("metadata", {}).get("analyzer_version", 0)
                if ver >= audio_analyzer.ANALYZER_VERSION:
                    json_exists = True
            except Exception as e:
                print(f"Error checking JSON validity: {e}")
                
        # 3. Play audio IMMEDIATELY
        self.saved_auto_launch = self.auto_launch
        self.auto_launch = False
        self.fireworks.clear()
        
        try:
            if self.audio_player.play(self.audio_path):
                self.music_playing = True
                self.playback_start_time = time.time()
            else:
                raise RuntimeError("UnifiedAudioPlayer failed to play track")
        except Exception as e:
            print(f"Failed to start audio playback: {e}")
            self.auto_launch = self.saved_auto_launch
            self.update_legend_labels()
            return

        # 4. If JSON is valid, load it immediately and start sync
        if json_exists:
            print("Up-to-date JSON found. Loading immediately...")
            self.load_sync_script(self.script_path)
            self.next_event_idx = 0
            self.check_pregenerate_next_track()
        else:
            # 5. Otherwise, start asynchronous background generation
            print("No up-to-date JSON found. Starting background analysis thread...")
            import threading
            threading.Thread(target=self.async_analyze_and_activate, daemon=True).start()

    def async_analyze_and_activate(self):
        try:
            import audio_analyzer
            print(f"[Async Analyzer] Analyzing {self.audio_path} in background...")
            hints = getattr(self, 'color_hints', None) or ["strontium_red", "magnesium_white", "copper_blue"]
            script = audio_analyzer.analyze_audio(self.audio_path, hints)
            
            with open(self.script_path, 'w') as f:
                json.dump(script, f, indent=2)
            print(f"[Async Analyzer] Background analysis completed and saved to {self.script_path}")
            
            GLib.idle_add(self.activate_async_json, self.script_path)
        except Exception as e:
            print(f"[Async Analyzer] Error in background analysis: {e}")

    def activate_async_json(self, filepath):
        expected_script_path = self.get_mangled_script_path(self.audio_path)
        if filepath != expected_script_path:
            print(f"Background analysis finished for {filepath}, but active track has changed. Ignoring.")
            return False
            
        print(f"Activating asynchronously generated JSON: {filepath}")
        if self.load_sync_script(filepath):
            elapsed = time.time() - self.playback_start_time
            idx = 0
            while idx < len(self.script_events) and self.script_events[idx].get("time", 0.0) < elapsed:
                idx += 1
            self.next_event_idx = idx
            print(f"Choreography synced to elapsed play time: {elapsed:.2f}s (starting at event index {idx})")
            
            self.check_pregenerate_next_track()
            
        return False

    def check_pregenerate_next_track(self):
        if not self.playlist or len(self.playlist) <= 1:
            return
            
        next_idx = (self.playlist_idx + 1) % len(self.playlist)
        next_audio_path = self.playlist[next_idx]
        next_script_path = self.get_mangled_script_path(next_audio_path)
        
        json_exists = False
        import audio_analyzer
        if os.path.exists(next_script_path):
            try:
                with open(next_script_path, 'r') as f:
                    data = json.load(f)
                ver = data.get("metadata", {}).get("analyzer_version", 0)
                if ver >= audio_analyzer.ANALYZER_VERSION:
                    json_exists = True
            except Exception:
                pass
                
        if not json_exists:
            print(f"Pre-emptive Cache: Next track '{os.path.basename(next_audio_path)}' has no up-to-date JSON.")
            print(f"Starting pre-emptive background analysis for next track...")
            import threading
            threading.Thread(target=self.async_pregenerate_track, args=(next_audio_path, next_script_path), daemon=True).start()
        else:
            print(f"Pre-emptive Cache: Next track '{os.path.basename(next_audio_path)}' already has up-to-date JSON.")

    def async_pregenerate_track(self, audio_path, script_path):
        try:
            import audio_analyzer
            print(f"[Pre-emptive Analyzer] Pre-generating JSON for {audio_path} in background...")
            hints = ["strontium_red", "magnesium_white", "copper_blue"]
            script = audio_analyzer.analyze_audio(audio_path, hints)
            with open(script_path, 'w') as f:
                json.dump(script, f, indent=2)
            print(f"[Pre-emptive Analyzer] Finished pre-generating JSON for {audio_path}.")
        except Exception as e:
            print(f"[Pre-emptive Analyzer] Error pre-generating JSON for {audio_path}: {e}")

    def play_next_track(self):
        if not self.playlist:
            return
        next_idx = (self.playlist_idx + 1) % len(self.playlist)
        self.playlist_idx = next_idx
        self.audio_path = self.playlist[self.playlist_idx]
        self.script_path = self.get_mangled_script_path(self.audio_path)
        self.load_and_play_track()

    def play_previous_track(self):
        if not self.playlist:
            return
        prev_idx = (self.playlist_idx - 1) % len(self.playlist)
        self.playlist_idx = prev_idx
        self.audio_path = self.playlist[self.playlist_idx]
        self.script_path = self.get_mangled_script_path(self.audio_path)
        self.load_and_play_track()

    def apply_preset(self, idx):
        self.preset_idx = idx
        preset = self.active_presets[idx]
        
        if preset.get("random_preset"):
            self.preset_random_mode = True
            self.preset_random_timer = 0.0
            self.pick_random_preset()
        else:
            self.preset_random_mode = False
            self.apply_preset_settings(preset)

    def apply_preset_settings(self, preset):
        # Clear any active or queued rarity from previous modes
        self.active_rarity = None
        self.rarity_queued_type = None
        
        self.major_mode = preset["major_mode"]
        if self.major_mode in self.modes:
            self.major_mode_idx = self.modes.index(self.major_mode)
            
        if self.major_mode != "FIREWORKS":
            self.fireworks.clear()
            
        self.show_rockets = preset["show_rockets"]
        self.opt_color_mode = preset["opt_color_mode"]
        self.opt_trailers = preset["opt_trailers"]
        self.opt_gravity = preset["opt_gravity"]
        self.opt_height_restrict = preset["opt_height_restrict"]
        self.opt_star_shape = preset["opt_star_shape"]
        
        if self.major_mode == "SYNAESTHESIA Classic":
            if self.opt_star_shape in (1, 2, 3):
                self.syn_points_are_diamonds = True
            elif self.opt_star_shape in (4, 5, 6):
                self.syn_points_are_diamonds = False
        
        if "syn_star_size" in preset:
            self.syn_star_size = preset["syn_star_size"]
        if "syn_fade_mode" in preset:
            self.syn_fade_mode = preset["syn_fade_mode"]
            
        self.mandala_slices = preset.get("mandala_slices", 12)
        self.update_legend_labels()

    def pick_random_preset(self):
        self.preset_random_timer = 0.0
        candidates = list(range(len(self.active_presets) - 1))
        if hasattr(self, 'last_random_preset_idx') and self.last_random_preset_idx in candidates and len(candidates) > 1:
            candidates.remove(self.last_random_preset_idx)
        chosen_idx = random.choice(candidates)
        self.last_random_preset_idx = chosen_idx
        
        preset = self.active_presets[chosen_idx]
        print(f"RANDOM PRESET SWITCH: Switching to {preset['name']}!")
        self.apply_preset_settings(preset)

    def update_preset_random_timer(self, dt):
        if hasattr(self, 'preset_random_mode') and self.preset_random_mode:
            self.preset_random_timer += dt

    def get_sim_time(self):
        if hasattr(self, 'is_recording') and self.is_recording:
            return self.record_time
        return time.time() - self.start_time

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
        .hud-routine {
            font-family: 'Inter', 'Sans-Serif', sans-serif;
            font-size: 11px;
            font-weight: bold;
            color: #ffa834;
            margin-top: 3px;
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
        .hud-music-time {
            font-family: 'Inter', 'Monospace', monospace;
            font-size: 11px;
            font-weight: bold;
            color: #34c7f3;
            margin-top: 2px;
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
        
        self.hud_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.hud_box.set_valign(Gtk.Align.START)
        self.hud_box.set_halign(Gtk.Align.START)
        self.hud_box.set_margin_start(20)
        self.hud_box.set_margin_top(20)
        
        title_lbl = Gtk.Label(label="PYRO-ENGINE 3D")
        title_lbl.add_css_class("hud-title")
        title_lbl.set_halign(Gtk.Align.START)
        self.hud_box.append(title_lbl)
        
        sub_lbl = Gtk.Label(label="High-Performance OpenGL Screensaver")
        sub_lbl.add_css_class("hud-subtitle")
        sub_lbl.set_halign(Gtk.Align.START)
        self.hud_box.append(sub_lbl)
        
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
        
        self.routine_lbl = Gtk.Label(label="Routine: None")
        self.routine_lbl.add_css_class("hud-routine")
        self.routine_lbl.set_halign(Gtk.Align.START)
        stats_box.append(self.routine_lbl)
        
        self.hud_box.append(stats_box)

        # Beautiful Music Sync Panel
        music_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        music_box.set_margin_top(15)
        music_box.set_halign(Gtk.Align.START)
        
        music_hdr = Gtk.Label(label="MUSIC SYNCHRONIZER:")
        music_hdr.add_css_class("hud-legend-title")
        music_hdr.set_halign(Gtk.Align.START)
        music_box.append(music_hdr)
        
        self.music_track_lbl = Gtk.Label(label="Track: None")
        self.music_track_lbl.add_css_class("hud-stats")
        self.music_track_lbl.set_halign(Gtk.Align.START)
        music_box.append(self.music_track_lbl)
        
        self.music_time_lbl = Gtk.Label(label="Time: 00:00 / 00:00")
        self.music_time_lbl.add_css_class("hud-music-time")
        self.music_time_lbl.set_halign(Gtk.Align.START)
        music_box.append(self.music_time_lbl)
        
        self.music_section_lbl = Gtk.Label(label="Section: None")
        self.music_section_lbl.add_css_class("hud-stats")
        self.music_section_lbl.set_halign(Gtk.Align.START)
        music_box.append(self.music_section_lbl)
        
        self.hud_box.append(music_box)

        overlay.add_overlay(self.hud_box)
        
        self.legend_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.legend_box.add_css_class("hud-legend")
        self.legend_box.set_valign(Gtk.Align.END)
        self.legend_box.set_halign(Gtk.Align.START)
        self.legend_box.set_margin_start(20)
        self.legend_box.set_margin_bottom(20)
        
        leg_title = Gtk.Label(label="KEYBOARD CONTROLS:")
        leg_title.add_css_class("hud-legend-title")
        leg_title.set_halign(Gtk.Align.START)
        self.legend_box.append(leg_title)
        
        lbl_space = Gtk.Label(label="[SPACE]  - Play/Pause Sync Playback")
        lbl_space.set_halign(Gtk.Align.START)
        self.legend_box.append(lbl_space)

        lbl_return = Gtk.Label(label="[ENTER]  - Launch Manual Shell")
        lbl_return.set_halign(Gtk.Align.START)
        self.legend_box.append(lbl_return)
        
        self.lbl_auto_launch = Gtk.Label()
        self.lbl_auto_launch.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_auto_launch)
        
        self.lbl_auto_rotate = Gtk.Label()
        self.lbl_auto_rotate.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_auto_rotate)
        
        self.lbl_music = Gtk.Label()
        self.lbl_music.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_music)
        
        self.lbl_rockets_toggle = Gtk.Label()
        self.lbl_rockets_toggle.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_rockets_toggle)
        
        self.lbl_legend_toggle = Gtk.Label()
        self.lbl_legend_toggle.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_legend_toggle)

        self.lbl_mode_toggle = Gtk.Label()
        self.lbl_mode_toggle.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_mode_toggle)
        
        self.lbl_rarity_cycle = Gtk.Label()
        self.lbl_rarity_cycle.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_rarity_cycle)

        lbl_tweaks_title = Gtk.Label(label="\nOPTIONAL TWEAKS:")
        lbl_tweaks_title.add_css_class("hud-legend-title")
        lbl_tweaks_title.set_halign(Gtk.Align.START)
        self.legend_box.append(lbl_tweaks_title)
        
        self.lbl_opt_color = Gtk.Label()
        self.lbl_opt_color.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_opt_color)

        self.lbl_opt_shape = Gtk.Label()
        self.lbl_opt_shape.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_opt_shape)

        self.lbl_opt_gravity = Gtk.Label()
        self.lbl_opt_gravity.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_opt_gravity)

        self.lbl_opt_trailers = Gtk.Label()
        self.lbl_opt_trailers.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_opt_trailers)
        
        self.lbl_opt_height = Gtk.Label()
        self.lbl_opt_height.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_opt_height)
        
        self.lbl_mandala_slices = Gtk.Label()
        self.lbl_mandala_slices.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_mandala_slices)
        
        self.update_legend_labels()
        
        lbl_clear = Gtk.Label(label="[C]      - Clear Active Particles")
        lbl_clear.set_halign(Gtk.Align.START)
        self.legend_box.append(lbl_clear)
        
        lbl_fs = Gtk.Label(label="[F]      - Toggle Fullscreen")
        lbl_fs.set_halign(Gtk.Align.START)
        self.legend_box.append(lbl_fs)
        
        lbl_quit = Gtk.Label(label="[ESC/Q]  - Quit Screensaver")
        lbl_quit.set_halign(Gtk.Align.START)
        self.legend_box.append(lbl_quit)
        
        lbl_routines_title = Gtk.Label(label="\nCHOREOGRAPHED ROUTINES:")
        lbl_routines_title.add_css_class("hud-legend-title")
        lbl_routines_title.set_halign(Gtk.Align.START)
        self.legend_box.append(lbl_routines_title)
        
        self.lbl_r1 = Gtk.Label(label="[1]  - American Flag")
        self.lbl_r1.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_r1)
        
        self.lbl_r2 = Gtk.Label(label="[2]  - Liberty Bell")
        self.lbl_r2.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_r2)
        
        self.lbl_r3 = Gtk.Label(label="[3]  - Statue of Liberty")
        self.lbl_r3.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_r3)
        
        self.lbl_r4 = Gtk.Label(label="[4]  - Flower Bouquet")
        self.lbl_r4.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_r4)
        
        self.lbl_r5 = Gtk.Label(label="[5]  - The Dragon")
        self.lbl_r5.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_r5)
        
        self.lbl_r6 = Gtk.Label(label="[6]  - Supernova")
        self.lbl_r6.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_r6)
        
        self.lbl_r7 = Gtk.Label(label="[7]  - Shooting Star")
        self.lbl_r7.set_halign(Gtk.Align.START)
        self.legend_box.append(self.lbl_r7)
        
        overlay.add_overlay(self.legend_box)
        
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

        # File Drag and Drop Support
        try:
            drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
            drop_target.connect("drop", self.on_file_drop)
            self.win.add_controller(drop_target)
        except Exception as e:
            print(f"Failed to initialize Drag & Drop: {e}")

        # Context Menu Right-Click Gestures
        right_click = Gtk.GestureClick.new()
        right_click.set_button(3) # Right mouse button
        right_click.connect("pressed", self.on_right_click)
        self.gl_area.add_controller(right_click)
        
        GLib.timeout_add(16, self.on_tick)
        
        # Connect close-request signal to cleanly terminate background music
        self.win.connect("close-request", self.on_close_request)
        
        # Explicit audio script parsing & auto-start
        if self.preset_random_mode:
            self.apply_preset(len(self.active_presets) - 1)

        if self.is_recording:
            if not os.path.exists(self.script_path):
                print(f"No display script found for recording. Generating synchronously: {self.script_path}...")
                try:
                    import audio_analyzer
                    script = audio_analyzer.analyze_audio(self.audio_path, ["strontium_red", "magnesium_white", "copper_blue"])
                    with open(self.script_path, 'w') as f:
                        json.dump(script, f, indent=2)
                except Exception as e:
                    print(f"Failed to generate script for recording: {e}")
                    sys.exit(1)
            self.load_sync_script(self.script_path)
        else:
            # Play first track immediately (analyzes asynchronously in background if needed)
            GLib.idle_add(self.load_and_play_track)
            
        self.win.present()
        
        if self.audio_explicit:
            self.win.fullscreen()
            self.is_fullscreen = True
 
    def update_legend_labels(self):
        if hasattr(self, 'lbl_opt_color') and self.lbl_opt_color:
            self.lbl_opt_color.set_text(f"[O]      - Color Mode: {self.opt_color_mode}")
        if hasattr(self, 'lbl_opt_shape') and self.lbl_opt_shape:
            shapes_desc = {0: "Default", 1: "Circles", 2: "Small Diamonds", 3: "Larger Diamonds", 4: "4-Pt Stars", 5: "5-Pt Stars", 6: "6-Pt Stars"}
            self.lbl_opt_shape.set_text(f"[P]      - Star Shape: {shapes_desc.get(self.opt_star_shape, 'Default')}")
        if hasattr(self, 'lbl_opt_gravity') and self.lbl_opt_gravity:
            grav_desc = "OFF" if self.opt_gravity == 0.0 else f"{self.opt_gravity}x"
            self.lbl_opt_gravity.set_text(f"[G]      - Gravity: {grav_desc}")
        if hasattr(self, 'lbl_opt_trailers') and self.lbl_opt_trailers:
            trail_desc = "OFF" if self.opt_trailers == 0 else f"Len {self.opt_trailers}"
            self.lbl_opt_trailers.set_text(f"[L]      - Trailers: {trail_desc}")
        if hasattr(self, 'lbl_opt_height') and self.lbl_opt_height:
            height_desc = "ON" if self.opt_height_restrict else "OFF"
            self.lbl_opt_height.set_text(f"[Y]      - Height Restriction: {height_desc}")
        if hasattr(self, 'lbl_mandala_slices') and self.lbl_mandala_slices:
            self.lbl_mandala_slices.set_text(f"[S]      - Mandala Slices: {self.mandala_slices}")

        self.lbl_auto_launch.set_text(f"[A]      - Toggle Auto-Launcher ({'ON' if self.auto_launch else 'OFF'})")
        self.lbl_auto_rotate.set_text(f"[R]      - Toggle Camera Auto-Rotation ({'ON' if self.auto_rotate else 'OFF'})")
        if self.music_playing:
            self.lbl_music.set_text("[M]      - Toggle Music Sync (PLAYING)")
        elif len(self.script_events) > 0:
            self.lbl_music.set_text("[M]      - Toggle Music Sync (READY)")
        else:
            self.lbl_music.set_text("[M]      - Toggle Music Sync (NO SCRIPT)")
            
        if hasattr(self, 'lbl_rockets_toggle') and self.lbl_rockets_toggle:
            self.lbl_rockets_toggle.set_text(f"[T]      - Toggle Rockets ({'ON' if self.show_rockets else 'OFF'})")
        if hasattr(self, 'lbl_legend_toggle') and self.lbl_legend_toggle:
            self.lbl_legend_toggle.set_text("[H]      - Toggle Keyboard Controls HUD")
        if hasattr(self, 'lbl_mode_toggle') and self.lbl_mode_toggle:
            preset_name = self.active_presets[self.preset_idx]["name"]
            if getattr(self, 'preset_random_mode', False) and hasattr(self, 'last_random_preset_idx'):
                cur_preset = self.active_presets[self.last_random_preset_idx]["name"]
                self.lbl_mode_toggle.set_text(f"[V]      - Cycle Visual Mode: {preset_name} ({cur_preset})")
            else:
                self.lbl_mode_toggle.set_text(f"[V]      - Cycle Visual Mode: {preset_name}")
        if hasattr(self, 'lbl_rarity_cycle') and self.lbl_rarity_cycle:
            rarity_name = getattr(self, 'current_rarity_cycle_name', 'None')
            self.lbl_rarity_cycle.set_text(f"[K]      - Cycle Rarities ({rarity_name})")
            
        if hasattr(self, 'lbl_r1'):
            if self.major_mode == "FIREWORKS":
                self.lbl_r1.set_text("[1]  - American Flag")
                self.lbl_r2.set_text("[2]  - Liberty Bell")
                self.lbl_r3.set_text("[3]  - Statue of Liberty")
                self.lbl_r4.set_text("[4]  - Flower Bouquet")
                self.lbl_r5.set_text("[5]  - The Dragon")
            elif self.major_mode == "TUNNEL Wormhole":
                self.lbl_r1.set_text("[1]  - Plasma Burst")
                self.lbl_r2.set_text("[2]  - Gravity Surge")
                self.lbl_r3.set_text("[3]  - Stardust Stream")
                self.lbl_r4.set_text("[4]  - Event Horizon")
                self.lbl_r5.set_text("[5]  - Lightning Flash")
            elif self.major_mode == "UNDERWATER Lava":
                self.lbl_r1.set_text("[1]  - Coral Pulse")
                self.lbl_r2.set_text("[2]  - Geyser Eruption")
                self.lbl_r3.set_text("[3]  - Plankton Surge")
                self.lbl_r4.set_text("[4]  - Deep Vent Blast")
                self.lbl_r5.set_text("[5]  - Bioluminescent Rainbow")
            elif self.major_mode == "MANDALA Sacred":
                self.lbl_r1.set_text("[1]  - Lotus Bloom")
                self.lbl_r2.set_text("[2]  - Cosmic Spin")
                self.lbl_r3.set_text("[3]  - Infinite Pulse")
                self.lbl_r4.set_text("[4]  - Geometric Collapse")
                self.lbl_r5.set_text("[5]  - Astral Projection")
            elif self.major_mode == "SYNAESTHESIA Classic":
                shape_name = "Diamond" if getattr(self, 'syn_points_are_diamonds', True) else "Star"
                self.lbl_r1.set_text(f"[1]  - Shape: {shape_name}")
                self.lbl_r2.set_text(f"[2]  - Star Size: {getattr(self, 'syn_star_size', 0.5)}")
                self.lbl_r3.set_text(f"[3]  - Brightness: {getattr(self, 'syn_brightness', 0.35)}")
                self.lbl_r4.set_text(f"[4]  - Fade Mode: {getattr(self, 'syn_fade_mode', 'Stars')}")
                self.lbl_r5.set_text("[5]  - Trigger Star Burst")
                
        if hasattr(self, 'lbl_r6'):
            if self.major_mode == "MANDALA Sacred":
                self.lbl_r6.set_text("[6]  - Peace Symbol")
            elif self.major_mode == "SYNAESTHESIA Classic":
                self.lbl_r6.set_text("")
            else:
                self.lbl_r6.set_text("[6]  - Supernova")
        if hasattr(self, 'lbl_r7'):
            if self.major_mode == "MANDALA Sacred":
                self.lbl_r7.set_text("[7]  - Halo & Outward Sparks")
            elif self.major_mode == "SYNAESTHESIA Classic":
                self.lbl_r7.set_text("")
            else:
                self.lbl_r7.set_text("[7]  - Shooting Star")

    # =========================================================================
    # MODE 2: COSMIC WORMHOLE TUNNEL (Winding Plasma Tunnel Overhaul)
    # =========================================================================
    def init_tunnel_mode(self):
        # Curved path dynamics (serpentine tunnel path)
        self.wormhole_bend_x = 0.0
        self.wormhole_bend_y = 0.0
        self.target_bend_x = 0.0
        self.target_bend_y = 0.0
        self.wormhole_phase_x = 0.0
        self.wormhole_phase_y = 0.0
        self.tunnel_change_timer = 0.0

        # WALL GEMS (glowing crystal nodules - heavily reduced)
        N_gems = 15
        self.gem_z = np.random.uniform(-60.0, 10.0, N_gems).astype(np.float32)
        self.gem_angle = np.random.uniform(0.0, 2 * np.pi, N_gems).astype(np.float32)
        self.gem_base_radius = np.random.uniform(7.5, 9.5, N_gems).astype(np.float32)
        self.gem_col = np.zeros((N_gems, 4), dtype=np.float32)
        for i in range(N_gems):
            self.gem_col[i] = random.choice([
                (1.0, 0.2, 0.2, 1.0),   # Ruby
                (0.2, 1.0, 0.4, 1.0),   # Emerald
                (0.15, 0.5, 1.0, 1.0),  # Sapphire
                (0.95, 0.95, 1.0, 1.0), # Diamond
                (1.0, 0.75, 0.05, 1.0)  # Topaz
            ])
        self.gem_size = np.random.uniform(11.0, 17.0, N_gems).astype(np.float32)

        # WALL GEMS SPARKS SYSTEM (Preallocated spark particle pool)
        N_sparks = 900
        self.spark_pos = np.zeros((N_sparks, 3), dtype=np.float32)
        self.spark_vel = np.zeros((N_sparks, 3), dtype=np.float32)
        self.spark_col = np.zeros((N_sparks, 4), dtype=np.float32)
        self.spark_size = np.zeros(N_sparks, dtype=np.float32)
        self.spark_age = np.zeros(N_sparks, dtype=np.float32)
        self.spark_max_age = np.ones(N_sparks, dtype=np.float32)
        self.spark_active = np.zeros(N_sparks, dtype=np.bool_)
        self.next_spark_idx = 0

    def update_tunnel(self, dt):
        # Constant, elegant forward travel camera speed (completely eliminates motion jerking)
        speed = 8.5 * dt
        self.gem_z += speed
        
        gem_passed = self.gem_z > 10.0
        num_gem_passed = np.sum(gem_passed)
        if num_gem_passed > 0:
            self.gem_z[gem_passed] = np.random.uniform(-60.0, -50.0, num_gem_passed).astype(np.float32)
            self.gem_angle[gem_passed] = np.random.uniform(0.0, 2 * np.pi, num_gem_passed).astype(np.float32)
            
        # Smooth wall spin speed
        spin_speed = (0.12 + self.react_mid * 0.4) * dt
        self.gem_angle += spin_speed * 0.8
        
        # Update curving serpentine bend coordinates
        self.wormhole_phase_x += (0.4 + self.react_bass * 0.5) * dt
        self.wormhole_phase_y += (0.25 + self.react_mid * 0.3) * dt
        
        # Music drops trigger gentle serpentine shifting
        self.tunnel_change_timer += dt
        if (self.react_bass > 1.25 and random.random() < 0.12) or self.tunnel_change_timer > 5.5:
            self.tunnel_change_timer = 0.0
            self.target_bend_x = np.random.uniform(-3.0, 3.0)
            self.target_bend_y = np.random.uniform(-3.0, 3.0)
            
        # Smooth transitions
        self.wormhole_bend_x += (self.target_bend_x - self.wormhole_bend_x) * dt * 1.5
        self.wormhole_bend_y += (self.target_bend_y - self.wormhole_bend_y) * dt * 1.5
        
        # Treble triggers gem spark burst emissions
        if self.react_treble > 0.4 or random.random() < 0.15:
            near_gems = np.where((self.gem_z < -5.0) & (self.gem_z > -45.0))[0]
            if len(near_gems) > 0:
                g_idx = random.choice(near_gems)
                self.spawn_gem_sparks(g_idx)
                
        # Update Sparks
        active_sparks = self.spark_active
        if np.any(active_sparks):
            self.spark_pos[active_sparks] += self.spark_vel[active_sparks] * dt
            self.spark_age[active_sparks] += dt
            
            expired = (self.spark_age >= self.spark_max_age) & active_sparks
            self.spark_active[expired] = False
            
            self.spark_col[active_sparks, 3] = np.clip(
                1.0 - self.spark_age[active_sparks] / self.spark_max_age[active_sparks], 0.0, 1.0
            )

    def spawn_gem_sparks(self, g_idx):
        gz = self.gem_z[g_idx]
        g_angle = self.gem_angle[g_idx]
        g_rad = self.gem_base_radius[g_idx]
        g_color = self.gem_col[g_idx]
        
        gx = g_rad * np.cos(g_angle)
        gy = g_rad * np.sin(g_angle)
        
        num_sparks_spawn = 6
        for _ in range(num_sparks_spawn):
            idx = self.next_spark_idx
            self.spark_pos[idx] = [gx, gy, gz]
            
            rad_speed = np.random.uniform(-14.0, -3.0)
            tan_speed = np.random.uniform(-5.0, 5.0)
            z_speed = np.random.uniform(-18.0, 6.0)
            
            cos_a = np.cos(g_angle)
            sin_a = np.sin(g_angle)
            
            vx = rad_speed * cos_a - tan_speed * sin_a
            vy = rad_speed * sin_a + tan_speed * cos_a
            vz = z_speed
            
            self.spark_vel[idx] = [vx, vy, vz]
            self.spark_col[idx] = [g_color[0], g_color[1], g_color[2], 1.0]
            self.spark_size[idx] = np.random.uniform(5.0, 9.0)
            self.spark_age[idx] = 0.0
            self.spark_max_age[idx] = np.random.uniform(0.4, 0.9)
            self.spark_active[idx] = True
            
            self.next_spark_idx = (self.next_spark_idx + 1) % len(self.spark_pos)

    def get_bend_offsets(self, z_arr):
        bx = self.wormhole_bend_x * np.sin(z_arr * 0.06 + self.wormhole_phase_x)
        by = self.wormhole_bend_y * np.cos(z_arr * 0.06 + self.wormhole_phase_y)
        return bx, by

    def render_tunnel(self):
        get_bend_offsets = self.get_bend_offsets
            
        hood_tri_pos = []
        hood_tri_col = []
        
        # Render Gems with fog
        gbx, gby = get_bend_offsets(self.gem_z)
        gx = self.gem_base_radius * np.cos(self.gem_angle) + gbx
        gy = self.gem_base_radius * np.sin(self.gem_angle) + gby + 4.0
        gz = self.gem_z
        
        gem_col_arr = self.gem_col.copy()
        gem_col_arr[:, 3] *= np.clip((gz + 60.0) / 60.0, 0.0, 1.0)
        
        # Render active sparks
        active_mask = self.spark_active
        num_act = np.sum(active_mask)
        
        # Gather additional backdrop particles (Aurora, Planet, Galaxy, Asteroids, Supernova)
        aurora_pos = []
        aurora_col = []
        aurora_size = []
        time_val = self.get_sim_time()
        
        # 1. CONTINUOUS BACKGROUND AURORA BOREALIS OUTSIDE TUNNEL WALLS (extremely transparent)
        for i_strip in range(15):
            ang = (i_strip / 14.0) * np.pi * 0.8 + np.pi * 0.1 # cover top half & sides
            for p_idx in range(25):
                z_coord = -55.0 + p_idx * 2.5
                bx, by = get_bend_offsets(z_coord)
                R_aur = 11.5 + np.sin(ang * 4.0 + time_val * 1.5) * np.cos(z_coord * 0.07 - time_val * 0.8) * 1.3
                px = R_aur * np.cos(ang) + bx
                py = R_aur * np.sin(ang) + by + 4.0
                pz = z_coord
                
                ang_f = abs(ang - np.pi / 2.0) / (np.pi / 2.0)
                # Blend from vibrant neon emerald-green to purple-pink outer sheets
                col_r = 0.1 * (1.0 - ang_f) + 0.75 * ang_f
                col_g = 0.95 * (1.0 - ang_f) + 0.1 * ang_f
                col_b = 0.35 * (1.0 - ang_f) + 0.9 * ang_f
                
                fog_factor = np.clip((z_coord + 50.0) / 50.0, 0.0, 1.0)
                alpha = 0.32 * fog_factor * (0.32 + self.react_mid * 0.68) * (1.0 - ang_f * 0.2)
                
                aurora_pos.append([px, py, pz])
                aurora_col.append([col_r, col_g, col_b, alpha])
                aurora_size.append(5.0)
                
        # 2. PLANET RARITY (solid 3D rocky sphere with tilting rings)
        if self.active_rarity is not None and self.active_rarity['type'] == 'PLANET':
            r = self.active_rarity
            p_pts, p_cols = make_rocky_planet(r['pos'], 2.3, r['phase'], r.get('style', 'JUPITER'))
            # Apply bend offsets to planet triangles before buffering
            bent_pts = []
            for pt in p_pts:
                bx, by = get_bend_offsets(pt[2])
                bent_pts.append([pt[0] + bx, pt[1] + by + 4.0, pt[2]])
            hood_tri_pos.extend(bent_pts)
            hood_tri_col.extend(p_cols)
                
        # 3. GALAXY RARITY (spiral structure outside tunnel)
        if self.active_rarity is not None and self.active_rarity['type'] == 'GALAXY':
            r = self.active_rarity
            center = r['pos']
            for i_g in range(160):
                t_frac = i_g / 160.0
                rad = 0.3 + t_frac * 4.5
                arm_ang = t_frac * 16.0 + (np.pi if i_g % 2 == 0 else 0.0) + r['phase']
                rx = rad * np.cos(arm_ang)
                ry = rad * np.sin(arm_ang) * 0.4
                rz = np.sin(arm_ang * 2.0) * 0.2
                p_world = center + np.array([rx, ry, rz])
                bx, by = get_bend_offsets(p_world[2])
                px = p_world[0] + bx
                py = p_world[1] + by + 4.0
                pz = p_world[2]
                # Adjust fog boundary specifically for Galaxy since it starts at Z = -85.0
                fog_factor = np.clip((pz + 85.0) / 60.0, 0.0, 1.0)
                alpha = (1.0 - t_frac * 0.5) * (0.6 + np.sin(time_val * 6.0 + i_g) * 0.3) * fog_factor
                if t_frac < 0.15:
                    col = [1.0, 0.85, 1.0, alpha] # Core starburst
                    size_pt = 12.0
                elif i_g % 2 == 0:
                    col = [0.15, 0.7, 1.0, alpha] # Cyan spiral arm
                    size_pt = 6.0
                else:
                    col = [0.95, 0.2, 0.75, alpha] # Magenta spiral arm
                    size_pt = 6.0
                aurora_pos.append([px, py, pz])
                aurora_col.append(col)
                aurora_size.append(size_pt)
                
        # 4. ASTEROIDS RARITY (tumbling rocks drifting past as solid 3D meshes)
        if self.active_rarity is not None and self.active_rarity['type'] == 'ASTEROIDS':
            r = self.active_rarity
            center = r['pos']
            for k in range(len(r['offsets'])):
                ast_pos = center + r['offsets'][k]
                rot = r['rotations'][k]
                rad_ast = 0.55 + 0.15 * np.sin(k * 4.0)
                a_pts, a_cols = make_3d_asteroid(ast_pos, rad_ast, rot)
                for pt, col in zip(a_pts, a_cols):
                    bx, by = get_bend_offsets(pt[2])
                    px = pt[0] + bx
                    py = pt[1] + by + 4.0
                    pz = pt[2]
                    fog_factor = np.clip((pz + 50.0) / 50.0, 0.0, 1.0)
                    c_fog = [col[0], col[1], col[2], col[3] * fog_factor]
                    hood_tri_pos.append([px, py, pz])
                    hood_tri_col.append(c_fog)
                    
        # 5. REAL SUPERNOVA SHOCKWAVE EXPANSION SHELL (Blinding core with filaments)
        if self.wormhole_supernova_active:
            r_shock = self.wormhole_supernova_age * 16.0
            center_z = -50.0
            for i_sn in range(160):
                lat = (i_sn / 160.0) * np.pi - np.pi / 2.0
                lon = (i_sn * 2.39996) % (2.0 * np.pi)
                turb = 1.0 + 0.12 * np.sin(lon * 5.0 + self.wormhole_supernova_age * 12.0)
                
                lx = np.cos(lat) * np.cos(lon) * turb
                ly = np.cos(lat) * np.sin(lon) * turb
                lz = np.sin(lat) * turb
                p_world = np.array([lx, ly, lz]) * r_shock
                p_world[2] += center_z
                
                bx, by = get_bend_offsets(p_world[2])
                px = p_world[0] + bx
                py = p_world[1] + by + 4.0
                pz = p_world[2]
                
                alpha = np.clip(1.0 - (self.wormhole_supernova_age / 3.5), 0.0, 1.0)
                if self.wormhole_supernova_age < 0.6:
                    col = [1.0, 0.95, 0.85, alpha] # Blinding hot white core flash
                    size_pt = 14.0
                elif i_sn % 3 == 0:
                    col = [1.0, 0.5, 0.1, alpha] # Fiery orange expanding shell gas
                    size_pt = 10.0
                elif i_sn % 3 == 1:
                    col = [0.1, 0.85, 1.0, alpha] # Cyan shock border
                    size_pt = 8.0
                else:
                    col = [0.95, 0.15, 0.5, alpha] # Magenta glowing filaments
                    size_pt = 9.0
                aurora_pos.append([px, py, pz])
                aurora_col.append(col)
                aurora_size.append(size_pt)
                
        # 6. MASSIVE FLY-BY SHOOTING STAR HEAD
        if self.wormhole_shooting_star_active:
            bx, by = get_bend_offsets(self.wormhole_shooting_star_z)
            px = self.wormhole_shooting_star_x + bx
            py = self.wormhole_shooting_star_y + by + 4.0
            pz = self.wormhole_shooting_star_z
            fog_factor = np.clip((pz + 50.0) / 50.0, 0.0, 1.0)
            aurora_pos.append([px, py, pz])
            aurora_col.append([1.0, 1.0, 1.0, 1.0 * fog_factor])
            aurora_size.append(16.0)
            
        if num_act > 0:
            sp_pos = self.spark_pos[active_mask].copy()
            sbx, sby = get_bend_offsets(sp_pos[:, 2])
            sp_pos[:, 0] += sbx
            sp_pos[:, 1] += sby + 4.0
            
            sp_col = self.spark_col[active_mask]
            sp_size = self.spark_size[active_mask]
            
            pos_combined = np.concatenate([
                np.stack([gx, gy, gz], axis=1),
                sp_pos
            ], axis=0).astype(np.float32)
            
            col_combined = np.concatenate([
                gem_col_arr,
                sp_col
            ], axis=0).astype(np.float32)
            
            size_combined = np.concatenate([
                self.gem_size * (1.1 + self.react_treble * 0.8),
                sp_size
            ], axis=0).astype(np.float32)
        else:
            pos_combined = np.stack([gx, gy, gz], axis=1).astype(np.float32)
            col_combined = gem_col_arr.astype(np.float32)
            size_combined = (self.gem_size * (1.1 + self.react_treble * 0.8)).astype(np.float32)
            
        if len(aurora_pos) > 0:
            pos_combined = np.concatenate([pos_combined, np.array(aurora_pos, dtype=np.float32)], axis=0)
            col_combined = np.concatenate([col_combined, np.array(aurora_col, dtype=np.float32)], axis=0)
            size_combined = np.concatenate([size_combined, np.array(aurora_size, dtype=np.float32)], axis=0)
            
        return pos_combined, col_combined, size_combined, np.array(hood_tri_pos, dtype=np.float32), np.array(hood_tri_col, dtype=np.float32)

    def get_tangential_jelly_dir(self, pos):
        # Calculate camera look/position to target [0, 4, 0]
        cx = self.camera_dist * np.cos(self.camera_phi) * np.sin(self.camera_theta)
        cy = self.camera_dist * np.sin(self.camera_phi)
        cz = self.camera_dist * np.cos(self.camera_phi) * np.cos(self.camera_theta)
        cam_pos = np.array([cx, cy, cz], dtype=np.float32)
        v_view = pos - cam_pos
        dist = np.linalg.norm(v_view)
        if dist < 1e-4:
            v_view = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        else:
            v_view = v_view / dist
        
        # Perpendicular vector 1
        if abs(v_view[0]) > 0.9:
            v_perp1 = np.array([v_view[1], -v_view[0], 0.0], dtype=np.float32)
        else:
            v_perp1 = np.array([0.0, v_view[2], -v_view[1]], dtype=np.float32)
        v_perp1 /= np.linalg.norm(v_perp1)
        
        # Perpendicular vector 2
        v_perp2 = np.cross(v_view, v_perp1)
        v_perp2 /= np.linalg.norm(v_perp2)
        
        # Angle in the plane perpendicular to view
        alpha = np.random.uniform(0.0, 2 * np.pi)
        # Angle out of plane (clamped to 30 degrees = pi / 6)
        beta = np.random.uniform(-np.pi / 6.0, np.pi / 6.0)
        
        v_plane = np.cos(alpha) * v_perp1 + np.sin(alpha) * v_perp2
        jelly_dir = v_plane * np.cos(beta) + v_view * np.sin(beta)
        
        # Ensure the jellyfish swims generally upwards (positive y)
        if jelly_dir[1] < 0:
            jelly_dir = -jelly_dir
            
        jelly_dir /= np.linalg.norm(jelly_dir)
        return jelly_dir

    # =========================================================================
    # MODE 3: BIOLUMINESCENT UNDERWATER DEEP-SEA LAVA LAMP
    # =========================================================================
    def init_underwater_mode(self):
        N_bubbles = 2500
        self.bubble_pos = np.zeros((N_bubbles, 3), dtype=np.float32)
        self.bubble_vel = np.zeros((N_bubbles, 3), dtype=np.float32)
        self.bubble_col = np.zeros((N_bubbles, 4), dtype=np.float32)
        self.bubble_size = np.zeros(N_bubbles, dtype=np.float32)
        self.bubble_phase = np.zeros(N_bubbles, dtype=np.float32)
        self.bubble_active = np.zeros(N_bubbles, dtype=np.bool_)
        self.bubble_is_fragment = np.zeros(N_bubbles, dtype=np.bool_)
        self.next_bubble_idx = 0
        self.vent_locs = [
            [-3.0, -2.5, 6.0],   # Left Foreground Vent (raised and brought closer)
            [0.0, -2.5, 4.0],    # Center Foreground Vent (raised and brought closer)
            [3.0, -2.5, 7.0]     # Right Foreground Vent (raised and brought closer)
        ]

        N_algae = 1500
        self.algae_pos = np.random.uniform(
            [-10.0, -2.5, -5.0], [10.0, 9.0, 12.0], (N_algae, 3)
        ).astype(np.float32)
        self.algae_phase = np.random.uniform(0.0, 2 * np.pi, (N_algae, 3)).astype(np.float32)
        self.algae_col = np.zeros((N_algae, 4), dtype=np.float32)
        for i in range(N_algae):
            self.algae_col[i] = random.choice([
                (0.1, 0.95, 0.4, 0.5), # Emerald Green
                (0.1, 0.7, 1.0, 0.5),  # Cyan
                (0.35, 0.15, 1.0, 0.5) # Neon Violet
            ])
        self.algae_size = np.random.uniform(2.5, 6.0, N_algae).astype(np.float32)

        # Irregular Stalagmites Volcanic Vents 3D Geometry Setup (Taller and rugged)
        # 3 vents, 6 rings of height, 4 points per ring = 72 points
        self.num_vent_pts = 72
        self.vent_pts_pos = np.zeros((self.num_vent_pts, 3), dtype=np.float32)
        self.vent_pts_col = np.zeros((self.num_vent_pts, 4), dtype=np.float32)
        self.vent_pts_size = np.zeros(self.num_vent_pts, dtype=np.float32)
        
        idx = 0
        for v_loc in self.vent_locs:
            ruggedness_seed = [np.random.uniform(0.8, 1.2, 4) for _ in range(6)]
            for ring in range(6):
                y_offset = ring * 0.35 # Height off seabed
                rad = 1.05 - ring * 0.17 # Stalagmite chimney tapers upward
                if ring == 5:
                    rad = 0.3 # narrow crater opening
                    
                num_ring_pts = 4
                for p in range(num_ring_pts):
                    angle = (p * 2 * np.pi / num_ring_pts) + ring * 0.4
                    r_jit = rad * ruggedness_seed[ring][p]
                    vx = v_loc[0] + r_jit * np.cos(angle) + np.random.uniform(-0.06, 0.06)
                    vy = v_loc[1] + y_offset + np.random.uniform(-0.04, 0.04)
                    vz = v_loc[2] + r_jit * np.sin(angle) + np.random.uniform(-0.06, 0.06)
                    
                    self.vent_pts_pos[idx] = [vx, vy, vz]
                    if ring == 5:
                        self.vent_pts_col[idx] = [0.1, 0.95, 1.0, 0.95] # Hot cyan lip
                        self.vent_pts_size[idx] = 13.0
                    else:
                        self.vent_pts_col[idx] = [0.10, 0.14, 0.20, 0.85]
                        self.vent_pts_size[idx] = 18.0 - ring * 2.2
                    idx += 1

        # Textured Sandy/Rocky Sea Floor Setup (Replacing computer grid lines)
        self.num_seabed_pts = 1500
        self.seabed_pos = np.zeros((self.num_seabed_pts, 3), dtype=np.float32)
        self.seabed_col = np.zeros((self.num_seabed_pts, 4), dtype=np.float32)
        self.seabed_size = np.zeros(self.num_seabed_pts, dtype=np.float32)
        
        self.seabed_pos[:, 0] = np.random.uniform(-16.0, 16.0, self.num_seabed_pts)
        self.seabed_pos[:, 1] = -2.5 + np.random.uniform(-0.15, 0.15, self.num_seabed_pts)
        self.seabed_pos[:, 2] = np.random.uniform(-5.0, 15.0, self.num_seabed_pts)
        
        for i in range(self.num_seabed_pts):
            self.seabed_col[i] = random.choice([
                (0.24, 0.18, 0.12, 0.75),  # Deep sand gold-brown
                (0.32, 0.26, 0.18, 0.70),  # Soft sandy beige
                (0.12, 0.14, 0.18, 0.85),  # Dark basalt stone
                (0.10, 0.22, 0.14, 0.65)   # Moss/Algae-covered rock
            ])
            self.seabed_size[i] = np.random.uniform(-4.0, -12.0)

        # Bioluminescent Waving Seaweed / Marine Plants Setup
        self.num_plants = 20
        self.plant_base = np.random.uniform([-10.0, -2.5, -5.0], [10.0, -2.5, 12.0], (self.num_plants, 3)).astype(np.float32)
        self.plant_phase = np.random.uniform(0.0, 2 * np.pi, self.num_plants).astype(np.float32)
        self.plant_color = np.zeros((self.num_plants, 3), dtype=np.float32)
        for i in range(self.num_plants):
            self.plant_color[i] = random.choice([
                (0.12, 0.90, 0.35), # Emerald Mint Seaweed
                (0.05, 0.75, 0.85), # Glowing Teal Seaweed
                (0.70, 0.95, 0.15)  # Neon Yellow-Green Kelp
            ])

        # Overhauled Pulsing 3D Jellyfish (Halved to 5 individuals representing Moon and Crystal)
        self.num_jelly = 5
        self.jelly_pos = np.zeros((self.num_jelly, 3), dtype=np.float32)
        self.jelly_dir = np.zeros((self.num_jelly, 3), dtype=np.float32)
        self.jelly_vel = np.zeros((self.num_jelly, 3), dtype=np.float32)
        self.jelly_col = np.zeros((self.num_jelly, 4), dtype=np.float32)
        self.jelly_size = np.zeros(self.num_jelly, dtype=np.float32)
        self.jelly_phase = np.zeros(self.num_jelly, dtype=np.float32)
        self.jelly_species = np.array([i % 2 for i in range(self.num_jelly)], dtype=np.int32)
        
        for i in range(self.num_jelly):
            self.jelly_pos[i] = [
                np.random.uniform(-6.0, 6.0),
                np.random.uniform(-1.5, 8.0),
                np.random.uniform(-2.0, 12.0)
            ]
            # Restrict swimming direction to 90 degrees +/- 30 degrees relative to camera view
            self.jelly_dir[i] = self.get_tangential_jelly_dir(self.jelly_pos[i])
            
            sp = self.jelly_species[i]
            if sp == 0:     # Moon Jelly (lavender-pink translucent)
                self.jelly_col[i] = (0.85, 0.65, 0.95, 1.0)
                self.jelly_size[i] = np.random.uniform(22.0, 28.0)
            else:           # Crystal Jelly (cyan-blue highly transparent)
                self.jelly_col[i] = (0.0, 0.85, 1.0, 1.0)
                self.jelly_size[i] = np.random.uniform(20.0, 26.0)
                
            self.jelly_phase[i] = np.random.uniform(0.0, 2 * np.pi)
            
        # Glowing 3D Animated Squid initialization
        self.squid_pos = np.array([0.0, 3.0, 5.0], dtype=np.float32)
        self.squid_dir = np.array([1.0, 0.1, 0.0], dtype=np.float32)
        self.squid_dir /= np.linalg.norm(self.squid_dir)
        self.squid_vel = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.squid_phase = 0.0
        self.squid_jet_cooldown = 0.0
            
        # Initialize plankton and seabed phosphorescence twinkling states
        self.algae_twinkle_phase = np.random.uniform(0.0, 2 * np.pi, N_algae).astype(np.float32)
        self.seabed_twinkle_phase = np.random.uniform(0.0, 2 * np.pi, self.num_seabed_pts).astype(np.float32)
        self.seabed_is_glowing = (np.random.rand(self.num_seabed_pts) < 0.28) # 28% of seabed points glow


    def update_underwater(self, dt):
        # Spawn bubbles based on volume hits and frequencies
        num_to_spawn = 0
        is_treble_heavy = False
        
        # Determine peak activity
        max_react = max(self.react_bass, self.react_mid, self.react_treble)
        
        if max_react > 0.3:
            # High volume hit: release significantly more bubbles!
            if self.react_treble > self.react_bass:
                is_treble_heavy = True
                # Treble hit: spawn MANY tiny, fast bubbles (up to 32 bubbles for intense peaks)
                num_to_spawn = int(2 + (self.react_treble ** 1.8) * 30.0)
            else:
                # Bass hit: spawn FEWER giant, slow bubbles (up to 10 bubbles)
                num_to_spawn = int(1 + (self.react_bass ** 1.8) * 9.0)
                
            # Add some randomness to keep the pattern uneven
            if random.random() > 0.85:
                num_to_spawn = int(num_to_spawn * 0.5)
        else:
            # Occasional light trickle when music is quiet
            if random.random() < 0.12:
                num_to_spawn = random.choice([1, 2])
                is_treble_heavy = random.random() < 0.5
                    
        num_to_spawn = min(num_to_spawn, 35) # Cap to avoid overloading
        
        for _ in range(num_to_spawn):
            idx = self.next_bubble_idx
            
            # Determine spout index biased by stereo panning
            p = getattr(self, 'current_stereo_panning', 0.0)
            p_left = max(0.05, 0.33 - 0.5 * p)
            p_right = max(0.05, 0.33 + 0.5 * p)
            p_center = max(0.05, 1.0 - p_left - p_right)
            total = p_left + p_center + p_right
            probs = [p_left / total, p_center / total, p_right / total]
            v_idx = np.random.choice([0, 1, 2], p=probs)
            v_loc = self.vent_locs[v_idx]
            
            # Bubbles rise directly from the open stalagmite mouths (y_offset=1.75)
            self.bubble_pos[idx] = [v_loc[0], v_loc[1] + 1.75, v_loc[2]] + np.random.uniform([-0.25, 0.0, -0.25], [0.25, 0.15, 0.25])
            
            # Compute a frequency-dependent reactive color
            tot_energy = self.react_bass + self.react_mid + self.react_treble + 1e-5
            fb = self.react_bass / tot_energy
            fm = self.react_mid / tot_energy
            ft = self.react_treble / tot_energy
            
            # Blend colors: Bass (deep blue/magenta), Mid (teal/green), Treble (cyan/white)
            r_c = fb * 0.05 + fm * 0.1 + ft * 0.7
            g_c = fb * 0.35 + fm * 0.9 + ft * 0.9
            b_c = fb * 1.0 + fm * 0.5 + ft * 1.0
            r_c = np.clip(r_c + np.random.uniform(-0.05, 0.05), 0.0, 1.0)
            g_c = np.clip(g_c + np.random.uniform(-0.05, 0.05), 0.0, 1.0)
            b_c = np.clip(b_c + np.random.uniform(-0.05, 0.05), 0.0, 1.0)
            alpha = np.clip(0.3 * fb + 0.6 * fm + 0.85 * ft + np.random.uniform(-0.1, 0.1), 0.25, 0.95)

            if is_treble_heavy:
                # Treble: tiny, fast bubbles
                self.bubble_size[idx] = np.random.uniform(1.2, 2.5)
                rise_speed = np.random.uniform(1.6, 2.8) * (1.0 + self.react_treble * 0.3)
                self.bubble_vel[idx] = [
                    np.random.uniform(-0.5, 0.5),
                    rise_speed,
                    np.random.uniform(-0.5, 0.5)
                ]
                # Frequency-reactive bubble color
                self.bubble_col[idx] = [r_c, g_c, b_c, alpha]
            else:
                # Bass: fewer, bigger, slower bubbles
                self.bubble_size[idx] = np.random.uniform(5.5, 9.0)
                rise_speed = np.random.uniform(0.6, 1.2) * (1.0 + self.react_bass * 0.2)
                self.bubble_vel[idx] = [
                    np.random.uniform(-0.2, 0.2),
                    rise_speed,
                    np.random.uniform(-0.2, 0.2)
                ]
                # Frequency-reactive bubble color
                self.bubble_col[idx] = [r_c, g_c, b_c, alpha]
                
            self.bubble_phase[idx] = np.random.uniform(0.0, 2 * np.pi)
            self.bubble_active[idx] = True
            self.bubble_is_fragment[idx] = False # Spawned bubbles are not fragments
            self.next_bubble_idx = (self.next_bubble_idx + 1) % len(self.bubble_pos)
            
        # Burst a small proportion of active normal bubbles on big volume hits
        if max_react > 0.8 and random.random() < 0.25:
            active_normal_indices = np.where(self.bubble_active & ~self.bubble_is_fragment)[0]
            if len(active_normal_indices) > 0:
                # Burst up to ~6% of active normal bubbles
                num_burst = max(1, int(len(active_normal_indices) * 0.06))
                burst_indices = np.random.choice(active_normal_indices, size=min(num_burst, len(active_normal_indices)), replace=False)
                for b_idx in burst_indices:
                    # Deactivate the original bubble
                    self.bubble_active[b_idx] = False
                    # Spawn 4 to 6 micro fragments
                    num_frags = random.randint(4, 6)
                    for _ in range(num_frags):
                        f_idx = self.next_bubble_idx
                        # Position is close to the original bubble's position
                        self.bubble_pos[f_idx] = self.bubble_pos[b_idx] + np.random.uniform(-0.05, 0.05, 3)
                        # Speed: shooting outwards
                        theta = np.random.uniform(0.0, 2 * np.pi)
                        phi = np.random.uniform(-np.pi/2, np.pi/2)
                        speed = np.random.uniform(1.5, 3.5)
                        self.bubble_vel[f_idx] = [
                            speed * np.cos(phi) * np.cos(theta),
                            speed * np.sin(phi) + 0.5, # slight upward bias
                            speed * np.cos(phi) * np.sin(theta)
                        ]
                        # Color: bright cyan-white
                        self.bubble_col[f_idx] = [0.6, 0.9, 1.0, 1.0]
                        self.bubble_size[f_idx] = np.random.uniform(0.7, 1.4)
                        self.bubble_phase[f_idx] = np.random.uniform(0.0, 2 * np.pi)
                        self.bubble_active[f_idx] = True
                        self.bubble_is_fragment[f_idx] = True
                        self.next_bubble_idx = (self.next_bubble_idx + 1) % len(self.bubble_pos)
            
        # Update Bubbles
        active = self.bubble_active
        if np.any(active):
            self.bubble_pos[active] += self.bubble_vel[active] * dt
            t = self.get_sim_time() * 3.5
            self.bubble_pos[active, 0] += np.sin(t + self.bubble_phase[active]) * dt * 0.55
            
            # Growth/Shrinkage
            self.bubble_size[active & ~self.bubble_is_fragment] += dt * 0.5
            self.bubble_size[active & self.bubble_is_fragment] -= dt * 3.0
            
            # Decay alpha for fragments
            self.bubble_col[active & self.bubble_is_fragment, 3] -= dt * 3.0
            
            # Apply height-based fade to normal active bubbles
            normal_active = active & ~self.bubble_is_fragment
            if np.any(normal_active):
                norm_heights = self.bubble_pos[normal_active, 1]
                norm_fade = np.clip((15.0 - norm_heights) / 5.0, 0.0, 1.0)
                self.bubble_col[normal_active, 3] *= norm_fade
                
            # Deactivate bubbles that are too high, shrunk too small, or faded completely
            too_high = (self.bubble_pos[:, 1] > 15.0) & active
            self.bubble_active[too_high] = False
            
            shrunk_too_small = (self.bubble_size <= 0.1) & active
            self.bubble_active[shrunk_too_small] = False
            
            faded_out = (self.bubble_col[:, 3] <= 0.0) & active
            self.bubble_active[faded_out] = False

        # Plankton drift
        t_val = self.get_sim_time()
        self.algae_pos[:, 0] += np.sin(t_val * 0.45 + self.algae_phase[:, 0]) * dt * 0.25
        self.algae_pos[:, 1] += np.cos(t_val * 0.35 + self.algae_phase[:, 1]) * dt * 0.18
        self.algae_pos[:, 2] += np.sin(t_val * 0.25 + self.algae_phase[:, 2]) * dt * 0.10
        
        x_out = self.algae_pos[:, 0] > 15.0
        self.algae_pos[x_out, 0] = -15.0
        x_out_neg = self.algae_pos[:, 0] < -15.0
        self.algae_pos[x_out_neg, 0] = 15.0
        
        y_out = self.algae_pos[:, 1] > 9.0
        self.algae_pos[y_out, 1] = -2.5
        y_out_neg = self.algae_pos[:, 1] < -2.5
        self.algae_pos[y_out_neg, 1] = 9.0
        
        # Individual plankton (algae) twinkling, modulated by the music
        self.algae_twinkle_phase += (1.5 + self.react_mid * 6.0) * dt * np.random.uniform(0.8, 1.5, len(self.algae_pos))
        algae_twinkle = np.sin(self.algae_twinkle_phase) * 0.5 + 0.5
        self.algae_col[:, 3] = (0.15 + self.react_mid * 0.85) * (0.2 + 0.8 * algae_twinkle)

        # Seabed bioluminescent phosphorescence twinkling
        self.seabed_twinkle_phase += (1.2 + self.react_bass * 5.0) * dt * np.random.uniform(0.7, 1.4, self.num_seabed_pts)
        for i in range(self.num_seabed_pts):
            if self.seabed_is_glowing[i]:
                twinkle_val = np.sin(self.seabed_twinkle_phase[i]) * 0.5 + 0.5
                self.seabed_col[i, 3] = (0.25 + self.react_bass * 0.75) * (0.15 + 0.85 * twinkle_val)

        # Update Jellyfish pulsing and movement physics
        for i in range(self.num_jelly):
            # Phase-locked directly to global tempo_phase to prevent drift and lock strictly on beat
            pulse_rate = 0.5 if (i % 2 == 1) else 1.0
            stagger = i * 0.25
            self.jelly_phase[i] = 2.0 * np.pi * (self.tempo_phase * pulse_rate + stagger)
            
            cos_val = np.cos(self.jelly_phase[i])
            if cos_val > 0.0:
                # Thrust synchronized directly with beat and amplified by real-time bass reactions
                thrust = 3.2 * cos_val * (1.0 + self.react_bass * 2.2)
                self.jelly_vel[i] += self.jelly_dir[i] * thrust * dt
            else:
                drag = 1.0
                self.jelly_vel[i] -= self.jelly_vel[i] * drag * dt
                
            # Apply position update
            self.jelly_pos[i] += self.jelly_vel[i] * dt
            
            # Gentle ambient upward buoyancy drift
            self.jelly_pos[i, 1] += 0.22 * dt
            
            # Reset jellyfish if they exit the water ceiling (expanded height limit to match bubbles)
            if self.jelly_pos[i, 1] > 16.0:
                self.jelly_pos[i, 1] = -11.0 # travel completely off-screen from bottom to top
                self.jelly_pos[i, 0] = np.random.uniform(-10.0, 10.0)
                self.jelly_pos[i, 2] = np.random.uniform(-4.0, 12.0)
                self.jelly_vel[i] = [0.0, 0.0, 0.0]
                self.jelly_dir[i] = self.get_tangential_jelly_dir(self.jelly_pos[i])
                
        # Update Glowing Squid Rarity pulsing, jet propulsion, and movement physics if active
        if self.active_rarity is not None and self.active_rarity['type'] == 'SQUID':
            bpm_rate = self.script_bpm / 60.0
            self.squid_phase += (bpm_rate * 0.7 + self.react_bass * 7.0) * dt
            cos_sq = np.cos(self.squid_phase)
            
            # Cooldown ticks down
            if not hasattr(self, 'squid_jet_cooldown'):
                self.squid_jet_cooldown = 0.0
            if self.squid_jet_cooldown > 0.0:
                self.squid_jet_cooldown -= dt

            # Big beat hit -> jet ink and speed off!
            if self.react_bass > 0.85 and self.squid_jet_cooldown <= 0.0:
                self.squid_vel += self.squid_dir * 18.0
                self.squid_jet_cooldown = 1.2
                
                # Jet ink: spawn a burst of dark ink bubbles behind the squid
                for _ in range(18):
                    idx = self.next_bubble_idx
                    self.bubble_pos[idx] = self.squid_pos - self.squid_dir * 1.5 + np.random.uniform(-0.35, 0.35, 3)
                    self.bubble_size[idx] = np.random.uniform(5.5, 10.0)
                    self.bubble_vel[idx] = -self.squid_dir * np.random.uniform(2.0, 5.0) + np.random.uniform(-0.6, 0.6, 3)
                    self.bubble_col[idx] = [0.01, 0.005, 0.03, 0.95] # dark ink
                    self.bubble_phase[idx] = np.random.uniform(0.0, 2.0 * np.pi)
                    self.bubble_active[idx] = True
                    self.bubble_is_fragment[idx] = False
                    self.next_bubble_idx = (self.next_bubble_idx + 1) % len(self.bubble_pos)

            if cos_sq > 0.0:
                # Cruising speed slowed down to 1/4 (thrust is scaled down from 4.5 to 1.125)
                sq_thrust = 1.125 * cos_sq * (1.0 + self.react_bass * 1.5)
                self.squid_vel += self.squid_dir * sq_thrust * dt
            
            # Drag is applied continuously to make impulse and cruising velocity decay naturally
            sq_drag = 1.2 if cos_sq <= 0.0 else 0.4
            self.squid_vel -= self.squid_vel * sq_drag * dt
            self.squid_pos += self.squid_vel * dt
            target_dir = np.array([-self.squid_pos[0]*0.1, 0.1, 4.0 - self.squid_pos[2]*0.2], dtype=np.float32)
            if np.linalg.norm(target_dir) > 1e-4:
                target_dir /= np.linalg.norm(target_dir)
                self.squid_dir = 0.95 * self.squid_dir + 0.05 * target_dir
                # Restrict squid direction vector to within 30 degrees of camera-perpendicular X-Y plane
                self.squid_dir[2] = np.clip(self.squid_dir[2], -0.45, 0.45)
                self.squid_dir /= np.linalg.norm(self.squid_dir)
            if self.squid_pos[1] > 18.0 or self.squid_pos[1] < -18.0 or abs(self.squid_pos[0]) > 24.0 or self.squid_pos[2] < -18.0 or self.squid_pos[2] > 24.0:
                self.squid_pos = np.array([np.random.uniform(-12.0, 12.0), np.random.uniform(-12.0, -4.0), np.random.uniform(-6.0, 8.0)], dtype=np.float32)
                self.squid_vel = np.array([0.0, 0.0, 0.0], dtype=np.float32)
                self.squid_dir = np.array([np.random.uniform(-1.0, 1.0), np.random.uniform(-0.2, 0.2), np.random.uniform(-0.45, 0.45)], dtype=np.float32)
                self.squid_dir /= np.linalg.norm(self.squid_dir)

    def render_underwater(self):
        act_mask = self.bubble_active
        if np.any(act_mask):
            b_pos = self.bubble_pos[act_mask]
            b_col = self.bubble_col[act_mask]
            b_size = -self.bubble_size[act_mask]
        else:
            b_pos = np.zeros((0, 3), dtype=np.float32)
            b_col = np.zeros((0, 4), dtype=np.float32)
            b_size = np.zeros(0, dtype=np.float32)
            
        a_pos = self.algae_pos
        a_col = self.algae_col
        a_size = -self.algae_size * (1.0 + self.react_treble * 0.4)
        
        # Render irregular Stalagmite Vents on seabed
        v_pos = self.vent_pts_pos
        v_col = self.vent_pts_col.copy()
        v_size = -self.vent_pts_size.copy()
        for i in range(self.num_vent_pts):
            if i % 24 >= 20: # Glowing crater mouths
                v_col[i, 3] = 0.5 + self.react_bass * 0.5
                v_size[i] *= (1.0 + self.react_bass * 0.4)
                
        # Render Sandy/Rocky Sea Floor Points
        seabed_pos = self.seabed_pos
        seabed_col = self.seabed_col
        seabed_size = self.seabed_size

        # Render Bioluminescent Seaweed / Waving Marine Plants
        plant_pos_list = []
        plant_col_list = []
        plant_size_list = []
        t_val = self.get_sim_time()
        
        for p in range(self.num_plants):
            base_col = self.plant_color[p]
            base_pos = self.plant_base[p]
            p_phase = self.plant_phase[p]
            
            for s in range(8):
                dist = s * 0.38
                y = base_pos[1] + dist
                sway = np.sin(2.0 * np.pi * self.tempo_phase + p_phase + s * 0.45) * 0.08 * (s + 1.0)
                x = base_pos[0] + sway
                z = base_pos[2]
                
                plant_pos_list.append([x, y, z])
                plant_col_list.append([
                    base_col[0], base_col[1], base_col[2],
                    0.65 * (1.0 - s * 0.09) * (0.5 + self.react_mid * 0.5)
                ])
                plant_size_list.append(-8.0 * (1.1 - s * 0.08))

        # Render Overhauled Moon and Crystal Jellyfish
        j_pos_list = []
        j_col_list = []
        j_size_list = []
        
        hood_tri_pos = []
        hood_tri_col = []
        
        for i in range(self.num_jelly):
            species = self.jelly_species[i] # 0 = Moon Jelly, 1 = Crystal Jelly
            base_col = self.jelly_col[i]
            base_size = self.jelly_size[i]
            pos = self.jelly_pos[i]
            dir_vec = self.jelly_dir[i]
            
            cos_val = np.cos(self.jelly_phase[i])
            
            # Setup dynamic local 3D orientation frame
            dx, dy, dz = dir_vec
            if abs(dx) < 0.9:
                u = np.cross(dir_vec, [1.0, 0.0, 0.0])
            else:
                u = np.cross(dir_vec, [0.0, 1.0, 0.0])
            u /= np.linalg.norm(u)
            w = np.cross(dir_vec, u)
            
            # HIGH-FIDELITY PARABOLOID DOME MESH MODEL (5 rings of 12 vertices = 60 vertices)
            # Dynamic deformation: contracts (elongates & pinches) on thrust, relaxes (shortens & widens) on glide
            if species == 0:     # Moon Jelly: round, flatter profile
                base_radius = 1.15
                base_height = 0.65
            else:               # Crystal Jelly: taller conical profile
                base_radius = 0.90
                base_height = 0.95
                
            deform_radius = base_radius * (1.0 - (0.22 + 0.08 * self.react_bass) * max(0.0, cos_val))
            deform_height = base_height * (1.0 + (0.28 + 0.12 * self.react_bass) * max(0.0, cos_val))
            
            # Generate the 60 bell dome coordinates
            v_coords = []
            v_cols = []
            for ring in range(5):
                h_frac = ring / 4.0 # 0.0 at apex, 1.0 at rim
                r_frac = np.sin(h_frac * np.pi / 2.0)
                
                ring_radius = deform_radius * r_frac
                ring_height = deform_height * (1.0 - h_frac)
                
                # Dynamic saucer-like contraction folding for Moon Jelly margin
                if species == 0 and ring >= 3:
                    pinch = 1.0 - 0.18 * max(0.0, cos_val) * (h_frac - 0.5)
                    ring_radius *= pinch
                
                # Glowing transparency profiles (increased opacity for gorgeous translucent bells)
                if species == 0:     # Moon Jelly: round, flatter profile
                    alpha_val = (0.16 - h_frac * 0.08) * (0.35 + self.react_treble * 0.85)
                else:               # Crystal Jelly: taller conical profile
                    alpha_val = (0.11 - h_frac * 0.05) * (0.35 + self.react_treble * 0.85)
                
                col = [base_col[0], base_col[1], base_col[2], alpha_val]
                
                for k in range(12):
                    ang = k * 2.0 * np.pi / 12.0
                    
                    # 8 shallow lobes along the bell rim for Moon Jelly
                    if species == 0 and ring == 4:
                        ring_radius_mod = ring_radius * (1.0 + 0.06 * np.cos(8.0 * ang))
                    else:
                        ring_radius_mod = ring_radius
                        
                    offset = (u * np.cos(ang) + w * np.sin(ang)) * ring_radius_mod + dir_vec * ring_height
                    jelly_v_pos = pos + offset
                    
                    v_coords.append(jelly_v_pos)
                    v_cols.append(col)
                    
                    # Fluorescent GFP margin organs: bright neon-green/teal points on the rim for Crystal Jelly
                    if species == 1 and ring == 4:
                        col_pt = [0.1, 0.95, 0.25, 0.85 * (0.8 + self.react_treble * 0.4)]
                        size_pt = -base_size * 0.25
                        j_pos_list.append(jelly_v_pos)
                        j_col_list.append(col_pt)
                        j_size_list.append(size_pt)
                    elif species == 1 and k % 3 == 0:
                        # Radial canals (ribs)
                        col_pt = [0.0, 0.95, 0.6, 0.45 * (0.8 + self.react_treble * 0.4)] # Glowing neon emerald-green rib
                        size_pt = -base_size * 0.12
                        j_pos_list.append(jelly_v_pos)
                        j_col_list.append(col_pt)
                        j_size_list.append(size_pt)
            
            # Build seamless triangle mesh quads connecting the 5 concentric rings (12 columns)
            for ring in range(4):
                for k in range(12):
                    k_next = (k + 1) % 12
                    i00 = ring * 12 + k
                    i10 = ring * 12 + k_next
                    i01 = (ring + 1) * 12 + k
                    i11 = (ring + 1) * 12 + k_next
                    
                    hood_tri_pos.append(v_coords[i00])
                    hood_tri_pos.append(v_coords[i10])
                    hood_tri_pos.append(v_coords[i11])
                    hood_tri_col.append(v_cols[i00])
                    hood_tri_col.append(v_cols[i10])
                    hood_tri_col.append(v_cols[i11])
                    
                    hood_tri_pos.append(v_coords[i00])
                    hood_tri_pos.append(v_coords[i11])
                    hood_tri_pos.append(v_coords[i01])
                    hood_tri_col.append(v_cols[i00])
                    hood_tri_col.append(v_cols[i11])
                    hood_tri_col.append(v_cols[i01])
            
            # SPECIES-SPECIFIC BIOLUMINESCENT ANATOMY DETAILS
            if species == 0:
                # 1. MOON JILLYFISH: 4 Glowing clover/horseshoe-shaped reproductive organ cores (each built of 3 small points to form a crescent)
                for k in range(4):
                    ang_base = k * 2.0 * np.pi / 4.0
                    # Create a horseshoe crescent loop
                    for sub in [-0.2, 0.0, 0.2]:
                        ang = ang_base + sub
                        rad_factor = 0.26 * (1.0 - 0.12 * abs(sub))
                        c_offset = (u * np.cos(ang) + w * np.sin(ang)) * rad_factor * deform_radius
                        c_pos = pos + dir_vec * (0.32 + 0.05 * np.cos(sub * 2.0)) * deform_height + c_offset
                        j_pos_list.append(c_pos)
                        j_col_list.append([1.0, 0.15, 0.65, 0.70 * (0.8 + self.react_mid * 0.4)])
                        j_size_list.append(-base_size * 0.32)
                    
                # 2. MOON JELLYFISH: 4 central frilly lavender-pink flowing oral arms
                for arm in range(4):
                    ang = arm * 2.0 * np.pi / 4.0
                    arm_anchor = pos + (u * np.cos(ang) + w * np.sin(ang)) * 0.15
                    for s in range(8):
                        dist = s * 0.22
                        wave_phase = self.jelly_phase[i] - s * 0.6 - t_val * 2.5
                        ripple = u * np.sin(wave_phase) * 0.06 * (s + 1.0) + w * np.cos(wave_phase * 1.2) * 0.04 * (s + 1.0)
                        arm_pos = arm_anchor - dir_vec * dist + ripple
                        
                        j_pos_list.append(arm_pos)
                        j_col_list.append([0.95, 0.25, 0.80, 0.45 * (1.0 - 0.11 * s) * (0.8 + self.react_mid * 0.4)])
                        j_size_list.append(-base_size * 0.45 * (1.0 - 0.08 * s))
                        
                # 3. MOON JELLYFISH: Fine fringe of short pink tentacles along the bell rim
                for k in range(12):
                    ang = k * 2.0 * np.pi / 12.0
                    rim_anchor = pos + (u * np.cos(ang) + w * np.sin(ang)) * deform_radius
                    for s in range(3):
                        dist = s * 0.12
                        wave_phase = self.jelly_phase[i] - s * 0.8 - t_val * 3.0
                        ripple = u * np.sin(wave_phase) * 0.03 + w * np.cos(wave_phase) * 0.03
                        ten_pos = rim_anchor - dir_vec * dist + ripple
                        
                        j_pos_list.append(ten_pos)
                        j_col_list.append([0.90, 0.35, 0.75, 0.30 * (1.0 - 0.25 * s) * (0.8 + self.react_treble * 0.4)])
                        j_size_list.append(-base_size * 0.15 * (1.0 - 0.15 * s))
                        
            else:
                # 1. CRYSTAL JELLYFISH: Glowing neon-cyan/white inner mouth core
                for k in range(3):
                    c_pos = pos + dir_vec * (0.2 + k * 0.18) * deform_height
                    j_pos_list.append(c_pos)
                    j_col_list.append([0.0, 0.85, 1.0, 0.65 * (0.8 + self.react_mid * 0.4)])
                    j_size_list.append(-base_size * 0.45)
                    
                # 2. CRYSTAL JELLYFISH: Exceptionally long, thin trailing bioluminescent neon-blue tentacles
                num_t = 12
                for k in range(num_t):
                    ang = k * 2.0 * np.pi / num_t
                    rim_anchor = pos + (u * np.cos(ang) + w * np.sin(ang)) * deform_radius
                    for s in range(14): # Very long, majestic trailing lines
                        dist = s * 0.45
                        wave_phase = self.jelly_phase[i] - s * 0.42 - t_val * 2.2
                        wave_amp = 0.13 * (s + 1.0)
                        ripple = u * np.sin(wave_phase) * wave_amp + w * np.cos(wave_phase * 1.15) * wave_amp * 0.65
                        ten_pos = rim_anchor - dir_vec * dist + ripple
                        
                        j_pos_list.append(ten_pos)
                        # Fade out to deep bioluminescent blue at the tips
                        alpha_fade = 0.55 * (1.0 - 0.06 * s) * (0.8 + self.react_treble * 0.4)
                        gfp_blend = max(0.0, 1.0 - s * 0.15) # Green near the base rim, blending to blue tips
                        col_r = 0.0
                        col_g = 0.55 * gfp_blend + 0.1 * (1.0 - gfp_blend)
                        col_b = 1.0
                        j_col_list.append([col_r, col_g, col_b, alpha_fade])
                        j_size_list.append(-base_size * 0.16 * (1.0 - 0.04 * s))
                        
            # Draw Squid, Manta, Seahorse, or Lantern Fish Rarity as solid 3D triangle meshes
            if self.active_rarity is not None and self.active_rarity['type'] == 'SQUID':
                sq_pts, sq_cols = make_solid_squid(self.squid_pos, self.squid_dir, self.squid_phase, self.react_bass, self.react_mid, self.react_treble)
                hood_tri_pos.extend(sq_pts)
                hood_tri_col.extend(sq_cols)
                
            if self.active_rarity is not None and self.active_rarity['type'] == 'MANTA':
                m_pts, m_cols = make_solid_manta(self.active_rarity['pos'], self.active_rarity['dir'], self.active_rarity['phase'])
                hood_tri_pos.extend(m_pts)
                hood_tri_col.extend(m_cols)
                
            if self.active_rarity is not None and self.active_rarity['type'] == 'SEAHORSE':
                sh_pts, sh_cols = make_solid_seahorse(self.active_rarity['pos'], self.active_rarity['phase'])
                hood_tri_pos.extend(sh_pts)
                hood_tri_col.extend(sh_cols)
                
            if self.active_rarity is not None and self.active_rarity['type'] == 'LANTERN_FISH':
                r = self.active_rarity
                center = r['pos']
                for k in range(len(r['offsets'])):
                    fish_pos = center + r['offsets'][k]
                    fish_pos[1] += np.sin(self.get_sim_time() * 8.0 + k) * 0.15
                    # Recolor fish bodies to beautiful matte deep purple-blue and indigo
                    col_fish = [0.18, 0.15, 0.45, 1.0] if k % 2 == 0 else [0.08, 0.05, 0.32, 1.0]
                    lf_pts, lf_cols = make_solid_fish(fish_pos, r['dir'], self.get_sim_time() + k, col_fish)
                    hood_tri_pos.extend(lf_pts)
                    hood_tri_col.extend(lf_cols)
                    
        j_pos_arr = np.array(j_pos_list, dtype=np.float32) if len(j_pos_list) > 0 else np.zeros((0, 3), dtype=np.float32)
        j_col_arr = np.array(j_col_list, dtype=np.float32) if len(j_col_list) > 0 else np.zeros((0, 4), dtype=np.float32)
        j_size_arr = np.array(j_size_list, dtype=np.float32) if len(j_size_list) > 0 else np.zeros(0, dtype=np.float32)

        # Convert seaweed plant lists to NumPy arrays
        p_pos_arr = np.array(plant_pos_list, dtype=np.float32) if len(plant_pos_list) > 0 else np.zeros((0, 3), dtype=np.float32)
        p_col_arr = np.array(plant_col_list, dtype=np.float32) if len(plant_col_list) > 0 else np.zeros((0, 4), dtype=np.float32)
        p_size_arr = np.array(plant_size_list, dtype=np.float32) if len(plant_size_list) > 0 else np.zeros(0, dtype=np.float32)

        # Concatenate all visual elements into unified arrays for high-performance rendering
        pos_combined = np.concatenate([b_pos, a_pos, v_pos, seabed_pos, p_pos_arr, j_pos_arr], axis=0).astype(np.float32)
        col_combined = np.concatenate([b_col, a_col, v_col, seabed_col, p_col_arr, j_col_arr], axis=0).astype(np.float32)
        size_combined = np.concatenate([b_size, a_size, v_size, seabed_size, p_size_arr, j_size_arr], axis=0).astype(np.float32)

        return pos_combined, col_combined, size_combined, np.array(hood_tri_pos, dtype=np.float32), np.array(hood_tri_col, dtype=np.float32)

    def init_mandala_mode(self):
        M = 250
        if not hasattr(self, 'mandala_slices'):
            self.mandala_slices = 12
        self.mandala_base_pos = np.zeros((M, 3), dtype=np.float32)
        self.mandala_base_pos[:, 1] = 4.0
        self.mandala_base_vel = np.zeros((M, 3), dtype=np.float32)
        self.mandala_base_ages = np.zeros(M, dtype=np.float32)
        self.mandala_base_max_ages = np.zeros(M, dtype=np.float32)
        self.mandala_base_col = np.zeros((M, 4), dtype=np.float32)
        self.mandala_base_size = np.zeros(M, dtype=np.float32)
        
        for i in range(M):
            self.reset_mandala_particle(i)

    def reset_mandala_particle(self, idx):
        self.mandala_base_pos[idx] = [0.0, 4.0, 0.0]
        angle = np.random.uniform(0.0, 2 * np.pi)
        speed = np.random.uniform(1.5, 4.5)
        self.mandala_base_vel[idx, 0] = speed * np.cos(angle)
        self.mandala_base_vel[idx, 1] = speed * np.sin(angle)
        self.mandala_base_vel[idx, 2] = np.random.uniform(-0.2, 0.2)
        
        self.mandala_base_ages[idx] = 0.0
        self.mandala_base_max_ages[idx] = np.random.uniform(1.8, 3.2)
        if self.opt_color_mode != 'REALISTIC':
            pal = get_palette_colors(self.opt_color_mode)
            col_choice = random.choice(pal)
        else:
            col_choice = random.choice([
                COLORS["sodium_gold"],
                COLORS["strontium_red"],
                COLORS["potassium_purple"],
                COLORS["copper_blue"],
                COLORS["magnesium_white"]
            ])
        self.mandala_base_col[idx] = col_choice
        self.mandala_base_col[idx, 3] = np.random.uniform(0.6, 1.0)
        self.mandala_base_size[idx] = np.random.uniform(5.0, 11.0)

    def update_mandala(self, dt):
        speed_factor = 1.0 + self.react_bass * 2.5
        if self.opt_gravity > 0.0:
            self.mandala_base_vel[:, 1] -= 3.0 * self.opt_gravity * dt
        self.mandala_base_pos += self.mandala_base_vel * speed_factor * dt

        if self.opt_trailers > 0:
            target_history_len = self.opt_trailers * 2
            if not hasattr(self, 'mandala_history') or self.mandala_history is None:
                self.mandala_history = []
            self.mandala_history.append((self.mandala_base_pos.copy(), self.mandala_base_col.copy(), self.mandala_base_ages.copy(), self.mandala_base_max_ages.copy()))
            while len(self.mandala_history) > target_history_len:
                self.mandala_history.pop(0)
        else:
            self.mandala_history = None
        
        center = np.array([0.0, 4.0, 0.0], dtype=np.float32)
        to_center = center[np.newaxis, :] - self.mandala_base_pos
        dist_c = np.linalg.norm(to_center, axis=1, keepdims=True) + 1e-6
        
        tangent_x = -to_center[:, 1] / dist_c[:, 0]
        tangent_y = to_center[:, 0] / dist_c[:, 0]
        self.mandala_base_pos[:, 0] += tangent_x * (0.8 + self.react_mid * 2.0) * dt
        self.mandala_base_pos[:, 1] += tangent_y * (0.8 + self.react_mid * 2.0) * dt
        
        self.mandala_base_ages += dt
        expired = self.mandala_base_ages >= self.mandala_base_max_ages
        for idx in np.where(expired)[0]:
            self.reset_mandala_particle(idx)

    def render_mandala(self):
        pal = get_palette_colors(self.opt_color_mode) if self.opt_color_mode != 'REALISTIC' else None
        M = len(self.mandala_base_pos)
        S = self.mandala_slices
        angles = np.arange(S) * (2 * np.pi / S) + (self.get_sim_time() * (0.15 + self.react_mid * 0.6))
        shifted = self.mandala_base_pos - np.array([0.0, 4.0, 0.0])
        
        x = shifted[:, 0][:, np.newaxis]
        y = shifted[:, 1][:, np.newaxis]
        z = shifted[:, 2][:, np.newaxis]
        
        cos_a = np.cos(angles)[np.newaxis, :]
        sin_a = np.sin(angles)[np.newaxis, :]
        
        rot_x = x * cos_a - y * sin_a
        rot_y = x * sin_a + y * cos_a
        rot_z = np.tile(z, (1, S))
        
        rot_pos = np.stack([rot_x, rot_y + 4.0, rot_z], axis=2)
        pos_arr = rot_pos.reshape(-1, 3).astype(np.float32)
        col_arr = np.repeat(self.mandala_base_col, S, axis=0).copy()
        
        # Apply current life ratio fade to current colors before historical appending
        ages_rep = np.repeat(self.mandala_base_ages, S)
        max_ages_rep = np.repeat(self.mandala_base_max_ages, S)
        life_ratio = ages_rep / max_ages_rep
        col_arr[:, 3] *= np.clip(1.0 - life_ratio, 0.0, 1.0)
        
        current_size_arr = np.repeat(self.mandala_base_size, S) * (1.0 + self.react_treble * 0.5)
        
        all_pos_list = [pos_arr]
        all_col_list = [col_arr]
        all_size_list = [current_size_arr]

        if hasattr(self, 'mandala_history') and self.mandala_history is not None and len(self.mandala_history) > 0:
            hist_len = len(self.mandala_history)
            for h_idx, (h_pos, h_col, h_ages, h_max_ages) in enumerate(self.mandala_history):
                fade_factor = (h_idx + 1) / (hist_len + 1)
                shifted_h = h_pos - np.array([0.0, 4.0, 0.0])
                hx = shifted_h[:, 0][:, np.newaxis]
                hy = shifted_h[:, 1][:, np.newaxis]
                hz = shifted_h[:, 2][:, np.newaxis]
                
                h_rot_x = hx * cos_a - hy * sin_a
                h_rot_y = hx * sin_a + hy * cos_a
                h_rot_z = np.tile(hz, (1, S))
                
                h_rot_pos = np.stack([h_rot_x, h_rot_y + 4.0, h_rot_z], axis=2)
                h_pos_arr = h_rot_pos.reshape(-1, 3).astype(np.float32)
                
                h_col_arr = np.repeat(h_col, S, axis=0).copy()
                h_ages_rep = np.repeat(h_ages, S)
                h_max_rep = np.repeat(h_max_ages, S)
                h_ratio = h_ages_rep / h_max_rep
                
                h_col_arr[:, 3] *= np.clip(1.0 - h_ratio, 0.0, 1.0) * fade_factor * 0.45
                h_size_arr = np.repeat(self.mandala_base_size, S) * (1.0 + self.react_treble * 0.5) * (0.4 + 0.6 * fade_factor)
                
                all_pos_list.append(h_pos_arr)
                all_col_list.append(h_col_arr)
                all_size_list.append(h_size_arr)
                
        pos_arr = np.concatenate(all_pos_list, axis=0)
        col_arr = np.concatenate(all_col_list, axis=0)
        size_arr = np.concatenate(all_size_list, axis=0)
        
        mandala_tri_pos = []
        mandala_tri_col = []
        
        # Render Peace Symbol Overlay in central space (Un-sliced to remain perfectly legible)
        if self.peace_symbol_timer > 0.0:
            peace_pos, peace_col, peace_size = [], [], []
            R = 3.6 + np.sin(self.get_sim_time() * 6.0) * 0.15
            center = np.array([0.0, 4.0, 0.0], dtype=np.float32)
            alpha_p = np.clip(self.peace_symbol_timer / 1.0, 0.0, 1.0) * (0.65 + self.react_mid * 0.35)
            p_col_rgb = list(pal[0][:3]) if pal else [1.0, 0.82, 0.1]
            for k_pt in range(60):
                ang = k_pt * 2.0 * np.pi / 60.0
                pt = center + np.array([R * np.cos(ang), R * np.sin(ang), 0.0], dtype=np.float32)
                peace_pos.append(pt)
                peace_col.append(p_col_rgb + [alpha_p])
                peace_size.append(10.0 + np.sin(self.get_sim_time() * 12.0 + k_pt) * 4.0)
            for y_pt in np.linspace(-R, R, 20):
                pt = center + np.array([0.0, y_pt, 0.0], dtype=np.float32)
                peace_pos.append(pt)
                peace_col.append([1.0, 0.82, 0.1, alpha_p])
                peace_size.append(10.0)
            for r_pt in np.linspace(0.0, R, 15):
                pt = center + np.array([r_pt * np.cos(5.0 * np.pi / 4.0), r_pt * np.sin(5.0 * np.pi / 4.0), 0.0], dtype=np.float32)
                peace_pos.append(pt)
                peace_col.append([1.0, 0.82, 0.1, alpha_p])
                peace_size.append(10.0)
            for r_pt in np.linspace(0.0, R, 15):
                pt = center + np.array([r_pt * np.cos(7.0 * np.pi / 4.0), r_pt * np.sin(7.0 * np.pi / 4.0), 0.0], dtype=np.float32)
                peace_pos.append(pt)
                peace_col.append([1.0, 0.82, 0.1, alpha_p])
                peace_size.append(10.0)
            pos_arr = np.concatenate([pos_arr, np.array(peace_pos, dtype=np.float32)], axis=0)
            col_arr = np.concatenate([col_arr, np.array(peace_col, dtype=np.float32)], axis=0)
            size_arr = np.concatenate([size_arr, np.array(peace_size, dtype=np.float32)], axis=0)
            
        # Render Pulsing Halo Effect with outward firing sparks (Un-sliced circle with scattered sparks)
        if self.halo_timer > 0.0:
            halo_pos, halo_col, halo_size = [], [], []
            R_halo = 5.2 + self.react_bass * 1.5 + np.sin(self.get_sim_time() * 5.0) * 0.25
            center = np.array([0.0, 4.0, 0.0], dtype=np.float32)
            alpha_h = np.clip(self.halo_timer / 1.0, 0.0, 1.0)
            for i_h in range(80):
                ang = i_h * 2.0 * np.pi / 80.0 + self.get_sim_time() * 1.5
                pt = center + np.array([R_halo * np.cos(ang), R_halo * np.sin(ang), 0.0], dtype=np.float32)
                halo_pos.append(pt)
                halo_col.append([0.1, 0.85, 1.0, alpha_h])
                halo_size.append(12.0)
                if i_h % 4 == 0 and random.random() < 0.28:
                    spark_r = R_halo + np.random.uniform(0.1, 1.8)
                    spark_ang = ang + np.random.uniform(-0.1, 0.1)
                    s_pt = center + np.array([spark_r * np.cos(spark_ang), spark_r * np.sin(spark_ang), np.random.uniform(-0.1, 0.1)], dtype=np.float32)
                    halo_pos.append(s_pt)
                    h_col_rgb = list(pal[1 % len(pal)][:3]) if pal else [0.9, 0.15, 0.5]
                    halo_col.append(h_col_rgb + [alpha_h * 0.6])
                    halo_size.append(6.0)
            pos_arr = np.concatenate([pos_arr, np.array(halo_pos, dtype=np.float32)], axis=0)
            col_arr = np.concatenate([col_arr, np.array(halo_col, dtype=np.float32)], axis=0)
            size_arr = np.concatenate([size_arr, np.array(halo_size, dtype=np.float32)], axis=0)
            
        # Render Mandala Mode Symmetrical Rarities (Bird, Smoke, Sun Burst, Butterfly)
        if self.active_rarity is not None:
            r = self.active_rarity
            r_pos_list, r_col_list, r_size_list = [], [], []
            if r['type'] == 'BIRD':
                # Render high-quality 3D Bird singleton directly as solid asymmetric (no pairs!)
                b_pts, b_cols = make_solid_bird(r['pos'], np.array([np.cos(r['ang']), np.sin(r['ang']), 0.0]), r['phase'])
                mandala_tri_pos.extend(b_pts)
                mandala_tri_col.extend(b_cols)
            elif r['type'] == 'SMOKE':
                for j in range(len(r['particles_pos'])):
                    pt_relative = r['particles_pos'][j] - np.array([0.0, 4.0, 0.0])
                    r_pos_list.append(pt_relative)
                    rad = r['particles_rad'][j]
                    alpha = 0.72 * (1.0 - rad / 12.0)
                    c1 = list(pal[0][:3]) if pal else [0.15, 0.85, 0.92]
                    c2 = list(pal[2 % len(pal)][:3]) if pal else [0.75, 0.12, 0.92]
                    col = c1 + [alpha] if j % 2 == 0 else c2 + [alpha]
                    r_col_list.append(col)
                    r_size_list.append(18.0 + rad * 3.5) # made smoke highly visible
            elif r['type'] == 'SUN_BURST':
                # Sunburst overhaul: 16 spokes, 24 points per spoke, golden-orange gradients, larger points
                for i_sp in range(16):
                    spoke_ang = i_sp * (np.pi / 8.0) + r['phase']
                    max_rad = (3.5 - r['life']) * 4.5
                    for j_pt in range(24):
                        pt_frac = j_pt / 23.0
                        rad = pt_frac * max_rad
                        pt_relative = np.array([rad * np.cos(spoke_ang), rad * np.sin(spoke_ang), 0.0])
                        r_pos_list.append(pt_relative)
                        alpha = 0.8 * (1.0 - pt_frac) * np.clip(r['life'] / 1.0, 0.0, 1.0)
                        if pal:
                            c_mix = (1.0 - pt_frac) * np.array(pal[0][:3]) + pt_frac * np.array(pal[2 % len(pal)][:3])
                            r_col_list.append(list(c_mix) + [alpha])
                        else:
                            r_col_list.append([1.0, 0.4 + 0.55 * (1.0 - pt_frac), 0.0, alpha])
                        r_size_list.append(16.0 * (1.0 - pt_frac * 0.3))
            elif r['type'] == 'BUTTERFLY':
                # Render high-quality 3D Butterfly singleton directly as solid asymmetric (no pairs!)
                bf_pts, bf_cols = make_solid_butterfly(r['pos'], np.array([np.cos(r['ang']), np.sin(r['ang']), 0.0]), r['phase'])
                if pal:
                    for idx_c in range(len(bf_cols)):
                        bf_cols[idx_c] = list(pal[idx_c % len(pal)][:3]) + [bf_cols[idx_c][3]]
                mandala_tri_pos.extend(bf_pts)
                mandala_tri_col.extend(bf_cols)
            if r['type'] == 'BIRD' and pal:
                for idx_c in range(len(mandala_tri_col)):
                    mandala_tri_col[idx_c] = list(pal[idx_c % len(pal)][:3]) + [mandala_tri_col[idx_c][3]]
                
            if len(r_pos_list) > 0:
                sym_pos, sym_col, sym_size = [], [], []
                angles_s = np.arange(S) * (2 * np.pi / S)
                r_pos_arr = np.array(r_pos_list)
                r_col_arr = np.array(r_col_list)
                r_size_arr = np.array(r_size_list)
                for ang_s in angles_s:
                    cos_s = np.cos(ang_s)
                    sin_s = np.sin(ang_s)
                    rot_x = r_pos_arr[:, 0] * cos_s - r_pos_arr[:, 1] * sin_s
                    rot_y = r_pos_arr[:, 0] * sin_s + r_pos_arr[:, 1] * cos_s
                    rot_z = r_pos_arr[:, 2]
                    for idx_pt in range(len(r_pos_arr)):
                        sym_pos.append([rot_x[idx_pt], rot_y[idx_pt] + 4.0, rot_z[idx_pt]])
                        sym_col.append(r_col_arr[idx_pt])
                        sym_size.append(r_size_arr[idx_pt])
                pos_arr = np.concatenate([pos_arr, np.array(sym_pos, dtype=np.float32)], axis=0)
                col_arr = np.concatenate([col_arr, np.array(sym_col, dtype=np.float32)], axis=0)
                size_arr = np.concatenate([size_arr, np.array(sym_size, dtype=np.float32)], axis=0)
                
        return pos_arr, col_arr, size_arr, np.array(mandala_tri_pos, dtype=np.float32), np.array(mandala_tri_col, dtype=np.float32)

    def trigger_climax_event(self, intensity=1.5, routine_name=""):
        # Setup climax properties
        self.climax_flash = intensity
        self.active_routine_name = routine_name or "Climax Burst!"
        self.routine_timer = 5.0
        
        # Boost visualizer envelopes aggressively
        self.react_bass = min(1.8, self.react_bass + 1.2)
        self.react_mid = min(1.8, self.react_mid + 1.2)
        self.react_treble = min(1.8, self.react_treble + 1.2)
        
        if self.major_mode == "UNDERWATER Lava":
            if routine_name == "Supernova":
                # Giant white-hot supernova eruption from all vents!
                for _ in range(240):
                    idx = self.next_bubble_idx
                    v_idx = random.randint(0, 2)
                    v_loc = self.vent_locs[v_idx]
                    self.bubble_pos[idx] = [v_loc[0], v_loc[1] + 1.75, v_loc[2]] + np.random.uniform([-0.5, 0.0, -0.5], [0.5, 0.25, 0.5])
                    self.bubble_size[idx] = np.random.uniform(4.0, 8.0)
                    self.bubble_vel[idx] = [np.random.uniform(-2.5, 2.5), np.random.uniform(4.0, 8.0), np.random.uniform(-2.5, 2.5)]
                    self.bubble_col[idx] = [1.0, 0.95, 0.8, 1.0]
                    self.bubble_active[idx] = True
                    self.bubble_is_fragment[idx] = False
                    self.next_bubble_idx = (self.next_bubble_idx + 1) % len(self.bubble_pos)
                if self.active_rarity is not None and self.active_rarity['type'] == 'SQUID':
                    self.squid_vel = self.squid_dir * 2.0 # slowed down to 1/4 from 8.0
                    self.squid_phase = 0.0
            elif routine_name == "Shooting Star":
                # Underwater shooting stars: cyan bioluminescent trails streaking horizontally
                for i in range(120):
                    idx = self.next_bubble_idx
                    self.bubble_pos[idx] = [-15.0 + i * 0.1, np.random.uniform(0.0, 8.0), np.random.uniform(0.0, 6.0)]
                    self.bubble_vel[idx] = [np.random.uniform(8.0, 15.0), np.random.uniform(-0.4, 0.4), np.random.uniform(-0.4, 0.4)]
                    self.bubble_size[idx] = np.random.uniform(2.0, 4.0)
                    self.bubble_col[idx] = [0.1, 0.85, 1.0, 0.95]
                    self.bubble_active[idx] = True
                    self.bubble_is_fragment[idx] = False
                    self.next_bubble_idx = (self.next_bubble_idx + 1) % len(self.bubble_pos)
            else:
                for _ in range(180):
                    idx = self.next_bubble_idx
                    v_idx = random.randint(0, 2)
                    v_loc = self.vent_locs[v_idx]
                    self.bubble_pos[idx] = [v_loc[0], v_loc[1] + 1.75, v_loc[2]] + np.random.uniform([-0.35, 0.0, -0.35], [0.35, 0.25, 0.35])
                    self.bubble_size[idx] = np.random.uniform(2.5, 6.0)
                    rise_speed = np.random.uniform(2.5, 5.5)
                    self.bubble_vel[idx] = [np.random.uniform(-1.5, 1.5), rise_speed, np.random.uniform(-1.5, 1.5)]
                    self.bubble_col[idx] = [random.choice([0.9, 0.1, 0.0]), random.choice([0.1, 0.9, 0.8]), random.choice([0.9, 0.1, 1.0]), np.random.uniform(0.7, 1.0)]
                    self.bubble_active[idx] = True
                    self.bubble_is_fragment[idx] = False
                    self.next_bubble_idx = (self.next_bubble_idx + 1) % len(self.bubble_pos)
                    
            for i in range(self.num_jelly):
                self.jelly_phase[i] = 0.0
                self.jelly_vel[i] = self.jelly_dir[i] * 5.0
                self.jelly_col[i, 3] = 1.0
                
        elif self.major_mode == "TUNNEL Wormhole":
            get_bend_offsets = self.get_bend_offsets
            if routine_name == "Lightning Flash":
                self.lightning_active_timer = 0.4
                self.active_lightning_bolts = []
                for _ in range(2):
                    bolt = []
                    bx, by = get_bend_offsets(-55.0)
                    bolt.append([np.random.uniform(-2.5, 2.5) + bx, np.random.uniform(-2.5, 2.5) + by + 4.0, -55.0])
                    for z_coord in np.linspace(-50.0, 0.0, 15):
                        bx, by = get_bend_offsets(z_coord)
                        bolt.append([np.random.uniform(-2.5, 2.5) + bx, np.random.uniform(-2.5, 2.5) + by + 4.0, z_coord])
                    self.active_lightning_bolts.append(bolt)
            if routine_name == "Supernova":
                self.wormhole_supernova_active = True
                self.wormhole_supernova_age = 0.0
                for k in range(120):
                    idx = self.next_spark_idx
                    self.spark_pos[idx] = [0.0, 0.0, -15.0]
                    theta_v = np.random.uniform(0.0, 2.0 * np.pi)
                    phi_v = np.random.uniform(-np.pi / 2.0, np.pi / 2.0)
                    speed_v = np.random.uniform(10.0, 20.0)
                    vx = speed_v * np.cos(phi_v) * np.cos(theta_v)
                    vy = speed_v * np.cos(phi_v) * np.sin(theta_v)
                    vz = speed_v * np.sin(phi_v)
                    
                    self.spark_vel[idx] = [vx, vy, vz]
                    self.spark_col[idx] = [1.0, 0.9, 0.7, 1.0] if k % 2 == 0 else [0.2, 0.8, 1.0, 1.0]
                    self.spark_size[idx] = np.random.uniform(9.0, 15.0)
                    self.spark_age[idx] = 0.0
                    self.spark_max_age[idx] = np.random.uniform(1.2, 2.0)
                    self.spark_active[idx] = True
                    self.next_spark_idx = (self.next_spark_idx + 1) % len(self.spark_pos)
            elif routine_name == "Shooting Star":
                self.wormhole_shooting_star_active = True
                self.wormhole_shooting_star_z = -55.0
                self.wormhole_shooting_star_x = np.random.uniform(-3.0, 3.0)
                self.wormhole_shooting_star_y = np.random.uniform(-3.0, 3.0)
                for ss in range(6):
                    ss_x = np.random.uniform(-5.0, 5.0)
                    ss_y = np.random.uniform(-5.0, 5.0)
                    ss_z = -55.0
                    for k in range(15):
                        idx = self.next_spark_idx
                        self.spark_pos[idx] = [ss_x, ss_y, ss_z - k * 0.8]
                        self.spark_vel[idx] = [0.0, 0.0, 35.0]
                        self.spark_col[idx] = [1.0, 0.95, 0.8, 1.0]
                        self.spark_size[idx] = np.random.uniform(8.0, 12.0) - k * 0.4
                        self.spark_age[idx] = 0.0
                        self.spark_max_age[idx] = np.random.uniform(1.5, 2.2)
                        self.spark_active[idx] = True
                        self.next_spark_idx = (self.next_spark_idx + 1) % len(self.spark_pos)
            else:
                near_gems = np.where((self.gem_z < 0.0) & (self.gem_z > -50.0))[0]
                if len(near_gems) > 0:
                    for _ in range(25):
                        g_idx = random.choice(near_gems)
                        self.spawn_gem_sparks(g_idx)
                        for s_offset in range(6):
                            s_idx = (self.next_spark_idx - s_offset - 1) % len(self.spark_pos)
                            if self.spark_active[s_idx]:
                                self.spark_vel[s_idx] *= 1.8
                                self.spark_size[s_idx] *= 1.6
                                
        elif self.major_mode == "MANDALA Sacred":
            if routine_name == "Peace Symbol":
                self.peace_symbol_timer = 5.0
                for idx in range(len(self.mandala_base_pos)):
                    self.mandala_base_pos[idx] = [0.0, 4.0, 0.0]
                    angle = (idx / len(self.mandala_base_pos)) * 2.0 * np.pi
                    speed = np.random.uniform(9.0, 14.0)
                    self.mandala_base_vel[idx, 0] = speed * np.cos(angle)
                    self.mandala_base_vel[idx, 1] = speed * np.sin(angle)
                    self.mandala_base_vel[idx, 2] = np.random.uniform(-0.5, 0.5)
                    self.mandala_base_ages[idx] = 0.0
                    self.mandala_base_max_ages[idx] = np.random.uniform(2.0, 3.0)
                    self.mandala_base_col[idx] = [1.0, 0.8, 0.1, 1.0] if idx % 2 == 0 else [1.0, 0.3, 0.2, 1.0]
                    self.mandala_base_size[idx] = np.random.uniform(10.0, 16.0)
            elif routine_name == "Halo Effect":
                self.halo_timer = 5.0
                for idx in range(len(self.mandala_base_pos)):
                    self.mandala_base_pos[idx] = [0.0, 4.0, 0.0]
                    angle = (idx / len(self.mandala_base_pos)) * 2.0 * np.pi
                    speed = np.random.uniform(11.0, 17.0)
                    self.mandala_base_vel[idx, 0] = speed * np.cos(angle)
                    self.mandala_base_vel[idx, 1] = speed * np.sin(angle)
                    self.mandala_base_vel[idx, 2] = np.random.uniform(-0.5, 0.5)
                    self.mandala_base_ages[idx] = 0.0
                    self.mandala_base_max_ages[idx] = np.random.uniform(2.2, 3.5)
                    self.mandala_base_col[idx] = [0.15, 0.85, 1.0, 1.0] if idx % 2 == 0 else [0.9, 0.15, 0.5, 1.0]
                    self.mandala_base_size[idx] = np.random.uniform(12.0, 20.0)
            elif routine_name == "Supernova":
                # Explode all mandala particles radially
                for idx in range(len(self.mandala_base_pos)):
                    self.mandala_base_pos[idx] = [0.0, 4.0, 0.0]
                    angle = (idx / len(self.mandala_base_pos)) * 2.0 * np.pi
                    speed = np.random.uniform(10.0, 15.0)
                    self.mandala_base_vel[idx, 0] = speed * np.cos(angle)
                    self.mandala_base_vel[idx, 1] = speed * np.sin(angle)
                    self.mandala_base_vel[idx, 2] = np.random.uniform(-1.0, 1.0)
                    self.mandala_base_ages[idx] = 0.0
                    self.mandala_base_max_ages[idx] = np.random.uniform(2.2, 3.5)
                    self.mandala_base_col[idx] = [1.0, 0.95, 0.8, 1.0] if idx % 2 == 0 else [0.95, 0.25, 0.85, 1.0]
                    self.mandala_base_size[idx] = np.random.uniform(14.0, 22.0)
            elif routine_name == "Shooting Star":
                # Contracting cosmic shooting stars inwards
                for idx in range(100):
                    angle = np.random.uniform(0.0, 2 * np.pi)
                    rad = 12.0
                    self.mandala_base_pos[idx] = [rad * np.cos(angle), 4.0 + rad * np.sin(angle), np.random.uniform(-0.5, 0.5)]
                    speed = -np.random.uniform(6.0, 10.0)
                    self.mandala_base_vel[idx, 0] = speed * np.cos(angle)
                    self.mandala_base_vel[idx, 1] = speed * np.sin(angle)
                    self.mandala_base_vel[idx, 2] = np.random.uniform(-0.1, 0.1)
                    self.mandala_base_ages[idx] = 0.0
                    self.mandala_base_max_ages[idx] = np.random.uniform(1.8, 2.8)
                    self.mandala_base_col[idx] = [0.1, 0.9, 1.0, 1.0]
                    self.mandala_base_size[idx] = np.random.uniform(8.0, 14.0)
        elif self.major_mode == "SYNAESTHESIA Classic":
            self.trigger_syn_star_burst()

    def spawn_rarity(self, r_type):
        print(f"SPAWNING RARITY: {r_type}!")
        if r_type == "SQUID":
            pos = np.array([np.random.uniform(-4.0, 4.0), np.random.uniform(1.0, 2.5), np.random.uniform(0.0, 4.0)], dtype=np.float32)
            # Restrict squid direction vector to within 30 degrees of camera-perpendicular X-Y plane
            theta = np.random.uniform(0.0, 2.0 * np.pi)
            dx = np.cos(theta)
            dy = np.sin(theta)
            dz = np.random.uniform(-0.45, 0.45)
            direction = np.array([dx, dy, dz], dtype=np.float32)
            direction /= np.linalg.norm(direction)
            self.squid_pos = pos
            self.squid_dir = direction
            self.squid_vel = direction * 1.0 # slowed down to 1/4 from 4.0
            self.squid_phase = 0.0
            self.active_rarity = {
                'type': 'SQUID',
                'life': 30.0,
                'max_life': 30.0
            }
        elif r_type == "MANTA":
            # Expand spawn starting point to -24.0 for full screen boundary clearance
            pos = np.array([-24.0, np.random.uniform(2.0, 7.0), np.random.uniform(0.0, 6.0)], dtype=np.float32)
            direction = np.array([1.0, np.random.uniform(-0.1, 0.1), np.random.uniform(-0.1, 0.1)], dtype=np.float32)
            direction /= np.linalg.norm(direction)
            self.active_rarity = {
                'type': 'MANTA',
                'pos': pos,
                'dir': direction,
                'vel': direction * 1.75,
                'phase': 0.0,
                'life': 25.0,
                'max_life': 25.0
            }
        elif r_type == "SEAHORSE":
            # Spawn just below seabed (Y=-6.0) so it rises into view quickly
            pos = np.array([np.random.uniform(-4.0, 4.0), -6.0, np.random.uniform(1.0, 5.0)], dtype=np.float32)
            direction = np.array([np.random.uniform(-0.15, 0.15), 1.0, np.random.uniform(-0.15, 0.15)], dtype=np.float32)
            direction /= np.linalg.norm(direction)
            self.active_rarity = {
                'type': 'SEAHORSE',
                'pos': pos,
                'dir': direction,
                'vel': direction * 1.15, # majestic upward swim speed
                'phase': 0.0,
                'life': 30.0,
                'max_life': 30.0
            }
        elif r_type == "LANTERN_FISH":
            # Spawn at -24.0 horizontally and keep deep in background (Z in [-15.0, -13.0])
            pos = np.array([-24.0, np.random.uniform(1.0, 7.0), np.random.uniform(-15.0, -13.0)], dtype=np.float32)
            direction = np.array([1.0, np.random.uniform(-0.1, 0.1), np.random.uniform(-0.1, 0.1)], dtype=np.float32)
            direction /= np.linalg.norm(direction)
            offsets = [np.array([np.random.uniform(-1.5, 1.5), np.random.uniform(-1.2, 1.2), np.random.uniform(-1.0, 1.0)], dtype=np.float32) for _ in range(8)]
            self.active_rarity = {
                'type': 'LANTERN_FISH',
                'pos': pos,
                'dir': direction,
                'vel': direction * 1.4, # slowed from 2.2 to 1.4
                'offsets': offsets,
                'life': 30.0,
                'max_life': 30.0
            }
        elif r_type == "PLANET":
            # Gas giant planet initialization
            ang = np.random.uniform(0.0, 2 * np.pi)
            r_dist = 13.0
            pos = np.array([r_dist * np.cos(ang), r_dist * np.sin(ang), -55.0], dtype=np.float32)
            style = "NEPTUNE"
            self.active_rarity = {
                'type': 'PLANET',
                'pos': pos,
                'vel': np.array([0.0, 0.0, 15.0], dtype=np.float32),
                'phase': 0.0,
                'style': style,
                'life': 7.0,
                'max_life': 7.0
            }
        elif r_type == "GALAXY":
            # Move Galaxy farther away in background
            ang = np.random.uniform(0.0, 2 * np.pi)
            r_dist = 22.0
            pos = np.array([r_dist * np.cos(ang), r_dist * np.sin(ang), -85.0], dtype=np.float32)
            self.active_rarity = {
                'type': 'GALAXY',
                'pos': pos,
                'vel': np.array([0.0, 0.0, 3.2], dtype=np.float32),
                'phase': 0.0,
                'life': 31.0,
                'max_life': 31.0
            }
        elif r_type == "ASTEROIDS":
            pos = np.array([0.0, 0.0, -55.0], dtype=np.float32)
            offsets = [np.random.uniform(-15.0, 15.0, 3) for _ in range(10)]
            for ao in offsets:
                ao[2] = np.random.uniform(-8.0, 8.0)
                ao[0] = np.sign(ao[0]) * max(11.0, abs(ao[0]))
                ao[1] = np.sign(ao[1]) * max(11.0, abs(ao[1]))
            self.active_rarity = {
                'type': 'ASTEROIDS',
                'pos': pos,
                'vel': np.array([0.0, 0.0, 23.0], dtype=np.float32),
                'offsets': offsets,
                'rotations': [np.random.uniform(0.0, 2*np.pi) for _ in range(10)],
                'rot_vels': [np.random.uniform(0.5, 2.5) for _ in range(10)],
                'life': 5.0,
                'max_life': 5.0
            }

        elif r_type == "CATHERINE_WHEEL":
            # Move Catherine Wheel center up to align with screen bottom (Y = -4.5)
            pos = np.array([np.random.uniform(-10.0, 10.0), -4.5, np.random.uniform(-5.0, -1.0)], dtype=np.float32)
            self.active_rarity = {
                'type': 'CATHERINE_WHEEL',
                'pos': pos,
                'phase': 0.0,
                'spin_vel': 18.0,
                'sparks_pos': [],
                'sparks_vel': [],
                'sparks_col': [],
                'sparks_age': [],
                'life': 10.0,
                'max_life': 10.0
            }
        elif r_type == "BIRD":
            self.active_rarity = {
                'type': 'BIRD',
                'pos': np.array([0.0, 4.0, 0.0], dtype=np.float32),
                'ang': np.random.uniform(0.0, 2*np.pi),
                'phase': 0.0,
                'life': 12.0,
                'max_life': 12.0
            }
        elif r_type == "SMOKE":
            self.active_rarity = {
                'type': 'SMOKE',
                'particles_pos': [],
                'particles_ang': [],
                'particles_rad': [],
                'life': 6.0,
                'max_life': 6.0
            }
        elif r_type == "SUN_BURST":
            self.active_rarity = {
                'type': 'SUN_BURST',
                'phase': 0.0,
                'life': 3.5,
                'max_life': 3.5
            }
        elif r_type == "BUTTERFLY":
            self.active_rarity = {
                'type': 'BUTTERFLY',
                'pos': np.array([0.0, 4.0, 0.0], dtype=np.float32),
                'ang': np.random.uniform(0.0, 2*np.pi),
                'phase': 0.0,
                'life': 15.0,
                'max_life': 15.0
            }

    def update_active_rarity(self, dt):
        r = self.active_rarity
        r['life'] -= dt
        if r['life'] <= 0.0:
            self.active_rarity = None
            return
        t_type = r['type']
        if t_type == "SQUID":
            # Squid is updated inside update_underwater_mode
            pass
        elif t_type == "MANTA":
            r['pos'] += r['vel'] * dt
            # Precisely match the wing flap to the music track's BPM (1 flap every 8 beats)
            r['phase'] += dt * (self.script_bpm / 60.0) * 0.25 * np.pi
            # Fully swims off the screen boundaries before deactivating
            if r['pos'][0] > 24.0:
                self.active_rarity = None
        elif t_type == "SEAHORSE":
            r['pos'] += r['vel'] * dt
            # Bobbing phase synchronized with audio
            r['phase'] += dt * (2.5 + self.react_bass * 5.0)
            # Add horizontal/vertical bobbing physics synchronized with audio
            bob_h = np.sin(r['phase'] * 1.2) * 0.8 * (1.0 + self.react_bass * 1.5)
            bob_v = np.cos(r['phase'] * 0.8) * 0.65 * (1.0 + self.react_bass * 1.5)
            r['pos'][0] += bob_h * dt
            r['pos'][1] += bob_v * dt
            # Fully bob/swim off screen boundaries before deactivating
            if r['pos'][1] > 11.0:
                self.active_rarity = None
        elif t_type == "LANTERN_FISH":
            r['pos'] += r['vel'] * dt
            # Fully swims off screen boundaries before deactivating
            if r['pos'][0] > 24.0:
                self.active_rarity = None
        elif t_type == "PLANET":
            r['pos'] += r['vel'] * dt
            r['phase'] += dt * 0.75
            if r['pos'][2] > 18.0:
                self.active_rarity = None
        elif t_type == "GALAXY":
            r['pos'] += r['vel'] * dt
            r['phase'] += dt * 0.5
            if r['pos'][2] > 18.0:
                self.active_rarity = None
        elif t_type == "ASTEROIDS":
            r['pos'] += r['vel'] * dt
            for i in range(len(r['rotations'])):
                r['rotations'][i] += r['rot_vels'][i] * dt
            if r['pos'][2] > 18.0:
                self.active_rarity = None

        elif t_type == "CATHERINE_WHEEL":
            r['phase'] += r['spin_vel'] * dt
            for i in range(4):
                ang = r['phase'] + i * (np.pi / 2.0)
                nozzle_pos = r['pos'] + np.array([np.cos(ang) * 0.5, np.sin(ang) * 0.5, 0.0], dtype=np.float32)
                out_dir = np.array([np.cos(ang), np.sin(ang), np.random.uniform(-0.15, 0.15)], dtype=np.float32)
                tangent_dir = np.array([-np.sin(ang), np.cos(ang), 0.0], dtype=np.float32)
                spark_vel = out_dir * np.random.uniform(6.0, 12.0) + tangent_dir * 8.0
                r['sparks_pos'].append(nozzle_pos)
                r['sparks_vel'].append(spark_vel)
                r['sparks_col'].append(random.choice([
                    [1.0, 0.8, 0.1, 1.0],
                    [0.9, 0.9, 0.95, 1.0],
                    [1.0, 0.3, 0.1, 1.0]
                ]))
                r['sparks_age'].append(0.0)
            rem_pos, rem_vel, rem_col, rem_age = [], [], [], []
            for j in range(len(r['sparks_pos'])):
                r['sparks_age'][j] += dt
                if r['sparks_age'][j] < 0.8:
                    r['sparks_vel'][j][1] -= 9.8 * dt # gravity
                    next_pos = r['sparks_pos'][j] + r['sparks_vel'][j] * dt
                    # Bounce or slide realistically on the floor plane Y = -12.0
                    if next_pos[1] < -12.0:
                        next_pos[1] = -12.0
                        r['sparks_vel'][j][1] = -r['sparks_vel'][j][1] * 0.45 # bounce elasticity
                        r['sparks_vel'][j][0] *= 0.85 # friction
                        r['sparks_vel'][j][2] *= 0.85 # friction
                    r['sparks_pos'][j] = next_pos
                    r['sparks_col'][j][3] = 1.0 - (r['sparks_age'][j] / 0.8)
                    rem_pos.append(r['sparks_pos'][j])
                    rem_vel.append(r['sparks_vel'][j])
                    rem_col.append(r['sparks_col'][j])
                    rem_age.append(r['sparks_age'][j])
            r['sparks_pos'] = rem_pos
            r['sparks_vel'] = rem_vel
            r['sparks_col'] = rem_col
            r['sparks_age'] = rem_age
        elif t_type == "BIRD":
            r['phase'] += dt * 15.0
            speed = 4.2 * (1.0 + self.react_mid * 0.5)
            r['pos'][0] += np.cos(r['ang']) * speed * dt
            r['pos'][1] += np.sin(r['ang']) * speed * dt
            # Fully flies off screen boundaries before deactivating
            if np.linalg.norm(r['pos'] - np.array([0.0, 4.0, 0.0])) > 24.0:
                self.active_rarity = None
        elif t_type == "SMOKE":
            # Spawn 4 smoke particles per frame at slightly offset spiral progression angles
            for step in range(4):
                ang = (r['life'] * 3.5 + step * 0.15) % (2.0 * np.pi)
                r['particles_pos'].append(np.array([0.0, 4.0, 0.0], dtype=np.float32))
                r['particles_ang'].append(ang)
                r['particles_rad'].append(0.0)
            rem_pos, rem_ang, rem_rad = [], [], []
            for j in range(len(r['particles_pos'])):
                r['particles_rad'][j] += dt * 2.8 * (1.0 + self.react_mid * 0.4)
                r['particles_ang'][j] += dt * 3.0
                rad = r['particles_rad'][j]
                theta = r['particles_ang'][j]
                r['particles_pos'][j] = np.array([rad * np.cos(theta), 4.0 + rad * np.sin(theta), np.sin(theta * 2.0) * 0.15], dtype=np.float32)
                if rad < 12.0:
                    rem_pos.append(r['particles_pos'][j])
                    rem_ang.append(r['particles_ang'][j])
                    rem_rad.append(r['particles_rad'][j])
            r['particles_pos'] = rem_pos
            r['particles_ang'] = rem_ang
            r['particles_rad'] = rem_rad
        elif t_type == "SUN_BURST":
            r['phase'] += dt * 0.4
        elif t_type == "BUTTERFLY":
            # Music-modulated wing flap rate
            flap_rate = 24.0 + self.react_treble * 35.0
            r['phase'] += dt * flap_rate
            # Music-modulated turning angles/speeds
            erratic_factor = 6.0 + self.react_bass * 12.0
            r['ang'] += np.random.uniform(-1.8, 1.8) * dt * erratic_factor
            # Music-modulated speed and bobbing amplitude
            speed = 3.6 + self.react_mid * 5.0
            bob_amp = 1.5 + self.react_bass * 4.0
            r['pos'][0] += (np.cos(r['ang']) * speed + np.sin(r['phase'] * 3.0) * bob_amp) * dt
            r['pos'][1] += (np.sin(r['ang']) * speed + np.cos(r['phase'] * 3.5) * bob_amp) * dt
            # Fully flies off screen boundaries before deactivating
            if np.linalg.norm(r['pos'] - np.array([0.0, 4.0, 0.0])) > 24.0:
                self.active_rarity = None

    def update_rarity_system(self, dt):
        if self.active_rarity is None and self.rarity_queued_type is None:
            self.rarity_cooldown += dt
            if self.rarity_cooldown >= RARITY_INTERVAL:
                if self.major_mode == "UNDERWATER Lava":
                    self.rarity_queued_type = random.choice(["SQUID", "MANTA", "SEAHORSE", "LANTERN_FISH"])
                elif self.major_mode == "TUNNEL Wormhole":
                    self.rarity_queued_type = random.choice(["PLANET", "GALAXY", "ASTEROIDS"])
                elif self.major_mode == "FIREWORKS":
                    self.rarity_queued_type = "CATHERINE_WHEEL" 
                elif self.major_mode == "MANDALA Sacred":
                    self.rarity_queued_type = random.choice(["BIRD", "SMOKE", "SUN_BURST", "BUTTERFLY"])
                if self.rarity_queued_type is not None:
                    print(f"Rarity queued: {self.rarity_queued_type}. Waiting for significant beat...")
                    self.rarity_cooldown = 0.0
        if self.rarity_queued_type is not None:
            if self.react_bass > .54:
                self.spawn_rarity(self.rarity_queued_type)
                self.rarity_queued_type = None
        if self.active_rarity is not None:
            self.update_active_rarity(dt)

    def trigger_routine(self, name, launch_func):
        self.routine_queue.clear()
        self.active_routine_name = name
        self.routine_timer = 5.0
        launch_func()

    def launch_american_flag(self):
        # Red stripes
        for x in [-9.0, -3.0, 3.0, 9.0]:
            self.routine_queue.append((0.0, Firework(fw_type=0, color=COLORS["strontium_red"], x_offset=x)))
        # White stripes
        for x in [-6.0, 0.0, 6.0]:
            self.routine_queue.append((0.2, Firework(fw_type=1, color=COLORS["magnesium_white"], x_offset=x)))
        # Blue canton stars
        for x in [-11.0, -7.0]:
            fw = Firework(fw_type=3, color=COLORS["copper_blue"], x_offset=x)
            fw.launch_vel[1] += 3.0
            self.routine_queue.append((0.4, fw))

    def launch_liberty_bell(self):
        # Top of the bell
        top_crown = Firework(fw_type=12, color=COLORS["sodium_gold"], x_offset=0.0)
        top_crown.launch_vel[1] += 4.0
        self.routine_queue.append((0.0, top_crown))
        
        # Sides of the bell fanning down
        left_waterfall = Firework(fw_type=5, color=COLORS["sodium_gold"], x_offset=-4.0)
        left_waterfall.launch_vel[0] = -1.5
        right_waterfall = Firework(fw_type=5, color=COLORS["sodium_gold"], x_offset=4.0)
        right_waterfall.launch_vel[0] = 1.5
        self.routine_queue.append((0.2, left_waterfall))
        self.routine_queue.append((0.2, right_waterfall))
        
        # Clapper at bottom cracking/crackling
        clapper = Firework(fw_type=15, color=COLORS["magnesium_white"], x_offset=0.0)
        clapper.launch_vel[1] -= 2.0
        self.routine_queue.append((0.5, clapper))

    def launch_statue_of_liberty(self):
        # Pedestal/Body (green waterfall)
        body = Firework(fw_type=5, color=COLORS["barium_green"], x_offset=-2.0)
        self.routine_queue.append((0.0, body))
        
        # Crown Rays (radiating green ghost rings)
        for idx, (x, vx) in enumerate([(-6.0, -3.0), (-2.0, -1.0), (2.0, 1.0)]):
            ray = Firework(fw_type=3, color=COLORS["barium_green"], x_offset=x)
            ray.launch_vel[0] = vx
            self.routine_queue.append((0.1 * idx, ray))
            
        # Golden Torch (high up on the right)
        torch = Firework(fw_type=11, color=COLORS["sodium_gold"], x_offset=3.0)
        torch.launch_vel[1] += 5.0
        torch.launch_vel[0] = 1.5
        self.routine_queue.append((0.4, torch))

    def launch_flower_bouquet(self):
        colors = [COLORS["strontium_red"], COLORS["barium_green"], COLORS["potassium_purple"], COLORS["calcium_orange"], COLORS["sodium_gold"]]
        types = [0, 1, 11]
        for idx, x in enumerate([-8.0, -4.0, 0.0, 4.0, 8.0]):
            col = colors[idx % len(colors)]
            t = types[idx % len(types)]
            fw = Firework(fw_type=t, color=col, x_offset=x)
            fw.launch_vel[0] = x * 0.4
            self.routine_queue.append((0.0, fw))

    def launch_the_dragon(self):
        for i in range(12):
            delay = i * 0.15
            x = -12.0 + i * 2.0
            col = COLORS["barium_green"] if i % 2 == 0 else COLORS["sodium_gold"]
            t = 17 if i % 2 == 0 else 6
            fw = Firework(fw_type=t, color=col, x_offset=x)
            fw.launch_vel[0] = -1.0 + (i * 0.2)
            self.routine_queue.append((delay, fw))
            
    def launch_supernova(self):
        fw_center = Firework(fw_type=4, color=COLORS["magnesium_white"], x_offset=0.0)
        fw_center.launch_vel = np.array([0.0, 26.0, 0.0], dtype=np.float32)
        fw_center.star_size = 15.0
        fw_center.secondary_color = COLORS["copper_blue"]
        self.routine_queue.append((0.0, fw_center))
        
        for angle in np.linspace(0, 2 * np.pi, 6, endpoint=False):
            x = 8.0 * np.cos(angle)
            z = 6.0 * np.sin(angle)
            fw_ring = Firework(fw_type=7, color=COLORS["sodium_gold"], x_offset=x)
            fw_ring.launch_pos[2] = z
            fw_ring.launch_vel = np.array([x * 0.15, 23.0, z * 0.15], dtype=np.float32)
            fw_ring.secondary_color = COLORS["potassium_purple"]
            self.routine_queue.append((0.4, fw_ring))
            
        for x in [-5.0, 5.0]:
            fw_crack = Firework(fw_type=15, color=COLORS["magnesium_white"], x_offset=x)
            fw_crack.launch_vel[1] = 24.0
            self.routine_queue.append((1.2, fw_crack))
            
    def launch_shooting_star(self):
        fw_left = Firework(fw_type=18, color=COLORS["magnesium_white"], x_offset=-14.0)
        fw_left.launch_vel = np.array([12.0, 16.0, -2.0], dtype=np.float32)
        fw_left.launch_fuse = 2.0
        fw_left.star_size = 10.0
        fw_left.secondary_color = COLORS["sodium_gold"]
        self.routine_queue.append((0.0, fw_left))
        
        fw_right = Firework(fw_type=18, color=COLORS["magnesium_white"], x_offset=14.0)
        fw_right.launch_vel = np.array([-12.0, 17.0, 2.0], dtype=np.float32)
        fw_right.launch_fuse = 2.0
        fw_right.star_size = 10.0
        fw_right.secondary_color = COLORS["sodium_gold"]
        self.routine_queue.append((0.3, fw_right))
        
        fw_mid = Firework(fw_type=10, color=COLORS["copper_blue"], x_offset=0.0)
        fw_mid.launch_vel = np.array([0.0, 25.0, -1.0], dtype=np.float32)
        fw_mid.secondary_color = COLORS["magnesium_white"]
        self.routine_queue.append((0.6, fw_mid))

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
        
        # Dynamic Jellyfish Hood Buffers Setup
        self.hood_vao = gl.glGenVertexArrays(1)
        self.hood_pos_vbo, self.hood_col_vbo = gl.glGenBuffers(2)
        
        gl.glBindVertexArray(self.hood_vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.hood_pos_vbo)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.hood_col_vbo)
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
        self.part_star_shape_loc = gl.glGetUniformLocation(self.particle_program, "uStarShape")
        self.sky_time_loc = gl.glGetUniformLocation(self.sky_program, "uTime")
        self.sky_ripple_loc = gl.glGetUniformLocation(self.sky_program, "uRipple")
        self.sky_climax_flash_loc = gl.glGetUniformLocation(self.sky_program, "uClimaxFlash")
        self.sky_bend_x_loc = gl.glGetUniformLocation(self.sky_program, "uWormholeBendX")
        self.sky_bend_y_loc = gl.glGetUniformLocation(self.sky_program, "uWormholeBendY")
        self.sky_phase_x_loc = gl.glGetUniformLocation(self.sky_program, "uWormholePhaseX")
        self.sky_phase_y_loc = gl.glGetUniformLocation(self.sky_program, "uWormholePhaseY")
        self.sky_react_bass_loc = gl.glGetUniformLocation(self.sky_program, "uReactBass")
        self.sky_react_treble_loc = gl.glGetUniformLocation(self.sky_program, "uReactTreble")
        self.sky_react_mid_loc = gl.glGetUniformLocation(self.sky_program, "uReactMid")
        self.sky_aspect_loc = gl.glGetUniformLocation(self.sky_program, "uAspect")
        self.sky_inv_vp_loc = gl.glGetUniformLocation(self.sky_program, "uInvVP")

    def on_render(self, area, context):
        get_bend_offsets = self.get_bend_offsets
        if self.sky_program is None:
            return False
            
        w = area.get_width()
        h = area.get_height()
        scale = area.get_scale_factor()
        w_phys = w * scale
        h_phys = h * scale
        aspect = w_phys / h_phys if h_phys > 0 else 1.0
        
        # Compute CPU Projection and View Matrices early so the fullscreen background shader can perform world-space tracking
        proj_matrix = perspective_matrix(50.0, aspect, 0.1, 150.0)
        cx = self.camera_dist * np.cos(self.camera_phi) * np.sin(self.camera_theta)
        cy = self.camera_dist * np.sin(self.camera_phi)
        cz = self.camera_dist * np.cos(self.camera_phi) * np.cos(self.camera_theta)
        view_matrix = look_at_matrix([cx, cy, cz], [0.0, 4.0, 0.0], [0.0, 1.0, 0.0])
        
        # Ensure active mode is initialized before rendering or binding uniforms
        if self.major_mode == "TUNNEL Wormhole":
            if not hasattr(self, 'gem_z'):
                self.init_tunnel_mode()
        elif self.major_mode == "UNDERWATER Lava":
            if not hasattr(self, 'bubble_pos'):
                self.init_underwater_mode()
        elif self.major_mode == "MANDALA Sacred":
            if not hasattr(self, 'mandala_base_pos'):
                self.init_mandala_mode()
        
        # Open recording process if first frame
        if hasattr(self, 'is_recording') and self.is_recording and self.ffmpeg_process is None:
            self.start_recording_process(w_phys, h_phys)
            
        # If we are recording, run the tick update first to compute the state at self.record_time
        if hasattr(self, 'is_recording') and self.is_recording:
            self.on_recording_tick()
        
        gl.glViewport(0, 0, w_phys, h_phys)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        
        # 1. Draw Fullscreen Sky Gradient or Raymarched Plasma Wormhole (Depth Testing Off)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glUseProgram(self.sky_program)
        if hasattr(self, 'sky_time_loc') and self.sky_time_loc != -1:
            gl.glUniform1f(self.sky_time_loc, self.get_sim_time())
            
        if hasattr(self, 'sky_climax_flash_loc') and self.sky_climax_flash_loc != -1:
            gl.glUniform1f(self.sky_climax_flash_loc, self.climax_flash)
            
        if hasattr(self, 'sky_ripple_loc') and self.sky_ripple_loc != -1:
            if self.major_mode == "UNDERWATER Lava":
                gl.glUniform1f(self.sky_ripple_loc, 1.0)
            elif self.major_mode == "TUNNEL Wormhole":
                gl.glUniform1f(self.sky_ripple_loc, 2.0)
            else:
                gl.glUniform1f(self.sky_ripple_loc, 0.0)
                
        # Send full coordinates and audio parameters for continuous GPU raymarching in Wormhole Mode
        if self.major_mode == "TUNNEL Wormhole":
            if hasattr(self, 'sky_bend_x_loc') and self.sky_bend_x_loc != -1:
                gl.glUniform1f(self.sky_bend_x_loc, self.wormhole_bend_x)
            if hasattr(self, 'sky_bend_y_loc') and self.sky_bend_y_loc != -1:
                gl.glUniform1f(self.sky_bend_y_loc, self.wormhole_bend_y)
            if hasattr(self, 'sky_phase_x_loc') and self.sky_phase_x_loc != -1:
                gl.glUniform1f(self.sky_phase_x_loc, self.wormhole_phase_x)
            if hasattr(self, 'sky_phase_y_loc') and self.sky_phase_y_loc != -1:
                gl.glUniform1f(self.sky_phase_y_loc, self.wormhole_phase_y)
            if hasattr(self, 'sky_react_bass_loc') and self.sky_react_bass_loc != -1:
                gl.glUniform1f(self.sky_react_bass_loc, self.react_bass_smooth)
            if hasattr(self, 'sky_react_treble_loc') and self.sky_react_treble_loc != -1:
                gl.glUniform1f(self.sky_react_treble_loc, self.react_treble)
            if hasattr(self, 'sky_react_mid_loc') and self.sky_react_mid_loc != -1:
                gl.glUniform1f(self.sky_react_mid_loc, self.react_mid)
            if hasattr(self, 'sky_aspect_loc') and self.sky_aspect_loc != -1:
                gl.glUniform1f(self.sky_aspect_loc, aspect)
            if hasattr(self, 'sky_inv_vp_loc') and self.sky_inv_vp_loc != -1:
                vp = proj_matrix @ view_matrix
                inv_vp = np.linalg.inv(vp)
                gl.glUniformMatrix4fv(self.sky_inv_vp_loc, 1, gl.GL_TRUE, inv_vp)
                
        gl.glBindVertexArray(self.sky_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_FAN, 0, 4)
        gl.glBindVertexArray(0)
        
        # Enable Depth Testing and Additive Blending for World Render
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
        
        # 2. Gather, Buffer and Render All Line Geometries (Ground Grid & Rocket Trails)
        line_pos = []
        line_col = []
        
        # Draw Jagged Lightning Bolts down the Tunnel during Lightning Flash event
        if self.major_mode == "TUNNEL Wormhole" and self.lightning_active_timer > 0.0:
            # Jagged paths in line segments
            for bolt in self.active_lightning_bolts:
                if len(bolt) > 1:
                    for idx in range(len(bolt) - 1):
                        line_pos.append(bolt[idx])
                        line_pos.append(bolt[idx + 1])
                        # strobe color
                        line_col.append([0.85, 0.95, 1.0, 1.0])
                        line_col.append([0.85, 0.95, 1.0, 1.0])
                        
        # Draw massive, central fly-by Shooting Star trail inside Wormhole
        if self.major_mode == "TUNNEL Wormhole" and self.wormhole_shooting_star_active:
            # Create dynamic segment lines representing a trail behind the star
            head_z = self.wormhole_shooting_star_z
            for t_seg in range(12):
                z0 = head_z - t_seg * 1.5
                z1 = head_z - (t_seg + 1) * 1.5
                bx0, by0 = get_bend_offsets(z0)
                bx1, by1 = get_bend_offsets(z1)
                line_pos.append([self.wormhole_shooting_star_x + bx0, self.wormhole_shooting_star_y + by0 + 4.0, z0])
                line_pos.append([self.wormhole_shooting_star_x + bx1, self.wormhole_shooting_star_y + by1 + 4.0, z1])
                alpha = np.clip((1.0 - t_seg / 12.0) * ((z0 + 50.0)/50.0), 0.0, 1.0)
                line_col.append([0.15, 0.85, 1.0, alpha])
                line_col.append([0.15, 0.85, 1.0, alpha])
        
        # Draw Reference Ground Grid (unless in Underwater Mode)
        if self.major_mode != "UNDERWATER Lava":
            grid_y = -12.0
            grid_range = 30.0
            steps = 10
            for i in range(steps + 1):
                val = -grid_range + (2.0 * grid_range / steps) * i
                grid_alpha = 0.08 + self.react_bass * 0.15
                grid_col = (0.15, 0.15, 0.3 + self.react_bass * 0.4, grid_alpha)
                
                line_pos.append([val, grid_y, -grid_range])
                line_pos.append([val, grid_y, grid_range])
                line_col.append(grid_col)
                line_col.append(grid_col)
                
                line_pos.append([-grid_range, grid_y, val])
                line_pos.append([grid_range, grid_y, val])
                line_col.append(grid_col)
                line_col.append(grid_col)
            
        # Add Rocket Launch Trails to Line Buffer
        if self.show_rockets and self.major_mode == "FIREWORKS":
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
        
        if self.major_mode == "FIREWORKS":
            for fw in self.fireworks:
                if fw.state == 'LAUNCH':
                    if self.show_rockets:
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
                            

            # Draw Catherine Wheel Nozzle sparks & Pinwheel
            if self.active_rarity is not None and self.active_rarity['type'] == 'CATHERINE_WHEEL':
                r = self.active_rarity
                # Removed central star at the middle completely!
                if len(r['sparks_pos']) > 0:
                    part_pos.append(r['sparks_pos'])
                    part_col.append(r['sparks_col'])
                    part_size.append(np.full(len(r['sparks_pos']), 4.5, dtype=np.float32))
        elif self.major_mode == "TUNNEL Wormhole":
            if not hasattr(self, 'gem_z'):
                self.init_tunnel_mode()
            t_pos, t_col, t_size, h_pos, h_col = self.render_tunnel()
            part_pos.append(t_pos)
            part_col.append(t_col)
            part_size.append(t_size)
        elif self.major_mode == "UNDERWATER Lava":
            if not hasattr(self, 'bubble_pos'):
                self.init_underwater_mode()
            u_pos, u_col, u_size, h_pos, h_col = self.render_underwater()
            part_pos.append(u_pos)
            part_col.append(u_col)
            part_size.append(u_size)
        elif self.major_mode == "MANDALA Sacred":
            if not hasattr(self, 'mandala_base_pos'):
                self.init_mandala_mode()
            m_pos, m_col, m_size, h_pos, h_col = self.render_mandala()
            part_pos.append(m_pos)
            part_col.append(m_col)
            part_size.append(m_size)
        elif self.major_mode == "SYNAESTHESIA Classic":
            if not hasattr(self, 'syn_stars'):
                self.init_synaesthesia_mode()
            s_pos, s_col, s_size, h_pos, h_col = self.render_synaesthesia()
            part_pos.append(s_pos)
            part_col.append(s_col)
            part_size.append(s_size)
        else:
            h_pos = np.zeros((0, 3), dtype=np.float32)
            h_col = np.zeros((0, 4), dtype=np.float32)
                        
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
                gl.glUniform1i(self.part_star_shape_loc, self.opt_star_shape)
                
                gl.glBindVertexArray(self.particle_vao)
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.particle_pos_vbo)
                gl.glBufferData(gl.GL_ARRAY_BUFFER, pos_arr.nbytes, pos_arr, gl.GL_DYNAMIC_DRAW)
                
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.particle_col_vbo)
                gl.glBufferData(gl.GL_ARRAY_BUFFER, col_arr.nbytes, col_arr, gl.GL_DYNAMIC_DRAW)
                
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.particle_size_vbo)
                gl.glBufferData(gl.GL_ARRAY_BUFFER, size_arr.nbytes, size_arr, gl.GL_DYNAMIC_DRAW)
                
                gl.glDrawArrays(gl.GL_POINTS, 0, len(pos_arr))
                gl.glBindVertexArray(0)
                
                # Draw Solid/Translucent 3D Meshes across ALL major visualizer modes
                if 'h_pos' in locals() and h_pos is not None and len(h_pos) > 0:
                    gl.glUseProgram(self.line_program)
                    gl.glUniformMatrix4fv(self.line_proj_loc, 1, gl.GL_TRUE, proj_matrix)
                    gl.glUniformMatrix4fv(self.line_view_loc, 1, gl.GL_TRUE, view_matrix)
                    
                    gl.glBindVertexArray(self.hood_vao)
                    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.hood_pos_vbo)
                    gl.glBufferData(gl.GL_ARRAY_BUFFER, h_pos.nbytes, h_pos, gl.GL_DYNAMIC_DRAW)
                    
                    gl.glBindVertexArray(self.hood_vao)
                    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.hood_col_vbo)
                    gl.glBufferData(gl.GL_ARRAY_BUFFER, h_col.nbytes, h_col, gl.GL_DYNAMIC_DRAW)
                    
                    gl.glDisable(gl.GL_CULL_FACE)
                    # Switch to matte standard alpha blending for solid meshes
                    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
                    gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(h_pos))
                    # Restore back to additive blending
                    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
                    gl.glBindVertexArray(0)
            except Exception as e:
                import traceback
                traceback.print_exc()
                
        if hasattr(self, 'is_recording') and self.is_recording and self.ffmpeg_process:
            self.capture_recording_frame(w_phys, h_phys)
            # Schedule next frame draw with a tiny timeout to let GTK do layout/allocation
            GLib.timeout_add(1, self.gl_area.queue_draw)
                 
        return True

    def on_tick(self):
        if hasattr(self, 'is_recording') and self.is_recording:
            return True
            
        now = time.time()
        dt = now - self.last_time
        self.last_time = now
        dt = min(dt, 0.1)
        self.update_preset_random_timer(dt)
        
        # Decay envelopes
        decay_rate = 5.0
        self.react_bass = max(0.0, self.react_bass - decay_rate * dt)
        self.react_mid = max(0.0, self.react_mid - decay_rate * dt)
        self.react_treble = max(0.0, self.react_treble - decay_rate * dt)
        self.react_bass_smooth += (self.react_bass - self.react_bass_smooth) * dt * 3.5
        
        # Smoothly decay current panning towards center over time
        self.current_stereo_panning -= self.current_stereo_panning * dt * 1.5
        
        # Decay climax flash and advance tempo phase
        self.climax_flash = max(0.0, self.climax_flash - 2.0 * dt)
        self.tempo_phase += dt * (self.script_bpm / 60.0)
        
        # Update active timers and state variables
        if self.lightning_active_timer > 0.0:
            self.lightning_active_timer -= dt
            if self.lightning_active_timer <= 0.0:
                self.active_lightning_bolts = []
        if self.peace_symbol_timer > 0.0:
            self.peace_symbol_timer = max(0.0, self.peace_symbol_timer - dt)
        if self.halo_timer > 0.0:
            self.halo_timer = max(0.0, self.halo_timer - dt)
        
        # Check for implicit/proactive real-time climax peak (flash point)
        if self.music_playing and self.major_mode != "FIREWORKS":
            now_sec = time.time()
            if self.react_bass > 1.35 and (now_sec - self.last_climax_trigger_time > 8.0):
                self.last_climax_trigger_time = now_sec
                self.trigger_climax_event(intensity=1.2, routine_name="Beat Flashpoint")
        
        # Playback sync event handler
        elapsed = 0.0
        if self.music_playing:
            # Check if player has stopped or finished
            if not self.audio_player.is_playing():
                if self.playlist and len(self.playlist) > 0:
                    self.play_next_track()
                else:
                    self.stop_sync_playback()
            else:
                elapsed = self.audio_player.get_elapsed_time()
                if self.script_events and self.script_duration > 0 and elapsed >= self.script_duration:
                    if self.playlist and len(self.playlist) > 0:
                        self.play_next_track()
                    else:
                        self.stop_sync_playback()
                else:
                    while (self.next_event_idx < len(self.script_events) and 
                           self.script_events[self.next_event_idx]["time"] <= elapsed):
                        event = self.script_events[self.next_event_idx]
                        self.trigger_script_event(event)
                        self.next_event_idx += 1

        # Update scheduled routine queue
        if len(self.routine_queue) > 0:
            remaining_queue = []
            for delay, fw in self.routine_queue:
                delay -= dt
                if delay <= 0:
                    self.fireworks.append(fw)
                else:
                    remaining_queue.append((delay, fw))
            self.routine_queue = remaining_queue
            
        if self.active_routine_name:
            self.routine_timer -= dt
            if self.routine_timer <= 0:
                self.active_routine_name = ""
        
        measured_fps = 1.0 / dt if dt > 0 else 60.0
        self.fps = self.fps * self.fps_filter + measured_fps * (1.0 - self.fps_filter)
        
        if self.auto_rotate:
            self.camera_theta += 0.15 * dt
            if self.camera_theta > 2 * np.pi:
                self.camera_theta -= 2 * np.pi
                
        if self.auto_launch or (self.music_playing and not getattr(self, 'script_events', None)):
            self.launch_timer += dt
            if self.launch_timer >= self.next_launch_interval:
                self.launch_timer = 0.0
                self.next_launch_interval = random.uniform(0.6, 1.3)
                if self.major_mode == "FIREWORKS":
                    self.fireworks.append(Firework())
                else:
                    # Trigger beat-synced artificial reactive envelopes
                    r = random.random()
                    if r < 0.33:
                        self.react_bass = min(1.5, self.react_bass + 0.8)
                    elif r < 0.66:
                        self.react_mid = min(1.5, self.react_mid + 0.8)
                    else:
                        self.react_treble = min(1.5, self.react_treble + 0.8)
                        
        # Background pulse
        self.procedural_beat_timer += dt
        if self.procedural_beat_timer >= 60.0 / 120.0:
            self.procedural_beat_timer = 0.0
            if not self.music_playing:
                self.react_bass = min(1.5, self.react_bass + 0.4)
                
        if self.major_mode == "FIREWORKS":
            for fw in self.fireworks:
                fw.update(dt)
            self.fireworks = [fw for fw in self.fireworks if fw.state != 'DEAD']
        elif self.major_mode == "TUNNEL Wormhole":
            if not hasattr(self, 'gem_z'):
                self.init_tunnel_mode()
            self.update_tunnel(dt)
            if self.wormhole_supernova_active:
                self.wormhole_supernova_age += dt
                if self.wormhole_supernova_age > 3.5:
                    self.wormhole_supernova_active = False
            if self.wormhole_shooting_star_active:
                self.wormhole_shooting_star_z += dt * 45.0
                if self.wormhole_shooting_star_z > 10.0:
                    self.wormhole_shooting_star_active = False
        elif self.major_mode == "UNDERWATER Lava":
            if not hasattr(self, 'bubble_pos'):
                self.init_underwater_mode()
            self.update_underwater(dt)
        elif self.major_mode == "MANDALA Sacred":
            if not hasattr(self, 'mandala_base_pos'):
                self.init_mandala_mode()
            self.update_mandala(dt)
        elif self.major_mode == "SYNAESTHESIA Classic":
            if not hasattr(self, 'syn_stars'):
                self.init_synaesthesia_mode()
            self.update_synaesthesia(dt)
            
        self.update_rarity_system(dt)
        
        self.fps_lbl.set_text(f"FPS: {self.fps:.1f}")
        if self.active_routine_name:
            self.routine_lbl.set_text(f"Routine: {self.active_routine_name}")
        else:
            self.routine_lbl.set_text("Routine: None")
            
        if self.music_playing:
            if self.script_events:
                self.music_track_lbl.set_text(f"Track: {self.loaded_script_name} ({self.script_bpm:.1f} BPM)")
            else:
                self.music_track_lbl.set_text(f"Track: {os.path.basename(self.audio_path)} (Analyzing...)")
            m_sec = int(elapsed) % 60
            m_min = int(elapsed) // 60
            if self.script_duration > 0:
                total_sec = int(self.script_duration) % 60
                total_min = int(self.script_duration) // 60
                self.music_time_lbl.set_text(f"Time: {m_min:02d}:{m_sec:02d} / {total_min:02d}:{total_sec:02d}")
            else:
                self.music_time_lbl.set_text(f"Time: {m_min:02d}:{m_sec:02d} / --:--")
        else:
            if len(self.script_events) > 0:
                self.music_track_lbl.set_text(f"Track: {self.loaded_script_name} (Ready)")
            else:
                self.music_track_lbl.set_text("Track: None (Press M to generate)")
            self.music_time_lbl.set_text("Time: 00:00 / 00:00")
            
        active_stars = 0
        active_rockets = 0
        if self.major_mode == "FIREWORKS":
            active_stars = sum(len(fw.positions) for fw in self.fireworks if fw.positions is not None)
            active_rockets = sum(1 for fw in self.fireworks if fw.state == 'LAUNCH')
        elif self.major_mode == "TUNNEL Wormhole":
            active_stars = len(self.gem_z) + 20 + np.sum(self.spark_active) if hasattr(self, 'gem_z') else 0
        elif self.major_mode == "UNDERWATER Lava":
            active_stars = ((np.sum(self.bubble_active) if hasattr(self, 'bubble_active') else 0) + 
                            (len(self.algae_pos) if hasattr(self, 'algae_pos') else 0) + 
                            (self.num_vent_pts if hasattr(self, 'num_vent_pts') else 0) + 
                            (self.num_jelly * 46 if hasattr(self, 'num_jelly') else 0))
        elif self.major_mode == "MANDALA Sacred":
            active_stars = len(self.mandala_base_pos) * self.mandala_slices if hasattr(self, 'mandala_base_pos') else 0
        elif self.major_mode == "SYNAESTHESIA Classic":
            active_stars = len(self.syn_stars) * 20 + 300 if hasattr(self, 'syn_stars') else 0
            
        self.shell_lbl.set_text(f"Active Shells: {active_rockets}")
        self.part_lbl.set_text(f"Simulated Particles: {active_stars:,}")
        
        self.gl_area.queue_draw()
        return True

    def on_key_pressed(self, controller, keyval, keycode, state):
        is_control = (state & Gdk.ModifierType.CONTROL_MASK) != 0
        if is_control:
            if keyval in (Gdk.KEY_f, Gdk.KEY_F, Gdk.KEY_o, Gdk.KEY_O):
                self.show_file_chooser()
                return True
            return False

        unicode_val = Gdk.keyval_to_unicode(keyval)
        key_char = chr(unicode_val) if unicode_val > 0 else ""
        
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q, Gdk.KEY_Q):
            self.win.close()
            return True
        elif keyval in (Gdk.KEY_space, getattr(Gdk, 'KEY_AudioPlay', -1), getattr(Gdk, 'KEY_AudioPlayPause', -1)):
            self.toggle_sync_playback()
            return True
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.fireworks.append(Firework())
            return True
        elif key_char == '1':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("American Flag", self.launch_american_flag)
            elif self.major_mode == "SYNAESTHESIA Classic":
                self.syn_points_are_diamonds = not self.syn_points_are_diamonds
                self.opt_star_shape = 2 if self.syn_points_are_diamonds else 5
                print(f"Synaesthesia Shape changed. Diamonds: {self.syn_points_are_diamonds}")
                self.update_legend_labels()
            else:
                self.trigger_climax_event(intensity=1.1, routine_name="Coral Pulse" if self.major_mode == "UNDERWATER Lava" else "Lotus Bloom" if self.major_mode == "MANDALA Sacred" else "Plasma Burst")
            return True
        elif key_char == '2':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("Liberty Bell", self.launch_liberty_bell)
            elif self.major_mode == "SYNAESTHESIA Classic":
                sizes = [0.1, 0.25, 0.5, 0.75, 1.0]
                idx = sizes.index(self.syn_star_size) if self.syn_star_size in sizes else 2
                self.syn_star_size = sizes[(idx + 1) % len(sizes)]
                print(f"Synaesthesia Star Size: {self.syn_star_size}")
                self.update_legend_labels()
            else:
                self.trigger_climax_event(intensity=1.2, routine_name="Geyser Eruption" if self.major_mode == "UNDERWATER Lava" else "Cosmic Spin" if self.major_mode == "MANDALA Sacred" else "Gravity Surge")
            return True
        elif key_char == '3':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("Statue of Liberty", self.launch_statue_of_liberty)
            elif self.major_mode == "SYNAESTHESIA Classic":
                brights = [0.1, 0.25, 0.35, 0.5, 0.7, 1.0]
                idx = brights.index(self.syn_brightness) if self.syn_brightness in brights else 2
                self.syn_brightness = brights[(idx + 1) % len(brights)]
                print(f"Synaesthesia Brightness: {self.syn_brightness}")
                self.update_legend_labels()
            else:
                self.trigger_climax_event(intensity=1.3, routine_name="Plankton Surge" if self.major_mode == "UNDERWATER Lava" else "Infinite Pulse" if self.major_mode == "MANDALA Sacred" else "Stardust Stream")
            return True
        elif key_char == '4':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("Flower Bouquet", self.launch_flower_bouquet)
            elif self.major_mode == "SYNAESTHESIA Classic":
                modes = ["Stars", "Wave", "Flame"]
                idx = modes.index(self.syn_fade_mode) if self.syn_fade_mode in modes else 0
                self.syn_fade_mode = modes[(idx + 1) % len(modes)]
                print(f"Synaesthesia Fade Mode: {self.syn_fade_mode}")
                self.update_legend_labels()
            else:
                self.trigger_climax_event(intensity=1.4, routine_name="Deep Vent Blast" if self.major_mode == "UNDERWATER Lava" else "Geometric Collapse" if self.major_mode == "MANDALA Sacred" else "Event Horizon")
            return True
        elif key_char == '5':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("The Dragon", self.launch_the_dragon)
            elif self.major_mode == "SYNAESTHESIA Classic":
                self.trigger_syn_star_burst()
                self.update_legend_labels()
            else:
                self.trigger_climax_event(intensity=1.8, routine_name="Bioluminescent Rainbow" if self.major_mode == "UNDERWATER Lava" else "Astral Projection" if self.major_mode == "MANDALA Sacred" else "Lightning Flash")
            return True
        elif key_char == '6':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("Supernova", self.launch_supernova)
            elif self.major_mode == "MANDALA Sacred":
                self.trigger_climax_event(intensity=1.6, routine_name="Peace Symbol")
            else:
                self.trigger_climax_event(intensity=2.0, routine_name="Supernova")
            return True
        elif key_char == '7':
            if self.major_mode == "FIREWORKS":
                self.trigger_routine("Shooting Star", self.launch_shooting_star)
            elif self.major_mode == "MANDALA Sacred":
                self.trigger_climax_event(intensity=1.8, routine_name="Halo Effect")
            else:
                self.trigger_climax_event(intensity=1.6, routine_name="Shooting Star")
            return True
        elif keyval in (Gdk.KEY_v, Gdk.KEY_V):
            next_idx = (self.preset_idx + 1) % len(self.active_presets)
            self.apply_preset(next_idx)
            return True
        elif keyval in (Gdk.KEY_y, Gdk.KEY_Y):
            self.opt_height_restrict = not self.opt_height_restrict
            self.update_legend_labels()
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
        elif keyval in (Gdk.KEY_m, Gdk.KEY_M):
            self.toggle_sync_playback()
            return True
        elif keyval in (Gdk.KEY_o, Gdk.KEY_O):
            modes = ['REALISTIC', 'NEON', 'TRANQUIL', 'METAL']
            idx = modes.index(self.opt_color_mode)
            self.opt_color_mode = modes[(idx + 1) % len(modes)]
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_p, Gdk.KEY_P):
            self.opt_star_shape = (self.opt_star_shape + 1) % 7
            if self.major_mode == "SYNAESTHESIA Classic":
                if self.opt_star_shape in (1, 2, 3):
                    self.syn_points_are_diamonds = True
                elif self.opt_star_shape in (4, 5, 6):
                    self.syn_points_are_diamonds = False
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_g, Gdk.KEY_G):
            gravs = [0.0, 0.5, 1.0, 2.0, 5.0, 10.0]
            idx = gravs.index(self.opt_gravity) if self.opt_gravity in gravs else 2
            self.opt_gravity = gravs[(idx + 1) % len(gravs)]
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_l, Gdk.KEY_L):
            self.opt_trailers = (self.opt_trailers + 1) % 11
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_t, Gdk.KEY_T):
            self.show_rockets = not self.show_rockets
            self.update_legend_labels()
            return True
        elif keyval in (Gdk.KEY_s, Gdk.KEY_S):
            slices_options = [3, 4, 5, 6, 8, 12, 18, 24]
            idx = slices_options.index(self.mandala_slices) if self.mandala_slices in slices_options else 5
            self.mandala_slices = slices_options[(idx + 1) % len(slices_options)]
            print(f"Mandala Slices: {self.mandala_slices}")
            self.update_legend_labels()
            return True
        elif keyval == Gdk.KEY_Left or keyval == getattr(Gdk, 'KEY_AudioPrev', -1):
            self.play_previous_track()
            return True
        elif keyval == Gdk.KEY_Right or keyval == getattr(Gdk, 'KEY_AudioNext', -1):
            self.play_next_track()
            return True
        elif keyval in (Gdk.KEY_h, Gdk.KEY_H):
            self.show_legend = not self.show_legend
            if hasattr(self, 'legend_box') and self.legend_box:
                self.legend_box.set_visible(self.show_legend)
            if hasattr(self, 'hud_box') and self.hud_box:
                self.hud_box.set_visible(self.show_legend)
            return True
        elif keyval in (Gdk.KEY_f, Gdk.KEY_F):
            if self.is_fullscreen:
                self.win.unfullscreen()
                self.is_fullscreen = False
            else:
                self.win.fullscreen()
                self.is_fullscreen = True
            return True
        elif keyval in (Gdk.KEY_k, Gdk.KEY_K):
            if not hasattr(self, 'rarity_cycle_list'):
                self.rarity_cycle_list = [
                    "SQUID", "MANTA", "SEAHORSE", "LANTERN_FISH",
                    "PLANET", "GALAXY", "ASTEROIDS",
                    "CATHERINE_WHEEL",
                    "BIRD", "SMOKE", "SUN_BURST", "BUTTERFLY"
                ]
                self.rarity_cycle_idx = -1
            self.rarity_cycle_idx = (self.rarity_cycle_idx + 1) % len(self.rarity_cycle_list)
            r_type = self.rarity_cycle_list[self.rarity_cycle_idx]
            self.current_rarity_cycle_name = r_type
            
            # Auto-initialize and switch major mode
            if r_type in ["SQUID", "MANTA", "SEAHORSE", "LANTERN_FISH"]:
                target_mode = "UNDERWATER Lava"
            elif r_type in ["PLANET", "GALAXY", "ASTEROIDS"]:
                target_mode = "TUNNEL Wormhole"
            elif r_type in ["CATHERINE_WHEEL"]:
                target_mode = "FIREWORKS"
            elif r_type in ["BIRD", "SMOKE", "SUN_BURST", "BUTTERFLY"]:
                target_mode = "MANDALA Sacred"
                
            self.major_mode = target_mode
            self.major_mode_idx = self.modes.index(target_mode)
            
            # Make sure mode structures are initialized
            if self.major_mode == "TUNNEL Wormhole":
                if not hasattr(self, 'gem_z'):
                    self.init_tunnel_mode()
            elif self.major_mode == "UNDERWATER Lava":
                if not hasattr(self, 'bubble_pos'):
                    self.init_underwater_mode()
            elif self.major_mode == "MANDALA Sacred":
                if not hasattr(self, 'mandala_base_pos'):
                    self.init_mandala_mode()
                    
            self.spawn_rarity(r_type)
            self.update_legend_labels()
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

    def on_file_drop(self, target, value, x, y):
        if isinstance(value, Gdk.FileList):
            files = value.get_files()
            paths = []
            for f in files:
                path = f.get_path()
                if path:
                    paths.append(path)
            if paths:
                print(f"Drag & Drop files received: {paths}")
                self.playlist = self.load_playlist_files(paths)
                self.playlist_idx = 0
                if self.playlist:
                    self.audio_path = self.playlist[self.playlist_idx]
                    self.script_path = self.get_mangled_script_path(self.audio_path)
                    self.load_and_play_track()
                return True
        return False

    def show_file_chooser(self):
        dialog = Gtk.FileChooserNative.new(
            title="Open Audio File",
            parent=self.win,
            action=Gtk.FileChooserAction.OPEN,
            accept_label="_Open",
            cancel_label="_Cancel"
        )
        
        filter_audio = Gtk.FileFilter()
        filter_audio.set_name("Audio Files")
        filter_audio.add_mime_type("audio/*")
        for ext in ["mp3", "wav", "ogg", "opus", "flac", "m4a", "aac"]:
            filter_audio.add_pattern(f"*.{ext}")
            filter_audio.add_pattern(f"*.{ext.upper()}")
        dialog.add_filter(filter_audio)
        
        filter_m3u = Gtk.FileFilter()
        filter_m3u.set_name("Playlists (*.m3u)")
        filter_m3u.add_pattern("*.m3u")
        filter_m3u.add_pattern("*.M3U")
        dialog.add_filter(filter_m3u)
        
        filter_all = Gtk.FileFilter()
        filter_all.set_name("All Files")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                file_obj = dialog.get_file()
                if file_obj:
                    path = file_obj.get_path()
                    if path:
                        print(f"File dialog selected: {path}")
                        self.playlist = self.load_playlist_files([path])
                        self.playlist_idx = 0
                        if self.playlist:
                            self.audio_path = self.playlist[self.playlist_idx]
                            self.script_path = self.get_mangled_script_path(self.audio_path)
                            self.load_and_play_track()
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def on_right_click(self, gesture, n_press, x, y):
        # Create a Popover
        popover = Gtk.Popover()
        popover.set_parent(self.gl_area)
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        popover.set_has_arrow(False)
        
        # Build menu content
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        menu_box.set_margin_start(8)
        menu_box.set_margin_end(8)
        menu_box.set_margin_top(8)
        menu_box.set_margin_bottom(8)
        menu_box.add_css_class("hud-legend")
        
        # Helper to create buttons
        def make_menu_item(label, callback):
            btn = Gtk.Button(label=label)
            btn.set_has_frame(False)
            btn.set_halign(Gtk.Align.FILL)
            # Create a left-aligned label style inside the button
            child = btn.get_child()
            if isinstance(child, Gtk.Label):
                child.set_xalign(0.0)
            btn.connect("clicked", lambda b: (popover.popdown(), callback()))
            return btn
            
        # File Open
        menu_box.append(make_menu_item("📂 Open Audio...", self.show_file_chooser))
        
        # Play / Pause
        play_label = "⏸ Pause Sync" if self.music_playing else "▶ Play Sync"
        menu_box.append(make_menu_item(play_label, self.toggle_sync_playback))
        
        # Next / Prev Track
        menu_box.append(make_menu_item("⏭ Next Track", self.play_next_track))
        menu_box.append(make_menu_item("⏮ Previous Track", self.play_previous_track))
        
        # Separator
        sep1 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep1.set_margin_top(4)
        sep1.set_margin_bottom(4)
        menu_box.append(sep1)
        
        # Preset Mode list
        modes_label = Gtk.Label(label="VISUALIZATION MODES:")
        modes_label.add_css_class("hud-legend-title")
        modes_label.set_halign(Gtk.Align.START)
        modes_label.set_margin_start(4)
        menu_box.append(modes_label)
        
        # Add preset buttons
        for idx, preset in enumerate(self.active_presets):
            name = preset["name"]
            # Highlight current active preset
            active_marker = "● " if (idx == self.preset_idx and not getattr(self, 'preset_random_mode', False)) else "  "
            menu_box.append(make_menu_item(f"{active_marker}{name}", lambda i=idx: self.apply_preset(i)))
            
        # Random Mode button
        random_marker = "● " if getattr(self, 'preset_random_mode', False) else "  "
        menu_box.append(make_menu_item(f"{random_marker}Random Mode", lambda: self.apply_preset(len(self.active_presets) - 1)))
        
        # Separator
        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep2.set_margin_top(4)
        sep2.set_margin_bottom(4)
        menu_box.append(sep2)
        
        # Exit
        menu_box.append(make_menu_item("❌ Exit Screensaver", self.win.close))
        
        popover.set_child(menu_box)
        popover.popup()

    def load_sync_script(self, filepath):
        import audio_analyzer
        if os.path.exists(filepath):
            need_regenerate = False
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                ver = data.get("metadata", {}).get("analyzer_version", 0)
                if ver < audio_analyzer.ANALYZER_VERSION:
                    print(f"JSON file {filepath} is outdated (version {ver} < {audio_analyzer.ANALYZER_VERSION}). Deleting and re-analyzing...")
                    need_regenerate = True
            except Exception as e:
                print(f"Error reading JSON file {filepath} for version check: {e}. Deleting and re-analyzing...")
                need_regenerate = True
                
            if need_regenerate:
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"Failed to remove outdated JSON {filepath}: {e}")
                    
                if os.path.exists(self.audio_path):
                    print(f"Auto-regenerating up-to-date JSON for {self.audio_path}...")
                    try:
                        hints = getattr(self, 'color_hints', None) or ["strontium_red", "magnesium_white", "copper_blue"]
                        script = audio_analyzer.analyze_audio(self.audio_path, hints)
                        with open(filepath, 'w') as f:
                            json.dump(script, f, indent=2)
                        print(f"Regenerated {filepath} successfully.")
                    except Exception as e:
                        print(f"Failed to auto-generate JSON: {e}")
                else:
                    print(f"Cannot regenerate, audio file {self.audio_path} not found!")
                    
        try:
            with open(filepath, 'r') as f:
                script = json.load(f)
            self.script_events = script.get("events", [])
            metadata = script.get("metadata", {})
            self.loaded_script_name = os.path.basename(filepath)
            self.script_duration = metadata.get("duration", 0.0)
            self.script_bpm = metadata.get("bpm", 120.0)
            self.script_total_events = metadata.get("total_events", len(self.script_events))
            self.color_hints = metadata.get("color_hints", [])
            print(f"Loaded sync script {filepath} successfully. Events: {len(self.script_events)}")
            self.update_legend_labels()
            return True
        except Exception as e:
            print(f"Failed to load sync script {filepath}: {e}")
            return False

    def start_sync_playback(self):
        if not self.script_events:
            print("No synchronized script loaded!")
            return
            
        self.stop_sync_playback()
        
        music_file = self.audio_path
        if not os.path.exists(music_file):
            print(f"Could not find music file: {music_file}")
            return
            
        print(f"Starting synchronized playback for: {music_file}")
        self.saved_auto_launch = self.auto_launch
        self.auto_launch = False
        self.update_legend_labels()
        
        self.fireworks.clear()
        
        try:
            if self.audio_player.play(music_file):
                self.music_playing = True
                self.playback_start_time = time.time()
                self.next_event_idx = 0
                print("Audio player started successfully.")
            else:
                raise RuntimeError("UnifiedAudioPlayer failed to play track")
        except Exception as e:
            print(f"Failed to start audio playback: {e}")
            self.auto_launch = self.saved_auto_launch
            self.update_legend_labels()

    def stop_sync_playback(self):
        if self.music_playing:
            self.music_playing = False
            self.audio_player.stop()
            self.music_process = None
            
            self.auto_launch = self.saved_auto_launch
            self.update_legend_labels()
            if hasattr(self, 'music_section_lbl') and self.music_section_lbl:
                self.music_section_lbl.set_text("Section: None")
            print("Synchronized playback stopped.")

    def toggle_sync_playback(self):
        if self.music_playing:
            self.stop_sync_playback()
        else:
            # If no script loaded, try auto-generating one
            if not self.script_events:
                print(f"No display script loaded. Attempting to auto-analyze {self.audio_path}...")
                if os.path.exists(self.audio_path):
                    try:
                        import audio_analyzer
                        script_data = audio_analyzer.analyze_audio(self.audio_path, ["strontium_red", "magnesium_white", "copper_blue"])
                        with open(self.script_path, 'w') as f:
                            json.dump(script_data, f, indent=2)
                        self.load_sync_script(self.script_path)
                    except Exception as e:
                        print(f"Failed auto-analysis: {e}")
                        return
                else:
                    print(f"Could not find {self.audio_path} in current directory!")
                    return
            self.start_sync_playback()

    def trigger_script_event(self, event):
        event_type = event.get("type")
        if event_type == "firework":
            fw_type = event.get("fw_type")
            color_key = event.get("color")
            sec_color_key = event.get("secondary_color")
            x_offset = event.get("x_offset", 0.0)
            self.current_stereo_panning = np.clip(x_offset / 6.0, -1.0, 1.0)
            
            color_rgb = COLORS.get(color_key, random.choice(COLOR_LIST))
            sec_color_rgb = COLORS.get(sec_color_key, random.choice(COLOR_LIST))
            
            # Sync visualizer reactive spikes to music event types
            if fw_type in [0, 2, 7, 8, 11, 12, 13]:
                self.react_bass = min(1.5, self.react_bass + 0.6)
            elif fw_type in [6, 14, 15, 17]:
                self.react_treble = min(1.5, self.react_treble + 0.6)
            else:
                self.react_mid = min(1.5, self.react_mid + 0.6)
            
            fw = Firework(fw_type=fw_type, color=color_rgb, x_offset=x_offset)
            fw.secondary_color = sec_color_rgb
            self.fireworks.append(fw)
            
        elif event_type == "routine":
            name = event.get("name")
            supported = SUPPORTED_ROUTINES.get(self.major_mode, [])
            if supported and name not in supported:
                old_name = name
                name = random.choice(supported)
                print(f"[Fallback] Routine '{old_name}' not supported in {self.major_mode}. Selected random fallback: '{name}'")
                
            if self.major_mode == "FIREWORKS":
                routines_map = {
                    "American Flag": self.launch_american_flag,
                    "Liberty Bell": self.launch_liberty_bell,
                    "Statue of Liberty": self.launch_statue_of_liberty,
                    "Flower Bouquet": self.launch_flower_bouquet,
                    "The Dragon": self.launch_the_dragon,
                    "Supernova": self.launch_supernova,
                    "Shooting Star": self.launch_shooting_star
                }
                if name in routines_map:
                    self.trigger_routine(name, routines_map[name])
            else:
                self.trigger_climax_event(intensity=1.5, routine_name=name)
                
        elif event_type == "climax":
            intensity = event.get("intensity", 1.5)
            if self.major_mode != "FIREWORKS":
                self.trigger_climax_event(intensity=intensity, routine_name="Climax Burst!")
                
        elif event_type == "key_change":
            key_name = event.get("key", "Unknown")
            self.react_mid = min(1.5, self.react_mid + 0.6)
            self.react_treble = min(1.5, self.react_treble + 0.5)
            if hasattr(self, 'music_section_lbl') and self.music_section_lbl:
                self.music_section_lbl.set_text(f"Key Shift: {key_name}")
                
        elif event_type == "dynamics":
            direction = event.get("direction", "none")
            if direction == "crescendo":
                self.react_bass = min(1.4, self.react_bass + 0.3)
                self.react_mid = min(1.4, self.react_mid + 0.3)
                self.procedural_beat_timer = 0.0
                
        elif event_type == "section":
            name = event.get("name", "Unknown")
            if hasattr(self, 'music_section_lbl') and self.music_section_lbl:
                self.music_section_lbl.set_text(f"Section: {name}")
            if getattr(self, 'preset_random_mode', False) and getattr(self, 'preset_random_timer', 0.0) >= 45.0:
                print(f"[Random Mode] Triggering preset switch at start of section: {name}")
                self.pick_random_preset()

    def start_recording_process(self, w, h):
        if w % 2 != 0:
            w = (w // 2) * 2
        if h % 2 != 0:
            h = (h // 2) * 2
            
        print(f"\nStarting offline HEVC recording of fireworks performance...")
        print(f"Target file: {self.record_path}")
        print(f"Resolution: {w}x{h} @ {self.record_fps} FPS")
        
        import audio_analyzer
        ffmpeg_bin = audio_analyzer.find_ffmpeg_binary()
        if not ffmpeg_bin:
            print("ERROR: FFmpeg binary not found on this system. Recording is not supported on this platform without FFmpeg.")
            self.is_recording = False
            return
            
        cmd = [
            ffmpeg_bin, '-y',
            '-f', 'rawvideo', '-vcodec', 'rawvideo',
            '-s', f'{w}x{h}', '-pix_fmt', 'rgba', '-r', str(self.record_fps),
            '-i', '-',
            '-c:v', 'libx265', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium',
            self.temp_video_path
        ]
        
        try:
            self.ffmpeg_process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            print("Successfully opened FFmpeg libx265 encoding process pipe.")
            self.auto_launch = False
            self.auto_rotate = True
            self.playback_start_time = 0.0
            self.record_time = 0.0
            self.next_event_idx = 0
            self.fireworks.clear()
            self.routine_queue.clear()
            
            # Start real-time music audio playback for live monitoring during recording
            music_file = self.audio_path
            if os.path.exists(music_file):
                try:
                    if self.audio_player.play(music_file):
                        self.music_playing = True
                        print(f"Started real-time music audio playback ({music_file}) for live monitoring.")
                    else:
                        raise RuntimeError("UnifiedAudioPlayer failed to start playback")
                except Exception as ex:
                    print(f"Failed to start live audio playback: {ex}")
        except Exception as e:
            print(f"Failed to start recording FFmpeg process: {e}")
            self.is_recording = False

    def on_recording_tick(self):
        dt = self.record_dt
        self.update_preset_random_timer(dt)
        elapsed = self.record_time
        
        # Decay envelopes in recording
        decay_rate = 5.0
        self.react_bass = max(0.0, self.react_bass - decay_rate * dt)
        self.react_mid = max(0.0, self.react_mid - decay_rate * dt)
        self.react_treble = max(0.0, self.react_treble - decay_rate * dt)
        self.react_bass_smooth += (self.react_bass - self.react_bass_smooth) * dt * 3.5
        
        # Decay climax flash and advance tempo phase in recording
        self.climax_flash = max(0.0, self.climax_flash - 2.0 * dt)
        self.tempo_phase += dt * (self.script_bpm / 60.0)
        
        # Check for implicit/proactive climax in offline recording
        if self.major_mode != "FIREWORKS":
            if self.react_bass > 1.35 and (elapsed - self.last_climax_trigger_time > 8.0):
                self.last_climax_trigger_time = elapsed
                self.trigger_climax_event(intensity=1.2, routine_name="Beat Flashpoint")
        
        if elapsed >= self.script_duration:
            self.finish_recording()
            return
            
        while (self.next_event_idx < len(self.script_events) and 
               self.script_events[self.next_event_idx]["time"] <= elapsed):
            event = self.script_events[self.next_event_idx]
            self.trigger_script_event(event)
            self.next_event_idx += 1
            
        # Update scheduled routine queue
        if len(self.routine_queue) > 0:
            remaining_queue = []
            for delay, fw in self.routine_queue:
                delay -= dt
                if delay <= 0:
                    self.fireworks.append(fw)
                else:
                    remaining_queue.append((delay, fw))
            self.routine_queue = remaining_queue
            
        if self.active_routine_name:
            self.routine_timer -= dt
            if self.routine_timer <= 0:
                self.active_routine_name = ""

        self.record_time += dt
        
        if self.auto_rotate:
            self.camera_theta += 0.15 * dt
            if self.camera_theta > 2 * np.pi:
                self.camera_theta -= 2 * np.pi
                
        if self.major_mode == "FIREWORKS":
            for fw in self.fireworks:
                fw.update(dt)
            self.fireworks = [fw for fw in self.fireworks if fw.state != 'DEAD']
        elif self.major_mode == "TUNNEL Wormhole":
            if not hasattr(self, 'gem_z'):
                self.init_tunnel_mode()
            self.update_tunnel(dt)
        elif self.major_mode == "UNDERWATER Lava":
            if not hasattr(self, 'bubble_pos'):
                self.init_underwater_mode()
            self.update_underwater(dt)
        elif self.major_mode == "MANDALA Sacred":
            if not hasattr(self, 'mandala_base_pos'):
                self.init_mandala_mode()
            self.update_mandala(dt)
        elif self.major_mode == "SYNAESTHESIA Classic":
            if not hasattr(self, 'syn_stars'):
                self.init_synaesthesia_mode()
            self.update_synaesthesia(dt)
        
        self.fps_lbl.set_text(f"FPS: RECORDING ({self.record_fps} FPS)")
        if self.active_routine_name:
            self.routine_lbl.set_text(f"Routine: {self.active_routine_name}")
        else:
            self.routine_lbl.set_text("Routine: None")
            
        self.music_track_lbl.set_text(f"Recording: {self.loaded_script_name}")
        m_sec = int(elapsed) % 60
        m_min = int(elapsed) // 60
        total_sec = int(self.script_duration) % 60
        total_min = int(self.script_duration) // 60
        self.music_time_lbl.set_text(f"Time: {m_min:02d}:{m_sec:02d} / {total_min:02d}:{total_sec:02d}")
        
        if self.major_mode == "FIREWORKS":
            active_stars = sum(len(fw.positions) for fw in self.fireworks if fw.positions is not None)
            active_rockets = sum(1 for fw in self.fireworks if fw.state == 'LAUNCH')
        elif self.major_mode == "TUNNEL Wormhole":
            active_stars = len(self.gem_z) + 100 + np.sum(self.spark_active) if hasattr(self, 'gem_z') else 0
            active_rockets = 0
        elif self.major_mode == "UNDERWATER Lava":
            active_stars = ((np.sum(self.bubble_active) if hasattr(self, 'bubble_active') else 0) + 
                            (len(self.algae_pos) if hasattr(self, 'algae_pos') else 0) + 
                            (self.num_vent_pts if hasattr(self, 'num_vent_pts') else 0) + 
                            (self.num_jelly * 46 if hasattr(self, 'num_jelly') else 0))
            active_rockets = 0
        elif self.major_mode == "MANDALA Sacred":
            active_stars = len(self.mandala_base_pos) * self.mandala_slices if hasattr(self, 'mandala_base_pos') else 0
            active_rockets = 0
        elif self.major_mode == "SYNAESTHESIA Classic":
            active_stars = len(self.syn_stars) * 20 + 300 if hasattr(self, 'syn_stars') else 0
            active_rockets = 0
            
        self.shell_lbl.set_text(f"Active Shells: {active_rockets}")
        self.part_lbl.set_text(f"Simulated Particles: {active_stars:,}")

    def capture_recording_frame(self, w, h):
        try:
            # Query GTK's offscreen draw framebuffer and bind it as the active read target
            fb = gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, fb)
            
            if fb > 0:
                gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0)
            else:
                gl.glReadBuffer(gl.GL_BACK)
                
            gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
            pixels = gl.glReadPixels(0, 0, w, h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            
            arr = np.frombuffer(pixels, dtype=np.uint8).reshape(h, w, 4)
            arr = np.flipud(arr)
            
            self.ffmpeg_process.stdin.write(arr.tobytes())
            
            if int(self.record_time * self.record_fps) % (self.record_fps * 5) == 0:
                print(f"Recorded frame: {self.record_time:.2f}s / {self.script_duration:.2f}s...")
        except Exception as e:
            print(f"Recording frame capture failed: {e}")
            self.is_recording = False
            if self.ffmpeg_process:
                self.ffmpeg_process.stdin.close()
                self.ffmpeg_process.wait()
                self.ffmpeg_process = None

    def finish_recording(self, close_window=True):
        if not self.is_recording:
            return
            
        self.is_recording = False
        print("\nFireworks offline recording render complete!")
        
        if self.ffmpeg_process:
            print("Closing video encoding pipe...")
            self.ffmpeg_process.stdin.close()
            self.ffmpeg_process.wait()
            self.ffmpeg_process = None
            
        music_file = self.audio_path
        if os.path.exists(music_file):
            print(f"Multiplexing audio track '{music_file}' into output file '{self.record_path}' using copy/copy stream mapping...")
            
            cmd = [
                '/home/sumner/bin/ffmpeg', '-y',
                '-i', self.temp_video_path,
                '-i', music_file,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-shortest',
                self.record_path
            ]
            
            try:
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = p.communicate()
                if p.returncode == 0:
                    print(f"\nSuccessfully generated finalized HEVC MP4 movie with audio at: {self.record_path}")
                else:
                    err = stderr.decode('utf-8', errors='ignore')[-300:]
                    print(f"Error multiplexing audio: {err}")
            except Exception as e:
                print(f"Failed to run multiplexer subprocess: {e}")
        else:
            print(f"Warning: Audio file '{music_file}' not found. Leaving silent video at '{self.temp_video_path}'.")
            os.rename(self.temp_video_path, self.record_path)
            print(f"Renamed silent video to: {self.record_path}")
            
        if os.path.exists(self.temp_video_path):
            try:
                os.remove(self.temp_video_path)
            except Exception:
                pass
                
        if close_window:
            self.win.close()

    def on_close_request(self, win):
        self.stop_sync_playback()
        if self.is_recording:
            self.finish_recording(close_window=False)
            return True
        return False

    # =========================================================================
    # MODE 5: SYNAESTHESIA CLASSIC (3D Real-time Spatial Music Visualizer)
    # =========================================================================
    def init_synaesthesia_mode(self):
        if not hasattr(self, 'syn_points_are_diamonds'):
            self.syn_points_are_diamonds = True
        if not hasattr(self, 'syn_star_size'):
            self.syn_star_size = 0.5
        if not hasattr(self, 'syn_brightness'):
            self.syn_brightness = 0.35
        if not hasattr(self, 'syn_fade_mode'):
            self.syn_fade_mode = "Stars"
        if not hasattr(self, 'syn_fg_red_slider'):
            self.syn_fg_red_slider = 0.0
        if not hasattr(self, 'syn_fg_green_slider'):
            self.syn_fg_green_slider = 0.5
        if not hasattr(self, 'syn_bg_red_slider'):
            self.syn_bg_red_slider = 0.75
        if not hasattr(self, 'syn_bg_green_slider'):
            self.syn_bg_green_slider = 0.4
        self.syn_stars = []

    def update_synaesthesia(self, dt):
        # Move and filter active stars
        active_stars = []
        for star in self.syn_stars:
            # Smoothly transition existing particles if user toggles fade mode in real-time
            if self.syn_fade_mode == "Stars":
                star['vel'] = np.array([0.0, 0.0, 0.0], dtype=np.float32)
            elif self.syn_fade_mode == "Flame":
                if np.all(star['vel'] == 0.0) or star['vel'][1] <= 0.0:
                    star['vel'] = np.array([np.random.uniform(-0.15, 0.15), np.random.uniform(1.2, 1.8), 0.0], dtype=np.float32)
            elif self.syn_fade_mode == "Wave":
                if np.all(star['vel'] == 0.0) or (star['vel'][0] == 0.0 and star['vel'][1] == 0.0):
                    theta = np.random.uniform(0.0, 2.0 * np.pi)
                    star['vel'] = np.array([np.cos(theta) * 1.5, np.sin(theta) * 1.5, 0.0], dtype=np.float32)
            
            star['pos'] += star['vel'] * dt
            star['life'] -= dt
            
            # Record position history for trailers if enabled
            if self.opt_trailers > 0:
                if 'history' not in star or star['history'] is None:
                    star['history'] = []
                star['history'].append(star['pos'].copy())
                # Limit history to match the trailers range
                target_len = self.opt_trailers * 2 + 1
                while len(star['history']) > target_len:
                    star['history'].pop(0)
            else:
                if 'history' in star:
                    star['history'] = None

            if star['life'] > 0.0:
                active_stars.append(star)
        self.syn_stars = active_stars

        # Spawn stars based on real-time frequency reactions
        if self.react_bass > 0.15:
            count = int(self.react_bass * 4)
            for _ in range(count):
                self.spawn_syn_star("bass", self.react_bass)

        if self.react_mid > 0.15:
            count = int(self.react_mid * 3)
            for _ in range(count):
                self.spawn_syn_star("mid", self.react_mid)

        if self.react_treble > 0.15:
            count = int(self.react_treble * 3)
            for _ in range(count):
                self.spawn_syn_star("treble", self.react_treble)

        if self.active_rarity is not None:
            self.update_active_rarity(dt)

    def spawn_syn_star(self, band, reaction_val):
        pan_x = self.current_stereo_panning * 8.0

        if band == "bass":
            y = np.random.uniform(0.5, 2.5)
            f_intensity = np.random.uniform(180.0, 255.0) * min(2.0, reaction_val)
            b_intensity = np.random.uniform(120.0, 255.0) * min(2.0, reaction_val)
            size_coef = np.random.uniform(1.2, 1.8)
        elif band == "mid":
            y = np.random.uniform(2.5, 5.5)
            f_intensity = np.random.uniform(150.0, 240.0) * min(2.0, reaction_val)
            b_intensity = np.random.uniform(100.0, 220.0) * min(2.0, reaction_val)
            size_coef = np.random.uniform(0.9, 1.3)
        else:  # treble
            y = np.random.uniform(5.5, 7.5)
            f_intensity = np.random.uniform(120.0, 220.0) * min(2.0, reaction_val)
            b_intensity = np.random.uniform(80.0, 180.0) * min(2.0, reaction_val)
            size_coef = np.random.uniform(0.6, 1.0)

        z = 0.0
        x = pan_x + np.random.uniform(-1.5, 1.5)

        if self.syn_fade_mode == "Flame":
            vx = np.random.uniform(-0.15, 0.15)
            vy = np.random.uniform(1.2, 1.8)
        elif self.syn_fade_mode == "Wave":
            theta = np.random.uniform(0.0, 2.0 * np.pi)
            vx = np.cos(theta) * 1.5
            vy = np.sin(theta) * 1.5
        else:  # "Stars"
            vx = 0.0
            vy = 0.0
        vz = 0.0

        self.syn_stars.append({
            'pos': np.array([x, y, z], dtype=np.float32),
            'vel': np.array([vx, vy, vz], dtype=np.float32),
            'f_intensity': f_intensity,
            'b_intensity': b_intensity,
            'life': np.random.uniform(2.2, 3.5),
            'size_coef': size_coef
        })

    def trigger_syn_star_burst(self):
        print("TRIGGERING SYNAESTHESIA STAR BURST!")
        for _ in range(45):
            angle = np.random.uniform(0.0, 2.0 * np.pi)
            r_dist = np.random.uniform(0.0, 3.5)
            x = r_dist * np.cos(angle)
            y = 4.0 + r_dist * np.sin(angle)
            z = 0.0

            speed = np.random.uniform(1.5, 3.2)
            vx = np.cos(angle) * speed
            vy = np.sin(angle) * speed
            vz = 0.0

            self.syn_stars.append({
                'pos': np.array([x, y, z], dtype=np.float32),
                'vel': np.array([vx, vy, vz], dtype=np.float32),
                'f_intensity': np.random.uniform(220.0, 255.0),
                'b_intensity': np.random.uniform(180.0, 255.0),
                'life': np.random.uniform(2.5, 4.0),
                'size_coef': np.random.uniform(1.3, 2.2)
            })

    def render_synaesthesia(self):
        pts = []
        cols = []
        sizes = []

        fade_fudge = 0.78
        if self.syn_fade_mode == "Wave":
            fade_fudge = 0.4
        elif self.syn_fade_mode == "Flame":
            fade_fudge = 0.6

        size = self.syn_star_size
        if self.opt_trailers > 0:
            decay_scale = 1.0 - min(0.9, self.opt_trailers * 0.08)
            factor = 256.0 - (256.0 - (min(255.0, np.exp(np.log(fade_fudge) / (size * 8.0)) * 255.0) if size > 0.0 else 0.0)) * decay_scale
        else:
            factor = min(255.0, np.exp(np.log(fade_fudge) / (size * 8.0)) * 255.0) if size > 0.0 else 0.0

        fgRed = self.syn_fg_red_slider
        fgGreen = self.syn_fg_green_slider
        if self.opt_color_mode != 'REALISTIC':
            pal = get_palette_colors(self.opt_color_mode)
            c1, c2 = pal[0], pal[1 % len(pal)]
            fgRed, fgGreen, fgBlue = c1[0], c1[1], c1[2]
            bgRed, bgGreen, bgBlue = c2[0], c2[1], c2[2]
            fg_s = fgRed + fgGreen + fgBlue
            if fg_s > 0.0:
                fgRed, fgGreen, fgBlue = (fgRed/fg_s)*2.0, (fgGreen/fg_s)*2.0, (fgBlue/fg_s)*2.0
            bg_s = bgRed + bgGreen + bgBlue
            if bg_s > 0.0:
                bgRed, bgGreen, bgBlue = (bgRed/bg_s)*2.0, (bgGreen/bg_s)*2.0, (bgBlue/bg_s)*2.0
        else:
            fgBlue = 1.0 - max(fgRed, fgGreen)
            bgRed = self.syn_bg_red_slider
            bgGreen = self.syn_bg_green_slider
            bgBlue = 1.0 - max(bgRed, bgGreen)
        
        fg_scale = (fgRed + fgGreen + fgBlue) / 2.0
        if fg_scale > 0.0:
            fgRed /= fg_scale
            fgGreen /= fg_scale
            fgBlue /= fg_scale
        bg_scale = (bgRed + bgGreen + bgBlue) / 2.0
        if bg_scale > 0.0:
            bgRed /= bg_scale
            bgGreen /= bg_scale
            bgBlue /= bg_scale

        def map_color(f, b):
            red = b * bgRed + f * fgRed
            green = b * bgGreen + f * fgGreen
            blue = b * bgBlue + f * fgBlue

            excess = 0.0
            for _ in range(5):
                red += excess / 3.0
                green += excess / 3.0
                blue += excess / 3.0
                excess = 0.0
                if red > 255.0:
                    excess += (red - 255.0)
                    red = 255.0
                if green > 255.0:
                    excess += (green - 255.0)
                    green = 255.0
                if blue > 255.0:
                    excess += (blue - 255.0)
                    blue = 255.0

            scale_col = (0.5 + (red + green + blue) / 768.0) / 1.5
            red *= scale_col
            green *= scale_col
            blue *= scale_col

            return [
                min(1.0, max(0.0, red / 255.0)),
                min(1.0, max(0.0, green / 255.0)),
                min(1.0, max(0.0, blue / 255.0)),
                1.0
            ]

        for star in self.syn_stars:
            cx, cy, cz = star['pos']
            f = star['f_intensity']
            b = star['b_intensity']

            pts.append([cx, cy, cz])
            cols.append(map_color(f, b))
            sizes.append(5.0 * self.syn_brightness * star.get('size_coef', 1.0))

            curr_f = f
            curr_b = b
            step_size = 0.09 * self.syn_star_size * star.get('size_coef', 1.0)

            # Draw base star with constant trail range (9) so size remains constant
            trail_range = 9
            for j in range(1, trail_range):
                curr_f = curr_f * factor / 256.0
                curr_b = curr_b * factor / 256.0
                if curr_f < 3.0 and curr_b < 3.0:
                    break

                color = map_color(curr_f, curr_b)
                life_frac = star['life'] / 3.5
                color[3] = min(1.0, max(0.0, life_frac))

                if self.syn_points_are_diamonds:
                    for k in range(j):
                        pts.append([cx + (-j + k) * step_size, cy - k * step_size, cz])
                        pts.append([cx + k * step_size, cy - (j - k) * step_size, cz])
                        pts.append([cx + (j - k) * step_size, cy + k * step_size, cz])
                        pts.append([cx - k * step_size, cy + (j - k) * step_size, cz])
                        for _ in range(4):
                            cols.append(color)
                            sizes.append(4.0 * self.syn_brightness * star.get('size_coef', 1.0))
                else:
                    pts.append([cx + j * step_size, cy, cz])
                    pts.append([cx, cy + j * step_size, cz])
                    pts.append([cx - j * step_size, cy, cz])
                    pts.append([cx, cy - j * step_size, cz])
                    for _ in range(4):
                        cols.append(color)
                        sizes.append(4.0 * self.syn_brightness * star.get('size_coef', 1.0))

            # Draw trailers along movement history if enabled
            if self.opt_trailers > 0 and 'history' in star and star['history']:
                history_list = star['history']
                num_trailers = self.opt_trailers
                for i in range(1, num_trailers + 1):
                    # We space them out backward (e.g. 2 steps per trailer level)
                    idx = -1 - i * 2
                    if abs(idx) <= len(history_list):
                        tcx, tcy, tcz = history_list[idx]
                        
                        # Decay factor for this trailer level
                        trail_decay = (1.0 - (i / (num_trailers + 1.0)))
                        tf = f * trail_decay
                        tb = b * trail_decay
                        
                        # Draw center of the trailer point
                        t_color = map_color(tf, tb)
                        life_frac = star['life'] / 3.5
                        t_color[3] = min(1.0, max(0.0, life_frac)) * trail_decay
                        pts.append([tcx, tcy, tcz])
                        cols.append(t_color)
                        sizes.append(4.0 * self.syn_brightness * star.get('size_coef', 1.0) * trail_decay)
                        
                        # Draw a smaller cross/diamond around the trailer point for a smooth glow
                        t_step_size = 0.09 * self.syn_star_size * star.get('size_coef', 1.0) * trail_decay
                        for tj in range(1, 3):
                            t_curr_f = tf * (0.6 ** tj)
                            t_curr_b = tb * (0.6 ** tj)
                            t_color_j = map_color(t_curr_f, t_curr_b)
                            t_color_j[3] = min(1.0, max(0.0, life_frac)) * trail_decay
                            
                            if self.syn_points_are_diamonds:
                                for tk in range(tj):
                                    pts.append([tcx + (-tj + tk) * t_step_size, tcy - tk * t_step_size, tcz])
                                    pts.append([tcx + tk * t_step_size, tcy - (tj - tk) * t_step_size, tcz])
                                    pts.append([tcx + (tj - tk) * t_step_size, tcy + tk * t_step_size, tcz])
                                    pts.append([tcx - tk * t_step_size, tcy + (tj - tk) * t_step_size, tcz])
                                    for _ in range(4):
                                        cols.append(t_color_j)
                                        sizes.append(3.0 * self.syn_brightness * star.get('size_coef', 1.0) * trail_decay)
                            else:
                                pts.append([tcx + tj * t_step_size, tcy, tcz])
                                pts.append([tcx, tcy + tj * t_step_size, tcz])
                                pts.append([tcx - tj * t_step_size, tcy, tcz])
                                pts.append([tcx, tcy - tj * t_step_size, tcz])
                                for _ in range(4):
                                    cols.append(t_color_j)
                                    sizes.append(3.0 * self.syn_brightness * star.get('size_coef', 1.0) * trail_decay)

        if not hasattr(self, 'syn_bg_particles'):
            self.syn_bg_particles = []
            for _ in range(300):
                self.syn_bg_particles.append({
                    'pos': np.array([np.random.uniform(-25.0, 25.0), np.random.uniform(-10.0, 18.0), -5.0], dtype=np.float32),
                    'col': [np.random.uniform(0.0, 0.25), np.random.uniform(0.1, 0.35), np.random.uniform(0.2, 0.6), np.random.uniform(0.25, 0.55)],
                    'size': np.random.uniform(1.5, 3.5),
                    'phase': np.random.uniform(0.0, 2.0 * np.pi),
                    'speed': np.random.uniform(1.0, 3.5)
                })

        for p in self.syn_bg_particles:
            # Twinkle individually over time
            p['phase'] += 0.016 * p['speed']
            if p['phase'] > 2.0 * np.pi:
                p['phase'] -= 2.0 * np.pi

            pts.append(p['pos'])
            col = p['col'].copy()
            twinkle = 0.5 + 0.5 * np.sin(p['phase'])
            col[3] *= (0.3 + 0.7 * twinkle) * (0.4 + self.react_mid * 0.6)
            if self.opt_color_mode != 'REALISTIC':
                pal = get_palette_colors(self.opt_color_mode)
                c_bg = pal[2 % len(pal)]
                col[:3] = c_bg[:3]
            cols.append(col)
            sizes.append(p['size'])

        h_pos = np.zeros((0, 3), dtype=np.float32)
        h_col = np.zeros((0, 4), dtype=np.float32)
        return pts, cols, sizes, h_pos, h_col


if __name__ == "__main__":
    import argparse
    import json
    import sys
    parser = argparse.ArgumentParser(description="3D Pyro-Engine Screensaver")
    parser.add_argument("--random", action="store_true", default=False, help="Start in random mode immediately")
    parser.add_argument("--record", type=str, default=None, help="Output file path to record the MP4 to")
    parser.add_argument("--audio", type=str, default=None, help="Audio file to run against")
    parser.add_argument("--tmpdir", type=str, default=None, help="Optional custom temporary directory for display scripts")
    parser.add_argument("playlist_files", nargs="*", help="Audio files or m3u playlist to play")
    args, unknown = parser.parse_known_args()
    
    app = Gtk.Application(application_id="org.fireworks.demo")
    pyro_app = FireworksApp(record_path=args.record, audio_path=args.audio, playlist_files=args.playlist_files, random_mode=args.random, tmp_dir=args.tmpdir)
    app.connect("activate", pyro_app.on_activate)
    
    gtk_args = [sys.argv[0]] + unknown
    app.run(gtk_args)
