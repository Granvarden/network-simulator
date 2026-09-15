"""
tests/test_static_routing.py - Comprehensive Static Routing Verification Suite (Phase 3.5)

Tests:
Test 1: Add Static Route
Test 2: Show Static Route
Test 3: Remove Static Route
Test 4: Invalid Network
Test 5: Invalid Subnet Mask
Test 6: Invalid Next-Hop
Test 7: Longest Prefix Match
Test 8: Connected vs Static Route Priority
Test 9: Default Route
Test 10: No Route / Unreachable
Test 11: Two-Router Static Routing
Test 12: Three-Router Multihop Static Routing
Test 13: Forward Path Verification
Test 14: Return Path Verification
Test 15: ARP Next-Hop Resolution
Test 16: TTL / L3 Hop Tracking
Test 17: Traceroute
Test 18: Static Route + DHCP Integration
Test 19: Static Route + ACL Integration
Test 20: Static Route + NAT Regression
Test 21: Static Route + Firewall Regression
Test 22: Duplicate Static Route Behavior
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


def test_01_add_static_route():
    """Test 1: Router adds static route via next-hop IP or interface."""
    r1 = Router("r1", hostname="Router-1")
    
    # 1. Add static route with next-hop IP
    added_ip = r1.add_static_route("192.168.20.0", "255.255.255.0", "10.0.0.2")
    assert added_ip is True
    assert len(r1.routes) == 1
    assert r1.routes[0]["network"] == "192.168.20.0"
    assert r1.routes[0]["mask"] == "255.255.255.0"
    assert r1.routes[0]["next_hop"] == "10.0.0.2"
    assert r1.routes[0]["interface"] is None
    assert r1.routes[0]["type"] == "S"
    assert r1.routes[0]["admin_distance"] == 1

    # 2. Add static route with valid interface
    added_if = r1.add_static_route("10.0.1.0", "255.255.255.0", "g0/1")
    assert added_if is True
    assert len(r1.routes) == 2
    assert r1.routes[1]["network"] == "10.0.1.0"
    assert r1.routes[1]["next_hop"] is None
    assert r1.routes[1]["interface"] == "g0/1"


def test_02_show_static_route():
    """Test 2: show ip route and show running-config formatting."""
    r1 = Router("r1", hostname="Router-1")
    p0 = r1.get_port("g0/0")
    p0.ip_address = "192.168.10.1"
    p0.subnet_mask = "255.255.255.0"
    p0.is_shutdown = False
    h1 = Host("h1")
    Cable(p0, h1.eth0)

    p1 = r1.get_port("g0/1")
    p1.is_shutdown = False
    h2 = Host("h2")
    Cable(p1, h2.eth0)

    r1.add_static_route("192.168.20.0", "255.255.255.0", "10.0.0.2")
    r1.add_static_route("10.0.1.0", "255.255.255.0", "g0/1")

    cli = CommandExecutor(r1)
    cli.execute("enable")
    output = cli.execute("show ip route")

    assert "Codes: C - connected, S - static" in output
    assert "C    192.168.10.0/24 is directly connected, g0/0" in output
    assert "S    192.168.20.0/24 [1/0] via 10.0.0.2" in output
    assert "S    10.0.1.0/24 is directly connected, g0/1" in output

    run_cfg = cli.execute("show running-config")
    assert "ip route 192.168.20.0 255.255.255.0 10.0.0.2" in run_cfg
    assert "ip route 10.0.1.0 255.255.255.0 g0/1" in run_cfg


def test_03_remove_static_route():
    """Test 3: Removing static routes via API and CLI 'no ip route'."""
    r1 = Router("r1", hostname="Router-1")
    r1.add_static_route("192.168.20.0", "255.255.255.0", "10.0.0.2")
    r1.add_static_route("10.0.1.0", "255.255.255.0", "g0/1")
    assert len(r1.routes) == 2

    # Remove via API
    removed = r1.remove_static_route("10.0.1.0", "255.255.255.0")
    assert removed is True
    assert len(r1.routes) == 1

    # Remove via CLI
    cli = CommandExecutor(r1)
    cli.execute("enable")
    cli.execute("configure terminal")
    cli.execute("no ip route 192.168.20.0 255.255.255.0 10.0.0.2")
    assert len(r1.routes) == 0

    # Ensure show ip route and show running-config do not display them
    cli.execute("end")
    out_routes = cli.execute("show ip route")
    assert "192.168.20.0" not in out_routes
    assert "10.0.1.0" not in out_routes

    run_cfg = cli.execute("show running-config")
    assert "ip route" not in run_cfg


def test_04_invalid_network():
    """Test 4: Invalid network IP rejection."""
    r1 = Router("r1", hostname="Router-1")
    res = r1.add_static_route("999.999.1.1", "255.255.255.0", "10.0.0.2")
    assert res is False
    assert len(r1.routes) == 0

    cli = CommandExecutor(r1)
    cli.execute("enable")
    cli.execute("configure terminal")
    err = cli.execute("ip route 999.999.1.1 255.255.255.0 10.0.0.2")
    assert "% Invalid prefix or next-hop address" in err

    inc = cli.execute("ip route 192.168.1.0")
    assert "% Incomplete command." in inc


def test_05_invalid_subnet_mask():
    """Test 5: Non-contiguous or malformed subnet mask rejection."""
    r1 = Router("r1", hostname="Router-1")
    
    # Non-contiguous bitmask
    res1 = r1.add_static_route("192.168.1.0", "255.255.255.123", "10.0.0.2")
    assert res1 is False

    # Invalid string mask
    res2 = r1.add_static_route("192.168.1.0", "255.255.notamask", "10.0.0.2")
    assert res2 is False
    assert len(r1.routes) == 0

    cli = CommandExecutor(r1)
    cli.execute("enable")
    cli.execute("configure terminal")
    err = cli.execute("ip route 192.168.1.0 255.255.255.123 10.0.0.2")
    assert "% Invalid prefix or next-hop address" in err


def test_06_invalid_next_hop():
    """Test 6: Invalid next-hop IP or non-existent interface rejection."""
    r1 = Router("r1", hostname="Router-1")
    
    # Invalid IP
    res1 = r1.add_static_route("192.168.1.0", "255.255.255.0", "999.999.999.999")
    assert res1 is False

    # Non-existent interface
    res2 = r1.add_static_route("192.168.1.0", "255.255.255.0", "FastEthernet99/99")
    assert res2 is False
    assert len(r1.routes) == 0

    cli = CommandExecutor(r1)
    cli.execute("enable")
    cli.execute("configure terminal")
    err = cli.execute("ip route 192.168.1.0 255.255.255.0 bad-hop")
    assert "% Invalid prefix or next-hop address" in err


def test_07_longest_prefix_match():
    """Test 7: LPM selects the most specific route (/24 > /16 > /8 > /0)."""
    r1 = Router("r1", hostname="Router-LPM")

    r1.add_static_route("0.0.0.0", "0.0.0.0", "192.168.0.1")       # /0
    r1.add_static_route("10.0.0.0", "255.0.0.0", "10.255.255.1")   # /8
    r1.add_static_route("10.1.0.0", "255.255.0.0", "10.1.255.1")   # /16
    r1.add_static_route("10.1.10.0", "255.255.255.0", "10.1.10.1") # /24

    # 10.1.10.50 must match /24
    m1 = r1.lookup_route("10.1.10.50")
    assert m1 is not None
    assert m1["mask"] == "255.255.255.0"
    assert m1["next_hop"] == "10.1.10.1"

    # 10.1.20.50 must match /16
    m2 = r1.lookup_route("10.1.20.50")
    assert m2 is not None
    assert m2["mask"] == "255.255.0.0"
    assert m2["next_hop"] == "10.1.255.1"

    # 10.2.1.1 must match /8
    m3 = r1.lookup_route("10.2.1.1")
    assert m3 is not None
    assert m3["mask"] == "255.0.0.0"
    assert m3["next_hop"] == "10.255.255.1"

    # 172.16.1.1 must fallback to default route /0
    m4 = r1.lookup_route("172.16.1.1")
    assert m4 is not None
    assert m4["mask"] == "0.0.0.0"
    assert m4["next_hop"] == "192.168.0.1"


def test_08_connected_vs_static_route():
    """Test 8: Connected route takes precedence over Static route for same prefix."""
    r1 = Router("r1", hostname="Router-1")
    p0 = r1.get_port("g0/0")
    p0.ip_address = "192.168.10.1"
    p0.subnet_mask = "255.255.255.0"
    p0.is_shutdown = False
    h1 = Host("h1")
    Cable(p0, h1.eth0)

    # Add competing static route for the exact same /24 subnet
    r1.add_static_route("192.168.10.0", "255.255.255.0", "10.0.0.2")

    matched = r1.lookup_route("192.168.10.50")
    assert matched is not None
    assert matched["type"] == "C", f"Expected Connected route to win, got {matched['type']}"
    assert matched["next_hop"] == "directly connected"
    assert matched["interface"] == "g0/0"


def test_09_default_route():
    """Test 9: Default route 0.0.0.0/0 configuration, lookup, and candidate default S*."""
    r1 = Router("r1", hostname="Router-1")
    added = r1.add_static_route("0.0.0.0", "0.0.0.0", "10.0.0.1")
    assert added is True

    # Lookup internet destination
    m = r1.lookup_route("8.8.8.8")
    assert m is not None
    assert m["network"] == "0.0.0.0"
    assert m["next_hop"] == "10.0.0.1"

    cli = CommandExecutor(r1)
    cli.execute("enable")
    output = cli.execute("show ip route")
    assert "Gateway of last resort is 10.0.0.1 to network 0.0.0.0" in output
    assert "S*   0.0.0.0/0 [1/0] via 10.0.0.1" in output


def test_10_no_route_unreachable():
    """Test 10: Unrouted traffic drops with 'U' status and does not loop."""
    pe = PacketEngine.get_instance()
    pc1 = Host("pc1", hostname="PC-1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/0").ip_address = "192.168.1.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.0"
    r1.get_port("g0/0").is_shutdown = False

    Cable(pc1.eth0, r1.get_port("g0/0"), CableType.CAT6)

    # Ping IP with no route on R1
    res = pe.simulate_ping(pc1, "192.168.50.10", count=3)
    assert res.loss_percent == 100
    assert any(c == "U" for c in res.status_codes)
    assert "no route" in res.error_message.lower()


def test_11_two_router_static_routing():
    """Test 11: Two routers communicating across static routes."""
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

    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.get_port("g0/1").ip_address = "192.168.2.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.0"
    r2.get_port("g0/1").is_shutdown = False

    pc2 = Host("pc2", hostname="PC-2")
    pc2.configure_ip("192.168.2.10", "255.255.255.0", gateway="192.168.2.1")

    # Static Routes
    r1.add_static_route("192.168.2.0", "255.255.255.0", "10.0.12.2")
    r2.add_static_route("192.168.1.0", "255.255.255.0", "10.0.12.1")

    Cable(pc1.eth0, r1.get_port("g0/0"))
    Cable(r1.get_port("g0/1"), r2.get_port("g0/0"))
    Cable(r2.get_port("g0/1"), pc2.eth0)

    res = pe.simulate_ping(pc1, "192.168.2.10", count=4)
    assert res.loss_percent == 0
    assert res.packets_received == 4


def build_three_router_topology():
    """Helper topology: PC1 | SW1 | R1 | R2 | R3 | SW2 | PC2"""
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
    r3.get_port("g0/1").ip_address = "192.168.20.1"
    r3.get_port("g0/1").subnet_mask = "255.255.255.0"
    r3.get_port("g0/1").is_shutdown = False

    sw2 = Switch("sw2", hostname="Switch-2")

    pc2 = Host("pc2", hostname="PC-2")
    pc2.configure_ip("192.168.20.10", "255.255.255.0", gateway="192.168.20.1")

    # Static routes
    r1.add_static_route("192.168.20.0", "255.255.255.0", "10.0.12.2")
    r2.add_static_route("192.168.10.0", "255.255.255.0", "10.0.12.1")
    r2.add_static_route("192.168.20.0", "255.255.255.0", "10.0.23.2")
    r3.add_static_route("192.168.10.0", "255.255.255.0", "10.0.23.1")

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


def test_12_three_router_multihop_static_routing():
    """Test 12: PC1 -> PC2 across 3 routers with 0% packet loss."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_topology()
    pc1, pc2 = topo["pc1"], topo["pc2"]

    res = pe.simulate_ping(pc1, "192.168.20.10", count=5, simulate_arp=False)
    assert res.loss_percent == 0, f"Expected 0% loss, got {res.loss_percent}% ({res.status_codes})"
    assert res.packets_received == 5
    assert all(c == "!" for c in res.status_codes)


