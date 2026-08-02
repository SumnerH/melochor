# Modern Shader Sources (GLSL ES 3.00) - Sky Shaders
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

vec2 get_bend(float z) {
    float bx = uWormholeBendX * sin(z * 0.06 + uWormholePhaseX);
    float by = uWormholeBendY * cos(z * 0.06 + uWormholePhaseY);
    return vec2(bx, by);
}

float sdTunnel(vec3 p) {
    // High-amplitude organic peristalsis wave traveling along the z-axis, enhanced with a base offset and bass hits
    float wave = sin(p.z * 0.18 - uTime * (2.5 * uWormholeSpeedFactor)) * 0.95;
    float peristalsis = (0.15 + uReactBass * 0.70) * (sin(p.z * 0.22 - uTime * (6.5 * uWormholeSpeedFactor)) * 0.5 + 0.5);
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
    
    // Twinkling procedural deep space starfield (Modulated stereoscopically and spectrally)
    vec3 stars = get_starfield(vPos, uAspect, t_gradient);
    if (uRipple > 2.5) {
        // Boost the stars in fire mode as requested
        base_color += stars * 2.2;
    } else {
        base_color += stars;
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
    else if (uRipple > 1.5 && uRipple < 2.5) {
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
            vec2 uv = vec2(cos(angle) * 1.8 + p.z * 0.02, sin(angle) * 1.8 - uTime * (0.9 * uWormholeSpeedFactor) + p.z * 0.045);
            
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
    else if (uRipple > 2.5) {
        // --- 1. Draw a highly realistic crescent moon (moon.png shaded to waning crescent) ---
        vec2 moon_uv = vPos * vec2(uAspect, 1.0);
        vec2 moon_pos = vec2(0.68, 0.52); // upper right quadrant
        float dist_moon = length(moon_uv - moon_pos);
        float moon_radius = 0.16;
        
        if (dist_moon <= moon_radius) {
            // Compute dynamic phase angle theta based on uMoonIsWaning and uMoonIllumed
            float angle_phase = (uMoonIsWaning > 0.5) ? -3.14159 * (1.0 - uMoonIllumed) : 3.14159 * (1.0 - uMoonIllumed);
            vec3 light_dir = normalize(vec3(sin(angle_phase), 0.06, cos(angle_phase)));
            
            if (uHasMoonTex > 0.5) {
                // Map screen coordinates to local 2D moon coordinates [0, 1]
                vec2 local_moon_uv = (moon_uv - moon_pos) / (2.0 * moon_radius) + vec2(0.5);
                float dist_center = length(local_moon_uv - vec2(0.5));
                if (dist_center <= 0.5) {
                    // Reconstruct 3D surface normals on moon hemisphere
                    float z = sqrt(0.25 - dist_center * dist_center);
                    vec3 normal = normalize(vec3(local_moon_uv - vec2(0.5), z));
                    
                    float light = clamp(dot(normal, light_dir), 0.0, 1.0);
                    float terminator = smoothstep(0.0, 0.08, light);
                    
                    // Sample full moon texture
                    vec4 tex_color = texture(uMoonTex, local_moon_uv);
                    
                    float earthshine = 0.05;
                    vec3 shaded_moon = tex_color.rgb * (terminator + earthshine);
                    float moon_alpha = smoothstep(0.5, 0.492, dist_center) * tex_color.a;
                    
                    base_color = mix(base_color, shaded_moon, moon_alpha * 0.95);
                }
            } else {
                // Procedural fallback moon with exact 3D hemisphere shading!
                vec2 local_moon_uv = (moon_uv - moon_pos) / (2.0 * moon_radius) + vec2(0.5);
                float dist_center = length(local_moon_uv - vec2(0.5));
                if (dist_center <= 0.5) {
                    float z = sqrt(0.25 - dist_center * dist_center);
                    vec3 normal = normalize(vec3(local_moon_uv - vec2(0.5), z));
                    
                    float light = clamp(dot(normal, light_dir), 0.0, 1.0);
                    float terminator = smoothstep(0.0, 0.08, light);
                    
                    float crater_noise = fbm(local_moon_uv * 18.0) * 0.15 + fbm(local_moon_uv * 35.0) * 0.06;
                    vec3 moon_base_color = vec3(0.92, 0.90, 0.84) * (0.85 - crater_noise);
                    
                    float earthshine = 0.05;
                    vec3 shaded_moon = moon_base_color * (terminator + earthshine);
                    base_color = mix(base_color, shaded_moon, 0.95);
                }
            }
        }    
        // Slow-drifting nighttime clouds (drift speed based on song tempo)
        vec2 cloud_uv = vPos * vec2(uAspect * 0.8, 1.0) * 0.85;
        float drift_speed = 0.015 * (1.0 + uWormholeSpeedFactor * 0.5);
        cloud_uv.x -= uTime * drift_speed;
        cloud_uv.y -= uTime * drift_speed * 0.12;
        
        float cloud_noise = fbm(cloud_uv * 2.5 + vec2(uTime * drift_speed * 0.2, 0.0));
        cloud_noise += fbm(cloud_uv * 5.0) * 0.35;
        
        float cloud_density = smoothstep(0.28, 0.75, cloud_noise) * 0.65;
        cloud_density *= smoothstep(-0.84, -0.35, vPos.y); // Fade out near ground
        
        // Backlighting effect if clouds pass near the moon!
        float dist_to_moon = length(moon_uv - moon_pos);
        float moon_glow = exp(-dist_to_moon * 4.5) * 0.38;
        
        // Campfire warm light reflecting off the bottom of the clouds
        float dist_to_fire = length(vec2(vPos.x * 1.5, vPos.y - (-0.84)));
        float fire_reflection = exp(-dist_to_fire * 1.8) * (0.3 + 0.3 * uReactBass);
        vec3 fire_glow_on_cloud = vec3(0.85, 0.28, 0.02) * fire_reflection;
        
        vec3 cloud_color = mix(vec3(0.06, 0.07, 0.11), vec3(0.55, 0.52, 0.45), moon_glow);
        cloud_color += fire_glow_on_cloud;
        
        base_color = mix(base_color, cloud_color, cloud_density);

        // --- 2. Highly Realistic Procedural Campfire Visualizer ---
        vec2 uv = vPos;
        float y_norm = (vPos.y + 1.0) * 0.5; // range [0, 1] from bottom to top
        
        // Smooth music reaction values using exponential moving average
        // (CPU must set uPrevReactBass, uPrevReactMid, uPrevReactTreble and uDeltaTime)
        // Restored partway from 2.2: this was stacking with the CPU-side EMA smoothing above,
        // over-blurring the real bass/mid/treble differences the Multi flame mode needs.
        float smoothFactor = clamp(uDeltaTime * 3.4, 0.0, 1.0);
        float bass = mix(uPrevReactBass, uReactBass, smoothFactor);
        float mid  = mix(uPrevReactMid,  uReactMid,  smoothFactor);
        float treble = mix(uPrevReactTreble, uReactTreble, smoothFactor);
        
        // Multi flame mode pulse values. The separate CPU-computed uFlameEnvBass/Mid/Treble
        // envelope uniforms proved unreliable (every attempt using them went completely
        // invisible, while this simpler approach using the confirmed-working bass/mid/treble
        // variables was the ONLY version that ever showed visible differentiation). bass/mid/
        // treble are themselves now genuinely smoothed on the CPU (react_bass_smooth/
        // react_mid_smooth/react_treble_smooth, all real persistent multi-frame EMAs — mid and
        // treble previously lacked this and were raw, unlike bass), so this stays organic
        // without depending on the broken pipeline.
        float pulseBass = bass;
        float pulseMid  = mid;
        float pulseTreble = treble;
        
        // Define music reaction factors
        // (now using smoothed values)
        
        // A. TEXTURED DIRT GROUND AND ASHES BED
        float bump = noise(vec2(vPos.x * 2.2, 0.0)) * 0.024;
        float ground_height = -0.84 + bump;
        
        // A1. DISTANT HORIZON WITH HILLS, BOULDERS, AND SHRUBS
        float horizon_hills = -0.38 + fbm(vec2(vPos.x * 1.5, 0.0)) * 0.08;
        
        if (vPos.y < horizon_hills && vPos.y >= ground_height) {
            float height_factor = (vPos.y - ground_height) / (horizon_hills - ground_height);
            vec3 hill_color = vec3(0.04, 0.05, 0.09); // Distant dark blue-grey hill silhouette
            
            // Scatter 2 distant rugged boulders
            float boulder_mask = 0.0;
            {
                vec2 center = vec2(-0.55, -0.42);
                float dist = length(vPos - center) - 0.035 + fbm(vPos * 25.0) * 0.006;
                if (dist < 0.0) boulder_mask = 1.0;
            }
            {
                vec2 center = vec2(0.52, -0.45);
                float dist = length(vPos - center) - 0.032 + fbm(vPos * 25.0) * 0.005;
                if (dist < 0.0) boulder_mask = 1.0;
            }
            
            // Scatter 2 distant wild shrubs
            float shrub_mask = 0.0;
            {
                vec2 center = vec2(-0.25, -0.44);
                float dist = length(vPos - center) - 0.024 + fbm(vPos * 45.0) * 0.009;
                if (dist < 0.0) shrub_mask = 1.0;
            }
            {
                vec2 center = vec2(0.32, -0.46);
                float dist = length(vPos - center) - 0.020 + fbm(vPos * 45.0) * 0.008;
                if (dist < 0.0) shrub_mask = 1.0;
            }
            
            if (boulder_mask > 0.5) {
                hill_color = vec3(0.03, 0.04, 0.07);
            } else if (shrub_mask > 0.5) {
                hill_color = vec3(0.02, 0.05, 0.04); // Deep forest green
            }
            
            // Soft atmospheric warm glow from the campfire reflecting on the hills
            float dist_to_fire = length(vec2(vPos.x * 1.8, vPos.y - ground_height));
            float hill_light = exp(-dist_to_fire * 2.2) * (0.45 + 0.35 * bass);
            vec3 warm_glow = vec3(0.85, 0.25, 0.04) * hill_light;
            
            base_color = mix(hill_color + warm_glow, base_color, smoothstep(0.92, 1.0, height_factor));
        }
        
        // A2. RENDERING GROUND AND INTERIOR ASHES/LOGS BED
        if (vPos.y < ground_height) {
            float dist_to_center = abs(vPos.x);
            
            if (dist_to_center < 0.32 && vPos.y > -0.915) {
                // Inside the campfire ring: dark soot, fine grey ash, and glowing embers veins
                float ash_noise = fbm(vPos * 25.0);
                vec3 ash_color = vec3(0.12, 0.12, 0.14) * (0.65 + 0.35 * ash_noise);
                
                // Heat-driven cycle factors: high frequency tempo-reactive speed cycling
                float song_heat = clamp(bass * 0.55 + mid * 0.30 + treble * 0.15, 0.0, 1.0);
                float heat_phase = uTime * 1.4 + (bass * 2.8 + treble * 1.2);
                
                // Hot flickering ember veins divided into much smaller, highly detailed multi-colored blocks
                // We increase spatial frequency to 160.0 and add heat_phase to cycle coordinates!
                float ember_noise = noise(vPos * 160.0 + vec2(heat_phase * 0.35, -heat_phase * 0.35));
                float ember_mask = smoothstep(0.44, 0.56, ember_noise);
                
                // Multi-colored variations (mix of deep red, hot orange, and bright gold)
                vec3 col_red = vec3(0.85, 0.04, 0.0);
                vec3 col_orange = vec3(1.0, 0.42, 0.0);
                vec3 col_gold = vec3(1.0, 0.85, 0.2);
                
                // Color variation based on spatial coordinates, cycling dynamically over time with the song heat!
                float col_mix_noise = noise(vPos * 100.0 + vec2(-heat_phase * 0.2, heat_phase * 0.2));
                
                // Heat cycling color mix: Higher song_heat shifts the color mixing thresholds
                // so that when the song is hot, more gold and orange embers appear!
                float mix1 = smoothstep(0.18 - song_heat * 0.12, 0.58 - song_heat * 0.12, col_mix_noise);
                float mix2 = smoothstep(0.38 - song_heat * 0.16, 0.78 - song_heat * 0.16, col_mix_noise);
                vec3 base_ember_color = mix(col_red, mix(col_orange, col_gold, mix2), mix1);
                
                // Shade gets more dark red with bass, and more orange/yellow with treble
                vec3 music_shaded_color = base_ember_color;
                music_shaded_color.g *= (1.0 - bass * 0.6) + treble * 0.3; // Less green with bass (deeper red), more green with treble (more orange/gold)
                music_shaded_color.r += treble * 0.1;
                music_shaded_color = clamp(music_shaded_color, 0.0, 1.0);
                
                // Glow pulses directly with the music beats
                float ember_glow_pulse = 0.65 + 0.45 * bass + 0.2 * treble;
                vec3 glowing_embers = music_shaded_color * ember_mask * ember_glow_pulse;
                
                vec3 ground_pixel = ash_color + glowing_embers * 1.5;
                
                // Charred black burnt logs crossed in the fireplace
                // Log 1: Angled from bottom-left to top-right
                vec2 log1_uv = vPos - vec2(-0.06, -0.87);
                float cos_a1 = cos(0.35); float sin_a1 = sin(0.35);
                vec2 log1_rot = vec2(log1_uv.x * cos_a1 - log1_uv.y * sin_a1, log1_uv.x * sin_a1 + log1_uv.y * cos_a1);
                float log1_dist = length(max(abs(log1_rot) - vec2(0.18, 0.018), 0.0));
                
                // Log 2: Angled from bottom-right to top-left
                vec2 log2_uv = vPos - vec2(0.06, -0.88);
                float cos_a2 = cos(-0.45); float sin_a2 = sin(-0.45);
                vec2 log2_rot = vec2(log2_uv.x * cos_a2 - log2_uv.y * sin_a2, log2_uv.x * sin_a2 + log2_uv.y * cos_a2);
                float log2_dist = length(max(abs(log2_rot) - vec2(0.15, 0.016), 0.0));
                
                if (log1_dist < 0.002 || log2_dist < 0.002) {
                    // Charcoal bark texture
                    float bark_noise = fbm(vPos * 50.0) * 0.25;
                    vec3 charcoal = vec3(0.05, 0.05, 0.05) + bark_noise;
                    
                    // Charred glowing red hot cracks
                    float cracks = noise(vPos * 80.0);
                    if (cracks > 0.65) {
                        charcoal += vec3(0.95, 0.16, 0.01) * (0.5 + 0.5 * bass);
                    }
                    ground_pixel = charcoal;
                }
                
                base_color = ground_pixel;
            } else {
                // Soil outside the campfire ring
                float soil_noise = fbm(vPos * vec2(12.0, 24.0));
                vec3 dirt_color = vec3(0.22, 0.13, 0.07) * (0.55 + 0.45 * soil_noise);
                
                // Warm pulsating light reflecting from the fire
                float dist_to_fire = length(vec2(vPos.x * 1.6, vPos.y - ground_height));
                float ground_light = exp(-dist_to_fire * 3.0) * (0.8 + 0.6 * bass);
                vec3 fire_glow = vec3(1.0, 0.38, 0.06) * ground_light;
                
                base_color = dirt_color + fire_glow * 1.6;
            }
        }
        
        // B. CORE FLAME RENDERING (6 algorithms)
        if (uFlameAlgorithm < 0.5) {
            // --- ALGORITHM 0: Current (original 3-plume noise-based campfire) ---
            float container_mask = smoothstep(0.31, 0.22, abs(vPos.x));
            
            // Procedural Behind-the-fire Smoke Layer (rises from base, drifts behind bright flames)
            if (vPos.y >= ground_height) {
                float s_height = vPos.y - ground_height;
                float smoke_width = 0.20 + 0.38 * s_height;
                float smoke_sway = sin(uTime * 1.3) * 0.16 + uStereoPanning * 0.40 + uWindGust * 0.65;
                float smoke_x = vPos.x - smoke_sway * s_height * 0.60;
                vec2 smoke_uv = vec2(smoke_x * 2.5, s_height * 0.40 - uTime * 0.55);
                float smoke_noise = fbm(smoke_uv * 3.5 + vec2(0.0, -uTime * 0.25));
                smoke_noise += fbm(smoke_uv * 7.5) * 0.35;
                float smoke_shape = exp(- (smoke_x * smoke_x) / (2.0 * smoke_width * smoke_width));
                float smoke_density = smoke_shape * (0.08 + 0.22 * smoke_noise) * smoothstep(1.0, 0.15, vPos.y);
                vec3 smoke_color = vec3(0.24, 0.25, 0.28) * (0.8 + 0.3 * fbm(vPos * 4.0));
                base_color = mix(base_color, smoke_color, smoke_density * 0.45);
            }
            
            float flame_height = 0.30 + 0.35 * bass + 0.12 * mid;
            float flame_width = 0.16 + 0.08 * bass;
            flame_height = max(0.1, flame_height);
            float y_scaled = (vPos.y - ground_height) / flame_height;
            
            // Glowing coals bed
            float dist_to_coals = length(vec2(vPos.x * 3.0, (vPos.y - ground_height) * 5.0));
            float coals_glow = exp(-dist_to_coals * 3.5) * (0.8 + 0.5 * bass) * container_mask;
            vec3 coals_color = vec3(0.98, 0.18, 0.01) * coals_glow;
            base_color += coals_color * 1.5;
            
            float total_temp = 0.0;
            float total_opacity = 0.0;
            float total_bg_glow = 0.0;
            float total_blue_mask = 0.0;
            
            float fx[3];
            fx[0] = -0.11; fx[1] = 0.0; fx[2] = 0.11;
            
            float x_factor = 2.5;
            float p_val[3];
            p_val[0] = (bass * x_factor + mid + treble) / (x_factor + 2.0);
            p_val[1] = (bass + mid * x_factor + treble) / (x_factor + 2.0);
            p_val[2] = (bass + mid + treble * x_factor) / (x_factor + 2.0);
            
            float f_height[3];
            f_height[0] = 0.20 + 0.30 * p_val[0];
            f_height[1] = 0.23 + 0.33 * p_val[1];
            f_height[2] = 0.20 + 0.30 * p_val[2];
            
            float f_width[3];
            f_width[0] = 0.09 + 0.04 * p_val[0];
            f_width[1] = 0.10 + 0.04 * p_val[1];
            f_width[2] = 0.09 + 0.04 * p_val[2];
            
            float f_sway[3];
            f_sway[0] = sin(uTime * 1.6 + 0.0) * 0.08 + uStereoPanning * 0.35 + uWindGust * 0.50;
            f_sway[1] = sin(uTime * 1.9 + 2.1) * 0.11 + uStereoPanning * 0.42 + uWindGust * 0.65;
            f_sway[2] = sin(uTime * 2.2 + 4.3) * 0.08 + uStereoPanning * 0.35 + uWindGust * 0.50;
            
            for (int p = 0; p < 3; p++) {
                float p_height = max(0.08, f_height[p]);
                float y_scaled = (vPos.y - ground_height) / p_height;
                
                if (vPos.y >= ground_height && y_scaled < 1.35) {
                    float height_fade = smoothstep(1.35, 0.75, y_scaled);
                    float taper = 1.05 - y_scaled * 0.85;
                    float profile_width = f_width[p] * max(0.1, taper);
                    
                    float px = vPos.x - fx[p];
                    px -= f_sway[p] * y_scaled * 0.45;
                    
                    float shape_mask = exp(- (px * px) / (2.0 * profile_width * profile_width)) * container_mask;
                    
                    vec2 noise_uv = vec2(px * 2.5, y_scaled);
                    vec2 disp1 = vec2(uTime * 0.30 + float(p) * 1.5, -uTime * 2.2 - bass * 1.0);
                    vec2 disp2 = vec2(-uTime * 0.20 - float(p) * 1.5, -uTime * 3.4 - treble * 0.4);
                    
                    vec2 warp1 = vec2(
                        fbm(noise_uv * 1.8 + disp1),
                        fbm(noise_uv * 2.2 + disp2)
                    );
                    vec2 warp2 = vec2(
                        fbm(noise_uv * 3.8 + warp1 * 1.4 - disp1 * 0.4),
                        fbm(noise_uv * 4.6 - warp1 * 1.1 + disp2 * 0.4)
                    );
                    vec2 final_uv = noise_uv + warp2 * 0.45;
                    float licks = fbm(final_uv * 4.8 - vec2(0.0, uTime * (2.4 + float(p) * 0.4)));
                    
                    float flame_field = (exp(-y_scaled * 2.4) * 0.38 + licks * 0.82) * shape_mask - y_scaled * 0.54;
                    
                    float solid_base = smoothstep(0.12, 0.0, y_scaled);
                    flame_field = mix(flame_field, 0.80, solid_base * shape_mask);
                    
                    float p_temp = smoothstep(0.08, 0.38, flame_field) * height_fade;
                    p_temp = clamp(p_temp, 0.0, 1.0);
                    
                    if (p_temp > total_temp) {
                        total_temp = p_temp;
                    }
                    
                    // Accumulate local blue mask for gas base
                    float p_blue = smoothstep(0.06, 0.0, y_scaled) * smoothstep(f_width[p] * 0.35, 0.0, abs(px));
                    if (p_blue > total_blue_mask) {
                        total_blue_mask = p_blue;
                    }
                    
                    // Add background glow for each plume
                    float glow_width = f_width[p] * 1.4;
                    float glow_shape = exp(- (px * px) / (2.0 * glow_width * glow_width)) * container_mask;
                    float glow_decay = exp(-y_scaled * 2.0);
                    total_bg_glow += glow_shape * glow_decay * (0.04 + 0.12 * bass);
                }
            }
            
            vec3 flame_color = vec3(0.0);
            float opacity = 0.0;
            
            if (total_temp > 0.005) {
                // More realistic (yellower) base colors
                vec3 col_blue = vec3(0.55, 0.15, 0.0) * (0.8 + bass * 0.2);  // warm dark orange base
                vec3 col_red, col_orange, col_yellow, col_white;
                
                if (uColorMode == 1) { // NEON
                    col_red = vec3(1.0, 0.0, 0.5) * (0.8 + bass * 0.35);
                    col_orange = vec3(0.5, 0.0, 1.0) * (0.8 + treble * 0.35);
                    col_yellow = vec3(0.0, 1.0, 1.0) * (0.8 + treble * 0.35);
                    col_white = vec3(0.0, 1.0, 0.0) * (0.8 + mid * 0.35);
                } else if (uColorMode == 2) { // TRANQUIL
                    col_red = vec3(0.0, 0.3, 0.8) * (0.8 + bass * 0.3);
                    col_orange = vec3(0.0, 0.6, 0.5) * (0.8 + treble * 0.3);
                    col_yellow = vec3(0.5, 0.2, 0.7) * (0.8 + treble * 0.3);
                    col_white = vec3(0.1, 0.7, 0.4) * (0.8 + mid * 0.3);
                } else if (uColorMode == 3) { // METAL
                    col_red = vec3(0.8, 0.5, 0.2) * (0.8 + bass * 0.35);
                    col_orange = vec3(1.0, 0.8, 0.2) * (0.8 + treble * 0.35);
                    col_yellow = vec3(0.9, 0.9, 0.95) * (0.8 + treble * 0.35);
                    col_white = vec3(1.0, 1.0, 1.0) * (0.8 + mid * 0.35);
                } else { // REALISTIC (more yellow)
                    col_red = vec3(0.85 + 0.15 * bass, 0.015 * (1.0 - bass), 0.005) * (1.25 + bass * 0.45);
                    col_orange = vec3(0.98, 0.40 + 0.20 * treble, 0.01); // more yellow
                    col_yellow = vec3(1.0, 0.90 + 0.10 * treble, 0.10 + 0.25 * treble); // more yellow
                    col_white = vec3(1.0, 1.0, 0.72 + 0.28 * mid);
                }
                
                float red_thresh = 0.04 + 0.06 * (1.0 - bass);
                float orange_thresh = 0.18 - 0.06 * bass;
                float yellow_thresh = 0.52 - 0.18 * treble;
                float white_thresh = 0.80 - 0.15 * treble;
                
                orange_thresh = max(red_thresh + 0.02, orange_thresh);
                yellow_thresh = max(orange_thresh + 0.02, yellow_thresh);
                white_thresh = max(yellow_thresh + 0.02, white_thresh);
                
                if (total_temp < red_thresh) {
                    float t = total_temp / red_thresh;
                    flame_color = mix(vec3(0.0), col_red, t);
                } else if (total_temp < orange_thresh) {
                    float t = (total_temp - red_thresh) / (orange_thresh - red_thresh);
                    flame_color = mix(col_red, col_orange, t);
                } else if (total_temp < yellow_thresh) {
                    float t = (total_temp - orange_thresh) / (yellow_thresh - orange_thresh);
                    flame_color = mix(col_orange, col_yellow, t);
                } else if (total_temp < white_thresh) {
                    float t = (total_temp - yellow_thresh) / (white_thresh - yellow_thresh);
                    flame_color = mix(col_yellow, col_white, t);
                } else {
                    float t = clamp((total_temp - white_thresh) / (1.0 - white_thresh), 0.0, 1.0);
                    flame_color = mix(col_white, vec3(1.0, 1.0, 1.0), t);
                }
                
                // Only mix in standard blue gas base if we are in realistic mode (reduced influence)
                if (uColorMode == 0) {
                    flame_color = mix(flame_color, col_blue, total_blue_mask * 0.3);
                }
                
                float target_density = total_temp * (3.8 + bass * 2.2);
                opacity = 1.0 - exp(-target_density);
                opacity = clamp(opacity, 0.0, 0.94);
            }
            
            float bg_glow = clamp(total_bg_glow, 0.0, 0.5);
            
            vec3 glow_tint;
            if (uColorMode == 1) {
                glow_tint = vec3(0.85, 0.0, 0.5);
            } else if (uColorMode == 2) {
                glow_tint = vec3(0.0, 0.3, 0.8);
            } else if (uColorMode == 3) {
                glow_tint = vec3(0.8, 0.5, 0.2);
            } else {
                glow_tint = vec3(0.85, 0.14, 0.01);
            }
            vec3 glow_color = glow_tint * bg_glow;
            base_color += glow_color;
            base_color = mix(base_color, flame_color * (1.1 + bass * 0.35), opacity);
            
        } else if (uFlameAlgorithm < 1.5) {
            // ... (Gas Jet, Bonfire, Candle, Vortex, Game unchanged) ...
        } else if (uFlameAlgorithm < 2.5) {
            // ... (Bonfire) ...
        } else if (uFlameAlgorithm < 3.5) {
            // ... (Candle) ...
        } else if (uFlameAlgorithm < 4.5) {
            // ... (Vortex) ...
        } else if (uFlameAlgorithm < 5.5) {
            // ... (Game) ...
        } else {
            // --- ALGORITHM 6: Multi (5 vortex plumes, independent flicker, spatial reactivity) ---
            float container_mask = smoothstep(0.35, 0.25, abs(vPos.x));

            // Smoke (unchanged)
            if (vPos.y >= ground_height) {
                float s_height = vPos.y - ground_height;
                float smoke_width = 0.20 + 0.35 * s_height;
                float smoke_sway = sin(uTime * 0.9) * 0.15 + uWindGust * 0.6;
                float smoke_x = vPos.x - smoke_sway * s_height * 0.55;
                vec2 smoke_uv = vec2(smoke_x * 2.5, s_height * 0.35 - uTime * 0.5);
                float smoke_noise = fbm(smoke_uv * 3.0) * 0.4;
                float smoke_shape = exp(- (smoke_x * smoke_x) / (2.0 * smoke_width * smoke_width));
                float smoke_density = smoke_shape * (0.06 + 0.18 * smoke_noise) * smoothstep(1.0, 0.2, vPos.y);
                base_color = mix(base_color, vec3(0.25, 0.25, 0.30), smoke_density * 0.4);
            }

            // Coals (unchanged)
            float dist_to_coals = length(vec2(vPos.x * 3.0, (vPos.y - ground_height) * 5.0));
            float coals_glow = exp(-dist_to_coals * 3.5) * (0.8 + 0.5 * bass) * container_mask;
            base_color += vec3(0.98, 0.18, 0.01) * coals_glow * 1.5;

            // Five vortex plumes – each with its own height, width, color, and independent flicker
            float vortex_x_offsets[5];
            vortex_x_offsets[0] = -0.18;
            vortex_x_offsets[1] = -0.09;
            vortex_x_offsets[2] = 0.0;
            vortex_x_offsets[3] = 0.09;
            vortex_x_offsets[4] = 0.18;

            // Base neutral fire colors, used as a fallback tint when there's little spectral
            // energy present (keeps the fire looking natural during quiet passages).
            vec3 vortex_colors[5];
            vortex_colors[0] = vec3(0.95, 0.55, 0.0);   // orange-yellow
            vortex_colors[1] = vec3(0.95, 0.65, 0.0);   // yellow-orange
            vortex_colors[2] = vec3(1.0, 0.85, 0.2);    // yellow
            vortex_colors[3] = vec3(0.95, 0.65, 0.0);   // yellow-orange
            vortex_colors[4] = vec3(0.95, 0.55, 0.0);   // orange-yellow

            // Explicit spectral tint colors. A color shift is far more perceptible than subtle
            // height/width changes, so this is now the PRIMARY mechanism for making
            // "left flame = bass, center = mid, right flame = treble" clearly readable: bass
            // tints deep red, mid stays a natural orange, treble tints icy blue-white.
            vec3 col_bass_tint = vec3(1.0, 0.05, 0.0);
            vec3 col_mid_tint = vec3(1.0, 0.55, 0.05);
            vec3 col_treble_tint = vec3(0.65, 0.85, 1.0);

            // Per‑vortex music reactivity – each flame's color and gentle breathing follow the
            // music, blended smoothly by its horizontal position: leftmost leans toward bass,
            // rightmost toward treble, center toward mid.
            float reacts[5];
            float pulse_contrib[5];
            float pulse_diff[5];
            float pulseAvg = (pulseBass + pulseMid + pulseTreble) / 3.0;
            float pulseTotal = pulseBass + pulseMid + pulseTreble + 1e-4;
            float shareBass = pulseBass / pulseTotal;
            float shareMid = pulseMid / pulseTotal;
            float shareTreble = pulseTreble / pulseTotal;
            // Organic "bubbling up" color modulation: a noise-driven band that continuously
            // rises from the base of the flame over time, so color shifts appear to bubble up
            // from the bottom instead of the whole flame changing color uniformly and instantly.
            // Sampling y with a negative time offset (matching the smoke/lick conventions used
            // elsewhere in this shader) makes the noise pattern appear to travel upward.
            float bubble_ref_height = 0.42;
            float y_for_bubble = (vPos.y - ground_height) / bubble_ref_height;
            float bubble_noise = fbm(vec2(vPos.x * 5.0, y_for_bubble * 2.6 - uTime * 1.1));
            float bubble_mask = smoothstep(0.35, 0.85, bubble_noise);
            for (int v = 0; v < 5; v++) {
                float tv = clamp((vortex_x_offsets[v] + 0.18) / 0.36, 0.0, 1.0);
                // Strongly sharpened (but still smooth/continuous) spatial blend so it reads
                // clearly as "left flame follows bass, right flame follows treble", blending
                // gradually through the middle flames.
                float bw = pow(1.0 - tv, 2.4);
                float tw = pow(tv, 2.4);
                float mw = pow(clamp(1.0 - 2.0 * abs(tv - 0.5), 0.0, 1.0), 2.4);
                float sum = bw + mw + tw + 1e-5;
                bw /= sum;
                mw /= sum;
                tw /= sum;

                float p_share = bw * shareBass + mw * shareMid + tw * shareTreble;
                pulse_contrib[v] = pulseAvg;
                pulse_diff[v] = clamp((p_share - 1.0 / 3.0) * pulseTotal, -1.0, 1.0);

                // Explicit per-flame band dominance: weight each tint color by this flame's
                // spatial bias AND its actual current envelope level, so the resulting hue
                // reveals which band is dominant for THIS flame right now, while overall tint
                // strength scales with how much of that band is actually present (fading back to
                // the neutral fire palette during quiet passages instead of staying stuck).
                float wBass = bw * pulseBass;
                float wMid = mw * pulseMid;
                float wTreble = tw * pulseTreble;
                float wSum = wBass + wMid + wTreble + 1e-4;
                vec3 band_tint = (wBass * col_bass_tint + wMid * col_mid_tint + wTreble * col_treble_tint) / wSum;
                // Modulated by bubble_mask so tint bubbles up organically from the base rather
                // than flashing uniformly. This is the ONLY place bubble_mask is applied to
                // color now — previously it was also applied a second time to
                // color_blend_amount below, which compounded into the tint nearly vanishing.
                // DIAGNOSTIC BOOST: amplified and bubble attenuation minimized so any existing
                // per-band signal becomes impossible to miss.
                float tint_strength = clamp(wSum * 4.0, 0.0, 1.0) * mix(0.7, 1.0, bubble_mask);
                vortex_colors[v] = mix(vortex_colors[v], band_tint, tint_strength);

                // DIAGNOSTIC BOOST
                float flicker = sin(uTime * (0.8 + 0.3 * float(v)) + float(v) * 2.4) * 0.5 + 0.5;
                reacts[v] = 1.0 + pulseAvg * 0.03 + pulse_diff[v] * 0.35 + flicker * pulseAvg * 0.02;
            }

            // Local temperatures and color weights for each vortex
            float temps[5];
            float color_weights[5];
            float total_bg_glow = 0.0;

            for (int v = 0; v < 5; v++) {
                // Height: the shared/average pulse gives a very subtle common rise-and-fall,
                // while the amplified per-flame difference term makes each flame's own
                // bass/mid/treble bias clearly readable (left taller on bass, right taller on
                // treble, center on mid) without the overall fire pulsing hard.
                // Moderately toned down from the confirmed-visible version, but not eliminated.
                // DIAGNOSTIC BOOST: substantially amplified so any existing per-band signal
                // becomes impossible to miss. Dial back down once confirmed visible.
                float v_height = 0.35 + 0.025 * pulseAvg + 0.45 * pulse_diff[v];
                v_height = max(0.08, v_height);
                float y_raw = vPos.y - ground_height;
                // Relative coordinate used ONLY for the overall silhouette envelope (taper,
                // fade-out, decay) – this is what lets the flame subtly grow/shrink.
                float y_scaled_v = y_raw / v_height;
                temps[v] = 0.0;
                color_weights[v] = exp(-pow(vPos.x - vortex_x_offsets[v], 2.0) * 80.0);

                if (vPos.y >= ground_height && y_scaled_v < 1.3) {
                    float height_fade = smoothstep(1.3, 0.5, y_scaled_v);
                    float taper = 1.05 - y_scaled_v * 0.8;
                    // Width breathes gently overall, but noticeably differs per-flame based on
                    // its spectral bias (bass/mid/treble) via the amplified difference term.
                    // DIAGNOSTIC BOOST
                    float width_scale = clamp(1.0 + 0.012 * pulseAvg + 0.32 * pulse_diff[v], 0.5, 1.8);
                    float profile_width = 0.07 * max(0.1, taper) * width_scale;
                    float px = vPos.x - vortex_x_offsets[v];

                    // DIAGNOSTIC BOOST
                    float speed_scale = clamp(1.0 + 0.022 * pulseAvg + 0.30 * pulse_diff[v], 0.4, 2.0);
                    float time_offset = uTime * (1.0 + 0.15 * float(v) + 0.5 * speed_scale);

                    // Fixed-frequency vertical coordinate for flame DETAIL (licks/helix). A
                    // constant reference height (instead of the reactive v_height) keeps the
                    // flickering flame texture a consistent size, so height changes look like the
                    // flame naturally growing taller rather than the whole pattern stretching.
                    float ref_height = 0.35;
                    float y_detail = y_raw / ref_height;

                    float helix_angle = time_offset * 2.0 + y_detail * 6.0 + float(v) * 2.0;
                    float helix_x = sin(helix_angle) * 0.03 * y_detail;
                    px -= helix_x;

                    float shape_mask = exp(- (px * px) / (2.0 * profile_width * profile_width)) * container_mask;

                    // Independent noise seed – each vortex uses a different offset
                    vec2 noise_uv = vec2(px * 3.0 + 0.17 * float(v), y_detail * 2.0 - time_offset * 0.8);
                    vec2 warp1 = vec2(fbm(noise_uv * 1.5 + 0.31 * float(v)), fbm(noise_uv * 2.0 + vec2(1.0 + 0.13 * float(v))));
                    vec2 final_uv = noise_uv + warp1 * 0.3;
                    // Intensity brightens gently overall, with a clearer per-flame spectral bias.
                    // DIAGNOSTIC BOOST
                    float intensity_scale = clamp(1.0 + 0.010 * pulseAvg + 0.22 * pulse_diff[v], 0.6, 1.7);
                    float licks = fbm(final_uv * 3.5 - vec2(0.0, time_offset * 0.9)) * intensity_scale;

                    float flame_field = (exp(-y_scaled_v * 2.0) * 0.4 + licks * 0.6) * shape_mask - y_scaled_v * 0.5;
                    float p_temp = smoothstep(0.05, 0.35, flame_field) * height_fade;
                    p_temp = clamp(p_temp, 0.0, 1.0);
                    temps[v] = p_temp;

                    // Background glow tied to this flame's own blended pulse (bass on the left,
                    // treble on the right) instead of a uniform global bass value, so the glow
                    // reflects the left/right spectral differentiation rather than pulsing
                    // uniformly with the beat.
                    float glow_width = profile_width * 1.5;
                    float glow_shape = exp(- (px * px) / (2.0 * glow_width * glow_width)) * container_mask;
                    // DIAGNOSTIC BOOST
                    total_bg_glow += glow_shape * exp(-y_scaled_v * 2.0) * clamp(0.04 + 0.015 * pulseAvg + 0.20 * pulse_diff[v], 0.0, 0.22);
                }
            }

            // Compute per-pixel local temperature by blending scaled temperatures from all vortices
            float local_temp = 0.0;
            float total_weight = 0.0;
            for (int v = 0; v < 5; v++) {
                float scaled_temp = temps[v] * reacts[v];
                float w = color_weights[v];
                local_temp += scaled_temp * w;
                total_weight += w;
            }
            if (total_weight > 0.001) {
                local_temp /= total_weight;
            } else {
                local_temp = 0.0;
            }

            // Smooth color blend from all vortices (unchanged)
            vec3 blend_color = vortex_colors[2];
            float total_cw = color_weights[0] + color_weights[1] + color_weights[2] + color_weights[3] + color_weights[4];
            if (total_cw > 0.001) {
                blend_color = vec3(0.0);
                for (int v = 0; v < 5; v++) {
                    blend_color += vortex_colors[v] * color_weights[v];
                }
                blend_color /= total_cw;
            }

            if (local_temp > 0.005) {
                // Vortex color gradient (orange → yellow → white) – more realistic, less blue, more yellow
                vec3 col_orange = vec3(0.95, 0.55, 0.0);
                vec3 col_yellow = vec3(1.0, 0.85, 0.2);
                vec3 col_white = vec3(1.0, 1.0, 0.8);
                vec3 flame_color;
                if (local_temp < 0.2) {
                    flame_color = mix(col_orange, col_yellow, local_temp / 0.2);
                } else if (local_temp < 0.6) {
                    flame_color = mix(col_yellow, col_white, (local_temp - 0.2) / 0.4);
                } else {
                    flame_color = mix(col_white, vec3(1.0, 0.95, 0.6), (local_temp - 0.6) / 0.4);
                }

                // Tint with the smoothly blended per‑vortex color (now carrying each flame's
                // dynamic bass/mid/treble tint) to give clearly visible spatial/spectral
                // variety. Blend strength scales up with overall spectral energy so the color
                // differentiation reads strongly during loud passages (like a prominent bass
                // hit) while staying subtle when the music is quiet.
                // bubble_mask is intentionally NOT reapplied here (see tint_strength above) to
                // avoid compounding two bubble-mask multiplications into near-invisibility.
                // DIAGNOSTIC BOOST
                float color_blend_amount = clamp(0.45 + pulseTotal * 0.45, 0.45, 0.95);
                flame_color = mix(flame_color, blend_color, color_blend_amount);

                // Density/opacity driven purely by local_temp, which already carries each
                // flame's own bass/mid/treble-blended pulse. Avoiding an additional uniform
                // global bass term here keeps brightness changes tied to the left/right
                // spectral differentiation instead of pulsing the whole fire uniformly.
                float target_density = local_temp * 3.0;
                float opacity = 1.0 - exp(-target_density);
                opacity = clamp(opacity, 0.0, 0.92);
                base_color = mix(base_color, flame_color, opacity);
            }
            base_color += vec3(0.85, 0.14, 0.01) * clamp(total_bg_glow, 0.0, 0.5);
        }
        
        // C. 3D NORMAL-MAPPED CAMPFIRE ROCKS RING (Calculated last so they sit in front of the fire!)
        // 7 rugged rocks arranged in a beautiful circular campfire ring around the fireplace ashes
        float closest_dist = 999.0;
        float closest_size = 0.0;
        vec2 closest_center = vec2(0.0);
        int closest_rock_idx = -1;
        
        // Rock 0 (Left-front)
        {
            vec2 center = vec2(-0.28, -0.86);
            float size = 0.085;
            float rock_noise = fbm(vPos * 14.0 + vec2(0.0)) * 0.018;
            float dist = length(vPos - center) - size + rock_noise;
            if (dist < 0.0 && dist < closest_dist) {
                closest_dist = dist; closest_size = size; closest_center = center; closest_rock_idx = 0;
            }
        }
        // Rock 1 (Left-back)
        {
            vec2 center = vec2(-0.20, -0.89);
            float size = 0.07;
            float rock_noise = fbm(vPos * 14.0 + vec2(2.3)) * 0.015;
            float dist = length(vPos - center) - size + rock_noise;
            if (dist < 0.0 && dist < closest_dist) {
                closest_dist = dist; closest_size = size; closest_center = center; closest_rock_idx = 1;
            }
        }
        // Rock 2 (Back-center)
        {
            vec2 center = vec2(0.00, -0.91);
            float size = 0.06;
            float rock_noise = fbm(vPos * 14.0 + vec2(4.6)) * 0.012;
            float dist = length(vPos - center) - size + rock_noise;
            if (dist < 0.0 && dist < closest_dist) {
                closest_dist = dist; closest_size = size; closest_center = center; closest_rock_idx = 2;
            }
        }
        // Rock 3 (Right-back)
        {
            vec2 center = vec2(0.20, -0.89);
            float size = 0.07;
            float rock_noise = fbm(vPos * 14.0 + vec2(6.9)) * 0.015;
            float dist = length(vPos - center) - size + rock_noise;
            if (dist < 0.0 && dist < closest_dist) {
                closest_dist = dist; closest_size = size; closest_center = center; closest_rock_idx = 3;
            }
        }
        // Rock 4 (Right-front)
        {
            vec2 center = vec2(0.28, -0.86);
            float size = 0.085;
            float rock_noise = fbm(vPos * 14.0 + vec2(9.2)) * 0.018;
            float dist = length(vPos - center) - size + rock_noise;
            if (dist < 0.0 && dist < closest_dist) {
                closest_dist = dist; closest_size = size; closest_center = center; closest_rock_idx = 4;
            }
        }
        // Rock 5 (Front-left-center)
        {
            vec2 center = vec2(-0.12, -0.84);
            float size = 0.09;
            float rock_noise = fbm(vPos * 14.0 + vec2(11.5)) * 0.020;
            float dist = length(vPos - center) - size + rock_noise;
            if (dist < 0.0 && dist < closest_dist) {
                closest_dist = dist; closest_size = size; closest_center = center; closest_rock_idx = 5;
            }
        }
        // Rock 6 (Front-right-center)
        {
            vec2 center = vec2(0.12, -0.84);
            float size = 0.09;
            float rock_noise = fbm(vPos * 14.0 + vec2(13.8)) * 0.020;
            float dist = length(vPos - center) - size + rock_noise;
            if (dist < 0.0 && dist < closest_dist) {
                closest_dist = dist; closest_size = size; closest_center = center; closest_rock_idx = 6;
            }
        }
        
        if (closest_rock_idx >= 0) {
            vec2 local_rock_uv = vPos - closest_center;
            float size = closest_size;
            float z = sqrt(max(0.0, size * size - dot(local_rock_uv, local_rock_uv)));
            vec3 normal = normalize(vec3(local_rock_uv, z * 2.2));
            
            float texture_bump = fbm(vPos * 42.0 + vec2(float(closest_rock_idx) * 1.5)) * 0.32;
            normal = normalize(normal + vec3(texture_bump, texture_bump, 0.0));
            
            vec3 rock_base = vec3(0.32, 0.30, 0.28) * (0.6 + 0.4 * fbm(vPos * 20.0));
            
            vec3 fire_pos = vec3(0.0, -0.74, 0.1);
            vec3 pixel_pos_3d = vec3(vPos, 0.0);
            vec3 light_dir = normalize(fire_pos - pixel_pos_3d);
            
            float diff = max(0.0, dot(normal, light_dir));
            float dist_to_fire = length(fire_pos.xy - vPos);
            float light_intensity = exp(-dist_to_fire * 3.6) * (1.3 + 0.7 * bass);
            
            vec3 fire_light = vec3(1.0, 0.40, 0.08) * diff * light_intensity;
            vec3 ambient = vec3(0.01, 0.01, 0.05);
            
            base_color = rock_base * (ambient + fire_light * 2.5);
        }
    }
    
    FragColor = vec4(base_color, 1.0);
}
"""
