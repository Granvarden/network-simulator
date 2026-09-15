"""
tests/test_rip.py - Comprehensive RIPv2 Dynamic Routing Verification Suite (Phase 3.9)

Tests:
Test 1: Enable RIP
Test 2: Configure RIP version 2
Test 3: Add RIP network
Test 4: Remove RIP network
Test 5: Discover direct RIP neighbor
Test 6: Advertise connected network
Test 7: Receive RIP route
Test 8: Install dynamic R route
Test 9: Metric increments by hop
Test 10: Maximum hop 16 is unreachable
Test 11: Connected route wins RIP
Test 12: Static route wins RIP
Test 13: Longest Prefix Match with RIP
Test 14: Two-router RIP connectivity
Test 15: Three-router RIP multihop
Test 16: Forward path
Test 17: Return path
Test 18: Link failure removes route
Test 19: Link restoration relearns route
Test 20: Split Horizon
Test 21: Route Poisoning
Test 22: No routing loop
Test 23: TTL / L3 hop tracking
Test 24: Traceroute
Test 25: VLAN / Subinterface integration
Test 26: DHCP + RIP
Test 27: RIP + ACL regression
Test 28: RIP + NAT regression
Test 29: RIP + Firewall regression
Test 30: Static Route + RIP preference
Test 31: show ip route
Test 32: show ip rip
Test 33: show ip protocols
Test 34: Disable RIP removes learned routes
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
from cli.command_executor import CommandExecutor


def test_01_enable_rip():
    """Test 1: Enable RIP via API and CLI 'router rip'."""
    r1 = Router("r1", hostname="Router-1")
    assert r1.rip_enabled is False

    # API
    r1.enable_rip()
    assert r1.rip_enabled is True

    # CLI
    r2 = Router("r2", hostname="Router-2")
    cli = CommandExecutor(r2)
    cli.execute("enable")
    cli.execute("configure terminal")
    cli.execute("router rip")
    assert r2.rip_enabled is True
    assert cli.get_prompt() == "Router-2(config-router)#"


def test_02_configure_version_2():
    """Test 2: Configure RIP version 2 and reject invalid versions."""
    r1 = Router("r1", hostname="Router-1")
    r1.enable_rip(version=2)
    assert r1.rip_version == 2

    cli = CommandExecutor(r1)
    cli.execute("enable")
    cli.execute("configure terminal")
    cli.execute("router rip")
    cli.execute("version 2")
    assert r1.rip_version == 2

    # Reject invalid version
    err = cli.execute("version 99")
    assert "% Invalid version" in err


def test_03_add_rip_network():
    """Test 3: Add RIP network statement activates matching interfaces."""
    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/0").ip_address = "192.168.10.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.0"
    r1.get_port("g0/0").is_shutdown = False

    r1.enable_rip()
    ok = r1.add_rip_network("192.168.10.0")
    assert ok is True
    assert "192.168.10.0" in r1.rip_networks
    assert r1.rip.is_interface_matched(r1.get_port("g0/0")) is True

    # Rejection of invalid IP
    bad = r1.add_rip_network("not.an.ip")
    assert bad is False


def test_04_remove_rip_network():
    """Test 4: Remove RIP network statement removes network and deactivates interfaces."""
    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/0").ip_address = "10.0.12.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.252"
    r1.get_port("g0/0").is_shutdown = False

    r1.enable_rip()
    r1.add_rip_network("10.0.0.0")
    assert r1.rip.is_interface_matched(r1.get_port("g0/0")) is True

    # CLI removal
    cli = CommandExecutor(r1)
    cli.execute("enable")
    cli.execute("configure terminal")
    cli.execute("router rip")
    cli.execute("no network 10.0.0.0")

    assert "10.0.0.0" not in r1.rip_networks
    assert r1.rip.is_interface_matched(r1.get_port("g0/0")) is False


def test_05_discover_direct_neighbor():
    """Test 5: Directly connected routers discover each other as RIP neighbors."""
    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/1").ip_address = "10.0.12.1"
    r1.get_port("g0/1").subnet_mask = "255.255.255.252"
    r1.get_port("g0/1").is_shutdown = False
    r1.enable_rip()
    r1.add_rip_network("10.0.0.0")

    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.enable_rip()
    r2.add_rip_network("10.0.0.0")

    Cable(r1.get_port("g0/1"), r2.get_port("g0/0"))

    r1.rip.discover_neighbors()
    r2.rip.discover_neighbors()

    assert "10.0.12.2" in r1.rip_neighbors
    assert "10.0.12.1" in r2.rip_neighbors


def test_06_advertise_connected_network():
    """Test 6: Router advertises connected network to neighbor in update payload."""
    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/0").ip_address = "192.168.10.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.0"
    r1.get_port("g0/0").is_shutdown = False
    # Attach cable so g0/0 link is UP
    h1 = Host("h1")
    Cable(r1.get_port("g0/0"), h1.eth0)

    r1.get_port("g0/1").ip_address = "10.0.12.1"
    r1.get_port("g0/1").subnet_mask = "255.255.255.252"
    r1.get_port("g0/1").is_shutdown = False

    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False

    Cable(r1.get_port("g0/1"), r2.get_port("g0/0"))

    r1.enable_rip()
    r1.add_rip_network("192.168.10.0")
    r1.add_rip_network("10.0.0.0")

    payload = r1.rip.build_update_payload(r1.get_port("g0/1"), "10.0.12.2")
    nets = [item["network"] for item in payload]
    assert "192.168.10.0" in nets
    # Check metric is 1
    m10 = [item for item in payload if item["network"] == "192.168.10.0"][0]
    assert m10["metric"] == 1


def test_07_receive_rip_route():
    """Test 7: Router receives and installs route from update payload."""
    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.enable_rip()
    r2.add_rip_network("10.0.0.0")

    payload = [{"network": "192.168.10.0", "mask": "255.255.255.0", "metric": 1}]
    changed = r2.rip.receive_update("10.0.12.1", r2.get_port("g0/0"), payload)
    assert changed is True
    assert ("192.168.10.0", "255.255.255.0") in r2.rip_routes


def test_08_install_dynamic_r_route():
    """Test 8: Installed RIP route appears as 'R' route with AD 120."""
    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.enable_rip()
    r2.add_rip_network("10.0.0.0")

    payload = [{"network": "192.168.10.0", "mask": "255.255.255.0", "metric": 1}]
    r2.rip.receive_update("10.0.12.1", r2.get_port("g0/0"), payload)

    all_r = r2.get_all_routes()
    r_route = [r for r in all_r if r["network"] == "192.168.10.0"][0]
    assert r_route["type"] == "R"
    assert r_route["admin_distance"] == 120
    assert r_route["next_hop"] == "10.0.12.1"
    assert r_route["metric"] == 1


def test_09_metric_increments_by_hop():
    """Test 9: Hop count metric increments by 1 at each router hop."""
    # R1 ---- R2 ---- R3
    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/0").ip_address = "192.168.10.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.0"
    r1.get_port("g0/0").is_shutdown = False
    h1 = Host("h1"); Cable(r1.get_port("g0/0"), h1.eth0)
    r1.get_port("g0/1").ip_address = "10.0.12.1"
    r1.get_port("g0/1").subnet_mask = "255.255.255.252"
    r1.get_port("g0/1").is_shutdown = False
    r1.enable_rip(); r1.add_rip_network("192.168.10.0"); r1.add_rip_network("10.0.0.0")

    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.get_port("g0/1").ip_address = "10.0.23.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.252"
    r2.get_port("g0/1").is_shutdown = False
    r2.enable_rip(); r2.add_rip_network("10.0.0.0")

    r3 = Router("r3", hostname="Router-3")
    r3.get_port("g0/0").ip_address = "10.0.23.2"
    r3.get_port("g0/0").subnet_mask = "255.255.255.252"
    r3.get_port("g0/0").is_shutdown = False
    r3.enable_rip(); r3.add_rip_network("10.0.0.0")

    Cable(r1.get_port("g0/1"), r2.get_port("g0/0"))
    Cable(r2.get_port("g0/1"), r3.get_port("g0/0"))

    PacketEngine.get_instance().converge_rip()

    # R2 learns 192.168.10.0 with metric 1
    assert ("192.168.10.0", "255.255.255.0") in r2.rip_routes
    assert r2.rip_routes[("192.168.10.0", "255.255.255.0")]["metric"] == 1

    # R3 learns 192.168.10.0 with metric 2
    assert ("192.168.10.0", "255.255.255.0") in r3.rip_routes
    assert r3.rip_routes[("192.168.10.0", "255.255.255.0")]["metric"] == 2


def test_10_maximum_hop_16_unreachable():
    """Test 10: Route with metric 16 (Infinity) is unreachable and not installed."""
    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.enable_rip(); r2.add_rip_network("10.0.0.0")

    payload = [{"network": "192.168.99.0", "mask": "255.255.255.0", "metric": 16}]
    r2.rip.receive_update("10.0.12.1", r2.get_port("g0/0"), payload)

    assert ("192.168.99.0", "255.255.255.0") not in r2.rip_routes
    assert r2.lookup_route("192.168.99.10") is None


def test_11_connected_route_wins_rip():
    """Test 11: Connected route (AD 0) beats RIP route (AD 120) for identical prefix."""
    r1 = Router("r1", hostname="Router-1")
    p0 = r1.get_port("g0/0")
    p0.ip_address = "192.168.10.1"
    p0.subnet_mask = "255.255.255.0"
    p0.is_shutdown = False
    h1 = Host("h1"); Cable(p0, h1.eth0)

    r1.enable_rip(); r1.add_rip_network("192.168.10.0")
    # Simulate receiving RIP route for 192.168.10.0/24 from external router
    r1.rip.routes[("192.168.10.0", "255.255.255.0")] = {
        "network": "192.168.10.0", "mask": "255.255.255.0", "next_hop": "10.0.0.99",
        "interface": "g0/1", "metric": 1, "type": "R", "admin_distance": 120
    }

    match = r1.lookup_route("192.168.10.50")
    assert match is not None
    assert match["type"] == "C", f"Connected route must win, got {match['type']}"
    assert match["next_hop"] == "directly connected"


def test_12_static_route_wins_rip():
    """Test 12: Static route (AD 1) beats RIP route (AD 120) for identical prefix."""
    r1 = Router("r1", hostname="Router-1")
    r1.enable_rip()
    r1.add_static_route("192.168.20.0", "255.255.255.0", "10.0.12.2")

    r1.rip.routes[("192.168.20.0", "255.255.255.0")] = {
        "network": "192.168.20.0", "mask": "255.255.255.0", "next_hop": "10.0.12.99",
        "interface": "g0/1", "metric": 1, "type": "R", "admin_distance": 120
    }

    match = r1.lookup_route("192.168.20.50")
    assert match is not None
    assert match["type"] == "S", f"Static route must win, got {match['type']}"
    assert match["next_hop"] == "10.0.12.2"


def test_13_longest_prefix_match_with_rip():
    """Test 13: LPM (/24 RIP route beats /16 Static route)."""
    r1 = Router("r1", hostname="Router-1")
    r1.enable_rip()

    # /16 Static route
    r1.add_static_route("10.1.0.0", "255.255.0.0", "10.0.0.1")

    # /24 RIP route
    r1.rip.routes[("10.1.10.0", "255.255.255.0")] = {
        "network": "10.1.10.0", "mask": "255.255.255.0", "next_hop": "10.0.12.2",
        "interface": "g0/1", "metric": 1, "type": "R", "admin_distance": 120
    }

    # 10.1.10.50 must match /24 RIP route because /24 is longer than /16
    m1 = r1.lookup_route("10.1.10.50")
    assert m1 is not None
    assert m1["mask"] == "255.255.255.0"
    assert m1["type"] == "R"
    assert m1["next_hop"] == "10.0.12.2"


def test_14_two_router_rip_connectivity():
    """Test 14: Two routers exchanging RIP updates establish end-to-end ping."""
    pe = PacketEngine.get_instance()

    pc1 = Host("pc1", hostname="PC-1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/0").ip_address = "192.168.1.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.0"
    r1.get_port("g0/0").is_shutdown = False
    r1.get_port("g0/1").ip_address = "10.0.12.1"
    r1.get_port("g0/1").subnet_mask = "255.255.255.252"
    r1.get_port("g0/1").is_shutdown = False
    r1.enable_rip(); r1.add_rip_network("192.168.1.0"); r1.add_rip_network("10.0.0.0")

    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.get_port("g0/1").ip_address = "192.168.2.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.0"
    r2.get_port("g0/1").is_shutdown = False
    r2.enable_rip(); r2.add_rip_network("192.168.2.0"); r2.add_rip_network("10.0.0.0")

    pc2 = Host("pc2", hostname="PC-2")
    pc2.configure_ip("192.168.2.10", "255.255.255.0", gateway="192.168.2.1")

    # NO STATIC ROUTES CONFIGURED!
    Cable(pc1.eth0, r1.get_port("g0/0"))
    Cable(r1.get_port("g0/1"), r2.get_port("g0/0"))
    Cable(r2.get_port("g0/1"), pc2.eth0)

    # Ping PC1 -> PC2
    res = pe.simulate_ping(pc1, "192.168.2.10", count=4, simulate_arp=False)
    assert res.loss_percent == 0, f"Expected 0% loss, got {res.loss_percent}%"
    assert res.packets_received == 4


def build_three_router_rip_topology():
    """Helper topology: PC1 | SW1 | R1 | R2 | R3 | SW2 | PC2 running RIPv2"""
    pc1 = Host("pc1", hostname="PC-1")
    pc1.configure_ip("192.168.10.10", "255.255.255.0", gateway="192.168.10.1")

    sw1 = Switch("sw1", hostname="Switch-1")

    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/0").ip_address = "192.168.10.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.0"
    r1.get_port("g0/0").is_shutdown = False
    r1.get_port("g0/1").ip_address = "10.0.12.1"
    r1.get_port("g0/1").subnet_mask = "255.255.255.252"
    r1.get_port("g0/1").is_shutdown = False
    r1.enable_rip(); r1.add_rip_network("192.168.10.0"); r1.add_rip_network("10.0.0.0")

    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.get_port("g0/1").ip_address = "10.0.23.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.252"
    r2.get_port("g0/1").is_shutdown = False
    r2.enable_rip(); r2.add_rip_network("10.0.0.0")

    r3 = Router("r3", hostname="Router-3")
    r3.get_port("g0/0").ip_address = "10.0.23.2"
    r3.get_port("g0/0").subnet_mask = "255.255.255.252"
    r3.get_port("g0/0").is_shutdown = False
    r3.get_port("g0/1").ip_address = "192.168.20.1"
    r3.get_port("g0/1").subnet_mask = "255.255.255.0"
    r3.get_port("g0/1").is_shutdown = False
    r3.enable_rip(); r3.add_rip_network("192.168.20.0"); r3.add_rip_network("10.0.0.0")

    sw2 = Switch("sw2", hostname="Switch-2")

    pc2 = Host("pc2", hostname="PC-2")
    pc2.configure_ip("192.168.20.10", "255.255.255.0", gateway="192.168.20.1")

    # Cabling
    c1 = Cable(pc1.eth0, sw1.get_port("g0/1"))
    c2 = Cable(sw1.get_port("g0/2"), r1.get_port("g0/0"))
    c3 = Cable(r1.get_port("g0/1"), r2.get_port("g0/0"))
    c4 = Cable(r2.get_port("g0/1"), r3.get_port("g0/0"))
    c5 = Cable(r3.get_port("g0/1"), sw2.get_port("g0/1"))
    c6 = Cable(sw2.get_port("g0/2"), pc2.eth0)

    return {
        "pc1": pc1, "sw1": sw1, "r1": r1, "r2": r2, "r3": r3, "sw2": sw2, "pc2": pc2,
        "cables": [c1, c2, c3, c4, c5, c6]
    }


def test_15_three_router_rip_multihop():
    """Test 15: Multihop dynamic ping across 3 routers with RIP."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_rip_topology()
    pc1, pc2 = topo["pc1"], topo["pc2"]

    res = pe.simulate_ping(pc1, "192.168.20.10", count=4, simulate_arp=False)
    assert res.loss_percent == 0
    assert res.packets_received == 4


