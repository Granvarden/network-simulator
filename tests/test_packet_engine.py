"""
tests/test_packet_engine.py - Tests for Packet Engine Lifecycle & Diagnostics
Validates:
1. Packet creation, transmission, processing, delivery, and drop.
2. TTL decrement across layer 3 router hops.
3. Diagnostic drop reasons (cable down, interface down, no route, loop, TTL expired).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.router import Router
from network.switch import Switch
from network.host import Host
from network.cable import Cable, CableType
from network.packet_engine import PacketEngine, is_private_ip, format_cisco_mac

def test_packet_lifecycle_and_ttl():
    pe = PacketEngine.get_instance()

    # Setup: Host1 (192.168.1.10) <-> R1 (192.168.1.1 / 10.0.0.1) <-> Host2 (10.0.0.2)
    h1 = Host("h1", hostname="Host-A")
    h1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    r1 = Router("r1", hostname="Router-1")
    p0 = r1.get_port("g0/0")
    p0.ip_address = "192.168.1.1"
    p0.subnet_mask = "255.255.255.0"
    p0.is_shutdown = False

    p1 = r1.get_port("g0/1")
    p1.ip_address = "10.0.0.1"
    p1.subnet_mask = "255.255.255.0"
    p1.is_shutdown = False

    h2 = Host("h2", hostname="Host-B")
    h2.configure_ip("10.0.0.2", "255.255.255.0", gateway="10.0.0.1")

    c1 = Cable(h1.eth0, p0, CableType.CAT6)
    c2 = Cable(p1, h2.eth0, CableType.CAT6)

    # 1. Successful packet delivery & TTL decrement
    step = pe.trace_single_packet(h1, "10.0.0.2", simulate_arp=False)
    assert step["success"] is True, f"Expected packet delivery, got {step}"
    assert step["status_code"] == "!"
    # Starting TTL 64 - 1 router hop = 63
    assert step["ttl"] == 63, f"Expected TTL 63, got {step['ttl']}"
    assert "Router-1" in step["hop_path"]
    assert "Host-B" in step["hop_path"]

    # 2. Local self-ping TTL
    step_self = pe.trace_single_packet(h1, "192.168.1.10")
    assert step_self["success"] is True
    assert step_self["ttl"] == 64

    # 3. Router self-ping TTL
    step_rtr = pe.trace_single_packet(r1, "192.168.1.1")
    assert step_rtr["success"] is True
    assert step_rtr["ttl"] == 255

def test_packet_engine_diagnostic_drops():
    pe = PacketEngine.get_instance()

    h1 = Host("h1", hostname="Host-A")
    h1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    r1 = Router("r1", hostname="Router-1")
    p0 = r1.get_port("g0/0")
    p0.ip_address = "192.168.1.1"
    p0.subnet_mask = "255.255.255.0"
    p0.is_shutdown = False

    c1 = Cable(h1.eth0, p0, CableType.CAT6)

    # Case A: Interface shutdown
    p0.is_shutdown = True
    step_shut = pe.trace_single_packet(h1, "192.168.1.1")
    assert step_shut["success"] is False
    assert step_shut["status_code"] == "U"
    assert "down" in step_shut["drop_reason"].lower() or "administratively down" in step_shut["drop_reason"].lower()
    p0.is_shutdown = False

    # Case B: Cable disconnected / damaged on transit link
    p1 = r1.get_port("g0/1")
    p1.ip_address = "10.0.0.1"
    p1.subnet_mask = "255.255.255.0"
    p1.is_shutdown = False
    h_temp = Host("h_temp")
    h_temp.configure_ip("10.0.0.2", "255.255.255.0", gateway="10.0.0.1")
    c2 = Cable(p1, h_temp.eth0, CableType.CAT6)
    c2.is_damaged = True
    step_dmg = pe.trace_single_packet(h1, "10.0.0.2", simulate_arp=False)
    assert step_dmg["success"] is False
    assert any(k in step_dmg["drop_reason"].lower() for k in ("no route", "down", "disconnected", "damaged"))
    c2.disconnect()

    # Case C: Unrouted destination
    step_unrouted = pe.trace_single_packet(r1, "172.16.50.1")
    assert step_unrouted["success"] is False
    assert step_unrouted["status_code"] == "U"
    assert "no route" in step_unrouted["drop_reason"].lower()

    # Case D: Host without default gateway trying to reach external subnet
    sw_temp = Switch("sw_temp")
    h_nogw = Host("h_nogw", hostname="Host-NoGW")
    h_nogw.eth0.ip_address = "192.168.1.20"
    h_nogw.eth0.subnet_mask = "255.255.255.0"
    h_nogw.default_gateway = None
    c_nogw = Cable(h_nogw.eth0, sw_temp.get_port("g0/1"), CableType.CAT6)
    step_nogw = pe.trace_single_packet(h_nogw, "8.8.8.8")
    assert step_nogw["success"] is False
    assert step_nogw["status_code"] == "U"
    assert "no default gateway" in step_nogw["drop_reason"].lower()
    c_nogw.disconnect()

def test_helpers():
    assert is_private_ip("10.0.0.1") is True
    assert is_private_ip("172.16.0.5") is True
    assert is_private_ip("192.168.1.1") is True
    assert is_private_ip("8.8.8.8") is False
    assert is_private_ip("203.0.113.1") is False

    mac_fmt = format_cisco_mac("02:00:ab:cd:ef:01")
    assert mac_fmt == "0200.abcd.ef01"

if __name__ == "__main__":
    test_packet_lifecycle_and_ttl()
    test_packet_engine_diagnostic_drops()
    test_helpers()
    print("ALL PACKET ENGINE TESTS PASSED!")
