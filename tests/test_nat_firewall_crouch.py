"""
tests/test_nat_firewall_crouch.py - Comprehensive Unit & Integration Tests for:
1. Camera Crouch Mechanic ([C] Key)
2. Cisco IOS NAT/PAT Overload & Public Internet ICMP Routing (8.8.8.8)
3. Cisco ASA Stateful Firewall (Security Levels, Connection Table, ACLs)
4. Sandbox Device Management for Firewalls
"""

import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pygame

from engine.camera import FPSCamera
from network.router import Router
from network.switch import Switch
from network.host import Host
from network.firewall import Firewall
from network.cable import Cable, CableType
from network.packet_engine import PacketEngine
from cli.command_executor import CommandExecutor, IOSMode
from modes.sandbox_mode import SandboxMode

def test_camera_crouch():
    print("\n--- Testing Camera Crouch Mechanic ---")
    pygame.init()
    cam = FPSCamera(pos=(0.0, 1.65, 2.8))
    assert abs(cam.y - 1.65) < 0.01
    assert not cam.is_crouching

    # Mock pygame keys array
    class MockKeys:
        def __init__(self, pressed_keys):
            self.pressed = pressed_keys
        def __getitem__(self, k):
            return k in self.pressed

    # 1. Update with no keys pressed
    cam.update(MockKeys(set()), dt=0.1, pygame_module=pygame)
    assert not cam.is_crouching
    assert abs(cam.y - 1.65) < 0.05

    # 2. Press [C] key -> crouch begins, y smoothly lerps down towards 0.85
    for _ in range(30):
        cam.update(MockKeys({pygame.K_c}), dt=0.05, pygame_module=pygame)
    assert cam.is_crouching
    assert abs(cam.y - 0.85) < 0.05, f"Expected height ~0.85, got {cam.y}"

    # 3. Release [C] key -> returns smoothly to 1.65
    for _ in range(30):
        cam.update(MockKeys(set()), dt=0.05, pygame_module=pygame)
    assert not cam.is_crouching
    assert abs(cam.y - 1.65) < 0.05, f"Expected height ~1.65, got {cam.y}"

    print("Camera Crouch mechanic verified successfully!")

