"""
engine/menu_scene.py - High-Fidelity 3D Datacenter Scene & Cinematic Camera for the Main Menu
Pre-populates 2 adjacent 42U server racks with enterprise switches, routers,
firewalls, servers, and multi-colored 3D patch cables with catenary sag physics
and animated blinking status LEDs.
"""

import time
import math
from OpenGL.GLU import gluLookAt
from network.switch import Switch
from network.router import Router
from network.host import Host
from network.firewall import Firewall
from network.cable import Cable, CableType

class Menu3DCamera:
    """Cinematic camera perfectly framing the 2 racks on the right side of the screen."""
    def __init__(self):
        self.x = 0.02
        self.y = 1.16
        self.z = 0.78
        self.base_eye_x = self.x
        self.base_eye_y = self.y
        self.base_eye_z = self.z
        self.target_x = 0.82
        self.target_y = 1.05
        self.target_z = -1.40

    def apply_view(self):
        gluLookAt(
            self.x, self.y, self.z,
            self.target_x, self.target_y, self.target_z,
            0.0, 1.0, 0.0
        )

class Menu3DScene:
    """Populates 2 42U server racks packed full of 3D equipment and cabling."""
    def __init__(self):
        self.devices = []
        self.cables = []
        self._build_scene()

    @staticmethod
    def calculate_rack_pos(rack_id, u_slot):
        x = (rack_id - 2) * 1.4
        z = -1.5
        y = round(0.14 + (u_slot / 42.0) * 1.85, 2)
        return x, y, z

    def _build_scene(self):
        self.devices.clear()
        self.cables.clear()

        # ------------------ RACK 2 (X = 0.0, Z = -1.5) - FULLY PACKED ------------------
        # 40U: ISP Demarc WAN Gateway
        isp = Host("isp_menu", hostname="ISP-Gateway-Demarc", device_type="isp_gateway", rack_id=2, u_slot=40)
        isp.pos_x, isp.pos_y, isp.pos_z = self.calculate_rack_pos(2, 40)
        self.devices.append(isp)

        # 36U: Next-Gen Enterprise Firewall
        fw1 = Firewall("fw1_menu", hostname="ASA-Edge-01", rack_id=2, u_slot=36, num_ports=6)
        fw1.pos_x, fw1.pos_y, fw1.pos_z = self.calculate_rack_pos(2, 36)
        self.devices.append(fw1)

        # 32U: Core Router 1
        rtr1 = Router("rtr1_menu", hostname="Core-Router-01", rack_id=2, u_slot=32, num_ports=4)
        rtr1.pos_x, rtr1.pos_y, rtr1.pos_z = self.calculate_rack_pos(2, 32)
        self.devices.append(rtr1)

        # 28U: Core Router 2
        rtr2 = Router("rtr2_menu", hostname="Spine-Router-02", rack_id=2, u_slot=28, num_ports=4)
        rtr2.pos_x, rtr2.pos_y, rtr2.pos_z = self.calculate_rack_pos(2, 28)
        self.devices.append(rtr2)

        # 24U: Core Switch 1 (48-Port Cisco Catalyst)
        sw1 = Switch("sw1_menu", hostname="Cat9300-Core-01", rack_id=2, u_slot=24, num_ports=8)
        sw1.pos_x, sw1.pos_y, sw1.pos_z = self.calculate_rack_pos(2, 24)
        self.devices.append(sw1)

        # 20U: Core Switch 2 (Stack Member)
        sw2 = Switch("sw2_menu", hostname="Cat9300-Core-02", rack_id=2, u_slot=20, num_ports=8)
        sw2.pos_x, sw2.pos_y, sw2.pos_z = self.calculate_rack_pos(2, 20)
        self.devices.append(sw2)

        # 16U: Distribution Switch
        sw3 = Switch("sw3_menu", hostname="Cat3850-Dist-01", rack_id=2, u_slot=16, num_ports=8)
        sw3.pos_x, sw3.pos_y, sw3.pos_z = self.calculate_rack_pos(2, 16)
        self.devices.append(sw3)

        # 12U: Database Cluster Server
        srv1 = Host("srv1_menu", hostname="PowerEdge-DB-01", device_type="server", rack_id=2, u_slot=12)
        srv1.pos_x, srv1.pos_y, srv1.pos_z = self.calculate_rack_pos(2, 12)
        self.devices.append(srv1)

        # 8U: SAN Storage Controller
        srv2 = Host("srv2_menu", hostname="PowerEdge-SAN-01", device_type="server", rack_id=2, u_slot=8)
        srv2.pos_x, srv2.pos_y, srv2.pos_z = self.calculate_rack_pos(2, 8)
        self.devices.append(srv2)

        # 4U: Backup Compute Node
        srv0 = Host("srv0_menu", hostname="PowerEdge-Vault-01", device_type="server", rack_id=2, u_slot=4)
        srv0.pos_x, srv0.pos_y, srv0.pos_z = self.calculate_rack_pos(2, 4)
        self.devices.append(srv0)

        # ------------------ RACK 3 (X = 1.4, Z = -1.5) - FULLY PACKED ------------------
        # 40U: Leaf Top-of-Rack Switch
        sw4 = Switch("sw4_menu", hostname="Cat9300-Leaf-01", rack_id=3, u_slot=40, num_ports=8)
        sw4.pos_x, sw4.pos_y, sw4.pos_z = self.calculate_rack_pos(3, 40)
        self.devices.append(sw4)

        # 36U: Leaf Switch 2
        sw5 = Switch("sw5_menu", hostname="Cat9300-Leaf-02", rack_id=3, u_slot=36, num_ports=8)
        sw5.pos_x, sw5.pos_y, sw5.pos_z = self.calculate_rack_pos(3, 36)
        self.devices.append(sw5)

        # 32U: Edge Router 3
        rtr3 = Router("rtr3_menu", hostname="Edge-Router-03", rack_id=3, u_slot=32, num_ports=4)
        rtr3.pos_x, rtr3.pos_y, rtr3.pos_z = self.calculate_rack_pos(3, 32)
        self.devices.append(rtr3)

        # 28U: Internal Firewall
        fw2 = Firewall("fw2_menu", hostname="ASA-Internal-02", rack_id=3, u_slot=28, num_ports=6)
        fw2.pos_x, fw2.pos_y, fw2.pos_z = self.calculate_rack_pos(3, 28)
        self.devices.append(fw2)

        # 24U: Access Switch 1
        sw6 = Switch("sw6_menu", hostname="Cat2960-Access-01", rack_id=3, u_slot=24, num_ports=8)
        sw6.pos_x, sw6.pos_y, sw6.pos_z = self.calculate_rack_pos(3, 24)
        self.devices.append(sw6)

        # 20U: Access Switch 2
        sw7 = Switch("sw7_menu", hostname="Cat2960-Access-02", rack_id=3, u_slot=20, num_ports=8)
        sw7.pos_x, sw7.pos_y, sw7.pos_z = self.calculate_rack_pos(3, 20)
        self.devices.append(sw7)

        # 16U: Access Switch 3 (PoE VoIP)
        sw8 = Switch("sw8_menu", hostname="Cat2960-VoIP-03", rack_id=3, u_slot=16, num_ports=8)
        sw8.pos_x, sw8.pos_y, sw8.pos_z = self.calculate_rack_pos(3, 16)
        self.devices.append(sw8)

        # 12U: Virtualization Host 1
        srv3 = Host("srv3_menu", hostname="ProLiant-Compute-01", device_type="server", rack_id=3, u_slot=12)
        srv3.pos_x, srv3.pos_y, srv3.pos_z = self.calculate_rack_pos(3, 12)
        self.devices.append(srv3)

        # 8U: Virtualization Host 2
        srv4 = Host("srv4_menu", hostname="ProLiant-Compute-02", device_type="server", rack_id=3, u_slot=8)
        srv4.pos_x, srv4.pos_y, srv4.pos_z = self.calculate_rack_pos(3, 8)
        self.devices.append(srv4)

        # 4U: Analytics Host 3
        srv5 = Host("srv5_menu", hostname="ProLiant-Analytics-03", device_type="server", rack_id=3, u_slot=4)
        srv5.pos_x, srv5.pos_y, srv5.pos_z = self.calculate_rack_pos(3, 4)
        self.devices.append(srv5)

        # ------------------ RICH 3D CABLES (โยงทั้งในตู้และข้ามตู้) ------------------
        # A. Intra-Rack 2 (In-Rack Cabling)
        self.cables.append(Cable(sw1.ports["g0/1"], sw2.ports["g0/1"], CableType.CAT6, color=(0.1, 0.45, 0.95)))
        self.cables.append(Cable(sw1.ports["g0/2"], rtr1.ports["g0/1"], CableType.CAT6, color=(0.1, 0.85, 0.45)))
        self.cables.append(Cable(sw2.ports["g0/2"], rtr2.ports["g0/1"], CableType.CAT6, color=(0.95, 0.80, 0.15)))
        self.cables.append(Cable(fw1.ports["g0/1"], rtr1.ports["g0/2"], CableType.CAT6, color=(0.95, 0.45, 0.15)))
        self.cables.append(Cable(sw3.ports["g0/1"], srv1.ports["eth0"], CableType.CAT6, color=(0.15, 0.55, 0.95)))
        self.cables.append(Cable(sw3.ports["g0/2"], srv2.ports["eth0"], CableType.CAT6, color=(0.65, 0.25, 0.95)))
        self.cables.append(Cable(sw3.ports["g0/4"], srv0.ports["eth0"], CableType.CAT6, color=(0.1, 0.88, 0.45)))
        self.cables.append(Cable(isp.ports["eth0"], fw1.ports["g0/2"], CableType.FIBER, color=(0.1, 0.85, 0.85)))

        # B. Intra-Rack 3 (In-Rack Cabling)
        self.cables.append(Cable(sw4.ports["g0/1"], sw5.ports["g0/1"], CableType.CAT6, color=(0.1, 0.45, 0.95)))
        self.cables.append(Cable(sw4.ports["g0/2"], rtr3.ports["g0/1"], CableType.CAT6, color=(0.95, 0.45, 0.15)))
        self.cables.append(Cable(sw6.ports["g0/1"], sw7.ports["g0/1"], CableType.CAT6, color=(0.1, 0.85, 0.45)))
        self.cables.append(Cable(sw6.ports["g0/2"], srv3.ports["eth0"], CableType.CAT6, color=(0.65, 0.25, 0.95)))
        self.cables.append(Cable(sw7.ports["g0/1"], srv4.ports["eth0"], CableType.CAT6, color=(0.15, 0.55, 0.95)))
        self.cables.append(Cable(sw8.ports["g0/1"], srv5.ports["eth0"], CableType.CAT6, color=(0.95, 0.80, 0.15)))
        self.cables.append(Cable(sw7.ports["g0/2"], sw8.ports["g0/2"], CableType.CAT6, color=(0.95, 0.45, 0.15)))

        # C. Cross-Rack Cables (Spanning across between Rack 2 and Rack 3!)
        # Trunk 1: Core Switch 1 -> Leaf Switch 1 (Cisco Electric Blue)
        self.cables.append(Cable(sw1.ports["g0/3"], sw4.ports["g0/3"], CableType.CAT6, color=(0.05, 0.55, 0.98)))
        # Trunk 2: Core Switch 2 -> Leaf Switch 2 (Mint Green)
        self.cables.append(Cable(sw2.ports["g0/3"], sw5.ports["g0/3"], CableType.CAT6, color=(0.1, 0.88, 0.45)))
        # Trunk 3: Core Router 1 -> Edge Router 3 (Vibrant Orange)
        self.cables.append(Cable(rtr1.ports["g0/3"], rtr3.ports["g0/3"], CableType.CAT6, color=(0.98, 0.45, 0.12)))
        # Trunk 4: Firewall HA Sync (Crimson Red)
        self.cables.append(Cable(fw1.ports["g0/3"], fw2.ports["g0/3"], CableType.CAT6, color=(0.95, 0.15, 0.20)))
        # Trunk 5: Distribution Switch -> Access Switch (Fiber Optic Gold/Yellow)
        self.cables.append(Cable(sw3.ports["g0/3"], sw6.ports["g0/3"], CableType.FIBER, color=(0.98, 0.82, 0.10)))
        # Trunk 6: SAN Fabric Storage Trunk (Purple)
        self.cables.append(Cable(sw2.ports["g0/4"], sw7.ports["g0/3"], CableType.CAT6, color=(0.65, 0.25, 0.95)))
