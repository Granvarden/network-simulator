"""
modes/challenge_mode.py - Incident Tickets & Troubleshooting Scenarios
Players act as on-call Network Engineers resolving NOC tickets under timer and auto-grading.
"""

import time
from .base_mode import BaseMode
from network.switch import Switch
from network.router import Router
from network.host import Host
from network.cable import Cable, CableType
from engine.audio import SoundManager

class ChallengeScenario:
    def __init__(self, ticket_id, title, priority, description, hint):
        self.ticket_id = ticket_id
        self.title = title
        self.priority = priority  # P1, P2, P3
        self.description = description
        self.hint = hint

SCENARIOS = [
    ChallengeScenario(
        ticket_id="INC-101",
        title="Web Server Down (Physical & Port Down)",
        priority="P1 CRITICAL",
        description="Monitoring alert: Web-Server-01 has dropped off the network. Restore link and verify ping to 192.168.1.1.",
        hint="Check physical cabling between Web-Server eth0 and Switch g0/1. Check if port g0/1 is shutdown."
    ),
    ChallengeScenario(
        ticket_id="INC-102",
        title="Finance VLAN Isolation Crisis",
        priority="P2 HIGH",
        description="Finance workstation cannot connect to Database Server. Rectify switchport VLAN configuration.",
        hint="Inspect Switch g0/3 using 'show vlan brief'. Set switchport access vlan 20."
    ),
    ChallengeScenario(
        ticket_id="INC-103",
        title="Branch Office Static Route Failure",
        priority="P2 HIGH",
        description="Branch Router cannot route packets to 10.0.0.0/24 subnet. Add missing static route.",
        hint="On Router: 'ip route 10.0.0.0 255.255.255.0 192.168.1.254', then test ping."
    )
]

