import os
import sys
sys.path.insert(0, r"c:\Users\admin\Desktop\programming\game")

import pygame
from OpenGL.GL import *
from OpenGL.GLU import gluLookAt

pygame.init()
pygame.font.init()

from modes.sandbox_mode import SandboxMode
from engine.renderer3d import Renderer3D

pygame.display.set_mode((1280, 720), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)
renderer = Renderer3D(fov=65.0)
renderer.init_gl(1280, 720)
sandbox = SandboxMode()

class Cam:
    def __init__(self, x, y, z, tx, ty, tz):
        self.x = x
        self.y = y
        self.z = z
        self.tx = tx
        self.ty = ty
        self.tz = tz
    def apply_view(self):
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        gluLookAt(self.x, self.y, self.z, self.tx, self.ty, self.tz, 0.0, 1.0, 0.0)

views = [
    # 1. User screenshot angle (chair removed, wall decorated)
    ("user_wall_angle_after.png", Cam(-1.20, 1.28, 0.30, -4.00, 1.45, 4.00)),
    # 2. Left Wall close-up (Blueprint, Fiber ODF, Tool Pegboard, Safety)
    ("wall_left_detail.png", Cam(-2.8, 1.55, 3.8, -5.95, 1.55, 3.8)),
    # 3. Front Wall NOC & Video Wall (Observation window, World clocks, 75" DCIM display, Airlock)
    ("wall_front_noc.png", Cam(0.0, 1.60, 2.0, 0.0, 1.65, 5.98)),
    # 4. Cold aisle & Racks (Centered mat and grilles, chair gone from workbench)
    ("cold_aisle_centered_mat.png", Cam(0.0, 1.70, 1.5, 0.0, 1.20, -1.5)),
    # 5. Right Wall detail (Switchgear cabinet and telemetry pod)
    ("wall_right_detail.png", Cam(3.0, 1.55, 4.0, 5.95, 1.55, 4.0)),
]

output_dir = r"C:\Users\admin\.gemini\antigravity-ide\brain\577a52f7-8e41-4992-8a99-dda184c7df4f\scratch"

for filename, cam in views:
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    renderer.render_scene(cam, sandbox.devices, sandbox.cables)
    data = glReadPixels(0, 0, 1280, 720, GL_RGBA, GL_UNSIGNED_BYTE)
    pygame.display.flip()
    img = pygame.image.fromstring(data, (1280, 720), "RGBA", True)
    filepath = os.path.join(output_dir, filename)
    pygame.image.save(img, filepath)
    print(f"Saved: {filepath}")

pygame.quit()
