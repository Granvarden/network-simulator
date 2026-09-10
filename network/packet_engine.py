"""
network/packet_engine.py - Realistic Hop-by-Hop Network Simulation & ICMP Engine
Simulates packet transmission through cables, switches (VLANs), and routers (Routing Tables).
Supports Cisco status codes (!, ., U, A), cold ARP cache drops (.!!!!), latency jitter,
TTL decrements, and step-by-step real-time execution.
"""

import time
import random
from .router import is_ip_in_subnet, ip_to_int, Router
from .switch import Switch
from .host import Host
from .firewall import Firewall
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
        return False

    def simulate_ping(self, source_device, target_ip, count=5, timeout=2, data_bytes=100,
                      source_interface=None, simulate_arp=False):
        """
        Executes complete ICMP ping from source_device to target_ip across the network topology.
        simulate_arp: If True, first packet on cold ARP cache drops with '.' and resolves ARP.
                      Default False preserves 100% backward compatibility with automated tests.
        """
        result = PingResult(target_ip, packets_sent=count, timeout_sec=timeout, data_bytes=data_bytes)

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
        Traces a single ICMP Echo packet from source_device to target_ip.
        Returns a dictionary containing status_code, success, rtt_ms, ttl, hop_path, and error.
        Used for real-time progressive terminal output and audio feedback.
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

        # Validate source
        src_port, src_ip, src_mask = self._find_source_ip_context(source_device, target_ip, source_interface)
        if not src_ip or not src_port or not src_port.is_link_up:
            step["status_code"] = "U"
            step["error_message"] = "% Interface is down or unconfigured"
            return step

        # Determine next-hop IP for ARP resolution
        next_hop_ip = target_ip
        if not is_ip_in_subnet(target_ip, src_ip, src_mask):
            if isinstance(source_device, (Router, Firewall)):
                route = source_device.lookup_route(target_ip)
                if not route:
                    step["status_code"] = "U"
                    step["error_message"] = "% Destination network unreachable"
                    return step
                if route.get("next_hop"):
                    next_hop_ip = route["next_hop"]
            elif isinstance(source_device, Host):
                if source_device.default_gateway:
                    next_hop_ip = source_device.default_gateway
                else:
                    step["status_code"] = "U"
                    step["error_message"] = "From " + source_device.hostname + ": Destination Host Unreachable"
                    return step

        # ARP Simulation
        if simulate_arp:
            arp_entry = source_device.lookup_arp(next_hop_ip)
            if not arp_entry:
                # Cold cache: probe if next hop is reachable
                reachable, peer_mac = self._probe_arp_resolution(source_device, src_port, next_hop_ip)
                if reachable:
                    # Learn ARP for subsequent packets
                    source_device.add_arp_entry(next_hop_ip, peer_mac, src_port.name)
                    # First packet drops while waiting for ARP reply
                    if pkt_index == 0:
                        step["status_code"] = "."
                        step["drop_reason"] = "ARP resolution timeout"
                        return step
                else:
                    step["status_code"] = "."
                    step["drop_reason"] = "ARP request failed"
                    return step

        # Trace packet through network hops
        visited = set()
        traversed_hops = [source_device.hostname]
        trace_context = {"drop_code": ".", "firewall_deny": False, "unrouted": False}

        success = self._trace_packet(source_device, src_port, src_ip, src_mask,
                                     target_ip, visited, traversed_hops,
                                     current_vlan=src_port.access_vlan,
                                     trace_context=trace_context)

        step["hop_path"] = traversed_hops

        if success:
            step["status_code"] = "!"
            step["success"] = True

            # Calculate realistic RTT based on number and type of traversed hops
            base_lat = 0.35 + (len(traversed_hops) - 1) * 0.45
            if target_ip in PUBLIC_INTERNET_IPS or "Public-Internet" in "".join(traversed_hops):
                base_lat += 12.0 + random.uniform(1.0, 4.5)

            jitter = random.uniform(-0.1, 0.25)
            step["rtt_ms"] = round(max(0.1, base_lat + jitter), 2 if base_lat < 1.0 else 1)

            # Calculate TTL: starting TTL minus Layer 3 hops
            l3_hops = sum(1 for h in traversed_hops if any(k in h.lower() for k in ("router", "firewall", "gateway", "asa")))
            start_ttl = 64 if isinstance(source_device, Host) else 255
            if target_ip in PUBLIC_INTERNET_IPS:
                step["ttl"] = max(1, 128 - 12 - l3_hops)
            else:
                step["ttl"] = max(1, start_ttl - l3_hops)
        else:
            if trace_context.get("firewall_deny"):
                step["status_code"] = "A"  # Administratively prohibited by ACL
                step["drop_reason"] = "Packet dropped by access-list or firewall inspection"
            elif trace_context.get("unrouted"):
                step["status_code"] = "U"  # Destination unreachable
                step["drop_reason"] = "No route to destination"
            else:
                step["status_code"] = "."  # Timeout
                step["drop_reason"] = "Request timed out"

        return step

    def _probe_arp_resolution(self, source_dev, out_port, target_ip):
        """Probes whether target_ip is reachable over the broadcast domain and returns its MAC."""
        if not out_port or not out_port.is_link_up or not out_port.cable:
            return False, None

        peer_port = out_port.cable.get_peer_port(out_port)
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

        # Check through Switch
        if isinstance(peer_dev, Switch):
            for p in peer_dev.ports.values():
                if p != peer_port and p.cable:
                    remote_port = p.cable.get_peer_port(p)
                    if remote_port and not remote_port.is_shutdown:
                        r_dev = remote_port.device
                        if isinstance(r_dev, Host) and r_dev.eth0 and r_dev.eth0.ip_address == target_ip:
                            return True, r_dev.eth0.mac_address
                        if hasattr(r_dev, "ports"):
                            for rp in r_dev.ports.values():
                                if rp.ip_address == target_ip:
                                    return True, getattr(rp, "mac_address", "02:00:1a:00:00:01")

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
            # Also check subinterfaces
            if hasattr(dev, "get_interface"):
                sub = dev.get_interface(preferred_interface)
                if sub and sub.is_link_up and sub.ip_address:
                    phys = getattr(sub, "parent_port", sub)
                    return phys, sub.ip_address, sub.subnet_mask

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
                            return sub.parent_port, sub.ip_address, sub.subnet_mask

            # 2. Check routing table
            route = dev.lookup_route(target_ip)
            if route and route.get("interface"):
                p = dev.get_port(route["interface"])
                if p and p.is_link_up and p.ip_address:
                    return p, p.ip_address, p.subnet_mask
                if hasattr(dev, "get_interface"):
                    sub = dev.get_interface(route["interface"])
                    if sub and sub.is_link_up and sub.ip_address:
                        phys = getattr(sub, "parent_port", sub)
                        return phys, sub.ip_address, sub.subnet_mask

        # Fallback: find first active port with IP
        if hasattr(dev, "ports"):
            for p in dev.ports.values():
                if p.is_link_up and p.ip_address:
                    return p, p.ip_address, p.subnet_mask
        if hasattr(dev, "subinterfaces"):
            for sub in dev.subinterfaces.values():
                if sub.is_link_up and sub.ip_address:
                    return sub.parent_port, sub.ip_address, sub.subnet_mask

        return None, None, None

    def _trace_packet(self, current_dev, out_port, current_ip, current_mask,
                      target_ip, visited, hop_path, current_vlan=1, ttl=15, trace_context=None):
        if ttl <= 0 or current_dev.id in visited:
            return False
        visited.add(current_dev.id)

        if trace_context is None:
            trace_context = {}

        # 1. Trigger physical LED activity on out_port
        if not out_port or not out_port.is_link_up:
            return False
        out_port.trigger_traffic()

        # 2. Check physical cable link
        cable = out_port.cable
        if not cable or cable.is_damaged:
            return False

        # 3. Arrive at peer port
        peer_port = cable.get_peer_port(out_port)
        if not peer_port or peer_port.is_shutdown:
            return False
        peer_port.trigger_traffic()
        next_dev = peer_port.device
        hop_path.append(next_dev.hostname)

        # 4. Handle destination matches on next_dev
        if self._is_device_ip(next_dev, target_ip, peer_port, current_vlan):
            return True

        # 5. Layer 2 Switching logic
        if isinstance(next_dev, Switch):
            in_vlan = current_vlan
            if peer_port.mode == "access":
                in_vlan = peer_port.access_vlan
            elif peer_port.mode == "trunk":
                pass  # keeps tagged vlan

            out_ports = next_dev.forward_packet(peer_port, "00:AA:BB:CC:DD:EE", "FF:FF:FF:FF:FF:FF", in_vlan)
            for cand_port in out_ports:
                if cand_port.cable and cand_port.cable.get_peer_port(cand_port) != out_port:
                    if self._trace_packet(next_dev, cand_port, current_ip, current_mask,
                                          target_ip, visited.copy(), hop_path, current_vlan=in_vlan,
                                          ttl=ttl-1, trace_context=trace_context):
                        return True
            return False

        # 6. Layer 3/4 Stateful Firewall Inspection logic
        if isinstance(next_dev, Firewall):
            permitted, reason = next_dev.inspect_packet(peer_port, target_ip, current_ip, protocol="icmp")
            if not permitted:
                trace_context["firewall_deny"] = True
                trace_context["drop_code"] = "A"
                return False

            route = next_dev.lookup_route(target_ip)
            egress_port = None
            if route and route.get("interface"):
                egress_port = next_dev.get_port(route["interface"])
            if not egress_port:
                for p in next_dev.ports.values():
                    if p != peer_port and p.is_link_up and p.ip_address and p.subnet_mask:
                        if is_ip_in_subnet(target_ip, p.ip_address, p.subnet_mask):
                            egress_port = p
                            break

            if egress_port and egress_port.is_link_up:
                return self._trace_packet(next_dev, egress_port, getattr(egress_port, "ip_address", current_ip),
                                          getattr(egress_port, "subnet_mask", current_mask), target_ip,
                                          visited, hop_path, current_vlan=1, ttl=ttl-1, trace_context=trace_context)
            trace_context["unrouted"] = True
            return False

        # 7. Layer 3 Routing & Cisco NAT logic
        if isinstance(next_dev, Router):
            route = next_dev.lookup_route(target_ip)
            if not route:
                trace_context["unrouted"] = True
                return False

            egress_name = route["interface"]
            if not egress_name:
                next_hop = route["next_hop"]
                hop_route = next_dev.lookup_route(next_hop)
                if hop_route:
                    egress_name = hop_route["interface"]

            if egress_name:
                egress_if = next_dev.get_interface(egress_name)
                if egress_if and egress_if.is_link_up:
                    physical_port = egress_if if not hasattr(egress_if, "parent_port") else egress_if.parent_port
                    vlan_tag = getattr(egress_if, "vlan_id", 1) or 1

                    # NAT Translation (Inside -> Outside)
                    translated_ip, nat_entry = next_dev.perform_nat(current_ip, peer_port.name, physical_port.name, protocol="icmp")
                    active_src_ip = translated_ip if translated_ip else current_ip

                    # If routing towards public internet IP (e.g. 8.8.8.8)
                    if target_ip in PUBLIC_INTERNET_IPS:
                        if is_private_ip(current_ip) and not translated_ip:
                            trace_context["unrouted"] = True
                            return False

                        peer_on_egress = physical_port.cable.get_peer_port(physical_port) if physical_port.cable else None
                        if peer_on_egress and not peer_on_egress.is_shutdown:
                            peer_dev = peer_on_egress.device
                            if any(k in peer_dev.hostname.lower() for k in ("isp", "internet", "cloud", "wan")):
                                hop_path.append(peer_dev.hostname)
                                hop_path.append(f"Public-Internet [{target_ip}]")
                                return True

                    return self._trace_packet(next_dev, physical_port, getattr(egress_if, "ip_address", active_src_ip),
                                             getattr(egress_if, "subnet_mask", current_mask), target_ip,
                                             visited, hop_path, current_vlan=vlan_tag, ttl=ttl-1, trace_context=trace_context)

        return False

    def _is_device_ip(self, dev, target_ip, in_port, vlan_id):
        """Checks if device owns target_ip on the incoming interface/vlan."""
        if target_ip in PUBLIC_INTERNET_IPS:
            if any(k in dev.hostname.lower() for k in ("isp", "internet", "cloud", "wan")):
                return True

        if isinstance(dev, Host):
            p = dev.eth0
            return p and p.ip_address == target_ip
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

    def simulate_traceroute(self, source_device, target_ip, max_hops=30, source_interface=None):
        """
        Simulates hop-by-hop traceroute to target_ip.
        Returns a list of dicts: [{'hop': 1, 'ip': '...', 'name': '...', 'rtts': [1.2, 1.1, 1.4]}, ...]
        """
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
                                     current_vlan=src_port.access_vlan,
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