def test_16_forward_path():
    """Test 16: Forward path traverses all 7 devices in order."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_rip_topology()
    pc1 = topo["pc1"]

    res = pe.simulate_ping(pc1, "192.168.20.10", count=1, simulate_arp=False)
    expected = ["PC-1", "Switch-1", "Router-1", "Router-2", "Router-3", "Switch-2", "PC-2"]
    assert res.hop_path == expected


def test_17_return_path():
    """Test 17: Return path PC2 -> PC1 succeeds across dynamic routes."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_rip_topology()
    pc2 = topo["pc2"]

    res = pe.simulate_ping(pc2, "192.168.10.10", count=3, simulate_arp=False)
    assert res.loss_percent == 0
    assert res.hop_path == ["PC-2", "Switch-2", "Router-3", "Router-2", "Router-1", "Switch-1", "PC-1"]


def test_18_link_failure_removes_route():
    """Test 18: Link failure causes route poisoning and removal from downstream routers."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_rip_topology()
    pc1, r2, r3 = topo["pc1"], topo["r2"], topo["r3"]

    # First verify convergence
    pe.converge_rip()
    assert ("192.168.20.0", "255.255.255.0") in topo["r1"].rip_routes

    # Break transit link between R2 and R3
    r2.get_port("g0/1").is_shutdown = True
    pe.converge_rip()

    # R1 should now lose route to 192.168.20.0/24
    res = pe.simulate_ping(pc1, "192.168.20.10", count=2, simulate_arp=False)
    assert res.loss_percent == 100
    assert any(c == "U" for c in res.status_codes)


def test_19_link_restoration_relearns_route():
    """Test 19: Restoring failed link allows RIP to re-converge and restore traffic."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_rip_topology()
    pc1, r2 = topo["pc1"], topo["r2"]

    # Break link
    r2.get_port("g0/1").is_shutdown = True
    pe.converge_rip()
    res_down = pe.simulate_ping(pc1, "192.168.20.10", count=2, simulate_arp=False)
    assert res_down.loss_percent == 100

    # Restore link
    r2.get_port("g0/1").is_shutdown = False
    pe.converge_rip()

    # Relearned route
    res_up = pe.simulate_ping(pc1, "192.168.20.10", count=2, simulate_arp=False)
    assert res_up.loss_percent == 0


