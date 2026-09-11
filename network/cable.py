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
        if hasattr(self.port_a.device, "_stp_dirty"):
            self.port_a.device._stp_dirty = True
        if hasattr(self.port_b.device, "_stp_dirty"):
            self.port_b.device._stp_dirty = True
        self._cached_points = None
        self._last_endpoints = None

    def get_peer_port(self, from_port):
        if from_port == self.port_a:
            return self.port_b
        elif from_port == self.port_b:
            return self.port_a
        return None

    def disconnect(self):
        self._cached_points = None
        self._last_endpoints = None
        if self.port_a:
            if hasattr(self.port_a.device, "_stp_dirty"):
                self.port_a.device._stp_dirty = True
            self.port_a.cable = None
        if self.port_b:
            if hasattr(self.port_b.device, "_stp_dirty"):
                self.port_b.device._stp_dirty = True
            self.port_b.cable = None
        self.port_a = None
        self.port_b = None

    def compute_curve_points(self, num_segments=24, devices=None):
        """Generates 3D points forming a realistic slack/sagging cable curve with obstacle avoidance."""
        if not self.port_a or not self.port_b:
            return []
        p1 = self.port_a.get_world_pos()
        p2 = self.port_b.get_world_pos()
        if not p1 or not p2:
            return []

        dev_a = self.port_a.device
        dev_b = self.port_b.device

        # Caching key
        dev_count = len(devices) if devices else 0
        curr_endpoints = (p1[0], p1[1], p1[2], p2[0], p2[1], p2[2], num_segments, dev_count)
        if self._cached_points is not None and self._last_endpoints == curr_endpoints:
            return self._cached_points

        # Port normal exit directions
        # For rack devices, ports face forward (+Z) into cold aisle
        # For laptop, eth0 is left (-X) and con0 is right (+X)
        if dev_a and dev_a.device_type == "laptop":
            lx = p1[0] - dev_a.pos_x
            n1 = (-1.0, 0.0, 0.0) if lx < 0 else (1.0, 0.0, 0.0)
        else:
            n1 = (0.0, 0.0, 1.0)

        if dev_b and dev_b.device_type == "laptop":
            lx = p2[0] - dev_b.pos_x
            n2 = (-1.0, 0.0, 0.0) if lx < 0 else (1.0, 0.0, 0.0)
        else:
            n2 = (0.0, 0.0, 1.0)

        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dz = p2[2] - p1[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        dist_y = abs(dy)

        # Wire endpoints (exiting from strain-relief boot along normal vector)
        boot_len = 0.024
        w_start = (p1[0] + n1[0] * boot_len, p1[1] + n1[1] * boot_len, p1[2] + n1[2] * boot_len)
        w_end = (p2[0] + n2[0] * boot_len, p2[1] + n2[1] * boot_len, p2[2] + n2[2] * boot_len)

        # Detect obstacles / devices in the same rack column between p1 and p2
        y_min = min(w_start[1], w_end[1])
        y_max = max(w_start[1], w_end[1])
        max_obstacle_z = max(w_start[2], w_end[2])

        is_same_rack = False
        if dev_a and dev_b and hasattr(dev_a, "rack_id") and hasattr(dev_b, "rack_id"):
            if dev_a.rack_id == dev_b.rack_id and dev_a.device_type != "laptop" and dev_b.device_type != "laptop":
                is_same_rack = True

        if devices:
            for dev in devices:
                if dev == dev_a or dev == dev_b:
                    continue
                if dev.device_type == "laptop":
                    continue
                # Check if device is in the same rack column
                if abs(dev.pos_x - w_start[0]) < 0.28:
                    dev_y_min = dev.pos_y - dev.height / 2.0 - 0.02
                    dev_y_max = dev.pos_y + dev.height / 2.0 + 0.02
                    if not (dev_y_max < y_min or dev_y_min > y_max):
                        dev_z_front = dev.pos_z + dev.depth / 2.0
                        if dev_z_front > max_obstacle_z:
                            max_obstacle_z = dev_z_front
        elif is_same_rack:
            dev_z_front = dev_a.pos_z + dev_a.depth / 2.0
            if dev_z_front > max_obstacle_z:
                max_obstacle_z = dev_z_front

        # Forward arc into cold aisle to prevent clipping into intermediate equipment
        if dist_y > 0.06:
            # Vertical drop across slots in rack: curve forward into aisle
            forward_clearance = max(0.12, min(0.22, 0.09 + dist_y * 0.12))
            target_forward_z = max_obstacle_z + forward_clearance
        else:
            # Mostly horizontal connection (adjacent ports or same level)
            forward_clearance = max(0.04, min(0.12, dist * 0.10))
            target_forward_z = max_obstacle_z + forward_clearance

        # Calculate smooth Bezier control points that naturally clear obstacles WITHOUT hard clamping
        z_ends = (w_start[2] + w_end[2]) / 2.0
        z_ctrl = max(target_forward_z, (target_forward_z - 0.25 * z_ends) / 0.75)

        # Lead length along exit normal
        lead_len = min(0.08, max(0.03, dist * 0.15))

        # Gravity sag (catenary effect)
        sag_amount = min(0.10, max(0.015, dist * 0.07))

        P0 = w_start
        if dist_y > 0.08:
            # Vertical connection: Control points depart along normal and curve towards mid-aisle
            P1 = (
                w_start[0] + n1[0] * lead_len,
                w_start[1] + dy * 0.28,
                z_ctrl
            )
            P2 = (
                w_end[0] + n2[0] * lead_len,
                w_end[1] - dy * 0.28,
                z_ctrl
            )
        else:
            # Horizontal connection
            P1 = (
                w_start[0] + n1[0] * lead_len,
                w_start[1] - sag_amount * 0.5,
                max(w_start[2] + n1[2] * lead_len, target_forward_z * 0.85 + w_start[2] * 0.15)
            )
            P2 = (
                w_end[0] + n2[0] * lead_len,
                w_end[1] - sag_amount * 0.5,
                max(w_end[2] + n2[2] * lead_len, target_forward_z * 0.85 + w_end[2] * 0.15)
            )
        P3 = w_end

        # Points start with straight normal lead-out from port
        lead_sample_start = (p1[0] + n1[0] * (boot_len * 0.5), p1[1] + n1[1] * (boot_len * 0.5), p1[2] + n1[2] * (boot_len * 0.5))
        lead_sample_end = (p2[0] + n2[0] * (boot_len * 0.5), p2[1] + n2[1] * (boot_len * 0.5), p2[2] + n2[2] * (boot_len * 0.5))

        points = [p1, lead_sample_start, w_start]
        for i in range(1, num_segments):
            t = i / float(num_segments)
            it = 1.0 - t

            bx = it**3 * P0[0] + 3 * it**2 * t * P1[0] + 3 * it * t**2 * P2[0] + t**3 * P3[0]
            by = it**3 * P0[1] + 3 * it**2 * t * P1[1] + 3 * it * t**2 * P2[1] + t**3 * P3[1]
            bz = it**3 * P0[2] + 3 * it**2 * t * P1[2] + 3 * it * t**2 * P2[2] + t**3 * P3[2]

            # Parabolic gravity sag for horizontal cables
            if dist_y < 0.20:
                parabola = 4.0 * t * it
                by -= sag_amount * parabola

            points.append((bx, by, bz))

        points.append(w_end)
        points.append(lead_sample_end)
        points.append(p2)

        self._cached_points = points
        self._last_endpoints = curr_endpoints
        return points
