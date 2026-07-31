import sys
import OpenGL.GL as gl

def compile_shader(shader_type, source):
    # Dynamic preprocessor to map GLES 3.00 shaders to Desktop GLSL 3.30 on Windows and macOS
    if sys.platform in ('win32', 'darwin'):
        if source.startswith("#version 300 es") or "#version 300 es" in source:
            source = source.replace("#version 300 es", "#version 330 core")
            
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
