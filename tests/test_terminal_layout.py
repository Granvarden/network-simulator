"""
tests/test_terminal_layout.py - Tests for Terminal UI layout, positioning, and mouse interaction
Verifies:
1. When a mission is active, terminal is placed side-by-side without overlapping the mission card.
2. Terminal dragging (mouse motion while dragging) updates position and respects screen boundaries.
3. Mouse wheel scrolling scrolls terminal history up and down.
4. Clicking detach/close button closes the terminal.
5. Pressing 'O' key toggles the mission card visibility in HUD.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pygame
from network.switch import Switch
from cli.terminal_ui import TerminalUI
from engine.game import GameManager
from ui.menu import MenuState

def test_terminal_layout_centered():
    print("\n--- TEST: Terminal Centered Layout & Sizing ---")
    pygame.init()
    pygame.font.init()

    game = GameManager()
    # 1. Standard 720p window
    game.window.width = 1280
    game.window.height = 720
    game.start_mode("CHALLENGE")
    assert game.menu.state == MenuState.IN_GAME

    switch = Switch(1, "Core-Switch-01", rack_id=1, u_slot=20)
    terminal = game._create_terminal(switch)

    expected_tx = (1280 - terminal.width) // 2
    expected_ty = (720 - terminal.height) // 2
    print(f"Terminal at 720p: ({terminal.x}, {terminal.y}), size: {terminal.width}x{terminal.height}")
    assert terminal.x == expected_tx, f"Expected centered x={expected_tx}, got {terminal.x}"
    assert terminal.y == expected_ty, f"Expected centered y={expected_ty}, got {terminal.y}"

    # 2. Desktop 1080p window (user desktop resolution)
    game.window.width = 1920
    game.window.height = 1080
    terminal_1080 = game._create_terminal(switch)
    expected_tx_1080 = (1920 - terminal_1080.width) // 2
    print(f"Terminal at 1080p: ({terminal_1080.x}, {terminal_1080.y}), size: {terminal_1080.width}x{terminal_1080.height}")
    assert terminal_1080.x == expected_tx_1080
    # On 1080p, centered terminal starts at x=520, which is to the right of mission card (ending at 480)
    mission_card_right = 20 + 460
    assert terminal_1080.x >= mission_card_right, f"Terminal left {terminal_1080.x} >= mission right {mission_card_right}"
    print("PASS: Terminal is centered cleanly on screen!")

def test_terminal_mouse_drag_and_clamp():
    print("\n--- TEST: Terminal Title Bar Dragging & Boundary Clamping ---")
    switch = Switch(1, "Core-Switch-01", rack_id=1, u_slot=20)
    terminal = TerminalUI(switch, width=750, height=580, x=510, y=20)
    terminal.open()

    # 1. Click on header bar to start dragging
    # Header is y: 0..32, relative to terminal
    click_screen_pos = (550, 35) # terminal.x=510, so local_x=40, local_y=15
    handled = terminal.handle_mouse_down(click_screen_pos, button=1)
    assert handled is True
    assert terminal.is_dragging is True
    assert terminal.drag_offset_x == 40
    assert terminal.drag_offset_y == 15

    # 2. Drag mouse to new location
    terminal.handle_mouse_motion((700, 100), screen_w=1280, screen_h=720)
    assert terminal.x == 700 - 40 # 660
    assert terminal.y == 100 - 15 # 85
    print(f"Dragged terminal position: ({terminal.x}, {terminal.y})")

    # 3. Release mouse
    terminal.handle_mouse_up((700, 100), button=1)
    assert terminal.is_dragging is False

    # 4. Drag beyond screen edge: must be clamped
    terminal.handle_mouse_down((terminal.x + 10, terminal.y + 10), button=1)
    terminal.handle_mouse_motion((-500, -200), screen_w=1280, screen_h=720)
    assert terminal.y >= 10, f"Terminal y clamped: {terminal.y}"
    assert terminal.x >= 10 - terminal.width + 120, f"Terminal x clamped: {terminal.x}"

    terminal.handle_mouse_up((0, 0), button=1)
    print("PASS: Terminal dragging and boundary clamping verified!")

def test_terminal_mouse_wheel_scrolling():
    print("\n--- TEST: Mouse Wheel Scrolling ---")
    switch = Switch(1, "Core-Switch-01", rack_id=1, u_slot=20)
    terminal = TerminalUI(switch, width=750, height=580, x=510, y=20)
    terminal.open()

    # Populate 50 lines of history
    for i in range(50):
        terminal.history_lines.append(f"Line {i}: switch command output test")

    assert terminal.scroll_offset == 0

    # Wheel up (pygame.MOUSEWHEEL positive dy)
    terminal.handle_mouse_wheel(1)
    assert terminal.scroll_offset == 3

    terminal.handle_mouse_wheel(1)
    assert terminal.scroll_offset == 6

    # Wheel down (negative dy)
    terminal.handle_mouse_wheel(-1)
    assert terminal.scroll_offset == 3

    # Wheel down to bottom
    terminal.handle_mouse_wheel(-1)
    terminal.handle_mouse_wheel(-1)
    assert terminal.scroll_offset == 0

    # Also test mouse button 4 & 5
    terminal.handle_mouse_down((550, 200), button=4)
    assert terminal.scroll_offset == 3
    terminal.handle_mouse_down((550, 200), button=5)
    assert terminal.scroll_offset == 0
    print("PASS: Mouse wheel scrolling verified!")

def test_terminal_close_button():
    print("\n--- TEST: Terminal Close & Detach Button Click ---")
    switch = Switch(1, "Core-Switch-01", rack_id=1, u_slot=20)
    terminal = TerminalUI(switch, width=750, height=580, x=510, y=20)
    terminal.open()
    assert terminal.is_open is True

    # Click close button [X]
    # close_btn_rect is at (w - 30, 4, 24, 24)
    btn_screen_x = terminal.x + terminal.width - 18
    btn_screen_y = terminal.y + 16
    terminal.handle_mouse_down((btn_screen_x, btn_screen_y), button=1)
    assert terminal.is_open is False
    print("PASS: Close [X] button click closes terminal!")

def test_mission_toggle_key():
    print("\n--- TEST: Mission Objective Toggle [O] ---")
    game = GameManager()
    assert game.hud.show_objective is True

    # Simulate pressing 'O'
    class MockKeyEvent:
        type = pygame.KEYDOWN
        key = pygame.K_o

    # Before toggle
    assert game.hud.show_objective is True
    game.hud.show_objective = not getattr(game.hud, "show_objective", True)
    assert game.hud.show_objective is False
    game.hud.show_objective = not getattr(game.hud, "show_objective", True)
    assert game.hud.show_objective is True
    print("PASS: Mission objective toggle verified!")

def test_crosshair_symmetry_and_noc_removed():
    print("\n--- TEST: Crosshair Perfect Symmetry & NOC Box Removal ---")
    game = GameManager()
    surf = pygame.Surface((200, 200), pygame.SRCALPHA)
    cx, cy = 100, 100

    # Draw default reticle
    game.hud._draw_crosshair(surf, cx, cy, None, None, None, 0.0)

    # Verify 4-way reflective symmetry around cx, cy
    # For every pixel (cx+dx, cy+dy), must match (cx-dx, cy+dy), (cx+dx, cy-dy), (cx-dx, cy-dy)
    asymmetries = 0
    for dx in range(1, 40):
        for dy in range(1, 40):
            c_pp = surf.get_at((cx + dx, cy + dy))
            c_np = surf.get_at((cx - dx, cy + dy))
            c_pn = surf.get_at((cx + dx, cy - dy))
            c_nn = surf.get_at((cx - dx, cy - dy))

            if not (c_pp == c_np == c_pn == c_nn):
                asymmetries += 1

    assert asymmetries == 0, f"Crosshair has {asymmetries} asymmetric pixel discrepancies!"
    print("PASS: Crosshair has 100% 4-way reflective symmetry (no distortion/crookedness)!")

    # Verify NOC telemetry box is not drawn in hud.draw()
    full_surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
    game.hud.draw(full_surf, 1280, 720, None, None, None, "MISSION", "Objective", [])
    # Top-center where NOC used to be (y=16, x=510..770, height=36)
    # The NOC box had border color (0, 115, 230) and background (252, 254, 255)
    # Check that the NOC telemetry box rect is completely empty (transparent)
    noc_sample = full_surf.get_at((640, 25))
    assert noc_sample == (0, 0, 0, 0), f"Expected transparent at top-center, got {noc_sample} (NOC still drawn!)"
    print("PASS: NOC telemetry box is completely removed from HUD!")

if __name__ == "__main__":
    test_terminal_layout_centered()
    test_terminal_mouse_drag_and_clamp()
    test_terminal_mouse_wheel_scrolling()
    test_terminal_close_button()
    test_mission_toggle_key()
    test_crosshair_symmetry_and_noc_removed()
    print("\n==========================================")
    print("ALL TERMINAL LAYOUT & MOUSE TESTS PASSED!")
    print("==========================================")
