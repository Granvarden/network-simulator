"""
modes/sandbox_mode.py - Freeform Datacenter Sandbox with Dynamic Device Management & JSON Save/Load
Full creative freedom to add/remove hardware in 42U racks, cable appliances, configure Cisco IOS CLI, and export/import topologies.
"""

import json
import os
from .base_mode import BaseMode
from network.switch import Switch
from network.router import Router
from network.host import Host
from network.firewall import Firewall
from network.cable import Cable, CableType
from engine.audio import SoundManager

class SandboxMode(BaseMode):
    def __init__(self):
        super().__init__("SANDBOX PLAYGROUND")
        self.sound = SoundManager.get_instance()
        self.save_file = "sandbox_topology.json"
        self.status_msg = ""
        self.device_counter = 10
        self.setup()

    @staticmethod
    def calculate_rack_position(rack_id, u_slot):
        """Calculates 3D world coordinates (x, y, z) for a device given its rack and U-slot."""
        # RACK 1: X = -1.4, RACK 2: X = 0.0, RACK 3: X = 1.4
        x = (rack_id - 2) * 1.4
        z = -1.5
        # U-slot: 1 to 42U (0.14m bottom rail to ~1.99m top rail)
        y = round(0.14 + (u_slot / 42.0) * 1.85, 2)
        return x, y, z

    def setup(self):
        self.devices = []
        self.cables = []
        self.device_counter = 10

        # RACK 1 (X = -1.4, Z = -1.5) - Access & Distribution Layer
        sw1 = Switch("sw1", hostname="Core-Switch-01", rack_id=1, u_slot=24, num_ports=8)
        sw1.pos_x, sw1.pos_y, sw1.pos_z = self.calculate_rack_position(1, 24)

        sw2 = Switch("sw2", hostname="Dist-Switch-02", rack_id=1, u_slot=18, num_ports=8)
        sw2.pos_x, sw2.pos_y, sw2.pos_z = self.calculate_rack_position(1, 18)

        srv1 = Host("srv1", hostname="App-Server-01", device_type="server", rack_id=1, u_slot=8)
        srv1.pos_x, srv1.pos_y, srv1.pos_z = self.calculate_rack_position(1, 8)
        srv1.configure_ip("192.168.10.10", "255.255.255.0", gateway="192.168.10.1")

        # RACK 2 (X = 0.0, Z = -1.5) - Core Routing, Firewall & WAN Uplink
        rtr1 = Router("rtr1", hostname="Core-Router-01", rack_id=2, u_slot=28, num_ports=4)
        rtr1.pos_x, rtr1.pos_y, rtr1.pos_z = self.calculate_rack_position(2, 28)

        rtr2 = Router("rtr2", hostname="Edge-Router-02", rack_id=2, u_slot=20, num_ports=4)
        rtr2.pos_x, rtr2.pos_y, rtr2.pos_z = self.calculate_rack_position(2, 20)

        # Enterprise Firewall (Cisco ASA 5506-X)
        fw1 = Firewall("fw1", hostname="Edge-ASA-5506", rack_id=2, u_slot=34, num_ports=6)
        fw1.pos_x, fw1.pos_y, fw1.pos_z = self.calculate_rack_position(2, 34)

        # ISP WAN Uplink Gateway (Public IP 203.0.113.1)
        isp = Host("isp1", hostname="ISP-Gateway-Uplink", device_type="server", rack_id=2, u_slot=40)
        isp.pos_x, isp.pos_y, isp.pos_z = self.calculate_rack_position(2, 40)
        isp.configure_ip("203.0.113.1", "255.255.255.0", gateway="203.0.113.1")

        # RACK 3 (X = 1.4, Z = -1.5) - Storage & Compute Farm
        db1 = Host("db1", hostname="DB-Cluster-01", device_type="server", rack_id=3, u_slot=24)
        db1.pos_x, db1.pos_y, db1.pos_z = self.calculate_rack_position(3, 24)
        db1.configure_ip("192.168.20.10", "255.255.255.0", gateway="192.168.20.1")

        storage1 = Host("san1", hostname="SAN-Storage-01", device_type="server", rack_id=3, u_slot=14)
        storage1.pos_x, storage1.pos_y, storage1.pos_z = self.calculate_rack_position(3, 14)
        storage1.configure_ip("192.168.30.50", "255.255.255.0", gateway="192.168.30.1")

        # Workbench Dual Engineer Laptops
        lap_win = Host("lap1", hostname="Win-Laptop-01",
                       device_type="laptop", rack_id=0, u_slot=0, os_type="windows")
        lap_win.pos_x, lap_win.pos_y, lap_win.pos_z = -3.55, 0.77, 0.50
        lap_win.configure_ip("192.168.1.99", "255.255.255.0", gateway="192.168.1.1", dns="8.8.8.8")

        lap_ubu = Host("lap2", hostname="Ubuntu-Laptop-02",
                       device_type="laptop", rack_id=0, u_slot=0, os_type="ubuntu")
        lap_ubu.pos_x, lap_ubu.pos_y, lap_ubu.pos_z = -2.85, 0.77, 0.50
        lap_ubu.configure_ip("192.168.1.100", "255.255.255.0", gateway="192.168.1.1", dns="8.8.8.8")

        self.devices.extend([sw1, sw2, srv1, rtr1, rtr2, fw1, isp, db1, storage1, lap_win, lap_ubu])

        # Pre-wire initial trunk link between SW1 and SW2
        c_trunk = Cable(sw1.ports["g0/8"], sw2.ports["g0/8"], CableType.CAT6)
        sw1.ports["g0/8"].mode = "trunk"
        sw2.ports["g0/8"].mode = "trunk"
        self.cables.append(c_trunk)

        # Pre-wire Router g0/0 to ISP Gateway WAN Uplink
        rtr1.ports["g0/0"].ip_address = "203.0.113.2"
        rtr1.ports["g0/0"].subnet_mask = "255.255.255.0"
        rtr1.ports["g0/0"].is_shutdown = False
        c_isp = Cable(rtr1.ports["g0/0"], isp.eth0, CableType.CAT6)
        self.cables.append(c_isp)

    def is_slot_occupied(self, rack_id, u_slot, needed_u=1, exclude_dev_id=None):
        """Checks if target U-slot range is occupied in the specified rack."""
        req_min = u_slot
        req_max = u_slot + needed_u - 1

        for dev in self.devices:
            if dev.rack_id != rack_id:
                continue
            if exclude_dev_id and dev.id == exclude_dev_id:
                continue

            dev_span = 1 if dev.device_type in ("switch", "firewall") else 2
            dev_min = dev.u_slot
            dev_max = dev.u_slot + dev_span - 1

            # Check overlap
            if not (req_max < dev_min or req_min > dev_max):
                return True, dev
        return False, None

    def add_device(self, device_type, rack_id, u_slot, hostname=None, num_ports=None):
        """Installs a new device into the rack with collision detection."""
        rack_id = int(rack_id)
        u_slot = int(u_slot)
        if rack_id not in (1, 2, 3):
            return False, f"Invalid Rack ID: {rack_id}. Choose 1, 2, or 3.", None

        needed_u = 1 if device_type in ("switch", "firewall") else 2
        if u_slot < 1 or u_slot + needed_u - 1 > 42:
            return False, f"Slot {u_slot}U exceeds rack boundaries (1-42U).", None

        occupied, occ_dev = self.is_slot_occupied(rack_id, u_slot, needed_u)
        if occupied:
            return False, f"Slot {u_slot}U is occupied by {occ_dev.hostname}.", None

        self.device_counter += 1
        cnt = self.device_counter

        if device_type == "switch":
            dev_id = f"sw_{cnt}"
            h_name = hostname.strip() if hostname else f"Switch-0{cnt}"
            dev = Switch(dev_id, hostname=h_name, rack_id=rack_id, u_slot=u_slot, num_ports=num_ports or 8)
        elif device_type == "router":
            dev_id = f"rtr_{cnt}"
            h_name = hostname.strip() if hostname else f"Router-0{cnt}"
            dev = Router(dev_id, hostname=h_name, rack_id=rack_id, u_slot=u_slot, num_ports=num_ports or 4)
        elif device_type == "firewall":
            dev_id = f"fw_{cnt}"
            h_name = hostname.strip() if hostname else f"Firewall-ASA-0{cnt}"
            dev = Firewall(dev_id, hostname=h_name, rack_id=rack_id, u_slot=u_slot, num_ports=num_ports or 6)
        else:
            dev_id = f"srv_{cnt}"
            h_name = hostname.strip() if hostname else f"Server-0{cnt}"
            dev = Host(dev_id, hostname=h_name, device_type="server", rack_id=rack_id, u_slot=u_slot)

        dev.pos_x, dev.pos_y, dev.pos_z = self.calculate_rack_position(rack_id, u_slot)
        self.devices.append(dev)
        self.status_msg = f"Installed {dev.hostname} at RACK-0{rack_id} (Slot {u_slot}U)!"
        self.sound.play_objective()
        return True, self.status_msg, dev

    def remove_device(self, device_or_id):
        """Unplugs all connected cables and removes device from rack."""
        dev = None
        if isinstance(device_or_id, str):
            dev = next((d for d in self.devices if d.id == device_or_id), None)
        else:
            dev = device_or_id

        if not dev or dev not in self.devices:
            return False, "Device not found."

        # Disconnect all cables linked to this device
        cables_to_remove = [
            c for c in self.cables
            if (c.port_a and c.port_a.device == dev) or (c.port_b and c.port_b.device == dev)
        ]
        for c in cables_to_remove:
            c.disconnect()
            if c in self.cables:
                self.cables.remove(c)

        self.devices.remove(dev)
        self.status_msg = f"Removed {dev.hostname} ({dev.device_type.upper()}) from RACK-0{dev.rack_id}."
        self.sound.play_key()
        return True, self.status_msg

    def get_title(self):
        return "SANDBOX: ENTERPRISE DATACENTER"

    def get_objective(self):
        return "Freely add/remove devices [N], cable racks [F], configure Cisco CLI [E], or save [K]."

    def get_checklist(self):
        return [
            {"text": f"Active Devices in Racks: {len(self.devices)}", "done": True},
            {"text": f"Physical Cable Links Connected: {len(self.cables)}", "done": True},
            {"text": "Press [N] to open Rack Device Manager (Add/Remove)", "done": True},
            {"text": "Press [M] to inspect 2D Topology Diagram", "done": True},
            {"text": "Press [K] to Save Topology / [L] to Load", "done": bool(self.status_msg)}
        ]

    def get_hint(self):
        if self.status_msg:
            return self.status_msg
        return "Press [N] to Add/Remove devices. Aim + [Del] for Quick Delete. [F] to Cable. [E] for CLI."

    def save_topology(self):
        """Exports current device configurations and cable interconnections to JSON."""
        data = {
            "devices": [],
            "cables": []
        }
        for dev in self.devices:
            dev_data = {
                "id": dev.id,
                "hostname": dev.hostname,
                "type": dev.device_type,
                "rack_id": dev.rack_id,
                "u_slot": dev.u_slot,
                "num_ports": len([p for p in dev.ports.values() if p.port_type != "CONSOLE"]),
                "ports": {}
            }
            for p_name, p in dev.ports.items():
                dev_data["ports"][p_name] = {
                    "ip": p.ip_address,
                    "mask": p.subnet_mask,
                    "shutdown": p.is_shutdown,
                    "mode": p.mode,
                    "vlan": p.access_vlan
                }
            if isinstance(dev, Switch):
                dev_data["vlans"] = {str(k): v for k, v in dev.vlans.items()}
            elif isinstance(dev, Router):
                dev_data["routes"] = dev.routes
                dev_data["nat_inside"] = list(dev.nat_inside_interfaces)
                dev_data["nat_outside"] = list(dev.nat_outside_interfaces)
                dev_data["nat_rules"] = dev.nat_rules
                dev_data["access_lists"] = dev.access_lists
            elif isinstance(dev, Firewall):
                dev_data["nameif"] = dev.nameif
                dev_data["security_levels"] = dev.security_levels
                dev_data["routes"] = dev.routes
                dev_data["access_lists"] = dev.access_lists
                dev_data["access_groups"] = dev.access_groups
            elif isinstance(dev, Host):
                dev_data["gateway"] = dev.default_gateway
                dev_data["os_type"] = getattr(dev, "os_type", "ubuntu")
                dev_data["dns_server"] = getattr(dev, "dns_server", "8.8.8.8")
                dev_data["pos"] = [dev.pos_x, dev.pos_y, dev.pos_z]
            data["devices"].append(dev_data)

        for cable in self.cables:
            if cable.port_a and cable.port_b:
                data["cables"].append({
                    "from_dev": cable.port_a.device.id,
                    "from_port": cable.port_a.name,
                    "to_dev": cable.port_b.device.id,
                    "to_port": cable.port_b.name,
                    "type": cable.cable_type
                })

        try:
            with open(self.save_file, "w") as f:
                json.dump(data, f, indent=2)
            self.status_msg = f"Topology successfully saved to {self.save_file}!"
            self.sound.play_objective()
        except Exception as e:
            self.status_msg = f"Save failed: {e}"

    def load_topology(self):
        """Loads saved topology JSON file and restores all links and configs dynamically."""
        if not os.path.exists(self.save_file):
            self.status_msg = "No saved topology file found."
            return

        try:
            with open(self.save_file, "r") as f:
                data = json.load(f)

            # Disconnect all existing cables
            for c in self.cables:
                c.disconnect()
            self.cables.clear()
            self.devices.clear()

            # Dynamic Re-creation of all devices
            dev_map = {}
            for dev_data in data.get("devices", []):
                d_id = dev_data["id"]
                d_type = dev_data.get("type", "server")
                d_host = dev_data.get("hostname", "Device")
                d_rack = dev_data.get("rack_id", 1)
                d_slot = dev_data.get("u_slot", 10)
                d_ports = dev_data.get("num_ports", 8 if d_type == "switch" else (6 if d_type == "firewall" else 4))

                if d_type == "switch":
                    dev = Switch(d_id, hostname=d_host, rack_id=d_rack, u_slot=d_slot, num_ports=d_ports)
                elif d_type == "router":
                    dev = Router(d_id, hostname=d_host, rack_id=d_rack, u_slot=d_slot, num_ports=d_ports)
                elif d_type == "firewall":
                    dev = Firewall(d_id, hostname=d_host, rack_id=d_rack, u_slot=d_slot, num_ports=d_ports)
                elif d_type == "laptop":
                    dev = Host(d_id, hostname=d_host, device_type="laptop", rack_id=d_rack, u_slot=d_slot,
                               os_type=dev_data.get("os_type", "windows"))
                    if "gateway" in dev_data:
                        dev.default_gateway = dev_data["gateway"]
                    if "dns_server" in dev_data:
                        dev.dns_server = dev_data["dns_server"]
                else:
                    dev = Host(d_id, hostname=d_host, device_type="server", rack_id=d_rack, u_slot=d_slot)
                    if "gateway" in dev_data:
                        dev.default_gateway = dev_data["gateway"]

                if "pos" in dev_data:
                    dev.pos_x, dev.pos_y, dev.pos_z = dev_data["pos"]
                elif d_type == "laptop":
                    dev.pos_x, dev.pos_y, dev.pos_z = (-3.55 if getattr(dev, "os_type", "windows") == "windows" else -2.85), 0.77, 0.50
                else:
                    dev.pos_x, dev.pos_y, dev.pos_z = self.calculate_rack_position(d_rack, d_slot)

                # Restore port configurations
                for p_name, p_info in dev_data.get("ports", {}).items():
                    p = dev.ports.get(p_name)
                    if p:
                        p.ip_address = p_info.get("ip")
                        p.subnet_mask = p_info.get("mask")
                        p.is_shutdown = p_info.get("shutdown", False)
                        p.mode = p_info.get("mode", "access")
                        p.access_vlan = p_info.get("vlan", 1)

                if isinstance(dev, Switch) and "vlans" in dev_data:
                    dev.vlans = {int(k): v for k, v in dev_data["vlans"].items()}
                elif isinstance(dev, Router):
                    if "routes" in dev_data:
                        dev.routes = dev_data["routes"]
                    if "nat_inside" in dev_data:
                        dev.nat_inside_interfaces = set(dev_data["nat_inside"])
                    if "nat_outside" in dev_data:
                        dev.nat_outside_interfaces = set(dev_data["nat_outside"])
                    if "nat_rules" in dev_data:
                        dev.nat_rules = dev_data["nat_rules"]
                    if "access_lists" in dev_data:
                        dev.access_lists = dev_data["access_lists"]
                elif isinstance(dev, Firewall):
                    if "nameif" in dev_data:
                        dev.nameif = dev_data["nameif"]
                    if "security_levels" in dev_data:
                        dev.security_levels = dev_data["security_levels"]
                    if "routes" in dev_data:
                        dev.routes = dev_data["routes"]
                    if "access_lists" in dev_data:
                        dev.access_lists = dev_data["access_lists"]
                    if "access_groups" in dev_data:
                        dev.access_groups = dev_data["access_groups"]

                self.devices.append(dev)
                dev_map[d_id] = dev

            # Re-create cables
            for c_data in data.get("cables", []):
                d1 = dev_map.get(c_data["from_dev"])
                d2 = dev_map.get(c_data["to_dev"])
                if d1 and d2:
                    p1 = d1.ports.get(c_data["from_port"])
                    p2 = d2.ports.get(c_data["to_port"])
                    if p1 and p2:
                        cable = Cable(p1, p2, c_data.get("type", CableType.CAT6))
                        self.cables.append(cable)

            self.status_msg = f"Loaded {len(self.devices)} devices & {len(self.cables)} cables successfully!"
            self.sound.play_objective()
        except Exception as e:
            self.status_msg = f"Load failed: {e}"