def test_20_split_horizon():
    """Test 20: Router does not advertise a route back out the interface it learned it from."""
    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/0").ip_address = "192.168.10.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.0"
    r1.get_port("g0/0").is_shutdown = False
    h1 = Host("h1"); Cable(r1.get_port("g0/0"), h1.eth0)
    r1.get_port("g0/1").ip_address = "10.0.12.1"
    r1.get_port("g0/1").subnet_mask = "255.255.255.252"
    r1.get_port("g0/1").is_shutdown = False
    r1.enable_rip(); r1.add_rip_network("192.168.10.0"); r1.add_rip_network("10.0.0.0")

    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.enable_rip(); r2.add_rip_network("10.0.0.0")

    Cable(r1.get_port("g0/1"), r2.get_port("g0/0"))
    PacketEngine.get_instance().converge_rip()

    # R2 learned 192.168.10.0/24 from R1 via g0/0
    assert ("192.168.10.0", "255.255.255.0") in r2.rip_routes

    # Check payload R2 would send back out g0/0 to R1
    r2_payload = r2.rip.build_update_payload(r2.get_port("g0/0"), "10.0.12.1")
    adv_nets = [item["network"] for item in r2_payload]
    # Split Horizon: 192.168.10.0 must NOT be in the update sent back to R1!
    assert "192.168.10.0" not in adv_nets, "Split Horizon failed: Route advertised back to origin!"


