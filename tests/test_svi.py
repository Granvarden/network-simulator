"""
tests/test_svi.py - Comprehensive Test Suite for Switch Virtual Interfaces (SVI)
Verifies:
1. VLAN existence requirement and rejection of non-existent VLANs.
2. SVI logical Layer-3 architecture (NOT in switch.ports).
3. IPv4 address & contiguous subnet mask validation.
4. Duplicate IP check across interfaces on the same device.
5. Administrative state (shutdown / no shutdown).
6. Removal of IP address (no ip address).
7. Autostate calculation (oper_state UP only when member port is UP).
8. ARP resolution between Host and SVI.
9. Bidirectional ICMP Ping (Host -> SVI and Switch -> Host).
10. Strict VLAN isolation (Host in VLAN 20 cannot reach SVI Vlan10).
11. STP compatibility (SVIs do not participate in STP or affect port roles).
12. CLI commands: show ip interface brief, show interfaces vlan, show running-config, ip default-gateway.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.router import Router, is_valid_ipv4, is_valid_netmask
from network.switch import Switch, SVI
from network.host import Host
from network.cable import Cable
from network.packet_engine import PacketEngine
from cli.command_executor import CommandExecutor, IOSMode


def test_vlan_existence_and_rejection():
    """Test 1: SVI must belong to a real VLAN; reject non-existent VLAN."""
    sw = Switch("sw1", hostname="Switch")
    exec_cli = CommandExecutor(sw)

    exec_cli.execute("enable")
    exec_cli.execute("configure terminal")
    assert exec_cli.mode == IOSMode.CONFIG

    # Non-existent VLAN 99 should be rejected
    out = exec_cli.execute("interface vlan 99")
    assert "% VLAN 99 does not exist." in out
    assert exec_cli.mode == IOSMode.CONFIG
    assert sw.get_svi(99) is None

    # Create VLAN 10
    exec_cli.execute("vlan 10")
    exec_cli.execute("exit")

    # Now interface vlan 10 must succeed
    out = exec_cli.execute("interface vlan 10")
    assert out == ""
    assert exec_cli.mode == IOSMode.CONFIG_IF
    assert exec_cli.current_interface is not None
    assert isinstance(exec_cli.current_interface, SVI)
    assert exec_cli.current_interface.vlan_id == 10
    assert exec_cli.get_prompt() == "Switch(config-if)#"


def test_svi_architecture_not_in_ports():
    """Test 2: SVI is purely logical Layer-3 interface, NOT in switch.ports."""
    sw = Switch("sw1", hostname="Switch")
    initial_port_count = len(sw.ports)

    sw.add_vlan(10, "Sales")
    svi = sw.create_svi(10)

    assert svi is not None
    assert isinstance(svi, SVI)
    assert svi.vlan_id == 10
    assert svi.name == "Vlan10"
    assert svi.full_name == "Vlan10"
    assert 10 in sw.svis

    # Verify SVI is strictly NOT in physical ports
    assert len(sw.ports) == initial_port_count
    assert "Vlan10" not in sw.ports
    assert "vlan10" not in sw.ports
    assert svi not in sw.ports.values()

    # get_interface should find it
    assert sw.get_interface("Vlan10") == svi
    assert sw.get_interface("vlan 10") == svi
    assert sw.get_interface("vlan10") == svi


def test_ip_address_assignment_and_validation():
    """Test 3: Validate IPv4 address format and contiguous subnet mask."""
    sw = Switch("sw1", hostname="Switch")
    sw.add_vlan(10, "Sales")
    exec_cli = CommandExecutor(sw)

    exec_cli.execute("enable")
    exec_cli.execute("configure terminal")
    exec_cli.execute("interface vlan 10")

    # Invalid IP format
    out = exec_cli.execute("ip address 999.168.10.1 255.255.255.0")
    assert "% Invalid IP address format." in out
    assert exec_cli.current_interface.ip_address is None

    # Invalid / non-contiguous netmask
    out = exec_cli.execute("ip address 192.168.10.1 255.255.0.255")
    assert "% Invalid subnet mask format." in out
    assert exec_cli.current_interface.ip_address is None

    # Valid IP and subnet mask
    out = exec_cli.execute("ip address 192.168.10.1 255.255.255.0")
    assert out == ""
    assert exec_cli.current_interface.ip_address == "192.168.10.1"
    assert exec_cli.current_interface.subnet_mask == "255.255.255.0"


def test_duplicate_ip_check():
    """Test 4: Reject duplicate IP address on another interface on the same switch."""
    sw = Switch("sw1", hostname="Switch")
    sw.add_vlan(10, "Sales")
    sw.add_vlan(20, "Engineering")
    exec_cli = CommandExecutor(sw)

    exec_cli.execute("enable")
    exec_cli.execute("configure terminal")

    # Configure Vlan10
    exec_cli.execute("interface vlan 10")
    exec_cli.execute("ip address 192.168.10.1 255.255.255.0")

    # Configure Vlan20 with duplicate IP
    exec_cli.execute("interface vlan 20")
    out = exec_cli.execute("ip address 192.168.10.1 255.255.255.0")
    assert "% IP address 192.168.10.1 already assigned to interface Vlan10." in out
    assert exec_cli.current_interface.ip_address is None

    # Re-assigning same IP to Vlan10 itself is allowed
    exec_cli.execute("interface vlan 10")
    out = exec_cli.execute("ip address 192.168.10.1 255.255.255.0")
    assert out == ""


def test_shutdown_and_no_shutdown():
    """Test 5: Administrative state defaults to shutdown, can be changed via shutdown/no shutdown."""
    sw = Switch("sw1", hostname="Switch")
    sw.add_vlan(10, "Sales")
    svi = sw.create_svi(10)

    # Default admin state is shutdown
    assert svi.is_shutdown is True
    assert svi.admin_state == "down"

    exec_cli = CommandExecutor(sw)
    exec_cli.execute("enable")
    exec_cli.execute("configure terminal")
    exec_cli.execute("interface vlan 10")

    out = exec_cli.execute("no shutdown")
    assert svi.is_shutdown is False
    assert svi.admin_state == "up"
    assert "changed state to up" in out

    out = exec_cli.execute("shutdown")
    assert svi.is_shutdown is True
    assert svi.admin_state == "down"
    assert "administratively down" in out


def test_no_ip_address():
    """Test 6: 'no ip address' clears configured IP and subnet mask."""
    sw = Switch("sw1", hostname="Switch")
    sw.add_vlan(10, "Sales")
    exec_cli = CommandExecutor(sw)

    exec_cli.execute("enable")
    exec_cli.execute("configure terminal")
    exec_cli.execute("interface vlan 10")
    exec_cli.execute("ip address 192.168.10.1 255.255.255.0")
    assert sw.get_svi(10).ip_address == "192.168.10.1"

    exec_cli.execute("no ip address")
    assert sw.get_svi(10).ip_address is None
    assert sw.get_svi(10).subnet_mask is None


def test_autostate_behavior():
    """Test 7: Autostate: SVI is UP only when admin is UP and at least one member port is UP."""
    sw = Switch("sw1", hostname="Switch")
    sw.add_vlan(10, "Sales")
    svi = sw.create_svi(10)
    svi.is_shutdown = False

    # No member ports assigned to VLAN 10 yet -> oper_state is DOWN
    assert svi.is_link_up is False
    assert svi.oper_state == "down"

    # Configure g0/1 as access port in VLAN 10
    p1 = sw.get_port("g0/1")
    p1.mode = "access"
    p1.access_vlan = 10

    # Port has no cable connected -> still DOWN
    assert svi.is_link_up is False
    assert svi.oper_state == "down"

    # Connect host to g0/1
    pc1 = Host("pc1", hostname="PC1")
    cable = Cable(pc1.eth0, p1)

    # Now at least one member port is UP -> SVI oper_state is UP!
    assert p1.is_link_up is True
    assert svi.is_link_up is True
    assert svi.oper_state == "up"

    # If physical port is administratively shutdown -> SVI drops back to DOWN
    p1.is_shutdown = True
    assert svi.is_link_up is False
    assert svi.oper_state == "down"

    # Bring physical port back UP
    p1.is_shutdown = False
    assert svi.is_link_up is True
    assert svi.oper_state == "up"

    # If SVI itself is shutdown -> oper_state is DOWN
    svi.is_shutdown = True
    assert svi.is_link_up is False
    assert svi.oper_state == "down"


def test_arp_resolution_between_host_and_svi():
    """Test 8: Host in VLAN 10 sends ARP request and resolves SVI MAC address."""
    pe = PacketEngine.get_instance()
    sw = Switch("sw1", hostname="Switch")
    sw.add_vlan(10, "Sales")
    svi = sw.create_svi(10)
    svi.ip_address = "192.168.10.1"
    svi.subnet_mask = "255.255.255.0"
    svi.is_shutdown = False

    p1 = sw.get_port("g0/1")
    p1.mode = "access"
    p1.access_vlan = 10

    pc1 = Host("pc1", hostname="PC1")
    pc1.configure_ip("192.168.10.10", "255.255.255.0")
    Cable(pc1.eth0, p1)

    # Host probes ARP for SVI IP
    reachable, peer_mac = pe._probe_arp_resolution(pc1, pc1.eth0, "192.168.10.1")
    assert reachable is True
    assert peer_mac == svi.mac_address


def test_ping_host_to_svi():
    """Test 9: ICMP Ping from PC1 to Switch SVI succeeds with 100% reply."""
    pe = PacketEngine.get_instance()
    sw = Switch("sw1", hostname="Switch")
    sw.add_vlan(10, "Sales")
    svi = sw.create_svi(10)
    svi.ip_address = "192.168.10.1"
    svi.subnet_mask = "255.255.255.0"
    svi.is_shutdown = False

    p1 = sw.get_port("g0/1")
    p1.mode = "access"
    p1.access_vlan = 10

    pc1 = Host("pc1", hostname="PC1")
    pc1.configure_ip("192.168.10.10", "255.255.255.0")
    Cable(pc1.eth0, p1)

    # Ping SVI IP from Host
    res = pe.simulate_ping(pc1, "192.168.10.1", count=5)
    assert res.success is True
    assert res.packets_received == 5
    assert res.loss_percent == 0
    assert all(code == "!" for code in res.status_codes)
    assert len(res.rtt_ms) == 5
    assert res.avg_rtt > 0


def test_ping_svi_to_host():
    """Test 10: Switch can initiate ping from SVI to connected host."""
    pe = PacketEngine.get_instance()
    sw = Switch("sw1", hostname="Switch")
    sw.add_vlan(10, "Sales")
    svi = sw.create_svi(10)
    svi.ip_address = "192.168.10.1"
    svi.subnet_mask = "255.255.255.0"
    svi.is_shutdown = False

    p1 = sw.get_port("g0/1")
    p1.mode = "access"
    p1.access_vlan = 10

    pc1 = Host("pc1", hostname="PC1")
    pc1.configure_ip("192.168.10.10", "255.255.255.0")
    Cable(pc1.eth0, p1)

    # Switch pings Host
    res = pe.simulate_ping(sw, "192.168.10.10", count=5)
    assert res.success is True
    assert res.packets_received == 5
    assert res.loss_percent == 0
    assert all(code == "!" for code in res.status_codes)


def test_vlan_isolation_svi():
    """Test 11: Host in VLAN 20 cannot reach SVI in VLAN 10 (VLAN isolation)."""
    pe = PacketEngine.get_instance()
    sw = Switch("sw1", hostname="Switch")
    sw.add_vlan(10, "Sales")
    sw.add_vlan(20, "Engineering")

    # SVI on VLAN 10
    svi10 = sw.create_svi(10)
    svi10.ip_address = "192.168.10.1"
    svi10.subnet_mask = "255.255.255.0"
    svi10.is_shutdown = False

    # Port in VLAN 10 with PC1 (needed so SVI 10 has active port)
    p1 = sw.get_port("g0/1")
    p1.mode = "access"
    p1.access_vlan = 10
    pc1 = Host("pc1", hostname="Sales-PC")
    pc1.configure_ip("192.168.10.10", "255.255.255.0")
    Cable(pc1.eth0, p1)

    # Port in VLAN 20 with PC2
    p2 = sw.get_port("g0/2")
    p2.mode = "access"
    p2.access_vlan = 20
    pc2 = Host("pc2", hostname="Eng-PC")
    # Even if configured in same subnet, VLAN tag isolation prevents L2 ARP
    pc2.configure_ip("192.168.10.20", "255.255.255.0")
    Cable(pc2.eth0, p2)

    # PC2 (VLAN 20) attempts to ping SVI Vlan10 (192.168.10.1) -> must FAIL
    res = pe.simulate_ping(pc2, "192.168.10.1", count=3)
    assert res.packets_received == 0
    assert res.loss_percent == 100


def test_stp_compatibility_with_svi():
    """Test 12: SVIs do NOT participate in STP or affect spanning-tree election."""
    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")
    sw3 = Switch("sw3", hostname="SW3")
    sw1.stp_priority = 4096
    sw2.stp_priority = 8192
    sw3.stp_priority = 32768

    # Configure SVIs on switches
    for sw in (sw1, sw2, sw3):
        sw.add_vlan(10, "Management")
        svi = sw.create_svi(10)
        svi.is_shutdown = False

    # Triangle topology
    Cable(sw1.get_port("g0/1"), sw2.get_port("g0/1"))
    Cable(sw2.get_port("g0/2"), sw3.get_port("g0/2"))
    Cable(sw3.get_port("g0/1"), sw1.get_port("g0/2"))

    # Recalculate STP
    sw1.recalculate_stp()
    sw2.recalculate_stp()
    sw3.recalculate_stp()

    # Root Bridge should be SW1 (lowest priority 4096)
    assert sw1.is_root_bridge is True
    assert sw2.is_root_bridge is False
    assert sw3.is_root_bridge is False

    # Verify no SVI is ever treated as an STP port
    for sw in (sw1, sw2, sw3):
        for p in sw.ports.values():
            assert not isinstance(p, SVI)
        for svi in sw.svis.values():
            assert not hasattr(svi, "stp_state")


def test_cli_show_commands_and_default_gateway():
    """Test 13: CLI show ip interface brief, show interfaces vlan, show running-config, ip default-gateway."""
    sw = Switch("sw1", hostname="Switch-Core")
    exec_cli = CommandExecutor(sw)

    exec_cli.execute("enable")
    exec_cli.execute("configure terminal")
    exec_cli.execute("vlan 10")
    exec_cli.execute("vlan 20")
    exec_cli.execute("interface vlan 10")
    exec_cli.execute("ip address 192.168.10.1 255.255.255.0")
    exec_cli.execute("no shutdown")
    exec_cli.execute("ip default-gateway 192.168.10.254")

    assert sw.default_gateway == "192.168.10.254"

    # Connect host to g0/1 in VLAN 10 so Vlan10 protocol is UP
    p1 = sw.get_port("g0/1")
    p1.mode = "access"
    p1.access_vlan = 10
    pc1 = Host("pc1", hostname="PC1")
    Cable(pc1.eth0, p1)

    # show ip interface brief
    out_brief = exec_cli.execute("show ip interface brief")
    assert "Vlan10" in out_brief
    assert "192.168.10.1" in out_brief
    assert "up" in out_brief

    # show interfaces vlan 10
    out_int = exec_cli.execute("show interfaces vlan 10")
    assert "Vlan10 is up, line protocol is up" in out_int
    assert "Internet address is 192.168.10.1/255.255.255.0" in out_int
    assert "EtherSVI" in out_int

    # show running-config
    out_run = exec_cli.execute("show running-config")
    assert "interface Vlan10" in out_run
    assert "ip address 192.168.10.1 255.255.255.0" in out_run
    assert "no shutdown" in out_run
    assert "ip default-gateway 192.168.10.254" in out_run

    # no ip default-gateway
    exec_cli.execute("configure terminal")
    exec_cli.execute("no ip default-gateway")
    assert sw.default_gateway is None


if __name__ == "__main__":
    print("Running SVI tests...")
    test_vlan_existence_and_rejection()
    test_svi_architecture_not_in_ports()
    test_ip_address_assignment_and_validation()
    test_duplicate_ip_check()
    test_shutdown_and_no_shutdown()
    test_no_ip_address()
    test_autostate_behavior()
    test_arp_resolution_between_host_and_svi()
    test_ping_host_to_svi()
    test_ping_svi_to_host()
    test_vlan_isolation_svi()
    test_stp_compatibility_with_svi()
    test_cli_show_commands_and_default_gateway()
    print("All 13 SVI tests PASSED successfully!")