def test_cisco_nat_and_internet():
    print("\n--- Testing Cisco IOS NAT/PAT & Internet Ping ---")
    pe = PacketEngine.get_instance()

    # Topology:
    # Client (192.168.10.10) <-> Switch <-> Router (inside g0/1: 192.168.10.1, outside g0/0: 203.0.113.2) <-> ISP Gateway (203.0.113.1)
    client = Host("client1", hostname="Client-PC")
    client.configure_ip("192.168.10.10", "255.255.255.0", gateway="192.168.10.1")

    sw = Switch("sw1", hostname="LAN-Switch")

    rtr = Router("rtr1", hostname="Border-Router")
    # Configure inside g0/1
    rg1 = rtr.get_port("g0/1")
    rg1.ip_address = "192.168.10.1"
    rg1.subnet_mask = "255.255.255.0"
    rg1.is_shutdown = False

    # Configure outside g0/0
    rg0 = rtr.get_port("g0/0")
    rg0.ip_address = "203.0.113.2"
    rg0.subnet_mask = "255.255.255.0"
    rg0.is_shutdown = False

    # ISP Gateway uplink host
    isp = Host("isp1", hostname="ISP-Gateway-Cloud")
    isp.configure_ip("203.0.113.1", "255.255.255.0", gateway="203.0.113.1")

    # Connect cables
    c1 = Cable(client.eth0, sw.get_port("g0/1"), CableType.CAT6)
    c2 = Cable(sw.get_port("g0/2"), rtr.get_port("g0/1"), CableType.CAT6)
    c3 = Cable(rtr.get_port("g0/0"), isp.eth0, CableType.CAT6)

    # 1. Pinging local gateway should work
    res_gw = pe.simulate_ping(client, "192.168.10.1", count=2)
    assert res_gw.packets_received == 2, f"Gateway ping failed: {res_gw.error_message}"

    # 2. Before default route & NAT: Ping 8.8.8.8 should fail!
    res_pre = pe.simulate_ping(client, "8.8.8.8", count=2)
    assert res_pre.packets_received == 0, "Public internet ping should fail without default route and NAT"

    # 3. Configure Default Route only: still fails because private IP cannot route to public internet without NAT
    rtr_cli = CommandExecutor(rtr)
    rtr_cli.execute("enable")
    rtr_cli.execute("configure terminal")
    rtr_cli.execute("ip route 0.0.0.0 0.0.0.0 203.0.113.1")
    res_no_nat = pe.simulate_ping(client, "8.8.8.8", count=2)
    assert res_no_nat.packets_received == 0, "Public internet ping should fail with private IP and no NAT"

    # 4. Configure Cisco IOS NAT/PAT via CLI
    # interface g0/1 -> ip nat inside
    rtr_cli.execute("interface g0/1")
    rtr_cli.execute("ip nat inside")
    # interface g0/0 -> ip nat outside
    rtr_cli.execute("interface g0/0")
    rtr_cli.execute("ip nat outside")
    rtr_cli.execute("exit")
    # access-list 1 permit 192.168.10.0 0.0.0.255
    rtr_cli.execute("access-list 1 permit 192.168.10.0 0.0.0.255")
    # ip nat inside source list 1 interface g0/0 overload
    rtr_cli.execute("ip nat inside source list 1 interface g0/0 overload")
    rtr_cli.execute("end")

    assert "g0/1" in rtr.nat_inside_interfaces
    assert "g0/0" in rtr.nat_outside_interfaces
    assert len(rtr.nat_rules) == 1
    assert rtr.matches_acl(1, "192.168.10.10")
    assert not rtr.matches_acl(1, "10.0.0.5")

    # 5. Ping 8.8.8.8 should now SUCCEED!
    res_post = pe.simulate_ping(client, "8.8.8.8", count=5)
    assert res_post.packets_received == 5, f"NAT internet ping failed: {res_post.error_message}"
    assert res_post.success_rate_cisco == "!!!!!", f"Expected !!!!! got {res_post.success_rate_cisco}"
    print(f"Client -> 8.8.8.8 with Cisco NAT: {res_post.success_rate_cisco} (Loss: {res_post.loss_percent}%)")

    # 6. Verify show ip nat translations output
    out_trans = rtr_cli.execute("show ip nat translations")
    assert "203.0.113.2" in out_trans
    assert "192.168.10.10" in out_trans
    print("NAT Translations table verified:\n" + out_trans)

    # 7. Verify show ip nat statistics
    out_stat = rtr_cli.execute("show ip nat statistics")
    assert "Total active translations: 1" in out_stat

    # 8. Clear translations
    clear_msg = rtr_cli.execute("clear ip nat translation *")
    assert "cleared" in clear_msg
    assert len(rtr.nat_translations) == 0

    print("Cisco IOS NAT/PAT & Public Internet simulation verified successfully!")

