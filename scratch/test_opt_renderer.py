import pygame
from OpenGL.GL import *
pygame.init()
pygame.display.set_mode((800, 600), pygame.OPENGL | pygame.DOUBLEBUF)

from engine.renderer3d import Renderer3D
from network.host import Host

r3d = Renderer3D()
r3d.init_gl(800, 600)
print('Renderer3D initialized successfully!')
pygame.quit()
