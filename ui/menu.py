"""
ui/menu.py - Main Menu, Pause Dialog, Controls Cheatsheet, 2D Topology Visualizer, and Rack Device Manager
"""

import pygame
import math
from network.switch import Switch
from network.router import Router
from network.host import Host
from network.firewall import Firewall

class MenuState:
    MAIN_MENU = "MAIN_MENU"
    IN_GAME = "IN_GAME"
    PAUSE = "PAUSE"
    TOPOLOGY_MAP = "TOPOLOGY_MAP"
    HELP_GUIDE = "HELP_GUIDE"
    DEVICE_MANAGER = "DEVICE_MANAGER"

class MenuManager:
    def __init__(self):
        self.state = MenuState.MAIN_MENU
        self.font_logo = pygame.font.SysFont("Segoe UI", 38, bold=True) or pygame.font.Font(None, 44)
        self.font_title = pygame.font.SysFont("Segoe UI", 20, bold=True) or pygame.font.Font(None, 24)
        self.font_sub = pygame.font.SysFont("Segoe UI", 16) or pygame.font.Font(None, 20)
        self.font_btn = pygame.font.SysFont("Segoe UI", 16, bold=True) or pygame.font.Font(None, 20)
        self.font_bold = pygame.font.SysFont("Segoe UI", 14, bold=True) or pygame.font.Font(None, 18)
        self.font_body = pygame.font.SysFont("Segoe UI", 14) or pygame.font.Font(None, 18)
        self.font_small = pygame.font.SysFont("Segoe UI", 12) or pygame.font.Font(None, 15)
        self.font_mono = pygame.font.SysFont("Consolas", 13) or pygame.font.Font(None, 16)

        self.selected_button = 0
        self.menu_options = [
            ("TUTORIAL MODE", "Learn step-by-step from cabling to Cisco CLI"),
            ("CHALLENGE MODE", "Solve real-world incident tickets under pressure"),
            ("SANDBOX PLAYGROUND", "Freely build, cable, configure and save topologies"),
            ("CONTROLS & CLI CHEATSHEET", "View keybindings and Cisco command reference"),
            ("EXIT SIMULATOR", "Quit to desktop")
        ]

        # Device Manager UI State
        self.dm_rack_filter = 0  # 0: All, 1: Rack 1, 2: Rack 2, 3: Rack 3
        self.dm_selected_type = "switch"  # "switch", "router", "server"
        self.dm_selected_rack = 1
        self.dm_selected_slot = 12
        self.dm_hostname_input = "Switch-New"
        self.dm_hostname_active = False
        self.dm_scroll_offset = 0
        self.dm_feedback = ""
        self.dm_feedback_color = (15, 140, 65)

    def get_main_menu_button_rect(self, idx, w, h):
        cx = w // 2
        btn_w, btn_h = 460, 56
        start_y = 200
        by = start_y + idx * (btn_h + 14)
        bx = cx - btn_w // 2
        return pygame.Rect(bx, by, btn_w, btn_h)

    def get_pause_button_rect(self, idx, w, h):
        cx, cy = w // 2, h // 2
        card_w, card_h = 420, 280
        rx, ry = cx - card_w // 2, cy - card_h // 2
        btn_w, btn_h = 360, 40
        by = ry + 95 + idx * 45
        bx = cx - btn_w // 2
        return pygame.Rect(bx, by, btn_w, btn_h)

    def _compute_dm_rects(self, w, h):
        win_w = min(1080, max(820, w - 80))
        win_h = min(640, max(520, h - 80))
        win_x = (w - win_w) // 2
        win_y = (h - win_h) // 2

        close_rect = pygame.Rect(win_x + win_w - 42, win_y + 12, 30, 30)

        # Left panel (Inventory): 57% width
        left_w = int(win_w * 0.57) - 20
        left_x = win_x + 18
        left_y = win_y + 55
        left_h = win_h - 70

        tab_names = ["All Racks", "Rack 1", "Rack 2", "Rack 3"]
        tab_w = (left_w - 18) // 4
        tab_rects = []
        for i in range(4):
            tab_rects.append(pygame.Rect(left_x + i * (tab_w + 6), left_y + 32, tab_w, 28))

        list_rect = pygame.Rect(left_x, left_y + 68, left_w, left_h - 76)

        # Right panel (Form): 43% width
        right_w = win_w - left_w - 54
        right_x = left_x + left_w + 18
        right_y = win_y + 55
        right_h = win_h - 70

        btn_type_w = (right_w - 18) // 4
        type_rects = {
            "switch": pygame.Rect(right_x, right_y + 52, btn_type_w, 34),
            "router": pygame.Rect(right_x + (btn_type_w + 6), right_y + 52, btn_type_w, 34),
            "firewall": pygame.Rect(right_x + (btn_type_w + 6) * 2, right_y + 52, btn_type_w, 34),
            "server": pygame.Rect(right_x + (btn_type_w + 6) * 3, right_y + 52, btn_type_w, 34),
        }

        btn_rack_w = (right_w - 12) // 3
        rack_rects = {
            1: pygame.Rect(right_x, right_y + 122, btn_rack_w, 32),
            2: pygame.Rect(right_x + btn_rack_w + 6, right_y + 122, btn_rack_w, 32),
            3: pygame.Rect(right_x + (btn_rack_w + 6) * 2, right_y + 122, btn_rack_w, 32),
        }

        slot_minus_rect = pygame.Rect(right_x, right_y + 188, 42, 34)
        slot_display_rect = pygame.Rect(right_x + 48, right_y + 188, right_w - 96, 34)
        slot_plus_rect = pygame.Rect(right_x + right_w - 42, right_y + 188, 42, 34)

        hostname_rect = pygame.Rect(right_x, right_y + 280, right_w, 34)
        install_btn_rect = pygame.Rect(right_x, right_y + 355, right_w, 46)

        return {
            "win_rect": pygame.Rect(win_x, win_y, win_w, win_h),
            "close_rect": close_rect,
            "left_rect": pygame.Rect(left_x, left_y, left_w, left_h),
            "tab_rects": tab_rects,
            "list_rect": list_rect,
            "right_rect": pygame.Rect(right_x, right_y, right_w, right_h),
            "type_rects": type_rects,
            "rack_rects": rack_rects,
            "slot_minus_rect": slot_minus_rect,
            "slot_display_rect": slot_display_rect,
            "slot_plus_rect": slot_plus_rect,
            "hostname_rect": hostname_rect,
            "install_btn_rect": install_btn_rect,
        }

    def handle_input(self, event, sound_mgr, screen_w=1280, screen_h=720, mode=None):
        if self.state == MenuState.MAIN_MENU:
            # 1. Mouse Hover
            if event.type == pygame.MOUSEMOTION:
                mouse_x, mouse_y = event.pos
                hovered = False
                for i in range(len(self.menu_options)):
                    rect = self.get_main_menu_button_rect(i, screen_w, screen_h)
                    if rect.collidepoint(mouse_x, mouse_y):
                        if self.selected_button != i:
                            self.selected_button = i
                            sound_mgr.play_key()
                        hovered = True
                        break
                try:
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if hovered else pygame.SYSTEM_CURSOR_ARROW)
                except Exception:
                    pass

            # 2. Mouse Left Click
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_x, mouse_y = event.pos
                for i in range(len(self.menu_options)):
                    rect = self.get_main_menu_button_rect(i, screen_w, screen_h)
                    if rect.collidepoint(mouse_x, mouse_y):
                        self.selected_button = i
                        sound_mgr.play_key()
                        return self._select_main_option(i)

            # 3. Keyboard Controls
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.selected_button = (self.selected_button - 1) % len(self.menu_options)
                    sound_mgr.play_key()
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.selected_button = (self.selected_button + 1) % len(self.menu_options)
                    sound_mgr.play_key()
                elif event.key == pygame.K_TAB:
                    mods = pygame.key.get_mods()
                    if mods & pygame.KMOD_SHIFT:
                        self.selected_button = (self.selected_button - 1) % len(self.menu_options)
                    else:
                        self.selected_button = (self.selected_button + 1) % len(self.menu_options)
                    sound_mgr.play_key()
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    sound_mgr.play_key()
                    return self._select_main_option(self.selected_button)
                elif event.key in (pygame.K_1, pygame.K_KP1):
                    sound_mgr.play_key()
                    return "TUTORIAL"
                elif event.key in (pygame.K_2, pygame.K_KP2):
                    sound_mgr.play_key()
                    return "CHALLENGE"
                elif event.key in (pygame.K_3, pygame.K_KP3):
                    sound_mgr.play_key()
                    return "SANDBOX"
                elif event.key in (pygame.K_4, pygame.K_KP4):
                    sound_mgr.play_key()
                    self.state = MenuState.HELP_GUIDE
                elif event.key in (pygame.K_5, pygame.K_KP5, pygame.K_ESCAPE):
                    sound_mgr.play_key()
                    return "EXIT"

        elif self.state == MenuState.PAUSE:
            # Mouse click in Pause Menu
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_x, mouse_y = event.pos
                for idx in range(3):
                    rect = self.get_pause_button_rect(idx, screen_w, screen_h)
                    if rect.collidepoint(mouse_x, mouse_y):
                        sound_mgr.play_key()
                        if idx == 0:
                            self.state = MenuState.IN_GAME
                            return "RESUME"
                        elif idx == 1:
                            return "RESTART"
                        elif idx == 2:
                            self.state = MenuState.MAIN_MENU
                            return "TO_MAIN_MENU"

            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_p):
                    self.state = MenuState.IN_GAME
                    return "RESUME"
                elif event.key == pygame.K_r:
                    return "RESTART"
                elif event.key == pygame.K_m:
                    self.state = MenuState.MAIN_MENU
                    return "TO_MAIN_MENU"

        elif self.state in (MenuState.TOPOLOGY_MAP, MenuState.HELP_GUIDE):
            if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1) or \
               (event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_m, pygame.K_RETURN, pygame.K_SPACE)):
                sound_mgr.play_key()
                self.state = MenuState.IN_GAME if self.state == MenuState.TOPOLOGY_MAP else MenuState.MAIN_MENU
                return "RESUME" if self.state == MenuState.IN_GAME else None

        elif self.state == MenuState.DEVICE_MANAGER:
            rects = self._compute_dm_rects(screen_w, screen_h)

            # 1. Keyboard handling in Device Manager
            if event.type == pygame.KEYDOWN:
                if self.dm_hostname_active:
                    if event.key == pygame.K_BACKSPACE:
                        self.dm_hostname_input = self.dm_hostname_input[:-1]
                        sound_mgr.play_key()
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                        self.dm_hostname_active = False
                        sound_mgr.play_key()
                    elif event.unicode and len(self.dm_hostname_input) < 22:
                        if event.unicode.isprintable():
                            self.dm_hostname_input += event.unicode
                            sound_mgr.play_key()
                    return None
                else:
                    if event.key in (pygame.K_ESCAPE, pygame.K_n):
                        sound_mgr.play_key()
                        self.state = MenuState.IN_GAME
                        return "RESUME"
                    elif event.key in (pygame.K_UP, pygame.K_PLUS, pygame.K_EQUALS):
                        self.dm_selected_slot = min(42, self.dm_selected_slot + 1)
                        sound_mgr.play_key()
                    elif event.key in (pygame.K_DOWN, pygame.K_MINUS):
                        self.dm_selected_slot = max(1, self.dm_selected_slot - 1)
                        sound_mgr.play_key()
                    elif event.key == pygame.K_TAB:
                        types = ["switch", "router", "firewall", "server"]
                        cur_idx = types.index(self.dm_selected_type)
                        self.dm_selected_type = types[(cur_idx + 1) % len(types)]
                        sound_mgr.play_key()

            # 2. Mouse Wheel scroll
            elif event.type == pygame.MOUSEWHEEL:
                self.dm_scroll_offset = max(0, self.dm_scroll_offset - event.y * 35)

            # 3. Mouse Click handling
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos

                # Close Button
                if rects["close_rect"].collidepoint(mx, my):
                    sound_mgr.play_key()
                    self.state = MenuState.IN_GAME
                    return "RESUME"

                # Filter Tabs
                for idx, tab_r in enumerate(rects["tab_rects"]):
                    if tab_r.collidepoint(mx, my):
                        self.dm_rack_filter = idx
                        self.dm_scroll_offset = 0
                        sound_mgr.play_key()
                        return None

                # Device List [Remove] buttons
                if mode and hasattr(mode, "devices"):
                    filtered_devs = [
                        d for d in mode.devices
                        if self.dm_rack_filter == 0 or d.rack_id == self.dm_rack_filter
                    ]
                    # Sort by rack then slot descending (top to bottom of rack)
                    filtered_devs.sort(key=lambda d: (d.rack_id, -d.u_slot))

                    row_h = 58
                    row_gap = 6
                    list_r = rects["list_rect"]
                    for i, dev in enumerate(filtered_devs):
                        ry = list_r.y + 4 + i * (row_h + row_gap) - self.dm_scroll_offset
                        if list_r.y <= ry <= list_r.bottom - row_h:
                            rem_btn = pygame.Rect(list_r.right - 85, ry + 14, 75, 28)
                            if rem_btn.collidepoint(mx, my):
                                ok, msg = mode.remove_device(dev)
                                self.dm_feedback = msg
                                self.dm_feedback_color = (220, 50, 40) if ok else (180, 100, 20)
                                sound_mgr.play_key()
                                return None

                # Right Panel: Device Type
                for t_name, t_rect in rects["type_rects"].items():
                    if t_rect.collidepoint(mx, my):
                        self.dm_selected_type = t_name
                        cnt = getattr(mode, "device_counter", 10) + 1 if mode else 10
                        if t_name == "switch":
                            self.dm_hostname_input = f"Switch-0{cnt}"
                        elif t_name == "router":
                            self.dm_hostname_input = f"Router-0{cnt}"
                        elif t_name == "firewall":
                            self.dm_hostname_input = f"Firewall-0{cnt}"
                        else:
                            self.dm_hostname_input = f"Server-0{cnt}"
                        sound_mgr.play_key()
                        return None

                # Destination Rack
                for r_id, r_rect in rects["rack_rects"].items():
                    if r_rect.collidepoint(mx, my):
                        self.dm_selected_rack = r_id
                        sound_mgr.play_key()
                        return None

                # Slot Stepper
                if rects["slot_minus_rect"].collidepoint(mx, my):
                    self.dm_selected_slot = max(1, self.dm_selected_slot - 1)
                    sound_mgr.play_key()
                    return None
                elif rects["slot_plus_rect"].collidepoint(mx, my):
                    self.dm_selected_slot = min(42, self.dm_selected_slot + 1)
                    sound_mgr.play_key()
                    return None

                # Hostname input box
                if rects["hostname_rect"].collidepoint(mx, my):
                    self.dm_hostname_active = True
                    sound_mgr.play_key()
                    return None
                else:
                    self.dm_hostname_active = False

                # Install Button
                if rects["install_btn_rect"].collidepoint(mx, my):
                    if mode and hasattr(mode, "add_device"):
                        ok, msg, new_dev = mode.add_device(
                            self.dm_selected_type,
                            self.dm_selected_rack,
                            self.dm_selected_slot,
                            self.dm_hostname_input
                        )
                        if ok:
                            self.dm_feedback = msg
                            self.dm_feedback_color = (15, 140, 65)
                            # Advance slot for next equipment
                            span = 1 if self.dm_selected_type in ("switch", "firewall") else 2
                            self.dm_selected_slot = min(42, self.dm_selected_slot + span)
                            cnt = getattr(mode, "device_counter", 10) + 1
                            if self.dm_selected_type == "switch":
                                self.dm_hostname_input = f"Switch-0{cnt}"
                            elif self.dm_selected_type == "router":
                                self.dm_hostname_input = f"Router-0{cnt}"
                            elif self.dm_selected_type == "firewall":
                                self.dm_hostname_input = f"Firewall-0{cnt}"
                            else:
                                self.dm_hostname_input = f"Server-0{cnt}"
                        else:
                            self.dm_feedback = msg
                            self.dm_feedback_color = (220, 50, 40)
                            sound_mgr.play_key()
                        return None

        return None

    def _select_main_option(self, idx):
        if idx == 0:
            return "TUTORIAL"
        elif idx == 1:
            return "CHALLENGE"
        elif idx == 2:
            return "SANDBOX"
        elif idx == 3:
            self.state = MenuState.HELP_GUIDE
            return None
        elif idx == 4:
            return "EXIT"
        return None

    def render(self, surface, screen_w, screen_h, devices=None, cables=None, mode=None):
        if self.state == MenuState.MAIN_MENU:
            self._render_main_menu(surface, screen_w, screen_h)
        elif self.state == MenuState.PAUSE:
            self._render_pause_menu(surface, screen_w, screen_h)
        elif self.state == MenuState.TOPOLOGY_MAP:
            self._render_topology_map(surface, screen_w, screen_h, devices, cables)
        elif self.state == MenuState.HELP_GUIDE:
            self._render_help_guide(surface, screen_w, screen_h)
        elif self.state == MenuState.DEVICE_MANAGER:
            self._render_device_manager(surface, screen_w, screen_h, mode)

    def _render_main_menu(self, surface, w, h):
        # Modern Enterprise Clean Light Background
        surface.fill((244, 247, 252))

        # Subtle Clean Blueprint Grid
        grid_color = (226, 233, 244)
        for x in range(0, w, 40):
            pygame.draw.line(surface, grid_color, (x, 0), (x, h), 1)
        for y in range(0, h, 40):
            pygame.draw.line(surface, grid_color, (0, y), (w, y), 1)

        # Title Card
        cx = w // 2
        logo_surf = self.font_logo.render("NETENGINEER 3D", True, (16, 42, 82))
        sub_surf = self.font_sub.render("Enterprise Datacenter & Cisco IOS Network Simulator", True, (0, 102, 204))
        surface.blit(logo_surf, (cx - logo_surf.get_width() // 2, 75))
        surface.blit(sub_surf, (cx - sub_surf.get_width() // 2, 130))

        # Menu Buttons
        for i, (title, desc) in enumerate(self.menu_options):
            btn_rect = self.get_main_menu_button_rect(i, w, h)
            is_hover = (i == self.selected_button)

            bg_col = (235, 245, 255) if is_hover else (255, 255, 255)
            border_col = (0, 115, 230) if is_hover else (205, 218, 235)

            # Drop shadow
            shadow_rect = pygame.Rect(btn_rect.x + 2, btn_rect.y + 3, btn_rect.w, btn_rect.h)
            pygame.draw.rect(surface, (215, 225, 238), shadow_rect, border_radius=8)

            pygame.draw.rect(surface, bg_col, btn_rect, border_radius=8)
            pygame.draw.rect(surface, border_col, btn_rect, width=2 if is_hover else 1, border_radius=8)

            t_color = (0, 85, 200) if is_hover else (24, 36, 54)
            d_color = (0, 105, 215) if is_hover else (90, 105, 125)

            t_surf = self.font_btn.render(f"[{i+1}] {title}", True, t_color)
            d_surf = self.font_body.render(desc, True, d_color)

            surface.blit(t_surf, (btn_rect.x + 20, btn_rect.y + 8))
            surface.blit(d_surf, (btn_rect.x + 20, btn_rect.y + 32))

        # Footer
        footer = self.font_body.render("Click buttons with MOUSE, or press [1]-[5] / [Up/Down] + [ENTER]", True, (90, 115, 145))
        surface.blit(footer, (cx - footer.get_width() // 2, h - 45))

    def _render_pause_menu(self, surface, w, h):
        # Semi-transparent light frosted overlay
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((244, 247, 252, 220))
        surface.blit(overlay, (0, 0))

        cx, cy = w // 2, h // 2
        card_w, card_h = 420, 280
        rx, ry = cx - card_w // 2, cy - card_h // 2
        card_rect = pygame.Rect(rx, ry, card_w, card_h)

        # Dialog Box
        pygame.draw.rect(surface, (210, 222, 238), (rx + 3, ry + 4, card_w, card_h), border_radius=10)
        pygame.draw.rect(surface, (255, 255, 255), card_rect, border_radius=10)
        pygame.draw.rect(surface, (0, 115, 230), card_rect, width=2, border_radius=10)

        # Title
        p_surf = self.font_title.render("SIMULATOR PAUSED", True, (15, 45, 90))
        surface.blit(p_surf, (cx - p_surf.get_width() // 2, ry + 25))

        # Buttons
        options = [
            ("RESUME SIMULATION", "[ESC] / [P]"),
            ("RESTART SCENARIO", "[R]"),
            ("RETURN TO MAIN MENU", "[M]")
        ]
        for i, (title, hotkey) in enumerate(options):
            b_rect = self.get_pause_button_rect(i, w, h)
            pygame.draw.rect(surface, (242, 247, 255), b_rect, border_radius=6)
            pygame.draw.rect(surface, (0, 115, 230), b_rect, width=1, border_radius=6)

            t_s = self.font_btn.render(title, True, (0, 85, 200))
            h_s = self.font_mono.render(hotkey, True, (80, 105, 135))
            surface.blit(t_s, (b_rect.x + 16, b_rect.y + 10))
            surface.blit(h_s, (b_rect.right - h_s.get_width() - 16, b_rect.y + 12))

    def _render_topology_map(self, surface, w, h, devices, cables):
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((246, 249, 254, 248))
        surface.blit(overlay, (0, 0))

        # Blueprint grid
        grid_color = (230, 237, 248)
        for x in range(0, w, 32):
            pygame.draw.line(surface, grid_color, (x, 0), (x, h), 1)
        for y in range(0, h, 32):
            pygame.draw.line(surface, grid_color, (0, y), (w, y), 1)

        # Title
        cx = w // 2
        title = self.font_logo.render("2D LOGICAL NETWORK TOPOLOGY", True, (16, 42, 82))
        sub = self.font_sub.render("Real-Time Device Interconnects & Link Operational Status", True, (0, 102, 204))
        surface.blit(title, (cx - title.get_width() // 2, 25))
        surface.blit(sub, (cx - sub.get_width() // 2, 70))

        if not devices:
            return

        # Tiered Layout: Routers (Top), Switches (Middle), Hosts/Servers (Bottom)
        node_positions = {}
        cy = h // 2

        routers = [d for d in devices if isinstance(d, Router)]
        firewalls = [d for d in devices if isinstance(d, Firewall)]
        switches = [d for d in devices if isinstance(d, Switch)]
        hosts = [d for d in devices if isinstance(d, Host)]

        def place_row(dev_list, y_pos):
            count = len(dev_list)
            if count == 0:
                return
            span = min(w - 200, count * 220)
            start_x = cx - span // 2
            step = span // max(1, count - 1) if count > 1 else 0
            for idx, dev in enumerate(dev_list):
                px = cx if count == 1 else (start_x + idx * step)
                node_positions[dev.id] = (px, y_pos)

        place_row(routers + firewalls, 140)
        place_row(switches, cy)
        place_row(hosts, h - 140)

        # Draw Connecting Cable Links
        if cables:
            for cable in cables:
                if not cable.port_a or not cable.port_b:
                    continue
                dev_a = cable.port_a.device
                dev_b = cable.port_b.device
                pos_a = node_positions.get(dev_a.id)
                pos_b = node_positions.get(dev_b.id)
                if pos_a and pos_b:
                    link_color = (15, 165, 75) if (cable.port_a.is_link_up and cable.port_b.is_link_up) else (225, 140, 20)
                    if cable.is_damaged:
                        link_color = (220, 50, 50)
                    pygame.draw.line(surface, link_color, pos_a, pos_b, 3)

                    # Port label tags at midpoints
                    mid_x = (pos_a[0] + pos_b[0]) // 2
                    mid_y = (pos_a[1] + pos_b[1]) // 2
                    tag = f"{cable.port_a.name} <-> {cable.port_b.name}"
                    t_s = self.font_mono.render(tag, True, (25, 40, 65))
                    pygame.draw.rect(surface, (255, 255, 255), (mid_x - t_s.get_width()//2 - 4, mid_y - 10, t_s.get_width() + 8, 20), border_radius=4)
                    pygame.draw.rect(surface, (200, 215, 235), (mid_x - t_s.get_width()//2 - 4, mid_y - 10, t_s.get_width() + 8, 20), width=1, border_radius=4)
                    surface.blit(t_s, (mid_x - t_s.get_width()//2, mid_y - 8))

        # Draw Device Nodes
        for dev in devices:
            pos = node_positions.get(dev.id)
            if not pos:
                continue
            dx, dy = pos
            nw, nh = 148, 68
            rect = pygame.Rect(dx - nw//2, dy - nh//2, nw, nh)

            bg_color = (255, 255, 255)
            border_color = (0, 115, 230)
            if isinstance(dev, Router):
                border_color = (0, 102, 204)
            elif isinstance(dev, Firewall):
                border_color = (200, 30, 45)
            elif isinstance(dev, Switch):
                border_color = (16, 160, 80)
            elif isinstance(dev, Host):
                border_color = (220, 130, 20)

            # Card with shadow
            shadow_rect = pygame.Rect(rect.x + 2, rect.y + 2, rect.w, rect.h)
            pygame.draw.rect(surface, (210, 222, 238), shadow_rect, border_radius=8)
            pygame.draw.rect(surface, bg_color, rect, border_radius=8)
            pygame.draw.rect(surface, border_color, rect, width=2, border_radius=8)

            d_name = self.font_btn.render(dev.hostname, True, (20, 35, 55))
            d_type = self.font_body.render(dev.device_type.upper(), True, border_color)
            surface.blit(d_name, (dx - d_name.get_width()//2, dy - 22))
            surface.blit(d_type, (dx - d_type.get_width()//2, dy + 4))

        close_lbl = self.font_btn.render("Press [M] or [ESC] to return to Datacenter 3D view", True, (80, 105, 135))
        surface.blit(close_lbl, (cx - close_lbl.get_width() // 2, h - 40))

    def _render_help_guide(self, surface, w, h):
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((244, 247, 252, 250))
        surface.blit(overlay, (0, 0))

        cx = w // 2
        title = self.font_logo.render("CONTROLS & CISCO IOS CHEATSHEET", True, (16, 42, 82))
        surface.blit(title, (cx - title.get_width() // 2, 35))

        box_w = min(1000, w - 80)
        box_rect = pygame.Rect(cx - box_w // 2, 95, box_w, h - 170)
        pygame.draw.rect(surface, (255, 255, 255), box_rect, border_radius=10)
        pygame.draw.rect(surface, (200, 215, 235), box_rect, width=1, border_radius=10)

        # Left Column: Simulator Controls
        col1_x = cx - box_w // 2 + 30
        curr_y = 115
        h1 = self.font_btn.render("SIMULATOR CONTROLS", True, (0, 102, 204))
        surface.blit(h1, (col1_x, curr_y))
        curr_y += 30

        controls = [
            ("W, A, S, D", "Walk in Datacenter room (First-Person)"),
            ("Mouse Look", "Rotate camera / Aim crosshair at racks & ports"),
            ("Left Shift", "Sprint / Walk faster"),
            ("[E] Key", "Open Cisco IOS Console Terminal for targeted device"),
            ("[F] Key", "Pick up cable / Connect cable to selected port"),
            ("[X] Key", "Cancel cable currently in hand"),
            ("[N] Key", "Open Rack Device Manager (Add/Remove devices in Sandbox)"),
            ("[Del] Key", "Quick Delete aimed device in Sandbox mode"),
            ("[M] Key", "Toggle 2D Logical Network Topology diagram"),
            ("[ESC] Key", "Detach CLI terminal / Open Pause Menu"),
            ("[F11]", "Toggle Fullscreen mode")
        ]
        for key, desc in controls:
            k_s = self.font_mono.render(f"{key:<14}", True, (0, 130, 70))
            d_s = self.font_body.render(desc, True, (40, 55, 75))
            surface.blit(k_s, (col1_x, curr_y))
            surface.blit(d_s, (col1_x + 130, curr_y))
            curr_y += 24

        # Right Column: Cisco CLI Commands
        col2_x = cx + 20
        curr_y = 115
        h2 = self.font_btn.render("CISCO IOS COMMAND REFERENCE", True, (0, 102, 204))
        surface.blit(h2, (col2_x, curr_y))
        curr_y += 30

        cisco_cmds = [
            ("enable", "Enter Privileged EXEC mode (Switch#)"),
            ("configure terminal", "Enter Global Configuration mode"),
            ("interface g0/1", "Select interface for configuration"),
            ("ip address <ip> <mask>", "Assign IPv4 address to interface"),
            ("no shutdown", "Bring interface administratively UP"),
            ("vlan 10 -> name HR", "Create and name a Layer 2 VLAN"),
            ("switchport mode access", "Set port to access mode"),
            ("switchport access vlan 10", "Assign port to VLAN 10"),
            ("ip route <net> <mask> <gw>", "Configure static route on Router"),
            ("show ip interface brief", "Display summary of all interface states"),
            ("show vlan brief", "Display active VLAN memberships"),
            ("ping <target_ip>", "Send 5 ICMP Echo Requests to verify reachability")
        ]
        for cmd, desc in cisco_cmds:
            c_s = self.font_mono.render(f"{cmd:<28}", True, (0, 102, 204))
            d_s = self.font_body.render(desc, True, (40, 55, 75))
            surface.blit(c_s, (col2_x, curr_y))
            surface.blit(d_s, (col2_x + 230, curr_y))
            curr_y += 24

        close_hint = self.font_btn.render("Click anywhere or press [ESC] to Return to Menu", True, (90, 115, 145))
        surface.blit(close_hint, (cx - close_hint.get_width() // 2, h - 55))

    def _render_device_manager(self, surface, w, h, mode):
        """Renders the comprehensive Rack Device Manager modal overlay for Sandbox Mode."""
        # Frosted Backdrop Overlay
        backdrop = pygame.Surface((w, h), pygame.SRCALPHA)
        backdrop.fill((20, 32, 50, 190))
        surface.blit(backdrop, (0, 0))

        rects = self._compute_dm_rects(w, h)
        win_r = rects["win_rect"]

        # Drop shadow & Main Card Window
        shadow_r = pygame.Rect(win_r.x + 3, win_r.y + 4, win_r.w, win_r.h)
        pygame.draw.rect(surface, (10, 18, 28, 90), shadow_r, border_radius=12)
        pygame.draw.rect(surface, (250, 252, 255), win_r, border_radius=12)
        pygame.draw.rect(surface, (0, 115, 230), win_r, width=2, border_radius=12)

        # Top Title Bar
        header_r = pygame.Rect(win_r.x, win_r.y, win_r.w, 48)
        pygame.draw.rect(surface, (235, 243, 253), header_r, border_top_left_radius=12, border_top_right_radius=12)
        pygame.draw.line(surface, (210, 225, 245), (win_r.x, win_r.y + 48), (win_r.right, win_r.y + 48), 1)

        t_title = self.font_title.render("RACK HARDWARE MANAGER - SANDBOX PLAYGROUND", True, (15, 45, 90))
        surface.blit(t_title, (win_r.x + 20, win_r.y + 12))

        # Close [X] Button
        cls_r = rects["close_rect"]
        pygame.draw.rect(surface, (245, 248, 252), cls_r, border_radius=6)
        pygame.draw.rect(surface, (190, 205, 225), cls_r, width=1, border_radius=6)
        x_lbl = self.font_btn.render("X", True, (70, 90, 120))
        surface.blit(x_lbl, (cls_r.x + (cls_r.w - x_lbl.get_width())//2, cls_r.y + 5))

        # =========================================================================
        # LEFT PANEL: INSTALLED HARDWARE INVENTORY
        # =========================================================================
        left_r = rects["left_rect"]
        pygame.draw.rect(surface, (255, 255, 255), left_r, border_radius=8)
        pygame.draw.rect(surface, (220, 230, 245), left_r, width=1, border_radius=8)

        # Section Header
        dev_count = len(mode.devices) if mode and hasattr(mode, "devices") else 0
        h_left = self.font_bold.render(f"INSTALLED EQUIPMENT ({dev_count} DEVICES)", True, (20, 45, 80))
        surface.blit(h_left, (left_r.x + 12, left_r.y + 8))

        # Filter Tabs
        tab_names = ["All Racks", "Rack 1 (A01)", "Rack 2 (A02)", "Rack 3 (A03)"]
        for idx, tab_r in enumerate(rects["tab_rects"]):
            is_active = (self.dm_rack_filter == idx)
            bg = (0, 115, 230) if is_active else (244, 248, 253)
            border = (0, 115, 230) if is_active else (210, 222, 238)
            tc = (255, 255, 255) if is_active else (50, 70, 95)

            pygame.draw.rect(surface, bg, tab_r, border_radius=5)
            pygame.draw.rect(surface, border, tab_r, width=1, border_radius=5)

            lbl = self.font_small.render(tab_names[idx], True, tc)
            surface.blit(lbl, (tab_r.x + (tab_r.w - lbl.get_width())//2, tab_r.y + 6))

        # Scrollable Device Cards
        list_r = rects["list_rect"]
        pygame.draw.rect(surface, (249, 251, 254), list_r, border_radius=6)

        # Gather and filter devices
        dev_list = []
        if mode and hasattr(mode, "devices"):
            dev_list = [
                d for d in mode.devices
                if self.dm_rack_filter == 0 or d.rack_id == self.dm_rack_filter
            ]
            dev_list.sort(key=lambda d: (d.rack_id, -d.u_slot))

        # Set up clipping for scrolling list
        prev_clip = surface.get_clip()
        surface.set_clip(list_r)

        row_h = 58
        row_gap = 6
        for i, dev in enumerate(dev_list):
            ry = list_r.y + 4 + i * (row_h + row_gap) - self.dm_scroll_offset
            row_r = pygame.Rect(list_r.x + 4, ry, list_r.w - 8, row_h)

            # Skip drawing if fully out of view
            if ry + row_h < list_r.y or ry > list_r.bottom:
                continue

            pygame.draw.rect(surface, (255, 255, 255), row_r, border_radius=6)
            pygame.draw.rect(surface, (222, 232, 245), row_r, width=1, border_radius=6)

            # Badge Color by Type
            badge_bg = (235, 250, 252)
            badge_tc = (15, 125, 140)
            badge_text = "SWITCH"
            if dev.device_type == "router":
                badge_bg = (235, 242, 255)
                badge_tc = (20, 80, 180)
                badge_text = "ROUTER"
            elif dev.device_type == "firewall":
                badge_bg = (255, 236, 238)
                badge_tc = (195, 30, 45)
                badge_text = "FIREWALL"
            elif dev.device_type == "server":
                badge_bg = (242, 244, 248)
                badge_tc = (65, 75, 95)
                badge_text = "SERVER"

            badge_r = pygame.Rect(row_r.x + 10, row_r.y + 8, 62, 20)
            pygame.draw.rect(surface, badge_bg, badge_r, border_radius=4)
            b_s = self.font_small.render(badge_text, True, badge_tc)
            surface.blit(b_s, (badge_r.x + (badge_r.w - b_s.get_width())//2, badge_r.y + 2))

            # Hostname
            h_s = self.font_bold.render(dev.hostname, True, (20, 35, 55))
            surface.blit(h_s, (row_r.x + 80, row_r.y + 8))

            # Location & Port info
            span = 1 if dev.device_type in ("switch", "firewall") else 2
            loc_str = f"RACK-0{dev.rack_id} (Slot {dev.u_slot}U" + (f"-{dev.u_slot+1}U" if span > 1 else "U") + ")"
            active_links = sum(1 for p in dev.ports.values() if p.cable)
            port_str = f"Ports: {len(dev.ports)} ({active_links} cabled)"
            sub_s = self.font_small.render(f"{loc_str}  |  {port_str}", True, (90, 105, 125))
            surface.blit(sub_s, (row_r.x + 12, row_r.y + 32))

            # [Remove] Button
            rem_btn = pygame.Rect(row_r.right - 85, row_r.y + 14, 75, 28)
            pygame.draw.rect(surface, (255, 242, 242), rem_btn, border_radius=5)
            pygame.draw.rect(surface, (235, 75, 75), rem_btn, width=1, border_radius=5)
            rem_lbl = self.font_small.render("Remove", True, (200, 30, 30))
            surface.blit(rem_lbl, (rem_btn.x + (rem_btn.w - rem_lbl.get_width())//2, rem_btn.y + 6))

        if len(dev_list) == 0:
            no_dev = self.font_body.render("No equipment currently installed in this selection.", True, (120, 135, 155))
            surface.blit(no_dev, (list_r.x + 20, list_r.y + 30))

        surface.set_clip(prev_clip)

        # =========================================================================
        # RIGHT PANEL: PROVISION / INSTALL NEW HARDWARE
        # =========================================================================
        right_r = rects["right_rect"]
        pygame.draw.rect(surface, (255, 255, 255), right_r, border_radius=8)
        pygame.draw.rect(surface, (220, 230, 245), right_r, width=1, border_radius=8)

        # Form Header
        h_right = self.font_bold.render("INSTALL NEW EQUIPMENT", True, (20, 45, 80))
        surface.blit(h_right, (right_r.x + 14, right_r.y + 10))

        # 1. Device Type
        lbl_type = self.font_small.render("1. SELECT HARDWARE TYPE:", True, (70, 90, 120))
        surface.blit(lbl_type, (right_r.x + 14, right_r.y + 34))

        type_labels = {
            "switch": "Switch (1U)",
            "router": "Router (2U)",
            "firewall": "Firewall (1U)",
            "server": "Server (2U)"
        }
        for t_name, t_rect in rects["type_rects"].items():
            is_active = (self.dm_selected_type == t_name)
            bg = (235, 245, 255) if is_active else (250, 252, 255)
            border = (0, 115, 230) if is_active else (215, 225, 240)
            tc = (0, 95, 210) if is_active else (60, 75, 95)
            pygame.draw.rect(surface, bg, t_rect, border_radius=5)
            pygame.draw.rect(surface, border, t_rect, width=2 if is_active else 1, border_radius=5)
            lbl = self.font_small.render(type_labels[t_name], True, tc)
            surface.blit(lbl, (t_rect.x + (t_rect.w - lbl.get_width())//2, t_rect.y + 9))

        # 2. Target Rack
        lbl_rack = self.font_small.render("2. DESTINATION 42U RACK:", True, (70, 90, 120))
        surface.blit(lbl_rack, (right_r.x + 14, right_r.y + 102))

        rack_labels = {1: "Rack 1 (A01)", 2: "Rack 2 (A02)", 3: "Rack 3 (A03)"}
        for r_id, r_rect in rects["rack_rects"].items():
            is_active = (self.dm_selected_rack == r_id)
            bg = (235, 245, 255) if is_active else (250, 252, 255)
            border = (0, 115, 230) if is_active else (215, 225, 240)
            tc = (0, 95, 210) if is_active else (60, 75, 95)
            pygame.draw.rect(surface, bg, r_rect, border_radius=5)
            pygame.draw.rect(surface, border, r_rect, width=2 if is_active else 1, border_radius=5)
            lbl = self.font_small.render(rack_labels[r_id], True, tc)
            surface.blit(lbl, (r_rect.x + (r_rect.w - lbl.get_width())//2, r_rect.y + 8))

        # 3. U-Slot Stepper
        lbl_slot = self.font_small.render("3. RACK MOUNTING SLOT (1U - 42U):", True, (70, 90, 120))
        surface.blit(lbl_slot, (right_r.x + 14, right_r.y + 168))

        # [-] button
        sm_r = rects["slot_minus_rect"]
        pygame.draw.rect(surface, (244, 248, 253), sm_r, border_radius=5)
        pygame.draw.rect(surface, (210, 222, 238), sm_r, width=1, border_radius=5)
        m_s = self.font_btn.render("-", True, (0, 102, 204))
        surface.blit(m_s, (sm_r.x + (sm_r.w - m_s.get_width())//2, sm_r.y + 5))

        # Display box
        sd_r = rects["slot_display_rect"]
        pygame.draw.rect(surface, (255, 255, 255), sd_r, border_radius=5)
        pygame.draw.rect(surface, (200, 215, 235), sd_r, width=1, border_radius=5)
        needed_span = 1 if self.dm_selected_type in ("switch", "firewall") else 2
        slot_text = f"Unit Slot: {self.dm_selected_slot}U" + (f" - {self.dm_selected_slot+1}U" if needed_span > 1 else "")
        sd_s = self.font_bold.render(slot_text, True, (20, 35, 55))
        surface.blit(sd_s, (sd_r.x + (sd_r.w - sd_s.get_width())//2, sd_r.y + 8))

        # [+] button
        sp_r = rects["slot_plus_rect"]
        pygame.draw.rect(surface, (244, 248, 253), sp_r, border_radius=5)
        pygame.draw.rect(surface, (210, 222, 238), sp_r, width=1, border_radius=5)
        p_s = self.font_btn.render("+", True, (0, 102, 204))
        surface.blit(p_s, (sp_r.x + (sp_r.w - p_s.get_width())//2, sp_r.y + 5))

        # Slot Availability Check Badge
        is_occ, occ_dev = False, None
        if mode and hasattr(mode, "is_slot_occupied"):
            is_occ, occ_dev = mode.is_slot_occupied(self.dm_selected_rack, self.dm_selected_slot, needed_span)

        status_box_r = pygame.Rect(right_r.x, right_r.y + 228, right_r.w, 24)
        if is_occ:
            pygame.draw.rect(surface, (255, 244, 230), status_box_r, border_radius=4)
            st_lbl = self.font_small.render(f"[!] Occupied by {occ_dev.hostname}", True, (200, 95, 10))
        else:
            pygame.draw.rect(surface, (235, 250, 240), status_box_r, border_radius=4)
            st_lbl = self.font_small.render(f"[OK] Slot {self.dm_selected_slot}U is available for install", True, (15, 140, 60))
        surface.blit(st_lbl, (status_box_r.x + 10, status_box_r.y + 4))

        # 4. Hostname Input Field
        lbl_host = self.font_small.render("4. DEVICE HOSTNAME:", True, (70, 90, 120))
        surface.blit(lbl_host, (right_r.x + 14, right_r.y + 258))

        h_rect = rects["hostname_rect"]
        h_bg = (255, 255, 255) if self.dm_hostname_active else (250, 252, 255)
        h_border = (0, 115, 230) if self.dm_hostname_active else (210, 222, 238)
        pygame.draw.rect(surface, h_bg, h_rect, border_radius=5)
        pygame.draw.rect(surface, h_border, h_rect, width=2 if self.dm_hostname_active else 1, border_radius=5)

        cursor_str = "|" if (self.dm_hostname_active and (pygame.time.get_ticks() // 400) % 2 == 0) else ""
        h_val = self.font_mono.render(self.dm_hostname_input + cursor_str, True, (20, 35, 55))
        surface.blit(h_val, (h_rect.x + 10, h_rect.y + 8))

        # Helper hint
        hint_s = self.font_small.render("Click box to edit name, [ENTER] when done", True, (130, 145, 165))
        surface.blit(hint_s, (h_rect.x, h_rect.bottom + 4))

        # 5. Big Install Button
        inst_r = rects["install_btn_rect"]
        can_install = not is_occ
        inst_bg = (0, 115, 230) if can_install else (220, 228, 238)
        inst_tc = (255, 255, 255) if can_install else (140, 155, 175)

        # Shadow
        if can_install:
            pygame.draw.rect(surface, (200, 215, 235), (inst_r.x + 2, inst_r.y + 2, inst_r.w, inst_r.h), border_radius=7)

        pygame.draw.rect(surface, inst_bg, inst_r, border_radius=7)
        btn_text = "+ INSTALL TO RACK" if can_install else "SLOT OCCUPIED"
        b_lbl = self.font_btn.render(btn_text, True, inst_tc)
        surface.blit(b_lbl, (inst_r.x + (inst_r.w - b_lbl.get_width())//2, inst_r.y + 14))

        # Bottom Feedback Toast Message
        if self.dm_feedback:
            fb_s = self.font_small.render(self.dm_feedback, True, self.dm_feedback_color)
            surface.blit(fb_s, (right_r.x, inst_r.bottom + 12))
