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

        # Datacenter Room Navigable Bounds (Room is -6.0 to +6.0, margin 0.35m for walls/baseboards)
        self.bounds_x = (-5.65, 5.65)
        self.bounds_z = (-5.65, 5.65)
        self.player_radius = 0.20
        self.stand_height = 1.65
        self.crouch_height = 0.85
        self.eye_height = 1.65
        self.is_crouching = False
        self._prev_crouch_key = False

    def _is_colliding(self, x, z, radius=None):
        r = self.player_radius if radius is None else radius

        # Room perimeter walls
        if x < (self.bounds_x[0] + r) or x > (self.bounds_x[1] - r):
            return True
        if z < (self.bounds_z[0] + r) or z > (self.bounds_z[1] - r):
            return True

        # 1. Three Server Racks (Exact physical footprint: 0.60m wide, 0.80m deep at z = -1.5)
        # Racks at x = -1.4, 0.0, 1.4. Depth: z in [-1.90, -1.10]
        for rx in (-1.4, 0.0, 1.4):
            if (rx - 0.30 - r) < x < (rx + 0.30 + r) and (-1.90 - r) < z < (-1.10 + r):
                return True

        # 2. Workbench Desk (center x = -3.2, z = 0.5, width = 1.4, depth = 0.75)
        if (-3.90 - r) < x < (-2.50 + r) and (0.125 - r) < z < (0.875 + r):
            return True

        # 3. CRAC Cooling Units on Right Wall (center x = 5.25, z = -2.0 and 1.8, w = 0.95, d = 1.25)
        for cz in (-2.0, 1.8):
            if (4.75 - r) < x < (5.75 + r) and (cz - 0.63 - r) < z < (cz + 0.63 + r):
                return True

        # 4. FM-200 Fire Suppression Cylinders on Left Wall (center x = -5.75, z in [-4.5, -3.6])
        if (-5.95 - r) < x < (-5.55 + r) and (-4.50 - r) < z < (-3.60 + r):
            return True

        return False

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

    def toggle_crouch(self):
        """Toggles crouching state between standing (1.65m) and crouched (0.85m)."""
        self.is_crouching = not self.is_crouching

    def update(self, keys, dt, pygame_module):
        # Check crouch toggle key [Ctrl] (Left Ctrl or Right Ctrl)
        ctrl_pressed = False
        if hasattr(pygame_module, "K_LCTRL") and keys[pygame_module.K_LCTRL]:
            ctrl_pressed = True
        if hasattr(pygame_module, "K_RCTRL") and keys[pygame_module.K_RCTRL]:
            ctrl_pressed = True

        # Rising-edge trigger: toggle crouch state when Ctrl is pressed
        if ctrl_pressed and not self._prev_crouch_key:
            self.is_crouching = not self.is_crouching
        self._prev_crouch_key = ctrl_pressed

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

        # Apply movement with smooth axis-independent sliding collision
        # 1. Try moving along X
        new_x = self.x + move_x
        if not self._is_colliding(new_x, self.z):
            self.x = new_x

        # 2. Try moving along Z
        new_z = self.z + move_z
        if not self._is_colliding(self.x, new_z):
            self.z = new_z

    def apply_view(self):
        """Applies FPS view matrix using gluLookAt."""
        dir_x, dir_y, dir_z = self.get_forward_vector()
        gluLookAt(
            self.x, self.y, self.z,
            self.x + dir_x, self.y + dir_y, self.z + dir_z,
            0.0, 1.0, 0.0
        )

    def _build_static_obstacles(self):
        """
        Builds 3D AABB bounding boxes (min_pt, max_pt) for all static physical
        structures in the datacenter that occlude line of sight (raycast blocking).
        """
        obstacles = []

        # 1. Three Server Racks (RACK-1: x=-1.4, RACK-2: x=0.0, RACK-3: x=1.4; z=-1.5)
        # Footprint: width=0.60m (hw=0.30m), depth=0.80m (hd=0.40m), height=2.10m
        for rx in (-1.4, 0.0, 1.4):
            rz = -1.5
            hw, hd, h = 0.30, 0.40, 2.10

            # Left solid metal side panel
            obstacles.append((
                (rx - hw - 0.015, 0.0, rz - hd),
                (rx - hw + 0.025, h,   rz + hd)
            ))
            # Right solid metal side panel
            obstacles.append((
                (rx + hw - 0.025, 0.0, rz - hd),
                (rx + hw + 0.015, h,   rz + hd)
            ))
            # Front-Left vertical corner post & door stile
            obstacles.append((
                (rx - hw - 0.015, 0.0, rz + hd - 0.065),
                (rx - hw + 0.055, h,   rz + hd + 0.025)
            ))
            # Front-Right vertical corner post & door stile
            obstacles.append((
                (rx + hw - 0.055, 0.0, rz + hd - 0.065),
                (rx + hw + 0.015, h,   rz + hd + 0.025)
            ))
            # Rear-Left vertical corner post & 0U PDU-A column
            obstacles.append((
                (rx - hw - 0.015, 0.0, rz - hd - 0.025),
                (rx - hw + 0.095, h,   rz - hd + 0.075)
            ))
            # Rear-Right vertical corner post & 0U PDU-B column
            obstacles.append((
                (rx + hw - 0.095, 0.0, rz - hd - 0.025),
                (rx + hw + 0.015, h,   rz - hd + 0.075)
            ))
            # Top canopy, roof, digital marquee & exhaust plenum
            obstacles.append((
                (rx - hw - 0.015, 1.98, rz - hd - 0.02),
                (rx + hw + 0.015, 2.25, rz + hd + 0.03)
            ))
            # Bottom chassis base, kick plates & wheels
            obstacles.append((
                (rx - hw - 0.015, 0.0,  rz - hd - 0.02),
                (rx + hw + 0.015, 0.09, rz + hd + 0.03)
            ))

        # 2. NOC Workbench Desk (center x = -3.2, z = 0.5, table top at y = 0.72 - 0.77)
        # Table top
        obstacles.append((
            (-3.92, 0.72, 0.11),
            (-2.48, 0.77, 0.89)
        ))
        # 4 Sturdy desk legs
        for lx in (-3.84, -2.56):
            for lz in (0.18, 0.82):
                obstacles.append((
                    (lx - 0.025, 0.0, lz - 0.025),
                    (lx + 0.025, 0.72, lz + 0.025)
                ))

        # 3. CRAC Cooling Units on Right Wall
        obstacles.append(((4.70, 0.0, -2.65), (5.75, 2.25, -1.35)))
        obstacles.append(((4.70, 0.0, 1.15),  (5.75, 2.25, 2.45)))

        # 4. FM-200 Fire Suppression Cylinders on Left Wall
        obstacles.append(((-5.95, 0.0, -4.50), (-5.55, 2.0, -3.60)))

        # 5. Room Perimeter Walls
        obstacles.append(((-6.0, 0.0, -6.10), (6.0, 3.4, -5.90)))
        obstacles.append(((-6.0, 0.0, 5.90),  (6.0, 3.4, 6.10)))
        obstacles.append(((-6.10, 0.0, -6.0), (-5.90, 3.4, 6.0)))
        obstacles.append(((5.90, 0.0, -6.0),  (6.10, 3.4, 6.0)))

        return obstacles

    def raycast(self, devices, max_dist=4.5, extra_obstacles=None):
        """
        Casts a ray from player eye position along view direction.
        Checks line-of-sight against solid physical obstacles (rack posts, side panels,
        canopy, workbench, walls) so devices behind obstacles are not highlighted or selected.
        Returns (hit_device, hit_port, hit_dist) or (None, None, None).
        """
        orig = (self.x, self.y, self.z)
        dx, dy, dz = self.get_forward_vector()
        dir_vec = (dx, dy, dz)

        closest_dist = max_dist
        hit_dev = None
        hit_port = None
        hit_is_obstacle = False

        # 1. Test Static World Obstacles (Rack posts, side panels, canopy, desk, walls)
        if not hasattr(self, "_static_obstacles") or self._static_obstacles is None:
            self._static_obstacles = self._build_static_obstacles()

        all_obstacles = self._static_obstacles
        if extra_obstacles:
            all_obstacles = list(all_obstacles) + list(extra_obstacles)

        for obs_min, obs_max in all_obstacles:
            t_obs = self._intersect_box(orig, dir_vec, obs_min, obs_max)
            if t_obs is not None and t_obs < closest_dist:
                closest_dist = t_obs
                hit_is_obstacle = True
                hit_dev = None
                hit_port = None

        # 2. Test Devices and their Ports
        for dev in devices:
            if dev.device_type == "laptop":
                half_w = dev.width / 2.0 + 0.01
                half_d = dev.depth / 2.0 + 0.01
                min_pt = (dev.pos_x - half_w, dev.pos_y - 0.005, dev.pos_z - half_d)
                max_pt = (dev.pos_x + half_w, dev.pos_y + dev.height + 0.01, dev.pos_z + half_d)
            else:
                # 19" EIA Rackmount appliances: width = 0.48m (half_w = 0.24m)
                # Fits perfectly within the 0.49m clear rack aperture without protruding into posts
                half_w = dev.width / 2.0
                half_h = max(0.024, dev.height / 2.0 + 0.004)
                half_d = dev.depth / 2.0
                min_pt = (dev.pos_x - half_w, dev.pos_y - half_h, dev.pos_z - half_d)
                max_pt = (dev.pos_x + half_w, dev.pos_y + half_h, dev.pos_z + half_d)

            t_dev = self._intersect_box(orig, dir_vec, min_pt, max_pt)

            # Check individual ports on this device
            dev_best_port = None
            port_hit_dist = 999.0
            for p_name, port in dev.ports.items():
                px, py, pz = port.get_world_pos()
                p_min = (px - 0.016, py - 0.015, pz - 0.015)
                p_max = (px + 0.016, py + 0.015, pz + 0.030)
                pt_t = self._intersect_box(orig, dir_vec, p_min, p_max)
                if pt_t is not None and pt_t < port_hit_dist:
                    port_hit_dist = pt_t
                    dev_best_port = port

            # Effective hit distance for this device (either body or port)
            effective_t = t_dev
            if port_hit_dist < 999.0:
                if effective_t is None or port_hit_dist < effective_t:
                    effective_t = port_hit_dist

            if effective_t is not None and effective_t < closest_dist:
                closest_dist = effective_t
                hit_dev = dev
                hit_port = dev_best_port
                hit_is_obstacle = False

        if hit_is_obstacle or hit_dev is None:
            return None, None, None

        return hit_dev, hit_port, closest_dist

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
