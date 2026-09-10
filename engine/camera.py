"""
engine/camera.py - First-Person Camera with 3D Raycasting & gluLookAt
Controls intuitive WASD movement, mouse look (yaw/pitch), datacenter bounds, and 3D picking.
"""

import math
from OpenGL.GL import *
from OpenGL.GLU import gluLookAt

class FPSCamera:
    def __init__(self, pos=(0.0, 1.65, 2.8)):
        self.x, self.y, self.z = pos
        self.yaw = 0.0         # 0 deg = facing forward along -Z (towards the racks)
        self.pitch = 0.0       # 0 deg = eye-level horizon
        self.mouse_sensitivity = 0.12
        self.speed = 3.2
        self.sprint_multiplier = 1.6

        # Room bounds (Datacenter size: X: -4.5 to 4.5, Z: -5.5 to 4.5)
        self.bounds_x = (-4.5, 4.5)
        self.bounds_z = (-5.5, 4.5)
        self.stand_height = 1.65
        self.crouch_height = 0.85
        self.eye_height = 1.65
        self.is_crouching = False

    def handle_mouse(self, dx, dy):
        # Moving mouse right (dx > 0) turns right (+yaw)
        self.yaw += dx * self.mouse_sensitivity
        # Moving mouse up (dy < 0 in Pygame) looks up (+pitch)
        self.pitch -= dy * self.mouse_sensitivity
        # Clamp pitch to avoid gimbal flip
        self.pitch = max(-85.0, min(85.0, self.pitch))

    def get_forward_vector(self):
        """Returns 3D unit direction vector where the camera is looking."""
        rad_yaw = math.radians(self.yaw)
        rad_pitch = math.radians(self.pitch)
        dir_x = math.sin(rad_yaw) * math.cos(rad_pitch)
        dir_y = math.sin(rad_pitch)
        dir_z = -math.cos(rad_yaw) * math.cos(rad_pitch)
        return (dir_x, dir_y, dir_z)

    def update(self, keys, dt, pygame_module):
        # Check crouch key [C]
        is_crouch_pressed = False
        if hasattr(pygame_module, "K_c") and keys[pygame_module.K_c]:
            is_crouch_pressed = True
        self.is_crouching = is_crouch_pressed

        target_height = self.crouch_height if self.is_crouching else self.stand_height
        self.y += (target_height - self.y) * min(1.0, 10.0 * dt)
        self.eye_height = self.y

        speed = self.speed * dt
        if self.is_crouching:
            speed *= 0.65
        elif keys[pygame_module.K_LSHIFT] or keys[pygame_module.K_RSHIFT]:
            speed *= self.sprint_multiplier

        rad_yaw = math.radians(self.yaw)
        # Forward vector on XZ floor plane
        fwd_x = math.sin(rad_yaw)
        fwd_z = -math.cos(rad_yaw)

        # Right vector on XZ floor plane (90 deg clockwise from forward)
        right_x = math.cos(rad_yaw)
        right_z = math.sin(rad_yaw)

        move_x = 0.0
        move_z = 0.0

        # W: Walk forward in look direction
        if keys[pygame_module.K_w]:
            move_x += fwd_x * speed
            move_z += fwd_z * speed
        # S: Walk backward
        if keys[pygame_module.K_s]:
            move_x -= fwd_x * speed
            move_z -= fwd_z * speed
        # A: Strafe left
        if keys[pygame_module.K_a]:
            move_x -= right_x * speed
            move_z -= right_z * speed
        # D: Strafe right
        if keys[pygame_module.K_d]:
            move_x += right_x * speed
            move_z += right_z * speed

        # Apply movement with Datacenter collision bounds
        new_x = self.x + move_x
        new_z = self.z + move_z

        # Collision with Datacenter racks row (racks are located around z = -1.5, x between -2.8 and 2.8)
        rack_collision = False
        if -2.3 < new_z < -0.7 and -2.8 < new_x < 2.8:
            rack_collision = True

        if not rack_collision:
            self.x = max(self.bounds_x[0], min(self.bounds_x[1], new_x))
            self.z = max(self.bounds_z[0], min(self.bounds_z[1], new_z))
        else:
            # Slide along free axis
            if not (-2.3 < self.z < -0.7 and -2.8 < new_x < 2.8):
                self.x = max(self.bounds_x[0], min(self.bounds_x[1], new_x))
            elif not (-2.3 < new_z < -0.7 and -2.8 < self.x < 2.8):
                self.z = max(self.bounds_z[0], min(self.bounds_z[1], new_z))

    def apply_view(self):
        """Applies FPS view matrix using gluLookAt."""
        dir_x, dir_y, dir_z = self.get_forward_vector()
        gluLookAt(
            self.x, self.y, self.z,
            self.x + dir_x, self.y + dir_y, self.z + dir_z,
            0.0, 1.0, 0.0
        )

    def raycast(self, devices, max_dist=4.5):
        """
        Casts a ray from player eye position along view direction.
        Returns (hit_device, hit_port, hit_dist) or (None, None, None).
        """
        orig = (self.x, self.y, self.z)
        dx, dy, dz = self.get_forward_vector()

        closest_dist = max_dist
        hit_dev = None
        hit_port = None

        for dev in devices:
            # 1. Device bounding box check
            half_w = dev.width / 2.0 + 0.08
            half_h = max(0.08, dev.height / 2.0)
            half_d = dev.depth / 2.0 + 0.08

            min_pt = (dev.pos_x - half_w, dev.pos_y - half_h, dev.pos_z - half_d)
            max_pt = (dev.pos_x + half_w, dev.pos_y + half_h, dev.pos_z + half_d)

            t = self._intersect_box(orig, (dx, dy, dz), min_pt, max_pt)
            if t is not None and t < closest_dist:
                closest_dist = t
                hit_dev = dev
                hit_port = None

                # 2. Check if aiming specifically at an individual port on this device
                port_hit_dist = 999.0
                for p_name, port in dev.ports.items():
                    px, py, pz = port.get_world_pos()
                    p_min = (px - 0.016, py - 0.015, pz - 0.015)
                    p_max = (px + 0.016, py + 0.015, pz + 0.030)
                    pt_t = self._intersect_box(orig, (dx, dy, dz), p_min, p_max)
                    if pt_t is not None and pt_t < port_hit_dist:
                        port_hit_dist = pt_t
                        hit_port = port

        return hit_dev, hit_port, closest_dist if hit_dev else None

    def _intersect_box(self, orig, dir_vec, box_min, box_max):
        """Slab method for Ray-AABB intersection."""
        tmin = -1e9
        tmax = 1e9

        for i in range(3):
            o = orig[i]
            d = dir_vec[i]
            b_min = box_min[i]
            b_max = box_max[i]

            if abs(d) < 1e-6:
                if o < b_min or o > b_max:
                    return None
            else:
                t1 = (b_min - o) / d
                t2 = (b_max - o) / d
                if t1 > t2:
                    t1, t2 = t2, t1
                tmin = max(tmin, t1)
                tmax = min(tmax, t2)
                if tmin > tmax or tmax < 0:
                    return None

        if tmin < 0:
            return tmax if tmax > 0 else None
        return tmin
