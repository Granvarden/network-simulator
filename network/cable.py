"""
network/cable.py - Physical layer cable simulation
Represents Cat6 (UTP copper), Fiber Optic (LC-LC duplex), and Roll-over Console cables.
Computes 3D catenary hanging curves between connected rack ports.
"""

import math

class CableType:
    CAT6 = "CAT6"         # Blue / Yellow / Green RJ45
    FIBER = "FIBER"       # Orange / Aqua LC-LC
    CONSOLE = "CONSOLE"   # Light Blue Flat RJ45-to-DB9/USB

CABLE_COLORS = {
    CableType.CAT6: (0.1, 0.45, 0.95),      # Enterprise Blue
    CableType.FIBER: (0.1, 0.85, 0.75),     # Aqua OM3/OM4
    CableType.CONSOLE: (0.3, 0.75, 0.9)     # Cisco Light Blue
}

class Cable:
    _counter = 1

    def __init__(self, port_a, port_b, cable_type=CableType.CAT6, color=None):
        self.id = f"cbl_{Cable._counter}"
        Cable._counter += 1
        self.port_a = port_a
        self.port_b = port_b
        self.cable_type = cable_type
        self.color = color if color else CABLE_COLORS.get(cable_type, (0.2, 0.6, 1.0))
        self.is_damaged = False  # Used for challenge/troubleshooting scenarios

        # Bind both ports
        self.port_a.connect_cable(self)
        self.port_b.connect_cable(self)

    def get_peer_port(self, from_port):
        if from_port == self.port_a:
            return self.port_b
        elif from_port == self.port_b:
            return self.port_a
        return None

    def disconnect(self):
        if self.port_a:
            self.port_a.cable = None
        if self.port_b:
            self.port_b.cable = None
        self.port_a = None
        self.port_b = None

    def compute_curve_points(self, num_segments=16):
        """Generates 3D points forming a realistic slack/sagging cable curve."""
        if not self.port_a or not self.port_b:
            return []
        p1 = self.port_a.get_world_pos()
        p2 = self.port_b.get_world_pos()
        if not p1 or not p2:
            return []

        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dz = p2[2] - p1[2]
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)

        # Sag amount proportional to distance
        sag = min(0.4, max(0.08, dist * 0.18))

        points = []
        for i in range(num_segments + 1):
            t = i / float(num_segments)
            # Parabolic sag downwards
            sag_offset = -4.0 * sag * t * (1.0 - t)
            # Outward forward curve towards cold aisle to prevent clipping into equipment/posts
            forward_curve = max(0.0, dist * 0.06) * 4.0 * t * (1.0 - t)

            px = p1[0] + dx * t
            py = p1[1] + dy * t + sag_offset
            pz = p1[2] + dz * t + forward_curve
            points.append((px, py, pz))
        return points
