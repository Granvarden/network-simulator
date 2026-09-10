"""
tests/test_laptop_gui.py - Automated Verification Suite for Dual-OS Engineer Laptops & Desktop GUI
Tests dual-laptop creation, 3D ports, Network Settings reconfiguration, Web Browser reachability,
PuTTY/Minicom serial rollover console sessions, and game mode integration.
"""

import os
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pygame
os.environ["SDL_VIDEODRIVER"] = "dummy"
pygame.init()
pygame.display.set_mode((1280, 720))

from network.host import Host
from network.switch import Switch
from network.cable import Cable, CableType
from ui.laptop_gui import LaptopGUI
from modes.tutorial_mode import TutorialMode
from modes.challenge_mode import ChallengeMode
from modes.sandbox_mode import SandboxMode

def test_dual_laptop_creation():
    print("[TEST] Dual Laptop Creation & 3D Port Geometry...")
    win_lap = Host("lap_win", hostname="Win-Laptop-01", device_type="laptop", os_type="windows")
    ubu_lap = Host("lap_ubu", hostname="Ubuntu-Laptop-02", device_type="laptop", os_type="ubuntu")

    assert win_lap.os_type == "windows"
    assert ubu_lap.os_type == "ubuntu"

    # Verify physical ports
    for lap in (win_lap, ubu_lap):
        assert "eth0" in lap.ports, "Laptop must have eth0 RJ45 port"
        assert "con0" in lap.ports, "Laptop must have con0 console port"
        assert lap.ports["eth0"].port_type == "RJ45"
        assert lap.ports["con0"].port_type == "CONSOLE"

        # Check port 3D coordinates
        p_eth = lap.get_port_local_pos("eth0")
        p_con = lap.get_port_local_pos("con0")
        assert p_eth[0] < 0, f"eth0 should be on left flank (x < 0), got {p_eth[0]}"
        assert p_con[0] > 0, f"con0 should be on right flank (x > 0), got {p_con[0]}"
        assert abs(p_eth[1] - 0.009) < 0.01, f"eth0 y position should align with chassis base: {p_eth[1]}"
        assert abs(p_con[1] - 0.009) < 0.01, f"con0 y position should align with chassis base: {p_con[1]}"

    print("  -> Dual laptops & 3D port coordinates verified successfully!")

def test_laptop_gui_rendering():
    print("[TEST] Laptop Desktop GUI Rendering (Windows 11 & Ubuntu 22.04 LTS)...")
    win_lap = Host("lap_win", hostname="Win-Laptop-01", device_type="laptop", os_type="windows")
    ubu_lap = Host("lap_ubu", hostname="Ubuntu-Laptop-02", device_type="laptop", os_type="ubuntu")

    gui_win = LaptopGUI(win_lap, 1280, 720)
    gui_ubu = LaptopGUI(ubu_lap, 1280, 720)

    gui_win.open()
    gui_ubu.open()

    surf_win = gui_win.render()
    surf_ubu = gui_ubu.render()

    assert isinstance(surf_win, pygame.Surface)
    assert isinstance(surf_ubu, pygame.Surface)
    assert surf_win.get_width() == gui_win.width
    assert surf_win.get_height() == gui_win.height
    print("  -> Laptop Desktop GUI rendering for Windows and Ubuntu verified!")

def test_network_settings_reconfiguration():
    print("[TEST] Network Settings IP Reconfiguration...")
    laptop = Host("lap_test", hostname="Win-Laptop-01", device_type="laptop", os_type="windows")
    laptop.configure_ip("192.168.1.50", "255.255.255.0", gateway="192.168.1.1", dns="8.8.8.8")

    gui = LaptopGUI(laptop, 1280, 720)
    gui.open()
    gui.active_app = "network_settings"
    gui._sync_network_fields()

    assert gui.net_ip == "192.168.1.50"
    assert gui.net_gw == "192.168.1.1"

    # User reconfigures IP
    gui.net_ip = "192.168.1.199"
    gui.net_mask = "255.255.255.128"
    gui.net_gw = "192.168.1.129"
    gui.net_dns = "1.1.1.1"
    gui.apply_network_settings()

    # Verify device ports and gateway are updated dynamically
    assert laptop.eth0.ip_address == "192.168.1.199"
    assert laptop.eth0.subnet_mask == "255.255.255.128"
    assert laptop.default_gateway == "192.168.1.129"
    assert laptop.dns_server == "1.1.1.1"
    assert gui.settings_banner is not None
    print("  -> Network Settings reconfiguration applied and verified dynamically!")

