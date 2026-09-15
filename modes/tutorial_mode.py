"""
modes/tutorial_mode.py - Modular Chapter-Based Guided Network Engineer Academy

Chapter 1: Datacenter Onboarding (5 Guided Phases)
  Phase 0: สอนเล่น (Basic Controls, Movement, Sprint & Camera Look)
  Phase 1: สอนติดตั้ง device ตู้ rack (Rack Device Manager [N] & Equipment Mounting)
  Phase 2: สอนต่อสาย (Physical Layer Cabling: Cat6 Server eth0 → Switch g0/1)
  Phase 3: สอนใช้ command แค่เข้าหน้า config (Cisco IOS Navigation: User > Privileged > Global Config)
  Phase 4: สอนใช้ 2D topology (Packet Tracer Mode: Pan, Zoom, Node Inspection)
"""

import os
import json
import math
import pygame

from .base_mode import BaseMode
from network.switch import Switch
from network.router import Router
from network.host import Host
from network.cable import Cable, CableType
from engine.audio import SoundManager


# ---------------------------------------------------------------------------
# Concept explanations shown as "📖 Learn" panel in the HUD
# ---------------------------------------------------------------------------
CONCEPT_TEXTS = {
    0: (
        "CONTROLS & 3D DATACENTER",
        [
            "WASD          Walk forward / left / back / right",
            "Mouse Look    Aim crosshair at datacenter equipment",
            "Shift         Hold to Sprint across the room",
            "Ctrl          Crouch to inspect low rack slots",
            "E             Open Cisco IOS / Linux Console",
            "F             Pick up & connect network cables",
            "N             Open 42U Rack Device Manager",
            "M             Open 2D Logical Topology Map",
            "P / Esc       Pause Menu",
        ]
    ),
    1: (
        "42U RACK CABINET & MOUNTING",
        [
            "Rack Unit (U) Standard height unit: 1U = 1.75 in (44.45mm)",
            "RACK-01       Compute & Access Layer (Servers, Switch)",
            "RACK-02       Core & Edge Layer (Routers, Firewalls)",
            "RACK-03       SAN Storage & Backup Infrastructure",
            "Mounting:     Press [N] to open Rack Device Manager",
            "Slot 24U:     Select Switch, choose RACK-01 Slot 24U,",
            "              and click '+ INSTALL TO RACK'.",
        ]
    ),
    2: (
        "PHYSICAL LAYER & CABLING",
        [
            "Cat6 UTP      Copper twisted-pair cable (RJ45 connector)",
            "Link LEDs     Green = Physical Link UP / Connected",
            "              Amber = Administratively Shutdown",
            "              OFF   = No physical connection",
            "Cabling Hint  Stand near RACK-01: press [F] on eth0,",
            "              then press [F] on switch port g0/1.",
            "Cancel Hand   Press [X] to drop cable in hand.",
        ]
    ),
    3: (
        "CISCO IOS MODE HIERARCHY",
        [
            "User EXEC     Switch>          Basic viewing commands only",
            "Privileged    Switch#          Type 'enable' (full admin)",
            "Global Config Switch(config)#  Type 'configure terminal'",
            "              (Used to configure ports, VLANs, IPs)",
            "Navigation:   Switch>  enable  -->  Switch#",
            "              Switch#  conf t  -->  Switch(config)#",
            "Help System   Type '?' or 'help' at any prompt",
        ]
    ),
    4: (
        "2D LOGICAL TOPOLOGY",
        [
            "Packet Tracer Intuitive 2D network diagram view",
            "Pan & Zoom    Drag Left Mouse to pan, Wheel to zoom",
            "Inspector     Click on any device to view live ports",
            "Realtime Sync Changes in 2D immediately sync with 3D!",
            "Exit 2D View  Press [M] or [ESC] to return to 3D room",
        ]
    ),
}


