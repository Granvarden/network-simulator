"""
tests/test_raycast_occlusion.py - Unit tests for Raycast Obstacle Occlusion
Verifies that devices located behind solid physical obstacles (rack posts, side panels,
top canopy, rear PDUs, workbench desk) are NOT targeted or highlighted.
"""

from engine.camera import FPSCamera
from network.switch import Switch
from network.host import Host


def test_raycast_occlusion():
    cam = FPSCamera()

    # Place a switch in Rack 1 (x = -1.4, z = -1.5, slot 24, y = 1.20)
    sw = Switch("sw1", "Test-Switch", rack_id=1, u_slot=24)
    sw.pos_x = -1.4
    sw.pos_y = 1.20
    sw.pos_z = -1.5
    devices = [sw]

    # 1. Frontal aim through clear aperture: must hit switch
    cam.x = -1.4
    cam.y = 1.20
    cam.z = 0.0
    cam.yaw = 0.0
    cam.pitch = 0.0
    hit_dev, hit_port, hit_dist = cam.raycast(devices)
    assert hit_dev == sw, f"Expected switch to be hit from front, got {hit_dev}"

    # 2. Aim at Front-Right vertical corner post: must be blocked by post (hit_dev = None)
    cam.x = -1.125
    cam.y = 1.20
    cam.z = 0.0
    cam.yaw = 0.0
    cam.pitch = 0.0
    hit_dev, hit_port, hit_dist = cam.raycast(devices)
    assert hit_dev is None, f"Expected None (blocked by front-right post), got {hit_dev}"

    # 3. Aim through side panel: must be blocked by side sheet metal (hit_dev = None)
    cam.x = -2.5
    cam.y = 1.20
    cam.z = -1.5
    cam.yaw = 90.0
    cam.pitch = 0.0
    hit_dev, hit_port, hit_dist = cam.raycast(devices)
    assert hit_dev is None, f"Expected None (blocked by side panel), got {hit_dev}"

    # 4. Aim directly at port g0/1 through clear opening: must target port
    if sw.ports:
        p1 = list(sw.ports.values())[0]
        px, py, pz = p1.get_world_pos()
        cam.x = px
        cam.y = py
        cam.z = 0.0
        cam.yaw = 0.0
        cam.pitch = 0.0
        h_dev, h_port, h_dist = cam.raycast(devices)
        assert h_dev == sw, f"Expected switch, got {h_dev}"
        assert h_port == p1, f"Expected {p1.name}, got {h_port.name if h_port else None}"

    # 5. Hot aisle rear aim through rear aperture: must hit switch
    cam.x = -1.4
    cam.y = 1.20
    cam.z = -3.0
    cam.yaw = 180.0
    cam.pitch = 0.0
    h_dev, h_port, h_dist = cam.raycast(devices)
    assert h_dev == sw, f"Expected switch from rear, got {h_dev}"

    # 6. Hot aisle rear aim at 0U PDU column: must be blocked (hit_dev = None)
    cam.x = -1.65
    cam.y = 1.20
    cam.z = -3.0
    cam.yaw = 180.0
    cam.pitch = 0.0
    h_dev, h_port, h_dist = cam.raycast(devices)
    assert h_dev is None, f"Expected None (blocked by rear PDU), got {h_dev}"

    # 7. Aim at top canopy / roof: must be blocked (hit_dev = None)
    cam.x = -1.4
    cam.y = 2.05
    cam.z = 0.0
    cam.yaw = 0.0
    cam.pitch = 0.0
    h_dev, h_port, h_dist = cam.raycast(devices)
    assert h_dev is None, f"Expected None (blocked by canopy), got {h_dev}"

    # 8. Workbench laptop aim: must hit laptop from above/front, but blocked from under desk
    laptop = Host("lap1", "NOC-Laptop", device_type="laptop", os_type="ubuntu")
    laptop.pos_x = -3.2
    laptop.pos_y = 0.77
    laptop.pos_z = 0.5
    devs_with_lap = [sw, laptop]

    # Front-facing look at laptop on desk
    cam.x = -3.2
    cam.y = 1.20
    cam.z = 1.5
    cam.yaw = 0.0
    cam.pitch = -23.27
    h_dev, h_port, h_dist = cam.raycast(devs_with_lap)
    assert h_dev == laptop, f"Expected laptop, got {h_dev}"

    # Aim from underneath desk
    cam.x = -3.2
    cam.y = 0.30
    cam.z = 0.5
    cam.yaw = 0.0
    cam.pitch = 90.0
    h_dev, h_port, h_dist = cam.raycast(devs_with_lap)
    assert h_dev is None, f"Expected None (blocked by desk surface), got {h_dev}"


if __name__ == "__main__":
    test_raycast_occlusion()
    print("test_raycast_occlusion: PASS")
