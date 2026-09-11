import os
import sys
sys.path.insert(0, os.path.abspath("."))

import pygame
from OpenGL.GL import *
from OpenGL.GLU import *
from engine.camera import FPSCamera
from engine.renderer3d import Renderer3D
from network.switch import Switch
from network.cable import Cable

def run():
    pygame.init()
    w, h = 1280, 720
    pygame.display.set_mode((w, h), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)
    
    renderer = Renderer3D()
    renderer.init_gl(w, h)
    
    cam = FPSCamera()
    
    sw = Switch("sw1", "Core-Switch-01", rack_id=1, u_slot=24)
    sw.pos_x = -1.4
    sw.pos_y = 1.20
    sw.pos_z = -1.5
    devices = [sw]
    cables = []
    
    # 1. Aim directly at front-right post (where user was aiming in screenshot)
    # Rack 1 is at x = -1.4. Front-right post is at x = -1.125, z = -1.10
    cam.x = -1.125
    cam.y = 1.20
    cam.z = -0.4
    cam.yaw = 0.0
    cam.pitch = 0.0
    
    f_dev, f_port, hit_dist = cam.raycast(devices)
    print(f"Aim at Post -> f_dev: {f_dev.hostname if f_dev else None}, f_port: {f_port}")
    assert f_dev is None, f"Expected f_dev to be None, got {f_dev}"
    
    renderer.render_scene(cam, devices, cables, focused_dev=f_dev, focused_port=f_port)
    glFinish()
    
    # Read OpenGL buffer to surface
    glPixelStorei(GL_PACK_ALIGNMENT, 1)
    data = glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE)
    surf = pygame.image.fromstring(data, (w, h), "RGB", True)
    pygame.image.save(surf, "scratch/raycast_blocked_post.png")
    print("Saved scratch/raycast_blocked_post.png")
    
    # 2. Aim at device front face
    cam.x = -1.4
    cam.y = 1.20
    cam.z = -0.4
    cam.yaw = 0.0
    cam.pitch = 0.0
    
    f_dev2, f_port2, hit_dist2 = cam.raycast(devices)
    print(f"Aim at Device -> f_dev: {f_dev2.hostname if f_dev2 else None}, f_port: {f_port2}")
    assert f_dev2 == sw, f"Expected f_dev to be sw, got {f_dev2}"
    
    renderer.render_scene(cam, devices, cables, focused_dev=f_dev2, focused_port=f_port2)
    glFinish()
    
    data2 = glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE)
    surf2 = pygame.image.fromstring(data2, (w, h), "RGB", True)
    pygame.image.save(surf2, "scratch/raycast_frontal_aim.png")
    print("Saved scratch/raycast_frontal_aim.png")
    
    pygame.quit()
    print("VERIFICATION COMPLETE!")

if __name__ == "__main__":
    run()
