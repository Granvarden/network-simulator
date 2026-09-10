"""
tests/test_realistic_ping.py - Comprehensive Unit Tests for Realistic Ping & ARP Engine
Validates:
1. Cold ARP cache drop (.!!!! 80%) on first ping, then instant hit (!!!!! 100%) on second ping.
2. Cisco status codes: '!' (Success), '.' (Timeout), 'U' (Unreachable), 'A' (Administratively Prohibited).
3. 'show ip arp' and 'clear ip arp'.
4. Extended ping syntax: repeat, size, source.
5. Traceroute simulation (Cisco and Linux).
6. Linux server ping output format (TTL, seq, jitter mdev, arp -a).
7. Interactive real-time streaming ping job in TerminalUI.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.router import Router
from network.switch import Switch
from network.host import Host
from network.firewall import Firewall
from network.cable import Cable, CableType
from network.packet_engine import PacketEngine, format_cisco_mac
from cli.command_executor import CommandExecutor
from cli.terminal_ui import TerminalUI

def test_cold_arp_drop_and_resolution():
    print("\n--- TEST: Cold ARP Drop & Caching (.!!!! -> !!!!!) ---")
    pe = PacketEngine.get_instance()

    router = Router(1, "Router-01", rack_id=1, u_slot=10)
    server = Host(2, "Server-01", rack_id=1, u_slot=14)

    r_p = router.get_port("g0/0")
    r_p.ip_address = "192.168.1.1"
    r_p.subnet_mask = "255.255.255.0"
    r_p.is_shutdown = False

    s_p = server.eth0
    s_p.ip_address = "192.168.1.10"
    s_p.subnet_mask = "255.255.255.0"
    s_p.is_shutdown = False
    server.default_gateway = "192.168.1.1"

    c = Cable(r_p, s_p, CableType.CAT6)

    # Verify cold ARP cache initially
    assert len(server.arp_table) == 0
    assert len(router.arp_table) == 0

    # 1. First ping with simulate_arp=True: should drop packet 0 for ARP (.!!!!)
    res1 = pe.simulate_ping(server, "192.168.1.1", count=5, simulate_arp=True)
    print(f"First Ping (Cold ARP): {res1.success_rate_cisco} (Loss: {res1.loss_percent}%)")
    assert res1.success_rate_cisco == ".!!!!", f"Expected '.!!!!' on cold ARP, got {res1.success_rate_cisco}"
    assert res1.packets_received == 4
    assert res1.loss_percent == 20

    # Verify ARP table populated on server
    assert "192.168.1.1" in server.arp_table
    entry = server.lookup_arp("192.168.1.1")
    assert entry is not None
    print(f"Learned ARP entry: {entry}")

    # 2. Second ping with simulate_arp=True: should hit cache immediately (!!!!!)
    res2 = pe.simulate_ping(server, "192.168.1.1", count=5, simulate_arp=True)
    print(f"Second Ping (Cached ARP): {res2.success_rate_cisco} (Loss: {res2.loss_percent}%)")
    assert res2.success_rate_cisco == "!!!!!", f"Expected '!!!!!' on warm cache, got {res2.success_rate_cisco}"
    assert res2.packets_received == 5
    assert res2.loss_percent == 0

    # 3. Test clear_arp: flushing ARP table drops first packet again
    server.clear_arp()
    assert len(server.arp_table) == 0
    res3 = pe.simulate_ping(server, "192.168.1.1", count=5, simulate_arp=True)
    print(f"Third Ping (After clear ARP): {res3.success_rate_cisco}")
    assert res3.success_rate_cisco == ".!!!!", "Expected '.!!!!' after clearing ARP cache"
    print("Cold ARP Drop and Resolution verified!")

def test_cisco_status_codes():
    print("\n--- TEST: Cisco Status Codes (!, ., U, A) ---")
    pe = PacketEngine.get_instance()

    # Router + Firewall + Host setup
    router = Router(1, "Rtr-Core", rack_id=1, u_slot=10)
    fw = Firewall(2, "ASA-Edge", rack_id=1, u_slot=12)

    r_p = router.get_port("g0/0")
    r_p.ip_address = "10.0.0.1"
    r_p.subnet_mask = "255.255.255.0"
    r_p.is_shutdown = False

    fw_in = fw.get_port("g0/0")
    fw_in.ip_address = "10.0.0.2"
    fw_in.subnet_mask = "255.255.255.0"
    fw_in.is_shutdown = False
    fw.set_interface_zone("g0/0", "inside")
    fw.set_zone_security("inside", 100)

    fw_out = fw.get_port("g0/1")
    fw_out.ip_address = "203.0.113.1"
    fw_out.subnet_mask = "255.255.255.0"
    fw_out.is_shutdown = False
    fw.set_interface_zone("g0/1", "outside")
    fw.set_zone_security("outside", 0)

    c1 = Cable(r_p, fw_in, CableType.CAT6)

    # 1. Unrouted IP: returns 'U'
    res_unrouted = pe.simulate_ping(router, "172.31.99.99", count=3)
    print(f"Unrouted IP status: {res_unrouted.success_rate_cisco}")
    assert "U" in res_unrouted.success_rate_cisco, f"Expected 'U' for unrouted IP, got {res_unrouted.success_rate_cisco}"

    # 2. Blocked by Firewall ACL: Outside -> Inside blocked by default
    outside_host = Host(3, "Internet-Tester", rack_id=2, u_slot=10)
    outside_host.eth0.ip_address = "203.0.113.50"
    outside_host.eth0.subnet_mask = "255.255.255.0"
    outside_host.eth0.is_shutdown = False
    outside_host.default_gateway = "203.0.113.1"
    c2 = Cable(fw_out, outside_host.eth0, CableType.CAT6)

    res_fw_drop = pe.simulate_ping(outside_host, "10.0.0.1", count=3)
    print(f"Firewall ACL Drop status: {res_fw_drop.success_rate_cisco}")
    assert res_fw_drop.status_codes == ["A", "A", "A"] or "A" in res_fw_drop.success_rate_cisco, "Expected 'A' (Admin prohibited) on firewall ACL drop"

    print("Cisco Status Codes verified!")

def test_arp_and_extended_cli_commands():
    print("\n--- TEST: CLI ARP, Traceroute, and Extended Ping Commands ---")
    router = Router(1, "Rtr-CLI", rack_id=1, u_slot=10)
    r_cli = CommandExecutor(router)

    r_p = router.get_port("g0/0")
    r_p.ip_address = "192.168.1.1"
    r_p.subnet_mask = "255.255.255.0"
    r_p.is_shutdown = False

    # Seed an ARP entry
    router.add_arp_entry("192.168.1.50", "02:00:ab:cd:ef:01", "GigabitEthernet0/0", age=3)

    # 1. Test show ip arp
    r_cli.execute("enable")
    out_arp = r_cli.execute("show ip arp")
    print(f"show ip arp output:\n{out_arp}")
    assert "Protocol  Address" in out_arp
    assert "192.168.1.1" in out_arp
    assert "192.168.1.50" in out_arp
    assert "0200.abcd.ef01" in out_arp or "02:00:ab:cd:ef:01" in out_arp

    # 2. Test clear ip arp
    out_clr = r_cli.execute("clear ip arp")
    assert "cleared" in out_clr
    assert "192.168.1.50" not in router.arp_table

    # 3. Test extended ping options parsing
    out_ping = r_cli.execute("ping 192.168.1.1 repeat 3 size 500 timeout 1")
    print(f"Extended ping output:\n{out_ping}")
    assert "Sending 3, 500-byte ICMP Echos to 192.168.1.1, timeout is 1 seconds:" in out_ping
    assert "Success rate is 100 percent (3/3)" in out_ping

    # 4. Test traceroute
    out_trace = r_cli.execute("traceroute 192.168.1.1")
    print(f"traceroute output:\n{out_trace}")
    assert "Tracing the route to 192.168.1.1" in out_trace
    assert "1 192.168.1.1" in out_trace

    print("CLI ARP and Extended Ping commands verified!")

def test_linux_server_ping():
    print("\n--- TEST: Linux Host Ping, TTL, and Jitter ---")
    server = Host(1, "Web-Server-01", rack_id=1, u_slot=14)
    s_cli = CommandExecutor(server)

    s_p = server.eth0
    s_p.ip_address = "10.0.0.5"
    s_p.subnet_mask = "255.255.255.0"
    s_p.is_shutdown = False

    out_ping = s_cli.execute("ping -c 3 10.0.0.5")
    print(f"Linux ping output:\n{out_ping}")
    assert "PING 10.0.0.5 (10.0.0.5) 56(84) bytes of data." in out_ping
    assert "64 bytes from 10.0.0.5: icmp_seq=1" in out_ping
    assert "ttl=64" in out_ping
    assert "--- 10.0.0.5 ping statistics ---" in out_ping
    assert "3 packets transmitted, 3 received, 0% packet loss" in out_ping
    assert "rtt min/avg/max/mdev" in out_ping

    out_arp = s_cli.execute("arp -a")
    print(f"Linux arp output:\n{out_arp}")

    out_trace = s_cli.execute("traceroute 10.0.0.5")
    print(f"Linux traceroute output:\n{out_trace}")
    assert "traceroute to 10.0.0.5" in out_trace

    print("Linux server ping verified!")

def test_terminal_realtime_ping_job():
    print("\n--- TEST: Terminal UI Streaming Ping Job ---")
    router = Router(1, "Rtr-Term", rack_id=1, u_slot=10)
    r_p = router.get_port("g0/0")
    r_p.ip_address = "192.168.1.1"
    r_p.subnet_mask = "255.255.255.0"
    r_p.is_shutdown = False

    term = TerminalUI(router, 800, 500)
    term.open()

    # Enter command: ping 192.168.1.1 repeat 3
    term.input_buffer = "ping 192.168.1.1 repeat 3"
    import pygame
    class MockEvent:
        def __init__(self, key, mod=0):
            self.key = key
            self.mod = mod

    # Press Enter
    term.handle_key(MockEvent(pygame.K_RETURN))
    assert term.active_job is not None, "Ping should start an active streaming job in TerminalUI"
    assert term.active_job["count"] == 3
    print("Ping job started successfully.")

    # Advance time frame by frame
    completed = False
    for frame in range(15):
        term.update(0.1) # 100ms ticks
        if term.active_job is None:
            completed = True
            break

    assert completed, "Active ping job should complete all packets over time"
    rendered_text = "\n".join(term.history_lines)
    print(f"Terminal History after streaming:\n{rendered_text}")
    assert "Sending 3, 100-byte ICMP Echos to 192.168.1.1" in rendered_text
    assert "!!!" in rendered_text
    assert "Success rate is 100 percent (3/3)" in rendered_text

    print("Terminal UI real-time streaming ping job verified!")

if __name__ == "__main__":
    test_cold_arp_drop_and_resolution()
    test_cisco_status_codes()
    test_arp_and_extended_cli_commands()
    test_linux_server_ping()
    test_terminal_realtime_ping_job()
    print("\n==========================================")
    print("ALL REALISTIC PING & ARP TESTS PASSED!")
    print("==========================================")
