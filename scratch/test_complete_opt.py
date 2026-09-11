import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time, math, ctypes
import pygame
from OpenGL.GL import *
from engine.window import WindowManager
from engine.camera import FPSCamera
from engine.renderer3d import Renderer3D
from engine.renderer2d import Renderer2D
from ui.hud import HUD
from modes.sandbox_mode import SandboxMode
from network.device import LEDState

def benchmark():
    pygame.init()
    win = WindowManager("Benchmark Full Opt")
    cam = FPSCamera()
    r3d = Renderer3D()
    r2d = Renderer2D(win.width, win.height)
    hud = HUD()
    mode = SandboxMode()

    r3d.init_gl(win.width, win.height)
    r2d.init_gl()

    # Pre-compile display lists for devices
    dev_lists = {}
    for dev in mode.devices:
        if dev.device_type == "laptop":
            continue
        dl = glGenLists(1)
        glNewList(dl, GL_COMPILE)
        r3d._draw_box(0.0, 0.0, 0.0, dev.width, dev.height, dev.depth, (0.16, 0.18, 0.22))
        hw = dev.width / 2.0
        hh = dev.height / 2.0
        front_z = dev.depth / 2.0 + 0.003
        
        if dev.device_type == "switch":
            r3d._draw_box(0.0, 0.0, front_z, dev.width, dev.height, 0.006, (0.14, 0.32, 0.42))
            r3d._draw_box(0.0, hh - 0.004, front_z + 0.001, dev.width - 0.04, 0.005, 0.002, (0.0, 0.75, 0.92))
            for lx, _ in [(-0.20, "SYST"), (-0.185, "RPS"), (-0.170, "STAT"), (-0.155, "SPEED")]:
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
            for idx, port in enumerate([p for p in dev.ports.values() if p.port_type != "CONSOLE"]):
                px, py, pz = dev.get_port_local_pos(port.name, port.port_index)
                r3d._draw_box(px, py, pz, 0.025, 0.020, 0.004, (0.52, 0.55, 0.58))
                r3d._draw_box(px, py, pz + 0.002, 0.020, 0.015, 0.003, (0.03, 0.03, 0.04))
                r3d._draw_box(px, py + 0.003, pz + 0.003, 0.012, 0.003, 0.001, (0.85, 0.72, 0.15))
        elif dev.device_type == "router":
            r3d._draw_box(0.0, 0.0, front_z, dev.width, dev.height, 0.006, (0.20, 0.24, 0.34))
            for mx in [-0.08, 0.08]:
                r3d._draw_box(mx, 0.022, front_z + 0.002, 0.14, 0.034, 0.003, (0.14, 0.16, 0.22))
                r3d._draw_box(mx - 0.06, 0.022, front_z + 0.004, 0.007, 0.007, 0.002, (0.75, 0.78, 0.82))
                r3d._draw_box(mx + 0.06, 0.022, front_z + 0.004, 0.007, 0.007, 0.002, (0.75, 0.78, 0.82))
            for sx, sy in [(-0.18, 0.025), (-0.165, 0.025), (-0.18, 0.012), (-0.165, 0.012)]:
                r3d._draw_box(sx, sy, front_z + 0.002, 0.006, 0.006, 0.002, (0.1, 0.95, 0.2))
            r3d._draw_box(0.18, 0.0, front_z + 0.001, 0.08, dev.height - 0.02, 0.002, (0.12, 0.14, 0.18))
            r3d._draw_box(-hw + 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.42, 0.45, 0.50))
            r3d._draw_box(hw - 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.42, 0.45, 0.50))
            for sy in [-0.025, 0.025]:
                r3d._draw_box(-hw + 0.01, sy, front_z + 0.004, 0.007, 0.007, 0.002, (0.85, 0.88, 0.92))
                r3d._draw_box(hw - 0.01, sy, front_z + 0.004, 0.007, 0.007, 0.002, (0.85, 0.88, 0.92))
            con_port = dev.ports.get("con0")
            if con_port:
                cx, cy, cz = dev.get_port_local_pos(con_port.name, con_port.port_index)
                r3d._draw_box(cx, cy, cz, 0.024, 0.018, 0.003, (0.2, 0.65, 0.95))
                r3d._draw_box(cx, cy, cz + 0.002, 0.018, 0.014, 0.002, (0.05, 0.08, 0.12))
            for idx, port in enumerate([p for p in dev.ports.values() if p.port_type != "CONSOLE"]):
                px, py, pz = dev.get_port_local_pos(port.name, port.port_index)
                r3d._draw_box(px, py, pz, 0.026, 0.022, 0.004, (0.50, 0.53, 0.56))
                r3d._draw_box(px, py, pz + 0.002, 0.020, 0.016, 0.003, (0.04, 0.04, 0.05))
        elif dev.device_type == "server" and not "isp" in dev.hostname.lower():
            r3d._draw_box(0.0, 0.0, front_z, dev.width, dev.height, 0.006, (0.24, 0.26, 0.29))
            for bay in range(8):
                bx = -0.16 + (bay % 4) * 0.065
                by = 0.018 if bay < 4 else -0.022
                r3d._draw_box(bx, by, front_z + 0.002, 0.058, 0.032, 0.004, (0.15, 0.16, 0.19))
                r3d._draw_box(bx - 0.018, by, front_z + 0.004, 0.012, 0.024, 0.002, (0.35, 0.38, 0.42))
            r3d._draw_box(0.14, 0.024, front_z + 0.004, 0.045, 0.014, 0.003, (0.0, 0.45, 0.85))
            r3d._draw_box(0.14, -0.002, front_z + 0.003, 0.060, 0.022, 0.002, (0.05, 0.22, 0.35))
            r3d._draw_box(0.19, 0.024, front_z + 0.004, 0.016, 0.016, 0.003, (0.1, 0.95, 0.3))
            r3d._draw_box(-hw + 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.50, 0.54, 0.58))
            r3d._draw_box(hw - 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.50, 0.54, 0.58))
            port = dev.ports.get("eth0")
            if port:
                px, py, pz = dev.get_port_local_pos(port.name, port.port_index)
                r3d._draw_box(px, py, pz, 0.026, 0.020, 0.004, (0.45, 0.48, 0.52))
                r3d._draw_box(px, py, pz + 0.002, 0.020, 0.015, 0.003, (0.04, 0.04, 0.05))
        elif dev.device_type == "firewall":
            r3d._draw_box(0.0, 0.0, front_z, dev.width, dev.height, 0.006, (0.58, 0.12, 0.16))
            r3d._draw_box(0.02, 0.0, front_z + 0.001, dev.width - 0.12, dev.height - 0.010, 0.003, (0.12, 0.13, 0.16))
            r3d._draw_box(-0.16, hh - 0.008, front_z + 0.003, 0.07, 0.010, 0.002, (0.82, 0.14, 0.18))
            for lx, ly, col in [(-0.19, 0.008, (0.1, 0.98, 0.2)), (-0.178, 0.008, (0.1, 0.98, 0.2)), (-0.19, -0.008, (0.1, 0.90, 0.85)), (-0.178, -0.008, (0.15, 0.82, 0.98))]:
                r3d._draw_box(lx, ly, front_z + 0.003, 0.005, 0.005, 0.002, col)
            con_port = dev.ports.get("con0")
            if con_port:
                cx, cy, cz = dev.get_port_local_pos(con_port.name, con_port.port_index)
                r3d._draw_box(cx, cy, cz, 0.022, 0.017, 0.003, (0.2, 0.65, 0.95))
                r3d._draw_box(cx, cy, cz + 0.002, 0.017, 0.013, 0.002, (0.05, 0.08, 0.12))
            m_port = dev.ports.get("m0/0")
            if m_port:
                mx, my, mz = dev.get_port_local_pos(m_port.name, m_port.port_index)
                r3d._draw_box(mx, my, mz, 0.022, 0.017, 0.003, (0.42, 0.45, 0.48))
                r3d._draw_box(mx, my, mz + 0.002, 0.017, 0.013, 0.002, (0.05, 0.08, 0.12))
            r3d._draw_box(0.20, 0.0, front_z + 0.002, 0.05, dev.height - 0.016, 0.002, (0.08, 0.09, 0.11))
            r3d._draw_box(-hw + 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.45, 0.48, 0.52))
            r3d._draw_box(hw - 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.45, 0.48, 0.52))
            r3d._draw_box(-hw + 0.01, 0.0, front_z + 0.004, 0.008, 0.008, 0.002, (0.85, 0.88, 0.92))
            r3d._draw_box(hw - 0.01, 0.0, front_z + 0.004, 0.008, 0.008, 0.002, (0.85, 0.88, 0.92))
            for idx, port in enumerate([p for p in dev.ports.values() if p.port_type != "CONSOLE" and not p.name.startswith("m")]):
                px, py, pz = dev.get_port_local_pos(port.name, port.port_index)
                r3d._draw_box(px, py, pz, 0.025, 0.020, 0.004, (0.52, 0.55, 0.58))
                r3d._draw_box(px, py, pz + 0.002, 0.020, 0.015, 0.003, (0.03, 0.03, 0.04))
                r3d._draw_box(px, py + 0.003, pz + 0.003, 0.012, 0.003, 0.001, (0.85, 0.72, 0.15))
                zone = getattr(dev, "nameif", {}).get(port.name, "")
                z_col = (0.85, 0.18, 0.18) if zone == "outside" else ((0.15, 0.75, 0.25) if zone == "inside" else ((0.95, 0.55, 0.10) if zone == "dmz" else (0.35, 0.40, 0.48)))
                r3d._draw_box(px, py + 0.014, pz + 0.002, 0.022, 0.003, 0.002, z_col)
        elif dev.device_type in ("isp_gateway", "isp") or (dev.device_type == "server" and "isp" in dev.hostname.lower()):
            r3d._draw_box(0.0, 0.0, front_z, dev.width, dev.height, 0.006, (0.20, 0.22, 0.26))
            r3d._draw_box(0.0, -0.002, front_z + 0.001, dev.width - 0.045, dev.height - 0.008, 0.003, (0.28, 0.31, 0.36))
            r3d._draw_box(0.0, hh - 0.003, front_z + 0.002, dev.width - 0.04, 0.003, 0.002, (0.95, 0.78, 0.10))
            r3d._draw_box(0.0, hh - 0.006, front_z + 0.002, dev.width - 0.04, 0.002, 0.002, (0.0, 0.75, 0.95))
            for ear_x in [-hw + 0.01, hw - 0.01]:
                r3d._draw_box(ear_x, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.42, 0.45, 0.50))
                for sy in [-0.012, 0.012]:
                    r3d._draw_box(ear_x, sy, front_z + 0.004, 0.006, 0.006, 0.002, (0.85, 0.88, 0.92))
                r3d._draw_box(ear_x, 0.0, front_z + 0.005, 0.009, 0.009, 0.004, (0.65, 0.68, 0.72))
            for gy in [-0.008, 0.008]:
                r3d._draw_box(-0.21, gy, front_z + 0.003, 0.005, 0.005, 0.003, (0.78, 0.65, 0.20))
            r3d._draw_box(-0.21, 0.0, front_z + 0.002, 0.004, 0.006, 0.001, (0.1, 0.85, 0.25))
            r3d._draw_box(-0.165, 0.0, front_z + 0.002, 0.075, dev.height - 0.014, 0.002, (0.12, 0.13, 0.16))
            r3d._draw_box(-0.145, 0.0, front_z + 0.003, 0.016, 0.016, 0.002, (0.95, 0.80, 0.10))
            r3d._draw_box(-0.145, 0.0, front_z + 0.004, 0.010, 0.010, 0.001, (0.10, 0.10, 0.10))
            r3d._draw_box(-0.145, 0.0, front_z + 0.0045, 0.004, 0.004, 0.001, (0.95, 0.80, 0.10))
            r3d._draw_box(-0.065, 0.0, front_z + 0.0025, 0.115, 0.028, 0.002, (0.10, 0.11, 0.13))
            r3d._draw_box(-0.065, 0.0, front_z + 0.0035, 0.105, 0.022, 0.001, (0.02, 0.14, 0.22))
            px, py, pz = dev.get_port_local_pos("eth0", 0)
            r3d._draw_box(px, py, front_z + 0.002, 0.038, dev.height - 0.012, 0.002, (0.16, 0.18, 0.22))
            r3d._draw_box(px, py + 0.013, front_z + 0.003, 0.032, 0.002, 0.001, (0.0, 0.75, 0.95))
            r3d._draw_box(px, py, pz, 0.026, 0.020, 0.004, (0.58, 0.62, 0.66))
            r3d._draw_box(px, py, pz + 0.002, 0.020, 0.015, 0.003, (0.03, 0.03, 0.04))
            r3d._draw_box(px, py + 0.003, pz + 0.003, 0.012, 0.003, 0.001, (0.90, 0.78, 0.18))
            r3d._draw_box(0.115, 0.0, front_z + 0.002, 0.065, dev.height - 0.012, 0.002, (0.14, 0.15, 0.18))
            sfp_configs = [(0.098, (0.05, 0.45, 0.90), True), (0.132, (0.95, 0.55, 0.10), False)]
            for s_idx, (sx, latch_col, has_fiber) in enumerate(sfp_configs):
                r3d._draw_box(sx, 0.0, front_z + 0.003, 0.024, 0.018, 0.005, (0.50, 0.53, 0.57))
                r3d._draw_box(sx, 0.0, front_z + 0.005, 0.020, 0.014, 0.003, (0.15, 0.16, 0.19))
                r3d._draw_box(sx, 0.0, front_z + 0.007, 0.017, 0.012, 0.004, (0.68, 0.72, 0.76))
                r3d._draw_box(sx, 0.005, front_z + 0.009, 0.015, 0.004, 0.003, latch_col)
                if has_fiber:
                    r3d._draw_box(sx - 0.003, -0.001, front_z + 0.012, 0.005, 0.006, 0.007, (0.08, 0.35, 0.85))
                    r3d._draw_box(sx + 0.003, -0.001, front_z + 0.012, 0.005, 0.006, 0.007, (0.08, 0.35, 0.85))
                    fiber_col = (0.98, 0.85, 0.05)
                    r3d._draw_box(sx - 0.003, -0.006, front_z + 0.016, 0.003, 0.008, 0.003, fiber_col)
                    r3d._draw_box(sx + 0.003, -0.006, front_z + 0.016, 0.003, 0.008, 0.003, fiber_col)
                    r3d._draw_box(sx, -0.012, front_z + 0.018, 0.008, 0.006, 0.003, fiber_col)
            r3d._draw_box(0.185, 0.0, front_z + 0.002, 0.055, dev.height - 0.014, 0.002, (0.07, 0.08, 0.10))
            for v in range(5):
                vy = -0.010 + v * 0.005
                r3d._draw_box(0.185, vy, front_z + 0.003, 0.048, 0.002, 0.001, (0.30, 0.34, 0.40))
        glEndList()
        dev_lists[dev] = dl

    frames = 120
    t0 = time.perf_counter()
    t_3d = 0.0
    t_2d = 0.0

    for _ in range(frames):
        now = time.time()
        f_dev, f_port, _ = cam.raycast(mode.devices)

        # 3D Render
        t_a = time.perf_counter()
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        cam.apply_view()

        # Optimized rack dynamic lights
        w = r3d.rack_width
        h = r3d.rack_height
        d = r3d.rack_depth
        hw, hh, hd = w / 2.0, h / 2.0, d / 2.0
        door_front_z = hd + 0.008
        lock_y = 1.05
        lock_x = hw - 0.024
        canopy_y = h - 0.075
        canopy_z = hd + 0.014
        beacon_x = 0.0
        beacon_z = hd - 0.08
        beacon_base_y = h + 0.015

        for r in r3d.racks:
            rx, rz = r["x"], r["z"]
            rack_id = r.get("id", 1)
            glPushMatrix()
            glTranslatef(rx, 0.0, rz)

            lock_pulse = 0.85 + 0.15 * math.sin(now * 3.5 + rack_id)
            name_glow = 0.90 + 0.10 * math.sin(now * 2.0 + rack_id)
            temp_glow = 0.85 + 0.15 * math.sin(now * 1.8 + rack_id)
            b_pulse = 0.82 + 0.18 * math.sin(now * 2.8 + rack_id)

            glBegin(GL_QUADS)
            # 1. Lock LED
            glColor3f(0.0, 0.95 * lock_pulse, 0.75 * lock_pulse)
            lx, ly, lz, lw, lh = lock_x, lock_y + 0.095, door_front_z + 0.016, 0.014, 0.006
            glVertex3f(lx - lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly + lh/2, lz); glVertex3f(lx - lw/2, ly + lh/2, lz)

            # 2. Lettering glow
            glColor3f(0.35 * name_glow, 0.88 * name_glow, 1.0 * name_glow)
            lx, ly, lz, lw, lh = -0.06, canopy_y, canopy_z + 0.013, 0.21, 0.038
            glVertex3f(lx - lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly + lh/2, lz); glVertex3f(lx - lw/2, ly + lh/2, lz)

            # 3. Temp & RH
            glColor3f(0.1, 0.98 * temp_glow, 0.35 * temp_glow)
            for seg_i in range(4):
                sx = 0.105 + seg_i * 0.026
                lx, ly, lz, lw, lh = sx, canopy_y + 0.008, canopy_z + 0.014, 0.018, 0.006
                glVertex3f(lx - lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly + lh/2, lz); glVertex3f(lx - lw/2, ly + lh/2, lz)
            glColor3f(0.0, 0.85 * temp_glow, 0.95 * temp_glow)
            for seg_i in range(4):
                sx = 0.105 + seg_i * 0.026
                lx, ly, lz, lw, lh = sx, canopy_y - 0.008, canopy_z + 0.014, 0.018, 0.006
                glVertex3f(lx - lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly + lh/2, lz); glVertex3f(lx - lw/2, ly + lh/2, lz)

            # 4. Beacon
            glColor3f(0.05 * b_pulse, 0.98 * b_pulse, 0.32 * b_pulse)
            bx, by, bz, bw, bh = beacon_x, beacon_base_y + 0.062, beacon_z + 0.018, 0.036, 0.030
            glVertex3f(bx - bw/2, by - bh/2, bz); glVertex3f(bx + bw/2, by - bh/2, bz); glVertex3f(bx + bw/2, by + bh/2, bz); glVertex3f(bx - bw/2, by + bh/2, bz)
            glEnd()

            glPopMatrix()

        # Render devices with display lists + batched LEDs
        for dev in mode.devices:
            glPushMatrix()
            glTranslatef(dev.pos_x, dev.pos_y, dev.pos_z)
            if dev.device_type == "laptop":
                r3d._render_laptop(dev, now)
            elif dev in dev_lists:
                glCallList(dev_lists[dev])
                # Batched dynamic LEDs
                if dev.device_type == "switch":
                    glBegin(GL_QUADS)
                    for idx, port in enumerate([p for p in dev.ports.values() if p.port_type != "CONSOLE"]):
                        px, py, pz = dev.get_port_local_pos(port.name, port.port_index)
                        led = port.get_led_state(now)
                        link_c = (0.1, 0.98, 0.2) if led == LEDState.GREEN else ((0.4, 1.0, 0.5) if led == LEDState.BLINK_GREEN else ((1.0, 0.65, 0.05) if led == LEDState.AMBER else (0.08, 0.12, 0.08)))
                        glColor3f(*link_c)
                        lx, ly, lz, lw, lh = px - 0.005, py + 0.016, pz + 0.005, 0.006, 0.006
                        glVertex3f(lx - lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly + lh/2, lz); glVertex3f(lx - lw/2, ly + lh/2, lz)
                        act_blink = (led in (LEDState.GREEN, LEDState.BLINK_GREEN)) and (int(now * 14 + idx) % 2 == 0)
                        act_c = (0.2, 0.95, 0.3) if act_blink else (0.06, 0.10, 0.06)
                        glColor3f(*act_c)
                        ax = px + 0.005
                        glVertex3f(ax - lw/2, ly - lh/2, lz); glVertex3f(ax + lw/2, ly - lh/2, lz); glVertex3f(ax + lw/2, ly + lh/2, lz); glVertex3f(ax - lw/2, ly + lh/2, lz)
                    glEnd()
                elif dev.device_type == "router":
                    glBegin(GL_QUADS)
                    for idx, port in enumerate([p for p in dev.ports.values() if p.port_type != "CONSOLE"]):
                        px, py, pz = dev.get_port_local_pos(port.name, port.port_index)
                        led = port.get_led_state(now)
                        led_c = (0.1, 0.98, 0.2) if led in (LEDState.GREEN, LEDState.BLINK_GREEN) else ((1.0, 0.65, 0.05) if led == LEDState.AMBER else (0.08, 0.12, 0.08))
                        glColor3f(*led_c)
                        lx, ly, lz, lw, lh = px, py + 0.016, pz + 0.005, 0.007, 0.007
                        glVertex3f(lx - lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly + lh/2, lz); glVertex3f(lx - lw/2, ly + lh/2, lz)
                    glEnd()
                elif dev.device_type == "server" and not "isp" in dev.hostname.lower():
                    glBegin(GL_QUADS)
                    for bay in range(8):
                        bx = -0.16 + (bay % 4) * 0.065
                        by = 0.018 if bay < 4 else -0.022
                        drive_blink = (int(now * 8 + bay * 3) % 5 == 0)
                        drive_c = (0.15, 0.98, 0.25) if drive_blink else (0.05, 0.15, 0.05)
                        glColor3f(*drive_c)
                        lx, ly, lz, lw, lh = bx + 0.022, by + 0.008, dev.depth / 2.0 + 0.008, 0.005, 0.005
                        glVertex3f(lx - lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly + lh/2, lz); glVertex3f(lx - lw/2, ly + lh/2, lz)
                    port = dev.ports.get("eth0")
                    if port:
                        px, py, pz = dev.get_port_local_pos(port.name, port.port_index)
                        led = port.get_led_state(now)
                        led_c = (0.1, 0.98, 0.2) if led in (LEDState.GREEN, LEDState.BLINK_GREEN) else (0.08, 0.12, 0.08)
                        glColor3f(*led_c)
                        lx, ly, lz, lw, lh = px, py + 0.014, pz + 0.005, 0.006, 0.006
                        glVertex3f(lx - lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly + lh/2, lz); glVertex3f(lx - lw/2, ly + lh/2, lz)
                    glEnd()
                elif dev.device_type == "firewall":
                    glBegin(GL_QUADS)
                    m_port = dev.ports.get("m0/0")
                    if m_port:
                        mx, my, mz = dev.get_port_local_pos(m_port.name, m_port.port_index)
                        led = m_port.get_led_state(now)
                        m_col = (0.1, 0.98, 0.2) if led in (LEDState.GREEN, LEDState.BLINK_GREEN) else (0.08, 0.12, 0.08)
                        glColor3f(*m_col)
                        lx, ly, lz, lw, lh = mx, my + 0.013, mz + 0.005, 0.005, 0.005
                        glVertex3f(lx - lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly + lh/2, lz); glVertex3f(lx - lw/2, ly + lh/2, lz)
                    for idx, port in enumerate([p for p in dev.ports.values() if p.port_type != "CONSOLE" and not p.name.startswith("m")]):
                        px, py, pz = dev.get_port_local_pos(port.name, port.port_index)
                        led = port.get_led_state(now)
                        link_c = (0.1, 0.98, 0.2) if led == LEDState.GREEN else ((0.4, 1.0, 0.5) if led == LEDState.BLINK_GREEN else ((1.0, 0.65, 0.05) if led == LEDState.AMBER else (0.08, 0.12, 0.08)))
                        glColor3f(*link_c)
                        lx, ly, lz, lw, lh = px - 0.005, py - 0.014, pz + 0.005, 0.005, 0.005
                        glVertex3f(lx - lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly + lh/2, lz); glVertex3f(lx - lw/2, ly + lh/2, lz)
                        act_blink = (led in (LEDState.GREEN, LEDState.BLINK_GREEN)) and (int(now * 14 + idx) % 2 == 0)
                        act_c = (0.2, 0.95, 0.3) if act_blink else (0.06, 0.10, 0.06)
                        glColor3f(*act_c)
                        ax = px + 0.005
                        glVertex3f(ax - lw/2, ly - lh/2, lz); glVertex3f(ax + lw/2, ly - lh/2, lz); glVertex3f(ax + lw/2, ly + lh/2, lz); glVertex3f(ax - lw/2, ly + lh/2, lz)
                    glEnd()
                elif dev.device_type in ("isp_gateway", "isp") or (dev.device_type == "server" and "isp" in dev.hostname.lower()):
                    front_z = dev.depth / 2.0 + 0.003
                    eth_port = dev.ports.get("eth0")
                    is_carrier_up = (eth_port and eth_port.is_link_up) or dev.is_powered
                    carrier_pulse = 0.85 + 0.15 * math.sin(now * 4.0)
                    carrier_col = (0.0, 1.0 * carrier_pulse, 0.4 * carrier_pulse) if is_carrier_up else (0.08, 0.12, 0.08)
                    sync_blink = int(now * 4) % 2 == 0
                    sync_col = (0.15, 0.85, 1.0) if sync_blink else (0.05, 0.25, 0.35)
                    alarm_col = (0.08, 0.50, 0.15) if is_carrier_up else (0.95, 0.20, 0.10)
                    glBegin(GL_QUADS)
                    glColor3f(*carrier_col)
                    lx, ly, lz, lw, lh = -0.178, 0.006, front_z + 0.005, 0.005, 0.005
                    glVertex3f(lx - lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly + lh/2, lz); glVertex3f(lx - lw/2, ly + lh/2, lz)
                    glColor3f(*sync_col)
                    lx = -0.164
                    glVertex3f(lx - lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly + lh/2, lz); glVertex3f(lx - lw/2, ly + lh/2, lz)
                    glColor3f(*alarm_col)
                    lx, ly = -0.192, -0.006
                    glVertex3f(lx - lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly + lh/2, lz); glVertex3f(lx - lw/2, ly + lh/2, lz)
                    if eth_port:
                        px, py, pz = dev.get_port_local_pos("eth0", 0)
                        led = eth_port.get_led_state(now)
                        link_col = (0.1, 0.98, 0.2) if led in (LEDState.GREEN, LEDState.BLINK_GREEN) else ((1.0, 0.65, 0.05) if led == LEDState.AMBER else (0.08, 0.12, 0.08))
                        glColor3f(*link_col)
                        lx, ly, lz, lw, lh = px - 0.006, py + 0.015, pz + 0.005, 0.005, 0.005
                        glVertex3f(lx - lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly + lh/2, lz); glVertex3f(lx - lw/2, ly + lh/2, lz)
                        act_blink = (led in (LEDState.GREEN, LEDState.BLINK_GREEN)) and (int(now * 16) % 2 == 0)
                        act_col = (0.2, 0.95, 0.3) if act_blink else (0.06, 0.10, 0.06)
                        glColor3f(*act_col)
                        lx = px + 0.006
                        glVertex3f(lx - lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly - lh/2, lz); glVertex3f(lx + lw/2, ly + lh/2, lz); glVertex3f(lx - lw/2, ly + lh/2, lz)
                    glEnd()
            glPopMatrix()

        r3d._render_cables(mode.cables)
        if f_dev:
            r3d._render_highlight(f_dev, f_port, now)
        t_b = time.perf_counter()

        # 2D Render
        r2d.clear_surface()
        hud.draw(r2d.hud_surface, win.width, win.height, f_dev, f_port, None,
                 mode.get_title(), mode.get_objective(), mode.get_checklist())

        # Zero-copy upload right before glTexSubImage2D
        buf = r2d.hud_surface.get_buffer()
        raw_data = (ctypes.c_char * buf.length).from_buffer(buf)
        glBindTexture(GL_TEXTURE_2D, r2d.texture_id)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, r2d.width, r2d.height, GL_BGRA, GL_UNSIGNED_BYTE, raw_data)
        del raw_data
        del buf

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, r2d.width, 0, r2d.height, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_TEXTURE_2D)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 1.0); glVertex2f(0.0, 0.0)
        glTexCoord2f(1.0, 1.0); glVertex2f(r2d.width, 0.0)
        glTexCoord2f(1.0, 0.0); glVertex2f(r2d.width, r2d.height)
        glTexCoord2f(0.0, 0.0); glVertex2f(0.0, r2d.height)
        glEnd()
        glDisable(GL_TEXTURE_2D)
        glEnable(GL_DEPTH_TEST)
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

        t_c = time.perf_counter()
        win.swap_buffers()

        t_3d += (t_b - t_a)
        t_2d += (t_c - t_b)

    total_time = time.perf_counter() - t0
    avg_fps = frames / total_time

    print(f"=== FULLY OPTIMIZED BENCHMARK RESULTS ({frames} frames) ===")
    print(f"Total Time: {total_time:.3f}s | Avg FPS: {avg_fps:.1f} (WAS: 63.6 FPS)")
    print(f"3D Render:  {t_3d*1000/frames:6.2f} ms/frame (WAS: 10.59 ms)")
    print(f"2D (HUD+TX):{t_2d*1000/frames:6.2f} ms/frame (WAS:  4.81 ms)")

    pygame.quit()

if __name__ == "__main__":
    benchmark()