def test_13_forward_path_verification():
    """Test 13: Hop path verification for forward path across all 7 devices."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_topology()
    pc1 = topo["pc1"]

    res = pe.simulate_ping(pc1, "192.168.20.10", count=1, simulate_arp=False)
    expected = ["PC-1", "Switch-1", "Router-1", "Router-2", "Router-3", "Switch-2", "PC-2"]
    assert res.hop_path == expected, f"Expected {expected}, got {res.hop_path}"


def test_14_return_path_verification():
    """Test 14: Return path verification & route removal failure scenario."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_topology()
    pc1, pc2, r3 = topo["pc1"], topo["pc2"], topo["r3"]

    # 1. Reverse ping PC2 -> PC1
    res_rev = pe.simulate_ping(pc2, "192.168.10.10", count=3, simulate_arp=False)
    assert res_rev.loss_percent == 0
    expected_rev = ["PC-2", "Switch-2", "Router-3", "Router-2", "Router-1", "Switch-1", "PC-1"]
    assert res_rev.hop_path == expected_rev

    # 2. Break return route on R3
    r3.remove_static_route("192.168.10.0", "255.255.255.0")
    res_broken = pe.simulate_ping(pc1, "192.168.20.10", count=2, simulate_arp=False)
    assert res_broken.loss_percent == 100
    assert any(c == "U" for c in res_broken.status_codes)
    assert "no route" in res_broken.error_message.lower()

    # 3. Restore return route
    r3.add_static_route("192.168.10.0", "255.255.255.0", "10.0.23.1")
    res_restored = pe.simulate_ping(pc1, "192.168.20.10", count=2, simulate_arp=False)
    assert res_restored.loss_percent == 0


