import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
import pygame
from engine.window import WindowManager
from engine.camera import FPSCamera
from engine.renderer3d import Renderer3D
from modes.sandbox_mode import SandboxMode

pygame.init()
win = WindowManager("Profile R3D")
cam = FPSCamera()
r3d = Renderer3D()
mode = SandboxMode()
r3d.init_gl(win.width, win.height)

now = time.time()
f_dev, f_port, _ = cam.raycast(mode.devices)

# Profile parts of render_scene
N = 100

t_room = 0.0
t_racks = 0.0
t_workbench = 0.0
t_devices = 0.0
t_cables = 0.0
t_highlight = 0.0

for _ in range(N):
    now = time.time()
    
    t0 = time.perf_counter()
    r3d._render_room(now)
    t1 = time.perf_counter()
    r3d._render_server_racks(now)
    t2 = time.perf_counter()
    r3d._render_workbench(now)
    t3 = time.perf_counter()
    r3d._render_devices(mode.devices, now)
    t4 = time.perf_counter()
    r3d._render_cables(mode.cables)
    t5 = time.perf_counter()
    if f_dev:
        r3d._render_highlight(f_dev, f_port, now)
    t6 = time.perf_counter()

    t_room += (t1 - t0)
    t_racks += (t2 - t1)
    t_workbench += (t3 - t2)
    t_devices += (t4 - t3)
    t_cables += (t5 - t4)
    t_highlight += (t6 - t5)

print(f"=== 3D RENDER DETAILED PROFILE ===")
print(f"Room:        {t_room*1000/N:6.2f} ms ({t_room/(t6-t0)*100:4.1f}%)")
print(f"Racks:       {t_racks*1000/N:6.2f} ms ({t_racks/(t6-t0)*100:4.1f}%)")
print(f"Workbench:   {t_workbench*1000/N:6.2f} ms ({t_workbench/(t6-t0)*100:4.1f}%)")
print(f"Devices:     {t_devices*1000/N:6.2f} ms ({t_devices/(t6-t0)*100:4.1f}%)")
print(f"Cables:      {t_cables*1000/N:6.2f} ms ({t_cables/(t6-t0)*100:4.1f}%)")
print(f"Highlight:   {t_highlight*1000/N:6.2f} ms ({t_highlight/(t6-t0)*100:4.1f}%)")
print(f"Total:       {(t6-t0)*1000/N:6.2f} ms")

pygame.quit()