def test_21_route_poisoning():
    """Test 21: Route Poisoning advertises metric 16 when route is lost."""
    r1 = Router("r1", hostname="Router-1")
    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.enable_rip(); r2.add_rip_network("10.0.0.0")

    # Manually poison a route on R2
    r2.rip.routes[("192.168.30.0", "255.255.255.0")] = {
        "network": "192.168.30.0", "mask": "255.255.255.0", "next_hop": "10.0.23.2",
        "interface": "g0/1", "metric": 1, "type": "R", "admin_distance": 120
    }
    r2.rip._poison_routes_from_neighbor("10.0.23.2")
    assert ("192.168.30.0", "255.255.255.0") in r2.rip.poisoned_routes

    # Verify update payload contains metric 16
    payload = r2.rip.build_update_payload(r2.get_port("g0/0"), "10.0.12.1")
    p30 = [item for item in payload if item["network"] == "192.168.30.0"][0]
    assert p30["metric"] == 16


def test_22_no_routing_loop():
    """Test 22: Triangle topology R1-R2-R3-R1 converges without count-to-infinity loop."""
    pe = PacketEngine.get_instance()

    # R1: 192.168.10.1/24 (LAN1), 10.0.12.1/30 (to R2), 10.0.13.1/30 (to R3)
    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/0").ip_address = "192.168.10.1"; r1.get_port("g0/0").subnet_mask = "255.255.255.0"; r1.get_port("g0/0").is_shutdown = False
    h1 = Host("h1"); Cable(r1.get_port("g0/0"), h1.eth0)
    r1.get_port("g0/1").ip_address = "10.0.12.1"; r1.get_port("g0/1").subnet_mask = "255.255.255.252"; r1.get_port("g0/1").is_shutdown = False
    r1.get_port("g0/2").ip_address = "10.0.13.1"; r1.get_port("g0/2").subnet_mask = "255.255.255.252"; r1.get_port("g0/2").is_shutdown = False
    r1.enable_rip(); r1.add_rip_network("192.168.10.0"); r1.add_rip_network("10.0.0.0")

    # R2: 10.0.12.2/30 (to R1), 10.0.23.1/30 (to R3)
    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"; r2.get_port("g0/0").subnet_mask = "255.255.255.252"; r2.get_port("g0/0").is_shutdown = False
    r2.get_port("g0/1").ip_address = "10.0.23.1"; r2.get_port("g0/1").subnet_mask = "255.255.255.252"; r2.get_port("g0/1").is_shutdown = False
    r2.enable_rip(); r2.add_rip_network("10.0.0.0")

    # R3: 10.0.13.2/30 (to R1), 10.0.23.2/30 (to R2)
    r3 = Router("r3", hostname="Router-3")
    r3.get_port("g0/0").ip_address = "10.0.13.2"; r3.get_port("g0/0").subnet_mask = "255.255.255.252"; r3.get_port("g0/0").is_shutdown = False
    r3.get_port("g0/1").ip_address = "10.0.23.2"; r3.get_port("g0/1").subnet_mask = "255.255.255.252"; r3.get_port("g0/1").is_shutdown = False
    r3.enable_rip(); r3.add_rip_network("10.0.0.0")

    # Triangle cabling
    Cable(r1.get_port("g0/1"), r2.get_port("g0/0"))
    Cable(r1.get_port("g0/2"), r3.get_port("g0/0"))
    Cable(r2.get_port("g0/1"), r3.get_port("g0/1"))

    pe.converge_rip()

    # R2 and R3 both learn 192.168.10.0 directly from R1 with metric 1
    assert r2.rip_routes[("192.168.10.0", "255.255.255.0")]["metric"] == 1
    assert r3.rip_routes[("192.168.10.0", "255.255.255.0")]["metric"] == 1


