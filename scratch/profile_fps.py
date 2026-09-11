import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
import pygame
from OpenGL.GL import *
from engine.window import WindowManager
from engine.camera import FPSCamera
from engine.renderer3d import Renderer3D
from engine.renderer2d import Renderer2D
from ui.hud import HUD
from modes.sandbox_mode import SandboxMode

def run_benchmark():
    pygame.init()
    pygame.font.init()

    # Create offscreen / hidden window or test window
    win = WindowManager("Benchmark")
    cam = FPSCamera()
    r3d = Renderer3D()
    r2d = Renderer2D(win.width, win.height)
    hud = HUD()
    mode = SandboxMode()

    r3d.init_gl(win.width, win.height)
    r2d.init_gl()

    # Warmup 10 frames
    for _ in range(10):
        f_dev, f_port, _ = cam.raycast(mode.devices)
        r3d.render_scene(cam, mode.devices, mode.cables, f_dev, f_port)
        r2d.clear_surface()
        hud.draw(r2d.hud_surface, win.width, win.height, f_dev, f_port, None,
                 mode.get_title(), mode.get_objective(), mode.get_checklist())
        r2d.render_overlay()
        win.swap_buffers()

    # Benchmark 120 frames
    t_raycast = 0.0
    t_r3d = 0.0
    t_clear2d = 0.0
    t_hud = 0.0
    t_overlay2d = 0.0
    t_swap = 0.0

    frames = 120
    t0 = time.perf_counter()
    for _ in range(frames):
        t_a = time.perf_counter()
        f_dev, f_port, _ = cam.raycast(mode.devices)
        t_b = time.perf_counter()
        r3d.render_scene(cam, mode.devices, mode.cables, f_dev, f_port)
        t_c = time.perf_counter()
        r2d.clear_surface()
        t_d = time.perf_counter()
        hud.draw(r2d.hud_surface, win.width, win.height, f_dev, f_port, None,
                 mode.get_title(), mode.get_objective(), mode.get_checklist())
        t_e = time.perf_counter()
        r2d.render_overlay()
        t_f = time.perf_counter()
        win.swap_buffers()
        t_g = time.perf_counter()

        t_raycast += (t_b - t_a)
        t_r3d += (t_c - t_b)
        t_clear2d += (t_d - t_c)
        t_hud += (t_e - t_d)
        t_overlay2d += (t_f - t_e)
        t_swap += (t_g - t_f)

    total_time = time.perf_counter() - t0
    avg_fps = frames / total_time

    print(f"=== BENCHMARK RESULTS ({frames} frames, {win.width}x{win.height}) ===")
    print(f"Total Time: {total_time:.3f}s | Avg FPS: {avg_fps:.1f}")
    print(f"1. Raycast:      {t_raycast*1000/frames:6.2f} ms/frame ({t_raycast/total_time*100:4.1f}%)")
    print(f"2. 3D Render:    {t_r3d*1000/frames:6.2f} ms/frame ({t_r3d/total_time*100:4.1f}%)")
    print(f"3. 2D Clear:     {t_clear2d*1000/frames:6.2f} ms/frame ({t_clear2d/total_time*100:4.1f}%)")
    print(f"4. 2D HUD:       {t_hud*1000/frames:6.2f} ms/frame ({t_hud/total_time*100:4.1f}%)")
    print(f"5. 2D Overlay:   {t_overlay2d*1000/frames:6.2f} ms/frame ({t_overlay2d/total_time*100:4.1f}%)")
    print(f"6. Swap Buffers: {t_swap*1000/frames:6.2f} ms/frame ({t_swap/total_time*100:4.1f}%)")

    pygame.quit()

if __name__ == "__main__":
    run_benchmark()
