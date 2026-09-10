"""
cli/command_parser.py - Autocompletion and Context-Sensitive Help ('?' / TAB)
Provides Cisco IOS style command discovery and auto-completion.
"""

from .command_executor import IOSMode
from network.router import Router

COMMAND_HELP = {
    IOSMode.USER: [
        ("enable", "Turn on privileged commands (enters Switch# / Router# / ASA#)"),
        ("ping <ip>", "Send ICMP Echo packets to verify host reachability"),
        ("traceroute <ip>", "Trace hop-by-hop packet path to destination"),
        ("show ip interface brief", "Display summary of all interface IP addresses and status"),
        ("show ip route", "Display current IP routing table"),
        ("show ip arp", "Display IP to MAC address resolution table"),
        ("show ip nat translations", "Display active NAT/PAT address mappings (Router)"),
        ("show access-list", "Display configured Access Control Lists"),
        ("show nameif", "Display interface names and security levels (Firewall)"),
        ("show conn", "Display active connection state table (Firewall)"),
        ("show vlan brief", "Display VLAN status and port assignments (Switches)"),
        ("show version", "Display system hardware and IOS software version"),
        ("help / ?", "Display list of available commands in current mode"),
        ("exit", "Exit the current EXEC session"),
    ],
    IOSMode.PRIVILEGED: [
        ("configure terminal", "Enter global configuration mode (enters config#)"),
        ("disable", "Turn off privileged commands (return to user mode)"),
        ("show running-config", "Display current operating configuration"),
        ("show ip interface brief", "Display summary of all interface IP and states"),
        ("show ip route", "Display current IP routing table (Routers/Firewall)"),
        ("show ip arp", "Display IP to MAC address resolution table (ARP cache)"),
        ("show ip nat translations", "Display active NAT/PAT address mappings (Router)"),
        ("show ip nat statistics", "Display NAT engine translation statistics (Router)"),
        ("show access-list", "Display configured Access Control Lists (ACL)"),
        ("show nameif", "Display interface names and security levels (Firewall)"),
        ("show conn", "Display active stateful connection table (Firewall)"),
        ("show vlan brief", "Display VLAN status and port assignments (Switches)"),
        ("show mac address-table", "Display Layer 2 MAC address learning table"),
        ("clear ip arp", "Flush dynamic ARP address cache"),
        ("clear ip nat translation *", "Clear all dynamic NAT translations"),
        ("clear conn", "Clear active stateful connection table (Firewall)"),
        ("ping <ip>", "Send ICMP Echo packets [repeat N] [size N] [source INT]"),
        ("traceroute <ip>", "Trace hop-by-hop packet path to destination"),
        ("write memory", "Save running configuration to startup memory"),
        ("reload", "Halt and perform a cold restart"),
        ("help / ?", "Display list of available commands in current mode"),
        ("exit", "Exit from the EXEC session"),
    ],
    IOSMode.CONFIG: [
        ("hostname <name>", "Set system network device name"),
        ("interface <name>", "Select an interface to configure (e.g. g0/1, g0/0.10)"),
        ("access-list <id> permit <source> [wildcard]", "Define standard IP access list (Router)"),
        ("access-list <name> extended permit <proto> <src> <dst>", "Define extended ACL (Firewall)"),
        ("access-group <name> in interface <zone>", "Apply ACL to interface zone (Firewall)"),
        ("ip nat inside source list <acl> interface <if> overload", "Configure PAT/NAT overload (Router)"),
        ("route <zone> <net> <mask> <gw>", "Establish static route on Firewall ASA"),
        ("ip route <net> <mask4> <gw>", "Establish static route on Router/Firewall"),
        ("vlan <id>", "Enter VLAN configuration mode (Switches)"),
        ("do <command>", "Execute an EXEC command from configuration mode"),
        ("help / ?", "Display configuration commands"),
        ("exit", "Exit from configure mode"),
        ("end", "Exit to privileged EXEC mode"),
    ],
    IOSMode.CONFIG_IF: [
        ("ip address <ip> <subnet>", "Set interface IPv4 address and subnet mask"),
        ("no shutdown", "Administratively bring interface UP"),
        ("shutdown", "Administratively bring interface DOWN"),
        ("ip nat inside", "Designate interface as inside NAT network (Router)"),
        ("ip nat outside", "Designate interface as outside public network (Router)"),
        ("nameif <zone>", "Assign security zone name (e.g. inside, outside, dmz) (Firewall)"),
        ("security-level <0-100>", "Set interface security level (100 inside, 0 outside) (Firewall)"),
        ("switchport mode access", "Set switchport to access mode"),
        ("switchport mode trunk", "Set switchport to 802.1Q trunk mode"),
        ("switchport access vlan <id>", "Assign access port to VLAN number"),
        ("switchport trunk allowed vlan", "Set allowed VLANs on trunk link"),
        ("encapsulation dot1Q <vlan>", "Set 802.1Q VLAN encapsulation tag"),
        ("do <command>", "Execute an EXEC command from interface config mode"),
        ("help / ?", "Display interface configuration commands"),
        ("exit", "Exit from interface configure mode"),
        ("end", "Exit to privileged EXEC mode"),
    ],
    IOSMode.CONFIG_SUBIF: [
        ("encapsulation dot1Q <vlan>", "Set 802.1Q VLAN encapsulation tag (Router-on-a-stick)"),
        ("ip address <ip> <subnet>", "Set subinterface IPv4 address and subnet mask"),
        ("no shutdown", "Bring subinterface UP"),
        ("do <command>", "Execute an EXEC command from subinterface mode"),
        ("help / ?", "Display subinterface commands"),
        ("exit", "Exit from subinterface configure mode"),
        ("end", "Exit to privileged EXEC mode"),
    ],
    IOSMode.CONFIG_VLAN: [
        ("name <name>", "Specify ASCII name for this VLAN"),
        ("help / ?", "Display VLAN commands"),
        ("exit", "Exit from VLAN configure mode"),
        ("end", "Exit to privileged EXEC mode"),
    ]
}

