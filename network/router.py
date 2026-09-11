"""
network/router.py - Layer 3 Router simulation
Supports Subinterfaces (802.1Q Trunking), Static Routing, and ARP lookup.
"""

import time
import socket
import struct
from .device import BaseDevice, Port

def is_valid_ipv4(ip_str):
    if not isinstance(ip_str, str):
        return False
    parts = ip_str.strip().split(".")
    if len(parts) != 4:
        return False
    for p in parts:
        if not p.isdigit():
            return False
        num = int(p)
        if num < 0 or num > 255:
            return False
    return True

def is_valid_netmask(mask_str):
    if not is_valid_ipv4(mask_str):
        return False
    val = ip_to_int(mask_str)
    if val == 0:
        return False
    inv = (~val) & 0xFFFFFFFF
    return (inv & (inv + 1)) == 0

def ip_to_int(ip_str):
    try:
        return struct.unpack("!I", socket.inet_aton(ip_str))[0]
    except Exception:
        return 0

def int_to_ip(ip_int):
    return socket.inet_ntoa(struct.pack("!I", ip_int))

def is_ip_in_subnet(ip, network, mask):
    ip_int = ip_to_int(ip)
    net_int = ip_to_int(network)
    mask_int = ip_to_int(mask)
    return (ip_int & mask_int) == (net_int & mask_int)

def is_ip_in_wildcard(ip_str, net_str, wildcard_str="0.0.0.0"):
    try:
        ip_i = ip_to_int(ip_str)
        net_i = ip_to_int(net_str)
        wc_i = ip_to_int(wildcard_str)
        mask = (~wc_i) & 0xFFFFFFFF
        return (ip_i & mask) == (net_i & mask)
    except Exception:
        return False

class SubInterface:
    def __init__(self, parent_port, sub_id):
        self.parent_port = parent_port
        self.sub_id = sub_id
        self.name = f"{parent_port.name}.{sub_id}"
        self.full_name = f"{parent_port.full_name}.{sub_id}"
        self.ip_address = None
        self.subnet_mask = None
        self.vlan_id = None  # 802.1Q encapsulation
        self.is_shutdown = False

    @property
    def is_link_up(self):
        return (not self.is_shutdown) and self.parent_port.is_link_up


