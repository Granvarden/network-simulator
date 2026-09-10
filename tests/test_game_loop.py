"""
tests/test_game_loop.py - Automated Headless Simulation Test
Verifies that 3D OpenGL Rendering, 2D Ortho blitting, Mode transitions,
and Raycasting run without any errors.
"""

import os
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pygame
from OpenGL.GL import *
from engine.game import GameManager
from ui.menu import MenuState

def test_game_loop():
    pygame.init()
    pygame.font.init()

    # Initialize GameManager
    game = GameManager()
    print("GameManager initialized successfully.")

    # 1. Test Tutorial Mode loop
    game.start_mode("TUTORIAL")
    assert game.menu.state == MenuState.IN_GAME
    print("Mode started: Tutorial.")
    for i in range(10):
        game._update(0.016)
        game._render()
        game.window.swap_buffers()
    print("10 frames rendered in Tutorial Mode successfully.")

    # 2. Test Terminal UI attachment
    dev = game.mode.devices[0]
    from cli.terminal_ui import TerminalUI
    game.terminal = TerminalUI(dev, 800, 500)
    game.terminal.open()
    assert game.terminal.is_open
    game._render()
    game.window.swap_buffers()
    print("Terminal UI rendered on top of 3D scene successfully.")

    # 3. Test Challenge Mode loop
    game.start_mode("CHALLENGE")
    assert game.menu.state == MenuState.IN_GAME
    print("Mode started: Challenge.")
    for i in range(5):
        game._update(0.016)
        game._render()
        game.window.swap_buffers()

    # 4. Test Sandbox Mode loop
    game.start_mode("SANDBOX")
    assert game.menu.state == MenuState.IN_GAME
    print("Mode started: Sandbox.")
    for i in range(5):
        game._update(0.016)
        game._render()
        game.window.swap_buffers()

    # 5. Test 2D Topology Map
    game.menu.state = MenuState.TOPOLOGY_MAP
    game._render()
    game.window.swap_buffers()
    print("2D Topology Map rendered successfully.")

    # 6. Test Rack Device Manager Modal rendering & input
    game.menu.state = MenuState.DEVICE_MANAGER
    game._render()
    game.window.swap_buffers()
    print("Rack Device Manager modal rendered successfully on top of 3D Datacenter.")

    # Simulate pressing ESC to close Device Manager
    esc_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    act = game.menu.handle_input(esc_event, game.sound, game.window.width, game.window.height, game.mode)
    assert act == "RESUME"
    game.menu.state = MenuState.IN_GAME
    print("Device Manager exit transition verified.")

    # 7. Test Laptop Desktop GUI event routing and input handling
    from ui.laptop_gui import LaptopGUI
    lap_dev = [d for d in game.mode.devices if d.device_type == "laptop"][0]
    game.laptop_gui = LaptopGUI(lap_dev, game.window.width, game.window.height)
    game.laptop_gui.open()
    assert game.laptop_gui.is_open

    # Simulate keyboard event (must not crash when event has no .pos attribute)
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_a, "unicode": "a"}))
    game._handle_events()

    # Simulate mouse motion
    pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, {"pos": (game.window.width // 2, game.window.height // 2), "rel": (0, 0), "buttons": (0, 0, 0)}))
    game._handle_events()

    # Simulate mouse click
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (game.window.width // 2, game.window.height // 2), "button": 1}))
    game._handle_events()

    # Close laptop GUI via ESC
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE, "unicode": ""}))
    game._handle_events()
    assert game.laptop_gui is None
    print("Laptop Desktop GUI event routing (Keyboard & Mouse) verified.")

    pygame.quit()
    print("\nALL GAME LOOP & RENDERER INTEGRATION TESTS PASSED!")

if __name__ == "__main__":
    test_game_loop()