COMMAND_CATALOG = {
    mode: [item[0].split()[0] for item in items]
    for mode, items in COMMAND_HELP.items()
}

class CommandParser:
    def __init__(self, executor):
        self.executor = executor

    def get_completions(self, text):
        """Returns auto-complete suggestions for current text buffer."""
        mode = self.executor.mode
        options = [item[0] for item in COMMAND_HELP.get(mode, [])]
        tokens = text.split()

        # Check interface completions if after 'int' or 'interface'
        if len(tokens) >= 1 and tokens[0].lower() in ("int", "interface"):
            ports = list(self.executor.device.ports.keys())
            if isinstance(self.executor.device, Router):
                ports.extend(list(self.executor.device.subinterfaces.keys()))
            prefix = tokens[1].lower() if len(tokens) > 1 else ""
            matches = [p for p in ports if p.lower().startswith(prefix)]
            return matches

        prefix = text.lower()
        matches = [cmd for cmd in options if cmd.lower().startswith(prefix)]
        return matches

    def get_help(self, text=""):
        """Returns context-sensitive help documentation for current mode."""
        clean = text.strip().lower().rstrip("?").strip()
        mode = self.executor.mode

        if clean in ("show", "sh"):
            return (
                "Show commands:\n"
                "  ip interface brief    Brief summary of interface IP and status\n"
                "  running-config        Current operating configuration\n"
                "  ip route              IP routing table (Routers/Firewall)\n"
                "  ip nat translations   Active NAT/PAT translations (Routers)\n"
                "  ip nat statistics     NAT translation statistics (Routers)\n"
                "  access-list           Access Control Lists (Routers/Firewall)\n"
                "  nameif                Interface security zones (Firewall)\n"
                "  conn                  Stateful active connections (Firewall)\n"
                "  vlan brief            VLAN status and ports (Switches)\n"
                "  mac address-table     MAC forwarding table (Switches)"
            )

        if clean in ("int", "interface"):
            ports = list(self.executor.device.ports.keys())
            if isinstance(self.executor.device, Router):
                ports.extend(list(self.executor.device.subinterfaces.keys()))
            return "Interfaces available on this device:\n  " + "  ".join(ports)

        # Mode-level help table
        items = COMMAND_HELP.get(mode, [])
        lines = [f"Available commands in {mode} mode:"]
        lines.append("-" * 65)
        for cmd, desc in items:
            lines.append(f"  {cmd:<32} {desc}")
        return "\n".join(lines)
