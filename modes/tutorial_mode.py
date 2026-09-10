"""
modes/tutorial_mode.py - 7-Step Guided Network Engineer Training Course

LESSONS:
  0: Welcome & Controls Orientation
  1: Datacenter Tour & Device Identification
  2: Physical Cabling (Cat6 Server → Switch)
  3: Cisco IOS Terminal & Mode Navigation
  4: Interface Bringup (no shutdown)
  5: IP Addressing & Verification with Ping
  6: VLAN Segmentation (Bonus Advanced Lesson)

Each step includes:
  - Objective text
  - Step-by-step checklist with independent completion tracking
  - Contextual hints
  - Concept explanation panel
  - Completion sound & automatic advance
"""

import math
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
        "CONTROLS REFERENCE",
        [
            "WASD          Move forward/backward/strafe",
            "Mouse         Look around (First-Person Camera)",
            "Shift         Sprint",
            "E             Open Cisco IOS / Linux Terminal",
            "F             Pick up / plug in network cable",
            "X             Cancel cable in hand",
            "M             Open 2D Topology Map",
            "P / Esc       Pause Menu",
            "F11           Toggle Fullscreen",
        ]
    ),
    1: (
        "DATACENTER BASICS",
        [
            "Rack          19-inch metal cabinet (1U=44mm height)",
            "Switch        L2 device; forwards frames by MAC address",
            "Router        L3 device; routes packets by IP address",
            "Server        End-host; runs applications",
            "LED Green     Port link UP (cable connected, no shut)",
            "LED Amber     Port administratively down (shutdown)",
            "LED OFF       No cable plugged in",
        ]
    ),
    2: (
        "PHYSICAL LAYER (L1)",
        [
            "Cat6 UTP      Copper; up to 1 Gbps / 100m",
            "Fiber LC-LC   Glass; up to 10+ Gbps / km",
            "Console       Roll-over; CLI management only",
            "RJ45 Jack     8P8C connector for Cat5e/Cat6",
            "TIP: Press [F] on source port, then [F] on dest port",
        ]
    ),
    3: (
        "CISCO IOS MODES",
        [
            "User EXEC     Router>   (view-only, basic commands)",
            "Privileged    Router#   type 'enable' to enter",
            "Global Config Router(config)# type 'conf t'",
            "Interface     Router(config-if)# type 'int g0/1'",
            "Exit mode     type 'exit' or 'end' (back to priv#)",
            "Help          type '?' or 'help' to list commands",
        ]
    ),
    4: (
        "INTERFACE STATES",
        [
            "Admin Down    'shutdown' applied — no traffic passes",
            "Line Down     Cable missing or peer is down",
            "Up/Up         Both physical & protocol layers active",
            "no shutdown   Removes admin-down; enables the port",
            "CMD SEQUENCE:",
            "  enable  →  conf t  →  int g0/1  →  no shut  →  end",
        ]
    ),
    5: (
        "IP ADDRESSING (L3)",
        [
            "IPv4 Format   A.B.C.D  (e.g. 192.168.1.10)",
            "Subnet Mask   255.255.255.0 = /24 (256 hosts)",
            "Gateway       Router IP that forwards off-subnet pkts",
            "ICMP Ping     Tests reachability; sends Echo Request",
            "Cisco CMD:    ping 192.168.1.1",
            "Linux CMD:    ping 192.168.1.1  (on Host terminal)",
        ]
    ),
    6: (
        "VLANs (VIRTUAL LANS)",
        [
            "VLAN          Logical L2 network segment (isolation)",
            "Access Port   Belongs to ONE vlan (end-device facing)",
            "Trunk Port    Carries MULTIPLE vlans (802.1Q tagging)",
            "VLAN 10       e.g. Engineering / Servers",
            "VLAN 20       e.g. Management / Admin",
            "CMD SEQUENCE:",
            "  vlan 10  →  name SERVERS  →  exit",
            "  int g0/1  →  sw mode access  →  sw access vlan 10",
        ]
    ),
}


