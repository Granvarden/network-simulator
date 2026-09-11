"""
tests/test_ttl.py - Comprehensive Unit & Integration Tests for L3 Hop Tracking and TTL Behavior
Validates:
1. Unusual router hostname (e.g. 'Jupiter') correctly recognized as L3 hop via device type
2. Multiple unusual router hostnames ('Jupiter', 'Mars') counted accurately as 2 L3 hops
3. Switches (Layer 2) are not counted as L3 hops
4. Host -> Router ICMP Echo Reply initial TTL is 255 (Cisco IOS behavior) and decrements across intermediate hops
5. Host -> Host through Router ICMP Echo Reply initial TTL is 64, decremented by L3 hops
6. Multi-router TTL decrement (64 -> 63 -> 62) in both forward and reverse directions
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.router import Router
from network.switch import Switch
from network.host import Host
from network.cable import Cable, CableType
from network.packet_engine import PacketEngine

def test_1_router_unusual_name():
    """
    Test 1 — Router ชื่อผิดปกติ:
    PC1 -> SW1 -> Jupiter -> PC2
    Jupiter เป็น Router จริง (ห้ามมีคำว่า router, r1, r2, gateway)
    ต้องนับ Jupiter เป็น 1 L3 hop จริง
    """
    print("\n--- TEST 1: Router with Unusual Hostname ('Jupiter') ---")
    pe = PacketEngine.get_instance()

    pc1 = Host("pc1", hostname="PC1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    sw1 = Switch("sw1", hostname="SW1")

    jupiter = Router("jup", hostname="Jupiter")
    jp0 = jupiter.get_port("g0/0")
    jp0.ip_address = "192.168.1.1"
    jp0.subnet_mask = "255.255.255.0"
    jp0.is_shutdown = False

    jp1 = jupiter.get_port("g0/1")
    jp1.ip_address = "192.168.2.1"
    jp1.subnet_mask = "255.255.255.0"
    jp1.is_shutdown = False

    pc2 = Host("pc2", hostname="PC2")
    pc2.configure_ip("192.168.2.10", "255.255.255.0", gateway="192.168.2.1")

    # Cabling
    Cable(pc1.eth0, sw1.get_port("g0/1"), CableType.CAT6)
    Cable(sw1.get_port("g0/2"), jp0, CableType.CAT6)
    Cable(jp1, pc2.eth0, CableType.CAT6)

    step = pe.trace_single_packet(pc1, "192.168.2.10", simulate_arp=False)
    print(f"Ping PC1 -> PC2: status={step['status_code']}, l3_hops={step.get('l3_hops')}, ttl={step['ttl']}, hops={step['hop_path']}")

    assert step["success"] is True, f"Ping failed: {step}"
    assert step["status_code"] == "!"
    assert step["l3_hops"] == 1, f"Expected 1 L3 hop for Jupiter, got {step.get('l3_hops')}"
    assert step["ttl"] == 63, f"Expected TTL 63 (64 - 1), got {step['ttl']}"
    assert "Jupiter" in step["hop_path"]
    print("[PASS] Test 1 passed: 'Jupiter' counted as 1 L3 hop, TTL=63")

def test_2_multiple_routers_unusual_names():
    """
    Test 2 — Router หลายตัวชื่อผิดปกติ:
    PC1 -> SW1 -> Jupiter -> Mars -> PC2
    Jupiter = Router, Mars = Router
    L3 hops ต้องเป็น 2 แม้ชื่อจะไม่มี router/r1/r2/gateway
    """
    print("\n--- TEST 2: Multiple Routers with Unusual Hostnames ('Jupiter', 'Mars') ---")
    pe = PacketEngine.get_instance()

    pc1 = Host("pc1", hostname="PC1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    sw1 = Switch("sw1", hostname="SW1")

    jupiter = Router("jup", hostname="Jupiter")
    jp0 = jupiter.get_port("g0/0")
    jp0.ip_address = "192.168.1.1"
    jp0.subnet_mask = "255.255.255.0"
    jp0.is_shutdown = False

    jp1 = jupiter.get_port("g0/1")
    jp1.ip_address = "10.0.0.1"
    jp1.subnet_mask = "255.255.255.252"
    jp1.is_shutdown = False

    mars = Router("mars", hostname="Mars")
    mp0 = mars.get_port("g0/0")
    mp0.ip_address = "10.0.0.2"
    mp0.subnet_mask = "255.255.255.252"
    mp0.is_shutdown = False

    mp1 = mars.get_port("g0/1")
    mp1.ip_address = "192.168.2.1"
    mp1.subnet_mask = "255.255.255.0"
    mp1.is_shutdown = False

    pc2 = Host("pc2", hostname="PC2")
    pc2.configure_ip("192.168.2.10", "255.255.255.0", gateway="192.168.2.1")

    # Static routes
    jupiter.add_static_route("192.168.2.0", "255.255.255.0", "10.0.0.2")
    mars.add_static_route("192.168.1.0", "255.255.255.0", "10.0.0.1")

    # Cabling
    Cable(pc1.eth0, sw1.get_port("g0/1"), CableType.CAT6)
    Cable(sw1.get_port("g0/2"), jp0, CableType.CAT6)
    Cable(jp1, mp0, CableType.CAT6)
    Cable(mp1, pc2.eth0, CableType.CAT6)

    step = pe.trace_single_packet(pc1, "192.168.2.10", simulate_arp=False)
    print(f"Ping PC1 -> PC2: status={step['status_code']}, l3_hops={step.get('l3_hops')}, ttl={step['ttl']}, hops={step['hop_path']}")

    assert step["success"] is True
    assert step["status_code"] == "!"
    assert step["l3_hops"] == 2, f"Expected 2 L3 hops for Jupiter and Mars, got {step.get('l3_hops')}"
    assert step["ttl"] == 62, f"Expected TTL 62 (64 - 2), got {step['ttl']}"
    print("[PASS] Test 2 passed: 'Jupiter' and 'Mars' counted as 2 L3 hops, TTL=62")

def test_3_switches_not_counted_as_l3():
    """
    Test 3 — Switch ไม่ควรถูกนับเป็น L3 Hop:
    PC1 -> SW1 -> SW2 -> Jupiter -> SW3 -> PC2
    Expected: L3 hops = 1 เพราะมี Router จริงเพียงตัวเดียว
    """
    print("\n--- TEST 3: Switches Not Counted as L3 Hops ---")
    pe = PacketEngine.get_instance()

    pc1 = Host("pc1", hostname="PC1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")
    sw3 = Switch("sw3", hostname="SW3")

    jupiter = Router("jup", hostname="Jupiter")
    jp0 = jupiter.get_port("g0/0")
    jp0.ip_address = "192.168.1.1"
    jp0.subnet_mask = "255.255.255.0"
    jp0.is_shutdown = False

    jp1 = jupiter.get_port("g0/1")
    jp1.ip_address = "192.168.2.1"
    jp1.subnet_mask = "255.255.255.0"
    jp1.is_shutdown = False

    pc2 = Host("pc2", hostname="PC2")
    pc2.configure_ip("192.168.2.10", "255.255.255.0", gateway="192.168.2.1")

    Cable(pc1.eth0, sw1.get_port("g0/1"), CableType.CAT6)
    Cable(sw1.get_port("g0/2"), sw2.get_port("g0/1"), CableType.CAT6)
    Cable(sw2.get_port("g0/2"), jp0, CableType.CAT6)
    Cable(jp1, sw3.get_port("g0/1"), CableType.CAT6)
    Cable(sw3.get_port("g0/2"), pc2.eth0, CableType.CAT6)

    # Pre-populate ARP across cascaded switches
    pc1.add_arp_entry("192.168.1.1", jp0.mac_address, "eth0")
    jupiter.add_arp_entry("192.168.1.10", pc1.eth0.mac_address, "g0/0")

    step = pe.trace_single_packet(pc1, "192.168.2.10", simulate_arp=False)
    print(f"Ping through 3 Switches + 1 Router: l3_hops={step.get('l3_hops')}, ttl={step['ttl']}, hops={step['hop_path']}")

    assert step["success"] is True
    assert step["l3_hops"] == 1, f"Expected 1 L3 hop (Jupiter only), got {step.get('l3_hops')}"
    assert step["ttl"] == 63, f"Expected TTL 63, got {step['ttl']}"
    print("[PASS] Test 3 passed: 3 Switches traversed, L3 hops correctly equals 1")

def test_4_host_to_router_echo_reply_ttl():
    """
    Test 4 — Host -> Router Echo Reply TTL:
    PC1 --- Jupiter (Router)
    ให้ PC1 ping interface ของ Jupiter
    Expected:
    Reply initial TTL = 255 (0 intermediate router hops -> TTL=255)
    และถ้า ping ผ่าน Router อื่น ให้ TTL ลดตาม L3 hop จริง (255 - 1 = 254)
    """
    print("\n--- TEST 4: Host -> Router Echo Reply TTL ---")
    pe = PacketEngine.get_instance()

    pc1 = Host("pc1", hostname="PC1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    jupiter = Router("jup", hostname="Jupiter")
    jp0 = jupiter.get_port("g0/0")
    jp0.ip_address = "192.168.1.1"
    jp0.subnet_mask = "255.255.255.0"
    jp0.is_shutdown = False

    jp1 = jupiter.get_port("g0/1")
    jp1.ip_address = "10.0.0.1"
    jp1.subnet_mask = "255.255.255.252"
    jp1.is_shutdown = False

    mars = Router("mars", hostname="Mars")
    mp0 = mars.get_port("g0/0")
    mp0.ip_address = "10.0.0.2"
    mp0.subnet_mask = "255.255.255.252"
    mp0.is_shutdown = False

    jupiter.add_static_route("10.0.0.0", "255.255.255.252", "10.0.0.2")
    mars.add_static_route("192.168.1.0", "255.255.255.0", "10.0.0.1")

    Cable(pc1.eth0, jp0, CableType.CAT6)
    Cable(jp1, mp0, CableType.CAT6)

    # 1. PC1 pings directly connected Router Jupiter
    step_direct = pe.trace_single_packet(pc1, "192.168.1.1", simulate_arp=False)
    print(f"Direct PC1 -> Jupiter (192.168.1.1): ttl={step_direct['ttl']}, l3_hops={step_direct.get('l3_hops')}")
    assert step_direct["success"] is True
    assert step_direct["ttl"] == 255, f"Expected Router initial TTL 255, got {step_direct['ttl']}"
    assert step_direct.get("l3_hops") == 0, f"Expected 0 intermediate forwarding hops, got {step_direct.get('l3_hops')}"

    # 2. PC1 pings remote Router Mars (via Jupiter)
    step_remote = pe.trace_single_packet(pc1, "10.0.0.2", simulate_arp=False)
    print(f"Remote PC1 -> Mars (10.0.0.2) via Jupiter: ttl={step_remote['ttl']}, l3_hops={step_remote.get('l3_hops')}")
    assert step_remote["success"] is True
    assert step_remote["ttl"] == 254, f"Expected Remote Router TTL 254 (255 - 1), got {step_remote['ttl']}"
    assert step_remote.get("l3_hops") == 1, f"Expected 1 intermediate L3 hop (Jupiter), got {step_remote.get('l3_hops')}"
    print("[PASS] Test 4 passed: Direct Router ping TTL=255, Remote Router ping TTL=254")

def test_5_host_to_host_through_router():
    """
    Test 5 — Host -> Host ผ่าน Router:
    PC1 -> SW1 -> Jupiter -> SW2 -> PC2
    Expected:
    Request initial TTL = 64
    Reply initial TTL = 64
    TTL ที่ปลายทาง = 64 - 1 = 63 ทั้งสองทิศทาง
    """
    print("\n--- TEST 5: Host -> Host through Router Two-Way TTL ---")
    pe = PacketEngine.get_instance()

    pc1 = Host("pc1", hostname="PC1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")

    jupiter = Router("jup", hostname="Jupiter")
    jp0 = jupiter.get_port("g0/0")
    jp0.ip_address = "192.168.1.1"
    jp0.subnet_mask = "255.255.255.0"
    jp0.is_shutdown = False

    jp1 = jupiter.get_port("g0/1")
    jp1.ip_address = "192.168.2.1"
    jp1.subnet_mask = "255.255.255.0"
    jp1.is_shutdown = False

    pc2 = Host("pc2", hostname="PC2")
    pc2.configure_ip("192.168.2.10", "255.255.255.0", gateway="192.168.2.1")

    Cable(pc1.eth0, sw1.get_port("g0/1"), CableType.CAT6)
    Cable(sw1.get_port("g0/2"), jp0, CableType.CAT6)
    Cable(jp1, sw2.get_port("g0/1"), CableType.CAT6)
    Cable(sw2.get_port("g0/2"), pc2.eth0, CableType.CAT6)

    # Forward: PC1 -> PC2
    res_fwd = pe.simulate_ping(pc1, "192.168.2.10", count=3, simulate_arp=False)
    assert res_fwd.loss_percent == 0
    assert all(ttl == 63 for ttl in res_fwd.ttl_replies), f"Expected TTL 63, got {res_fwd.ttl_replies}"

    # Reverse: PC2 -> PC1
    res_rev = pe.simulate_ping(pc2, "192.168.1.10", count=3, simulate_arp=False)
    assert res_rev.loss_percent == 0
    assert all(ttl == 63 for ttl in res_rev.ttl_replies), f"Expected TTL 63, got {res_rev.ttl_replies}"

    print("[PASS] Test 5 passed: Two-way Host <-> Host ping TTL=63 in both directions")

def test_6_multiple_routers_ttl_decrement():
    """
    Test 6 — หลาย Router:
    PC1 -> Jupiter -> Mars -> PC2
    Expected:
    Request: 64 -> 63 (Jupiter) -> 62 (Mars) -> PC2
    Reply:   64 -> 63 (Mars) -> 62 (Jupiter) -> PC1
    Destination TTL = 62 ทั้งสองทิศทาง
    """
    print("\n--- TEST 6: Multiple Routers TTL Decrement (PC1 -> Jupiter -> Mars -> PC2) ---")
    pe = PacketEngine.get_instance()

    pc1 = Host("pc1", hostname="PC1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0", gateway="192.168.1.1")

    jupiter = Router("jup", hostname="Jupiter")
    jp0 = jupiter.get_port("g0/0")
    jp0.ip_address = "192.168.1.1"
    jp0.subnet_mask = "255.255.255.0"
    jp0.is_shutdown = False

    jp1 = jupiter.get_port("g0/1")
    jp1.ip_address = "10.0.0.1"
    jp1.subnet_mask = "255.255.255.252"
    jp1.is_shutdown = False

    mars = Router("mars", hostname="Mars")
    mp0 = mars.get_port("g0/0")
    mp0.ip_address = "10.0.0.2"
    mp0.subnet_mask = "255.255.255.252"
    mp0.is_shutdown = False

    mp1 = mars.get_port("g0/1")
    mp1.ip_address = "192.168.2.1"
    mp1.subnet_mask = "255.255.255.0"
    mp1.is_shutdown = False

    pc2 = Host("pc2", hostname="PC2")
    pc2.configure_ip("192.168.2.10", "255.255.255.0", gateway="192.168.2.1")

    jupiter.add_static_route("192.168.2.0", "255.255.255.0", "10.0.0.2")
    mars.add_static_route("192.168.1.0", "255.255.255.0", "10.0.0.1")

    Cable(pc1.eth0, jp0, CableType.CAT6)
    Cable(jp1, mp0, CableType.CAT6)
    Cable(mp1, pc2.eth0, CableType.CAT6)

    # Forward: PC1 -> PC2
    res_fwd = pe.simulate_ping(pc1, "192.168.2.10", count=3, simulate_arp=False)
    assert res_fwd.loss_percent == 0
    assert all(ttl == 62 for ttl in res_fwd.ttl_replies), f"Expected TTL 62, got {res_fwd.ttl_replies}"

    # Reverse: PC2 -> PC1
    res_rev = pe.simulate_ping(pc2, "192.168.1.10", count=3, simulate_arp=False)
    assert res_rev.loss_percent == 0
    assert all(ttl == 62 for ttl in res_rev.ttl_replies), f"Expected TTL 62, got {res_rev.ttl_replies}"

    print("[PASS] Test 6 passed: Two-way multi-router ping TTL=62 (64 - 2 hops)")

if __name__ == "__main__":
    test_1_router_unusual_name()
    test_2_multiple_routers_unusual_names()
    test_3_switches_not_counted_as_l3()
    test_4_host_to_router_echo_reply_ttl()
    test_5_host_to_host_through_router()
    test_6_multiple_routers_ttl_decrement()
    print("\n==========================================")
    print("ALL TTL & L3 HOP TRACKING TESTS PASSED 100%!")
    print("==========================================")
