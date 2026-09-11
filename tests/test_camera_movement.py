"""
tests/test_camera_movement.py - Automated verification of Camera & WASD directions
"""

import pygame
from engine.camera import FPSCamera

def test_camera_direction():
    cam = FPSCamera(pos=(0.0, 1.65, 2.8))

    # Initial state: yaw=0 (facing forward towards racks at -Z), pitch=0
    assert cam.yaw == 0.0
    assert cam.pitch == 0.0
    vx, vy, vz = cam.get_forward_vector()
    assert abs(vx) < 1e-5
    assert abs(vy) < 1e-5
    assert abs(vz - (-1.0)) < 1e-5
    print(f"Initial look vector: ({vx:.2f}, {vy:.2f}, {vz:.2f}) -> Looking forward down -Z. [PASS]")

    # 1. Mouse Right: dx > 0
    cam.handle_mouse(dx=10, dy=0)
    assert cam.yaw > 0, "Yaw should increase when moving mouse right"
    vx, vy, vz = cam.get_forward_vector()
    assert vx > 0, "Look direction should turn towards +X (Right)"
    print(f"Mouse Right: yaw={cam.yaw:.1f} deg, dir=({vx:.2f}, {vy:.2f}, {vz:.2f}) -> Turned RIGHT. [PASS]")

    # 2. Mouse Left: dx < 0
    cam.handle_mouse(dx=-20, dy=0)
    assert cam.yaw < 0, "Yaw should decrease when moving mouse left"
    vx, vy, vz = cam.get_forward_vector()
    assert vx < 0, "Look direction should turn towards -X (Left)"
    print(f"Mouse Left: yaw={cam.yaw:.1f} deg, dir=({vx:.2f}, {vy:.2f}, {vz:.2f}) -> Turned LEFT. [PASS]")

    # Reset yaw
    cam.yaw = 0.0

    # 3. Mouse Up: dy < 0 in Pygame
    cam.handle_mouse(dx=0, dy=-15)
    assert cam.pitch > 0, "Pitch should increase when moving mouse up"
    vx, vy, vz = cam.get_forward_vector()
    assert vy > 0, "Look direction should turn towards +Y (Up)"
    print(f"Mouse Up: pitch={cam.pitch:.1f} deg, dir=({vx:.2f}, {vy:.2f}, {vz:.2f}) -> Looking UP. [PASS]")

    # 4. Mouse Down: dy > 0 in Pygame
    cam.handle_mouse(dx=0, dy=30)
    assert cam.pitch < 0, "Pitch should decrease when moving mouse down"
    vx, vy, vz = cam.get_forward_vector()
    assert vy < 0, "Look direction should turn towards -Y (Down)"
    print(f"Mouse Down: pitch={cam.pitch:.1f} deg, dir=({vx:.2f}, {vy:.2f}, {vz:.2f}) -> Looking DOWN. [PASS]")

    # 5. WASD Movement Test at yaw=0
    cam.yaw = 0.0
    cam.pitch = 0.0
    cam.x, cam.z = 0.0, 2.0

    class DummyKeys:
        def __init__(self, active_key):
            self.active = active_key
        def __getitem__(self, k):
            return k == self.active

    # Press W -> should walk forward towards -Z (z decreases)
    init_z = cam.z
    cam.update(DummyKeys(pygame.K_w), dt=0.1, pygame_module=pygame)
    assert cam.z < init_z, "Pressing W must decrease Z (move forward)"
    print(f"Press W: Z moved from {init_z:.2f} to {cam.z:.2f} (Forward towards racks). [PASS]")

    # Press S -> should walk backward towards +Z (z increases)
    init_z = cam.z
    cam.update(DummyKeys(pygame.K_s), dt=0.1, pygame_module=pygame)
    assert cam.z > init_z, "Pressing S must increase Z (move backward)"
    print(f"Press S: Z moved from {init_z:.2f} to {cam.z:.2f} (Backward away from racks). [PASS]")

    # Press D -> should strafe right towards +X (x increases)
    init_x = cam.x
    cam.update(DummyKeys(pygame.K_d), dt=0.1, pygame_module=pygame)
    assert cam.x > init_x, "Pressing D must increase X (strafe right)"
    print(f"Press D: X moved from {init_x:.2f} to {cam.x:.2f} (Strafe right). [PASS]")

    # Press A -> should strafe left towards -X (x decreases)
    init_x = cam.x
    cam.update(DummyKeys(pygame.K_a), dt=0.1, pygame_module=pygame)
    assert cam.x < init_x, "Pressing A must decrease X (strafe left)"
    print(f"Press A: X moved from {init_x:.2f} to {cam.x:.2f} (Strafe left). [PASS]")

    print("\nALL CAMERA & MOVEMENT DIRECTION TESTS PASSED 100%!")

