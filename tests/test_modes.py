"""
tests/test_modes.py - Automated tests for Game Modes, Device Management & Serialization
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modes.tutorial_mode import TutorialMode
from modes.challenge_mode import ChallengeMode
from modes.sandbox_mode import SandboxMode
from network.cable import Cable, CableType
from network.switch import Switch
from network.router import Router
from network.host import Host

def test_modes():
    # 1. Test Tutorial Mode
    tut = TutorialMode()
    assert tut.step in (0, 1)
    assert len(tut.devices) >= 3
    print("Tutorial Mode initialized with", len(tut.devices), "devices.")

    # 2. Test Challenge Mode
    chal = ChallengeMode()
    assert chal.scenario_index == 0
    assert chal.get_title().startswith("INC-101")
    print("Challenge Mode initialized scenario:", chal.get_title())

    has_next = chal.next_scenario()
    assert has_next
    assert chal.scenario_index == 1
    print("Next scenario successfully loaded:", chal.get_title())

    # 3. Test Sandbox Mode Add / Remove Devices & Collision Checks
    sandbox = SandboxMode()
    initial_device_count = len(sandbox.devices)
    initial_cable_count = len(sandbox.cables)
    print("Sandbox Mode initialized with", initial_device_count, "devices.")

    # A. Add a new Switch to Rack 2, Slot 10
    ok, msg, new_sw = sandbox.add_device("switch", rack_id=2, u_slot=10, hostname="Agg-SW-02")
    assert ok, f"Failed to add switch: {msg}"
    assert new_sw is not None
    assert new_sw in sandbox.devices
    assert new_sw.hostname == "Agg-SW-02"
    assert new_sw.rack_id == 2
    assert new_sw.u_slot == 10
    assert new_sw.pos_x == 0.0  # Rack 2 X is 0.0
    print("Successfully added Switch to Rack 2 (Slot 10U).")

    # B. Test Collision Detection: Trying to install on an occupied slot must fail
    ok_col, msg_col, _ = sandbox.add_device("router", rack_id=2, u_slot=10, hostname="Colliding-RTR")
    assert not ok_col, "Collision check failed! Should not allow installing on occupied slot."
    print("Collision check correctly prevented double installation:", msg_col)

    # C. Add a Server to Rack 2, Slot 35 (2U: uses 35 and 36)
    ok, msg, new_srv = sandbox.add_device("server", rack_id=2, u_slot=35, hostname="Backup-Vault")
    assert ok, f"Failed to add server: {msg}"
    assert new_srv.pos_x == 0.0

    # Overlap test: slot 36 should be blocked because server at 35 uses 35U and 36U (2U)
    ok_over, msg_over, _ = sandbox.add_device("switch", rack_id=2, u_slot=36)
    assert not ok_over, "2U overlap check failed! Slot 36 should be blocked by 2U server at 35."
    print("2U Span collision check correctly detected overlap on slot 36:", msg_over)

    # D. Connect cable between newly installed Switch and Server
    test_cable = Cable(new_sw.ports["g0/1"], new_srv.ports["eth0"], CableType.CAT6)
    sandbox.cables.append(test_cable)
    assert test_cable in sandbox.cables
    assert new_sw.ports["g0/1"].cable == test_cable
    assert new_srv.ports["eth0"].cable == test_cable
    print("Connected cable between new switch and new server.")

    # E. Remove Server: Verify automatic cable unhooking & removal
    cables_before_remove = len(sandbox.cables)
    ok_rem, msg_rem = sandbox.remove_device(new_srv)
    assert ok_rem, f"Failed to remove device: {msg_rem}"
    assert new_srv not in sandbox.devices
    assert test_cable not in sandbox.cables
    assert new_sw.ports["g0/1"].cable is None
    assert len(sandbox.cables) == cables_before_remove - 1
    print("Successfully removed server. Connected cable automatically unplugged and removed.")

    # F. Test Save / Load with dynamically added devices
    sandbox.save_file = "test_sandbox_save.json"
    sandbox.save_topology()
    assert os.path.exists("test_sandbox_save.json")
    print("Saved sandbox topology file created successfully.")

    # Load into a clean instance
    sandbox2 = SandboxMode()
    sandbox2.save_file = "test_sandbox_save.json"
    sandbox2.load_topology()
    # Check that new_sw (Agg-SW-02) was dynamically recreated in sandbox2
    reloaded_sw = next((d for d in sandbox2.devices if d.hostname == "Agg-SW-02"), None)
    assert reloaded_sw is not None, "Reload failed to recreate dynamically added device Agg-SW-02!"
    assert reloaded_sw.rack_id == 2
    assert reloaded_sw.u_slot == 10
    print("Loaded sandbox topology successfully with dynamic devices verified.")

    if os.path.exists("test_sandbox_save.json"):
        os.remove("test_sandbox_save.json")

    print("\nALL GAME MODES & DEVICE MANAGEMENT TESTS PASSED!")

if __name__ == "__main__":
    test_modes()
