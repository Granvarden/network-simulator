"""
tests/test_acl.py - Tests for Access Control Lists (ACL) on Router
Validates:
1. Standard ACL permit and deny rules.
2. First-match rule ordering behavior.
3. Implicit deny at end of ACL.
4. Interface access-group application (ingress and egress).
5. Packet drop reason diagnostic reporting (identifying which rule denied the packet).
6. Topology tests:
   ALLOW: PC -> Router -> Server
   DENY: PC -> Router -X- Server (Status 'A' with exact rule message).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.router import Router
from network.host import Host
from network.cable import Cable, CableType
from network.packet_engine import PacketEngine

def test_acl_first_match_and_implicit_deny():
    r1 = Router("r1", hostname="Router-ACL")

    # ACL 10:
    # line 1: deny 192.168.1.50 0.0.0.0 (explicit host deny)
    # line 2: permit 192.168.1.0 0.0.0.255 (permit rest of subnet)
    # implicit deny at end
    r1.add_access_list(10, "deny", "192.168.1.50", "0.0.0.0")
    r1.add_access_list(10, "permit", "192.168.1.0", "0.0.0.255")

    # 1. Host 192.168.1.50 must be DENIED by line 1
    perm1, msg1 = r1.check_acl(10, "192.168.1.50")
    assert perm1 is False
    assert "line 1" in msg1
    assert "deny" in msg1

    # 2. Host 192.168.1.10 must be PERMITTED by line 2
    perm2, msg2 = r1.check_acl(10, "192.168.1.10")
    assert perm2 is True
    assert "line 2" in msg2
    assert "permit" in msg2

    # 3. Host 10.0.0.5 must be DENIED by implicit deny
    perm3, msg3 = r1.check_acl(10, "10.0.0.5")
    assert perm3 is False
    assert "implicit deny" in msg3

def test_router_interface_acl_forwarding():
    pe = PacketEngine.get_instance()

    # Topology: PC1 (192.168.1.10) <-> R1 (g0/0: 192.168.1.1, g0/1: 10.0.0.1) <-> Server (10.0.0.2)
    pc1 = Host("pc1", hostname="Finance-PC")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    r1 = Router("r1", hostname="R1")
    rg0 = r1.get_port("g0/0")
    rg0.ip_address = "192.168.1.1"
    rg0.subnet_mask = "255.255.255.0"
    rg0.is_shutdown = False

    rg1 = r1.get_port("g0/1")
    rg1.ip_address = "10.0.0.1"
    rg1.subnet_mask = "255.255.255.0"
    rg1.is_shutdown = False

    server = Host("server", hostname="App-Server")
    server.configure_ip("10.0.0.2", "255.255.255.0", gateway="10.0.0.1")

    c1 = Cable(pc1.eth0, rg0, CableType.CAT6)
    c2 = Cable(rg1, server.eth0, CableType.CAT6)

    # 1. ALLOW Scenario without ACL
    res_allow = pe.simulate_ping(pc1, "10.0.0.2", count=3)
    assert res_allow.loss_percent == 0
    assert res_allow.success_rate_cisco == "!!!"

    # 2. DENY Scenario: Apply ACL 20 on ingress of g0/0 to block 192.168.1.10
    r1.add_access_list(20, "deny", "192.168.1.10", "0.0.0.0")
    r1.add_access_list(20, "permit", "any", "0.0.0.0")
    r1.set_access_group(20, "in", "g0/0")

    step_deny = pe.trace_single_packet(pc1, "10.0.0.2")
    assert step_deny["success"] is False
    assert step_deny["status_code"] == "A"
    assert "denied by access-list 20" in step_deny["drop_reason"].lower()

    res_deny = pe.simulate_ping(pc1, "10.0.0.2", count=3)
    assert res_deny.packets_received == 0
    assert res_deny.status_codes == ["A", "A", "A"]

    # 3. Modify ACL to PERMIT PC1
    r1.access_lists["20"] = []
    r1.add_access_list(20, "permit", "192.168.1.10", "0.0.0.0")
    res_permit = pe.simulate_ping(pc1, "10.0.0.2", count=3)
    assert res_permit.loss_percent == 0
    assert res_permit.success_rate_cisco == "!!!"

if __name__ == "__main__":
    test_acl_first_match_and_implicit_deny()
    test_router_interface_acl_forwarding()
    print("ALL ACL TESTS PASSED!")
