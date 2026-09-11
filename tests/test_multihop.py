"""
tests/test_multihop.py - Multi-hop End-to-End Network Core Tests & Failure Scenarios (Phases L & M)
Topology:
  PC1 (192.168.1.10/24, GW: 192.168.1.1)
    | [eth0 <-> g0/1]
  SW1 (Switch-1, VLAN 1)
    | [g0/2 <-> g0/0]
  R1 (Router-1, g0/0: 192.168.1.1/24, g0/1: 10.0.12.1/30)
    | [g0/1 <-> g0/0]
  R2 (Router-2, g0/0: 10.0.12.2/30, g0/1: 192.168.2.1/24)
    | [g0/1 <-> g0/1]
  SW2 (Switch-2, VLAN 1)
    | [g0/2 <-> eth0]
  PC2 (192.168.2.10/24, GW: 192.168.2.1)

Validates:
1. End-to-end bidirectional ping (PC1 -> PC2 and PC2 -> PC1) with 0% loss.
2. Hop-by-hop path tracing traversing all 6 devices.
3. TTL decrement across two Layer 3 routers (64 -> 63 -> 62).
4. Layer 2 Switch MAC learning (both switches learn correct host and router ports).
5. Layer 3 Router ARP caching on transit and edge links.
6. Failure Case: Link down / interface shutdown between R1 and R2 ('U' status).
7. Failure Case: Missing return route on R2 ('U' destination unreachable).
8. Failure Case: Invalid next-hop IP on R1.
9. Failure Case: VLAN mismatch on SW1 (drops at Layer 2).
10. Failure Case: Router ACL blocking on R1 ('A' administratively prohibited).
11. Multi-hop with intermediate stateful Firewall inspection.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.router import Router
from network.switch import Switch
from network.host import Host
from network.firewall import Firewall
from network.cable import Cable, CableType
from network.packet_engine import PacketEngine

def build_multihop_topology():
    """Builds and returns the standard 6-device multi-hop topology."""
    pc1 = Host("pc1", hostname="PC-1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    sw1 = Switch("sw1", hostname="Switch-1")

    r1 = Router("r1", hostname="Router-1")
    p0 = r1.get_port("g0/0")
    p0.ip_address = "192.168.1.1"
    p0.subnet_mask = "255.255.255.0"
    p0.is_shutdown = False

    p1 = r1.get_port("g0/1")
    p1.ip_address = "10.0.12.1"
    p1.subnet_mask = "255.255.255.252"
    p1.is_shutdown = False

    r2 = Router("r2", hostname="Router-2")
    r2_p0 = r2.get_port("g0/0")
    r2_p0.ip_address = "10.0.12.2"
    r2_p0.subnet_mask = "255.255.255.252"
    r2_p0.is_shutdown = False

    r2_p1 = r2.get_port("g0/1")
    r2_p1.ip_address = "192.168.2.1"
    r2_p1.subnet_mask = "255.255.255.0"
    r2_p1.is_shutdown = False

    sw2 = Switch("sw2", hostname="Switch-2")

    pc2 = Host("pc2", hostname="PC-2")
    pc2.configure_ip("192.168.2.10", "255.255.255.0", gateway="192.168.2.1")

    # Static Routing
    r1.add_static_route("192.168.2.0", "255.255.255.0", "10.0.12.2")
    r2.add_static_route("192.168.1.0", "255.255.255.0", "10.0.12.1")

    # Cabling
    c1 = Cable(pc1.eth0, sw1.get_port("g0/1"), CableType.CAT6)
    c2 = Cable(sw1.get_port("g0/2"), r1.get_port("g0/0"), CableType.CAT6)
    c3 = Cable(r1.get_port("g0/1"), r2.get_port("g0/0"), CableType.CAT6)
    c4 = Cable(r2.get_port("g0/1"), sw2.get_port("g0/1"), CableType.CAT6)
    c5 = Cable(sw2.get_port("g0/2"), pc2.eth0, CableType.CAT6)

    return {
        "pc1": pc1, "sw1": sw1, "r1": r1,
        "r2": r2, "sw2": sw2, "pc2": pc2,
        "cables": [c1, c2, c3, c4, c5]
    }

def test_multihop_end_to_end_ping_and_ttl():
    pe = PacketEngine.get_instance()
    topo = build_multihop_topology()
    pc1, sw1, r1 = topo["pc1"], topo["sw1"], topo["r1"]
    r2, sw2, pc2 = topo["r2"], topo["sw2"], topo["pc2"]

    # 1. Forward Ping: PC1 -> PC2
    res_fwd = pe.simulate_ping(pc1, "192.168.2.10", count=5, simulate_arp=False)
    assert res_fwd.loss_percent == 0, f"Expected 0% loss PC1->PC2, got {res_fwd.loss_percent}% (status: {res_fwd.status_codes})"
    assert res_fwd.packets_received == 5
    assert all(c == "!" for c in res_fwd.status_codes)

    # Verify TTL: Host initial 64 - 2 routers (R1, R2) = 62
    assert all(ttl == 62 for ttl in res_fwd.ttl_replies), f"Expected TTL 62, got {res_fwd.ttl_replies}"

    # Verify Hop Path contains all 6 devices
    expected_hops = ["PC-1", "Switch-1", "Router-1", "Router-2", "Switch-2", "PC-2"]
    assert res_fwd.hop_path == expected_hops, f"Expected {expected_hops}, got {res_fwd.hop_path}"

    # 2. Reverse Ping: PC2 -> PC1
    res_rev = pe.simulate_ping(pc2, "192.168.1.10", count=5, simulate_arp=False)
    assert res_rev.loss_percent == 0, f"Expected 0% loss PC2->PC1, got {res_rev.loss_percent}%"
    assert all(ttl == 62 for ttl in res_rev.ttl_replies)
    assert res_rev.hop_path == ["PC-2", "Switch-2", "Router-2", "Router-1", "Switch-1", "PC-1"]

    # 3. Verify Switch MAC Learning
    assert pc1.eth0.mac_address in sw1.mac_table
    assert sw1.mac_table[pc1.eth0.mac_address]["port"] == "g0/1"
    assert r1.get_port("g0/0").mac_address in sw1.mac_table
    assert sw1.mac_table[r1.get_port("g0/0").mac_address]["port"] == "g0/2"

    assert pc2.eth0.mac_address in sw2.mac_table
    assert sw2.mac_table[pc2.eth0.mac_address]["port"] == "g0/2"
    assert r2.get_port("g0/1").mac_address in sw2.mac_table
    assert sw2.mac_table[r2.get_port("g0/1").mac_address]["port"] == "g0/1"

    # 4. Verify Router ARP Tables
    assert r1.lookup_arp("192.168.1.10") is not None
    assert r1.lookup_arp("10.0.12.2") is not None
    assert r2.lookup_arp("10.0.12.1") is not None
    assert r2.lookup_arp("192.168.2.10") is not None

def test_failure_link_down_between_routers():
    pe = PacketEngine.get_instance()
    topo = build_multihop_topology()
    pc1, r1 = topo["pc1"], topo["r1"]

    # Shut down transit interface between R1 and R2
    r1.get_port("g0/1").is_shutdown = True

    res_down = pe.simulate_ping(pc1, "192.168.2.10", count=3)
    assert res_down.loss_percent == 100, f"Expected 100% loss on link down, got {res_down.loss_percent}%"
    assert any(c == "U" for c in res_down.status_codes)
    assert res_down.error_message is not None

    # Bring transit interface back UP
    r1.get_port("g0/1").is_shutdown = False
    res_up = pe.simulate_ping(pc1, "192.168.2.10", count=3)
    assert res_up.loss_percent == 0, f"Expected recovery after link UP, got {res_up.loss_percent}%"

def test_failure_missing_return_route():
    pe = PacketEngine.get_instance()
    topo = build_multihop_topology()
    pc1, r2 = topo["pc1"], topo["r2"]

    # Remove return static route on R2 back to 192.168.1.0/24
    r2.remove_static_route("192.168.1.0", "255.255.255.0")

    # Ping from PC1 to PC2: Echo Request reaches PC2, but R2 cannot route Echo Reply back
    res = pe.simulate_ping(pc1, "192.168.2.10", count=3)
    assert res.loss_percent == 100
    assert any(c == "U" for c in res.status_codes)
    assert "no route back to 192.168.1.10" in res.error_message.lower() or "no route" in res.error_message.lower()

    # Restore route: ping succeeds
    r2.add_static_route("192.168.1.0", "255.255.255.0", "10.0.12.1")
    res_ok = pe.simulate_ping(pc1, "192.168.2.10", count=3)
    assert res_ok.loss_percent == 0

def test_failure_invalid_next_hop():
    pe = PacketEngine.get_instance()
    topo = build_multihop_topology()
    pc1, r1 = topo["pc1"], topo["r1"]

    # Point R1 static route to unreachable next hop
    r1.add_static_route("192.168.2.0", "255.255.255.0", "10.0.99.2")

    res = pe.simulate_ping(pc1, "192.168.2.10", count=3)
    assert res.loss_percent == 100
    assert any(c in (".", "U") for c in res.status_codes)

    # Restore valid route
    r1.add_static_route("192.168.2.0", "255.255.255.0", "10.0.12.2")
    res_ok = pe.simulate_ping(pc1, "192.168.2.10", count=3)
    assert res_ok.loss_percent == 0

def test_failure_vlan_mismatch_on_switch():
    pe = PacketEngine.get_instance()
    topo = build_multihop_topology()
    pc1, sw1 = topo["pc1"], topo["sw1"]

    # Move PC1's switch port into VLAN 99, while Router port remains in VLAN 1
    sw1.add_vlan(99, "Isolated")
    sw1.get_port("g0/1").access_vlan = 99

    res = pe.simulate_ping(pc1, "192.168.2.10", count=3)
    assert res.loss_percent == 100, f"Expected 100% loss due to VLAN mismatch, got {res.loss_percent}%"

    # Restore VLAN 1
    sw1.get_port("g0/1").access_vlan = 1
    res_ok = pe.simulate_ping(pc1, "192.168.2.10", count=3)
    assert res_ok.loss_percent == 0

def test_failure_router_acl_blocking():
    pe = PacketEngine.get_instance()
    topo = build_multihop_topology()
    pc1, r1 = topo["pc1"], topo["r1"]

    # Deny PC1 via inbound standard ACL on R1 g0/0
    r1.add_access_list(10, "deny", "192.168.1.10", "0.0.0.0")
    r1.set_access_group(10, "in", "g0/0")

    res_blocked = pe.simulate_ping(pc1, "192.168.2.10", count=3)
    assert res_blocked.loss_percent == 100
    assert any(c == "A" for c in res_blocked.status_codes), f"Expected 'A' status code for ACL drop, got {res_blocked.status_codes}"
    assert "access-list 10" in res_blocked.error_message.lower() or "10" in res_blocked.error_message.lower()

    # Remove ACL
    r1.set_access_group(None, "in", "g0/0")
    res_ok = pe.simulate_ping(pc1, "192.168.2.10", count=3)
    assert res_ok.loss_percent == 0

def test_multihop_with_intermediate_firewall():
    """
    Topology with Firewall between R1 and R2:
    PC1 <-> SW1 <-> R1 <-> FW1 <-> R2 <-> SW2 <-> PC2
    """
    pe = PacketEngine.get_instance()

    pc1 = Host("pc1", hostname="PC-1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    sw1 = Switch("sw1", hostname="Switch-1")

    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/0").ip_address = "192.168.1.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.0"
    r1.get_port("g0/0").is_shutdown = False
    r1.get_port("g0/1").ip_address = "10.0.10.1"
    r1.get_port("g0/1").subnet_mask = "255.255.255.252"
    r1.get_port("g0/1").is_shutdown = False

    # Firewall between R1 and R2
    fw1 = Firewall("fw1", hostname="Firewall-1")
    fw1.get_port("g0/0").ip_address = "10.0.10.2"
    fw1.get_port("g0/0").subnet_mask = "255.255.255.252"
    fw1.get_port("g0/0").is_shutdown = False
    fw1.get_port("g0/1").ip_address = "10.0.20.1"
    fw1.get_port("g0/1").subnet_mask = "255.255.255.252"
    fw1.get_port("g0/1").is_shutdown = False

    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.20.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.get_port("g0/1").ip_address = "192.168.2.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.0"
    r2.get_port("g0/1").is_shutdown = False

    sw2 = Switch("sw2", hostname="Switch-2")

    pc2 = Host("pc2", hostname="PC-2")
    pc2.configure_ip("192.168.2.10", "255.255.255.0", gateway="192.168.2.1")

    # Routing
    r1.add_static_route("192.168.2.0", "255.255.255.0", "10.0.10.2")
    fw1.add_static_route("192.168.2.0", "255.255.255.0", "10.0.20.2")
    fw1.add_static_route("192.168.1.0", "255.255.255.0", "10.0.10.1")
    r2.add_static_route("192.168.1.0", "255.255.255.0", "10.0.20.1")

    # Cabling
    c1 = Cable(pc1.eth0, sw1.get_port("g0/1"), CableType.CAT6)
    c2 = Cable(sw1.get_port("g0/2"), r1.get_port("g0/0"), CableType.CAT6)
    c3 = Cable(r1.get_port("g0/1"), fw1.get_port("g0/0"), CableType.CAT6)
    c4 = Cable(fw1.get_port("g0/1"), r2.get_port("g0/0"), CableType.CAT6)
    c5 = Cable(r2.get_port("g0/1"), sw2.get_port("g0/1"), CableType.CAT6)
    c6 = Cable(sw2.get_port("g0/2"), pc2.eth0, CableType.CAT6)

    # Firewall zone configuration: g0/0 is inside (facing R1/PC1), g0/1 is outside (facing R2/PC2)
    fw1.set_nameif("g0/0", "inside")
    fw1.set_security_level("inside", 100)
    fw1.set_nameif("g0/1", "outside")
    fw1.set_security_level("outside", 0)

    # 1. Outbound ping across firewall permitted statefully by default
    res = pe.simulate_ping(pc1, "192.168.2.10", count=3)
    assert res.loss_percent == 0, f"Expected 0% loss across firewall, got {res.loss_percent}% (error: {res.error_message})"

    # 2. Add firewall deny rule for ICMP on inside interface
    fw1.add_access_list("BLOCK_ICMP", "deny", "icmp", "any", "any")
    fw1.set_access_group("BLOCK_ICMP", "in", "inside")
    res_denied = pe.simulate_ping(pc1, "192.168.2.10", count=2)
    assert res_denied.loss_percent == 100
    assert any(c == "A" for c in res_denied.status_codes)

    # 3. Remove firewall rule: recovery
    fw1.set_access_group(None, "in", "inside")
    res_restored = pe.simulate_ping(pc1, "192.168.2.10", count=2)
    assert res_restored.loss_percent == 0

if __name__ == "__main__":
    test_multihop_end_to_end_ping_and_ttl()
    test_failure_link_down_between_routers()
    test_failure_missing_return_route()
    test_failure_invalid_next_hop()
    test_failure_vlan_mismatch_on_switch()
    test_failure_router_acl_blocking()
    test_multihop_with_intermediate_firewall()
    print("ALL MULTI-HOP & FAILURE SCENARIO TESTS PASSED!")
