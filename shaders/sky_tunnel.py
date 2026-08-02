# Cosmic Wormhole Tunnel sky rendering: raymarched plasma tunnel walls.
SKY_TUNNEL_SOURCE = """
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

vec3 renderTunnelSky(vec2 vPos, vec3 base_color) {
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
    
    return base_color;
}
"""