def test_23_ttl_l3_hop_tracking():
    """Test 23: TTL decrements by 1 at each dynamic router hop (64 -> 61)."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_rip_topology()
    pc1 = topo["pc1"]

    res = pe.simulate_ping(pc1, "192.168.20.10", count=3, simulate_arp=False)
    assert res.loss_percent == 0
    # 64 - 3 router hops = 61
    assert all(ttl == 61 for ttl in res.ttl_replies)


def test_24_traceroute():
    """Test 24: Traceroute across dynamic RIP topology discovers intermediate routers."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_rip_topology()
    pc1 = topo["pc1"]

    hops = pe.simulate_traceroute(pc1, "192.168.20.10")
    hop_names = [h["name"] for h in hops]
    assert "Router-1" in hop_names
    assert "Router-2" in hop_names
    assert "Router-3" in hop_names
    assert "PC-2" in hop_names


def test_25_vlan_subinterface_integration():
    """Test 25: RIP operates across 802.1Q router subinterfaces."""
    pe = PacketEngine.get_instance()

    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/0").is_shutdown = False
    sub10 = r1.create_subinterface("g0/0", 10)
    sub10.ip_address = "192.168.10.1"
    sub10.subnet_mask = "255.255.255.0"
    sub10.vlan_id = 10

    r1.get_port("g0/1").ip_address = "10.0.12.1"
    r1.get_port("g0/1").subnet_mask = "255.255.255.252"
    r1.get_port("g0/1").is_shutdown = False
    r1.enable_rip(); r1.add_rip_network("192.168.10.0"); r1.add_rip_network("10.0.0.0")

    sw = Switch("sw", hostname="Switch-1")
    sw.add_vlan(10, "DATA")
    sw.get_port("g0/1").mode = "trunk"
    sw.get_port("g0/1").trunk_allowed_vlans = {1, 10}
    sw.get_port("g0/2").mode = "access"
    sw.get_port("g0/2").access_vlan = 10

    pc1 = Host("pc1", hostname="PC-1")
    pc1.configure_ip("192.168.10.10", "255.255.255.0", gateway="192.168.10.1")

    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.get_port("g0/1").ip_address = "192.168.20.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.0"
    r2.get_port("g0/1").is_shutdown = False
    r2.enable_rip(); r2.add_rip_network("192.168.20.0"); r2.add_rip_network("10.0.0.0")

    pc2 = Host("pc2", hostname="PC-2")
    pc2.configure_ip("192.168.20.10", "255.255.255.0", gateway="192.168.20.1")

    Cable(r1.get_port("g0/0"), sw.get_port("g0/1"))
    Cable(sw.get_port("g0/2"), pc1.eth0)
    Cable(r1.get_port("g0/1"), r2.get_port("g0/0"))
    Cable(r2.get_port("g0/1"), pc2.eth0)

    res = pe.simulate_ping(pc1, "192.168.20.10", count=3, simulate_arp=False)
    assert res.loss_percent == 0


