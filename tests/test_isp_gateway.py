"""
tests/test_isp_gateway.py - Automated Verification Suite for 3D ISP Gateway Model
Tests device creation, 1U rack dimensions, port local coordinates, sandbox topology,
pre-wired router link, and rendering dispatch.
"""

import os
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pygame
pygame.init()

from network.host import Host
from network.router import Router
from network.cable import Cable, CableType
from modes.sandbox_mode import SandboxMode
from engine.renderer3d import Renderer3D
from engine.camera import FPSCamera

def test_isp_gateway_model_and_geometry():
    print("[TEST] ISP Gateway Model & Port Coordinates...")
    isp = Host("isp1", hostname="ISP-Gateway-Uplink", device_type="isp_gateway", rack_id=2, u_slot=40)
    
    assert isp.device_type == "isp_gateway"
    assert isp.hostname == "ISP-Gateway-Uplink"
    # Verify 1U rack dimensions
    assert abs(isp.height - 0.044) < 1e-4, f"ISP Gateway height should be 1U (0.044m), got {isp.height}"
    assert abs(isp.width - 0.48) < 1e-4, f"ISP Gateway width should be 0.48m, got {isp.width}"
    assert abs(isp.depth - 0.38) < 1e-4, f"ISP Gateway depth should be 0.38m, got {isp.depth}"

    # Verify eth0 RJ45 handoff port
    assert "eth0" in isp.ports
    assert isp.eth0.port_type == "RJ45"

    px, py, pz = isp.get_port_local_pos("eth0")
    # Customer handoff port should be at x = 0.04m, y = 0.0m, front_z
    assert abs(px - 0.04) < 1e-4, f"eth0 x-coord expected 0.04, got {px}"
    assert abs(py - 0.0) < 1e-4, f"eth0 y-coord expected 0.0, got {py}"
    expected_front_z = (isp.depth / 2.0) + 0.007
    assert abs(pz - expected_front_z) < 1e-4, f"eth0 z-coord expected {expected_front_z}, got {pz}"
    print("  -> ISP Gateway dimensions & port geometry verified!")

def test_sandbox_isp_gateway_integration():
    print("[TEST] Sandbox Mode ISP Gateway Integration & Pre-wiring...")
    sandbox = SandboxMode()
    sandbox.setup()

    # Find isp1
    isp_list = [d for d in sandbox.devices if d.id == "isp1"]
    assert len(isp_list) == 1, "isp1 device must exist in SandboxMode"
    isp = isp_list[0]

    assert isp.device_type == "isp_gateway"
    assert isp.rack_id == 2
    assert isp.u_slot == 40
    assert isp.eth0.ip_address == "203.0.113.1"

    # Find cable connecting rtr1 g0/0 to isp1 eth0
    isp_cables = [c for c in sandbox.cables if (c.port_a == isp.eth0 or c.port_b == isp.eth0)]
    assert len(isp_cables) == 1, "There should be 1 cable connected to ISP Gateway eth0"
    c_isp = isp_cables[0]
    peer = c_isp.get_peer_port(isp.eth0)
    assert peer is not None
    assert peer.device.id == "rtr1"
    assert peer.name == "g0/0"
    print("  -> Sandbox ISP Gateway device & Core-Router connection verified!")

def test_rendering_dispatch():
    print("[TEST] Renderer3D ISP Gateway Rendering Dispatch...")
    from engine.game import GameManager
    game = GameManager()
    game.start_mode("SANDBOX")

    isp = [d for d in game.mode.devices if d.id == "isp1"][0]
    assert isp.device_type == "isp_gateway"

    # Render frames with ISP gateway in focus
    for _ in range(5):
        game._update(0.016)
        game._render()
        game.window.swap_buffers()
    print("  -> Renderer3D successfully rendered ISP Gateway without errors!")

if __name__ == "__main__":
    test_isp_gateway_model_and_geometry()
    test_sandbox_isp_gateway_integration()
    test_rendering_dispatch()
    print("\n[SUCCESS] All ISP Gateway tests passed 100%!")