class TutorialMode(BaseMode):
    """
    Modular Chapter-Based Network Engineer Training Course.
    Chapter 1: Datacenter Onboarding (5 progressive guided phases).
    """

    def __init__(self, chapter=1):
        super().__init__(f"TUTORIAL CHAPTER {chapter}: DATACENTER ONBOARDING")
        self.chapter = chapter
        self.step = 0
        self.max_steps = 4  # 0 to 4 (5 phases)
        self.sound = SoundManager.get_instance()
        self.device_counter = 10
        self.status_msg = ""
        self.is_completed = False

        # Phase 0: Controls & Movement
        self.has_moved = False
        self.has_looked_around = False
        self.has_approached_rack = False
        self._total_mouse_dx = 0.0
        self._step0_camera_yaw_start = None

        # Phase 1: Rack Equipment Mounting
        self.has_opened_rack_manager = False
        self.has_mounted_switch = False

        # Phase 2: Physical Cabling
        self.cable_picked_up = False
        self.has_cabled_server_to_sw = False

        # Phase 3: Cisco IOS Navigation to Config Mode
        self.has_opened_terminal = False
        self.has_used_enable = False
        self.has_entered_config = False

        # Phase 4: 2D Logical Topology
        self.has_opened_topology = False
        self.has_panned_or_zoomed = False
        self.has_inspected_topology_device = False
        self.has_returned_to_3d = False

        self.setup()

    # ------------------------------------------------------------------
    # Rack Helper Methods
    # ------------------------------------------------------------------
    @staticmethod
    def calculate_rack_position(rack_id, u_slot):
        """Calculates 3D world coordinates (x, y, z) for a device given its rack and U-slot."""
        x = (rack_id - 2) * 1.4
        z = -1.5
        y = round(0.14 + (u_slot / 42.0) * 1.85, 2)
        return x, y, z

    def is_slot_occupied(self, rack_id, u_slot, needed_u=1, exclude_dev_id=None):
        """Checks if target U-slot range is occupied in the specified rack."""
        req_min = u_slot
        req_max = u_slot + needed_u - 1
        for dev in self.devices:
            if dev.rack_id != rack_id:
                continue
            if exclude_dev_id and dev.id == exclude_dev_id:
                continue
            dev_span = 1 if dev.device_type in ("switch", "firewall", "isp_gateway", "isp") else 2
            dev_min = dev.u_slot
            dev_max = dev.u_slot + dev_span - 1
            if not (req_max < dev_min or req_min > dev_max):
                return True, dev
        return False, None

    def add_device(self, device_type, rack_id, u_slot, hostname=None, num_ports=None):
        """Installs a new device into the rack with collision detection."""
        rack_id = int(rack_id)
        u_slot = int(u_slot)
        if rack_id not in (1, 2, 3):
            return False, f"Invalid Rack ID: {rack_id}. Choose 1, 2, or 3.", None

        needed_u = 1 if device_type in ("switch", "firewall", "isp_gateway", "isp") else 2
        if u_slot < 1 or u_slot + needed_u - 1 > 42:
            return False, f"Slot {u_slot}U exceeds rack boundaries (1-42U).", None

        occupied, occ_dev = self.is_slot_occupied(rack_id, u_slot, needed_u)
        if occupied:
            return False, f"Slot {u_slot}U is occupied by {occ_dev.hostname}.", None

        self.device_counter += 1
        cnt = self.device_counter

        if device_type == "switch":
            dev_id = f"sw_{cnt}"
            h_name = hostname.strip() if hostname else "Core-Switch-01"
            dev = Switch(dev_id, hostname=h_name, rack_id=rack_id, u_slot=u_slot, num_ports=num_ports or 8)
            self.switch1 = dev
        elif device_type == "router":
            dev_id = f"rtr_{cnt}"
            h_name = hostname.strip() if hostname else "Edge-Router-01"
            dev = Router(dev_id, hostname=h_name, rack_id=rack_id, u_slot=u_slot, num_ports=num_ports or 4)
            self.router1 = dev
        else:
            dev_id = f"srv_{cnt}"
            h_name = hostname.strip() if hostname else f"Server-0{cnt}"
            dev = Host(dev_id, hostname=h_name, device_type="server", rack_id=rack_id, u_slot=u_slot)

        dev.pos_x, dev.pos_y, dev.pos_z = self.calculate_rack_position(rack_id, u_slot)
        self.devices.append(dev)
        self.status_msg = f"Installed {dev.hostname} at RACK-0{rack_id} (Slot {u_slot}U)!"
        self.sound.play_objective()

        # If in step 1 and switch is mounted, advance
        if self.step == 1 and dev.device_type == "switch" and rack_id == 1:
            self.has_mounted_switch = True
            # Re-wire console cable from Windows Laptop to Switch con0 for convenience
            if hasattr(self, "laptop_win") and "con0" in self.laptop_win.ports and "con0" in dev.ports:
                for c in list(self.cables):
                    if c.cable_type == CableType.CONSOLE:
                        c.disconnect()
                        if c in self.cables:
                            self.cables.remove(c)
                con_cable = Cable(self.laptop_win.ports["con0"], dev.ports["con0"], CableType.CONSOLE)
                self.cables.append(con_cable)
            self._advance_step(2)

        return True, self.status_msg, dev

    def remove_device(self, device_or_id):
        """Unplugs all connected cables and removes device from rack."""
        dev = next((d for d in self.devices if d.id == device_or_id), None) if isinstance(device_or_id, str) else device_or_id
        if not dev or dev not in self.devices:
            return False, "Device not found."

        cables_to_remove = [
            c for c in self.cables
            if (c.port_a and c.port_a.device == dev) or (c.port_b and c.port_b.device == dev)
        ]
        for c in cables_to_remove:
            c.disconnect()
            if c in self.cables:
                self.cables.remove(c)

        self.devices.remove(dev)
        if dev == getattr(self, "switch1", None):
            self.switch1 = None
            self.has_mounted_switch = False
        self.sound.play_key()
        return True, f"Removed {dev.hostname} from rack."

    # ------------------------------------------------------------------
    # Setup / Reset
    # ------------------------------------------------------------------
    def setup(self):
        """Build initial datacenter scene for Chapter 1."""
        self.devices = []
        self.cables = []
        self.step = 0
        self.is_completed = False

        # Reset all completion flags
        self.has_moved = False
        self.has_looked_around = False
        self.has_approached_rack = False
        self._total_mouse_dx = 0.0
        self._step0_camera_yaw_start = None

        self.has_opened_rack_manager = False
        self.has_mounted_switch = False

        self.cable_picked_up = False
        self.has_cabled_server_to_sw = False

        self.has_opened_terminal = False
        self.has_used_enable = False
        self.has_entered_config = False

        self.has_opened_topology = False
        self.has_panned_or_zoomed = False
        self.has_inspected_topology_device = False
        self.has_returned_to_3d = False

        # 1. Pre-mount Web-Server-01 at RACK-01 Slot 12U
        self.server1 = Host("srv1", hostname="Web-Server-01",
                            device_type="server", rack_id=1, u_slot=12)
        self.server1.pos_x, self.server1.pos_y, self.server1.pos_z = -1.4, 0.70, -1.5
        self.server1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")
        self.devices.append(self.server1)

        # 2. Dual Workstation Laptops on Tech Desk
        self.laptop_win = Host("lap1", hostname="Win-Laptop-01",
                               device_type="laptop", rack_id=0, u_slot=0, os_type="windows")
        self.laptop_win.pos_x, self.laptop_win.pos_y, self.laptop_win.pos_z = -3.55, 0.77, 0.50
        self.laptop_win.configure_ip("192.168.1.99", "255.255.255.0", gateway="192.168.1.1", dns="8.8.8.8")
        self.devices.append(self.laptop_win)
        self.laptop = self.laptop_win

        self.laptop_ubu = Host("lap2", hostname="Ubuntu-Laptop-02",
                               device_type="laptop", rack_id=0, u_slot=0, os_type="ubuntu")
        self.laptop_ubu.pos_x, self.laptop_ubu.pos_y, self.laptop_ubu.pos_z = -2.85, 0.77, 0.50
        self.laptop_ubu.configure_ip("192.168.1.100", "255.255.255.0", gateway="192.168.1.1", dns="8.8.8.8")
        self.devices.append(self.laptop_ubu)

        # Pre-wire initial rollover console cable on engineer workbench
        con_cable = Cable(self.laptop_win.ports["con0"], self.laptop_ubu.ports["con0"], CableType.CONSOLE)
        self.cables.append(con_cable)

        # Core-Switch-01 is NOT yet in the rack! It will be installed in Phase 1 (Slot 24U).
        self.switch1 = None
        self.router1 = None

    # ------------------------------------------------------------------
    # Update Loop & Phase Progressions
    # ------------------------------------------------------------------
    def update(self, dt, player_camera):
        # Phase 0: Orientation & Movement
        if self.step == 0:
            self._check_step0(player_camera)

        # Phase 1: Rack Equipment Mounting
        elif self.step == 1:
            self._check_step1()

        # Phase 2: Physical Cabling
        elif self.step == 2:
            self._check_step2()

        # Phase 3: Cisco IOS CLI Navigation
        elif self.step == 3:
            self._check_step3()

        # Phase 4: 2D Logical Topology
        elif self.step == 4:
            self._check_step4()

    def _check_step0(self, cam):
        """Track movement, mouse look, and approach to RACK-01."""
        if self._step0_camera_yaw_start is None:
            self._step0_camera_yaw_start = cam.yaw

        # Check mouse look yaw delta
        yaw_delta = abs(cam.yaw - self._step0_camera_yaw_start)
        if yaw_delta > 25.0:
            self.has_looked_around = True

        # Check movement distance from spawn
        dist_from_spawn = math.sqrt((cam.x - 0.0)**2 + (cam.z - 2.8)**2)
        if dist_from_spawn > 0.6:
            self.has_moved = True

        # Check approach to RACK-01
        dist_to_rack1 = math.sqrt((cam.x - (-1.4))**2 + (cam.z - (-1.5))**2)
        if dist_to_rack1 < 3.2:
            self.has_approached_rack = True

        if self.has_moved and self.has_looked_around and self.has_approached_rack:
            self._advance_step(1)

    def _check_step1(self):
        """Verify Switch is installed at RACK-01."""
        if self.switch1 and self.switch1 in self.devices and self.switch1.rack_id == 1:
            self.has_mounted_switch = True
            self._advance_step(2)

    def _check_step2(self):
        """Verify Web-Server-01 eth0 is cabled to Core-Switch-01 g0/1."""
        if not self.switch1:
            return
        p_server = self.server1.eth0
        p_sw = self.switch1.ports.get("g0/1")
        if p_server and p_sw and p_server.cable:
            peer = p_server.cable.get_peer_port(p_server)
            if peer == p_sw:
                self.has_cabled_server_to_sw = True
                self._advance_step(3)

    def _check_step3(self):
        """Verify player navigated Cisco IOS terminal to Global Config mode."""
        if self.has_entered_config:
            self._advance_step(4)

    def _check_step4(self):
        """Verify 2D Logical Topology inspection and return to 3D."""
        if (self.has_opened_topology and
                (self.has_panned_or_zoomed or self.has_inspected_topology_device) and
                self.has_returned_to_3d):
            if not self.is_completed:
                self.is_completed = True
                self.sound.play_objective()
                self._save_chapter_progress()

    def _advance_step(self, next_step):
        """Advance to next tutorial phase with chime sound."""
        self.step = next_step
        self.sound.play_objective()

    def _save_chapter_progress(self):
        """Record chapter completion in tutorial_progress.json."""
        progress_path = "tutorial_progress.json"
        data = {
            "unlocked_chapters": ["chapter_1", "chapter_2"],
            "completed_chapters": ["chapter_1"],
            "current_chapter": "chapter_1"
        }
        try:
            if os.path.exists(progress_path):
                with open(progress_path, "r", encoding="utf-8") as fp:
                    loaded = json.load(fp)
                    if isinstance(loaded, dict):
                        data = loaded
            if "completed_chapters" not in data:
                data["completed_chapters"] = []
            if "chapter_1" not in data["completed_chapters"]:
                data["completed_chapters"].append("chapter_1")
            if "unlocked_chapters" not in data:
                data["unlocked_chapters"] = ["chapter_1", "chapter_2"]
            elif "chapter_2" not in data["unlocked_chapters"]:
                data["unlocked_chapters"].append("chapter_2")

            with open(progress_path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # External Event Callbacks
    # ------------------------------------------------------------------
    def on_command_executed(self, device, command, output):
        """Track Cisco IOS command execution and mode transitions."""
        cmd = command.strip().lower()
        self.has_opened_terminal = True

        if cmd in ("enable", "en"):
            self.has_used_enable = True

        if cmd in ("configure terminal", "conf t", "configure t", "conf terminal"):
            self.has_entered_config = True

    def on_cable_connected(self, port_a, port_b):
        """Track cable plug actions."""
        if not self.switch1:
            return
        p_server = self.server1.eth0
        p_sw = self.switch1.ports.get("g0/1")
        if (port_a == p_server and port_b == p_sw) or (port_a == p_sw and port_b == p_server):
            self.has_cabled_server_to_sw = True

    def on_cable_picked_up(self):
        """Called when player picks up cable with [F]."""
        self.cable_picked_up = True

    def on_topology_event(self, event_type):
        """Called from 2D Topology view to track interactions."""
        if event_type == "open":
            self.has_opened_topology = True
        elif event_type in ("pan", "zoom"):
            self.has_panned_or_zoomed = True
        elif event_type == "inspect":
            self.has_inspected_topology_device = True
        elif event_type == "close":
            if self.has_opened_topology:
                self.has_returned_to_3d = True

    # ------------------------------------------------------------------
    # HUD Content Providers
    # ------------------------------------------------------------------
    def get_title(self):
        if self.is_completed:
            return "CHAPTER 1: DATACENTER ONBOARDING COMPLETED!"
        titles = {
            0: "PHASE 1/5: CONTROLS & MOVEMENT (สอนเล่น)",
            1: "PHASE 2/5: RACK MOUNTING (สอนติดตั้ง DEVICE ตู้ RACK)",
            2: "PHASE 3/5: PHYSICAL CABLING (สอนต่อสายเคเบิล)",
            3: "PHASE 4/5: CISCO CLI CONFIG MODE (สอนใช้คำสั่ง)",
            4: "PHASE 5/5: 2D LOGICAL TOPOLOGY (สอนใช้ 2D TOPOLOGY)",
        }
        return titles.get(self.step, "TUTORIAL: CHAPTER 1")

    def get_objective(self):
        if self.is_completed:
            return "Congratulations! You have mastered all 5 core Datacenter Onboarding fundamentals. Press [P] or [ESC] to return to Chapter Select."
        objectives = {
            0: "Controls Orientation: Move around the datacenter with [W][A][S][D], look with mouse, and walk close to RACK-01.",
            1: "Rack Mounting: Install a new Switch into RACK-01 at Slot 24U using the Rack Device Manager [N].",
            2: "Physical Cabling: Connect a Cat6 cable from Web-Server-01 (eth0) to your new Switch (g0/1).",
            3: "Cisco CLI Navigation: Open the Switch terminal [E], enter Privileged mode ('enable') then Global Config ('conf t').",
            4: "2D Logical Topology: Open the Packet Tracer map [M], pan/zoom around, inspect a device, and return to 3D room.",
        }
        return objectives.get(self.step, "")

    def get_checklist(self):
        if self.step == 0:
            return [
                {"text": "Walk around the datacenter using [W][A][S][D] keys", "done": self.has_moved},
                {"text": "Look around the room by moving your Mouse", "done": self.has_looked_around},
                {"text": "Walk close to RACK-01 (the metal cabinet on your left)", "done": self.has_approached_rack},
            ]
        elif self.step == 1:
            return [
                {"text": "Press [N] to open the 42U Rack Device Manager", "done": self.has_opened_rack_manager or self.has_mounted_switch},
                {"text": "Select 'Switch' type and target RACK-01 at Slot 24U", "done": self.has_mounted_switch},
                {"text": "Click '+ INSTALL TO RACK' to mount the equipment", "done": self.has_mounted_switch},
            ]
        elif self.step == 2:
            return [
                {"text": "Aim crosshair at Web-Server-01 port eth0, press [F] to pick up cable", "done": self.cable_picked_up or self.has_cabled_server_to_sw},
                {"text": "Aim at Core-Switch-01 port g0/1, press [F] to plug in and complete link", "done": self.has_cabled_server_to_sw},
            ]
        elif self.step == 3:
            return [
                {"text": "Aim crosshair at Core-Switch-01, press [E] to open Cisco IOS Console", "done": self.has_opened_terminal},
                {"text": "Type 'enable' [Enter] to enter Privileged EXEC mode (Switch#)", "done": self.has_used_enable},
                {"text": "Type 'configure terminal' [Enter] to enter Global Config mode (Switch(config)#)", "done": self.has_entered_config},
            ]
        elif self.step == 4:
            return [
                {"text": "Press [M] to open 2D Logical Topology (Packet Tracer Mode)", "done": self.has_opened_topology},
                {"text": "Pan canvas (Left Mouse Drag) or Zoom (Mouse Wheel)", "done": self.has_panned_or_zoomed},
                {"text": "Click on any device to view live ports in the Inspector panel", "done": self.has_inspected_topology_device},
                {"text": "Press [M] or [ESC] to return to the 3D Datacenter room", "done": self.has_returned_to_3d},
            ]
        if self.is_completed:
            return [
                {"text": "Chapter 1 completed 100%! All 5 fundamentals mastered.", "done": True},
                {"text": "Press [P] or [ESC] to return to Chapter Select menu", "done": True},
            ]
        return []

    def get_hint(self):
        if self.is_completed:
            return "Excellent work, Engineer! Press [P] or [ESC] to return to Chapter Select."
        hints = {
            0: "Use [W][A][S][D] to walk. Hold [Shift] to sprint. Walk up to RACK-01 on your left.",
            1: "Press [N] to open Rack Device Manager. Make sure 'Switch' and 'Rack 1' are selected, set Slot to 24U, then click '+ INSTALL TO RACK'.",
            2: "Stand in front of RACK-01. Aim at Web-Server eth0 (bottom slot 12U) and press [F]. Then aim at Switch g0/1 (slot 24U) and press [F]. Press [X] if you need to drop cable.",
            3: "Press [E] while aiming at the Switch. In the console, type 'enable' then press Enter. Next, type 'configure terminal' (or 'conf t') then press Enter.",
            4: "Press [M] to toggle 2D Topology. Drag canvas to pan, scroll wheel to zoom. Click Web-Server-01 or Switch to inspect properties. Press [M] or [ESC] to finish!",
        }
        return hints.get(self.step, "")

    def get_concept(self):
        """Returns (title, lines) for the concept panel on the HUD."""
        return CONCEPT_TEXTS.get(self.step, None)
