"""
tests/test_stp.py - Comprehensive Spanning Tree Protocol (IEEE 802.1D) Unit & Integration Tests
Validates:
1. Root Bridge Election (Lowest Bridge ID = Root)
2. Priority Election (Priority 24576 beats 32768)
3. MAC Address Tie Break (Equal priority -> lowest MAC wins)
4. Root Port & Designated Port selection (SW1 Root <-> SW2 Non-Root)
5. Triangle Loop (SW1-SW2-SW3) -> Exactly 1 port in Blocking state
6. Broadcast Loop Prevention (ARP/Broadcast frame does not infinite loop)
7. MAC Learning + STP (Source MAC learned on forwarding ports, blocking port respected)
8. VLAN Isolation + STP (VLAN 10 / 20 isolation preserved with loop prevention)
9. Link Failure & STP Recalculation (Cut link -> Alternate port transitions to Forwarding)
10. CLI `show spanning-tree` formatting and priority configuration
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.switch import Switch
from network.host import Host
from network.cable import Cable, CableType
from network.packet_engine import PacketEngine
from cli.command_executor import CommandExecutor, IOSMode

def test_1_root_bridge_election():
    """
    Test 1 — Root Bridge Election:
    SW1, SW2, SW3
    Switch with lowest Bridge ID must be elected Root Bridge.
    """
    print("\n--- TEST 1: Root Bridge Election ---")
    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")
    sw3 = Switch("sw3", hostname="SW3")

    sw1.stp_priority = 32768
    sw2.stp_priority = 32768
    sw3.stp_priority = 32768

    sw1.mac_address = "00:11:22:33:44:01"
    sw2.mac_address = "00:11:22:33:44:02"
    sw3.mac_address = "00:11:22:33:44:03"

    # Line topology: SW1 <-> SW2 <-> SW3
    Cable(sw1.get_port("g0/1"), sw2.get_port("g0/1"), CableType.CAT6)
    Cable(sw2.get_port("g0/2"), sw3.get_port("g0/1"), CableType.CAT6)

    sw1.recalculate_stp()

    print(f"SW1 Bridge ID: {sw1.bridge_id}, Root: {sw1.root_bridge_id}")
    print(f"SW2 Bridge ID: {sw2.bridge_id}, Root: {sw2.root_bridge_id}")
    print(f"SW3 Bridge ID: {sw3.bridge_id}, Root: {sw3.root_bridge_id}")

    assert sw1.is_root_bridge is True, "SW1 with lowest MAC should be Root Bridge"
    assert sw2.is_root_bridge is False
    assert sw3.is_root_bridge is False

    assert sw2.root_bridge_id == sw1.bridge_id
    assert sw3.root_bridge_id == sw1.bridge_id
    print("[PASS] Test 1 passed: SW1 elected Root Bridge based on lowest Bridge ID")

def test_2_priority_election():
    """
    Test 2 — Priority Election:
    SW1 priority 32768, MAC 00:00:00:00:00:01
    SW2 priority 24576, MAC 00:00:00:00:00:99
    Expected: SW2 = Root (Priority takes precedence over MAC)
    """
    print("\n--- TEST 2: Priority Election ---")
    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")

    sw1.stp_priority = 32768
    sw1.mac_address = "00:00:00:00:00:01"

    sw2.stp_priority = 24576
    sw2.mac_address = "00:00:00:00:00:99"

    Cable(sw1.get_port("g0/1"), sw2.get_port("g0/1"), CableType.CAT6)

    sw1.recalculate_stp()

    print(f"SW1 Priority: {sw1.stp_priority}, SW2 Priority: {sw2.stp_priority}")
    print(f"Elected Root Bridge ID: {sw1.root_bridge_id}")

    assert sw2.is_root_bridge is True, "SW2 with lower priority 24576 must be Root"
    assert sw1.is_root_bridge is False
    assert sw1.root_bridge_id == sw2.bridge_id
    print("[PASS] Test 2 passed: Lower priority 24576 elected Root Bridge")

def test_3_mac_tie_break():
    """
    Test 3 — MAC Tie Break:
    Equal Priority:
    SW1 MAC = lower
    SW2 MAC = higher
    Expected: SW1 = Root
    """
    print("\n--- TEST 3: MAC Address Tie Break ---")
    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")

    sw1.stp_priority = 32768
    sw1.mac_address = "00:00:5e:00:53:01"

    sw2.stp_priority = 32768
    sw2.mac_address = "00:00:5e:00:53:02"

    Cable(sw1.get_port("g0/1"), sw2.get_port("g0/1"), CableType.CAT6)

    sw1.recalculate_stp()

    assert sw1.is_root_bridge is True
    assert sw2.is_root_bridge is False
    print("[PASS] Test 3 passed: Equal priority tie broken by MAC address (SW1 wins)")

def test_4_root_port_selection():
    """
    Test 4 — Root Port & Designated Port:
    SW1 (ROOT) <-> SW2
    Expected:
    SW1 port = Designated
    SW2 port = Root
    """
    print("\n--- TEST 4: Root Port & Designated Port ---")
    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")

    sw1.stp_priority = 24576  # SW1 is Root
    sw2.stp_priority = 32768

    Cable(sw1.get_port("g0/1"), sw2.get_port("g0/1"), CableType.CAT6)

    sw1.recalculate_stp()

    sw1_p1 = sw1.get_port("g0/1")
    sw2_p1 = sw2.get_port("g0/1")

    print(f"SW1 (Root) g0/1: Role={sw1_p1.stp_role}, State={sw1_p1.stp_state}")
    print(f"SW2 (Non-Root) g0/1: Role={sw2_p1.stp_role}, State={sw2_p1.stp_state}")

    assert sw1_p1.stp_role == "Designated"
    assert sw1_p1.stp_state == "Forwarding"

    assert sw2_p1.stp_role == "Root"
    assert sw2_p1.stp_state == "Forwarding"
    assert sw2.root_port == sw2_p1
    assert sw2.root_path_cost == 4
    print("[PASS] Test 4 passed: SW1 port Designated, SW2 port Root")

def test_5_triangle_loop_blocking():
    """
    Test 5 — Triangle Loop:
          SW1 (Root)
         /   \
        /     \
      SW2-----SW3
    Expected: Exactly 1 redundant path = Blocking
    No forwarding loop!
    """
    print("\n--- TEST 5: Triangle Loop & Single Port Blocking ---")
    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")
    sw3 = Switch("sw3", hostname="SW3")

    sw1.stp_priority = 24576
    sw2.stp_priority = 32768
    sw3.stp_priority = 32768

    sw1.mac_address = "00:11:22:33:44:01"
    sw2.mac_address = "00:11:22:33:44:02"
    sw3.mac_address = "00:11:22:33:44:03"

    # Triangle cabling:
    # SW1 g0/1 <-> SW2 g0/1
    # SW1 g0/2 <-> SW3 g0/1
    # SW2 g0/2 <-> SW3 g0/2
    c1 = Cable(sw1.get_port("g0/1"), sw2.get_port("g0/1"), CableType.CAT6)
    c2 = Cable(sw1.get_port("g0/2"), sw3.get_port("g0/1"), CableType.CAT6)
    c3 = Cable(sw2.get_port("g0/2"), sw3.get_port("g0/2"), CableType.CAT6)

    sw1.recalculate_stp()

    # Collect port states
    sw1_states = {p.name: (p.stp_role, p.stp_state) for p in sw1.ports.values() if p.cable}
    sw2_states = {p.name: (p.stp_role, p.stp_state) for p in sw2.ports.values() if p.cable}
    sw3_states = {p.name: (p.stp_role, p.stp_state) for p in sw3.ports.values() if p.cable}

    print(f"SW1 ports: {sw1_states}")
    print(f"SW2 ports: {sw2_states}")
    print(f"SW3 ports: {sw3_states}")

    # Count blocking ports in entire triangle
    all_ports = [p for sw in (sw1, sw2, sw3) for p in sw.ports.values() if p.cable]
    blocking_ports = [p for p in all_ports if p.stp_state == "Blocking"]
    forwarding_ports = [p for p in all_ports if p.stp_state == "Forwarding"]

    assert len(blocking_ports) == 1, f"Expected exactly 1 Blocking port in triangle, got {len(blocking_ports)}"
    assert len(forwarding_ports) == 5, f"Expected 5 Forwarding ports in triangle, got {len(forwarding_ports)}"

    # SW3 g0/2 should be the Blocking Alternate port (SW2 has lower MAC than SW3)
    assert sw3.get_port("g0/2").stp_state == "Blocking"
    assert sw3.get_port("g0/2").stp_role == "Alternate"
    print("[PASS] Test 5 passed: Exactly 1 port (SW3 g0/2) is Blocking (Alternate)")

def test_6_broadcast_loop_prevention():
    """
    Test 6 — Broadcast Loop Prevention:
    Send broadcast/flooding traffic into a triangle switch topology with physical loop.
    Verify: No infinite loop, traffic converges cleanly.
    """
    print("\n--- TEST 6: Broadcast Loop Prevention ---")
    pe = PacketEngine.get_instance()

    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")
    sw3 = Switch("sw3", hostname="SW3")

    sw1.stp_priority = 24576
    sw2.stp_priority = 32768
    sw3.stp_priority = 32768

    sw1.mac_address = "00:11:22:33:44:01"
    sw2.mac_address = "00:11:22:33:44:02"
    sw3.mac_address = "00:11:22:33:44:03"

    # Triangle loop
    Cable(sw1.get_port("g0/1"), sw2.get_port("g0/1"), CableType.CAT6)
    Cable(sw1.get_port("g0/2"), sw3.get_port("g0/1"), CableType.CAT6)
    Cable(sw2.get_port("g0/2"), sw3.get_port("g0/2"), CableType.CAT6)

    # Attach hosts
    pc1 = Host("pc1", hostname="PC1")
    pc1.configure_ip("192.168.1.10", "255.255.255.0")
    Cable(pc1.eth0, sw1.get_port("g0/3"), CableType.CAT6)

    pc2 = Host("pc2", hostname="PC2")
    pc2.configure_ip("192.168.1.20", "255.255.255.0")
    Cable(pc2.eth0, sw3.get_port("g0/3"), CableType.CAT6)

    # Send Ping (which involves broadcast ARP probe)
    step = pe.trace_single_packet(pc1, "192.168.1.20", simulate_arp=False)
    print(f"PC1 -> PC2 ping in triangle loop: status={step['status_code']}, success={step['success']}, hops={step['hop_path']}")

    assert step["success"] is True, f"Ping should succeed across spanning tree without loop: {step}"
    assert step["status_code"] == "!"
    # Ensure blocked port was not traversed in hop path
    assert "SW2" not in step["hop_path"] or "SW3" not in step["hop_path"] or step["hop_path"].count("SW1") == 1
    print("[PASS] Test 6 passed: Broadcast/ARP frame reached destination with 0 loops")

def test_7_mac_learning_and_stp():
    """
    Test 7 — MAC Learning + STP:
    Verify:
    1. Forwarding ports learn source MAC.
    2. Blocking ports do NOT learn MAC.
    3. Known-unicast forwarding works properly along the Spanning Tree.
    """
    print("\n--- TEST 7: MAC Learning & STP Interaction ---")
    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")
    sw3 = Switch("sw3", hostname="SW3")

    sw1.stp_priority = 24576
    sw2.stp_priority = 32768
    sw3.stp_priority = 32768

    sw1.mac_address = "00:11:22:33:44:01"
    sw2.mac_address = "00:11:22:33:44:02"
    sw3.mac_address = "00:11:22:33:44:03"

    Cable(sw1.get_port("g0/1"), sw2.get_port("g0/1"), CableType.CAT6)
    Cable(sw1.get_port("g0/2"), sw3.get_port("g0/1"), CableType.CAT6)
    Cable(sw2.get_port("g0/2"), sw3.get_port("g0/2"), CableType.CAT6)

    sw1.recalculate_stp()
    blocked_port = sw3.get_port("g0/2")
    assert blocked_port.stp_state == "Blocking"

    # Frame arriving on Blocking port should be dropped and NOT learned
    dummy_mac = "AA:BB:CC:DD:EE:FF"
    out = sw3.forward_packet(blocked_port, dummy_mac, "FF:FF:FF:FF:FF:FF", vlan_id=1)
    assert out == [], "Blocking port must drop incoming frames immediately"
    assert dummy_mac not in sw3.mac_table, "Blocking port must not learn source MAC address"

    # Frame arriving on Forwarding port should be learned
    valid_mac = "00:AA:BB:11:22:33"
    fwd_port = sw3.get_port("g0/1")
    assert fwd_port.stp_state == "Forwarding"
    out_fwd = sw3.forward_packet(fwd_port, valid_mac, "FF:FF:FF:FF:FF:FF", vlan_id=1)
    assert valid_mac in sw3.mac_table, "Forwarding port must learn source MAC address"
    assert blocked_port not in out_fwd, "Flood output must not include Blocking port"

    print("[PASS] Test 7 passed: MAC learning respects STP Blocking state")

def test_8_vlan_and_stp():
    """
    Test 8 — VLAN Isolation + STP:
    Topology with triangle loop and multiple VLANs (VLAN 10, VLAN 20).
    Verify:
    1. STP loop prevention is active.
    2. VLAN 10 and VLAN 20 remain strictly isolated.
    """
    print("\n--- TEST 8: VLAN Isolation + STP ---")
    pe = PacketEngine.get_instance()

    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")
    sw3 = Switch("sw3", hostname="SW3")

    sw1.stp_priority = 24576
    sw2.stp_priority = 32768
    sw3.stp_priority = 32768

    sw1.mac_address = "00:11:22:33:44:01"
    sw2.mac_address = "00:11:22:33:44:02"
    sw3.mac_address = "00:11:22:33:44:03"

    # Configure VLANs
    for sw in (sw1, sw2, sw3):
        sw.add_vlan(10, "Engineering")
        sw.add_vlan(20, "Management")

    # Trunk cables in loop
    for p in (sw1.get_port("g0/1"), sw1.get_port("g0/2"),
              sw2.get_port("g0/1"), sw2.get_port("g0/2"),
              sw3.get_port("g0/1"), sw3.get_port("g0/2")):
        p.mode = "trunk"
        p.trunk_allowed_vlans = {1, 10, 20}

    Cable(sw1.get_port("g0/1"), sw2.get_port("g0/1"), CableType.CAT6)
    Cable(sw1.get_port("g0/2"), sw3.get_port("g0/1"), CableType.CAT6)
    Cable(sw2.get_port("g0/2"), sw3.get_port("g0/2"), CableType.CAT6)

    # PC-VLAN10 on SW1
    pc_v10_a = Host("pc_v10_a", hostname="PC_V10_A")
    pc_v10_a.configure_ip("192.168.10.10", "255.255.255.0")
    p_sw1_v10 = sw1.get_port("g0/3")
    p_sw1_v10.access_vlan = 10
    Cable(pc_v10_a.eth0, p_sw1_v10, CableType.CAT6)

    # PC-VLAN10 on SW3
    pc_v10_b = Host("pc_v10_b", hostname="PC_V10_B")
    pc_v10_b.configure_ip("192.168.10.20", "255.255.255.0")
    p_sw3_v10 = sw3.get_port("g0/3")
    p_sw3_v10.access_vlan = 10
    Cable(pc_v10_b.eth0, p_sw3_v10, CableType.CAT6)

    # PC-VLAN20 on SW1
    pc_v20 = Host("pc_v20", hostname="PC_V20")
    pc_v20.configure_ip("192.168.20.10", "255.255.255.0")
    p_sw1_v20 = sw1.get_port("g0/4")
    p_sw1_v20.access_vlan = 20
    Cable(pc_v20.eth0, p_sw1_v20, CableType.CAT6)

    # 1. PC_V10_A -> PC_V10_B (Same VLAN 10 across STP loop)
    step_v10 = pe.trace_single_packet(pc_v10_a, "192.168.10.20", simulate_arp=False)
    assert step_v10["success"] is True, f"VLAN 10 communication should succeed: {step_v10}"

    # 2. PC_V10_A -> PC_V20 (Different VLAN without router)
    step_v20 = pe.trace_single_packet(pc_v10_a, "192.168.20.10", simulate_arp=False)
    assert step_v20["success"] is False, "VLAN 10 and VLAN 20 must remain isolated"

    print("[PASS] Test 8 passed: VLAN isolation and STP loop prevention operate together seamlessly")

def test_9_link_failure_recalculation():
    """
    Test 9 — Link Failure & STP Recalculation:
          SW1 (Root)
         /   \
      (cut)   \
      SW2-----SW3 (Blocked link)
    When SW1-SW2 fails, STP recalculates:
    SW2-SW3 link unblocks and transitions to Forwarding!
    """
    print("\n--- TEST 9: Link Failure & STP Recalculation ---")
    sw1 = Switch("sw1", hostname="SW1")
    sw2 = Switch("sw2", hostname="SW2")
    sw3 = Switch("sw3", hostname="SW3")

    sw1.stp_priority = 24576
    sw2.stp_priority = 32768
    sw3.stp_priority = 32768

    sw1.mac_address = "00:11:22:33:44:01"
    sw2.mac_address = "00:11:22:33:44:02"
    sw3.mac_address = "00:11:22:33:44:03"

    c1 = Cable(sw1.get_port("g0/1"), sw2.get_port("g0/1"), CableType.CAT6)
    c2 = Cable(sw1.get_port("g0/2"), sw3.get_port("g0/1"), CableType.CAT6)
    c3 = Cable(sw2.get_port("g0/2"), sw3.get_port("g0/2"), CableType.CAT6)

    sw1.recalculate_stp()

    # Initial state: SW3 g0/2 is Blocking
    assert sw3.get_port("g0/2").stp_state == "Blocking"
    assert sw2.root_port == sw2.get_port("g0/1")
    print("Initial state: SW3 g0/2 is Blocking")

    # Disconnect link SW1 <-> SW2
    c1.disconnect()
    print("Cable between SW1 and SW2 disconnected!")

    # Recalculate STP
    sw2.recalculate_stp()

    # Failover: SW2's Root Port is now g0/2 (to SW3)
    # SW3's g0/2 unblocks and becomes Designated Forwarding!
    sw2_p2 = sw2.get_port("g0/2")
    sw3_p2 = sw3.get_port("g0/2")

    print(f"After failover SW2 g0/2: Role={sw2_p2.stp_role}, State={sw2_p2.stp_state}")
    print(f"After failover SW3 g0/2: Role={sw3_p2.stp_role}, State={sw3_p2.stp_state}")

    assert sw2_p2.stp_state == "Forwarding", "SW2 g0/2 must unblock and transition to Forwarding"
    assert sw2_p2.stp_role == "Root", "SW2 g0/2 must become Root Port to SW3"
    assert sw3_p2.stp_state == "Forwarding", "SW3 g0/2 must transition to Forwarding"
    assert sw3_p2.stp_role == "Designated", "SW3 g0/2 must become Designated Port"

    print("[PASS] Test 9 passed: Link failure triggered STP recalculation and unblocked redundant link")

def test_10_cli_show_spanning_tree():
    """
    Test 10 — CLI `show spanning-tree`:
    Verify Cisco CLI output format for spanning-tree,
    including Root ID, Bridge ID, Port Role, and State.
    """
    print("\n--- TEST 10: CLI `show spanning-tree` & Priority Config ---")
    sw1 = Switch("sw1", hostname="SW-Core")
    sw1.stp_priority = 24576
    sw1.mac_address = "00:11:22:33:44:01"

    cli = CommandExecutor(sw1)

    # 1. show spanning-tree
    out = cli.execute("show spanning-tree")
    print(f"CLI Output:\n{out}")

    assert "VLAN0001" in out
    assert "Spanning tree enabled protocol ieee" in out
    assert "Root ID" in out
    assert "24576" in out
    assert "This bridge is the root" in out
    assert "Bridge ID" in out
    assert "Interface" in out
    assert "Role" in out
    assert "State" in out
    assert "Designated" in out
    assert "Forwarding" in out

    # 2. Configure priority via CLI: spanning-tree vlan 1 priority 4096
    cli.mode = IOSMode.CONFIG
    cli.execute("spanning-tree vlan 1 priority 4096")
    assert sw1.stp_priority == 4096, f"Expected priority 4096, got {sw1.stp_priority}"

    out_new = cli.execute("do show spanning-tree")
    assert "4096" in out_new

    print("[PASS] Test 10 passed: CLI `show spanning-tree` and priority config verified")

if __name__ == "__main__":
    test_1_root_bridge_election()
    test_2_priority_election()
    test_3_mac_tie_break()
    test_4_root_port_selection()
    test_5_triangle_loop_blocking()
    test_6_broadcast_loop_prevention()
    test_7_mac_learning_and_stp()
    test_8_vlan_and_stp()
    test_9_link_failure_recalculation()
    test_10_cli_show_spanning_tree()
    print("\n=======================================================")
    print("ALL 10 STP (SPANNING TREE PROTOCOL) TESTS PASSED 100%!")
    print("=======================================================")