def test_camera_collision():
    cam = FPSCamera(pos=(0.0, 1.65, 2.0))

    # 1. Verify previously blocked empty areas are now open
    # Open area between Rack 1 and Rack 2 (x = -0.7, z = -1.5)
    assert not cam._is_colliding(-0.7, -1.5), "Gap between rack 1 and rack 2 should be walkable"

    # Open area between Rack 2 and Rack 3 (x = 0.7, z = -1.5)
    assert not cam._is_colliding(0.7, -1.5), "Gap between rack 2 and rack 3 should be walkable"

    # Open floor to the left of Rack 1 (x = -2.2, z = -1.5)
    assert not cam._is_colliding(-2.2, -1.5), "Area to left of Rack 1 should be walkable"

    # Open floor to the right of Rack 3 (x = 2.2, z = -1.5)
    assert not cam._is_colliding(2.2, -1.5), "Area to right of Rack 3 should be walkable"

    # Open hot aisle behind racks (x = 0.0, z = -2.2)
    assert not cam._is_colliding(0.0, -2.2), "Hot aisle behind racks should be walkable"

    # Open floor close in front of racks (x = 0.0, z = -0.85)
    assert not cam._is_colliding(0.0, -0.85), "Front cold aisle should be walkable close to rack ports"

    # Open floor near room perimeter walls (x = -5.0, z = 0.0)
    assert not cam._is_colliding(-5.0, 0.0), "Floor near perimeter wall should be walkable"

    print("Verified: All previously blocked empty open spaces are now walkable! [PASS]")

    # 2. Verify actual solid obstacles are properly blocked
    # Inside Rack 1
    assert cam._is_colliding(-1.4, -1.5), "Inside Rack 1 must collide"
    # Inside Rack 2
    assert cam._is_colliding(0.0, -1.5), "Inside Rack 2 must collide"
    # Inside Rack 3
    assert cam._is_colliding(1.4, -1.5), "Inside Rack 3 must collide"
    # Inside Workbench Desk
    assert cam._is_colliding(-3.2, 0.5), "Inside Workbench desk must collide"
    # Beyond room perimeter wall
    assert cam._is_colliding(-5.6, 0.0), "At perimeter wall boundary must collide"
    assert cam._is_colliding(6.0, 0.0), "Outside room boundary must collide"

    print("Verified: Real physical obstacles remain solid and blocked! [PASS]")

    # 3. Verify axis-independent sliding collision
    # Position player against front of rack 2 (x=0, z=-0.88, facing -Z)
    cam.x = 0.0
    cam.z = -0.88
    cam.yaw = 0.0

    class DummyKeys:
        def __init__(self, *active_keys):
            self.keys = set(active_keys)
        def __getitem__(self, k):
            return k in self.keys

    # Walking diagonally forward-right (W + D):
    # Moving forward into rack should be blocked, but strafing right should succeed!
    init_x = cam.x
    init_z = cam.z
    cam.update(DummyKeys(pygame.K_w, pygame.K_d), dt=0.05, pygame_module=pygame)
    assert cam.x > init_x, "Player should slide right along the rack face"
    assert cam.z == init_z, "Player forward movement into the rack should be stopped"
    print(f"Smooth sliding: X slid from {init_x:.2f} to {cam.x:.2f} while Z stayed at {init_z:.2f}. [PASS]")

    print("\nALL CAMERA COLLISION & SLIDING TESTS PASSED 100%!")

if __name__ == "__main__":
    pygame.init()
    test_camera_direction()
    test_camera_collision()
    pygame.quit()

