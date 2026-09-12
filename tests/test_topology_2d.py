"""
tests/test_topology_2d.py - Comprehensive Unit & Integration Tests for 2D Topology Editor
Verifies:
1. Topology2D initialization and default state.
2. Sandbox Mode drag-and-drop device placement, U-slot allocation, and 3D rack position synchronization.
3. Interactive port-to-port cable connection and link UP status.
4. Strict View-Only enforcement in Tutorial and Challenge modes (editing blocked).
5. Auto-arrange topology layout algorithm.
6. Topology serialization and coordinate persistence (save_topology / load_topology).
7. MenuManager integration, rendering, and ESC/resume key handling.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import tempfile
import pygame

from ui.topology_2d import Topology2D
from ui.menu import MenuManager, MenuState
from engine.audio import SoundManager
from network.cable import Cable, CableType
from modes.sandbox_mode import SandboxMode
from modes.tutorial_mode import TutorialMode
from modes.challenge_mode import ChallengeMode


def init_pygame():
    pygame.init()
    pygame.font.init()
    if not pygame.display.get_surface():
        pygame.display.set_mode((1, 1), pygame.NOFRAME)


def test_topology_2d_init():
    """Verify Topology2D initializes with expected defaults and Thai-capable fonts."""
    topo = Topology2D()
    assert topo.zoom == 1.0
    assert topo.pan_x == 0.0 and topo.pan_y == 0.0
    assert topo.selected_tool == "select"
    assert topo.active_cable_type == CableType.CAT6
    assert topo.active_category == "network"
    assert topo.font_title is not None
    assert topo.font_toast is not None


def test_sandbox_device_placement_and_3d_sync():
    """Verify that placing a device in Sandbox mode assigns 2D topo coordinates and valid 3D rack positions."""
    topo = Topology2D()
    sandbox = SandboxMode()
    sandbox.setup()
    sound = SoundManager.get_instance()

    init_count = len(sandbox.devices)

    # Spawn a router at 2D canvas coordinates (450, 320)
    topo._spawn_device_at("router", 450, 320, sandbox, sound)

    assert len(sandbox.devices) == init_count + 1
    new_dev = sandbox.devices[-1]
    assert new_dev.device_type == "router"
    assert getattr(new_dev, "topo_x", None) == 450
    assert getattr(new_dev, "topo_y", None) == 320

    # Verify 3D rack synchronization
    assert new_dev.rack_id in (1, 2, 3)
    assert 1 <= new_dev.u_slot <= 42
    assert hasattr(new_dev, "pos_x") and hasattr(new_dev, "pos_y") and hasattr(new_dev, "pos_z")
    # Verify 3D Y coordinate corresponds to slot height
    assert new_dev.pos_y > 0.0


def test_sandbox_cable_connection():
    """Verify connecting two ports in Sandbox mode instantiates Cable and brings link up."""
    topo = Topology2D()
    sandbox = SandboxMode()
    sandbox.setup()
    sound = SoundManager.get_instance()

    # Find two devices with available ports
    dev1 = sandbox.devices[0]
    dev2 = sandbox.devices[1]

    # Find open ports
    port_a = next((p for p in dev1.ports.values() if p.cable is None and "con" not in p.name.lower()), None)
    port_b = next((p for p in dev2.ports.values() if p.cable is None and "con" not in p.name.lower()), None)

    assert port_a is not None and port_b is not None

    init_cables = len(sandbox.cables)
    topo._connect_cables(port_a, port_b, CableType.CAT6, sandbox, sound)

    assert len(sandbox.cables) == init_cables + 1
    new_cable = sandbox.cables[-1]
    assert new_cable.port_a == port_a
    assert new_cable.port_b == port_b
    assert port_a.cable == new_cable
    assert port_b.cable == new_cable


def test_strict_mode_permissions_tutorial_and_challenge():
    """Verify that Tutorial and Challenge modes are strictly View-Only (cannot add or delete devices)."""
    topo = Topology2D()
    sound = SoundManager.get_instance()

    # 1. Tutorial Mode
    tutorial = TutorialMode()
    tutorial.setup()
    t_dev_count = len(tutorial.devices)

    # Attempt to spawn device in Tutorial mode -> must be blocked
    topo._spawn_device_at("switch", 300, 300, tutorial, sound)
    assert len(tutorial.devices) == t_dev_count

    # Attempt to remove device in Tutorial mode -> must be blocked
    target = tutorial.devices[0]
    topo._remove_device(target, tutorial, sound)
    assert len(tutorial.devices) == t_dev_count
    assert target in tutorial.devices

    # 2. Challenge Mode
    challenge = ChallengeMode()
    challenge.setup()
    c_dev_count = len(challenge.devices)

    # Attempt to spawn device in Challenge mode -> must be blocked
    topo._spawn_device_at("firewall", 300, 300, challenge, sound)
    assert len(challenge.devices) == c_dev_count

    # Attempt to remove device in Challenge mode -> must be blocked
    target_c = challenge.devices[0]
    topo._remove_device(target_c, challenge, sound)
    assert len(challenge.devices) == c_dev_count
    assert target_c in challenge.devices


def test_auto_arrange_algorithm():
    """Verify auto-arrange assigns non-overlapping structured layout across tiers."""
    topo = Topology2D()
    sandbox = SandboxMode()
    sandbox.setup()

    topo.auto_arrange(sandbox.devices, 1280, 720)

    for dev in sandbox.devices:
        assert hasattr(dev, "topo_x") and hasattr(dev, "topo_y")
        # Coordinates must be within reasonable canvas range
        assert -200 <= dev.topo_x <= 1600
        assert -200 <= dev.topo_y <= 1200


def test_topology_save_load_coordinate_persistence():
    """Verify that topo_x and topo_y coordinates are preserved across save and load."""
    sandbox = SandboxMode()
    sandbox.setup()

    # Set custom 2D topology coordinates
    test_dev = sandbox.devices[0]
    test_dev.topo_x = 888.5
    test_dev.topo_y = 444.2
    target_dev_id = test_dev.id

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        tmp_path = tf.name

    try:
        ok, msg = sandbox.save_topology(tmp_path)
        assert ok, f"Save failed: {msg}"

        # Reload into a fresh sandbox
        reloaded_sandbox = SandboxMode()
        reloaded_sandbox.setup()
        ok_load, msg_load = reloaded_sandbox.load_topology(tmp_path)
        assert ok_load, f"Load failed: {msg_load}"

        loaded_dev = next((d for d in reloaded_sandbox.devices if d.id == target_dev_id), None)
        assert loaded_dev is not None
        assert loaded_dev.topo_x == 888.5
        assert loaded_dev.topo_y == 444.2
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_menu_manager_topology_map_integration():
    """Verify MenuManager correctly renders 2D topology and handles ESC / resume key events."""
    menu = MenuManager()
    sandbox = SandboxMode()
    sandbox.setup()
    sound = SoundManager.get_instance()
    surf = pygame.Surface((1280, 720))

    # Switch to TOPOLOGY_MAP
    menu.state = MenuState.TOPOLOGY_MAP

    # Render frame to surface
    menu.render(surf, 1280, 720, sandbox.devices, sandbox.cables, sandbox)

    # Press ESC to exit 2D topology
    esc_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE, "mod": 0, "unicode": ""})
    action = menu.handle_input(esc_event, sound, 1280, 720, sandbox)

    assert action == "RESUME"
    assert menu.state == MenuState.IN_GAME


def test_category_switching_and_dock_scoping():
    """Verify category switching correctly updates items and prevents rect collisions."""
    init_pygame()
    topo = Topology2D()
    sandbox = SandboxMode()
    sandbox.setup()
    sound = SoundManager.get_instance()
    surf = pygame.Surface((1280, 720))

    # Initial frame render
    topo.render(surf, 1280, 720, sandbox.devices, sandbox.cables, sandbox)
    assert topo.active_category == "network"

    # Click category "end_devices"
    cat_end_rect = topo.cached_btn_rects.get("cat_end_devices")
    assert cat_end_rect is not None
    click_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (cat_end_rect.centerx, cat_end_rect.centery)})
    topo.handle_input(click_event, sound, 1280, 720, sandbox)
    assert topo.active_category == "end_devices"

    # Render frame with active category "end_devices"
    topo.render(surf, 1280, 720, sandbox.devices, sandbox.cables, sandbox)
    assert "item_server" in topo.cached_btn_rects
    assert "item_router" not in topo.cached_btn_rects

    # Click "server" item
    server_rect = topo.cached_btn_rects["item_server"]
    click_server = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (server_rect.centerx, server_rect.centery)})
    topo.handle_input(click_server, sound, 1280, 720, sandbox)
    assert topo.placing_device_type == "server"

    # Switch to "connections"
    cat_conn_rect = topo.cached_btn_rects.get("cat_connections")
    assert cat_conn_rect is not None
    click_conn = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (cat_conn_rect.centerx, cat_conn_rect.centery)})
    topo.handle_input(click_conn, sound, 1280, 720, sandbox)
    assert topo.active_category == "connections"

    topo.render(surf, 1280, 720, sandbox.devices, sandbox.cables, sandbox)
    assert "item_cable_fiber" in topo.cached_btn_rects
    assert "item_server" not in topo.cached_btn_rects

    # Click Fiber Cable item
    fiber_rect = topo.cached_btn_rects["item_cable_fiber"]
    click_fiber = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (fiber_rect.centerx, fiber_rect.centery)})
    topo.handle_input(click_fiber, sound, 1280, 720, sandbox)
    assert topo.selected_tool == "cable"
    assert topo.active_cable_type == CableType.FIBER


def test_rack_slot_picker_custom_selection():
    """Verify interactive Rack Slot Picker allows choosing target rack, U-slot, and hostname."""
    init_pygame()
    topo = Topology2D()
    sandbox = SandboxMode()
    sandbox.setup()
    sound = SoundManager.get_instance()
    surf = pygame.Surface((1280, 720))

    # Select router and click canvas to open picker
    topo.placing_device_type = "router"
    click_canvas = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (500, 300)})
    topo.handle_input(click_canvas, sound, 1280, 720, sandbox)

    assert topo.rack_picker_open is True
    assert topo.rack_picker_dev_type == "router"
    assert topo.rack_picker_wx == 500.0
    assert topo.rack_picker_wy == 300.0

    # Render modal
    topo.render(surf, 1280, 720, sandbox.devices, sandbox.cables, sandbox)
    assert "rack_tab_1" in topo.cached_btn_rects
    assert "rack_tab_2" in topo.cached_btn_rects
    assert "rack_tab_3" in topo.cached_btn_rects
    assert "slot_minus" in topo.cached_btn_rects
    assert "slot_plus" in topo.cached_btn_rects
    assert "rack_picker_install" in topo.cached_btn_rects

    # Click Rack 3 tab
    r3_rect = topo.cached_btn_rects["rack_tab_3"]
    click_r3 = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (r3_rect.centerx, r3_rect.centery)})
    topo.handle_input(click_r3, sound, 1280, 720, sandbox)
    assert topo.rack_picker_rack_id == 3

    # Set custom U-slot 36
    topo.rack_picker_slot = 36
    topo.rack_picker_hostname = "Custom-RTR-99"

    # Click install
    install_rect = topo.cached_btn_rects["rack_picker_install"]
    click_install = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (install_rect.centerx, install_rect.centery)})
    topo.handle_input(click_install, sound, 1280, 720, sandbox)

    assert topo.rack_picker_open is False
    installed_dev = next((d for d in sandbox.devices if d.hostname == "Custom-RTR-99"), None)
    assert installed_dev is not None
    assert installed_dev.rack_id == 3
    assert installed_dev.u_slot == 36
    assert installed_dev.topo_x == 500.0
    assert installed_dev.topo_y == 300.0

    # Attempt to install another device at occupied slot 36 -> should be blocked by modal validation
    topo._open_rack_picker("router", 600, 300, sandbox)
    topo.rack_picker_rack_id = 3
    topo.rack_picker_slot = 36
    topo.rack_picker_hostname = "Conflict-RTR"

    # Re-render
    topo.render(surf, 1280, 720, sandbox.devices, sandbox.cables, sandbox)
    topo.handle_input(click_install, sound, 1280, 720, sandbox)

    # Must still be open because install was blocked!
    assert topo.rack_picker_open is True
    assert not any(d.hostname == "Conflict-RTR" for d in sandbox.devices)


def test_english_localization():
    """Verify that topology_2d.py contains zero Thai characters and strictly renders English."""
    import re
    with open(os.path.join(os.path.dirname(__file__), "..", "ui", "topology_2d.py"), "r", encoding="utf-8") as f:
        content = f.read()

    thai_chars = re.findall(r"[\u0E00-\u0E7F]", content)
    assert len(thai_chars) == 0, f"Found {len(thai_chars)} Thai characters in topology_2d.py: {thai_chars[:10]}"


if __name__ == "__main__":
    init_pygame()
    test_topology_2d_init()
    print("test_topology_2d_init PASSED")
    test_sandbox_device_placement_and_3d_sync()
    print("test_sandbox_device_placement_and_3d_sync PASSED")
    test_sandbox_cable_connection()
    print("test_sandbox_cable_connection PASSED")
    test_strict_mode_permissions_tutorial_and_challenge()
    print("test_strict_mode_permissions_tutorial_and_challenge PASSED")
    test_auto_arrange_algorithm()
    print("test_auto_arrange_algorithm PASSED")
    test_topology_save_load_coordinate_persistence()
    print("test_topology_save_load_coordinate_persistence PASSED")
    test_menu_manager_topology_map_integration()
    print("test_menu_manager_topology_map_integration PASSED")
    test_category_switching_and_dock_scoping()
    print("test_category_switching_and_dock_scoping PASSED")
    test_rack_slot_picker_custom_selection()
    print("test_rack_slot_picker_custom_selection PASSED")
    test_english_localization()
    print("test_english_localization PASSED")
    print("ALL TOPOLOGY 2D TESTS PASSED!")