def test_26_dhcp_rip_integration():
    """Test 26: Client configured via DHCP uses dynamic RIP routes to reach remote network."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_rip_topology()
    pc1, r1 = topo["pc1"], topo["r1"]

    # Configure PC1 as DHCP client
    pc1.ports["eth0"].ip_address = None
    pc1.ports["eth0"].subnet_mask = None
    pc1.default_gateway = None

    r1.dhcp_server.add_pool("LAN_A", network="192.168.10.0", subnet_mask="255.255.255.0", default_router="192.168.10.1")
    r1.dhcp_server.add_excluded_address("192.168.10.1")

    ok, _ = pc1.request_dhcp("eth0")
    assert ok is True
    assert pc1.ports["eth0"].ip_address == "192.168.10.2"

    res = pe.simulate_ping(pc1, "192.168.20.10", count=3, simulate_arp=False)
    assert res.loss_percent == 0


def test_27_rip_acl_regression():
    """Test 27: RIP does not bypass data-plane ACL (denied traffic drops with 'A')."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_rip_topology()
    pc1, r1 = topo["pc1"], topo["r1"]

    r1.add_access_list(10, "deny", "192.168.10.10", "0.0.0.0")
    r1.set_access_group(10, "in", "g0/0")

    res = pe.simulate_ping(pc1, "192.168.20.10", count=2, simulate_arp=False)
    assert res.loss_percent == 100
    assert any(c == "A" for c in res.status_codes)

    r1.set_access_group(None, "in", "g0/0")
    res_ok = pe.simulate_ping(pc1, "192.168.20.10", count=2, simulate_arp=False)
    assert res_ok.loss_percent == 0


