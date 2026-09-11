"""
engine/window.py - Window Manager and Display Configuration
Handles Pygame + PyOpenGL context, maximized window with taskbar, mouse capture, and fullscreen toggles.
"""

import pygame
from OpenGL.GL import *

class WindowManager:
    def __init__(self, title="NetEngineer 3D - Enterprise Datacenter Simulator"):
        self.title = title
        self.is_fullscreen = False

        # Enable Per-Monitor High-DPI Awareness on Windows to prevent OS blur
        try:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

        info = pygame.display.Info()
        self.desktop_w = info.current_w if info.current_w > 0 else 1920
        self.desktop_h = info.current_h if info.current_h > 0 else 1080

        # Query Windows Work Area (Screen minus Taskbar)
        work_w = self.desktop_w
        work_h = max(700, self.desktop_h - 60)
        try:
            import ctypes
            import ctypes.wintypes
            rect = ctypes.wintypes.RECT()
            # SPI_GETWORKAREA = 0x0030
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                work_w = rect.right - rect.left
                work_h = rect.bottom - rect.top
        except Exception:
            pass

        self.width = work_w
        self.height = work_h

        pygame.display.set_caption(self.title)

        # High-Fidelity OpenGL Context Attributes
        pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE, 24)
        pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)

        self.flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE

        # Enable Hardware Multisample Anti-Aliasing (4x MSAA, fallback to 2x or 0x)
        screen_created = False
        for samples in (4, 2):
            try:
                pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 1)
                pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, samples)
                self.screen = pygame.display.set_mode((self.width, self.height), self.flags)
                screen_created = True
                break
            except Exception:
                continue

        if not screen_created:
            pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 0)
            pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, 0)
            self.screen = pygame.display.set_mode((self.width, self.height), self.flags)

        # Maximize the window on Windows while keeping the taskbar visible
        try:
            import ctypes
            hwnd = pygame.display.get_wm_info().get("window")
            if hwnd:
                # SW_MAXIMIZE = 3
                ctypes.windll.user32.ShowWindow(hwnd, 3)
                info = pygame.display.Info()
                if info.current_w > 0:
                    self.width = info.current_w
                    self.height = info.current_h
        except Exception:
            pass

        self.mouse_captured = False
        self.capture_mouse(False)

    def capture_mouse(self, capture=True):
        self.mouse_captured = capture
        pygame.mouse.set_visible(not capture)
        pygame.event.set_grab(capture)

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.FULLSCREEN
            self.screen = pygame.display.set_mode((self.desktop_w, self.desktop_h), flags)
            self.width, self.height = self.desktop_w, self.desktop_h
        else:
            flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE
            self.screen = pygame.display.set_mode((self.width, self.height), flags)
            try:
                import ctypes
                hwnd = pygame.display.get_wm_info().get("window")
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 3)
            except Exception:
                pass
        return self.width, self.height

    def handle_resize(self, new_w, new_h):
        self.width = max(800, new_w)
        self.height = max(600, new_h)
        self.screen = pygame.display.set_mode((self.width, self.height), self.flags)
        return self.width, self.height

    def swap_buffers(self):
        pygame.display.flip()
