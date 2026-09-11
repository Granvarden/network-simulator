"""
engine/renderer2d.py - 2D Orthographic HUD & Overlay Pipeline
Renders 2D Pygame surface (HUD, terminal, objectives, minimap) cleanly over the 3D OpenGL viewport.
"""

import pygame
from OpenGL.GL import *

class Renderer2D:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.texture_id = None
        self.hud_surface = pygame.Surface((width, height), pygame.SRCALPHA)

    def init_gl(self):
        if self.texture_id is None:
            self.texture_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.texture_id)
            # GL_NEAREST ensures 1:1 pixel crispness for HUD text, icons, and terminal console
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.width, self.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)

    def resize(self, width, height):
        self.width = width
        self.height = height
        self.hud_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        if self.texture_id:
            glBindTexture(GL_TEXTURE_2D, self.texture_id)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)

    def clear_surface(self):
        self.hud_surface.fill((0, 0, 0, 0))

    def render_overlay(self):
        """Uploads hud_surface to OpenGL texture via fast subimage transfer and draws an orthographic textured quad."""
        if not self.texture_id:
            self.init_gl()

        # Direct memory transfer without CPU row flipping or color channel conversions
        raw_data = bytes(self.hud_surface.get_buffer())
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.width, self.height, GL_BGRA, GL_UNSIGNED_BYTE, raw_data)

        # Switch to 2D Ortho projection
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.width, 0, self.height, -1, 1)

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_TEXTURE_2D)

        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 1.0); glVertex2f(0.0, 0.0)
        glTexCoord2f(1.0, 1.0); glVertex2f(self.width, 0.0)
        glTexCoord2f(1.0, 0.0); glVertex2f(self.width, self.height)
        glTexCoord2f(0.0, 0.0); glVertex2f(0.0, self.height)
        glEnd()

        glDisable(GL_TEXTURE_2D)
        glEnable(GL_DEPTH_TEST)

        # Restore 3D projection
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
