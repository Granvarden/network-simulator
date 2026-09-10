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
        """
        High-Fidelity 42U Datacenter Server Racks (Enterprise Architecture).
        Features heavy-duty structural frame, front beveled door perimeter with stainless hinges,
        electronic smart-lock swing handle with RFID lens and green access status LED,
        illuminated datacenter marquee canopy with cyan glow and digital environmental telemetry pod (temp/humidity),
        folded EIA-310 square-hole vertical mounting rails with silkscreened white U graduations,
        zero-U vertical cable management channels with bundled Cat6/fiber trunk runs,
        dual redundant rear vertical 0U PDUs (Feed A & Feed B) with ammeter readouts and outlet LEDs,
        3-tier industrial status stack light (Andon tower), dual high-flow roof exhaust fan shrouds with spinner hubs,
        overhead cable drop brush glands, seismic yellow floor anchor brackets, and heavy-duty leveling feet.
        """
        w = self.rack_width   # 0.60m
        h = self.rack_height  # 2.10m
        d = self.rack_depth   # 0.80m
        hw, hh, hd = w / 2.0, h / 2.0, d / 2.0

        for r in self.racks:
            rx, rz = r["x"], r["z"]
            rack_id = r.get("id", 1)
            rack_name = r.get("name", f"RACK-A0{rack_id}")
            glPushMatrix()
            glTranslatef(rx, 0.0, rz)

            # =========================================================================
            # 1. HEAVY-DUTY BASE CHASSIS, LEVELING FEET, WHEELS & SEISMIC FLOOR ANCHORS
            # =========================================================================
            # Stamped steel bottom plinth / base plate
            self._draw_box(0.0, 0.025, 0.0, w, 0.05, d, (0.08, 0.09, 0.11))
            self._draw_box(0.0, 0.052, 0.0, w - 0.03, 0.008, d - 0.03, (0.13, 0.14, 0.17))

            # Corner Leveling Feet (Threaded zinc bolts & heavy cast foot pads at 4 corners)
            for fx in [-hw + 0.04, hw - 0.04]:
                for fz in [-hd + 0.04, hd - 0.04]:
                    # Threaded leveling bolt shaft
                    self._draw_box(fx, 0.012, fz, 0.016, 0.024, 0.016, (0.62, 0.65, 0.70))
                    # Hex adjustment nut
                    self._draw_box(fx, 0.016, fz, 0.026, 0.008, 0.026, (0.75, 0.78, 0.82))
                    # Circular cast-iron footpad
                    self._draw_box(fx, 0.004, fz, 0.045, 0.008, 0.045, (0.22, 0.24, 0.28))

            # Swivel Casters (Heavy-duty urethane wheels inside base recess)
            for cx in [-hw + 0.07, hw - 0.07]:
                for cz in [-hd + 0.07, hd - 0.07]:
                    self._draw_box(cx, 0.018, cz, 0.025, 0.026, 0.040, (0.16, 0.17, 0.20))
                    self._draw_box(cx, 0.010, cz, 0.020, 0.020, 0.032, (0.35, 0.18, 0.12))  # Urethane wheel

            # High-Visibility Yellow Seismic Tie-Down Floor Anchor Brackets (Front Left & Right)
            for sx in [-hw - 0.012, hw + 0.012]:
                self._draw_box(sx, 0.012, hd - 0.02, 0.028, 0.024, 0.065, (0.92, 0.76, 0.10))
                # High-tensile floor anchor bolts
                self._draw_box(sx, 0.025, hd - 0.02, 0.012, 0.006, 0.012, (0.85, 0.88, 0.92))

            # Chassis Earth Ground Bonding Strap (Braided Copper)
            self._draw_box(-hw + 0.02, 0.016, hd + 0.008, 0.014, 0.030, 0.004, (0.82, 0.52, 0.20))
            self._draw_box(-hw + 0.02, 0.008, hd + 0.012, 0.018, 0.006, 0.012, (0.78, 0.65, 0.22))

            # =========================================================================
            # 2. FOUR VERTICAL CORNER POSTS & REINFORCED CHASSIS FRAME
            # =========================================================================
            post_w = 0.042
            corners = [
                (-hw + post_w/2, -hd + post_w/2),
                ( hw - post_w/2, -hd + post_w/2),
                (-hw + post_w/2,  hd - post_w/2),
                ( hw - post_w/2,  hd - post_w/2)
            ]
            for cx, cz in corners:
                # Vertical corner upright column
                self._draw_box(cx, hh, cz, post_w, h - 0.06, post_w, (0.10, 0.11, 0.13))
                # Internal bevel reinforcement rib
                self._draw_box(cx, hh, cz, post_w - 0.012, h - 0.08, post_w - 0.012, (0.14, 0.15, 0.18))

            # =========================================================================
            # 3. SIDE PANELS WITH PERIMETER BEVEL & VENTILATION LOUVERS
            # =========================================================================
            for side_x, side_sign in [(-hw + 0.005, -1), (hw - 0.005, 1)]:
                # Main recessed textured side sheet metal panel
                self._draw_box(side_x, hh, 0.0, 0.010, h - 0.12, d - 0.08, (0.12, 0.13, 0.16))
                # Perimeter stiffening border
                self._draw_box(side_x, hh, 0.0, 0.014, h - 0.10, d - 0.06, (0.09, 0.10, 0.12))
                # Recessed keylock release handle on side panel
                self._draw_box(side_x + 0.002 * side_sign, hh, 0.0, 0.004, 0.045, 0.035, (0.24, 0.26, 0.30))

                # Upper & Lower Honeycomb Exhaust Louvers on side panels
                for louver_y in [0.35, h - 0.35]:
                    self._draw_box(side_x + 0.001 * side_sign, louver_y, 0.0, 0.006, 0.16, d - 0.24, (0.07, 0.08, 0.10))
                    # Louver horizontal slats
                    for ls in range(5):
                        ly = louver_y - 0.06 + ls * 0.03
                        self._draw_box(side_x + 0.003 * side_sign, ly, 0.0, 0.004, 0.005, d - 0.26, (0.20, 0.22, 0.26))

            # =========================================================================
            # 4. FRONT DOOR APERTURE FRAME, STAINLESS HINGES & SMART-LOCK SWING HANDLE
            # =========================================================================
            door_front_z = hd + 0.008
            stile_w = 0.048

            # Left Door Vertical Stile
            self._draw_box(-hw + stile_w/2, hh, door_front_z, stile_w, h - 0.06, 0.016, (0.13, 0.14, 0.17))
            # Right Door Vertical Stile
            self._draw_box(hw - stile_w/2, hh, door_front_z, stile_w, h - 0.06, 0.016, (0.13, 0.14, 0.17))
            # Bottom Kickplate Transom
            self._draw_box(0.0, 0.045, door_front_z, w, 0.065, 0.018, (0.15, 0.16, 0.19))

            # Heavy-Duty Stainless Steel Precision Door Hinges (Left Stile)
            for hy in [0.45, 1.10, 1.75]:
                # Hinge barrel mounting flange
                self._draw_box(-hw + 0.006, hy, door_front_z + 0.008, 0.014, 0.055, 0.014, (0.65, 0.68, 0.74))
                # Hinge pivot pin core
                self._draw_box(-hw + 0.006, hy, door_front_z + 0.015, 0.008, 0.065, 0.008, (0.85, 0.88, 0.92))
                # Fastener hex bolts
                for h_bolt in [-0.018, 0.018]:
                    self._draw_box(-hw + 0.018, hy + h_bolt, door_front_z + 0.008, 0.005, 0.005, 0.003, (0.85, 0.88, 0.92))

            # High-Security Electronic RFID / Keypad Swing Handle Lock (Right Stile at Waist Height)
            lock_y = 1.05
            lock_x = hw - 0.024
            # Recessed escutcheon handle cup
            self._draw_box(lock_x, lock_y, door_front_z + 0.006, 0.032, 0.22, 0.010, (0.07, 0.08, 0.10))
            # Matte Chrome Ergonomic Swing Lever Handle
            self._draw_box(lock_x, lock_y - 0.02, door_front_z + 0.014, 0.018, 0.14, 0.012, (0.72, 0.76, 0.82))
            # Push-button mechanical thumb release
            self._draw_box(lock_x, lock_y + 0.065, door_front_z + 0.015, 0.015, 0.022, 0.008, (0.28, 0.30, 0.35))
            # Electronic RFID Keycard Proximity Lens
            self._draw_box(lock_x, lock_y + 0.095, door_front_z + 0.012, 0.020, 0.024, 0.004, (0.05, 0.12, 0.18))

            # Smart Access Authorized Glow LED (Emerald Green / Cyan Pulse)
            lock_pulse = 0.85 + 0.15 * math.sin(now * 3.5 + rack_id)
            lock_col = (0.0, 0.95 * lock_pulse, 0.75 * lock_pulse)
            self._draw_box(lock_x, lock_y + 0.095, door_front_z + 0.015, 0.014, 0.006, 0.002, lock_col)

            # =========================================================================
            # 5. ILLUMINATED DATACENTER CANOPY MARQUEE & CLIMATE TELEMETRY POD
            # =========================================================================
            canopy_y = h - 0.075
            canopy_z = hd + 0.014

            # Deep Anodized Navy/Charcoal Canopy Header Box
            self._draw_box(0.0, canopy_y, canopy_z, 0.48, 0.095, 0.018, (0.06, 0.09, 0.14))
            # Cyan glowing accent trim line across upper and lower border
            self._draw_box(0.0, canopy_y + 0.042, canopy_z + 0.008, 0.46, 0.003, 0.003, (0.0, 0.80, 1.0))
            self._draw_box(0.0, canopy_y - 0.042, canopy_z + 0.008, 0.46, 0.003, 0.003, (0.0, 0.80, 1.0))

            # Backlit Rack Name Plate (RACK-A01, RACK-A02, RACK-A03)
            self._draw_box(-0.06, canopy_y, canopy_z + 0.009, 0.24, 0.055, 0.004, (0.04, 0.18, 0.34))
            # Illuminated Lettering Core Glow
            name_glow = 0.90 + 0.10 * math.sin(now * 2.0 + rack_id)
            self._draw_box(-0.06, canopy_y, canopy_z + 0.012, 0.21, 0.038, 0.002, (0.35 * name_glow, 0.88 * name_glow, 1.0 * name_glow))

            # Environmental Climate Sensor Pod (Temperature & Humidity OLED Telemetry)
            self._draw_box(0.145, canopy_y, canopy_z + 0.008, 0.125, 0.060, 0.004, (0.08, 0.10, 0.13))
            # Sapphire display glass
            self._draw_box(0.145, canopy_y, canopy_z + 0.011, 0.115, 0.048, 0.002, (0.02, 0.14, 0.22))
            # Digital Green 7-Segment Temperature & RH Simulation (19.4°C / 45% RH)
            temp_glow = 0.85 + 0.15 * math.sin(now * 1.8 + rack_id)
            for seg_i in range(4):
                sx = 0.105 + seg_i * 0.026
                self._draw_box(sx, canopy_y + 0.008, canopy_z + 0.013, 0.018, 0.006, 0.001, (0.1, 0.98 * temp_glow, 0.35 * temp_glow))
                self._draw_box(sx, canopy_y - 0.008, canopy_z + 0.013, 0.018, 0.006, 0.001, (0.0, 0.85 * temp_glow, 0.95 * temp_glow))
            # Climate probe intake aspiration slots
            for slt in [-0.015, 0.015]:
                self._draw_box(0.198, canopy_y + slt, canopy_z + 0.010, 0.008, 0.003, 0.002, (0.15, 0.18, 0.22))

            # =========================================================================
            # 6. EIA-310-D SQUARE-HOLE VERTICAL MOUNTING RAILS & U-GRADUATIONS
            # =========================================================================
            rail_z = hd - 0.060
            rail_w = 0.038
            rail_d = 0.030

            for rx_rail in [-hw + 0.08, hw - 0.08]:
                # Folded Heavy C-Channel Steel Rail
                self._draw_box(rx_rail, hh, rail_z, rail_w, h - 0.14, rail_d, (0.32, 0.36, 0.42))
                # Rail interior bevel cavity
                self._draw_box(rx_rail, hh, rail_z - 0.005, rail_w - 0.010, h - 0.15, rail_d - 0.008, (0.18, 0.20, 0.24))

                # EIA-310 Genuine 3-Hole Square Cage Nut Perforation Pattern (1U to 42U)
                # Render square punchouts on rail face
                for u in range(1, 43):
                    uy = 0.14 + (u / 42.0) * 1.85
                    # 3 square holes per 1U
                    for hole_offset in [-0.012, 0.0, 0.012]:
                        self._draw_box(rx_rail, uy + hole_offset, rail_z + rail_d/2 + 0.001, 0.007, 0.007, 0.002, (0.06, 0.07, 0.09))

            # Fine Division Horizontal Rail Tick Lines
            glLineWidth(1.5)
            glColor3f(0.55, 0.62, 0.72)
            glBegin(GL_LINES)
            for u in range(1, 43):
                uy = 0.14 + (u / 42.0) * 1.85
                glVertex3f(-hw + 0.062, uy, rail_z + rail_d/2 + 0.002)
                glVertex3f(-hw + 0.098, uy, rail_z + rail_d/2 + 0.002)
                glVertex3f( hw - 0.098, uy, rail_z + rail_d/2 + 0.002)
                glVertex3f( hw - 0.062, uy, rail_z + rail_d/2 + 0.002)
            glEnd()

            # High-Visibility Silkscreened White U-Markers at every 5U (5, 10, 15, 20, 25, 30, 35, 40, 42)
            for mark_u in [5, 10, 15, 20, 25, 30, 35, 40, 42]:
                my = 0.14 + (mark_u / 42.0) * 1.85
                for rx_rail in [-hw + 0.052, hw - 0.052]:
                    # White U-Tag plate
                    self._draw_box(rx_rail, my, rail_z + rail_d/2 + 0.003, 0.016, 0.013, 0.002, (0.94, 0.96, 1.0))
                    # Number marker inner core
                    self._draw_box(rx_rail, my, rail_z + rail_d/2 + 0.004, 0.010, 0.007, 0.001, (0.05, 0.22, 0.45))

            # =========================================================================
            # 7. ZERO-U VERTICAL CABLE MANAGEMENT DUCTS & HIGH-DENSITY CABLE BUNDLES
            # =========================================================================
            # In the 6cm gap between rail (x=0.24) and outer frame (x=0.30)
            duct_z = hd - 0.075
            duct_w = 0.034

            for dx, d_sign, bundle_col in [(-hw + 0.038, -1, (0.0, 0.48, 0.95)), (hw - 0.038, 1, (0.95, 0.82, 0.05))]:
                # Vertical Cable Trough Channel
                self._draw_box(dx, hh, duct_z, duct_w, h - 0.20, 0.045, (0.09, 0.10, 0.13))

                # Vertical Cable Bundle running through duct
                self._draw_box(dx, hh, duct_z, duct_w - 0.012, h - 0.22, 0.025, bundle_col)

                # Plastic Cable Management Retention Fingers & Black Velcro Ties
                for f_idx in range(9):
                    fy = 0.25 + (f_idx / 8.0) * (h - 0.50)
                    # Nylon finger latch
                    self._draw_box(dx + 0.015 * d_sign, fy, duct_z + 0.015, 0.016, 0.008, 0.005, (0.24, 0.26, 0.30))
                    # Black cinch Velcro tie
                    self._draw_box(dx, fy, duct_z, duct_w - 0.008, 0.012, 0.028, (0.05, 0.05, 0.06))

            # =========================================================================
            # 8. DUAL REDUNDANT 0U VERTICAL REAR PDUS (FEED A & FEED B)
            # =========================================================================
            pdu_z = -hd + 0.058
            pdu_w = 0.040
            pdu_h = h - 0.22

            # PDU-A (Utility Power Primary - Feed A Blue Stripe) on Left Rear
            self._draw_box(-hw + 0.075, hh, pdu_z, pdu_w, pdu_h, 0.032, (0.08, 0.08, 0.10))
            self._draw_box(-hw + 0.075, hh, pdu_z + 0.016, 0.008, pdu_h - 0.04, 0.002, (0.0, 0.55, 0.95))
            # PDU-A Digital LED Ammeter at top
            self._draw_box(-hw + 0.075, h - 0.20, pdu_z + 0.017, 0.028, 0.020, 0.002, (0.0, 0.95, 0.50))
            # PDU-A Outlets & Green Status LEDs
            for p_idx in range(10):
                py = 0.25 + (p_idx / 9.0) * (h - 0.55)
                # Outlet socket (C13/C19)
                self._draw_box(-hw + 0.075, py, pdu_z + 0.016, 0.022, 0.014, 0.002, (0.03, 0.03, 0.04))
                # Status LED
                self._draw_box(-hw + 0.090, py + 0.005, pdu_z + 0.017, 0.005, 0.005, 0.002, (0.1, 0.98, 0.2))

            # PDU-B (Generator/UPS Secondary - Feed B Red Stripe) on Right Rear
            self._draw_box(hw - 0.075, hh, pdu_z, pdu_w, pdu_h, 0.032, (0.08, 0.08, 0.10))
            self._draw_box(hw - 0.075, hh, pdu_z + 0.016, 0.008, pdu_h - 0.04, 0.002, (0.90, 0.20, 0.15))
            # PDU-B Digital LED Ammeter at top
            self._draw_box(hw - 0.075, h - 0.20, pdu_z + 0.017, 0.028, 0.020, 0.002, (0.1, 0.90, 0.60))
            # PDU-B Outlets & Green Status LEDs
            for p_idx in range(10):
                py = 0.25 + (p_idx / 9.0) * (h - 0.55)
                # Outlet socket
                self._draw_box(hw - 0.075, py, pdu_z + 0.016, 0.022, 0.014, 0.002, (0.03, 0.03, 0.04))
                # Status LED
                self._draw_box(hw - 0.060, py + 0.005, pdu_z + 0.017, 0.005, 0.005, 0.002, (0.1, 0.98, 0.2))

            # =========================================================================
            # 9. ROOF STRUCTURE, DUAL HIGH-VELOCITY EXHAUST FANS & CABLE DROP GLANDS
            # =========================================================================
            roof_y = h - 0.025
            # Heavy-gauge roof steel plate with beveled rim
            self._draw_box(0.0, roof_y, 0.0, w, 0.05, d, (0.08, 0.09, 0.11))
            self._draw_box(0.0, h + 0.002, 0.0, w - 0.02, 0.004, d - 0.02, (0.12, 0.13, 0.16))

            # Dual High-Velocity Exhaust Fans on Roof with Concentric Guard Rings & Hubs
            for fx in [-0.15, 0.15]:
                # Circular fan cowl shroud
                self._draw_box(fx, h + 0.008, 0.0, 0.18, 0.012, 0.18, (0.16, 0.18, 0.22))
                self._draw_box(fx, h + 0.015, 0.0, 0.15, 0.004, 0.15, (0.06, 0.07, 0.09))
                # Metallic concentric wire finger guard
                self._draw_box(fx, h + 0.018, 0.0, 0.12, 0.002, 0.12, (0.50, 0.54, 0.60))
                # Center spinner hub
                self._draw_box(fx, h + 0.020, 0.0, 0.045, 0.008, 0.045, (0.28, 0.32, 0.38))

            # Overhead Cable Entry Drop Glands (Nylon Brush Grommets on Roof)
            for gx in [-0.12, 0.12]:
                # Rectangular gland frame
                self._draw_box(gx, h + 0.006, -0.22, 0.09, 0.010, 0.12, (0.14, 0.15, 0.18))
                # Dense nylon bristle brush seal
                self._draw_box(gx, h + 0.010, -0.22, 0.07, 0.004, 0.10, (0.03, 0.03, 0.04))

            # =========================================================================
            # 10. MULTI-TIER INDUSTRIAL STATUS BEACON STACK LIGHT (ANDON TOWER)
            # =========================================================================
            beacon_x = 0.0
            beacon_z = hd - 0.08
            beacon_base_y = h + 0.015

            # Heavy Aluminum Stanchion Mounting Pole
            self._draw_box(beacon_x, beacon_base_y + 0.02, beacon_z, 0.018, 0.040, 0.018, (0.55, 0.58, 0.64))
            self._draw_box(beacon_x, beacon_base_y + 0.042, beacon_z, 0.038, 0.008, 0.038, (0.12, 0.14, 0.18))

            # Tier 1 (Bottom): Emerald Green Module (Nominal System Sync - Gentle Breathing Pulse)
            b_pulse = 0.82 + 0.18 * math.sin(now * 2.8 + rack_id)
            tier1_col = (0.05 * b_pulse, 0.98 * b_pulse, 0.32 * b_pulse)
            self._draw_box(beacon_x, beacon_base_y + 0.062, beacon_z, 0.036, 0.030, 0.036, tier1_col)

            # Tier 2 (Middle): Amber Warning Module (Standby)
            self._draw_box(beacon_x, beacon_base_y + 0.094, beacon_z, 0.036, 0.030, 0.036, (0.35, 0.18, 0.04))

            # Tier 3 (Top): Ruby Red Critical Alarm Module (Dark in normal state)
            self._draw_box(beacon_x, beacon_base_y + 0.126, beacon_z, 0.036, 0.030, 0.036, (0.30, 0.06, 0.06))

            # Black Cap with Piezo Sounder Dome
            self._draw_box(beacon_x, beacon_base_y + 0.146, beacon_z, 0.040, 0.010, 0.040, (0.10, 0.11, 0.13))
            self._draw_box(beacon_x, beacon_base_y + 0.154, beacon_z, 0.020, 0.006, 0.020, (0.20, 0.22, 0.26))

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

        # Seamless Wide Executive Leather Desk Pad under both laptops
        self._draw_box(0.0, 0.771, 0.0, 1.18, 0.002, 0.44, (0.13, 0.14, 0.17))
        self._draw_box(0.0, 0.772, 0.0, 1.16, 0.001, 0.42, (0.18, 0.20, 0.24))
        self._draw_box(0.0, 0.7725, 0.0, 1.14, 0.001, 0.40, (0.12, 0.13, 0.15))

        # Desk Center Accessories: Datacenter Engineering Notepad with Slate Clip & Pen
        self._draw_box(0.0, 0.775, 0.16, 0.18, 0.004, 0.14, (0.25, 0.26, 0.30))
        self._draw_box(0.0, 0.778, 0.16, 0.16, 0.002, 0.12, (0.94, 0.94, 0.94))
        self._draw_box(0.0, 0.780, 0.22, 0.04, 0.003, 0.015, (0.45, 0.48, 0.52))
        self._draw_box(0.10, 0.778, 0.16, 0.008, 0.006, 0.12, (0.1, 0.45, 0.85))

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
                elif dev.device_type in ("isp_gateway", "isp") or (dev.device_type == "server" and "isp" in dev.hostname.lower()):
                    self._render_isp_gateway(dev, current_time)
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
        base_color = (0.80, 0.82, 0.86) if is_windows else (0.12, 0.13, 0.15)
        self._draw_box(0.0, 0.008, 0.0, 0.36, 0.016, 0.26, base_color)

        # 2. Keyboard Well & Chiclet Keys
        well_color = (0.13, 0.14, 0.17) if is_windows else (0.07, 0.07, 0.08)
        self._draw_box(0.0, 0.016, -0.020, 0.29, 0.002, 0.13, well_color)

        key_color = (0.24, 0.26, 0.30) if is_windows else (0.18, 0.19, 0.22)

        # Row 0: Function Keys (Esc, F1-F12, Del)
        for ki in range(6):
            kx = -0.115 + ki * 0.046
            self._draw_box(kx, 0.0172, -0.068, 0.038, 0.002, 0.010, key_color)

        # Row 1: Numbers & Backspace
        for ki in range(8):
            kx = -0.122 + ki * 0.035
            self._draw_box(kx, 0.0175, -0.050, 0.028, 0.002, 0.014, key_color)

        # Row 2: QWERTY Row
        for ki in range(8):
            kx = -0.122 + ki * 0.035
            self._draw_box(kx, 0.0175, -0.030, 0.028, 0.002, 0.014, key_color)

        # Row 3: Home Row (ASDF)
        for ki in range(8):
            kx = -0.122 + ki * 0.035
            self._draw_box(kx, 0.0175, -0.010, 0.028, 0.002, 0.014, key_color)

        # Row 4: Bottom Row (Modifiers & Spacebar)
        self._draw_box(-0.115, 0.0175, 0.014, 0.036, 0.002, 0.016, key_color)
        self._draw_box(-0.070, 0.0175, 0.014, 0.036, 0.002, 0.016, key_color)
        # Wide Spacebar
        space_col = (0.27, 0.29, 0.33) if is_windows else (0.20, 0.21, 0.24)
        self._draw_box(0.0, 0.0178, 0.014, 0.085, 0.002, 0.016, space_col)
        self._draw_box(0.070, 0.0175, 0.014, 0.036, 0.002, 0.016, key_color)
        self._draw_box(0.115, 0.0175, 0.014, 0.036, 0.002, 0.016, key_color)

        # 3. Trackpad, Buttons & Palmrest Badges
        if is_windows:
            # Silver Precision Glass Trackpad
            self._draw_box(0.0, 0.0165, 0.075, 0.11, 0.002, 0.068, (0.72, 0.74, 0.78))
            self._draw_box(0.0, 0.0168, 0.075, 0.108, 0.001, 0.066, (0.76, 0.78, 0.82))
            # Windows 11 Cyan Logo Badge
            self._draw_box(0.11, 0.0165, 0.075, 0.018, 0.001, 0.014, (0.0, 0.48, 0.92))
            # Intel / Core Badge
            self._draw_box(0.135, 0.0165, 0.075, 0.012, 0.001, 0.014, (0.15, 0.55, 0.95))
        else:
            # Iconic ThinkPad Red TrackPoint Dome in center of keyboard
            self._draw_box(0.0, 0.0195, -0.020, 0.009, 0.004, 0.009, (0.88, 0.12, 0.12))
            # Matte Black Trackpad with discrete click buttons
            self._draw_box(0.0, 0.0165, 0.080, 0.10, 0.002, 0.058, (0.14, 0.15, 0.17))
            self._draw_box(0.0, 0.0170, 0.048, 0.09, 0.001, 0.012, (0.20, 0.21, 0.24))
            self._draw_box(0.0, 0.0173, 0.048, 0.025, 0.001, 0.003, (0.85, 0.20, 0.15))
            # Ubuntu Orange Badge
            self._draw_box(0.11, 0.0165, 0.075, 0.016, 0.001, 0.016, (0.90, 0.35, 0.10))

        # 4. Tilted Laptop Screen Lid (Tilted BACKWARDS by -25 degrees for natural viewing)
        glPushMatrix()
        glTranslatef(0.0, 0.016, -0.118)
        glRotatef(-25.0, 1.0, 0.0, 0.0)

        # Screen Lid Outer Shell
        lid_color = (0.76, 0.78, 0.82) if is_windows else (0.11, 0.12, 0.14)
        self._draw_box(0.0, 0.12, 0.0, 0.36, 0.24, 0.010, lid_color)

        # Front Display Bezel (Thin sleek bezel)
        self._draw_box(0.0, 0.12, 0.005, 0.35, 0.23, 0.002, (0.08, 0.09, 0.11))

        # Webcam & Status Indicator LED at top of bezel
        self._draw_box(0.0, 0.23, 0.006, 0.006, 0.006, 0.001, (0.02, 0.02, 0.02))
        self._draw_box(0.010, 0.23, 0.006, 0.002, 0.002, 0.001, (0.1, 0.95, 0.3))

        # Glowing IPS Display Face & Authentic OS Graphics
        if is_windows:
            # Windows 11 Sapphire Blue Wallpaper Base
            self._draw_box(0.0, 0.12, 0.0065, 0.32, 0.20, 0.001, (0.05, 0.14, 0.32))

            # Windows 11 Bloom Flower (Layered dynamic petals)
            # Left & Right outer petals
            self._draw_box(-0.035, 0.135, 0.0070, 0.09, 0.08, 0.001, (0.08, 0.32, 0.72))
            self._draw_box(0.035, 0.135, 0.0070, 0.09, 0.08, 0.001, (0.08, 0.32, 0.72))
            # Main central petals
            self._draw_box(0.0, 0.140, 0.0072, 0.11, 0.09, 0.001, (0.14, 0.48, 0.88))
            self._draw_box(-0.015, 0.130, 0.0074, 0.08, 0.07, 0.001, (0.28, 0.68, 0.98))
            self._draw_box(0.015, 0.130, 0.0074, 0.08, 0.07, 0.001, (0.35, 0.74, 1.0))
            # Core bright highlights
            self._draw_box(0.0, 0.125, 0.0076, 0.045, 0.045, 0.001, (0.75, 0.90, 1.0))

            # Centered Modern Acrylic Taskbar
            self._draw_box(0.0, 0.030, 0.0075, 0.32, 0.016, 0.001, (0.06, 0.12, 0.24))
            # 4-Quadrant Windows Start Logo
            for sqx in [-0.042, -0.036]:
                for sqy in [0.033, 0.027]:
                    self._draw_box(sqx, sqy, 0.008, 0.004, 0.004, 0.001, (0.0, 0.65, 1.0))
            # Search Bar Pill
            self._draw_box(-0.020, 0.030, 0.008, 0.018, 0.008, 0.001, (0.12, 0.20, 0.35))
            # App icons (Edge, PuTTY, Terminal, Settings)
            app_cols = [(0.0, 0.65, 0.95), (0.2, 0.5, 0.9), (0.1, 0.1, 0.12), (0.45, 0.48, 0.52)]
            for ic_idx, ic_col in enumerate(app_cols):
                self._draw_box(-0.002 + ic_idx * 0.012, 0.030, 0.008, 0.007, 0.007, 0.001, ic_col)
            # System tray dots (Wifi, Sound, Clock)
            for tr_idx, tr_col in enumerate([(0.8, 0.85, 0.9), (0.8, 0.85, 0.9), (0.95, 0.95, 0.98)]):
                self._draw_box(0.120 + tr_idx * 0.010, 0.030, 0.008, 0.005, 0.005, 0.001, tr_col)
        else:
            # Ubuntu 22.04 LTS Jammy Aubergine & Sunset Orange Wallpaper
            self._draw_box(0.0, 0.12, 0.0065, 0.32, 0.20, 0.001, (0.26, 0.07, 0.22))
            # Warm dusk gradient backdrop
            self._draw_box(0.05, 0.12, 0.007, 0.18, 0.14, 0.001, (0.48, 0.16, 0.12))
            # Stylized Jammy Jellyfish silhouette & tentacles
            self._draw_box(0.06, 0.145, 0.0072, 0.08, 0.05, 0.001, (0.78, 0.28, 0.12))
            self._draw_box(0.06, 0.135, 0.0074, 0.06, 0.03, 0.001, (0.92, 0.44, 0.15))
            # Flowing tentacles
            for ti, tx in enumerate([0.04, 0.055, 0.07, 0.085]):
                self._draw_box(tx, 0.095 - ti * 0.004, 0.0075, 0.003, 0.05, 0.001, (0.85, 0.38, 0.12))

            # GNOME 42 Top Bar
            self._draw_box(0.0, 0.212, 0.0075, 0.32, 0.014, 0.001, (0.07, 0.07, 0.09))
            self._draw_box(-0.130, 0.212, 0.008, 0.024, 0.008, 0.001, (0.18, 0.18, 0.22))
            self._draw_box(0.0, 0.212, 0.008, 0.022, 0.006, 0.001, (0.88, 0.88, 0.92))
            for ri in range(3):
                self._draw_box(0.130 + ri * 0.008, 0.212, 0.008, 0.004, 0.004, 0.001, (0.8, 0.8, 0.85))

            # GNOME 42 Left Dock Launcher
            self._draw_box(-0.148, 0.114, 0.0075, 0.024, 0.182, 0.001, (0.08, 0.08, 0.10))
            dock_cols = [(0.92, 0.35, 0.12), (0.0, 0.48, 0.92), (0.1, 0.1, 0.12), (0.42, 0.44, 0.48), (0.8, 0.8, 0.85)]
            for ic_idx, ic_col in enumerate(dock_cols):
                self._draw_box(-0.148, 0.178 - ic_idx * 0.026, 0.008, 0.013, 0.013, 0.001, ic_col)

        glPopMatrix()

        # 5. Physical Network & Console Ports on Chassis Flanks (Flush recessed sockets)
        # Left Flank: eth0 (Cat6 RJ45 Gigabit Ethernet)
        eth_port = dev.ports.get("eth0")
        if eth_port:
            px, py, pz = dev.get_port_local_pos("eth0", 0)
            # Flush dark metallic socket frame
            self._draw_box(px, py, pz, 0.003, 0.010, 0.015, (0.32, 0.34, 0.38))
            # Socket cavity
            self._draw_box(px, py, pz, 0.002, 0.007, 0.011, (0.04, 0.04, 0.05))
            # Link LED
            led = eth_port.get_led_state(now)
            led_c = (0.1, 0.98, 0.2) if led in (LEDState.GREEN, LEDState.BLINK_GREEN) else (0.08, 0.12, 0.08)
            self._draw_box(px, py + 0.004, pz + 0.006, 0.002, 0.002, 0.002, led_c)

        # Right Flank: con0 (Serial Console Rollover Port)
        con_port = dev.ports.get("con0")
        if con_port:
            cx, cy, cz = dev.get_port_local_pos("con0", 0)
            # Flush dark metallic socket frame
            self._draw_box(cx, cy, cz, 0.003, 0.008, 0.014, (0.24, 0.26, 0.30))
            # Socket cavity
            self._draw_box(cx, cy, cz, 0.002, 0.005, 0.010, (0.04, 0.04, 0.05))
            # Connection Status LED
            con_connected = con_port.cable is not None
            con_led = (0.1, 0.95, 0.2) if con_connected else (0.08, 0.12, 0.08)
            self._draw_box(cx, cy + 0.004, cz + 0.006, 0.002, 0.002, 0.002, con_led)

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

    def _render_isp_gateway(self, dev, now):
        """
        High-detail Carrier Ethernet Optical Demarcation & WAN Provider Edge Gateway (1U).
        Features industrial two-tone titanium-charcoal bezel, carrier sync status LEDs,
        Class 1 Laser safety chevron, cyan-backlit diagnostic LCD matrix display,
        shielded 10GbE RJ45 customer handoff socket (eth0), dual SFP+ optical WAN cages
        with LC duplex transceivers and yellow Single-Mode Fiber (SMF) patch leads,
        brass dual chassis grounding studs, honeycomb exhaust grille, and telecom rack ears.
        """
        hw = dev.width / 2.0
        hh = dev.height / 2.0
        front_z = dev.depth / 2.0 + 0.003

        # 1. Front Faceplate (Two-tone: Charcoal Chassis with Titanium Pearl Faceplate)
        self._draw_box(0.0, 0.0, front_z, dev.width, dev.height, 0.006, (0.20, 0.22, 0.26))
        # Titanium Pearl main instrument fascia
        self._draw_box(0.0, -0.002, front_z + 0.001, dev.width - 0.045, dev.height - 0.008, 0.003, (0.28, 0.31, 0.36))

        # 2. Telecom Warning Yellow & High-Tech Cyan Accent Stripes across top edge
        self._draw_box(0.0, hh - 0.003, front_z + 0.002, dev.width - 0.04, 0.003, 0.002, (0.95, 0.78, 0.10))
        self._draw_box(0.0, hh - 0.006, front_z + 0.002, dev.width - 0.04, 0.002, 0.002, (0.0, 0.75, 0.95))

        # 3. Heavy-Duty Telecom Rack Mount Ears with Captive Knurled Thumbscrews
        self._draw_box(-hw + 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.42, 0.45, 0.50))
        self._draw_box(hw - 0.01, 0.0, front_z + 0.001, 0.02, dev.height, 0.005, (0.42, 0.45, 0.50))
        # Stainless hex mounting screws (top and bottom of each ear)
        for ear_x in [-hw + 0.01, hw - 0.01]:
            for sy in [-0.012, 0.012]:
                self._draw_box(ear_x, sy, front_z + 0.004, 0.006, 0.006, 0.002, (0.85, 0.88, 0.92))
            # Captive thumbscrew in center
            self._draw_box(ear_x, 0.0, front_z + 0.005, 0.009, 0.009, 0.004, (0.65, 0.68, 0.72))

        # 4. Dual Brass Telecom Grounding Studs (Chassis Earth Safety)
        for gy in [-0.008, 0.008]:
            self._draw_box(-0.21, gy, front_z + 0.003, 0.005, 0.005, 0.003, (0.78, 0.65, 0.20))
        # Green ground symbol badge
        self._draw_box(-0.21, 0.0, front_z + 0.002, 0.004, 0.006, 0.001, (0.1, 0.85, 0.25))

        # 5. Telecom Status LED Cluster (PWR, CARRIER, SYNC, ALARM, TEST)
        eth_port = dev.ports.get("eth0")
        is_carrier_up = (eth_port and eth_port.is_link_up) or dev.is_powered

        # Status LED Bank Base Plate
        self._draw_box(-0.165, 0.0, front_z + 0.002, 0.075, dev.height - 0.014, 0.002, (0.12, 0.13, 0.16))

        # PWR LED (Steady Green)
        self._draw_box(-0.192, 0.006, front_z + 0.0035, 0.005, 0.005, 0.002, (0.1, 0.98, 0.2) if dev.is_powered else (0.08, 0.12, 0.08))

        # CARRIER LED (High-Intensity Emerald Green - Link Sync)
        carrier_pulse = 0.85 + 0.15 * math.sin(now * 4.0)
        carrier_col = (0.0, 1.0 * carrier_pulse, 0.4 * carrier_pulse) if is_carrier_up else (0.08, 0.12, 0.08)
        self._draw_box(-0.178, 0.006, front_z + 0.0035, 0.005, 0.005, 0.002, carrier_col)

        # SYNC / BITS LED (Telecom Clock Sync - High-precision 2Hz pulse)
        sync_blink = int(now * 4) % 2 == 0
        sync_col = (0.15, 0.85, 1.0) if sync_blink else (0.05, 0.25, 0.35)
        self._draw_box(-0.164, 0.006, front_z + 0.0035, 0.005, 0.005, 0.002, sync_col)

        # ALARM LED (Bi-color: Steady Dim Green when normal, Amber/Red if issue)
        alarm_col = (0.08, 0.50, 0.15) if is_carrier_up else (0.95, 0.20, 0.10)
        self._draw_box(-0.192, -0.006, front_z + 0.0035, 0.005, 0.005, 0.002, alarm_col)

        # TEST / LOOP LED (Loopback Diagnostic Indicator)
        self._draw_box(-0.178, -0.006, front_z + 0.0035, 0.005, 0.005, 0.002, (0.08, 0.08, 0.10))

        # 6. Class 1 Laser Product Warning Chevron Badge
        self._draw_box(-0.145, 0.0, front_z + 0.003, 0.016, 0.016, 0.002, (0.95, 0.80, 0.10))
        self._draw_box(-0.145, 0.0, front_z + 0.004, 0.010, 0.010, 0.001, (0.10, 0.10, 0.10))
        self._draw_box(-0.145, 0.0, front_z + 0.0045, 0.004, 0.004, 0.001, (0.95, 0.80, 0.10))

        # 7. Diagnostic Carrier Backlit LCD Display (Cyan/Sapphire Matrix)
        # Bezel frame
        self._draw_box(-0.065, 0.0, front_z + 0.0025, 0.115, 0.028, 0.002, (0.10, 0.11, 0.13))
        # Inset display glass
        self._draw_box(-0.065, 0.0, front_z + 0.0035, 0.105, 0.022, 0.001, (0.02, 0.14, 0.22))

        # Backlit Screen glow & dynamic scanning line
        lcd_glow = 0.88 + 0.12 * math.sin(now * 2.5)
        # Top line: Carrier WAN Sync status dots/segments
        for seg in range(6):
            sx = -0.105 + seg * 0.016
            self._draw_box(sx, 0.005, front_z + 0.004, 0.012, 0.004, 0.001, (0.0, 0.85 * lcd_glow, 0.95 * lcd_glow))
        # Bottom line: IP / Carrier Uplink telemetry segments
        for seg in range(5):
            sx = -0.100 + seg * 0.018
            self._draw_box(sx, -0.005, front_z + 0.004, 0.014, 0.004, 0.001, (0.15, 0.70 * lcd_glow, 0.90 * lcd_glow))

        # 8. Customer Handoff RJ45 10GbE Port (eth0)
        # Matches exact coordinate from dev.get_port_local_pos("eth0") -> (0.04, 0.0, front_z + 0.004)
        px, py, pz = dev.get_port_local_pos("eth0", 0)

        # Port decorative bezel plate with silkscreen trim
        self._draw_box(px, py, front_z + 0.002, 0.038, dev.height - 0.012, 0.002, (0.16, 0.18, 0.22))
        # Cyan outline trim around handoff port
        self._draw_box(px, py + 0.013, front_z + 0.003, 0.032, 0.002, 0.001, (0.0, 0.75, 0.95))

        # Heavy-duty shielded RJ45 metal jack frame
        self._draw_box(px, py, pz, 0.026, 0.020, 0.004, (0.58, 0.62, 0.66))
        # Dark recessed cavity
        self._draw_box(px, py, pz + 0.002, 0.020, 0.015, 0.003, (0.03, 0.03, 0.04))
        # Internal gold contact pins
        self._draw_box(px, py + 0.003, pz + 0.003, 0.012, 0.003, 0.001, (0.90, 0.78, 0.18))

        # Dual Status LEDs on RJ45 Handoff:
        led = eth_port.get_led_state(now) if eth_port else LEDState.OFF
        link_col = (0.1, 0.98, 0.2) if led in (LEDState.GREEN, LEDState.BLINK_GREEN) else ((1.0, 0.65, 0.05) if led == LEDState.AMBER else (0.08, 0.12, 0.08))
        self._draw_box(px - 0.006, py + 0.015, pz + 0.003, 0.005, 0.005, 0.002, link_col)

        act_blink = (led in (LEDState.GREEN, LEDState.BLINK_GREEN)) and (int(now * 16) % 2 == 0)
        act_col = (0.2, 0.95, 0.3) if act_blink else (0.06, 0.10, 0.06)
        self._draw_box(px + 0.006, py + 0.015, pz + 0.003, 0.005, 0.005, 0.002, act_col)

        # 9. Dual Optical SFP+ WAN Uplink Transceiver Cages (SFP0 / SFP1)
        # SFP Cages Base housing
        self._draw_box(0.115, 0.0, front_z + 0.002, 0.065, dev.height - 0.012, 0.002, (0.14, 0.15, 0.18))

        # Dual SFP+ Cages (SFP0 at x=0.098, SFP1 at x=0.132)
        sfp_configs = [
            (0.098, (0.05, 0.45, 0.90), True),   # SFP0: Primary WAN 10G-LR (Blue LC latch, Active fiber)
            (0.132, (0.95, 0.55, 0.10), False)   # SFP1: Backup WAN Demarc (Orange/Amber LC latch, Standby)
        ]
        for s_idx, (sx, latch_col, has_fiber) in enumerate(sfp_configs):
            # Metal SFP Cage Body with spring EMI ground fingers
            self._draw_box(sx, 0.0, front_z + 0.003, 0.024, 0.018, 0.005, (0.50, 0.53, 0.57))
            self._draw_box(sx, 0.0, front_z + 0.005, 0.020, 0.014, 0.003, (0.15, 0.16, 0.19))

            # Optical LC Duplex Transceiver Module body
            self._draw_box(sx, 0.0, front_z + 0.007, 0.017, 0.012, 0.004, (0.68, 0.72, 0.76))
            # Colored Optical Pull Latch / Bail
            self._draw_box(sx, 0.005, front_z + 0.009, 0.015, 0.004, 0.003, latch_col)

            # Optical RX_LOS & TX_ACT Micro LEDs above each SFP cage
            rx_led = (0.1, 0.98, 0.2) if (dev.is_powered and s_idx == 0) else (0.08, 0.12, 0.08)
            self._draw_box(sx - 0.005, 0.013, front_z + 0.004, 0.004, 0.004, 0.002, rx_led)
            tx_blink = (int(now * 18 + s_idx) % 2 == 0) and dev.is_powered
            tx_led = (0.2, 0.90, 1.0) if tx_blink else (0.05, 0.15, 0.25)
            self._draw_box(sx + 0.005, 0.013, front_z + 0.004, 0.004, 0.004, 0.002, tx_led)

            # High-Visibility Yellow Single-Mode Fiber (SMF) Optical Patch Leads entering SFP0
            if has_fiber:
                # Dual LC connector boot ferrules (Blue)
                self._draw_box(sx - 0.003, -0.001, front_z + 0.012, 0.005, 0.006, 0.007, (0.08, 0.35, 0.85))
                self._draw_box(sx + 0.003, -0.001, front_z + 0.012, 0.005, 0.006, 0.007, (0.08, 0.35, 0.85))

                # Yellow Single-Mode Fiber optical cable leads curving downward
                fiber_col = (0.98, 0.85, 0.05)
                self._draw_box(sx - 0.003, -0.006, front_z + 0.016, 0.003, 0.008, 0.003, fiber_col)
                self._draw_box(sx + 0.003, -0.006, front_z + 0.016, 0.003, 0.008, 0.003, fiber_col)
                # Lower curve of fiber patch cord
                self._draw_box(sx, -0.012, front_z + 0.018, 0.008, 0.006, 0.003, fiber_col)

        # 10. Right Honeycomb Exhaust Ventilation Grille
        self._draw_box(0.185, 0.0, front_z + 0.002, 0.055, dev.height - 0.014, 0.002, (0.07, 0.08, 0.10))
        # Slotted airflow vanes
        for v in range(5):
            vy = -0.010 + v * 0.005
            self._draw_box(0.185, vy, front_z + 0.003, 0.048, 0.002, 0.001, (0.30, 0.34, 0.40))

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
                if port.device and port.device.device_type == "laptop":
                    lx = pp[0] - port.device.pos_x
                    laptop_boot_c = (0.16, 0.18, 0.20)
                    if lx < 0:
                        # Left side port (eth0) -> boot extends to the left (-X)
                        self._draw_box(pp[0] - 0.008, pp[1], pp[2], 0.012, 0.010, 0.013, laptop_boot_c)
                    else:
                        # Right side port (con0) -> boot extends to the right (+X)
                        self._draw_box(pp[0] + 0.008, pp[1], pp[2], 0.012, 0.010, 0.013, laptop_boot_c)
                else:
                    self._draw_box(pp[0], pp[1], pp[2] + 0.014, 0.018, 0.016, 0.024, boot_c)
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