def test_15_arp_next_hop_resolution():
    """Test 15: Routers resolve ARP for next-hop gateway on transit links."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_topology()
    pc1, r1, r2, r3 = topo["pc1"], topo["r1"], topo["r2"], topo["r3"]

    pe.simulate_ping(pc1, "192.168.20.10", count=1, simulate_arp=False)

    # R1 knows next hop 10.0.12.2 and local client 192.168.10.10
    assert r1.lookup_arp("192.168.10.10") is not None
    assert r1.lookup_arp("10.0.12.2") is not None

    # R2 knows next hops 10.0.12.1 and 10.0.23.2
    assert r2.lookup_arp("10.0.12.1") is not None
    assert r2.lookup_arp("10.0.23.2") is not None

    # R3 knows next hop 10.0.23.1 and destination host 192.168.20.10
    assert r3.lookup_arp("10.0.23.1") is not None
    assert r3.lookup_arp("192.168.20.10") is not None


def test_16_ttl_l3_hop_tracking():
    """Test 16: Host TTL 64 decremented by 3 routers to 61 (switches do not decrement)."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_topology()
    pc1 = topo["pc1"]

    res = pe.simulate_ping(pc1, "192.168.20.10", count=3, simulate_arp=False)
    assert res.loss_percent == 0
    # 64 - 3 router hops = 61
    assert all(ttl == 61 for ttl in res.ttl_replies), f"Expected TTL 61, got {res.ttl_replies}"


