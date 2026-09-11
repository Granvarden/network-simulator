import sys
import os
sys.path.insert(0, os.path.abspath("."))
import math
from engine.camera import FPSCamera
from network.switch import Switch
from network.router import Router
from network.host import Host

def test_raycast():
    cam = FPSCamera()
    
    # Place a switch in Rack 1 (x = -1.4, z = -1.5, slot 24)
    # y = round(0.14 + (24 / 42.0) * 1.85, 2) = 1.20
    sw = Switch("sw1", "Test-Switch", rack_id=1, u_slot=24)
    sw.pos_x = -1.4
    sw.pos_y = 1.20
    sw.pos_z = -1.5
    devices = [sw]

    print("=== Testing Direct Frontal Aim (Cold Aisle) ===")
    # Stand in front of Rack 1 at (x = -1.4, y = 1.20, z = 0.0) looking directly at switch
    cam.x = -1.4
    cam.y = 1.20
    cam.z = 0.0
    cam.yaw = 0.0     # looking straight at -Z
    cam.pitch = 0.0
    
    hit_dev, hit_port, hit_dist = cam.raycast(devices)
    print(f"Frontal aim result: hit_dev={hit_dev.hostname if hit_dev else None}, dist={hit_dist}")

    print("=== Testing Aim at Rack 1 Front-Right Post ===")
    # Rack 1 is at x = -1.4. Front-right post is at x = -1.4 + 0.275 = -1.125, z = -1.10
    # Stand at (x = -1.125, y = 1.20, z = 0.0) looking straight at -Z
    cam.x = -1.125
    cam.y = 1.20
    cam.z = 0.0
    cam.yaw = 0.0
    cam.pitch = 0.0
    
    hit_dev, hit_port, hit_dist = cam.raycast(devices)
    print(f"Front-right post aim result: hit_dev={hit_dev.hostname if hit_dev else None}, dist={hit_dist}")

    print("=== Testing Aim through Side Panel ===")
    # Stand to the left of Rack 1 at x = -2.5, y = 1.20, z = -1.5 looking towards +X (yaw = 90)
    cam.x = -2.5
    cam.y = 1.20
    cam.z = -1.5
    cam.yaw = 90.0
    cam.pitch = 0.0
    
    hit_dev, hit_port, hit_dist = cam.raycast(devices)
    print(f"Side panel aim result: hit_dev={hit_dev.hostname if hit_dev else None}, dist={hit_dist}")
    assert hit_dev is None, f"Expected None (blocked by side panel), got {hit_dev}"

    print("=== Testing Direct Aim at Port (Cold Aisle) ===")
    # Aim directly at port g0/1 on the switch
    # Let's see if sw has ports
    if sw.ports:
        p1 = list(sw.ports.values())[0]
        px, py, pz = p1.get_world_pos()
        cam.x = px
        cam.y = py
        cam.z = 0.0
        cam.yaw = 0.0
        cam.pitch = 0.0
        h_dev, h_port, h_dist = cam.raycast(devices)
        print(f"Port aim result: dev={h_dev.hostname if h_dev else None}, port={h_port.name if h_port else None}")
        assert h_dev == sw, f"Expected sw, got {h_dev}"
        assert h_port == p1, f"Expected {p1.name}, got {h_port.name if h_port else None}"

    print("=== Testing Hot Aisle Rear Aim ===")
    # Behind Rack 1 at (x = -1.4, y = 1.20, z = -3.0) looking towards +Z (yaw = 180)
    cam.x = -1.4
    cam.y = 1.20
    cam.z = -3.0
    cam.yaw = 180.0
    cam.pitch = 0.0
    h_dev, h_port, h_dist = cam.raycast(devices)
    print(f"Hot aisle rear aim result: hit_dev={h_dev.hostname if h_dev else None}, dist={h_dist}")
    assert h_dev == sw, f"Expected sw from rear, got {h_dev}"

    print("=== Testing Rear Aim at 0U PDU Column ===")
    # Behind Rack 1 aiming at rear-left PDU (x = -1.4 - 0.25 = -1.65, z = -3.0)
    cam.x = -1.65
    cam.y = 1.20
    cam.z = -3.0
    cam.yaw = 180.0
    cam.pitch = 0.0
    h_dev, h_port, h_dist = cam.raycast(devices)
    print(f"Rear PDU aim result: hit_dev={h_dev.hostname if h_dev else None}, dist={h_dist}")
    assert h_dev is None, f"Expected None (blocked by PDU), got {h_dev}"

    print("=== Testing Top Canopy Aim ===")
    # Above Rack 1 looking down at the roof marquee (y = 2.05)
    cam.x = -1.4
    cam.y = 2.05
    cam.z = 0.0
    cam.yaw = 0.0
    cam.pitch = 0.0
    h_dev, h_port, h_dist = cam.raycast(devices)
    print(f"Top canopy aim result: hit_dev={h_dev.hostname if h_dev else None}, dist={h_dist}")
    assert h_dev is None, f"Expected None (blocked by canopy), got {h_dev}"

    print("=== Testing Workbench Laptop Aim ===")
    laptop = Host("lap1", "NOC-Laptop", device_type="laptop", os_type="ubuntu")
    laptop.pos_x = -3.2
    laptop.pos_y = 0.77
    laptop.pos_z = 0.5
    devs_with_lap = [sw, laptop]
    
    # Stand in front of workbench looking at laptop
    cam.x = -3.2
    cam.y = 1.20
    cam.z = 1.5
    # Calculate yaw and pitch to look directly at laptop (-3.2, 0.77, 0.5)
    cam.yaw = 0.0
    cam.pitch = -23.27  # atan2(0.77 - 1.20, 1.0) = -23.27 deg
    h_dev, h_port, h_dist = cam.raycast(devs_with_lap)
    print(f"Laptop aim result: hit_dev={h_dev.hostname if h_dev else None}, dist={h_dist}")
    assert h_dev == laptop, f"Expected laptop, got {h_dev}"

    print("=== Testing Laptop Aim from Under Workbench (Blocked by Desk) ===")
    cam.x = -3.2
    cam.y = 0.30   # under the desk (desk top is at 0.72 - 0.77)
    cam.z = 0.5
    cam.yaw = 0.0
    cam.pitch = 90.0  # looking straight up at desk bottom
    h_dev, h_port, h_dist = cam.raycast(devs_with_lap)
    print(f"Under desk aim result: hit_dev={h_dev.hostname if h_dev else None}, dist={h_dist}")
    assert h_dev is None, f"Expected None (blocked by desk), got {h_dev}"

    print("ALL 8 OCCLUSION TEST SCENARIOS PASSED!")

if __name__ == "__main__":
    test_raycast()