def test_web_browser():
    print("[TEST] Web Browser Application...")
    laptop = Host("lap_test", hostname="Win-Laptop-01", device_type="laptop", os_type="windows")
    laptop.configure_ip("192.168.1.99", "255.255.255.0", gateway="192.168.1.1")

    gui = LaptopGUI(laptop, 1280, 720)
    gui.open()
    gui.active_app = "browser"

    # 1. Navigate to unreachable address (no route, no cable)
    gui.navigate_browser("http://10.254.254.1")
    assert gui.browser_page_status == "ERROR", "Unreachable address should trigger browser error"

    # Render error page without crash
    surf = gui.render()
    assert isinstance(surf, pygame.Surface)

    # 2. Connect laptop to switch and switch to router with web server
    sw = Switch("sw1", hostname="Core-SW", num_ports=8)
    laptop.ports["eth0"].is_shutdown = False
    sw.ports["g0/1"].is_shutdown = False
    Cable(laptop.ports["eth0"], sw.ports["g0/1"], CableType.CAT6)

    server = Host("srv1", hostname="Web-Server-01", device_type="server")
    server.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")
    sw.ports["g0/2"].is_shutdown = False
    Cable(server.ports["eth0"], sw.ports["g0/2"], CableType.CAT6)

    # Now navigate to Web-Server-01
    gui.navigate_browser("http://192.168.1.10")
    assert gui.browser_page_status == "OK", "Connected Web Server should be reachable via browser"

    # Render web page
    surf_page = gui.render()
    assert isinstance(surf_page, pygame.Surface)
    print("  -> Web Browser navigation, reachability check, and rendering verified!")

def test_putty_serial_console():
    print("[TEST] PuTTY / Minicom Serial Console with Rollover Cable...")
    laptop = Host("lap_test", hostname="Win-Laptop-01", device_type="laptop", os_type="windows")
    sw = Switch("sw1", hostname="Core-Switch-01", num_ports=8)

    gui = LaptopGUI(laptop, 1280, 720)
    gui.open()
    gui.active_app = "putty"

    # 1. Not connected -> expect fatal error
    gui._try_connect_putty()
    assert not gui.putty_connected, "PuTTY should not connect without rollover cable"
    assert gui.putty_error_msg is not None

    # 2. Connect Console Rollover Cable from laptop con0 to switch con0
    cable = Cable(laptop.ports["con0"], sw.ports["con0"], CableType.CONSOLE)
    gui._try_connect_putty()
    assert gui.putty_connected, "PuTTY must connect when rollover cable is plugged into con0"
    assert gui.putty_target_device == sw

    # 3. Send CLI command through PuTTY
    event_cmd = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN, "unicode": ""})
    gui.putty_input = "enable"
    gui.handle_key(event_cmd)

    gui.putty_input = "show ip int brief"
    gui.handle_key(event_cmd)

    # Check output in history
    history_text = "\n".join(gui.putty_history)
    assert "Core-Switch-01#" in history_text
    assert "Interface" in history_text
    print("  -> PuTTY Serial Console connection and command execution verified!")

