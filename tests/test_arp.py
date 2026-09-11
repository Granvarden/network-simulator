"""
tests/test_arp.py - Tests for ARP Implementation & Behavior
Validates:
1. Cold ARP cache drop (.!!!!) on first ping.
2. Immediate ARP cache hit (!!!!!) on subsequent ping.
3. ARP table lookup and clear_arp flushing.
4. ARP failure handling for non-existent destination.
5. VLAN isolation during ARP: Host in VLAN 10 CANNOT resolve ARP for Host in VLAN 20 directly through Switch without router.
6. Router ARP behavior across subnets.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.router import Router
from network.switch import Switch
from network.host import Host
from network.cable import Cable, CableType
from network.packet_engine import PacketEngine

def test_arp_cache_hit_and_miss():
    pe = PacketEngine.get_instance()

    r1 = Router("r1", hostname="Router-1")
    p0 = r1.get_port("g0/0")
    p0.ip_address = "192.168.1.1"
    p0.subnet_mask = "255.255.255.0"
    p0.is_shutdown = False

    h1 = Host("h1", hostname="Host-1")
    h1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    c = Cable(p0, h1.eth0, CableType.CAT6)

    # Initial empty cache
    h1.clear_arp()
    r1.clear_arp()
    assert len(h1.arp_table) == 0

    # 1. Cold ARP cache drop: first packet drops with '.' while resolving ARP
    res_cold = pe.simulate_ping(h1, "192.168.1.1", count=5, simulate_arp=True)
    assert res_cold.success_rate_cisco == ".!!!!"
    assert res_cold.packets_received == 4
    assert res_cold.loss_percent == 20

    # 2. Verify ARP table populated
    entry = h1.lookup_arp("192.168.1.1")
    assert entry is not None
    assert "mac" in entry
    assert entry["mac"] == p0.mac_address

    # 3. Warm ARP cache hit: all 5 packets succeed immediately
    res_warm = pe.simulate_ping(h1, "192.168.1.1", count=5, simulate_arp=True)
    assert res_warm.success_rate_cisco == "!!!!!"
    assert res_warm.packets_received == 5
    assert res_warm.loss_percent == 0

    # 4. Clear ARP flushes cache
    h1.clear_arp()
    assert len(h1.arp_table) == 0
    assert h1.lookup_arp("192.168.1.1") is None

    # First packet drops again after flush
    res_flushed = pe.simulate_ping(h1, "192.168.1.1", count=5, simulate_arp=True)
    assert res_cold.success_rate_cisco == ".!!!!"

def test_arp_unreachable_destination():
    pe = PacketEngine.get_instance()

    h1 = Host("h1", hostname="Host-1")
    h1.configure_ip("192.168.1.10", "255.255.255.0")

    sw = Switch("sw1", hostname="SW-1")
    c1 = Cable(h1.eth0, sw.get_port("g0/1"), CableType.CAT6)

    # Ping non-existent host in same subnet
    res = pe.simulate_ping(h1, "192.168.1.99", count=3, simulate_arp=True)
    assert res.packets_received == 0
    assert res.loss_percent == 100
    assert res.status_codes == [".", ".", "."]
    assert h1.lookup_arp("192.168.1.99") is None

def test_arp_vlan_isolation():
    """Verify that ARP does NOT leak across isolated VLANs on a switch."""
    pe = PacketEngine.get_instance()

    sw = Switch("sw1", hostname="Core-Switch")
    sw.add_vlan(10, "Sales")
    sw.add_vlan(20, "Engineering")

    # Port g0/1 in VLAN 10
    sw.get_port("g0/1").access_vlan = 10
    # Port g0/2 in VLAN 20
    sw.get_port("g0/2").access_vlan = 20

    h1 = Host("h1", hostname="Sales-PC")
    h1.configure_ip("192.168.1.10", "255.255.255.0")

    h2 = Host("h2", hostname="Eng-PC")
    h2.configure_ip("192.168.1.20", "255.255.255.0")

    c1 = Cable(h1.eth0, sw.get_port("g0/1"), CableType.CAT6)
    c2 = Cable(h2.eth0, sw.get_port("g0/2"), CableType.CAT6)

    # h1 attempts ARP resolution for h2 across switch
    h1.clear_arp()
    res = pe.simulate_ping(h1, "192.168.1.20", count=3, simulate_arp=True)
    # Must fail because VLAN 10 and VLAN 20 are isolated at Layer 2
    assert res.packets_received == 0
    assert res.loss_percent == 100
    assert h1.lookup_arp("192.168.1.20") is None

def test_router_arp_resolution():
    """Verify router properly resolves next-hop ARP during forwarding."""
    pe = PacketEngine.get_instance()

    r1 = Router("r1", hostname="Router-1")
    p0 = r1.get_port("g0/0")
    p0.ip_address = "192.168.1.1"
    p0.subnet_mask = "255.255.255.0"
    p0.is_shutdown = False

    p1 = r1.get_port("g0/1")
    p1.ip_address = "10.0.0.1"
    p1.subnet_mask = "255.255.255.0"
    p1.is_shutdown = False

    h1 = Host("h1", hostname="Host-1")
    h1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    h2 = Host("h2", hostname="Host-2")
    h2.configure_ip("10.0.0.2", "255.255.255.0", gateway="10.0.0.1")

    c1 = Cable(h1.eth0, p0, CableType.CAT6)
    c2 = Cable(p1, h2.eth0, CableType.CAT6)

    r1.clear_arp()
    res = pe.simulate_ping(h1, "10.0.0.2", count=2, simulate_arp=False)
    assert res.packets_received == 2
    # Verify router learned h2's MAC
    assert r1.lookup_arp("10.0.0.2") is not None
    assert r1.lookup_arp("10.0.0.2")["mac"] == h2.eth0.mac_address

if __name__ == "__main__":
    test_arp_cache_hit_and_miss()
    test_arp_unreachable_destination()
    test_arp_vlan_isolation()
    test_router_arp_resolution()
    print("ALL ARP TESTS PASSED!")
