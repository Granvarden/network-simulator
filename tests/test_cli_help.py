"""
tests/test_cli_help.py - Automated tests for '?' and 'help' commands across all modes
"""

import os
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from network.router import Router
from network.switch import Switch
from network.host import Host
from cli.command_executor import CommandExecutor

def test_cli_help():
    router = Router("r1", hostname="Router1")
    exec_rtr = CommandExecutor(router)

    # 1. User Mode Help
    out_user_qm = exec_rtr.execute("?")
    print("USER MODE '?' OUTPUT:\n", out_user_qm)
    assert "enable" in out_user_qm
    assert "Available Cisco IOS commands" in out_user_qm

    out_user_help = exec_rtr.execute("help")
    assert "enable" in out_user_help

    # 2. Privileged Mode Help
    exec_rtr.execute("enable")
    out_priv_qm = exec_rtr.execute("?")
    print("\nPRIVILEGED MODE '?' OUTPUT:\n", out_priv_qm)
    assert "configure terminal" in out_priv_qm
    assert "write memory" in out_priv_qm

    # 3. Show commands help: 'show ?' and 'sh ?'
    out_show_qm = exec_rtr.execute("show ?")
    print("\nSHOW 'show ?' OUTPUT:\n", out_show_qm)
    assert "ip interface brief" in out_show_qm
    assert "running-config" in out_show_qm

    out_sh_qm = exec_rtr.execute("sh ?")
    assert "ip interface brief" in out_sh_qm

    # 4. Interface selection help: 'int ?'
    out_int_qm = exec_rtr.execute("int ?")
    print("\nINT 'int ?' OUTPUT:\n", out_int_qm)
    assert "g0/0" in out_int_qm

    # 5. Config Mode Help
    exec_rtr.execute("conf t")
    out_conf_qm = exec_rtr.execute("?")
    print("\nCONFIG MODE '?' OUTPUT:\n", out_conf_qm)
    assert "interface" in out_conf_qm
    assert "ip route" in out_conf_qm

    # 6. Interface Config Mode Help
    exec_rtr.execute("int g0/0")
    out_if_qm = exec_rtr.execute("?")
    print("\nINTERFACE CONFIG MODE '?' OUTPUT:\n", out_if_qm)
    assert "ip address" in out_if_qm
    assert "no shutdown" in out_if_qm

    # 7. Host Linux Terminal Help
    server = Host("srv1", hostname="Web-Server")
    exec_host = CommandExecutor(server)
    out_host_qm = exec_host.execute("?")
    print("\nHOST '?' OUTPUT:\n", out_host_qm)
    assert "ifconfig" in out_host_qm
    assert "ping" in out_host_qm

    out_host_help = exec_host.execute("help")
    assert "ifconfig" in out_host_help

    print("\nALL CLI '?' AND 'HELP' TESTS PASSED 100%!")

if __name__ == "__main__":
    test_cli_help()
