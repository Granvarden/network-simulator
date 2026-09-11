import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import ctypes
import pygame

pygame.init()
surf = pygame.Surface((100, 100), pygame.SRCALPHA)
buf = surf.get_buffer()
c_buf = (ctypes.c_char * buf.length).from_buffer(buf)

try:
    surf.fill((10, 20, 30, 40))
    print("surf.fill succeeded while buffer held!")
except Exception as e:
    print(f"surf.fill failed: {e}")

pygame.quit()
