"""
network/firewall.py - Enterprise Stateful Firewall Appliance (Cisco ASA Style)
Supports interface security zones (nameif), security levels (0-100),
stateful packet inspection, Access Control Lists (ACL), and connection tracking.
"""

import time
import socket
import struct
from .device import BaseDevice, Port
from .router import ip_to_int, int_to_ip, is_ip_in_subnet

class Firewall(BaseDevice):
    def __init__(self, id, hostname="Firewall-ASA", rack_id=2, u_slot=22, num_ports=6):
        super().__init__(id, hostname, device_type="firewall", rack_id=rack_id, u_slot=u_slot)
        self.height = 0.044 * 1  # 1U rack height
        self.depth = 0.52

        # 6 Data Gigabit ports (g0/0 to g0/5)
        for i in range(num_ports):
            p = self.add_port(f"g0/{i}", port_type="RJ45")
            p.is_shutdown = True

        # Management & Console ports
        m0 = self.add_port("m0/0", port_type="RJ45")
        m0.is_shutdown = True
        con = self.add_port("con0", port_type="CONSOLE")
        con.is_shutdown = False

        # Interface Zone Mappings & Security Levels (Cisco ASA syntax)
        # Port name -> Zone name (nameif)
        self.nameif = {
            "g0/0": "outside",
            "g0/1": "inside",
            "g0/2": "dmz",
        }
        # Zone name -> Security level (0 - 100)
        self.security_levels = {
            "outside": 0,
            "inside": 100,
            "dmz": 50,
        }

        # Static routes: list of dicts {"network": "0.0.0.0", "mask": "0.0.0.0", "next_hop": "203.0.113.1", "interface": "g0/0"}
        self.routes = []

        # Stateful Connection Table: list of active sessions
        # {"protocol": "icmp", "src_ip": ..., "dst_ip": ..., "in_zone": ..., "out_zone": ..., "created": ...}
        self.connections = []

        # Access Control Lists (Extended ACL)
        # name -> list of rules: [{"action": "permit"/"deny", "protocol": "icmp"/"ip", "src": "any", "dst": "any"}]
        self.access_lists = {}

        # Access Groups: interface_zone -> {"in": acl_name, "out": acl_name}
        self.access_groups = {}

    def get_port_local_pos(self, port_name, port_index=0):
        """Returns exact local coordinates (x, y, z) on Firewall front face."""
        front_z = (self.depth / 2.0) + 0.007
        clean = port_name.lower()

        if "con" in clean:
            return (-0.17, 0.0, front_z)
        if "m0" in clean:
            return (-0.125, 0.0, front_z)

        data_ports = [p for p in self.ports.values() if p.port_type != "CONSOLE" and not p.name.startswith("m")]
        idx = 0
        for i, p in enumerate(data_ports):
            if p.name.lower() == clean or p.port_index == port_index:
                idx = i
                break

        spacing = 0.038
        start_x = -0.04
        lx = start_x + idx * spacing
        ly = 0.0
        return (lx, ly, front_z)

    def set_nameif(self, port_name, zone_name):
        clean_p = port_name.strip().lower()
        port = self.get_port(clean_p)
        if port:
            self.nameif[port.name] = zone_name.strip().lower()
            # Default security levels for common names if not set
            zn = zone_name.strip().lower()
            if zn == "inside" and "inside" not in self.security_levels:
                self.security_levels["inside"] = 100
            elif zn == "outside" and "outside" not in self.security_levels:
                self.security_levels["outside"] = 0
            elif zn == "dmz" and "dmz" not in self.security_levels:
                self.security_levels["dmz"] = 50
            return True
        return False

    def set_security_level(self, zone_or_port, level):
        try:
            lvl = int(level)
            lvl = max(0, min(100, lvl))
            target_zone = zone_or_port.strip().lower()
            if target_zone in self.nameif:
                target_zone = self.nameif[target_zone]
            self.security_levels[target_zone] = lvl
            return True
        except ValueError:
            return False

    set_interface_zone = set_nameif
    set_zone_security = set_security_level

    def get_zone_for_port(self, port_name):
        clean = port_name.strip().lower()
        for p, z in self.nameif.items():
            if p.lower() == clean:
                return z
        return None

    def get_port_for_zone(self, zone_name):
        clean = zone_name.strip().lower()
        for p, z in self.nameif.items():
            if z.lower() == clean:
                return self.get_port(p)
        return None

    def add_static_route(self, network, mask, next_hop_or_int, interface=None):
        network = network.strip()
        mask = mask.strip()
        self.routes = [r for r in self.routes if not (r["network"] == network and r["mask"] == mask)]
        is_ip = "." in next_hop_or_int and not next_hop_or_int.lower().startswith("g")
        route = {
            "network": network,
            "mask": mask,
            "next_hop": next_hop_or_int if is_ip else None,
            "interface": interface or (None if is_ip else next_hop_or_int),
            "type": "S"
        }
        self.routes.append(route)

    def remove_static_route(self, network, mask, next_hop_or_int=None, interface=None):
        network = network.strip()
        mask = mask.strip()
        orig_len = len(self.routes)
        if next_hop_or_int:
            clean = next_hop_or_int.strip()
            self.routes = [r for r in self.routes if not (
                r["network"] == network and r["mask"] == mask and
                (r.get("next_hop") == clean or r.get("interface") == clean)
            )]
        else:
            self.routes = [r for r in self.routes if not (r["network"] == network and r["mask"] == mask)]
        return len(self.routes) < orig_len

    def get_all_routes(self):
        all_routes = []
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
        all_routes.extend(self.routes)
        return all_routes

    def lookup_route(self, dest_ip):
        best_match = None
        best_prefix_len = -1
        for r in self.get_all_routes():
            net = r["network"]
            mask = r["mask"]
            if is_ip_in_subnet(dest_ip, net, mask):
                prefix_len = bin(ip_to_int(mask)).count("1")
                if prefix_len > best_prefix_len:
                    best_prefix_len = prefix_len
                    best_match = r
        if best_match and not best_match.get("interface") and best_match.get("next_hop"):
            nh = best_match["next_hop"]
            for p in self.ports.values():
                if p.is_link_up and p.ip_address and p.subnet_mask:
                    if is_ip_in_subnet(nh, p.ip_address, p.subnet_mask):
                        best_match = dict(best_match)
                        best_match["interface"] = p.name
                        break
        return best_match

    def add_access_list(self, acl_name, action, protocol, src, dst):
        acl_name = acl_name.strip().upper()
        if acl_name not in self.access_lists:
            self.access_lists[acl_name] = []
        rule = {
            "action": action.lower(),      # "permit" or "deny"
            "protocol": protocol.lower(),  # "ip", "icmp", "tcp", "udp"
            "src": src.lower(),            # "any" or IP
            "dst": dst.lower(),            # "any" or IP
        }
        self.access_lists[acl_name].append(rule)

    def set_access_group(self, acl_name, direction, interface_or_zone):
        clean_target = interface_or_zone.strip().lower()
        # If port name given, convert to zone if possible
        zone = self.nameif.get(clean_target, clean_target)
        if zone not in self.access_groups:
            self.access_groups[zone] = {}
        if acl_name is None:
            self.access_groups[zone].pop(direction.lower(), None)
        else:
            self.access_groups[zone][direction.lower()] = acl_name.strip().upper()

    def inspect_packet(self, in_port, target_ip, src_ip, protocol="icmp", is_reply=False):
        """
        Stateful packet inspection engine:
        - Allows established return traffic (is_reply=True).
        - Ingress ACL (if applied) is evaluated first.
        - Higher security level -> Lower security level: PERMIT statefully.
        - Lower security level -> Higher security level: DENY unless explicitly permitted by ACL.
        Returns (is_permitted: bool, reason_str: str)
        """
        now = time.time()
        # Clean expired connections older than 30 seconds
        self.connections = [c for c in self.connections if now - c.get("created", 0) < 30.0]

        # 1. Identify Ingress Zone & Security Level
        in_zone = self.get_zone_for_port(in_port.name) or in_port.name
        in_sec = self.security_levels.get(in_zone, 100)

        # 2. Identify Egress Zone & Security Level via Routing
        route = self.lookup_route(target_ip)
        egress_port = None
        if route and route.get("interface"):
            egress_port = self.get_port(route["interface"])

        if not egress_port:
            # Check directly connected interfaces
            for p in self.ports.values():
                if p != in_port and p.is_link_up and p.ip_address and p.subnet_mask:
                    if is_ip_in_subnet(target_ip, p.ip_address, p.subnet_mask):
                        egress_port = p
                        break

        out_zone = self.get_zone_for_port(egress_port.name) if egress_port else "outside"
        out_sec = self.security_levels.get(out_zone, 0)

        # 3. Check Established Session for Return Traffic (Replies)
        if is_reply:
            for conn in self.connections:
                if (conn["protocol"] in ("ip", protocol) and
                    conn["src_ip"] == target_ip and
                    conn["dst_ip"] == src_ip):
                    conn["last_used"] = now
                    return True, f"Permitted: established session ({in_zone} -> {out_zone})"

        # 4. Check Access-List on ingress interface/zone (if configured)
        acl_name = None
        if in_zone in self.access_groups and "in" in self.access_groups[in_zone]:
            acl_name = self.access_groups[in_zone]["in"]
        elif in_port.name in self.access_groups and "in" in self.access_groups[in_port.name]:
            acl_name = self.access_groups[in_port.name]["in"]

        if acl_name and acl_name in self.access_lists:
            rules = self.access_lists[acl_name]
            for rule in rules:
                proto_ok = (rule["protocol"] in ("ip", protocol))
                src_ok = (rule["src"] == "any" or rule["src"] == src_ip)
                dst_ok = (rule["dst"] == "any" or rule["dst"] == target_ip)

                if proto_ok and src_ok and dst_ok:
                    if rule["action"] == "permit":
                        self.connections.append({
                            "protocol": protocol,
                            "src_ip": src_ip,
                            "dst_ip": target_ip,
                            "in_zone": in_zone,
                            "out_zone": out_zone,
                            "created": now
                        })
                        return True, f"Permitted by access-list {acl_name}"
                    else:
                        return False, f"%ASA-4-106023: Denied by access-list {acl_name} explicit deny rule"
            return False, f"%ASA-4-106023: Deny by access-list {acl_name} implicit deny"

        # 5. Outbound Traffic: Higher to Lower Security Level (e.g. inside (100) -> outside (0))
        if in_sec > out_sec:
            self.connections.append({
                "protocol": protocol,
                "src_ip": src_ip,
                "dst_ip": target_ip,
                "in_zone": in_zone,
                "out_zone": out_zone,
                "created": now
            })
            return True, f"Permitted: higher security level ({in_zone}:{in_sec}) -> lower ({out_zone}:{out_sec})"

        # Default Implicit Deny for inbound traffic
        return False, f"%ASA-4-106023: Deny {protocol} src {in_zone}:{src_ip} dst {out_zone}:{target_ip} by default security policy"
