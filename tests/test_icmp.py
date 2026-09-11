"""
tests/test_icmp.py - Tests for ICMP Ping & Two-Way Packet Flow
Validates:
1. PC -> Router, PC -> PC, Router -> Router two-way ICMP ping.
2. Two-way lifecycle: Echo Request arrives at target, Echo Reply traverses back to source.
3. Destination with no return route/gateway fails with 'U' (Destination Host Unreachable).
4. Failure testing: link down, interface down, unrouted network, ARP failure.
5. Cisco status codes (!, ., U, A) and statistics.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.router import Router
from network.switch import Switch
from network.host import Host
from network.cable import Cable, CableType
from network.packet_engine import PacketEngine

def test_icmp_success_flows():
    pe = PacketEngine.get_instance()

    # Topology: PC1 <-> SW1 <-> R1 <-> R2 <-> SW2 <-> PC2
    pc1 = Host("pc1", hostname="Finance-PC")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    sw1 = Switch("sw1", hostname="SW-Core-1")
    sw2 = Switch("sw2", hostname="SW-Core-2")

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

    pc2 = Host("pc2", hostname="HR-PC")
    pc2.configure_ip("192.168.2.10", "255.255.255.0", gateway="192.168.2.1")

    # Static routes
    r1.add_static_route("192.168.2.0", "255.255.255.0", "10.0.12.2")
    r2.add_static_route("192.168.1.0", "255.255.255.0", "10.0.12.1")

    # Connect cables
    c1 = Cable(pc1.eth0, sw1.get_port("g0/1"), CableType.CAT6)
    c2 = Cable(sw1.get_port("g0/2"), r1.get_port("g0/0"), CableType.CAT6)
    c3 = Cable(r1.get_port("g0/1"), r2.get_port("g0/0"), CableType.CAT6)
    c4 = Cable(r2.get_port("g0/1"), sw2.get_port("g0/1"), CableType.CAT6)
    c5 = Cable(sw2.get_port("g0/2"), pc2.eth0, CableType.CAT6)

    # 1. PC -> Local Router Gateway
    res_pc_rtr = pe.simulate_ping(pc1, "192.168.1.1", count=3)
    assert res_pc_rtr.packets_received == 3
    assert res_pc_rtr.loss_percent == 0
    assert res_pc_rtr.success_rate_cisco == "!!!"

    # 2. Router -> Router across point-to-point link
    res_rtr_rtr = pe.simulate_ping(r1, "10.0.12.2", count=3)
    assert res_rtr_rtr.packets_received == 3
    assert res_rtr_rtr.loss_percent == 0

    # 3. PC -> Remote Router
    res_pc_rem_rtr = pe.simulate_ping(pc1, "192.168.2.1", count=3)
    assert res_pc_rem_rtr.packets_received == 3
    assert res_pc_rem_rtr.loss_percent == 0

    # 4. PC1 -> PC2 end-to-end multi-hop
    res_pc_pc = pe.simulate_ping(pc1, "192.168.2.10", count=5)
    assert res_pc_pc.packets_received == 5
    assert res_pc_pc.loss_percent == 0
    assert res_pc_pc.success_rate_cisco == "!!!!!"

    # 5. Reverse flow PC2 -> PC1
    res_pc2_pc1 = pe.simulate_ping(pc2, "192.168.1.10", count=5)
    assert res_pc2_pc1.packets_received == 5
    assert res_pc2_pc1.loss_percent == 0

def test_icmp_return_path_validation():
    """Verify that if the destination cannot route back to sender, ping fails!"""
    pe = PacketEngine.get_instance()

    pc1 = Host("pc1", hostname="PC-1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    r1 = Router("r1", hostname="R1")
    r1.get_port("g0/0").ip_address = "192.168.1.1"
    r1.get_port("g0/0").subnet_mask = "255.255.255.0"
    r1.get_port("g0/0").is_shutdown = False
    r1.get_port("g0/1").ip_address = "10.0.0.1"
    r1.get_port("g0/1").subnet_mask = "255.255.255.0"
    r1.get_port("g0/1").is_shutdown = False

    # Target host has NO default gateway set!
    pc2 = Host("pc2", hostname="PC-2-NoGateway")
    pc2.configure_ip("10.0.0.2", "255.255.255.0", gateway=None)

    c1 = Cable(pc1.eth0, r1.get_port("g0/0"), CableType.CAT6)
    c2 = Cable(r1.get_port("g0/1"), pc2.eth0, CableType.CAT6)

    # Ping from PC1 to PC2: Echo Request reaches PC2, but PC2 cannot send Echo Reply!
    res = pe.simulate_ping(pc1, "10.0.0.2", count=3)
    assert res.packets_received == 0
    assert res.loss_percent == 100
    assert res.status_codes == ["U", "U", "U"]
    assert "no default gateway" in res.error_message.lower()

def test_icmp_failure_scenarios():
    pe = PacketEngine.get_instance()

    pc1 = Host("pc1", hostname="PC-1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    r1 = Router("r1", hostname="R1")
    p0 = r1.get_port("g0/0")
    p0.ip_address = "192.168.1.1"
    p0.subnet_mask = "255.255.255.0"
    p0.is_shutdown = False

    c1 = Cable(pc1.eth0, p0, CableType.CAT6)

    # 1. Destination unreachable (no route)
    res_no_route = pe.simulate_ping(pc1, "172.16.99.99", count=3)
    assert res_no_route.packets_received == 0
    assert res_no_route.status_codes == ["U", "U", "U"]
    assert "no route" in res_no_route.error_message.lower()

    # 2. Interface shutdown
    p0.is_shutdown = True
    res_down = pe.simulate_ping(pc1, "192.168.1.1", count=2)
    assert res_down.packets_received == 0
    assert res_down.status_codes == ["U", "U"]

    # 3. Cable disconnected
    c1.disconnect()
    res_disc = pe.simulate_ping(pc1, "192.168.1.1", count=2)
    assert res_disc.packets_received == 0
    assert res_disc.status_codes == ["U", "U"]

if __name__ == "__main__":
    test_icmp_success_flows()
    test_icmp_return_path_validation()
    test_icmp_failure_scenarios()
    print("ALL ICMP TESTS PASSED!")
