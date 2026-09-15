"""
network/packet_engine.py - Realistic Hop-by-Hop Network Simulation & ICMP Engine
Simulates packet transmission through cables, switches (VLANs), and routers (Routing Tables).
Supports Cisco status codes (!, ., U, A), cold ARP cache drops (.!!!!), latency jitter,
TTL decrements, and step-by-step real-time execution.
"""

import time
import random
from .router import is_ip_in_subnet, ip_to_int, Router
from .switch import Switch, SVI
from .host import Host
from .firewall import Firewall
from .dhcp import DHCPMessage, DHCPMessageType, DHCPClientState
from engine.audio import SoundManager

PUBLIC_INTERNET_IPS = {"8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1", "208.67.222.222", "9.9.9.9"}

def is_private_ip(ip_str):
    try:
        val = ip_to_int(ip_str)
        # 10.0.0.0/8
        if (val & 0xFF000000) == 0x0A000000:
            return True
        # 172.16.0.0/12
        if (val & 0xFFF00000) == 0xAC100000:
            return True
        # 192.168.0.0/16
        if (val & 0xFFFF0000) == 0xC0A80000:
            return True
        # 127.0.0.0/8
        if (val & 0xFF000000) == 0x7F000000:
            return True
        return False
    except Exception:
        return False

def format_cisco_mac(mac_str):
    """Formats standard MAC 02:00:xx:xx:xx:xx into Cisco dotted notation: 0200.xxxx.xxxx."""
    if not mac_str:
        return "0000.0000.0000"
    clean = mac_str.replace(":", "").replace(".", "").replace("-", "").lower()
    if len(clean) == 12:
        return f"{clean[0:4]}.{clean[4:8]}.{clean[8:12]}"
    return mac_str

class PingResult:
    def __init__(self, target_ip, packets_sent=5, timeout_sec=2, data_bytes=100):
        self.target_ip = target_ip
        self.packets_sent = packets_sent
        self.packets_received = 0
        self.timeout_sec = timeout_sec
        self.data_bytes = data_bytes
        self.rtt_ms = []
        self.status_codes = []  # List of status characters: '!', '.', 'U', 'A'
        self.ttl_replies = []   # TTL values per reply
        self.hop_path = []      # List of device hostnames traversed
        self.detailed_hops = [] # List of hop dicts
        self.error_message = None

    @property
    def success(self):
        return self.packets_received > 0

    @property
    def loss_percent(self):
        if self.packets_sent == 0:
            return 100
        return int(((self.packets_sent - self.packets_received) / self.packets_sent) * 100)

    @property
    def success_rate_cisco(self):
        if self.status_codes:
            return "".join(self.status_codes)
        # Fallback if status_codes empty
        result = []
        for i in range(self.packets_sent):
            if i < self.packets_received:
                result.append("!")
            else:
                result.append("." if not self.error_message else "U")
        return "".join(result)

    @property
    def avg_rtt(self):
        return round(sum(self.rtt_ms) / len(self.rtt_ms), 2) if self.rtt_ms else 0.0

    @property
    def min_rtt(self):
        return min(self.rtt_ms) if self.rtt_ms else 0.0

    @property
    def max_rtt(self):
        return max(self.rtt_ms) if self.rtt_ms else 0.0

    @property
    def mdev(self):
        """Mean deviation / jitter for Linux ping statistics."""
        if len(self.rtt_ms) < 2:
            return 0.0
        avg = sum(self.rtt_ms) / len(self.rtt_ms)
        devs = [abs(x - avg) for x in self.rtt_ms]
        return round(sum(devs) / len(devs), 3)

