import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
import pygame
from OpenGL.GL import *
from engine.window import WindowManager
from engine.camera import FPSCamera
from engine.renderer3d import Renderer3D
from modes.sandbox_mode import SandboxMode

pygame.init()
win = WindowManager("Test Device DL")
cam = FPSCamera()
r3d = Renderer3D()
mode = SandboxMode()
r3d.init_gl(win.width, win.height)

# Measure current _render_devices
N = 120
t0 = time.perf_counter()
for _ in range(N):
    r3d._render_devices(mode.devices, time.time())
t_current = (time.perf_counter() - t0) / N * 1000
print(f"Current _render_devices: {t_current:.3f} ms")

# Now let's see: what if we compile static geometry for each device into a display list?
# We create a display list for each device's static parts
device_dl = {}
for dev in mode.devices:
    if dev.device_type == "laptop":
        continue
    dl = glGenLists(1)
    glNewList(dl, GL_COMPILE)
    # Draw static body
    r3d._draw_box(0.0, 0.0, 0.0, dev.width, dev.height, dev.depth, (0.16, 0.18, 0.22))
    
    if dev.device_type == "switch":
        hw = dev.width / 2.0
        hh = dev.height / 2.0
        front_z = dev.depth / 2.0 + 0.003
        r3d._draw_box(0.0, 0.0, front_z, dev.width, dev.height, 0.006, (0.14, 0.32, 0.42))
        r3d._draw_box(0.0, hh - 0.004, front_z + 0.001, dev.width - 0.04, 0.005, 0.002, (0.0, 0.75, 0.92))
        led_names = [(-0.20, "SYST"), (-0.185, "RPS"), (-0.170, "STAT"), (-0.155, "SPEED")]
        for lx, _ in led_names:
            r3d._draw_box(lx, hh - 0.015, front_z + 0.002, 0.005, 0.005, 0.002, (0.1, 0.98, 0.2))
        con_port = dev.ports.get("con0")
        if con_port:
            cx, cy, cz = dev.get_port_local_pos(con_port.name, con_port.port_index)
            r3d._draw_box(cx, cy, cz, 0.024, 0.018, 0.003, (0.2, 0.65, 0.95))
            r3d._draw_box(cx, cy, cz + 0.002, 0.018, 0.014, 0.002, (0.05, 0.08, 0.12))
        r3d._draw_box(0.20, 0.0, front_z + 0.001, 0.06, dev.height - 0.015, 0.002, (0.09, 0.12, 0.16))
        r3d._draw_box(-hw + 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.45, 0.48, 0.52))
        r3d._draw_box(hw - 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.45, 0.48, 0.52))
        r3d._draw_box(-hw + 0.01, 0.0, front_z + 0.004, 0.008, 0.008, 0.002, (0.85, 0.88, 0.92))
        r3d._draw_box(hw - 0.01, 0.0, front_z + 0.004, 0.008, 0.008, 0.002, (0.85, 0.88, 0.92))
        port_list = [p for p in dev.ports.values() if p.port_type != "CONSOLE"]
        for idx, port in enumerate(port_list):
            px, py, pz = dev.get_port_local_pos(port.name, port.port_index)
            r3d._draw_box(px, py, pz, 0.025, 0.020, 0.004, (0.52, 0.55, 0.58))
            r3d._draw_box(px, py, pz + 0.002, 0.020, 0.015, 0.003, (0.03, 0.03, 0.04))
            r3d._draw_box(px, py + 0.003, pz + 0.003, 0.012, 0.003, 0.001, (0.85, 0.72, 0.15))
    glEndList()
    device_dl[dev] = dl

# Now test rendering with display list for switch + dynamic LEDs
t0 = time.perf_counter()
for _ in range(N):
    now = time.time()
    for dev in mode.devices:
        glPushMatrix()
        glTranslatef(dev.pos_x, dev.pos_y, dev.pos_z)
        if dev in device_dl:
            glCallList(device_dl[dev])
            # Only draw dynamic LEDs for switch
            if dev.device_type == "switch":
                port_list = [p for p in dev.ports.values() if p.port_type != "CONSOLE"]
                for idx, port in enumerate(port_list):
                    px, py, pz = dev.get_port_local_pos(port.name, port.port_index)
                    r3d._draw_box(px - 0.005, py + 0.016, pz + 0.003, 0.006, 0.006, 0.003, (0.1, 0.98, 0.2))
                    r3d._draw_box(px + 0.005, py + 0.016, pz + 0.003, 0.006, 0.006, 0.003, (0.2, 0.95, 0.3))
        elif dev.device_type == "laptop":
            r3d._render_laptop(dev, now)
        else:
            # other devices fallback
            r3d._draw_box(0.0, 0.0, 0.0, dev.width, dev.height, dev.depth, (0.16, 0.18, 0.22))
        glPopMatrix()

t_dl = (time.perf_counter() - t0) / N * 1000
print(f"Display list optimized _render_devices (switches only): {t_dl:.3f} ms")

pygame.quit()