class ChallengeMode(BaseMode):
    def __init__(self):
        super().__init__("CHALLENGE: INCIDENT TROUBLESHOOTING")
        self.scenario_index = 0
        self.sound = SoundManager.get_instance()
        self.start_time = time.time()
        self.elapsed_time = 0.0
        self.stars_earned = 3
        self.is_ticket_resolved = False

        self.setup()

    def setup(self):
        self.devices = []
        self.cables = []
        self.start_time = time.time()
        self.is_ticket_resolved = False
        self.is_completed = False

        scenario = SCENARIOS[self.scenario_index]

        if scenario.ticket_id == "INC-101":
            self._setup_scenario_1()
        elif scenario.ticket_id == "INC-102":
            self._setup_scenario_2()
        elif scenario.ticket_id == "INC-103":
            self._setup_scenario_3()

        self._setup_laptops()

    def _setup_laptops(self):
        # Workbench Dual Engineer Laptops
        self.laptop_win = Host("lap1", hostname="Win-Laptop-01",
                               device_type="laptop", rack_id=0, u_slot=0, os_type="windows")
        self.laptop_win.pos_x, self.laptop_win.pos_y, self.laptop_win.pos_z = -3.55, 0.77, 0.50
        self.laptop_win.configure_ip("192.168.1.99", "255.255.255.0", gateway="192.168.1.1", dns="8.8.8.8")

        self.laptop_ubu = Host("lap2", hostname="Ubuntu-Laptop-02",
                               device_type="laptop", rack_id=0, u_slot=0, os_type="ubuntu")
        self.laptop_ubu.pos_x, self.laptop_ubu.pos_y, self.laptop_ubu.pos_z = -2.85, 0.77, 0.50
        self.laptop_ubu.configure_ip("192.168.1.100", "255.255.255.0", gateway="192.168.1.1", dns="8.8.8.8")

        self.devices.extend([self.laptop_win, self.laptop_ubu])

    def _setup_scenario_1(self):
        # Scenario 1: Unplugged cable & Shutdown port
        # Server 01
        self.server = Host("srv1", hostname="Web-Server-01", device_type="server", rack_id=1, u_slot=12)
        self.server.pos_x, self.server.pos_y, self.server.pos_z = -1.4, 0.7, -1.5
        self.server.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")
        self.devices.append(self.server)

        # Core Switch
        self.switch = Switch("sw1", hostname="Core-Switch-01", rack_id=1, u_slot=24)
        self.switch.pos_x, self.switch.pos_y, self.switch.pos_z = -1.4, 1.25, -1.5
        self.switch.ports["g0/1"].is_shutdown = True  # Problem 1
        self.devices.append(self.switch)

        # Router (Gateway)
        self.router = Router("rtr1", hostname="Core-Gateway", rack_id=2, u_slot=28)
        self.router.pos_x, self.router.pos_y, self.router.pos_z = 0.0, 1.45, -1.5
        rg0 = self.router.ports["g0/0"]
        rg0.ip_address = "192.168.1.1"
        rg0.subnet_mask = "255.255.255.0"
        rg0.is_shutdown = False
        self.devices.append(self.router)

        # Cable between Switch g0/2 and Router g0/0
        c_gw = Cable(self.switch.ports["g0/2"], self.router.ports["g0/0"], CableType.CAT6)
        self.cables.append(c_gw)

    def _setup_scenario_2(self):
        # Scenario 2: VLAN Mismatch
        self.switch = Switch("sw1", hostname="Dist-Switch-01", rack_id=1, u_slot=24)
        self.switch.pos_x, self.switch.pos_y, self.switch.pos_z = -1.4, 1.25, -1.5
        self.switch.add_vlan(10, "Corporate")
        self.switch.add_vlan(20, "Finance_DB")
        # Port g0/1 is in VLAN 20
        self.switch.ports["g0/1"].access_vlan = 20
        # Port g0/3 is WRONGLY in VLAN 1
        self.switch.ports["g0/3"].access_vlan = 1
        self.devices.append(self.switch)

        # DB Server on g0/1
        self.db_server = Host("db1", hostname="DB-Server-20", device_type="server", rack_id=1, u_slot=12)
        self.db_server.pos_x, self.db_server.pos_y, self.db_server.pos_z = -1.4, 0.7, -1.5
        self.db_server.configure_ip("192.168.20.10", "255.255.255.0")
        self.devices.append(self.db_server)

        # Finance PC on g0/3
        self.pc = Host("pc1", hostname="Finance-PC", device_type="server", rack_id=2, u_slot=10)
        self.pc.pos_x, self.pc.pos_y, self.pc.pos_z = 0.0, 0.6, -1.5
        self.pc.configure_ip("192.168.20.50", "255.255.255.0")
        self.devices.append(self.pc)

        # Cables
        c1 = Cable(self.db_server.eth0, self.switch.ports["g0/1"], CableType.CAT6)
        c2 = Cable(self.pc.eth0, self.switch.ports["g0/3"], CableType.CAT6)
        self.cables.extend([c1, c2])

    def _setup_scenario_3(self):
        # Scenario 3: Missing Static Route
        self.router = Router("rtr1", hostname="Branch-Router", rack_id=1, u_slot=28)
        self.router.pos_x, self.router.pos_y, self.router.pos_z = -1.4, 1.45, -1.5
        rg0 = self.router.ports["g0/0"]
        rg0.ip_address = "192.168.1.1"
        rg0.subnet_mask = "255.255.255.0"
        rg0.is_shutdown = False

        rg1 = self.router.ports["g0/1"]
        rg1.ip_address = "192.168.100.1"
        rg1.subnet_mask = "255.255.255.0"
        rg1.is_shutdown = False
        self.devices.append(self.router)

        # Cloud Gateway Host (192.168.100.254) with route to 10.0.0.0/24
        self.gw = Host("gw1", hostname="Cloud-Gateway", device_type="server", rack_id=2, u_slot=20)
        self.gw.pos_x, self.gw.pos_y, self.gw.pos_z = 0.0, 1.1, -1.5
        self.gw.configure_ip("10.0.0.1", "255.255.255.0")
        self.devices.append(self.gw)

        c = Cable(self.router.ports["g0/1"], self.gw.eth0, CableType.CAT6)
        self.cables.append(c)

    def update(self, dt, player_camera):
        if not self.is_ticket_resolved:
            self.elapsed_time = time.time() - self.start_time

        scenario = SCENARIOS[self.scenario_index]
        if scenario.ticket_id == "INC-101":
            # Criteria: Cable connected to g0/1, g0/1 not shutdown, ping successful
            p_sw = self.switch.ports.get("g0/1")
            if p_sw and p_sw.is_link_up and not p_sw.is_shutdown and self.is_ticket_resolved:
                self.is_completed = True
        elif scenario.ticket_id == "INC-102":
            p_sw = self.switch.ports.get("g0/3")
            if p_sw and p_sw.access_vlan == 20 and self.is_ticket_resolved:
                self.is_completed = True
        elif scenario.ticket_id == "INC-103":
            if self.is_ticket_resolved:
                self.is_completed = True

    def get_title(self):
        sc = SCENARIOS[self.scenario_index]
        mins = int(self.elapsed_time) // 60
        secs = int(self.elapsed_time) % 60
        return f"{sc.ticket_id}: {sc.title} [{sc.priority}] - Timer: {mins:02d}:{secs:02d}"

    def get_objective(self):
        sc = SCENARIOS[self.scenario_index]
        if self.is_completed:
            return f"TICKET RESOLVED! Time: {int(self.elapsed_time)}s. Press [N] for Next Scenario."
        return sc.description

    def get_checklist(self):
        sc = SCENARIOS[self.scenario_index]
        if sc.ticket_id == "INC-101":
            p_sw = self.switch.ports.get("g0/1")
            cabled = p_sw and p_sw.cable is not None
            unshut = p_sw and not p_sw.is_shutdown
            return [
                {"text": "Plug Cat6 Cable between Web-Server eth0 and Switch g0/1", "done": cabled},
                {"text": "On Switch: configure 'no shutdown' on interface g0/1", "done": unshut},
                {"text": "Verify ICMP Ping from Server to Gateway (192.168.1.1)", "done": self.is_ticket_resolved}
            ]
        elif sc.ticket_id == "INC-102":
            p_sw = self.switch.ports.get("g0/3")
            vlan_fixed = p_sw and p_sw.access_vlan == 20
            return [
                {"text": "Inspect Switch VLAN assignments ('show vlan brief')", "done": True},
                {"text": "Set Switch g0/3 to 'switchport access vlan 20'", "done": vlan_fixed},
                {"text": "Verify ping from Finance-PC to DB-Server-20 (192.168.20.10)", "done": self.is_ticket_resolved}
            ]
        elif sc.ticket_id == "INC-103":
            has_route = any(r["network"] == "10.0.0.0" for r in self.router.routes)
            return [
                {"text": "Check routing table ('show ip route')", "done": True},
                {"text": "Add static route: 'ip route 10.0.0.0 255.255.255.0 g0/1'", "done": has_route},
                {"text": "Verify ping to 10.0.0.1 from Branch-Router", "done": self.is_ticket_resolved}
            ]
        return []

    def get_hint(self):
        return SCENARIOS[self.scenario_index].hint

    def on_command_executed(self, device, command, output):
        cmd = command.strip().lower()
        if "ping" in cmd and any(k in output for k in ("5/5", "4/5", "0% packet loss", "20% packet loss", "!!!!!", ".!!!!", "bytes from")):
            self.is_ticket_resolved = True
            self.sound.play_objective()

    def next_scenario(self):
        if self.scenario_index < len(SCENARIOS) - 1:
            self.scenario_index += 1
            self.setup()
            return True
        return False
