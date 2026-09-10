"""
network/switch.py - Layer 2 Managed Switch with VLANs and MAC Table
Simulates Cisco Catalyst / Nexus style Layer 2 switching.
"""

import time
from .device import BaseDevice

class Switch(BaseDevice):
    def __init__(self, id, hostname="Switch", rack_id=1, u_slot=24, num_ports=8):
        super().__init__(id, hostname, device_type="switch", rack_id=rack_id, u_slot=u_slot)
        self.height = 0.044 * 1  # 1U

        # VLAN Database: vlan_id -> {"name": str, "status": "active"}
        self.vlans = {
            1: {"name": "default", "status": "active"}
        }

        # MAC Address Table: mac -> {"port": port_name, "vlan": vlan_id, "timestamp": float}
        self.mac_table = {}

        # Initialize ports (e.g. g0/1 to g0/8)
        for i in range(1, num_ports + 1):
            p = self.add_port(f"g0/{i}", port_type="RJ45")
            # In switches, ports default to no shutdown
            p.is_shutdown = False
            p.mode = "access"
            p.access_vlan = 1
            p.trunk_allowed_vlans = {1}

        # Console port
        con = self.add_port("con0", port_type="CONSOLE")
        con.is_shutdown = False

    def get_port_local_pos(self, port_name, port_index=0):
        """Returns exact local coordinates (x, y, z) on Switch front face."""
        front_z = (self.depth / 2.0) + 0.007
        if "con" in port_name.lower():
            return (-0.12, -0.004, front_z)

        # Data ports (g0/1 .. g0/8)
        data_ports = [p for p in self.ports.values() if p.port_type != "CONSOLE"]
        num_data = max(1, len(data_ports))
        idx = 0
        for i, p in enumerate(data_ports):
            if p.name == port_name or p.port_index == port_index:
                idx = i
                break

        spacing = 0.034
        start_x = -((num_data - 1) * spacing) / 2.0 + 0.02
        lx = start_x + idx * spacing
        ly = -0.004
        return (lx, ly, front_z)

    def add_vlan(self, vlan_id, name=None):
        if name is None:
            name = f"VLAN{vlan_id:04d}"
        self.vlans[vlan_id] = {"name": name, "status": "active"}
        return self.vlans[vlan_id]

    def remove_vlan(self, vlan_id):
        if vlan_id in self.vlans and vlan_id != 1:
            del self.vlans[vlan_id]
            # Reset any ports using this vlan
            for port in self.ports.values():
                if port.access_vlan == vlan_id:
                    port.access_vlan = 1

    def learn_mac(self, mac, port_name, vlan_id):
        self.mac_table[mac] = {
            "port": port_name,
            "vlan": vlan_id,
            "timestamp": time.time()
        }

    def forward_packet(self, in_port, src_mac, dst_mac, vlan_id):
        """Simulates frame forwarding logic with MAC learning and broadcast/unicast."""
        # 1. Learn source MAC
        self.learn_mac(src_mac, in_port.name, vlan_id)
        in_port.trigger_traffic()

        # 2. Check destination MAC
        if dst_mac == "FF:FF:FF:FF:FF:FF" or dst_mac not in self.mac_table:
            # Broadcast / Flood to all ports participating in this VLAN
            out_ports = []
            for p_name, port in self.ports.items():
                if port == in_port or port.is_shutdown or not port.cable:
                    continue
                if port.mode == "access" and port.access_vlan == vlan_id:
                    out_ports.append(port)
                elif port.mode == "trunk" and (vlan_id in port.trunk_allowed_vlans or not port.trunk_allowed_vlans):
                    out_ports.append(port)
            return out_ports
        else:
            # Known unicast
            entry = self.mac_table[dst_mac]
            target_port_name = entry["port"]
            target_port = self.get_port(target_port_name)
            if target_port and not target_port.is_shutdown and target_port.cable:
                # Check VLAN membership
                if target_port.mode == "access" and target_port.access_vlan == vlan_id:
                    return [target_port]
                elif target_port.mode == "trunk" and (vlan_id in target_port.trunk_allowed_vlans or not target_port.trunk_allowed_vlans):
                    return [target_port]
            return []
