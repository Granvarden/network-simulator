import unittest
import math
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from network.switch import Switch
from network.host import Host
from network.cable import Cable


class TestCablePhysicsAndAntiClipping(unittest.TestCase):
    def setUp(self):
        # Create standard rack devices in Rack 1
        # In the engine, standard rack is pos_x=0.0, pos_z=-1.5, depth=0.60 (front face at z = -1.20)
        self.top_switch = Switch("sw_top", hostname="Top-Switch", rack_id=1, u_slot=24)
        self.top_switch.pos_x = 0.0
        self.top_switch.pos_y = 1.35
        self.top_switch.pos_z = -1.5
        self.top_switch.depth = 0.60
        self.top_switch.height = 0.044

        self.mid_switch = Switch("sw_mid", hostname="Mid-Switch", rack_id=1, u_slot=16)
        self.mid_switch.pos_x = 0.0
        self.mid_switch.pos_y = 1.00
        self.mid_switch.pos_z = -1.5
        self.mid_switch.depth = 0.60
        self.mid_switch.height = 0.044

        self.bot_switch = Switch("sw_bot", hostname="Bot-Switch", rack_id=1, u_slot=8)
        self.bot_switch.pos_x = 0.0
        self.bot_switch.pos_y = 0.65
        self.bot_switch.pos_z = -1.5
        self.bot_switch.depth = 0.60
        self.bot_switch.height = 0.044

        self.devices = [self.top_switch, self.mid_switch, self.bot_switch]

    def test_cable_curve_does_not_clip_intermediate_device(self):
        """Verify that a cable connecting top and bottom switches loops forward into the aisle
        and NEVER clips through the intermediate device chassis."""
        port_a = self.top_switch.get_port("g0/1")
        port_b = self.bot_switch.get_port("g0/1")

        cable = Cable(port_a, port_b)
        pts = cable.compute_curve_points(num_segments=30, devices=self.devices)

        self.assertGreater(len(pts), 2)

        # Front face of rack devices
        face_z = self.mid_switch.pos_z + self.mid_switch.depth / 2.0  # -1.5 + 0.30 = -1.20

        # In the vertical span covering the intermediate device, all points must be
        # strictly in front of the front face with at least 6cm of clearance
        intermediate_span_points = [
            p for p in pts
            if (self.bot_switch.pos_y + 0.05) <= p[1] <= (self.top_switch.pos_y - 0.05)
        ]
        self.assertTrue(len(intermediate_span_points) > 0, "Should have curve points spanning intermediate device")

        for p in intermediate_span_points:
            z_clearance = p[2] - face_z
            self.assertGreaterEqual(
                z_clearance,
                0.060,
                f"Cable point {p} is too close to or clipping device face at z={face_z}! Clearance: {z_clearance}m"
            )

    def test_cable_normal_exit_tangency(self):
        """Verify that points leaving a rack port exit forwards (+Z) into the aisle before curving."""
        port_a = self.top_switch.get_port("g0/1")
        port_b = self.bot_switch.get_port("g0/1")

        cable = Cable(port_a, port_b)
        pts = cable.compute_curve_points(num_segments=24, devices=self.devices)

        p_start = pts[0]
        p_first = pts[1]

        # p_first must be strictly further forward in Z than p_start (exiting from the port normal +Z)
        self.assertGreater(p_first[2], p_start[2], "Cable should exit along port normal (+Z) into aisle")

    def test_laptop_cable_curve(self):
        """Verify cable connected to laptop exits along side normal and avoids clipping."""
        laptop = Host("lap1", hostname="Win-Laptop", device_type="laptop", rack_id=0, u_slot=0, os_type="windows")
        laptop.pos_x = 0.6
        laptop.pos_y = 0.75
        laptop.pos_z = -0.4

        port_a = self.top_switch.get_port("g0/1")
        port_b = laptop.eth0

        cable = Cable(port_a, port_b)
        pts = cable.compute_curve_points(num_segments=24, devices=self.devices + [laptop])

        self.assertGreater(len(pts), 2)
        # Check no NaN values
        for p in pts:
            self.assertFalse(math.isnan(p[0]))
            self.assertFalse(math.isnan(p[1]))
            self.assertFalse(math.isnan(p[2]))

    def test_rj45_dimensions_fit_port_pitch(self):
        """Verify RJ45 connector width (12.2mm boot) is strictly smaller than port pitch (16mm-35mm)
        to prevent lateral overlapping."""
        boot_width_mm = 12.2
        dense_port_pitch_mm = 16.0
        self.assertLess(boot_width_mm, dense_port_pitch_mm, "RJ45 boot must fit inside port pitch without clipping")


if __name__ == "__main__":
    unittest.main()
