# Underwater (Lava/deep-sea) sky rendering: caustics, god-rays, and climax plankton bloom.
SKY_UNDERWATER_SOURCE = """
vec3 renderUnderwaterSky(vec2 vPos, float t_gradient, vec3 base_color) {
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
    return base_color;
}
"""
