"""
cli/terminal_ui.py - Graphical Terminal Window UI (Pygame Surface Overlay)
Renders Cisco IOS / Linux Console with cursor, text history, scrollback,
and real-time packet-by-packet ping streaming with audio and LED synchronization.
"""

import pygame
import time
from .command_executor import CommandExecutor
from .command_parser import CommandParser
from engine.audio import SoundManager

class TerminalUI:
    def __init__(self, device, width=880, height=540):
        self.device = device
        self.executor = CommandExecutor(device)
        self.parser = CommandParser(self.executor)
        self.sound = SoundManager.get_instance()
        self.on_command_executed_callback = None

        self.width = width
        self.height = height
        self.surface = pygame.Surface((width, height), pygame.SRCALPHA)

        # Monospace font
        if not pygame.font.get_init():
            pygame.font.init()
        self.font = pygame.font.SysFont("Consolas", 15) or pygame.font.Font(None, 18)
        self.title_font = pygame.font.SysFont("Segoe UI", 13, bold=True) or pygame.font.Font(None, 16)

        # Text & buffer management
        self.history_lines = [
            f"=== NetEngineer Cisco IOS Console: {device.hostname} ===",
            "Connected via Roll-over Serial Cable (Speed: 9600 baud, 8-N-1)",
            "Press '?' or 'help' for command list. Press [ESC] to detach terminal.",
            ""
        ]
        self.input_buffer = ""
        self.cmd_history = []
        self.history_index = -1
        self.cursor_pos = 0
        self.scroll_offset = 0

        # Colors - Modern Enterprise Light Console Theme
        self.COLOR_BG = (252, 253, 255, 248)        # Clean off-white surface
        self.COLOR_HEADER = (235, 242, 252)          # Soft ice-blue title bar
        self.COLOR_BORDER = (0, 115, 230)            # Crisp enterprise blue accent
        self.COLOR_TEXT = (25, 35, 50)               # Deep crisp charcoal
        self.COLOR_PROMPT = (10, 125, 60)            # Deep emerald green
        self.COLOR_TITLE = (15, 45, 90)              # Navy blue title
        self.COLOR_CURSOR = (0, 110, 220)            # Blue caret
        self.COLOR_SHADOW = (180, 195, 215, 120)

        self.is_open = False
        self._last_key_sound_time = 0.0

        # Real-time interactive job state (e.g. progressive ping execution)
        self.active_job = None
        self.active_job_progress = 0
        self.active_job_timer = 0.0
        self.active_job_interval = 0.28  # seconds between ping packets
        self.active_job_results = []
        self.active_job_rtts = []
        self.active_job_ttls = []
        self.active_job_line_idx = None
        self.active_job_cmd = ""

    def _play_key_sound(self):
        now = time.time()
        if now - self._last_key_sound_time >= 0.05:
            self.sound.play_key()
            self._last_key_sound_time = now

    def open(self):
        self.is_open = True
        self.input_buffer = ""
        self.cursor_pos = 0
        try:
            pygame.key.set_repeat(280, 28)
        except pygame.error:
            pass

    def close(self):
        self.is_open = False
        try:
            pygame.key.set_repeat(0)
        except pygame.error:
            pass

    def abort_job(self):
        """Aborts currently active running job (Ctrl+C / Escape)."""
        if not self.active_job:
            return
        if self.active_job["type"] == "cisco":
            recv = sum(1 for c in self.active_job_results if c == "!")
            sent = max(1, len(self.active_job_results))
            loss = int(((sent - recv) / sent) * 100)
            self.history_lines.append(f"\nSuccess rate is {100 - loss} percent ({recv}/{sent})")
        else:
            self.history_lines.append("^C")
            recv = sum(1 for c in self.active_job_results if c == "!")
            sent = max(1, len(self.active_job_results))
            loss = int(((sent - recv) / sent) * 100)
            self.history_lines.append(f"--- {self.active_job['target_ip']} ping statistics ---")
            self.history_lines.append(f"{sent} packets transmitted, {recv} received, {loss}% packet loss")
        self.history_lines.append("")
        self.active_job = None
        self.scroll_offset = 0

    def update(self, dt):
        """Updates active streaming jobs (e.g. ping packets) frame-by-frame."""
        if not self.active_job:
            return

        self.active_job_timer += dt
        if self.active_job_timer < self.active_job_interval:
            return

        self.active_job_timer = 0.0
        job = self.active_job
        pkt_idx = self.active_job_progress

        step = self.executor.packet_engine.trace_single_packet(
            self.device,
            job["target_ip"],
            pkt_index=pkt_idx,
            count=job["count"],
            timeout=job["timeout"],
            data_bytes=job["size"],
            source_interface=job.get("source_if"),
            simulate_arp=True
        )

        code = step["status_code"]
        self.active_job_results.append(code)

        if step["success"]:
            self.active_job_rtts.append(step["rtt_ms"])
            self.active_job_ttls.append(step["ttl"])
            self.sound.play_ping(success=True)
        else:
            self.sound.play_ping(success=False)

        # Update terminal text
        if job["type"] == "cisco":
            if self.active_job_line_idx is not None and self.active_job_line_idx < len(self.history_lines):
                self.history_lines[self.active_job_line_idx] += code
        else:
            # Linux server format
            if step["success"]:
                self.history_lines.append(
                    f"{job['size']+8} bytes from {job['target_ip']}: icmp_seq={pkt_idx+1} ttl={step['ttl']} time={step['rtt_ms']} ms"
                )
            elif code == "A":
                self.history_lines.append(f"From {self.device.hostname}: Packet filtered by administrative policy")
            else:
                self.history_lines.append(f"From {self.device.hostname}: Destination Host Unreachable")

        self.active_job_progress += 1
        self.scroll_offset = 0

        # Check for ping completion
        if self.active_job_progress >= job["count"]:
            if job["type"] == "cisco":
                recv = sum(1 for c in self.active_job_results if c == "!")
                sent = len(self.active_job_results)
                loss = int(((sent - recv) / sent) * 100)
                self.history_lines.append(f"Success rate is {100 - loss} percent ({recv}/{sent})")
                if self.active_job_rtts:
                    min_r = int(min(self.active_job_rtts)) if min(self.active_job_rtts).is_integer() else round(min(self.active_job_rtts), 1)
                    avg_r = round(sum(self.active_job_rtts)/len(self.active_job_rtts), 1)
                    max_r = int(max(self.active_job_rtts)) if max(self.active_job_rtts).is_integer() else round(max(self.active_job_rtts), 1)
                    self.history_lines.append(f"round-trip min/avg/max = {min_r}/{avg_r}/{max_r} ms")
            else:
                recv = sum(1 for c in self.active_job_results if c == "!")
                sent = len(self.active_job_results)
                loss = int(((sent - recv) / sent) * 100)
                self.history_lines.append(f"--- {job['target_ip']} ping statistics ---")
                total_time = int(sent * 1000 + 4)
                self.history_lines.append(f"{sent} packets transmitted, {recv} received, {loss}% packet loss, time {total_time}ms")
                if self.active_job_rtts:
                    min_r = round(min(self.active_job_rtts), 3)
                    avg_r = round(sum(self.active_job_rtts)/len(self.active_job_rtts), 3)
                    max_r = round(max(self.active_job_rtts), 3)
                    mdev_r = round(sum(abs(x - avg_r) for x in self.active_job_rtts)/len(self.active_job_rtts), 3)
                    self.history_lines.append(f"rtt min/avg/max/mdev = {min_r:.3f}/{avg_r:.3f}/{max_r:.3f}/{mdev_r:.3f} ms")

            self.history_lines.append("")
            # Notify game mode of completed command
            if self.on_command_executed_callback:
                recent_output = "\n".join(self.history_lines[-12:])
                self.on_command_executed_callback(self.device, self.active_job_cmd, recent_output)

            self.active_job = None
            self.scroll_offset = 0

    def handle_key(self, event):
        if not self.is_open:
            return

        # While a job is running, allow aborting via Ctrl+C, Escape, or Ctrl+Shift+6
        if self.active_job:
            if event.key == pygame.K_ESCAPE:
                self.abort_job()
                return
            if event.key == pygame.K_c and (event.mod & pygame.KMOD_CTRL):
                self.abort_job()
                return
            if event.key == pygame.K_6 and (event.mod & pygame.KMOD_CTRL):
                self.abort_job()
                return
            # Block all other input while job is streaming
            return

        if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
            line = self.input_buffer
            prompt = self.executor.get_prompt()
            self.history_lines.append(f"{prompt}{line}")
            if line.strip():
                self.cmd_history.append(line)
                self.history_index = -1

            # Check if this command can be run as a progressive streaming job (ping)
            is_ping, ping_job = self.executor.parse_ping_job(line)
            if is_ping and ping_job:
                self.active_job = ping_job
                self.active_job_progress = 0
                self.active_job_timer = 0.0
                self.active_job_results = []
                self.active_job_rtts = []
                self.active_job_ttls = []
                self.active_job_cmd = line

                for h_line in ping_job["header_lines"]:
                    self.history_lines.append(h_line)

                if ping_job["type"] == "cisco":
                    self.history_lines.append("")
                    self.active_job_line_idx = len(self.history_lines) - 1
                else:
                    self.active_job_line_idx = None
            else:
                output = self.executor.execute(line)
                if output:
                    for out_line in output.split("\n"):
                        self.history_lines.append(out_line)
                if self.on_command_executed_callback and line.strip():
                    self.on_command_executed_callback(self.device, line, output or "")

            self.input_buffer = ""
            self.cursor_pos = 0
            self.scroll_offset = 0
            self.sound.play_key()

        elif event.key == pygame.K_BACKSPACE:
            if self.cursor_pos > 0:
                self.input_buffer = self.input_buffer[:self.cursor_pos-1] + self.input_buffer[self.cursor_pos:]
                self.cursor_pos -= 1
                self._play_key_sound()

        elif event.key == pygame.K_DELETE:
            if self.cursor_pos < len(self.input_buffer):
                self.input_buffer = self.input_buffer[:self.cursor_pos] + self.input_buffer[self.cursor_pos+1:]
                self._play_key_sound()

        elif event.key == pygame.K_LEFT:
            if self.cursor_pos > 0:
                self.cursor_pos -= 1

        elif event.key == pygame.K_RIGHT:
            if self.cursor_pos < len(self.input_buffer):
                self.cursor_pos += 1

        elif event.key == pygame.K_HOME:
            self.cursor_pos = 0

        elif event.key == pygame.K_END:
            self.cursor_pos = len(self.input_buffer)

        elif event.key == pygame.K_UP:
            if self.cmd_history:
                if self.history_index == -1:
                    self.history_index = len(self.cmd_history) - 1
                elif self.history_index > 0:
                    self.history_index -= 1
                self.input_buffer = self.cmd_history[self.history_index]
                self.cursor_pos = len(self.input_buffer)

        elif event.key == pygame.K_DOWN:
            if self.cmd_history and self.history_index != -1:
                if self.history_index < len(self.cmd_history) - 1:
                    self.history_index += 1
                    self.input_buffer = self.cmd_history[self.history_index]
                else:
                    self.history_index = -1
                    self.input_buffer = ""
                self.cursor_pos = len(self.input_buffer)

        elif event.key == pygame.K_TAB:
            completions = self.parser.get_completions(self.input_buffer)
            if len(completions) == 1:
                self.input_buffer = completions[0] + " "
                self.cursor_pos = len(self.input_buffer)
            elif len(completions) > 1:
                self.history_lines.append(f"{self.executor.get_prompt()}{self.input_buffer}")
                self.history_lines.append("  ".join(completions))
            self.sound.play_key()

        elif event.key == pygame.K_PAGEUP:
            self.scroll_offset = min(len(self.history_lines) - 5, self.scroll_offset + 5)
        elif event.key == pygame.K_PAGEDOWN:
            self.scroll_offset = max(0, self.scroll_offset - 5)

        else:
            if event.unicode and event.unicode.isprintable():
                self.input_buffer = (self.input_buffer[:self.cursor_pos] +
                                     event.unicode +
                                     self.input_buffer[self.cursor_pos:])
                self.cursor_pos += len(event.unicode)
                self._play_key_sound()

    def render(self):
        self.surface.fill((0, 0, 0, 0))
        w, h = self.width, self.height

        # Background Window Box
        pygame.draw.rect(self.surface, self.COLOR_BG, (0, 0, w, h), border_radius=8)
        pygame.draw.rect(self.surface, self.COLOR_BORDER, (0, 0, w, h), width=2, border_radius=8)

        # Header Bar
        pygame.draw.rect(self.surface, self.COLOR_HEADER, (0, 0, w, 32), border_top_left_radius=8, border_top_right_radius=8)
        pygame.draw.line(self.surface, self.COLOR_BORDER, (0, 32), (w, 32), 1)

        # Window Title & Connection Status
        status_suffix = " [Executing...]" if self.active_job else f" - Mode: {self.executor.mode}"
        title = f"CONSOLE TERMINAL: {self.device.hostname} [Port: Con0 - 9600 baud]{status_suffix}"
        t_surf = self.title_font.render(title, True, self.COLOR_TITLE)
        self.surface.blit(t_surf, (14, 8))

        close_hint = self.title_font.render("[ESC] Detach Terminal", True, (90, 115, 145))
        self.surface.blit(close_hint, (w - 180, 8))

        # Terminal Content Area
        line_height = 20
        content_top = 42
        max_visible_lines = (h - 50) // line_height

        # Calculate history window with scroll offset
        start_idx = max(0, len(self.history_lines) - max_visible_lines - self.scroll_offset)
        end_idx = max(0, len(self.history_lines) - self.scroll_offset)
        visible_history = self.history_lines[start_idx:end_idx]

        y = content_top
        for line in visible_history:
            txt_surf = self.font.render(line, True, self.COLOR_TEXT)
            self.surface.blit(txt_surf, (14, y))
            y += line_height

        # Draw Active Prompt line if no active job is running
        if self.scroll_offset == 0:
            if not self.active_job:
                prompt_str = self.executor.get_prompt()
                prompt_surf = self.font.render(prompt_str, True, self.COLOR_PROMPT)
                p_w = prompt_surf.get_width()
                input_surf = self.font.render(self.input_buffer, True, self.COLOR_TEXT)

                self.surface.blit(prompt_surf, (14, y))
                self.surface.blit(input_surf, (14 + p_w, y))

                # Blinking Caret Cursor
                if int(time.time() * 2) % 2 == 0:
                    cursor_x_offset = self.font.size(self.input_buffer[:self.cursor_pos])[0]
                    cursor_rect = pygame.Rect(14 + p_w + cursor_x_offset, y + 2, 8, line_height - 4)
                    pygame.draw.rect(self.surface, self.COLOR_CURSOR, cursor_rect)

        return self.surface
