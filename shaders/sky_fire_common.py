# Fire Plasma sky rendering: moon/clouds backdrop, smoothed audio bands, ground/ash bed, and
# the campfire rocks ring. The flame plume rendering itself lives in sky_fire_flames.py so that
# working on flame algorithms doesn't require touching this environmental/backdrop code.
SKY_FIRE_COMMON_SOURCE = """
vec3 renderFireMoonAndClouds(vec2 vPos, vec3 base_color) {
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
    return base_color;
}

void computeSmoothedBands(out float bass, out float mid, out float treble) {
    // Smooth music reaction values using exponential moving average
    // (CPU must set uPrevReactBass, uPrevReactMid, uPrevReactTreble and uDeltaTime)
    // Restored partway from 2.2: this was stacking with the CPU-side EMA smoothing above,
    // over-blurring the real bass/mid/treble differences the Multi flame mode needs.
    float smoothFactor = clamp(uDeltaTime * 3.4, 0.0, 1.0);
    bass = mix(uPrevReactBass, uReactBass, smoothFactor);
    mid  = mix(uPrevReactMid,  uReactMid,  smoothFactor);
    treble = mix(uPrevReactTreble, uReactTreble, smoothFactor);
}

float renderFireGround(vec2 vPos, float bass, float mid, float treble, inout vec3 base_color) {
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
    
    return ground_height;
}

vec3 renderFireRocks(vec2 vPos, float bass, vec3 base_color) {
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
    
    return base_color;
}
"""
