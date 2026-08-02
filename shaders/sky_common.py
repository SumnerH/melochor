# Shared vertex shader and common fragment shader header/helpers used by all sky modes.
SKY_VERTEX_SHADER = """#version 300 es
layout (location = 0) in vec2 aPos;
out vec2 vPos;
void main() {
    vPos = aPos;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

SKY_COMMON_SOURCE = """#version 300 es
precision mediump float;
in vec2 vPos;
out vec4 FragColor;

uniform float uTime;
uniform float uRipple; // 0.0 = normal, 1.0 = Underwater, 2.0 = Tunnel
uniform float uClimaxFlash; // Climax event flash intensity
uniform float uFlameAlgorithm; // 0=Current, 1=Gas Jet, 2=Bonfire, 3=Candle, 4=Vortex, 5=Game, 6=Multi

// Fullscreen rendering uniforms for Tunnel Mode
uniform float uWormholeBendX;
uniform float uWormholeBendY;
uniform float uWormholePhaseX;
uniform float uWormholePhaseY;
uniform float uReactBass;
uniform float uReactTreble;
uniform float uReactMid;
uniform float uStereoPanning;
uniform float uWormholeSpeedFactor;
uniform float uAspect;
uniform mat4 uInvVP;
uniform float uWindGust;

uniform sampler2D uMoonTex;
uniform float uHasMoonTex;
uniform float uMoonIllumed;
uniform float uMoonIsWaning;
uniform int uColorMode;

// --- New uniforms for smooth flame height ---
uniform float uPrevReactBass;
uniform float uPrevReactMid;
uniform float uPrevReactTreble;
uniform float uDeltaTime;   // frame time in seconds

// Persistent peak-hold/slow-release envelope (real multi-frame memory, computed on the CPU)
// used exclusively by the Multi flame mode for organic, non-jittery height pulsing.
uniform float uFlameEnvBass;
uniform float uFlameEnvMid;
uniform float uFlameEnvTreble;

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

vec3 get_starfield(vec2 pos, float aspect, float t_grad) {
    vec3 stars_color = vec3(0.0);
    vec2 star_uv = vec2(pos.x * aspect, pos.y) * 15.0;
    vec2 star_id = floor(star_uv);
    vec2 star_f = fract(star_uv) - 0.5;
    float star_h = hash(star_id);
    if (star_h > 0.982) {
        // 1. Map depth-gradient (vertical spectral blending weights)
        float w_bass = (1.0 - t_grad) * (1.0 - t_grad);
        float w_treble = t_grad * t_grad;
        float w_mid = 1.0 - w_bass - w_treble;

        // 2. Localized spectral energy based on vertical coordinate
        float e_local = w_bass * uReactBass + w_mid * uReactMid + w_treble * uReactTreble;

        // 3. Map horizontal stereo soundstage scale
        float s_coeff = 1.0 + 0.8 * (pos.x * uStereoPanning);

        // 4. Compute final spatial-audio reaction factor
        float r_local = e_local * s_coeff;

        // 5. Unique, randomized baseline twinkling properties (very slow, delicate, and unsynchronized)
        float base_freq = 0.35 + star_h * 1.45;
        float base_phase = star_h * 12.56;
        float base_brightness = 0.04 + star_h * 0.12;
        float base_amplitude = 0.02 + star_h * 0.08;
        float base_twinkle = sin(uTime * base_freq + base_phase) * 0.5 + 0.5;
        float base_value = base_brightness + base_amplitude * base_twinkle;

        // 6. Music-reactive frequency and phase modulation (additive & stronger)
        float music_freq_shift = r_local * (5.0 + star_h * 12.0);
        float music_phase_shift = r_local * 25.0;
        float music_twinkle = sin(uTime * (base_freq + music_freq_shift) + base_phase + music_phase_shift) * 0.5 + 0.5;
        float music_value = r_local * (0.65 + star_h * 1.85) * music_twinkle;

        // 7. Add combined intensities
        float final_intensity = base_value + music_value;

        // 8. Dynamic temperature-dependent star coloring (G/K yellow/gold, A/B blue-white, M red/amber, pure white)
        float t_color = (star_h - 0.982) / 0.018; // Normalized range [0.0, 1.0]
        vec3 star_color = vec3(1.0);
        if (t_color < 0.35) {
            star_color = mix(vec3(1.0, 0.85, 0.62), vec3(1.0, 1.0, 1.0), t_color / 0.35);
        } else if (t_color < 0.75) {
            star_color = mix(vec3(1.0, 1.0, 1.0), vec3(0.78, 0.90, 1.0), (t_color - 0.35) / 0.40);
        } else {
            star_color = mix(vec3(0.78, 0.90, 1.0), vec3(1.0, 0.65, 0.52), (t_color - 0.75) / 0.25);
        }

        float dist = length(star_f);
        float star_p = smoothstep(0.08, 0.0, dist) * 0.4 + smoothstep(0.02, 0.0, dist) * 0.6;
        stars_color = star_color * star_p * final_intensity;
    }
    return stars_color;
}
"""