class TutorialMode(BaseMode):
    """7-step guided tutorial teaching real network engineering skills."""

    def __init__(self):
        super().__init__("TUTORIAL: NETWORK ENGINEER 101")
        self.step = 0
        self.max_steps = 6  # 0..6
        self.sound = SoundManager.get_instance()

        # --- Step completion flags (each tracked independently) ---
        # Step 0
        self.has_moved = False
        self.has_looked_around = False

        # Step 1
        self.has_approached_rack = False
        self.has_inspected_switch = False
        self.has_inspected_server = False

        # Step 2
        self.cable_picked_up = False
        self.has_cabled_server_to_sw = False

        # Step 3
        self.has_opened_terminal = False
        self.has_used_enable = False
        self.has_used_show = False

        # Step 4
        self.has_entered_config = False
        self.has_selected_interface = False
        self.has_enabled_interface = False

        # Step 5
        self.router_cabled = False
        self.router_ip_configured = False
        self.has_pinged_gateway = False

        # Step 6 (Bonus VLAN)
        self.vlan_created = False
        self.port_vlan_assigned = False

        # Internal: track mouse delta movement for step 0
        self._total_mouse_dx = 0.0
        self._step0_camera_yaw_start = None

        self.setup()

    # ------------------------------------------------------------------
    # Setup / Reset
    # ------------------------------------------------------------------
    def setup(self):
        """Build/reset the datacenter scene for this tutorial."""
        self.devices = []
        self.cables = []
        self.step = 0

        # Reset all completion flags
        self.has_moved = False
        self.has_looked_around = False
        self.has_approached_rack = False
        self.has_inspected_switch = False
        self.has_inspected_server = False
        self.cable_picked_up = False
        self.has_cabled_server_to_sw = False
        self.has_opened_terminal = False
        self.has_used_enable = False
        self.has_used_show = False
        self.has_entered_config = False
        self.has_selected_interface = False
        self.has_enabled_interface = False
        self.router_cabled = False
        self.router_ip_configured = False
        self.has_pinged_gateway = False
        self.vlan_created = False
        self.port_vlan_assigned = False
        self._total_mouse_dx = 0.0
        self._step0_camera_yaw_start = None

        # ----- RACK 1: Server + Switch -----
        # Web-Server-01 at 12U
        self.server1 = Host("srv1", hostname="Web-Server-01",
                            device_type="server", rack_id=1, u_slot=12)
        self.server1.pos_x, self.server1.pos_y, self.server1.pos_z = -1.4, 0.7, -1.5
        self.server1.configure_ip("192.168.1.10", "255.255.255.0",
                                  gateway="192.168.1.1")
        self.devices.append(self.server1)

        # Core-Switch-01 at 24U
        self.switch1 = Switch("sw1", hostname="Core-Switch-01",
                              rack_id=1, u_slot=24, num_ports=8)
        self.switch1.pos_x, self.switch1.pos_y, self.switch1.pos_z = -1.4, 1.25, -1.5
        # Port g0/1 starts administratively down (lesson 4 objective)
        self.switch1.ports["g0/1"].is_shutdown = True
        self.devices.append(self.switch1)

        # ----- RACK 2: Edge Router -----
        self.router1 = Router("rtr1", hostname="Edge-Router-01",
                              rack_id=2, u_slot=28, num_ports=4)
        self.router1.pos_x, self.router1.pos_y, self.router1.pos_z = 0.0, 1.45, -1.5
        self.devices.append(self.router1)

        # ----- Workbench: Dual Engineer Laptops -----
        # 1. Windows 11 Pro Laptop on Left Side of Desk
        self.laptop_win = Host("lap1", hostname="Win-Laptop-01",
                               device_type="laptop", rack_id=0, u_slot=0, os_type="windows")
        self.laptop_win.pos_x, self.laptop_win.pos_y, self.laptop_win.pos_z = -3.55, 0.77, 0.50
        self.laptop_win.configure_ip("192.168.1.99", "255.255.255.0",
                                     gateway="192.168.1.1", dns="8.8.8.8")
        self.devices.append(self.laptop_win)
        self.laptop = self.laptop_win  # Backward compatibility

        # 2. Ubuntu 22.04 LTS Laptop on Right Side of Desk
        self.laptop_ubu = Host("lap2", hostname="Ubuntu-Laptop-02",
                               device_type="laptop", rack_id=0, u_slot=0, os_type="ubuntu")
        self.laptop_ubu.pos_x, self.laptop_ubu.pos_y, self.laptop_ubu.pos_z = -2.85, 0.77, 0.50
        self.laptop_ubu.configure_ip("192.168.1.100", "255.255.255.0",
                                     gateway="192.168.1.1", dns="8.8.8.8")
        self.devices.append(self.laptop_ubu)

        # Pre-connect Console Cable (Windows Laptop con0 → Switch con0) for CLI access
        con_cable = Cable(self.laptop_win.ports["con0"],
                          self.switch1.ports["con0"],
                          CableType.CONSOLE)
        self.cables.append(con_cable)

    # ------------------------------------------------------------------
    # Update Logic
    # ------------------------------------------------------------------
    def update(self, dt, player_camera):
        # Step 0: Welcome — detect movement & mouse look
        if self.step == 0:
            self._check_step0(player_camera)

        # Step 1: Approach racks and inspect devices
        elif self.step == 1:
            self._check_step1(player_camera)

        # Step 2: Physical cabling
        elif self.step == 2:
            self._check_step2(player_camera)

        # Step 3: Open terminal and navigate IOS modes
        elif self.step == 3:
            if self.has_opened_terminal and self.has_used_enable and self.has_used_show:
                self._advance_step(4)

        # Step 4: Interface bringup (no shutdown)
        elif self.step == 4:
            p_sw = self.switch1.ports.get("g0/1")
            if p_sw and not p_sw.is_shutdown:
                self.has_enabled_interface = True
            if (self.has_entered_config and
                    self.has_selected_interface and
                    self.has_enabled_interface):
                self._advance_step(5)

        # Step 5: Router IP + Ping
        elif self.step == 5:
            self._check_step5(player_camera)

        # Step 6: VLAN bonus lesson
        elif self.step == 6:
            self._check_step6()

    def _check_step0(self, cam):
        """Track movement and mouse look for the orientation step."""
        if self._step0_camera_yaw_start is None:
            self._step0_camera_yaw_start = cam.yaw

        # Detect if camera yaw changed significantly (looked around)
        yaw_delta = abs(cam.yaw - self._step0_camera_yaw_start)
        if yaw_delta > 30.0:
            self.has_looked_around = True

        # Detect positional movement from spawn
        dist_from_spawn = math.sqrt((cam.x - 0.0)**2 + (cam.z - 2.8)**2)
        if dist_from_spawn > 0.8:
            self.has_moved = True

        if self.has_moved and self.has_looked_around:
            self._advance_step(1)

    def _check_step1(self, cam):
        """Check proximity and crosshair inspection of rack devices."""
        dist_to_rack1 = math.sqrt((cam.x - (-1.4))**2 + (cam.z - (-1.5))**2)
        if dist_to_rack1 < 3.5:
            self.has_approached_rack = True

        dev, port, _ = cam.raycast(self.devices)
        if dev == self.switch1:
            self.has_inspected_switch = True
        if dev == self.server1:
            self.has_inspected_server = True

        if (self.has_approached_rack and
                self.has_inspected_switch and
                self.has_inspected_server):
            self._advance_step(2)

    def _check_step2(self, player_camera):
        """Check if server eth0 is connected to switch g0/1."""
        p_server = self.server1.eth0
        p_sw = self.switch1.ports.get("g0/1")
        if p_server and p_sw and p_server.cable:
            peer = p_server.cable.get_peer_port(p_server)
            if peer == p_sw:
                self.has_cabled_server_to_sw = True
                self._advance_step(3)

    def _check_step5(self, cam):
        """Check router cabling + IP config + ping."""
        rg0 = self.router1.ports.get("g0/0")
        if rg0 and rg0.cable:
            self.router_cabled = True
        if rg0 and rg0.ip_address == "192.168.1.1" and not rg0.is_shutdown:
            self.router_ip_configured = True
        if (self.router_cabled and
                self.router_ip_configured and
                self.has_pinged_gateway):
            self._advance_step(6)

    def _check_step6(self):
        """Check VLAN creation and port assignment on switch."""
        if 10 in self.switch1.vlans:
            self.vlan_created = True
        p = self.switch1.ports.get("g0/1")
        if p and p.access_vlan == 10:
            self.port_vlan_assigned = True
        if self.vlan_created and self.port_vlan_assigned:
            self.is_completed = True
            self.sound.play_objective()

    def _advance_step(self, next_step):
        """Move to the next tutorial step and play objective sound."""
        self.step = next_step
        self.sound.play_objective()

    # ------------------------------------------------------------------
    # HUD Content Providers
    # ------------------------------------------------------------------
    def get_title(self):
        if self.step == 0:
            return "TUTORIAL: WELCOME TO NETLAB"
        if self.is_completed:
            return "TUTORIAL: ALL LESSONS COMPLETE!"
        return f"TUTORIAL: LESSON {self.step} OF {self.max_steps}"

    def get_objective(self):
        objectives = {
            0: "Welcome to NetEngineer 3D! Move around and look at the datacenter.",
            1: "Datacenter Tour: Walk close to RACK-01 and inspect the Switch and Server.",
            2: "Physical Cabling: Connect a Cat6 cable from Web-Server eth0 to Switch g0/1.",
            3: "Cisco Terminal: Open the Switch console and practice IOS mode navigation.",
            4: "Interface Bringup: Use CLI to bring port g0/1 UP (remove shutdown).",
            5: "IP & Connectivity: Configure Router g0/0 IP and ping it from the Server.",
            6: "[BONUS] VLAN: Create VLAN 10 'SERVERS' and assign Switch port g0/1 to it.",
        }
        if self.is_completed:
            return "Congratulations! You've completed all Network Engineer 101 lessons."
        return objectives.get(self.step, "")

    def get_checklist(self):
        if self.step == 0:
            return [
                {"text": "Move around the datacenter room (WASD keys)", "done": self.has_moved},
                {"text": "Look around with the mouse (move mouse left/right)", "done": self.has_looked_around},
            ]
        elif self.step == 1:
            return [
                {"text": "Walk to RACK-01 (the rack on your left side)", "done": self.has_approached_rack},
                {"text": "Aim crosshair at Core-Switch-01 (blue 2U chassis)", "done": self.has_inspected_switch},
                {"text": "Aim crosshair at Web-Server-01 (1U black chassis)", "done": self.has_inspected_server},
            ]
        elif self.step == 2:
            return [
                {"text": "Aim at Web-Server-01 port eth0, press [F] to pick up cable", "done": self.has_cabled_server_to_sw},
                {"text": "Aim at Core-Switch-01 port g0/1, press [F] to connect", "done": self.has_cabled_server_to_sw},
            ]
        elif self.step == 3:
            return [
                {"text": "Aim at Core-Switch-01, press [E] to open IOS Terminal", "done": self.has_opened_terminal},
                {"text": "Type 'enable' to enter Privileged EXEC mode (Switch#)", "done": self.has_used_enable},
                {"text": "Type 'show ip interface brief' to view port status", "done": self.has_used_show},
                {"text": "Type '?' or 'help' to see available commands", "done": self.has_opened_terminal},
            ]
        elif self.step == 4:
            p_sw = self.switch1.ports.get("g0/1")
            is_up = p_sw and not p_sw.is_shutdown
            return [
                {"text": "Type 'configure terminal' (or 'conf t') for Config mode", "done": self.has_entered_config},
                {"text": "Type 'interface g0/1' to select the port", "done": self.has_selected_interface},
                {"text": "Type 'no shutdown' to bring the port UP", "done": is_up},
                {"text": "Type 'end' to return to Privileged mode", "done": is_up},
            ]
        elif self.step == 5:
            rg0 = self.router1.ports.get("g0/0")
            cabled = rg0 and rg0.cable is not None
            ip_done = rg0 and rg0.ip_address == "192.168.1.1" and not rg0.is_shutdown
            return [
                {"text": "Cable: Connect Switch port g0/2 to Router port g0/0 [F]", "done": cabled},
                {"text": "On Router terminal: 'conf t' → 'int g0/0'", "done": ip_done},
                {"text": "On Router: 'ip address 192.168.1.1 255.255.255.0'", "done": ip_done},
                {"text": "On Router: 'no shutdown' then 'end'", "done": ip_done},
                {"text": "On Web-Server-01 terminal: 'ping 192.168.1.1'", "done": self.has_pinged_gateway},
            ]
        elif self.step == 6:
            return [
                {"text": "[BONUS] On Switch: 'conf t' → 'vlan 10' → 'name SERVERS'", "done": self.vlan_created},
                {"text": "[BONUS] 'exit' → 'int g0/1' → 'sw mode access'", "done": self.port_vlan_assigned},
                {"text": "[BONUS] 'sw access vlan 10' → 'end'", "done": self.port_vlan_assigned},
            ]
        if self.is_completed:
            return [
                {"text": "All lessons complete! Try Challenge Mode for real scenarios.", "done": True},
                {"text": "Or explore Sandbox Mode to build your own network!", "done": True},
            ]
        return []

    def get_hint(self):
        hints = {
            0: "Use W to move forward, S to move back. Move your mouse slowly to look around.",
            1: "Walk toward the tall metal racks (cabinets) in the room. Aim your crosshair at each device.",
            2: (
                "Stand close to RACK-01. Aim at Web-Server eth0 port, press [F]. "
                "Then aim at Switch port g0/1 and press [F] again to complete the connection. "
                "Press [X] to cancel a cable in hand."
            ),
            3: (
                "Press [E] while aiming at the Switch. "
                "Then type: enable → show ip int br → help  (press Enter after each command)."
            ),
            4: "Full sequence: enable → conf t → int g0/1 → no shutdown → end",
            5: (
                "First cable Switch g0/2 to Router g0/0 using [F]. "
                "Then open Router terminal [E]: conf t → int g0/0 → ip address 192.168.1.1 255.255.255.0 → no shut → end. "
                "Finally open Server terminal [E] and type: ping 192.168.1.1"
            ),
            6: (
                "Open Switch terminal [E]: conf t → vlan 10 → name SERVERS → exit → "
                "int g0/1 → switchport mode access → switchport access vlan 10 → end"
            ),
        }
        if self.is_completed:
            return "Well done! You are now a certified NetLab Engineer. Press [P] to return to main menu."
        return hints.get(self.step, "")

    def get_concept(self):
        """Returns (title, lines) for the concept panel on the HUD."""
        return CONCEPT_TEXTS.get(self.step, None)

    # ------------------------------------------------------------------
    # Callback: CLI Command Executed
    # ------------------------------------------------------------------
    def on_command_executed(self, device, command, output):
        """
        Called by GameManager after each CLI command is executed.
        Updates per-command completion flags for checklist tracking.
        """
        cmd = command.strip().lower()

        if device == self.switch1:
            # Step 3 tracking
            if cmd in ("enable", "en"):
                self.has_used_enable = True
            if cmd.startswith("show") or cmd.startswith("sh "):
                self.has_used_show = True

            # Step 4 tracking
            if cmd in ("configure terminal", "conf t", "configure t", "conf terminal"):
                self.has_entered_config = True
            if cmd.startswith("interface") or cmd.startswith("int "):
                self.has_selected_interface = True
            if "no shut" in cmd:
                self.has_enabled_interface = True

            # Step 6: VLAN tracking
            if cmd.startswith("vlan 10") or "vlan 10" in cmd:
                self.vlan_created = True
            if "vlan 10" in output or ("switchport access vlan 10" in cmd):
                self.port_vlan_assigned = True

        if device == self.router1:
            # Step 5: IP configuration tracking
            if cmd in ("configure terminal", "conf t"):
                pass  # not individually tracked
            if "ip address 192.168.1.1" in cmd:
                self.router_ip_configured = True

        if device == self.server1 or device == self.laptop:
            # Step 5: Ping success
            if "ping 192.168.1.1" in cmd:
                if any(k in output for k in ("0% packet loss", "5/5", "received, 0%", "bytes from", "!", "80 percent", "4/5")):
                    self.has_pinged_gateway = True
                    self.sound.play_objective()

    # ------------------------------------------------------------------
    # Notify that player picked up a cable
    # ------------------------------------------------------------------
    def on_cable_picked_up(self):
        """Called by GameManager when player picks up a cable in step 2."""
        self.cable_picked_up = True