def test_firewall_inspection():
    print("\n--- Testing Cisco ASA Stateful Firewall ---")
    pe = PacketEngine.get_instance()

    fw = Firewall("fw1", hostname="ASA-Edge-5506")
    # Inside interface: g0/1 (192.168.1.1/24, security level 100)
    fg1 = fw.get_port("g0/1")
    fg1.ip_address = "192.168.1.1"
    fg1.subnet_mask = "255.255.255.0"
    fg1.is_shutdown = False

    # Outside interface: g0/0 (203.0.113.10/24, security level 0)
    fg0 = fw.get_port("g0/0")
    fg0.ip_address = "203.0.113.10"
    fg0.subnet_mask = "255.255.255.0"
    fg0.is_shutdown = False

    inside_host = Host("in_host", hostname="Inside-Web")
    inside_host.configure_ip("192.168.1.50", "255.255.255.0", gateway="192.168.1.1")

    outside_host = Host("out_host", hostname="Outside-Partner")
    outside_host.configure_ip("203.0.113.50", "255.255.255.0", gateway="203.0.113.10")

    # Connect cables
    c_in = Cable(inside_host.eth0, fw.get_port("g0/1"), CableType.CAT6)
    c_out = Cable(fw.get_port("g0/0"), outside_host.eth0, CableType.CAT6)

    # CLI for Firewall
    fw_cli = CommandExecutor(fw)
    fw_cli.execute("enable")

    # 1. Inspect nameif
    out_nameif = fw_cli.execute("show nameif")
    assert "inside" in out_nameif and "100" in out_nameif
    assert "outside" in out_nameif and "0" in out_nameif
    print("Firewall show nameif output:\n" + out_nameif)

    # 2. Outbound traffic: Inside (100) -> Outside (0)
    # Permitted statefully!
    res_out = pe.simulate_ping(inside_host, "203.0.113.50", count=3)
    assert res_out.packets_received == 3, f"Outbound ping through firewall failed: {res_out.error_message}"
    print(f"Inside (sec 100) -> Outside (sec 0) Ping: {res_out.success_rate_cisco} (Permitted statefully)")

    # 3. Check connection table
    out_conn = fw_cli.execute("show conn")
    assert "192.168.1.50" in out_conn
    assert "203.0.113.50" in out_conn
    print("Firewall show conn output:\n" + out_conn)

    # 4. Inbound traffic: Outside (0) -> Inside (100)
    # Dropped by default (lower security level to higher without ACL)
    res_in_drop = pe.simulate_ping(outside_host, "192.168.1.50", count=3)
    assert res_in_drop.packets_received == 0, "Inbound traffic must be dropped by default security policy"
    print(f"Outside (sec 0) -> Inside (sec 100) without ACL: {res_in_drop.success_rate_cisco} (Correctly Dropped)")

    # 5. Configure ACL to permit inbound ICMP:
    fw_cli.execute("configure terminal")
    fw_cli.execute("access-list OUTSIDE_IN extended permit icmp any any")
    fw_cli.execute("access-group OUTSIDE_IN in interface outside")
    fw_cli.execute("end")

    out_acl = fw_cli.execute("show access-list")
    assert "OUTSIDE_IN" in out_acl
    print("Firewall show access-list output:\n" + out_acl)

    # 6. Inbound traffic should now SUCCEED!
    res_in_pass = pe.simulate_ping(outside_host, "192.168.1.50", count=3)
    assert res_in_pass.packets_received == 3, f"Inbound ping with permit ACL failed: {res_in_pass.error_message}"
    print(f"Outside (sec 0) -> Inside (sec 100) with ACL: {res_in_pass.success_rate_cisco} (Permitted by ACL)")

    print("Cisco ASA Stateful Firewall tests verified successfully!")

def test_sandbox_firewall_management():
    print("\n--- Testing Sandbox Firewall Device Management ---")
    sb = SandboxMode()
    initial_count = len(sb.devices)

    # Add Firewall to Rack 1, slot 30U
    ok, msg, new_fw = sb.add_device("firewall", 1, 30, hostname="Branch-ASA-01")
    assert ok, f"Failed to add firewall: {msg}"
    assert new_fw.device_type == "firewall"
    assert new_fw.rack_id == 1
    assert new_fw.u_slot == 30
    assert len(sb.devices) == initial_count + 1

    # Verify 1U collision: slot 30 is occupied
    occ, _ = sb.is_slot_occupied(1, 30, needed_u=1)
    assert occ, "Slot 30U should be occupied"

    # Slot 31 is free (since firewall is 1U)
    occ_31, _ = sb.is_slot_occupied(1, 31, needed_u=1)
    assert not occ_31, "Slot 31U should be free for 1U appliance"

    # Remove the firewall
    rem_ok, rem_msg = sb.remove_device(new_fw)
    assert rem_ok, f"Failed to remove firewall: {rem_msg}"
    assert len(sb.devices) == initial_count

    print("Sandbox Firewall device management verified successfully!")

if __name__ == "__main__":
    test_camera_crouch()
    test_cisco_nat_and_internet()
    test_firewall_inspection()
    test_sandbox_firewall_management()
    print("\n=======================================================")
    print("ALL CROUCH, CISCO NAT, & FIREWALL TESTS PASSED 100%!")
    print("=======================================================")
