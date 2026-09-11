"""
tests/test_nat.py - Tests for Cisco IOS NAT/PAT & Reverse Translation
Validates:
1. Inside local -> Inside global source address transformation.
2. Outside -> Inside reverse destination translation on return traffic.
3. NAT translation table state tracking and clearing.
4. Traffic not matching the NAT ACL is not translated.
5. Bidirectional ping across NAT router.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.router import Router
from network.host import Host
from network.cable import Cable, CableType
from network.packet_engine import PacketEngine

def test_nat_forward_and_reverse_translation():
    pe = PacketEngine.get_instance()

    # Topology:
    # Inside Host (192.168.1.10) <-> R1 (inside g0/1: 192.168.1.1, outside g0/0: 203.0.113.2) <-> Outside Host (203.0.113.50)
    inside_host = Host("in_host", hostname="Inside-PC")
    inside_host.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    r1 = Router("r1", hostname="NAT-Router")
    rg1 = r1.get_port("g0/1")
    rg1.ip_address = "192.168.1.1"
    rg1.subnet_mask = "255.255.255.0"
    rg1.is_shutdown = False
    r1.nat_inside_interfaces.add("g0/1")

    rg0 = r1.get_port("g0/0")
    rg0.ip_address = "203.0.113.2"
    rg0.subnet_mask = "255.255.255.0"
    rg0.is_shutdown = False
    r1.nat_outside_interfaces.add("g0/0")

    outside_host = Host("out_host", hostname="Outside-Server")
    outside_host.configure_ip("203.0.113.50", "255.255.255.0", gateway="203.0.113.2")

    c_in = Cable(inside_host.eth0, rg1, CableType.CAT6)
    c_out = Cable(rg0, outside_host.eth0, CableType.CAT6)

    # Configure NAT:
    # access-list 1 permit 192.168.1.0 0.0.0.255
    r1.add_access_list(1, "permit", "192.168.1.0", "0.0.0.255")
    # ip nat inside source list 1 interface g0/0 overload
    r1.add_nat_rule("overload", 1, "g0/0")

    # 1. Test perform_nat forward translation
    out_ip, entry = r1.perform_nat("192.168.1.10", "g0/1", "g0/0", protocol="icmp")
    assert out_ip == "203.0.113.2"
    assert entry is not None
    assert "192.168.1.10:1" in entry["inside_local"]
    assert "203.0.113.2:1" in entry["inside_global"]

    # 2. Test perform_reverse_nat for return traffic
    rev_ip, rev_entry = r1.perform_reverse_nat("203.0.113.2", "g0/0", protocol="icmp")
    assert rev_ip == "192.168.1.10"
    assert rev_entry is not None
    assert rev_entry == entry

    # 3. End-to-end ping Inside -> Outside Server
    res = pe.simulate_ping(inside_host, "203.0.113.50", count=3)
    assert res.loss_percent == 0
    assert res.packets_received == 3
    assert res.success_rate_cisco == "!!!"

    # 4. Verify NAT table has active translations
    assert len(r1.nat_translations) >= 1

    # 5. Clear NAT translations
    count = r1.clear_nat_translations()
    assert count >= 1
    assert len(r1.nat_translations) == 0

def test_nat_acl_unmatched_traffic():
    r1 = Router("r1", hostname="NAT-Router")
    r1.nat_inside_interfaces.add("g0/1")
    r1.nat_outside_interfaces.add("g0/0")
    r1.get_port("g0/0").ip_address = "203.0.113.2"
    r1.get_port("g0/0").is_shutdown = False

    # ACL permits only 10.0.0.0/24
    r1.add_access_list(5, "permit", "10.0.0.0", "0.0.0.255")
    r1.add_nat_rule("overload", 5, "g0/0")

    # 192.168.1.50 does not match ACL 5
    out_ip, entry = r1.perform_nat("192.168.1.50", "g0/1", "g0/0", protocol="icmp")
    assert out_ip is None
    assert entry is None

if __name__ == "__main__":
    test_nat_forward_and_reverse_translation()
    test_nat_acl_unmatched_traffic()
    print("ALL NAT TESTS PASSED!")
