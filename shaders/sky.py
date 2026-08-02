from shaders.sky_common import SKY_VERTEX_SHADER, SKY_COMMON_SOURCE
from shaders.sky_underwater import SKY_UNDERWATER_SOURCE
from shaders.sky_tunnel import SKY_TUNNEL_SOURCE
from shaders.sky_fire_common import SKY_FIRE_COMMON_SOURCE
from shaders.sky_fire_flames import SKY_FIRE_FLAMES_SOURCE

# Thin assembler: builds the final SKY_FRAGMENT_SHADER by concatenating the shared header
# (uniforms + noise helpers + starfield) with each mode's rendering function, then a small
# main() that dispatches to the right function based on uRipple/mode. This lets each mode's
# shader code live in its own file (sky_underwater.py, sky_tunnel.py, sky_fire_common.py,
# sky_fire_flames.py) so working on a single mode doesn't require touching the others.

_SKY_MAIN_SOURCE = """
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
        base_color = renderUnderwaterSky(vPos, t_gradient, base_color);
    } 
    else if (uRipple > 1.5 && uRipple < 2.5) {
        base_color = renderTunnelSky(vPos, base_color);
    }
    else if (uRipple > 2.5) {
        base_color = renderFireMoonAndClouds(vPos, base_color);

        float bass, mid, treble;
        computeSmoothedBands(bass, mid, treble);

        float ground_height = renderFireGround(vPos, bass, mid, treble, base_color);
        base_color = renderFireFlames(vPos, ground_height, bass, mid, treble, base_color);
        base_color = renderFireRocks(vPos, bass, base_color);
    }
    
    FragColor = vec4(base_color, 1.0);
}
"""

SKY_FRAGMENT_SHADER = (
    SKY_COMMON_SOURCE
    + SKY_UNDERWATER_SOURCE
    + SKY_TUNNEL_SOURCE
    + SKY_FIRE_COMMON_SOURCE
    + SKY_FIRE_FLAMES_SOURCE
    + _SKY_MAIN_SOURCE
)
