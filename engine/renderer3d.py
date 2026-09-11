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

        # Performance Display Lists for static 3D geometry
        self.room_display_list = None
        self.racks_display_list = None
        self.workbench_display_list = None
        self.laptop_win_display_list = None
        self.laptop_linux_display_list = None
        self.cables_display_list = None
        self._cables_cache_key = None
        self._device_display_lists = set()

    def init_gl(self, width, height):
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        # Near plane at 0.08m provides 2x depth buffer resolution, eliminating z-fighting and shimmering
        gluPerspective(self.fov, float(width) / float(max(1, height)), 0.08, 100.0)
        glMatrixMode(GL_MODELVIEW)

        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)
        glShadeModel(GL_SMOOTH)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Hardware Anti-Aliasing & Line Smoothing for ultra-sharp edges
        try:
            glEnable(GL_MULTISAMPLE)
        except Exception:
            pass

        try:
            glEnable(GL_LINE_SMOOTH)
            glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        except Exception:
            pass

        glClearColor(0.88, 0.91, 0.95, 1.0)
        self._delete_display_lists()

    def _delete_display_lists(self):
        for attr in ("room_display_list", "racks_display_list", "workbench_display_list",
                     "laptop_win_display_list", "laptop_linux_display_list", "cables_display_list"):
            l_id = getattr(self, attr, None)
            if l_id is not None:
                try:
                    glDeleteLists(l_id, 1)
                except Exception:
                    pass
                setattr(self, attr, None)
        self._cables_cache_key = None

        # Clean up all allocated device display lists
        for dl in list(self._device_display_lists):
            try:
                glDeleteLists(dl, 1)
            except Exception:
                pass
        self._device_display_lists.clear()

    def invalidate_device(self, dev):
        """Invalidates and frees cached display lists for a specific device."""
        for attr in ("_dl_body", "_dl_front", "_dl_rear"):
            dl = getattr(dev, attr, None)
            if dl is not None:
                try:
                    glDeleteLists(dl, 1)
                except Exception:
                    pass
                self._device_display_lists.discard(dl)
                setattr(dev, attr, None)

    def _init_display_lists(self):
        self._delete_display_lists()

        # 1. Compile Room static list
        self.room_display_list = glGenLists(1)
        glNewList(self.room_display_list, GL_COMPILE)
        self._compile_room_static_list()
        glEndList()

        # 2. Compile Server Racks static list
        self.racks_display_list = glGenLists(1)
        glNewList(self.racks_display_list, GL_COMPILE)
        self._compile_server_racks_static_list()
        glEndList()

        # 3. Compile Workbench static list
        self.workbench_display_list = glGenLists(1)
        glNewList(self.workbench_display_list, GL_COMPILE)
        self._compile_workbench_static_list()
        glEndList()

        # 4. Compile Laptop Windows 11 list
        self.laptop_win_display_list = glGenLists(1)
        glNewList(self.laptop_win_display_list, GL_COMPILE)
        self._compile_laptop_static_list(is_windows=True)
        glEndList()

        # 5. Compile Laptop Ubuntu list
        self.laptop_linux_display_list = glGenLists(1)
        glNewList(self.laptop_linux_display_list, GL_COMPILE)
        self._compile_laptop_static_list(is_windows=False)
        glEndList()

    def render_scene(self, camera, devices, cables, focused_dev=None, focused_port=None):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        camera.apply_view()

        now = time.time()

        if self.room_display_list is None:
            self._init_display_lists()

        # 1. Render Datacenter Room (Floor, Cold-Aisle Vents, Ceiling, Walls, Cable Ladders)
        self._render_room(now)

        # 2. Render 42U Server Racks with Status Beacons, Fans & PDUs
        self._render_server_racks(now)

        # 3. Render Engineer Dual-Screen NOC Workbench
        self._render_workbench(now)

        # 4. Render High-Detail Network Devices inside Racks
        self._render_devices(devices, now, camera=camera)

        # 5. Render 3D Cables with Catenary Sag, Anti-Clipping & Authentic RJ45 Connectors
        self._render_cables(cables, devices, camera=camera)

        # 6. Render Aim Selection Highlight (Crosshair target)
        if focused_dev:
            self._render_highlight(focused_dev, focused_port, now)

    def _compile_room_static_list(self):
        tile_size = 0.6
        ch = self.ceiling_height

        # 1. Raised Floor Grid (Standard Anti-Static Vinyl Floor Tiles)
        glBegin(GL_QUADS)
        for x in range(-10, 10):
            for z in range(-10, 10):
                x0, z0 = x * tile_size, z * tile_size
                x1, z1 = x0 + tile_size, z0 + tile_size

                # Check if this tile is in the Cold Aisle directly in front of the racks
                # Symmetrically 7 tiles wide (-2.1 to +2.1, centered at x = 0.0)
                in_cold_aisle = (-2.1 <= x0 < 2.1) and (-1.2 <= z0 < -0.3)
                if in_cold_aisle:
                    glColor3f(0.70, 0.74, 0.80)
                elif (x + z) % 2 == 0:
                    glColor3f(0.89, 0.91, 0.95)
                else:
                    glColor3f(0.84, 0.87, 0.91)

                glVertex3f(x0, 0.0, z0)
                glVertex3f(x1, 0.0, z0)
                glVertex3f(x1, 0.0, z1)
                glVertex3f(x0, 0.0, z1)
        glEnd()

        # 2. Centered ESD Anti-Static Rubber Floor Runner Mat & Precision Airflow Grilles
        # Continuous runner mat centered at x = 0.0 spanning across all 3 racks (-2.05 to +2.05)
        # Sits flush in front of the rack doors from z = -1.14 to z = -0.50 (centered at z = -0.82)
        mat_x0, mat_x1 = -2.05, 2.05
        mat_z0, mat_z1 = -1.14, -0.50

        # Beveled Safety Yellow ESD Edge Border Trim
        glBegin(GL_QUADS)
        glColor3f(0.92, 0.78, 0.10)
        glVertex3f(mat_x0 - 0.025, 0.0015, mat_z0 - 0.02)
        glVertex3f(mat_x1 + 0.025, 0.0015, mat_z0 - 0.02)
        glVertex3f(mat_x1 + 0.025, 0.0015, mat_z1 + 0.02)
        glVertex3f(mat_x0 - 0.025, 0.0015, mat_z1 + 0.02)

        # Charcoal Heavy-Duty ESD Anti-Static Mat Surface
        glColor3f(0.18, 0.20, 0.24)
        glVertex3f(mat_x0, 0.0022, mat_z0)
        glVertex3f(mat_x1, 0.0022, mat_z0)
        glVertex3f(mat_x1, 0.0022, mat_z1)
        glVertex3f(mat_x0, 0.0022, mat_z1)
        glEnd()

        # Mat Corner Earth Grounding Rivet Studs & Green Ground Wire
        for gx in [mat_x0 + 0.04, mat_x1 - 0.04]:
            self._draw_box(gx, 0.003, mat_z0 + 0.04, 0.016, 0.004, 0.016, (0.85, 0.75, 0.22))
            self._draw_box(gx, 0.003, mat_z0 - 0.01, 0.004, 0.004, 0.06, (0.15, 0.75, 0.25))

        # Precision Perforated Airflow Grilles Centered directly in front of each rack door (rx = -1.4, 0.0, 1.4)
        glLineWidth(1.5)
        for rx in [-1.4, 0.0, 1.4]:
            vx0, vz0 = rx - 0.26, -1.10
            vx1, vz1 = rx + 0.26, -0.56

            # Dark plenum recess underneath
            glBegin(GL_QUADS)
            glColor4f(0.08, 0.10, 0.14, 0.95)
            glVertex3f(vx0, 0.003, vz0)
            glVertex3f(vx1, 0.003, vz0)
            glVertex3f(vx1, 0.003, vz1)
            glVertex3f(vx0, 0.003, vz1)
            glEnd()

            # Galvanized metal honeycomb airflow slats
            glColor3f(0.48, 0.52, 0.60)
            glBegin(GL_LINES)
            for s in range(9):
                sz = vz0 + (s / 8.0) * (vz1 - vz0)
                glVertex3f(vx0 + 0.015, 0.004, sz)
                glVertex3f(vx1 - 0.015, 0.004, sz)
            # Center structural spine
            glVertex3f(rx, 0.0045, vz0)
            glVertex3f(rx, 0.0045, vz1)
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

        # Front Wall facing racks (Z = 6.0)
        glColor3f(0.86, 0.89, 0.93)
        glVertex3f(6.0, 0.0, 6.0)
        glVertex3f(-6.0, 0.0, 6.0)
        glColor3f(0.91, 0.93, 0.96)
        glVertex3f(-6.0, ch, 6.0)
        glVertex3f(6.0, ch, 6.0)

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

        # Enterprise Corporate Blue Feature Wall Stripe around all 4 perimeter walls (Y = 1.25 to 1.35)
        glColor4f(0.0, 0.45, 0.85, 0.95)
        # Back Wall (Z = -5.99)
        glVertex3f(-6.0, 1.25, -5.99); glVertex3f(6.0, 1.25, -5.99)
        glVertex3f(6.0, 1.35, -5.99); glVertex3f(-6.0, 1.35, -5.99)
        # Front Wall (Z = 5.99)
        glVertex3f(6.0, 1.25, 5.99); glVertex3f(-6.0, 1.25, 5.99)
        glVertex3f(-6.0, 1.35, 5.99); glVertex3f(6.0, 1.35, 5.99)
        # Left Wall (X = -5.99)
        glVertex3f(-5.99, 1.25, 6.0); glVertex3f(-5.99, 1.25, -6.0)
        glVertex3f(-5.99, 1.35, -6.0); glVertex3f(-5.99, 1.35, 6.0)
        # Right Wall (X = 5.99)
        glVertex3f(5.99, 1.25, -6.0); glVertex3f(5.99, 1.25, 6.0)
        glVertex3f(5.99, 1.35, 6.0); glVertex3f(5.99, 1.35, -6.0)

        # Dark Slate Baseboard (Y = 0.0 to 0.12) around all 4 perimeter walls
        glColor3f(0.20, 0.23, 0.28)
        # Back Wall
        glVertex3f(-6.0, 0.0, -5.99); glVertex3f(6.0, 0.0, -5.99)
        glVertex3f(6.0, 0.12, -5.99); glVertex3f(-6.0, 0.12, -5.99)
        # Front Wall
        glVertex3f(6.0, 0.0, 5.99); glVertex3f(-6.0, 0.0, 5.99)
        glVertex3f(-6.0, 0.12, 5.99); glVertex3f(6.0, 0.12, 5.99)
        # Left Wall
        glVertex3f(-5.99, 0.0, 6.0); glVertex3f(-5.99, 0.0, -6.0)
        glVertex3f(-5.99, 0.12, -6.0); glVertex3f(-5.99, 0.12, 6.0)
        # Right Wall
        glVertex3f(5.99, 0.0, -6.0); glVertex3f(5.99, 0.0, 6.0)
        glVertex3f(5.99, 0.12, 6.0); glVertex3f(5.99, 0.12, -6.0)
        glEnd()

        # 5. Wall Fixtures: EPO (Emergency Power Off) Button & Keycard Reader Body
        self._draw_box(-5.98, 1.4, -2.0, 0.02, 0.16, 0.14, (0.9, 0.75, 0.1))  # Yellow housing
        self._draw_box(-5.96, 1.4, -2.0, 0.03, 0.08, 0.08, (0.85, 0.15, 0.15))  # Red button
        self._draw_box(-5.98, 1.35, 1.5, 0.02, 0.18, 0.12, (0.15, 0.16, 0.18))

        # 6. Overhead Cable Ladder Trays & Multi-Strand Cable Bundles
        glColor3f(0.75, 0.62, 0.12)  # High-visibility Safety Yellow Trays
        glLineWidth(2.0)
        glBegin(GL_LINES)
        for tx in [-1.4, 0.0, 1.4]:
            glVertex3f(tx - 0.28, 2.55, -4.5)
            glVertex3f(tx - 0.28, 2.55, 2.0)
            glVertex3f(tx + 0.28, 2.55, -4.5)
            glVertex3f(tx + 0.28, 2.55, 2.0)
            for rz in range(-4, 3):
                glVertex3f(tx - 0.28, 2.55, float(rz))
                glVertex3f(tx + 0.28, 2.55, float(rz))
        for bx in [-1.4, 1.4]:
            glVertex3f(-1.4, 2.55, -1.5)
            glVertex3f(1.4, 2.55, -1.5)
        glEnd()

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

        # 7. Enterprise Precision CRAC / Cooling Units (on Right Wall at X = 5.25)
        for crac_z in [-2.0, 1.8]:
            # Main CRAC Enclosure (Charcoal / Titanium Gray)
            self._draw_box(5.25, 1.20, crac_z, 0.95, 2.40, 1.25, (0.16, 0.18, 0.22))
            # Recessed Front Air Intake Grille (Black with dark louvers)
            self._draw_box(4.76, 0.85, crac_z, 0.02, 1.40, 1.10, (0.07, 0.08, 0.10))
            for lvr in range(11):
                ly = 0.25 + lvr * 0.12
                self._draw_box(4.75, ly, crac_z, 0.015, 0.025, 1.06, (0.28, 0.32, 0.38))
            # Climate Telemetry Touchscreen & Controller Panel
            self._draw_box(4.76, 1.85, crac_z, 0.02, 0.32, 0.45, (0.11, 0.13, 0.16))
            self._draw_box(4.75, 1.85, crac_z, 0.015, 0.24, 0.35, (0.02, 0.15, 0.35))  # Deep Blue LCD Screen
            # Schneider / APC Brand Stripe
            self._draw_box(4.76, 2.15, crac_z, 0.02, 0.04, 1.10, (0.0, 0.65, 0.35))
            # Overhead Discharge Plenum Hood connecting to ceiling
            self._draw_box(5.25, 2.65, crac_z, 0.80, 0.50, 1.05, (0.22, 0.25, 0.30))

        # 8. Datacenter Security Double Doors & Emergency Exit (on Right Wall at X = 5.96, Z = -4.2)
        # Door Frame (Heavy-Duty Slate Anodized Aluminum)
        self._draw_box(5.96, 1.18, -4.2, 0.04, 2.36, 1.86, (0.15, 0.17, 0.20))
        # Left & Right Leaf Doors
        for d_z in [-4.63, -3.77]:
            self._draw_box(5.95, 1.15, d_z, 0.03, 2.26, 0.82, (0.75, 0.78, 0.84))
            # Brushed Stainless Steel Kickplate at bottom
            self._draw_box(5.93, 0.20, d_z, 0.015, 0.35, 0.78, (0.58, 0.62, 0.68))
            # Reinforced Safety Glass Window (Narrow Vertical Vision Panel)
            self._draw_box(5.93, 1.45, d_z, 0.02, 0.75, 0.22, (0.12, 0.22, 0.30))
            self._draw_box(5.92, 1.45, d_z, 0.01, 0.70, 0.18, (0.65, 0.82, 0.95))
            # Red Emergency Crash Push-Bar
            self._draw_box(5.90, 0.98, d_z, 0.04, 0.05, 0.70, (0.85, 0.15, 0.15))

        # Overhead Illuminated Green Emergency "EXIT" Sign above double doors
        self._draw_box(5.88, 2.50, -4.2, 0.06, 0.18, 0.46, (0.12, 0.14, 0.18))
        self._draw_box(5.84, 2.50, -4.2, 0.02, 0.14, 0.40, (0.10, 0.92, 0.30))

        # Biometric Hand Scanner & Badge Reader by Security Doors
        self._draw_box(5.96, 1.35, -3.15, 0.03, 0.22, 0.15, (0.12, 0.14, 0.18))
        self._draw_box(5.94, 1.38, -3.15, 0.02, 0.08, 0.08, (0.0, 0.65, 0.95))

        # 9. Clean-Agent Fire Suppression System (FM-200 / Novec Cylinders on Left Wall)
        for cyl_z in [-4.3, -3.8]:
            self._draw_box(-5.75, 0.95, cyl_z, 0.34, 1.65, 0.34, (0.85, 0.12, 0.12))  # Cylinder body
            self._draw_box(-5.75, 1.82, cyl_z, 0.24, 0.10, 0.24, (0.70, 0.10, 0.10))  # Dome cap
            self._draw_box(-5.75, 1.92, cyl_z, 0.10, 0.12, 0.10, (0.75, 0.65, 0.20))  # Brass discharge valve
            self._draw_box(-5.86, 0.65, cyl_z, 0.15, 0.04, 0.38, (0.25, 0.28, 0.32))
            self._draw_box(-5.86, 1.45, cyl_z, 0.15, 0.04, 0.38, (0.25, 0.28, 0.32))

        # Chrome High-Pressure Manifold Pipe connecting to ceiling
        self._draw_box(-5.75, 2.05, -4.05, 0.06, 0.06, 0.65, (0.80, 0.84, 0.90))
        self._draw_box(-5.75, 2.45, -4.05, 0.06, 0.75, 0.06, (0.80, 0.84, 0.90))

        # Caution Discharge System Warning Sign
        self._draw_box(-5.97, 1.95, -3.2, 0.02, 0.26, 0.36, (0.95, 0.85, 0.10))
        self._draw_box(-5.96, 1.95, -3.2, 0.01, 0.20, 0.30, (0.10, 0.10, 0.12))

        # Wall-Mounted CO2 Fire Extinguisher
        self._draw_box(-5.95, 1.05, -3.2, 0.15, 0.65, 0.15, (0.88, 0.10, 0.10))
        self._draw_box(-5.94, 1.42, -3.2, 0.08, 0.10, 0.08, (0.15, 0.16, 0.18))
        self._draw_box(-5.92, 1.25, -3.12, 0.04, 0.25, 0.04, (0.10, 0.10, 0.12))

        # 10. Large Magnetic Network Architecture Whiteboard (Facing Workbench on Left Wall)
        self._draw_box(-5.98, 1.65, 0.5, 0.02, 1.18, 2.24, (0.65, 0.68, 0.74))
        self._draw_box(-5.96, 1.65, 0.5, 0.01, 1.10, 2.16, (0.96, 0.97, 0.99))
        self._draw_box(-5.94, 1.06, 0.5, 0.06, 0.02, 2.20, (0.50, 0.54, 0.60))

        # Markers on tray (Blue, Red, Green, Black) and Felt Eraser
        self._draw_box(-5.92, 1.08, 0.15, 0.015, 0.015, 0.12, (0.0, 0.45, 0.95))
        self._draw_box(-5.92, 1.08, 0.30, 0.015, 0.015, 0.12, (0.90, 0.15, 0.15))
        self._draw_box(-5.92, 1.08, 0.45, 0.015, 0.015, 0.12, (0.05, 0.80, 0.35))
        self._draw_box(-5.92, 1.08, 0.60, 0.015, 0.015, 0.12, (0.12, 0.12, 0.15))
        self._draw_box(-5.92, 1.09, 0.85, 0.040, 0.030, 0.14, (0.25, 0.25, 0.28))

        # Sketched Enterprise Network Topology Diagram on Whiteboard
        self._draw_box(-5.95, 1.95, 0.5, 0.005, 0.10, 0.28, (0.15, 0.45, 0.85))
        self._draw_box(-5.95, 1.65, 0.15, 0.005, 0.08, 0.22, (0.0, 0.68, 0.85))
        self._draw_box(-5.95, 1.65, 0.85, 0.005, 0.08, 0.22, (0.0, 0.68, 0.85))
        self._draw_box(-5.95, 1.35, -0.15, 0.005, 0.06, 0.18, (0.10, 0.70, 0.40))
        self._draw_box(-5.95, 1.35, 0.45, 0.005, 0.06, 0.18, (0.10, 0.70, 0.40))
        self._draw_box(-5.95, 1.35, 1.05, 0.005, 0.06, 0.18, (0.10, 0.70, 0.40))
        glLineWidth(2.0)
        glColor3f(0.20, 0.25, 0.35)
        glBegin(GL_LINES)
        glVertex3f(-5.94, 1.90, 0.5); glVertex3f(-5.94, 1.70, 0.15)
        glVertex3f(-5.94, 1.90, 0.5); glVertex3f(-5.94, 1.70, 0.85)
        glColor3f(0.85, 0.20, 0.20)
        glVertex3f(-5.94, 1.65, 0.26); glVertex3f(-5.94, 1.65, 0.74)
        glColor3f(0.15, 0.45, 0.85)
        glVertex3f(-5.94, 1.60, 0.15); glVertex3f(-5.94, 1.40, -0.15)
        glVertex3f(-5.94, 1.60, 0.15); glVertex3f(-5.94, 1.40, 0.45)
        glVertex3f(-5.94, 1.60, 0.85); glVertex3f(-5.94, 1.40, 0.45)
        glVertex3f(-5.94, 1.60, 0.85); glVertex3f(-5.94, 1.40, 1.05)
        glEnd()

        # Sticky Notes on Whiteboard
        self._draw_box(-5.95, 1.92, 1.15, 0.004, 0.08, 0.08, (0.95, 0.90, 0.20))
        self._draw_box(-5.95, 1.80, 1.25, 0.004, 0.08, 0.08, (0.95, 0.40, 0.65))
        self._draw_box(-5.95, 1.92, -0.25, 0.004, 0.08, 0.08, (0.45, 0.95, 0.45))

        # 11. 3-Phase Main Power Distribution Sub-Panel (on Back Wall at X = -4.0, Z = -5.96)
        self._draw_box(-4.0, 1.45, -5.96, 0.75, 1.15, 0.16, (0.72, 0.75, 0.80))
        self._draw_box(-4.0, 1.45, -5.87, 0.71, 1.09, 0.02, (0.64, 0.67, 0.72))
        self._draw_box(-3.85, 1.65, -5.85, 0.12, 0.12, 0.03, (0.92, 0.78, 0.10))
        self._draw_box(-3.85, 1.65, -5.83, 0.04, 0.09, 0.03, (0.85, 0.15, 0.15))
        self._draw_box(-4.15, 1.65, -5.85, 0.16, 0.12, 0.02, (0.10, 0.12, 0.15))
        self._draw_box(-4.15, 1.65, -5.84, 0.13, 0.08, 0.01, (0.05, 0.85, 0.35))
        self._draw_box(-4.0, 1.25, -5.85, 0.14, 0.12, 0.01, (0.95, 0.82, 0.08))

        # 12. Overhead Industrial Galvanized HVAC Supply Duct & Fire Sprinkler Pipes
        self._draw_box(3.6, 2.78, 0.0, 0.75, 0.36, 11.0, (0.75, 0.78, 0.84))
        for rz_d in range(-5, 6):
            self._draw_box(3.6, 2.78, float(rz_d), 0.77, 0.38, 0.03, (0.55, 0.58, 0.65))

        glLineWidth(2.5)
        glColor3f(0.85, 0.15, 0.15)
        glBegin(GL_LINES)
        glVertex3f(-5.5, 2.90, 0.5); glVertex3f(5.5, 2.90, 0.5)
        glVertex3f(-5.5, 2.90, -3.0); glVertex3f(5.5, 2.90, -3.0)
        glEnd()
        for sp_x in [-4.0, -2.0, 0.0, 2.0, 4.0]:
            for sp_z in [0.5, -3.0]:
                self._draw_box(sp_x, 2.86, sp_z, 0.03, 0.08, 0.03, (0.85, 0.15, 0.15))
                self._draw_box(sp_x, 2.81, sp_z, 0.04, 0.02, 0.04, (0.85, 0.75, 0.20))

        # 13. Safety Floor Markings (Yellow/Black Hazard Chevrons in Front of CRACs)
        for crac_z in [-2.0, 1.8]:
            for chv in range(6):
                cz = crac_z - 0.50 + chv * 0.20
                col = (0.92, 0.82, 0.08) if chv % 2 == 0 else (0.12, 0.13, 0.16)
                glBegin(GL_QUADS)
                glColor3f(*col)
                glVertex3f(4.20, 0.002, cz - 0.08)
                glVertex3f(4.70, 0.002, cz - 0.08)
                glVertex3f(4.70, 0.002, cz + 0.08)
                glVertex3f(4.20, 0.002, cz + 0.08)
                glEnd()

        # 14. Left Wall Datacenter Infrastructure & Tool Station (X = -5.98, Z = 2.0 to 5.7)
        # A. Architectural Datacenter Floorplan & Rack Layout Blueprint (Z = 2.45)
        self._draw_box(-5.98, 1.65, 2.45, 0.02, 1.15, 1.45, (0.68, 0.72, 0.78))
        self._draw_box(-5.96, 1.65, 2.45, 0.01, 1.08, 1.38, (0.05, 0.18, 0.38))
        self._draw_box(-5.95, 2.08, 2.45, 0.005, 0.08, 1.30, (0.02, 0.12, 0.28))
        # 4 Standoff mounts
        for cz in [1.85, 3.05]:
            for cy in [1.16, 2.14]:
                self._draw_box(-5.94, cy, cz, 0.025, 0.035, 0.035, (0.85, 0.88, 0.92))
        # Blueprint grid and layout markings
        glColor3f(0.20, 0.55, 0.85)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        for bz in range(7):
            gz = 1.95 + bz * 0.16
            glVertex3f(-5.945, 1.25, gz); glVertex3f(-5.945, 2.00, gz)
        for by in range(5):
            gy = 1.25 + by * 0.18
            glVertex3f(-5.945, gy, 1.95); glVertex3f(-5.945, gy, 2.95)
        # Rack footprint boxes in blueprint
        glColor3f(0.85, 0.95, 1.0)
        for r_bx in [2.20, 2.45, 2.70]:
            glVertex3f(-5.94, 1.50, r_bx - 0.08); glVertex3f(-5.94, 1.50, r_bx + 0.08)
            glVertex3f(-5.94, 1.50, r_bx + 0.08); glVertex3f(-5.94, 1.75, r_bx + 0.08)
            glVertex3f(-5.94, 1.75, r_bx + 0.08); glVertex3f(-5.94, 1.75, r_bx - 0.08)
            glVertex3f(-5.94, 1.75, r_bx - 0.08); glVertex3f(-5.94, 1.50, r_bx - 0.08)
        glEnd()

        # B. 6U Wall-Mount Fiber Optic Distribution & Patching Enclosure (ODF) (Z = 3.55)
        self._draw_box(-5.88, 1.70, 3.55, 0.22, 0.44, 0.58, (0.16, 0.18, 0.22))
        self._draw_box(-5.76, 1.70, 3.55, 0.01, 0.38, 0.52, (0.10, 0.22, 0.32))
        self._draw_box(-5.75, 1.70, 3.76, 0.02, 0.05, 0.025, (0.75, 0.78, 0.82))
        # Interior fiber adapter panels: OM4 Aqua & OS2 Single-mode Blue
        self._draw_box(-5.84, 1.78, 3.55, 0.04, 0.07, 0.44, (0.08, 0.10, 0.12))
        self._draw_box(-5.84, 1.62, 3.55, 0.04, 0.07, 0.44, (0.08, 0.10, 0.12))
        for ci in range(8):
            fz = 3.38 + ci * 0.048
            self._draw_box(-5.82, 1.78, fz, 0.015, 0.03, 0.032, (0.15, 0.80, 0.82))
            self._draw_box(-5.82, 1.62, fz, 0.015, 0.03, 0.032, (0.10, 0.45, 0.95))
        # Laser Caution warning label
        self._draw_box(-5.75, 1.84, 3.36, 0.005, 0.05, 0.05, (0.95, 0.85, 0.05))

        # C. Network Field Operations Tool Pegboard & Equipment Station (Z = 4.65)
        self._draw_box(-5.97, 1.55, 4.65, 0.02, 1.10, 1.25, (0.32, 0.35, 0.40))
        self._draw_box(-5.96, 1.55, 4.65, 0.015, 1.14, 1.29, (0.65, 0.68, 0.74))
        # Pegboard holes pattern
        glColor3f(0.18, 0.20, 0.24)
        glPointSize(2.0)
        glBegin(GL_POINTS)
        for py_i in range(8):
            for pz_i in range(12):
                glVertex3f(-5.955, 1.10 + py_i * 0.12, 4.15 + pz_i * 0.09)
        glEnd()

        # Fluke Networks DSX Cable Certifier & Tester
        self._draw_box(-5.93, 1.75, 4.38, 0.04, 0.28, 0.16, (0.95, 0.82, 0.08))
        self._draw_box(-5.91, 1.75, 4.38, 0.02, 0.25, 0.14, (0.18, 0.20, 0.24))
        self._draw_box(-5.90, 1.80, 4.38, 0.005, 0.11, 0.11, (0.10, 0.55, 0.85))
        self._draw_box(-5.895, 1.80, 4.38, 0.002, 0.04, 0.07, (0.15, 0.92, 0.35))
        self._draw_box(-5.90, 1.68, 4.38, 0.005, 0.06, 0.10, (0.35, 0.38, 0.42))

        # Dual Cable Spool Dispenser (Blue Cat6 + Yellow Single-mode Fiber)
        self._draw_box(-5.88, 1.32, 4.45, 0.16, 0.04, 0.48, (0.25, 0.28, 0.32))
        # Blue Cat6 spool
        self._draw_box(-5.88, 1.32, 4.28, 0.18, 0.24, 0.02, (0.62, 0.48, 0.32))
        self._draw_box(-5.88, 1.32, 4.42, 0.18, 0.24, 0.02, (0.62, 0.48, 0.32))
        self._draw_box(-5.88, 1.32, 4.35, 0.15, 0.20, 0.12, (0.05, 0.42, 0.92))
        # Yellow Fiber spool
        self._draw_box(-5.88, 1.32, 4.54, 0.18, 0.24, 0.02, (0.62, 0.48, 0.32))
        self._draw_box(-5.88, 1.32, 4.68, 0.18, 0.24, 0.02, (0.62, 0.48, 0.32))
        self._draw_box(-5.88, 1.32, 4.61, 0.15, 0.20, 0.12, (0.95, 0.85, 0.12))

        # Hand tools (Crimper & Punch-down tool)
        self._draw_box(-5.93, 1.76, 4.72, 0.02, 0.22, 0.06, (0.95, 0.42, 0.05))
        self._draw_box(-5.93, 1.76, 4.86, 0.02, 0.18, 0.04, (0.92, 0.80, 0.10))
        # Parts storage bin with RJ45 jacks
        self._draw_box(-5.92, 1.52, 4.82, 0.06, 0.14, 0.28, (0.75, 0.80, 0.86))
        for bi in range(4):
            self._draw_box(-5.90, 1.52, 4.72 + bi * 0.065, 0.04, 0.08, 0.05, (0.15 + bi * 0.2, 0.50, 0.85 - bi * 0.15))

        # D. Health, Safety & ISO Certification Station (Z = 5.50)
        self._draw_box(-5.96, 1.55, 5.50, 0.06, 0.45, 0.36, (0.94, 0.95, 0.96))
        self._draw_box(-5.92, 1.55, 5.50, 0.01, 0.18, 0.06, (0.10, 0.75, 0.30))
        self._draw_box(-5.92, 1.55, 5.50, 0.01, 0.06, 0.18, (0.10, 0.75, 0.30))
        # Emergency Eyewash Station
        self._draw_box(-5.88, 1.05, 5.50, 0.20, 0.16, 0.26, (0.15, 0.75, 0.30))
        self._draw_box(-5.88, 1.15, 5.45, 0.04, 0.04, 0.04, (0.95, 0.85, 0.10))
        self._draw_box(-5.88, 1.15, 5.55, 0.04, 0.04, 0.04, (0.95, 0.85, 0.10))
        # Tier-IV ISO 27001 Certification plaque
        self._draw_box(-5.97, 1.95, 5.50, 0.015, 0.28, 0.36, (0.22, 0.24, 0.28))
        self._draw_box(-5.96, 1.95, 5.50, 0.005, 0.24, 0.32, (0.92, 0.90, 0.82))
        self._draw_box(-5.95, 1.88, 5.60, 0.002, 0.05, 0.05, (0.85, 0.72, 0.20))

        # 15. Front Wall NOC Command Center, Video Wall & Airlock (Z = 6.0)
        # Note: Wall is at Z = 6.0. Room interior is at smaller Z (facing -Z towards camera).
        # A. NOC Command Center Panoramic Glass Observation Window (X = 0.90, Y = 1.65)
        # 1. Dark titanium outer window frame surround (4 border pieces)
        self._draw_box(0.90, 2.41, 5.93, 3.24, 0.07, 0.05, (0.18, 0.20, 0.25))  # Top
        self._draw_box(0.90, 0.89, 5.93, 3.24, 0.07, 0.05, (0.18, 0.20, 0.25))  # Bottom
        self._draw_box(-0.68, 1.65, 5.93, 0.08, 1.55, 0.05, (0.18, 0.20, 0.25)) # Left
        self._draw_box(2.48, 1.65, 5.93, 0.08, 1.55, 0.05, (0.18, 0.20, 0.25))  # Right
        self._draw_box(0.90, 1.65, 5.92, 0.06, 1.45, 0.04, (0.22, 0.25, 0.30))  # Center vertical mullion

        # 2. Command Center interior room backdrop (Deep high-tech twilight navy)
        self._draw_box(0.90, 1.65, 5.97, 3.08, 1.45, 0.01, (0.04, 0.08, 0.18))

        # 3. Inside NOC: Global Backbone Fiber World Map Screen (Z = 5.96)
        self._draw_box(0.90, 1.82, 5.96, 2.92, 0.92, 0.005, (0.02, 0.05, 0.12))

        # Continents and Network Backbone Arcs
        continents = [
            (-0.35, 1.95, 0.28, 0.18),  # North America
            (-0.25, 1.55, 0.16, 0.22),  # South America
            (0.30, 2.05, 0.22, 0.16),   # Europe
            (0.35, 1.60, 0.22, 0.24),   # Africa
            (1.45, 1.95, 0.55, 0.26),   # Asia
            (1.90, 1.35, 0.22, 0.14),   # Australia
        ]
        for cx_c, cy_c, cw_c, ch_c in continents:
            self._draw_box(cx_c, cy_c, 5.958, cw_c, ch_c, 0.002, (0.06, 0.22, 0.45))

        glColor3f(0.0, 0.82, 1.0)
        glLineWidth(2.0)
        glBegin(GL_LINES)
        hub_coords = [
            (-0.35, 1.95),  # Americas
            (0.30, 2.05),   # Europe
            (0.95, 1.85),   # Middle East
            (1.55, 1.95),   # Asia / Bangkok
            (2.05, 1.70),   # East Asia / Pacific
            (1.90, 1.35),   # Australia
        ]
        for i in range(len(hub_coords) - 1):
            h1, h2 = hub_coords[i], hub_coords[i + 1]
            glVertex3f(h1[0], h1[1], 5.955); glVertex3f(h2[0], h2[1], 5.955)
        # Trans-pacific link
        glVertex3f(-0.35, 1.95, 5.955); glVertex3f(2.05, 1.70, 5.955)
        # Trans-atlantic link
        glVertex3f(-0.35, 1.95, 5.955); glVertex3f(0.30, 2.05, 5.955)
        glEnd()

        # Glowing neon data hubs
        for hx, hy in hub_coords:
            self._draw_box(hx, hy, 5.952, 0.045, 0.045, 0.004, (0.15, 0.98, 0.70))

        # NOC Telemetry Wall Displays inside command center
        self._draw_box(0.05, 1.46, 5.955, 0.68, 0.18, 0.004, (0.0, 0.45, 0.80))
        self._draw_box(1.75, 1.46, 5.955, 0.68, 0.18, 0.004, (0.05, 0.65, 0.40))

        # NOC Operator Workstations Silhouettes (Desks & dual glowing curved monitors)
        for desk_x in [0.15, 1.65]:
            self._draw_box(desk_x, 1.06, 5.95, 0.80, 0.26, 0.015, (0.08, 0.10, 0.14))
            self._draw_box(desk_x - 0.16, 1.25, 5.945, 0.24, 0.14, 0.005, (0.0, 0.75, 0.95))
            self._draw_box(desk_x + 0.16, 1.25, 5.945, 0.24, 0.14, 0.005, (0.10, 0.85, 0.40))

        # 4. Architectural Observation Glass with High-Tech Cyan Tint & Light Sheen
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glBegin(GL_QUADS)
        glColor4f(0.08, 0.35, 0.65, 0.15)
        glVertex3f(-0.64, 0.92, 5.925); glVertex3f(2.44, 0.92, 5.925)
        glVertex3f(2.44, 2.38, 5.925); glVertex3f(-0.64, 2.38, 5.925)
        # Reflection highlight streak
        glColor4f(1.0, 1.0, 1.0, 0.15)
        glVertex3f(-0.25, 0.92, 5.922); glVertex3f(0.05, 0.92, 5.922)
        glVertex3f(1.45, 2.38, 5.922); glVertex3f(1.15, 2.38, 5.922)
        glEnd()
        glDisable(GL_BLEND)

        # B. Synchronized World Time Digital Clock Array (above observation window, Y = 2.65)
        clock_zones = [
            (-0.35, (0.15, 0.95, 0.35)),
            (0.35,  (0.10, 0.85, 0.98)),
            (1.05,  (0.95, 0.85, 0.15)),
            (1.75,  (0.98, 0.55, 0.10))
        ]
        for cx, led_col in clock_zones:
            # Housing (Z = 5.92)
            self._draw_box(cx, 2.65, 5.92, 0.54, 0.18, 0.04, (0.10, 0.12, 0.15))
            # Bezel recess
            self._draw_box(cx, 2.67, 5.895, 0.46, 0.08, 0.005, (0.04, 0.05, 0.07))
            # Segmented LED digits
            for d in range(6):
                dx = cx - 0.18 + d * 0.072
                self._draw_box(dx, 2.67, 5.890, 0.04, 0.06, 0.002, led_col)
            # Label badge
            self._draw_box(cx, 2.59, 5.895, 0.24, 0.035, 0.002, (0.75, 0.78, 0.84))
        # NTP Stratum-1 badge
        self._draw_box(2.25, 2.65, 5.92, 0.24, 0.12, 0.03, (0.05, 0.35, 0.65))

        # C. 75" Enterprise Datacenter Infrastructure Video Wall (DCIM Telemetry) (X = -3.8)
        self._draw_box(-3.80, 1.72, 5.96, 0.45, 0.55, 0.04, (0.25, 0.28, 0.32))  # Wall mount
        self._draw_box(-3.80, 1.72, 5.92, 1.85, 1.15, 0.04, (0.12, 0.13, 0.16))  # Bezel
        self._draw_box(-3.80, 1.72, 5.895, 1.78, 1.08, 0.005, (0.06, 0.09, 0.15)) # Screen
        # DCIM header bar
        self._draw_box(-3.80, 2.18, 5.890, 1.74, 0.08, 0.002, (0.0, 0.38, 0.78))
        # Tile 1: Facility PUE Gauge (1.18 PUE - Green Optimal)
        self._draw_box(-4.25, 1.92, 5.890, 0.72, 0.36, 0.002, (0.09, 0.13, 0.22))
        self._draw_box(-4.25, 1.92, 5.886, 0.24, 0.24, 0.002, (0.10, 0.85, 0.35))
        # Tile 2: Thermal & Climate Environmental Map (19.4°C / 46% RH)
        self._draw_box(-3.35, 1.92, 5.890, 0.72, 0.36, 0.002, (0.09, 0.13, 0.22))
        self._draw_box(-3.35, 1.92, 5.886, 0.24, 0.14, 0.002, (0.0, 0.65, 0.95))
        # Tile 3: Rack Compute Load & Network Throughput
        self._draw_box(-3.80, 1.42, 5.890, 1.62, 0.50, 0.002, (0.09, 0.13, 0.22))
        for r_bar in range(3):
            bx = -4.30 + r_bar * 0.50
            self._draw_box(bx, 1.40, 5.886, 0.32, 0.28, 0.002, (0.12, 0.16, 0.26))
            fill_h = 0.12 + r_bar * 0.06
            self._draw_box(bx, 1.26 + fill_h / 2.0, 5.882, 0.26, fill_h, 0.002, (0.10, 0.80, 0.45))

        # D. High-Security Airlock / Mantrap Entrance Double Doors (X = 4.30)
        # Door frame architrave (Z = 5.95, d = 0.06 -> front face at 5.92)
        self._draw_box(4.30, 1.25, 5.95, 1.88, 2.52, 0.06, (0.16, 0.18, 0.22))
        # Door leaves (Z = 5.91, d = 0.03 -> front face at 5.895)
        for d_x in [3.91, 4.69]:
            self._draw_box(d_x, 1.20, 5.91, 0.84, 2.38, 0.03, (0.76, 0.80, 0.86))
            # Stainless kickplate
            self._draw_box(d_x, 0.22, 5.89, 0.80, 0.38, 0.005, (0.58, 0.62, 0.68))
            # Vision safety glass window
            self._draw_box(d_x, 1.45, 5.89, 0.20, 0.90, 0.005, (0.15, 0.30, 0.45))
            self._draw_box(d_x, 1.45, 5.888, 0.16, 0.84, 0.002, (0.65, 0.85, 0.98))
        # Stainless steel long vertical pull handles
        self._draw_box(4.25, 1.15, 5.86, 0.025, 0.55, 0.025, (0.90, 0.92, 0.95))
        self._draw_box(4.35, 1.15, 5.86, 0.025, 0.55, 0.025, (0.90, 0.92, 0.95))
        # Biometric Palm/Fingerprint Terminal
        self._draw_box(5.35, 1.35, 5.92, 0.14, 0.24, 0.04, (0.12, 0.14, 0.18))
        self._draw_box(5.35, 1.40, 5.895, 0.06, 0.07, 0.005, (0.0, 0.70, 0.95))
        self._draw_box(5.35, 1.27, 5.895, 0.08, 0.08, 0.005, (0.28, 0.30, 0.35))
        # Emergency door release station
        self._draw_box(5.35, 1.05, 5.92, 0.12, 0.14, 0.04, (0.10, 0.70, 0.30))
        # Overhead illuminated status banner
        self._draw_box(4.30, 2.62, 5.92, 0.72, 0.16, 0.04, (0.12, 0.14, 0.18))
        self._draw_box(4.30, 2.62, 5.895, 0.64, 0.11, 0.005, (0.05, 0.85, 0.35))

        # 16. Right Wall High-Power Switchgear Cabinet & Environmental Telemetry Pod (X = 5.98, Z = 2.8 to 5.5)
        # 480V 3-Phase Main Switchgear & ATS Cabinet (Z = 3.60)
        self._draw_box(5.88, 1.35, 3.60, 0.22, 2.20, 0.95, (0.72, 0.75, 0.80))
        self._draw_box(5.76, 1.35, 3.38, 0.015, 2.12, 0.44, (0.64, 0.67, 0.72))
        self._draw_box(5.76, 1.35, 3.82, 0.015, 2.12, 0.44, (0.64, 0.67, 0.72))
        # Rotary disconnect switch
        self._draw_box(5.74, 1.70, 3.82, 0.04, 0.12, 0.12, (0.85, 0.15, 0.15))
        # Power Quality digital meter
        self._draw_box(5.75, 1.95, 3.38, 0.01, 0.18, 0.22, (0.10, 0.12, 0.16))
        self._draw_box(5.74, 1.95, 3.38, 0.005, 0.12, 0.16, (0.05, 0.35, 0.85))
        # 3-Phase neon indicator lamps
        self._draw_box(5.75, 2.15, 3.28, 0.02, 0.03, 0.03, (0.95, 0.15, 0.15))
        self._draw_box(5.75, 2.15, 3.38, 0.02, 0.03, 0.03, (0.95, 0.85, 0.10))
        self._draw_box(5.75, 2.15, 3.48, 0.02, 0.03, 0.03, (0.15, 0.45, 0.95))
        # Arc-flash hazard placard
        self._draw_box(5.75, 1.45, 3.38, 0.005, 0.14, 0.18, (0.95, 0.82, 0.08))

        # Datacenter Environmental Telemetry Pod (Z = 4.80)
        self._draw_box(5.95, 1.55, 4.80, 0.06, 0.35, 0.25, (0.92, 0.94, 0.96))
        self._draw_box(5.91, 1.48, 4.80, 0.02, 0.12, 0.18, (0.18, 0.20, 0.24))
        self._draw_box(5.91, 1.65, 4.80, 0.01, 0.02, 0.02, (0.10, 0.95, 0.35))

    def _render_room(self, now):
        if self.room_display_list is None:
            self._init_display_lists()
        glCallList(self.room_display_list)

        # Dynamic elements:
        # 1. Subtle blue chilled-air glow from plenum
        for rx in [-1.4, 0.0, 1.4]:
            vx0, vz0 = rx - 0.26, -1.10
            vx1, vz1 = rx + 0.26, -0.56
            pulse = 0.65 + 0.15 * math.sin(now * 2.0 + rx)
            glBegin(GL_QUADS)
            glColor4f(0.0, 0.65, 0.95, 0.12 * pulse)
            glVertex3f(vx0, 0.005, vz0)
            glVertex3f(vx1, 0.005, vz0)
            glVertex3f(vx1, 0.005, vz1)
            glVertex3f(vx0, 0.005, vz1)
            glEnd()

        # 2. RFID status LED blink
        rfid_blink = int(now * 2) % 2 == 0
        rfid_color = (0.1, 0.95, 0.2) if rfid_blink else (0.05, 0.3, 0.1)
        self._draw_box(-5.96, 1.40, 1.5, 0.02, 0.015, 0.04, rfid_color)

        # 3. CRAC Units Live LED Status & Climate Temperature Indicators
        for crac_z in [-2.0, 1.8]:
            crac_pulse = 0.85 + 0.15 * math.sin(now * 3.0 + crac_z)
            self._draw_box(4.74, 1.95, crac_z + 0.12, 0.01, 0.012, 0.012, (0.0, 0.98 * crac_pulse, 0.35 * crac_pulse))
            self._draw_box(4.74, 1.95, crac_z - 0.12, 0.01, 0.012, 0.012, (0.0, 0.80 * crac_pulse, 1.0 * crac_pulse))

        # 4. Emergency EXIT Sign Soft Green Ambient Glow
        exit_pulse = 0.92 + 0.08 * math.sin(now * 1.5)
        self._draw_box(5.83, 2.50, -4.2, 0.01, 0.12, 0.36, (0.15 * exit_pulse, 0.98 * exit_pulse, 0.35 * exit_pulse))

    def _compile_server_racks_static_list(self):
        w = self.rack_width   # 0.60m
        h = self.rack_height  # 2.10m
        d = self.rack_depth   # 0.80m
        hw, hh, hd = w / 2.0, h / 2.0, d / 2.0

        for r in self.racks:
            rx, rz = r["x"], r["z"]
            glPushMatrix()
            glTranslatef(rx, 0.0, rz)

            # 1. HEAVY-DUTY BASE CHASSIS, LEVELING FEET, WHEELS & SEISMIC FLOOR ANCHORS
            self._draw_box(0.0, 0.025, 0.0, w, 0.05, d, (0.08, 0.09, 0.11))
            self._draw_box(0.0, 0.052, 0.0, w - 0.03, 0.008, d - 0.03, (0.13, 0.14, 0.17))

            for fx in [-hw + 0.04, hw - 0.04]:
                for fz in [-hd + 0.04, hd - 0.04]:
                    self._draw_box(fx, 0.012, fz, 0.016, 0.024, 0.016, (0.62, 0.65, 0.70))
                    self._draw_box(fx, 0.016, fz, 0.026, 0.008, 0.026, (0.75, 0.78, 0.82))
                    self._draw_box(fx, 0.004, fz, 0.045, 0.008, 0.045, (0.22, 0.24, 0.28))

            for cx in [-hw + 0.07, hw - 0.07]:
                for cz in [-hd + 0.07, hd - 0.07]:
                    self._draw_box(cx, 0.018, cz, 0.025, 0.026, 0.040, (0.16, 0.17, 0.20))
                    self._draw_box(cx, 0.010, cz, 0.020, 0.020, 0.032, (0.35, 0.18, 0.12))

            for sx in [-hw - 0.012, hw + 0.012]:
                self._draw_box(sx, 0.012, hd - 0.02, 0.028, 0.024, 0.065, (0.92, 0.76, 0.10))
                self._draw_box(sx, 0.025, hd - 0.02, 0.012, 0.006, 0.012, (0.85, 0.88, 0.92))

            self._draw_box(-hw + 0.02, 0.016, hd + 0.008, 0.014, 0.030, 0.004, (0.82, 0.52, 0.20))
            self._draw_box(-hw + 0.02, 0.008, hd + 0.012, 0.018, 0.006, 0.012, (0.78, 0.65, 0.22))

            # 2. FOUR VERTICAL CORNER POSTS & REINFORCED CHASSIS FRAME
            post_w = 0.042
            corners = [
                (-hw + post_w/2, -hd + post_w/2),
                ( hw - post_w/2, -hd + post_w/2),
                (-hw + post_w/2,  hd - post_w/2),
                ( hw - post_w/2,  hd - post_w/2)
            ]
            for cx, cz in corners:
                self._draw_box(cx, hh, cz, post_w, h - 0.06, post_w, (0.10, 0.11, 0.13))
                self._draw_box(cx, hh, cz, post_w - 0.012, h - 0.08, post_w - 0.012, (0.14, 0.15, 0.18))

            # 3. SIDE PANELS WITH PERIMETER BEVEL & VENTILATION LOUVERS
            for side_x, side_sign in [(-hw + 0.005, -1), (hw - 0.005, 1)]:
                self._draw_box(side_x, hh, 0.0, 0.010, h - 0.12, d - 0.08, (0.12, 0.13, 0.16))
                self._draw_box(side_x, hh, 0.0, 0.014, h - 0.10, d - 0.06, (0.09, 0.10, 0.12))
                self._draw_box(side_x + 0.002 * side_sign, hh, 0.0, 0.004, 0.045, 0.035, (0.24, 0.26, 0.30))

                for louver_y in [0.35, h - 0.35]:
                    self._draw_box(side_x + 0.001 * side_sign, louver_y, 0.0, 0.006, 0.16, d - 0.24, (0.07, 0.08, 0.10))
                    for ls in range(5):
                        ly = louver_y - 0.06 + ls * 0.03
                        self._draw_box(side_x + 0.003 * side_sign, ly, 0.0, 0.004, 0.005, d - 0.26, (0.20, 0.22, 0.26))

            # 4. FRONT DOOR APERTURE FRAME, STAINLESS HINGES & SMART-LOCK SWING HANDLE
            door_front_z = hd + 0.008
            stile_w = 0.048

            self._draw_box(-hw + stile_w/2, hh, door_front_z, stile_w, h - 0.06, 0.016, (0.13, 0.14, 0.17))
            self._draw_box(hw - stile_w/2, hh, door_front_z, stile_w, h - 0.06, 0.016, (0.13, 0.14, 0.17))
            self._draw_box(0.0, 0.026, door_front_z, w, 0.050, 0.018, (0.15, 0.16, 0.19))

            for hy in [0.45, 1.10, 1.75]:
                self._draw_box(-hw + 0.006, hy, door_front_z + 0.008, 0.014, 0.055, 0.014, (0.65, 0.68, 0.74))
                self._draw_box(-hw + 0.006, hy, door_front_z + 0.015, 0.008, 0.065, 0.008, (0.85, 0.88, 0.92))
                for h_bolt in [-0.018, 0.018]:
                    self._draw_box(-hw + 0.018, hy + h_bolt, door_front_z + 0.008, 0.005, 0.005, 0.003, (0.85, 0.88, 0.92))

            lock_y = 1.05
            lock_x = hw - 0.024
            self._draw_box(lock_x, lock_y, door_front_z + 0.006, 0.032, 0.22, 0.010, (0.07, 0.08, 0.10))
            self._draw_box(lock_x, lock_y - 0.02, door_front_z + 0.014, 0.018, 0.14, 0.012, (0.72, 0.76, 0.82))
            self._draw_box(lock_x, lock_y + 0.065, door_front_z + 0.015, 0.015, 0.022, 0.008, (0.28, 0.30, 0.35))
            self._draw_box(lock_x, lock_y + 0.095, door_front_z + 0.012, 0.020, 0.024, 0.004, (0.05, 0.12, 0.18))

            # 5. ILLUMINATED DATACENTER CANOPY MARQUEE & CLIMATE TELEMETRY POD
            canopy_y = h - 0.075
            canopy_z = hd + 0.014
            self._draw_box(0.0, canopy_y, canopy_z, 0.48, 0.095, 0.018, (0.06, 0.09, 0.14))
            self._draw_box(0.0, canopy_y + 0.042, canopy_z + 0.008, 0.46, 0.003, 0.003, (0.0, 0.80, 1.0))
            self._draw_box(0.0, canopy_y - 0.042, canopy_z + 0.008, 0.46, 0.003, 0.003, (0.0, 0.80, 1.0))
            self._draw_box(-0.06, canopy_y, canopy_z + 0.009, 0.24, 0.055, 0.004, (0.04, 0.18, 0.34))

            self._draw_box(0.145, canopy_y, canopy_z + 0.008, 0.125, 0.060, 0.004, (0.08, 0.10, 0.13))
            self._draw_box(0.145, canopy_y, canopy_z + 0.011, 0.115, 0.048, 0.002, (0.02, 0.14, 0.22))
            for slt in [-0.015, 0.015]:
                self._draw_box(0.198, canopy_y + slt, canopy_z + 0.010, 0.008, 0.003, 0.002, (0.15, 0.18, 0.22))

            # 6. EIA-310-D SQUARE-HOLE VERTICAL MOUNTING RAILS & U-GRADUATIONS
            rail_z = hd - 0.060
            rail_w = 0.038
            rail_d = 0.030

            for rx_rail in [-hw + 0.08, hw - 0.08]:
                self._draw_box(rx_rail, hh, rail_z, rail_w, h - 0.14, rail_d, (0.32, 0.36, 0.42))
                self._draw_box(rx_rail, hh, rail_z - 0.005, rail_w - 0.010, h - 0.15, rail_d - 0.008, (0.18, 0.20, 0.24))

                for u in range(1, 43):
                    uy = 0.14 + (u / 42.0) * 1.85
                    for hole_offset in [-0.012, 0.0, 0.012]:
                        self._draw_box(rx_rail, uy + hole_offset, rail_z + rail_d/2 + 0.001, 0.007, 0.007, 0.002, (0.06, 0.07, 0.09))

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

            for mark_u in [5, 10, 15, 20, 25, 30, 35, 40, 42]:
                my = 0.14 + (mark_u / 42.0) * 1.85
                for rx_rail in [-hw + 0.052, hw - 0.052]:
                    self._draw_box(rx_rail, my, rail_z + rail_d/2 + 0.003, 0.016, 0.013, 0.002, (0.94, 0.96, 1.0))
                    self._draw_box(rx_rail, my, rail_z + rail_d/2 + 0.004, 0.010, 0.007, 0.001, (0.05, 0.22, 0.45))

            # 7. ZERO-U VERTICAL CABLE MANAGEMENT DUCTS & HIGH-DENSITY CABLE BUNDLES
            duct_z = hd - 0.075
            duct_w = 0.034

            for dx, d_sign, bundle_col in [(-hw + 0.038, -1, (0.0, 0.48, 0.95)), (hw - 0.038, 1, (0.95, 0.82, 0.05))]:
                self._draw_box(dx, hh, duct_z, duct_w, h - 0.20, 0.045, (0.09, 0.10, 0.13))
                self._draw_box(dx, hh, duct_z, duct_w - 0.012, h - 0.22, 0.025, bundle_col)

                for f_idx in range(9):
                    fy = 0.25 + (f_idx / 8.0) * (h - 0.50)
                    self._draw_box(dx + 0.015 * d_sign, fy, duct_z + 0.015, 0.016, 0.008, 0.005, (0.24, 0.26, 0.30))
                    self._draw_box(dx, fy, duct_z, duct_w - 0.008, 0.012, 0.028, (0.05, 0.05, 0.06))

            # 8. DUAL REDUNDANT 0U VERTICAL REAR PDUS, OVERHEAD POWER WHIPS & REAR CABLING
            pdu_z = -hd + 0.058
            pdu_w = 0.046
            pdu_h = h - 0.16

            # Rear EIA-310-D Vertical Equipment Mounting Rails & Cable Lacing Points
            for rx_rail in [-hw + 0.08, hw - 0.08]:
                self._draw_box(rx_rail, hh, -hd + 0.060, 0.034, h - 0.14, 0.026, (0.28, 0.32, 0.38))
                for u in range(1, 43, 2):
                    uy = 0.14 + (u / 42.0) * 1.85
                    self._draw_box(rx_rail, uy, -hd + 0.060 - 0.013, 0.007, 0.007, 0.002, (0.06, 0.07, 0.09))

            # Horizontal Cable Lacing Bars across rear posts at 10U, 22U, 34U
            for ly_u in [10, 22, 34]:
                ly = 0.14 + (ly_u / 42.0) * 1.85
                self._draw_box(0.0, ly, -hd + 0.046, w - 0.14, 0.014, 0.012, (0.22, 0.25, 0.30))
                # Cable tie-wrap anchors along lacing bar
                for tx in [-0.16, -0.08, 0.0, 0.08, 0.16]:
                    self._draw_box(tx, ly, -hd + 0.046 - 0.006, 0.008, 0.016, 0.004, (0.10, 0.11, 0.14))

            # Solid Copper Earth Grounding Busbar along left rear post
            busbar_x = -hw + 0.045
            self._draw_box(busbar_x, hh, -hd + 0.048, 0.012, h - 0.24, 0.006, (0.88, 0.58, 0.24))
            for bg in range(7):
                bgy = 0.25 + (bg / 6.0) * (h - 0.50)
                # Brass dual-hole grounding lug with hex bolts
                self._draw_box(busbar_x, bgy, -hd + 0.048 - 0.004, 0.016, 0.014, 0.004, (0.82, 0.72, 0.22))
                # Yellow/Green safety earth bonding wire jumper to rack frame
                self._draw_box(busbar_x - 0.015, bgy, -hd + 0.040, 0.024, 0.005, 0.005, (0.85, 0.85, 0.12))

            # Sub-Floor Cable Entry Cutout with Nylon Brush Grommet at base
            self._draw_box(0.0, 0.060, -hd + 0.065, w - 0.16, 0.010, 0.065, (0.10, 0.11, 0.14))
            self._draw_box(0.0, 0.066, -hd + 0.065, w - 0.18, 0.004, 0.055, (0.04, 0.04, 0.05))

            # PDU-A (Left Rear Post - Feed A: Royal Blue Scheme)
            pdu_a_x = -hw + 0.075
            # Heavy Extruded Aluminum PDU Housing
            self._draw_box(pdu_a_x, hh, pdu_z, pdu_w, pdu_h, 0.038, (0.11, 0.12, 0.15))
            # Feed A Royal Blue Color-Code Channel Stripe
            self._draw_box(pdu_a_x, hh, pdu_z + 0.019, 0.010, pdu_h - 0.02, 0.002, (0.0, 0.52, 0.98))
            # Digital OLED Power Telemetry Pod at Top
            self._draw_box(pdu_a_x, h - 0.16, pdu_z + 0.020, 0.034, 0.026, 0.004, (0.04, 0.12, 0.20))
            self._draw_box(pdu_a_x, h - 0.16, pdu_z + 0.022, 0.028, 0.018, 0.002, (0.0, 0.95, 0.75)) # glowing telemetry
            # Bank of 20 IEC C13 & 4 C19 Outlets with Green LEDs
            for p_idx in range(16):
                py = 0.22 + (p_idx / 15.0) * (h - 0.46)
                # Recessed Outlet Bezel & Cavity
                self._draw_box(pdu_a_x, py, pdu_z + 0.018, 0.026, 0.016, 0.003, (0.24, 0.26, 0.30))
                self._draw_box(pdu_a_x, py, pdu_z + 0.020, 0.020, 0.012, 0.002, (0.03, 0.03, 0.04))
                # Green Branch Circuit Breaker Active LED
                self._draw_box(pdu_a_x + 0.014, py, pdu_z + 0.020, 0.004, 0.004, 0.002, (0.1, 0.98, 0.2))

            # Overhead Heavy Industrial Power Whip for PDU-A (Drops from Yellow Cable Ladder to PDU-A)
            # Compression Gland Fitting at PDU top
            self._draw_box(pdu_a_x, h - 0.07, pdu_z, 0.030, 0.028, 0.030, (0.78, 0.68, 0.25))
            # 32mm Flexible Industrial Power Conduit rising to ceiling ladder
            self._draw_box(pdu_a_x, h + 0.18, pdu_z, 0.024, 0.48, 0.024, (0.10, 0.11, 0.14))
            self._draw_box(pdu_a_x + 0.04, h + 0.44, pdu_z + 0.08, 0.10, 0.024, 0.16, (0.10, 0.11, 0.14))

            # PDU-B (Right Rear Post - Feed B: Crimson Red Scheme)
            pdu_b_x = hw - 0.075
            # Heavy Extruded Aluminum PDU Housing
            self._draw_box(pdu_b_x, hh, pdu_z, pdu_w, pdu_h, 0.038, (0.11, 0.12, 0.15))
            # Feed B Crimson Red Color-Code Channel Stripe
            self._draw_box(pdu_b_x, hh, pdu_z + 0.019, 0.010, pdu_h - 0.02, 0.002, (0.92, 0.18, 0.18))
            # Digital OLED Power Telemetry Pod at Top
            self._draw_box(pdu_b_x, h - 0.16, pdu_z + 0.020, 0.034, 0.026, 0.004, (0.16, 0.04, 0.06))
            self._draw_box(pdu_b_x, h - 0.16, pdu_z + 0.022, 0.028, 0.018, 0.002, (0.1, 0.95, 0.45))
            # Bank of Outlets
            for p_idx in range(16):
                py = 0.22 + (p_idx / 15.0) * (h - 0.46)
                self._draw_box(pdu_b_x, py, pdu_z + 0.018, 0.026, 0.016, 0.003, (0.24, 0.26, 0.30))
                self._draw_box(pdu_b_x, py, pdu_z + 0.020, 0.020, 0.012, 0.002, (0.03, 0.03, 0.04))
                self._draw_box(pdu_b_x - 0.014, py, pdu_z + 0.020, 0.004, 0.004, 0.002, (0.1, 0.98, 0.2))

            # Overhead Heavy Industrial Power Whip for PDU-B
            self._draw_box(pdu_b_x, h - 0.07, pdu_z, 0.030, 0.028, 0.030, (0.78, 0.68, 0.25))
            self._draw_box(pdu_b_x, h + 0.18, pdu_z, 0.024, 0.48, 0.024, (0.10, 0.11, 0.14))
            self._draw_box(pdu_b_x - 0.04, h + 0.44, pdu_z + 0.08, 0.10, 0.024, 0.16, (0.10, 0.11, 0.14))

            # Rear High-Density Vertical Cable Bundles with Hook-and-Loop (Velcro) Straps
            # Left Vertical Cable Harness (Feed A power cords & network trunks)
            bundle_a_x = -hw + 0.032
            bundle_z = -hd + 0.042
            self._draw_box(bundle_a_x, hh, bundle_z, 0.028, h - 0.18, 0.028, (0.10, 0.11, 0.13))
            self._draw_box(bundle_a_x, hh, bundle_z - 0.008, 0.018, h - 0.20, 0.014, (0.0, 0.45, 0.90))
            for v_idx in range(9):
                vy = 0.25 + (v_idx / 8.0) * (h - 0.50)
                # Royal Blue Velcro Tie Strap cinched around bundle
                self._draw_box(bundle_a_x, vy, bundle_z, 0.034, 0.016, 0.034, (0.08, 0.42, 0.95))

            # Right Vertical Cable Harness (Feed B power cords & storage trunks)
            bundle_b_x = hw - 0.032
            self._draw_box(bundle_b_x, hh, bundle_z, 0.028, h - 0.18, 0.028, (0.10, 0.11, 0.13))
            self._draw_box(bundle_b_x, hh, bundle_z - 0.008, 0.018, h - 0.20, 0.014, (0.85, 0.20, 0.20))
            for v_idx in range(9):
                vy = 0.25 + (v_idx / 8.0) * (h - 0.50)
            # 9. ENTERPRISE UNDER-RACK SMART-UPS POWER SYSTEM (BELOW SLOT U1 IN BASE PLINTH - ZERO OVERLAP)
            ups_y = 0.088
            ups_h = 0.070
            ups_w = 0.442
            ups_d = 0.660

            # Main Heavy-Duty Steel Chassis Enclosure resting on lower plinth base
            self._draw_box(0.0, ups_y, 0.0, ups_w, ups_h, ups_d, (0.13, 0.14, 0.17))
            # Heavy-Duty Rackmount Ear Brackets (19-inch EIA standard) & Screws
            self._draw_box(-hw + 0.078, ups_y, 0.342, 0.022, ups_h, 0.006, (0.42, 0.45, 0.50))
            self._draw_box( hw - 0.078, ups_y, 0.342, 0.022, ups_h, 0.006, (0.42, 0.45, 0.50))
            # Stainless Hex Screws (2 per ear)
            for ear_x in [-hw + 0.078, hw - 0.078]:
                self._draw_box(ear_x, ups_y + 0.022, 0.346, 0.008, 0.008, 0.003, (0.85, 0.88, 0.92))
                self._draw_box(ear_x, ups_y - 0.022, 0.346, 0.008, 0.008, 0.003, (0.85, 0.88, 0.92))

            # A. FRONT PANEL (Z = +0.344)
            # Left: Hot-Swap Battery Pack Cartridge Module
            self._draw_box(-0.105, ups_y, 0.348, 0.200, ups_h - 0.008, 0.005, (0.16, 0.18, 0.22))
            # Recessed Finger Pull Handle
            self._draw_box(-0.105, ups_y, 0.351, 0.080, 0.014, 0.003, (0.07, 0.08, 0.10))
            # Battery Pack Identity Badge
            self._draw_box(-0.155, ups_y + 0.020, 0.351, 0.050, 0.010, 0.002, (0.28, 0.32, 0.38))

            # Right: UPS Controller, Intelligence Module & LCD
            self._draw_box(0.105, ups_y, 0.348, 0.200, ups_h - 0.008, 0.005, (0.18, 0.20, 0.24))
            # Backlit Cyan/Blue Diagnostic LCD Telemetry Screen
            self._draw_box(0.105, ups_y + 0.012, 0.351, 0.095, 0.024, 0.003, (0.04, 0.20, 0.36))
            self._draw_box(0.105, ups_y + 0.012, 0.353, 0.085, 0.018, 0.002, (0.06, 0.85, 0.95)) # glowing telemetry
            # 5-Bar LED Battery Capacity Gauge (Green)
            for b in range(5):
                self._draw_box(0.075 + b * 0.014, ups_y - 0.007, 0.352, 0.010, 0.004, 0.002, (0.1, 0.98, 0.2))
            # 5-Bar LED Load Meter Gauge (Green & Amber)
            for l_idx in range(5):
                l_col = (0.1, 0.98, 0.2) if l_idx < 4 else (1.0, 0.65, 0.05)
                self._draw_box(0.075 + l_idx * 0.014, ups_y - 0.016, 0.352, 0.010, 0.004, 0.002, l_col)
            # Status Indicator Micro-LEDs (ONLINE = Green, BATT = Amber, BYPASS = Amber, FAULT = Red)
            self._draw_box(0.170, ups_y + 0.020, 0.352, 0.005, 0.005, 0.002, (0.1, 0.98, 0.2))
            self._draw_box(0.184, ups_y + 0.020, 0.352, 0.005, 0.005, 0.002, (0.20, 0.14, 0.05))
            self._draw_box(0.170, ups_y + 0.009, 0.352, 0.005, 0.005, 0.002, (0.20, 0.14, 0.05))
            self._draw_box(0.184, ups_y + 0.009, 0.352, 0.005, 0.005, 0.002, (0.25, 0.05, 0.05))
            # Round Power ON / Test Button
            self._draw_box(0.178, ups_y - 0.010, 0.352, 0.012, 0.012, 0.003, (0.12, 0.85, 0.30))
            # Vivid Schneider Green Brand Accent Stripe
            self._draw_box(0.0, ups_y - 0.028, 0.350, 0.420, 0.004, 0.002, (0.0, 0.70, 0.35))

            # B. REAR PANEL (Z = -0.344)
            # Rear Metal Faceplate
            self._draw_box(0.0, ups_y, -0.344, 0.442, ups_h, 0.006, (0.14, 0.15, 0.18))
            # Main AC Utility Mains Input Power Gland (Mains Feed)
            self._draw_box(-0.150, ups_y - 0.010, -0.348, 0.028, 0.028, 0.016, (0.75, 0.65, 0.22))
            # Heavy 22mm Black Rubber Power Supply Cable dropping into floor cutout
            cable_h = max(0.01, ups_y - 0.010)
            self._draw_box(-0.150, cable_h / 2.0, -0.348, 0.020, cable_h, 0.020, (0.08, 0.09, 0.11))
            # Heavy Output Feeds connecting UPS directly to PDU-A (Blue) and PDU-B (Red)
            pdu_bottom = 0.20
            conduit_h = max(0.02, pdu_bottom - (ups_y + 0.015))
            conduit_y = (ups_y + 0.015) + conduit_h / 2.0
            self._draw_box(-hw + 0.075, conduit_y, pdu_z, 0.020, conduit_h, 0.020, (0.0, 0.48, 0.95))
            self._draw_box( hw - 0.075, conduit_y, pdu_z, 0.020, conduit_h, 0.020, (0.88, 0.15, 0.15))
            # Bank of 6 IEC C13 Output Receptacles
            for r_idx in range(6):
                rx_out = -0.060 + r_idx * 0.024
                self._draw_box(rx_out, ups_y + 0.012, -0.348, 0.018, 0.014, 0.003, (0.04, 0.04, 0.05))
            # SmartSlot Network Management Card (NMC 3) with RJ45
            self._draw_box(0.140, ups_y + 0.014, -0.348, 0.026, 0.018, 0.004, (0.45, 0.48, 0.52))
            self._draw_box(0.140, ups_y + 0.014, -0.350, 0.018, 0.012, 0.002, (0.05, 0.08, 0.12))
            self._draw_box(0.140, ups_y + 0.024, -0.349, 0.005, 0.005, 0.002, (0.1, 0.98, 0.2))
            # External Battery High-Current DC Connector
            self._draw_box(0.020, ups_y - 0.016, -0.348, 0.038, 0.022, 0.014, (0.15, 0.35, 0.85))


            # 10. ROOF STRUCTURE, DUAL EXHAUST FANS & CABLE DROP GLANDS
            roof_y = h - 0.025
            self._draw_box(0.0, roof_y, 0.0, w, 0.05, d, (0.08, 0.09, 0.11))
            self._draw_box(0.0, h + 0.002, 0.0, w - 0.02, 0.004, d - 0.02, (0.12, 0.13, 0.16))

            for fx in [-0.15, 0.15]:
                self._draw_box(fx, h + 0.008, 0.0, 0.18, 0.012, 0.18, (0.16, 0.18, 0.22))
                self._draw_box(fx, h + 0.015, 0.0, 0.15, 0.004, 0.15, (0.06, 0.07, 0.09))
                self._draw_box(fx, h + 0.018, 0.0, 0.12, 0.002, 0.12, (0.50, 0.54, 0.60))
                self._draw_box(fx, h + 0.020, 0.0, 0.045, 0.008, 0.045, (0.28, 0.32, 0.38))

            for gx in [-0.12, 0.12]:
                self._draw_box(gx, h + 0.006, -0.22, 0.09, 0.010, 0.12, (0.14, 0.15, 0.18))
                self._draw_box(gx, h + 0.010, -0.22, 0.07, 0.004, 0.10, (0.03, 0.03, 0.04))

            # 10. INDUSTRIAL STATUS BEACON STACK LIGHT (ANDON TOWER)
            beacon_x = 0.0
            beacon_z = hd - 0.08
            beacon_base_y = h + 0.015

            self._draw_box(beacon_x, beacon_base_y + 0.02, beacon_z, 0.018, 0.040, 0.018, (0.55, 0.58, 0.64))
            self._draw_box(beacon_x, beacon_base_y + 0.042, beacon_z, 0.038, 0.008, 0.038, (0.12, 0.14, 0.18))
            self._draw_box(beacon_x, beacon_base_y + 0.094, beacon_z, 0.036, 0.030, 0.036, (0.35, 0.18, 0.04))
            self._draw_box(beacon_x, beacon_base_y + 0.126, beacon_z, 0.036, 0.030, 0.036, (0.30, 0.06, 0.06))
            self._draw_box(beacon_x, beacon_base_y + 0.146, beacon_z, 0.040, 0.010, 0.040, (0.10, 0.11, 0.13))
            self._draw_box(beacon_x, beacon_base_y + 0.154, beacon_z, 0.020, 0.006, 0.020, (0.20, 0.22, 0.26))

            glPopMatrix()

    def _render_server_racks(self, now):
        if self.racks_display_list is None:
            self._init_display_lists()
        glCallList(self.racks_display_list)

        w = self.rack_width
        h = self.rack_height
        d = self.rack_depth
        hw, hh, hd = w / 2.0, h / 2.0, d / 2.0

        door_front_z = hd + 0.008
        lock_y = 1.05
        lock_x = hw - 0.024
        canopy_y = h - 0.075
        canopy_z = hd + 0.014
        beacon_x = 0.0
        beacon_z = hd - 0.08
        beacon_base_y = h + 0.015

        for r in self.racks:
            rx, rz = r["x"], r["z"]
            rack_id = r.get("id", 1)
            glPushMatrix()
            glTranslatef(rx, 0.0, rz)

            # Smart Access Authorized Glow LED (Emerald Green / Cyan Pulse)
            lock_pulse = 0.85 + 0.15 * math.sin(now * 3.5 + rack_id)
            lock_col = (0.0, 0.95 * lock_pulse, 0.75 * lock_pulse)
            self._draw_box(lock_x, lock_y + 0.095, door_front_z + 0.015, 0.014, 0.006, 0.002, lock_col)

            # Illuminated Lettering Core Glow
            name_glow = 0.90 + 0.10 * math.sin(now * 2.0 + rack_id)
            self._draw_box(-0.06, canopy_y, canopy_z + 0.012, 0.21, 0.038, 0.002, (0.35 * name_glow, 0.88 * name_glow, 1.0 * name_glow))

            # Digital Green 7-Segment Temperature & RH Simulation
            temp_glow = 0.85 + 0.15 * math.sin(now * 1.8 + rack_id)
            for seg_i in range(4):
                sx = 0.105 + seg_i * 0.026
                self._draw_box(sx, canopy_y + 0.008, canopy_z + 0.013, 0.018, 0.006, 0.001, (0.1, 0.98 * temp_glow, 0.35 * temp_glow))
                self._draw_box(sx, canopy_y - 0.008, canopy_z + 0.013, 0.018, 0.006, 0.001, (0.0, 0.85 * temp_glow, 0.95 * temp_glow))

            # Tier 1 (Bottom): Emerald Green Module (Nominal System Sync - Gentle Breathing Pulse)
            b_pulse = 0.82 + 0.18 * math.sin(now * 2.8 + rack_id)
            tier1_col = (0.05 * b_pulse, 0.98 * b_pulse, 0.32 * b_pulse)
            self._draw_box(beacon_x, beacon_base_y + 0.062, beacon_z, 0.036, 0.030, 0.036, tier1_col)

            glPopMatrix()

    def _compile_workbench_static_list(self):
        glPushMatrix()
        glTranslatef(-3.2, 0.0, 0.5)

        # Desk Top & Legs (Modern executive white / slate desk)
        self._draw_box(0.0, 0.75, 0.0, 1.4, 0.04, 0.75, (0.92, 0.94, 0.97))
        self._draw_box(0.0, 0.75, 0.373, 1.4, 0.038, 0.005, (0.20, 0.24, 0.28))
        for lx in [-0.64, 0.64]:
            for lz in [-0.32, 0.32]:
                self._draw_box(lx, 0.375, lz, 0.04, 0.75, 0.04, (0.22, 0.25, 0.30))

        glPopMatrix()

    def _render_workbench(self, now):
        if self.workbench_display_list is None:
            self._init_display_lists()
        glCallList(self.workbench_display_list)

    def _render_devices(self, devices, current_time, camera=None):
        cam_z = getattr(camera, "z", getattr(camera, "base_eye_z", 0.0)) if camera else 0.0
        # Datacenter racks are centered at z = -1.5 (front: -1.10, rear: -1.90)
        # In front of racks (cold aisle / main menu): cam_z >= -1.65 -> front visible
        # Behind racks (hot aisle): cam_z <= -1.35 -> rear visible
        is_front_visible = cam_z >= -1.65
        is_rear_visible = cam_z <= -1.35

        for dev in devices:
            glPushMatrix()
            glTranslatef(dev.pos_x, dev.pos_y, dev.pos_z)

            # Dedicated Renderers per Device Type
            if dev.device_type == "laptop":
                self._render_laptop(dev, current_time)
            else:
                # Compile Solid Chassis Body display list if not present
                if getattr(dev, "_dl_body", None) is None:
                    dev._dl_body = glGenLists(1)
                    self._device_display_lists.add(dev._dl_body)
                    glNewList(dev._dl_body, GL_COMPILE)
                    self._compile_device_body(dev)
                    glEndList()

                # Compile Front static display list if not present
                if getattr(dev, "_dl_front", None) is None:
                    dev._dl_front = glGenLists(1)
                    self._device_display_lists.add(dev._dl_front)
                    glNewList(dev._dl_front, GL_COMPILE)
                    self._compile_device_front(dev)
                    glEndList()

                # Compile Rear static display list if in a server rack
                if getattr(dev, "rack_id", 0) in (1, 2, 3):
                    if getattr(dev, "_dl_rear", None) is None:
                        dev._dl_rear = glGenLists(1)
                        self._device_display_lists.add(dev._dl_rear)
                        glNewList(dev._dl_rear, GL_COMPILE)
                        self._compile_device_rear(dev)
                        glEndList()

                # Always render solid 3D chassis enclosure (visible from front, rear, and all camera angles)
                glCallList(dev._dl_body)

                # Render Front if visible
                if is_front_visible:
                    glCallList(dev._dl_front)
                    self._render_device_dynamic_front(dev, current_time)

                # Render Rear if visible
                if is_rear_visible and getattr(dev, "rack_id", 0) in (1, 2, 3):
                    glCallList(dev._dl_rear)
                    self._render_device_dynamic_rear(dev, current_time)

            glPopMatrix()

    def _compile_device_body(self, dev):
        """Compiles 3D solid steel chassis, top/bottom sheet metal, and side slide mounting rails into an OpenGL display list."""
        hw = dev.width / 2.0
        hh = dev.height / 2.0
        hd = dev.depth / 2.0
        chassis_w = dev.width - 0.042  # ~0.438m wide, fits inside 19" EIA rack aperture
        chassis_h = dev.height - 0.002 # leaves 1mm clearance top & bottom
        chassis_d = dev.depth          # 0.60m full depth

        # 1. Main Structural Cold-Rolled Steel Chassis Enclosure
        # Dark charcoal / matte enterprise appliance finish
        self._draw_box(0.0, 0.0, 0.0, chassis_w, chassis_h, chassis_d, (0.15, 0.16, 0.19))

        # 2. Top Sheet Metal Cover Plate (Galvanized / Brushed Aluminum Finish)
        # Prevents any hollow gaps when viewing device from above
        top_y = hh - 0.0008
        self._draw_box(0.0, top_y, 0.0, chassis_w - 0.004, 0.0016, chassis_d - 0.008, (0.22, 0.24, 0.28))
        # Top cover stamping stiffener grooves
        self._draw_box(0.0, hh, 0.0, chassis_w - 0.040, 0.0004, chassis_d - 0.080, (0.18, 0.20, 0.23))

        # 3. Bottom Chassis Plate (Underside Stiffener)
        # Prevents any hollow gaps when viewing device from below
        bot_y = -hh + 0.0008
        self._draw_box(0.0, bot_y, 0.0, chassis_w - 0.004, 0.0016, chassis_d - 0.008, (0.11, 0.12, 0.14))

        # 4. Left & Right Heavy-Duty 4-Post Inner Slide Mounting Rails (Tool-less Slide Rail Kit)
        # Running the full 60cm depth on both left and right sides
        rail_h = max(0.024, dev.height - 0.006)
        rail_w = 0.010
        for sx in [-hw + 0.012, hw - 0.012]:
            # Galvanized steel rail body spanning the full chassis depth
            self._draw_box(sx, 0.0, 0.0, rail_w, rail_h, chassis_d + 0.04, (0.55, 0.58, 0.64))
            # Ball bearing guide channel recess
            self._draw_box(sx, 0.0, 0.0, rail_w + 0.002, rail_h * 0.45, chassis_d, (0.35, 0.38, 0.44))
            # Rear EIA rail locking bracket clamp at the rear post (-hd - 0.035)
            self._draw_box(sx, 0.0, -hd - 0.035, 0.018, dev.height - 0.002, 0.035, (0.42, 0.46, 0.52))
            # Quick-release latch button on rear bracket
            latch_col = (0.0, 0.55, 0.95) if sx < 0 else (0.95, 0.50, 0.10)
            self._draw_box(sx, 0.0, -hd - 0.025, 0.020, 0.010, 0.010, latch_col)

        # 5. Side Ventilation Louvers along full depth
        for sx in [-chassis_w / 2.0 - 0.0005, chassis_w / 2.0 + 0.0005]:
            for vz in [-0.16, -0.06, 0.06, 0.16]:
                self._draw_box(sx, 0.0, vz, 0.001, dev.height * 0.55, 0.065, (0.08, 0.09, 0.11))

    def _compile_device_front(self, dev):
        """Compiles static bezels, ears, ports, and heat sinks into an OpenGL display list."""
        if dev.device_type == "switch":
            self._render_switch(dev, 0.0)
        elif dev.device_type == "router":
            self._render_router(dev, 0.0)
        elif dev.device_type in ("isp_gateway", "isp") or (dev.device_type == "server" and "isp" in dev.hostname.lower()):
            self._render_isp_gateway(dev, 0.0)
        elif dev.device_type == "server":
            self._render_server(dev, 0.0)
        elif dev.device_type == "firewall":
            self._render_firewall(dev, 0.0)
        else:
            self._render_generic_device(dev, 0.0)

    def _compile_device_rear(self, dev):
        """Compiles static rear backplate, dual hot-swap PSUs, and 3D power cords into an OpenGL display list."""
        self._render_device_rear(dev, 0.0)

    def _render_device_dynamic_front(self, dev, now):
        """Draws dynamic blinking port LEDs, link states, and activity beacons with minimal vertex overhead."""
        if dev.device_type == "switch":
            for idx, port in enumerate(dev.ports.values()):
                if port.port_type == "CONSOLE":
                    continue
                px, py, pz = dev.get_port_local_pos(port.name, port.port_index)
                led = port.get_led_state(now)
                if led == LEDState.GREEN:
                    link_c = (0.1, 0.98, 0.2)
                elif led == LEDState.BLINK_GREEN:
                    link_c = (0.4, 1.0, 0.5)
                elif led == LEDState.AMBER:
                    link_c = (1.0, 0.65, 0.05)
                else:
                    link_c = (0.08, 0.12, 0.08)
                self._draw_box(px - 0.005, py + 0.016, pz + 0.0035, 0.006, 0.006, 0.002, link_c)

                act_blink = (led in (LEDState.GREEN, LEDState.BLINK_GREEN)) and (int(now * 14 + idx) % 2 == 0)
                act_c = (0.2, 0.95, 0.3) if act_blink else (0.06, 0.10, 0.06)
                self._draw_box(px + 0.005, py + 0.016, pz + 0.0035, 0.006, 0.006, 0.002, act_c)

        elif dev.device_type == "router":
            data_ports = [p for p in dev.ports.values() if p.port_type != "CONSOLE"]
            for idx, port in enumerate(data_ports):
                px, py, pz = dev.get_port_local_pos(port.name, port.port_index)
                led = port.get_led_state(now)
                if led == LEDState.GREEN:
                    link_c = (0.1, 0.98, 0.2)
                elif led == LEDState.BLINK_GREEN:
                    link_c = (0.4, 1.0, 0.5)
                elif led == LEDState.AMBER:
                    link_c = (1.0, 0.65, 0.05)
                else:
                    link_c = (0.08, 0.12, 0.08)
                self._draw_box(px - 0.004, py - 0.014, pz + 0.0035, 0.005, 0.005, 0.002, link_c)

                act_blink = (led in (LEDState.GREEN, LEDState.BLINK_GREEN)) and (int(now * 14 + idx) % 2 == 0)
                act_c = (0.2, 0.95, 0.3) if act_blink else (0.06, 0.10, 0.06)
                self._draw_box(px + 0.004, py - 0.014, pz + 0.0035, 0.005, 0.005, 0.002, act_c)

        elif dev.device_type == "server":
            hh = dev.height / 2.0
            front_z = dev.depth / 2.0 + 0.003
            power_col = (0.1, 0.98, 0.2) if dev.is_powered else (0.08, 0.12, 0.08)
            self._draw_box(-0.19, hh - 0.012, front_z + 0.0035, 0.006, 0.006, 0.002, power_col)
            hdd_blink = dev.is_powered and (int(now * 9) % 2 == 0)
            hdd_col = (0.2, 0.85, 0.98) if hdd_blink else (0.06, 0.14, 0.20)
            self._draw_box(-0.178, hh - 0.012, front_z + 0.0035, 0.005, 0.005, 0.002, hdd_col)

        elif dev.device_type == "firewall":
            data_ports = [p for p in dev.ports.values() if p.port_type != "CONSOLE" and not p.name.startswith("m")]
            for idx, port in enumerate(data_ports):
                px, py, pz = dev.get_port_local_pos(port.name, port.port_index)
                led = port.get_led_state(now)
                link_c = (0.1, 0.98, 0.2) if led == LEDState.GREEN else ((0.4, 1.0, 0.5) if led == LEDState.BLINK_GREEN else ((1.0, 0.65, 0.05) if led == LEDState.AMBER else (0.08, 0.12, 0.08)))
                self._draw_box(px - 0.005, py - 0.014, pz + 0.0035, 0.005, 0.005, 0.002, link_c)

                act_blink = (led in (LEDState.GREEN, LEDState.BLINK_GREEN)) and (int(now * 14 + idx) % 2 == 0)
                act_c = (0.2, 0.95, 0.3) if act_blink else (0.06, 0.10, 0.06)
                self._draw_box(px + 0.005, py - 0.014, pz + 0.0035, 0.005, 0.005, 0.002, act_c)

        elif dev.device_type in ("isp_gateway", "isp") or (dev.device_type == "server" and "isp" in dev.hostname.lower()):
            front_z = dev.depth / 2.0 + 0.003
            eth_port = dev.ports.get("eth0")
            is_carrier_up = (eth_port and eth_port.is_link_up) or dev.is_powered
            carrier_blink = is_carrier_up and (int(now * 4) % 2 == 0)
            c_col = (0.1, 0.98, 0.2) if carrier_blink else (0.06, 0.35, 0.12)
            self._draw_box(-0.177, 0.006, front_z + 0.004, 0.005, 0.005, 0.002, c_col)

    def _render_device_dynamic_rear(self, dev, now):
        """Draws dynamic rear iDRAC and server UID beacon blink LEDs."""
        if dev.device_type == "server":
            back_z = -dev.depth / 2.0
            mgmt_blink = int(now * 6) % 2 == 0
            mgmt_col = (0.2, 0.95, 0.3) if mgmt_blink else (0.08, 0.12, 0.08)
            self._draw_box(-0.048, 0.022, back_z - 0.006, 0.005, 0.005, 0.002, mgmt_col)

            uid_blink = int(now * 2) % 2 == 0
            uid_col = (0.0, 0.75, 1.0) if uid_blink else (0.02, 0.25, 0.40)
            self._draw_box(0.045, 0.015, back_z - 0.006, 0.008, 0.008, 0.002, uid_col)

    def _compile_laptop_static_list(self, is_windows):
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
        space_col = (0.27, 0.29, 0.33) if is_windows else (0.20, 0.21, 0.24)
        self._draw_box(0.0, 0.0178, 0.014, 0.085, 0.002, 0.016, space_col)
        self._draw_box(0.070, 0.0175, 0.014, 0.036, 0.002, 0.016, key_color)
        self._draw_box(0.115, 0.0175, 0.014, 0.036, 0.002, 0.016, key_color)

        # 3. Trackpad, Buttons & Palmrest Badges
        if is_windows:
            self._draw_box(0.0, 0.0165, 0.075, 0.11, 0.002, 0.068, (0.72, 0.74, 0.78))
            self._draw_box(0.0, 0.0168, 0.075, 0.108, 0.001, 0.066, (0.76, 0.78, 0.82))
            self._draw_box(0.11, 0.0165, 0.075, 0.018, 0.001, 0.014, (0.0, 0.48, 0.92))
            self._draw_box(0.135, 0.0165, 0.075, 0.012, 0.001, 0.014, (0.15, 0.55, 0.95))
        else:
            self._draw_box(0.0, 0.0195, -0.020, 0.009, 0.004, 0.009, (0.88, 0.12, 0.12))
            self._draw_box(0.0, 0.0165, 0.080, 0.10, 0.002, 0.058, (0.14, 0.15, 0.17))
            self._draw_box(0.0, 0.0170, 0.048, 0.09, 0.001, 0.012, (0.20, 0.21, 0.24))
            self._draw_box(0.0, 0.0173, 0.048, 0.025, 0.001, 0.003, (0.85, 0.20, 0.15))
            self._draw_box(0.11, 0.0165, 0.075, 0.016, 0.001, 0.016, (0.90, 0.35, 0.10))

        # 4. Tilted Laptop Screen Lid (Tilted BACKWARDS by -25 degrees)
        glPushMatrix()
        glTranslatef(0.0, 0.016, -0.118)
        glRotatef(-25.0, 1.0, 0.0, 0.0)

        lid_color = (0.76, 0.78, 0.82) if is_windows else (0.11, 0.12, 0.14)
        self._draw_box(0.0, 0.12, 0.0, 0.36, 0.24, 0.010, lid_color)
        self._draw_box(0.0, 0.12, 0.005, 0.35, 0.23, 0.002, (0.08, 0.09, 0.11))
        self._draw_box(0.0, 0.23, 0.006, 0.006, 0.006, 0.001, (0.02, 0.02, 0.02))
        self._draw_box(0.010, 0.23, 0.006, 0.002, 0.002, 0.001, (0.1, 0.95, 0.3))

        # Glowing IPS Display Face & Authentic OS Graphics
        if is_windows:
            self._draw_box(0.0, 0.12, 0.0065, 0.32, 0.20, 0.001, (0.05, 0.14, 0.32))
            self._draw_box(-0.035, 0.135, 0.0070, 0.09, 0.08, 0.001, (0.08, 0.32, 0.72))
            self._draw_box(0.035, 0.135, 0.0070, 0.09, 0.08, 0.001, (0.08, 0.32, 0.72))
            self._draw_box(0.0, 0.140, 0.0072, 0.11, 0.09, 0.001, (0.14, 0.48, 0.88))
            self._draw_box(-0.015, 0.130, 0.0074, 0.08, 0.07, 0.001, (0.28, 0.68, 0.98))
            self._draw_box(0.015, 0.130, 0.0074, 0.08, 0.07, 0.001, (0.35, 0.74, 1.0))
            self._draw_box(0.0, 0.125, 0.0076, 0.045, 0.045, 0.001, (0.75, 0.90, 1.0))

            self._draw_box(0.0, 0.030, 0.0075, 0.32, 0.016, 0.001, (0.06, 0.12, 0.24))
            for sqx in [-0.042, -0.036]:
                for sqy in [0.033, 0.027]:
                    self._draw_box(sqx, sqy, 0.008, 0.004, 0.004, 0.001, (0.0, 0.65, 1.0))
            self._draw_box(-0.020, 0.030, 0.008, 0.018, 0.008, 0.001, (0.12, 0.20, 0.35))
            app_cols = [(0.0, 0.65, 0.95), (0.2, 0.5, 0.9), (0.1, 0.1, 0.12), (0.45, 0.48, 0.52)]
            for ic_idx, ic_col in enumerate(app_cols):
                self._draw_box(-0.002 + ic_idx * 0.012, 0.030, 0.008, 0.007, 0.007, 0.001, ic_col)
            for tr_idx, tr_col in enumerate([(0.8, 0.85, 0.9), (0.8, 0.85, 0.9), (0.95, 0.95, 0.98)]):
                self._draw_box(0.120 + tr_idx * 0.010, 0.030, 0.008, 0.005, 0.005, 0.001, tr_col)
        else:
            self._draw_box(0.0, 0.12, 0.0065, 0.32, 0.20, 0.001, (0.26, 0.07, 0.22))
            self._draw_box(0.05, 0.12, 0.007, 0.18, 0.14, 0.001, (0.48, 0.16, 0.12))
            self._draw_box(0.06, 0.145, 0.0072, 0.08, 0.05, 0.001, (0.78, 0.28, 0.12))
            self._draw_box(0.06, 0.135, 0.0074, 0.06, 0.03, 0.001, (0.92, 0.44, 0.15))
            for ti, tx in enumerate([0.04, 0.055, 0.07, 0.085]):
                self._draw_box(tx, 0.095 - ti * 0.004, 0.0075, 0.003, 0.05, 0.001, (0.85, 0.38, 0.12))

            self._draw_box(0.0, 0.212, 0.0075, 0.32, 0.014, 0.001, (0.07, 0.07, 0.09))
            self._draw_box(-0.130, 0.212, 0.008, 0.024, 0.008, 0.001, (0.18, 0.18, 0.22))
            self._draw_box(0.0, 0.212, 0.008, 0.022, 0.006, 0.001, (0.88, 0.88, 0.92))
            for ri in range(3):
                self._draw_box(0.130 + ri * 0.008, 0.212, 0.008, 0.004, 0.004, 0.001, (0.8, 0.8, 0.85))

            self._draw_box(-0.148, 0.114, 0.0075, 0.024, 0.182, 0.001, (0.08, 0.08, 0.10))
            dock_cols = [(0.92, 0.35, 0.12), (0.0, 0.48, 0.92), (0.1, 0.1, 0.12), (0.42, 0.44, 0.48), (0.8, 0.8, 0.85)]
            for ic_idx, ic_col in enumerate(dock_cols):
                self._draw_box(-0.148, 0.178 - ic_idx * 0.026, 0.008, 0.013, 0.013, 0.001, ic_col)

        glPopMatrix()

        # 5. Socket frames & cavities on flanks
        px, py, pz = (-0.181, 0.009, 0.04)
        self._draw_box(px, py, pz, 0.003, 0.010, 0.015, (0.32, 0.34, 0.38))
        self._draw_box(px, py, pz, 0.002, 0.007, 0.011, (0.04, 0.04, 0.05))

        cx, cy, cz = (0.181, 0.009, 0.04)
        self._draw_box(cx, cy, cz, 0.003, 0.008, 0.014, (0.24, 0.26, 0.30))
        self._draw_box(cx, cy, cz, 0.002, 0.005, 0.010, (0.04, 0.04, 0.05))

    def _render_laptop(self, dev, now):
        """High-detail procedural 3D Laptop for Windows 11 and Ubuntu 22.04 LTS (Optimized with Display Lists)."""
        is_windows = getattr(dev, "os_type", "windows").lower() == "windows"

        if is_windows and self.laptop_win_display_list:
            glCallList(self.laptop_win_display_list)
        elif not is_windows and self.laptop_linux_display_list:
            glCallList(self.laptop_linux_display_list)

        # Dynamic port LEDs on flanks:
        eth_port = dev.ports.get("eth0")
        if eth_port:
            px, py, pz = (-0.181, 0.009, 0.04)
            led = eth_port.get_led_state(now)
            led_c = (0.1, 0.98, 0.2) if led in (LEDState.GREEN, LEDState.BLINK_GREEN) else (0.08, 0.12, 0.08)
            self._draw_box(px, py + 0.004, pz + 0.006, 0.002, 0.002, 0.002, led_c)

        con_port = dev.ports.get("con0")
        if con_port:
            cx, cy, cz = (0.181, 0.009, 0.04)
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

    def _draw_curved_cord(self, p0, p1, p2, p3, radius, color, num_segments=10):
        """Draws a smooth 3D curved electrical cord with Gouraud shading."""
        pts = []
        for i in range(num_segments + 1):
            t = i / float(num_segments)
            u = 1.0 - t
            x = u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0]
            y = u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1]
            z = u*u*u*p0[2] + 3*u*u*t*p1[2] + 3*u*t*t*p2[2] + t*t*t*p3[2]
            pts.append((x, y, z))

        lx, ly, lz = 0.0, 0.88, 0.47
        NUM_SIDES = 6
        cos_tab = (1.0, 0.5, -0.5, -1.0, -0.5, 0.5)
        sin_tab = (0.0, 0.866025, 0.866025, 0.0, -0.866025, -0.866025)

        rings = []
        prev_n = (0.0, 1.0, 0.0)
        for i in range(len(pts)):
            if i == 0:
                tx, ty, tz = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1], pts[1][2] - pts[0][2]
            elif i == len(pts) - 1:
                tx, ty, tz = pts[i][0] - pts[i-1][0], pts[i][1] - pts[i-1][1], pts[i][2] - pts[i-1][2]
            else:
                tx, ty, tz = pts[i+1][0] - pts[i-1][0], pts[i+1][1] - pts[i-1][1], pts[i+1][2] - pts[i-1][2]
            tlen = math.sqrt(tx*tx + ty*ty + tz*tz)
            if tlen > 1e-6:
                tx, ty, tz = tx/tlen, ty/tlen, tz/tlen
            else:
                tx, ty, tz = 0.0, 0.0, 1.0

            dot = prev_n[0]*tx + prev_n[1]*ty + prev_n[2]*tz
            nx, ny, nz = prev_n[0] - dot*tx, prev_n[1] - dot*ty, prev_n[2] - dot*tz
            nlen = math.sqrt(nx*nx + ny*ny + nz*nz)
            if nlen > 1e-6:
                nx, ny, nz = nx/nlen, ny/nlen, nz/nlen
            else:
                nx, ny, nz = 0.0, 1.0, 0.0
            prev_n = (nx, ny, nz)

            bx = ty*nz - tz*ny
            by = tz*nx - tx*nz
            bz = tx*ny - ty*nx

            ring_verts = []
            ring_colors = []
            px, py, pz = pts[i]
            for s in range(NUM_SIDES):
                c_val, s_val = cos_tab[s], sin_tab[s]
                vx = px + radius * (c_val * nx + s_val * bx)
                vy = py + radius * (c_val * ny + s_val * by)
                vz = pz + radius * (c_val * nz + s_val * bz)
                norm_x = c_val * nx + s_val * bx
                norm_y = c_val * ny + s_val * by
                norm_z = c_val * nz + s_val * bz
                dot_l = max(0.0, norm_x*lx + norm_y*ly + norm_z*lz)
                shade = 0.40 + 0.60 * dot_l
                ring_verts.append((vx, vy, vz))
                ring_colors.append((color[0]*shade, color[1]*shade, color[2]*shade))
            rings.append((ring_verts, ring_colors))

        glBegin(GL_QUADS)
        for i in range(len(rings) - 1):
            v0, c0 = rings[i]
            v1, c1 = rings[i+1]
            for s in range(NUM_SIDES):
                s_next = (s + 1) % NUM_SIDES
                glColor3f(*c0[s])
                glVertex3f(*v0[s])
                glColor3f(*c1[s])
                glVertex3f(*v1[s])
                glColor3f(*c1[s_next])
                glVertex3f(*v1[s_next])
                glColor3f(*c0[s_next])
                glVertex3f(*v0[s_next])
        glEnd()

    def _render_device_rear(self, dev, now):
        """
        Renders authentic rear panel details, dual hot-swap PSUs, cooling fans,
        management ports, and real 3D power cords (Feed A & Feed B) to the rack PDUs.
        """
        hw = dev.width / 2.0
        hh = dev.height / 2.0
        hd = dev.depth / 2.0
        chassis_w = dev.width - 0.042
        back_z = -dev.depth / 2.0

        # 1. Rear Metal Backplate (Galvanized / Charcoal Anodized Steel)
        self._draw_box(0.0, 0.0, back_z - 0.001, chassis_w, dev.height - 0.004, 0.002, (0.13, 0.14, 0.17))
        # Top and Bottom Chassis Flange Lips
        self._draw_box(0.0, hh - 0.002, back_z - 0.002, chassis_w, 0.003, 0.003, (0.28, 0.30, 0.35))
        self._draw_box(0.0, -hh + 0.002, back_z - 0.002, chassis_w, 0.003, 0.003, (0.28, 0.30, 0.35))

        # 2. Chassis Safety Earth Grounding Lug on Corner
        lug_x = -chassis_w / 2.0 + 0.024
        lug_y = -hh + 0.010
        self._draw_box(lug_x, lug_y, back_z - 0.003, 0.014, 0.010, 0.003, (0.88, 0.58, 0.22))
        self._draw_box(lug_x - 0.003, lug_y, back_z - 0.005, 0.004, 0.004, 0.002, (0.75, 0.78, 0.82))
        self._draw_box(lug_x + 0.003, lug_y, back_z - 0.005, 0.004, 0.004, 0.002, (0.75, 0.78, 0.82))
        # Yellow/Green grounding jumper wire to rack frame
        self._draw_box(lug_x - 0.018, lug_y, back_z - 0.003, 0.024, 0.004, 0.004, (0.85, 0.85, 0.12))

        # 3. Dual Redundant Hot-Swappable Power Supplies (PSU 1 on Left, PSU 2 on Right)
        for side, psu_x, feed_col, tag in [(-1, -0.14, (0.0, 0.52, 0.98), "A"), (1, 0.14, (0.92, 0.18, 0.18), "B")]:
            # PSU Outer Housing Casing
            self._draw_box(psu_x, 0.0, back_z - 0.004, 0.076, dev.height - 0.008, 0.006, (0.22, 0.25, 0.29))
            self._draw_box(psu_x, 0.0, back_z - 0.007, 0.072, dev.height - 0.012, 0.002, (0.16, 0.18, 0.21))

            # PSU Exhaust Cooling Fan Grill
            fan_x = psu_x - 0.018 * side
            self._draw_box(fan_x, 0.0, back_z - 0.008, 0.026, dev.height - 0.014, 0.002, (0.07, 0.08, 0.10))
            self._draw_box(fan_x, 0.0, back_z - 0.009, 0.010, 0.010, 0.002, (0.45, 0.48, 0.52))

            # IEC C14 Power Inlet Socket
            sock_x = psu_x + 0.015 * side
            self._draw_box(sock_x, 0.004, back_z - 0.007, 0.024, 0.018, 0.004, (0.04, 0.04, 0.05))
            self._draw_box(sock_x, 0.004, back_z - 0.009, 0.018, 0.013, 0.002, (0.02, 0.02, 0.03))
            # 3 Brass Pins inside socket
            self._draw_box(sock_x, 0.004, back_z - 0.008, 0.012, 0.003, 0.003, (0.88, 0.72, 0.20))
            # Metal wire retention bail clip
            self._draw_box(sock_x, -0.008, back_z - 0.008, 0.020, 0.003, 0.004, (0.75, 0.78, 0.82))

            # PSU Status LED: Solid Glowing Green (AC OK status)
            self._draw_box(psu_x + 0.002 * side, hh - 0.010, back_z - 0.008, 0.005, 0.005, 0.002, (0.1, 0.98, 0.2))

            # Hot-Swap Quick-Release Ejector Handle (Red or Charcoal Latch)
            handle_x = psu_x + 0.033 * side
            self._draw_box(handle_x, 0.0, back_z - 0.010, 0.007, dev.height - 0.014, 0.008, (0.85, 0.18, 0.18))
            self._draw_box(handle_x, 0.0, back_z - 0.014, 0.005, 0.016, 0.004, (0.10, 0.11, 0.13))

            # AC Power Rocker Switch (I / O)
            sw_x = psu_x - 0.030 * side
            self._draw_box(sw_x, -hh + 0.012, back_z - 0.008, 0.007, 0.011, 0.003, (0.12, 0.13, 0.15))
            self._draw_box(sw_x, -hh + 0.012, back_z - 0.009, 0.005, 0.007, 0.002, (0.85, 0.88, 0.92))

        # 4. Central Rear I/O, Fan Modules & Expansion Slots
        if dev.device_type == "switch":
            # Cisco Catalyst: Dual StackWise-480 high-speed stacking ports
            for st_idx, sx in enumerate([-0.045, 0.035]):
                self._draw_box(sx, 0.006, back_z - 0.004, 0.030, 0.016, 0.004, (0.45, 0.48, 0.52))
                self._draw_box(sx, 0.006, back_z - 0.006, 0.024, 0.011, 0.002, (0.08, 0.10, 0.14))
                self._draw_box(sx - 0.018, 0.006, back_z - 0.007, 0.006, 0.006, 0.004, (0.82, 0.72, 0.22))
                self._draw_box(sx + 0.018, 0.006, back_z - 0.007, 0.006, 0.006, 0.004, (0.82, 0.72, 0.22))
            # StackPower Power-Sharing bus connector
            self._draw_box(-0.005, -0.008, back_z - 0.004, 0.024, 0.012, 0.003, (0.10, 0.12, 0.16))
            # OOB Gigabit Ethernet Management Port (RJ45 with link LED)
            self._draw_box(0.075, 0.004, back_z - 0.004, 0.020, 0.016, 0.003, (0.45, 0.48, 0.52))
            self._draw_box(0.075, 0.004, back_z - 0.006, 0.015, 0.012, 0.002, (0.04, 0.04, 0.05))
            self._draw_box(0.075, 0.014, back_z - 0.005, 0.005, 0.005, 0.002, (0.1, 0.98, 0.2))

        elif dev.device_type == "server":
            # Enterprise Server Rear: Dedicated iDRAC/iLO Remote Management Port (Orange bezel)
            self._draw_box(-0.048, 0.012, back_z - 0.004, 0.022, 0.018, 0.003, (0.95, 0.45, 0.08))
            self._draw_box(-0.048, 0.012, back_z - 0.006, 0.016, 0.013, 0.002, (0.04, 0.04, 0.05))
            mgmt_blink = int(now * 6) % 2 == 0
            mgmt_col = (0.2, 0.95, 0.3) if mgmt_blink else (0.08, 0.12, 0.08)
            self._draw_box(-0.048, 0.022, back_z - 0.005, 0.005, 0.005, 0.002, mgmt_col)

            # Blue VGA DB15 connector
            self._draw_box(-0.016, 0.012, back_z - 0.004, 0.024, 0.014, 0.003, (0.15, 0.35, 0.85))
            # Dual USB 3.0 Ports (Blue interior)
            self._draw_box(0.014, 0.012, back_z - 0.004, 0.018, 0.014, 0.003, (0.10, 0.55, 0.95))

            # 4 PCIe Expansion Slot Brackets (Brushed Stainless Steel with vent slots)
            for pcie_idx in range(4):
                px = -0.055 + pcie_idx * 0.036
                self._draw_box(px, -0.014, back_z - 0.003, 0.028, 0.022, 0.002, (0.65, 0.68, 0.74))
                self._draw_box(px, -0.014, back_z - 0.004, 0.020, 0.014, 0.002, (0.08, 0.09, 0.11))
                self._draw_box(px, -0.024, back_z - 0.005, 0.005, 0.005, 0.002, (0.85, 0.88, 0.92))

            # Blue Server Identification UID Beacon LED
            uid_blink = int(now * 2) % 2 == 0
            uid_col = (0.0, 0.75, 1.0) if uid_blink else (0.02, 0.25, 0.40)
            self._draw_box(0.045, 0.015, back_z - 0.005, 0.008, 0.008, 0.002, uid_col)

        else:
            # Router / Firewall / Demarc: Cooling exhaust vents and AUX/Console port
            for vx in [-0.035, 0.035]:
                self._draw_box(vx, 0.0, back_z - 0.004, 0.045, dev.height - 0.014, 0.002, (0.08, 0.09, 0.12))
                self._draw_box(vx, 0.0, back_z - 0.005, 0.012, 0.012, 0.002, (0.45, 0.48, 0.52))
            self._draw_box(0.0, 0.0, back_z - 0.004, 0.020, 0.016, 0.003, (0.40, 0.44, 0.48))
            self._draw_box(0.0, 0.0, back_z - 0.006, 0.015, 0.012, 0.002, (0.04, 0.04, 0.05))

        # 5. REAL 3D POWER CORDS (C13-to-C14) TO REAR PDUS (FEED A = BLUE, FEED B = RED)
        if getattr(dev, "is_showcase", False):
            return

        cord_radius = 0.0062  # Heavy-duty 12AWG datacenter power cord (12.4mm diameter)

        # Cord A: From PSU 1 on left to PDU-A on left rear post (Feed A - Enterprise Royal Blue)
        c13_a_x = -0.125
        self._draw_box(c13_a_x, 0.004, back_z - 0.016, 0.024, 0.018, 0.024, (0.08, 0.08, 0.10)) # C13 plug body
        self._draw_box(c13_a_x, 0.004, back_z - 0.030, 0.016, 0.014, 0.014, (0.16, 0.18, 0.22)) # rubber boot
        self._draw_box(c13_a_x, 0.004, back_z - 0.026, 0.018, 0.016, 0.006, (0.0, 0.48, 0.95))  # Feed A blue collar ring

        p0_a = (c13_a_x, 0.004, back_z - 0.038)
        p3_a_z = min(-0.340, back_z - 0.040)
        p3_a = (-0.225, -0.016, p3_a_z)
        # Molded IEC C14 Plug at PDU-A receptacle
        self._draw_box(p3_a[0], p3_a[1], p3_a[2] + 0.014, 0.022, 0.016, 0.022, (0.08, 0.08, 0.10))
        self._draw_box(p3_a[0], p3_a[1], p3_a[2] + 0.006, 0.018, 0.014, 0.006, (0.0, 0.48, 0.95))

        # Natural gravitational catenary loop
        p1_a = (p0_a[0] - 0.025, p0_a[1] - 0.065, p0_a[2] - 0.055)
        p2_a = (p3_a[0] + 0.035, p3_a[1] - 0.055, p3_a[2] + 0.055)
        self._draw_curved_cord(p0_a, p1_a, p2_a, p3_a, radius=cord_radius, color=(0.04, 0.38, 0.88), num_segments=12)

        # Cord B: From PSU 2 on right to PDU-B on right rear post (Feed B - Enterprise Crimson Red)
        c13_b_x = 0.125
        self._draw_box(c13_b_x, 0.004, back_z - 0.016, 0.024, 0.018, 0.024, (0.08, 0.08, 0.10))
        self._draw_box(c13_b_x, 0.004, back_z - 0.030, 0.016, 0.014, 0.014, (0.16, 0.18, 0.22))
        self._draw_box(c13_b_x, 0.004, back_z - 0.026, 0.018, 0.016, 0.006, (0.88, 0.15, 0.15))

        p0_b = (c13_b_x, 0.004, back_z - 0.038)
        p3_b_z = min(-0.340, back_z - 0.040)
        p3_b = (0.225, -0.016, p3_b_z)
        # Molded IEC C14 Plug at PDU-B receptacle
        self._draw_box(p3_b[0], p3_b[1], p3_b[2] + 0.014, 0.022, 0.016, 0.022, (0.08, 0.08, 0.10))
        self._draw_box(p3_b[0], p3_b[1], p3_b[2] + 0.006, 0.018, 0.014, 0.006, (0.88, 0.15, 0.15))

        p1_b = (p0_b[0] + 0.025, p0_b[1] - 0.065, p0_b[2] - 0.055)
        p2_b = (p3_b[0] - 0.035, p3_b[1] - 0.055, p3_b[2] + 0.055)
        self._draw_curved_cord(p0_b, p1_b, p2_b, p3_b, radius=cord_radius, color=(0.85, 0.15, 0.16), num_segments=12)

        # 6. REAR DATA / STACKING / MANAGEMENT CABLING
        if dev.device_type == "switch":
            # Cisco StackWise-480 Heavy Braided Stacking Loop
            sw_p0 = (-0.045, 0.006, back_z - 0.010)
            sw_p3 = ( 0.035, 0.006, back_z - 0.010)
            sw_p1 = (-0.045, 0.055, back_z - 0.075)
            sw_p2 = ( 0.035, 0.055, back_z - 0.075)
            self._draw_curved_cord(sw_p0, sw_p1, sw_p2, sw_p3, radius=0.0055, color=(0.28, 0.32, 0.38), num_segments=12)

        elif dev.device_type == "server":
            # Orange Cat6A Patch Cable from iDRAC Port to Left Cable Manager
            idrac_p0 = (-0.048, 0.012, back_z - 0.008)
            idrac_p3 = (-0.230, -0.045, min(-0.330, back_z - 0.030))
            idrac_p1 = (-0.048, -0.040, back_z - 0.065)
            idrac_p2 = (-0.180, -0.060, idrac_p3[2] + 0.040)
            self._draw_curved_cord(idrac_p0, idrac_p1, idrac_p2, idrac_p3, radius=0.0035, color=(0.95, 0.48, 0.08), num_segments=10)

    def _draw_rj45_connector(self, pos, normal, cable_color, is_laptop=False):
        """Renders an authentic RJ45 modular plug with clear polycarbonate body, gold pins, molded snagless boot, and latch."""
        nx, ny, nz = normal
        fx, fy, fz = nx, ny, nz

        # Up and Right orthogonal frame vectors
        if abs(fy) < 0.9:
            ux, uy, uz = 0.0, 1.0, 0.0
        else:
            ux, uy, uz = 0.0, 0.0, -1.0

        r, g, b = cable_color
        boot_color = (r * 0.82, g * 0.82, b * 0.82)
        if is_laptop and abs(nx) > 0.5:
            boot_color = (0.18, 0.20, 0.24)

        def draw_box_rel(offset_f, offset_u, size_r, size_u, size_f, col):
            cx = pos[0] + fx * offset_f + ux * offset_u
            cy = pos[1] + fy * offset_f + uy * offset_u
            cz = pos[2] + fz * offset_f + uz * offset_u
            if abs(fz) > 0.9:
                self._draw_box(cx, cy, cz, size_r, size_u, size_f, col)
            else:
                self._draw_box(cx, cy, cz, size_f, size_u, size_r, col)

        # 1. Clear Polycarbonate 8P8C Plug Head (seated into socket, extends 0..7mm forward)
        clear_head_color = (0.84, 0.90, 0.96)
        draw_box_rel(0.0035, 0.0, 0.0112, 0.0075, 0.0070, clear_head_color)

        # 2. Gold Contact Pins (visible inside the clear tip)
        gold_color = (0.95, 0.78, 0.18)
        draw_box_rel(0.0015, -0.0012, 0.0078, 0.0015, 0.0028, gold_color)

        # 3. Molded Snagless Strain-Relief Rubber Boot (extends 7..18mm forward)
        draw_box_rel(0.0125, 0.0, 0.0116, 0.0088, 0.0110, boot_color)

        # 4. Snagless Release Latch Lever & Protective Hood (on top +U)
        latch_color = (min(1.0, boot_color[0] * 1.25), min(1.0, boot_color[1] * 1.25), min(1.0, boot_color[2] * 1.25))
        # Release clip lever
        draw_box_rel(0.0105, 0.0050, 0.0034, 0.0018, 0.0080, latch_color)
        # Snagless hood arch
        draw_box_rel(0.0145, 0.0051, 0.0042, 0.0016, 0.0050, boot_color)

        # 5. Tapered Collar / Strain-Relief Neck (extends 18..24mm forward)
        draw_box_rel(0.0210, 0.0, 0.0074, 0.0074, 0.0060, boot_color)

    def _render_cables(self, cables, devices=None, camera=None):
        """
        Renders 3D cables with Parallel Transport Bishop frames (zero twist), smooth round tube,
        and authentic RJ45 connectors. Caches static cable geometry in an OpenGL display list.
        """
        if not cables:
            return

        # Angle / position culling: front patch cables are completely hidden behind racks in the hot aisle
        cam_z = getattr(camera, "z", getattr(camera, "base_eye_z", 0.0)) if camera else 0.0
        if cam_z < -1.65:
            return

        # Fast cache key to detect topology or cable state modifications
        cables_key = (
            len(cables),
            tuple(
                (id(c), c.cable_type, c.is_damaged,
                 id(c.port_a), getattr(c.port_a, "name", ""),
                 id(c.port_b), getattr(c.port_b, "name", ""),
                 c.port_a.device.pos_x if c.port_a and c.port_a.device else 0,
                 c.port_a.device.pos_y if c.port_a and c.port_a.device else 0,
                 c.port_b.device.pos_x if c.port_b and c.port_b.device else 0,
                 c.port_b.device.pos_y if c.port_b and c.port_b.device else 0)
                for c in cables
            )
        )

        if self.cables_display_list is None or self._cables_cache_key != cables_key:
            if self.cables_display_list is not None:
                try:
                    glDeleteLists(self.cables_display_list, 1)
                except Exception:
                    pass
            self.cables_display_list = glGenLists(1)
            glNewList(self.cables_display_list, GL_COMPILE)
            self._compile_cables_geometry(cables, devices)
            glEndList()
            self._cables_cache_key = cables_key

        glCallList(self.cables_display_list)

    def _compile_cables_geometry(self, cables, devices=None):
        """Compiles 3D cables and RJ45 modular plugs into the display list."""
        glDisable(GL_LIGHTING)

        # Precomputed 12-sided smooth cylinder trigonometry table (every 30 degrees)
        NUM_SIDES = 12
        cos_tab = (
            1.0, 0.866025, 0.5, 0.0, -0.5, -0.866025,
            -1.0, -0.866025, -0.5, 0.0, 0.5, 0.866025
        )
        sin_tab = (
            0.0, 0.5, 0.866025, 1.0, 0.866025, 0.5,
            0.0, -0.5, -0.866025, -1.0, -0.866025, -0.5
        )

        radius = 0.0030  # 3.0mm radius = 6.0mm Cat6 round patch cable
        # Directional overhead datacenter lighting vector (0.0, 0.88, 0.47)
        lx, ly, lz = 0.0, 0.88, 0.47

        for cable in cables:
            pts = cable.compute_curve_points(num_segments=24, devices=devices)
            if len(pts) < 2:
                continue

            r, g, b = cable.color
            if cable.is_damaged:
                r, g, b = 0.92, 0.15, 0.15  # Vivid red for damaged / disconnected

            # 1. Render Authentic RJ45 Connectors at both endpoints
            for port in (cable.port_a, cable.port_b):
                if not port or not port.device:
                    continue
                pp = port.get_world_pos()
                is_laptop = (port.device.device_type == "laptop")
                if is_laptop:
                    lx_dev = pp[0] - port.device.pos_x
                    normal = (-1.0, 0.0, 0.0) if lx_dev < 0 else (1.0, 0.0, 0.0)
                else:
                    normal = (0.0, 0.0, 1.0)

                self._draw_rj45_connector(pp, normal, (r, g, b), is_laptop=is_laptop)

            # 2. Compute Twist-Free Reference Frames using Parallel Transport (Bishop Frame)
            N = len(pts)
            frames = []
            for i in range(N):
                if i == 0:
                    tx = pts[1][0] - pts[0][0]
                    ty = pts[1][1] - pts[0][1]
                    tz = pts[1][2] - pts[0][2]
                elif i == N - 1:
                    tx = pts[N-1][0] - pts[N-2][0]
                    ty = pts[N-1][1] - pts[N-2][1]
                    tz = pts[N-1][2] - pts[N-2][2]
                else:
                    tx = pts[i+1][0] - pts[i-1][0]
                    ty = pts[i+1][1] - pts[i-1][1]
                    tz = pts[i+1][2] - pts[i-1][2]

                t_len = math.sqrt(tx*tx + ty*ty + tz*tz)
                if t_len > 1e-6:
                    tx, ty, tz = tx / t_len, ty / t_len, tz / t_len
                else:
                    tx, ty, tz = 0.0, 0.0, 1.0

                if i == 0:
                    # Initial normal orthogonal to t0
                    if abs(ty) < 0.92:
                        ref_x, ref_y, ref_z = 0.0, 1.0, 0.0
                    else:
                        ref_x, ref_y, ref_z = 1.0, 0.0, 0.0
                    dot = ref_x * tx + ref_y * ty + ref_z * tz
                    nx = ref_x - dot * tx
                    ny = ref_y - dot * ty
                    nz = ref_z - dot * tz
                    n_len = math.sqrt(nx*nx + ny*ny + nz*nz)
                    if n_len > 1e-6:
                        nx, ny, nz = nx / n_len, ny / n_len, nz / n_len
                    else:
                        nx, ny, nz = 1.0, 0.0, 0.0
                else:
                    # Parallel transport previous normal onto plane orthogonal to current tangent
                    prev_n = frames[-1][1]
                    dot = prev_n[0] * tx + prev_n[1] * ty + prev_n[2] * tz
                    nx = prev_n[0] - dot * tx
                    ny = prev_n[1] - dot * ty
                    nz = prev_n[2] - dot * tz
                    n_len = math.sqrt(nx*nx + ny*ny + nz*nz)
                    if n_len > 1e-6:
                        nx, ny, nz = nx / n_len, ny / n_len, nz / n_len
                    else:
                        nx, ny, nz = prev_n[0], prev_n[1], prev_n[2]

                bx = ty * nz - tz * ny
                by = tz * nx - tx * nz
                bz = tx * ny - ty * nx
                frames.append(((tx, ty, tz), (nx, ny, nz), (bx, by, bz)))

            # 3. Compute Smooth Ring Vertices & Per-Vertex Gouraud Illumination
            rings = []
            ring_colors = []
            for i in range(N):
                p_curr = pts[i]
                _, (nx, ny, nz), (bx, by, bz) = frames[i]

                ring_verts = []
                ring_cols = []
                for k in range(NUM_SIDES):
                    c, s = cos_tab[k], sin_tab[k]
                    # Radial normal on the cylindrical tube surface
                    vnx = c * nx + s * bx
                    vny = c * ny + s * by
                    vnz = c * nz + s * bz

                    vx = p_curr[0] + vnx * radius
                    vy = p_curr[1] + vny * radius
                    vz = p_curr[2] + vnz * radius
                    ring_verts.append((vx, vy, vz))

                    # Continuous smooth diffuse lighting from overhead datacenter lights
                    dot_l = max(0.0, vnx * lx + vny * ly + vnz * lz)
                    bright = 0.45 + 0.55 * dot_l
                    # Subtle specular shine running along the top of the round cable
                    if dot_l > 0.55:
                        bright = min(1.35, bright + ((dot_l - 0.55) ** 2) * 0.45)

                    cr = min(1.0, r * bright)
                    cg = min(1.0, g * bright)
                    cb = min(1.0, b * bright)
                    ring_cols.append((cr, cg, cb))

                rings.append(ring_verts)
                ring_colors.append(ring_cols)

            # 4. Render Seamless Smooth Round Tube with Gouraud Shading
            glBegin(GL_QUADS)
            for i in range(N - 1):
                r0 = rings[i]
                r1 = rings[i + 1]
                c0 = ring_colors[i]
                c1 = ring_colors[i + 1]
                for k in range(NUM_SIDES):
                    k_next = (k + 1) % NUM_SIDES
                    glColor3f(*c0[k])
                    glVertex3f(*r0[k])
                    glColor3f(*c0[k_next])
                    glVertex3f(*r0[k_next])
                    glColor3f(*c1[k_next])
                    glVertex3f(*r1[k_next])
                    glColor3f(*c1[k])
                    glVertex3f(*r1[k])
            glEnd()

    def _render_highlight(self, dev, port, now):
        """Draws neon cyan/golden wireframe bounding box with animated targeting brackets."""
        # Respect depth testing so wireframe is occluded by foreground obstacles (posts, racks, etc.)
        glEnable(GL_DEPTH_TEST)
        glDepthMask(GL_FALSE)

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
            w_margin = 0.006 if dev.device_type != "laptop" else 0.015
            h_margin = 0.006 if dev.device_type != "laptop" else 0.015
            d_margin = 0.008 if dev.device_type != "laptop" else 0.015
            self._draw_wireframe_box(dev.pos_x, dev.pos_y, dev.pos_z, dev.width + w_margin, dev.height + h_margin, dev.depth + d_margin)

        glDepthMask(GL_TRUE)

    def _draw_box(self, x, y, z, w, h, d, color):
        """Draws a 3D box with directional illumination for crisp edge definition and contrast."""
        r, g, b = color[0], color[1], color[2]
        hw, hh, hd = w / 2.0, h / 2.0, d / 2.0

        glBegin(GL_QUADS)
        # Front (+Z, direct frontal eye-level light)
        glColor3f(r, g, b)
        glVertex3f(x - hw, y - hh, z + hd)
        glVertex3f(x + hw, y - hh, z + hd)
        glVertex3f(x + hw, y + hh, z + hd)
        glVertex3f(x - hw, y + hh, z + hd)

        # Back (-Z, away from aisle light)
        glColor3f(r * 0.72, g * 0.72, b * 0.72)
        glVertex3f(x - hw, y - hh, z - hd)
        glVertex3f(x - hw, y + hh, z - hd)
        glVertex3f(x + hw, y + hh, z - hd)
        glVertex3f(x + hw, y - hh, z - hd)

        # Top (+Y, bright overhead datacenter ceiling LED panels)
        glColor3f(min(1.0, r * 1.15), min(1.0, g * 1.15), min(1.0, b * 1.15))
        glVertex3f(x - hw, y + hh, z - hd)
        glVertex3f(x - hw, y + hh, z + hd)
        glVertex3f(x + hw, y + hh, z + hd)
        glVertex3f(x + hw, y + hh, z - hd)

        # Bottom (-Y, underside contact shadow)
        glColor3f(r * 0.58, g * 0.58, b * 0.58)
        glVertex3f(x - hw, y - hh, z - hd)
        glVertex3f(x + hw, y - hh, z - hd)
        glVertex3f(x + hw, y - hh, z + hd)
        glVertex3f(x - hw, y - hh, z + hd)

        # Right (+X, directional side shadow)
        glColor3f(r * 0.85, g * 0.85, b * 0.85)
        glVertex3f(x + hw, y - hh, z - hd)
        glVertex3f(x + hw, y + hh, z - hd)
        glVertex3f(x + hw, y + hh, z + hd)
        glVertex3f(x + hw, y - hh, z + hd)

        # Left (-X, directional side shadow)
        glColor3f(r * 0.88, g * 0.88, b * 0.88)
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

    def _draw_turntable_pedestal(self, radius=0.38, y=-0.04, now=0.0):
        """Draws high-tech sci-fi circular pedestal platform under the showcase device (Clean Light Studio Theme)."""
        segments = 48
        # Outer brushed aluminum metallic disc
        glBegin(GL_TRIANGLE_FAN)
        glColor3f(0.86, 0.89, 0.93)
        glVertex3f(0.0, y, 0.0)
        for i in range(segments + 1):
            ang = i * (2.0 * math.pi / segments)
            px = math.cos(ang) * radius
            pz = math.sin(ang) * radius
            glColor3f(0.78, 0.82, 0.88)
            glVertex3f(px, y, pz)
        glEnd()

        # Concentric glowing enterprise blue accent ring
        pulse = 0.85 + 0.15 * math.sin(now * 3.0)
        glLineWidth(2.5)
        glBegin(GL_LINE_LOOP)
        glColor4f(0.0, 0.45 * pulse, 0.92 * pulse, 0.95)
        r_glow = radius * 0.92
        for i in range(segments):
            ang = i * (2.0 * math.pi / segments)
            glVertex3f(math.cos(ang) * r_glow, y + 0.001, math.sin(ang) * r_glow)
        glEnd()

        # Inner subtle ring
        glLineWidth(1.0)
        glBegin(GL_LINE_LOOP)
        glColor4f(0.55, 0.65, 0.78, 0.7)
        r_inner = radius * 0.70
        for i in range(segments):
            ang = i * (2.0 * math.pi / segments)
            glVertex3f(math.cos(ang) * r_inner, y + 0.001, math.sin(ang) * r_inner)
        glEnd()

        # Radial tick marks at 45 degree intervals
        glBegin(GL_LINES)
        glColor4f(0.0, 0.40, 0.85, 0.9)
        for deg in (0, 45, 90, 135, 180, 225, 270, 315):
            rad = math.radians(deg)
            c = math.cos(rad)
            s = math.sin(rad)
            glVertex3f(c * (radius * 0.80), y + 0.001, s * (radius * 0.80))
            glVertex3f(c * (radius * 0.94), y + 0.001, s * (radius * 0.94))
        glEnd()

    def render_device_preview(self, dev, yaw, pitch, now, viewport_rect, screen_w, screen_h):
        """Renders an interactive 3D device model on a high-tech pedestal in a dedicated viewport."""
        vx, vy, vw, vh = viewport_rect
        if vw <= 0 or vh <= 0:
            return

        gl_y = screen_h - (vy + vh)

        glEnable(GL_SCISSOR_TEST)
        glScissor(vx, gl_y, vw, vh)
        glViewport(vx, gl_y, vw, vh)

        # Clear viewport background with sleek light studio datacenter tone
        glClearColor(0.93, 0.95, 0.98, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        aspect = float(vw) / float(max(1, vh))
        gluPerspective(38.0, aspect, 0.05, 50.0)

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        if dev is None:
            # If no device, restore and return
            glPopMatrix()
            glMatrixMode(GL_PROJECTION)
            glPopMatrix()
            glMatrixMode(GL_MODELVIEW)
            glDisable(GL_SCISSOR_TEST)
            glViewport(0, 0, screen_w, screen_h)
            return

        # Fixed camera distance tailored to device form factor (NO mouse wheel zoom per user request)
        if dev.device_type == "laptop":
            dist = 0.62
            pedestal_y = -0.06
            pedestal_r = 0.28
        elif dev.device_type == "server":
            dist = 1.15
            pedestal_y = -dev.height / 2.0 - 0.02
            pedestal_r = 0.42
        else:
            dist = 1.05
            pedestal_y = -dev.height / 2.0 - 0.02
            pedestal_r = 0.38

        glTranslatef(0.0, 0.0, -dist)
        glRotatef(pitch, 1.0, 0.0, 0.0)
        glRotatef(yaw, 0.0, 1.0, 0.0)

        # 1. Render High-Tech Turntable Pedestal
        self._draw_turntable_pedestal(radius=pedestal_r, y=pedestal_y, now=now)

        # 2. Render 3D Device Geometry
        if dev.device_type == "laptop":
            if self.laptop_linux_display_list is None or not glIsList(self.laptop_linux_display_list):
                self.laptop_linux_display_list = glGenLists(1)
                glNewList(self.laptop_linux_display_list, GL_COMPILE)
                self._compile_laptop_static_list(is_windows=False)
                glEndList()
            if self.laptop_win_display_list is None or not glIsList(self.laptop_win_display_list):
                self.laptop_win_display_list = glGenLists(1)
                glNewList(self.laptop_win_display_list, GL_COMPILE)
                self._compile_laptop_static_list(is_windows=True)
                glEndList()
            glPushMatrix()
            glTranslatef(0.0, -0.02, 0.0)
            self._render_laptop(dev, now)
            glPopMatrix()
        else:
            # Compile display lists if needed
            if getattr(dev, "_dl_body", None) is None or not glIsList(dev._dl_body):
                dev._dl_body = glGenLists(1)
                self._device_display_lists.add(dev._dl_body)
                glNewList(dev._dl_body, GL_COMPILE)
                self._compile_device_body(dev)
                glEndList()

            if getattr(dev, "_dl_front", None) is None or not glIsList(dev._dl_front):
                dev._dl_front = glGenLists(1)
                self._device_display_lists.add(dev._dl_front)
                glNewList(dev._dl_front, GL_COMPILE)
                self._compile_device_front(dev)
                glEndList()

            if getattr(dev, "_dl_rear", None) is None or not glIsList(dev._dl_rear):
                dev._dl_rear = glGenLists(1)
                self._device_display_lists.add(dev._dl_rear)
                glNewList(dev._dl_rear, GL_COMPILE)
                self._compile_device_rear(dev)
                glEndList()

            # Render complete solid chassis enclosure
            glCallList(dev._dl_body)

            # Render front ports, bezels, and blinking LEDs
            glCallList(dev._dl_front)
            self._render_device_dynamic_front(dev, now)

            # Render rear PSUs, fan grilles, switches, and ports
            glCallList(dev._dl_rear)
            self._render_device_dynamic_rear(dev, now)

        # Restore OpenGL state
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glDisable(GL_SCISSOR_TEST)
        glViewport(0, 0, screen_w, screen_h)
        glClearColor(0.88, 0.91, 0.95, 1.0)

