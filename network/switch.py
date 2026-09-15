"""
network/switch.py - Layer 2 Managed Switch with VLANs, MAC Table, and Spanning Tree Protocol (STP)
Simulates Cisco Catalyst / Nexus style Layer 2 switching with IEEE 802.1D Spanning Tree.
"""

import time
from .device import BaseDevice

def normalize_mac(mac_str):
    if not mac_str:
        return "00:00:00:00:00:00"
    clean = mac_str.lower().replace(".", "").replace("-", "").replace(":", "")
    if len(clean) == 12:
        return ":".join(clean[i:i+2] for i in range(0, 12, 2))
    return mac_str.lower()

def format_vlan_ranges(vlan_iter):
    """Formats an iterable of VLAN IDs into Cisco range notation (e.g. '1,10-12,20')."""
    if not vlan_iter:
        return "none"
    try:
        vlans = sorted(set(int(v) for v in vlan_iter if isinstance(v, (int, str)) and str(v).isdigit()))
    except Exception:
        return "none"
    if not vlans:
        return "none"
    ranges = []
    start = vlans[0]
    end = vlans[0]
    for v in vlans[1:]:
        if v == end + 1:
            end = v
        else:
            ranges.append(f"{start}-{end}" if start != end else f"{start}")
            start = v
            end = v
    ranges.append(f"{start}-{end}" if start != end else f"{start}")
    return ",".join(ranges)

def parse_vlan_ranges(vlan_str):
    """
    Parses a string containing VLAN IDs and ranges (e.g. '10,20,30-35') into a set of ints.
    Raises ValueError on invalid formats, out-of-bounds VLAN IDs (1-4094), or inverted ranges.
    """
    if not vlan_str or not vlan_str.strip():
        return set()
    clean = vlan_str.replace(" ", ",")
    parts = [p.strip() for p in clean.split(",") if p.strip()]
    vlans = set()
    for part in parts:
        if "-" in part:
            sub = part.split("-")
            if len(sub) != 2 or not sub[0].isdigit() or not sub[1].isdigit():
                raise ValueError(f"Invalid VLAN range: {part}")
            low, high = int(sub[0]), int(sub[1])
            if low < 1 or high > 4094 or low > high:
                raise ValueError(f"Invalid VLAN range: {part}")
            for vid in range(low, high + 1):
                vlans.add(vid)
        else:
            if not part.isdigit():
                raise ValueError(f"Invalid VLAN ID: {part}")
            vid = int(part)
            if vid < 1 or vid > 4094:
                raise ValueError(f"VLAN ID out of range (1-4094): {vid}")
            vlans.add(vid)
    return vlans

class SVI:
    """
    Switch Virtual Interface (SVI) - A logical Layer 3 interface representing a VLAN.
    In Cisco IOS, SVIs start administratively down and transition to operational UP
    only when not shutdown and at least one physical port in that VLAN is UP (autostate).
    """
    def __init__(self, switch, vlan_id):
        self.switch = switch
        self.vlan_id = int(vlan_id)
        self.name = f"Vlan{self.vlan_id}"
        self.full_name = f"Vlan{self.vlan_id}"
        self.ip_address = None
        self.subnet_mask = None
        self.is_shutdown = True  # Cisco standard: SVI starts administratively down
        # MAC address derived from the switch's base MAC
        self.mac_address = switch.mac_address

    @property
    def is_link_up(self):
        """
        Operational state (Autostate):
        Returns True only if administratively UP, the VLAN exists and is active,
        and at least one member physical port in the VLAN is operationally up.
        """
        if self.is_shutdown:
            return False
        if self.vlan_id not in self.switch.vlans:
            return False
        if self.switch.vlans[self.vlan_id].get("status") != "active":
            return False
        for p in self.switch.ports.values():
            if p.port_type == "CONSOLE" or p.is_shutdown or not p.is_link_up:
                continue
            if p.mode == "access" and p.access_vlan == self.vlan_id:
                return True
            elif p.mode == "trunk" and (self.vlan_id in p.trunk_allowed_vlans or not p.trunk_allowed_vlans):
                return True
        return False

    @property
    def admin_state(self):
        return "down" if self.is_shutdown else "up"

    @property
    def oper_state(self):
        return "up" if self.is_link_up else "down"

    def __repr__(self):
        return f"<SVI {self.name} IP={self.ip_address} Admin={'DOWN' if self.is_shutdown else 'UP'} Oper={'UP' if self.is_link_up else 'DOWN'}>"

