import os
import sys
import time
sys.path.insert(0, r"c:\Users\admin\Desktop\programming\game")

import pygame
from OpenGL.GL import *
from OpenGL.GLU import gluLookAt

pygame.init()
pygame.font.init()

from ui.menu import MenuManager, MenuState
from engine.renderer3d import Renderer3D
from engine.renderer2d import Renderer2D

W, H = 1280, 720
pygame.display.set_mode((W, H), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)

renderer3d = Renderer3D(fov=65.0)
renderer3d.init_gl(W, H)

renderer2d = Renderer2D(W, H)
renderer2d.init_gl()

menu = MenuManager()
menu.state = MenuState.HELP_GUIDE

output_dir = r"C:\Users\admin\.gemini\antigravity-ide\brain\577a52f7-8e41-4992-8a99-dda184c7df4f\scratch"
os.makedirs(output_dir, exist_ok=True)

test_cases = [
    ("cheatsheet_router.png", 0, 0, 35.0, 18.0),       # Router, 3/4 view
    ("cheatsheet_router_rear.png", 0, 1, 185.0, 15.0), # Router rear view, Routing cat
    ("cheatsheet_switch.png", 1, 0, 30.0, 20.0),       # Switch, VLAN cat
    ("cheatsheet_server.png", 2, 0, 40.0, 16.0),       # Server, Network IP cat
    ("cheatsheet_firewall.png", 3, 0, -35.0, 18.0),    # Firewall, 3/4 angle
    ("cheatsheet_laptop.png", 4, 0, 25.0, 15.0),       # Laptop, CLI cat
    ("cheatsheet_controls.png", 5, 0, 15.0, 12.0),     # Simulator Controls
]

for filename, dev_idx, cat_idx, yaw, pitch in test_cases:
    menu.showcase_selected_idx = dev_idx
    menu.showcase_cat_idx = cat_idx
    menu.showcase_yaw = yaw
    menu.showcase_pitch = pitch
    menu.showcase_scroll_y = 0

    # 1. Clear OpenGL buffer
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    # 2. Render 3D Device Showcase Viewport
    vp_rect = menu.get_showcase_viewport(W, H)
    dev = menu.get_showcase_device()
    renderer3d.render_device_preview(dev, menu.showcase_yaw, menu.showcase_pitch, 1.0, vp_rect, W, H)

    # 3. Render 2D Menu HUD Surface
    renderer2d.clear_surface()
    menu.render(renderer2d.hud_surface, W, H)

    # 4. Composite 2D overlay onto OpenGL buffer
    renderer2d.render_overlay()

    # 5. Read back pixels and save
    glPixelStorei(GL_PACK_ALIGNMENT, 1)
    data = glReadPixels(0, 0, W, H, GL_RGBA, GL_UNSIGNED_BYTE)
    pygame.display.flip()

    img = pygame.image.fromstring(data, (W, H), "RGBA", True)
    filepath = os.path.join(output_dir, filename)
    pygame.image.save(img, filepath)
    print(f"Saved: {filepath}")

pygame.quit()
print("All cheatsheet test renderings completed successfully!")
