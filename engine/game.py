"""
engine/game.py - Central Game Coordinator & Simulation Loop
Orchestrates 3D Rendering, FPS Camera, Cisco CLI Terminal, 2D HUD, Sound, and Game Modes.
"""

import pygame
import sys
import time
from OpenGL.GL import *

from .window import WindowManager
from .camera import FPSCamera
from .renderer3d import Renderer3D
from .renderer2d import Renderer2D
from .audio import SoundManager
from ui.hud import HUD
from ui.menu import MenuManager, MenuState
from cli.terminal_ui import TerminalUI
from ui.laptop_gui import LaptopGUI
from network.cable import Cable, CableType
from modes.tutorial_mode import TutorialMode
from modes.challenge_mode import ChallengeMode
from modes.sandbox_mode import SandboxMode
from engine.menu_scene import Menu3DScene, Menu3DCamera

class GameManager:
    def __init__(self):
        self.window = WindowManager("NetEngineer 3D - Enterprise Network Simulator")
        self.camera = FPSCamera(pos=(0.0, 1.65, 2.8))
        self.renderer3d = Renderer3D(fov=65.0)
        self.renderer2d = Renderer2D(self.window.width, self.window.height)
        self.sound = SoundManager.get_instance()
        self.hud = HUD()
        self.menu = MenuManager()
        self.menu_scene = Menu3DScene()
        self.menu_camera = Menu3DCamera()

        # Initialize OpenGL context
        self.renderer3d.init_gl(self.window.width, self.window.height)
        self.renderer2d.init_gl()

        # Current active gameplay mode
        self.mode = None
        self.terminal = None  # Active TerminalUI overlay when attached
        self.laptop_gui = None  # Active Laptop Desktop GUI overlay
        self.held_cable_port = None  # Port where cable was picked up

        self.clock = pygame.time.Clock()
        self.is_running = True

    def start_mode(self, mode_name):
        if mode_name == "TUTORIAL":
            self.mode = TutorialMode()
        elif mode_name == "CHALLENGE":
            self.mode = ChallengeMode()
        elif mode_name == "SANDBOX":
            self.mode = SandboxMode()

        self.camera.x, self.camera.y, self.camera.z = 0.0, 1.65, 2.8
        self.camera.yaw = 0.0
        self.camera.pitch = -4.0
        self.menu.state = MenuState.IN_GAME
        self.window.capture_mouse(True)
        self.sound.start_ambient()

    def run(self):
        last_time = time.time()

        while self.is_running:
            now = time.time()
            dt = max(0.001, min(0.1, now - last_time))
            last_time = now

            self._handle_events()
            self._update(dt)
            self._render()

            self.window.swap_buffers()
            self.clock.tick(60)

        pygame.quit()
        sys.exit(0)

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False
                return

            if event.type == pygame.VIDEORESIZE:
                w, h = self.window.handle_resize(event.w, event.h)
                self.renderer3d.init_gl(w, h)
                self.renderer2d.resize(w, h)
                if self.terminal and self.terminal.is_open:
                    self.terminal.x = max(10, min(w - 120, getattr(self.terminal, "x", 20)))
                    self.terminal.y = max(10, min(h - 40, getattr(self.terminal, "y", 20)))

            # Global Fullscreen Toggle
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                w, h = self.window.toggle_fullscreen()
                self.renderer3d.init_gl(w, h)
                self.renderer2d.resize(w, h)
                continue

            # 1. Menu Input routing
            if self.menu.state != MenuState.IN_GAME:
                action = self.menu.handle_input(event, self.sound, self.window.width, self.window.height, self.mode)
                if action == "TUTORIAL":
                    self.start_mode("TUTORIAL")
                elif action == "CHALLENGE":
                    self.start_mode("CHALLENGE")
                elif action == "SANDBOX":
                    self.start_mode("SANDBOX")
                elif action == "RESUME":
                    self.menu.state = MenuState.IN_GAME
                    self.window.capture_mouse(True)
                elif action == "RESTART" and self.mode:
                    self.mode.setup()
                    self.menu.state = MenuState.IN_GAME
                    self.window.capture_mouse(True)
                elif action == "TO_MAIN_MENU":
                    self.terminal = None
                    self.laptop_gui = None
                    self.sound.stop_ambient()
                    self.window.capture_mouse(False)
                elif action == "EXIT":
                    self.is_running = False
                continue

            # 2. Laptop GUI Input routing
            if self.laptop_gui and self.laptop_gui.is_open:
                if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                    tx = (self.window.width - self.laptop_gui.width) // 2
                    ty = (self.window.height - self.laptop_gui.height) // 2
                    local_pos = (event.pos[0] - tx, event.pos[1] - ty)

                    if event.type == pygame.MOUSEMOTION:
                        self.laptop_gui.handle_mouse_motion(local_pos)
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        # Check if clicked outside laptop chassis -> dismiss
                        if (local_pos[0] < 0 or local_pos[0] > self.laptop_gui.width or
                                local_pos[1] < 0 or local_pos[1] > self.laptop_gui.height):
                            self.laptop_gui.close()
                            self.laptop_gui = None
                            self.window.capture_mouse(True)
                        else:
                            self.laptop_gui.handle_mouse_down(local_pos, event.button)
                            if not self.laptop_gui.is_open:
                                self.laptop_gui = None
                                self.window.capture_mouse(True)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE and self.laptop_gui.active_app is None:
                        self.laptop_gui.close()
                        self.laptop_gui = None
                        self.window.capture_mouse(True)
                    else:
                        self.laptop_gui.handle_key(event)
                        if not self.laptop_gui.is_open:
                            self.laptop_gui = None
                            self.window.capture_mouse(True)
                continue

            # 3. Terminal UI Input routing
            if self.terminal and self.terminal.is_open:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and not getattr(self.terminal, "active_job", None):
                    self.terminal.close()
                    self.window.capture_mouse(True)
                elif event.type == pygame.KEYDOWN:
                    self.terminal.handle_key(event)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.terminal.handle_mouse_down(event.pos, event.button)
                    if not self.terminal.is_open:
                        self.window.capture_mouse(True)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.terminal.handle_mouse_up(event.pos, event.button)
                elif event.type == pygame.MOUSEMOTION:
                    self.terminal.handle_mouse_motion(event.pos, self.window.width, self.window.height)
                elif event.type == pygame.MOUSEWHEEL:
                    self.terminal.handle_mouse_wheel(event.y)
                continue

            # 4. 3D In-Game Input Routing
            if event.type == pygame.MOUSEMOTION and self.window.mouse_captured:
                dx, dy = event.rel
                self.camera.handle_mouse(dx, dy)

            elif event.type == pygame.KEYDOWN:
                # Open/Close Pause Menu
                if event.key in (pygame.K_ESCAPE, pygame.K_p):
                    self.menu.state = MenuState.PAUSE
                    self.window.capture_mouse(False)

                # Open/Close 2D Topology Map
                elif event.key == pygame.K_m:
                    self.menu.state = MenuState.TOPOLOGY_MAP
                    self.window.capture_mouse(False)

                # Open Terminal / Laptop GUI on targeted device [E]
                elif event.key == pygame.K_e:
                    f_dev, f_port, _ = self.camera.raycast(self.mode.devices)
                    target_dev = f_port.device if f_port else f_dev
                    if target_dev:
                        if target_dev.device_type == "laptop":
                            self.laptop_gui = LaptopGUI(target_dev, self.window.width, self.window.height)
                            self.laptop_gui.open()
                            self.window.capture_mouse(False)
                        else:
                            self.terminal = self._create_terminal(target_dev)
                            self.terminal.open()
                            self.window.capture_mouse(False)
                        if hasattr(self.mode, "has_opened_terminal"):
                            self.mode.has_opened_terminal = True

                # Toggle Mission Objective Card [O]
                elif event.key == pygame.K_o:
                    self.hud.show_objective = not getattr(self.hud, "show_objective", True)
                    self.sound.play_key()

                # Cable Connect / Disconnect Action [F]
                elif event.key == pygame.K_f:
                    self._handle_cable_action()

                # Cancel held cable [X]
                elif event.key == pygame.K_x:
                    if self.held_cable_port:
                        self.held_cable_port = None
                        self.sound.play_key()

                # Sandbox Controls: Save [K] / Load [L] / Device Manager [N] / Quick Delete [Del]
                elif isinstance(self.mode, SandboxMode):
                    if event.key == pygame.K_k:
                        self.mode.save_topology()
                    elif event.key == pygame.K_l:
                        self.mode.load_topology()
                    elif event.key == pygame.K_n:
                        self.menu.state = MenuState.DEVICE_MANAGER
                        self.window.capture_mouse(False)
                    elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                        f_dev, f_port, _ = self.camera.raycast(self.mode.devices)
                        target_dev = f_port.device if f_port else f_dev
                        if target_dev:
                            if self.terminal and self.terminal.device == target_dev:
                                self.terminal.close()
                                self.terminal = None
                            if self.held_cable_port and self.held_cable_port.device == target_dev:
                                self.held_cable_port = None
                            self.mode.remove_device(target_dev)

                # Challenge Next Scenario [N]
                elif isinstance(self.mode, ChallengeMode) and self.mode.is_completed:
                    if event.key == pygame.K_n:
                        self.mode.next_scenario()

    def _handle_cable_action(self):
        f_dev, f_port, _ = self.camera.raycast(self.mode.devices)
        if not f_port:
            if f_dev and len(f_dev.ports) > 0:
                # Target first available port if aimed at device body
                f_port = list(f_dev.ports.values())[0]
            else:
                return

        if self.held_cable_port is None:
            # If port already has cable, unplug it
            if f_port.cable:
                c = f_port.cable
                if c in self.mode.cables:
                    self.mode.cables.remove(c)
                c.disconnect()
                self.sound.play_cable()
            else:
                # Pick up cable from this port
                self.held_cable_port = f_port
                self.sound.play_cable()
                # Notify tutorial mode of cable pickup
                if hasattr(self.mode, "on_cable_picked_up"):
                    self.mode.on_cable_picked_up()
        else:
            # Connect cable to second port
            if f_port != self.held_cable_port:
                # Check if target port already has cable
                if f_port.cable:
                    c = f_port.cable
                    if c in self.mode.cables:
                        self.mode.cables.remove(c)
                    c.disconnect()

                c_type = CableType.CONSOLE if ("con" in self.held_cable_port.name or "con" in f_port.name) else CableType.CAT6
                new_cable = Cable(self.held_cable_port, f_port, c_type)
                self.mode.cables.append(new_cable)
                self.sound.play_cable()
                self.held_cable_port = None
            else:
                # Cancel if clicking same port
                self.held_cable_port = None

    def _create_terminal(self, target_dev):
        """Creates a TerminalUI sized and centered on the screen."""
        w = self.window.width
        h = self.window.height

        term_w = min(880, w - 80)
        term_h = min(600, h - 80)
        tx = (w - term_w) // 2
        ty = max(20, (h - term_h) // 2)

        terminal = TerminalUI(target_dev, term_w, term_h, x=tx, y=ty)
        terminal.on_command_executed_callback = self._on_terminal_command
        return terminal

    def _on_terminal_command(self, device, cmd_line, output):
        if self.mode:
            self.mode.on_command_executed(device, cmd_line, output)

    def _update(self, dt):
        if self.laptop_gui and self.laptop_gui.is_open:
            self.laptop_gui.update(dt)

        if self.terminal and self.terminal.is_open:
            self.terminal.update(dt)

        if self.menu.state == MenuState.IN_GAME and not (self.terminal and self.terminal.is_open) and not (self.laptop_gui and self.laptop_gui.is_open):
            keys = pygame.key.get_pressed()
            self.camera.update(keys, dt, pygame)

        if self.mode:
            self.mode.update(dt, self.camera)

    def _render(self):
        # Raycast once per frame if in active gameplay/inspect mode
        f_dev, f_port = None, None
        if self.menu.state == MenuState.MAIN_MENU:
            # Render live 3D Datacenter scene with 2 fully loaded racks & cabling
            self.renderer3d.render_scene(self.menu_camera, self.menu_scene.devices, self.menu_scene.cables)
        elif self.mode and self.menu.state in (MenuState.IN_GAME, MenuState.PAUSE, MenuState.TOPOLOGY_MAP, MenuState.DEVICE_MANAGER):
            f_dev, f_port, _ = self.camera.raycast(self.mode.devices)
            self.renderer3d.render_scene(self.camera, self.mode.devices, self.mode.cables, f_dev, f_port)
        else:
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # 2. 2D Surface Layer
        self.renderer2d.clear_surface()
        surf = self.renderer2d.hud_surface
        w, h = self.window.width, self.window.height

        if self.menu.state == MenuState.IN_GAME:
            # Get concept panel data (Tutorial mode only)
            concept_data = None
            if hasattr(self.mode, "get_concept"):
                concept_data = self.mode.get_concept()
            self.hud.draw(surf, w, h, f_dev, f_port, self.held_cable_port,
                          self.mode.get_title(), self.mode.get_objective(),
                          self.mode.get_checklist(), self.mode.get_hint(),
                          concept_data)

            # Draw Laptop Desktop GUI overlay if open
            if self.laptop_gui and self.laptop_gui.is_open:
                gui_surf = self.laptop_gui.render()
                gx = (w - self.laptop_gui.width) // 2
                gy = (h - self.laptop_gui.height) // 2
                surf.blit(gui_surf, (gx, gy))

            # Draw CLI Terminal window overlay if open
            elif self.terminal and self.terminal.is_open:
                term_surf = self.terminal.render()
                tx = getattr(self.terminal, "x", (w - self.terminal.width) // 2)
                ty = getattr(self.terminal, "y", (h - self.terminal.height) // 2)
                surf.blit(term_surf, (tx, ty))

        # Draw Menu / Dialogs
        devs = self.mode.devices if self.mode else []
        cbls = self.mode.cables if self.mode else []
        self.menu.render(surf, w, h, devs, cbls, self.mode)

        # Blit 2D overlay to OpenGL
        self.renderer2d.render_overlay()
