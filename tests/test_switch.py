"""
tests/test_switch.py - Tests for Layer 2 Managed Switch Implementation
Validates:
1. Source MAC learning into mac_table.
2. Destination MAC lookup in mac_table.
3. Known unicast forwarding to single target port.
4. Unknown unicast & broadcast flooding to all active ports in the same VLAN.
5. Port state handling (shutdown, no cable).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.switch import Switch
from network.host import Host
from network.cable import Cable, CableType
from network.packet_engine import PacketEngine

def test_switch_mac_learning_and_unicast():
    sw = Switch("sw1", hostname="Core-Switch")
    p1 = sw.get_port("g0/1")
    p2 = sw.get_port("g0/2")
    p3 = sw.get_port("g0/3")

    h1 = Host("h1", hostname="Host-1")
    h2 = Host("h2", hostname="Host-2")
    h3 = Host("h3", hostname="Host-3")

    c1 = Cable(h1.eth0, p1)
    c2 = Cable(h2.eth0, p2)
    c3 = Cable(h3.eth0, p3)

    # Initial MAC table empty
    assert len(sw.mac_table) == 0

    # 1. Unknown destination MAC causes flooding to all other active ports in VLAN 1
    out_ports_flood = sw.forward_packet(p1, h1.eth0.mac_address, "FF:FF:FF:FF:FF:FF", 1)
    # Learned source MAC
    assert h1.eth0.mac_address in sw.mac_table
    assert sw.mac_table[h1.eth0.mac_address]["port"] == "g0/1"
    # Flooded to p2 and p3 (not back out p1)
    assert p2 in out_ports_flood
    assert p3 in out_ports_flood
    assert p1 not in out_ports_flood

    # 2. Host 2 sends frame; switch learns Host 2 MAC on g0/2
    sw.forward_packet(p2, h2.eth0.mac_address, h1.eth0.mac_address, 1)
    assert h2.eth0.mac_address in sw.mac_table
    assert sw.mac_table[h2.eth0.mac_address]["port"] == "g0/2"

    # 3. Host 1 sends unicast to Host 2; switch forwards ONLY to g0/2 (no flooding)
    out_unicast = sw.forward_packet(p1, h1.eth0.mac_address, h2.eth0.mac_address, 1)
    assert len(out_unicast) == 1
    assert out_unicast[0] == p2

def test_switch_port_state_filtering():
    sw = Switch("sw1", hostname="Core-Switch")
    p1 = sw.get_port("g0/1")
    p2 = sw.get_port("g0/2")
    p3 = sw.get_port("g0/3")

    h1 = Host("h1")
    h2 = Host("h2")
    h3 = Host("h3")

    c1 = Cable(h1.eth0, p1)
    c2 = Cable(h2.eth0, p2)
    c3 = Cable(h3.eth0, p3)

    # Shutdown port 2
    p2.is_shutdown = True

    # Flood should NOT forward to shutdown port
    out_ports = sw.forward_packet(p1, h1.eth0.mac_address, "FF:FF:FF:FF:FF:FF", 1)
    assert p2 not in out_ports
    assert p3 in out_ports

    # Unicast to learned MAC on shutdown port should drop (return empty)
    sw.learn_mac("02:00:99:99:99:99", p2.name, 1)
    out_drop = sw.forward_packet(p1, h1.eth0.mac_address, "02:00:99:99:99:99", 1)
    assert len(out_drop) == 0

def test_switch_end_to_end_ping_with_learning():
    pe = PacketEngine.get_instance()

    sw = Switch("sw1", hostname="Switch-L2")
    h1 = Host("h1", hostname="PC1")
    h1.configure_ip("192.168.1.10", "255.255.255.0")

    h2 = Host("h2", hostname="PC2")
    h2.configure_ip("192.168.1.20", "255.255.255.0")

    c1 = Cable(h1.eth0, sw.get_port("g0/1"))
    c2 = Cable(h2.eth0, sw.get_port("g0/2"))

    # Ping PC1 -> PC2
    res = pe.simulate_ping(h1, "192.168.1.20", count=3)
    assert res.loss_percent == 0

    # Switch must have learned both MACs!
    assert h1.eth0.mac_address in sw.mac_table
    assert sw.mac_table[h1.eth0.mac_address]["port"] == "g0/1"
    assert h2.eth0.mac_address in sw.mac_table
    assert sw.mac_table[h2.eth0.mac_address]["port"] == "g0/2"

if __name__ == "__main__":
    test_switch_mac_learning_and_unicast()
    test_switch_port_state_filtering()
    test_switch_end_to_end_ping_with_learning()
    print("ALL SWITCH TESTS PASSED!")
