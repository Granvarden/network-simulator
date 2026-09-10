"""
ui/laptop_gui.py - Interactive Laptop Desktop GUI for Windows 11 & Ubuntu 22.04 LTS
Provides realistic Desktop environments, Web Browser, Network Settings, and PuTTY/Minicom Serial Console.
All clickable elements use unified, single-source-of-truth pygame.Rect layout definitions.
"""

import pygame
import time
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

    def _render_windows_desktop(self):
        L = self.layout
        dx, dy, dw, dh = L["dx"], L["dy"], L["dw"], L["dh"]
        mx, my = self.hover_pos

        # Windows 11 Cyan Bloom Background Gradient
        for y in range(dh):
            prog = y / float(dh)
            r = int(18 + 25 * prog)
            g = int(58 + 70 * prog)
            b = int(130 + 95 * prog)
            pygame.draw.line(self.surface, (r, g, b), (dx, dy + y), (dx + dw, dy + y))

        # Bloom abstract floral petal art in center
        cx, cy = dx + dw // 2, dy + dh // 2 - 20
        pygame.draw.circle(self.surface, (70, 140, 240), (cx, cy), 130)
        pygame.draw.circle(self.surface, (110, 180, 255), (cx + 25, cy - 20), 90)
        pygame.draw.circle(self.surface, (160, 215, 255), (cx - 30, cy + 20), 75)

        # Desktop Icons
        self._draw_desktop_icon_box(L["desktop_icons"]["browser"], "Edge", (0, 120, 215), "WEB")
        self._draw_desktop_icon_box(L["desktop_icons"]["network_settings"], "Settings", (70, 80, 95), "NET")
        self._draw_desktop_icon_box(L["desktop_icons"]["putty"], "PuTTY", (20, 50, 160), "SER")
        self._draw_desktop_icon_box(L["desktop_icons"]["terminal"], "Terminal", (15, 15, 20), "CMD")

        # Windows 11 Center Taskbar (Frosted Acrylic blur)
        tb_r = L["taskbar_rect"]
        pygame.draw.rect(self.surface, (240, 245, 252), tb_r)
        pygame.draw.line(self.surface, (210, 220, 235), (tb_r.x, tb_r.y), (tb_r.x + tb_r.width, tb_r.y), 1)

        # Taskbar Buttons
        icons = L["taskbar_icons"]

        # Start
        self._draw_taskbar_button(icons["start"], (0, 120, 215), "WIN")
        # Search
        self._draw_taskbar_button(icons["search"], (90, 100, 115), "SRC")
        # Edge
        self._draw_taskbar_button(icons["browser"], (0, 120, 215), "WEB", is_active=(self.active_app == "browser"))
        # PuTTY
        self._draw_taskbar_button(icons["putty"], (20, 50, 160), "PUT", is_active=(self.active_app == "putty"))
        # Terminal
        self._draw_taskbar_button(icons["terminal"], (20, 20, 25), "CMD", is_active=(self.active_app == "terminal"))
        # Settings
        self._draw_taskbar_button(icons["network_settings"], (70, 80, 95), "NET", is_active=(self.active_app == "network_settings"))

        # System Tray (Time & Network)
        cur_time = time.strftime("%H:%M")
        t_surf = self.font_sm.render(cur_time, True, (30, 35, 45))
        self.surface.blit(t_surf, (dx + dw - 65, tb_r.y + 14))
        # Ethernet Connected Icon
        p = self.device.eth0
        net_col = (10, 140, 50) if (p and p.is_link_up) else (180, 40, 40)
        pygame.draw.rect(self.surface, net_col, (dx + dw - 95, tb_r.y + 16, 16, 12), border_radius=2)

    def _render_ubuntu_desktop(self):
        L = self.layout
        dx, dy, dw, dh = L["dx"], L["dy"], L["dw"], L["dh"]
        mx, my = self.hover_pos

        # Ubuntu 22.04 Aubergine / Jammy Gradient
        for y in range(dh):
            prog = y / float(dh)
            r = int(45 + 30 * prog)
            g = int(8 + 10 * prog)
            b = int(40 - 15 * prog)
            pygame.draw.line(self.surface, (r, g, b), (dx, dy + y), (dx + dw, dy + y))

        # Jammy geometric orange accent
        cx, cy = dx + dw // 2 + 80, dy + dh // 2
        pygame.draw.polygon(self.surface, (233, 84, 32), [
            (cx - 160, cy - 100), (cx + 120, cy - 150),
            (cx + 180, cy + 80), (cx - 60, cy + 160)
        ])

        # Top Bar (Ubuntu GNOME 42)
        top_r = L["topbar_rect"]
        pygame.draw.rect(self.surface, (16, 16, 18), top_r)

        # Activities button
        act_r = L["activities_btn"]
        act_hover = act_r.collidepoint(mx, my)
        if act_hover:
            pygame.draw.rect(self.surface, (45, 45, 50), act_r, border_radius=4)
        act_surf = self.font_sm.render("Activities", True, (255, 255, 255) if act_hover else (220, 220, 220))
        self.surface.blit(act_surf, (act_r.x + 8, act_r.y + 4))

        # Center Clock
        date_str = time.strftime("%b %d  %H:%M")
        c_surf = self.font_sm.render(date_str, True, (240, 240, 240))
        self.surface.blit(c_surf, (dx + dw // 2 - 40, top_r.y + 6))

        # Right Cluster
        p = self.device.eth0
        net_col = (70, 210, 80) if (p and p.is_link_up) else (210, 70, 60)
        pygame.draw.circle(self.surface, net_col, (dx + dw - 30, top_r.y + 14), 4)

        # Left Vertical Dock (Yaru Launcher)
        dock_r = L["dock_rect"]
        pygame.draw.rect(self.surface, (18, 18, 20), dock_r)
        pygame.draw.line(self.surface, (35, 35, 40), (dock_r.x + dock_r.width, dock_r.y), (dock_r.x + dock_r.width, dock_r.y + dock_r.height), 1)

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
        """Draws desktop app icon with smooth hover selection box."""
        mx, my = self.hover_pos
        is_hover = rect.collidepoint(mx, my)

        if is_hover:
            pygame.draw.rect(self.surface, (255, 255, 255, 45), rect, border_radius=6)
            pygame.draw.rect(self.surface, (255, 255, 255, 90), rect, width=1, border_radius=6)

        # Centered icon emblem
        ic_rect = pygame.Rect(rect.x + (rect.width - 40) // 2, rect.y + 4, 40, 40)
        pygame.draw.rect(self.surface, col, ic_rect, border_radius=8)
        tag_s = self.font_sm.render(tag, True, (255, 255, 255))
        self.surface.blit(tag_s, (ic_rect.x + (40 - tag_s.get_width()) // 2, ic_rect.y + 12))

        # Text label
        lbl_s = self.font_sm.render(label, True, (255, 255, 255))
        self.surface.blit(lbl_s, (rect.x + (rect.width - lbl_s.get_width()) // 2, rect.y + 48))

    def _draw_taskbar_button(self, rect, col, tag, is_active=False):
        """Draws a taskbar icon button with hover and active app pill indicator."""
        mx, my = self.hover_pos
        is_hover = rect.collidepoint(mx, my)

        if is_hover:
            pygame.draw.rect(self.surface, (220, 230, 245), rect, border_radius=4)

        ic_x = rect.x + (rect.width - 22) // 2
        ic_y = rect.y + (rect.height - 22) // 2
        if tag == "WIN":
            pygame.draw.rect(self.surface, col, (ic_x, ic_y, 22, 22), border_radius=3)
        elif tag == "SRC":
            pygame.draw.circle(self.surface, col, (rect.centerx, rect.centery), 9, 2)
        else:
            pygame.draw.rect(self.surface, col, (ic_x, ic_y, 22, 22), border_radius=4)
            tag_s = self.font_sm.render(tag[:2], True, (255, 255, 255))
            self.surface.blit(tag_s, (ic_x + 3, ic_y + 4))

        # Active indicator pill at bottom
        if is_active:
            pygame.draw.rect(self.surface, (0, 120, 215), (rect.x + 8, rect.bottom - 3, rect.width - 16, 2), border_radius=1)

    def _draw_dock_button(self, rect, col, tag, is_active=False):
        """Draws an Ubuntu dock button with hover and orange active dot indicator."""
        mx, my = self.hover_pos
        is_hover = rect.collidepoint(mx, my)

        if is_hover:
            pygame.draw.rect(self.surface, (45, 45, 50), rect, border_radius=8)

        pygame.draw.rect(self.surface, col, (rect.x + 2, rect.y + 2, 36, 36), border_radius=7)
        tag_s = self.font_sm.render(tag, True, (255, 255, 255))
        self.surface.blit(tag_s, (rect.x + 6, rect.y + 11))

        if is_active:
            # Orange indicator pip on left
            pygame.draw.rect(self.surface, (233, 84, 32), (rect.x - 5, rect.y + 14, 3, 12), border_radius=1)

    def _render_window_frame(self, title_text, title_col=(30, 45, 60), bar_bg=(235, 242, 250)):
        """Renders standard window chassis, titlebar, and close button."""
        W = self.layout["window_rect"]
        C = self.layout["window_close_btn"]
        mx, my = self.hover_pos

        # Window Box & Border
        pygame.draw.rect(self.surface, (252, 253, 255), W, border_radius=8)
        pygame.draw.rect(self.surface, (0, 115, 230), W, width=2, border_radius=8)

        # Title Bar
        pygame.draw.rect(self.surface, bar_bg, (W.x, W.y, W.width, 32), border_top_left_radius=8, border_top_right_radius=8)
        t_surf = self.font_md.render(title_text, True, title_col)
        self.surface.blit(t_surf, (W.x + 14, W.y + 7))

        # Close [X] Button with hover effect
        is_close_hover = C.collidepoint(mx, my)
        c_bg = (235, 40, 40) if is_close_hover else (220, 60, 60)
        pygame.draw.rect(self.surface, c_bg, C, border_radius=3)
        x_s = self.font_sm.render("X", True, (255, 255, 255))
        self.surface.blit(x_s, (C.x + (C.width - x_s.get_width()) // 2, C.y + (C.height - x_s.get_height()) // 2))

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