class PacketEngine:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = PacketEngine()
        return cls._instance

    def __init__(self):
        self.sound = SoundManager.get_instance()

    def _is_self_ip(self, dev, target_ip):
        """Checks if target_ip is a loopback or local interface IP of dev."""
        if target_ip in ("127.0.0.1", "localhost"):
            return True
        if isinstance(dev, Host):
            return bool(dev.eth0 and dev.eth0.ip_address == target_ip)
        if hasattr(dev, "ports"):
            for p in dev.ports.values():
                if p.ip_address == target_ip and not p.is_shutdown:
                    return True
        if hasattr(dev, "subinterfaces"):
            for sub in dev.subinterfaces.values():
                if sub.ip_address == target_ip and not sub.is_shutdown:
                    return True
        if hasattr(dev, "svis"):
            for svi in dev.svis.values():
                if svi.ip_address == target_ip and not svi.is_shutdown:
                    return True
        return False

    def simulate_ping(self, source_device, target_ip, count=5, timeout=2, data_bytes=100,
                      source_interface=None, simulate_arp=False):
        """
        Executes complete ICMP ping from source_device to target_ip across the network topology.
        simulate_arp: If True, first packet on cold ARP cache drops with '.' and resolves ARP.
                      Default False preserves 100% backward compatibility with automated tests.
        """
        result = PingResult(target_ip, packets_sent=count, timeout_sec=timeout, data_bytes=data_bytes)

        # Ensure dynamic routing tables are converged
        from .rip import converge_all_rip
        converge_all_rip()
        from .ospf import converge_all_ospf
        converge_all_ospf()

        # 0. Check self-ping (always succeeds without wire traversal)
        if self._is_self_ip(source_device, target_ip):
            result.packets_received = count
            result.rtt_ms = [0.1] * count
            result.status_codes = ["!"] * count
            result.ttl_replies = [64 if isinstance(source_device, Host) else 255] * count
            result.hop_path = [source_device.hostname]
            self.sound.play_ping(success=True)
            return result

        # 1. Validate source configuration
        src_port, src_ip, src_mask = self._find_source_ip_context(source_device, target_ip, source_interface)
        if not src_ip or not src_port:
            result.error_message = "% No IP address or active interface configured on source"
            result.status_codes = ["U"] * count
            return result

        # 2. Transmit packets
        for pkt_idx in range(count):
            step = self.trace_single_packet(source_device, target_ip, pkt_index=pkt_idx,
                                           count=count, timeout=timeout, data_bytes=data_bytes,
                                           source_interface=source_interface, simulate_arp=simulate_arp)
            result.status_codes.append(step["status_code"])
            if step["success"]:
                result.packets_received += 1
                result.rtt_ms.append(step["rtt_ms"])
                result.ttl_replies.append(step["ttl"])
                result.hop_path = step["hop_path"]
            elif step["error_message"] and not result.error_message:
                result.error_message = step["error_message"]

        if result.packets_received > 0:
            self.sound.play_ping(success=True)
        else:
            self.sound.play_ping(success=False)

        return result

    def trace_single_packet(self, source_device, target_ip, pkt_index=0, count=5, timeout=2,
                            data_bytes=100, source_interface=None, simulate_arp=True):
        """
        Traces a single ICMP Echo packet (Echo Request -> Echo Reply) from source_device to target_ip.
        Returns a dictionary containing status_code, success, rtt_ms, ttl, hop_path, error_message, and drop_reason.
        """
        step = {
            "status_code": ".",
            "success": False,
            "rtt_ms": None,
            "ttl": None,
            "hop_path": [source_device.hostname],
            "error_message": None,
            "drop_reason": None
        }

        # 0. Check self-ping
        if self._is_self_ip(source_device, target_ip):
            step["status_code"] = "!"
            step["success"] = True
            step["rtt_ms"] = 0.1
            step["ttl"] = 64 if isinstance(source_device, Host) else 255
            return step

        # 1. Validate source configuration
        src_if, src_ip, src_mask = self._find_source_ip_context(source_device, target_ip, source_interface)
        if not src_ip or not src_if or not src_if.is_link_up:
            step["status_code"] = "U"
            step["error_message"] = "% Interface is down or unconfigured"
            step["drop_reason"] = "Source interface is down or unconfigured"
            return step

        src_port = getattr(src_if, "parent_port", src_if)
        src_vlan = getattr(src_if, "vlan_id", getattr(src_port, "access_vlan", 1)) or 1
        if isinstance(source_device, Switch) and hasattr(source_device, "svis"):
            for s in source_device.svis.values():
                if s.ip_address == src_ip:
                    src_vlan = s.vlan_id
                    break

        # 2. Determine next-hop IP for ARP resolution
        next_hop_ip = target_ip
        if not is_ip_in_subnet(target_ip, src_ip, src_mask):
            if isinstance(source_device, (Router, Firewall)):
                route = source_device.lookup_route(target_ip)
                if not route:
                    step["status_code"] = "U"
                    step["error_message"] = "% Destination network unreachable"
                    step["drop_reason"] = "No route to destination network"
                    return step
                if route.get("next_hop") and route["next_hop"] != "directly connected":
                    next_hop_ip = route["next_hop"]
            elif isinstance(source_device, Host):
                if source_device.default_gateway:
                    next_hop_ip = source_device.default_gateway
                else:
                    step["status_code"] = "U"
                    step["error_message"] = "From " + source_device.hostname + ": Destination Host Unreachable"
                    step["drop_reason"] = "No default gateway configured on host"
                    return step
            elif isinstance(source_device, Switch):
                if getattr(source_device, "default_gateway", None):
                    next_hop_ip = source_device.default_gateway
                else:
                    step["status_code"] = "U"
                    step["error_message"] = "% Destination network unreachable"
                    step["drop_reason"] = "No default gateway configured on switch"
                    return step

        # 3. ARP Simulation on Source
        arp_entry = source_device.lookup_arp(next_hop_ip)
        if simulate_arp:
            if not arp_entry:
                reachable, peer_mac = self._probe_arp_resolution(source_device, src_port, next_hop_ip, vlan_id=src_vlan)
                if reachable:
                    source_device.add_arp_entry(next_hop_ip, peer_mac, src_port.name)
                    arp_entry = source_device.lookup_arp(next_hop_ip)
                    if pkt_index == 0:
                        step["status_code"] = "."
                        step["drop_reason"] = "ARP resolution timeout"
                        step["error_message"] = "Request timed out during ARP resolution"
                        return step
                else:
                    step["status_code"] = "."
                    step["drop_reason"] = "ARP request failed"
                    step["error_message"] = "ARP resolution failed"
                    return step
        elif not arp_entry:
            # Automatic ARP resolution for tests with simulate_arp=False
            reachable, peer_mac = self._probe_arp_resolution(source_device, src_port, next_hop_ip, vlan_id=src_vlan)
            if reachable:
                source_device.add_arp_entry(next_hop_ip, peer_mac, src_port.name)
                arp_entry = source_device.lookup_arp(next_hop_ip)

        src_mac = getattr(src_port, "mac_address", "02:00:1a:00:00:01")
        if isinstance(source_device, Switch):
            for s in getattr(source_device, "svis", {}).values():
                if s.ip_address == src_ip:
                    src_mac = s.mac_address
                    break
        dst_mac = arp_entry["mac"] if arp_entry else "FF:FF:FF:FF:FF:FF"

        # 4. Trace Echo Request forward path
        req_visited = set()
        traversed_hops = [source_device.hostname]
        req_context = {"drop_code": ".", "firewall_deny": False, "unrouted": False, "l3_hops": 0}

        is_sub = hasattr(src_if, "parent_port")
        init_tagged = is_sub or (getattr(src_port, "mode", None) == "trunk" and src_vlan != getattr(src_port, "native_vlan", 1))
        req_ok = self._trace_packet(source_device, src_port, src_ip, src_mask,
                                    target_ip, req_visited, traversed_hops,
                                    current_vlan=src_vlan,
                                    ttl=15, trace_context=req_context,
                                    src_mac=src_mac, dst_mac=dst_mac, is_reply=False,
                                    is_tagged=init_tagged)

        step["hop_path"] = traversed_hops

        if not req_ok:
            if req_context.get("firewall_deny") or req_context.get("acl_deny"):
                step["status_code"] = "A"
            elif req_context.get("unrouted") or req_context.get("interface_down"):
                step["status_code"] = "U"
            else:
                step["status_code"] = req_context.get("drop_code", ".")
            step["drop_reason"] = req_context.get("drop_reason", "Request timed out")
            step["error_message"] = step["drop_reason"]
            return step

        # 5. Handle Destination Reachability & Echo Reply
        if target_ip in PUBLIC_INTERNET_IPS or "Public-Internet" in "".join(traversed_hops):
            # Public Cloud/Internet simulated Echo Reply
            reply_ok = True
            dest_dev = None
        else:
            dest_dev = req_context.get("destination_device")
            dest_target_ip = req_context.get("final_dst_ip", target_ip)
            dest_reply_to_ip = req_context.get("final_src_ip", src_ip)

            # Check if destination device has return route / default gateway
            if isinstance(dest_dev, Host):
                reply_if = dest_dev.eth0
                if not is_ip_in_subnet(dest_reply_to_ip, dest_dev.eth0.ip_address, dest_dev.eth0.subnet_mask):
                    if not dest_dev.default_gateway:
                        step["status_code"] = "U"
                        step["drop_reason"] = f"Destination {dest_dev.hostname} has no default gateway to reach {dest_reply_to_ip}"
                        step["error_message"] = step["drop_reason"]
                        return step
            elif isinstance(dest_dev, (Router, Firewall)):
                rep_route = dest_dev.lookup_route(dest_reply_to_ip)
                if not rep_route:
                    step["status_code"] = "U"
                    step["drop_reason"] = f"Destination {dest_dev.hostname} has no route back to {dest_reply_to_ip}"
                    step["error_message"] = step["drop_reason"]
                    return step
                reply_if, _, _ = self._find_source_ip_context(dest_dev, dest_reply_to_ip)
            elif isinstance(dest_dev, Switch):
                reply_svi = None
                for s in dest_dev.svis.values():
                    if s.ip_address == dest_target_ip and s.is_link_up:
                        reply_svi = s
                        break
                if not reply_svi:
                    step["status_code"] = "U"
                    step["drop_reason"] = f"Destination {dest_dev.hostname} SVI is down or unconfigured"
                    step["error_message"] = step["drop_reason"]
                    return step
                if not is_ip_in_subnet(dest_reply_to_ip, reply_svi.ip_address, reply_svi.subnet_mask):
                    if not dest_dev.default_gateway:
                        step["status_code"] = "U"
                        step["drop_reason"] = f"Destination {dest_dev.hostname} has no default gateway to reach {dest_reply_to_ip}"
                        step["error_message"] = step["drop_reason"]
                        return step
                reply_if = req_context.get("destination_port")
            else:
                reply_if = req_context.get("destination_port")

            reply_port = getattr(reply_if, "parent_port", reply_if)
            reply_vlan = req_context.get("final_vlan", getattr(reply_if, "vlan_id", getattr(reply_port, "access_vlan", 1)) or 1)

            # Trace Echo Reply packet back to source
            rep_visited = set()
            rep_hops = [dest_dev.hostname if dest_dev else "Destination"]
            rep_context = {"drop_code": ".", "firewall_deny": False, "unrouted": False, "l3_hops": 0}

            # Reply next hop MAC resolution
            rep_next_hop = dest_reply_to_ip
            if isinstance(dest_dev, Host) and not is_ip_in_subnet(dest_reply_to_ip, dest_dev.eth0.ip_address, dest_dev.eth0.subnet_mask):
                rep_next_hop = dest_dev.default_gateway
            elif isinstance(dest_dev, Switch) and not is_ip_in_subnet(dest_reply_to_ip, reply_svi.ip_address, reply_svi.subnet_mask):
                rep_next_hop = dest_dev.default_gateway
            elif isinstance(dest_dev, (Router, Firewall)):
                if rep_route and rep_route.get("next_hop") and rep_route["next_hop"] != "directly connected":
                    rep_next_hop = rep_route["next_hop"]

            rep_arp = dest_dev.lookup_arp(rep_next_hop) if dest_dev else None
            if not rep_arp and dest_dev and reply_port:
                reachable, peer_mac = self._probe_arp_resolution(dest_dev, reply_port, rep_next_hop, vlan_id=reply_vlan)
                if reachable:
                    dest_dev.add_arp_entry(rep_next_hop, peer_mac, reply_port.name)
                    rep_arp = dest_dev.lookup_arp(rep_next_hop)

            rep_src_mac = getattr(reply_port, "mac_address", "02:00:1a:00:00:01") if reply_port else None
            if isinstance(dest_dev, Switch) and reply_svi:
                rep_src_mac = reply_svi.mac_address
            rep_dst_mac = rep_arp["mac"] if rep_arp else "FF:FF:FF:FF:FF:FF"

            rep_is_sub = hasattr(reply_if, "parent_port")
            rep_tagged = rep_is_sub or (getattr(reply_port, "mode", None) == "trunk" and reply_vlan != getattr(reply_port, "native_vlan", 1))
            reply_ok = self._trace_packet(dest_dev, reply_port, dest_target_ip,
                                         getattr(reply_port, "subnet_mask", "255.255.255.0"),
                                         dest_reply_to_ip, rep_visited, rep_hops,
                                         current_vlan=reply_vlan,
                                         ttl=15, trace_context=rep_context,
                                         src_mac=rep_src_mac, dst_mac=rep_dst_mac, is_reply=True,
                                         is_tagged=rep_tagged)

            if not reply_ok:
                if rep_context.get("firewall_deny") or rep_context.get("acl_deny"):
                    step["status_code"] = "A"
                elif rep_context.get("unrouted") or rep_context.get("interface_down"):
                    step["status_code"] = "U"
                else:
                    step["status_code"] = rep_context.get("drop_code", ".")
                step["drop_reason"] = rep_context.get("drop_reason", "Echo Reply lost in transit")
                step["error_message"] = step["drop_reason"]
                return step

        # Both Request and Reply succeeded
        step["status_code"] = "!"
        step["success"] = True

        # Calculate realistic RTT
        base_lat = 0.35 + (len(traversed_hops) - 1) * 0.45
        if target_ip in PUBLIC_INTERNET_IPS or "Public-Internet" in "".join(traversed_hops):
            base_lat += 12.0 + random.uniform(1.0, 4.5)

        jitter = random.uniform(-0.05, 0.15)
        step["rtt_ms"] = round(max(0.1, base_lat + jitter), 2 if base_lat < 1.0 else 1)

        # Calculate TTL decremented across router hops
        l3_hops = rep_context.get("l3_hops", 0) if dest_dev else req_context.get("l3_hops", 0)
        start_ttl = 255 if isinstance(dest_dev, (Router, Firewall)) else 64
        if target_ip in PUBLIC_INTERNET_IPS:
            step["ttl"] = max(1, 128 - 12 - l3_hops)
        else:
            step["ttl"] = max(1, start_ttl - l3_hops)
        step["l3_hops"] = l3_hops

        return step

    def _probe_arp_resolution(self, source_dev, out_port, target_ip, vlan_id=None):
        """Probes whether target_ip is reachable over the broadcast domain with VLAN isolation and returns its MAC."""
        from .switch import SVI, Switch

        in_vlan = vlan_id
        if in_vlan is None:
            if isinstance(source_dev, Switch) and hasattr(source_dev, "svis"):
                for s in source_dev.svis.values():
                    if s.is_link_up and s.ip_address and s.subnet_mask:
                        if is_ip_in_subnet(target_ip, s.ip_address, s.subnet_mask):
                            in_vlan = s.vlan_id
                            break
            if in_vlan is None:
                in_vlan = getattr(out_port, "vlan_id", None) or getattr(out_port, "access_vlan", 1)

        if isinstance(out_port, SVI) or (isinstance(source_dev, Switch) and not getattr(out_port, "cable", None)):
            peer_dev = source_dev
            peer_port = None
        else:
            phys_port = getattr(out_port, "parent_port", out_port)
            if not phys_port or not phys_port.is_link_up or not phys_port.cable:
                return False, None

            peer_port = phys_port.cable.get_peer_port(phys_port)
            if not peer_port or peer_port.is_shutdown:
                return False, None

            # Check peer device directly
            peer_dev = peer_port.device
            if hasattr(peer_dev, "ports"):
                for p in peer_dev.ports.values():
                    if p.ip_address == target_ip:
                        return True, getattr(p, "mac_address", "02:00:1a:00:00:01")
            if isinstance(peer_dev, Host) and peer_dev.eth0 and peer_dev.eth0.ip_address == target_ip:
                return True, peer_dev.eth0.mac_address

        # Check through Switch - ENFORCE VLAN ISOLATION & STP BLOCKING across multi-switch trunks
        if isinstance(peer_dev, Switch):
            # BFS queue: (current_switch, ingress_port, current_vlan)
            queue = [(peer_dev, peer_port, in_vlan)]
            visited_switches = {peer_dev}

            while queue:
                curr_sw, ingress_port, curr_vlan = queue.pop(0)

                if curr_sw.stp_enabled:
                    if getattr(curr_sw, "_stp_dirty", True) or curr_sw.root_bridge_id is None:
                        curr_sw.recalculate_stp()
                    if ingress_port and getattr(ingress_port, "stp_state", "Forwarding") == "Blocking":
                        continue

                # Determine effective VLAN on ingress_port
                effective_vlan = curr_vlan
                if ingress_port:
                    if ingress_port.mode == "access":
                        effective_vlan = ingress_port.access_vlan
                    elif ingress_port.mode == "trunk":
                        if effective_vlan not in ingress_port.trunk_allowed_vlans:
                            continue

                # Check if current switch owns target_ip on SVI for effective_vlan
                if hasattr(curr_sw, "svis"):
                    svi = curr_sw.svis.get(effective_vlan)
                    if svi and svi.ip_address == target_ip and svi.is_link_up:
                        return True, svi.mac_address

                # Inspect all other ports on current switch
                for p in curr_sw.ports.values():
                    if p == ingress_port or not p.cable or p.is_shutdown:
                        continue
                    if curr_sw.stp_enabled and getattr(p, "stp_state", "Forwarding") == "Blocking":
                        continue

                    # Check VLAN membership on egress port p
                    if p.mode == "access":
                        if p.access_vlan != effective_vlan:
                            continue
                        next_vlan = p.access_vlan
                    elif p.mode == "trunk":
                        if effective_vlan not in p.trunk_allowed_vlans:
                            continue
                        next_vlan = effective_vlan
                    else:
                        continue

                    remote_port = p.cable.get_peer_port(p)
                    if not remote_port or remote_port.is_shutdown:
                        continue

                    r_dev = remote_port.device
                    if isinstance(r_dev, Switch):
                        if r_dev.stp_enabled and getattr(remote_port, "stp_state", "Forwarding") == "Blocking":
                            continue
                        if remote_port.mode == "access" and remote_port.access_vlan != next_vlan:
                            continue
                        if remote_port.mode == "trunk" and next_vlan not in remote_port.trunk_allowed_vlans:
                            continue
                        if r_dev not in visited_switches:
                            visited_switches.add(r_dev)
                            queue.append((r_dev, remote_port, next_vlan))
                        continue

                    # Endpoint devices (Host, Router, Firewall)
                    if isinstance(r_dev, Host) and r_dev.eth0 and r_dev.eth0.ip_address == target_ip:
                        return True, r_dev.eth0.mac_address
                    if hasattr(r_dev, "ports"):
                        for rp in r_dev.ports.values():
                            if rp.ip_address == target_ip:
                                return True, getattr(rp, "mac_address", "02:00:1a:00:00:01")
                    if hasattr(r_dev, "subinterfaces"):
                        for sub in r_dev.subinterfaces.values():
                            if sub.ip_address == target_ip:
                                if sub.vlan_id is None or sub.vlan_id == next_vlan:
                                    parent = getattr(sub, "parent_port", sub)
                                    return True, getattr(parent, "mac_address", "02:00:1a:00:00:01")
                    if hasattr(r_dev, "svis"):
                        r_svi = r_dev.svis.get(next_vlan)
                        if r_svi and r_svi.ip_address == target_ip and r_svi.is_link_up:
                            return True, r_svi.mac_address

        return False, None

    def _find_source_ip_context(self, dev, target_ip=None, preferred_interface=None):
        """Finds active egress interface, IP and subnet mask for source device."""
        if isinstance(dev, Host):
            p = dev.eth0
            if p and p.is_link_up and p.ip_address:
                return p, p.ip_address, p.subnet_mask
            return None, None, None

        # If user specified source interface (e.g. 'source g0/1')
        if preferred_interface:
            p = dev.get_port(preferred_interface) if hasattr(dev, "get_port") else None
            if p and p.is_link_up and p.ip_address:
                return p, p.ip_address, p.subnet_mask
            if hasattr(dev, "get_interface"):
                sub = dev.get_interface(preferred_interface)
                if sub and sub.is_link_up and sub.ip_address:
                    from .switch import SVI
                    if isinstance(sub, SVI):
                        phys = dev.get_first_active_port_for_vlan(sub.vlan_id) if hasattr(dev, "get_first_active_port_for_vlan") else None
                        return phys or sub, sub.ip_address, sub.subnet_mask
                    return sub, sub.ip_address, sub.subnet_mask

        # For Routers / Firewalls: choose interface based on routing table or destination subnet
        if isinstance(dev, (Router, Firewall)) and target_ip:
            # 1. Check if directly connected on any interface
            for p in dev.ports.values():
                if p.is_link_up and p.ip_address and p.subnet_mask:
                    if is_ip_in_subnet(target_ip, p.ip_address, p.subnet_mask):
                        return p, p.ip_address, p.subnet_mask
            if hasattr(dev, "subinterfaces"):
                for sub in dev.subinterfaces.values():
                    if sub.is_link_up and sub.ip_address and sub.subnet_mask:
                        if is_ip_in_subnet(target_ip, sub.ip_address, sub.subnet_mask):
                            return sub, sub.ip_address, sub.subnet_mask

            # 2. Check routing table
            route = dev.lookup_route(target_ip)
            if route:
                target_if = route.get("interface")
                if not target_if and route.get("next_hop") and route["next_hop"] != "directly connected":
                    nh_route = dev.lookup_route(route["next_hop"])
                    if nh_route and nh_route.get("interface"):
                        target_if = nh_route["interface"]
                    else:
                        for p in dev.ports.values():
                            if p.is_link_up and p.ip_address and p.subnet_mask:
                                if is_ip_in_subnet(route["next_hop"], p.ip_address, p.subnet_mask):
                                    target_if = p.name
                                    break
                        if not target_if and hasattr(dev, "subinterfaces"):
                            for sub in dev.subinterfaces.values():
                                if sub.is_link_up and sub.ip_address and sub.subnet_mask:
                                    if is_ip_in_subnet(route["next_hop"], sub.ip_address, sub.subnet_mask):
                                        target_if = sub.name
                                        break
                if target_if:
                    p = dev.get_port(target_if)
                    if p and p.is_link_up and p.ip_address:
                        return p, p.ip_address, p.subnet_mask
                    if hasattr(dev, "get_interface"):
                        sub = dev.get_interface(target_if)
                        if sub and sub.is_link_up and sub.ip_address:
                            return sub, sub.ip_address, sub.subnet_mask

        # For Switches: select active SVI based on destination subnet or default gateway
        if isinstance(dev, Switch):
            svi = None
            if preferred_interface:
                clean = preferred_interface.strip().lower()
                if clean.startswith("vlan"):
                    vid_str = clean[4:].strip()
                    if vid_str.isdigit():
                        svi = dev.get_svi(int(vid_str))
                if not svi and hasattr(dev, "get_interface"):
                    cand = dev.get_interface(preferred_interface)
                    if isinstance(cand, SVI):
                        svi = cand

            if not svi and target_ip:
                for s in dev.svis.values():
                    if s.is_link_up and s.ip_address and s.subnet_mask:
                        if is_ip_in_subnet(target_ip, s.ip_address, s.subnet_mask):
                            svi = s
                            break
                if not svi and getattr(dev, "default_gateway", None):
                    for s in dev.svis.values():
                        if s.is_link_up and s.ip_address and s.subnet_mask:
                            if is_ip_in_subnet(dev.default_gateway, s.ip_address, s.subnet_mask):
                                svi = s
                                break

            if not svi:
                for s in dev.svis.values():
                    if s.is_link_up and s.ip_address and s.subnet_mask:
                        svi = s
                        break

            if svi and svi.is_link_up and svi.ip_address:
                phys = dev.get_first_active_port_for_vlan(svi.vlan_id)
                if phys:
                    return phys, svi.ip_address, svi.subnet_mask
                return svi, svi.ip_address, svi.subnet_mask

        # Fallback: find first active port with IP
        if hasattr(dev, "ports"):
            for p in dev.ports.values():
                if p.is_link_up and p.ip_address:
                    return p, p.ip_address, p.subnet_mask
        if hasattr(dev, "subinterfaces"):
            for sub in dev.subinterfaces.values():
                if sub.is_link_up and sub.ip_address:
                    return sub, sub.ip_address, sub.subnet_mask
        if hasattr(dev, "svis"):
            for s in dev.svis.values():
                if s.is_link_up and s.ip_address:
                    phys = dev.get_first_active_port_for_vlan(s.vlan_id) if hasattr(dev, "get_first_active_port_for_vlan") else None
                    return phys or s, s.ip_address, s.subnet_mask

        return None, None, None

    def _trace_packet(self, current_dev, out_port, current_ip, current_mask,
                      target_ip, visited, hop_path, current_vlan=1, ttl=15,
                      trace_context=None, src_mac=None, dst_mac=None, is_reply=False, is_tagged=False):
        if trace_context is None:
            trace_context = {}

        # 0. TTL & Loop Prevention
        if ttl <= 0:
            trace_context["drop_reason"] = "TTL expired in transit"
            trace_context["drop_code"] = "U"
            return False
        visit_key = (current_dev.id, current_vlan)
        if visit_key in visited:
            trace_context["drop_reason"] = "Routing loop detected"
            trace_context["drop_code"] = "U"
            return False
        visited.add(visit_key)

        # 1. Trigger physical LED activity on out_port
        if not out_port or not out_port.is_link_up:
            trace_context["drop_reason"] = f"Interface {out_port.name if out_port else 'unknown'} is down or disconnected"
            trace_context["drop_code"] = "U"
            trace_context["interface_down"] = True
            return False
        if isinstance(current_dev, Switch) and getattr(current_dev, "stp_enabled", False):
            if getattr(out_port, "stp_state", "Forwarding") == "Blocking":
                trace_context["drop_reason"] = f"Port {out_port.name} on {current_dev.hostname} is in STP Blocking state"
                trace_context["drop_code"] = "."
                return False
        if hasattr(out_port, "trigger_traffic"):
            out_port.trigger_traffic()

        # 2. Check physical cable link
        cable = out_port.cable
        if not cable or cable.is_damaged:
            trace_context["drop_reason"] = "Cable disconnected or damaged"
            trace_context["drop_code"] = "U"
            return False

        # 3. Arrive at peer port
        peer_port = cable.get_peer_port(out_port)
        if not peer_port or peer_port.is_shutdown:
            trace_context["drop_reason"] = f"Peer interface {peer_port.name if peer_port else 'unknown'} is administratively down"
            trace_context["drop_code"] = "U"
            trace_context["interface_down"] = True
            return False
        peer_port.trigger_traffic()
        next_dev = peer_port.device
        hop_path.append(next_dev.hostname)

        # Ingress frame processing on Switch
        in_vlan = current_vlan
        if isinstance(next_dev, Switch):
            if getattr(next_dev, "stp_enabled", False):
                if getattr(peer_port, "stp_state", "Forwarding") == "Blocking":
                    trace_context["drop_reason"] = f"Port {peer_port.name} on {next_dev.hostname} is in STP Blocking state"
                    trace_context["drop_code"] = "."
                    return False
            if peer_port.mode == "access":
                if is_tagged:
                    trace_context["drop_reason"] = f"Access port {peer_port.name} on {next_dev.hostname} dropped tagged frame (VLAN {current_vlan})"
                    trace_context["drop_code"] = "."
                    return False
                in_vlan = peer_port.access_vlan
            elif peer_port.mode == "trunk":
                if is_tagged:
                    if current_vlan not in peer_port.trunk_allowed_vlans:
                        trace_context["drop_reason"] = f"Trunk port {peer_port.name} on {next_dev.hostname} dropped disallowed VLAN {current_vlan}"
                        trace_context["drop_code"] = "."
                        return False
                    in_vlan = current_vlan
                else:
                    # Untagged frame arriving on trunk port
                    if getattr(out_port, "mode", None) == "trunk":
                        if getattr(out_port, "native_vlan", 1) != getattr(peer_port, "native_vlan", 1):
                            trace_context["drop_reason"] = f"% Native VLAN mismatch detected: local {peer_port.native_vlan} vs remote {out_port.native_vlan}"
                            trace_context["drop_code"] = "."
                            return False
                    in_vlan = getattr(peer_port, "native_vlan", 1)
                    if in_vlan not in peer_port.trunk_allowed_vlans:
                        trace_context["drop_reason"] = f"Trunk port {peer_port.name} on {next_dev.hostname} native VLAN {in_vlan} is not allowed"
                        trace_context["drop_code"] = "."
                        return False

        # 4. Handle destination matches on next_dev
        if self._is_device_ip(next_dev, target_ip, peer_port, in_vlan):
            trace_context["destination_device"] = next_dev
            trace_context["destination_port"] = peer_port
            trace_context["final_src_ip"] = current_ip
            trace_context["final_dst_ip"] = target_ip
            trace_context["final_vlan"] = in_vlan
            return True

        # 5. Layer 2 Switching logic (MAC Learning & Forwarding)
        if isinstance(next_dev, Switch):
            active_src_mac = src_mac or getattr(out_port, "mac_address", "02:00:1a:00:00:01")
            active_dst_mac = dst_mac or "FF:FF:FF:FF:FF:FF"

            out_ports = next_dev.forward_packet(peer_port, active_src_mac, active_dst_mac, in_vlan)
            if not out_ports:
                trace_context["drop_reason"] = "Switch dropped frame (VLAN mismatch, blocked, or port down)"
                trace_context["drop_code"] = "."
                return False

            for cand_port in out_ports:
                if cand_port.cable and cand_port.cable.get_peer_port(cand_port) != out_port:
                    if cand_port.mode == "access":
                        cand_vlan = cand_port.access_vlan
                        cand_tagged = False
                    elif cand_port.mode == "trunk":
                        cand_vlan = in_vlan
                        if in_vlan == getattr(cand_port, "native_vlan", 1):
                            cand_tagged = False
                        else:
                            cand_tagged = True
                    else:
                        cand_vlan = in_vlan
                        cand_tagged = False

                    if self._trace_packet(next_dev, cand_port, current_ip, current_mask,
                                          target_ip, visited.copy(), hop_path, current_vlan=cand_vlan,
                                          ttl=ttl-1, trace_context=trace_context,
                                          src_mac=active_src_mac, dst_mac=active_dst_mac,
                                          is_reply=is_reply, is_tagged=cand_tagged):
                        return True
            return False

        # 6. Layer 3/4 Stateful Firewall Inspection logic
        if isinstance(next_dev, Firewall):
            permitted, reason = next_dev.inspect_packet(peer_port, target_ip, current_ip, protocol="icmp", is_reply=is_reply)
            if not permitted:
                trace_context["firewall_deny"] = True
                trace_context["drop_reason"] = reason
                trace_context["drop_code"] = "A"
                return False

            route = next_dev.lookup_route(target_ip)
            egress_port = None
            if route and route.get("interface"):
                egress_port = next_dev.get_port(route["interface"])
            if not egress_port and route and route.get("next_hop"):
                hop_route = next_dev.lookup_route(route["next_hop"])
                if hop_route and hop_route.get("interface"):
                    egress_port = next_dev.get_port(hop_route["interface"])
            if not egress_port:
                for p in next_dev.ports.values():
                    if p != peer_port and p.is_link_up and p.ip_address and p.subnet_mask:
                        if is_ip_in_subnet(target_ip, p.ip_address, p.subnet_mask):
                            egress_port = p
                            break

            if egress_port and egress_port.is_link_up:
                egress_mac = getattr(egress_port, "mac_address", "02:00:1a:00:00:01")
                trace_context["l3_hops"] = trace_context.get("l3_hops", 0) + 1
                return self._trace_packet(next_dev, egress_port, current_ip,
                                          getattr(egress_port, "subnet_mask", current_mask), target_ip,
                                          visited, hop_path, current_vlan=1, ttl=ttl-1,
                                          trace_context=trace_context, src_mac=egress_mac, dst_mac=None,
                                          is_reply=is_reply)
            trace_context["unrouted"] = True
            trace_context["drop_reason"] = f"No route to destination {target_ip} on firewall {next_dev.hostname}"
            trace_context["drop_code"] = "U"
            return False

        # 7. Layer 3 Routing & Cisco NAT logic
        if isinstance(next_dev, Router):
            # Ingress ACL check
            in_acl = next_dev.access_groups.get(peer_port.name.lower(), {}).get("in")
            if in_acl:
                perm, acl_msg = next_dev.check_acl(in_acl, current_ip)
                if not perm:
                    trace_context["acl_deny"] = True
                    trace_context["drop_reason"] = acl_msg
                    trace_context["drop_code"] = "A"
                    return False

            # Reverse NAT check (Outside -> Inside)
            rev_ip, rev_tr = next_dev.perform_reverse_nat(target_ip, peer_port.name, protocol="icmp")
            effective_target_ip = rev_ip if rev_ip else target_ip

            # Destination check after Reverse NAT
            if rev_ip and self._is_device_ip(next_dev, rev_ip, peer_port, current_vlan):
                trace_context["destination_device"] = next_dev
                trace_context["destination_port"] = peer_port
                trace_context["final_src_ip"] = current_ip
                trace_context["final_dst_ip"] = effective_target_ip
                return True

            # Route lookup
            route = next_dev.lookup_route(effective_target_ip)
            if not route:
                trace_context["unrouted"] = True
                trace_context["drop_reason"] = f"No route to destination {effective_target_ip} on {next_dev.hostname}"
                trace_context["drop_code"] = "U"
                return False

            egress_name = route.get("interface")
            next_hop = route.get("next_hop")
            if not egress_name and next_hop and next_hop != "directly connected":
                hop_route = next_dev.lookup_route(next_hop)
                if hop_route:
                    egress_name = hop_route.get("interface")

            if not egress_name:
                trace_context["unrouted"] = True
                trace_context["drop_reason"] = f"Unreachable next-hop {next_hop} on {next_dev.hostname}"
                trace_context["drop_code"] = "U"
                return False

            egress_if = next_dev.get_interface(egress_name)
            if not egress_if or not egress_if.is_link_up:
                trace_context["interface_down"] = True
                trace_context["drop_reason"] = f"Exit interface {egress_name} on {next_dev.hostname} is down"
                trace_context["drop_code"] = "U"
                return False

            # Egress ACL check
            out_acl = next_dev.access_groups.get(egress_if.name.lower(), {}).get("out")
            if out_acl:
                perm, acl_msg = next_dev.check_acl(out_acl, current_ip)
                if not perm:
                    trace_context["acl_deny"] = True
                    trace_context["drop_reason"] = acl_msg
                    trace_context["drop_code"] = "A"
                    return False

            physical_port = egress_if if not hasattr(egress_if, "parent_port") else egress_if.parent_port
            vlan_tag = getattr(egress_if, "vlan_id", 1) or 1

            # Forward NAT Translation (Inside -> Outside)
            translated_ip, nat_entry = next_dev.perform_nat(current_ip, peer_port.name, physical_port.name, protocol="icmp")
            active_src_ip = translated_ip if translated_ip else current_ip

            # Public Internet IP check
            if effective_target_ip in PUBLIC_INTERNET_IPS:
                if is_private_ip(current_ip) and not translated_ip:
                    trace_context["unrouted"] = True
                    trace_context["drop_reason"] = f"Private IP {current_ip} cannot route to public internet without NAT"
                    trace_context["drop_code"] = "U"
                    return False

                peer_on_egress = physical_port.cable.get_peer_port(physical_port) if physical_port.cable else None
                if peer_on_egress and not peer_on_egress.is_shutdown:
                    peer_dev = peer_on_egress.device
                    if any(k in peer_dev.hostname.lower() for k in ("isp", "internet", "cloud", "wan")):
                        trace_context["l3_hops"] = trace_context.get("l3_hops", 0) + 1
                        hop_path.append(peer_dev.hostname)
                        hop_path.append(f"Public-Internet [{effective_target_ip}]")
                        return True

            # Resolve next-hop MAC via ARP
            if not next_hop or next_hop == "directly connected":
                egress_next_hop = effective_target_ip
            else:
                egress_next_hop = next_hop

            arp_entry = next_dev.lookup_arp(egress_next_hop)
            if not arp_entry:
                reachable, peer_mac = self._probe_arp_resolution(next_dev, physical_port, egress_next_hop, vlan_id=vlan_tag)
                if reachable:
                    next_dev.add_arp_entry(egress_next_hop, peer_mac, physical_port.name)
                    dst_next_mac = peer_mac
                else:
                    trace_context["arp_failure"] = True
                    trace_context["drop_reason"] = f"ARP resolution failed for {egress_next_hop} on {next_dev.hostname}"
                    trace_context["drop_code"] = "."
                    return False
            else:
                dst_next_mac = arp_entry["mac"]

            router_src_mac = getattr(physical_port, "mac_address", "02:00:1a:00:00:01")
            trace_context["l3_hops"] = trace_context.get("l3_hops", 0) + 1

            is_sub = hasattr(egress_if, "parent_port")
            return self._trace_packet(next_dev, physical_port, active_src_ip,
                                     getattr(egress_if, "subnet_mask", current_mask), effective_target_ip,
                                     visited, hop_path, current_vlan=vlan_tag, ttl=ttl-1,
                                     trace_context=trace_context, src_mac=router_src_mac, dst_mac=dst_next_mac,
                                     is_reply=is_reply, is_tagged=is_sub)

        return False

    def _is_device_ip(self, dev, target_ip, in_port, vlan_id):
        """Checks if device owns target_ip on the incoming interface/vlan."""
        if target_ip in PUBLIC_INTERNET_IPS:
            if any(k in dev.hostname.lower() for k in ("isp", "internet", "cloud", "wan")):
                return True

        if isinstance(dev, Host):
            p = dev.eth0
            return p and p.ip_address == target_ip
        elif isinstance(dev, Switch):
            effective_vlan = vlan_id
            if in_port and getattr(in_port, "mode", None) == "access":
                effective_vlan = in_port.access_vlan
            if hasattr(dev, "svis"):
                svi = dev.svis.get(effective_vlan)
                if svi and svi.ip_address == target_ip and svi.is_link_up:
                    return True
            return False
        elif isinstance(dev, Router):
            for p in dev.ports.values():
                if p.ip_address == target_ip:
                    return True
            for sub in dev.subinterfaces.values():
                if sub.ip_address == target_ip and (sub.vlan_id is None or sub.vlan_id == vlan_id):
                    return True
        elif isinstance(dev, Firewall):
            for p in dev.ports.values():
                if p.ip_address == target_ip:
                    return True
        return False

    def converge_rip(self, max_rounds=6):
        from .rip import converge_all_rip
        converge_all_rip(max_rounds=max_rounds)

    def converge_ospf(self, max_rounds=10):
        from .ospf import converge_all_ospf
        converge_all_ospf(max_rounds=max_rounds)

    def simulate_traceroute(self, source_device, target_ip, max_hops=30, source_interface=None):
        """
        Simulates hop-by-hop traceroute to target_ip.
        Returns a list of dicts: [{'hop': 1, 'ip': '...', 'name': '...', 'rtts': [1.2, 1.1, 1.4]}, ...]
        """
        from .rip import converge_all_rip
        converge_all_rip()
        from .ospf import converge_all_ospf
        converge_all_ospf()

        if self._is_self_ip(source_device, target_ip):
            return [{
                "hop": 1,
                "ip": target_ip,
                "name": source_device.hostname,
                "rtts": [0.1, 0.1, 0.1]
            }]

        hops = []
        src_port, src_ip, src_mask = self._find_source_ip_context(source_device, target_ip, source_interface)
        if not src_ip or not src_port or not src_port.is_link_up:
            return [{"hop": 1, "ip": "*", "name": "Request timed out", "rtts": []}]

        # Probe path
        visited = set()
        traversed = [source_device.hostname]
        trace_context = {}
        success = self._trace_packet(source_device, src_port, src_ip, src_mask,
                                     target_ip, visited, traversed,
                                     current_vlan=getattr(src_port, "vlan_id", getattr(src_port, "access_vlan", 1)) or 1,
                                     trace_context=trace_context)

        # Filter hop devices (exclude layer 2 switches, focus on L3 hops)
        current_lat = 0.8
        hop_num = 1
        for idx, h_name in enumerate(traversed[1:]):
            if any(k in h_name.lower() for k in ("switch",)):
                continue
            rtts = [
                round(current_lat + random.uniform(0.05, 0.25), 2),
                round(current_lat + random.uniform(0.02, 0.20), 2),
                round(current_lat + random.uniform(0.04, 0.28), 2)
            ]
            hops.append({
                "hop": hop_num,
                "ip": target_ip if idx == len(traversed[1:]) - 1 else f"192.168.{hop_num}.1",
                "name": h_name,
                "rtts": rtts
            })
            hop_num += 1
            current_lat += 1.4 if "isp" not in h_name.lower() else 11.5

        if not success:
            hops.append({
                "hop": hop_num,
                "ip": "* * *",
                "name": "Request timed out",
                "rtts": []
            })

        return hops

    def _collect_broadcast_endpoints(self, source_dev, out_port, vlan_id=None):
        """
        Discovers all reachable Layer 3 candidate endpoints (Router interfaces, SVIs, Hosts)
        within the broadcast domain, respecting physical links, access/trunk VLAN memberships,
        and Spanning Tree Protocol (STP) blocking states.
        """
        phys_port = getattr(out_port, "parent_port", out_port)
        if not phys_port or not phys_port.is_link_up or not phys_port.cable:
            return []

        peer_port = phys_port.cable.get_peer_port(phys_port)
        if not peer_port or peer_port.is_shutdown:
            return []

        in_vlan = vlan_id
        if in_vlan is None:
            in_vlan = getattr(out_port, "vlan_id", None) or getattr(out_port, "access_vlan", 1)

        endpoints = []
        peer_dev = peer_port.device

        # Direct connection to Router
        if isinstance(peer_dev, Router):
            matched = False
            if hasattr(peer_dev, "subinterfaces"):
                for sub in peer_dev.subinterfaces.values():
                    if sub.vlan_id == in_vlan or sub.vlan_id is None:
                        endpoints.append((peer_dev, sub, in_vlan))
                        matched = True
            if not matched or peer_port.ip_address:
                endpoints.append((peer_dev, peer_port, in_vlan))
            return endpoints

        # Direct connection to Host
        if isinstance(peer_dev, Host):
            endpoints.append((peer_dev, peer_port, in_vlan))
            return endpoints

        # Connection through Switch
        if isinstance(peer_dev, Switch):
            if peer_dev.stp_enabled:
                if getattr(peer_dev, "_stp_dirty", True) or peer_dev.root_bridge_id is None:
                    peer_dev.recalculate_stp()
                if getattr(peer_port, "stp_state", "Forwarding") == "Blocking":
                    return []

            if peer_port.mode == "access":
                in_vlan = peer_port.access_vlan

            # Check if switch itself has SVI for in_vlan
            if hasattr(peer_dev, "svis") and in_vlan in peer_dev.svis:
                svi = peer_dev.svis[in_vlan]
                if svi.is_link_up:
                    endpoints.append((peer_dev, svi, in_vlan))

            # Traverse Layer 2 switch topology with loop prevention
            visited_switches = {peer_dev}
            queue = [(peer_dev, peer_port, in_vlan)]

            while queue:
                curr_sw, from_port, curr_vlan = queue.pop(0)
                for p in curr_sw.ports.values():
                    if p == from_port or p.is_shutdown or not p.cable:
                        continue
                    if curr_sw.stp_enabled and getattr(p, "stp_state", "Forwarding") == "Blocking":
                        continue
                    if p.mode == "access" and p.access_vlan != curr_vlan:
                        continue
                    if p.mode == "trunk" and p.trunk_allowed_vlans and curr_vlan not in p.trunk_allowed_vlans:
                        continue

                    r_port = p.cable.get_peer_port(p)
                    if not r_port or r_port.is_shutdown:
                        continue
                    r_dev = r_port.device

                    if isinstance(r_dev, Switch):
                        if r_dev.stp_enabled and getattr(r_port, "stp_state", "Forwarding") == "Blocking":
                            continue
                        if r_port.mode == "trunk" and curr_vlan not in r_port.trunk_allowed_vlans:
                            continue
                        if r_port.mode == "access" and r_port.access_vlan != curr_vlan:
                            continue
                        if r_dev not in visited_switches:
                            visited_switches.add(r_dev)
                            if hasattr(r_dev, "svis") and curr_vlan in r_dev.svis:
                                r_svi = r_dev.svis[curr_vlan]
                                if r_svi.is_link_up:
                                    endpoints.append((r_dev, r_svi, curr_vlan))
                            queue.append((r_dev, r_port, curr_vlan))

                    elif isinstance(r_dev, Router):
                        matched = False
                        if hasattr(r_dev, "subinterfaces"):
                            for sub in r_dev.subinterfaces.values():
                                if sub.vlan_id == curr_vlan:
                                    endpoints.append((r_dev, sub, curr_vlan))
                                    matched = True
                        if not matched or r_port.ip_address:
                            endpoints.append((r_dev, r_port, curr_vlan))

                    elif isinstance(r_dev, Host):
                        endpoints.append((r_dev, r_port, curr_vlan))

        return endpoints

    def simulate_dhcp_dora(self, client_dev, client_port):
        """
        Executes complete DHCP DORA handshake from client_port across the network topology.
        Returns (success: bool, result_msg_or_error: DHCPMessage or str).
        """
        if not client_port or not client_port.is_link_up or not client_port.cable:
            return False, "Interface is down or disconnected"

        vlan_id = getattr(client_port, "vlan_id", None) or getattr(client_port, "access_vlan", 1)
        endpoints = self._collect_broadcast_endpoints(client_dev, client_port, vlan_id=vlan_id)

        # Look for reachable DHCP Server with matching pool
        server_match = None
        server_iface = None
        server_vlan = vlan_id

        for dev, iface, ep_vlan in endpoints:
            if hasattr(dev, "dhcp_server") and dev.dhcp_server and dev.dhcp_server.pools:
                pool = dev.dhcp_server.find_pool_for_context(in_vlan=ep_vlan, in_ip=getattr(iface, "ip_address", None))
                if pool:
                    server_match = dev.dhcp_server
                    server_iface = iface
                    server_vlan = ep_vlan
                    break

        if not server_match:
            return False, "DHCPDISCOVER timeout: No DHCP server found in broadcast domain"

        # 1. DHCPDISCOVER
        client_port.trigger_traffic()
        server_ip = getattr(server_iface, "ip_address", None)
        xid = getattr(getattr(client_dev, "dhcp_client", None), "current_xid", 1001)
        if hasattr(client_dev, "dhcp_client") and client_dev.dhcp_client:
            client_dev.dhcp_client.current_xid += 1
            client_dev.dhcp_client.state = DHCPClientState.SELECTING

        discover_msg = DHCPMessage(
            msg_type=DHCPMessageType.DISCOVER,
            xid=xid,
            client_mac=getattr(client_port, "mac_address", "02:00:1a:00:00:01"),
            hostname=client_dev.hostname,
            vlan_id=server_vlan
        )

        offer_msg = server_match.handle_discover(
            discover_msg,
            in_vlan=server_vlan,
            in_ip=server_ip,
            server_ip=server_ip
        )

        if not offer_msg:
            return False, "DHCPOFFER failed: DHCP pool exhausted or unavailable"

        # 2. DHCPREQUEST
        if hasattr(client_dev, "dhcp_client") and client_dev.dhcp_client:
            client_dev.dhcp_client.state = DHCPClientState.REQUESTING

        request_msg = DHCPMessage(
            msg_type=DHCPMessageType.REQUEST,
            xid=offer_msg.xid,
            client_mac=client_port.mac_address,
            yiaddr=offer_msg.yiaddr,
            server_id=offer_msg.server_id,
            hostname=client_dev.hostname,
            vlan_id=server_vlan
        )

        ack_msg = server_match.handle_request(
            request_msg,
            in_vlan=server_vlan,
            in_ip=server_ip,
            server_ip=server_ip
        )

        if not ack_msg or ack_msg.msg_type == DHCPMessageType.NAK:
            if hasattr(client_dev, "dhcp_client") and client_dev.dhcp_client:
                client_dev.dhcp_client.state = DHCPClientState.INIT
            return False, "DHCPNAK received: Request rejected by DHCP server"

        # 3. DHCPACK: Configure client
        client_port.ip_address = ack_msg.yiaddr
        client_port.subnet_mask = ack_msg.subnet_mask
        if ack_msg.router:
            client_dev.default_gateway = ack_msg.router
        if ack_msg.dns_server:
            client_dev.dns_server = ack_msg.dns_server
        client_dev.dhcp_enabled = True

        if hasattr(client_dev, "dhcp_client") and client_dev.dhcp_client:
            client_dev.dhcp_client.state = DHCPClientState.BOUND
            client_dev.dhcp_client.lease = server_match.binding_table.get(ack_msg.yiaddr)
            client_dev.dhcp_lease = client_dev.dhcp_client.lease

        return True, ack_msg

    def simulate_dhcp_release(self, client_dev, client_port):
        """
        Transmits DHCPRELEASE and clears client IP configuration.
        """
        if not client_port or not client_port.ip_address:
            return False, "Interface has no assigned IP"

        vlan_id = getattr(client_port, "vlan_id", None) or getattr(client_port, "access_vlan", 1)
        endpoints = self._collect_broadcast_endpoints(client_dev, client_port, vlan_id=vlan_id)

        current_ip = client_port.ip_address
        current_mac = getattr(client_port, "mac_address", "")

        rel_msg = DHCPMessage(
            msg_type=DHCPMessageType.RELEASE,
            client_mac=current_mac,
            ciaddr=current_ip,
            hostname=client_dev.hostname,
            vlan_id=vlan_id
        )

        released = False
        for dev, iface, ep_vlan in endpoints:
            if hasattr(dev, "dhcp_server") and dev.dhcp_server:
                if dev.dhcp_server.handle_release(rel_msg):
                    released = True
                    break

        client_port.ip_address = None
        client_port.subnet_mask = None
        client_dev.default_gateway = None
        client_dev.dhcp_enabled = False
        if hasattr(client_dev, "dhcp_client") and client_dev.dhcp_client:
            client_dev.dhcp_client.state = DHCPClientState.INIT
            client_dev.dhcp_client.lease = None
            client_dev.dhcp_lease = None

        return True, "DHCP lease released"