def test_17_traceroute():
    """Test 17: Traceroute across static routes discovers all L3 intermediate routers."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_topology()
    pc1 = topo["pc1"]

    hops = pe.simulate_traceroute(pc1, "192.168.20.10")
    assert len(hops) >= 3
    hop_names = [h["name"] for h in hops]
    # L3 hops traversed in order
    assert "Router-1" in hop_names
    assert "Router-2" in hop_names
    assert "Router-3" in hop_names
    assert "PC-2" in hop_names


def test_18_static_route_dhcp_integration():
    """Test 18: DHCP client leases IP/Gateway from R1 and uses static routes to reach PC2."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_topology()
    pc1, r1 = topo["pc1"], topo["r1"]

    # Clear PC1 static IP to emulate unconfigured DHCP client
    pc1.ports["eth0"].ip_address = None
    pc1.ports["eth0"].subnet_mask = None
    pc1.default_gateway = None

    # Configure DHCP server on R1
    r1.dhcp_server.add_pool("LAN_A", network="192.168.10.0", subnet_mask="255.255.255.0", default_router="192.168.10.1")
    r1.dhcp_server.add_excluded_address("192.168.10.1")

    # Host requests DHCP lease
    ok, _ = pc1.request_dhcp("eth0")
    assert ok is True
    assert pc1.ports["eth0"].ip_address == "192.168.10.2"
    assert pc1.default_gateway == "192.168.10.1"

    # Host can ping across multihop static routes
    res = pe.simulate_ping(pc1, "192.168.20.10", count=3, simulate_arp=False)
    assert res.loss_percent == 0


