import os
import sys
sys.path.insert(0, os.path.abspath("."))

import pygame
from OpenGL.GL import *
from OpenGL.GLU import *
from engine.camera import FPSCamera
from engine.renderer3d import Renderer3D
from engine.renderer2d import Renderer2D
from ui.hud import HUD
from network.switch import Switch
from network.cable import Cable

def run():
    pygame.init()
    w, h = 1280, 720
    pygame.display.set_mode((w, h), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)
    
    r3d = Renderer3D()
    r3d.init_gl(w, h)
    r2d = Renderer2D(w, h)
    hud = HUD()
    
    cam = FPSCamera()
    
    # Recreate the exact scene from user screenshot:
    # User was looking at a switch in a rack, with post in the center
    # In the screenshot, switch is to the left, black vertical post in the center
    # Cam is around x = -1.15, y = 1.20, z = -0.45, looking slightly right or straight
    sw = Switch("sw1", "Core-Switch-01", rack_id=1, u_slot=24)
    sw.pos_x = -1.4
    sw.pos_y = 1.20
    sw.pos_z = -1.5
    devices = [sw]
    
    # 1. Aim at post (Reticle is on the post, switch is visible to the left behind it)
    cam.x = -1.12
    cam.y = 1.20
    cam.z = -0.55
    cam.yaw = 0.0
    cam.pitch = 0.0
    
    f_dev, f_port, hit_dist = cam.raycast(devices)
    print(f"Scenario 1 (Crosshair on Post) -> f_dev: {f_dev}")
    assert f_dev is None, f"Expected None, got {f_dev}"
    
    # Render 3D
    r3d.render_scene(cam, devices, [], focused_dev=f_dev, focused_port=f_port)
    
    # Render 2D HUD
    r2d.clear_surface()
    hud.draw(r2d.hud_surface, w, h, f_dev, f_port, None,
             "SANDBOX MODE", "Explore & build", [])
    
    # Composite to screen
    r2d.render_overlay()
    glFinish()
    
    data = glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE)
    surf = pygame.image.fromstring(data, (w, h), "RGB", True)
    pygame.image.save(surf, "scratch/occlusion_post_hud.png")
    print("Saved scratch/occlusion_post_hud.png")
    
    # 2. Aim at switch (Move camera or look at switch)
    cam.x = -1.35
    f_dev2, f_port2, hit_dist2 = cam.raycast(devices)
    print(f"Scenario 2 (Crosshair on Switch) -> f_dev: {f_dev2.hostname if f_dev2 else None}")
    assert f_dev2 == sw, f"Expected sw, got {f_dev2}"
    
    r3d.render_scene(cam, devices, [], focused_dev=f_dev2, focused_port=f_port2)
    r2d.clear_surface()
    hud.draw(r2d.hud_surface, w, h, f_dev2, f_port2, None,
             "SANDBOX MODE", "Explore & build", [])
    r2d.render_overlay()
    glFinish()
    
    data2 = glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE)
    surf2 = pygame.image.fromstring(data2, (w, h), "RGB", True)
    pygame.image.save(surf2, "scratch/occlusion_switch_hud.png")
    print("Saved scratch/occlusion_switch_hud.png")
    
    pygame.quit()

if __name__ == "__main__":
    run()
