"""
network/ospf.py - OSPFv2 (Open Shortest Path First version 2) Protocol Implementation
Implements RFC 2328 for Layer 3 Routers in the Network Simulator:
- Protocol: OSPFv2 / IPv4 / Single Area (Area 0)
- Metric: Interface Cost (default 1, configurable via 'ip ospf cost <val>')
- Administrative Distance: 110
- Adjacency State Machine: DOWN -> INIT -> 2-WAY -> FULL
- Link-State Database (LSDB) with Router-LSAs and Sequence Numbering (0x80000001+)
- Dijkstra's Shortest Path First (SPF) Algorithm for Route Calculation
- Dynamic Route Installation (Type 'O')
- Deterministic Event-Driven Convergence
"""

import socket
import struct
import copy
from .device import Port

# Standard OSPF Constants & Timers
OSPF_HELLO_INTERVAL = 10
OSPF_DEAD_INTERVAL = 40
OSPF_DEFAULT_COST = 1
OSPF_AD = 110
OSPF_INITIAL_SEQ = 0x80000001


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


def is_valid_wildcard(wc_str):
    if not is_valid_ipv4(wc_str):
        return False
    return True


def is_ip_in_wildcard(ip_str, net_str, wildcard_str="0.0.0.0"):
    try:
        ip_i = ip_to_int(ip_str)
        net_i = ip_to_int(net_str)
        wc_i = ip_to_int(wildcard_str)
        mask = (~wc_i) & 0xFFFFFFFF
        return (ip_i & mask) == (net_i & mask)
    except Exception:
        return False


class RouterLSA:
    """
    Represents an OSPF Type 1 Router-LSA.
    Describes all router links within Area 0 (point-to-point connections and stub subnets).
    """
    def __init__(self, adv_router, area=0, sequence=OSPF_INITIAL_SEQ, age=1):
        self.adv_router = str(adv_router)  # Advertising Router ID
        self.lsa_type = "Router-LSA"
        self.area = area
        self.sequence = int(sequence)      # 32-bit signed sequence number (0x80000001+)
        self.age = int(age)                # Age in seconds
        self.links = []                    # List of link dicts

    def add_point_to_point_link(self, neighbor_router_id, local_ip, peer_ip, cost=1):
        self.links.append({
            "type": "point-to-point",
            "link_id": str(neighbor_router_id),
            "link_data": str(local_ip),
            "neighbor_ip": str(peer_ip),
            "cost": int(cost)
        })

    def add_stub_link(self, network_str, mask_str, cost=1):
        self.links.append({
            "type": "stub",
            "network": str(network_str),
            "mask": str(mask_str),
            "cost": int(cost)
        })

    def clone(self):
        new_lsa = RouterLSA(self.adv_router, self.area, self.sequence, self.age)
        new_lsa.links = copy.deepcopy(self.links)
        return new_lsa


class OSPFNeighbor:
    """
    Tracks an individual OSPF neighbor relationship across a specific local interface.
    """
    def __init__(self, neighbor_id, neighbor_ip, local_if, peer_if, peer_router, cost=1, area=0):
        self.neighbor_id = str(neighbor_id)  # Peer Router ID
        self.neighbor_ip = str(neighbor_ip)  # Peer Interface IP
        self.local_if = local_if             # Local Port or SubInterface
        self.peer_if = peer_if               # Peer Port or SubInterface
        self.peer_router = peer_router       # Peer Router instance
        self.state = "DOWN"                  # DOWN, INIT, 2-WAY, FULL
        self.cost = int(cost)
        self.area = area
        self.priority = 1
        self.last_hello_time = 0.0


