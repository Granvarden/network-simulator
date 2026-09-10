"""
tests/test_cli.py - Automated tests for Cisco IOS CLI Executor
"""

import os
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from network.switch import Switch
from network.router import Router
from cli.command_executor import CommandExecutor, IOSMode

def test_cisco_cli():
    # 1. Test Router CLI
    router = Router("r1", hostname="Edge-Router")
    exec_rtr = CommandExecutor(router)

    assert exec_rtr.get_prompt() == "Edge-Router>"
    exec_rtr.execute("enable")
    assert exec_rtr.get_prompt() == "Edge-Router#"
    exec_rtr.execute("conf t")
    assert exec_rtr.get_prompt() == "Edge-Router(config)#"
    exec_rtr.execute("int g0/0")
    assert exec_rtr.get_prompt() == "Edge-Router(config-if)#"
    exec_rtr.execute("ip address 10.0.0.1 255.255.255.0")
    exec_rtr.execute("no shut")

    p = router.get_port("g0/0")
    assert p.ip_address == "10.0.0.1"
    assert p.subnet_mask == "255.255.255.0"
    assert not p.is_shutdown

    # Test show ip int br
    exec_rtr.execute("exit")
    exec_rtr.execute("exit")
    output = exec_rtr.execute("sh ip int br")
    print("SHOW IP INT BR OUTPUT:")
    print(output)
    assert "g0/0" in output
    assert "10.0.0.1" in output

    # 2. Test Switch CLI (VLANs & Access Ports)
    switch = Switch("sw1", hostname="Core-Switch")
    exec_sw = CommandExecutor(switch)
    exec_sw.execute("en")
    exec_sw.execute("conf t")
    exec_sw.execute("vlan 10")
    exec_sw.execute("name Engineering")
    exec_sw.execute("exit")
    exec_sw.execute("int g0/1")
    exec_sw.execute("switchport mode access")
    exec_sw.execute("switchport access vlan 10")
    exec_sw.execute("end")

    assert switch.ports["g0/1"].access_vlan == 10
    vlan_out = exec_sw.execute("sh vlan brief")
    print("\nSHOW VLAN BRIEF OUTPUT:")
    print(vlan_out)
    assert "Engineering" in vlan_out
    assert "g0/1" in vlan_out

    print("\nALL CISCO CLI TESTS PASSED!")

if __name__ == "__main__":
    test_cisco_cli()
