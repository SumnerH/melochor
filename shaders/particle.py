# Modern Shader Sources (GLSL ES 3.00) - Particle Shaders
PARTICLE_VERTEX_SHADER = """#version 300 es
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec4 aColor;
layout (location = 2) in float aSize;

out vec4 vColor;
out float vRand;
out float vStyle; // 0.0 = Star/Spark, 1.0 = Smooth Gaseous Puff

uniform mat4 projection;
uniform mat4 view;
uniform int uFireMode;

// High quality GPU hash function to generate a stable random seed [0, 1] per particle
float hash3(vec3 p) {
    return fract(sin(dot(p, vec3(12.9898, 78.233, 45.164))) * 43758.5453123);
}

void main() {
    vColor = aColor;
    vRand = hash3(aPos);
    vStyle = aSize < 0.0 ? 1.0 : 0.0;
    
    if (uFireMode == 1) {
        // Direct screen-space projection for flat 2D effects (e.g., procedural campfire)
        gl_Position = vec4(aPos.x, aPos.y, 0.0, 1.0);
        gl_PointSize = abs(aSize) * 2.5;
    } else {
        // 3D Perspective Projection for full space scenes
        vec4 mvPos = view * vec4(aPos, 1.0);
        gl_Position = projection * mvPos;
        float dist = max(0.1, -mvPos.z);
        gl_PointSize = abs(aSize) * (42.0 / dist);
    }
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
        float r = length(coord);
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
