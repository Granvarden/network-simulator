"""
tests/test_dhcp.py - Comprehensive Test Suite for IPv4 DHCP Server and Client Simulation
Covers:
1. DHCP Pool creation, subnet arithmetic (/24, /30), and network/broadcast exclusions.
2. DHCPServer pool management (add, get, delete, lease cleanup).
3. Excluded addresses (single and range) and guarantee of non-allocation.
4. Complete DORA handshake (Discover -> Offer -> Request -> Ack) with valid options.
5. Host DHCP Client configuration (IP, subnet mask, default gateway, DNS server, state).
6. Multiple hosts receiving unique, non-overlapping IP leases.
7. Pool exhaustion handling and graceful rejection.
8. DHCPRELEASE handling and immediate IP reclaimability.
9. DHCP client rediscover reusing existing lease for the same MAC.
10. DHCPNAK generation on invalid, out-of-pool, or excluded IP requests.
11. SVI as DHCP Server (Switch SVI serving DHCP to access VLAN).
12. VLAN-aware DHCP allocation and strict subnet/broadcast isolation.
13. Router subinterface 802.1Q trunk DHCP Server serving multiple VLANs.
14. STP compatibility (broadcast packets dropped across blocked ports, no loops).
15. Static IP coexistence with DHCP on the same subnet without conflicts.
16. ARP resolution and ICMP Ping between DHCP clients and to the default gateway.
17. Cisco IOS CLI DHCP Pool configuration and mode transitions.
18. Cisco IOS CLI Show commands: show ip dhcp pool, binding, statistics.
19. Cisco IOS CLI interface DHCP: "ip address dhcp" and show ip int brief method.
20. Linux Host CLI emulation: dhclient and dhclient -r.
21. Cisco IOS show running-config inclusion of DHCP pools and excluded addresses.
22. Multi-switch topology DHCP traversal across 802.1Q trunk links.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.router import Router, is_valid_ipv4, is_valid_netmask
from network.switch import Switch, SVI
from network.host import Host
from network.cable import Cable
from network.packet_engine import PacketEngine
from network.dhcp import DHCPPool, DHCPServer, DHCPLease, DHCPMessage, DHCPMessageType, DHCPClientState
from cli.command_executor import CommandExecutor, IOSMode


def test_dhcp_pool_creation_and_subnet_arithmetic():
    """Test 1: DHCP Pool creation, subnet arithmetic (/24 and /30), and exclusion of net/bcast."""
    pool24 = DHCPPool("LAN24", network="192.168.1.0", subnet_mask="255.255.255.0",
                      default_router="192.168.1.1", dns_server="8.8.8.8", lease_duration=86400)
    assert pool24.name == "LAN24"
    assert pool24.get_total_addresses() == 254
    first_ip, last_ip = pool24.get_usable_ip_range()
    assert first_ip == "192.168.1.1"
    assert last_ip == "192.168.1.254"
    assert not pool24.is_ip_in_pool("192.168.1.0")    # Subnet ID excluded
    assert not pool24.is_ip_in_pool("192.168.1.255")  # Broadcast excluded
    assert pool24.is_ip_in_pool("192.168.1.1")
    assert pool24.is_ip_in_pool("192.168.1.254")
    assert not pool24.is_ip_in_pool("192.168.2.10")

    # /30 subnet (wildcard 3 -> 2 usable hosts: .1 and .2)
    pool30 = DHCPPool("P2P", network="10.0.0.0", subnet_mask="255.255.255.252")
    assert pool30.get_total_addresses() == 2
    f30, l30 = pool30.get_usable_ip_range()
    assert f30 == "10.0.0.1"
    assert l30 == "10.0.0.2"
    assert not pool30.is_ip_in_pool("10.0.0.0")
    assert not pool30.is_ip_in_pool("10.0.0.3")
    assert pool30.is_ip_in_pool("10.0.0.1")
    assert pool30.is_ip_in_pool("10.0.0.2")


def test_dhcp_server_pool_management():
    """Test 2: DHCPServer pool creation, retrieval, and deletion with lease cleanup."""
    router = Router("r1", hostname="Router1")
    server = router.dhcp_server
    assert server is not None

    p1 = server.create_pool("POOL_A")
    assert p1.name == "POOL_A"
    assert server.get_pool("POOL_A") is p1

    # Add a mock lease to POOL_A
    lease = DHCPLease("192.168.1.50", "02:00:1a:00:00:01", "PC1", "POOL_A")
    server.binding_table["192.168.1.50"] = lease
    server.mac_to_ip["02:00:1a:00:00:01"] = "192.168.1.50"

    # Delete pool
    assert server.delete_pool("POOL_A") is True
    assert server.get_pool("POOL_A") is None
    assert "192.168.1.50" not in server.binding_table
    assert "02:00:1a:00:00:01" not in server.mac_to_ip


def test_dhcp_excluded_addresses():
    """Test 3: Excluded address handling (single IP & range)."""
    router = Router("r1", hostname="Router1")
    server = router.dhcp_server
    pool = server.add_pool("LAN", network="192.168.1.0", subnet_mask="255.255.255.0", default_router="192.168.1.1")

    # Exclude single IP: default router 192.168.1.1
    server.add_excluded_address("192.168.1.1")
    assert "192.168.1.1" in server.excluded_addresses

    # Exclude range: 192.168.1.10 to 192.168.1.20
    server.add_excluded_address("192.168.1.10", "192.168.1.20")
    for i in range(10, 21):
        assert f"192.168.1.{i}" in server.excluded_addresses

    # Check available IPs in pool
    avail = pool.get_available_ips(server.excluded_addresses, set())
    assert "192.168.1.1" not in avail
    assert "192.168.1.10" not in avail
    assert "192.168.1.20" not in avail
    assert "192.168.1.2" in avail
    assert "192.168.1.21" in avail

    # Remove excluded address
    server.remove_excluded_address("192.168.1.1")
    assert "192.168.1.1" not in server.excluded_addresses


def test_dora_basic_handshake():
    """Test 4: Complete DORA handshake direct verification."""
    router = Router("r1", hostname="Router")
    server = router.dhcp_server
    pool = server.add_pool("LAN", network="192.168.1.0", subnet_mask="255.255.255.0",
                           default_router="192.168.1.1", dns_server="8.8.4.4")
    server.add_excluded_address("192.168.1.1")

    # 1. Discover
    disc = DHCPMessage(msg_type=DHCPMessageType.DISCOVER, xid=42, client_mac="02:00:1a:00:00:aa", hostname="HostA")
    offer = server.handle_discover(disc, in_subnet="192.168.1.0", server_ip="192.168.1.1")
    assert offer is not None
    assert offer.msg_type == DHCPMessageType.OFFER
    assert offer.xid == 42
    assert offer.yiaddr == "192.168.1.2"
    assert offer.router == "192.168.1.1"
    assert offer.dns_server == "8.8.4.4"

    # 2. Request
    req = DHCPMessage(msg_type=DHCPMessageType.REQUEST, xid=42, client_mac="02:00:1a:00:00:aa",
                      yiaddr=offer.yiaddr, server_id=offer.server_id, hostname="HostA")
    ack = server.handle_request(req, in_subnet="192.168.1.0", server_ip="192.168.1.1")
    assert ack is not None
    assert ack.msg_type == DHCPMessageType.ACK
    assert ack.yiaddr == "192.168.1.2"
    assert "192.168.1.2" in server.binding_table
    assert server.binding_table["192.168.1.2"].mac_address == "02:00:1a:00:00:aa"


def test_host_dhcp_client_configuration():
    """Test 5: Host DHCP client acquires IP and configures all interface & system fields."""
    router = Router("r1", hostname="R1")
    router.ports["g0/0"].ip_address = "192.168.1.1"
    router.ports["g0/0"].subnet_mask = "255.255.255.0"
    router.ports["g0/0"].is_shutdown = False

    pool = router.dhcp_server.add_pool("LAN", network="192.168.1.0", subnet_mask="255.255.255.0",
                                       default_router="192.168.1.1", dns_server="1.1.1.1", lease_duration=7200)
    router.dhcp_server.add_excluded_address("192.168.1.1")

    host = Host("h1", hostname="PC1")
    host.ports["eth0"].is_shutdown = False

    Cable(router.ports["g0/0"], host.ports["eth0"])

    assert host.ports["eth0"].ip_address is None
    assert host.default_gateway is None
    assert host.dhcp_client.state == DHCPClientState.INIT

    # Request DHCP
    ok, msg = host.request_dhcp("eth0")
    assert ok is True
    assert host.ports["eth0"].ip_address == "192.168.1.2"
    assert host.ports["eth0"].subnet_mask == "255.255.255.0"
    assert host.default_gateway == "192.168.1.1"
    assert host.dns_server == "1.1.1.1"
    assert host.dhcp_enabled is True
    assert host.dhcp_client.state == DHCPClientState.BOUND
    assert host.dhcp_lease is not None
    assert host.dhcp_lease.ip_address == "192.168.1.2"


def test_multiple_hosts_unique_leases():
    """Test 6: Multiple hosts connected to a switch get unique, non-overlapping IP leases."""
    sw = Switch("sw1", hostname="Switch")
    r1 = Router("r1", hostname="Router")
    r1.ports["g0/0"].ip_address = "192.168.1.1"
    r1.ports["g0/0"].subnet_mask = "255.255.255.0"
    r1.ports["g0/0"].is_shutdown = False

    r1.dhcp_server.add_pool("LAN", network="192.168.1.0", subnet_mask="255.255.255.0", default_router="192.168.1.1")
    r1.dhcp_server.add_excluded_address("192.168.1.1")

    # Connect Router to Switch port 1
    Cable(r1.ports["g0/0"], sw.ports["g0/1"])

    h1 = Host("h1", hostname="PC1")
    h2 = Host("h2", hostname="PC2")
    h3 = Host("h3", hostname="PC3")

    Cable(h1.ports["eth0"], sw.ports["g0/2"])
    Cable(h2.ports["eth0"], sw.ports["g0/3"])
    Cable(h3.ports["eth0"], sw.ports["g0/4"])

    ok1, _ = h1.request_dhcp("eth0")
    ok2, _ = h2.request_dhcp("eth0")
    ok3, _ = h3.request_dhcp("eth0")

    assert ok1 and ok2 and ok3
    ip1 = h1.ports["eth0"].ip_address
    ip2 = h2.ports["eth0"].ip_address
    ip3 = h3.ports["eth0"].ip_address

    assert len({ip1, ip2, ip3}) == 3  # All unique!
    assert ip1 in ("192.168.1.2", "192.168.1.3", "192.168.1.4")
    assert ip2 in ("192.168.1.2", "192.168.1.3", "192.168.1.4")
    assert ip3 in ("192.168.1.2", "192.168.1.3", "192.168.1.4")
    assert len(r1.dhcp_server.binding_table) == 3


def test_dhcp_pool_exhaustion():
    """Test 7: Pool exhaustion handling when all usable IP addresses are assigned."""
    router = Router("r1", hostname="R1")
    router.ports["g0/0"].ip_address = "10.0.0.1"
    router.ports["g0/0"].subnet_mask = "255.255.255.252"  # /30: only .1 and .2 usable
    router.ports["g0/0"].is_shutdown = False

    # Create /30 pool and exclude router IP .1 -> exactly 1 usable IP (.2)
    router.dhcp_server.add_pool("MINI", network="10.0.0.0", subnet_mask="255.255.255.252", default_router="10.0.0.1")
    router.dhcp_server.add_excluded_address("10.0.0.1")

    sw = Switch("sw1", hostname="SW")
    Cable(router.ports["g0/0"], sw.ports["g0/1"])

    h1 = Host("h1", hostname="PC1")
    h2 = Host("h2", hostname="PC2")
    Cable(h1.ports["eth0"], sw.ports["g0/2"])
    Cable(h2.ports["eth0"], sw.ports["g0/3"])

    # Host 1 takes the only available IP (.2)
    ok1, _ = h1.request_dhcp("eth0")
    assert ok1 is True
    assert h1.ports["eth0"].ip_address == "10.0.0.2"

    # Host 2 requests -> pool exhausted!
    ok2, err = h2.request_dhcp("eth0")
    assert ok2 is False
    assert "exhausted" in err.lower()
    assert h2.ports["eth0"].ip_address is None


def test_dhcp_release_and_reclaim():
    """Test 8: DHCPRELEASE clears host config and allows immediate IP reuse."""
    router = Router("r1", hostname="R1")
    router.ports["g0/0"].ip_address = "10.0.0.1"
    router.ports["g0/0"].subnet_mask = "255.255.255.252"
    router.ports["g0/0"].is_shutdown = False

    router.dhcp_server.add_pool("MINI", network="10.0.0.0", subnet_mask="255.255.255.252", default_router="10.0.0.1")
    router.dhcp_server.add_excluded_address("10.0.0.1")

    sw = Switch("sw1", hostname="SW")
    Cable(router.ports["g0/0"], sw.ports["g0/1"])

    h1 = Host("h1", hostname="PC1")
    h2 = Host("h2", hostname="PC2")
    Cable(h1.ports["eth0"], sw.ports["g0/2"])
    Cable(h2.ports["eth0"], sw.ports["g0/3"])

    # Host 1 leases .2
    h1.request_dhcp("eth0")
    assert h1.ports["eth0"].ip_address == "10.0.0.2"

    # Host 1 releases .2
    rel_ok, rel_msg = h1.release_dhcp("eth0")
    assert rel_ok is True
    assert h1.ports["eth0"].ip_address is None
    assert h1.default_gateway is None
    assert "10.0.0.2" not in router.dhcp_server.binding_table

    # Now Host 2 can lease the released .2
    ok2, _ = h2.request_dhcp("eth0")
    assert ok2 is True
    assert h2.ports["eth0"].ip_address == "10.0.0.2"


def test_dhcp_re_request_same_ip():
    """Test 9: DHCP Client rediscovering with existing lease is offered the same IP."""
    router = Router("r1", hostname="R1")
    router.ports["g0/0"].ip_address = "192.168.1.1"
    router.ports["g0/0"].subnet_mask = "255.255.255.0"
    router.ports["g0/0"].is_shutdown = False

    router.dhcp_server.add_pool("LAN", network="192.168.1.0", subnet_mask="255.255.255.0", default_router="192.168.1.1")
    router.dhcp_server.add_excluded_address("192.168.1.1")

    host = Host("h1", hostname="PC1")
    Cable(router.ports["g0/0"], host.ports["eth0"])

    ok, _ = host.request_dhcp("eth0")
    assert ok is True
    assigned_ip = host.ports["eth0"].ip_address

    # Rediscover without releasing
    ok2, _ = host.request_dhcp("eth0")
    assert ok2 is True
    assert host.ports["eth0"].ip_address == assigned_ip


def test_dhcp_nak_on_invalid_request():
    """Test 10: Server generates DHCPNAK on invalid, out-of-pool, or excluded IP requests."""
    router = Router("r1", hostname="R1")
    server = router.dhcp_server
    server.add_pool("LAN", network="192.168.1.0", subnet_mask="255.255.255.0", default_router="192.168.1.1")
    server.add_excluded_address("192.168.1.5")

    # Request out of pool
    req_bad = DHCPMessage(msg_type=DHCPMessageType.REQUEST, xid=10, client_mac="02:00:1a:00:00:11",
                          yiaddr="10.99.99.99")
    nak = server.handle_request(req_bad, in_subnet="192.168.1.0")
    assert nak.msg_type == DHCPMessageType.NAK

    # Request excluded IP
    req_ex = DHCPMessage(msg_type=DHCPMessageType.REQUEST, xid=11, client_mac="02:00:1a:00:00:11",
                         yiaddr="192.168.1.5")
    nak2 = server.handle_request(req_ex, in_subnet="192.168.1.0")
    assert nak2.msg_type == DHCPMessageType.NAK


def test_svi_as_dhcp_server():
    """Test 11: Switch SVI (Layer-3) acting as DHCP Server for access VLAN."""
    sw = Switch("sw1", hostname="CoreSwitch")
    sw.add_vlan(10, "DATA")
    svi10 = sw.create_svi(10)
    svi10.ip_address = "192.168.10.1"
    svi10.subnet_mask = "255.255.255.0"
    svi10.is_shutdown = False

    # Configure DHCP pool on Switch
    sw.dhcp_server.add_pool("VLAN10_POOL", network="192.168.10.0", subnet_mask="255.255.255.0",
                            default_router="192.168.10.1", dns_server="8.8.8.8")
    sw.dhcp_server.add_excluded_address("192.168.10.1")

    # Host connected to access port in VLAN 10
    sw.ports["g0/1"].mode = "access"
    sw.ports["g0/1"].access_vlan = 10
    sw.ports["g0/1"].is_shutdown = False

    host = Host("h1", hostname="Client1")
    Cable(host.ports["eth0"], sw.ports["g0/1"])

    assert svi10.is_link_up is True

    ok, _ = host.request_dhcp("eth0")
    assert ok is True
    assert host.ports["eth0"].ip_address == "192.168.10.2"
    assert host.ports["eth0"].subnet_mask == "255.255.255.0"
    assert host.default_gateway == "192.168.10.1"


def test_vlan_aware_dhcp_isolation():
    """Test 12: Multiple VLANs get correct IPs from their respective pools."""
    sw = Switch("sw1", hostname="SW")
    sw.add_vlan(10, "VLAN10")
    sw.add_vlan(20, "VLAN20")

    svi10 = sw.create_svi(10)
    svi10.ip_address = "192.168.10.1"
    svi10.subnet_mask = "255.255.255.0"
    svi10.is_shutdown = False

    svi20 = sw.create_svi(20)
    svi20.ip_address = "192.168.20.1"
    svi20.subnet_mask = "255.255.255.0"
    svi20.is_shutdown = False

    sw.dhcp_server.add_pool("POOL10", network="192.168.10.0", subnet_mask="255.255.255.0", default_router="192.168.10.1")
    sw.dhcp_server.add_excluded_address("192.168.10.1")

    sw.dhcp_server.add_pool("POOL20", network="192.168.20.0", subnet_mask="255.255.255.0", default_router="192.168.20.1")
    sw.dhcp_server.add_excluded_address("192.168.20.1")

    sw.ports["g0/1"].mode = "access"
    sw.ports["g0/1"].access_vlan = 10

    sw.ports["g0/2"].mode = "access"
    sw.ports["g0/2"].access_vlan = 20

    h10 = Host("h10", hostname="PC_V10")
    h20 = Host("h20", hostname="PC_V20")

    Cable(h10.ports["eth0"], sw.ports["g0/1"])
    Cable(h20.ports["eth0"], sw.ports["g0/2"])

    ok10, _ = h10.request_dhcp("eth0")
    ok20, _ = h20.request_dhcp("eth0")

    assert ok10 and ok20
    assert h10.ports["eth0"].ip_address.startswith("192.168.10.")
    assert h10.default_gateway == "192.168.10.1"

    assert h20.ports["eth0"].ip_address.startswith("192.168.20.")
    assert h20.default_gateway == "192.168.20.1"


def test_router_subinterfaces_dhcp_server():
    """Test 13: Router-on-a-stick subinterfaces serving DHCP to different VLANs over trunk."""
    r1 = Router("r1", hostname="Router")
    r1.ports["g0/0"].is_shutdown = False

    sub10 = r1.create_subinterface("g0/0", 10)
    sub10.vlan_id = 10
    sub10.ip_address = "172.16.10.1"
    sub10.subnet_mask = "255.255.255.0"
    sub10.is_shutdown = False

    sub20 = r1.create_subinterface("g0/0", 20)
    sub20.vlan_id = 20
    sub20.ip_address = "172.16.20.1"
    sub20.subnet_mask = "255.255.255.0"
    sub20.is_shutdown = False

    r1.dhcp_server.add_pool("VLAN10", network="172.16.10.0", subnet_mask="255.255.255.0", default_router="172.16.10.1")
    r1.dhcp_server.add_excluded_address("172.16.10.1")

    r1.dhcp_server.add_pool("VLAN20", network="172.16.20.0", subnet_mask="255.255.255.0", default_router="172.16.20.1")
    r1.dhcp_server.add_excluded_address("172.16.20.1")

    sw = Switch("sw1", hostname="Switch")
    sw.add_vlan(10)
    sw.add_vlan(20)

    # Trunk port to Router
    sw.ports["g0/1"].mode = "trunk"
    sw.ports["g0/1"].trunk_allowed_vlans = {1, 10, 20}
    Cable(r1.ports["g0/0"], sw.ports["g0/1"])

    # Access ports
    sw.ports["g0/2"].mode = "access"
    sw.ports["g0/2"].access_vlan = 10

    sw.ports["g0/3"].mode = "access"
    sw.ports["g0/3"].access_vlan = 20

    h1 = Host("h1", hostname="Client10")
    h2 = Host("h2", hostname="Client20")

    Cable(h1.ports["eth0"], sw.ports["g0/2"])
    Cable(h2.ports["eth0"], sw.ports["g0/3"])

    ok1, _ = h1.request_dhcp("eth0")
    ok2, _ = h2.request_dhcp("eth0")

    assert ok1 is True
    assert ok2 is True
    assert h1.ports["eth0"].ip_address == "172.16.10.2"
    assert h1.default_gateway == "172.16.10.1"
    assert h2.ports["eth0"].ip_address == "172.16.20.2"
    assert h2.default_gateway == "172.16.20.1"


def test_stp_compatibility_dhcp_blocked_port():
    """Test 14: DHCP broadcast packets are dropped on STP Blocking ports (no loop)."""
    pe = PacketEngine.get_instance()
    sw = Switch("sw1", hostname="SW")
    r1 = Router("r1", hostname="R1")
    r1.ports["g0/0"].ip_address = "192.168.1.1"
    r1.ports["g0/0"].subnet_mask = "255.255.255.0"
    r1.ports["g0/0"].is_shutdown = False

    r1.dhcp_server.add_pool("LAN", network="192.168.1.0", subnet_mask="255.255.255.0")
    Cable(r1.ports["g0/0"], sw.ports["g0/1"])

    h1 = Host("h1", hostname="PC1")
    Cable(h1.ports["eth0"], sw.ports["g0/2"])

    sw.recalculate_stp()
    # If port g0/1 is Blocking, DHCP must fail
    sw.ports["g0/1"].stp_state = "Blocking"
    sw._stp_dirty = False
    endpoints = pe._collect_broadcast_endpoints(h1, h1.ports["eth0"], vlan_id=1)
    # r1 should NOT be discovered because g0/1 is Blocking
    assert not any(dev == r1 for dev, iface, vlan in endpoints)

    # Bring port to Forwarding
    sw.ports["g0/1"].stp_state = "Forwarding"
    sw._stp_dirty = False
    endpoints2 = pe._collect_broadcast_endpoints(h1, h1.ports["eth0"], vlan_id=1)
    assert any(dev == r1 for dev, iface, vlan in endpoints2)


def test_static_ip_coexistence_and_ping():
    """Test 15: Static IP hosts coexist with DHCP hosts without conflicts, and can ping."""
    router = Router("r1", hostname="R1")
    router.ports["g0/0"].ip_address = "192.168.1.1"
    router.ports["g0/0"].subnet_mask = "255.255.255.0"
    router.ports["g0/0"].is_shutdown = False

    router.dhcp_server.add_pool("LAN", network="192.168.1.0", subnet_mask="255.255.255.0", default_router="192.168.1.1")
    # Exclude .1 and static host .10
    router.dhcp_server.add_excluded_address("192.168.1.1")
    router.dhcp_server.add_excluded_address("192.168.1.10")

    sw = Switch("sw1", hostname="SW")
    Cable(router.ports["g0/0"], sw.ports["g0/1"])

    # Static host .10
    h_static = Host("h_stat", hostname="StaticPC")
    h_static.ports["eth0"].ip_address = "192.168.1.10"
    h_static.ports["eth0"].subnet_mask = "255.255.255.0"
    h_static.default_gateway = "192.168.1.1"
    Cable(h_static.ports["eth0"], sw.ports["g0/2"])

    # Dynamic host
    h_dyn = Host("h_dyn", hostname="DynPC")
    Cable(h_dyn.ports["eth0"], sw.ports["g0/3"])

    ok, _ = h_dyn.request_dhcp("eth0")
    assert ok is True
    assert h_dyn.ports["eth0"].ip_address == "192.168.1.2"

    # Ping from dynamic host to static host
    pe = PacketEngine.get_instance()
    res = pe.simulate_ping(h_dyn, "192.168.1.10", count=2)
    assert res.packets_received == 2


def test_dhcp_hosts_ping_each_other_and_gateway():
    """Test 16: Two DHCP-configured hosts resolve ARP and ping each other and the gateway."""
    router = Router("r1", hostname="R1")
    router.ports["g0/0"].ip_address = "192.168.1.1"
    router.ports["g0/0"].subnet_mask = "255.255.255.0"
    router.ports["g0/0"].is_shutdown = False

    router.dhcp_server.add_pool("LAN", network="192.168.1.0", subnet_mask="255.255.255.0", default_router="192.168.1.1")
    router.dhcp_server.add_excluded_address("192.168.1.1")

    sw = Switch("sw1", hostname="SW")
    Cable(router.ports["g0/0"], sw.ports["g0/1"])

    h1 = Host("h1", hostname="PC1")
    h2 = Host("h2", hostname="PC2")
    Cable(h1.ports["eth0"], sw.ports["g0/2"])
    Cable(h2.ports["eth0"], sw.ports["g0/3"])

    h1.request_dhcp("eth0")
    h2.request_dhcp("eth0")

    pe = PacketEngine.get_instance()
    # Ping default gateway
    res_gw = pe.simulate_ping(h1, "192.168.1.1", count=2)
    assert res_gw.packets_received == 2

    # Ping peer host
    res_peer = pe.simulate_ping(h1, h2.ports["eth0"].ip_address, count=2)
    assert res_peer.packets_received == 2


def test_cisco_cli_dhcp_pool_configuration():
    """Test 17: Cisco IOS CLI configuration for DHCP Pool, network, default-router, dns, lease."""
    router = Router("r1", hostname="Router")
    cli = CommandExecutor(router)

    cli.execute("enable")
    cli.execute("configure terminal")
    assert cli.mode == IOSMode.CONFIG

    # Configure excluded addresses
    out_ex = cli.execute("ip dhcp excluded-address 192.168.1.1 192.168.1.10")
    assert out_ex == ""
    assert ("192.168.1.1", "192.168.1.10") in router.dhcp_server.excluded_ranges

    # Enter DHCP pool config
    out_pool = cli.execute("ip dhcp pool MY_POOL")
    assert out_pool == ""
    assert cli.mode == IOSMode.CONFIG_DHCP_POOL
    assert cli.get_prompt() == "Router(dhcp-config)#"

    # Pool subcommands
    cli.execute("network 192.168.1.0 255.255.255.0")
    cli.execute("default-router 192.168.1.1")
    cli.execute("dns-server 8.8.8.8 1.1.1.1")
    cli.execute("lease 3 12 30")

    pool = router.dhcp_server.get_pool("MY_POOL")
    assert pool.network == "192.168.1.0"
    assert pool.subnet_mask == "255.255.255.0"
    assert pool.default_router == "192.168.1.1"
    assert pool.dns_servers == ["8.8.8.8", "1.1.1.1"]
    assert pool.lease_duration == 3 * 86400 + 12 * 3600 + 30 * 60

    # Exit back to config mode
    cli.execute("exit")
    assert cli.mode == IOSMode.CONFIG
    assert cli.get_prompt() == "Router(config)#"


def test_cisco_cli_show_commands():
    """Test 18: Cisco IOS show ip dhcp pool, show ip dhcp binding, show ip dhcp statistics."""
    router = Router("r1", hostname="Router")
    cli = CommandExecutor(router)

    cli.execute("enable")
    cli.execute("configure terminal")
    cli.execute("ip dhcp excluded-address 192.168.1.1 192.168.1.5")
    cli.execute("ip dhcp pool OFFICE")
    cli.execute("network 192.168.1.0 255.255.255.0")
    cli.execute("default-router 192.168.1.1")
    cli.execute("end")

    # Add a mock lease
    router.dhcp_server.binding_table["192.168.1.20"] = DHCPLease(
        "192.168.1.20", "02:00:1a:00:00:22", "Desktop", "OFFICE", lease_duration=86400
    )
    router.dhcp_server.statistics["discover"] = 5
    router.dhcp_server.statistics["offer"] = 5
    router.dhcp_server.statistics["request"] = 4
    router.dhcp_server.statistics["ack"] = 4

    # show ip dhcp pool
    out_pool = cli.execute("show ip dhcp pool")
    assert "Pool OFFICE :" in out_pool
    assert "Total addresses                : 254" in out_pool
    assert "Leased addresses               : 1" in out_pool
    assert "Excluded addresses             : 5" in out_pool

    # show ip dhcp binding
    out_bind = cli.execute("show ip dhcp binding")
    assert "192.168.1.20" in out_bind
    assert "0200.1a00.0022" in out_bind
    assert "Automatic" in out_bind

    # show ip dhcp statistics
    out_stat = cli.execute("show ip dhcp statistics")
    assert "DHCPDISCOVER                    5" in out_stat
    assert "DHCPOFFER                       5" in out_stat
    assert "DHCPACK                         4" in out_stat


def test_cisco_cli_ip_address_dhcp():
    """Test 19: Cisco IOS interface DHCP client: 'ip address dhcp' and method in show ip int brief."""
    r1 = Router("r1", hostname="R1")
    r1.ports["g0/0"].ip_address = "192.168.50.1"
    r1.ports["g0/0"].subnet_mask = "255.255.255.0"
    r1.ports["g0/0"].is_shutdown = False

    r1.dhcp_server.add_pool("LAN50", network="192.168.50.0", subnet_mask="255.255.255.0", default_router="192.168.50.1")
    r1.dhcp_server.add_excluded_address("192.168.50.1")

    # Client router R2
    r2 = Router("r2", hostname="R2")
    r2.ports["g0/0"].is_shutdown = False
    Cable(r1.ports["g0/0"], r2.ports["g0/0"])

    cli = CommandExecutor(r2)
    cli.execute("enable")
    cli.execute("configure terminal")
    cli.execute("interface g0/0")
    out = cli.execute("ip address dhcp")
    assert out == ""
    assert r2.ports["g0/0"].ip_address == "192.168.50.2"

    cli.execute("end")
    out_brief = cli.execute("show ip interface brief")
    assert "192.168.50.2" in out_brief
    assert "DHCP" in out_brief


def test_linux_host_cli_dhclient():
    """Test 20: Linux Host CLI: dhclient and dhclient -r."""
    router = Router("r1", hostname="R1")
    router.ports["g0/0"].ip_address = "192.168.1.1"
    router.ports["g0/0"].subnet_mask = "255.255.255.0"
    router.ports["g0/0"].is_shutdown = False

    router.dhcp_server.add_pool("LAN", network="192.168.1.0", subnet_mask="255.255.255.0", default_router="192.168.1.1")
    router.dhcp_server.add_excluded_address("192.168.1.1")

    host = Host("h1", hostname="ubuntu")
    Cable(router.ports["g0/0"], host.ports["eth0"])

    cli = CommandExecutor(host)
    # Acquire IP
    out = cli.execute("dhclient")
    assert "DHCPDISCOVER on eth0" in out
    assert "DHCPOFFER of 192.168.1.2" in out
    assert "bound to 192.168.1.2" in out

    out_if = cli.execute("ifconfig")
    assert "inet 192.168.1.2" in out_if

    # Release IP
    out_rel = cli.execute("dhclient -r")
    assert "released IP" in out_rel

    out_if2 = cli.execute("ifconfig")
    assert "inet unassigned" in out_if2


def test_show_running_config_dhcp():
    """Test 21: Show running-config displays DHCP pools and excluded addresses."""
    sw = Switch("sw1", hostname="SW1")
    cli = CommandExecutor(sw)

    cli.execute("enable")
    cli.execute("configure terminal")
    cli.execute("ip dhcp excluded-address 10.0.0.1 10.0.0.10")
    cli.execute("ip dhcp pool SALES")
    cli.execute("network 10.0.0.0 255.255.255.0")
    cli.execute("default-router 10.0.0.1")
    cli.execute("dns-server 8.8.8.8")
    cli.execute("lease 7")
    cli.execute("end")

    run_cfg = cli.execute("show running-config")
    assert "ip dhcp excluded-address 10.0.0.1 10.0.0.10" in run_cfg
    assert "ip dhcp pool SALES" in run_cfg
    assert " network 10.0.0.0 255.255.255.0" in run_cfg
    assert " default-router 10.0.0.1" in run_cfg
    assert " dns-server 8.8.8.8" in run_cfg
    assert " lease 7" in run_cfg


def test_multi_switch_dhcp_over_trunk():
    """Test 22: Host -> Switch1 (access vlan 10) -> Trunk -> Switch2 (SVI Vlan10 DHCP Server)."""
    # Switch 2 (Core with SVI Vlan10 and DHCP Server)
    sw2 = Switch("sw2", hostname="CoreSW")
    sw2.add_vlan(10)
    svi10 = sw2.create_svi(10)
    svi10.ip_address = "192.168.10.1"
    svi10.subnet_mask = "255.255.255.0"
    svi10.is_shutdown = False

    sw2.dhcp_server.add_pool("LAN10", network="192.168.10.0", subnet_mask="255.255.255.0", default_router="192.168.10.1")
    sw2.dhcp_server.add_excluded_address("192.168.10.1")

    # Switch 1 (Access Switch)
    sw1 = Switch("sw1", hostname="AccessSW")
    sw1.add_vlan(10)

    # Trunk between SW1 g0/1 and SW2 g0/1
    sw1.ports["g0/1"].mode = "trunk"
    sw1.ports["g0/1"].trunk_allowed_vlans = {1, 10}
    sw2.ports["g0/1"].mode = "trunk"
    sw2.ports["g0/1"].trunk_allowed_vlans = {1, 10}
    Cable(sw1.ports["g0/1"], sw2.ports["g0/1"])

    # Host on SW1 g0/2 (access vlan 10)
    sw1.ports["g0/2"].mode = "access"
    sw1.ports["g0/2"].access_vlan = 10

    host = Host("h1", hostname="PC1")
    Cable(host.ports["eth0"], sw1.ports["g0/2"])

    ok, _ = host.request_dhcp("eth0")
    assert ok is True
    assert host.ports["eth0"].ip_address == "192.168.10.2"
    assert host.default_gateway == "192.168.10.1"


if __name__ == "__main__":
    print("Running DHCP tests...")
    test_dhcp_pool_creation_and_subnet_arithmetic()
    test_dhcp_server_pool_management()
    test_dhcp_excluded_addresses()
    test_dora_basic_handshake()
    test_host_dhcp_client_configuration()
    test_multiple_hosts_unique_leases()
    test_dhcp_pool_exhaustion()
    test_dhcp_release_and_reclaim()
    test_dhcp_re_request_same_ip()
    test_dhcp_nak_on_invalid_request()
    test_svi_as_dhcp_server()
    test_vlan_aware_dhcp_isolation()
    test_router_subinterfaces_dhcp_server()
    test_stp_compatibility_dhcp_blocked_port()
    test_static_ip_coexistence_and_ping()
    test_dhcp_hosts_ping_each_other_and_gateway()
    test_cisco_cli_dhcp_pool_configuration()
    test_cisco_cli_show_commands()
    test_cisco_cli_ip_address_dhcp()
    test_linux_host_cli_dhclient()
    test_show_running_config_dhcp()
    test_multi_switch_dhcp_over_trunk()
    print("All 22 DHCP tests PASSED successfully!")