def test_19_static_route_acl_integration():
    """Test 19: Static route does not bypass Router ACL (drops with status 'A')."""
    pe = PacketEngine.get_instance()
    topo = build_three_router_topology()
    pc1, r1 = topo["pc1"], topo["r1"]

    # Apply ACL blocking PC1 on R1 ingress
    r1.add_access_list(10, "deny", "192.168.10.10", "0.0.0.0")
    r1.set_access_group(10, "in", "g0/0")

    res = pe.simulate_ping(pc1, "192.168.20.10", count=3, simulate_arp=False)
    assert res.loss_percent == 100
    assert any(c == "A" for c in res.status_codes)

    # Remove ACL -> traffic flows
    r1.set_access_group(None, "in", "g0/0")
    res_ok = pe.simulate_ping(pc1, "192.168.20.10", count=3, simulate_arp=False)
    assert res_ok.loss_percent == 0


def test_20_static_route_nat_regression():
    """Test 20: Traffic routed via static route passes through NAT correctly."""
    pe = PacketEngine.get_instance()

    pc1 = Host("pc1", hostname="PC-1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    r1 = Router("r1", hostname="NAT-R1")
    r1.get_port("g0/0").ip_address = "192.168.1.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.0"
    r1.get_port("g0/0").is_shutdown = False
    r1.nat_inside_interfaces.add("g0/0")

    r1.get_port("g0/1").ip_address = "10.0.12.1"
    r1.get_port("g0/1").subnet_mask = "255.255.255.252"
    r1.get_port("g0/1").is_shutdown = False
    r1.nat_outside_interfaces.add("g0/1")

    # NAT configuration on R1
    r1.add_access_list(1, "permit", "192.168.1.0", "0.0.0.255")
    r1.add_nat_rule("overload", 1, "g0/1")

    # Static route on R1 to 192.168.2.0/24 via R2
    r1.add_static_route("192.168.2.0", "255.255.255.0", "10.0.12.2")

    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.12.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.get_port("g0/1").ip_address = "192.168.2.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.0"
    r2.get_port("g0/1").is_shutdown = False

    pc2 = Host("pc2", hostname="PC-2")
    pc2.configure_ip("192.168.2.10", "255.255.255.0", gateway="192.168.2.1")

    Cable(pc1.eth0, r1.get_port("g0/0"))
    Cable(r1.get_port("g0/1"), r2.get_port("g0/0"))
    Cable(r2.get_port("g0/1"), pc2.eth0)

    res = pe.simulate_ping(pc1, "192.168.2.10", count=3, simulate_arp=False)
    assert res.loss_percent == 0


def test_21_static_route_firewall_regression():
    """Test 21: Static route across intermediate Stateful Firewall."""
    pe = PacketEngine.get_instance()

    pc1 = Host("pc1", hostname="PC-1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    r1 = Router("r1", hostname="Router-1")
    r1.get_port("g0/0").ip_address = "192.168.1.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.0"
    r1.get_port("g0/0").is_shutdown = False
    r1.get_port("g0/1").ip_address = "10.0.10.1"
    r1.get_port("g0/1").subnet_mask = "255.255.255.252"
    r1.get_port("g0/1").is_shutdown = False

    fw1 = Firewall("fw1", hostname="Firewall-1")
    fw1.get_port("g0/0").ip_address = "10.0.10.2"
    fw1.get_port("g0/0").subnet_mask = "255.255.255.252"
    fw1.get_port("g0/0").is_shutdown = False
    fw1.get_port("g0/1").ip_address = "10.0.20.1"
    fw1.get_port("g0/1").subnet_mask = "255.255.255.252"
    fw1.get_port("g0/1").is_shutdown = False
    fw1.set_nameif("g0/0", "inside")
    fw1.set_security_level("inside", 100)
    fw1.set_nameif("g0/1", "outside")
    fw1.set_security_level("outside", 0)

    r2 = Router("r2", hostname="Router-2")
    r2.get_port("g0/0").ip_address = "10.0.20.2"
    r2.get_port("g0/0").subnet_mask = "255.255.255.252"
    r2.get_port("g0/0").is_shutdown = False
    r2.get_port("g0/1").ip_address = "192.168.2.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.0"
    r2.get_port("g0/1").is_shutdown = False

    pc2 = Host("pc2", hostname="PC-2")
    pc2.configure_ip("192.168.2.10", "255.255.255.0", gateway="192.168.2.1")

    # Routing
    r1.add_static_route("192.168.2.0", "255.255.255.0", "10.0.10.2")
    fw1.add_static_route("192.168.2.0", "255.255.255.0", "10.0.20.2")
    fw1.add_static_route("192.168.1.0", "255.255.255.0", "10.0.10.1")
    r2.add_static_route("192.168.1.0", "255.255.255.0", "10.0.20.1")

    Cable(pc1.eth0, r1.get_port("g0/0"))
    Cable(r1.get_port("g0/1"), fw1.get_port("g0/0"))
    Cable(fw1.get_port("g0/1"), r2.get_port("g0/0"))
    Cable(r2.get_port("g0/1"), pc2.eth0)

    # Ping across firewall permitted statefully
    res = pe.simulate_ping(pc1, "192.168.20.10", count=3, simulate_arp=False)
    # Wait, pc2 IP is 192.168.2.10
    res = pe.simulate_ping(pc1, "192.168.2.10", count=3, simulate_arp=False)
    assert res.loss_percent == 0


def test_22_duplicate_static_route_behavior():
    """Test 22: Duplicate static route deterministically REPLACES old entry."""
    r1 = Router("r1", hostname="Router-1")
    r1.add_static_route("192.168.20.0", "255.255.255.0", "10.0.0.2")
    assert len(r1.routes) == 1
    assert r1.routes[0]["next_hop"] == "10.0.0.2"

    # Add duplicate with different next-hop
    r1.add_static_route("192.168.20.0", "255.255.255.0", "10.0.0.3")
    assert len(r1.routes) == 1, "Duplicate should replace, not create multiple entries"
    assert r1.routes[0]["next_hop"] == "10.0.0.3"


if __name__ == "__main__":
    test_01_add_static_route()
    print("Test 1: Add Static Route [PASS]")
    test_02_show_static_route()
    print("Test 2: Show Static Route [PASS]")
    test_03_remove_static_route()
    print("Test 3: Remove Static Route [PASS]")
    test_04_invalid_network()
    print("Test 4: Invalid Network [PASS]")
    test_05_invalid_subnet_mask()
    print("Test 5: Invalid Subnet Mask [PASS]")
    test_06_invalid_next_hop()
    print("Test 6: Invalid Next-Hop [PASS]")
    test_07_longest_prefix_match()
    print("Test 7: Longest Prefix Match [PASS]")
    test_08_connected_vs_static_route()
    print("Test 8: Connected vs Static Route [PASS]")
    test_09_default_route()
    print("Test 9: Default Route [PASS]")
    test_10_no_route_unreachable()
    print("Test 10: No Route / Unreachable [PASS]")
    test_11_two_router_static_routing()
    print("Test 11: Two-Router Static Routing [PASS]")
    test_12_three_router_multihop_static_routing()
    print("Test 12: Three-Router Multihop Static Routing [PASS]")
    test_13_forward_path_verification()
    print("Test 13: Forward Path Verification [PASS]")
    test_14_return_path_verification()
    print("Test 14: Return Path Verification [PASS]")
    test_15_arp_next_hop_resolution()
    print("Test 15: ARP Next-Hop Resolution [PASS]")
    test_16_ttl_l3_hop_tracking()
    print("Test 16: TTL / L3 Hop Tracking [PASS]")
    test_17_traceroute()
    print("Test 17: Traceroute [PASS]")
    test_18_static_route_dhcp_integration()
    print("Test 18: Static Route + DHCP Integration [PASS]")
    test_19_static_route_acl_integration()
    print("Test 19: Static Route + ACL Integration [PASS]")
    test_20_static_route_nat_regression()
    print("Test 20: Static Route + NAT Regression [PASS]")
    test_21_static_route_firewall_regression()
    print("Test 21: Static Route + Firewall Regression [PASS]")
    test_22_duplicate_static_route_behavior()
    print("Test 22: Duplicate Static Route Behavior [PASS]")
    print("\nALL 22 STATIC ROUTING TESTS PASSED!")