def test_game_modes_have_dual_laptops():
    print("[TEST] Game Modes Dual-Laptop Verification...")
    # 1. Tutorial Mode
    tut = TutorialMode()
    tut_laptops = [d for d in tut.devices if d.device_type == "laptop"]
    assert len(tut_laptops) == 2, f"Tutorial mode must have 2 laptops, found {len(tut_laptops)}"
    hostnames = [d.hostname for d in tut_laptops]
    assert "Win-Laptop-01" in hostnames
    assert "Ubuntu-Laptop-02" in hostnames
    assert hasattr(tut, "laptop_win")
    assert hasattr(tut, "laptop_ubu")

    # Verify console cable is pre-connected in tutorial mode
    con_cables = [c for c in tut.cables if c.cable_type == CableType.CONSOLE]
    assert len(con_cables) >= 1, "Tutorial mode should have pre-connected console cable"
    c = con_cables[0]
    assert c.port_a.device.device_type == "laptop" or c.port_b.device.device_type == "laptop"

    # 2. Challenge Mode
    chal = ChallengeMode()
    chal_laptops = [d for d in chal.devices if d.device_type == "laptop"]
    assert len(chal_laptops) == 2, f"Challenge mode must have 2 laptops, found {len(chal_laptops)}"

    # 3. Sandbox Mode
    sand = SandboxMode()
    sand_laptops = [d for d in sand.devices if d.device_type == "laptop"]
    assert len(sand_laptops) == 2, f"Sandbox mode must have 2 laptops, found {len(sand_laptops)}"

    print("  -> All game modes have dual Windows 11 & Ubuntu 22.04 laptops verified!")

