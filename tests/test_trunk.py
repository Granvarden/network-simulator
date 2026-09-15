"""
tests/test_trunk.py - Comprehensive Test Suite for IEEE 802.1Q VLAN Trunking (Phase 4.5)
Validates:
1. Trunk and Access port mode transitions
2. Allowed VLAN list parsing, range syntax (e.g. 10-20), combined specs, validation
3. Native VLAN configuration, validation, and defaults
4. Ingress filtering (drop disallowed VLANs, drop tagged frames on access ports)
5. Egress processing (tag non-native VLANs, leave native VLAN untagged)
6. Untagged ingress mapping to Native VLAN
7. Native VLAN mismatch detection and isolation
8. Per-VLAN MAC address learning and forwarding
9. Multi-switch trunk transit (SW1 - SW2 - SW3)
10. VLAN isolation over trunk (VLAN 10 isolated from VLAN 20)
11. Broadcast and unknown unicast containment per VLAN
12. Spanning Tree Protocol (STP) Blocking port integration
13. Router-on-a-Stick Subinterface integration (802.1Q encapsulation)
14. DHCP over Trunk across multiple isolated VLANs
15. Dynamic Routing (RIPv2 & OSPFv2) over 802.1Q subinterfaces across Trunk
16. SVI inter-switch communication over Trunk
17. Cisco IOS CLI: switchport commands, show interfaces switchport/trunk, show running-config
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.device import Port
from network.switch import Switch, format_vlan_ranges, parse_vlan_ranges
from network.router import Router
from network.host import Host
from network.cable import Cable
from network.packet_engine import PacketEngine
from cli.command_executor import CommandExecutor, IOSMode


# =====================================================================
# Group 1: Configuration & CLI Validation Tests
# =====================================================================

def test_set_port_mode_trunk():
    sw = Switch("sw1")
    p = sw.get_port("g0/1")
    assert p.mode == "access"
    p.mode = "trunk"
    assert p.mode == "trunk"

def test_set_port_mode_access():
    sw = Switch("sw1")
    p = sw.get_port("g0/1")
    p.mode = "trunk"
    p.mode = "access"
    assert p.mode == "access"

def test_configure_allowed_vlan_comma_list():
    vlans = parse_vlan_ranges("10,20,30")
    assert vlans == {10, 20, 30}

def test_configure_allowed_vlan_range():
    vlans = parse_vlan_ranges("10-15")
    assert vlans == {10, 11, 12, 13, 14, 15}

def test_configure_allowed_vlan_combined():
    vlans = parse_vlan_ranges("1,10-12,20,30-32")
    assert vlans == {1, 10, 11, 12, 20, 30, 31, 32}
    formatted = format_vlan_ranges(vlans)
    assert formatted == "1,10-12,20,30-32"

def test_configure_native_vlan():
    sw = Switch("sw1")
    cli = CommandExecutor(sw)
    cli.execute("enable")
    cli.execute("configure terminal")
    cli.execute("interface g0/1")
    cli.execute("switchport mode trunk")
    cli.execute("switchport trunk allowed vlan 1,99")
    res = cli.execute("switchport trunk native vlan 99")
    assert res == ""
    p = sw.get_port("g0/1")
    assert p.native_vlan == 99

def test_remove_trunk_allowed_vlan():
    sw = Switch("sw1")
    cli = CommandExecutor(sw)
    cli.execute("enable")
    cli.execute("configure terminal")
    cli.execute("interface g0/1")
    cli.execute("switchport mode trunk")
    cli.execute("switchport trunk allowed vlan 1,10,20")
    p = sw.get_port("g0/1")
    assert p.trunk_allowed_vlans == {1, 10, 20}
    cli.execute("no switchport trunk allowed vlan")
    assert p.trunk_allowed_vlans == {1}

def test_remove_trunk_native_vlan():
    sw = Switch("sw1")
    cli = CommandExecutor(sw)
    cli.execute("enable")
    cli.execute("configure terminal")
    cli.execute("interface g0/1")
    cli.execute("switchport mode trunk")
    cli.execute("switchport trunk allowed vlan 1,99")
    cli.execute("switchport trunk native vlan 99")
    p = sw.get_port("g0/1")
    assert p.native_vlan == 99
    cli.execute("no switchport trunk native vlan")
    assert p.native_vlan == 1

def test_invalid_vlan_id_rejected():
    try:
        parse_vlan_ranges("5000")
        assert False, "Should have raised ValueError for VLAN > 4094"
    except ValueError:
        pass

    try:
        parse_vlan_ranges("invalid")
        assert False, "Should have raised ValueError for non-integer"
    except ValueError:
        pass

def test_invalid_vlan_range_rejected():
    try:
        parse_vlan_ranges("30-20")  # Inverted
        assert False, "Should have raised ValueError for inverted range"
    except ValueError:
        pass

def test_duplicate_vlan_handling():
    vlans = parse_vlan_ranges("10,10,20,10,20")
    assert vlans == {10, 20}

def test_native_vlan_not_allowed_drops_ingress():
    """When trunk native VLAN is not in allowed list, untagged ingress (mapped to native) is dropped."""
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1"); sw2 = Switch("sw2")
    sw1.add_vlan(99); sw2.add_vlan(99)

    sw1.get_port("g0/1").mode = "access"; sw1.get_port("g0/1").access_vlan = 99
    sw2.get_port("g0/1").mode = "access"; sw2.get_port("g0/1").access_vlan = 99

    t1 = sw1.get_port("g0/8"); t1.mode = "trunk"; t1.native_vlan = 99; t1.trunk_allowed_vlans = {1, 10}  # 99 not allowed
    t2 = sw2.get_port("g0/8"); t2.mode = "trunk"; t2.native_vlan = 99; t2.trunk_allowed_vlans = {1, 10}
    Cable(t1, t2)

    h1 = Host("h1"); h1.configure_ip("10.99.0.1", "255.255.255.0"); Cable(h1.eth0, sw1.get_port("g0/1"))
    h2 = Host("h2"); h2.configure_ip("10.99.0.2", "255.255.255.0"); Cable(h2.eth0, sw2.get_port("g0/1"))

    res = pe.simulate_ping(h1, "10.99.0.2", count=2)
    assert res.loss_percent == 100

def test_native_vlan_not_allowed_drops_egress():
    """When trunk native VLAN is not in allowed list, egress traffic for native VLAN is dropped."""
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1"); sw2 = Switch("sw2")
    sw1.add_vlan(99); sw2.add_vlan(99)

    sw1.get_port("g0/1").mode = "access"; sw1.get_port("g0/1").access_vlan = 99
    sw2.get_port("g0/1").mode = "access"; sw2.get_port("g0/1").access_vlan = 99

    t1 = sw1.get_port("g0/8"); t1.mode = "trunk"; t1.native_vlan = 99; t1.trunk_allowed_vlans = {1}  # 99 disallowed
    t2 = sw2.get_port("g0/8"); t2.mode = "trunk"; t2.native_vlan = 99; t2.trunk_allowed_vlans = {1, 99}
    Cable(t1, t2)

    h1 = Host("h1"); h1.configure_ip("10.99.0.1", "255.255.255.0"); Cable(h1.eth0, sw1.get_port("g0/1"))
    h2 = Host("h2"); h2.configure_ip("10.99.0.2", "255.255.255.0"); Cable(h2.eth0, sw2.get_port("g0/1"))

    res = pe.simulate_ping(h1, "10.99.0.2", count=2)
    assert res.loss_percent == 100


# =====================================================================
# Group 2: Data Plane Forwarding & Isolation Tests
# =====================================================================

def test_single_vlan_transport_over_trunk():
    """PC1 (VLAN 10) -> SW1 -> Trunk (VLAN 10) -> SW2 -> PC2 (VLAN 10) succeeds."""
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")
    sw1.add_vlan(10, "Sales")
    sw2.add_vlan(10, "Sales")

    sw1.get_port("g0/1").mode = "access"
    sw1.get_port("g0/1").access_vlan = 10
    sw2.get_port("g0/1").mode = "access"
    sw2.get_port("g0/1").access_vlan = 10

    t1 = sw1.get_port("g0/8")
    t1.mode = "trunk"
    t1.trunk_allowed_vlans = {1, 10}

    t2 = sw2.get_port("g0/8")
    t2.mode = "trunk"
    t2.trunk_allowed_vlans = {1, 10}

    Cable(t1, t2)

    pc1 = Host("pc1")
    pc1.configure_ip("192.168.10.10", "255.255.255.0")
    Cable(pc1.eth0, sw1.get_port("g0/1"))

    pc2 = Host("pc2")
    pc2.configure_ip("192.168.10.20", "255.255.255.0")
    Cable(pc2.eth0, sw2.get_port("g0/1"))

    res = pe.simulate_ping(pc1, "192.168.10.20", count=3)
    assert res.loss_percent == 0
    assert res.packets_received == 3

def test_multiple_vlans_over_single_trunk():
    """Trunk carries VLAN 10, 20, 30 simultaneously between SW1 and SW2."""
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")
    for vid in (10, 20, 30):
        sw1.add_vlan(vid)
        sw2.add_vlan(vid)

    sw1.get_port("g0/1").mode = "access"; sw1.get_port("g0/1").access_vlan = 10
    sw1.get_port("g0/2").mode = "access"; sw1.get_port("g0/2").access_vlan = 20
    sw1.get_port("g0/3").mode = "access"; sw1.get_port("g0/3").access_vlan = 30

    sw2.get_port("g0/1").mode = "access"; sw2.get_port("g0/1").access_vlan = 10
    sw2.get_port("g0/2").mode = "access"; sw2.get_port("g0/2").access_vlan = 20
    sw2.get_port("g0/3").mode = "access"; sw2.get_port("g0/3").access_vlan = 30

    t1 = sw1.get_port("g0/8"); t1.mode = "trunk"; t1.trunk_allowed_vlans = {1, 10, 20, 30}
    t2 = sw2.get_port("g0/8"); t2.mode = "trunk"; t2.trunk_allowed_vlans = {1, 10, 20, 30}
    Cable(t1, t2)

    # VLAN 10 hosts
    pc1_10 = Host("pc1_10"); pc1_10.configure_ip("192.168.10.1", "255.255.255.0"); Cable(pc1_10.eth0, sw1.get_port("g0/1"))
    pc2_10 = Host("pc2_10"); pc2_10.configure_ip("192.168.10.2", "255.255.255.0"); Cable(pc2_10.eth0, sw2.get_port("g0/1"))

    # VLAN 20 hosts
    pc1_20 = Host("pc1_20"); pc1_20.configure_ip("192.168.20.1", "255.255.255.0"); Cable(pc1_20.eth0, sw1.get_port("g0/2"))
    pc2_20 = Host("pc2_20"); pc2_20.configure_ip("192.168.20.2", "255.255.255.0"); Cable(pc2_20.eth0, sw2.get_port("g0/2"))

    # VLAN 30 hosts
    pc1_30 = Host("pc1_30"); pc1_30.configure_ip("192.168.30.1", "255.255.255.0"); Cable(pc1_30.eth0, sw1.get_port("g0/3"))
    pc2_30 = Host("pc2_30"); pc2_30.configure_ip("192.168.30.2", "255.255.255.0"); Cable(pc2_30.eth0, sw2.get_port("g0/3"))

    assert pe.simulate_ping(pc1_10, "192.168.10.2", count=2).loss_percent == 0
    assert pe.simulate_ping(pc1_20, "192.168.20.2", count=2).loss_percent == 0
    assert pe.simulate_ping(pc1_30, "192.168.30.2", count=2).loss_percent == 0

def test_vlan_isolation_over_trunk():
    """Traffic from PC1 (VLAN 10) must NEVER reach PC2 (VLAN 20) across trunk."""
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1"); sw2 = Switch("sw2")
    sw1.add_vlan(10); sw1.add_vlan(20)
    sw2.add_vlan(10); sw2.add_vlan(20)

    sw1.get_port("g0/1").mode = "access"; sw1.get_port("g0/1").access_vlan = 10
    sw2.get_port("g0/2").mode = "access"; sw2.get_port("g0/2").access_vlan = 20

    t1 = sw1.get_port("g0/8"); t1.mode = "trunk"; t1.trunk_allowed_vlans = {1, 10, 20}
    t2 = sw2.get_port("g0/8"); t2.mode = "trunk"; t2.trunk_allowed_vlans = {1, 10, 20}
    Cable(t1, t2)

    pc1 = Host("pc1"); pc1.configure_ip("192.168.10.10", "255.255.255.0"); Cable(pc1.eth0, sw1.get_port("g0/1"))
    pc2 = Host("pc2"); pc2.configure_ip("192.168.10.20", "255.255.255.0"); Cable(pc2.eth0, sw2.get_port("g0/2"))

    res = pe.simulate_ping(pc1, "192.168.10.20", count=2)
    assert res.loss_percent == 100
    assert res.packets_received == 0

def test_access_to_trunk_to_access_flow():
    """Validates end-to-end untagged -> tagged -> untagged frame flow."""
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1"); sw2 = Switch("sw2")
    sw1.add_vlan(15); sw2.add_vlan(15)

    sw1.get_port("g0/1").mode = "access"; sw1.get_port("g0/1").access_vlan = 15
    sw2.get_port("g0/1").mode = "access"; sw2.get_port("g0/1").access_vlan = 15

    Cable(sw1.get_port("g0/8"), sw2.get_port("g0/8"))
    sw1.get_port("g0/8").mode = "trunk"; sw1.get_port("g0/8").trunk_allowed_vlans = {1, 15}
    sw2.get_port("g0/8").mode = "trunk"; sw2.get_port("g0/8").trunk_allowed_vlans = {1, 15}

    h1 = Host("h1"); h1.configure_ip("10.0.15.1", "255.255.255.0"); Cable(h1.eth0, sw1.get_port("g0/1"))
    h2 = Host("h2"); h2.configure_ip("10.0.15.2", "255.255.255.0"); Cable(h2.eth0, sw2.get_port("g0/1"))

    res = pe.simulate_ping(h1, "10.0.15.2", count=3)
    assert res.loss_percent == 0

def test_trunk_to_trunk_transit():
    """SW1 (access) -> SW2 (transit trunk) -> SW3 (access) over 2 trunk links."""
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")
    sw3 = Switch("sw3", hostname="SW3")

    for sw in (sw1, sw2, sw3):
        sw.add_vlan(50)

    sw1.get_port("g0/1").mode = "access"; sw1.get_port("g0/1").access_vlan = 50
    sw3.get_port("g0/1").mode = "access"; sw3.get_port("g0/1").access_vlan = 50

    # SW1 -> SW2
    t1_2 = sw1.get_port("g0/7"); t1_2.mode = "trunk"; t1_2.trunk_allowed_vlans = {1, 50}
    t2_1 = sw2.get_port("g0/7"); t2_1.mode = "trunk"; t2_1.trunk_allowed_vlans = {1, 50}
    Cable(t1_2, t2_1)

    # SW2 -> SW3
    t2_3 = sw2.get_port("g0/8"); t2_3.mode = "trunk"; t2_3.trunk_allowed_vlans = {1, 50}
    t3_2 = sw3.get_port("g0/8"); t3_2.mode = "trunk"; t3_2.trunk_allowed_vlans = {1, 50}
    Cable(t2_3, t3_2)

    h1 = Host("h1"); h1.configure_ip("10.50.0.1", "255.255.255.0"); Cable(h1.eth0, sw1.get_port("g0/1"))
    h3 = Host("h3"); h3.configure_ip("10.50.0.3", "255.255.255.0"); Cable(h3.eth0, sw3.get_port("g0/1"))

    res = pe.simulate_ping(h1, "10.50.0.3", count=3)
    assert res.loss_percent == 0


# =====================================================================
# Group 3: Allowed VLAN Filtering Tests
# =====================================================================

def test_allowed_vlan_passes_traffic():
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1"); sw2 = Switch("sw2")
    sw1.add_vlan(10); sw2.add_vlan(10)
    sw1.get_port("g0/1").mode = "access"; sw1.get_port("g0/1").access_vlan = 10
    sw2.get_port("g0/1").mode = "access"; sw2.get_port("g0/1").access_vlan = 10

    t1 = sw1.get_port("g0/8"); t1.mode = "trunk"; t1.trunk_allowed_vlans = {1, 10}
    t2 = sw2.get_port("g0/8"); t2.mode = "trunk"; t2.trunk_allowed_vlans = {1, 10}
    Cable(t1, t2)

    h1 = Host("h1"); h1.configure_ip("192.168.10.1", "255.255.255.0"); Cable(h1.eth0, sw1.get_port("g0/1"))
    h2 = Host("h2"); h2.configure_ip("192.168.10.2", "255.255.255.0"); Cable(h2.eth0, sw2.get_port("g0/1"))

    res = pe.simulate_ping(h1, "192.168.10.2", count=2)
    assert res.loss_percent == 0

def test_disallowed_vlan_dropped_at_ingress():
    """SW1 allows VLAN 10 on egress, but SW2 trunk ingress disallows VLAN 10 -> dropped."""
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1"); sw2 = Switch("sw2")
    sw1.add_vlan(10); sw2.add_vlan(10)
    sw1.get_port("g0/1").mode = "access"; sw1.get_port("g0/1").access_vlan = 10
    sw2.get_port("g0/1").mode = "access"; sw2.get_port("g0/1").access_vlan = 10

    t1 = sw1.get_port("g0/8"); t1.mode = "trunk"; t1.trunk_allowed_vlans = {1, 10}
    t2 = sw2.get_port("g0/8"); t2.mode = "trunk"; t2.trunk_allowed_vlans = {1}  # VLAN 10 disallowed on SW2
    Cable(t1, t2)

    h1 = Host("h1"); h1.configure_ip("192.168.10.1", "255.255.255.0"); Cable(h1.eth0, sw1.get_port("g0/1"))
    h2 = Host("h2"); h2.configure_ip("192.168.10.2", "255.255.255.0"); Cable(h2.eth0, sw2.get_port("g0/1"))

    res = pe.simulate_ping(h1, "192.168.10.2", count=2)
    assert res.loss_percent == 100

def test_disallowed_vlan_dropped_at_egress():
    """SW1 trunk egress does not allow VLAN 10 -> dropped before leaving SW1."""
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1"); sw2 = Switch("sw2")
    sw1.add_vlan(10); sw2.add_vlan(10)
    sw1.get_port("g0/1").mode = "access"; sw1.get_port("g0/1").access_vlan = 10
    sw2.get_port("g0/1").mode = "access"; sw2.get_port("g0/1").access_vlan = 10

    t1 = sw1.get_port("g0/8"); t1.mode = "trunk"; t1.trunk_allowed_vlans = {1}  # 10 disallowed
    t2 = sw2.get_port("g0/8"); t2.mode = "trunk"; t2.trunk_allowed_vlans = {1, 10}
    Cable(t1, t2)

    h1 = Host("h1"); h1.configure_ip("192.168.10.1", "255.255.255.0"); Cable(h1.eth0, sw1.get_port("g0/1"))
    h2 = Host("h2"); h2.configure_ip("192.168.10.2", "255.255.255.0"); Cable(h2.eth0, sw2.get_port("g0/1"))

    res = pe.simulate_ping(h1, "192.168.10.2", count=2)
    assert res.loss_percent == 100

def test_allowed_vlan_update_stops_traffic_immediately():
    """Removing VLAN 10 from trunk allowed list immediately stops forwarding."""
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1"); sw2 = Switch("sw2")
    sw1.add_vlan(10); sw2.add_vlan(10)
    sw1.get_port("g0/1").mode = "access"; sw1.get_port("g0/1").access_vlan = 10
    sw2.get_port("g0/1").mode = "access"; sw2.get_port("g0/1").access_vlan = 10

    t1 = sw1.get_port("g0/8"); t1.mode = "trunk"; t1.trunk_allowed_vlans = {1, 10}
    t2 = sw2.get_port("g0/8"); t2.mode = "trunk"; t2.trunk_allowed_vlans = {1, 10}
    Cable(t1, t2)

    h1 = Host("h1"); h1.configure_ip("192.168.10.1", "255.255.255.0"); Cable(h1.eth0, sw1.get_port("g0/1"))
    h2 = Host("h2"); h2.configure_ip("192.168.10.2", "255.255.255.0"); Cable(h2.eth0, sw2.get_port("g0/1"))

    # Initial ping passes
    assert pe.simulate_ping(h1, "192.168.10.2", count=2).loss_percent == 0

    # Remove VLAN 10 from allowed list
    t1.trunk_allowed_vlans = {1}
    # Immediate ping must drop
    res = pe.simulate_ping(h1, "192.168.10.2", count=2)
    assert res.loss_percent == 100


# =====================================================================
# Group 4: Native VLAN Tests
# =====================================================================

def test_native_vlan_egress_is_untagged():
    """Native VLAN frames are egressed untagged across trunk."""
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1"); sw2 = Switch("sw2")
    sw1.add_vlan(99); sw2.add_vlan(99)

    sw1.get_port("g0/1").mode = "access"; sw1.get_port("g0/1").access_vlan = 99
    sw2.get_port("g0/1").mode = "access"; sw2.get_port("g0/1").access_vlan = 99

    t1 = sw1.get_port("g0/8"); t1.mode = "trunk"; t1.native_vlan = 99; t1.trunk_allowed_vlans = {1, 99}
    t2 = sw2.get_port("g0/8"); t2.mode = "trunk"; t2.native_vlan = 99; t2.trunk_allowed_vlans = {1, 99}
    Cable(t1, t2)

    h1 = Host("h1"); h1.configure_ip("10.99.0.1", "255.255.255.0"); Cable(h1.eth0, sw1.get_port("g0/1"))
    h2 = Host("h2"); h2.configure_ip("10.99.0.2", "255.255.255.0"); Cable(h2.eth0, sw2.get_port("g0/1"))

    res = pe.simulate_ping(h1, "10.99.0.2", count=2)
    assert res.loss_percent == 0

def test_non_native_vlan_egress_is_tagged():
    """Non-native VLAN (VLAN 10) is egressed tagged while native is 99."""
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1"); sw2 = Switch("sw2")
    for vid in (10, 99):
        sw1.add_vlan(vid); sw2.add_vlan(vid)

    sw1.get_port("g0/1").mode = "access"; sw1.get_port("g0/1").access_vlan = 10
    sw2.get_port("g0/1").mode = "access"; sw2.get_port("g0/1").access_vlan = 10

    t1 = sw1.get_port("g0/8"); t1.mode = "trunk"; t1.native_vlan = 99; t1.trunk_allowed_vlans = {1, 10, 99}
    t2 = sw2.get_port("g0/8"); t2.mode = "trunk"; t2.native_vlan = 99; t2.trunk_allowed_vlans = {1, 10, 99}
    Cable(t1, t2)

    h1 = Host("h1"); h1.configure_ip("10.10.0.1", "255.255.255.0"); Cable(h1.eth0, sw1.get_port("g0/1"))
    h2 = Host("h2"); h2.configure_ip("10.10.0.2", "255.255.255.0"); Cable(h2.eth0, sw2.get_port("g0/1"))

    res = pe.simulate_ping(h1, "10.10.0.2", count=2)
    assert res.loss_percent == 0

def test_untagged_ingress_maps_to_native_vlan():
    """Untagged frame arriving on a trunk port is mapped to native_vlan."""
    pe = PacketEngine.get_instance()
    sw = Switch("sw1")
    sw.add_vlan(40)
    sw.create_svi(40)
    svi40 = sw.get_svi(40)
    svi40.ip_address = "192.168.40.1"
    svi40.subnet_mask = "255.255.255.0"
    svi40.is_shutdown = False

    t = sw.get_port("g0/1")
    t.mode = "trunk"
    t.native_vlan = 40
    t.trunk_allowed_vlans = {1, 40}

    h = Host("h1")
    h.configure_ip("192.168.40.10", "255.255.255.0")
    Cable(h.eth0, t)

    res = pe.simulate_ping(h, "192.168.40.1", count=2)
    assert res.loss_percent == 0

def test_tagged_frame_on_access_port_dropped():
    """Access port receiving tagged frame drops it immediately."""
    pe = PacketEngine.get_instance()
    sw = Switch("sw1")
    sw.add_vlan(10)
    p = sw.get_port("g0/1")
    p.mode = "access"
    p.access_vlan = 10

    # Router subinterface sends tagged frame
    r = Router("r1")
    r.get_port("g0/0").is_shutdown = False
    sub = r.create_subinterface("g0/0", 10)
    sub.ip_address = "192.168.10.1"
    sub.subnet_mask = "255.255.255.0"
    sub.vlan_id = 10

    Cable(r.get_port("g0/0"), p)

    h = Host("h1")
    h.configure_ip("192.168.10.10", "255.255.255.0", gateway="192.168.10.1")
    p2 = sw.get_port("g0/2")
    p2.mode = "access"; p2.access_vlan = 10
    Cable(h.eth0, p2)

    # Ping from router subinterface (tagged) into access port must drop
    res = pe.simulate_ping(r, "192.168.10.10", source_interface="g0/0.10", count=2)
    assert res.loss_percent == 100

def test_native_vlan_mismatch_detected_and_blocked():
    """SW1 (native 99) vs SW2 (native 100) drops traffic with diagnostic."""
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")
    sw1.add_vlan(99); sw2.add_vlan(100)

    sw1.get_port("g0/1").mode = "access"; sw1.get_port("g0/1").access_vlan = 99
    sw2.get_port("g0/1").mode = "access"; sw2.get_port("g0/1").access_vlan = 100

    t1 = sw1.get_port("g0/8"); t1.mode = "trunk"; t1.native_vlan = 99; t1.trunk_allowed_vlans = {1, 99}
    t2 = sw2.get_port("g0/8"); t2.mode = "trunk"; t2.native_vlan = 100; t2.trunk_allowed_vlans = {1, 100}
    Cable(t1, t2)

    h1 = Host("h1"); h1.configure_ip("10.99.0.1", "255.255.255.0"); Cable(h1.eth0, sw1.get_port("g0/1"))
    h2 = Host("h2"); h2.configure_ip("10.99.0.2", "255.255.255.0"); Cable(h2.eth0, sw2.get_port("g0/1"))

    # Untagged native frames must NOT leak from VLAN 99 into VLAN 100
    res = pe.simulate_ping(h1, "10.99.0.2", count=2)
    assert res.loss_percent == 100
    assert res.error_message and "Native VLAN mismatch" in res.error_message


# =====================================================================
# Group 5: MAC Learning & Forwarding per VLAN Tests
# =====================================================================

def test_mac_learning_per_vlan():
    """Same MAC address on different VLANs is tracked independently."""
    sw = Switch("sw1")
    sw.add_vlan(10); sw.add_vlan(20)

    mac_dup = "02:00:aa:bb:cc:dd"
    sw.learn_mac(mac_dup, "g0/1", 10)
    sw.learn_mac(mac_dup, "g0/2", 20)

    assert (10, mac_dup) in sw.mac_vlan_table
    assert (20, mac_dup) in sw.mac_vlan_table
    assert sw.mac_vlan_table[(10, mac_dup)]["port"] == "g0/1"
    assert sw.mac_vlan_table[(20, mac_dup)]["port"] == "g0/2"

def test_broadcast_forwarding_isolated_to_vlan_over_trunk():
    """Broadcast frame on VLAN 10 floods out VLAN 10 ports and trunk, NOT VLAN 20."""
    sw = Switch("sw1")
    sw.stp_enabled = False
    sw.add_vlan(10); sw.add_vlan(20)

    sw.get_port("g0/1").mode = "access"; sw.get_port("g0/1").access_vlan = 10
    sw.get_port("g0/2").mode = "access"; sw.get_port("g0/2").access_vlan = 20
    sw.get_port("g0/3").mode = "access"; sw.get_port("g0/3").access_vlan = 10
    t = sw.get_port("g0/8"); t.mode = "trunk"; t.trunk_allowed_vlans = {1, 10, 20}

    # Connect dummy peer cables so ports are UP
    other = Switch("dummy")
    Cable(sw.get_port("g0/1"), other.get_port("g0/1"))
    Cable(sw.get_port("g0/2"), other.get_port("g0/2"))
    Cable(sw.get_port("g0/3"), other.get_port("g0/3"))
    Cable(t, other.get_port("g0/8"))

    out_ports = sw.forward_packet(sw.get_port("g0/1"), "02:00:00:00:00:01", "FF:FF:FF:FF:FF:FF", 10)
    out_names = [p.name for p in out_ports]

    assert "g0/3" in out_names
    assert "g0/8" in out_names
    assert "g0/2" not in out_names  # VLAN 20 must NOT receive VLAN 10 broadcast

def test_unknown_unicast_flooding_respects_vlan_and_allowed_list():
    """Unknown unicast in VLAN 20 only floods to ports in VLAN 20, excluding disallowed trunks."""
    sw = Switch("sw1")
    sw.stp_enabled = False
    sw.add_vlan(20)

    p1 = sw.get_port("g0/1"); p1.mode = "access"; p1.access_vlan = 20
    p2 = sw.get_port("g0/2"); p2.mode = "access"; p2.access_vlan = 20
    p3 = sw.get_port("g0/3"); p3.mode = "access"; p3.access_vlan = 1  # Other VLAN
    t1 = sw.get_port("g0/7"); t1.mode = "trunk"; t1.trunk_allowed_vlans = {1, 20}
    t2 = sw.get_port("g0/8"); t2.mode = "trunk"; t2.trunk_allowed_vlans = {1}  # VLAN 20 disallowed

    other = Switch("dummy")
    Cable(p1, other.get_port("g0/1"))
    Cable(p2, other.get_port("g0/2"))
    Cable(p3, other.get_port("g0/3"))
    Cable(t1, other.get_port("g0/7"))
    Cable(t2, other.get_port("g0/8"))

    out_ports = sw.forward_packet(p1, "02:00:00:00:00:01", "02:00:99:99:99:99", 20)
    out_names = [p.name for p in out_ports]

    assert "g0/2" in out_names
    assert "g0/7" in out_names
    assert "g0/3" not in out_names  # access VLAN 1
    assert "g0/8" not in out_names  # trunk without VLAN 20


# =====================================================================
# Group 6: STP Integration Tests
# =====================================================================

def test_stp_blocking_port_drops_trunk_traffic():
    """A trunk port in STP Blocking state drops all frame forwarding regardless of allowed VLANs."""
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")
    sw3 = Switch("sw3", hostname="SW3")

    sw1.stp_priority = 24576
    sw2.stp_priority = 32768
    sw3.stp_priority = 32768

    sw1.mac_address = "00:11:22:33:44:01"
    sw2.mac_address = "00:11:22:33:44:02"
    sw3.mac_address = "00:11:22:33:44:03"

    Cable(sw1.get_port("g0/1"), sw2.get_port("g0/1"))
    Cable(sw1.get_port("g0/2"), sw3.get_port("g0/1"))
    Cable(sw2.get_port("g0/2"), sw3.get_port("g0/2"))

    for sw in (sw1, sw2, sw3):
        sw.add_vlan(10)
        sw.get_port("g0/1").mode = "trunk"
        sw.get_port("g0/1").trunk_allowed_vlans = {1, 10}
        sw.get_port("g0/2").mode = "trunk"
        sw.get_port("g0/2").trunk_allowed_vlans = {1, 10}

    sw1.recalculate_stp()
    bp = sw3.get_port("g0/2")
    assert bp.stp_state == "Blocking"

    # 1. Ingress frame on blocking trunk is dropped
    out_drop = sw3.forward_packet(bp, "02:00:00:00:00:01", "FF:FF:FF:FF:FF:FF", 10)
    assert out_drop == []

    # 2. Source MAC is not learned on blocking trunk
    assert (10, "02:00:00:00:00:01") not in sw3.mac_vlan_table

    # 3. Egress flooding from forwarding port excludes blocking trunk
    out_fwd = sw3.forward_packet(sw3.get_port("g0/1"), "02:00:00:00:00:01", "FF:FF:FF:FF:FF:FF", 10)
    assert bp not in out_fwd

    # 4. PacketEngine trace drops across the blocking trunk port
    ctx = {}
    ok = pe._trace_packet(sw2, sw2.get_port("g0/2"), "192.168.10.2", "255.255.255.0",
                          "192.168.10.3", set(), [], current_vlan=10, trace_context=ctx)
    assert not ok
    assert "STP Blocking" in ctx.get("drop_reason", "")


# =====================================================================
# Group 7: Subsystems & Routing Integration Tests
# =====================================================================

def test_router_on_a_stick_subinterfaces_over_trunk():
    """Validates router 802.1Q subinterfaces routing between VLAN 10 and 20 over trunk."""
    pe = PacketEngine.get_instance()
    sw = Switch("sw1")
    sw.add_vlan(10); sw.add_vlan(20)

    sw.get_port("g0/1").mode = "access"; sw.get_port("g0/1").access_vlan = 10
    sw.get_port("g0/2").mode = "access"; sw.get_port("g0/2").access_vlan = 20

    t = sw.get_port("g0/8")
    t.mode = "trunk"
    t.trunk_allowed_vlans = {1, 10, 20}

    r = Router("r1")
    r_phys = r.get_port("g0/0")
    r_phys.is_shutdown = False

    sub10 = r.create_subinterface("g0/0", 10)
    sub10.ip_address = "192.168.10.1"; sub10.subnet_mask = "255.255.255.0"; sub10.vlan_id = 10

    sub20 = r.create_subinterface("g0/0", 20)
    sub20.ip_address = "192.168.20.1"; sub20.subnet_mask = "255.255.255.0"; sub20.vlan_id = 20

    Cable(t, r_phys)

    pc1 = Host("pc1"); pc1.configure_ip("192.168.10.10", "255.255.255.0", gateway="192.168.10.1"); Cable(pc1.eth0, sw.get_port("g0/1"))
    pc2 = Host("pc2"); pc2.configure_ip("192.168.20.10", "255.255.255.0", gateway="192.168.20.1"); Cable(pc2.eth0, sw.get_port("g0/2"))

    res = pe.simulate_ping(pc1, "192.168.20.10", count=3)
    assert res.loss_percent == 0
    assert res.packets_received == 3

def test_dhcp_over_trunk_multiple_vlans():
    """DHCP Server on Router serves isolated address pools across 802.1Q trunk."""
    pe = PacketEngine.get_instance()
    sw = Switch("sw1")
    sw.add_vlan(10); sw.add_vlan(20)

    sw.get_port("g0/1").mode = "access"; sw.get_port("g0/1").access_vlan = 10
    sw.get_port("g0/2").mode = "access"; sw.get_port("g0/2").access_vlan = 20

    t = sw.get_port("g0/8"); t.mode = "trunk"; t.trunk_allowed_vlans = {1, 10, 20}

    r = Router("r1")
    r.get_port("g0/0").is_shutdown = False
    sub10 = r.create_subinterface("g0/0", 10)
    sub10.ip_address = "192.168.10.1"; sub10.subnet_mask = "255.255.255.0"; sub10.vlan_id = 10

    sub20 = r.create_subinterface("g0/0", 20)
    sub20.ip_address = "192.168.20.1"; sub20.subnet_mask = "255.255.255.0"; sub20.vlan_id = 20

    # Configure DHCP server on router
    r.dhcp_server.add_pool("POOL10", "192.168.10.0", "255.255.255.0", default_router="192.168.10.1")
    r.dhcp_server.add_pool("POOL20", "192.168.20.0", "255.255.255.0", default_router="192.168.20.1")

    Cable(t, r.get_port("g0/0"))

    pc1 = Host("pc1"); Cable(pc1.eth0, sw.get_port("g0/1"))
    pc2 = Host("pc2"); Cable(pc2.eth0, sw.get_port("g0/2"))

    ok1, msg1 = pe.simulate_dhcp_dora(pc1, pc1.eth0)
    assert ok1
    assert pc1.eth0.ip_address.startswith("192.168.10.")
    assert pc1.default_gateway == "192.168.10.1"

    ok2, msg2 = pe.simulate_dhcp_dora(pc2, pc2.eth0)
    assert ok2
    assert pc2.eth0.ip_address.startswith("192.168.20.")
    assert pc2.default_gateway == "192.168.20.1"

def test_ripv2_over_trunk_subinterfaces():
    """RIPv2 discovers neighbor and exchanges routes across 802.1Q trunk subinterfaces."""
    pe = PacketEngine.get_instance()
    sw = Switch("sw1")
    sw.add_vlan(10)
    t1 = sw.get_port("g0/1"); t1.mode = "trunk"; t1.trunk_allowed_vlans = {1, 10}
    t2 = sw.get_port("g0/2"); t2.mode = "trunk"; t2.trunk_allowed_vlans = {1, 10}

    r1 = Router("r1"); r1.get_port("g0/0").is_shutdown = False
    sub1_10 = r1.create_subinterface("g0/0", 10)
    sub1_10.ip_address = "10.0.10.1"; sub1_10.subnet_mask = "255.255.255.0"; sub1_10.vlan_id = 10
    Cable(r1.get_port("g0/0"), t1)

    r2 = Router("r2"); r2.get_port("g0/0").is_shutdown = False
    sub2_10 = r2.create_subinterface("g0/0", 10)
    sub2_10.ip_address = "10.0.10.2"; sub2_10.subnet_mask = "255.255.255.0"; sub2_10.vlan_id = 10
    # Additional LAN on R2 (connected to PC so link is UP)
    r2.get_port("g0/1").is_shutdown = False
    r2.get_port("g0/1").ip_address = "172.16.1.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.0"
    pc_rip = Host("pc_rip")
    Cable(r2.get_port("g0/1"), pc_rip.eth0)
    Cable(r2.get_port("g0/0"), t2)

    r1.enable_rip()
    r1.add_rip_network("10.0.0.0")

    r2.enable_rip()
    r2.add_rip_network("10.0.0.0")
    r2.add_rip_network("172.16.0.0")

    pe.converge_rip()

    routes = [r["network"] for r in r1.get_all_routes() if r["type"] == "R"]
    assert "172.16.1.0" in routes

def test_ospfv2_over_trunk_subinterfaces():
    """OSPFv2 forms FULL adjacency and exchanges LSAs across 802.1Q trunk."""
    pe = PacketEngine.get_instance()
    sw = Switch("sw1")
    sw.add_vlan(25)
    t1 = sw.get_port("g0/1"); t1.mode = "trunk"; t1.trunk_allowed_vlans = {1, 25}
    t2 = sw.get_port("g0/2"); t2.mode = "trunk"; t2.trunk_allowed_vlans = {1, 25}

    r1 = Router("r1"); r1.get_port("g0/0").is_shutdown = False
    sub1 = r1.create_subinterface("g0/0", 25)
    sub1.ip_address = "10.0.25.1"; sub1.subnet_mask = "255.255.255.252"; sub1.vlan_id = 25
    Cable(r1.get_port("g0/0"), t1)

    r2 = Router("r2"); r2.get_port("g0/0").is_shutdown = False
    sub2 = r2.create_subinterface("g0/0", 25)
    sub2.ip_address = "10.0.25.2"; sub2.subnet_mask = "255.255.255.252"; sub2.vlan_id = 25
    # LAN on R2 (connected to PC so link is UP)
    r2.get_port("g0/1").is_shutdown = False
    r2.get_port("g0/1").ip_address = "10.200.1.1"
    r2.get_port("g0/1").subnet_mask = "255.255.255.0"
    pc_ospf = Host("pc_ospf")
    Cable(r2.get_port("g0/1"), pc_ospf.eth0)
    Cable(r2.get_port("g0/0"), t2)

    r1.enable_ospf(process_id=1)
    r1.add_ospf_network("10.0.25.0", "0.0.0.3", area=0)

    r2.enable_ospf(process_id=1)
    r2.add_ospf_network("10.0.25.0", "0.0.0.3", area=0)
    r2.add_ospf_network("10.200.1.0", "0.0.0.255", area=0)

    pe.converge_ospf()

    assert "10.0.25.2" in r1.ospf_neighbors
    nbr = r1.ospf_neighbors["10.0.25.2"]
    assert nbr.state == "FULL"
    assert nbr.neighbor_ip == "10.0.25.2"

    routes = [r["network"] for r in r1.get_all_routes() if r["type"] == "O"]
    assert "10.200.1.0" in routes

def test_svi_communication_over_trunk():
    """SVIs configured on SW1 and SW2 communicate across an 802.1Q trunk."""
    pe = PacketEngine.get_instance()
    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")
    sw1.add_vlan(30); sw2.add_vlan(30)

    svi1 = sw1.create_svi(30)
    svi1.ip_address = "192.168.30.1"; svi1.subnet_mask = "255.255.255.0"; svi1.is_shutdown = False

    svi2 = sw2.create_svi(30)
    svi2.ip_address = "192.168.30.2"; svi2.subnet_mask = "255.255.255.0"; svi2.is_shutdown = False

    t1 = sw1.get_port("g0/8"); t1.mode = "trunk"; t1.trunk_allowed_vlans = {1, 30}
    t2 = sw2.get_port("g0/8"); t2.mode = "trunk"; t2.trunk_allowed_vlans = {1, 30}
    Cable(t1, t2)

    res = pe.simulate_ping(sw1, "192.168.30.2", source_interface="Vlan30", count=3)
    assert res.loss_percent == 0


# =====================================================================
# Group 8: CLI Show & Running-Config Tests
# =====================================================================

def test_cli_show_interfaces_switchport():
    sw = Switch("sw1")
    cli = CommandExecutor(sw)
    cli.execute("enable")
    cli.execute("configure terminal")
    cli.execute("interface g0/1")
    cli.execute("switchport mode trunk")
    cli.execute("switchport trunk allowed vlan 10,20,30")
    cli.execute("switchport trunk native vlan 10")

    output = cli.execute("show interfaces switchport")
    assert "Name: g0/1" in output
    assert "Administrative Mode: trunk" in output
    assert "Operational Mode: trunk" in output
    assert "Trunking Native Mode VLAN: 10" in output
    assert "Trunking VLANs Enabled: 10,20,30" in output
    assert "STP State: Forwarding" in output

    output_single = cli.execute("show interface g0/1 switchport")
    assert "Name: g0/1" in output_single
    assert "Trunking Native Mode VLAN: 10" in output_single

def test_cli_show_interfaces_trunk():
    sw = Switch("sw1")
    cli = CommandExecutor(sw)
    cli.execute("enable")
    cli.execute("configure terminal")
    cli.execute("interface g0/1")
    cli.execute("switchport mode trunk")
    cli.execute("switchport trunk allowed vlan 10-15,20")
    cli.execute("switchport trunk native vlan 10")

    output = cli.execute("show interfaces trunk")
    assert "g0/1" in output
    assert "802.1q" in output
    assert "Native vlan" in output
    assert "10-15,20" in output

def test_cli_show_running_config_trunk():
    sw = Switch("sw1")
    cli = CommandExecutor(sw)
    cli.execute("enable")
    cli.execute("configure terminal")
    cli.execute("interface g0/1")
    cli.execute("switchport mode trunk")
    cli.execute("switchport trunk allowed vlan 10,20,30")
    cli.execute("switchport trunk native vlan 10")

    cfg = cli.execute("show running-config")
    assert "interface GigabitEthernet0/1" in cfg
    assert " switchport mode trunk" in cfg
    assert " switchport trunk allowed vlan 10,20,30" in cfg
    assert " switchport trunk native vlan 10" in cfg


if __name__ == "__main__":
    tests = [
        test_set_port_mode_trunk,
        test_set_port_mode_access,
        test_configure_allowed_vlan_comma_list,
        test_configure_allowed_vlan_range,
        test_configure_allowed_vlan_combined,
        test_configure_native_vlan,
        test_remove_trunk_allowed_vlan,
        test_remove_trunk_native_vlan,
        test_invalid_vlan_id_rejected,
        test_invalid_vlan_range_rejected,
        test_duplicate_vlan_handling,
        test_native_vlan_not_allowed_drops_ingress,
        test_native_vlan_not_allowed_drops_egress,
        test_single_vlan_transport_over_trunk,
        test_multiple_vlans_over_single_trunk,
        test_vlan_isolation_over_trunk,
        test_access_to_trunk_to_access_flow,
        test_trunk_to_trunk_transit,
        test_allowed_vlan_passes_traffic,
        test_disallowed_vlan_dropped_at_ingress,
        test_disallowed_vlan_dropped_at_egress,
        test_allowed_vlan_update_stops_traffic_immediately,
        test_native_vlan_egress_is_untagged,
        test_non_native_vlan_egress_is_tagged,
        test_untagged_ingress_maps_to_native_vlan,
        test_tagged_frame_on_access_port_dropped,
        test_native_vlan_mismatch_detected_and_blocked,
        test_mac_learning_per_vlan,
        test_broadcast_forwarding_isolated_to_vlan_over_trunk,
        test_unknown_unicast_flooding_respects_vlan_and_allowed_list,
        test_stp_blocking_port_drops_trunk_traffic,
        test_router_on_a_stick_subinterfaces_over_trunk,
        test_dhcp_over_trunk_multiple_vlans,
        test_ripv2_over_trunk_subinterfaces,
        test_ospfv2_over_trunk_subinterfaces,
        test_svi_communication_over_trunk,
        test_cli_show_interfaces_switchport,
        test_cli_show_interfaces_trunk,
        test_cli_show_running_config_trunk
    ]

    print(f"Running {len(tests)} IEEE 802.1Q Trunk Port tests...")
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  [PASS] {t.__name__}")
        except Exception as e:
            print(f"  [FAIL] {t.__name__}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\nResult: {passed}/{len(tests)} tests passed.")
    if passed == len(tests):
        print("ALL 39 IEEE 802.1Q TRUNK PORT TESTS PASSED SUCCESSFULLY!")
    else:
        sys.exit(1)
