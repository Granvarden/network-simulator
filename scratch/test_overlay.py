import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
import pygame
from OpenGL.GL import *
from engine.window import WindowManager

pygame.init()
win = WindowManager("Test Overlay")
w, h = win.width, win.height

surf = pygame.Surface((w, h), pygame.SRCALPHA)
surf.fill((0, 0, 0, 0))

tex_id = glGenTextures(1)
glBindTexture(GL_TEXTURE_2D, tex_id)
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)

# Test 1: bytes(surf.get_buffer())
N = 100
t0 = time.perf_counter()
for _ in range(N):
    buf = surf.get_buffer()
    b = bytes(buf)
t_bytes = (time.perf_counter() - t0) / N * 1000

# Test 2: memoryview(buf)
t0 = time.perf_counter()
try:
    mv = memoryview(surf.get_buffer())
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_BGRA, GL_UNSIGNED_BYTE, mv)
    for _ in range(N):
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_BGRA, GL_UNSIGNED_BYTE, memoryview(surf.get_buffer()))
    t_mv = (time.perf_counter() - t0) / N * 1000
    print(f"memoryview:                       {t_mv:.3f} ms")
except Exception as e:
    print(f"memoryview failed: {e}")

# Test 3: pygame.image.tobytes
t0 = time.perf_counter()
for _ in range(N):
    b = pygame.image.tobytes(surf, "BGRA")
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_BGRA, GL_UNSIGNED_BYTE, b)
t_tobytes = (time.perf_counter() - t0) / N * 1000
print(f"pygame.image.tobytes + glTex:     {t_tobytes:.3f} ms")

# Test 4: bytes(buf)
t0 = time.perf_counter()
for _ in range(N):
    b = bytes(surf.get_buffer())
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_BGRA, GL_UNSIGNED_BYTE, b)
t_bytes_buf = (time.perf_counter() - t0) / N * 1000
print(f"bytes(get_buffer()) + glTex:      {t_bytes_buf:.3f} ms")

print(f"Resolution: {w}x{h}")
print(f"bytes(get_buffer()):              {t_bytes:.3f} ms")
print(f"glTexSubImage2D with buf direct:  {t_subimage_buffer:.3f} ms")
print(f"glTexSubImage2D with bytes(buf):  {t_subimage_bytes:.3f} ms")

pygame.quit()