def test_laptop_gui_click_hitboxes():
    print("[TEST] Laptop Desktop GUI Click Hitbox & Interaction Verification...")
    win_lap = Host("lap_win", hostname="Win-Laptop-01", device_type="laptop", os_type="windows")
    ubu_lap = Host("lap_ubu", hostname="Ubuntu-Laptop-02", device_type="laptop", os_type="ubuntu")

    gui_win = LaptopGUI(win_lap, 1280, 720)
    gui_win.open()
    L_win = gui_win.layout

    # 1. Test clicking Windows Desktop Icons (Edge, Settings, PuTTY, Terminal)
    edge_rect = L_win["desktop_icons"]["browser"]
    gui_win.handle_mouse_down((edge_rect.centerx, edge_rect.centery), 1)
    assert gui_win.active_app == "browser", "Clicking Edge desktop icon must open browser"

    close_btn = L_win["window_close_btn"]
    gui_win.handle_mouse_down((close_btn.centerx, close_btn.centery), 1)
    assert gui_win.active_app is None, "Clicking [X] must close active application"

    net_rect = L_win["desktop_icons"]["network_settings"]
    gui_win.handle_mouse_down((net_rect.centerx, net_rect.centery), 1)
    assert gui_win.active_app == "network_settings", "Clicking Settings desktop icon must open network settings"
    gui_win.handle_mouse_down((close_btn.centerx, close_btn.centery), 1)
    assert gui_win.active_app is None

    putty_rect = L_win["desktop_icons"]["putty"]
    gui_win.handle_mouse_down((putty_rect.centerx, putty_rect.centery), 1)
    assert gui_win.active_app == "putty", "Clicking PuTTY desktop icon must open putty"
    gui_win.handle_mouse_down((close_btn.centerx, close_btn.centery), 1)
    assert gui_win.active_app is None

    term_rect = L_win["desktop_icons"]["terminal"]
    gui_win.handle_mouse_down((term_rect.centerx, term_rect.centery), 1)
    assert gui_win.active_app == "terminal", "Clicking Terminal desktop icon must open terminal"
    gui_win.handle_mouse_down((close_btn.centerx, close_btn.centery), 1)
    assert gui_win.active_app is None

    # 2. Test Taskbar Icons and app-switching while window is open
    tb_icons = L_win["taskbar_icons"]
    gui_win.handle_mouse_down((tb_icons["browser"].centerx, tb_icons["browser"].centery), 1)
    assert gui_win.active_app == "browser", "Clicking Taskbar Edge must open browser"

    gui_win.handle_mouse_down((tb_icons["network_settings"].centerx, tb_icons["network_settings"].centery), 1)
    assert gui_win.active_app == "network_settings", "Clicking Taskbar Settings must switch directly to network settings"

    gui_win.handle_mouse_down((tb_icons["putty"].centerx, tb_icons["putty"].centery), 1)
    assert gui_win.active_app == "putty", "Clicking Taskbar PuTTY must switch directly to putty"

    gui_win.handle_mouse_down((tb_icons["terminal"].centerx, tb_icons["terminal"].centery), 1)
    assert gui_win.active_app == "terminal", "Clicking Taskbar Terminal must switch directly to terminal"

    gui_win.handle_mouse_down((tb_icons["start"].centerx, tb_icons["start"].centery), 1)
    assert gui_win.active_app is None, "Clicking Start button must return to desktop"

    # 3. Test Web Browser Controls (URL Bar, Go button, Bookmarks)
    gui_win.active_app = "browser"
    B = L_win["browser"]

    gui_win.handle_mouse_down((B["bm_router"].centerx, B["bm_router"].centery), 1)
    assert "192.168.1.1" in gui_win.browser_url

    gui_win.handle_mouse_down((B["bm_server"].centerx, B["bm_server"].centery), 1)
    assert "192.168.1.10" in gui_win.browser_url

    gui_win.handle_mouse_down((B["bm_asa"].centerx, B["bm_asa"].centery), 1)
    assert "203.0.113.1" in gui_win.browser_url

    gui_win.handle_mouse_down((B["bm_google"].centerx, B["bm_google"].centery), 1)
    assert "8.8.8.8" in gui_win.browser_url

    gui_win.handle_mouse_down((B["url_bar"].centerx, B["url_bar"].centery), 1)
    assert gui_win.browser_url_active is True, "Clicking URL bar must activate input"

    gui_win.browser_input = "http://192.168.1.200"
    gui_win.handle_mouse_down((B["go_btn"].centerx, B["go_btn"].centery), 1)
    assert gui_win.browser_url == "http://192.168.1.200", "Clicking Go button must navigate to typed URL"
    assert gui_win.browser_url_active is False

    # 4. Test Network Settings Form Inputs & Apply Button
    gui_win.active_app = "network_settings"
    N = L_win["network"]

    gui_win.handle_mouse_down((N["field_ip"].centerx, N["field_ip"].centery), 1)
    assert gui_win.active_field == "ip", "Clicking IP field must activate IP input"

    gui_win.handle_mouse_down((N["field_mask"].centerx, N["field_mask"].centery), 1)
    assert gui_win.active_field == "mask", "Clicking Mask field must activate mask input"

    gui_win.handle_mouse_down((N["field_gw"].centerx, N["field_gw"].centery), 1)
    assert gui_win.active_field == "gw", "Clicking GW field must activate gateway input"

    gui_win.handle_mouse_down((N["field_dns"].centerx, N["field_dns"].centery), 1)
    assert gui_win.active_field == "dns", "Clicking DNS field must activate dns input"

    gui_win.net_ip = "192.168.1.77"
    gui_win.handle_mouse_down((N["btn_apply"].centerx, N["btn_apply"].centery), 1)
    assert win_lap.eth0.ip_address == "192.168.1.77", "Clicking Apply Changes must update device IP"
    assert gui_win.settings_banner is not None

    # 5. Test Ubuntu Dock Launchers
    gui_ubu = LaptopGUI(ubu_lap, 1280, 720)
    gui_ubu.open()
    L_ubu = gui_ubu.layout
    d_icons = L_ubu["dock_icons"]

    gui_ubu.handle_mouse_down((d_icons["browser"].centerx, d_icons["browser"].centery), 1)
    assert gui_ubu.active_app == "browser", "Clicking Ubuntu Firefox dock icon must open browser"

    gui_ubu.handle_mouse_down((d_icons["network_settings"].centerx, d_icons["network_settings"].centery), 1)
    assert gui_ubu.active_app == "network_settings", "Clicking Ubuntu Settings dock icon must switch to settings"

    gui_ubu.handle_mouse_down((d_icons["putty"].centerx, d_icons["putty"].centery), 1)
    assert gui_ubu.active_app == "putty", "Clicking Ubuntu Minicom dock icon must switch to putty"

    gui_ubu.handle_mouse_down((d_icons["terminal"].centerx, d_icons["terminal"].centery), 1)
    assert gui_ubu.active_app == "terminal", "Clicking Ubuntu Terminal dock icon must switch to terminal"

    act_btn = L_ubu["activities_btn"]
    gui_ubu.handle_mouse_down((act_btn.centerx, act_btn.centery), 1)
    assert gui_ubu.active_app is None, "Clicking Activities button must minimize window"

    # 6. Test Detach Laptop button
    detach_btn = L_win["detach_btn"]
    gui_win.handle_mouse_down((detach_btn.centerx, detach_btn.centery), 1)
    assert gui_win.is_open is False, "Clicking Detach Laptop button must close laptop GUI"
    print("  -> All Laptop GUI Click Hitboxes, App Switching, and Form Inputs verified 100%!")

