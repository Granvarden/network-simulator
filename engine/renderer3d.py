"""
engine/renderer3d.py - High-Fidelity 3D Datacenter Room, Server Racks, Network Appliances, and Cables
Implements modern OpenGL 3D rendering with realistic hardware details, status beacons,
catenary cable physics, dual-monitor NOC workbench, and cold-aisle perforated floor tiles.
"""

import time
import math
from OpenGL.GL import *
from OpenGL.GLU import gluPerspective
from network.cable import CableType
from network.device import LEDState

class Renderer3D:
    def __init__(self, fov=65.0):
        self.fov = fov
        self.racks = [
            {"id": 1, "name": "RACK-A01", "x": -1.4, "z": -1.5},
            {"id": 2, "name": "RACK-A02", "x": 0.0,  "z": -1.5},
            {"id": 3, "name": "RACK-A03", "x": 1.4,  "z": -1.5},
        ]
        self.rack_height = 2.1  # ~42U rack height
        self.rack_width = 0.6
        self.rack_depth = 0.8
        self.ceiling_height = 3.4

    def init_gl(self, width, height):
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(self.fov, float(width) / float(max(1, height)), 0.05, 100.0)
        glMatrixMode(GL_MODELVIEW)

        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)
        glShadeModel(GL_SMOOTH)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0.88, 0.91, 0.95, 1.0)

    def render_scene(self, camera, devices, cables, focused_dev=None, focused_port=None):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        camera.apply_view()

        now = time.time()

        # 1. Render Datacenter Room (Floor, Cold-Aisle Vents, Ceiling, Walls, Cable Ladders)
        self._render_room(now)

        # 2. Render 42U Server Racks with Status Beacons, Fans & PDUs
        self._render_server_racks(now)

        # 3. Render Engineer Dual-Screen NOC Workbench
        self._render_workbench(now)

        # 4. Render High-Detail Network Devices inside Racks
        self._render_devices(devices, now)

        # 5. Render 3D Cables with Catenary Sag & Snagless Boots
        self._render_cables(cables)

        # 6. Render Aim Selection Highlight (Crosshair target)
        if focused_dev:
            self._render_highlight(focused_dev, focused_port, now)

    def _render_room(self, now):
        tile_size = 0.6
        ch = self.ceiling_height

        # 1. Raised Floor Grid (Standard Anti-Static Vinyl Floor Tiles)
        glBegin(GL_QUADS)
        for x in range(-10, 10):
            for z in range(-10, 10):
                x0, z0 = x * tile_size, z * tile_size
                x1, z1 = x0 + tile_size, z0 + tile_size

                # Check if this tile is in the Cold Aisle directly in front of the racks
                in_cold_aisle = (-2.1 <= x0 <= 1.8) and (-1.2 <= z0 <= -0.4)
                if in_cold_aisle:
                    # Perforated metal ventilation tile base
                    glColor3f(0.68, 0.72, 0.78)
                elif (x + z) % 2 == 0:
                    glColor3f(0.89, 0.91, 0.95)
                else:
                    glColor3f(0.84, 0.87, 0.91)

                glVertex3f(x0, 0.0, z0)
                glVertex3f(x1, 0.0, z0)
                glVertex3f(x1, 0.0, z1)
                glVertex3f(x0, 0.0, z1)
        glEnd()

        # 2. Perforated Ventilation Grilles in Cold Aisle (Airflow Slots with subtle blue under-glow)
        glLineWidth(1.5)
        for rx in [-1.4, 0.0, 1.4]:
            # Ventilation tile right in front of each rack
            vx0, vz0 = rx - 0.28, -0.95
            vx1, vz1 = rx + 0.28, -0.45

            # Dark plenum recess underneath
            glBegin(GL_QUADS)
            glColor4f(0.12, 0.18, 0.26, 0.9)
            glVertex3f(vx0, 0.002, vz0)
            glVertex3f(vx1, 0.002, vz0)
            glVertex3f(vx1, 0.002, vz1)
            glVertex3f(vx0, 0.002, vz1)
            glEnd()

            # Metal honeycomb / slotted air grille bars
            glColor3f(0.45, 0.50, 0.58)
            glBegin(GL_LINES)
            for s in range(7):
                sz = vz0 + (s / 6.0) * (vz1 - vz0)
                glVertex3f(vx0 + 0.02, 0.003, sz)
                glVertex3f(vx1 - 0.02, 0.003, sz)
            glEnd()

            # Subtle blue chilled-air glow from plenum
            pulse = 0.65 + 0.15 * math.sin(now * 2.0 + rx)
            glBegin(GL_QUADS)
            glColor4f(0.0, 0.65, 0.95, 0.12 * pulse)
            glVertex3f(vx0, 0.005, vz0)
            glVertex3f(vx1, 0.005, vz0)
            glVertex3f(vx1, 0.005, vz1)
            glVertex3f(vx0, 0.005, vz1)
            glEnd()

        # Floor grid line seams
        glColor4f(0.70, 0.75, 0.82, 0.7)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        for i in range(-10, 11):
            coord = i * tile_size
            glVertex3f(coord, 0.001, -6.0)
            glVertex3f(coord, 0.001, 6.0)
            glVertex3f(-6.0, 0.001, coord)
            glVertex3f(6.0, 0.001, coord)
        glEnd()

        # 3. Bright Ceiling Panels & Overhead Lights
        glBegin(GL_QUADS)
        glColor3f(0.93, 0.95, 0.98)
        glVertex3f(-6.0, ch, -6.0)
        glVertex3f(6.0, ch, -6.0)
        glVertex3f(6.0, ch, 6.0)
        glVertex3f(-6.0, ch, 6.0)

        # High-Efficiency Datacenter LED Light Fixtures (Pure bright white glow)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        for lx in [-1.5, 0.0, 1.5]:
            glVertex3f(lx - 0.22, ch - 0.02, -4.5)
            glVertex3f(lx + 0.22, ch - 0.02, -4.5)
            glVertex3f(lx + 0.22, ch - 0.02, 3.5)
            glVertex3f(lx - 0.22, ch - 0.02, 3.5)
        glEnd()

        # 4. Datacenter Walls
        glBegin(GL_QUADS)
        # Back Wall behind racks (Z = -6.0)
        glColor3f(0.86, 0.89, 0.93)
        glVertex3f(-6.0, 0.0, -6.0)
        glVertex3f(6.0, 0.0, -6.0)
        glColor3f(0.91, 0.93, 0.96)
        glVertex3f(6.0, ch, -6.0)
        glVertex3f(-6.0, ch, -6.0)

        # Enterprise Corporate Blue Feature Wall Stripe
        glColor4f(0.0, 0.45, 0.85, 0.95)
        glVertex3f(-6.0, 1.25, -5.99)
        glVertex3f(6.0, 1.25, -5.99)
        glVertex3f(6.0, 1.35, -5.99)
        glVertex3f(-6.0, 1.35, -5.99)

        # Dark Slate Baseboard
        glColor3f(0.20, 0.23, 0.28)
        glVertex3f(-6.0, 0.0, -5.99)
        glVertex3f(6.0, 0.0, -5.99)
        glVertex3f(6.0, 0.12, -5.99)
        glVertex3f(-6.0, 0.12, -5.99)

        # Left Wall (X = -6.0)
        glColor3f(0.84, 0.87, 0.91)
        glVertex3f(-6.0, 0.0, 6.0)
        glVertex3f(-6.0, 0.0, -6.0)
        glVertex3f(-6.0, ch, -6.0)
        glVertex3f(-6.0, ch, 6.0)

        # Right Wall (X = 6.0)
        glColor3f(0.84, 0.87, 0.91)
        glVertex3f(6.0, 0.0, -6.0)
        glVertex3f(6.0, 0.0, 6.0)
        glVertex3f(6.0, ch, 6.0)
        glVertex3f(6.0, ch, -6.0)
        glEnd()

        # 5. Wall Fixtures: EPO (Emergency Power Off) Button & Keycard Reader
        # EPO Button at X = -5.98, Y = 1.4, Z = -2.0
        self._draw_box(-5.98, 1.4, -2.0, 0.02, 0.16, 0.14, (0.9, 0.75, 0.1))  # Yellow housing
        self._draw_box(-5.96, 1.4, -2.0, 0.03, 0.08, 0.08, (0.85, 0.15, 0.15))  # Red button

        # RFID Security Keycard Reader at X = -5.98, Y = 1.35, Z = 1.5
        self._draw_box(-5.98, 1.35, 1.5, 0.02, 0.18, 0.12, (0.15, 0.16, 0.18))
        rfid_blink = int(now * 2) % 2 == 0
        rfid_color = (0.1, 0.95, 0.2) if rfid_blink else (0.05, 0.3, 0.1)
        self._draw_box(-5.96, 1.40, 1.5, 0.02, 0.015, 0.04, rfid_color)  # RFID status LED

        # 6. Overhead Cable Ladder Trays & Multi-Strand Cable Bundles
        glColor3f(0.75, 0.62, 0.12)  # High-visibility Safety Yellow Trays
        glLineWidth(2.0)
        glBegin(GL_LINES)
        for tx in [-1.4, 0.0, 1.4]:
            glVertex3f(tx - 0.28, 2.55, -4.5)
            glVertex3f(tx - 0.28, 2.55, 2.0)
            glVertex3f(tx + 0.28, 2.55, -4.5)
            glVertex3f(tx + 0.28, 2.55, 2.0)
            # Rungs
            for rz in range(-4, 3):
                glVertex3f(tx - 0.28, 2.55, float(rz))
                glVertex3f(tx + 0.28, 2.55, float(rz))
        # Cross bridge connecting the three tray rows
        for bx in [-1.4, 1.4]:
            glVertex3f(-1.4, 2.55, -1.5)
            glVertex3f(1.4, 2.55, -1.5)
        glEnd()

        # Render Cable Bundles resting inside the overhead trays
        glLineWidth(3.0)
        glBegin(GL_LINES)
        for tx in [-1.4, 0.0, 1.4]:
            # Yellow Fiber Bundle
            glColor3f(0.95, 0.85, 0.1)
            glVertex3f(tx - 0.12, 2.57, -4.5)
            glVertex3f(tx - 0.12, 2.57, 1.8)
            # Blue Cat6 Bundle
            glColor3f(0.0, 0.45, 0.95)
            glVertex3f(tx - 0.04, 2.57, -4.5)
            glVertex3f(tx - 0.04, 2.57, 1.8)
            # Aqua 10GbE Fiber Bundle
            glColor3f(0.1, 0.85, 0.85)
            glVertex3f(tx + 0.04, 2.57, -4.5)
            glVertex3f(tx + 0.04, 2.57, 1.8)
            # Orange Multimode Bundle
            glColor3f(0.95, 0.45, 0.05)
            glVertex3f(tx + 0.12, 2.57, -4.5)
            glVertex3f(tx + 0.12, 2.57, 1.8)

            # Drop bundle going into the top of each rack
            glColor3f(0.0, 0.45, 0.95)
            glVertex3f(tx, 2.57, -1.5)
            glVertex3f(tx, 2.12, -1.5)
        glEnd()

    def _render_server_racks(self, now):
        w = self.rack_width
        h = self.rack_height
        d = self.rack_depth

        for r in self.racks:
            rx, rz = r["x"], r["z"]
            glPushMatrix()
            glTranslatef(rx, 0.0, rz)

            # Rack Frame Posts (4 uprights)
            post_thickness = 0.038
            corners = [
                (-w/2, -d/2), (w/2 - post_thickness, -d/2),
                (-w/2, d/2 - post_thickness), (w/2 - post_thickness, d/2 - post_thickness)
            ]
            for cx, cz in corners:
                self._draw_box(cx + post_thickness/2, h/2, cz + post_thickness/2, post_thickness, h, post_thickness, (0.09, 0.10, 0.13))

            # Top and Bottom Steel Plates
            self._draw_box(0.0, 0.025, 0.0, w, 0.05, d, (0.08, 0.09, 0.11))
            self._draw_box(0.0, h - 0.025, 0.0, w, 0.05, d, (0.08, 0.09, 0.11))

            # Roof Exhaust Fans (2 circular fan cutouts on top of each rack)
            for fx in [-0.15, 0.15]:
                self._draw_box(fx, h - 0.005, 0.0, 0.18, 0.008, 0.18, (0.16, 0.18, 0.22))
                # Fan center spinner
                self._draw_box(fx, h + 0.002, 0.0, 0.05, 0.006, 0.05, (0.28, 0.32, 0.38))

            # Status Beacon Tower on Rack Roof
            # Sleek modern cylindrical beacon (Green for nominal status, subtle gentle pulse)
            beacon_pulse = 0.85 + 0.15 * math.sin(now * 3.0 + r["id"])
            beacon_color = (0.1 * beacon_pulse, 0.98 * beacon_pulse, 0.3 * beacon_pulse)
            self._draw_box(0.0, h + 0.03, d/2 - 0.08, 0.04, 0.06, 0.04, (0.12, 0.14, 0.18))  # Beacon base
            self._draw_box(0.0, h + 0.08, d/2 - 0.08, 0.035, 0.05, 0.035, beacon_color)     # Beacon illuminated dome

            # Side Sheet Metal Panels with Perforated Ventilation Grille Slots
            self._draw_box(-w/2 + 0.005, h/2, 0.0, 0.01, h - 0.1, d - 0.04, (0.11, 0.12, 0.15))
            self._draw_box(w/2 - 0.005, h/2, 0.0, 0.01, h - 0.1, d - 0.04, (0.11, 0.12, 0.15))

            # Top Rack Name Label Banner
            self._draw_box(0.0, h - 0.08, d/2 + 0.003, 0.38, 0.08, 0.005, (0.05, 0.28, 0.52))

            # Vertical Mounting Rails (19-inch standard front rails)
            glLineWidth(1.0)
            glColor3f(0.32, 0.38, 0.46)
            glBegin(GL_LINES)
            for u in range(1, 43):
                uy = 0.14 + (u / 42.0) * 1.85
                glVertex3f(-w/2 + 0.06, uy, d/2 - 0.06)
                glVertex3f(-w/2 + 0.09, uy, d/2 - 0.06)
                glVertex3f(w/2 - 0.09, uy, d/2 - 0.06)
                glVertex3f(w/2 - 0.06, uy, d/2 - 0.06)
            glEnd()

            # Rack Unit (U) Number Markers at 10U, 20U, 30U, 40U
            for mark_u in [10, 20, 30, 40]:
                my = 0.14 + (mark_u / 42.0) * 1.85
                self._draw_box(-w/2 + 0.05, my, d/2 - 0.058, 0.015, 0.012, 0.002, (0.9, 0.95, 1.0))
                self._draw_box(w/2 - 0.05, my, d/2 - 0.058, 0.015, 0.012, 0.002, (0.9, 0.95, 1.0))

            # Vertical PDU (Power Distribution Unit) strip inside rear of rack
            self._draw_box(-w/2 + 0.08, h/2, -d/2 + 0.06, 0.04, h - 0.2, 0.03, (0.08, 0.08, 0.10))
            # PDU Outlet LEDs (green powered indicator dots)
            for p_idx in range(8):
                py = 0.25 + (p_idx / 7.0) * (h - 0.5)
                self._draw_box(-w/2 + 0.105, py, -d/2 + 0.06, 0.008, 0.008, 0.008, (0.1, 0.95, 0.2))

            glPopMatrix()

    def _render_workbench(self, now):
        # Engineer console desk at X = -3.2, Z = 0.5 (Width = 1.4, Depth = 0.75, Height = 0.75)
        glPushMatrix()
        glTranslatef(-3.2, 0.0, 0.5)

        # Desk Top & Legs (Modern executive white / slate desk)
        self._draw_box(0.0, 0.75, 0.0, 1.4, 0.04, 0.75, (0.92, 0.94, 0.97))
        # Front beveled edge trim
        self._draw_box(0.0, 0.75, 0.373, 1.4, 0.038, 0.005, (0.20, 0.24, 0.28))
        for lx in [-0.64, 0.64]:
            for lz in [-0.32, 0.32]:
                self._draw_box(lx, 0.375, lz, 0.04, 0.75, 0.04, (0.22, 0.25, 0.30))

        # Dual Desk Mats under both laptops
        # Left Mat (Under Windows 11 Laptop at X = -0.35)
        self._draw_box(-0.35, 0.771, 0.02, 0.44, 0.002, 0.32, (0.13, 0.15, 0.18))
        self._draw_box(-0.35, 0.772, 0.02, 0.43, 0.001, 0.31, (0.16, 0.35, 0.65))
        self._draw_box(-0.35, 0.7725, 0.02, 0.41, 0.001, 0.29, (0.15, 0.17, 0.21))

        # Right Mat (Under Ubuntu 22.04 Laptop at X = +0.35)
        self._draw_box(0.35, 0.771, 0.02, 0.44, 0.002, 0.32, (0.13, 0.15, 0.18))
        self._draw_box(0.35, 0.772, 0.02, 0.43, 0.001, 0.31, (0.65, 0.30, 0.10))
        self._draw_box(0.35, 0.7725, 0.02, 0.41, 0.001, 0.29, (0.15, 0.17, 0.21))

        # Center Secondary NOC Monitor
        # Heavy weighted stand base
        self._draw_box(0.0, 0.776, -0.15, 0.16, 0.012, 0.14, (0.16, 0.18, 0.22))
        # Articulated monitor pole
        self._draw_box(0.0, 0.92, -0.15, 0.035, 0.26, 0.035, (0.22, 0.25, 0.30))
        # 27-inch Display Frame
        self._draw_box(0.0, 1.06, -0.15, 0.48, 0.28, 0.015, (0.12, 0.13, 0.16))
        # Glowing Screen Face
        self._draw_box(0.0, 1.06, -0.141, 0.45, 0.25, 0.002, (0.05, 0.12, 0.22))

        # Animated live NOC network telemetry waveforms
        glLineWidth(2.0)
        glColor3f(0.1, 0.85, 0.95)
        glBegin(GL_LINE_STRIP)
        for i in range(15):
            gx = -0.19 + (i / 14.0) * 0.38
            gy = 1.06 - 0.04 + (0.035 * math.sin(now * 4.5 + i * 0.8))
            glVertex3f(gx, gy, -0.138)
        glEnd()

        glColor3f(0.95, 0.65, 0.15)
        glBegin(GL_LINE_STRIP)
        for i in range(15):
            gx = -0.19 + (i / 14.0) * 0.38
            gy = 1.06 + 0.04 + (0.02 * math.cos(now * 3.0 + i * 1.2))
            glVertex3f(gx, gy, -0.138)
        glEnd()

        # Desk Accessories: Datacenter Blueprint Clipboard
        self._draw_box(-0.02, 0.775, 0.22, 0.22, 0.008, 0.16, (0.45, 0.35, 0.20))
        self._draw_box(-0.02, 0.780, 0.22, 0.20, 0.002, 0.14, (0.95, 0.95, 0.95))
        self._draw_box(0.10, 0.781, 0.22, 0.01, 0.006, 0.12, (0.1, 0.45, 0.9))

        # Engineer Coffee Mug with Coffee
        self._draw_box(0.60, 0.80, 0.22, 0.08, 0.09, 0.08, (0.0, 0.45, 0.85))
        self._draw_box(0.645, 0.80, 0.22, 0.015, 0.06, 0.03, (0.0, 0.35, 0.75))
        self._draw_box(0.60, 0.835, 0.22, 0.065, 0.005, 0.065, (0.22, 0.14, 0.08))

        glPopMatrix()

    def _render_devices(self, devices, current_time):
        for dev in devices:
            glPushMatrix()
            glTranslatef(dev.pos_x, dev.pos_y, dev.pos_z)

            # Dedicated Renderers per Device Type
            if dev.device_type == "laptop":
                self._render_laptop(dev, current_time)
            else:
                # Metal Enclosure Body (Common to 19-inch rack appliances)
                body_color = (0.16, 0.18, 0.22)
                self._draw_box(0.0, 0.0, 0.0, dev.width, dev.height, dev.depth, body_color)

                if dev.device_type == "switch":
                    self._render_switch(dev, current_time)
                elif dev.device_type == "router":
                    self._render_router(dev, current_time)
                elif dev.device_type == "server":
                    self._render_server(dev, current_time)
                elif dev.device_type == "firewall":
                    self._render_firewall(dev, current_time)
                else:
                    self._render_generic_device(dev, current_time)

            glPopMatrix()

    def _render_laptop(self, dev, now):
        """High-detail procedural 3D Laptop for Windows 11 and Ubuntu 22.04 LTS."""
        is_windows = getattr(dev, "os_type", "windows").lower() == "windows"

        # 1. Base Chassis Body (0.36m width x 0.26m depth x 0.016m height)
        base_color = (0.78, 0.80, 0.84) if is_windows else (0.11, 0.12, 0.14)
        self._draw_box(0.0, 0.008, 0.0, 0.36, 0.016, 0.26, base_color)

        # 2. Keyboard Well & Keycaps
        well_color = (0.20, 0.22, 0.25) if is_windows else (0.08, 0.08, 0.09)
        self._draw_box(0.0, 0.016, -0.02, 0.28, 0.002, 0.12, well_color)

        key_color = (0.28, 0.30, 0.34) if is_windows else (0.16, 0.17, 0.19)
        for row in range(4):
            kz = -0.06 + row * 0.026
            self._draw_box(0.0, 0.0175, kz, 0.27, 0.002, 0.022, key_color)

        # 3. Trackpad & Badges
        if is_windows:
            # Silver Glass Trackpad
            self._draw_box(0.0, 0.0165, 0.075, 0.11, 0.002, 0.07, (0.68, 0.70, 0.74))
            # Windows 11 Cyan Logo Badge
            self._draw_box(0.10, 0.0165, 0.075, 0.018, 0.001, 0.014, (0.0, 0.47, 0.84))
            # Intel / Core Badge
            self._draw_box(0.125, 0.0165, 0.075, 0.012, 0.001, 0.014, (0.15, 0.55, 0.95))
        else:
            # Iconic ThinkPad Red TrackPoint Nub in center of keyboard
            self._draw_box(0.0, 0.019, -0.02, 0.012, 0.005, 0.012, (0.88, 0.12, 0.12))
            # Matte Black Trackpad with physical click buttons
            self._draw_box(0.0, 0.0165, 0.08, 0.10, 0.002, 0.06, (0.14, 0.15, 0.17))
            self._draw_box(0.0, 0.017, 0.048, 0.09, 0.001, 0.012, (0.20, 0.22, 0.25))
            self._draw_box(0.0, 0.0172, 0.048, 0.08, 0.001, 0.003, (0.85, 0.20, 0.15))
            # Ubuntu Orange Badge
            self._draw_box(0.10, 0.0165, 0.075, 0.016, 0.001, 0.016, (0.90, 0.35, 0.10))

        # 4. Tilted Laptop Screen Lid (~22 degrees tilt back)
        glPushMatrix()
        glTranslatef(0.0, 0.016, -0.12)
        glRotatef(22.0, 1.0, 0.0, 0.0)

        # Screen Lid Outer Shell
        lid_color = (0.74, 0.76, 0.80) if is_windows else (0.10, 0.11, 0.13)
        self._draw_box(0.0, 0.12, 0.0, 0.36, 0.24, 0.010, lid_color)

        # Front Display Bezel
        self._draw_box(0.0, 0.12, 0.005, 0.35, 0.23, 0.002, (0.08, 0.09, 0.11))

        # Webcam & Status LED
        self._draw_box(0.0, 0.23, 0.006, 0.008, 0.008, 0.001, (0.02, 0.02, 0.02))
        self._draw_box(0.012, 0.23, 0.006, 0.003, 0.003, 0.001, (0.1, 0.95, 0.3))

        # Glowing IPS Display Face
        if is_windows:
            # Windows 11 Bloom Blue Wallpaper
            self._draw_box(0.0, 0.12, 0.0065, 0.32, 0.20, 0.001, (0.08, 0.32, 0.68))
            self._draw_box(0.0, 0.13, 0.007, 0.12, 0.10, 0.001, (0.25, 0.65, 0.95))
            self._draw_box(0.0, 0.13, 0.0075, 0.06, 0.05, 0.001, (0.65, 0.85, 1.0))
            # Centered Taskbar
            self._draw_box(0.0, 0.028, 0.0075, 0.32, 0.016, 0.001, (0.06, 0.12, 0.22))
            for ic_idx, ic_col in enumerate([(0.0, 0.5, 0.95), (0.1, 0.6, 0.9), (0.2, 0.45, 0.85), (0.1, 0.1, 0.1), (0.4, 0.4, 0.4)]):
                self._draw_box(-0.03 + ic_idx * 0.015, 0.028, 0.008, 0.008, 0.008, 0.001, ic_col)
        else:
            # Ubuntu 22.04 LTS Jammy Aubergine & Orange Wallpaper
            self._draw_box(0.0, 0.12, 0.0065, 0.32, 0.20, 0.001, (0.28, 0.08, 0.24))
            self._draw_box(0.05, 0.12, 0.007, 0.15, 0.12, 0.001, (0.65, 0.24, 0.12))
            self._draw_box(0.07, 0.12, 0.0075, 0.08, 0.06, 0.001, (0.85, 0.38, 0.10))
            # GNOME Top Bar
            self._draw_box(0.0, 0.212, 0.0075, 0.32, 0.014, 0.001, (0.07, 0.07, 0.08))
            # Left Vertical Dock
            self._draw_box(-0.148, 0.12, 0.0075, 0.024, 0.198, 0.001, (0.09, 0.09, 0.10))
            for ic_idx, ic_col in enumerate([(0.91, 0.33, 0.13), (0.0, 0.45, 0.9), (0.1, 0.1, 0.1), (0.35, 0.35, 0.35)]):
                self._draw_box(-0.148, 0.18 - ic_idx * 0.028, 0.008, 0.014, 0.014, 0.001, ic_col)

        glPopMatrix()

        # 5. Physical Network & Console Ports on Chassis Flanks
        # Left Flank: eth0 (Cat6 RJ45 Gigabit Ethernet)
        eth_port = dev.ports.get("eth0")
        if eth_port:
            px, py, pz = dev.get_port_local_pos("eth0", 0)
            # Metallic Shielding
            self._draw_box(px, py, pz, 0.004, 0.012, 0.018, (0.50, 0.52, 0.55))
            # Socket cavity
            self._draw_box(px - 0.001, py, pz, 0.003, 0.009, 0.014, (0.04, 0.04, 0.05))
            # Link LED
            led = eth_port.get_led_state(now)
            led_c = (0.1, 0.98, 0.2) if led in (LEDState.GREEN, LEDState.BLINK_GREEN) else (0.08, 0.12, 0.08)
            self._draw_box(px, py + 0.005, pz + 0.007, 0.003, 0.003, 0.003, led_c)

        # Right Flank: con0 (Serial Console Rollover Port)
        con_port = dev.ports.get("con0")
        if con_port:
            cx, cy, cz = dev.get_port_local_pos("con0", 0)
            # Baby Blue Console Shield
            self._draw_box(cx, cy, cz, 0.004, 0.010, 0.016, (0.2, 0.65, 0.95))
            # Socket cavity
            self._draw_box(cx + 0.001, cy, cz, 0.003, 0.007, 0.012, (0.04, 0.04, 0.05))
            # Connection Status LED
            con_connected = con_port.cable is not None
            con_led = (0.1, 0.95, 0.2) if con_connected else (0.1, 0.2, 0.1)
            self._draw_box(cx, cy + 0.004, cz + 0.006, 0.003, 0.003, 0.003, con_led)

    def _render_switch(self, dev, now):
        """High-detail Cisco Catalyst 1U Switch."""
        hw = dev.width / 2.0
        hh = dev.height / 2.0
        front_z = dev.depth / 2.0 + 0.003

        # 1. Front Faceplate (Cisco Catalyst Metallic Teal-Blue)
        self._draw_box(0.0, 0.0, front_z, dev.width, dev.height, 0.006, (0.14, 0.32, 0.42))

        # 2. Cisco Cyan Accent Stripe across top of faceplate
        self._draw_box(0.0, hh - 0.004, front_z + 0.001, dev.width - 0.04, 0.005, 0.002, (0.0, 0.75, 0.92))

        # 3. Left Corner: System Status LED Cluster (SYST, RPS, STAT, SPEED)
        led_names = [(-0.20, "SYST"), (-0.185, "RPS"), (-0.170, "STAT"), (-0.155, "SPEED")]
        for lx, _ in led_names:
            self._draw_box(lx, hh - 0.015, front_z + 0.002, 0.005, 0.005, 0.002, (0.1, 0.98, 0.2))

        # 4. Baby Blue RJ45 Console Port on the left
        con_port = dev.ports.get("con0")
        if con_port:
            cx, cy, cz = dev.get_port_local_pos(con_port.name, con_port.port_index)
            self._draw_box(cx, cy, cz, 0.024, 0.018, 0.003, (0.2, 0.65, 0.95))
            self._draw_box(cx, cy, cz + 0.002, 0.018, 0.014, 0.002, (0.05, 0.08, 0.12))

        # 5. Right Intake Cooling Vent Grille
        self._draw_box(0.20, 0.0, front_z + 0.001, 0.06, dev.height - 0.015, 0.002, (0.09, 0.12, 0.16))

        # 6. Metal Rack-Mount Ear Brackets & Screws on sides
        self._draw_box(-hw + 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.45, 0.48, 0.52))
        self._draw_box(hw - 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.45, 0.48, 0.52))
        # Shiny screw heads
        self._draw_box(-hw + 0.01, 0.0, front_z + 0.004, 0.008, 0.008, 0.002, (0.85, 0.88, 0.92))
        self._draw_box(hw - 0.01, 0.0, front_z + 0.004, 0.008, 0.008, 0.002, (0.85, 0.88, 0.92))

        # 7. Ports with Dual-LEDs (Link LED + Activity LED)
        port_list = [p for p in dev.ports.values() if p.port_type != "CONSOLE"]
        for idx, port in enumerate(port_list):
            px, py, pz = dev.get_port_local_pos(port.name, port.port_index)

            # Metallic Port Shield Frame
            self._draw_box(px, py, pz, 0.025, 0.020, 0.004, (0.52, 0.55, 0.58))
            # Dark Recessed Socket Interior
            self._draw_box(px, py, pz + 0.002, 0.020, 0.015, 0.003, (0.03, 0.03, 0.04))
            # Gold pin contacts inside socket
            self._draw_box(px, py + 0.003, pz + 0.003, 0.012, 0.003, 0.001, (0.85, 0.72, 0.15))

            # LED 1: Upper Link/Speed LED
            led = port.get_led_state(now)
            if led == LEDState.GREEN:
                link_c = (0.1, 0.98, 0.2)
            elif led == LEDState.BLINK_GREEN:
                link_c = (0.4, 1.0, 0.5)
            elif led == LEDState.AMBER:
                link_c = (1.0, 0.65, 0.05)
            else:
                link_c = (0.08, 0.12, 0.08)
            self._draw_box(px - 0.005, py + 0.016, pz + 0.003, 0.006, 0.006, 0.003, link_c)

            # LED 2: Lower Activity LED (Blinks with network activity)
            act_blink = (led in (LEDState.GREEN, LEDState.BLINK_GREEN)) and (int(now * 14 + idx) % 2 == 0)
            act_c = (0.2, 0.95, 0.3) if act_blink else (0.06, 0.10, 0.06)
            self._draw_box(px + 0.005, py + 0.016, pz + 0.003, 0.006, 0.006, 0.003, act_c)

    def _render_router(self, dev, now):
        """High-detail Cisco ISR 2U Router with NIM slots & SFP cages."""
        hw = dev.width / 2.0
        hh = dev.height / 2.0
        front_z = dev.depth / 2.0 + 0.003

        # 1. Front Faceplate (Cisco Slate Navy)
        self._draw_box(0.0, 0.0, front_z, dev.width, dev.height, 0.006, (0.20, 0.24, 0.34))

        # 2. Dual Modular NIM Slot Expansion Bays (Top Tier)
        for mx in [-0.08, 0.08]:
            # Slot blank / cover plate
            self._draw_box(mx, 0.022, front_z + 0.002, 0.14, 0.034, 0.003, (0.14, 0.16, 0.22))
            # Thumbscrews on expansion slot
            self._draw_box(mx - 0.06, 0.022, front_z + 0.004, 0.007, 0.007, 0.002, (0.75, 0.78, 0.82))
            self._draw_box(mx + 0.06, 0.022, front_z + 0.004, 0.007, 0.007, 0.002, (0.75, 0.78, 0.82))

        # 3. Status LED Cluster (PWR, SYS, ACT, POE) on the left
        status_leds = [(-0.18, 0.025), (-0.165, 0.025), (-0.18, 0.012), (-0.165, 0.012)]
        for sx, sy in status_leds:
            self._draw_box(sx, sy, front_z + 0.002, 0.006, 0.006, 0.002, (0.1, 0.95, 0.2))

        # 4. Cooling Fin Ventilation Slats
        self._draw_box(0.18, 0.0, front_z + 0.001, 0.08, dev.height - 0.02, 0.002, (0.12, 0.14, 0.18))

        # 5. Heavy-Duty Rack Mount Ears with 4 screws
        self._draw_box(-hw + 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.42, 0.45, 0.50))
        self._draw_box(hw - 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.42, 0.45, 0.50))
        for sy in [-0.025, 0.025]:
            self._draw_box(-hw + 0.01, sy, front_z + 0.004, 0.007, 0.007, 0.002, (0.85, 0.88, 0.92))
            self._draw_box(hw - 0.01, sy, front_z + 0.004, 0.007, 0.007, 0.002, (0.85, 0.88, 0.92))

        # 6. Console Port
        con_port = dev.ports.get("con0")
        if con_port:
            cx, cy, cz = dev.get_port_local_pos(con_port.name, con_port.port_index)
            self._draw_box(cx, cy, cz, 0.024, 0.018, 0.003, (0.2, 0.65, 0.95))
            self._draw_box(cx, cy, cz + 0.002, 0.018, 0.014, 0.002, (0.05, 0.08, 0.12))

        # 7. Gigabit Ports & SFP Fiber Cages on bottom tier
        port_list = [p for p in dev.ports.values() if p.port_type != "CONSOLE"]
        for idx, port in enumerate(port_list):
            px, py, pz = dev.get_port_local_pos(port.name, port.port_index)

            # Port frame & socket
            self._draw_box(px, py, pz, 0.026, 0.022, 0.004, (0.50, 0.53, 0.56))
            self._draw_box(px, py, pz + 0.002, 0.020, 0.016, 0.003, (0.04, 0.04, 0.05))

            # Status LED
            led = port.get_led_state(now)
            led_c = (0.1, 0.98, 0.2) if led in (LEDState.GREEN, LEDState.BLINK_GREEN) else ((1.0, 0.65, 0.05) if led == LEDState.AMBER else (0.08, 0.12, 0.08))
            self._draw_box(px, py + 0.016, pz + 0.003, 0.007, 0.007, 0.003, led_c)

    def _render_server(self, dev, now):
        """High-detail Enterprise 2U Server with 8 Hot-Swap Drive Bays & Status LCD."""
        hw = dev.width / 2.0
        hh = dev.height / 2.0
        front_z = dev.depth / 2.0 + 0.003

        # 1. Front Faceplate (Brushed Metal & Charcoal)
        self._draw_box(0.0, 0.0, front_z, dev.width, dev.height, 0.006, (0.24, 0.26, 0.29))

        # 2. Hot-Swap 2.5" / 3.5" Drive Bay Caddies (8 Drive Trays)
        for bay in range(8):
            bx = -0.16 + (bay % 4) * 0.065
            by = 0.018 if bay < 4 else -0.022

            # Drive caddy bezel
            self._draw_box(bx, by, front_z + 0.002, 0.058, 0.032, 0.004, (0.15, 0.16, 0.19))
            # Drive release latch lever
            self._draw_box(bx - 0.018, by, front_z + 0.004, 0.012, 0.024, 0.002, (0.35, 0.38, 0.42))

            # Drive Activity LED (subtle green flicker simulating disk read/write)
            drive_blink = (int(now * 8 + bay * 3) % 5 == 0)
            drive_c = (0.15, 0.98, 0.25) if drive_blink else (0.05, 0.15, 0.05)
            self._draw_box(bx + 0.022, by + 0.008, front_z + 0.005, 0.005, 0.005, 0.002, drive_c)

        # 3. Pull-Out Asset Tag (Blue enterprise ID tag) on top right
        self._draw_box(0.14, 0.024, front_z + 0.004, 0.045, 0.014, 0.003, (0.0, 0.45, 0.85))

        # 4. Diagnostic Amber/Blue LCD Status Display
        self._draw_box(0.14, -0.002, front_z + 0.003, 0.060, 0.022, 0.002, (0.05, 0.22, 0.35))

        # 5. Round Illuminated Power Button
        self._draw_box(0.19, 0.024, front_z + 0.004, 0.016, 0.016, 0.003, (0.1, 0.95, 0.3))

        # 6. Silver Quick-Release Rack-Mount Ears
        self._draw_box(-hw + 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.50, 0.54, 0.58))
        self._draw_box(hw - 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.50, 0.54, 0.58))

        # 7. Management / Host Network Port eth0
        port = dev.ports.get("eth0")
        if port:
            px, py, pz = dev.get_port_local_pos(port.name, port.port_index)
            self._draw_box(px, py, pz, 0.026, 0.020, 0.004, (0.45, 0.48, 0.52))
            self._draw_box(px, py, pz + 0.002, 0.020, 0.015, 0.003, (0.04, 0.04, 0.05))

            led = port.get_led_state(now)
            led_c = (0.1, 0.98, 0.2) if led in (LEDState.GREEN, LEDState.BLINK_GREEN) else (0.08, 0.12, 0.08)
            self._draw_box(px, py + 0.014, pz + 0.003, 0.006, 0.006, 0.002, led_c)

    def _render_firewall(self, dev, now):
        """High-detail Cisco ASA 5500 Series 1U Enterprise Firewall."""
        hw = dev.width / 2.0
        hh = dev.height / 2.0
        front_z = dev.depth / 2.0 + 0.003

        # 1. Front Faceplate (Cisco ASA Crimson Red Metallic Bezel)
        self._draw_box(0.0, 0.0, front_z, dev.width, dev.height, 0.006, (0.58, 0.12, 0.16))

        # 2. Central Dark Obsidian Recessed Tray
        self._draw_box(0.02, 0.0, front_z + 0.001, dev.width - 0.12, dev.height - 0.010, 0.003, (0.12, 0.13, 0.16))

        # 3. Cisco ASA Metallic Logo / Crimson Model Badge on upper left
        self._draw_box(-0.16, hh - 0.008, front_z + 0.003, 0.07, 0.010, 0.002, (0.82, 0.14, 0.18))

        # 4. Security Status LED Cluster (PWR, STATUS, ACTIVE, VPN) on the left
        sec_leds = [
            (-0.19, 0.008, (0.1, 0.98, 0.2)),    # PWR
            (-0.178, 0.008, (0.1, 0.98, 0.2)),   # STATUS
            (-0.19, -0.008, (0.1, 0.90, 0.85)),  # ACTIVE
            (-0.178, -0.008, (0.15, 0.82, 0.98)) # VPN
        ]
        for lx, ly, col in sec_leds:
            self._draw_box(lx, ly, front_z + 0.003, 0.005, 0.005, 0.002, col)

        # 5. Console Port (Baby Blue) & Management Port (Charcoal)
        con_port = dev.ports.get("con0")
        if con_port:
            cx, cy, cz = dev.get_port_local_pos(con_port.name, con_port.port_index)
            self._draw_box(cx, cy, cz, 0.022, 0.017, 0.003, (0.2, 0.65, 0.95))
            self._draw_box(cx, cy, cz + 0.002, 0.017, 0.013, 0.002, (0.05, 0.08, 0.12))

        m_port = dev.ports.get("m0/0")
        if m_port:
            mx, my, mz = dev.get_port_local_pos(m_port.name, m_port.port_index)
            self._draw_box(mx, my, mz, 0.022, 0.017, 0.003, (0.42, 0.45, 0.48))
            self._draw_box(mx, my, mz + 0.002, 0.017, 0.013, 0.002, (0.05, 0.08, 0.12))
            led = m_port.get_led_state(now)
            m_col = (0.1, 0.98, 0.2) if led in (LEDState.GREEN, LEDState.BLINK_GREEN) else (0.08, 0.12, 0.08)
            self._draw_box(mx, my + 0.013, mz + 0.003, 0.005, 0.005, 0.002, m_col)

        # 6. Right Side Diamond Intake Cooling Vent Grille
        self._draw_box(0.20, 0.0, front_z + 0.002, 0.05, dev.height - 0.016, 0.002, (0.08, 0.09, 0.11))

        # 7. Heavy-Duty Metal Rack Mount Ears & Screws
        self._draw_box(-hw + 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.45, 0.48, 0.52))
        self._draw_box(hw - 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.45, 0.48, 0.52))
        self._draw_box(-hw + 0.01, 0.0, front_z + 0.004, 0.008, 0.008, 0.002, (0.85, 0.88, 0.92))
        self._draw_box(hw - 0.01, 0.0, front_z + 0.004, 0.008, 0.008, 0.002, (0.85, 0.88, 0.92))

        # 8. Data Ports (g0/0 to g0/5) with Shielding, Pins and Dual Status LEDs
        data_ports = [p for p in dev.ports.values() if p.port_type != "CONSOLE" and not p.name.startswith("m")]
        for idx, port in enumerate(data_ports):
            px, py, pz = dev.get_port_local_pos(port.name, port.port_index)

            # Metallic Shielding
            self._draw_box(px, py, pz, 0.025, 0.020, 0.004, (0.52, 0.55, 0.58))
            # Socket Cavity
            self._draw_box(px, py, pz + 0.002, 0.020, 0.015, 0.003, (0.03, 0.03, 0.04))
            # Gold Pins
            self._draw_box(px, py + 0.003, pz + 0.003, 0.012, 0.003, 0.001, (0.85, 0.72, 0.15))

            # Zone color accent indicator bar above port (Outside = red, Inside = green, DMZ = orange)
            zone = getattr(dev, "nameif", {}).get(port.name, "")
            if zone == "outside":
                z_col = (0.85, 0.18, 0.18)
            elif zone == "inside":
                z_col = (0.15, 0.75, 0.25)
            elif zone == "dmz":
                z_col = (0.95, 0.55, 0.10)
            else:
                z_col = (0.35, 0.40, 0.48)
            self._draw_box(px, py + 0.014, pz + 0.002, 0.022, 0.003, 0.002, z_col)

            # Dual LEDs
            led = port.get_led_state(now)
            link_c = (0.1, 0.98, 0.2) if led == LEDState.GREEN else ((0.4, 1.0, 0.5) if led == LEDState.BLINK_GREEN else ((1.0, 0.65, 0.05) if led == LEDState.AMBER else (0.08, 0.12, 0.08)))
            self._draw_box(px - 0.005, py - 0.014, pz + 0.003, 0.005, 0.005, 0.002, link_c)

            act_blink = (led in (LEDState.GREEN, LEDState.BLINK_GREEN)) and (int(now * 14 + idx) % 2 == 0)
            act_c = (0.2, 0.95, 0.3) if act_blink else (0.06, 0.10, 0.06)
            self._draw_box(px + 0.005, py - 0.014, pz + 0.003, 0.005, 0.005, 0.002, act_c)

    def _render_generic_device(self, dev, now):
        """Fallback renderer for other appliances e.g. Laptop."""
        front_z = dev.depth / 2.0 + 0.002
        self._draw_box(0.0, 0.0, front_z, dev.width, dev.height, 0.005, (0.22, 0.25, 0.30))

        for port in dev.ports.values():
            px, py, pz = dev.get_port_local_pos(port.name, port.port_index)
            self._draw_box(px, py, pz, 0.022, 0.016, 0.004, (0.40, 0.44, 0.48))
            self._draw_box(px, py, pz + 0.002, 0.016, 0.012, 0.002, (0.05, 0.08, 0.12))

    def _render_cables(self, cables):
        """Renders 3D cables with catenary gravity sag and snagless rubber boots."""
        glDisable(GL_LIGHTING)

        for cable in cables:
            pts = cable.compute_curve_points(num_segments=22)
            if len(pts) < 2:
                continue

            r, g, b = cable.color
            if cable.is_damaged:
                r, g, b = 0.90, 0.12, 0.12  # Vivid red for damaged / disconnected

            # 1. Smooth Cable Ribbon / Tube
            glColor3f(r, g, b)
            glLineWidth(4.0)
            glBegin(GL_LINE_STRIP)
            for p in pts:
                glVertex3f(p[0], p[1], p[2])
            glEnd()

            # 2. Snagless Molded Rubber Strain-Relief Boot & RJ45 Clip at both ends
            for port in (cable.port_a, cable.port_b):
                if not port:
                    continue
                pp = port.get_world_pos()

                # Snagless rubber boot (matches cable color)
                boot_c = (r * 0.85, g * 0.85, b * 0.85)
                self._draw_box(pp[0], pp[1], pp[2] + 0.014, 0.018, 0.016, 0.024, boot_c)

                # Clear / frosted plastic latch clip on top of connector
                self._draw_box(pp[0], pp[1] + 0.010, pp[2] + 0.016, 0.008, 0.006, 0.018, (0.85, 0.90, 0.95))

    def _render_highlight(self, dev, port, now):
        """Draws neon cyan/golden wireframe bounding box with animated targeting brackets."""
        glDisable(GL_DEPTH_TEST)

        if port:
            # Highlight individual port with neon golden focus box
            px, py, pz = port.get_world_pos()
            pulse = 0.85 + 0.15 * math.sin(now * 6.0)
            glColor4f(1.0, 0.85 * pulse, 0.1, 0.95)
            glLineWidth(3.0)
            self._draw_wireframe_box(px, py, pz, 0.034, 0.034, 0.034)
        else:
            # Highlight whole device with neon enterprise cyan
            pulse = 0.85 + 0.15 * math.sin(now * 4.0)
            glColor4f(0.0, 0.80 * pulse, 1.0, 0.90)
            glLineWidth(2.5)
            self._draw_wireframe_box(dev.pos_x, dev.pos_y, dev.pos_z, dev.width + 0.015, dev.height + 0.015, dev.depth + 0.015)

        glEnable(GL_DEPTH_TEST)

    def _draw_box(self, x, y, z, w, h, d, color):
        glColor3f(*color)
        hw, hh, hd = w / 2.0, h / 2.0, d / 2.0

        glBegin(GL_QUADS)
        # Front
        glVertex3f(x - hw, y - hh, z + hd)
        glVertex3f(x + hw, y - hh, z + hd)
        glVertex3f(x + hw, y + hh, z + hd)
        glVertex3f(x - hw, y + hh, z + hd)
        # Back
        glVertex3f(x - hw, y - hh, z - hd)
        glVertex3f(x - hw, y + hh, z - hd)
        glVertex3f(x + hw, y + hh, z - hd)
        glVertex3f(x + hw, y - hh, z - hd)
        # Top
        glVertex3f(x - hw, y + hh, z - hd)
        glVertex3f(x - hw, y + hh, z + hd)
        glVertex3f(x + hw, y + hh, z + hd)
        glVertex3f(x + hw, y + hh, z - hd)
        # Bottom
        glVertex3f(x - hw, y - hh, z - hd)
        glVertex3f(x + hw, y - hh, z - hd)
        glVertex3f(x + hw, y - hh, z + hd)
        glVertex3f(x - hw, y - hh, z + hd)
        # Right
        glVertex3f(x + hw, y - hh, z - hd)
        glVertex3f(x + hw, y + hh, z - hd)
        glVertex3f(x + hw, y + hh, z + hd)
        glVertex3f(x + hw, y - hh, z + hd)
        # Left
        glVertex3f(x - hw, y - hh, z - hd)
        glVertex3f(x - hw, y - hh, z + hd)
        glVertex3f(x - hw, y + hh, z + hd)
        glVertex3f(x - hw, y + hh, z - hd)
        glEnd()

    def _draw_wireframe_box(self, x, y, z, w, h, d):
        hw, hh, hd = w / 2.0, h / 2.0, d / 2.0
        glBegin(GL_LINES)
        for sx in [-1, 1]:
            for sy in [-1, 1]:
                glVertex3f(x + sx*hw, y + sy*hh, z - hd)
                glVertex3f(x + sx*hw, y + sy*hh, z + hd)
        for sx in [-1, 1]:
            for sz in [-1, 1]:
                glVertex3f(x + sx*hw, y - hh, z + sz*hd)
                glVertex3f(x + sx*hw, y + hh, z + sz*hd)
        for sy in [-1, 1]:
            for sz in [-1, 1]:
                glVertex3f(x - hw, y + sy*hh, z + sz*hd)
                glVertex3f(x + hw, y + sy*hh, z + sz*hd)
        glEnd()
