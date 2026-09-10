"""
ui/laptop_gui.py - Interactive Laptop Desktop GUI for Windows 11 & Ubuntu 22.04 LTS
Provides realistic Desktop environments, Web Browser, Network Settings, and PuTTY/Minicom Serial Console.
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
            f"Microsoft Windows [Version 10.0.22631.3007]" if self.is_windows else "Ubuntu 22.04.4 LTS (Jammy Jellyfish)",
            f"(c) Microsoft Corporation. All rights reserved." if self.is_windows else f"Welcome to Ubuntu 22.04 LTS (GNU/Linux 6.5.0 generic)",
            f"Type 'ping <ip>', 'ipconfig' (or 'ifconfig'), 'traceroute <ip>', 'help'.",
            ""
        ]
        self.local_term_input = ""
        self.local_term_executor = CommandExecutor(self.device)

    def open(self):
        self.is_open = True
        self.active_app = None
        self.settings_banner = None
        self._sync_network_fields()

    def close(self):
        self.is_open = False

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

    def handle_mouse_down(self, pos, button):
        if not self.is_open or button != 1:
            return

        # Calculate local offset inside laptop window
        # (Assuming window is centered on screen)
        # Note: caller should pass local pos relative to laptop surface
        mx, my = pos

        # 1. Check close laptop button [ESC] at top right of laptop frame
        if self.width - 150 <= mx <= self.width - 10 and 4 <= my <= 32:
            self.close()
            self.sound.play_key()
            return

        # 2. Window close button [X] for active application
        if self.active_app is not None:
            # Window title bar is at Y=50..82, X=50..width-50
            wx = 60
            wy = 55
            ww = self.width - 120
            if wx + ww - 35 <= mx <= wx + ww - 8 and wy + 4 <= my <= wy + 26:
                # Close active app
                self.active_app = None
                self.sound.play_key()
                return

        # 3. Handle App-specific clicks
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

        # 4. Handle Desktop Icons and Taskbar clicks
        self._handle_desktop_and_taskbar_click(mx, my)

    def _handle_desktop_and_taskbar_click(self, mx, my):
        # Desktop Icons
        # Icon 1: Browser (X=40, Y=70, W=80, H=80)
        if 40 <= mx <= 120 and 70 <= my <= 150:
            self.active_app = "browser"
            self.sound.play_key()
            return
        # Icon 2: Network Settings (X=40, Y=170, W=80, H=80)
        if 40 <= mx <= 120 and 170 <= my <= 250:
            self.active_app = "network_settings"
            self._sync_network_fields()
            self.sound.play_key()
            return
        # Icon 3: PuTTY / Minicom (X=40, Y=270, W=80, H=80)
        if 40 <= mx <= 120 and 270 <= my <= 350:
            self.active_app = "putty"
            self._try_connect_putty()
            self.sound.play_key()
            return
        # Icon 4: Terminal / CMD (X=40, Y=370, W=80, H=80)
        if 40 <= mx <= 120 and 370 <= my <= 450:
            self.active_app = "terminal"
            self.sound.play_key()
            return

        # Taskbar / Dock clicks
        if self.is_windows:
            # Bottom Taskbar at Y = height - 48
            if my >= self.height - 48:
                cx = self.width // 2
                # Start / Search / Edge / PuTTY / Terminal / Settings
                if cx - 110 <= mx <= cx - 75:
                    self.active_app = None  # Start menu toggle
                elif cx - 70 <= mx <= cx - 35:
                    self.active_app = "browser"
                elif cx - 30 <= mx <= cx + 5:
                    self.active_app = "putty"
                    self._try_connect_putty()
                elif cx + 10 <= mx <= cx + 45:
                    self.active_app = "terminal"
                elif cx + 50 <= mx <= cx + 85:
                    self.active_app = "network_settings"
                self.sound.play_key()
        else:
            # Ubuntu Left Vertical Dock at X = 0..54
            if mx <= 54:
                if 50 <= my <= 100:
                    self.active_app = "browser"
                elif 105 <= my <= 155:
                    self.active_app = "putty"
                    self._try_connect_putty()
                elif 160 <= my <= 210:
                    self.active_app = "terminal"
                elif 215 <= my <= 265:
                    self.active_app = "network_settings"
                self.sound.play_key()

    def _handle_browser_click(self, mx, my):
        # URL bar click (X=140..width-200, Y=95..125)
        wx = 60
        wy = 55
        if wx + 90 <= mx <= wx + self.width - 260 and wy + 40 <= my <= wy + 68:
            self.browser_url_active = True
            self.sound.play_key()
            return
        else:
            self.browser_url_active = False

        # Go / Navigate button (X=width-160, Y=95..125)
        if wx + self.width - 250 <= mx <= wx + self.width - 200 and wy + 40 <= my <= wy + 68:
            self.navigate_browser(self.browser_input)
            self.sound.play_key()
            return

        # Bookmarks Bar:
        # Bookmark 1: Router Admin (192.168.1.1) (X=70..230, Y=132..155)
        if wx + 10 <= mx <= wx + 180 and wy + 72 <= my <= wy + 96:
            self.browser_input = "http://192.168.1.1"
            self.navigate_browser(self.browser_input)
            self.sound.play_key()
            return
        # Bookmark 2: Web Server (192.168.1.10) (X=240..390, Y=132..155)
        if wx + 190 <= mx <= wx + 360 and wy + 72 <= my <= wy + 96:
            self.browser_input = "http://192.168.1.10"
            self.navigate_browser(self.browser_input)
            self.sound.play_key()
            return
        # Bookmark 3: ASA ASDM (203.0.113.1)
        if wx + 370 <= mx <= wx + 540 and wy + 72 <= my <= wy + 96:
            self.browser_input = "https://203.0.113.1"
            self.navigate_browser(self.browser_input)
            self.sound.play_key()
            return
        # Bookmark 4: Google (8.8.8.8)
        if wx + 550 <= mx <= wx + 700 and wy + 72 <= my <= wy + 96:
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
        wx = 60
        wy = 55
        # Form fields:
        # IP Field: Y=wy+130..160
        if wx + 180 <= mx <= wx + 380 and wy + 130 <= my <= wy + 160:
            self.active_field = "ip"
            self.sound.play_key()
            return
        # Subnet Mask: Y=wy+175..205
        if wx + 180 <= mx <= wx + 380 and wy + 175 <= my <= wy + 205:
            self.active_field = "mask"
            self.sound.play_key()
            return
        # Default Gateway: Y=wy+220..250
        if wx + 180 <= mx <= wx + 380 and wy + 220 <= my <= wy + 250:
            self.active_field = "gw"
            self.sound.play_key()
            return
        # Preferred DNS: Y=wy+265..295
        if wx + 180 <= mx <= wx + 380 and wy + 265 <= my <= wy + 295:
            self.active_field = "dns"
            self.sound.play_key()
            return

        # Apply Settings Button: Y=wy+320..355
        if wx + 180 <= mx <= wx + 340 and wy + 320 <= my <= wy + 355:
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
        # Reconnect button on error dialog
        if not self.putty_connected:
            wx = 60
            wy = 55
            if wx + 150 <= mx <= wx + 270 and wy + 260 <= my <= wy + 295:
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
                self.sound.play_key()
            elif event.unicode and event.unicode.isprintable():
                self.browser_input += event.unicode
                self.sound.play_key()
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
                self.sound.play_key()
            elif event.unicode and (event.unicode.isdigit() or event.unicode == "."):
                if self.active_field == "ip": self.net_ip += event.unicode
                elif self.active_field == "mask": self.net_mask += event.unicode
                elif self.active_field == "gw": self.net_gw += event.unicode
                elif self.active_field == "dns": self.net_dns += event.unicode
                self.sound.play_key()
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
                self.sound.play_key()
            elif event.unicode and event.unicode.isprintable():
                self.putty_input += event.unicode
                self.sound.play_key()
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
                self.sound.play_key()
            elif event.unicode and event.unicode.isprintable():
                self.local_term_input += event.unicode
                self.sound.play_key()
            return

    def render(self):
        w, h = self.width, self.height
        self.surface.fill((0, 0, 0, 0))

        # 1. Outer Laptop Chassis & Screen Bezel (Matte Charcoal / Titanium)
        pygame.draw.rect(self.surface, (28, 30, 34), (0, 0, w, h), border_radius=12)
        pygame.draw.rect(self.surface, (50, 54, 60), (0, 0, w, h), width=2, border_radius=12)

        # Top Bezel: Webcam & Status LED
        pygame.draw.circle(self.surface, (15, 18, 22), (w // 2, 14), 5)
        pygame.draw.circle(self.surface, (0, 220, 100) if int(time.time()*2)%2==0 else (20, 40, 30), (w // 2 + 14, 14), 2)

        # Top Right Close Hint [ESC]
        close_btn = self.font_sm.render("[ESC] Detach Laptop", True, (160, 175, 195))
        self.surface.blit(close_btn, (w - 140, 8))

        # 2. Display Viewport (Inside bezel: X=12, Y=26, W=w-24, H=h-38)
        dw, dh = w - 24, h - 38
        dx, dy = 12, 26
        disp_rect = pygame.Rect(dx, dy, dw, dh)

        # Render OS Desktop Wallpaper
        if self.is_windows:
            self._render_windows_desktop(dx, dy, dw, dh)
        else:
            self._render_ubuntu_desktop(dx, dy, dw, dh)

        # 3. Render Active Application Window
        if self.active_app == "browser":
            self._render_browser_window(dx, dy, dw, dh)
        elif self.active_app == "network_settings":
            self._render_network_window(dx, dy, dw, dh)
        elif self.active_app == "putty":
            self._render_putty_window(dx, dy, dw, dh)
        elif self.active_app == "terminal":
            self._render_terminal_window(dx, dy, dw, dh)

        return self.surface

    def _render_windows_desktop(self, dx, dy, dw, dh):
        # Windows 11 Cyan Bloom Background Gradient
        for y in range(dh):
            prog = y / float(dh)
            r = int(18 + 25 * prog)
            g = int(58 + 70 * prog)
            b = int(130 + 95 * prog)
            pygame.draw.line(self.surface, (r, g, b), (dx, dy + y), (dx + dw, dy + y))

        # Bloom abstract floral petal art in center
        cx, cy = dx + dw // 2, dy + dh // 2 - 20
        pygame.draw.circle(self.surface, (70, 140, 240, 180), (cx, cy), 130)
        pygame.draw.circle(self.surface, (110, 180, 255, 200), (cx + 25, cy - 20), 90)
        pygame.draw.circle(self.surface, (160, 215, 255, 220), (cx - 30, cy + 20), 75)

        # Desktop Icons
        self._draw_desktop_icon(dx + 25, dy + 25, "Edge", (0, 120, 215), "WEB")
        self._draw_desktop_icon(dx + 25, dy + 115, "Settings", (70, 80, 95), "NET")
        self._draw_desktop_icon(dx + 25, dy + 205, "PuTTY", (20, 50, 160), "SER")
        self._draw_desktop_icon(dx + 25, dy + 295, "Terminal", (15, 15, 20), "CMD")

        # Windows 11 Center Taskbar (Frosted Acrylic blur)
        tb_h = 44
        tb_y = dy + dh - tb_h
        pygame.draw.rect(self.surface, (240, 245, 252, 235), (dx, tb_y, dw, tb_h))
        pygame.draw.line(self.surface, (210, 220, 235), (dx, tb_y), (dx + dw, tb_y), 1)

        # Center Icons Cluster
        tcx = dx + dw // 2
        # Win Logo
        pygame.draw.rect(self.surface, (0, 120, 215), (tcx - 90, tb_y + 11, 20, 20), border_radius=3)
        # Search
        pygame.draw.circle(self.surface, (90, 100, 115), (tcx - 55, tb_y + 21), 9, 2)
        # Edge
        pygame.draw.circle(self.surface, (0, 120, 215), (tcx - 20, tb_y + 21), 10)
        # PuTTY
        pygame.draw.rect(self.surface, (20, 50, 160), (tcx + 15, tb_y + 11, 20, 20), border_radius=3)
        # Terminal
        pygame.draw.rect(self.surface, (20, 20, 25), (tcx + 50, tb_y + 11, 20, 20), border_radius=3)
        # Settings
        pygame.draw.circle(self.surface, (70, 80, 95), (tcx + 85, tb_y + 21), 10)

        # System Tray (Time & Network)
        cur_time = time.strftime("%H:%M")
        t_surf = self.font_sm.render(cur_time, True, (30, 35, 45))
        self.surface.blit(t_surf, (dx + dw - 65, tb_y + 14))
        # Ethernet Connected Icon
        p = self.device.eth0
        net_col = (10, 140, 50) if (p and p.is_link_up) else (180, 40, 40)
        pygame.draw.rect(self.surface, net_col, (dx + dw - 95, tb_y + 16, 16, 12), border_radius=2)

    def _render_ubuntu_desktop(self, dx, dy, dw, dh):
        # Ubuntu 22.04 Aubergine / Jammy Gradient
        for y in range(dh):
            prog = y / float(dh)
            r = int(45 + 30 * prog)
            g = int(8 + 10 * prog)
            b = int(40 - 15 * prog)
            pygame.draw.line(self.surface, (r, g, b), (dx, dy + y), (dx + dw, dy + y))

        # Jammy geometric orange accent
        cx, cy = dx + dw // 2 + 80, dy + dh // 2
        pygame.draw.polygon(self.surface, (233, 84, 32, 40), [
            (cx - 160, cy - 100), (cx + 120, cy - 150),
            (cx + 180, cy + 80), (cx - 60, cy + 160)
        ])

        # Top Bar (Ubuntu GNOME)
        tb_h = 28
        pygame.draw.rect(self.surface, (16, 16, 18), (dx, dy, dw, tb_h))
        act_surf = self.font_sm.render("Activities", True, (240, 240, 240))
        self.surface.blit(act_surf, (dx + 16, dy + 6))
        # Center Clock
        date_str = time.strftime("%b %d  %H:%M")
        c_surf = self.font_sm.render(date_str, True, (240, 240, 240))
        self.surface.blit(c_surf, (dx + dw // 2 - 40, dy + 6))
        # Right Cluster
        p = self.device.eth0
        net_col = (70, 210, 80) if (p and p.is_link_up) else (210, 70, 60)
        pygame.draw.circle(self.surface, net_col, (dx + dw - 30, dy + 14), 4)

        # Left Vertical Dock (Yaru Launcher)
        dock_w = 54
        pygame.draw.rect(self.surface, (18, 18, 20, 240), (dx, dy + tb_h, dock_w, dh - tb_h))
        self._draw_dock_icon(dx + 9, dy + tb_h + 15, "Firefox", (233, 84, 32), "FOX")
        self._draw_dock_icon(dx + 9, dy + tb_h + 70, "Minicom", (0, 115, 230), "COM")
        self._draw_dock_icon(dx + 9, dy + tb_h + 125, "Terminal", (10, 10, 12), ">_")
        self._draw_dock_icon(dx + 9, dy + tb_h + 180, "Settings", (80, 80, 90), "NET")

    def _draw_desktop_icon(self, x, y, label, col, tag):
        pygame.draw.rect(self.surface, col, (x + 10, y, 40, 40), border_radius=8)
        tag_s = self.font_sm.render(tag, True, (255, 255, 255))
        self.surface.blit(tag_s, (x + 16, y + 12))
        lbl_s = self.font_sm.render(label, True, (245, 250, 255))
        self.surface.blit(lbl_s, (x + 2, y + 44))

    def _draw_dock_icon(self, x, y, label, col, tag):
        pygame.draw.rect(self.surface, col, (x, y, 36, 36), border_radius=7)
        tag_s = self.font_sm.render(tag, True, (255, 255, 255))
        self.surface.blit(tag_s, (x + 6, y + 10))

    def _render_browser_window(self, dx, dy, dw, dh):
        wx = dx + 50
        wy = dy + 35
        ww = dw - 100
        wh = dh - 85

        # Window Box & Shadow
        pygame.draw.rect(self.surface, (250, 252, 255), (wx, wy, ww, wh), border_radius=8)
        pygame.draw.rect(self.surface, (0, 115, 230), (wx, wy, ww, wh), width=2, border_radius=8)

        # Title Bar
        pygame.draw.rect(self.surface, (235, 242, 250), (wx, wy, ww, 34), border_top_left_radius=8, border_top_right_radius=8)
        t_name = "Microsoft Edge" if self.is_windows else "Mozilla Firefox"
        title_s = self.font_md.render(f"{t_name} - {self.browser_url}", True, (30, 45, 60))
        self.surface.blit(title_s, (wx + 16, wy + 8))

        # Close [X]
        pygame.draw.rect(self.surface, (220, 50, 50), (wx + ww - 28, wy + 6, 20, 20), border_radius=3)
        x_s = self.font_sm.render("X", True, (255, 255, 255))
        self.surface.blit(x_s, (wx + ww - 22, wy + 8))

        # URL Navigation Bar
        nav_y = wy + 38
        pygame.draw.rect(self.surface, (245, 247, 250), (wx, nav_y, ww, 36))
        # Nav Buttons (< > R)
        self.surface.blit(self.font_md.render("<", True, (100, 115, 130)), (wx + 15, nav_y + 8))
        self.surface.blit(self.font_md.render(">", True, (100, 115, 130)), (wx + 35, nav_y + 8))
        self.surface.blit(self.font_md.render("@", True, (100, 115, 130)), (wx + 55, nav_y + 8))

        # URL Input Box
        url_rect = pygame.Rect(wx + 80, nav_y + 5, ww - 150, 26)
        u_border = (0, 115, 230) if self.browser_url_active else (190, 205, 220)
        pygame.draw.rect(self.surface, (255, 255, 255), url_rect, border_radius=4)
        pygame.draw.rect(self.surface, u_border, url_rect, width=1, border_radius=4)
        u_surf = self.font_mono.render(self.browser_input, True, (20, 30, 45))
        self.surface.blit(u_surf, (wx + 88, nav_y + 9))

        # Go Button
        go_rect = pygame.Rect(wx + ww - 60, nav_y + 5, 48, 26)
        pygame.draw.rect(self.surface, (0, 115, 230), go_rect, border_radius=4)
        self.surface.blit(self.font_sm.render("Go", True, (255, 255, 255)), (wx + ww - 44, nav_y + 9))

        # Bookmarks Bar
        bm_y = nav_y + 36
        pygame.draw.rect(self.surface, (238, 242, 248), (wx, bm_y, ww, 26))
        self._draw_bookmark(wx + 10, bm_y + 3, "Router Admin (192.168.1.1)")
        self._draw_bookmark(wx + 190, bm_y + 3, "Web Server (192.168.1.10)")
        self._draw_bookmark(wx + 370, bm_y + 3, "ASA ASDM (203.0.113.1)")
        self._draw_bookmark(wx + 540, bm_y + 3, "Google (8.8.8.8)")

        # Page Content Area
        cy = bm_y + 26
        ch = wh - (cy - wy)
        c_rect = pygame.Rect(wx, cy, ww, ch)
        pygame.draw.rect(self.surface, (255, 255, 255), c_rect, border_bottom_left_radius=8, border_bottom_right_radius=8)

        if self.browser_page_status == "ERROR":
            self._render_browser_error(wx, cy, ww, ch)
        elif "192.168.1.1" in self.browser_url:
            self._render_cisco_router_web_page(wx, cy, ww, ch)
        elif "192.168.1.10" in self.browser_url:
            self._render_web_server_page(wx, cy, ww, ch)
        elif "203.0.113.1" in self.browser_url:
            self._render_asa_web_page(wx, cy, ww, ch)
        else:
            self._render_google_page(wx, cy, ww, ch)

    def _draw_bookmark(self, x, y, title):
        pygame.draw.rect(self.surface, (225, 232, 242), (x, y, len(title)*7 + 10, 20), border_radius=3)
        self.surface.blit(self.font_sm.render(title, True, (40, 55, 75)), (x + 5, y + 2))

    def _render_browser_error(self, x, y, w, h):
        self.surface.blit(self.font_lg.render("This site can't be reached", True, (40, 45, 55)), (x + 40, y + 50))
        msg1 = f"{self.browser_url}'s server IP address could not be found or reached."
        self.surface.blit(self.font_md.render(msg1, True, (90, 100, 115)), (x + 40, y + 90))
        self.surface.blit(self.font_sm.render("Try:", True, (50, 60, 75)), (x + 40, y + 130))
        self.surface.blit(self.font_sm.render(" * Checking your network cable connection ([F] Key)", True, (80, 90, 105)), (x + 60, y + 155))
        self.surface.blit(self.font_sm.render(" * Checking IP address and Default Gateway in Network Settings", True, (80, 90, 105)), (x + 60, y + 180))
        self.surface.blit(self.font_sm.render(" * Checking Cisco NAT / PAT overload configuration on Router-01", True, (80, 90, 105)), (x + 60, y + 205))
        self.surface.blit(self.font_mono.render("ERR_CONNECTION_TIMED_OUT", True, (180, 40, 40)), (x + 40, y + 250))

    def _render_cisco_router_web_page(self, x, y, w, h):
        # Header banner (Cisco ISR Web Admin)
        pygame.draw.rect(self.surface, (14, 32, 48), (x, y, w, 55))
        self.surface.blit(self.font_lg.render("CISCO ISR 4331 - Device Manager Web Console", True, (0, 200, 255)), (x + 25, y + 15))

        # Dashboard Grid
        # Left Card: System Summary
        pygame.draw.rect(self.surface, (245, 248, 252), (x + 25, y + 75, 380, 200), border_radius=6)
        pygame.draw.rect(self.surface, (215, 225, 238), (x + 25, y + 75, 380, 200), width=1, border_radius=6)
        self.surface.blit(self.font_md.render("System Overview", True, (15, 45, 90)), (x + 40, y + 88))
        self.surface.blit(self.font_sm.render("Hostname: Router-01 (Cisco IOS-XE 17.3.4)", True, (50, 60, 75)), (x + 40, y + 120))
        self.surface.blit(self.font_sm.render("Uptime: 2 days, 14 hours, 32 mins", True, (50, 60, 75)), (x + 40, y + 145))
        self.surface.blit(self.font_sm.render("CPU Utilization: 6%   |   Memory Usage: 22%", True, (10, 140, 60)), (x + 40, y + 170))
        self.surface.blit(self.font_sm.render("NAT Engine: Overload Active (Inside: g0/0, Outside: g0/1)", True, (0, 110, 220)), (x + 40, y + 195))

        # Right Card: Interface States
        pygame.draw.rect(self.surface, (245, 248, 252), (x + 430, y + 75, 420, 200), border_radius=6)
        pygame.draw.rect(self.surface, (215, 225, 238), (x + 430, y + 75, 420, 200), width=1, border_radius=6)
        self.surface.blit(self.font_md.render("Port Status Summary", True, (15, 45, 90)), (x + 445, y + 88))
        self.surface.blit(self.font_mono.render("GigabitEthernet0/0:  192.168.1.1/24  [UP / RUNNING]", True, (10, 140, 50)), (x + 445, y + 120))
        self.surface.blit(self.font_mono.render("GigabitEthernet0/1:  203.0.113.2/24 [UP / RUNNING]", True, (10, 140, 50)), (x + 445, y + 150))
        self.surface.blit(self.font_mono.render("Default Route:      via 203.0.113.1 (ISP Uplink)", True, (30, 45, 60)), (x + 445, y + 180))

        # Bottom diagnostics hint
        self.surface.blit(self.font_sm.render("Network health normal. All interfaces passing telemetry.", True, (100, 115, 130)), (x + 25, y + 300))

    def _render_web_server_page(self, x, y, w, h):
        pygame.draw.rect(self.surface, (30, 40, 55), (x, y, w, 50))
        self.surface.blit(self.font_lg.render("Enterprise Datacenter Intranet Portal - Web-Server-01", True, (255, 255, 255)), (x + 25, y + 14))

        pygame.draw.rect(self.surface, (240, 245, 252), (x + 30, y + 70, w - 60, 240), border_radius=8)
        self.surface.blit(self.font_md.render("Welcome to Internal Corporate Services", True, (20, 40, 70)), (x + 50, y + 90))
        self.surface.blit(self.font_sm.render("Host: Web-Server-01.corp.internal  (IP: 192.168.1.10)", True, (60, 75, 95)), (x + 50, y + 120))
        self.surface.blit(self.font_sm.render("Nginx Version: 1.24.0 (Ubuntu Linux)", True, (60, 75, 95)), (x + 50, y + 145))
        self.surface.blit(self.font_sm.render("Status: HTTP 200 OK  |  Database Cluster: CONNECTED", True, (10, 140, 50)), (x + 50, y + 170))
        self.surface.blit(self.font_sm.render("Active Services: ERP, CRM, Active Directory Sync, Gitlab", True, (30, 50, 75)), (x + 50, y + 195))

    def _render_asa_web_page(self, x, y, w, h):
        pygame.draw.rect(self.surface, (140, 20, 30), (x, y, w, 50))
        self.surface.blit(self.font_lg.render("Cisco Adaptive Security Appliance - ASDM Console", True, (255, 255, 255)), (x + 25, y + 14))

        pygame.draw.rect(self.surface, (252, 245, 245), (x + 30, y + 70, w - 60, 240), border_radius=8)
        self.surface.blit(self.font_md.render("Cisco ASA 5506-X Threat Defense", True, (120, 20, 30)), (x + 50, y + 90))
        self.surface.blit(self.font_sm.render("Management IP: 203.0.113.1  |  Status: ACTIVE", True, (50, 60, 75)), (x + 50, y + 120))
        self.surface.blit(self.font_sm.render("Security Zones: inside (sec: 100), outside (sec: 0), dmz (sec: 50)", True, (10, 130, 50)), (x + 50, y + 145))
        self.surface.blit(self.font_sm.render("Stateful Packet Inspection: ENABLED", True, (10, 130, 50)), (x + 50, y + 170))
        self.surface.blit(self.font_sm.render("Active Inbound ACL: OUTSIDE_IN applied on interface outside", True, (30, 45, 60)), (x + 50, y + 195))

    def _render_google_page(self, x, y, w, h):
        cx = x + w // 2
        # Colorful Google text
        self.surface.blit(self.font_lg.render("G o o g l e", True, (66, 133, 244)), (cx - 50, y + 60))
        # Search Box
        sbox = pygame.Rect(cx - 180, y + 110, 360, 36)
        pygame.draw.rect(self.surface, (255, 255, 255), sbox, border_radius=18)
        pygame.draw.rect(self.surface, (210, 220, 230), sbox, width=1, border_radius=18)
        self.surface.blit(self.font_sm.render("Search Google or type a URL", True, (150, 160, 175)), (cx - 150, y + 120))

        # Status Badge
        badge = pygame.Rect(cx - 210, y + 190, 420, 50)
        pygame.draw.rect(self.surface, (235, 248, 238), badge, border_radius=8)
        pygame.draw.rect(self.surface, (150, 210, 160), badge, width=1, border_radius=8)
        self.surface.blit(self.font_md.render("Internet Connection: ONLINE", True, (15, 130, 50)), (cx - 190, y + 196))
        self.surface.blit(self.font_sm.render("Public IP Translation: 203.0.113.2 via Cisco NAT Overload (PAT)", True, (60, 80, 95)), (cx - 190, y + 218))

    def _render_network_window(self, dx, dy, dw, dh):
        wx = dx + 80
        wy = dy + 40
        ww = dw - 160
        wh = dh - 95

        pygame.draw.rect(self.surface, (252, 253, 255), (wx, wy, ww, wh), border_radius=8)
        pygame.draw.rect(self.surface, (0, 115, 230), (wx, wy, ww, wh), width=2, border_radius=8)

        # Title
        pygame.draw.rect(self.surface, (235, 242, 250), (wx, wy, ww, 34), border_top_left_radius=8, border_top_right_radius=8)
        t_str = "Network & Internet > Ethernet Properties" if self.is_windows else "Settings > Network > Wired Connection"
        self.surface.blit(self.font_md.render(t_str, True, (20, 35, 55)), (wx + 16, wy + 8))

        # Close [X]
        pygame.draw.rect(self.surface, (220, 50, 50), (wx + ww - 28, wy + 6, 20, 20), border_radius=3)
        self.surface.blit(self.font_sm.render("X", True, (255, 255, 255)), (wx + ww - 22, wy + 8))

        # Status Summary Box
        p = self.device.eth0
        is_up = p and p.is_link_up
        stat_col = (10, 140, 50) if is_up else (190, 40, 40)
        stat_txt = "Connected (1000 Mbps Full Duplex)" if is_up else "Cable Unplugged (Link Down)"
        pygame.draw.rect(self.surface, (242, 246, 252), (wx + 30, wy + 50, ww - 60, 60), border_radius=6)
        self.surface.blit(self.font_md.render(f"Adapter: Intel(R) Gigabit Ethernet (eth0)", True, (25, 35, 50)), (wx + 45, wy + 58))
        self.surface.blit(self.font_sm.render(f"Physical Status: {stat_txt}", True, stat_col), (wx + 45, wy + 84))

        # Form
        fields = [
            ("IP Address:", self.net_ip, "ip", wy + 130),
            ("Subnet Mask:", self.net_mask, "mask", wy + 175),
            ("Default Gateway:", self.net_gw, "gw", wy + 220),
            ("Preferred DNS:", self.net_dns, "dns", wy + 265),
        ]

        for lbl, val, f_id, fy in fields:
            self.surface.blit(self.font_md.render(lbl, True, (40, 50, 65)), (wx + 45, fy + 5))
            f_rect = pygame.Rect(wx + 180, fy, 220, 28)
            border_c = (0, 115, 230) if self.active_field == f_id else (190, 205, 220)
            pygame.draw.rect(self.surface, (255, 255, 255), f_rect, border_radius=4)
            pygame.draw.rect(self.surface, border_c, f_rect, width=1, border_radius=4)
            self.surface.blit(self.font_mono.render(val, True, (20, 30, 40)), (wx + 188, fy + 6))

        # Apply Button
        btn_rect = pygame.Rect(wx + 180, wy + 315, 160, 36)
        pygame.draw.rect(self.surface, (0, 115, 230), btn_rect, border_radius=4)
        self.surface.blit(self.font_md.render("Apply Changes", True, (255, 255, 255)), (wx + 205, wy + 323))

        # Banner message
        if self.settings_banner:
            b_surf = self.font_md.render(self.settings_banner, True, (10, 140, 50))
            self.surface.blit(b_surf, (wx + 45, wy + 365))

    def _render_putty_window(self, dx, dy, dw, dh):
        wx = dx + 60
        wy = dy + 40
        ww = dw - 120
        wh = dh - 90

        pygame.draw.rect(self.surface, (245, 247, 250), (wx, wy, ww, wh), border_radius=8)
        pygame.draw.rect(self.surface, (30, 60, 140), (wx, wy, ww, wh), width=2, border_radius=8)

        # Title Bar
        pygame.draw.rect(self.surface, (30, 60, 140), (wx, wy, ww, 30), border_top_left_radius=8, border_top_right_radius=8)
        t_label = "PuTTY - COM1 (9600 8-N-1)" if self.is_windows else "Minicom - /dev/ttyUSB0 (9600 8-N-1)"
        self.surface.blit(self.font_sm.render(t_label, True, (255, 255, 255)), (wx + 14, wy + 7))

        # Close [X]
        pygame.draw.rect(self.surface, (220, 50, 50), (wx + ww - 26, wy + 5, 20, 20), border_radius=3)
        self.surface.blit(self.font_sm.render("X", True, (255, 255, 255)), (wx + ww - 20, wy + 7))

        if not self.putty_connected:
            # Error Dialog Box
            diag = pygame.Rect(wx + 80, wy + 80, ww - 160, 220)
            pygame.draw.rect(self.surface, (255, 255, 255), diag, border_radius=8)
            pygame.draw.rect(self.surface, (200, 50, 50), diag, width=1, border_radius=8)
            self.surface.blit(self.font_lg.render("PuTTY Fatal Error" if self.is_windows else "Minicom Error", True, (200, 30, 30)), (wx + 110, wy + 105))
            lines = self.putty_error_msg.split("\n")
            for i, l in enumerate(lines[1:]):
                self.surface.blit(self.font_sm.render(l, True, (50, 60, 75)), (wx + 110, wy + 145 + i * 22))

            # Retry Button
            r_rect = pygame.Rect(wx + 150, wy + 245, 120, 32)
            pygame.draw.rect(self.surface, (0, 115, 230), r_rect, border_radius=4)
            self.surface.blit(self.font_sm.render("Retry / Connect", True, (255, 255, 255)), (wx + 165, wy + 252))
        else:
            # Active Cisco Terminal Viewport
            term_rect = pygame.Rect(wx + 8, wy + 34, ww - 16, wh - 42)
            pygame.draw.rect(self.surface, (12, 16, 22), term_rect)

            y = wy + 42
            for line in self.putty_history[-20:]:
                self.surface.blit(self.font_mono.render(line, True, (220, 230, 240)), (wx + 16, y))
                y += 18

            # Active Prompt
            prompt = self.putty_terminal_executor.get_prompt()
            p_surf = self.font_mono.render(f"{prompt}{self.putty_input}", True, (50, 220, 100))
            self.surface.blit(p_surf, (wx + 16, y))

    def _render_terminal_window(self, dx, dy, dw, dh):
        wx = dx + 60
        wy = dy + 40
        ww = dw - 120
        wh = dh - 90

        pygame.draw.rect(self.surface, (12, 16, 22), (wx, wy, ww, wh), border_radius=8)
        pygame.draw.rect(self.surface, (50, 60, 75), (wx, wy, ww, wh), width=1, border_radius=8)

        # Title Bar
        pygame.draw.rect(self.surface, (30, 36, 45), (wx, wy, ww, 30), border_top_left_radius=8, border_top_right_radius=8)
        t_label = "Command Prompt (Administrator)" if self.is_windows else "engineer@ubuntu: ~ (bash)"
        self.surface.blit(self.font_sm.render(t_label, True, (220, 230, 240)), (wx + 14, wy + 7))

        # Close [X]
        pygame.draw.rect(self.surface, (200, 50, 50), (wx + ww - 26, wy + 5, 20, 20), border_radius=3)
        self.surface.blit(self.font_sm.render("X", True, (255, 255, 255)), (wx + ww - 20, wy + 7))

        y = wy + 40
        for line in self.local_term_history[-22:]:
            self.surface.blit(self.font_mono.render(line, True, (215, 225, 235)), (wx + 16, y))
            y += 18

        # Active Prompt
        prompt = "C:\\Users\\Engineer> " if self.is_windows else "engineer@ubuntu:~$ "
        p_surf = self.font_mono.render(f"{prompt}{self.local_term_input}", True, (255, 255, 255))
        self.surface.blit(p_surf, (wx + 16, y))
