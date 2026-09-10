"""
tests/test_network.py - Automated tests for Network Simulation Engine
"""

import os
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from network.router import Router
from network.switch import Switch
from network.host import Host
from network.cable import Cable, CableType
from network.packet_engine import PacketEngine

def test_packet_flow():
    # Setup Topology: Server (192.168.1.10) <-> Switch <-> Router (192.168.1.1 / 10.0.0.1) <-> Host2 (10.0.0.2)
    server = Host("srv1", hostname="Web-Server-01")
    server.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    switch = Switch("sw1", hostname="Core-Switch-01")

    router = Router("rtr1", hostname="Edge-Router-01")
    # Configure Router g0/0 with 192.168.1.1
    rg0 = router.get_port("g0/0")
    rg0.ip_address = "192.168.1.1"
    rg0.subnet_mask = "255.255.255.0"
    rg0.is_shutdown = False

    # Configure Router g0/1 with 10.0.0.1
    rg1 = router.get_port("g0/1")
    rg1.ip_address = "10.0.0.1"
    rg1.subnet_mask = "255.255.255.0"
    rg1.is_shutdown = False

    host2 = Host("pc1", hostname="Finance-PC")
    host2.configure_ip("10.0.0.2", "255.255.255.0", gateway="10.0.0.1")

    # Connect Cables:
    # 1. Server eth0 -> Switch g0/1
    c1 = Cable(server.eth0, switch.get_port("g0/1"), CableType.CAT6)
    # 2. Switch g0/2 -> Router g0/0
    c2 = Cable(switch.get_port("g0/2"), router.get_port("g0/0"), CableType.CAT6)
    # 3. Router g0/1 -> Host2 eth0
    c3 = Cable(router.get_port("g0/1"), host2.eth0, CableType.CAT6)

    engine = PacketEngine.get_instance()

    # Test 1: Ping gateway from Server
    res1 = engine.simulate_ping(server, "192.168.1.1", count=5)
    print(f"Ping Server -> Gateway: {res1.success_rate_cisco} (Loss: {res1.loss_percent}%)")
    assert res1.loss_percent == 0, "Ping to gateway should succeed 100%"

    # Test 2: Ping Host2 across router
    res2 = engine.simulate_ping(server, "10.0.0.2", count=5)
    print(f"Ping Server -> Host2 (cross-subnet): {res2.success_rate_cisco} (Loss: {res2.loss_percent}%)")
    assert res2.loss_percent == 0, "Ping across router should succeed 100%"

    # Test 3: Ping non-existent IP
    res3 = engine.simulate_ping(server, "192.168.99.99", count=3)
    print(f"Ping Server -> Non-existent IP: {res3.success_rate_cisco} (Loss: {res3.loss_percent}%)")
    assert res3.loss_percent == 100, "Ping to unrouted IP should fail 100%"

    # Test 4: Disconnect cable and verify fail
    c1.disconnect()
    res4 = engine.simulate_ping(server, "192.168.1.1", count=3)
    print(f"Ping after cable disconnect: {res4.success_rate_cisco} (Loss: {res4.loss_percent}%)")
    assert res4.loss_percent == 100, "Ping with unplugged cable should fail"

    print("ALL NETWORK SIMULATION TESTS PASSED!")

if __name__ == "__main__":
    test_packet_flow()
