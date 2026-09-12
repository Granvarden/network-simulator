"""
ui/topology_2d.py - Interactive 2D Packet Tracer-Style Topology Editor & Visualizer
Provides:
1. Cisco Packet Tracer aesthetic with pan/zoom grid canvas, vector-styled device cards, and cables.
2. Mode-aware permissions: Full Drag-and-Drop & Cabling in Sandbox Mode; View-Only in Tutorial/Challenge Modes.
3. Real-Time 3D Rack Synchronization: Auto-allocates non-overlapping U-slots in Rack 1/2/3 and syncs 3D positions.
4. Interactive Port-to-Port Cabling: Visual port picker dialog with available/occupied ports and rubber-band preview.
5. Complete 100% Thai language support using Windows system fonts (Leelawadee UI, Tahoma).
"""

import math
import time
import pygame
from network.switch import Switch
from network.router import Router
from network.host import Host
from network.firewall import Firewall
from network.cable import Cable, CableType

class Topology2D:
    def __init__(self):
        # High-legibility Thai and English fonts
        self.font_title = pygame.font.SysFont("leelawadeeui,tahoma,segoeui", 20, bold=True) or pygame.font.Font(None, 24)
        self.font_sub = pygame.font.SysFont("leelawadeeui,tahoma,segoeui", 12) or pygame.font.Font(None, 15)
        self.font_btn = pygame.font.SysFont("leelawadeeui,tahoma,segoeui", 14, bold=True) or pygame.font.Font(None, 17)
        self.font_node_title = pygame.font.SysFont("leelawadeeui,tahoma,segoeui", 13, bold=True) or pygame.font.Font(None, 16)
        self.font_node_sub = pygame.font.SysFont("leelawadeeui,tahoma,segoeui", 11) or pygame.font.Font(None, 14)
        self.font_badge = pygame.font.SysFont("leelawadeeui,tahoma,segoeui", 10, bold=True) or pygame.font.Font(None, 13)
        self.font_mono = pygame.font.SysFont("consolas", 11) or pygame.font.Font(None, 14)
        self.font_mono_bold = pygame.font.SysFont("consolas", 12, bold=True) or pygame.font.Font(None, 15)
        self.font_toast = pygame.font.SysFont("leelawadeeui,tahoma,segoeui", 13, bold=True) or pygame.font.Font(None, 16)

        # Canvas Pan & Zoom
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.zoom = 1.0
        self.is_panning = False
        self.pan_start_mouse = (0, 0)
        self.pan_start_offset = (0.0, 0.0)

        # Tools: 'select', 'cable', 'delete', 'inspect'
        self.selected_tool = "select"
        self.active_cable_type = CableType.CAT6
        self.active_category = "network"  # "network", "end_devices", "connections"

        # Interactive Drag & Drop
        self.selected_dev = None
        self.dragging_dev = None
        self.drag_start_pos = (0, 0)
        self.hovered_dev = None
        self.hovered_cable = None

        # Device Placement in Progress (Ghost from palette)
        self.placing_device_type = None

        # Cabling State
        self.cable_source_dev = None
        self.cable_source_port = None
        self.cable_target_dev = None
        self.port_picker_dev = None
        self.port_picker_mode = None  # "source" or "target"
        self.port_picker_rects = []
        self.port_picker_scroll = 0

        # Device Properties Modal
        self.inspect_dev = None
        self.inspect_tab = "info"  # "info" or "ports"
        self.edit_hostname_active = False
        self.edit_hostname_text = ""

        # Rack Slot Picker Modal (Custom placement)
        self.rack_picker_open = False
        self.rack_picker_dev_type = None
        self.rack_picker_wx = 0.0
        self.rack_picker_wy = 0.0
        self.rack_picker_rack_id = 1
        self.rack_picker_slot = 12
        self.rack_picker_hostname = ""
        self.rack_picker_hostname_active = False

        # Notification Toast
        self.toast_msg = ""
        self.toast_time = 0.0
        self.toast_color = (0, 120, 240)

        # UI Element Layout Rects
        self.cached_btn_rects = {}

    def show_toast(self, msg, color=(16, 145, 65)):
        self.toast_msg = msg
        self.toast_time = time.time()
        self.toast_color = color

    def _screen_to_world(self, sx, sy):
        wx = (sx - self.pan_x) / self.zoom
        wy = (sy - self.pan_y) / self.zoom
        return wx, wy

    def _world_to_screen(self, wx, wy):
        sx = wx * self.zoom + self.pan_x
        sy = wy * self.zoom + self.pan_y
        return sx, sy

    def _init_device_positions(self, devices, w, h):
        """Assigns clean initial 2D coordinates if dev.topo_x is missing."""
        if not devices:
            return

        cx = w / 2.0
        routers = [d for d in devices if isinstance(d, Router)]
        firewalls = [d for d in devices if isinstance(d, Firewall)]
        switches = [d for d in devices if isinstance(d, Switch)]
        hosts = [d for d in devices if isinstance(d, Host)]

        rows = [
            (routers, 150),
            (firewalls, 240),
            (switches, 330),
            (hosts, 425)
        ]

        for dev_list, base_y in rows:
            count = len(dev_list)
            if count == 0:
                continue
            max_per_row = max(1, int((w - 180) / 185))
            num_rows = (count + max_per_row - 1) // max_per_row
            for r_idx in range(num_rows):
                chunk = dev_list[r_idx * max_per_row : (r_idx + 1) * max_per_row]
                c_cnt = len(chunk)
                span = min(w - 200, max(200, (c_cnt - 1) * 185)) if c_cnt > 1 else 0
                start_x = cx - span / 2.0
                step = span / max(1, c_cnt - 1) if c_cnt > 1 else 0
                row_y = base_y + r_idx * 90
                for idx, dev in enumerate(chunk):
                    if not hasattr(dev, "topo_x") or not hasattr(dev, "topo_y"):
                        dev.topo_x = cx if c_cnt == 1 else (start_x + idx * step)
                        dev.topo_y = row_y

    def auto_arrange(self, devices, w, h):
        """Rearranges devices into clean hierarchical rows with multi-row wrapping."""
        cx = w / 2.0
        routers = [d for d in devices if isinstance(d, Router)]
        firewalls = [d for d in devices if isinstance(d, Firewall)]
        switches = [d for d in devices if isinstance(d, Switch)]
        hosts = [d for d in devices if isinstance(d, Host)]

        rows = [
            (routers, 150),
            (firewalls, 240),
            (switches, 330),
            (hosts, 425)
        ]

        for dev_list, base_y in rows:
            count = len(dev_list)
            if count == 0:
                continue
            max_per_row = max(1, int((w - 180) / 185))
            num_rows = (count + max_per_row - 1) // max_per_row
            for r_idx in range(num_rows):
                chunk = dev_list[r_idx * max_per_row : (r_idx + 1) * max_per_row]
                c_cnt = len(chunk)
                span = min(w - 200, max(200, (c_cnt - 1) * 185)) if c_cnt > 1 else 0
                start_x = cx - span / 2.0
                step = span / max(1, c_cnt - 1) if c_cnt > 1 else 0
                row_y = base_y + r_idx * 90
                for idx, dev in enumerate(chunk):
                    dev.topo_x = cx if c_cnt == 1 else (start_x + idx * step)
                    dev.topo_y = row_y

        self.show_toast("Auto arranged network topology successfully.", (0, 102, 204))

    def _allocate_rack_slot(self, mode, dev_type, preferred_rack_id=None):
        """Finds next non-overlapping rack slot in 3D datacenter."""
        needed_u = 1 if dev_type in ("switch", "firewall", "isp_gateway", "isp") else 2
        if hasattr(mode, "find_next_free_slot"):
            return mode.find_next_free_slot(preferred_rack_id=preferred_rack_id, needed_u=needed_u)
        return 1, 14

    def _open_rack_picker(self, dev_type, wx, wy, mode):
        """Initializes and opens the interactive Rack Slot selection modal."""
        self.rack_picker_open = True
        self.rack_picker_dev_type = dev_type
        self.rack_picker_wx = wx
        self.rack_picker_wy = wy
        self.rack_picker_rack_id = 1

        needed_u = 1 if dev_type in ("switch", "firewall", "isp_gateway", "isp") else 2
        if hasattr(mode, "find_next_free_slot"):
            r_id, u_slot = mode.find_next_free_slot(preferred_rack_id=1, needed_u=needed_u)
            self.rack_picker_rack_id = r_id
            self.rack_picker_slot = u_slot
        else:
            self.rack_picker_slot = 12

        prefix_map = {
            "router": "R",
            "switch": "SW",
            "firewall": "FW",
            "server": "SRV",
        }
        count = sum(1 for d in getattr(mode, "devices", []) if getattr(d, "device_type", "") == dev_type) + 1
        self.rack_picker_hostname = f"{prefix_map.get(dev_type, dev_type.upper())}{count}"
        self.rack_picker_hostname_active = False

    # -------------------------------------------------------------------------
    # RENDERING METHODS
    # -------------------------------------------------------------------------
    def render(self, surface, screen_w, screen_h, devices, cables, mode=None):
        from modes.sandbox_mode import SandboxMode
        is_sandbox = isinstance(mode, SandboxMode)

        # Clear cached button rects per frame to prevent cross-category rect collisions
        self.cached_btn_rects.clear()

        # 1. Initialize positions if needed
        self._init_device_positions(devices, screen_w, screen_h)

        # 2. Tech Blueprint Grid Background
        surface.fill((246, 248, 252))
        self._draw_grid(surface, screen_w, screen_h)

        # 3. Cable Links
        self._draw_cables(surface, cables, screen_w, screen_h)

        # 4. Rubber-band in-progress cable line
        if self.cable_source_dev and self.cable_source_port:
            self._draw_rubber_band_cable(surface)

        # 5. Device Nodes
        self._draw_devices(surface, devices)

        # 6. Placement Ghost (when dragging or clicked from palette)
        if self.placing_device_type:
            self._draw_placement_ghost(surface)

        # 7. Top Header & Control Bar
        self._draw_top_bar(surface, screen_w, screen_h, len(devices), len(cables), is_sandbox)

        # 8. Bottom Palette / Dock (Sandbox Mode only)
        if is_sandbox:
            self._draw_bottom_dock(surface, screen_w, screen_h)
        else:
            self._draw_view_only_dock(surface, screen_w, screen_h)

        # 9. Modals (Rack Slot Picker, Port Picker, Device Inspector)
        if self.rack_picker_open:
            self._draw_rack_picker_modal(surface, screen_w, screen_h, mode)
        elif self.port_picker_dev:
            self._draw_port_picker_modal(surface, screen_w, screen_h)
        elif self.inspect_dev:
            self._draw_device_inspector_modal(surface, screen_w, screen_h, is_sandbox)

        # 10. Notification Toast
        if self.toast_msg and (time.time() - self.toast_time < 3.2):
            self._draw_toast(surface, screen_w, screen_h)

    def _draw_grid(self, surface, w, h):
        grid_step = int(32 * self.zoom)
        if grid_step < 12:
            grid_step *= 2
        start_x = int(self.pan_x % grid_step)
        start_y = int(self.pan_y % grid_step)

        grid_col = (232, 237, 245)
        for x in range(start_x, w, grid_step):
            pygame.draw.line(surface, grid_col, (x, 0), (x, h), 1)
        for y in range(start_y, h, grid_step):
            pygame.draw.line(surface, grid_col, (0, y), (w, y), 1)

    def _draw_cables(self, surface, cables, w, h):
        now = time.time()
        for cable in cables:
            if not cable.port_a or not cable.port_b:
                continue
            dev_a = cable.port_a.device
            dev_b = cable.port_b.device
            if not hasattr(dev_a, "topo_x") or not hasattr(dev_b, "topo_x"):
                continue

            sx1, sy1 = self._world_to_screen(dev_a.topo_x, dev_a.topo_y)
            sx2, sy2 = self._world_to_screen(dev_b.topo_x, dev_b.topo_y)

            # Highlight if hovered
            is_hover = (self.hovered_cable == cable)

            # Color scheme by cable type
            if cable.cable_type == CableType.FIBER:
                col = (235, 140, 20)
                thick = 4 if is_hover else 3
            elif cable.cable_type == CableType.CONSOLE:
                col = (0, 175, 235)
                thick = 4 if is_hover else 3
            else:
                col = (0, 102, 204)
                thick = 5 if is_hover else 3

            if is_hover:
                col = (255, 185, 0)

            # Drop shadow
            pygame.draw.line(surface, (210, 220, 235), (sx1 + 1, sy1 + 2), (sx2 + 1, sy2 + 2), thick)
            # Main cable line
            pygame.draw.line(surface, col, (sx1, sy1), (sx2, sy2), thick)

            # Link status LED indicators on both ends
            link_a = cable.port_a.is_link_up
            link_b = cable.port_b.is_link_up
            col_a = (15, 185, 75) if link_a else (220, 60, 50)
            col_b = (15, 185, 75) if link_b else (220, 60, 50)

            # Vector towards center
            dx = sx2 - sx1
            dy = sy2 - sy1
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 30:
                ux, uy = dx / dist, dy / dist
                # LED near dev_a
                la_x, la_y = sx1 + ux * 45, sy1 + uy * 45
                pygame.draw.circle(surface, (255, 255, 255), (int(la_x), int(la_y)), 6)
                pygame.draw.circle(surface, col_a, (int(la_x), int(la_y)), 4)

                # LED near dev_b
                lb_x, lb_y = sx2 - ux * 45, sy2 - uy * 45
                pygame.draw.circle(surface, (255, 255, 255), (int(lb_x), int(lb_y)), 6)
                pygame.draw.circle(surface, col_b, (int(lb_x), int(lb_y)), 4)

                # Midpoint tag badge
                mid_x = (sx1 + sx2) / 2.0
                mid_y = (sy1 + sy2) / 2.0
                tag_txt = f"{cable.port_a.name} <-> {cable.port_b.name}"
                ts = self.font_badge.render(tag_txt, True, (25, 45, 75))
                tw, th = ts.get_width() + 12, ts.get_height() + 6
                tag_rect = pygame.Rect(mid_x - tw / 2, mid_y - th / 2, tw, th)

                pygame.draw.rect(surface, (255, 255, 255), tag_rect, border_radius=4)
                pygame.draw.rect(surface, (190, 210, 235), tag_rect, width=1, border_radius=4)
                surface.blit(ts, (tag_rect.x + 6, tag_rect.y + 3))

    def _draw_rubber_band_cable(self, surface):
        dev = self.cable_source_dev
        sx1, sy1 = self._world_to_screen(dev.topo_x, dev.topo_y)
        mx, my = pygame.mouse.get_pos()

        col = (0, 115, 230)
        if self.active_cable_type == CableType.FIBER:
            col = (235, 140, 20)
        elif self.active_cable_type == CableType.CONSOLE:
            col = (0, 175, 235)

        # Draw elastic animated cable line
        pygame.draw.line(surface, col, (sx1, sy1), (mx, my), 3)

        # Draw starting port badge
        p_txt = f"From: {dev.hostname} [{self.cable_source_port.name}]"
        ts = self.font_badge.render(p_txt, True, (255, 255, 255))
        tw, th = ts.get_width() + 14, ts.get_height() + 6
        bg_rect = pygame.Rect(mx + 12, my - 10, tw, th)
        pygame.draw.rect(surface, (20, 35, 60), bg_rect, border_radius=4)
        surface.blit(ts, (bg_rect.x + 7, bg_rect.y + 3))

    def _draw_devices(self, surface, devices):
        card_w = 160 * self.zoom
        card_h = 76 * self.zoom

        for dev in devices:
            if not hasattr(dev, "topo_x") or not hasattr(dev, "topo_y"):
                continue

            sx, sy = self._world_to_screen(dev.topo_x, dev.topo_y)
            rect = pygame.Rect(sx - card_w / 2.0, sy - card_h / 2.0, card_w, card_h)

            is_selected = (self.selected_dev == dev)
            is_hovered = (self.hovered_dev == dev)

            # Color Themes by Device Type
            if isinstance(dev, Router):
                header_col = (0, 102, 204)     # Cisco Blue
                sub_label = "Cisco 2U Router"
                dev_cat_en = "ROUTER"
            elif isinstance(dev, Switch):
                header_col = (16, 145, 65)     # Cisco Switch Green
                sub_label = "Catalyst 1U Switch"
                dev_cat_en = "SWITCH"
            elif isinstance(dev, Firewall):
                header_col = (195, 30, 45)     # Cisco ASA Crimson
                sub_label = "Cisco ASA 5506-X"
                dev_cat_en = "FIREWALL"
            elif isinstance(dev, Host) and dev.device_type == "server":
                header_col = (220, 130, 15)    # Enterprise Gold/Amber
                sub_label = "Enterprise 2U Host"
                dev_cat_en = "SERVER"
            elif isinstance(dev, Host) and dev.device_type in ("laptop", "pc"):
                header_col = (0, 145, 210)     # Workstation Cyan
                sub_label = "Workstation PC" if dev.device_type == "pc" else "Laptop"
                dev_cat_en = "PC" if dev.device_type == "pc" else "LAPTOP"
            else:
                header_col = (90, 105, 125)
                sub_label = "Network Appliance"
                dev_cat_en = "APPLIANCE"

            # 1. Drop Shadow
            shadow_rect = pygame.Rect(rect.x + 3, rect.y + 3, rect.w, rect.h)
            pygame.draw.rect(surface, (215, 225, 238), shadow_rect, border_radius=8)

            # 2. Main Card Body
            pygame.draw.rect(surface, (255, 255, 255), rect, border_radius=8)

            # 3. Header Bar
            header_h = max(20, int(24 * self.zoom))
            header_rect = pygame.Rect(rect.x, rect.y, rect.w, header_h)
            pygame.draw.rect(surface, header_col, header_rect, border_top_left_radius=8, border_top_right_radius=8)

            # Header Category Text
            en_lbl = self.font_badge.render(dev_cat_en, True, (255, 255, 255))
            surface.blit(en_lbl, (header_rect.x + 8, header_rect.y + (header_h - en_lbl.get_height()) // 2))

            # 3D Rack Location Tag in Header (Right Side)
            if getattr(dev, "rack_id", 0) in (1, 2, 3):
                rack_tag = f"RACK {dev.rack_id}:{dev.u_slot}U"
            elif getattr(dev, "device_type", "") in ("laptop", "pc"):
                rack_tag = "DESK"
            else:
                rack_tag = "WAN"
            tag_s = self.font_badge.render(rack_tag, True, (240, 248, 255))
            surface.blit(tag_s, (header_rect.right - tag_s.get_width() - 8, header_rect.y + (header_h - tag_s.get_height()) // 2))

            # 4. Hostname
            hn_s = self.font_node_title.render(dev.hostname, True, (20, 35, 55))
            surface.blit(hn_s, (rect.x + 10, header_rect.bottom + 6))

            # 5. Subtitle / IP Information
            # Find primary IP if present
            ip_str = "No IP Configured"
            for p in dev.ports.values():
                if getattr(p, "ip_address", None):
                    ip_str = p.ip_address
                    break
            if ip_str == "No IP Configured":
                sub_txt = sub_label
            else:
                sub_txt = f"IP: {ip_str}"

            ip_s = self.font_node_sub.render(sub_txt, True, (90, 110, 135))
            surface.blit(ip_s, (rect.x + 10, header_rect.bottom + 26))

            # 6. Port Mini Status Row at bottom of card
            mini_y = rect.bottom - 10
            port_count = min(8, len(dev.ports))
            p_start_x = rect.x + 10
            for pi, port in enumerate(list(dev.ports.values())[:port_count]):
                p_col = (15, 185, 75) if port.is_link_up else ((210, 130, 20) if port.cable else (200, 210, 225))
                pygame.draw.circle(surface, p_col, (p_start_x + pi * 10, mini_y), 3)

            # 7. Selection & Hover Border
            if is_selected:
                pygame.draw.rect(surface, (0, 120, 245), rect, width=2, border_radius=8)
            elif is_hovered:
                pygame.draw.rect(surface, (120, 175, 235), rect, width=2, border_radius=8)
            else:
                pygame.draw.rect(surface, (205, 218, 235), rect, width=1, border_radius=8)

    def _draw_placement_ghost(self, surface):
        mx, my = pygame.mouse.get_pos()
        gw, gh = 160, 70
        rect = pygame.Rect(mx - gw / 2, my - gh / 2, gw, gh)
        pygame.draw.rect(surface, (230, 242, 255), rect, border_radius=8)
        pygame.draw.rect(surface, (0, 120, 240), rect, width=2, border_radius=8)

        lbl = self.font_node_title.render(f"Place {self.placing_device_type.upper()}", True, (0, 102, 204))
        surface.blit(lbl, (rect.x + (gw - lbl.get_width()) // 2, rect.y + 14))
        hint = self.font_node_sub.render("Click on canvas to mount", True, (60, 90, 130))
        surface.blit(hint, (rect.x + (gw - hint.get_width()) // 2, rect.y + 38))

    def _draw_top_bar(self, surface, w, h, dev_count, cable_count, is_sandbox):
        bar_h = 56
        bar_rect = pygame.Rect(0, 0, w, bar_h)

        # White header with soft bottom border
        pygame.draw.rect(surface, (255, 255, 255), bar_rect)
        pygame.draw.line(surface, (215, 225, 238), (0, bar_h), (w, bar_h), 1)

        # 1. Back to 3D Button (Left)
        back_rect = pygame.Rect(16, 10, 250, 36)
        self.cached_btn_rects["back_3d"] = back_rect
        is_back_hover = back_rect.collidepoint(pygame.mouse.get_pos())
        b_bg = (235, 245, 255) if is_back_hover else (244, 248, 254)
        pygame.draw.rect(surface, b_bg, back_rect, border_radius=6)
        pygame.draw.rect(surface, (0, 115, 230), back_rect, width=1, border_radius=6)
        b_txt = self.font_btn.render("< Return to 3D Datacenter [ESC / M]", True, (0, 102, 204))
        surface.blit(b_txt, (back_rect.x + (back_rect.w - b_txt.get_width()) // 2, back_rect.y + 8))

        # 2. Title & Mode Badge (Center-Left)
        t_x = back_rect.right + 20
        title = self.font_title.render("2D Network Topology (Packet Tracer Mode)", True, (16, 42, 82))
        surface.blit(title, (t_x, 8))

        mode_desc = f"Total Devices: {dev_count}  |  Active Links: {cable_count}  |  Realtime 3D Rack Sync"
        sub = self.font_sub.render(mode_desc, True, (85, 105, 135))
        surface.blit(sub, (t_x, 32))

        # 3. Action Buttons (Right)
        rx = w - 16
        # Auto Arrange Button
        aa_rect = pygame.Rect(rx - 150, 10, 140, 36)
        self.cached_btn_rects["auto_arrange"] = aa_rect
        is_aa_hover = aa_rect.collidepoint(pygame.mouse.get_pos())
        aa_bg = (240, 248, 255) if is_aa_hover else (255, 255, 255)
        pygame.draw.rect(surface, aa_bg, aa_rect, border_radius=6)
        pygame.draw.rect(surface, (180, 205, 235), aa_rect, width=1, border_radius=6)
        aa_txt = self.font_btn.render("Auto Arrange", True, (25, 45, 80))
        surface.blit(aa_txt, (aa_rect.x + (aa_rect.w - aa_txt.get_width()) // 2, aa_rect.y + 8))

        # Mode Badge Indicator
        if is_sandbox:
            badge_txt = "Sandbox Mode (Editable & Cabling)"
            badge_bg = (235, 252, 242)
            badge_border = (16, 160, 80)
            badge_col = (10, 120, 50)
        else:
            badge_txt = "Mission / Tutorial (View-Only Mode)"
            badge_bg = (255, 248, 235)
            badge_border = (235, 145, 25)
            badge_col = (160, 85, 10)

        badge_s = self.font_badge.render(badge_txt, True, badge_col)
        bw = badge_s.get_width() + 16
        b_rect = pygame.Rect(aa_rect.x - bw - 14, 13, bw, 30)
        pygame.draw.rect(surface, badge_bg, b_rect, border_radius=15)
        pygame.draw.rect(surface, badge_border, b_rect, width=1, border_radius=15)
        surface.blit(badge_s, (b_rect.x + 8, b_rect.y + 7))

    def _draw_bottom_dock(self, surface, w, h):
        """Packet Tracer bottom docked device and cabling palette."""
        dock_h = 100
        dock_y = h - dock_h
        dock_rect = pygame.Rect(0, dock_y, w, dock_h)

        # Background with top border
        pygame.draw.rect(surface, (255, 255, 255), dock_rect)
        pygame.draw.line(surface, (215, 225, 238), (0, dock_y), (w, dock_y), 1)

        # 1. Left Categories Toolbar
        cat_w = 210
        cat_rect = pygame.Rect(12, dock_y + 8, cat_w, dock_h - 16)
        pygame.draw.rect(surface, (244, 248, 254), cat_rect, border_radius=8)

        categories = [
            ("network", "Network Devices"),
            ("end_devices", "End Devices"),
            ("connections", "Connections / Cables")
        ]
        for idx, (cat_id, cat_title) in enumerate(categories):
            btn_r = pygame.Rect(cat_rect.x + 6, cat_rect.y + 6 + idx * 28, cat_rect.w - 12, 26)
            self.cached_btn_rects[f"cat_{cat_id}"] = btn_r
            is_active = (self.active_category == cat_id)
            bg = (0, 115, 230) if is_active else ((230, 240, 252) if btn_r.collidepoint(pygame.mouse.get_pos()) else (255, 255, 255))
            txt_c = (255, 255, 255) if is_active else (25, 45, 75)
            pygame.draw.rect(surface, bg, btn_r, border_radius=4)
            lbl = self.font_badge.render(cat_title, True, txt_c)
            surface.blit(lbl, (btn_r.x + 8, btn_r.y + 6))

        # 2. Center Items Palette based on active category
        items_x = cat_rect.right + 14
        items_w = w - items_x - 170

        if self.active_category == "network":
            items = [
                ("router", "Router", "Cisco 2U Modular", (0, 102, 204)),
                ("switch", "Switch", "Catalyst 1U 8-Port", (16, 145, 65)),
                ("firewall", "Firewall", "Cisco ASA 5506-X", (195, 30, 45)),
            ]
        elif self.active_category == "end_devices":
            items = [
                ("server", "Server", "Enterprise 2U Host", (220, 130, 15)),
                ("pc", "PC Workstation", "Desktop Workstation", (0, 145, 210)),
                ("laptop", "Laptop", "Ubuntu / Windows", (80, 110, 145)),
            ]
        else:
            items = [
                ("cable_cat6", "Cat6 UTP", "Copper Straight-Through", (0, 102, 204)),
                ("cable_fiber", "Fiber Optic", "LC Duplex Optical", (235, 140, 20)),
                ("cable_console", "Console Cable", "Rollover RJ45/USB", (0, 175, 235)),
            ]

        for idx, (i_id, i_title, i_sub, i_col) in enumerate(items):
            i_rect = pygame.Rect(items_x + idx * 165, dock_y + 12, 155, dock_h - 24)
            self.cached_btn_rects[f"item_{i_id}"] = i_rect
            is_hover = i_rect.collidepoint(pygame.mouse.get_pos())
            is_selected_cable = (i_id == "cable_cat6" and self.selected_tool == "cable" and self.active_cable_type == CableType.CAT6) or \
                                (i_id == "cable_fiber" and self.selected_tool == "cable" and self.active_cable_type == CableType.FIBER) or \
                                (i_id == "cable_console" and self.selected_tool == "cable" and self.active_cable_type == CableType.CONSOLE)

            bg = (235, 245, 255) if (is_selected_cable or is_hover) else (255, 255, 255)
            border_c = i_col if (is_selected_cable or is_hover) else (215, 228, 242)
            pygame.draw.rect(surface, bg, i_rect, border_radius=6)
            pygame.draw.rect(surface, border_c, i_rect, width=2 if is_selected_cable else 1, border_radius=6)

            # Indicator dot
            pygame.draw.circle(surface, i_col, (i_rect.x + 16, i_rect.y + 18), 6)
            # Item title
            t_s = self.font_btn.render(i_title, True, (20, 35, 55))
            surface.blit(t_s, (i_rect.x + 28, i_rect.y + 10))
            # Subtitle
            s_s = self.font_sub.render(i_sub, True, (90, 110, 135))
            surface.blit(s_s, (i_rect.x + 14, i_rect.y + 36))
            # Action hint
            act_txt = "Click to cable" if i_id.startswith("cable") else "+ Drag or click to place"
            act_s = self.font_badge.render(act_txt, True, i_col)
            surface.blit(act_s, (i_rect.x + 14, i_rect.y + 56))

        # 3. Right Tool Buttons (Select / Delete)
        tools_x = w - 160
        tools_rect = pygame.Rect(tools_x, dock_y + 8, 148, dock_h - 16)
        pygame.draw.rect(surface, (244, 248, 254), tools_rect, border_radius=8)

        # Select/Pan Tool
        sel_rect = pygame.Rect(tools_rect.x + 6, tools_rect.y + 8, tools_rect.w - 12, 32)
        self.cached_btn_rects["tool_select"] = sel_rect
        is_sel = (self.selected_tool == "select")
        sel_bg = (0, 115, 230) if is_sel else (255, 255, 255)
        sel_txt_c = (255, 255, 255) if is_sel else (25, 45, 75)
        pygame.draw.rect(surface, sel_bg, sel_rect, border_radius=4)
        sel_s = self.font_btn.render("Select / Pan [V]", True, sel_txt_c)
        surface.blit(sel_s, (sel_rect.x + (sel_rect.w - sel_s.get_width()) // 2, sel_rect.y + 7))

        # Delete Tool
        del_rect = pygame.Rect(tools_rect.x + 6, tools_rect.y + 46, tools_rect.w - 12, 32)
        self.cached_btn_rects["tool_delete"] = del_rect
        is_del = (self.selected_tool == "delete")
        del_bg = (215, 40, 50) if is_del else (255, 255, 255)
        del_txt_c = (255, 255, 255) if is_del else (215, 40, 50)
        pygame.draw.rect(surface, del_bg, del_rect, border_radius=4)
        del_s = self.font_btn.render("Delete [Del]", True, del_txt_c)
        surface.blit(del_s, (del_rect.x + (del_rect.w - del_s.get_width()) // 2, del_rect.y + 7))

    def _draw_view_only_dock(self, surface, w, h):
        """Clean informational banner shown when in Tutorial or Challenge mode."""
        dock_h = 56
        dock_y = h - dock_h
        dock_rect = pygame.Rect(0, dock_y, w, dock_h)

        pygame.draw.rect(surface, (255, 255, 255), dock_rect)
        pygame.draw.line(surface, (215, 225, 238), (0, dock_y), (w, dock_y), 1)

        info_txt = "[!] View-Only Mode: You can inspect ports and cabling, but cannot add, modify, or delete devices during missions."
        lbl = self.font_btn.render(info_txt, True, (60, 85, 120))
        surface.blit(lbl, (w // 2 - lbl.get_width() // 2, dock_y + 18))

    # -------------------------------------------------------------------------
    # MODAL DIALOGS
    # -------------------------------------------------------------------------
    def _draw_port_picker_modal(self, surface, w, h):
        """Port selection dialog styled after Cisco Packet Tracer."""
        dev = self.port_picker_dev
        mode_title = "Select Source Port" if self.port_picker_mode == "source" else "Select Target Port"

        dialog_w = 420
        ports = list(dev.ports.values())
        dialog_h = min(480, 110 + len(ports) * 44)
        dx = (w - dialog_w) // 2
        dy = (h - dialog_h) // 2
        d_rect = pygame.Rect(dx, dy, dialog_w, dialog_h)

        # Backdrop dim
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 80))
        surface.blit(dim, (0, 0))

        # Modal Window
        pygame.draw.rect(surface, (255, 255, 255), d_rect, border_radius=10)
        pygame.draw.rect(surface, (0, 115, 230), d_rect, width=2, border_radius=10)

        # Header
        header_r = pygame.Rect(dx, dy, dialog_w, 48)
        pygame.draw.rect(surface, (0, 102, 204), header_r, border_top_left_radius=10, border_top_right_radius=10)
        t_s = self.font_title.render(mode_title, True, (255, 255, 255))
        surface.blit(t_s, (dx + 16, dy + 12))

        # Close button [X]
        close_r = pygame.Rect(dx + dialog_w - 36, dy + 10, 26, 26)
        self.cached_btn_rects["close_port_picker"] = close_r
        pygame.draw.rect(surface, (255, 255, 255), close_r, border_radius=4)
        x_s = self.font_btn.render("X", True, (0, 102, 204))
        surface.blit(x_s, (close_r.x + 7, close_r.y + 4))

        # Subtitle
        sub_txt = f"Device: {dev.hostname} ({dev.device_type.upper()})"
        sub_s = self.font_node_sub.render(sub_txt, True, (80, 105, 135))
        surface.blit(sub_s, (dx + 18, dy + 56))

        # Ports list
        self.port_picker_rects.clear()
        start_py = dy + 82

        for pi, port in enumerate(ports):
            pr = pygame.Rect(dx + 18, start_py + pi * 42, dialog_w - 36, 36)
            self.port_picker_rects.append((port, pr))

            is_connected = (port.cable is not None)
            is_hover = pr.collidepoint(pygame.mouse.get_pos())

            if is_connected:
                bg = (245, 247, 250)
                border_c = (220, 228, 238)
                name_c = (120, 135, 155)
                peer = port.cable.get_peer_port(port)
                peer_name = peer.device.hostname if peer else "Connected"
                status_txt = f"Connected -> {peer_name}:{peer.name}"
                status_c = (140, 150, 165)
            else:
                bg = (235, 248, 255) if is_hover else (255, 255, 255)
                border_c = (0, 120, 240) if is_hover else (195, 215, 238)
                name_c = (15, 45, 80)
                status_txt = "[Available] Ready to connect"
                status_c = (16, 155, 75)

            pygame.draw.rect(surface, bg, pr, border_radius=6)
            pygame.draw.rect(surface, border_c, pr, width=1, border_radius=6)

            p_name = self.font_mono_bold.render(port.name, True, name_c)
            surface.blit(p_name, (pr.x + 12, pr.y + 10))

            p_stat = self.font_node_sub.render(status_txt, True, status_c)
            surface.blit(p_stat, (pr.right - p_stat.get_width() - 12, pr.y + 10))

    def _draw_device_inspector_modal(self, surface, w, h, is_sandbox):
        """Device Properties & 3D Rack Location modal dialog."""
        dev = self.inspect_dev
        dw, dh = 480, 420
        dx = (w - dw) // 2
        dy = (h - dh) // 2
        d_rect = pygame.Rect(dx, dy, dw, dh)

        # Backdrop dim
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 80))
        surface.blit(dim, (0, 0))

        # Dialog Box
        pygame.draw.rect(surface, (255, 255, 255), d_rect, border_radius=10)
        pygame.draw.rect(surface, (0, 115, 230), d_rect, width=2, border_radius=10)

        # Header
        header_r = pygame.Rect(dx, dy, dw, 52)
        pygame.draw.rect(surface, (0, 102, 204), header_r, border_top_left_radius=10, border_top_right_radius=10)
        t_s = self.font_title.render("Device Properties", True, (255, 255, 255))
        surface.blit(t_s, (dx + 16, dy + 14))

        # Close button [X]
        close_r = pygame.Rect(dx + dw - 38, dy + 12, 28, 28)
        self.cached_btn_rects["close_inspector"] = close_r
        pygame.draw.rect(surface, (255, 255, 255), close_r, border_radius=4)
        x_s = self.font_btn.render("X", True, (0, 102, 204))
        surface.blit(x_s, (close_r.x + 8, close_r.y + 5))

        # Content fields
        py = dy + 68
        # Hostname
        surface.blit(self.font_btn.render("Hostname:", True, (20, 35, 60)), (dx + 20, py))
        surface.blit(self.font_mono_bold.render(dev.hostname, True, (0, 102, 204)), (dx + 210, py))
        py += 32

        # Device Type
        surface.blit(self.font_btn.render("Device Type:", True, (20, 35, 60)), (dx + 20, py))
        surface.blit(self.font_node_title.render(dev.device_type.upper(), True, (25, 45, 75)), (dx + 210, py))
        py += 32

        # 3D Rack Location
        surface.blit(self.font_btn.render("3D Datacenter Location:", True, (20, 35, 60)), (dx + 20, py))
        if getattr(dev, "rack_id", 0) in (1, 2, 3):
            r_str = f"Rack 0{dev.rack_id} (Slot {dev.u_slot}U)"
        elif getattr(dev, "device_type", "") in ("laptop", "pc"):
            r_str = "NOC Workbench Desk"
        else:
            r_str = "Unassigned Location"
        surface.blit(self.font_node_title.render(r_str, True, (16, 145, 65)), (dx + 210, py))
        py += 36

        # Port Summary Box
        pygame.draw.line(surface, (220, 230, 242), (dx + 20, py), (dx + dw - 20, py), 1)
        py += 12
        surface.blit(self.font_btn.render("Port List & Active Links:", True, (20, 35, 60)), (dx + 20, py))
        py += 26

        port_box_r = pygame.Rect(dx + 20, py, dw - 40, 120)
        pygame.draw.rect(surface, (246, 249, 254), port_box_r, border_radius=6)
        pygame.draw.rect(surface, (215, 228, 242), port_box_r, width=1, border_radius=6)

        for p_idx, port in enumerate(list(dev.ports.values())[:4]):
            p_y = port_box_r.y + 8 + p_idx * 26
            c_info = f"-> {port.cable.get_peer_port(port).device.hostname}:{port.cable.get_peer_port(port).name}" if port.cable else "Available"
            p_line = f"{port.name.upper()}: {port.ip_address or 'No IP'}"
            col = (16, 145, 65) if port.is_link_up else ((210, 130, 20) if port.cable else (100, 120, 140))
            p_surf = self.font_mono.render(p_line, True, col)
            surface.blit(p_surf, (port_box_r.x + 10, p_y))
            c_surf = self.font_node_sub.render(f"({c_info})", True, (110, 130, 155))
            surface.blit(c_surf, (port_box_r.x + 10 + p_surf.get_width() + 8, p_y - 1))

        py = port_box_r.bottom + 18

        # Bottom Action Buttons
        # CLI Terminal Button
        cli_r = pygame.Rect(dx + 20, py, 200, 38)
        self.cached_btn_rects["open_cli_btn"] = cli_r
        pygame.draw.rect(surface, (0, 102, 204), cli_r, border_radius=6)
        cli_txt = self.font_btn.render("Open CLI Terminal [E]", True, (255, 255, 255))
        surface.blit(cli_txt, (cli_r.x + (cli_r.w - cli_txt.get_width()) // 2, cli_r.y + 9))

        # Close Button
        done_r = pygame.Rect(dx + dw - 140, py, 120, 38)
        self.cached_btn_rects["close_inspector_btn"] = done_r
        pygame.draw.rect(surface, (240, 245, 252), done_r, border_radius=6)
        pygame.draw.rect(surface, (190, 210, 235), done_r, width=1, border_radius=6)
        d_txt = self.font_btn.render("Close", True, (25, 45, 75))
        surface.blit(d_txt, (done_r.x + (done_r.w - d_txt.get_width()) // 2, done_r.y + 9))

    def _draw_rack_picker_modal(self, surface, w, h, mode):
        """Custom interactive 3D Rack and U-slot selection modal."""
        dw, dh = 500, 440
        dx = (w - dw) // 2
        dy = (h - dh) // 2
        d_rect = pygame.Rect(dx, dy, dw, dh)

        # Backdrop dim
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 85))
        surface.blit(dim, (0, 0))

        # Modal Box
        pygame.draw.rect(surface, (255, 255, 255), d_rect, border_radius=10)
        pygame.draw.rect(surface, (0, 115, 230), d_rect, width=2, border_radius=10)

        # Header
        header_r = pygame.Rect(dx, dy, dw, 50)
        pygame.draw.rect(surface, (0, 102, 204), header_r, border_top_left_radius=10, border_top_right_radius=10)
        t_s = self.font_title.render("Rack Slot & Position Selection", True, (255, 255, 255))
        surface.blit(t_s, (dx + 16, dy + 13))

        # Close button [X]
        close_r = pygame.Rect(dx + dw - 38, dy + 11, 28, 28)
        self.cached_btn_rects["close_rack_picker"] = close_r
        pygame.draw.rect(surface, (255, 255, 255), close_r, border_radius=4)
        x_s = self.font_btn.render("X", True, (0, 102, 204))
        surface.blit(x_s, (close_r.x + 8, close_r.y + 5))

        # Subtitle
        dev_type_str = (self.rack_picker_dev_type or "DEVICE").upper()
        sub_s = self.font_node_sub.render(f"Configure 3D datacenter mount position for new {dev_type_str}", True, (80, 105, 135))
        surface.blit(sub_s, (dx + 20, dy + 60))

        py = dy + 84

        # Section 1: Target Rack Unit
        sec1_lbl = self.font_btn.render("Target Server Rack:", True, (20, 35, 60))
        surface.blit(sec1_lbl, (dx + 20, py))
        py += 26

        rack_tabs = [
            (1, "Rack 1: Core"),
            (2, "Rack 2: Dist"),
            (3, "Rack 3: Storage")
        ]
        tab_w = (dw - 40 - 16) // 3
        for idx, (r_id, r_label) in enumerate(rack_tabs):
            r_rect = pygame.Rect(dx + 20 + idx * (tab_w + 8), py, tab_w, 36)
            self.cached_btn_rects[f"rack_tab_{r_id}"] = r_rect
            is_active = (self.rack_picker_rack_id == r_id)
            bg = (0, 115, 230) if is_active else (244, 248, 254)
            border_c = (0, 90, 180) if is_active else (210, 225, 240)
            txt_c = (255, 255, 255) if is_active else (25, 45, 75)
            pygame.draw.rect(surface, bg, r_rect, border_radius=6)
            pygame.draw.rect(surface, border_c, r_rect, width=1, border_radius=6)
            tab_txt = self.font_btn.render(r_label, True, txt_c)
            surface.blit(tab_txt, (r_rect.x + (r_rect.w - tab_txt.get_width()) // 2, r_rect.y + 8))

        py += 48

        # Section 2: Rack Unit Slot Stepper & Auto-Find
        sec2_lbl = self.font_btn.render("Rack Unit Position (U-Slot 1 - 42):", True, (20, 35, 60))
        surface.blit(sec2_lbl, (dx + 20, py))
        py += 26

        # Stepper [-]
        minus_r = pygame.Rect(dx + 20, py, 40, 36)
        self.cached_btn_rects["slot_minus"] = minus_r
        is_m_hov = minus_r.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(surface, (235, 245, 255) if is_m_hov else (244, 248, 254), minus_r, border_radius=6)
        pygame.draw.rect(surface, (180, 205, 235), minus_r, width=1, border_radius=6)
        m_lbl = self.font_title.render("-", True, (0, 102, 204))
        surface.blit(m_lbl, (minus_r.x + (minus_r.w - m_lbl.get_width()) // 2, minus_r.y + 3))

        # Current Slot Box
        slot_box_r = pygame.Rect(minus_r.right + 8, py, 110, 36)
        pygame.draw.rect(surface, (255, 255, 255), slot_box_r, border_radius=6)
        pygame.draw.rect(surface, (0, 115, 230), slot_box_r, width=1, border_radius=6)
        slot_str = f"Slot {self.rack_picker_slot}U"
        slot_txt = self.font_btn.render(slot_str, True, (15, 35, 65))
        surface.blit(slot_txt, (slot_box_r.x + (slot_box_r.w - slot_txt.get_width()) // 2, slot_box_r.y + 8))

        # Stepper [+]
        plus_r = pygame.Rect(slot_box_r.right + 8, py, 40, 36)
        self.cached_btn_rects["slot_plus"] = plus_r
        is_p_hov = plus_r.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(surface, (235, 245, 255) if is_p_hov else (244, 248, 254), plus_r, border_radius=6)
        pygame.draw.rect(surface, (180, 205, 235), plus_r, width=1, border_radius=6)
        p_lbl = self.font_title.render("+", True, (0, 102, 204))
        surface.blit(p_lbl, (plus_r.x + (plus_r.w - p_lbl.get_width()) // 2, plus_r.y + 3))

        # [Auto Free Slot] button
        auto_r = pygame.Rect(plus_r.right + 14, py, dw - 40 - (plus_r.right + 14 - (dx + 20)), 36)
        self.cached_btn_rects["slot_auto_find"] = auto_r
        is_a_hov = auto_r.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(surface, (235, 248, 255) if is_a_hov else (244, 248, 254), auto_r, border_radius=6)
        pygame.draw.rect(surface, (0, 120, 240), auto_r, width=1, border_radius=6)
        a_lbl = self.font_badge.render("Find Free Slot", True, (0, 102, 204))
        surface.blit(a_lbl, (auto_r.x + (auto_r.w - a_lbl.get_width()) // 2, auto_r.y + 9))

        py += 46

        # Real-time Occupancy Badge
        needed_u = 1 if self.rack_picker_dev_type in ("switch", "firewall", "isp_gateway", "isp") else 2
        occupied = False
        occ_dev = None
        if mode and hasattr(mode, "is_slot_occupied"):
            occupied, occ_dev = mode.is_slot_occupied(self.rack_picker_rack_id, self.rack_picker_slot, needed_u)

        badge_rect = pygame.Rect(dx + 20, py, dw - 40, 36)
        if occupied:
            pygame.draw.rect(surface, (254, 242, 242), badge_rect, border_radius=6)
            pygame.draw.rect(surface, (239, 68, 68), badge_rect, width=1, border_radius=6)
            val_txt = f"[Conflict] Slot {self.rack_picker_slot}U is occupied by {occ_dev.hostname} ({occ_dev.device_type.upper()})"
            val_s = self.font_node_sub.render(val_txt, True, (185, 28, 28))
        else:
            pygame.draw.rect(surface, (240, 253, 244), badge_rect, border_radius=6)
            pygame.draw.rect(surface, (34, 197, 94), badge_rect, width=1, border_radius=6)
            val_txt = f"[Available] Slot {self.rack_picker_slot}U ({needed_u}U) is free in Rack 0{self.rack_picker_rack_id}"
            val_s = self.font_node_sub.render(val_txt, True, (21, 128, 61))
        surface.blit(val_s, (badge_rect.x + 12, badge_rect.y + 10))

        py += 48

        # Section 3: Hostname Input Field
        h_lbl = self.font_btn.render("Device Hostname:", True, (20, 35, 60))
        surface.blit(h_lbl, (dx + 20, py))
        py += 24

        h_rect = pygame.Rect(dx + 20, py, dw - 40, 36)
        self.cached_btn_rects["hostname_input"] = h_rect
        h_border = (0, 120, 240) if self.rack_picker_hostname_active else (210, 225, 240)
        pygame.draw.rect(surface, (255, 255, 255), h_rect, border_radius=6)
        pygame.draw.rect(surface, h_border, h_rect, width=2 if self.rack_picker_hostname_active else 1, border_radius=6)

        cursor = "|" if (self.rack_picker_hostname_active and int(time.time() * 2) % 2 == 0) else ""
        h_text_render = self.font_mono_bold.render(self.rack_picker_hostname + cursor, True, (15, 45, 80))
        surface.blit(h_text_render, (h_rect.x + 12, h_rect.y + 8))

        # Bottom Action Buttons
        btn_y = dy + dh - 48
        # Cancel Button
        cancel_r = pygame.Rect(dx + dw - 240, btn_y, 100, 36)
        self.cached_btn_rects["rack_picker_cancel"] = cancel_r
        is_c_hov = cancel_r.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(surface, (244, 248, 254) if is_c_hov else (255, 255, 255), cancel_r, border_radius=6)
        pygame.draw.rect(surface, (190, 210, 235), cancel_r, width=1, border_radius=6)
        c_txt = self.font_btn.render("Cancel", True, (65, 85, 115))
        surface.blit(c_txt, (cancel_r.x + (cancel_r.w - c_txt.get_width()) // 2, cancel_r.y + 8))

        # Install Button
        install_r = pygame.Rect(dx + dw - 128, btn_y, 110, 36)
        self.cached_btn_rects["rack_picker_install"] = install_r
        can_install = not occupied and bool(self.rack_picker_hostname.strip())
        is_i_hov = install_r.collidepoint(pygame.mouse.get_pos())

        if can_install:
            i_bg = (20, 165, 75) if is_i_hov else (16, 145, 65)
            i_txt_c = (255, 255, 255)
        else:
            i_bg = (230, 235, 242)
            i_txt_c = (155, 170, 185)

        pygame.draw.rect(surface, i_bg, install_r, border_radius=6)
        i_txt = self.font_btn.render("Install in Rack", True, i_txt_c)
        surface.blit(i_txt, (install_r.x + (install_r.w - i_txt.get_width()) // 2, install_r.y + 8))

    def _draw_toast(self, surface, w, h):
        tw, th = self.font_toast.size(self.toast_msg)
        toast_w = tw + 32
        toast_h = th + 16
        tx = (w - toast_w) // 2
        ty = 56
        t_rect = pygame.Rect(tx, ty, toast_w, toast_h)

        pygame.draw.rect(surface, (255, 255, 255), t_rect, border_radius=8)
        pygame.draw.rect(surface, self.toast_color, t_rect, width=2, border_radius=8)
        t_lbl = self.font_toast.render(self.toast_msg, True, self.toast_color)
        surface.blit(t_lbl, (tx + 16, ty + 8))

    # -------------------------------------------------------------------------
    # INPUT HANDLING
    # -------------------------------------------------------------------------
    def handle_input(self, event, sound_mgr, screen_w, screen_h, mode=None):
        from modes.sandbox_mode import SandboxMode
        is_sandbox = isinstance(mode, SandboxMode)
        devices = mode.devices if mode else []
        cables = mode.cables if mode else []

        # 1. Global Key shortcuts
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_m):
                # Close any active modal first
                if self.rack_picker_open:
                    self.rack_picker_open = False
                    sound_mgr.play_key()
                    return None
                if self.port_picker_dev:
                    self.port_picker_dev = None
                    self.cable_source_dev = None
                    self.cable_source_port = None
                    return None
                if self.inspect_dev:
                    self.inspect_dev = None
                    return None
                if self.placing_device_type:
                    self.placing_device_type = None
                    return None
                # Otherwise return to 3D Datacenter!
                sound_mgr.play_key()
                return "RESUME"

            if event.key == pygame.K_v:
                self.selected_tool = "select"
                self.placing_device_type = None
            elif event.key == pygame.K_DELETE and is_sandbox:
                if self.selected_dev:
                    self._remove_device(self.selected_dev, mode, sound_mgr)
                    self.selected_dev = None

        # 2. Modal Input Interception (Rack Slot Picker, Port Picker, Inspector)
        if self.rack_picker_open:
            return self._handle_rack_picker_input(event, sound_mgr, mode)
        if self.port_picker_dev:
            return self._handle_port_picker_input(event, sound_mgr, mode)
        if self.inspect_dev:
            return self._handle_inspector_input(event, sound_mgr, mode)

        # 3. Top bar and Dock Buttons clicks
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # Back to 3D Button
            if self.cached_btn_rects.get("back_3d", pygame.Rect(0, 0, 0, 0)).collidepoint(mx, my):
                sound_mgr.play_key()
                return "RESUME"

            # Auto Arrange Button
            if self.cached_btn_rects.get("auto_arrange", pygame.Rect(0, 0, 0, 0)).collidepoint(mx, my):
                sound_mgr.play_key()
                self.auto_arrange(devices, screen_w, screen_h)
                return None

            # Dock Category Buttons (Sandbox only)
            if is_sandbox:
                for cat_id in ("network", "end_devices", "connections"):
                    rect = self.cached_btn_rects.get(f"cat_{cat_id}")
                    if rect and rect.collidepoint(mx, my):
                        sound_mgr.play_key()
                        self.active_category = cat_id
                        return None

                # Dock Item Buttons scoped STRICTLY to active category to prevent collisions!
                if self.active_category == "network":
                    for i_id in ("router", "switch", "firewall"):
                        rect = self.cached_btn_rects.get(f"item_{i_id}")
                        if rect and rect.collidepoint(mx, my):
                            sound_mgr.play_key()
                            self.placing_device_type = i_id
                            self.selected_tool = "select"
                            return None
                elif self.active_category == "end_devices":
                    for i_id in ("server", "pc", "laptop"):
                        rect = self.cached_btn_rects.get(f"item_{i_id}")
                        if rect and rect.collidepoint(mx, my):
                            sound_mgr.play_key()
                            self.placing_device_type = i_id
                            self.selected_tool = "select"
                            return None
                elif self.active_category == "connections":
                    cable_map = {
                        "cable_cat6": CableType.CAT6,
                        "cable_fiber": CableType.FIBER,
                        "cable_console": CableType.CONSOLE,
                    }
                    for c_btn, c_type in cable_map.items():
                        rect = self.cached_btn_rects.get(f"item_{c_btn}")
                        if rect and rect.collidepoint(mx, my):
                            sound_mgr.play_key()
                            self.selected_tool = "cable"
                            self.active_cable_type = c_type
                            self.placing_device_type = None
                            self.show_toast("Click source device to begin cabling", (0, 115, 230))
                            return None

                # Tool Buttons (Select / Delete)
                if self.cached_btn_rects.get("tool_select", pygame.Rect(0, 0, 0, 0)).collidepoint(mx, my):
                    sound_mgr.play_key()
                    self.selected_tool = "select"
                    self.placing_device_type = None
                    return None

                if self.cached_btn_rects.get("tool_delete", pygame.Rect(0, 0, 0, 0)).collidepoint(mx, my):
                    sound_mgr.play_key()
                    self.selected_tool = "delete"
                    self.placing_device_type = None
                    self.show_toast("Click on device or cable link to delete", (215, 40, 50))
                    return None

        # 4. Canvas Placement of new device (Sandbox only)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.placing_device_type and is_sandbox:
            mx, my = event.pos
            # Ignore if clicking in top bar or bottom dock
            if my > 56 and my < screen_h - 100:
                wx, wy = self._screen_to_world(mx, my)
                dev_type = self.placing_device_type
                if dev_type in ("pc", "laptop"):
                    # Place workstations on workbench table directly
                    self._spawn_device_at(dev_type, wx, wy, mode, sound_mgr)
                    self.placing_device_type = None
                else:
                    # Open interactive Rack Slot Picker for 3D rack appliances
                    self._open_rack_picker(dev_type, wx, wy, mode)
                    self.placing_device_type = None
                return None

        # Right click cancels placing or cabling
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.placing_device_type:
                self.placing_device_type = None
            if self.cable_source_dev:
                self.cable_source_dev = None
                self.cable_source_port = None
            return None

        # 5. Canvas Zoom (Mouse Wheel)
        if event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            old_wx, old_wy = self._screen_to_world(mx, my)
            zoom_factor = 1.1 if event.y > 0 else 0.9
            new_zoom = max(0.6, min(1.8, self.zoom * zoom_factor))
            self.zoom = new_zoom
            # Re-center around mouse
            self.pan_x = mx - old_wx * self.zoom
            self.pan_y = my - old_wy * self.zoom
            return None

        # 6. Canvas Pan (Middle click or Right click drag)
        if event.type == pygame.MOUSEBUTTONDOWN and (event.button == 2 or (event.button == 3 and not self.cable_source_dev)):
            self.is_panning = True
            self.pan_start_mouse = event.pos
            self.pan_start_offset = (self.pan_x, self.pan_y)
            return None
        elif event.type == pygame.MOUSEBUTTONUP and (event.button == 2 or event.button == 3):
            self.is_panning = False
            return None
        elif event.type == pygame.MOUSEMOTION and self.is_panning:
            dx = event.pos[0] - self.pan_start_mouse[0]
            dy = event.pos[1] - self.pan_start_mouse[1]
            self.pan_x = self.pan_start_offset[0] + dx
            self.pan_y = self.pan_start_offset[1] + dy
            return None

        # 7. Device Node Hover & Interaction
        mx, my = pygame.mouse.get_pos()
        card_w = 160 * self.zoom
        card_h = 76 * self.zoom

        self.hovered_dev = None
        for dev in reversed(devices):
            if hasattr(dev, "topo_x") and hasattr(dev, "topo_y"):
                sx, sy = self._world_to_screen(dev.topo_x, dev.topo_y)
                rect = pygame.Rect(sx - card_w / 2.0, sy - card_h / 2.0, card_w, card_h)
                if rect.collidepoint(mx, my) and my > 56 and my < (screen_h - 100 if is_sandbox else screen_h - 56):
                    self.hovered_dev = dev
                    break

        # Node Click Actions
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.hovered_dev:
            target_dev = self.hovered_dev
            sound_mgr.play_key()

            # Tool: Cable (Sandbox only)
            if self.selected_tool == "cable" and is_sandbox:
                if not self.cable_source_dev:
                    # Pick source port on target_dev
                    self.cable_source_dev = target_dev
                    self.port_picker_dev = target_dev
                    self.port_picker_mode = "source"
                else:
                    if target_dev != self.cable_source_dev:
                        # Pick target port on target_dev
                        self.cable_target_dev = target_dev
                        self.port_picker_dev = target_dev
                        self.port_picker_mode = "target"
                return None

            # Tool: Delete (Sandbox only)
            elif self.selected_tool == "delete" and is_sandbox:
                self._remove_device(target_dev, mode, sound_mgr)
                return None

            # Tool: Select / Drag
            else:
                self.selected_dev = target_dev
                self.dragging_dev = target_dev
                self.drag_start_pos = (mx, my)
                return None

        # Double-click or click inspector
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and event.dict.get("clicks", 1) >= 2 and self.hovered_dev:
            self.inspect_dev = self.hovered_dev
            return None

        # Node Drag Motion
        if event.type == pygame.MOUSEMOTION and self.dragging_dev:
            wx, wy = self._screen_to_world(mx, my)
            self.dragging_dev.topo_x = wx
            self.dragging_dev.topo_y = wy
            return None

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging_dev = None

        return None

    def _handle_rack_picker_input(self, event, sound_mgr, mode):
        needed_u = 1 if self.rack_picker_dev_type in ("switch", "firewall", "isp_gateway", "isp") else 2

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                sound_mgr.play_key()
                self.rack_picker_open = False
                return None
            if self.rack_picker_hostname_active:
                if event.key == pygame.K_BACKSPACE:
                    self.rack_picker_hostname = self.rack_picker_hostname[:-1]
                    sound_mgr.play_key()
                    return None
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    # Enter triggers install
                    pass
                elif event.unicode and len(self.rack_picker_hostname) < 20:
                    if event.unicode.isalnum() or event.unicode in ("-", "_"):
                        self.rack_picker_hostname += event.unicode
                        sound_mgr.play_key()
                        return None

        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1) or \
           (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.rack_picker_hostname_active):
            mx, my = event.pos if event.type == pygame.MOUSEBUTTONDOWN else (0, 0)

            # Close [X] or Cancel
            if event.type == pygame.MOUSEBUTTONDOWN and (
                self.cached_btn_rects.get("close_rack_picker", pygame.Rect(0, 0, 0, 0)).collidepoint(mx, my) or
                self.cached_btn_rects.get("rack_picker_cancel", pygame.Rect(0, 0, 0, 0)).collidepoint(mx, my)
            ):
                sound_mgr.play_key()
                self.rack_picker_open = False
                return None

            # Hostname input focus
            if event.type == pygame.MOUSEBUTTONDOWN:
                h_rect = self.cached_btn_rects.get("hostname_input", pygame.Rect(0, 0, 0, 0))
                self.rack_picker_hostname_active = h_rect.collidepoint(mx, my)

            # Target Rack tabs
            if event.type == pygame.MOUSEBUTTONDOWN:
                for r_id in (1, 2, 3):
                    tab_r = self.cached_btn_rects.get(f"rack_tab_{r_id}", pygame.Rect(0, 0, 0, 0))
                    if tab_r.collidepoint(mx, my):
                        sound_mgr.play_key()
                        self.rack_picker_rack_id = r_id
                        # If slot occupied in new rack, auto-suggest next free slot
                        if mode and hasattr(mode, "is_slot_occupied"):
                            occupied, _ = mode.is_slot_occupied(r_id, self.rack_picker_slot, needed_u)
                            if occupied and hasattr(mode, "find_next_free_slot"):
                                _, new_slot = mode.find_next_free_slot(preferred_rack_id=r_id, needed_u=needed_u)
                                self.rack_picker_slot = new_slot
                        return None

                # Stepper [-]
                if self.cached_btn_rects.get("slot_minus", pygame.Rect(0, 0, 0, 0)).collidepoint(mx, my):
                    sound_mgr.play_key()
                    self.rack_picker_slot = max(1, self.rack_picker_slot - 1)
                    return None

                # Stepper [+]
                if self.cached_btn_rects.get("slot_plus", pygame.Rect(0, 0, 0, 0)).collidepoint(mx, my):
                    sound_mgr.play_key()
                    self.rack_picker_slot = min(42 - needed_u + 1, self.rack_picker_slot + 1)
                    return None

                # Auto Find Free Slot
                if self.cached_btn_rects.get("slot_auto_find", pygame.Rect(0, 0, 0, 0)).collidepoint(mx, my):
                    if hasattr(mode, "find_next_free_slot"):
                        r_id, u_slot = mode.find_next_free_slot(preferred_rack_id=self.rack_picker_rack_id, needed_u=needed_u)
                        self.rack_picker_rack_id = r_id
                        self.rack_picker_slot = u_slot
                        sound_mgr.play_objective()
                        self.show_toast(f"Found available slot: Rack 0{r_id} Slot {u_slot}U", (0, 102, 204))
                    return None

            # Install in Rack Button (or Enter key)
            install_clicked = event.type == pygame.MOUSEBUTTONDOWN and \
                self.cached_btn_rects.get("rack_picker_install", pygame.Rect(0, 0, 0, 0)).collidepoint(mx, my)
            enter_pressed = event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER)

            if install_clicked or enter_pressed:
                h_name = self.rack_picker_hostname.strip()
                if not h_name:
                    sound_mgr.play_error()
                    self.show_toast("Please specify a valid device hostname", (215, 40, 50))
                    return None

                if mode and hasattr(mode, "is_slot_occupied"):
                    occupied, occ_dev = mode.is_slot_occupied(self.rack_picker_rack_id, self.rack_picker_slot, needed_u)
                    if occupied:
                        sound_mgr.play_error()
                        self.show_toast(f"Slot {self.rack_picker_slot}U is occupied by {occ_dev.hostname}", (215, 40, 50))
                        return None

                ok, msg, dev = mode.add_device(self.rack_picker_dev_type, self.rack_picker_rack_id, self.rack_picker_slot, hostname=h_name)
                if ok and dev:
                    dev.topo_x = self.rack_picker_wx
                    dev.topo_y = self.rack_picker_wy
                    self.rack_picker_open = False
                    sound_mgr.play_objective()
                    self.show_toast(f"Installed {dev.hostname} in Rack 0{self.rack_picker_rack_id} (Slot {self.rack_picker_slot}U) successfully!", (16, 145, 65))
                else:
                    sound_mgr.play_error()
                    self.show_toast(f"Installation failed: {msg}", (215, 40, 50))
                return None

        return None

    def _handle_port_picker_input(self, event, sound_mgr, mode):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # Close button
            if self.cached_btn_rects.get("close_port_picker", pygame.Rect(0, 0, 0, 0)).collidepoint(mx, my):
                sound_mgr.play_key()
                self.port_picker_dev = None
                self.cable_source_dev = None
                self.cable_source_port = None
                return None

            # Port items
            for port, rect in self.port_picker_rects:
                if rect.collidepoint(mx, my):
                    if port.cable is not None:
                        sound_mgr.play_error()
                        self.show_toast("This port is already connected. Please select an available port.", (215, 40, 50))
                        return None

                    sound_mgr.play_cable()
                    if self.port_picker_mode == "source":
                        self.cable_source_port = port
                        self.port_picker_dev = None
                        self.show_toast(f"Selected source port {port.name}. Now click target device.", (0, 115, 230))
                    else:
                        # Create Cable!
                        self._connect_cables(self.cable_source_port, port, self.active_cable_type, mode, sound_mgr)
                        self.port_picker_dev = None
                        self.cable_source_dev = None
                        self.cable_source_port = None
                        self.cable_target_dev = None
                    return None
        return None

    def _handle_inspector_input(self, event, sound_mgr, mode):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # Close button [X] or [Close]
            if self.cached_btn_rects.get("close_inspector", pygame.Rect(0, 0, 0, 0)).collidepoint(mx, my) or \
               self.cached_btn_rects.get("close_inspector_btn", pygame.Rect(0, 0, 0, 0)).collidepoint(mx, my):
                sound_mgr.play_key()
                self.inspect_dev = None
                return None

            # Open CLI Terminal Button
            if self.cached_btn_rects.get("open_cli_btn", pygame.Rect(0, 0, 0, 0)).collidepoint(mx, my):
                sound_mgr.play_objective()
                target_dev = self.inspect_dev
                self.inspect_dev = None
                return f"OPEN_TERMINAL:{target_dev.id}"
        return None

    def _spawn_device_at(self, dev_type, wx, wy, mode, sound_mgr):
        """Creates a device and installs it with 3D datacenter sync."""
        from modes.sandbox_mode import SandboxMode
        if not isinstance(mode, SandboxMode):
            return

        r_id, u_slot = self._allocate_rack_slot(mode, dev_type)
        ok, msg, dev = mode.add_device(dev_type, r_id, u_slot)
        if ok and dev:
            dev.topo_x = wx
            dev.topo_y = wy
            sound_mgr.play_objective()
            if getattr(dev, "device_type", "") in ("laptop", "pc"):
                self.show_toast(f"Placed {dev.hostname} on NOC workbench desk successfully!", (16, 145, 65))
            else:
                self.show_toast(f"Installed {dev.hostname} in Rack 0{r_id} (Slot {u_slot}U) successfully!", (16, 145, 65))
        else:
            sound_mgr.play_error()
            self.show_toast(f"Installation failed: {msg}", (215, 40, 50))

    def _connect_cables(self, port_a, port_b, cable_type, mode, sound_mgr):
        """Creates a new cable connecting port_a and port_b."""
        if not port_a or not port_b or not mode:
            return

        # Auto-detect console rollover
        if "con" in port_a.name.lower() or "con" in port_b.name.lower():
            cable_type = CableType.CONSOLE

        cable = Cable(port_a, port_b, cable_type)
        mode.cables.append(cable)
        sound_mgr.play_cable()
        self.show_toast(f"Connected cable: {port_a.device.hostname} [{port_a.name}] <-> {port_b.device.hostname} [{port_b.name}]", (16, 145, 65))

    def _remove_device(self, dev, mode, sound_mgr):
        """Removes device and unplugs all its cables."""
        from modes.sandbox_mode import SandboxMode
        if not isinstance(mode, SandboxMode):
            return

        h_name = dev.hostname
        ok, msg = mode.remove_device(dev)
        if ok:
            sound_mgr.play_key()
            self.show_toast(f"Removed device {h_name} from rack and topology.", (215, 40, 50))
