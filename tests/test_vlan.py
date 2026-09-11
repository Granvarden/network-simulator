"""
tests/test_vlan.py - Tests for VLAN Membership, Isolation, and Inter-VLAN Routing
Validates:
1. Access VLAN isolation: PC1 (VLAN 10) and PC2 (VLAN 20) on same switch CANNOT communicate directly over Layer 2.
2. Trunk port forwarding with allowed VLANs filtering.
3. Inter-VLAN routing via Router-on-a-Stick (802.1Q subinterfaces):
   PC1 (VLAN 10) -> SW1 (Trunk) -> R1 (g0/0.10 & g0/0.20) -> SW1 -> PC2 (VLAN 20) SUCCEEDS!
4. Disallowed VLAN on trunk link is dropped.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.router import Router
from network.switch import Switch
from network.host import Host
from network.cable import Cable, CableType
from network.packet_engine import PacketEngine

def test_vlan_layer2_isolation():
    pe = PacketEngine.get_instance()

    sw = Switch("sw1", hostname="Access-Switch")
    sw.add_vlan(10, "Sales")
    sw.add_vlan(20, "Engineering")

    p1 = sw.get_port("g0/1")
    p1.mode = "access"
    p1.access_vlan = 10

    p2 = sw.get_port("g0/2")
    p2.mode = "access"
    p2.access_vlan = 20

    pc1 = Host("pc1", hostname="Sales-PC")
    pc1.configure_ip("192.168.10.10", "255.255.255.0")

    pc2 = Host("pc2", hostname="Eng-PC")
    pc2.configure_ip("192.168.10.20", "255.255.255.0")

    c1 = Cable(pc1.eth0, p1)
    c2 = Cable(pc2.eth0, p2)

    # Direct Layer 2 communication must FAIL due to VLAN isolation
    res = pe.simulate_ping(pc1, "192.168.10.20", count=3)
    assert res.loss_percent == 100
    assert res.packets_received == 0

def test_inter_vlan_routing_router_on_a_stick():
    """
    Topology:
    PC1 (192.168.10.10, VLAN 10) ---- SW1 (g0/1: acc 10)
                                      SW1 (g0/8: trunk 10,20) ---- R1 (g0/0.10: 192.168.10.1)
                                                                 R1 (g0/0.20: 192.168.20.1)
    PC2 (192.168.20.10, VLAN 20) ---- SW1 (g0/2: acc 20)
    """
    pe = PacketEngine.get_instance()

    sw = Switch("sw1", hostname="Core-Switch")
    sw.add_vlan(10, "Sales")
    sw.add_vlan(20, "Engineering")

    # Access ports
    sw.get_port("g0/1").mode = "access"
    sw.get_port("g0/1").access_vlan = 10

    sw.get_port("g0/2").mode = "access"
    sw.get_port("g0/2").access_vlan = 20

    # Trunk port to router
    trunk_port = sw.get_port("g0/8")
    trunk_port.mode = "trunk"
    trunk_port.trunk_allowed_vlans = {1, 10, 20}

    # Router with 802.1Q subinterfaces
    r1 = Router("r1", hostname="Router-on-a-Stick")
    r_phys = r1.get_port("g0/0")
    r_phys.is_shutdown = False

    sub10 = r1.create_subinterface("g0/0", 10)
    sub10.ip_address = "192.168.10.1"
    sub10.subnet_mask = "255.255.255.0"
    sub10.vlan_id = 10

    sub20 = r1.create_subinterface("g0/0", 20)
    sub20.ip_address = "192.168.20.1"
    sub20.subnet_mask = "255.255.255.0"
    sub20.vlan_id = 20

    pc1 = Host("pc1", hostname="PC-VLAN10")
    pc1.configure_ip("192.168.10.10", "255.255.255.0", gateway="192.168.10.1")

    pc2 = Host("pc2", hostname="PC-VLAN20")
    pc2.configure_ip("192.168.20.10", "255.255.255.0", gateway="192.168.20.1")

    # Connect cables
    c1 = Cable(pc1.eth0, sw.get_port("g0/1"))
    c2 = Cable(pc2.eth0, sw.get_port("g0/2"))
    c_trunk = Cable(trunk_port, r_phys)

    # 1. PC1 -> Gateway (subinterface g0/0.10)
    res_gw1 = pe.simulate_ping(pc1, "192.168.10.1", count=2)
    assert res_gw1.loss_percent == 0

    # 2. PC2 -> Gateway (subinterface g0/0.20)
    res_gw2 = pe.simulate_ping(pc2, "192.168.20.1", count=2)
    assert res_gw2.loss_percent == 0

    # 3. Inter-VLAN Routing: PC1 (VLAN 10) -> PC2 (VLAN 20) across Router
    res_inter = pe.simulate_ping(pc1, "192.168.20.10", count=5)
    assert res_inter.loss_percent == 0
    assert res_inter.packets_received == 5
    assert res_inter.success_rate_cisco == "!!!!!"

    # 4. Reverse Inter-VLAN: PC2 -> PC1
    res_rev = pe.simulate_ping(pc2, "192.168.10.10", count=5)
    assert res_rev.loss_percent == 0
    assert res_rev.packets_received == 5

    # 5. Trunk filtering: remove VLAN 20 from allowed trunk VLANs
    trunk_port.trunk_allowed_vlans = {1, 10} # 20 is not allowed
    res_filtered = pe.simulate_ping(pc1, "192.168.20.10", count=2)
    assert res_filtered.loss_percent == 100

if __name__ == "__main__":
    test_vlan_layer2_isolation()
    test_inter_vlan_routing_router_on_a_stick()
    print("ALL VLAN TESTS PASSED!")