def test_continuous_backspace_repeat():
    print("[TEST] Continuous Backspace & Keyboard Auto-Repeat Verification...")
    win_lap = Host("lap_win", hostname="Win-Laptop-01", device_type="laptop", os_type="windows")
    gui_win = LaptopGUI(win_lap, 1280, 720)

    # 1. Opening Laptop GUI enables auto-repeat
    gui_win.open()
    repeat_delay, repeat_interval = pygame.key.get_repeat()
    assert repeat_delay > 0 and repeat_interval > 0, f"Key repeat must be active on open(), got: ({repeat_delay}, {repeat_interval})"

    # 2. Test continuous Backspace on Browser URL Bar
    gui_win.active_app = "browser"
    gui_win.browser_url_active = True
    gui_win.browser_input = "http://192.168.1.1"
    ev_backspace = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_BACKSPACE, "unicode": ""})

    # Simulate holding backspace (repeated KEYDOWN events)
    for _ in range(4):
        gui_win.handle_key(ev_backspace)
    assert gui_win.browser_input == "http://192.168", f"Expected 'http://192.168', got '{gui_win.browser_input}'"

    # Delete all remaining characters
    for _ in range(30):
        gui_win.handle_key(ev_backspace)
    assert gui_win.browser_input == "", f"Expected empty input after holding backspace, got '{gui_win.browser_input}'"

    # 3. Test continuous Backspace on Network Settings Fields
    gui_win.active_app = "network_settings"
    gui_win.active_field = "ip"
    gui_win.net_ip = "192.168.1.150"
    for _ in range(3):
        gui_win.handle_key(ev_backspace)
    assert gui_win.net_ip == "192.168.1.", f"Expected '192.168.1.', got '{gui_win.net_ip}'"

    gui_win.active_field = "mask"
    gui_win.net_mask = "255.255.255.0"
    for _ in range(20):
        gui_win.handle_key(ev_backspace)
    assert gui_win.net_mask == ""

    # 4. Closing Laptop GUI disables auto-repeat for 3D navigation
    gui_win.close()
    assert pygame.key.get_repeat() == (0, 0), "Key repeat must be disabled when laptop closes"

    # 5. Test TerminalUI key repeat and continuous backspace
    from cli.terminal_ui import TerminalUI
    term = TerminalUI(win_lap, 800, 500)
    term.open()
    assert pygame.key.get_repeat() != (0, 0), "Key repeat must be active when TerminalUI opens"

    term.input_buffer = "configure terminal"
    term.cursor_pos = len(term.input_buffer)
    for _ in range(9):
        term.handle_key(ev_backspace)
    assert term.input_buffer == "configure", f"Expected 'configure', got '{term.input_buffer}'"

    term.close()
    assert pygame.key.get_repeat() == (0, 0), "Key repeat must be disabled when TerminalUI closes"
    print("  -> Continuous Backspace and auto-repeat verified across all UI inputs!")

if __name__ == "__main__":
    test_dual_laptop_creation()
    test_laptop_gui_rendering()
    test_laptop_gui_click_hitboxes()
    test_continuous_backspace_repeat()
    test_network_settings_reconfiguration()
    test_web_browser()
    test_putty_serial_console()
    test_game_modes_have_dual_laptops()
    print("\n[SUCCESS] All Laptop & Desktop GUI test suites passed flawlessly!")

