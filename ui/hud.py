"""
ui/hud.py - In-Game Heads-Up Display (HUD) - Precision Enterprise Light Theme
Renders high-tech dynamic targeting crosshair, live NOC bandwidth telemetry,
interactive device hardware inspector with CPU/RAM bars & port LED matrix,
and mission checklist with animated progress bars.
"""

import math
import time
import functools
import pygame

@functools.lru_cache(maxsize=256)
def _cached_wrap_text(text, font, max_w):
    words = text.split()
    if not words:
        return ()
    lines = []
    cur_line = words[0]
    for w in words[1:]:
        test_line = f"{cur_line} {w}"
        if font.size(test_line)[0] <= max_w:
            cur_line = test_line
        else:
            lines.append(cur_line)
            cur_line = w
    lines.append(cur_line)
    return tuple(lines)

class HUD:
    def __init__(self):
        self.font_main = pygame.font.SysFont("Segoe UI", 14) or pygame.font.Font(None, 18)
        self.font_bold = pygame.font.SysFont("Segoe UI", 15, bold=True) or pygame.font.Font(None, 18)
        self.font_title = pygame.font.SysFont("Segoe UI", 18, bold=True) or pygame.font.Font(None, 22)
        self.font_small = pygame.font.SysFont("Segoe UI", 12) or pygame.font.Font(None, 15)
        self.font_mono = pygame.font.SysFont("Consolas", 13) or pygame.font.Font(None, 16)
        self.font_mono_bold = pygame.font.SysFont("Consolas", 14, bold=True) or pygame.font.Font(None, 17)

        # Reticle animation state
        self.crosshair_size = 10
        self.crosshair_gap = 5
        self.reticle_anim = 0.0

    def draw(self, surface, screen_w, screen_h, focused_dev, focused_port, held_cable_port,
             current_mode_title, current_objective, objective_checklist, hint_text=None,
             concept_data=None):
        cx, cy = screen_w // 2, screen_h // 2
        now = time.time()
        self.reticle_anim = now

        # 1. Precision Targeting Reticle / Crosshair
        self._draw_crosshair(surface, cx, cy, focused_dev, focused_port, held_cable_port, now)

        # 2. NOC Real-Time Telemetry / Bandwidth Monitor Widget (Top Center)
        self._draw_noc_telemetry(surface, screen_w, now)

        # 3. Floating Context Action Prompt (Under crosshair)
        if held_cable_port:
            txt = f"CABLE HELD: {held_cable_port.device.hostname} [{held_cable_port.name}] -> Aim at peer port + [F] to Connect (or [X] to Cancel)"
            self._draw_badge(surface, cx, cy + 38, txt, bg_color=(235, 246, 255), border_color=(0, 115, 230), text_color=(0, 70, 160))
        elif focused_port:
            peer = focused_port.cable.get_peer_port(focused_port) if focused_port.cable else None
            cable_info = f"-> Linked to {peer.device.hostname}:{peer.name}" if peer else "[Unconnected Port]"
            txt = f"[F] Plug/Unplug Cable | {focused_port.name.upper()} {cable_info}"
            self._draw_badge(surface, cx, cy + 38, txt, bg_color=(240, 252, 244), border_color=(15, 160, 75), text_color=(10, 110, 50))
        elif focused_dev:
            if focused_dev.device_type == "laptop":
                os_title = "Windows 11 Pro" if getattr(focused_dev, "os_type", "windows") == "windows" else "Ubuntu 22.04 LTS"
                txt = f"[E] Open {os_title} Desktop GUI ({focused_dev.hostname}) | [F] Cable Ports"
                self._draw_badge(surface, cx, cy + 38, txt, bg_color=(240, 248, 255), border_color=(0, 115, 230), text_color=(0, 60, 140))
            else:
                txt = f"[E] Cisco/Host CLI Console ({focused_dev.hostname}) | [F] Cable Ports | [Del] Delete"
                self._draw_badge(surface, cx, cy + 38, txt, bg_color=(255, 255, 255), border_color=(0, 115, 230), text_color=(15, 45, 90))

        # 4. Quick Device Hardware Inspector Card (Bottom-Right)
        if focused_dev:
            self._draw_inspector(surface, screen_w - 360, screen_h - 225, 340, 190, focused_dev, now)

        # 5. Mission Objective / Quest Checklist Card with Progress Bar (Top-Left)
        if current_objective or objective_checklist:
            self._draw_objective_card(surface, 20, 20, 500, current_mode_title, current_objective, objective_checklist, hint_text)

        # 6. Concept / Theory Panel (Top-Right, only in Tutorial mode)
        if concept_data:
            self._draw_concept_panel(surface, screen_w, concept_data)

        # 7. Bottom Navigation Control Bar
        is_sandbox = "SANDBOX" in (current_mode_title or "")
        self._draw_bottom_bar(surface, screen_w, screen_h, is_sandbox)

    def _draw_crosshair(self, surface, cx, cy, focused_dev, focused_port, held_cable_port, now):
        """Draws a high-tech precision targeting reticle with dynamic brackets and state indicators."""
        if focused_port:
            # Locked onto individual port: Golden/Emerald tight brackets
            color = (16, 175, 80)
            bracket_color = (0, 200, 100)
            b_size = 14
            b_gap = 7
        elif focused_dev:
            # Aimed at device chassis: High-tech Cyan expanded brackets
            color = (0, 130, 220)
            bracket_color = (0, 170, 245)
            b_size = 20
            b_gap = 12
        elif held_cable_port:
            # Carrying cable: Pulsing Blue/Cyan reticle
            pulse = 0.75 + 0.25 * math.sin(now * 5.0)
            color = (int(0 * pulse), int(140 * pulse), int(240 * pulse))
            bracket_color = color
            b_size = 16
            b_gap = 9
        else:
            # Default reticle: Subtle clean slate blue
            color = (0, 105, 195)
            bracket_color = (90, 140, 195)
            b_size = 12
            b_gap = 6

        # Center Precision Dot
        pygame.draw.circle(surface, color, (cx, cy), 2)

        # 4 Corner Angle Brackets
        gl = 5  # bracket arm length
        # Top-Left Bracket
        pygame.draw.line(surface, bracket_color, (cx - b_gap, cy - b_gap), (cx - b_gap + gl, cy - b_gap), 2)
        pygame.draw.line(surface, bracket_color, (cx - b_gap, cy - b_gap), (cx - b_gap, cy - b_gap + gl), 2)
        # Top-Right Bracket
        pygame.draw.line(surface, bracket_color, (cx + b_gap, cy - b_gap), (cx + b_gap - gl, cy - b_gap), 2)
        pygame.draw.line(surface, bracket_color, (cx + b_gap, cy - b_gap), (cx + b_gap, cy - b_gap + gl), 2)
        # Bottom-Left Bracket
        pygame.draw.line(surface, bracket_color, (cx - b_gap, cy + b_gap), (cx - b_gap + gl, cy + b_gap), 2)
        pygame.draw.line(surface, bracket_color, (cx - b_gap, cy + b_gap), (cx - b_gap, cy + b_gap - gl), 2)
        # Bottom-Right Bracket
        pygame.draw.line(surface, bracket_color, (cx + b_gap, cy + b_gap), (cx + b_gap - gl, cy + b_gap), 2)
        pygame.draw.line(surface, bracket_color, (cx + b_gap, cy + b_gap), (cx + b_gap, cy + b_gap - gl), 2)

        # Floating Port Tooltip Tag right above the crosshair when hovering a port
        if focused_port:
            port_name = focused_port.name.upper()
            state_str = "UP" if focused_port.is_link_up else ("DOWN" if focused_port.cable else "UNPLUGGED")
            tag_text = f"{port_name} [{state_str}]"
            tag_surf = self.font_mono_bold.render(tag_text, True, (255, 255, 255))
            tw = tag_surf.get_width() + 14
            th = 20
            tx = cx - tw // 2
            ty = cy - b_gap - 28

            # Tag pill background
            bg_c = (14, 150, 65) if focused_port.is_link_up else ((215, 125, 10) if focused_port.cable else (70, 85, 105))
            pygame.draw.rect(surface, bg_c, (tx, ty, tw, th), border_radius=4)
            surface.blit(tag_surf, (tx + 7, ty + 2))

    def _draw_noc_telemetry(self, surface, screen_w, now):
        """Renders live Datacenter NOC telemetry bandwidth waveform widget."""
        box_w = 260
        box_h = 36
        x = (screen_w - box_w) // 2
        y = 16

        rect = pygame.Rect(x, y, box_w, box_h)
        shadow_rect = pygame.Rect(x + 2, y + 2, box_w, box_h)
        pygame.draw.rect(surface, (200, 215, 235), shadow_rect, border_radius=6)
        pygame.draw.rect(surface, (252, 254, 255), rect, border_radius=6)
        pygame.draw.rect(surface, (0, 115, 230), rect, width=1, border_radius=6)

        # Pulsing green status LED dot
        pulse = 0.75 + 0.25 * math.sin(now * 4.0)
        led_c = (int(15 * pulse), int(220 * pulse), int(80 * pulse))
        pygame.draw.circle(surface, led_c, (x + 14, y + box_h // 2), 4)

        # Simulated dynamic network telemetry
        throughput = 54.2 + 8.5 * math.sin(now * 1.5) + 3.0 * math.cos(now * 3.7)
        packets = int(3200 + 450 * math.sin(now * 2.2))
        t_str = f"NOC: {throughput:.1f} Mbps  |  {packets} pps"
        lbl = self.font_mono.render(t_str, True, (20, 45, 75))
        surface.blit(lbl, (x + 26, y + 9))

        # Mini waveform visualizer bars on right
        for i in range(7):
            bx = x + box_w - 55 + i * 7
            bar_h = int(6 + 8 * math.sin(now * 5.0 + i * 1.2))
            bar_h = max(2, min(18, bar_h))
            by = y + box_h - 9 - bar_h
            pygame.draw.rect(surface, (0, 125, 230), (bx, by, 4, bar_h), border_radius=1)

    def _draw_badge(self, surface, x, y, text, bg_color, border_color, text_color):
        surf = self.font_bold.render(text, True, text_color)
        pad_x, pad_y = 14, 7
        w = surf.get_width() + pad_x * 2
        h = surf.get_height() + pad_y * 2
        rx = x - w // 2
        ry = y
        badge_rect = pygame.Rect(rx, ry, w, h)
        shadow_rect = pygame.Rect(rx + 2, ry + 2, w, h)
        pygame.draw.rect(surface, (200, 215, 235), shadow_rect, border_radius=6)
        pygame.draw.rect(surface, bg_color, badge_rect, border_radius=6)
        pygame.draw.rect(surface, border_color, badge_rect, width=1, border_radius=6)
        surface.blit(surf, (rx + pad_x, ry + pad_y))

    def _draw_inspector(self, surface, x, y, w, h, dev, now):
        """Enhanced Hardware Inspector Card with simulated CPU/RAM gauges and port LED matrix."""
        rect = pygame.Rect(x, y, w, h)
        shadow_rect = pygame.Rect(x + 2, y + 2, w, h)
        pygame.draw.rect(surface, (205, 218, 235), shadow_rect, border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), rect, border_radius=8)
        pygame.draw.rect(surface, (0, 115, 230), rect, width=1, border_radius=8)

        # Header Title Bar
        header_h = 28
        pygame.draw.rect(surface, (235, 244, 255), (x, y, w, header_h), border_top_left_radius=8, border_top_right_radius=8)

        if dev.device_type in ("isp_gateway", "isp") or (dev.device_type == "server" and "isp" in dev.hostname.lower()):
            badge_txt = "ISP WAN"
            badge_col = (0, 150, 200)
        else:
            badge_txt = dev.device_type.upper()
            badge_col = (0, 115, 230)
        title = f"INSPECT: {dev.hostname}"
        t_surf = self.font_bold.render(title, True, (0, 75, 160))
        surface.blit(t_surf, (x + 10, y + 5))

        # Type Pill Badge
        b_surf = self.font_small.render(badge_txt, True, (255, 255, 255))
        bw = b_surf.get_width() + 10
        bx = x + w - bw - 8
        pygame.draw.rect(surface, badge_col, (bx, y + 4, bw, 20), border_radius=4)
        surface.blit(b_surf, (bx + 5, y + 6))

        # Device details
        info_lines = [
            f"Location: RACK-0{dev.rack_id} (Slot: {dev.u_slot}U)",
            f"Power State: {'ONLINE (Dual Redundant PSU)' if dev.is_powered else 'OFF'}",
            f"Active Links: {sum(1 for p in dev.ports.values() if p.is_link_up)} / {len(dev.ports)} Interfaces Up"
        ]
        curr_y = y + 34
        for line in info_lines:
            s = self.font_main.render(line, True, (45, 60, 80))
            surface.blit(s, (x + 12, curr_y))
            curr_y += 18

        # Simulated Dynamic CPU Load & Memory Gauges
        active_ratio = sum(1 for p in dev.ports.values() if p.is_link_up) / max(1, len(dev.ports))
        cpu_load = int(12 + active_ratio * 35 + 8 * math.sin(now * 3.0))
        ram_gb = 2.4 + active_ratio * 4.2
        ram_total = 16 if dev.device_type == "server" else 4

        curr_y += 4
        # CPU Gauge Bar
        cpu_lbl = self.font_small.render(f"CPU: {cpu_load}%", True, (60, 75, 95))
        surface.blit(cpu_lbl, (x + 12, curr_y))
        bar_w = 75
        pygame.draw.rect(surface, (230, 235, 245), (x + 75, curr_y + 3, bar_w, 8), border_radius=3)
        pygame.draw.rect(surface, (0, 130, 230), (x + 75, curr_y + 3, int(bar_w * (cpu_load / 100.0)), 8), border_radius=3)

        # RAM Gauge Bar
        ram_lbl = self.font_small.render(f"RAM: {ram_gb:.1f}/{ram_total}GB", True, (60, 75, 95))
        surface.blit(ram_lbl, (x + 170, curr_y))
        pygame.draw.rect(surface, (230, 235, 245), (x + 252, curr_y + 3, bar_w, 8), border_radius=3)
        pygame.draw.rect(surface, (16, 165, 80), (x + 252, curr_y + 3, int(bar_w * (ram_gb / ram_total)), 8), border_radius=3)

        # Mini Port Status Matrix (Small labeled socket indicators)
        curr_y += 24
        lbl_p = self.font_small.render("PORT LED MATRIX:", True, (90, 105, 125))
        surface.blit(lbl_p, (x + 12, curr_y))
        curr_y += 16

        px = x + 12
        for p_name, p in dev.ports.items():
            color = (16, 175, 75) if p.is_link_up else ((225, 140, 20) if p.cable else (185, 195, 212))
            p_rect = pygame.Rect(px, curr_y, 22, 16)
            pygame.draw.rect(surface, color, p_rect, border_radius=3)
            # Port mini name
            lbl = self.font_small.render(p.name[:2], True, (255, 255, 255))
            surface.blit(lbl, (px + 3, curr_y + 1))
            px += 26
            if px > x + w - 30:
                break

    def _wrap_text(self, text, font, max_w):
        return list(_cached_wrap_text(text, font, max_w))

    def _draw_objective_card(self, surface, x, y, w, mode_title, current_obj, checklist, hint_text):
        """Draws Mission Objective card with dynamic checklist progress bar."""
        max_text_w = w - 32

        # 1. Pre-wrap all text blocks to compute dynamic card height
        goal_lines = self._wrap_text(f"Goal: {current_obj}", self.font_bold, max_text_w) if current_obj else []

        wrapped_checklist = []
        done_count = 0
        total_count = 0
        if checklist:
            total_count = len(checklist)
            for item in checklist:
                is_done = item.get("done", False)
                if is_done:
                    done_count += 1
                text = item.get("text", "")
                icon = "[v] " if is_done else "[ ] "
                item_lines = self._wrap_text(icon + text, self.font_main, max_text_w)
                wrapped_checklist.append((is_done, item_lines))

        hint_lines = self._wrap_text(f"Hint: {hint_text}", self.font_mono, max_text_w) if hint_text else []

        # Calculate exact height
        line_h = 22
        total_h = 36  # Header
        if total_count > 0:
            total_h += 24  # Progress bar height
        if goal_lines:
            total_h += len(goal_lines) * line_h + 6
        if wrapped_checklist:
            total_items_lines = sum(len(lines) for _, lines in wrapped_checklist)
            total_h += total_items_lines * line_h + 6
        if hint_lines:
            total_h += len(hint_lines) * 20 + 8

        total_h += 12  # Bottom padding

        rect = pygame.Rect(x, y, w, total_h)
        shadow_rect = pygame.Rect(x + 2, y + 3, w, total_h)
        pygame.draw.rect(surface, (210, 222, 238), shadow_rect, border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), rect, border_radius=8)
        pygame.draw.rect(surface, (0, 115, 230), rect, width=1, border_radius=8)

        # Header
        pygame.draw.rect(surface, (235, 244, 255), (x, y, w, 32), border_top_left_radius=8, border_top_right_radius=8)
        header_surf = self.font_bold.render(f"MISSION: {mode_title.upper()}", True, (0, 80, 175))
        surface.blit(header_surf, (x + 12, y + 7))

        curr_y = y + 40

        # Mission Progress Bar
        if total_count > 0:
            pct = done_count / float(total_count)
            bar_w = w - 24
            bar_h = 10
            pygame.draw.rect(surface, (230, 236, 246), (x + 12, curr_y, bar_w, bar_h), border_radius=5)
            # Animated gradient progress fill
            fill_w = int(bar_w * pct)
            if fill_w > 0:
                fill_color = (15, 170, 75) if pct >= 1.0 else (0, 125, 230)
                pygame.draw.rect(surface, fill_color, (x + 12, curr_y, fill_w, bar_h), border_radius=5)

            prog_lbl = self.font_small.render(f"Progress: {int(pct*100)}% ({done_count}/{total_count} Objectives Done)", True, (70, 90, 115))
            surface.blit(prog_lbl, (x + 12, curr_y + 12))
            curr_y += 30

        # Draw Goal
        for gl in goal_lines:
            g_surf = self.font_bold.render(gl, True, (0, 95, 190))
            surface.blit(g_surf, (x + 12, curr_y))
            curr_y += line_h
        if goal_lines:
            curr_y += 6

        # Draw Checklist
        for is_done, item_lines in wrapped_checklist:
            color = (14, 150, 65) if is_done else (40, 55, 75)
            for idx, il in enumerate(item_lines):
                x_offset = 14 if idx == 0 else 32
                i_surf = self.font_main.render(il, True, color)
                surface.blit(i_surf, (x + x_offset, curr_y))
                curr_y += line_h
        if wrapped_checklist:
            curr_y += 4

        # Draw Hint
        for hl in hint_lines:
            h_surf = self.font_mono.render(hl, True, (80, 105, 135))
            surface.blit(h_surf, (x + 12, curr_y))
            curr_y += 20

    def _draw_concept_panel(self, surface, screen_w, concept_data):
        """Draw a knowledge card in the top-right corner for tutorial concept explanations."""
        title, lines = concept_data
        panel_w = 380
        line_h = 18
        pad = 10
        total_h = 30 + len(lines) * line_h + pad * 2

        x = screen_w - panel_w - 18
        y = 18

        rect = pygame.Rect(x, y, panel_w, total_h)
        shadow = pygame.Rect(x + 2, y + 2, panel_w, total_h)
        pygame.draw.rect(surface, (205, 220, 240), shadow, border_radius=8)
        pygame.draw.rect(surface, (248, 252, 255), rect, border_radius=8)
        pygame.draw.rect(surface, (30, 130, 220), rect, width=1, border_radius=8)

        # Header
        pygame.draw.rect(surface, (220, 237, 255), (x, y, panel_w, 28),
                         border_top_left_radius=8, border_top_right_radius=8)
        try:
            icon_surf = self.font_bold.render(f"\U0001F4D6 LEARN: {title}", True, (10, 65, 150))
        except Exception:
            icon_surf = self.font_bold.render(f"LEARN: {title}", True, (10, 65, 150))
        surface.blit(icon_surf, (x + 10, y + 5))

        curr_y = y + 34
        for line in lines:
            color = (10, 90, 170) if line and not line.startswith(" ") and ":" in line[:18] else (40, 58, 80)
            lsurf = self.font_mono.render(line, True, color)
            surface.blit(lsurf, (x + pad, curr_y))
            curr_y += line_h

    def _draw_bottom_bar(self, surface, screen_w, screen_h, is_sandbox=False):
        bar_h = 30
        bar_rect = pygame.Rect(0, screen_h - bar_h, screen_w, bar_h)
        pygame.draw.rect(surface, (244, 247, 252, 240), bar_rect)
        pygame.draw.line(surface, (215, 226, 240), (0, screen_h - bar_h), (screen_w, screen_h - bar_h), 1)

        if is_sandbox:
            controls = "[WASD] Move   [C] Crouch   [E] CLI   [F] Cable   [N] Rack Manager (Add/Remove)   [Del] Quick Delete   [M] 2D Map   [K] Save   [L] Load   [P] Pause"
        else:
            controls = "[WASD] Move   [C] Crouch   [Mouse] Look   [E] Terminal   [F] Cable Action   [M] 2D Topology   [P] Pause Menu   [F11] Fullscreen"
        ctrl_surf = self.font_main.render(controls, True, (50, 75, 105))
        surface.blit(ctrl_surf, (20, screen_h - bar_h + 6))
