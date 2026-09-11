import pygame, time
from engine.window import WindowManager
from engine.renderer3d import Renderer3D
from engine.menu_scene import Menu3DScene, Menu3DCamera
from OpenGL.GL import *

pygame.init()
win = WindowManager("Perf Prototype Test")
r3d = Renderer3D()
r3d.init_gl(win.width, win.height)
scene = Menu3DScene()
cam = Menu3DCamera()

# Test the separation of static vs dynamic
# 1. Compile cable DL
cable_dl = glGenLists(1)
glNewList(cable_dl, GL_COMPILE)
r3d._render_cables(scene.cables, scene.devices)
glEndList()

# 2. Compile device front DL and rear DL
dev_dls = {}
for dev in scene.devices:
    dl_front = glGenLists(1)
    glNewList(dl_front, GL_COMPILE)
    r3d._draw_box(0.0, 0.0, 0.0, dev.width, dev.height, dev.depth, (0.16, 0.18, 0.22))
    if dev.device_type == "switch":
        r3d._render_switch(dev, 0.0)
    elif dev.device_type == "router":
        r3d._render_router(dev, 0.0)
    elif dev.device_type in ("isp_gateway", "isp") or (dev.device_type == "server" and "isp" in dev.hostname.lower()):
        r3d._render_isp_gateway(dev, 0.0)
    elif dev.device_type == "server":
        r3d._render_server(dev, 0.0)
    elif dev.device_type == "firewall":
        r3d._render_firewall(dev, 0.0)
    else:
        r3d._render_generic_device(dev, 0.0)
    glEndList()

    dl_rear = glGenLists(1)
    glNewList(dl_rear, GL_COMPILE)
    if getattr(dev, "rack_id", 0) in (1, 2, 3):
        r3d._render_device_rear(dev, 0.0)
    glEndList()
    dev_dls[dev.id] = (dl_front, dl_rear)

# Benchmark 100 frames with camera in front (Menu view)
cam_z = cam.base_eye_z
t0 = time.perf_counter()
N = 100
for _ in range(N):
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    cam.apply_view()
    now = time.time()
    
    r3d._render_room(now)
    r3d._render_server_racks(now)
    r3d._render_workbench(now)
    
    # Fast device render
    is_front = cam_z >= -1.65
    is_rear = cam_z <= -1.35
    for dev in scene.devices:
        glPushMatrix()
        glTranslatef(dev.pos_x, dev.pos_y, dev.pos_z)
        dl_f, dl_r = dev_dls[dev.id]
        if is_front:
            glCallList(dl_f)
        if is_rear:
            glCallList(dl_r)
        glPopMatrix()
        
    if is_front:
        glCallList(cable_dl)
        
    pygame.display.flip()

t1 = time.perf_counter()
elapsed = (t1 - t0) / N * 1000
fps = 1000.0 / elapsed
print(f"RESULTS WITH OPTIMIZATION:")
print(f"  Frame time: {elapsed:.2f} ms")
print(f"  Estimated FPS: {fps:.1f} FPS")
pygame.quit()
