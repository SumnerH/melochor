# Modern Shader Sources (GLSL ES 3.00) - Line Shaders
LINE_VERTEX_SHADER = """#version 300 es
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec4 aColor;
out vec4 vColor;
uniform mat4 projection;
uniform mat4 view;
uniform int uFireMode;
void main() {
    vColor = aColor;
    if (uFireMode == 1) {
        gl_Position = vec4(aPos.x, aPos.y, 0.0, 1.0);
    } else {
        gl_Position = projection * view * vec4(aPos, 1.0);
    }
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