class Switch(BaseDevice):
    def __init__(self, id, hostname="Switch", rack_id=1, u_slot=24, num_ports=8):
        super().__init__(id, hostname, device_type="switch", rack_id=rack_id, u_slot=u_slot)
        self.height = 0.044 * 1  # 1U

        # VLAN Database: vlan_id -> {"name": str, "status": "active"}
        self.vlans = {
            1: {"name": "default", "status": "active"}
        }

        # SVI (Switch Virtual Interfaces): vlan_id -> SVI
        self.svis = {}
        self.default_gateway = None

        from .dhcp import DHCPServer
        self.dhcp_server = DHCPServer(self)

        # MAC Address Table: mac -> {"port": port_name, "vlan": vlan_id, "timestamp": float}
        self.mac_table = {}
        # Per-VLAN MAC Table: (vlan_id, mac) -> {"port": port_name, "vlan": vlan_id, "timestamp": float}
        self.mac_vlan_table = {}

        # STP (Spanning Tree Protocol - IEEE 802.1D)
        self.stp_enabled = True
        self.stp_priority = 32768
        self.mac_address = f"00:11:22:33:{(hash(str(self.id)) & 0xFF):02x}:01"
        self.root_bridge_id = None
        self.root_path_cost = 0
        self.root_port = None
        self._stp_dirty = True

        # Initialize ports (e.g. g0/1 to g0/8)
        for i in range(1, num_ports + 1):
            p = self.add_port(f"g0/{i}", port_type="RJ45")
            # In switches, ports default to no shutdown
            p.is_shutdown = False
            p.mode = "access"
            p.access_vlan = 1
            p.trunk_allowed_vlans = {1}
            p.stp_state = "Forwarding"
            p.stp_role = "Designated"
            p.stp_cost = 4

        # Console port
        con = self.add_port("con0", port_type="CONSOLE")
        con.is_shutdown = False

    @property
    def bridge_id(self):
        """Returns the Bridge ID tuple: (Priority, Normalized MAC)."""
        return (int(self.stp_priority), normalize_mac(self.mac_address))

    @property
    def is_root_bridge(self):
        """Returns True if this switch is currently the Root Bridge."""
        if self.root_bridge_id is None:
            return True
        return self.bridge_id == self.root_bridge_id

    def get_port_local_pos(self, port_name, port_index=0):
        """Returns exact local coordinates (x, y, z) on Switch front face."""
        front_z = (self.depth / 2.0) + 0.007
        if "con" in port_name.lower():
            return (-0.160, -0.004, front_z)

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

    def get_svi(self, vlan_id):
        """Returns SVI for vlan_id or None."""
        try:
            return self.svis.get(int(vlan_id))
        except (ValueError, TypeError):
            return None

    def create_svi(self, vlan_id):
        """Creates or returns SVI for vlan_id. Requires VLAN to exist in self.vlans."""
        try:
            vid = int(vlan_id)
        except (ValueError, TypeError):
            return None
        if vid not in self.vlans:
            return None
        if vid not in self.svis:
            self.svis[vid] = SVI(self, vid)
        return self.svis[vid]

    def remove_svi(self, vlan_id):
        """Removes SVI for vlan_id."""
        try:
            vid = int(vlan_id)
            if vid in self.svis:
                del self.svis[vid]
                return True
        except (ValueError, TypeError):
            pass
        return False

    def get_interface(self, name):
        """Finds physical port or SVI by name (e.g. g0/1, Vlan10, vlan 10)."""
        clean = name.strip().lower()
        if clean.startswith("vlan"):
            v_str = clean[4:].strip()
            if v_str.isdigit():
                return self.get_svi(int(v_str))
        return self.get_port(name)

    def get_all_routes(self):
        """Returns directly connected routes for active SVIs with configured IP."""
        from .router import ip_to_int, int_to_ip
        routes = []
        for vid, svi in sorted(self.svis.items()):
            if svi.is_link_up and svi.ip_address and svi.subnet_mask:
                net_int = ip_to_int(svi.ip_address) & ip_to_int(svi.subnet_mask)
                net_str = int_to_ip(net_int)
                routes.append({
                    "network": net_str,
                    "mask": svi.subnet_mask,
                    "next_hop": "directly connected",
                    "interface": svi.name,
                    "type": "C"
                })
        return routes

    def get_first_active_port_for_vlan(self, vlan_id):
        """Returns the first physically UP and STP forwarding port for the given VLAN."""
        for port in self.ports.values():
            if port.port_type == "CONSOLE" or port.is_shutdown or not port.cable or not port.is_link_up:
                continue
            if self.stp_enabled and getattr(port, "stp_state", "Forwarding") == "Blocking":
                continue
            if port.mode == "access" and port.access_vlan == vlan_id:
                return port
            if port.mode == "trunk" and (vlan_id in port.trunk_allowed_vlans or not port.trunk_allowed_vlans):
                return port
        return None

    def get_connected_switches(self):
        """Discovers all reachable switches in the same Layer 2 network component via cables."""
        visited = set()
        queue = [self]
        visited.add(self)
        while queue:
            curr = queue.pop(0)
            for p in curr.ports.values():
                if p.is_shutdown or not p.cable or p.cable.is_damaged:
                    continue
                peer = p.cable.get_peer_port(p)
                if peer and not peer.is_shutdown and isinstance(peer.device, Switch):
                    if peer.device not in visited:
                        visited.add(peer.device)
                        queue.append(peer.device)
        return list(visited)

    def recalculate_stp(self):
        """
        Calculates IEEE 802.1D Spanning Tree for the connected switch topology.
        Determines Root Bridge, Root Ports, Designated Ports, and Alternate (Blocking) Ports.
        """
        switches = self.get_connected_switches()
        if not switches:
            return

        # 1. Elect Root Bridge (Lowest Bridge ID: Priority first, then MAC)
        root_bridge = min(switches, key=lambda s: s.bridge_id)

        # 2. Dijkstra: Shortest Path to Root Bridge (Root Path Cost)
        root_path_cost = {s: float("inf") for s in switches}
        root_path_cost[root_bridge] = 0

        unvisited = set(switches)
        while unvisited:
            curr = min(unvisited, key=lambda s: (root_path_cost[s], s.bridge_id))
            unvisited.remove(curr)
            curr_cost = root_path_cost[curr]
            if curr_cost == float("inf"):
                break

            for p in curr.ports.values():
                if p.is_shutdown or not p.cable or p.cable.is_damaged:
                    continue
                peer = p.cable.get_peer_port(p)
                if peer and not peer.is_shutdown and isinstance(peer.device, Switch) and peer.device in switches:
                    neighbor = peer.device
                    alt_cost = curr_cost + p.stp_cost
                    if alt_cost < root_path_cost[neighbor]:
                        root_path_cost[neighbor] = alt_cost

        # 3. Choose Root Port for each non-root switch
        for s in switches:
            s.root_bridge_id = root_bridge.bridge_id
            s.root_path_cost = root_path_cost[s]
            s._stp_dirty = False

            if s == root_bridge:
                s.root_port = None
            else:
                candidates = []
                for p in s.ports.values():
                    if p.is_shutdown or not p.cable or p.cable.is_damaged:
                        continue
                    peer = p.cable.get_peer_port(p)
                    if peer and not peer.is_shutdown and isinstance(peer.device, Switch) and peer.device in switches:
                        neighbor = peer.device
                        total_cost = root_path_cost[neighbor] + p.stp_cost
                        # Tie-breaking order (IEEE 802.1D):
                        # 1. Lowest Root Path Cost
                        # 2. Lowest Neighbor Bridge ID
                        # 3. Lowest Neighbor Port Index
                        # 4. Lowest Local Port Index
                        cand_key = (total_cost, neighbor.bridge_id, peer.port_index, p.port_index)
                        candidates.append((cand_key, p))
                if candidates:
                    candidates.sort(key=lambda x: x[0])
                    s.root_port = candidates[0][1]
                else:
                    s.root_port = None

        # 4. Assign default roles and states for all ports
        for s in switches:
            for p in s.ports.values():
                if p.is_shutdown:
                    p.stp_role = "Disabled"
                    p.stp_state = "Disabled"
                    continue
                if p.cable and p.cable.is_damaged:
                    p.stp_role = "Disabled"
                    p.stp_state = "Disabled"
                    continue
                peer = p.cable.get_peer_port(p) if p.cable else None
                if peer and peer.is_shutdown:
                    p.stp_role = "Disabled"
                    p.stp_state = "Disabled"
                    continue
                # For all non-shutdown ports, default to Designated / Forwarding
                p.stp_role = "Designated"
                p.stp_state = "Forwarding"

        # 5. Evaluate all Switch-to-Switch links
        evaluated_links = set()
        for s in switches:
            for p in s.ports.values():
                if p.is_shutdown or not p.cable or p.cable.is_damaged:
                    continue
                peer = p.cable.get_peer_port(p)
                if not peer or peer.is_shutdown or not isinstance(peer.device, Switch) or peer.device not in switches:
                    continue

                link_id = tuple(sorted([(s.id, p.name), (peer.device.id, peer.name)]))
                if link_id in evaluated_links:
                    continue
                evaluated_links.add(link_id)

                sw_a, port_a = s, p
                sw_b, port_b = peer.device, peer

                is_rp_a = (port_a == sw_a.root_port)
                is_rp_b = (port_b == sw_b.root_port)

                if is_rp_a and is_rp_b:
                    port_a.stp_role = "Root"
                    port_a.stp_state = "Forwarding"
                    port_b.stp_role = "Root"
                    port_b.stp_state = "Forwarding"
                elif is_rp_a:
                    port_a.stp_role = "Root"
                    port_a.stp_state = "Forwarding"
                    port_b.stp_role = "Designated"
                    port_b.stp_state = "Forwarding"
                elif is_rp_b:
                    port_b.stp_role = "Root"
                    port_b.stp_state = "Forwarding"
                    port_a.stp_role = "Designated"
                    port_a.stp_state = "Forwarding"
                else:
                    # Neither is Root Port: potential loop segment
                    # Elect Designated Bridge:
                    # 1. Lowest root_path_cost
                    # 2. Lowest bridge_id
                    # 3. Lowest port_index
                    key_a = (sw_a.root_path_cost, sw_a.bridge_id, port_a.port_index)
                    key_b = (sw_b.root_path_cost, sw_b.bridge_id, port_b.port_index)

                    if key_a < key_b:
                        port_a.stp_role = "Designated"
                        port_a.stp_state = "Forwarding"
                        port_b.stp_role = "Alternate"
                        port_b.stp_state = "Blocking"
                    else:
                        port_b.stp_role = "Designated"
                        port_b.stp_state = "Forwarding"
                        port_a.stp_role = "Alternate"
                        port_a.stp_state = "Blocking"

    def learn_mac(self, mac, port_name, vlan_id):
        """Records source MAC in MAC table and per-VLAN MAC table, respecting STP blocking state."""
        port = self.get_port(port_name)
        if port and self.stp_enabled and getattr(port, "stp_state", "Forwarding") == "Blocking":
            return
        entry = {
            "port": port_name,
            "vlan": vlan_id,
            "timestamp": time.time()
        }
        self.mac_table[mac] = entry
        self.mac_vlan_table[(vlan_id, mac)] = entry

    def forward_packet(self, in_port, src_mac, dst_mac, vlan_id):
        """Simulates frame forwarding logic with per-VLAN MAC learning, STP blocking, and broadcast/unicast."""
        if self.stp_enabled:
            if self._stp_dirty or self.root_bridge_id is None:
                self.recalculate_stp()

        # 0. Check if incoming port is in Blocking state
        if self.stp_enabled and getattr(in_port, "stp_state", "Forwarding") == "Blocking":
            return []

        # 1. Ingress VLAN filtering on in_port
        if in_port.mode == "access" and in_port.access_vlan != vlan_id:
            return []
        if in_port.mode == "trunk" and (vlan_id not in in_port.trunk_allowed_vlans):
            return []

        # 2. Learn source MAC (only if port is in Forwarding state)
        if (not self.stp_enabled) or getattr(in_port, "stp_state", "Forwarding") == "Forwarding":
            self.learn_mac(src_mac, in_port.name, vlan_id)
        in_port.trigger_traffic()

        # 3. Check destination MAC per VLAN
        vlan_mac_key = (vlan_id, dst_mac)
        if dst_mac == "FF:FF:FF:FF:FF:FF" or vlan_mac_key not in self.mac_vlan_table:
            # Broadcast / Unknown Unicast: flood to all ports participating in this VLAN in Forwarding state
            out_ports = []
            for p_name, port in self.ports.items():
                if port == in_port or port.is_shutdown or not port.cable:
                    continue
                # STP check
                if self.stp_enabled and getattr(port, "stp_state", "Forwarding") != "Forwarding":
                    continue
                # Egress VLAN check
                if port.mode == "access" and port.access_vlan == vlan_id:
                    out_ports.append(port)
                elif port.mode == "trunk" and vlan_id in port.trunk_allowed_vlans:
                    out_ports.append(port)
            return out_ports
        else:
            # Known unicast in this VLAN
            entry = self.mac_vlan_table[vlan_mac_key]
            target_port_name = entry["port"]
            target_port = self.get_port(target_port_name)
            if target_port and not target_port.is_shutdown and target_port.cable:
                # STP check
                if self.stp_enabled and getattr(target_port, "stp_state", "Forwarding") != "Forwarding":
                    return []
                # Egress VLAN check
                if target_port.mode == "access" and target_port.access_vlan == vlan_id:
                    return [target_port]
                elif target_port.mode == "trunk" and vlan_id in target_port.trunk_allowed_vlans:
                    return [target_port]
            return []