class Router(BaseDevice):
    def __init__(self, id, hostname="Router", rack_id=1, u_slot=28, num_ports=4):
        super().__init__(id, hostname, device_type="router", rack_id=rack_id, u_slot=u_slot)
        self.height = 0.044 * 2  # 2U rack height for enterprise router
        self.subinterfaces = {}  # name -> SubInterface

        for i in range(num_ports):
            p = self.add_port(f"g0/{i}", port_type="RJ45")
            p.is_shutdown = True  # Cisco router ports default to shutdown

        # Console port
        con = self.add_port("con0", port_type="CONSOLE")
        con.is_shutdown = False

        # Static / Connected Routes: list of dicts:
        # {"network": "192.168.1.0", "mask": "255.255.255.0", "next_hop": "10.0.0.2", "interface": "g0/0", "type": "S"}
        self.routes = []

        # Cisco IOS NAT & Access Lists
        self.nat_inside_interfaces = set()   # set of interface names e.g. {"g0/1"}
        self.nat_outside_interfaces = set()  # set of interface names e.g. {"g0/0"}
        self.nat_rules = []                  # list of dicts: [{"type": "overload", "acl": 1, "interface": "g0/0"}]
        self.nat_translations = []           # active mappings: [{"protocol": "icmp", "inside_global": ..., ...}]
        self.access_lists = {}               # acl_id -> list of rule dicts
        self.access_groups = {}              # interface_name (lowercase) -> {"in": acl_id, "out": acl_id}

        from .dhcp import DHCPServer
        self.dhcp_server = DHCPServer(self)

    def get_port_local_pos(self, port_name, port_index=0):
        """Returns exact local coordinates (x, y, z) on Router front face."""
        front_z = (self.depth / 2.0) + 0.007
        if "con" in port_name.lower():
            return (-0.16, -0.022, front_z)

        data_ports = [p for p in self.ports.values() if p.port_type != "CONSOLE"]
        num_data = max(1, len(data_ports))
        idx = 0
        for i, p in enumerate(data_ports):
            if p.name == port_name or p.port_index == port_index:
                idx = i
                break

        spacing = 0.040
        start_x = -((num_data - 1) * spacing) / 2.0 + 0.02
        lx = start_x + idx * spacing
        ly = -0.022
        return (lx, ly, front_z)

    def get_interface(self, name):
        """Finds physical port or subinterface by name (e.g. g0/0 or g0/0.10)."""
        clean = name.strip().lower()
        if "." in clean:
            for s_name, sub in self.subinterfaces.items():
                if s_name.lower() == clean or sub.full_name.lower() == clean:
                    return sub
        return self.get_port(name)

    def create_subinterface(self, port_name, sub_id):
        port = self.get_port(port_name)
        if not port:
            return None
        sub_name = f"{port.name}.{sub_id}"
        sub = SubInterface(port, sub_id)
        self.subinterfaces[sub_name] = sub
        return sub

    def add_static_route(self, network, mask, next_hop_or_int):
        network = network.strip()
        mask = mask.strip()
        next_hop_or_int = next_hop_or_int.strip()

        if not is_valid_ipv4(network) or not is_valid_ipv4(mask):
            return False

        # Remove duplicate if exists
        self.routes = [r for r in self.routes if not (r["network"] == network and r["mask"] == mask)]
        is_ip = is_valid_ipv4(next_hop_or_int)
        route = {
            "network": network,
            "mask": mask,
            "next_hop": next_hop_or_int if is_ip else None,
            "interface": None if is_ip else next_hop_or_int,
            "type": "S"
        }
        self.routes.append(route)
        return True

    def remove_static_route(self, network, mask, next_hop_or_int=None):
        network = network.strip()
        mask = mask.strip()
        orig_len = len(self.routes)
        if next_hop_or_int:
            clean_hop = next_hop_or_int.strip()
            self.routes = [r for r in self.routes if not (
                r["network"] == network and r["mask"] == mask and
                (r.get("next_hop") == clean_hop or r.get("interface") == clean_hop)
            )]
        else:
            self.routes = [r for r in self.routes if not (r["network"] == network and r["mask"] == mask)]
        return len(self.routes) < orig_len

    def get_all_routes(self):
        """Returns directly connected routes + active static routes."""
        all_routes = []

        # 1. Directly Connected routes from physical interfaces
        for p_name, port in self.ports.items():
            if port.is_link_up and port.ip_address and port.subnet_mask:
                net_int = ip_to_int(port.ip_address) & ip_to_int(port.subnet_mask)
                net_str = int_to_ip(net_int)
                all_routes.append({
                    "network": net_str,
                    "mask": port.subnet_mask,
                    "next_hop": "directly connected",
                    "interface": port.name,
                    "type": "C"
                })

        # 2. Directly Connected routes from subinterfaces
        for s_name, sub in self.subinterfaces.items():
            if sub.is_link_up and sub.ip_address and sub.subnet_mask:
                net_int = ip_to_int(sub.ip_address) & ip_to_int(sub.subnet_mask)
                net_str = int_to_ip(net_int)
                all_routes.append({
                    "network": net_str,
                    "mask": sub.subnet_mask,
                    "next_hop": "directly connected",
                    "interface": sub.name,
                    "type": "C"
                })

        # 3. Static routes - check interface link up if interface is specified
        for r in self.routes:
            if r.get("interface"):
                iface = self.get_interface(r["interface"])
                if iface and iface.is_link_up:
                    all_routes.append(r)
            else:
                all_routes.append(r)

        return all_routes

    def lookup_route(self, dest_ip):
        """Longest prefix match routing lookup."""
        if not is_valid_ipv4(dest_ip):
            return None
        best_match = None
        best_prefix_len = -1

        for r in self.get_all_routes():
            net = r["network"]
            mask = r["mask"]
            if is_ip_in_subnet(dest_ip, net, mask):
                # Count bits in mask
                prefix_len = bin(ip_to_int(mask)).count("1")
                if prefix_len > best_prefix_len:
                    best_prefix_len = prefix_len
                    best_match = r
        return best_match

    def add_access_list(self, acl_id, action, source, wildcard="0.0.0.0"):
        """Standard IPv4 Access-List (1-99)."""
        acl_key = str(acl_id)
        if acl_key not in self.access_lists:
            self.access_lists[acl_key] = []
        rule = {
            "action": action.lower(),
            "source": source.lower(),
            "wildcard": wildcard or "0.0.0.0"
        }
        self.access_lists[acl_key].append(rule)

    def set_access_group(self, acl_id, direction, interface_name):
        """Applies ACL to interface in ingress ('in') or egress ('out') direction."""
        clean_if = interface_name.strip().lower()
        if clean_if not in self.access_groups:
            self.access_groups[clean_if] = {}
        if acl_id is None:
            self.access_groups[clean_if].pop(direction.strip().lower(), None)
        else:
            self.access_groups[clean_if][direction.strip().lower()] = str(acl_id)

    def check_acl(self, acl_id, ip_address):
        """
        Tests ip_address against acl_id.
        Returns (permitted: bool, reason_str: str)
        First-match rule ordering with implicit deny.
        """
        acl_key = str(acl_id)
        rules = self.access_lists.get(acl_key, [])
        for idx, rule in enumerate(rules):
            src = rule["source"]
            wc = rule["wildcard"]
            matched = False
            if src == "any":
                matched = True
            elif is_ip_in_wildcard(ip_address, src, wc):
                matched = True

            if matched:
                action = rule["action"]
                if action == "permit":
                    return True, f"Permitted by access-list {acl_key} line {idx+1} ({action} {src} {wc})"
                else:
                    return False, f"Denied by access-list {acl_key} line {idx+1} ({action} {src} {wc})"
        return False, f"Denied by access-list {acl_key} implicit deny"

    def matches_acl(self, acl_id, ip_address):
        """Tests if ip_address matches any permit rule in acl_id (backward compatibility)."""
        permitted, _ = self.check_acl(acl_id, ip_address)
        return permitted

    def add_nat_rule(self, rule_type, acl_id, out_interface):
        rule = {
            "type": rule_type.lower(),  # "overload"
            "acl": str(acl_id),
            "interface": out_interface.strip().lower()
        }
        # Avoid duplicate
        self.nat_rules = [r for r in self.nat_rules if not (r["acl"] == rule["acl"] and r["interface"] == rule["interface"])]
        self.nat_rules.append(rule)

    def perform_nat(self, src_ip, in_port_name, out_port_name, protocol="icmp"):
        """
        Translates private inside local source IP to public inside global IP
        if in_port is inside, out_port is outside, and src_ip matches a NAT rule.
        """
        clean_in = in_port_name.strip().lower()
        clean_out = out_port_name.strip().lower()

        # Check if inside and outside interfaces match
        if clean_in not in self.nat_inside_interfaces or clean_out not in self.nat_outside_interfaces:
            return None, None

        # Check rules
        for rule in self.nat_rules:
            if rule["interface"] == clean_out:
                acl_id = rule["acl"]
                if self.matches_acl(acl_id, src_ip):
                    out_port = self.get_interface(clean_out)
                    out_ip = out_port.ip_address if (out_port and out_port.ip_address) else "203.0.113.2"
                    now = time.time()

                    # Find existing translation
                    existing = None
                    for tr in self.nat_translations:
                        if tr["inside_local"] == f"{src_ip}:1" and tr["protocol"] == protocol:
                            existing = tr
                            existing["last_used"] = now
                            break

                    if not existing:
                        existing = {
                            "protocol": protocol,
                            "inside_global": f"{out_ip}:1",
                            "inside_local": f"{src_ip}:1",
                            "outside_local": "---",
                            "outside_global": "---",
                            "created": now,
                            "last_used": now
                        }
                        self.nat_translations.append(existing)

                    return out_ip, existing
        return None, None

    def perform_reverse_nat(self, dst_ip, in_port_name, protocol="icmp"):
        """
        Translates public inside global destination IP back to private inside local IP
        for return traffic arriving on an outside interface.
        """
        clean_in = in_port_name.strip().lower()
        if clean_in not in self.nat_outside_interfaces:
            return None, None

        now = time.time()
        for tr in self.nat_translations:
            if tr.get("protocol") in ("ip", protocol):
                ig_ip = tr["inside_global"].split(":")[0]
                if ig_ip == dst_ip:
                    tr["last_used"] = now
                    il_ip = tr["inside_local"].split(":")[0]
                    return il_ip, tr

        return None, None

    def clear_nat_translations(self):
        count = len(self.nat_translations)
        self.nat_translations.clear()
        return count
