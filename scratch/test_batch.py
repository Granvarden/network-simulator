import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
import pygame
from OpenGL.GL import *
from engine.window import WindowManager

pygame.init()
win = WindowManager("Test Batch")

# Test 1: 50 individual boxes with glBegin/glEnd each
N = 1000
t0 = time.perf_counter()
for _ in range(N):
    for i in range(30):
        glColor3f(1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        glVertex3f(0, 0, 0); glVertex3f(1, 0, 0); glVertex3f(1, 1, 0); glVertex3f(0, 1, 0)
        glVertex3f(0, 0, 1); glVertex3f(1, 0, 1); glVertex3f(1, 1, 1); glVertex3f(0, 1, 1)
        glVertex3f(0, 1, 0); glVertex3f(1, 1, 0); glVertex3f(1, 1, 1); glVertex3f(0, 1, 1)
        glVertex3f(0, 0, 0); glVertex3f(1, 0, 0); glVertex3f(1, 0, 1); glVertex3f(0, 0, 1)
        glVertex3f(1, 0, 0); glVertex3f(1, 1, 0); glVertex3f(1, 1, 1); glVertex3f(1, 0, 1)
        glVertex3f(0, 0, 0); glVertex3f(0, 1, 0); glVertex3f(0, 1, 1); glVertex3f(0, 0, 1)
        glEnd()
t1 = (time.perf_counter() - t0) / N * 1000

# Test 2: Single glBegin(GL_QUADS) with 30 boxes
t0 = time.perf_counter()
for _ in range(N):
    glBegin(GL_QUADS)
    for i in range(30):
        glColor3f(1.0, 1.0, 1.0)
        glVertex3f(0, 0, 0); glVertex3f(1, 0, 0); glVertex3f(1, 1, 0); glVertex3f(0, 1, 0)
        glVertex3f(0, 0, 1); glVertex3f(1, 0, 1); glVertex3f(1, 1, 1); glVertex3f(0, 1, 1)
        glVertex3f(0, 1, 0); glVertex3f(1, 1, 0); glVertex3f(1, 1, 1); glVertex3f(0, 1, 1)
        glVertex3f(0, 0, 0); glVertex3f(1, 0, 0); glVertex3f(1, 0, 1); glVertex3f(0, 0, 1)
        glVertex3f(1, 0, 0); glVertex3f(1, 1, 0); glVertex3f(1, 1, 1); glVertex3f(1, 0, 1)
        glVertex3f(0, 0, 0); glVertex3f(0, 1, 0); glVertex3f(0, 1, 1); glVertex3f(0, 0, 1)
    glEnd()
t2 = (time.perf_counter() - t0) / N * 1000

print(f"30 boxes separate glBegin/glEnd: {t1:.3f} ms")
print(f"30 boxes single glBegin/glEnd:   {t2:.3f} ms")

pygame.quit()
