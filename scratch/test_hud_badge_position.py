import os
import sys
sys.path.insert(0, r"c:\Users\admin\Desktop\programming\game")

import pygame
pygame.init()
pygame.font.init()

from ui.hud import HUD
from network.router import Router
from network.cable import Cable, CableType

screen_w, screen_h = 1280, 720
surface = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
hud = HUD()

router = Router("r1", "Edge-Router-02", rack_id=1, u_slot=10)
port_g0 = router.ports["g0/0"]

# 1. Test Device Focused (Router focused)
surface.fill((20, 24, 30))
hud.draw(surface, screen_w, screen_h, focused_dev=router, focused_port=None, held_cable_port=None,
         current_mode_title="SANDBOX LAB", current_objective=None, objective_checklist=[])

out_dir = r"C:\Users\admin\.gemini\antigravity-ide\brain\577a52f7-8e41-4992-8a99-dda184c7df4f\scratch"
path1 = os.path.join(out_dir, "hud_device_badge_test.png")
pygame.image.save(surface, path1)
print(f"Saved: {path1}")

# 2. Test Port Focused (G0/0 focused)
surface.fill((20, 24, 30))
hud.draw(surface, screen_w, screen_h, focused_dev=router, focused_port=port_g0, held_cable_port=None,
         current_mode_title="SANDBOX LAB", current_objective=None, objective_checklist=[])

path2 = os.path.join(out_dir, "hud_port_badge_test.png")
pygame.image.save(surface, path2)
print(f"Saved: {path2}")

pygame.quit()
