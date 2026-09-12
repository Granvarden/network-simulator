"""
engine/audio.py - Procedural Sound Effects & Ambient Audio Engine
Generates Datacenter ambient fan hum, mechanical keyboard clicks,
RJ45/Fiber cable snap sounds, and ICMP Ping chimes using NumPy + Pygame Mixer.
"""

import pygame
import numpy as np

class SoundManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SoundManager()
        return cls._instance

    def __init__(self):
        self.enabled = True
        self.volume = 0.7
        self.ambient_channel = None
        self.fan_sound = None
        self.key_sounds = []
        self.cable_snap = None
        self.ping_success = None
        self.ping_fail = None
        self.chime_success = None

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self._generate_sounds()
        except Exception as e:
            print(f"[SoundManager] Audio initialization warning: {e}")
            self.enabled = False

    def _generate_sounds(self):
        sr = 44100

        # 1. Datacenter Ambient Fan Hum (3 seconds loopable noise + 60Hz hum)
        dur = 3.0
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        # Pinkish noise + multiple harmonic fans (60Hz, 120Hz, 300Hz, 1800Hz)
        noise = np.random.normal(0, 0.08, len(t))
        hum = (0.25 * np.sin(2 * np.pi * 58.0 * t) +
               0.18 * np.sin(2 * np.pi * 116.0 * t) +
               0.12 * np.sin(2 * np.pi * 232.0 * t) +
               0.08 * np.sin(2 * np.pi * 480.0 * t) +
               0.04 * np.sin(2 * np.pi * 1200.0 * t))
        ambient = (noise + hum) * 0.35
        ambient = np.clip(ambient, -1.0, 1.0)
        pcm_ambient = (ambient * 32767).astype(np.int16)
        stereo_ambient = np.column_stack([pcm_ambient, pcm_ambient])
        self.fan_sound = pygame.sndarray.make_sound(stereo_ambient)

        # 2. Mechanical Keyboard Click variations
        for freq_base in [2200, 2600, 3100, 3500]:
            k_dur = 0.035
            kt = np.linspace(0, k_dur, int(sr * k_dur), endpoint=False)
            env = np.exp(-kt * 180)
            k_wave = np.sin(2 * np.pi * freq_base * kt) * env * 0.4
            # Add click pop
            click_noise = np.random.normal(0, 0.2, len(kt)) * env
            k_total = np.clip(k_wave + click_noise, -1.0, 1.0)
            pcm_k = (k_total * 32767).astype(np.int16)
            self.key_sounds.append(pygame.sndarray.make_sound(np.column_stack([pcm_k, pcm_k])))

        # 3. Cable Snap / Click (RJ45 locking into port)
        c_dur = 0.06
        ct = np.linspace(0, c_dur, int(sr * c_dur), endpoint=False)
        c_env = np.exp(-ct * 110)
        c_pop = (0.5 * np.sin(2 * np.pi * 450 * ct) + 0.3 * np.sin(2 * np.pi * 950 * ct)) * c_env
        c_noise = np.random.normal(0, 0.3, len(ct)) * c_env
        c_total = np.clip(c_pop + c_noise, -1.0, 1.0)
        pcm_c = (c_total * 32767).astype(np.int16)
        self.cable_snap = pygame.sndarray.make_sound(np.column_stack([pcm_c, pcm_c]))

        # 4. ICMP Ping Success (High electronic beep - 1400Hz)
        p_dur = 0.07
        pt = np.linspace(0, p_dur, int(sr * p_dur), endpoint=False)
        p_env = np.exp(-pt * 40)
        p_wave = (np.sin(2 * np.pi * 1450 * pt) * 0.45) * p_env
        pcm_p = (p_wave * 32767).astype(np.int16)
        self.ping_success = pygame.sndarray.make_sound(np.column_stack([pcm_p, pcm_p]))

        # 5. ICMP Ping Fail / Timeout (Low dull buzz - 180Hz)
        f_dur = 0.15
        ft = np.linspace(0, f_dur, int(sr * f_dur), endpoint=False)
        f_env = np.exp(-ft * 25)
        f_wave = (np.sin(2 * np.pi * 180 * ft) * 0.5) * f_env
        pcm_f = (f_wave * 32767).astype(np.int16)
        self.ping_fail = pygame.sndarray.make_sound(np.column_stack([pcm_f, pcm_f]))

        # 6. Objective Complete Chime (Harmonic triad: C6, E6, G6)
        ch_dur = 0.45
        cht = np.linspace(0, ch_dur, int(sr * ch_dur), endpoint=False)
        ch_env = np.exp(-cht * 8)
        ch_wave = (0.3 * np.sin(2 * np.pi * 1046.5 * cht) +
                   0.3 * np.sin(2 * np.pi * 1318.5 * cht) +
                   0.4 * np.sin(2 * np.pi * 1567.9 * cht)) * ch_env
        pcm_ch = (np.clip(ch_wave, -1.0, 1.0) * 32767).astype(np.int16)
        self.chime_success = pygame.sndarray.make_sound(np.column_stack([pcm_ch, pcm_ch]))

    def start_ambient(self):
        if not self.enabled or not self.fan_sound:
            return
        try:
            if self.ambient_channel is None or not self.ambient_channel.get_busy():
                self.ambient_channel = pygame.mixer.Channel(0)
                self.ambient_channel.set_volume(0.22 * self.volume)
                self.ambient_channel.play(self.fan_sound, loops=-1)
        except Exception:
            pass

    def stop_ambient(self):
        if self.ambient_channel:
            self.ambient_channel.stop()

    def play_key(self):
        if not self.enabled or not self.key_sounds:
            return
        try:
            snd = np.random.choice(self.key_sounds)
            snd.set_volume(0.25 * self.volume)
            snd.play()
        except Exception:
            pass

    def play_cable(self):
        if not self.enabled or not self.cable_snap:
            return
        try:
            self.cable_snap.set_volume(0.6 * self.volume)
            self.cable_snap.play()
        except Exception:
            pass

    def play_ping(self, success=True):
        if not self.enabled:
            return
        try:
            if success and self.ping_success:
                self.ping_success.set_volume(0.4 * self.volume)
                self.ping_success.play()
            elif not success and self.ping_fail:
                self.ping_fail.set_volume(0.4 * self.volume)
                self.ping_fail.play()
        except Exception:
            pass

    def play_objective(self):
        if not self.enabled or not self.chime_success:
            return
        try:
            self.chime_success.set_volume(0.55 * self.volume)
            self.chime_success.play()
        except Exception:
            pass

    def play_error(self):
        self.play_ping(success=False)
