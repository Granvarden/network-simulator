"""
tests/test_tutorial_chapter1.py - Automated Verification for Tutorial Chapter 1 & Chapter Selection
Tests all 5 guided phases:
  Phase 0: Controls & Movement Orientation
  Phase 1: 42U Rack Equipment Mounting ([N])
  Phase 2: Physical Layer Cabling (Cat6 Server eth0 -> Switch g0/1)
  Phase 3: Cisco IOS CLI Navigation (enable -> conf t)
  Phase 4: 2D Logical Topology Inspection & Chapter Completion
"""

import os
import sys
import json
import pygame

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modes.tutorial_mode import TutorialMode
from ui.menu import MenuManager, MenuState
from network.cable import Cable, CableType
from engine.camera import FPSCamera
from engine.audio import SoundManager


def test_tutorial_chapter1_full_progression():
    pygame.init()
    pygame.font.init()
    sound = SoundManager.get_instance()

    # -------------------------------------------------------------
    # 1. Test Menu Chapter Selection UI
    # -------------------------------------------------------------
    menu = MenuManager()
    w, h = 1280, 720

    # Trigger Tutorial Mode from Main Menu
    menu.selected_button = 0
    enter_ev = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
    action = menu.handle_input(enter_ev, sound, w, h)
    assert action == "TUTORIAL"
    menu.state = MenuState.TUTORIAL_SELECT
    print("[PASS] Main Menu -> Chapter Selection screen transition verified.")

    # Render Chapter Select Screen onto a dummy surface
    surf = pygame.Surface((w, h))
    menu.render(surf, w, h)
    assert len(menu._chapter_card_rects) == 3
    print("[PASS] Chapter Cards rendered (3 cards: Chapter 1, 2, 3).")

    # Navigate cards with Left/Right
    r_ev = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RIGHT})
    menu.handle_input(r_ev, sound, w, h)
    assert menu.selected_chapter_idx == 1

    l_ev = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_LEFT})
    menu.handle_input(l_ev, sound, w, h)
    assert menu.selected_chapter_idx == 0

    # Launch Chapter 1 via Enter
    launch_ev = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
    launch_act = menu.handle_input(launch_ev, sound, w, h)
    assert launch_act == "START_TUTORIAL:1"
    assert menu.state == MenuState.IN_GAME
    print("[PASS] Chapter 1 Launch action verified.")

    # Test [ESC] to return to Main Menu from Chapter Selection
    menu.state = MenuState.TUTORIAL_SELECT
    esc_ev = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE})
    esc_act = menu.handle_input(esc_ev, sound, w, h)
    assert esc_act == "TO_MAIN_MENU"
    assert menu.state == MenuState.MAIN_MENU
    print("[PASS] Chapter Select [ESC] -> Main Menu transition verified.")

    # -------------------------------------------------------------
    # 2. Test TutorialMode Initialization
    # -------------------------------------------------------------
    tut = TutorialMode(chapter=1)
    assert tut.step == 0
    assert len(tut.devices) == 3  # Web-Server-01, Win-Laptop-01, Ubuntu-Laptop-02
    assert tut.switch1 is None    # Core-Switch-01 is mounted in Phase 1
    assert "PHASE 1/5" in tut.get_title()
    print("[PASS] TutorialMode Chapter 1 Initialized (3 devices, empty switch slot).")

    cam = FPSCamera(pos=(0.0, 1.65, 2.8))

    # -------------------------------------------------------------
    # 3. Test Phase 0: Controls & Movement Orientation
    # -------------------------------------------------------------
    # Initial frame
    tut.update(0.1, cam)

    # Player moves and looks around
    cam.x = -1.0
    cam.z = -1.0
    cam.yaw = 35.0
    tut.update(0.1, cam)

    assert tut.has_moved is True
    assert tut.has_looked_around is True
    assert tut.has_approached_rack is True
    assert tut.step == 1
    assert "PHASE 2/5" in tut.get_title()
    print("[PASS] Phase 0 complete -> advanced to Phase 1 (Rack Mounting).")

    # -------------------------------------------------------------
    # 4. Test Phase 1: 42U Rack Equipment Mounting ([N])
    # -------------------------------------------------------------
    # Test collision check on occupied slot 12U
    coll_ok, coll_msg, _ = tut.add_device("switch", rack_id=1, u_slot=12, hostname="Bad-SW")
    assert coll_ok is False
    assert "occupied" in coll_msg

    # Install Switch into RACK-01 Slot 24U
    ok, msg, sw = tut.add_device("switch", rack_id=1, u_slot=24, hostname="Core-Switch-01")
    assert ok is True
    assert sw is not None
    assert tut.switch1 == sw
    assert sw.rack_id == 1
    assert sw.u_slot == 24
    assert tut.has_mounted_switch is True
    assert tut.step == 2
    assert "PHASE 3/5" in tut.get_title()
    print("[PASS] Phase 1 complete -> Core-Switch-01 mounted at RACK-01 Slot 24U.")

    # -------------------------------------------------------------
    # 5. Test Phase 2: Physical Layer Cabling (Cat6 Server eth0 -> Switch g0/1)
    # -------------------------------------------------------------
    p_srv = tut.server1.eth0
    p_sw = tut.switch1.ports["g0/1"]
    cable = Cable(p_srv, p_sw, CableType.CAT6)
    tut.cables.append(cable)
    tut.on_cable_connected(p_srv, p_sw)
    tut.update(0.1, cam)

    assert tut.has_cabled_server_to_sw is True
    assert tut.step == 3
    assert "PHASE 4/5" in tut.get_title()
    print("[PASS] Phase 2 complete -> Cat6 Cable connected between server and switch.")

    # -------------------------------------------------------------
    # 6. Test Phase 3: Cisco IOS CLI Navigation (enable -> conf t)
    # -------------------------------------------------------------
    # User EXEC -> Privileged EXEC
    tut.on_command_executed(tut.switch1, "enable", "Switch#")
    assert tut.has_used_enable is True
    assert tut.has_entered_config is False

    # Privileged EXEC -> Global Config
    tut.on_command_executed(tut.switch1, "configure terminal", "Enter configuration commands one per line.")
    assert tut.has_entered_config is True
    tut.update(0.1, cam)

    assert tut.step == 4
    assert "PHASE 5/5" in tut.get_title()
    print("[PASS] Phase 3 complete -> Cisco IOS navigated to Global Config mode.")

    # -------------------------------------------------------------
    # 7. Test Phase 4: 2D Logical Topology & Inspection
    # -------------------------------------------------------------
    tut.on_topology_event("open")
    assert tut.has_opened_topology is True

    tut.on_topology_event("zoom")
    assert tut.has_panned_or_zoomed is True

    tut.on_topology_event("inspect")
    assert tut.has_inspected_topology_device is True

    tut.on_topology_event("close")
    assert tut.has_returned_to_3d is True

    tut.update(0.1, cam)
    assert tut.is_completed is True
    assert "COMPLETED" in tut.get_title()
    print("[PASS] Phase 4 complete -> Chapter 1 Completed 100%!")

    # -------------------------------------------------------------
    # 8. Verify tutorial_progress.json Persistence
    # -------------------------------------------------------------
    assert os.path.exists("tutorial_progress.json")
    with open("tutorial_progress.json", "r", encoding="utf-8") as fp:
        prog = json.load(fp)
    assert "chapter_1" in prog.get("completed_chapters", [])
    print("[PASS] tutorial_progress.json persistence verified (chapter_1 completed).")

    print("\n" + "="*50)
    print("ALL TUTORIAL CHAPTER 1 AUTOMATED TESTS PASSED!")
    print("="*50)


if __name__ == "__main__":
    test_tutorial_chapter1_full_progression()