class OSPFProcess:
    """
    OSPFv2 Routing Engine for Layer 3 Routers.
    """
    def __init__(self, router):
        self.router = router
        self.enabled = False
        self.process_id = 1
        self.area = 0
        self.explicit_router_id = None
        self.networks = []          # List of tuples: (network_str, wildcard_str, area_id)
        self.neighbors = {}         # neighbor_ip -> OSPFNeighbor
        self.lsdb = {}              # adv_router_id -> RouterLSA
        self.routes = {}            # (network, mask) -> route_dict
        self.spf_runs = 0

    @property
    def router_id(self):
        return self.get_router_id()

    def get_router_id(self):
        """
        Determines Router ID deterministically:
        1. Explicitly configured 'router-id <ip>'
        2. Highest IPv4 address on active, non-shutdown interfaces/subinterfaces
        3. Fallback deterministic ID from router hostname/id
        """
        if self.explicit_router_id:
            return self.explicit_router_id

        # Search active interfaces for highest IP
        active_ips = []
        if hasattr(self.router, "ports"):
            for p in self.router.ports.values():
                if not p.is_shutdown and p.ip_address:
                    active_ips.append(p.ip_address)
        if hasattr(self.router, "subinterfaces"):
            for sub in self.router.subinterfaces.values():
                if not sub.is_shutdown and sub.ip_address:
                    active_ips.append(sub.ip_address)

        if active_ips:
            # Sort by integer value descending
            active_ips.sort(key=lambda ip: ip_to_int(ip), reverse=True)
            return active_ips[0]

        # Fallback deterministic IP
        h_val = abs(hash(self.router.id)) % 250 + 1
        return f"1.1.1.{h_val}"

    def set_router_id(self, rid_str):
        if not is_valid_ipv4(rid_str):
            return False
        self.explicit_router_id = rid_str
        self.trigger_convergence()
        return True

    def enable(self, process_id=1):
        self.enabled = True
        self.process_id = process_id
        self.trigger_convergence()

    def disable(self):
        self.enabled = False
        self.neighbors.clear()
        self.lsdb.clear()
        self.routes.clear()
        self.trigger_convergence()

    def add_network(self, net_str, wildcard_str="0.0.0.0", area=0):
        if not is_valid_ipv4(net_str) or not is_valid_wildcard(wildcard_str):
            return False
        entry = (net_str, wildcard_str, int(area))
        if entry not in self.networks:
            self.networks.append(entry)
            self.trigger_convergence()
        return True

    def remove_network(self, net_str, wildcard_str="0.0.0.0", area=0):
        entry = (net_str, wildcard_str, int(area))
        if entry in self.networks:
            self.networks.remove(entry)
            self.trigger_convergence()
            return True
        return False

    def is_interface_matched(self, iface):
        """Checks if an interface/subinterface IP matches any configured OSPF network statement."""
        if not iface or not iface.ip_address:
            return False
        for net_str, wc_str, area in self.networks:
            if area == 0 and is_ip_in_wildcard(iface.ip_address, net_str, wc_str):
                return True
        return False

    def get_participating_interfaces(self):
        """Returns list of active, link-up interfaces/subinterfaces participating in OSPF Area 0."""
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
        Discovers directly connected OSPF routers across physical cables and Layer 2 switches.
        Updates self.neighbors and transitions adjacency states: DOWN -> INIT -> 2-WAY -> FULL.
        """
        if not self.enabled:
            self.neighbors.clear()
            return

        current_neighbors = {}
        for iface in self.get_participating_interfaces():
            phys_port = iface if not hasattr(iface, "parent_port") else iface.parent_port
            if not phys_port.cable:
                continue

            vlan_id = getattr(iface, "vlan_id", 1) or 1
            peer_port = phys_port.cable.get_peer_port(phys_port)
            if not peer_port or peer_port.is_shutdown:
                continue

            peer_dev = peer_port.device
            from .router import Router

            # 1. Direct Cable Connection
            if isinstance(peer_dev, Router) and getattr(peer_dev, "ospf_enabled", False):
                peer_if = self._match_peer_interface(iface, peer_dev, vlan_id)
                if peer_if and peer_dev.ospf.is_interface_matched(peer_if):
                    cost = getattr(iface, "ospf_cost", OSPFDEFAULT_COST if "OSPFDEFAULT_COST" in globals() else 1)
                    cost = getattr(iface, "ospf_cost", 1)
                    nbr = OSPFNeighbor(
                        neighbor_id=peer_dev.ospf.get_router_id(),
                        neighbor_ip=peer_if.ip_address,
                        local_if=iface,
                        peer_if=peer_if,
                        peer_router=peer_dev,
                        cost=cost,
                        area=0
                    )
                    nbr.state = "FULL"  # Synchronized state
                    current_neighbors[peer_if.ip_address] = nbr

            # 2. Connection through Layer 2 Switch
            from .switch import Switch
            if isinstance(peer_dev, Switch):
                discovered = self._scan_switch_for_ospf_neighbors(peer_dev, peer_port, iface, vlan_id)
                current_neighbors.update(discovered)

        self.neighbors = current_neighbors

    def _match_peer_interface(self, local_if, peer_dev, vlan_id):
        """Finds matching peer interface/subinterface on peer_dev with same subnet and VLAN."""
        local_net = ip_to_int(local_if.ip_address) & ip_to_int(local_if.subnet_mask)
        # Check subinterfaces
        if hasattr(peer_dev, "subinterfaces"):
            for sub in peer_dev.subinterfaces.values():
                if sub.is_link_up and sub.ip_address and sub.subnet_mask:
                    sub_vlan = getattr(sub, "vlan_id", 1)
                    if sub_vlan == vlan_id:
                        peer_net = ip_to_int(sub.ip_address) & ip_to_int(sub.subnet_mask)
                        if peer_net == local_net:
                            return sub
        # Check physical ports
        for p in peer_dev.ports.values():
            if p.is_link_up and p.ip_address and p.subnet_mask:
                peer_net = ip_to_int(p.ip_address) & ip_to_int(p.subnet_mask)
                if peer_net == local_net:
                    return p
        return None

    def _scan_switch_for_ospf_neighbors(self, switch, ingress_port, local_if, vlan_id):
        """Traverses L2 switch ports to discover OSPF neighbors on matching VLAN."""
        discovered = {}
        from .router import Router
        from .switch import Switch

        visited_switches = {switch}
        switches_to_visit = [(switch, ingress_port)]

        while switches_to_visit:
            curr_sw, in_p = switches_to_visit.pop(0)
            for out_name, out_p in curr_sw.ports.items():
                if out_p == in_p or out_p.is_shutdown or not out_p.cable:
                    continue

                # STP check: port must be forwarding
                if getattr(out_p, "stp_state", "Forwarding") == "Blocking":
                    continue

                # VLAN membership check
                if out_p.mode == "access":
                    if out_p.access_vlan != vlan_id:
                        continue
                elif out_p.mode == "trunk":
                    if vlan_id not in out_p.trunk_allowed_vlans:
                        continue

                peer_p = out_p.cable.get_peer_port(out_p)
                if not peer_p or peer_p.is_shutdown:
                    continue

                # Another switch (e.g. switch-to-switch trunk)
                if isinstance(peer_p.device, Switch) and peer_p.device not in visited_switches:
                    visited_switches.add(peer_p.device)
                    switches_to_visit.append((peer_p.device, peer_p))
                    continue

                # Target Router
                if isinstance(peer_p.device, Router) and getattr(peer_p.device, "ospf_enabled", False):
                    peer_dev = peer_p.device
                    peer_if = self._match_peer_interface(local_if, peer_dev, vlan_id)
                    if peer_if and peer_dev.ospf.is_interface_matched(peer_if):
                        cost = getattr(local_if, "ospf_cost", 1)
                        nbr = OSPFNeighbor(
                            neighbor_id=peer_dev.ospf.get_router_id(),
                            neighbor_ip=peer_if.ip_address,
                            local_if=local_if,
                            peer_if=peer_if,
                            peer_router=peer_dev,
                            cost=cost,
                            area=0
                        )
                        nbr.state = "FULL"
                        discovered[peer_if.ip_address] = nbr

        return discovered

    def originate_router_lsa(self):
        """
        Builds the local Type 1 Router-LSA reflecting all current FULL neighbors
        and directly connected stub networks, incrementing the sequence number.
        """
        my_rid = self.get_router_id()
        prev_lsa = self.lsdb.get(my_rid)
        new_seq = (prev_lsa.sequence + 1) if prev_lsa else OSPF_INITIAL_SEQ

        lsa = RouterLSA(my_rid, area=0, sequence=new_seq, age=1)

        # 1. Point-to-Point links to FULL neighbors
        for nbr in self.neighbors.values():
            if nbr.state == "FULL":
                cost = getattr(nbr.local_if, "ospf_cost", 1)
                lsa.add_point_to_point_link(
                    neighbor_router_id=nbr.neighbor_id,
                    local_ip=nbr.local_if.ip_address,
                    peer_ip=nbr.neighbor_ip,
                    cost=cost
                )

        # 2. Stub links for participating connected subnets
        participating = self.get_participating_interfaces()
        seen_stubs = set()
        for iface in participating:
            net_i = ip_to_int(iface.ip_address) & ip_to_int(iface.subnet_mask)
            net_str = int_to_ip(net_i)
            key = (net_str, iface.subnet_mask)
            if key not in seen_stubs:
                seen_stubs.add(key)
                cost = getattr(iface, "ospf_cost", 1)
                lsa.add_stub_link(net_str, iface.subnet_mask, cost=cost)

        self.lsdb[my_rid] = lsa
        return lsa

    def receive_lsa(self, lsa):
        """
        Ingests an LSA into the local LSDB.
        Returns True if the LSDB was modified with a newer LSA.
        """
        if not lsa or lsa.area != 0:
            return False

        existing = self.lsdb.get(lsa.adv_router)
        if existing is None:
            self.lsdb[lsa.adv_router] = lsa.clone()
            return True
        elif lsa.sequence > existing.sequence:
            self.lsdb[lsa.adv_router] = lsa.clone()
            return True
        return False

    def run_spf(self):
        """
        Executes Dijkstra's Shortest Path First algorithm over the local LSDB.
        Calculates cumulative path cost and installs best dynamic 'O' routes into self.routes.
        """
        if not self.enabled:
            self.routes.clear()
            return

        my_rid = self.get_router_id()
        if my_rid not in self.lsdb:
            self.routes.clear()
            return

        # 1. Graph nodes: all routers in LSDB
        all_rids = set(self.lsdb.keys())
        dist = {rid: float("inf") for rid in all_rids}
        dist[my_rid] = 0
        first_hop = {}  # rid -> (next_hop_ip, outgoing_if_name)

        visited = set()
        unvisited = set(all_rids)

        while unvisited:
            # Find unvisited vertex with minimum distance
            u = None
            min_d = float("inf")
            for node in unvisited:
                if dist[node] < min_d:
                    min_d = dist[node]
                    u = node

            if u is None or min_d == float("inf"):
                break

            unvisited.remove(u)
            visited.add(u)

            u_lsa = self.lsdb.get(u)
            if not u_lsa:
                continue

            for link in u_lsa.links:
                if link.get("type") == "point-to-point":
                    v = link.get("link_id")
                    if v in all_rids and v not in visited:
                        edge_cost = link.get("cost", 1)
                        alt = dist[u] + edge_cost

                        if alt < dist[v]:
                            dist[v] = alt
                            if u == my_rid:
                                # First hop determination from root router
                                neighbor_ip = link.get("neighbor_ip")
                                local_ip = link.get("link_data")
                                out_if_name = self._find_local_if_by_ip(local_ip)
                                first_hop[v] = (neighbor_ip, out_if_name)
                            else:
                                first_hop[v] = first_hop.get(u)

        # 2. Build routing table from Stub links of all reachable routers
        new_routes = {}
        for rid, lsa in self.lsdb.items():
            if dist[rid] < float("inf"):
                for link in lsa.links:
                    if link.get("type") == "stub":
                        net = link.get("network")
                        mask = link.get("mask")
                        stub_cost = link.get("cost", 1)

                        if rid == my_rid:
                            # Directly connected stub networks are handled by Connected routes
                            continue

                        if rid in first_hop and first_hop[rid]:
                            next_hop_ip, out_if = first_hop[rid]
                            total_cost = int(dist[rid] + stub_cost)
                            key = (net, mask)

                            if key not in new_routes or total_cost < new_routes[key]["metric"]:
                                new_routes[key] = {
                                    "network": net,
                                    "mask": mask,
                                    "next_hop": next_hop_ip,
                                    "interface": out_if,
                                    "type": "O",
                                    "admin_distance": OSPF_AD,
                                    "metric": total_cost,
                                    "cost": total_cost,
                                }

        self.routes = new_routes
        self.spf_runs += 1

    def _find_local_if_by_ip(self, ip_str):
        """Resolves interface or subinterface name given local IP address."""
        if hasattr(self.router, "ports"):
            for p in self.router.ports.values():
                if p.ip_address == ip_str:
                    return p.name
        if hasattr(self.router, "subinterfaces"):
            for sub in self.router.subinterfaces.values():
                if sub.ip_address == ip_str:
                    return sub.name
        return "GigabitEthernet0/0"

    def trigger_convergence(self):
        """Triggers local convergence across all OSPF routers."""
        converge_all_ospf()


def converge_all_ospf(routers=None, max_rounds=10):
    """
    Simulates iterative Link-State discovery, LSA flooding, LSDB synchronization,
    and Dijkstra SPF calculation across all OSPF-enabled routers.
    Guarantees deterministic convergence without background threads.
    """
    from .router import Router
    if routers is None:
        routers = [d for d in Router._all_routers if getattr(d, "ospf_enabled", False)]
    else:
        routers = [d for d in routers if getattr(d, "ospf_enabled", False)]

    if not routers:
        return

    # Phase 1: Neighbor discovery & Hello / Adjacency state machine
    for r in routers:
        r.ospf.discover_neighbors()

    # Phase 2: Local LSA Origination
    for r in routers:
        r.ospf.originate_router_lsa()

    # Phase 3: LSA Flooding / LSDB Synchronization across FULL neighbors
    for _ in range(max_rounds):
        any_lsa_changed = False
        for r in routers:
            # Propagate all LSAs in local LSDB to all connected FULL neighbors
            for nbr in r.ospf.neighbors.values():
                if nbr.state == "FULL" and nbr.peer_router.ospf.enabled:
                    for lsa in list(r.ospf.lsdb.values()):
                        if nbr.peer_router.ospf.receive_lsa(lsa):
                            any_lsa_changed = True

        if not any_lsa_changed:
            break

    # Phase 4: Independent Dijkstra SPF Calculation on synchronized LSDB
    for r in routers:
        r.ospf.run_spf()