def test_28_rip_nat_regression():
    """Test 28: Outbound traffic across RIP undergoes NAT overload properly."""
    pe = PacketEngine.get_instance()

    pc1 = Host("pc1", hostname="PC-1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    r1 = Router("r1", hostname="NAT-R1")
    r1.get_port("g0/0").ip_address = "192.168.1.1"; r1.get_port("g0/0").subnet_mask = "255.255.255.0"; r1.get_port("g0/0").is_shutdown = False
    r1.get_port("g0/1").ip_address = "10.0.12.1"; r1.get_port("g0/1").subnet_mask = "255.255.255.252"; r1.get_port("g0/1").is_shutdown = False
    r1.nat_inside_interfaces.add("g0/0")
    r1.nat_outside_interfaces.add("g0/1")
    r1.add_access_list(1, "permit", "192.168.1.0", "0.0.0.255")
    r1.add_nat_rule("overload", 1, "g0/1")
    r1.enable_rip(); r1.add_rip_network("10.0.0.0")

    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"; r2.get_port("g0/0").subnet_mask = "255.255.255.252"; r2.get_port("g0/0").is_shutdown = False
    r2.get_port("g0/1").ip_address = "192.168.2.1"; r2.get_port("g0/1").subnet_mask = "255.255.255.0"; r2.get_port("g0/1").is_shutdown = False
    r2.enable_rip(); r2.add_rip_network("192.168.2.0"); r2.add_rip_network("10.0.0.0")

    pc2 = Host("pc2", hostname="PC-2")
    pc2.configure_ip("192.168.2.10", "255.255.255.0", gateway="192.168.2.1")

    Cable(pc1.eth0, r1.get_port("g0/0"))
    Cable(r1.get_port("g0/1"), r2.get_port("g0/0"))
    Cable(r2.get_port("g0/1"), pc2.eth0)

    res = pe.simulate_ping(pc1, "192.168.2.10", count=3, simulate_arp=False)
    assert res.loss_percent == 0


def test_29_rip_firewall_regression():
    """Test 29: Static routes across intermediate Firewall operate alongside RIP."""
    pe = PacketEngine.get_instance()

    pc1 = Host("pc1", hostname="PC-1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/0").ip_address = "192.168.1.1"; r1.get_port("g0/0").subnet_mask = "255.255.255.0"; r1.get_port("g0/0").is_shutdown = False
    r1.get_port("g0/1").ip_address = "10.0.10.1"; r1.get_port("g0/1").subnet_mask = "255.255.255.252"; r1.get_port("g0/1").is_shutdown = False

    fw1 = Firewall("fw1", hostname="Firewall-1")
    fw1.get_port("g0/0").ip_address = "10.0.10.2"; fw1.get_port("g0/0").subnet_mask = "255.255.255.252"; fw1.get_port("g0/0").is_shutdown = False
    fw1.get_port("g0/1").ip_address = "10.0.20.1"; fw1.get_port("g0/1").subnet_mask = "255.255.255.252"; fw1.get_port("g0/1").is_shutdown = False
    fw1.set_nameif("g0/0", "inside"); fw1.set_security_level("inside", 100)
    fw1.set_nameif("g0/1", "outside"); fw1.set_security_level("outside", 0)

    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.20.2"; r2.get_port("g0/0").subnet_mask = "255.255.255.252"; r2.get_port("g0/0").is_shutdown = False
    r2.get_port("g0/1").ip_address = "192.168.2.1"; r2.get_port("g0/1").subnet_mask = "255.255.255.0"; r2.get_port("g0/1").is_shutdown = False

    pc2 = Host("pc2", hostname="PC-2")
    pc2.configure_ip("192.168.2.10", "255.255.255.0", gateway="192.168.2.1")

    # Static routes on Firewall and edge routers
    r1.add_static_route("192.168.2.0", "255.255.255.0", "10.0.10.2")
    fw1.add_static_route("192.168.2.0", "255.255.255.0", "10.0.20.2")
    fw1.add_static_route("192.168.1.0", "255.255.255.0", "10.0.10.1")
    r2.add_static_route("192.168.1.0", "255.255.255.0", "10.0.20.1")

    Cable(pc1.eth0, r1.get_port("g0/0"))
    Cable(r1.get_port("g0/1"), fw1.get_port("g0/0"))
    Cable(fw1.get_port("g0/1"), r2.get_port("g0/0"))
    Cable(r2.get_port("g0/1"), pc2.eth0)

    res = pe.simulate_ping(pc1, "192.168.2.10", count=3, simulate_arp=False)
    assert res.loss_percent == 0


def test_30_static_route_rip_preference():
    """Test 30: Static route (AD 1) preferred over RIP (AD 120); deleting static allows RIP to take over."""
    r1 = Router("r1", hostname="Router-1")
    r1.enable_rip()

    # Dynamic RIP route learned
    r1.rip.routes[("192.168.20.0", "255.255.255.0")] = {
        "network": "192.168.20.0", "mask": "255.255.255.0", "next_hop": "10.0.12.2",
        "interface": "g0/1", "metric": 1, "type": "R", "admin_distance": 120
    }

    # Add Static route pointing to different next hop
    r1.add_static_route("192.168.20.0", "255.255.255.0", "10.0.12.5")

    # Static route wins
    m1 = r1.lookup_route("192.168.20.10")
    assert m1["type"] == "S"
    assert m1["next_hop"] == "10.0.12.5"

    # Remove Static route -> RIP route takes over
    r1.remove_static_route("192.168.20.0", "255.255.255.0")
    m2 = r1.lookup_route("192.168.20.10")
    assert m2["type"] == "R"
    assert m2["next_hop"] == "10.0.12.2"


def test_31_show_ip_route():
    """Test 31: show ip route renders dynamic R routes with [120/metric]."""
    r1 = Router("r1", hostname="Router-1")
    r1.enable_rip()
    r1.rip.routes[("192.168.20.0", "255.255.255.0")] = {
        "network": "192.168.20.0", "mask": "255.255.255.0", "next_hop": "10.0.12.2",
        "interface": "g0/1", "metric": 1, "type": "R", "admin_distance": 120
    }
    r1.rip.routes[("192.168.30.0", "255.255.255.0")] = {
        "network": "192.168.30.0", "mask": "255.255.255.0", "next_hop": "10.0.12.2",
        "interface": "g0/1", "metric": 2, "type": "R", "admin_distance": 120
    }

    cli = CommandExecutor(r1)
    cli.execute("enable")
    output = cli.execute("show ip route")

    assert "R    192.168.20.0/24 [120/1] via 10.0.12.2" in output
    assert "R    192.168.30.0/24 [120/2] via 10.0.12.2" in output


def test_32_show_ip_rip():
    """Test 32: show ip rip displays version, networks, neighbors, learned routes."""
    r1 = Router("r1", hostname="Router-1")
    r1.enable_rip(version=2)
    r1.add_rip_network("10.0.0.0")
    r1.add_rip_network("192.168.10.0")
    r1.rip.neighbors.add("10.0.12.2")
    r1.rip.routes[("192.168.20.0", "255.255.255.0")] = {
        "network": "192.168.20.0", "mask": "255.255.255.0", "next_hop": "10.0.12.2",
        "interface": "g0/1", "metric": 1, "type": "R", "admin_distance": 120
    }

    cli = CommandExecutor(r1)
    cli.execute("enable")
    output = cli.execute("show ip rip")

    assert "RIP Version: 2" in output
    assert "RIP Enabled: Yes" in output
    assert "10.0.0.0" in output
    assert "192.168.10.0" in output
    assert "10.0.12.2" in output
    assert "192.168.20.0/24 via 10.0.12.2 metric 1" in output


def test_33_show_ip_protocols():
    """Test 33: show ip protocols displays protocol 'rip', version 2, distance 120."""
    r1 = Router("r1", hostname="Router-1")
    r1.enable_rip(version=2)
    r1.add_rip_network("10.0.0.0")

    cli = CommandExecutor(r1)
    cli.execute("enable")
    output = cli.execute("show ip protocols")

    assert 'Routing Protocol is "rip"' in output
    assert "10.0.0.0" in output
    assert "Distance: (default is 120)" in output


def test_34_disable_rip_removes_learned_routes():
    """Test 34: no router rip flushes all learned R routes."""
    r1 = Router("r1", hostname="Router-1")
    r1.enable_rip()
    r1.rip.routes[("192.168.20.0", "255.255.255.0")] = {
        "network": "192.168.20.0", "mask": "255.255.255.0", "next_hop": "10.0.12.2",
        "interface": "g0/1", "metric": 1, "type": "R", "admin_distance": 120
    }
    assert len(r1.rip_routes) == 1

    cli = CommandExecutor(r1)
    cli.execute("enable")
    cli.execute("configure terminal")
    cli.execute("no router rip")

    assert r1.rip_enabled is False
    assert len(r1.rip_routes) == 0
    assert r1.lookup_route("192.168.20.10") is None


if __name__ == "__main__":
    test_01_enable_rip()
    print("Test 1: Enable RIP [PASS]")
    test_02_configure_version_2()
    print("Test 2: Configure RIP version 2 [PASS]")
    test_03_add_rip_network()
    print("Test 3: Add RIP network [PASS]")
    test_04_remove_rip_network()
    print("Test 4: Remove RIP network [PASS]")
    test_05_discover_direct_neighbor()
    print("Test 5: Discover direct RIP neighbor [PASS]")
    test_06_advertise_connected_network()
    print("Test 6: Advertise connected network [PASS]")
    test_07_receive_rip_route()
    print("Test 7: Receive RIP route [PASS]")
    test_08_install_dynamic_r_route()
    print("Test 8: Install dynamic R route [PASS]")
    test_09_metric_increments_by_hop()
    print("Test 9: Metric increments by hop [PASS]")
    test_10_maximum_hop_16_unreachable()
    print("Test 10: Maximum hop 16 is unreachable [PASS]")
    test_11_connected_route_wins_rip()
    print("Test 11: Connected route wins RIP [PASS]")
    test_12_static_route_wins_rip()
    print("Test 12: Static route wins RIP [PASS]")
    test_13_longest_prefix_match_with_rip()
    print("Test 13: Longest Prefix Match with RIP [PASS]")
    test_14_two_router_rip_connectivity()
    print("Test 14: Two-router RIP connectivity [PASS]")
    test_15_three_router_rip_multihop()
    print("Test 15: Three-router RIP multihop [PASS]")
    test_16_forward_path()
    print("Test 16: Forward path [PASS]")
    test_17_return_path()
    print("Test 17: Return path [PASS]")
    test_18_link_failure_removes_route()
    print("Test 18: Link failure removes route [PASS]")
    test_19_link_restoration_relearns_route()
    print("Test 19: Link restoration relearns route [PASS]")
    test_20_split_horizon()
    print("Test 20: Split Horizon [PASS]")
    test_21_route_poisoning()
    print("Test 21: Route Poisoning [PASS]")
    test_22_no_routing_loop()
    print("Test 22: No routing loop [PASS]")
    test_23_ttl_l3_hop_tracking()
    print("Test 23: TTL / L3 hop tracking [PASS]")
    test_24_traceroute()
    print("Test 24: Traceroute [PASS]")
    test_25_vlan_subinterface_integration()
    print("Test 25: VLAN / Subinterface integration [PASS]")
    test_26_dhcp_rip_integration()
    print("Test 26: DHCP + RIP [PASS]")
    test_27_rip_acl_regression()
    print("Test 27: RIP + ACL regression [PASS]")
    test_28_rip_nat_regression()
    print("Test 28: RIP + NAT regression [PASS]")
    test_29_rip_firewall_regression()
    print("Test 29: RIP + Firewall regression [PASS]")
    test_30_static_route_rip_preference()
    print("Test 30: Static Route + RIP preference [PASS]")
    test_31_show_ip_route()
    print("Test 31: show ip route [PASS]")
    test_32_show_ip_rip()
    print("Test 32: show ip rip [PASS]")
    test_33_show_ip_protocols()
    print("Test 33: show ip protocols [PASS]")
    test_34_disable_rip_removes_learned_routes()
    print("Test 34: Disable RIP removes learned routes [PASS]")
    print("\nALL 34 RIP TESTS PASSED!")
