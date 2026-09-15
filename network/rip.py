"""
network/rip.py - RIPv2 Dynamic Routing Protocol Implementation
Implements RFC 2453 (RIPv2) for Layer 3 Routers in the Network Simulator:
- Metric: Hop Count (1-15, 16 = Unreachable / Infinity)
- Administrative Distance: 120
- Loop Prevention: Split Horizon and Route Poisoning (Poison Reverse)
- Deterministic Event-Driven Convergence
"""

import socket
import struct
from .device import Port

# Standard RIP Timers (seconds)
RIP_UPDATE_INTERVAL = 30
RIP_TIMEOUT = 180
RIP_HOLD_DOWN = 180
RIP_FLUSH_TIME = 240
RIP_INFINITY = 16


def ip_to_int(ip_str):
    try:
        return struct.unpack("!I", socket.inet_aton(ip_str))[0]
    except Exception:
        return 0


def int_to_ip(ip_int):
    return socket.inet_ntoa(struct.pack("!I", ip_int))


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


def get_classful_mask(net_str):
    """Determines default classful subnet mask for Class A, B, or C IPv4 addresses."""
    try:
        parts = net_str.strip().split(".")
        first = int(parts[0])
        if 1 <= first <= 126:
            return "255.0.0.0"
        elif 128 <= first <= 191:
            return "255.255.0.0"
        elif 192 <= first <= 223:
            return "255.255.255.0"
        return "255.255.255.0"
    except Exception:
        return "255.255.255.0"


def is_ip_in_network(ip_str, net_str):
    """
    Checks if an IP matches a configured RIP network statement.
    Supports classful network boundaries or explicit subnet prefixes.
    """
    if not is_valid_ipv4(ip_str) or not is_valid_ipv4(net_str):
        return False
    mask_str = get_classful_mask(net_str)
    ip_i = ip_to_int(ip_str)
    net_i = ip_to_int(net_str)
    mask_i = ip_to_int(mask_str)
    return (ip_i & mask_i) == (net_i & mask_i)


