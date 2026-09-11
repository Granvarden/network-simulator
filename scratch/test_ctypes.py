import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time, ctypes
import pygame
from OpenGL.GL import *
from engine.window import WindowManager

pygame.init()
win = WindowManager("Test Ctypes")
w, h = win.width, win.height

surf = pygame.Surface((w, h), pygame.SRCALPHA)
surf.fill((0, 0, 0, 0))

tex_id = glGenTextures(1)
glBindTexture(GL_TEXTURE_2D, tex_id)
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)

buf = surf.get_buffer()
size = buf.length

# Test ctypes pointer from buffer
c_buf = (ctypes.c_char * size).from_buffer(buf)

N = 100
t0 = time.perf_counter()
for _ in range(N):
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_BGRA, GL_UNSIGNED_BYTE, c_buf)
t_ctypes = (time.perf_counter() - t0) / N * 1000
print(f"ctypes from_buffer: {t_ctypes:.3f} ms")

pygame.quit()
