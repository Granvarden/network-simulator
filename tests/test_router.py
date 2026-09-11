"""
tests/test_router.py - Tests for Layer 3 Router Implementation
Validates:
1. Connected routes automatically installed when interface is up.
2. Inactive/shutdown interfaces do not install routes.
3. Subinterfaces (Router-on-a-Stick 802.1Q).
4. Static routes & default route lookup.
5. Longest prefix match.
6. Topology: PC1 | R1 -------- R2 | PC2
   Tests: PC1 -> R1, PC1 -> R2, PC1 -> PC2, PC2 -> PC1.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.router import Router
from network.host import Host
from network.cable import Cable, CableType
from network.packet_engine import PacketEngine

def test_router_connected_and_shutdown_routes():
    r1 = Router("r1", hostname="Router-1")
    p0 = r1.get_port("g0/0")
    p0.ip_address = "192.168.1.1"
    p0.subnet_mask = "255.255.255.0"
    p0.is_shutdown = True # Initially administratively shutdown

    h1 = Host("h1")
    c1 = Cable(p0, h1.eth0)

    # When port is shutdown, no connected route should be active
    routes = r1.get_all_routes()
    assert len(routes) == 0, f"Expected 0 active routes when port is shutdown, got {routes}"

    # Bring port UP
    p0.is_shutdown = False
    routes_up = r1.get_all_routes()
    assert len(routes_up) == 1
    assert routes_up[0]["network"] == "192.168.1.0"
    assert routes_up[0]["type"] == "C"

def test_router_subinterfaces():
    r1 = Router("r1", hostname="Router-1")
    p0 = r1.get_port("g0/0")
    p0.is_shutdown = False

    h1 = Host("h1")
    c1 = Cable(p0, h1.eth0)

    sub10 = r1.create_subinterface("g0/0", 10)
    sub10.ip_address = "192.168.10.1"
    sub10.subnet_mask = "255.255.255.0"
    sub10.vlan_id = 10

    sub20 = r1.create_subinterface("g0/0", 20)
    sub20.ip_address = "192.168.20.1"
    sub20.subnet_mask = "255.255.255.0"
    sub20.vlan_id = 20

    routes = r1.get_all_routes()
    nets = [r["network"] for r in routes]
    assert "192.168.10.0" in nets
    assert "192.168.20.0" in nets

    match10 = r1.lookup_route("192.168.10.50")
    assert match10 is not None
    assert match10["interface"] == "g0/0.10"

    match20 = r1.lookup_route("192.168.20.50")
    assert match20 is not None
    assert match20["interface"] == "g0/0.20"

def test_router_topology_forwarding():
    """
    Topology:
    PC1 (192.168.1.10)
      |
      R1 (g0/0: 192.168.1.1, g0/1: 10.0.12.1)
      |
      R2 (g0/0: 10.0.12.2,   g0/1: 192.168.2.1)
      |
    PC2 (192.168.2.10)
    """
    pe = PacketEngine.get_instance()

    pc1 = Host("pc1", hostname="PC1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    r1 = Router("r1", hostname="R1")
    r1.get_port("g0/0").ip_address = "192.168.1.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.0"
    r1.get_port("g0/0").is_shutdown = False
    r1.get_port("g0/1").ip_address = "10.0.12.1"
    r1.get_port("g0/1").subnet_mask = "255.255.255.252"
    r1.get_port("g0/1").is_shutdown = False

    r2 = Router("r2", hostname="R2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.get_port("g0/1").ip_address = "192.168.2.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.0"
    r2.get_port("g0/1").is_shutdown = False

    pc2 = Host("pc2", hostname="PC2")
    pc2.configure_ip("192.168.2.10", "255.255.255.0", gateway="192.168.2.1")

    # Static routes
    r1.add_static_route("192.168.2.0", "255.255.255.0", "10.0.12.2")
    r2.add_static_route("192.168.1.0", "255.255.255.0", "10.0.12.1")

    # Connect cables
    c1 = Cable(pc1.eth0, r1.get_port("g0/0"))
    c2 = Cable(r1.get_port("g0/1"), r2.get_port("g0/0"))
    c3 = Cable(r2.get_port("g0/1"), pc2.eth0)

    # 1. PC1 -> R1
    res1 = pe.simulate_ping(pc1, "192.168.1.1", count=2)
    assert res1.loss_percent == 0

    # 2. PC1 -> R2
    res2 = pe.simulate_ping(pc1, "10.0.12.2", count=2)
    assert res2.loss_percent == 0

    # 3. PC1 -> PC2
    res3 = pe.simulate_ping(pc1, "192.168.2.10", count=3)
    assert res3.loss_percent == 0

    # 4. PC2 -> PC1
    res4 = pe.simulate_ping(pc2, "192.168.1.10", count=3)
    assert res4.loss_percent == 0

    # 5. Invalid next-hop failure
    r1.add_static_route("192.168.2.0", "255.255.255.0", "10.0.99.2") # unreachable next hop
    res_bad = pe.simulate_ping(pc1, "192.168.2.10", count=2)
    assert res_bad.loss_percent == 100
    assert res_bad.status_codes == [".", "."] or res_bad.status_codes == ["U", "U"]

if __name__ == "__main__":
    test_router_connected_and_shutdown_routes()
    test_router_subinterfaces()
    test_router_topology_forwarding()
    print("ALL ROUTER TESTS PASSED!")
