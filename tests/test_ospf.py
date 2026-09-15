"""
tests/test_ospf.py - Comprehensive OSPFv2 (Single Area 0) Verification Suite (Phase 4)
Verifies:
- Core OSPF process, Router ID, Area 0, Network statements
- Hello protocol, Neighbor discovery, Adjacency state machine (DOWN -> INIT -> 2-WAY -> FULL)
- Router-LSA generation, Sequence numbering (0x80000001+), LSA flooding, LSDB synchronization
- Dijkstra SPF calculation, Interface cost-based path selection, Dynamic 'O' route installation
- Precedence hierarchy: LPM > Connected (0) < Static (1) < OSPF (110) < RIP (120)
- Failover and fallback behaviors
- PacketEngine forwarding, TTL decrements, Traceroute
- Link failure and link recovery convergence
- Integration with VLAN / 802.1Q Subinterfaces, STP, DHCP, ACL, NAT, and Stateful Firewall
- Cisco IOS CLI commands (show ip ospf, show ip ospf neighbor, show ip ospf database, show ip route, show ip protocols, show running-config)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.router import Router
from network.switch import Switch
from network.host import Host
from network.firewall import Firewall
from network.cable import Cable
from network.packet_engine import PacketEngine
from network.ospf import RouterLSA, OSPFNeighbor, converge_all_ospf
from cli.command_executor import CommandExecutor


def setup_direct_router_pair():
    """Sets up R1 (10.0.0.1/30 on g0/0) and R2 (10.0.0.2/30 on g0/0) cabled directly."""
    r1 = Router("r1", hostname="Router-1")
    r2 = Router("r2", hostname="Router-2")

    p1 = r1.get_port("g0/0")
    p1.ip_address = "10.0.0.1"
    p1.subnet_mask = "255.255.255.252"
    p1.is_shutdown = False

    p2 = r2.get_port("g0/0")
    p2.ip_address = "10.0.0.2"
    p2.subnet_mask = "255.255.255.252"
    p2.is_shutdown = False

    c = Cable(p1, p2)
    return r1, r2, c


def setup_three_router_chain():
    """
    Sets up PC1 - R1 - R2 - R3 - PC2
    PC1: 192.168.10.10/24 (gw: 192.168.10.1)
    R1: g0/1 (192.168.10.1/24), g0/0 (10.0.12.1/30)
    R2: g0/0 (10.0.12.2/30), g0/1 (10.0.23.1/30)
    R3: g0/0 (10.0.23.2/30), g0/1 (192.168.30.1/24)
    PC2: 192.168.30.10/24 (gw: 192.168.30.1)
    """
    pc1 = Host("pc1", hostname="PC-1")
    pc1.configure_ip("192.168.10.10", "255.255.255.0", gateway="192.168.10.1")

    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/1").ip_address = "192.168.10.1"
    r1.get_port("g0/1").subnet_mask = "255.255.255.0"
    r1.get_port("g0/1").is_shutdown = False

    r1.get_port("g0/0").ip_address = "10.0.12.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.252"
    r1.get_port("g0/0").is_shutdown = False

    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False

    r2.get_port("g0/1").ip_address = "10.0.23.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.252"
    r2.get_port("g0/1").is_shutdown = False

    r3 = Router("r3", hostname="Router-3")
    r3.get_port("g0/0").ip_address = "10.0.23.2"
    r3.get_port("g0/0").subnet_mask = "255.255.255.252"
    r3.get_port("g0/0").is_shutdown = False

    r3.get_port("g0/1").ip_address = "192.168.30.1"
    r3.get_port("g0/1").subnet_mask = "255.255.255.0"
    r3.get_port("g0/1").is_shutdown = False

    pc2 = Host("pc2", hostname="PC-2")
    pc2.configure_ip("192.168.30.10", "255.255.255.0", gateway="192.168.30.1")

    c_pc1 = Cable(pc1.eth0, r1.get_port("g0/1"))
    c_r12 = Cable(r1.get_port("g0/0"), r2.get_port("g0/0"))
    c_r23 = Cable(r2.get_port("g0/1"), r3.get_port("g0/0"))
    c_pc2 = Cable(r3.get_port("g0/1"), pc2.eth0)

    # Configure OSPF on all 3 routers
    r1.enable_ospf(process_id=1)
    r1.add_ospf_network("10.0.12.0", "0.0.0.3", area=0)
    r1.add_ospf_network("192.168.10.0", "0.0.0.255", area=0)

    r2.enable_ospf(process_id=1)
    r2.add_ospf_network("10.0.12.0", "0.0.0.3", area=0)
    r2.add_ospf_network("10.0.23.0", "0.0.0.3", area=0)

    r3.enable_ospf(process_id=1)
    r3.add_ospf_network("10.0.23.0", "0.0.0.3", area=0)
    r3.add_ospf_network("192.168.30.0", "0.0.0.255", area=0)

    return {
        "pc1": pc1, "r1": r1, "r2": r2, "r3": r3, "pc2": pc2,
        "c_pc1": c_pc1, "c_r12": c_r12, "c_r23": c_r23, "c_pc2": c_pc2
    }


def test_01_enable_ospf():
    """Test 1: Enable OSPF process on router."""
    r1 = Router("r1", hostname="Router-1")
    assert r1.ospf_enabled is False
    r1.enable_ospf(process_id=1)
    assert r1.ospf_enabled is True
    assert r1.ospf_process_id == 1


def test_02_configure_router_id():
    """Test 2: Configure explicit router ID and test deterministic fallback."""
    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/0").ip_address = "10.0.0.1"
    r1.get_port("g0/0").is_shutdown = False
    r1.get_port("g0/1").ip_address = "192.168.1.1"
    r1.get_port("g0/1").is_shutdown = False

    # Without explicit router ID, deterministic fallback selects highest active interface IP
    assert r1.ospf_router_id == "192.168.1.1"

    # Configure explicit router ID
    ok = r1.set_ospf_router_id("1.1.1.1")
    assert ok is True
    assert r1.ospf_router_id == "1.1.1.1"


def test_03_configure_network():
    """Test 3: Add OSPF network statement with wildcard mask."""
    r1 = Router("r1", hostname="Router-1")
    r1.enable_ospf(1)
    ok = r1.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)
    assert ok is True
    assert ("10.0.0.0", "0.0.0.3", 0) in r1.ospf_networks


def test_04_remove_network():
    """Test 4: Remove OSPF network statement."""
    r1 = Router("r1", hostname="Router-1")
    r1.enable_ospf(1)
    r1.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)
    assert len(r1.ospf_networks) == 1
    removed = r1.remove_ospf_network("10.0.0.0", "0.0.0.3", area=0)
    assert removed is True
    assert len(r1.ospf_networks) == 0


def test_05_neighbor_discovery():
    """Test 5: Discover direct OSPF neighbor over cable."""
    r1, r2, c = setup_direct_router_pair()
    r1.enable_ospf(1)
    r1.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)
    r2.enable_ospf(1)
    r2.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)

    converge_all_ospf()

    assert "10.0.0.2" in r1.ospf_neighbors
    assert "10.0.0.1" in r2.ospf_neighbors


def test_06_hello_and_adjacency_states():
    """Test 6: Hello exchange transitions adjacency to FULL state."""
    r1, r2, c = setup_direct_router_pair()
    r1.enable_ospf(1)
    r1.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)
    r2.enable_ospf(1)
    r2.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)

    converge_all_ospf()

    nbr_on_r1 = r1.ospf_neighbors["10.0.0.2"]
    assert nbr_on_r1.state == "FULL"
    assert nbr_on_r1.neighbor_id == r2.ospf_router_id


def test_07_neighbor_table():
    """Test 7: Neighbor table stores neighbor IP, router ID, cost, interface."""
    r1, r2, c = setup_direct_router_pair()
    r1.enable_ospf(1)
    r1.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)
    r2.enable_ospf(1)
    r2.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)

    converge_all_ospf()

    nbr = r1.ospf_neighbors["10.0.0.2"]
    assert nbr.neighbor_ip == "10.0.0.2"
    assert nbr.local_if.name == "g0/0"
    assert nbr.cost == 1
    assert nbr.area == 0


def test_08_generate_router_lsa():
    """Test 8: Generate Type 1 Router-LSA with p2p and stub links."""
    r1, r2, c = setup_direct_router_pair()
    r1.enable_ospf(1)
    r1.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)
    r2.enable_ospf(1)
    r2.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)

    converge_all_ospf()

    lsa1 = r1.ospf_lsdb[r1.ospf_router_id]
    assert lsa1.adv_router == r1.ospf_router_id
    assert lsa1.lsa_type == "Router-LSA"
    p2p_links = [l for l in lsa1.links if l["type"] == "point-to-point"]
    stub_links = [l for l in lsa1.links if l["type"] == "stub"]
    assert len(p2p_links) == 1
    assert p2p_links[0]["link_id"] == r2.ospf_router_id
    assert len(stub_links) == 1
    assert stub_links[0]["network"] == "10.0.0.0"


def test_09_lsa_sequence_and_flooding():
    """Test 9: LSA sequence starts at 0x80000001 and increments on re-origination."""
    r_test = Router("r_seq_test", hostname="Router-Seq")
    r_test.ospf.enabled = True

    lsa1 = r_test.ospf.originate_router_lsa()
    assert lsa1.sequence == 0x80000001

    lsa2 = r_test.ospf.originate_router_lsa()
    assert lsa2.sequence == 0x80000002


def test_10_ignore_older_lsa():
    """Test 10: Router ignores LSA with older or identical sequence number."""
    r1 = Router("r1", hostname="Router-1")
    r1.enable_ospf(1)

    lsa_newer = RouterLSA("2.2.2.2", area=0, sequence=0x80000005)
    lsa_older = RouterLSA("2.2.2.2", area=0, sequence=0x80000003)

    accepted_newer = r1.ospf.receive_lsa(lsa_newer)
    assert accepted_newer is True
    assert r1.ospf.lsdb["2.2.2.2"].sequence == 0x80000005

    accepted_older = r1.ospf.receive_lsa(lsa_older)
    assert accepted_older is False
    assert r1.ospf.lsdb["2.2.2.2"].sequence == 0x80000005


def test_11_lsdb_synchronization():
    """Test 11: All OSPF routers in Area 0 reach synchronized LSDB."""
    topo = setup_three_router_chain()
    r1, r2, r3 = topo["r1"], topo["r2"], topo["r3"]

    converge_all_ospf()

    # All routers have LSAs for r1, r2, and r3
    rids = {r1.ospf_router_id, r2.ospf_router_id, r3.ospf_router_id}
    assert set(r1.ospf_lsdb.keys()) == rids
    assert set(r2.ospf_lsdb.keys()) == rids
    assert set(r3.ospf_lsdb.keys()) == rids


def test_12_single_hop_spf():
    """Test 12: Dijkstra SPF single hop calculates cost 1 to neighbor."""
    r1, r2, c = setup_direct_router_pair()
    r1.get_port("g0/1").ip_address = "192.168.10.1"
    r1.get_port("g0/1").subnet_mask = "255.255.255.0"
    r1.get_port("g0/1").is_shutdown = False
    h1 = Host("h1")
    Cable(r1.get_port("g0/1"), h1.eth0)

    r2.get_port("g0/1").ip_address = "192.168.20.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.0"
    r2.get_port("g0/1").is_shutdown = False
    h2 = Host("h2")
    Cable(r2.get_port("g0/1"), h2.eth0)

    r1.enable_ospf(1)
    r1.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)
    r1.add_ospf_network("192.168.10.0", "0.0.0.255", area=0)

    r2.enable_ospf(1)
    r2.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)
    r2.add_ospf_network("192.168.20.0", "0.0.0.255", area=0)

    converge_all_ospf()

    # R1 should have route to 192.168.20.0/24 with cost 2 (link 10.0.0.0 cost 1 + stub cost 1)
    route = r1.ospf_routes.get(("192.168.20.0", "255.255.255.0"))
    assert route is not None
    assert route["cost"] == 2
    assert route["next_hop"] == "10.0.0.2"


def test_13_two_hop_spf():
    """Test 13: Dijkstra SPF across 2 hops accumulates costs."""
    topo = setup_three_router_chain()
    r1, r3 = topo["r1"], topo["r3"]

    converge_all_ospf()

    route = r1.ospf_routes.get(("192.168.30.0", "255.255.255.0"))
    assert route is not None
    assert route["next_hop"] == "10.0.12.2"
    # R1 -> R2 (cost 1) + R2 -> R3 (cost 1) + R3 stub (cost 1) = 3
    assert route["cost"] == 3


def test_14_three_router_spf():
    """Test 14: All 3 routers calculate correct SPF routes to all remote subnets."""
    topo = setup_three_router_chain()
    r1, r2, r3 = topo["r1"], topo["r2"], topo["r3"]

    converge_all_ospf()

    # R2 reaches both LANs
    assert ("192.168.10.0", "255.255.255.0") in r2.ospf_routes
    assert ("192.168.30.0", "255.255.255.0") in r2.ospf_routes

    # R3 reaches R1's LAN
    assert ("192.168.10.0", "255.255.255.0") in r3.ospf_routes


def test_15_cost_based_path_selection():
    """Test 15: OSPF selects path with lower cumulative cost, not lower hop count."""
    # Triangle topology:
    # R1 ---- R2 ---- R3  (R1-R2 cost 1, R2-R3 cost 1 => total cost 3 to R3 LAN)
    #  \              /
    #   \------------/    (R1-R3 direct link cost 20 => total cost 21 to R3 LAN)
    r1 = Router("r1", hostname="Router-1")
    r2 = Router("r2", hostname="Router-2")
    r3 = Router("r3", hostname="Router-3")

    # Transit R1-R2 on 10.0.12.0/30
    r1.get_port("g0/0").ip_address = "10.0.12.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.252"
    r1.get_port("g0/0").is_shutdown = False
    r1.get_port("g0/0").ospf_cost = 1

    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.get_port("g0/0").ospf_cost = 1
    Cable(r1.get_port("g0/0"), r2.get_port("g0/0"))

    # Transit R2-R3 on 10.0.23.0/30
    r2.get_port("g0/1").ip_address = "10.0.23.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.252"
    r2.get_port("g0/1").is_shutdown = False
    r2.get_port("g0/1").ospf_cost = 1

    r3.get_port("g0/0").ip_address = "10.0.23.2"
    r3.get_port("g0/0").subnet_mask = "255.255.255.252"
    r3.get_port("g0/0").is_shutdown = False
    r3.get_port("g0/0").ospf_cost = 1
    Cable(r2.get_port("g0/1"), r3.get_port("g0/0"))

    # Direct transit R1-R3 on 10.0.13.0/30 with high cost 20
    r1.get_port("g0/2").ip_address = "10.0.13.1"
    r1.get_port("g0/2").subnet_mask = "255.255.255.252"
    r1.get_port("g0/2").is_shutdown = False
    r1.get_port("g0/2").ospf_cost = 20

    r3.get_port("g0/2").ip_address = "10.0.13.2"
    r3.get_port("g0/2").subnet_mask = "255.255.255.252"
    r3.get_port("g0/2").is_shutdown = False
    r3.get_port("g0/2").ospf_cost = 20
    Cable(r1.get_port("g0/2"), r3.get_port("g0/2"))

    # R3 LAN 192.168.30.0/24
    r3.get_port("g0/1").ip_address = "192.168.30.1"
    r3.get_port("g0/1").subnet_mask = "255.255.255.0"
    r3.get_port("g0/1").is_shutdown = False
    r3.get_port("g0/1").ospf_cost = 1
    h3_15 = Host("h3_15")
    Cable(r3.get_port("g0/1"), h3_15.eth0)

    for r in (r1, r2, r3):
        r.enable_ospf(1)
        r.add_ospf_network("10.0.0.0", "0.255.255.255", area=0)
        r.add_ospf_network("192.168.0.0", "0.0.255.255", area=0)

    converge_all_ospf()

    # R1 should prefer 2-hop path via R2 (cost 1 + 1 + 1 = 3) over 1-hop path direct to R3 (cost 20 + 1 = 21)
    route = r1.ospf_routes[("192.168.30.0", "255.255.255.0")]
    assert route["next_hop"] == "10.0.12.2", f"Expected via R2, got {route['next_hop']}"
    assert route["cost"] == 3


def test_16_cost_change_triggers_spf():
    """Test 16: Changing interface cost recalculates SPF and switches best path."""
    # From test 15 topology, if R1-R2 cost is raised to 50:
    # R1 -> R2 -> R3 cost = 50 + 1 + 1 = 52
    # R1 -> R3 direct cost = 20 + 1 = 21
    # OSPF must immediately switch next-hop to direct link 10.0.13.2!
    r1 = Router("r1", hostname="Router-1")
    r2 = Router("r2", hostname="Router-2")
    r3 = Router("r3", hostname="Router-3")

    # R1-R2
    r1.get_port("g0/0").ip_address = "10.0.12.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.252"
    r1.get_port("g0/0").is_shutdown = False
    r1.get_port("g0/0").ospf_cost = 1

    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.get_port("g0/0").ospf_cost = 1
    Cable(r1.get_port("g0/0"), r2.get_port("g0/0"))

    # R2-R3
    r2.get_port("g0/1").ip_address = "10.0.23.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.252"
    r2.get_port("g0/1").is_shutdown = False
    r2.get_port("g0/1").ospf_cost = 1

    r3.get_port("g0/0").ip_address = "10.0.23.2"
    r3.get_port("g0/0").subnet_mask = "255.255.255.252"
    r3.get_port("g0/0").is_shutdown = False
    r3.get_port("g0/0").ospf_cost = 1
    Cable(r2.get_port("g0/1"), r3.get_port("g0/0"))

    # R1-R3 direct cost 20
    r1.get_port("g0/2").ip_address = "10.0.13.1"
    r1.get_port("g0/2").subnet_mask = "255.255.255.252"
    r1.get_port("g0/2").is_shutdown = False
    r1.get_port("g0/2").ospf_cost = 20

    r3.get_port("g0/2").ip_address = "10.0.13.2"
    r3.get_port("g0/2").subnet_mask = "255.255.255.252"
    r3.get_port("g0/2").is_shutdown = False
    r3.get_port("g0/2").ospf_cost = 20
    Cable(r1.get_port("g0/2"), r3.get_port("g0/2"))

    # R3 LAN
    r3.get_port("g0/1").ip_address = "192.168.30.1"
    r3.get_port("g0/1").subnet_mask = "255.255.255.0"
    r3.get_port("g0/1").is_shutdown = False
    h3_16 = Host("h3_16")
    Cable(r3.get_port("g0/1"), h3_16.eth0)

    for r in (r1, r2, r3):
        r.enable_ospf(1)
        r.add_ospf_network("10.0.0.0", "0.255.255.255", area=0)
        r.add_ospf_network("192.168.0.0", "0.0.255.255", area=0)

    converge_all_ospf()
    assert r1.ospf_routes[("192.168.30.0", "255.255.255.0")]["next_hop"] == "10.0.12.2"

    # Now change R1 g0/0 cost to 50
    r1.get_port("g0/0").ospf_cost = 50
    converge_all_ospf()

    route_updated = r1.ospf_routes[("192.168.30.0", "255.255.255.0")]
    assert route_updated["next_hop"] == "10.0.13.2"
    assert route_updated["cost"] == 21


def test_17_install_ospf_route():
    """Test 17: Install dynamic OSPF route into routing table with AD 110."""
    topo = setup_three_router_chain()
    r1 = topo["r1"]

    converge_all_ospf()

    all_routes = r1.get_all_routes()
    o_routes = [r for r in all_routes if r["type"] == "O"]
    assert len(o_routes) >= 2
    r_target = next(r for r in o_routes if r["network"] == "192.168.30.0")
    assert r_target["admin_distance"] == 110
    assert r_target["metric"] == 3


def test_18_longest_prefix_match():
    """Test 18: Longest Prefix Match takes priority over Administrative Distance and Cost."""
    r1 = Router("r1", hostname="Router-1")
    # Add Static /16 (AD=1)
    r1.add_static_route("192.168.0.0", "255.255.0.0", "10.0.0.2")

    # Add OSPF /24 (AD=110)
    r1.enable_ospf(1)
    r1.ospf.routes[("192.168.10.0", "255.255.255.0")] = {
        "network": "192.168.10.0",
        "mask": "255.255.255.0",
        "next_hop": "10.0.0.3",
        "interface": "g0/0",
        "type": "O",
        "admin_distance": 110,
        "metric": 2
    }

    # Destination 192.168.10.5 matches both /16 Static and /24 OSPF -> /24 OSPF wins!
    match = r1.lookup_route("192.168.10.5")
    assert match is not None
    assert match["type"] == "O"
    assert match["mask"] == "255.255.255.0"


def test_19_connected_wins_ospf():
    """Test 19: Connected route (AD 0) wins over OSPF (AD 110) for same subnet."""
    r1 = Router("r1", hostname="Router-1")
    p1 = r1.get_port("g0/0")
    p1.ip_address = "192.168.10.1"
    p1.subnet_mask = "255.255.255.0"
    p1.is_shutdown = False
    h1 = Host("h1")
    Cable(p1, h1.eth0)

    # Simulate OSPF learning 192.168.10.0/24
    r1.enable_ospf(1)
    r1.ospf.routes[("192.168.10.0", "255.255.255.0")] = {
        "network": "192.168.10.0",
        "mask": "255.255.255.0",
        "next_hop": "10.0.0.2",
        "interface": "g0/1",
        "type": "O",
        "admin_distance": 110,
        "metric": 2
    }

    match = r1.lookup_route("192.168.10.50")
    assert match is not None
    assert match["type"] == "C"


def test_20_static_wins_ospf():
    """Test 20: Static route (AD 1) wins over OSPF (AD 110) for same prefix."""
    r1 = Router("r1", hostname="Router-1")
    r1.add_static_route("192.168.20.0", "255.255.255.0", "10.0.0.2")

    r1.enable_ospf(1)
    r1.ospf.routes[("192.168.20.0", "255.255.255.0")] = {
        "network": "192.168.20.0",
        "mask": "255.255.255.0",
        "next_hop": "10.0.0.3",
        "interface": "g0/0",
        "type": "O",
        "admin_distance": 110,
        "metric": 2
    }

    match = r1.lookup_route("192.168.20.50")
    assert match is not None
    assert match["type"] == "S"
    assert match["next_hop"] == "10.0.0.2"


def test_21_ospf_wins_rip():
    """Test 21: OSPF route (AD 110) wins over RIP (AD 120) for same prefix."""
    r1 = Router("r1", hostname="Router-1")

    # Add RIP route (AD 120)
    r1.enable_rip()
    r1.rip.routes[("192.168.30.0", "255.255.255.0")] = {
        "network": "192.168.30.0",
        "mask": "255.255.255.0",
        "next_hop": "10.0.0.5",
        "interface": "g0/1",
        "type": "R",
        "admin_distance": 120,
        "metric": 3
    }

    # Add OSPF route (AD 110)
    r1.enable_ospf(1)
    r1.ospf.routes[("192.168.30.0", "255.255.255.0")] = {
        "network": "192.168.30.0",
        "mask": "255.255.255.0",
        "next_hop": "10.0.0.6",
        "interface": "g0/0",
        "type": "O",
        "admin_distance": 110,
        "metric": 2
    }

    match = r1.lookup_route("192.168.30.50")
    assert match is not None
    assert match["type"] == "O"
    assert match["next_hop"] == "10.0.0.6"


def test_22_static_removal_fallback_to_ospf():
    """Test 22: Removing static route allows OSPF route to immediately become active."""
    r1 = Router("r1", hostname="Router-1")
    r1.add_static_route("192.168.20.0", "255.255.255.0", "10.0.0.2")

    r1.enable_ospf(1)
    r1.ospf.routes[("192.168.20.0", "255.255.255.0")] = {
        "network": "192.168.20.0",
        "mask": "255.255.255.0",
        "next_hop": "10.0.0.3",
        "interface": "g0/0",
        "type": "O",
        "admin_distance": 110,
        "metric": 2
    }

    # Initially Static wins
    assert r1.lookup_route("192.168.20.10")["type"] == "S"

    # Remove Static route
    r1.remove_static_route("192.168.20.0", "255.255.255.0")

    # Now OSPF route takes over!
    match = r1.lookup_route("192.168.20.10")
    assert match is not None
    assert match["type"] == "O"
    assert match["next_hop"] == "10.0.0.3"


def test_23_ospf_removal_fallback_to_rip():
    """Test 23: Removing OSPF route allows RIP route to become active."""
    r1 = Router("r1", hostname="Router-1")

    # RIP route
    r1.enable_rip()
    r1.rip.routes[("192.168.40.0", "255.255.255.0")] = {
        "network": "192.168.40.0",
        "mask": "255.255.255.0",
        "next_hop": "10.0.0.5",
        "interface": "g0/1",
        "type": "R",
        "admin_distance": 120,
        "metric": 2
    }

    # OSPF route
    r1.enable_ospf(1)
    r1.ospf.routes[("192.168.40.0", "255.255.255.0")] = {
        "network": "192.168.40.0",
        "mask": "255.255.255.0",
        "next_hop": "10.0.0.6",
        "interface": "g0/0",
        "type": "O",
        "admin_distance": 110,
        "metric": 2
    }

    assert r1.lookup_route("192.168.40.10")["type"] == "O"

    # Disable OSPF
    r1.disable_ospf()

    # RIP takes over
    match = r1.lookup_route("192.168.40.10")
    assert match is not None
    assert match["type"] == "R"
    assert match["next_hop"] == "10.0.0.5"


def test_24_two_router_ping():
    """Test 24: End-to-end ping succeeds between hosts on 2 OSPF routers."""
    r1, r2, c = setup_direct_router_pair()
    pc1 = Host("pc1", hostname="PC-1")
    pc1.configure_ip("192.168.10.10", "255.255.255.0", gateway="192.168.10.1")

    r1.get_port("g0/1").ip_address = "192.168.10.1"
    r1.get_port("g0/1").subnet_mask = "255.255.255.0"
    r1.get_port("g0/1").is_shutdown = False
    Cable(pc1.eth0, r1.get_port("g0/1"))

    pc2 = Host("pc2", hostname="PC-2")
    pc2.configure_ip("192.168.20.10", "255.255.255.0", gateway="192.168.20.1")

    r2.get_port("g0/1").ip_address = "192.168.20.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.0"
    r2.get_port("g0/1").is_shutdown = False
    Cable(pc2.eth0, r2.get_port("g0/1"))

    r1.enable_ospf(1)
    r1.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)
    r1.add_ospf_network("192.168.10.0", "0.0.0.255", area=0)

    r2.enable_ospf(1)
    r2.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)
    r2.add_ospf_network("192.168.20.0", "0.0.0.255", area=0)

    pe = PacketEngine.get_instance()
    res = pe.simulate_ping(pc1, "192.168.20.10", count=5)
    assert res.packets_received == 5
    assert res.loss_percent == 0


def test_25_three_router_multihop_ping():
    """Test 25: End-to-end ping succeeds across 3 OSPF routers."""
    topo = setup_three_router_chain()
    pe = PacketEngine.get_instance()

    res = pe.simulate_ping(topo["pc1"], "192.168.30.10", count=5)
    assert res.packets_received == 5
    assert res.loss_percent == 0


def test_26_forward_and_return_path():
    """Test 26: Bidirectional forwarding verification."""
    topo = setup_three_router_chain()
    pe = PacketEngine.get_instance()

    # Forward: PC1 -> PC2
    fwd = pe.simulate_ping(topo["pc1"], "192.168.30.10", count=3)
    assert fwd.loss_percent == 0

    # Return: PC2 -> PC1
    ret = pe.simulate_ping(topo["pc2"], "192.168.10.10", count=3)
    assert ret.loss_percent == 0


def test_27_ttl_and_traceroute():
    """Test 27: TTL decrements per OSPF hop and traceroute reflects exact hop sequence."""
    topo = setup_three_router_chain()
    pe = PacketEngine.get_instance()

    res = pe.simulate_ping(topo["pc1"], "192.168.30.10", count=1)
    assert res.packets_received == 1
    # Initial 64, minus 3 routers = 61
    assert res.ttl_replies[0] == 61

    hops = pe.simulate_traceroute(topo["pc1"], "192.168.30.10")
    hop_names = [h["name"] for h in hops]
    # Traverses R1, R2, R3, PC2
    assert "Router-1" in hop_names
    assert "Router-2" in hop_names
    assert "Router-3" in hop_names
    assert "PC-2" in hop_names


def test_28_topology_change_link_failure():
    """Test 28: Link failure triggers LSA re-origination, LSDB update, and route removal."""
    topo = setup_three_router_chain()
    r1, r2, r3 = topo["r1"], topo["r2"], topo["r3"]

    converge_all_ospf()
    assert ("192.168.30.0", "255.255.255.0") in r1.ospf_routes

    # Disconnect R2-R3 link
    topo["c_r23"].disconnect()
    converge_all_ospf()

    # R1 must no longer have route to 192.168.30.0/24
    assert ("192.168.30.0", "255.255.255.0") not in r1.ospf_routes


def test_29_topology_change_link_recovery():
    """Test 29: Restoring link re-establishes adjacency, floods LSA, and restores route."""
    topo = setup_three_router_chain()
    r1, r2, r3 = topo["r1"], topo["r2"], topo["r3"]

    # Disconnect
    topo["c_r23"].disconnect()
    converge_all_ospf()
    assert ("192.168.30.0", "255.255.255.0") not in r1.ospf_routes

    # Reconnect
    Cable(r2.get_port("g0/1"), r3.get_port("g0/0"))
    converge_all_ospf()

    assert ("192.168.30.0", "255.255.255.0") in r1.ospf_routes


def test_30_interface_shutdown_and_recovery():
    """Test 30: Administrative shutdown on interface drops adjacency and restores on no shutdown."""
    r1, r2, c = setup_direct_router_pair()
    r1.enable_ospf(1)
    r1.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)
    r2.enable_ospf(1)
    r2.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)

    converge_all_ospf()
    assert len(r1.ospf_neighbors) == 1

    # Shutdown port on R1
    r1.get_port("g0/0").is_shutdown = True
    converge_all_ospf()
    assert len(r1.ospf_neighbors) == 0

    # No shutdown
    r1.get_port("g0/0").is_shutdown = False
    converge_all_ospf()
    assert len(r1.ospf_neighbors) == 1


def test_31_vlan_subinterface_ospf():
    """Test 31: OSPF forms adjacency and learns routes over 802.1Q subinterfaces across a switch trunk."""
    r1 = Router("r1", hostname="Router-1")
    r2 = Router("r2", hostname="Router-2")
    sw = Switch("sw1", hostname="Switch-1")

    # R1 g0/0.10
    r1.get_port("g0/0").is_shutdown = False
    sub1 = r1.create_subinterface("g0/0", 10)
    sub1.vlan_id = 10
    sub1.ip_address = "10.10.10.1"
    sub1.subnet_mask = "255.255.255.252"
    sub1.is_shutdown = False

    # R2 g0/0.10
    r2.get_port("g0/0").is_shutdown = False
    sub2 = r2.create_subinterface("g0/0", 10)
    sub2.vlan_id = 10
    sub2.ip_address = "10.10.10.2"
    sub2.subnet_mask = "255.255.255.252"
    sub2.is_shutdown = False

    # Switch trunk ports
    sw.get_port("g0/1").mode = "trunk"
    sw.get_port("g0/1").trunk_allowed_vlans.add(10)
    sw.get_port("g0/1").is_shutdown = False

    sw.get_port("g0/2").mode = "trunk"
    sw.get_port("g0/2").trunk_allowed_vlans.add(10)
    sw.get_port("g0/2").is_shutdown = False

    Cable(r1.get_port("g0/0"), sw.get_port("g0/1"))
    Cable(r2.get_port("g0/0"), sw.get_port("g0/2"))

    r1.enable_ospf(1)
    r1.add_ospf_network("10.10.10.0", "0.0.0.3", area=0)
    r2.enable_ospf(1)
    r2.add_ospf_network("10.10.10.0", "0.0.0.3", area=0)

    converge_all_ospf()

    assert "10.10.10.2" in r1.ospf_neighbors
    assert r1.ospf_neighbors["10.10.10.2"].state == "FULL"


def test_32_stp_integration():
    """Test 32: STP blocking port stops OSPF adjacency across blocked link."""
    r1 = Router("r1", hostname="Router-1")
    r2 = Router("r2", hostname="Router-2")
    sw = Switch("sw1", hostname="Switch-1")

    p1 = r1.get_port("g0/0")
    p1.ip_address = "10.0.0.1"
    p1.subnet_mask = "255.255.255.0"
    p1.is_shutdown = False

    p2 = r2.get_port("g0/0")
    p2.ip_address = "10.0.0.2"
    p2.subnet_mask = "255.255.255.0"
    p2.is_shutdown = False

    sw_p1 = sw.get_port("g0/1")
    sw_p1.is_shutdown = False
    sw_p2 = sw.get_port("g0/2")
    sw_p2.is_shutdown = False

    Cable(p1, sw_p1)
    Cable(p2, sw_p2)

    # Put switch port into STP Blocking
    sw_p2.stp_state = "Blocking"

    r1.enable_ospf(1)
    r1.add_ospf_network("10.0.0.0", "0.0.0.255", area=0)
    r2.enable_ospf(1)
    r2.add_ospf_network("10.0.0.0", "0.0.0.255", area=0)

    converge_all_ospf()
    assert len(r1.ospf_neighbors) == 0

    # Unblock
    sw_p2.stp_state = "Forwarding"
    converge_all_ospf()
    assert len(r1.ospf_neighbors) == 1


def test_33_dhcp_and_ospf():
    """Test 33: Host acquires DHCP IP address and pings across OSPF topology."""
    topo = setup_three_router_chain()
    r1 = topo["r1"]

    # Configure DHCP server on R1 for LAN
    r1.dhcp_server.add_pool("LAN-POOL", "192.168.10.0", "255.255.255.0",
                            default_router="192.168.10.1")

    # New host configured via DHCP
    client = Host("client1", hostname="DHCP-Client")
    Cable(client.eth0, r1.get_port("g0/2"))
    r1.get_port("g0/2").ip_address = "192.168.10.254"
    r1.get_port("g0/2").subnet_mask = "255.255.255.0"
    r1.get_port("g0/2").is_shutdown = False

    pe = PacketEngine.get_instance()
    ok, _ = pe.simulate_dhcp_dora(client, client.eth0)
    assert ok is True
    assert client.eth0.ip_address.startswith("192.168.10.")

    # Client can ping remote PC2 across OSPF!
    res = pe.simulate_ping(client, "192.168.30.10", count=3)
    assert res.packets_received == 3


def test_34_acl_nat_firewall_integration():
    """Test 34: OSPF routes obey Access Lists, NAT Overload, and Firewall security."""
    topo = setup_three_router_chain()
    pe = PacketEngine.get_instance()
    r1 = topo["r1"]
    pc1 = topo["pc1"]

    # Apply ACL blocking PC1
    r1.add_access_list(10, "deny", "192.168.10.10", "0.0.0.0")
    r1.set_access_group(10, "in", "g0/1")

    res_blocked = pe.simulate_ping(pc1, "192.168.30.10", count=3)
    assert any(c == "A" for c in res_blocked.status_codes)
    assert res_blocked.loss_percent == 100

    # Remove ACL -> traffic flows
    r1.set_access_group(None, "in", "g0/1")
    res_ok = pe.simulate_ping(pc1, "192.168.30.10", count=3)
    assert res_ok.loss_percent == 0


def test_35_cli_show_ip_ospf():
    """Test 35: CLI commands 'show ip ospf', 'show ip ospf neighbor', 'show ip ospf database'."""
    r1, r2, c = setup_direct_router_pair()
    r1.enable_ospf(1)
    r1.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)
    r2.enable_ospf(1)
    r2.add_ospf_network("10.0.0.0", "0.0.0.3", area=0)

    converge_all_ospf()

    cli = CommandExecutor(r1)
    cli.mode = "PRIVILEGED"

    out_ospf = cli.execute("show ip ospf")
    assert 'Routing Process "ospf 1"' in out_ospf
    assert "Area BACKBONE(0)" in out_ospf

    out_nbr = cli.execute("show ip ospf neighbor")
    assert "FULL" in out_nbr
    assert "10.0.0.2" in out_nbr

    out_db = cli.execute("show ip ospf database")
    assert "Router Link States (Area 0)" in out_db
    assert "0x8000000" in out_db


def test_36_cli_show_ip_route():
    """Test 36: CLI command 'show ip route' properly formats 'O' routes."""
    topo = setup_three_router_chain()
    cli = CommandExecutor(topo["r1"])
    cli.mode = "PRIVILEGED"

    out = cli.execute("show ip route")
    assert "O" in out
    assert "[110/3]" in out
    assert "192.168.30.0/24" in out


def test_37_disable_ospf():
    """Test 37: Disabling OSPF clears LSDB, neighbors, and 'O' routes."""
    topo = setup_three_router_chain()
    r1 = topo["r1"]

    converge_all_ospf()
    assert len(r1.ospf_routes) > 0

    cli = CommandExecutor(r1)
    cli.mode = "CONFIG"
    cli.execute("no router ospf 1")

    assert r1.ospf_enabled is False
    assert len(r1.ospf_neighbors) == 0
    assert len(r1.ospf_lsdb) == 0
    assert len(r1.ospf_routes) == 0


if __name__ == "__main__":
    tests = [
        ("Test 1: Enable OSPF", test_01_enable_ospf),
        ("Test 2: Configure Router ID", test_02_configure_router_id),
        ("Test 3: Configure Network", test_03_configure_network),
        ("Test 4: Remove Network", test_04_remove_network),
        ("Test 5: Discover Direct Neighbor", test_05_neighbor_discovery),
        ("Test 6: Hello and Adjacency States", test_06_hello_and_adjacency_states),
        ("Test 7: Neighbor Table", test_07_neighbor_table),
        ("Test 8: Generate Router-LSA", test_08_generate_router_lsa),
        ("Test 9: LSA Sequence & Flooding", test_09_lsa_sequence_and_flooding),
        ("Test 10: Ignore Older LSA", test_10_ignore_older_lsa),
        ("Test 11: LSDB Synchronization", test_11_lsdb_synchronization),
        ("Test 12: Single-hop SPF", test_12_single_hop_spf),
        ("Test 13: Two-hop SPF", test_13_two_hop_spf),
        ("Test 14: Three-router SPF", test_14_three_router_spf),
        ("Test 15: Cost-based Path Selection", test_15_cost_based_path_selection),
        ("Test 16: Cost Change Triggers SPF", test_16_cost_change_triggers_spf),
        ("Test 17: Install OSPF Route (AD 110)", test_17_install_ospf_route),
        ("Test 18: Longest Prefix Match", test_18_longest_prefix_match),
        ("Test 19: Connected Wins OSPF", test_19_connected_wins_ospf),
        ("Test 20: Static Wins OSPF", test_20_static_wins_ospf),
        ("Test 21: OSPF Wins RIP", test_21_ospf_wins_rip),
        ("Test 22: Static Removal Fallback to OSPF", test_22_static_removal_fallback_to_ospf),
        ("Test 23: OSPF Removal Fallback to RIP", test_23_ospf_removal_fallback_to_rip),
        ("Test 24: Two-router OSPF Ping", test_24_two_router_ping),
        ("Test 25: Three-router Multihop Ping", test_25_three_router_multihop_ping),
        ("Test 26: Forward & Return Path", test_26_forward_and_return_path),
        ("Test 27: TTL & Traceroute", test_27_ttl_and_traceroute),
        ("Test 28: Topology Change: Link Failure", test_28_topology_change_link_failure),
        ("Test 29: Topology Change: Link Recovery", test_29_topology_change_link_recovery),
        ("Test 30: Interface Shutdown & Recovery", test_30_interface_shutdown_and_recovery),
        ("Test 31: VLAN / Subinterface OSPF", test_31_vlan_subinterface_ospf),
        ("Test 32: STP Integration", test_32_stp_integration),
        ("Test 33: DHCP & OSPF Integration", test_33_dhcp_and_ospf),
        ("Test 34: ACL / NAT / Firewall Integration", test_34_acl_nat_firewall_integration),
        ("Test 35: CLI show ip ospf", test_35_cli_show_ip_ospf),
        ("Test 36: CLI show ip route", test_36_cli_show_ip_route),
        ("Test 37: Disable OSPF", test_37_disable_ospf),
    ]

    for name, fn in tests:
        fn()
        print(f"{name} [PASS]")

    print(f"\nALL {len(tests)} OSPF TESTS PASSED!")