class RIPProcess:
    def __init__(self, router):
        self.router = router
        self.enabled = False
        self.version = 2
        self.networks = set()       # set of network strings e.g. {"10.0.0.0", "192.168.10.0"}
        self.neighbors = set()      # set of discovered neighbor IP strings e.g. {"10.0.12.2"}
        self.neighbor_info = {}     # neighbor_ip -> {"router": dev, "interface": local_if, "peer_if": remote_if}
        self.routes = {}            # (network, mask) -> route_dict (metric < 16)
        self.poisoned_routes = {}   # (network, mask) -> route_dict with metric=16

    def enable(self):
        self.enabled = True
        self.trigger_convergence()

    def disable(self):
        self.enabled = False
        self.routes.clear()
        self.neighbors.clear()
        self.neighbor_info.clear()
        self.poisoned_routes.clear()
        self.trigger_convergence()

    def add_network(self, net_str):
        clean = net_str.strip()
        if not is_valid_ipv4(clean):
            return False
        self.networks.add(clean)
        self.trigger_convergence()
        return True

    def remove_network(self, net_str):
        clean = net_str.strip()
        if clean in self.networks:
            self.networks.remove(clean)
            self.trigger_convergence()
            return True
        return False

    def is_interface_matched(self, iface):
        """Checks if a port or subinterface has an IP that matches configured RIP networks."""
        if not iface or not iface.ip_address:
            return False
        for net in self.networks:
            if is_ip_in_network(iface.ip_address, net):
                return True
        return False

    def get_participating_interfaces(self):
        """Returns list of local interfaces/subinterfaces participating in RIP and currently link up."""
        if not self.enabled:
            return []
        active = []
        # 1. Physical ports
        for p in self.router.ports.values():
            if p.is_link_up and p.ip_address and p.subnet_mask:
                if self.is_interface_matched(p):
                    active.append(p)
        # 2. Subinterfaces
        if hasattr(self.router, "subinterfaces"):
            for sub in self.router.subinterfaces.values():
                if sub.is_link_up and sub.ip_address and sub.subnet_mask:
                    if self.is_interface_matched(sub):
                        active.append(sub)
        return active

    def discover_neighbors(self):
        """
        Discovers directly connected RIP-enabled routers across links and Layer 2 switches.
        Updates self.neighbors and self.neighbor_info.
        """
        if not self.enabled:
            self.neighbors.clear()
            self.neighbor_info.clear()
            return

        current_neighbors = {}
        for iface in self.get_participating_interfaces():
            phys_port = iface if not hasattr(iface, "parent_port") else iface.parent_port
            if not phys_port.cable:
                continue

            vlan_id = getattr(iface, "vlan_id", 1) or 1

            # 1. Direct connection
            peer_port = phys_port.cable.get_peer_port(phys_port)
            if not peer_port or peer_port.is_shutdown:
                continue

            peer_dev = peer_port.device
            from .router import Router
            if isinstance(peer_dev, Router) and getattr(peer_dev, "rip_enabled", False):
                peer_if = self._match_peer_interface(iface, peer_dev, vlan_id)
                if peer_if and peer_dev.rip.is_interface_matched(peer_if):
                    current_neighbors[peer_if.ip_address] = {
                        "router": peer_dev,
                        "local_if": iface,
                        "peer_if": peer_if
                    }

            # 2. Connection through Layer 2 Switch
            from .switch import Switch
            if isinstance(peer_dev, Switch):
                discovered = self._scan_switch_for_rip_neighbors(peer_dev, peer_port, iface, vlan_id)
                current_neighbors.update(discovered)

        # Detect lost neighbors and poison their routes
        lost_neighbors = set(self.neighbor_info.keys()) - set(current_neighbors.keys())
        for lost_ip in lost_neighbors:
            self._poison_routes_from_neighbor(lost_ip)

        self.neighbor_info = current_neighbors
        self.neighbors = set(current_neighbors.keys())

    def _match_peer_interface(self, local_if, peer_dev, vlan_id):
        """Finds peer interface on peer_dev that shares the same IP subnet and VLAN."""
        local_net = ip_to_int(local_if.ip_address) & ip_to_int(local_if.subnet_mask)
        # Check subinterfaces first if 802.1Q
        if hasattr(peer_dev, "subinterfaces"):
            for sub in peer_dev.subinterfaces.values():
                if sub.is_link_up and sub.ip_address and sub.subnet_mask:
                    sub_vlan = getattr(sub, "vlan_id", 1)
                    if sub_vlan == vlan_id:
                        p_net = ip_to_int(sub.ip_address) & ip_to_int(sub.subnet_mask)
                        if p_net == local_net:
                            return sub
        # Check physical ports
        for p in peer_dev.ports.values():
            if p.is_link_up and p.ip_address and p.subnet_mask:
                p_net = ip_to_int(p.ip_address) & ip_to_int(p.subnet_mask)
                if p_net == local_net:
                    return p
        return None

    def _scan_switch_for_rip_neighbors(self, switch, in_port, local_if, vlan_id):
        """Scans switch ports in the same VLAN for adjacent RIP routers."""
        found = {}
        from .router import Router
        for p in switch.ports.values():
            if p != in_port and p.cable and not p.is_shutdown:
                # Check VLAN membership
                if p.mode == "access" and p.access_vlan != vlan_id:
                    continue
                if p.mode == "trunk" and vlan_id not in p.trunk_allowed_vlans:
                    continue

                remote_port = p.cable.get_peer_port(p)
                if remote_port and not remote_port.is_shutdown:
                    remote_dev = remote_port.device
                    if isinstance(remote_dev, Router) and getattr(remote_dev, "rip_enabled", False):
                        peer_if = self._match_peer_interface(local_if, remote_dev, vlan_id)
                        if peer_if and remote_dev.rip.is_interface_matched(peer_if):
                            found[peer_if.ip_address] = {
                                "router": remote_dev,
                                "local_if": local_if,
                                "peer_if": peer_if
                            }
        return found

    def _poison_routes_from_neighbor(self, neighbor_ip):
        """Marks routes learned via a lost neighbor as unreachable (metric 16)."""
        to_poison = [k for k, r in self.routes.items() if r.get("next_hop") == neighbor_ip]
        for k in to_poison:
            r = self.routes.pop(k)
            r["metric"] = RIP_INFINITY
            self.poisoned_routes[k] = r

    def build_update_payload(self, out_iface, neighbor_ip):
        """
        Builds RIP advertisement payload to send out of out_iface towards neighbor_ip.
        Implements Split Horizon: Never advertises a route back out through the interface
        it was learned on, or to the neighbor it was learned from.
        """
        payload = []

        # 1. Connected routes on participating interfaces
        for iface in self.get_participating_interfaces():
            net_int = ip_to_int(iface.ip_address) & ip_to_int(iface.subnet_mask)
            net_str = int_to_ip(net_int)
            mask_str = iface.subnet_mask

            # Split Horizon: Do NOT advertise out_iface's own subnet back out of out_iface
            if iface.name == out_iface.name:
                continue

            payload.append({
                "network": net_str,
                "mask": mask_str,
                "metric": 1  # 1 hop away from sender
            })

        # 2. Learned dynamic RIP routes (with Split Horizon)
        for (net, mask), r in self.routes.items():
            # Split Horizon: If route was learned on out_iface or from this neighbor, suppress it
            if r.get("interface") == out_iface.name or r.get("next_hop") == neighbor_ip:
                continue

            metric = r.get("metric", 1)
            adv_metric = min(metric + 1, RIP_INFINITY)
            payload.append({
                "network": net,
                "mask": mask,
                "metric": adv_metric
            })

        # 3. Route Poisoning: Advertise unreachable routes (metric 16) to poison downstream
        for (net, mask), r in self.poisoned_routes.items():
            if r.get("interface") == out_iface.name or r.get("next_hop") == neighbor_ip:
                continue
            payload.append({
                "network": net,
                "mask": mask,
                "metric": RIP_INFINITY
            })

        return payload

    def receive_update(self, source_ip, in_iface, update_payload):
        """
        Processes incoming RIP update from neighbor source_ip on in_iface.
        Returns True if any routing change occurred (new route, better metric, or poisoned).
        """
        if not self.enabled:
            return False

        changed = False
        # Record neighbor
        self.neighbors.add(source_ip)

        for item in update_payload:
            net = item["network"]
            mask = item["mask"]
            metric = item["metric"]
            route_key = (net, mask)

            # Check if this route is one of our own directly connected subnets
            is_local = False
            for iface in self.router.ports.values():
                if iface.is_link_up and iface.ip_address and iface.subnet_mask:
                    l_net = int_to_ip(ip_to_int(iface.ip_address) & ip_to_int(iface.subnet_mask))
                    if l_net == net and iface.subnet_mask == mask:
                        is_local = True
                        break
            if hasattr(self.router, "subinterfaces"):
                for sub in self.router.subinterfaces.values():
                    if sub.is_link_up and sub.ip_address and sub.subnet_mask:
                        l_net = int_to_ip(ip_to_int(sub.ip_address) & ip_to_int(sub.subnet_mask))
                        if l_net == net and sub.subnet_mask == mask:
                            is_local = True
                            break
            if is_local:
                # Connected route always has metric 0, never overwritten by RIP
                continue

            # Route Poisoning handling: metric >= 16
            if metric >= RIP_INFINITY:
                if route_key in self.routes and self.routes[route_key].get("next_hop") == source_ip:
                    poisioned = self.routes.pop(route_key)
                    poisioned["metric"] = RIP_INFINITY
                    self.poisoned_routes[route_key] = poisioned
                    changed = True
                continue

            # Valid route (metric 1-15)
            if route_key in self.poisoned_routes:
                self.poisoned_routes.pop(route_key)

            if route_key in self.routes:
                existing = self.routes[route_key]
                if existing.get("next_hop") == source_ip:
                    # Update from current next-hop (metric change or refresh)
                    if existing["metric"] != metric or existing["interface"] != in_iface.name:
                        existing["metric"] = metric
                        existing["interface"] = in_iface.name
                        changed = True
                elif metric < existing["metric"]:
                    # Better path found from another neighbor!
                    self.routes[route_key] = {
                        "network": net,
                        "mask": mask,
                        "next_hop": source_ip,
                        "interface": in_iface.name,
                        "metric": metric,
                        "type": "R",
                        "admin_distance": 120
                    }
                    changed = True
            else:
                # Install new dynamic RIP route
                self.routes[route_key] = {
                    "network": net,
                    "mask": mask,
                    "next_hop": source_ip,
                    "interface": in_iface.name,
                    "metric": metric,
                    "type": "R",
                    "admin_distance": 120
                }
                changed = True

        return changed

    def trigger_convergence(self):
        """Triggers local neighbor discovery and global Bellman-Ford convergence."""
        converge_all_rip()


def converge_all_rip(routers=None, max_rounds=6):
    """
    Simulates iterative Bellman-Ford update propagation across all RIP routers in the simulator.
    Stops when routing tables reach steady-state convergence.
    """
    from .router import Router
    if routers is None:
        routers = [d for d in Router._all_routers if getattr(d, "rip_enabled", False)]
    else:
        routers = [d for d in routers if getattr(d, "rip_enabled", False)]
    if not routers:
        return

    for _ in range(max_rounds):
        any_changed = False
        # 1. Neighbor discovery on each router
        for r in routers:
            r.rip.discover_neighbors()

        # 2. Exchange updates between discovered neighbors
        for r in routers:
            for neighbor_ip, info in list(r.rip.neighbor_info.items()):
                peer_router = info["router"]
                local_if = info["local_if"]
                peer_if = info["peer_if"]

                # Ensure peer router still has RIP enabled and link is up
                if not peer_router.rip.enabled or not local_if.is_link_up or not peer_if.is_link_up:
                    continue

                payload = r.rip.build_update_payload(local_if, neighbor_ip)
                changed = peer_router.rip.receive_update(local_if.ip_address, peer_if, payload)
                if changed:
                    any_changed = True

        if not any_changed:
            break
