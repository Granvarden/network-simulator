"""
tests/test_menu_mouse.py - Automated tests for Menu Mouse Click and Keyboard Navigation
"""

import pygame
from ui.menu import MenuManager, MenuState
from engine.audio import SoundManager

def test_menu_mouse_and_keys():
    pygame.init()
    pygame.font.init()
    menu = MenuManager()
    sound = SoundManager.get_instance()
    w, h = 1280, 720

    # 1. Test Mouse Hover over Button 0
    b0_rect = menu.get_main_menu_button_rect(0, w, h)
    hover_event = pygame.event.Event(pygame.MOUSEMOTION, {"pos": (b0_rect.centerx, b0_rect.centery), "rel": (0, 0), "buttons": (0, 0, 0)})
    menu.handle_input(hover_event, sound, w, h)
    assert menu.selected_button == 0
    print("Mouse hover over Button 0 verified.")

    # 2. Test Mouse Click on Button 0 (TUTORIAL)
    click_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (b0_rect.centerx, b0_rect.centery), "button": 1})
    action = menu.handle_input(click_event, sound, w, h)
    assert action == "TUTORIAL", f"Expected TUTORIAL, got {action}"
    print("Mouse click on Button 0 returned:", action)

    # 3. Test Mouse Click on Button 1 (CHALLENGE)
    b1_rect = menu.get_main_menu_button_rect(1, w, h)
    click1 = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (b1_rect.centerx, b1_rect.centery), "button": 1})
    action1 = menu.handle_input(click1, sound, w, h)
    assert action1 == "CHALLENGE"
    print("Mouse click on Button 1 returned:", action1)

    # 4. Test Mouse Click on Button 2 (SANDBOX)
    b2_rect = menu.get_main_menu_button_rect(2, w, h)
    click2 = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (b2_rect.centerx, b2_rect.centery), "button": 1})
    action2 = menu.handle_input(click2, sound, w, h)
    assert action2 == "SANDBOX"
    print("Mouse click on Button 2 returned:", action2)

    # 5. Test Keypad 1 (K_KP1)
    kp1_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_KP1})
    action_kp = menu.handle_input(kp1_event, sound, w, h)
    assert action_kp == "TUTORIAL"
    print("Keypad 1 returned:", action_kp)

    # 6. Test Enter key on selected button
    menu.selected_button = 0
    enter_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
    action_enter = menu.handle_input(enter_event, sound, w, h)
    assert action_enter == "TUTORIAL"
    print("Enter key on selected button returned:", action_enter)

    # 7. Test Pause Menu Mouse Click
    menu.state = MenuState.PAUSE
    p0_rect = menu.get_pause_button_rect(0, w, h)
    p_click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (p0_rect.centerx, p0_rect.centery), "button": 1})
    menu.handle_input(p_click, sound, w, h)
    assert menu.state == MenuState.IN_GAME
    print("Pause menu resume click verified.")

    pygame.quit()
    print("\nALL MENU MOUSE & KEYBOARD TESTS PASSED!")

if __name__ == "__main__":
    test_menu_mouse_and_keys()
