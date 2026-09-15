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

    # 1. User Mode Help (Router)
    out_user_qm = exec_rtr.execute("?")
    print("USER MODE '?' OUTPUT:\n", out_user_qm)
    assert "enable" in out_user_qm
    assert "Available Cisco IOS commands" in out_user_qm
    # Router must NOT have switch or firewall commands
    assert "switchport" not in out_user_qm
    assert "nameif" not in out_user_qm
    assert "spanning-tree" not in out_user_qm

    out_user_help = exec_rtr.execute("help")
    assert "enable" in out_user_help

    # 2. Privileged Mode Help (Router)
    exec_rtr.execute("enable")
    out_priv_qm = exec_rtr.execute("?")
    print("\nPRIVILEGED MODE '?' OUTPUT:\n", out_priv_qm)
    assert "configure terminal" in out_priv_qm
    assert "write memory" in out_priv_qm
    assert "show ip ospf" in out_priv_qm
    assert "show ip rip" in out_priv_qm
    # Must NOT have switch/firewall commands
    assert "mac address-table" not in out_priv_qm
    assert "vlan brief" not in out_priv_qm
    assert "conn" not in out_priv_qm

    # 3. Show commands help on Router: 'show ?' and 'sh ?'
    out_show_qm = exec_rtr.execute("show ?")
    print("\nROUTER SHOW 'show ?' OUTPUT:\n", out_show_qm)
    assert "ip interface brief" in out_show_qm
    assert "running-config" in out_show_qm
    assert "ip ospf" in out_show_qm
    assert "ip rip" in out_show_qm
    # Must NOT have switch or firewall show commands
    assert "vlan brief" not in out_show_qm
    assert "mac address-table" not in out_show_qm
    assert "interfaces trunk" not in out_show_qm
    assert "spanning-tree" not in out_show_qm
    assert "nameif" not in out_show_qm
    assert "conn" not in out_show_qm
    assert "xlate" not in out_show_qm

    out_sh_qm = exec_rtr.execute("sh ?")
    assert "ip interface brief" in out_sh_qm

    # 4. Interface selection help: 'int ?'
    out_int_qm = exec_rtr.execute("int ?")
    print("\nINT 'int ?' OUTPUT:\n", out_int_qm)
    assert "g0/0" in out_int_qm

    # 5. Config Mode Help (Router)
    exec_rtr.execute("conf t")
    out_conf_qm = exec_rtr.execute("?")
    print("\nCONFIG MODE '?' OUTPUT:\n", out_conf_qm)
    assert "interface" in out_conf_qm
    assert "ip route" in out_conf_qm
    assert "router ospf" in out_conf_qm
    assert "router rip" in out_conf_qm
    # Router config must NOT have switch/firewall commands
    assert "vlan" not in out_conf_qm
    assert "spanning-tree" not in out_conf_qm
    assert "nameif" not in out_conf_qm

    # 6. Interface Config Mode Help (Router)
    exec_rtr.execute("int g0/0")
    out_if_qm = exec_rtr.execute("?")
    print("\nINTERFACE CONFIG MODE '?' OUTPUT:\n", out_if_qm)
    assert "ip address" in out_if_qm
    assert "no shutdown" in out_if_qm
    assert "ip ospf cost" in out_if_qm
    # Router interface must NOT have switchport commands
    assert "switchport" not in out_if_qm

    # 7. Switch Help & Show commands (Strict Separation)
    switch = Switch("sw1", hostname="Switch1")
    exec_sw = CommandExecutor(switch)
    exec_sw.execute("enable")

    out_sw_show = exec_sw.execute("show ?")
    print("\nSWITCH SHOW 'show ?' OUTPUT:\n", out_sw_show)
    assert "vlan brief" in out_sw_show
    assert "mac address-table" in out_sw_show
    assert "interfaces trunk" in out_sw_show
    assert "interfaces switchport" in out_sw_show
    assert "spanning-tree" in out_sw_show
    # Switch must NOT show router or firewall commands
    assert "ip ospf" not in out_sw_show
    assert "ip rip" not in out_sw_show
    assert "ip nat" not in out_sw_show
    assert "nameif" not in out_sw_show
    assert "xlate" not in out_sw_show

    exec_sw.execute("conf t")
    out_sw_conf = exec_sw.execute("?")
    print("\nSWITCH CONFIG '?' OUTPUT:\n", out_sw_conf)
    assert "vlan <id>" in out_sw_conf
    assert "spanning-tree" in out_sw_conf
    # Switch config must NOT show router dynamic protocols or NAT
    assert "router ospf" not in out_sw_conf
    assert "router rip" not in out_sw_conf
    assert "ip nat" not in out_sw_conf

    exec_sw.execute("int g0/1")
    out_sw_if = exec_sw.execute("?")
    print("\nSWITCHPORT CONFIG-IF '?' OUTPUT:\n", out_sw_if)
    assert "switchport mode access" in out_sw_if
    assert "switchport mode trunk" in out_sw_if
    assert "switchport trunk native vlan" in out_sw_if
    assert "switchport trunk allowed vlan" in out_sw_if
    # Switchport must NOT have router IP commands
    assert "ip ospf" not in out_sw_if
    assert "ip nat" not in out_sw_if

    # 8. Firewall Help & Show commands (Strict Separation)
    from network.firewall import Firewall
    fw = Firewall("fw1", hostname="Firewall1")
    exec_fw = CommandExecutor(fw)
    exec_fw.execute("enable")

    out_fw_show = exec_fw.execute("show ?")
    print("\nFIREWALL SHOW 'show ?' OUTPUT:\n", out_fw_show)
    assert "nameif" in out_fw_show
    assert "conn" in out_fw_show
    assert "xlate" in out_fw_show
    # Firewall must NOT show switch or router dynamic protocols
    assert "vlan brief" not in out_fw_show
    assert "spanning-tree" not in out_fw_show
    assert "mac address-table" not in out_fw_show
    assert "ip ospf" not in out_fw_show

    exec_fw.execute("conf t")
    exec_fw.execute("int g0/0")
    out_fw_if = exec_fw.execute("?")
    print("\nFIREWALL CONFIG-IF '?' OUTPUT:\n", out_fw_if)
    assert "nameif" in out_fw_if
    assert "security-level" in out_fw_if
    assert "switchport" not in out_fw_if

    # 9. Host Linux Terminal Help
    server = Host("srv1", hostname="Web-Server")
    exec_host = CommandExecutor(server)
    out_host_qm = exec_host.execute("?")
    print("\nHOST '?' OUTPUT:\n", out_host_qm)
    assert "ifconfig" in out_host_qm
    assert "ping" in out_host_qm
    assert "dhclient" in out_host_qm
    assert "curl" in out_host_qm
    # Host must NOT have Cisco IOS commands
    assert "enable" not in out_host_qm
    assert "switchport" not in out_host_qm
    assert "router ospf" not in out_host_qm
    assert "configure terminal" not in out_host_qm

    out_host_help = exec_host.execute("help")
    assert "ifconfig" in out_host_help

    # 10. Auto-completion isolation
    from cli.command_parser import CommandParser
    rtr_parser = CommandParser(exec_rtr)
    sw_parser = CommandParser(exec_sw)

    # In CONFIG_IF:
    # Switch should autocomplete switchport commands
    sw_completions = sw_parser.get_completions("switchport")
    assert len(sw_completions) > 0
    # Router should NOT autocomplete switchport commands
    rtr_completions = rtr_parser.get_completions("switchport")
    assert len(rtr_completions) == 0

    print("\nALL STRICT DEVICE SEPARATION CLI '?' AND 'HELP' TESTS PASSED 100%!")

if __name__ == "__main__":
    test_cli_help()
