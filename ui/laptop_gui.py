"""
ui/laptop_gui.py - Interactive Laptop Desktop GUI for Windows 11 & Ubuntu 22.04 LTS
Provides realistic Desktop environments, Web Browser, Network Settings, and PuTTY/Minicom Serial Console.
All clickable elements use unified, single-source-of-truth pygame.Rect layout definitions.
"""

import pygame
import time
import math
from engine.audio import SoundManager
from network.packet_engine import PacketEngine
from cli.command_executor import CommandExecutor

class LaptopGUI:
    def __init__(self, device, screen_w=1280, screen_h=720):
        self.device = device  # Host (laptop)
        self.is_windows = getattr(device, "os_type", "windows").lower() == "windows"
        self.sound = SoundManager.get_instance()
        self.packet_engine = PacketEngine.get_instance()

        self.width = min(1040, screen_w - 80)
        self.height = min(660, screen_h - 60)
        self.surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.is_open = False
        self._wallpaper_surface = None

        # Fonts
        if not pygame.font.get_init():
            pygame.font.init()
        self.font_sm = pygame.font.SysFont("Segoe UI", 12) or pygame.font.Font(None, 14)
        self.font_md = pygame.font.SysFont("Segoe UI", 14, bold=True) or pygame.font.Font(None, 16)
        self.font_lg = pygame.font.SysFont("Segoe UI", 18, bold=True) or pygame.font.Font(None, 20)
        self.font_mono = pygame.font.SysFont("Consolas", 13) or pygame.font.Font(None, 15)

        # Mouse hover tracking
        self.hover_pos = (-100, -100)

        # Active App: None (Desktop), "browser", "network_settings", "putty", "terminal"
        self.active_app = None

        # Network Settings Form State
        p = self.device.eth0
        self.net_ip = p.ip_address if (p and p.ip_address) else "192.168.1.99"
        self.net_mask = p.subnet_mask if (p and p.subnet_mask) else "255.255.255.0"
        self.net_gw = self.device.default_gateway or "192.168.1.1"
        self.net_dns = getattr(self.device, "dns_server", "8.8.8.8")
        self.active_field = None  # "ip", "mask", "gw", "dns"
        self.settings_banner = None
        self.banner_time = 0.0

        # Web Browser State
        self.browser_url = "http://192.168.1.1"
        self.browser_input = "http://192.168.1.1"
        self.browser_url_active = False
        self.browser_page_status = "OK"  # "OK", "ERROR"

        # PuTTY / Serial Console State
        self.putty_connected = False
        self.putty_target_device = None
        self.putty_terminal_executor = None
        self.putty_history = []
        self.putty_input = ""
        self.putty_error_msg = None

        # Local Terminal State (CMD / bash)
        self.local_term_history = [
            "Microsoft Windows [Version 10.0.22631.3007]" if self.is_windows else "Ubuntu 22.04.4 LTS (Jammy Jellyfish)",
            "(c) Microsoft Corporation. All rights reserved." if self.is_windows else "Welcome to Ubuntu 22.04 LTS (GNU/Linux 6.5.0 generic)",
            "Type 'ping <ip>', 'ipconfig' (or 'ifconfig'), 'traceroute <ip>', 'help'.",
            ""
        ]
        self.local_term_input = ""
        self.local_term_executor = CommandExecutor(self.device)

        # Audio rate limiter for continuous typing/backspacing
        self._last_key_sound_time = 0.0

        # Pre-compute layout hitboxes
        self.layout = self._compute_layout()

    def _compute_layout(self):
        """Computes exact coordinate rectangles for every UI element (Single Source of Truth)."""
        w, h = self.width, self.height
        dx, dy = 12, 26
        dw, dh = w - 24, h - 38

        layout = {
            "dx": dx, "dy": dy, "dw": dw, "dh": dh,
            "detach_btn": pygame.Rect(w - 152, 4, 142, 20),
        }

        if self.is_windows:
            # Desktop Icons (left column)
            col_x = dx + 24
            layout["desktop_icons"] = {
                "browser": pygame.Rect(col_x, dy + 20, 68, 68),
                "network_settings": pygame.Rect(col_x, dy + 104, 68, 68),
                "putty": pygame.Rect(col_x, dy + 188, 68, 68),
                "terminal": pygame.Rect(col_x, dy + 272, 68, 68),
            }
            # Windows 11 Centered Taskbar at bottom
            tb_h = 44
            tb_y = dy + dh - tb_h
            layout["taskbar_rect"] = pygame.Rect(dx, tb_y, dw, tb_h)
            tcx = dx + dw // 2
            layout["taskbar_icons"] = {
                "start": pygame.Rect(tcx - 110, tb_y + 4, 34, 36),
                "search": pygame.Rect(tcx - 70, tb_y + 4, 34, 36),
                "browser": pygame.Rect(tcx - 30, tb_y + 4, 34, 36),
                "putty": pygame.Rect(tcx + 10, tb_y + 4, 34, 36),
                "terminal": pygame.Rect(tcx + 50, tb_y + 4, 34, 36),
                "network_settings": pygame.Rect(tcx + 90, tb_y + 4, 34, 36),
            }
            # App Window Geometry (keeps taskbar visible)
            wx = dx + 36
            wy = dy + 20
            ww = dw - 72
            wh = dh - 20 - tb_h - 10
            layout["window_rect"] = pygame.Rect(wx, wy, ww, wh)
        else:
            # Ubuntu Desktop
            tb_h = 28
            layout["topbar_rect"] = pygame.Rect(dx, dy, dw, tb_h)
            layout["activities_btn"] = pygame.Rect(dx + 6, dy + 2, 70, 24)

            # Left Dock Launcher
            dock_w = 56
            dock_y = dy + tb_h
            dock_h = dh - tb_h
            layout["dock_rect"] = pygame.Rect(dx, dock_y, dock_w, dock_h)
            layout["dock_icons"] = {
                "browser": pygame.Rect(dx + 8, dock_y + 12, 40, 40),
                "putty": pygame.Rect(dx + 8, dock_y + 64, 40, 40),
                "terminal": pygame.Rect(dx + 8, dock_y + 116, 40, 40),
                "network_settings": pygame.Rect(dx + 8, dock_y + 168, 40, 40),
            }
            # Desktop Icons (right of dock)
            col_x = dx + dock_w + 20
            layout["desktop_icons"] = {
                "browser": pygame.Rect(col_x, dy + tb_h + 20, 68, 68),
                "network_settings": pygame.Rect(col_x, dy + tb_h + 104, 68, 68),
                "putty": pygame.Rect(col_x, dy + tb_h + 188, 68, 68),
                "terminal": pygame.Rect(col_x, dy + tb_h + 272, 68, 68),
            }
            # App Window Geometry (keeps dock and topbar visible)
            wx = dx + dock_w + 16
            wy = dy + tb_h + 12
            ww = dw - dock_w - 32
            wh = dh - tb_h - 24
            layout["window_rect"] = pygame.Rect(wx, wy, ww, wh)

        # Common Window Close Button [X] (top-right of active window)
        win_r = layout["window_rect"]
        layout["window_close_btn"] = pygame.Rect(win_r.x + win_r.width - 32, win_r.y + 4, 24, 24)

        # Web Browser Navigation & Bookmarks
        b_nav_y = win_r.y + 34
        b_bm_y = b_nav_y + 36
        layout["browser"] = {
            "back_btn": pygame.Rect(win_r.x + 8, b_nav_y + 4, 28, 28),
            "forward_btn": pygame.Rect(win_r.x + 40, b_nav_y + 4, 28, 28),
            "refresh_btn": pygame.Rect(win_r.x + 72, b_nav_y + 4, 28, 28),
            "url_bar": pygame.Rect(win_r.x + 108, b_nav_y + 4, win_r.width - 180, 28),
            "go_btn": pygame.Rect(win_r.x + win_r.width - 64, b_nav_y + 4, 54, 28),
            "bm_router": pygame.Rect(win_r.x + 8, b_bm_y + 3, 175, 22),
            "bm_server": pygame.Rect(win_r.x + 188, b_bm_y + 3, 175, 22),
            "bm_asa": pygame.Rect(win_r.x + 368, b_bm_y + 3, 170, 22),
            "bm_google": pygame.Rect(win_r.x + 543, b_bm_y + 3, 135, 22),
            "content_rect": pygame.Rect(win_r.x, b_bm_y + 28, win_r.width, win_r.height - (b_bm_y + 28 - win_r.y)),
        }

        # Network Settings Form
        n_form_y = win_r.y + 115
        layout["network"] = {
            "field_ip": pygame.Rect(win_r.x + 160, n_form_y, 240, 30),
            "field_mask": pygame.Rect(win_r.x + 160, n_form_y + 42, 240, 30),
            "field_gw": pygame.Rect(win_r.x + 160, n_form_y + 84, 240, 30),
            "field_dns": pygame.Rect(win_r.x + 160, n_form_y + 126, 240, 30),
            "btn_apply": pygame.Rect(win_r.x + 160, n_form_y + 172, 160, 36),
        }

        # PuTTY Serial Console
        layout["putty"] = {
            "retry_btn": pygame.Rect(win_r.x + 120, win_r.y + 230, 140, 34),
            "term_rect": pygame.Rect(win_r.x + 6, win_r.y + 34, win_r.width - 12, win_r.height - 40),
        }

        # Terminal (CMD / bash)
        layout["terminal"] = {
            "term_rect": pygame.Rect(win_r.x + 6, win_r.y + 34, win_r.width - 12, win_r.height - 40),
        }

        return layout

    def _play_key_sound(self):
        """Plays keyboard sound with rate-limiting to prevent audio distortion during auto-repeat."""
        now = time.time()
        if now - self._last_key_sound_time >= 0.05:
            self.sound.play_key()
            self._last_key_sound_time = now

    def open(self):
        self.is_open = True
        self.active_app = None
        self.settings_banner = None
        self._sync_network_fields()
        # Enable continuous key repeat (delay=280ms, interval=28ms) for snappy text editing & backspace
        pygame.key.set_repeat(280, 28)

    def close(self):
        self.is_open = False
        # Reset key repeat for 3D navigation
        pygame.key.set_repeat(0)

    def _sync_network_fields(self):
        p = self.device.eth0
        if p and p.ip_address:
            self.net_ip = p.ip_address
            self.net_mask = p.subnet_mask or "255.255.255.0"
        self.net_gw = self.device.default_gateway or "192.168.1.1"
        self.net_dns = getattr(self.device, "dns_server", "8.8.8.8")

    def update(self, dt):
        if self.settings_banner and (time.time() - self.banner_time > 3.0):
            self.settings_banner = None

    def handle_mouse_motion(self, pos):
        """Records local mouse coordinate inside laptop surface for hover highlights & cursor."""
        self.hover_pos = pos

    def handle_mouse_down(self, pos, button):
        if not self.is_open or button != 1:
            return

        mx, my = pos
        self.hover_pos = pos
        L = self.layout

        # 1. Close Laptop button [ESC] at top right of laptop bezel
        if L["detach_btn"].collidepoint(mx, my):
            self.close()
            self.sound.play_key()
            return

        # 2. Window Close Button [X] for active application
        if self.active_app is not None and L["window_close_btn"].collidepoint(mx, my):
            self.active_app = None
            self.sound.play_key()
            return

        # 3. Allow direct app switching from Taskbar (Windows) or Dock (Ubuntu) even if window is open
        if self.is_windows:
            for app_id, rect in L["taskbar_icons"].items():
                if rect.collidepoint(mx, my):
                    self._activate_app_from_launcher(app_id)
                    return
        else:
            for app_id, rect in L["dock_icons"].items():
                if rect.collidepoint(mx, my):
                    self._activate_app_from_launcher(app_id)
                    return

            # Ubuntu Activities button (clicking toggles/minimizes window to desktop)
            if L["activities_btn"].collidepoint(mx, my):
                self.active_app = None
                self.sound.play_key()
                return

        # 4. Handle App-specific clicks if a window is open
        if self.active_app == "browser":
            self._handle_browser_click(mx, my)
            return
        elif self.active_app == "network_settings":
            self._handle_network_click(mx, my)
            return
        elif self.active_app == "putty":
            self._handle_putty_click(mx, my)
            return
        elif self.active_app == "terminal":
            self._handle_terminal_click(mx, my)
            return

        # 5. Desktop Icons (when no window is focused)
        for app_id, rect in L["desktop_icons"].items():
            if rect.collidepoint(mx, my):
                self._activate_app_from_launcher(app_id)
                return

    def _activate_app_from_launcher(self, app_id):
        """Activates/launches the requested app with proper initialization."""
        if app_id in ("start", "search"):
            # Toggle start menu / return to desktop
            self.active_app = None
        elif app_id == "browser":
            self.active_app = "browser"
        elif app_id == "network_settings":
            self.active_app = "network_settings"
            self._sync_network_fields()
        elif app_id == "putty":
            self.active_app = "putty"
            self._try_connect_putty()
        elif app_id == "terminal":
            self.active_app = "terminal"

        self.sound.play_key()

    def _handle_browser_click(self, mx, my):
        B = self.layout["browser"]

        # URL Input Bar
        if B["url_bar"].collidepoint(mx, my):
            self.browser_url_active = True
            self.sound.play_key()
            return
        else:
            self.browser_url_active = False

        # Go Button
        if B["go_btn"].collidepoint(mx, my):
            self.navigate_browser(self.browser_input)
            self.sound.play_key()
            return

        # Back Button (<)
        if B["back_btn"].collidepoint(mx, my):
            self.browser_input = "http://192.168.1.1"
            self.navigate_browser(self.browser_input)
            self.sound.play_key()
            return

        # Refresh Button (↻)
        if B["refresh_btn"].collidepoint(mx, my):
            self.navigate_browser(self.browser_input)
            self.sound.play_key()
            return

        # Bookmarks Bar:
        if B["bm_router"].collidepoint(mx, my):
            self.browser_input = "http://192.168.1.1"
            self.navigate_browser(self.browser_input)
            self.sound.play_key()
            return
        elif B["bm_server"].collidepoint(mx, my):
            self.browser_input = "http://192.168.1.10"
            self.navigate_browser(self.browser_input)
            self.sound.play_key()
            return
        elif B["bm_asa"].collidepoint(mx, my):
            self.browser_input = "https://203.0.113.1"
            self.navigate_browser(self.browser_input)
            self.sound.play_key()
            return
        elif B["bm_google"].collidepoint(mx, my):
            self.browser_input = "http://8.8.8.8"
            self.navigate_browser(self.browser_input)
            self.sound.play_key()
            return

    def navigate_browser(self, url):
        clean = url.strip().lower().replace("http://", "").replace("https://", "").split("/")[0]
        self.browser_url = url
        self.browser_input = url
        self.browser_url_active = False

        # Probe reachability using packet engine
        res = self.packet_engine.simulate_ping(self.device, clean, count=1, simulate_arp=False)
        self.browser_page_status = "OK" if res.packets_received > 0 else "ERROR"

    def _handle_network_click(self, mx, my):
        N = self.layout["network"]

        # Form Fields
        if N["field_ip"].collidepoint(mx, my):
            self.active_field = "ip"
            self.sound.play_key()
            return
        elif N["field_mask"].collidepoint(mx, my):
            self.active_field = "mask"
            self.sound.play_key()
            return
        elif N["field_gw"].collidepoint(mx, my):
            self.active_field = "gw"
            self.sound.play_key()
            return
        elif N["field_dns"].collidepoint(mx, my):
            self.active_field = "dns"
            self.sound.play_key()
            return

        # Apply Settings Button
        if N["btn_apply"].collidepoint(mx, my):
            self.apply_network_settings()
            self.sound.play_key()
            return

        self.active_field = None

    def apply_network_settings(self):
        self.device.configure_ip(self.net_ip.strip(), self.net_mask.strip(),
                                 gateway=self.net_gw.strip(), dns=self.net_dns.strip())
        self.settings_banner = "Network configuration applied successfully!"
        self.banner_time = time.time()
        self.sound.play_ping(success=True)

    def _try_connect_putty(self):
        """Attempts to open serial rollover session if con0 is cabled to an appliance."""
        con0 = self.device.ports.get("con0")
        if con0 and con0.cable:
            peer_port = con0.cable.get_peer_port(con0)
            if peer_port and not peer_port.is_shutdown:
                target_dev = peer_port.device
                self.putty_connected = True
                self.putty_target_device = target_dev
                self.putty_terminal_executor = CommandExecutor(target_dev)
                self.putty_history = [
                    f"=== Connected to {target_dev.hostname} via Rollover Serial Cable (COM1: 9600-8-N-1) ===",
                    "Type '?' or 'help' for command list. Type 'exit' to disconnect.",
                    ""
                ]
                self.putty_error_msg = None
                return

        # No cable connected to laptop con0
        self.putty_connected = False
        self.putty_target_device = None
        self.putty_terminal_executor = None
        self.putty_error_msg = (
            "PuTTY Fatal Error:\n"
            "Unable to open serial port COM1.\n"
            "No active rollover console cable connected to Laptop con0 port.\n"
            "Please connect a Console cable ([F]) from Laptop to a Switch, Router, or Firewall."
        )

    def _handle_putty_click(self, mx, my):
        P = self.layout["putty"]
        # Reconnect button on error dialog
        if not self.putty_connected:
            if P["retry_btn"].collidepoint(mx, my):
                self._try_connect_putty()
                self.sound.play_key()

    def _handle_terminal_click(self, mx, my):
        pass

    def handle_key(self, event):
        if not self.is_open:
            return

        if event.key == pygame.K_ESCAPE:
            if self.active_app is not None:
                self.active_app = None
                self.sound.play_key()
            else:
                self.close()
            return

        # 1. Browser URL Bar Input
        if self.active_app == "browser" and self.browser_url_active:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.navigate_browser(self.browser_input)
                self.sound.play_key()
            elif event.key == pygame.K_BACKSPACE:
                self.browser_input = self.browser_input[:-1]
                self._play_key_sound()
            elif event.unicode and event.unicode.isprintable():
                self.browser_input += event.unicode
                self._play_key_sound()
            return

        # 2. Network Settings Text Input
        if self.active_app == "network_settings" and self.active_field:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.apply_network_settings()
            elif event.key == pygame.K_BACKSPACE:
                if self.active_field == "ip": self.net_ip = self.net_ip[:-1]
                elif self.active_field == "mask": self.net_mask = self.net_mask[:-1]
                elif self.active_field == "gw": self.net_gw = self.net_gw[:-1]
                elif self.active_field == "dns": self.net_dns = self.net_dns[:-1]
                self._play_key_sound()
            elif event.unicode and (event.unicode.isdigit() or event.unicode == "."):
                if self.active_field == "ip": self.net_ip += event.unicode
                elif self.active_field == "mask": self.net_mask += event.unicode
                elif self.active_field == "gw": self.net_gw += event.unicode
                elif self.active_field == "dns": self.net_dns += event.unicode
                self._play_key_sound()
            return

        # 3. PuTTY Serial Console Input
        if self.active_app == "putty" and self.putty_connected and self.putty_terminal_executor:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                cmd = self.putty_input
                prompt = self.putty_terminal_executor.get_prompt()
                self.putty_history.append(f"{prompt}{cmd}")
                output = self.putty_terminal_executor.execute(cmd)
                if output:
                    for line in output.split("\n"):
                        self.putty_history.append(line)
                self.putty_input = ""
                self.sound.play_key()
            elif event.key == pygame.K_BACKSPACE:
                self.putty_input = self.putty_input[:-1]
                self._play_key_sound()
            elif event.unicode and event.unicode.isprintable():
                self.putty_input += event.unicode
                self._play_key_sound()
            return

        # 4. Local Host Terminal (CMD / bash) Input
        if self.active_app == "terminal":
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                cmd = self.local_term_input
                prompt = "C:\\Users\\Engineer> " if self.is_windows else "engineer@ubuntu:~$ "
                self.local_term_history.append(f"{prompt}{cmd}")
                output = self.local_term_executor.execute(cmd)
                if output:
                    for line in output.split("\n"):
                        self.local_term_history.append(line)
                self.local_term_input = ""
                self.sound.play_key()
            elif event.key == pygame.K_BACKSPACE:
                self.local_term_input = self.local_term_input[:-1]
                self._play_key_sound()
            elif event.unicode and event.unicode.isprintable():
                self.local_term_input += event.unicode
                self._play_key_sound()
            return

    def render(self):
        w, h = self.width, self.height
        L = self.layout
        dx, dy, dw, dh = L["dx"], L["dy"], L["dw"], L["dh"]
        mx, my = self.hover_pos

        self.surface.fill((0, 0, 0, 0))

        # 1. Outer Laptop Chassis & Screen Bezel (Matte Charcoal / Titanium)
        pygame.draw.rect(self.surface, (28, 30, 34), (0, 0, w, h), border_radius=12)
        pygame.draw.rect(self.surface, (50, 54, 60), (0, 0, w, h), width=2, border_radius=12)

        # Top Bezel: Webcam & Status LED
        pygame.draw.circle(self.surface, (15, 18, 22), (w // 2, 14), 5)
        pygame.draw.circle(self.surface, (0, 220, 100) if int(time.time()*2)%2==0 else (20, 40, 30), (w // 2 + 14, 14), 2)

        # Top Right Close Button [ESC] Detach Laptop
        d_rect = L["detach_btn"]
        d_hover = d_rect.collidepoint(mx, my)
        d_bg = (180, 45, 45) if d_hover else (38, 42, 48)
        pygame.draw.rect(self.surface, d_bg, d_rect, border_radius=4)
        pygame.draw.rect(self.surface, (70, 75, 85) if not d_hover else (220, 80, 80), d_rect, width=1, border_radius=4)
        close_btn = self.font_sm.render("[ESC] Detach Laptop", True, (255, 255, 255) if d_hover else (180, 195, 210))
        self.surface.blit(close_btn, (d_rect.x + 12, d_rect.y + 2))

        # 2. Render OS Desktop Wallpaper
        if self.is_windows:
            self._render_windows_desktop()
        else:
            self._render_ubuntu_desktop()

        # 3. Render Active Application Window
        if self.active_app == "browser":
            self._render_browser_window()
        elif self.active_app == "network_settings":
            self._render_network_window()
        elif self.active_app == "putty":
            self._render_putty_window()
        elif self.active_app == "terminal":
            self._render_terminal_window()

        # 4. Draw Custom Software Cursor for pinpoint optical alignment
        if 0 <= mx < w and 0 <= my < h:
            cursor_poly = [
                (mx, my),
                (mx, my + 16),
                (mx + 4, my + 13),
                (mx + 8, my + 20),
                (mx + 11, my + 19),
                (mx + 7, my + 12),
                (mx + 12, my + 12),
            ]
            pygame.draw.polygon(self.surface, (20, 24, 30), cursor_poly)
            inner_poly = [
                (mx + 1, my + 2),
                (mx + 1, my + 13),
                (mx + 4, my + 11),
                (mx + 7, my + 16),
                (mx + 9, my + 15),
                (mx + 6, my + 10),
                (mx + 10, my + 10),
            ]
            pygame.draw.polygon(self.surface, (255, 255, 255), inner_poly)

        return self.surface

    @staticmethod
    def _create_smooth_petal(cx, cy, length, max_width, angle_deg, curve_sweep=0.0):
        """Generates a smooth, natural curved petal polygon with tapered tip."""
        rad = math.radians(angle_deg)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        perp_cos = -sin_a
        perp_sin = cos_a

        pts = [(cx, cy)]
        steps = 22
        # Left flank
        for i in range(1, steps):
            t = i / float(steps)
            dist = length * t
            width = math.sin(math.pi * (t ** 0.85)) * (max_width * 0.5)
            sweep = (t ** 1.8) * curve_sweep * length * 0.25
            px = cx + cos_a * dist + perp_cos * (width + sweep)
            py = cy + sin_a * dist + perp_sin * (width + sweep)
            pts.append((int(px), int(py)))

        # Tip point
        tip_sweep = curve_sweep * length * 0.25
        tip_x = cx + cos_a * length + perp_cos * tip_sweep
        tip_y = cy + sin_a * length + perp_sin * tip_sweep
        pts.append((int(tip_x), int(tip_y)))

        # Right flank
        for i in range(steps - 1, 0, -1):
            t = i / float(steps)
            dist = length * t
            width = -math.sin(math.pi * (t ** 0.85)) * (max_width * 0.5)
            sweep = (t ** 1.8) * curve_sweep * length * 0.25
            px = cx + cos_a * dist + perp_cos * (width + sweep)
            py = cy + sin_a * dist + perp_sin * (width + sweep)
            pts.append((int(px), int(py)))

        return pts

    def _generate_windows_wallpaper(self, dw, dh):
        """Generates authentic Windows 11 Bloom wallpaper with layered luminous petals."""
        surf = pygame.Surface((dw, dh))

        # Deep midnight navy to royal blue vertical gradient
        for y in range(dh):
            prog = y / float(dh)
            r = int(10 + 15 * prog)
            g = int(22 + 38 * prog)
            b = int(50 + 68 * prog)
            pygame.draw.line(surf, (r, g, b), (0, y), (dw, y))

        cx, cy = dw // 2, dh // 2 - 15

        # Ultra-smooth continuous radial glow using downscale + smoothscale
        glow_size = 120
        glow_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        gcx, gcy = glow_size // 2, glow_size // 2
        for r in range(gcx, 0, -1):
            t = 1.0 - (r / float(gcx))
            alpha = int(90 * (t ** 1.8))
            pygame.draw.circle(glow_surf, (0, 130, 255, alpha), (gcx, gcy), r)

        target_glow_w = int(dw * 0.72)
        target_glow_h = int(dh * 0.92)
        scaled_glow = pygame.transform.smoothscale(glow_surf, (target_glow_w, target_glow_h))
        surf.blit(scaled_glow, (cx - target_glow_w // 2, cy - target_glow_h // 2))

        # Bloom Petal Ribbons
        bloom_surf = pygame.Surface((dw, dh), pygame.SRCALPHA)
        petal_specs = [
            # Layer 1: Deep Sapphire Outer Wings
            (210, 110, -135, -0.35, (0, 60, 140, 190), (0, 95, 195, 220), 160),
            (215, 115, -45, 0.35, (0, 65, 145, 190), (0, 100, 200, 220), 160),
            (230, 120, -90, 0.0, (0, 70, 155, 195), (0, 110, 215, 225), 180),
            (220, 105, -112, -0.2, (0, 65, 150, 195), (0, 105, 205, 220), 170),
            (220, 105, -68, 0.2, (0, 68, 152, 195), (0, 108, 208, 220), 170),

            # Layer 2: Rich Azure Mid Petals
            (190, 95, -150, -0.25, (0, 85, 185, 210), (20, 135, 240, 230), 200),
            (195, 95, -30, 0.25, (0, 90, 190, 210), (25, 140, 245, 230), 200),
            (185, 90, -125, -0.15, (0, 100, 205, 215), (40, 155, 255, 235), 210),
            (190, 90, -55, 0.15, (0, 105, 210, 215), (45, 160, 255, 235), 210),
            (200, 100, -90, -0.05, (0, 115, 225, 220), (60, 175, 255, 240), 220),

            # Layer 3: Vibrant Glowing Sky Petals
            (165, 80, -108, -0.15, (10, 135, 250, 230), (80, 195, 255, 245), 230),
            (170, 80, -72, 0.15, (20, 145, 255, 230), (95, 205, 255, 245), 230),
            (150, 75, -135, -0.1, (0, 125, 240, 225), (75, 190, 255, 240), 220),
            (155, 75, -45, 0.1, (10, 130, 245, 225), (85, 195, 255, 240), 220),

            # Layer 4: Luminous Inner Core Ribbons
            (135, 65, -96, -0.08, (60, 175, 255, 240), (160, 230, 255, 255), 240),
            (140, 68, -84, 0.08, (75, 185, 255, 240), (180, 238, 255, 255), 240),
            (110, 52, -90, 0.0, (110, 205, 255, 245), (220, 248, 255, 255), 250),

            # Layer 5: Bottom Fold / Base Collar
            (130, 75, 40, 0.2, (0, 75, 165, 200), (0, 115, 220, 225), 180),
            (135, 75, 140, -0.2, (0, 70, 160, 200), (0, 110, 215, 225), 180),
            (115, 70, 90, 0.0, (0, 90, 185, 215), (20, 140, 240, 230), 200),
            (95, 60, 80, -0.08, (0, 110, 215, 225), (60, 175, 255, 235), 210),
            (95, 60, 100, 0.08, (0, 110, 215, 225), (60, 175, 255, 235), 210),
        ]

        for length, width, angle, sweep, fill, edge, sheen_a in petal_specs:
            pts = self._create_smooth_petal(cx, cy + 20, length, width, angle, sweep)
            pygame.draw.polygon(bloom_surf, fill, pts)
            pygame.draw.polygon(bloom_surf, edge, pts, width=2)
            half_pts = pts[len(pts)//4 : len(pts)//2 + 2]
            if len(half_pts) >= 2:
                pygame.draw.lines(bloom_surf, (220, 245, 255, sheen_a), False, half_pts, width=2)

        pygame.draw.circle(bloom_surf, (160, 230, 255, 200), (cx, cy + 20), 12)
        pygame.draw.circle(bloom_surf, (245, 252, 255, 240), (cx, cy + 20), 5)

        surf.blit(bloom_surf, (0, 0))
        return surf

    def _generate_ubuntu_wallpaper(self, dw, dh):
        """Generates authentic Ubuntu 22.04 LTS Jammy Jellyfish geometric wallpaper."""
        surf = pygame.Surface((dw, dh))

        # Rich aubergine diagonal gradient
        for y in range(dh):
            prog = y / float(dh)
            r = int(44 + 26 * prog)
            g = int(6 + 10 * prog)
            b = int(48 - 20 * prog)
            pygame.draw.line(surf, (r, g, b), (0, y), (dw, y))

        glow_surf = pygame.Surface((dw, dh), pygame.SRCALPHA)
        cx, cy = int(dw * 0.65), int(dh * 0.44)

        # Concentric sonar water ripples
        for r_ring, a_ring in [(170, 25), (240, 18), (310, 12), (380, 8)]:
            pygame.draw.circle(glow_surf, (240, 110, 45, a_ring), (cx, cy - 25), r_ring, width=1)

        # Ambient purple aura
        for radius, alpha in [(260, 18), (180, 30), (110, 42)]:
            pygame.draw.circle(glow_surf, (155, 40, 115, alpha), (cx, cy), radius)

        # Jammy Jellyfish Bell Dome
        bell_w = 145
        bell_h = 135
        dome_outline = []
        for i in range(17):
            ang = math.pi + i * (math.pi / 16.0)
            px = cx + math.cos(ang) * bell_w
            py = cy - 25 + math.sin(ang) * bell_h
            dome_outline.append((int(px), int(py)))

        rim_pts = [
            (cx + bell_w, cy - 20),
            (cx + 105, cy - 10),
            (cx + 60, cy),
            (cx + 15, cy - 12),
            (cx - 35, cy - 2),
            (cx - 85, cy - 12),
            (cx - bell_w, cy - 20),
        ]
        full_dome = dome_outline + rim_pts

        pygame.draw.polygon(glow_surf, (233, 84, 32, 22), full_dome)
        pygame.draw.polygon(glow_surf, (233, 84, 32, 160), full_dome, width=2)

        # Internal facet grid
        facet_lines = [
            ((cx - 100, cy - 90), (cx - 35, cy - 2)),
            ((cx - 45, cy - 130), (cx + 15, cy - 12)),
            ((cx + 45, cy - 130), (cx + 60, cy)),
            ((cx + 100, cy - 90), (cx + 105, cy - 10)),
            ((cx - 100, cy - 90), (cx - 45, cy - 130)),
            ((cx - 45, cy - 130), (cx + 45, cy - 130)),
            ((cx + 45, cy - 130), (cx + 100, cy - 90)),
            ((cx - 125, cy - 50), (cx - 85, cy - 12)),
            ((cx + 125, cy - 50), (cx + 105, cy - 10)),
            ((cx - 100, cy - 90), (cx + 15, cy - 12)),
            ((cx + 100, cy - 90), (cx + 15, cy - 12)),
        ]
        for p1, p2 in facet_lines:
            pygame.draw.line(glow_surf, (255, 135, 45, 90), p1, p2, width=1)

        # Flowing tentacles
        tentacles_def = [
            [(cx - 105, cy - 15), (cx - 125, cy + 50), (cx - 95, cy + 130), (cx - 115, cy + 220), (cx - 105, cy + 280)],
            [(cx - 60, cy - 5), (cx - 35, cy + 65), (cx - 75, cy + 145), (cx - 45, cy + 235), (cx - 60, cy + 290)],
            [(cx - 10, cy - 8), (cx + 25, cy + 60), (cx - 5, cy + 140), (cx + 30, cy + 225), (cx + 15, cy + 285)],
            [(cx + 40, cy - 3), (cx + 70, cy + 55), (cx + 45, cy + 135), (cx + 80, cy + 215), (cx + 65, cy + 275)],
            [(cx + 85, cy - 8), (cx + 115, cy + 45), (cx + 95, cy + 125), (cx + 120, cy + 205), (cx + 110, cy + 265)],
        ]
        for t_idx, tent in enumerate(tentacles_def):
            alpha = 140 if t_idx in (1, 2, 3) else 95
            pygame.draw.lines(glow_surf, (233, 84, 32, alpha), False, tent, width=2)
            for p in tent[1:-1]:
                pygame.draw.circle(glow_surf, (255, 175, 60, alpha + 30), p, 2)

        surf.blit(glow_surf, (0, 0))
        return surf

    def _draw_vector_firefox(self, surface, rect):
        """Draws stylized Firefox vector icon."""
        cx, cy = rect.centerx, rect.centery
        r = min(rect.width, rect.height) // 2 - 2

        pygame.draw.circle(surface, (20, 60, 150), (cx, cy), r)
        pygame.draw.circle(surface, (30, 110, 225), (cx - r//5, cy - r//5), int(r * 0.75))
        pygame.draw.circle(surface, (60, 160, 255), (cx - r//3, cy - r//3), int(r * 0.45))

        pts_tail = [
            (cx - r + 1, cy + r//3),
            (cx - int(r*0.8), cy + int(r*0.9)),
            (cx, cy + r + 1),
            (cx + int(r*0.9), cy + int(r*0.6)),
            (cx + r + 1, cy),
            (cx + int(r*0.8), cy - int(r*0.7)),
            (cx + int(r*0.4), cy - r),
            (cx + int(r*0.1), cy - int(r*0.6)),
            (cx + int(r*0.5), cy - int(r*0.2)),
            (cx + int(r*0.6), cy + int(r*0.3)),
            (cx + int(r*0.2), cy + int(r*0.6)),
            (cx - int(r*0.4), cy + int(r*0.4)),
            (cx - int(r*0.7), cy),
        ]
        pygame.draw.polygon(surface, (235, 75, 20), pts_tail)

        pts_flame = [
            (cx - int(r*0.7), cy + int(r*0.7)),
            (cx - int(r*0.1), cy + int(r*0.9)),
            (cx + int(r*0.7), cy + int(r*0.6)),
            (cx + int(r*0.9), cy + int(r*0.1)),
            (cx + int(r*0.7), cy - int(r*0.4)),
            (cx + int(r*0.4), cy - int(r*0.2)),
            (cx + int(r*0.5), cy + int(r*0.2)),
            (cx + int(r*0.2), cy + int(r*0.5)),
            (cx - int(r*0.3), cy + int(r*0.5)),
        ]
        pygame.draw.polygon(surface, (255, 185, 25), pts_flame)

        pts_ear = [
            (cx + int(r*0.4), cy - r),
            (cx + int(r*0.75), cy - int(r*0.85)),
            (cx + int(r*0.6), cy - int(r*0.45)),
        ]
        pygame.draw.polygon(surface, (255, 140, 0), pts_ear)

    def _draw_vector_edge(self, surface, rect):
        """Draws Microsoft Edge wave vector icon."""
        cx, cy = rect.centerx, rect.centery
        r = min(rect.width, rect.height) // 2 - 2

        pygame.draw.circle(surface, (0, 80, 190), (cx, cy), r)
        pygame.draw.circle(surface, (0, 165, 245), (cx - 2, cy - 3), int(r * 0.85))

        pts_wave = [
            (cx - r + 1, cy),
            (cx - int(r*0.6), cy + int(r*0.8)),
            (cx + int(r*0.4), cy + int(r*0.85)),
            (cx + r, cy + int(r*0.3)),
            (cx + int(r*0.5), cy + int(r*0.1)),
            (cx, cy + int(r*0.4)),
            (cx - int(r*0.5), cy + int(r*0.3)),
        ]
        pygame.draw.polygon(surface, (0, 205, 140), pts_wave)

        pygame.draw.circle(surface, (0, 120, 215), (cx + int(r*0.25), cy - int(r*0.15)), int(r * 0.45))
        pygame.draw.circle(surface, (255, 255, 255), (cx + int(r*0.35), cy - int(r*0.2)), int(r * 0.28))

    def _draw_vector_terminal(self, surface, rect, is_windows=False):
        """Draws sleek Terminal console vector icon."""
        x, y, w, h = rect.x, rect.y, rect.width, rect.height
        pad = max(2, min(w, h) // 8)
        tw, th = w - pad * 2, h - pad * 2
        tx, ty = x + pad, y + pad

        base_col = (16, 20, 28) if is_windows else (28, 28, 34)
        pygame.draw.rect(surface, base_col, (tx, ty, tw, th), border_radius=max(3, tw//6))
        pygame.draw.rect(surface, (55, 65, 80) if is_windows else (60, 55, 65), (tx, ty, tw, th), width=1, border_radius=max(3, tw//6))

        hb_h = max(4, th // 4)
        pygame.draw.rect(surface, (30, 36, 48) if is_windows else (48, 32, 45), (tx, ty, tw, hb_h), border_top_left_radius=max(3, tw//6), border_top_right_radius=max(3, tw//6))

        dot_r = max(1, hb_h // 4)
        for i, dot_col in enumerate([(235, 80, 80), (240, 180, 40), (60, 200, 80)] if not is_windows else [(120, 140, 160)]*3):
            pygame.draw.circle(surface, dot_col, (tx + 4 + i * (dot_r * 2 + 2), ty + hb_h // 2), dot_r)

        prompt_col = (0, 220, 255) if is_windows else (75, 220, 100)
        px = tx + max(4, tw // 5)
        py = ty + hb_h + (th - hb_h) // 2
        sz = max(3, tw // 6)
        pts_chevron = [
            (px - sz//2, py - sz),
            (px + sz//2, py),
            (px - sz//2, py + sz)
        ]
        pygame.draw.lines(surface, prompt_col, False, pts_chevron, width=max(1, sz//2))

        cx = px + sz + 2
        cw = max(3, sz)
        pygame.draw.line(surface, (255, 255, 255) if is_windows else (233, 84, 32), (cx, py + sz), (cx + cw, py + sz), width=max(1, sz//2))

    def _draw_vector_settings(self, surface, rect):
        """Draws metallic/Fluent gear cog vector icon."""
        cx, cy = rect.centerx, rect.centery
        r = min(rect.width, rect.height) // 2 - 2

        gear_col = (115, 130, 150)
        inner_col = (48, 58, 72)

        num_teeth = 8
        tooth_len = max(2, r // 4)
        tooth_w = max(2, int(r * 0.3))
        for i in range(num_teeth):
            angle = i * (2 * math.pi / num_teeth)
            tx = cx + int(math.cos(angle) * (r - tooth_len // 2))
            ty = cy + int(math.sin(angle) * (r - tooth_len // 2))
            pygame.draw.circle(surface, gear_col, (tx, ty), tooth_w)

        pygame.draw.circle(surface, gear_col, (cx, cy), r - tooth_len // 3)
        pygame.draw.circle(surface, inner_col, (cx, cy), int(r * 0.72))
        pygame.draw.circle(surface, (22, 26, 34), (cx, cy), int(r * 0.38))
        pygame.draw.circle(surface, (160, 180, 205), (cx, cy), int(r * 0.38), width=1)

    def _draw_vector_putty(self, surface, rect):
        """Draws serial terminal console vector icon."""
        cx, cy = rect.centerx, rect.centery
        w, h = rect.width, rect.height
        pad = max(2, min(w, h) // 8)
        tw, th = w - pad * 2, h - pad * 2
        tx, ty = cx - tw // 2, cy - th // 2

        pygame.draw.rect(surface, (30, 50, 90), (tx, ty, tw, th - max(3, th//5)), border_radius=max(2, tw//8))
        pygame.draw.rect(surface, (70, 110, 180), (tx, ty, tw, th - max(3, th//5)), width=1, border_radius=max(2, tw//8))

        screen_rect = pygame.Rect(tx + 2, ty + 2, tw - 4, th - max(3, th//5) - 4)
        pygame.draw.rect(surface, (10, 25, 55), screen_rect, border_radius=2)

        lx, ly = screen_rect.centerx, screen_rect.centery
        pts_bolt = [
            (lx - screen_rect.width//3, ly - screen_rect.height//4),
            (lx, ly),
            (lx - 2, ly + 1),
            (lx + screen_rect.width//3, ly + screen_rect.height//3),
            (lx + 1, ly - 1),
            (lx + 4, ly - screen_rect.height//3),
        ]
        pygame.draw.lines(surface, (255, 200, 30), False, pts_bolt, width=max(1, tw//15))

        stand_w = max(4, tw // 3)
        stand_h = max(2, th // 6)
        pygame.draw.rect(surface, (50, 70, 100), (cx - stand_w//2, ty + th - stand_h, stand_w, stand_h), border_radius=1)

    def _draw_vector_start(self, surface, rect):
        """Draws official Windows 11 4-square Fluent Start icon."""
        cx, cy = rect.centerx, rect.centery
        sz = max(4, min(rect.width, rect.height) // 2 - 2)
        gap = 2
        sq = sz - gap // 2
        col = (0, 120, 215)

        pygame.draw.rect(surface, col, (cx - sq - 1, cy - sq - 1, sq, sq), border_radius=1)
        pygame.draw.rect(surface, col, (cx + 1, cy - sq - 1, sq, sq), border_radius=1)
        pygame.draw.rect(surface, col, (cx - sq - 1, cy + 1, sq, sq), border_radius=1)
        pygame.draw.rect(surface, col, (cx + 1, cy + 1, sq, sq), border_radius=1)

    def _draw_vector_search(self, surface, rect):
        """Draws magnifying glass search icon."""
        cx, cy = rect.centerx, rect.centery
        r = max(3, min(rect.width, rect.height) // 3)
        col = (100, 115, 130)

        pygame.draw.circle(surface, col, (cx - 1, cy - 1), r, width=max(1, r//3))
        hx = cx - 1 + int(r * 0.7)
        hy = cy - 1 + int(r * 0.7)
        pygame.draw.line(surface, col, (hx, hy), (hx + r - 1, hy + r - 1), width=max(1, r//3))

    def _draw_system_tray_icons(self, surface, x, y, is_up=True, is_windows=True):
        """Draws mini vector tray icons: Network, Speaker, Battery."""
        fg = (40, 50, 65) if is_windows else (220, 220, 220)

        # 1. Network / Ethernet Icon
        net_col = (10, 160, 60) if is_up else (190, 40, 40)
        pygame.draw.rect(surface, net_col if not is_windows else fg, (x, y + 2, 14, 10), width=1, border_radius=2)
        pygame.draw.rect(surface, net_col, (x + 3, y + 5, 8, 4))
        pygame.draw.line(surface, fg, (x + 5, y + 12), (x + 9, y + 12), width=1)

        # 2. Speaker Icon
        sx = x + 20
        pygame.draw.rect(surface, fg, (sx, y + 4, 3, 6))
        pygame.draw.polygon(surface, fg, [(sx + 3, y + 4), (sx + 8, y + 1), (sx + 8, y + 13), (sx + 3, y + 10)])
        pygame.draw.arc(surface, fg, (sx + 6, y + 2, 8, 10), -math.pi/3, math.pi/3, 1)

        # 3. Battery Icon
        bx = sx + 20
        pygame.draw.rect(surface, fg, (bx, y + 3, 16, 8), width=1, border_radius=2)
        pygame.draw.rect(surface, fg, (bx + 16, y + 5, 2, 4), border_radius=1)
        pygame.draw.rect(surface, (10, 180, 70), (bx + 2, y + 5, 10, 4))

    def _render_windows_desktop(self):
        L = self.layout
        dx, dy, dw, dh = L["dx"], L["dy"], L["dw"], L["dh"]

        # Cache wallpaper surface for high-performance 60 FPS rendering
        if self._wallpaper_surface is None or self._wallpaper_surface.get_size() != (dw, dh):
            self._wallpaper_surface = self._generate_windows_wallpaper(dw, dh)
        self.surface.blit(self._wallpaper_surface, (dx, dy))

        # Desktop Icons
        self._draw_desktop_icon_box(L["desktop_icons"]["browser"], "Edge", (0, 120, 215), "WEB")
        self._draw_desktop_icon_box(L["desktop_icons"]["network_settings"], "Settings", (70, 80, 95), "NET")
        self._draw_desktop_icon_box(L["desktop_icons"]["putty"], "PuTTY", (20, 50, 160), "SER")
        self._draw_desktop_icon_box(L["desktop_icons"]["terminal"], "Terminal", (15, 15, 20), "CMD")

        # Windows 11 Center Taskbar (Frosted Acrylic)
        tb_r = L["taskbar_rect"]
        pygame.draw.rect(self.surface, (244, 246, 250), tb_r)
        pygame.draw.line(self.surface, (218, 224, 235), (tb_r.left, tb_r.top), (tb_r.right, tb_r.top), 1)

        # Taskbar Buttons
        icons = L["taskbar_icons"]
        self._draw_taskbar_button(icons["start"], (0, 120, 215), "WIN")
        self._draw_taskbar_button(icons["search"], (90, 100, 115), "SRC")
        self._draw_taskbar_button(icons["browser"], (0, 120, 215), "WEB", is_active=(self.active_app == "browser"))
        self._draw_taskbar_button(icons["putty"], (20, 50, 160), "PUT", is_active=(self.active_app == "putty"))
        self._draw_taskbar_button(icons["terminal"], (20, 20, 25), "CMD", is_active=(self.active_app == "terminal"))
        self._draw_taskbar_button(icons["network_settings"], (70, 80, 95), "NET", is_active=(self.active_app == "network_settings"))

        # System Tray (Network, Sound, Battery, Time & Date)
        p = self.device.eth0
        is_up = bool(p and p.is_link_up)
        self._draw_system_tray_icons(self.surface, dx + dw - 145, tb_r.y + 14, is_up=is_up, is_windows=True)

        cur_time = time.strftime("%H:%M")
        cur_date = time.strftime("%m/%d/%Y")
        t_surf = self.font_sm.render(cur_time, True, (30, 35, 45))
        d_surf = self.font_sm.render(cur_date, True, (90, 95, 105))
        self.surface.blit(t_surf, (dx + dw - 75, tb_r.y + 6))
        self.surface.blit(d_surf, (dx + dw - 75, tb_r.y + 22))

    def _render_ubuntu_desktop(self):
        L = self.layout
        dx, dy, dw, dh = L["dx"], L["dy"], L["dw"], L["dh"]
        mx, my = self.hover_pos

        # Cache wallpaper surface for high-performance 60 FPS rendering
        if self._wallpaper_surface is None or self._wallpaper_surface.get_size() != (dw, dh):
            self._wallpaper_surface = self._generate_ubuntu_wallpaper(dw, dh)
        self.surface.blit(self._wallpaper_surface, (dx, dy))

        # Top Bar (Ubuntu GNOME 42)
        top_r = L["topbar_rect"]
        pygame.draw.rect(self.surface, (18, 18, 22), top_r)
        pygame.draw.line(self.surface, (35, 35, 42), (top_r.left, top_r.bottom), (top_r.right, top_r.bottom), 1)

        # Activities button
        act_r = L["activities_btn"]
        act_hover = act_r.collidepoint(mx, my)
        if act_hover:
            pygame.draw.rect(self.surface, (45, 45, 52), act_r, border_radius=12)
        act_surf = self.font_sm.render("Activities", True, (255, 255, 255) if act_hover else (220, 220, 225))
        self.surface.blit(act_surf, (act_r.x + (act_r.width - act_surf.get_width()) // 2, act_r.y + 4))

        # Center Clock
        date_str = time.strftime("%b %d  %H:%M")
        c_surf = self.font_sm.render(date_str, True, (240, 240, 240))
        self.surface.blit(c_surf, (dx + dw // 2 - c_surf.get_width() // 2, top_r.y + 6))

        # Right Status Cluster (Network, Speaker, Battery)
        p = self.device.eth0
        is_up = bool(p and p.is_link_up)
        self._draw_system_tray_icons(self.surface, dx + dw - 75, top_r.y + 6, is_up=is_up, is_windows=False)

        # Left Vertical Dock (Yaru Launcher)
        dock_r = L["dock_rect"]
        pygame.draw.rect(self.surface, (20, 20, 24), dock_r)
        pygame.draw.line(self.surface, (38, 38, 46), (dock_r.right, dock_r.top), (dock_r.right, dock_r.bottom), 1)

        d_icons = L["dock_icons"]
        self._draw_dock_button(d_icons["browser"], (233, 84, 32), "FOX", is_active=(self.active_app == "browser"))
        self._draw_dock_button(d_icons["putty"], (0, 115, 230), "COM", is_active=(self.active_app == "putty"))
        self._draw_dock_button(d_icons["terminal"], (10, 10, 12), ">_", is_active=(self.active_app == "terminal"))
        self._draw_dock_button(d_icons["network_settings"], (80, 80, 90), "NET", is_active=(self.active_app == "network_settings"))

        # Desktop Icons on Ubuntu
        self._draw_desktop_icon_box(L["desktop_icons"]["browser"], "Firefox", (233, 84, 32), "FOX")
        self._draw_desktop_icon_box(L["desktop_icons"]["network_settings"], "Settings", (80, 80, 90), "NET")
        self._draw_desktop_icon_box(L["desktop_icons"]["putty"], "Minicom", (0, 115, 230), "COM")
        self._draw_desktop_icon_box(L["desktop_icons"]["terminal"], "Terminal", (10, 10, 12), ">_")

    def _draw_desktop_icon_box(self, rect, label, col, tag):
        """Draws desktop app icon with vector art and translucent pill label."""
        mx, my = self.hover_pos
        is_hover = rect.collidepoint(mx, my)

        if is_hover:
            pygame.draw.rect(self.surface, (255, 255, 255, 35), rect, border_radius=8)
            pygame.draw.rect(self.surface, (255, 255, 255, 80), rect, width=1, border_radius=8)

        # Centered 40x40 icon emblem
        ic_rect = pygame.Rect(rect.x + (rect.width - 40) // 2, rect.y + 4, 40, 40)
        # Drop shadow behind icon
        pygame.draw.rect(self.surface, (0, 0, 0, 45), (ic_rect.x, ic_rect.y + 2, 40, 40), border_radius=8)

        tag_upper = str(tag).upper()
        lbl_lower = str(label).lower()
        if tag_upper == "FOX" or "firefox" in lbl_lower:
            self._draw_vector_firefox(self.surface, ic_rect)
        elif tag_upper == "WEB" or "edge" in lbl_lower:
            self._draw_vector_edge(self.surface, ic_rect)
        elif tag_upper in ("NET", "SET") or "setting" in lbl_lower:
            self._draw_vector_settings(self.surface, ic_rect)
        elif tag_upper in ("PUT", "COM", "SER") or "putty" in lbl_lower or "minicom" in lbl_lower:
            self._draw_vector_putty(self.surface, ic_rect)
        elif tag_upper in ("CMD", ">_") or "terminal" in lbl_lower:
            self._draw_vector_terminal(self.surface, ic_rect, is_windows=self.is_windows)
        else:
            pygame.draw.rect(self.surface, col, ic_rect, border_radius=8)
            tag_s = self.font_sm.render(tag, True, (255, 255, 255))
            self.surface.blit(tag_s, (ic_rect.x + (40 - tag_s.get_width()) // 2, ic_rect.y + 12))

        # Translucent pill label
        lbl_s = self.font_sm.render(label, True, (255, 255, 255))
        lw = lbl_s.get_width() + 10
        lh = lbl_s.get_height() + 4
        lbl_rect = pygame.Rect(rect.centerx - lw // 2, rect.y + 48, lw, lh)
        pygame.draw.rect(self.surface, (15, 18, 24, 160), lbl_rect, border_radius=4)
        self.surface.blit(lbl_s, (lbl_rect.x + 5, lbl_rect.y + 2))

    def _draw_taskbar_button(self, rect, col, tag, is_active=False):
        """Draws a Windows 11 taskbar button with vector art and active indicator pill."""
        mx, my = self.hover_pos
        is_hover = rect.collidepoint(mx, my)

        if is_hover:
            pygame.draw.rect(self.surface, (230, 236, 245), rect, border_radius=4)

        ic_rect = pygame.Rect(rect.x + (rect.width - 24) // 2, rect.y + (rect.height - 24) // 2, 24, 24)
        tag_upper = str(tag).upper()

        if tag_upper == "WIN":
            self._draw_vector_start(self.surface, ic_rect)
        elif tag_upper == "SRC":
            self._draw_vector_search(self.surface, ic_rect)
        elif tag_upper == "WEB":
            self._draw_vector_edge(self.surface, ic_rect)
        elif tag_upper in ("PUT", "SER", "COM"):
            self._draw_vector_putty(self.surface, ic_rect)
        elif tag_upper in ("CMD", ">_"):
            self._draw_vector_terminal(self.surface, ic_rect, is_windows=True)
        elif tag_upper in ("NET", "SET"):
            self._draw_vector_settings(self.surface, ic_rect)
        else:
            pygame.draw.rect(self.surface, col, ic_rect, border_radius=4)

        # Windows 11 Active Indicator Pill
        if is_active:
            pygame.draw.rect(self.surface, (0, 103, 192), (rect.x + 8, rect.bottom - 3, rect.width - 16, 3), border_radius=2)

    def _draw_dock_button(self, rect, col, tag, is_active=False):
        """Draws an Ubuntu dock button with vector art and orange indicator pip."""
        mx, my = self.hover_pos
        is_hover = rect.collidepoint(mx, my)

        if is_hover:
            pygame.draw.rect(self.surface, (45, 45, 52), rect, border_radius=8)

        ic_rect = pygame.Rect(rect.x + 2, rect.y + 2, 36, 36)
        tag_upper = str(tag).upper()

        if tag_upper in ("FOX", "WEB"):
            self._draw_vector_firefox(self.surface, ic_rect)
        elif tag_upper in ("COM", "PUT", "SER"):
            self._draw_vector_putty(self.surface, ic_rect)
        elif tag_upper in (">_", "CMD"):
            self._draw_vector_terminal(self.surface, ic_rect, is_windows=False)
        elif tag_upper in ("NET", "SET"):
            self._draw_vector_settings(self.surface, ic_rect)
        else:
            pygame.draw.rect(self.surface, col, ic_rect, border_radius=7)

        # Ubuntu Active Indicator Pip
        if is_active:
            pygame.draw.rect(self.surface, (233, 84, 32), (rect.x - 5, rect.y + 14, 3, 12), border_radius=1)

    def _render_window_frame(self, title_text, title_col=(30, 45, 60), bar_bg=(235, 242, 250)):
        """Renders standard window chassis, titlebar, and close button."""
        W = self.layout["window_rect"]
        C = self.layout["window_close_btn"]
        mx, my = self.hover_pos

        # Window Drop Shadow
        shadow_surf = pygame.Surface((W.width + 16, W.height + 16), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 20), (0, 0, W.width + 16, W.height + 16), border_radius=12)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 40), (3, 3, W.width + 10, W.height + 10), border_radius=10)
        self.surface.blit(shadow_surf, (W.x - 8, W.y - 6))

        if self.is_windows:
            # Windows 11 Fluent Window Chassis
            pygame.draw.rect(self.surface, (255, 255, 255), W, border_radius=8)
            pygame.draw.rect(self.surface, (218, 224, 235), W, width=1, border_radius=8)

            # Title Bar
            pygame.draw.rect(self.surface, bar_bg, (W.x, W.y, W.width, 32), border_top_left_radius=8, border_top_right_radius=8)
            pygame.draw.line(self.surface, (220, 226, 236), (W.x, W.y + 32), (W.right, W.y + 32), 1)

            t_surf = self.font_md.render(title_text, True, title_col)
            self.surface.blit(t_surf, (W.x + 16, W.y + 7))

            # Controls: Minimize, Maximize
            pygame.draw.line(self.surface, (90, 100, 115), (W.right - 76, W.y + 16), (W.right - 66, W.y + 16), 1)
            pygame.draw.rect(self.surface, (90, 100, 115), (W.right - 54, W.y + 11, 10, 10), width=1)

            # Close Button
            is_close_hover = C.collidepoint(mx, my)
            c_bg = (232, 17, 35) if is_close_hover else bar_bg
            pygame.draw.rect(self.surface, c_bg, C, border_top_right_radius=7)
            x_col = (255, 255, 255) if is_close_hover else (60, 70, 85)
            cx, cy = C.centerx, C.centery
            pygame.draw.line(self.surface, x_col, (cx - 4, cy - 4), (cx + 4, cy + 4), 1)
            pygame.draw.line(self.surface, x_col, (cx - 4, cy + 4), (cx + 4, cy - 4), 1)
        else:
            # Ubuntu Yaru Window Chassis
            pygame.draw.rect(self.surface, (250, 250, 252), W, border_radius=8)
            pygame.draw.rect(self.surface, (45, 45, 52), W, width=1, border_radius=8)

            u_bar_bg = (38, 38, 44) if bar_bg == (235, 242, 250) else bar_bg
            u_title_col = (240, 240, 245) if title_col == (30, 45, 60) else title_col
            pygame.draw.rect(self.surface, u_bar_bg, (W.x, W.y, W.width, 32), border_top_left_radius=8, border_top_right_radius=8)
            pygame.draw.line(self.surface, (55, 55, 62), (W.x, W.y + 32), (W.right, W.y + 32), 1)

            t_surf = self.font_md.render(title_text, True, u_title_col)
            self.surface.blit(t_surf, (W.x + 16, W.y + 7))

            # Controls: Minimize, Maximize
            pygame.draw.circle(self.surface, (55, 55, 62), (W.right - 68, W.y + 16), 8)
            pygame.draw.line(self.surface, (180, 180, 190), (W.right - 72, W.y + 16), (W.right - 64, W.y + 16), 1)
            pygame.draw.circle(self.surface, (55, 55, 62), (W.right - 46, W.y + 16), 8)
            pygame.draw.rect(self.surface, (180, 180, 190), (W.right - 49, W.y + 13, 6, 6), width=1)

            # Close Button
            is_close_hover = C.collidepoint(mx, my)
            c_bg = (235, 65, 45) if is_close_hover else (220, 80, 60)
            pygame.draw.circle(self.surface, c_bg, (C.centerx, C.centery), 9)
            cx, cy = C.centerx, C.centery
            pygame.draw.line(self.surface, (255, 255, 255), (cx - 3, cy - 3), (cx + 3, cy + 3), 1)
            pygame.draw.line(self.surface, (255, 255, 255), (cx - 3, cy + 3), (cx + 3, cy - 3), 1)

    def _render_browser_window(self):
        B = self.layout["browser"]
        W = self.layout["window_rect"]
        mx, my = self.hover_pos

        t_name = "Microsoft Edge" if self.is_windows else "Mozilla Firefox"
        self._render_window_frame(f"{t_name} - {self.browser_url}")

        # Navigation Bar Container
        nav_y = W.y + 32
        pygame.draw.rect(self.surface, (245, 247, 250), (W.x, nav_y, W.width, 36))
        pygame.draw.line(self.surface, (220, 225, 235), (W.x, nav_y + 36), (W.x + W.width, nav_y + 36), 1)

        # Nav Buttons (<, >, ↻)
        for btn_k, lbl in [("back_btn", "<"), ("forward_btn", ">"), ("refresh_btn", "@")]:
            rect = B[btn_k]
            is_h = rect.collidepoint(mx, my)
            if is_h:
                pygame.draw.rect(self.surface, (225, 232, 242), rect, border_radius=4)
            b_txt = self.font_md.render(lbl, True, (40, 55, 75) if is_h else (100, 115, 130))
            self.surface.blit(b_txt, (rect.x + (rect.width - b_txt.get_width()) // 2, rect.y + 4))

        # URL Input Bar
        u_rect = B["url_bar"]
        u_hover = u_rect.collidepoint(mx, my)
        u_border = (0, 115, 230) if self.browser_url_active else ((160, 180, 205) if u_hover else (200, 210, 225))
        pygame.draw.rect(self.surface, (255, 255, 255), u_rect, border_radius=4)
        pygame.draw.rect(self.surface, u_border, u_rect, width=1 if not self.browser_url_active else 2, border_radius=4)

        # Padlock icon
        pygame.draw.rect(self.surface, (10, 140, 50), (u_rect.x + 8, u_rect.y + 7, 10, 12), border_radius=2)

        # URL text with blinking cursor
        u_str = self.browser_input
        if self.browser_url_active and int(time.time() * 2) % 2 == 0:
            u_str += "|"
        u_surf = self.font_mono.render(u_str, True, (20, 30, 45))
        self.surface.blit(u_surf, (u_rect.x + 24, u_rect.y + 6))

        # Go Button
        g_rect = B["go_btn"]
        g_hover = g_rect.collidepoint(mx, my)
        g_bg = (20, 135, 250) if g_hover else (0, 115, 230)
        pygame.draw.rect(self.surface, g_bg, g_rect, border_radius=4)
        g_txt = self.font_sm.render("Go", True, (255, 255, 255))
        self.surface.blit(g_txt, (g_rect.x + (g_rect.width - g_txt.get_width()) // 2, g_rect.y + 6))

        # Bookmarks Bar Container
        bm_y = nav_y + 36
        pygame.draw.rect(self.surface, (238, 242, 248), (W.x, bm_y, W.width, 28))
        pygame.draw.line(self.surface, (215, 222, 232), (W.x, bm_y + 28), (W.x + W.width, bm_y + 28), 1)

        # Bookmarks Buttons
        self._draw_bookmark_button(B["bm_router"], "Router Admin (192.168.1.1)")
        self._draw_bookmark_button(B["bm_server"], "Web Server (192.168.1.10)")
        self._draw_bookmark_button(B["bm_asa"], "ASA ASDM (203.0.113.1)")
        self._draw_bookmark_button(B["bm_google"], "Google (8.8.8.8)")

        # Web Page Viewport Content
        C = B["content_rect"]
        pygame.draw.rect(self.surface, (255, 255, 255), C, border_bottom_left_radius=8, border_bottom_right_radius=8)

        if self.browser_page_status == "ERROR":
            self._render_browser_error(C.x, C.y, C.width, C.height)
        elif "192.168.1.1" in self.browser_url:
            self._render_cisco_router_web_page(C.x, C.y, C.width, C.height)
        elif "192.168.1.10" in self.browser_url:
            self._render_web_server_page(C.x, C.y, C.width, C.height)
        elif "203.0.113.1" in self.browser_url:
            self._render_asa_web_page(C.x, C.y, C.width, C.height)
        else:
            self._render_google_page(C.x, C.y, C.width, C.height)

    def _draw_bookmark_button(self, rect, title):
        mx, my = self.hover_pos
        is_hover = rect.collidepoint(mx, my)
        bg = (215, 225, 240) if is_hover else (228, 234, 244)
        border = (160, 185, 220) if is_hover else (205, 215, 230)

        pygame.draw.rect(self.surface, bg, rect, border_radius=3)
        pygame.draw.rect(self.surface, border, rect, width=1, border_radius=3)
        self.surface.blit(self.font_sm.render(title, True, (20, 35, 55) if is_hover else (45, 60, 80)), (rect.x + 6, rect.y + 3))

    def _render_browser_error(self, x, y, w, h):
        self.surface.blit(self.font_lg.render("This site can't be reached", True, (40, 45, 55)), (x + 40, y + 40))
        msg1 = f"{self.browser_url}'s server IP address could not be found or reached."
        self.surface.blit(self.font_md.render(msg1, True, (90, 100, 115)), (x + 40, y + 75))
        self.surface.blit(self.font_sm.render("Try:", True, (50, 60, 75)), (x + 40, y + 115))
        self.surface.blit(self.font_sm.render(" * Checking your network cable connection ([F] Key)", True, (80, 90, 105)), (x + 60, y + 140))
        self.surface.blit(self.font_sm.render(" * Checking IP address and Default Gateway in Network Settings", True, (80, 90, 105)), (x + 60, y + 165))
        self.surface.blit(self.font_sm.render(" * Checking Cisco NAT / PAT overload configuration on Router-01", True, (80, 90, 105)), (x + 60, y + 190))
        self.surface.blit(self.font_mono.render("ERR_CONNECTION_TIMED_OUT", True, (180, 40, 40)), (x + 40, y + 230))

    def _render_cisco_router_web_page(self, x, y, w, h):
        pygame.draw.rect(self.surface, (14, 32, 48), (x, y, w, 50))
        self.surface.blit(self.font_lg.render("CISCO ISR 4331 - Device Manager Web Console", True, (0, 200, 255)), (x + 25, y + 12))

        # Left Card: System Summary
        pygame.draw.rect(self.surface, (245, 248, 252), (x + 25, y + 65, 380, 190), border_radius=6)
        pygame.draw.rect(self.surface, (215, 225, 238), (x + 25, y + 65, 380, 190), width=1, border_radius=6)
        self.surface.blit(self.font_md.render("System Overview", True, (15, 45, 90)), (x + 40, y + 75))
        self.surface.blit(self.font_sm.render("Hostname: Router-01 (Cisco IOS-XE 17.3.4)", True, (50, 60, 75)), (x + 40, y + 105))
        self.surface.blit(self.font_sm.render("Uptime: 2 days, 14 hours, 32 mins", True, (50, 60, 75)), (x + 40, y + 130))
        self.surface.blit(self.font_sm.render("CPU Utilization: 6%   |   Memory Usage: 22%", True, (10, 140, 60)), (x + 40, y + 155))
        self.surface.blit(self.font_sm.render("NAT Engine: Overload Active (Inside: g0/0, Outside: g0/1)", True, (0, 110, 220)), (x + 40, y + 180))

        # Right Card: Interface States
        pygame.draw.rect(self.surface, (245, 248, 252), (x + 420, y + 65, 380, 190), border_radius=6)
        pygame.draw.rect(self.surface, (215, 225, 238), (x + 420, y + 65, 380, 190), width=1, border_radius=6)
        self.surface.blit(self.font_md.render("Port Status Summary", True, (15, 45, 90)), (x + 435, y + 75))
        self.surface.blit(self.font_mono.render("GigabitEthernet0/0:  192.168.1.1/24  [UP]", True, (10, 140, 50)), (x + 435, y + 105))
        self.surface.blit(self.font_mono.render("GigabitEthernet0/1:  203.0.113.2/24 [UP]", True, (10, 140, 50)), (x + 435, y + 130))
        self.surface.blit(self.font_mono.render("Default Route:      via 203.0.113.1 (ISP)", True, (30, 45, 60)), (x + 435, y + 155))

    def _render_web_server_page(self, x, y, w, h):
        pygame.draw.rect(self.surface, (30, 40, 55), (x, y, w, 50))
        self.surface.blit(self.font_lg.render("Enterprise Datacenter Intranet Portal - Web-Server-01", True, (255, 255, 255)), (x + 25, y + 14))

        pygame.draw.rect(self.surface, (240, 245, 252), (x + 30, y + 65, w - 60, 220), border_radius=8)
        self.surface.blit(self.font_md.render("Welcome to Internal Corporate Services", True, (20, 40, 70)), (x + 50, y + 80))
        self.surface.blit(self.font_sm.render("Host: Web-Server-01.corp.internal  (IP: 192.168.1.10)", True, (60, 75, 95)), (x + 50, y + 110))
        self.surface.blit(self.font_sm.render("Nginx Version: 1.24.0 (Ubuntu Linux)", True, (60, 75, 95)), (x + 50, y + 135))
        self.surface.blit(self.font_sm.render("Status: HTTP 200 OK  |  Database Cluster: CONNECTED", True, (10, 140, 50)), (x + 50, y + 160))
        self.surface.blit(self.font_sm.render("Active Services: ERP, CRM, Active Directory Sync, Gitlab", True, (30, 50, 75)), (x + 50, y + 185))

    def _render_asa_web_page(self, x, y, w, h):
        pygame.draw.rect(self.surface, (140, 20, 30), (x, y, w, 50))
        self.surface.blit(self.font_lg.render("Cisco Adaptive Security Appliance - ASDM Console", True, (255, 255, 255)), (x + 25, y + 14))

        pygame.draw.rect(self.surface, (252, 245, 245), (x + 30, y + 65, w - 60, 220), border_radius=8)
        self.surface.blit(self.font_md.render("Cisco ASA 5506-X Threat Defense", True, (120, 20, 30)), (x + 50, y + 80))
        self.surface.blit(self.font_sm.render("Management IP: 203.0.113.1  |  Status: ACTIVE", True, (50, 60, 75)), (x + 50, y + 110))
        self.surface.blit(self.font_sm.render("Security Zones: inside (sec: 100), outside (sec: 0), dmz (sec: 50)", True, (10, 130, 50)), (x + 50, y + 135))
        self.surface.blit(self.font_sm.render("Stateful Packet Inspection: ENABLED", True, (10, 130, 50)), (x + 50, y + 160))
        self.surface.blit(self.font_sm.render("Active Inbound ACL: OUTSIDE_IN applied on interface outside", True, (30, 45, 60)), (x + 50, y + 185))

    def _render_google_page(self, x, y, w, h):
        cx = x + w // 2
        self.surface.blit(self.font_lg.render("G o o g l e", True, (66, 133, 244)), (cx - 45, y + 50))
        sbox = pygame.Rect(cx - 180, y + 95, 360, 34)
        pygame.draw.rect(self.surface, (255, 255, 255), sbox, border_radius=17)
        pygame.draw.rect(self.surface, (210, 220, 230), sbox, width=1, border_radius=17)
        self.surface.blit(self.font_sm.render("Search Google or type a URL", True, (150, 160, 175)), (cx - 150, y + 104))

        badge = pygame.Rect(cx - 210, y + 165, 420, 48)
        pygame.draw.rect(self.surface, (235, 248, 238), badge, border_radius=8)
        pygame.draw.rect(self.surface, (150, 210, 160), badge, width=1, border_radius=8)
        self.surface.blit(self.font_md.render("Internet Connection: ONLINE", True, (15, 130, 50)), (cx - 190, y + 172))
        self.surface.blit(self.font_sm.render("Public IP Translation: 203.0.113.2 via Cisco NAT Overload (PAT)", True, (60, 80, 95)), (cx - 190, y + 192))

    def _render_network_window(self):
        N = self.layout["network"]
        W = self.layout["window_rect"]
        mx, my = self.hover_pos

        t_str = "Network & Internet > Ethernet Properties" if self.is_windows else "Settings > Network > Wired Connection"
        self._render_window_frame(t_str)

        # Status Summary Box
        p = self.device.eth0
        is_up = p and p.is_link_up
        stat_col = (10, 140, 50) if is_up else (190, 40, 40)
        stat_txt = "Connected (1000 Mbps Full Duplex)" if is_up else "Cable Unplugged (Link Down)"
        pygame.draw.rect(self.surface, (242, 246, 252), (W.x + 30, W.y + 44, W.width - 60, 56), border_radius=6)
        self.surface.blit(self.font_md.render("Adapter: Intel(R) Gigabit Ethernet (eth0)", True, (25, 35, 50)), (W.x + 45, W.y + 50))
        self.surface.blit(self.font_sm.render(f"Physical Status: {stat_txt}", True, stat_col), (W.x + 45, W.y + 74))

        # Form Fields
        fields = [
            ("IP Address:", self.net_ip, "ip", N["field_ip"]),
            ("Subnet Mask:", self.net_mask, "mask", N["field_mask"]),
            ("Default Gateway:", self.net_gw, "gw", N["field_gw"]),
            ("Preferred DNS:", self.net_dns, "dns", N["field_dns"]),
        ]

        for lbl, val, f_id, f_rect in fields:
            self.surface.blit(self.font_md.render(lbl, True, (40, 50, 65)), (W.x + 35, f_rect.y + 6))
            is_active = (self.active_field == f_id)
            is_hover = f_rect.collidepoint(mx, my)
            border_c = (0, 115, 230) if is_active else ((150, 180, 210) if is_hover else (200, 210, 225))

            pygame.draw.rect(self.surface, (255, 255, 255), f_rect, border_radius=4)
            pygame.draw.rect(self.surface, border_c, f_rect, width=2 if is_active else 1, border_radius=4)

            v_str = val
            if is_active and int(time.time() * 2) % 2 == 0:
                v_str += "|"
            self.surface.blit(self.font_mono.render(v_str, True, (20, 30, 40)), (f_rect.x + 8, f_rect.y + 7))

        # Apply Changes Button
        btn_r = N["btn_apply"]
        btn_hover = btn_r.collidepoint(mx, my)
        btn_bg = (20, 135, 250) if btn_hover else (0, 115, 230)
        pygame.draw.rect(self.surface, btn_bg, btn_r, border_radius=4)
        btn_txt = self.font_md.render("Apply Changes", True, (255, 255, 255))
        self.surface.blit(btn_txt, (btn_r.x + (btn_r.width - btn_txt.get_width()) // 2, btn_r.y + 8))

        # Banner message
        if self.settings_banner:
            b_surf = self.font_md.render(self.settings_banner, True, (10, 140, 50))
            self.surface.blit(b_surf, (W.x + 35, btn_r.bottom + 12))

    def _render_putty_window(self):
        P = self.layout["putty"]
        W = self.layout["window_rect"]
        mx, my = self.hover_pos

        t_label = "PuTTY - COM1 (9600 8-N-1)" if self.is_windows else "Minicom - /dev/ttyUSB0 (9600 8-N-1)"
        self._render_window_frame(t_label, title_col=(255, 255, 255), bar_bg=(30, 60, 140))

        if not self.putty_connected:
            # Error Dialog Box
            diag = pygame.Rect(W.x + 60, W.y + 60, W.width - 120, 220)
            pygame.draw.rect(self.surface, (255, 255, 255), diag, border_radius=8)
            pygame.draw.rect(self.surface, (200, 50, 50), diag, width=1, border_radius=8)

            t_err = "PuTTY Fatal Error" if self.is_windows else "Minicom Error"
            self.surface.blit(self.font_lg.render(t_err, True, (200, 30, 30)), (diag.x + 30, diag.y + 25))
            lines = self.putty_error_msg.split("\n")
            for i, l in enumerate(lines[1:]):
                self.surface.blit(self.font_sm.render(l, True, (50, 60, 75)), (diag.x + 30, diag.y + 65 + i * 22))

            # Retry Button
            r_rect = P["retry_btn"]
            r_hover = r_rect.collidepoint(mx, my)
            pygame.draw.rect(self.surface, (20, 135, 250) if r_hover else (0, 115, 230), r_rect, border_radius=4)
            r_txt = self.font_sm.render("Retry / Connect", True, (255, 255, 255))
            self.surface.blit(r_txt, (r_rect.x + (r_rect.width - r_txt.get_width()) // 2, r_rect.y + 9))
        else:
            # Active Cisco Terminal Viewport
            term_rect = P["term_rect"]
            pygame.draw.rect(self.surface, (12, 16, 22), term_rect, border_bottom_left_radius=8, border_bottom_right_radius=8)

            y = term_rect.y + 10
            for line in self.putty_history[-18:]:
                self.surface.blit(self.font_mono.render(line, True, (220, 230, 240)), (term_rect.x + 12, y))
                y += 18

            # Active Prompt with blinking cursor
            prompt = self.putty_terminal_executor.get_prompt()
            p_str = f"{prompt}{self.putty_input}"
            if int(time.time() * 2) % 2 == 0:
                p_str += "_"
            p_surf = self.font_mono.render(p_str, True, (50, 220, 100))
            self.surface.blit(p_surf, (term_rect.x + 12, y))

    def _render_terminal_window(self):
        T = self.layout["terminal"]
        W = self.layout["window_rect"]

        t_label = "Command Prompt (Administrator)" if self.is_windows else "engineer@ubuntu: ~ (bash)"
        self._render_window_frame(t_label, title_col=(220, 230, 240), bar_bg=(30, 36, 45))

        term_rect = T["term_rect"]
        pygame.draw.rect(self.surface, (12, 16, 22), term_rect, border_bottom_left_radius=8, border_bottom_right_radius=8)

        y = term_rect.y + 10
        for line in self.local_term_history[-18:]:
            self.surface.blit(self.font_mono.render(line, True, (215, 225, 235)), (term_rect.x + 12, y))
            y += 18

        # Active Prompt with blinking cursor
        prompt = "C:\\Users\\Engineer> " if self.is_windows else "engineer@ubuntu:~$ "
        p_str = f"{prompt}{self.local_term_input}"
        if int(time.time() * 2) % 2 == 0:
            p_str += "_"
        p_surf = self.font_mono.render(p_str, True, (255, 255, 255))
        self.surface.blit(p_surf, (term_rect.x + 12, y))
