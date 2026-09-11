"""
tests/test_firewall.py - Tests for Stateful Firewall Inspection (Cisco ASA Style)
Validates:
1. Security zones and levels (inside=100, dmz=50, outside=0).
2. Outbound traffic (higher -> lower security) permitted statefully and adds connection to session table.
3. Return traffic (lower -> higher security) matching established connection is PERMITTED statefully.
4. Unsolicited inbound traffic without ACL is DROPPED by default security policy.
5. Inbound traffic with explicit extended ACL is PERMITTED.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.firewall import Firewall
from network.host import Host
from network.cable import Cable, CableType
from network.packet_engine import PacketEngine

def test_firewall_stateful_session_and_return_traffic():
    pe = PacketEngine.get_instance()

    fw = Firewall("fw1", hostname="ASA-5506")
    fg1 = fw.get_port("g0/1")
    fg1.ip_address = "192.168.1.1"
    fg1.subnet_mask = "255.255.255.0"
    fg1.is_shutdown = False
    fw.set_nameif("g0/1", "inside")
    fw.set_security_level("inside", 100)

    fg0 = fw.get_port("g0/0")
    fg0.ip_address = "203.0.113.1"
    fg0.subnet_mask = "255.255.255.0"
    fg0.is_shutdown = False
    fw.set_nameif("g0/0", "outside")
    fw.set_security_level("outside", 0)

    inside_host = Host("in_host", hostname="Inside-Client")
    inside_host.configure_ip("192.168.1.50", "255.255.255.0", gateway="192.168.1.1")

    outside_server = Host("out_server", hostname="Outside-Server")
    outside_server.configure_ip("203.0.113.50", "255.255.255.0", gateway="203.0.113.1")

    c_in = Cable(inside_host.eth0, fg1, CableType.CAT6)
    c_out = Cable(fg0, outside_server.eth0, CableType.CAT6)

    # 1. Outbound Ping: Inside (sec 100) -> Outside (sec 0)
    # Both Echo Request (Inside -> Outside) and Echo Reply (Outside -> Inside) must succeed statefully!
    res_out = pe.simulate_ping(inside_host, "203.0.113.50", count=3)
    assert res_out.loss_percent == 0
    assert res_out.packets_received == 3
    assert res_out.success_rate_cisco == "!!!"

    # Verify session recorded in connection table
    assert len(fw.connections) >= 1
    conn = fw.connections[0]
    assert conn["src_ip"] == "192.168.1.50"
    assert conn["dst_ip"] == "203.0.113.50"

    # 2. Unsolicited Inbound Ping: Outside (sec 0) -> Inside (sec 100)
    # Must be dropped by default policy (Status 'A')
    res_in_unsolicited = pe.simulate_ping(outside_server, "192.168.1.50", count=3)
    assert res_in_unsolicited.packets_received == 0
    assert res_in_unsolicited.status_codes == ["A", "A", "A"]
    assert "default security policy" in res_in_unsolicited.error_message.lower()

    # 3. Configure Extended ACL to permit inbound ICMP:
    fw.add_access_list("OUTSIDE_ACCESS", "permit", "icmp", "203.0.113.50", "192.168.1.50")
    fw.set_access_group("OUTSIDE_ACCESS", "in", "outside")

    # Inbound Ping should now SUCCEED!
    res_in_acl = pe.simulate_ping(outside_server, "192.168.1.50", count=3)
    assert res_in_acl.loss_percent == 0
    assert res_in_acl.packets_received == 3
    assert res_in_acl.success_rate_cisco == "!!!"

def test_firewall_zone_security_levels():
    fw = Firewall("fw1")
    assert fw.security_levels["inside"] == 100
    assert fw.security_levels["outside"] == 0
    assert fw.security_levels["dmz"] == 50

    # Modify security level
    fw.set_security_level("dmz", 75)
    assert fw.security_levels["dmz"] == 75

if __name__ == "__main__":
    test_firewall_stateful_session_and_return_traffic()
    test_firewall_zone_security_levels()
    print("ALL FIREWALL TESTS PASSED!")
