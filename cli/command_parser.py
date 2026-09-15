"""
cli/command_parser.py - Autocompletion and Context-Sensitive Help ('?' / TAB)
Provides Cisco IOS style command discovery and auto-completion separated strictly by device type.
Supported device types:
- Cisco Router (ISR G2 / 2911)
- Cisco Catalyst Switch (2960-X / L2/L3 SVI)
- Next-Gen Firewall (Cisco ASA / FortiGate)
- Host / Server / Field Laptop (Linux / Windows shell)
"""

from .command_executor import IOSMode
from network.router import Router
from network.switch import Switch, SVI
from network.firewall import Firewall
from network.host import Host

# =====================================================================
# 1. Router Specific Command Help (Cisco IOS Router)
# =====================================================================
ROUTER_COMMAND_HELP = {
    IOSMode.USER: [
        ("enable", "Turn on privileged commands (enters Router#)"),
        ("ping <ip>", "Send ICMP Echo packets to verify host reachability"),
        ("traceroute <ip>", "Trace hop-by-hop packet path to destination"),
        ("show ip interface brief", "Display summary of all interface IP addresses and status"),
        ("show ip route", "Display current IPv4 routing table (Connected, Static, OSPF, RIP)"),
        ("show ip arp", "Display IP to MAC address resolution table (ARP cache)"),
        ("show ip nat translations", "Display active NAT/PAT address mappings"),
        ("show ip nat statistics", "Display NAT engine translation statistics"),
        ("show ip dhcp pool", "Display DHCP address pool configuration and status"),
        ("show ip dhcp binding", "Display active DHCP client address leases"),
        ("show ip dhcp statistics", "Display DHCP server message counters"),
        ("show ip ospf", "Display OSPF process parameters, Router ID, and area info"),
        ("show ip ospf neighbor", "Display OSPF neighbor adjacency table and states"),
        ("show ip ospf database", "Display OSPF Link-State Database (LSDB Router-LSAs)"),
        ("show ip rip", "Display RIP routing database and route metrics"),
        ("show ip protocols", "Display active dynamic routing protocol parameters"),
        ("show access-list", "Display configured Access Control Lists (ACL)"),
        ("show version", "Display Cisco IOS router software and hardware version"),
        ("help / ?", "Display list of available commands in current mode"),
        ("exit", "Exit the current EXEC session"),
    ],
    IOSMode.PRIVILEGED: [
        ("configure terminal", "Enter global configuration mode (enters config#)"),
        ("disable", "Turn off privileged commands (return to user mode)"),
        ("show running-config", "Display current operating configuration"),
        ("show ip interface brief", "Display summary of all interface IP addresses and status"),
        ("show ip route", "Display current IPv4 routing table (Connected, Static, OSPF, RIP)"),
        ("show ip arp", "Display IP to MAC address resolution table (ARP cache)"),
        ("show ip nat translations", "Display active NAT/PAT address mappings"),
        ("show ip nat statistics", "Display NAT engine translation statistics"),
        ("show ip dhcp pool", "Display DHCP address pool configuration and status"),
        ("show ip dhcp binding", "Display active DHCP client address leases"),
        ("show ip dhcp statistics", "Display DHCP server message counters"),
        ("show ip ospf", "Display OSPF process parameters, Router ID, and area info"),
        ("show ip ospf neighbor", "Display OSPF neighbor adjacency table and states"),
        ("show ip ospf database", "Display OSPF Link-State Database (LSDB Router-LSAs)"),
        ("show ip rip", "Display RIP routing database and route metrics"),
        ("show ip protocols", "Display active dynamic routing protocol parameters"),
        ("show access-list", "Display configured Access Control Lists (ACL)"),
        ("show version", "Display Cisco IOS router software and hardware version"),
        ("clear ip arp", "Flush dynamic ARP address cache"),
        ("clear ip nat translation *", "Clear all dynamic NAT translations"),
        ("clear ip ospf process", "Reset OSPF process and reconverge adjacencies"),
        ("clear ip rip", "Reset dynamic RIP routes and trigger updates"),
        ("ping <ip>", "Send ICMP Echo packets [repeat N] [size N] [source INT]"),
        ("traceroute <ip>", "Trace hop-by-hop packet path to destination"),
        ("write memory", "Save running configuration to startup memory"),
        ("reload", "Halt and perform a cold restart"),
        ("help / ?", "Display list of available commands in current mode"),
        ("exit", "Exit from privileged EXEC session"),
    ],
    IOSMode.CONFIG: [
        ("hostname <name>", "Set router hostname"),
        ("interface <name>", "Select interface or subinterface (e.g. g0/0, g0/1, g0/0.10)"),
        ("ip route <net> <mask> <gw>", "Establish static route via next-hop IP or interface"),
        ("no ip route <net> <mask> <gw>", "Remove configured static route"),
        ("router ospf <process-id>", "Enable OSPF routing process and enter router config mode"),
        ("no router ospf <process-id>", "Disable OSPF routing process"),
        ("router rip", "Enable RIP routing process and enter router config mode"),
        ("no router rip", "Disable RIP routing process"),
        ("ip dhcp pool <name>", "Configure DHCP address pool and enter pool config mode"),
        ("no ip dhcp pool <name>", "Delete DHCP address pool"),
        ("ip dhcp excluded-address <low> [high]", "Prevent IP range from being dynamically assigned"),
        ("no ip dhcp excluded-address <low> [high]", "Remove DHCP excluded address range"),
        ("access-list <id> permit/deny <src> [wildcard]", "Define standard IP access list (1-99)"),
        ("no access-list <id>", "Delete access list"),
        ("ip nat inside source list <acl> interface <if> overload", "Configure NAT/PAT overload on WAN port"),
        ("no ip nat inside source list ...", "Remove NAT/PAT overload configuration"),
        ("do <command>", "Execute an EXEC command from configuration mode"),
        ("help / ?", "Display configuration commands"),
        ("exit", "Exit from configure mode"),
        ("end", "Exit to privileged EXEC mode"),
    ],
    IOSMode.CONFIG_IF: [
        ("ip address <ip> <subnet>", "Set interface IPv4 address and subnet mask"),
        ("ip address dhcp", "Acquire IP address dynamically via DHCP"),
        ("no ip address", "Remove interface IP address"),
        ("no shutdown", "Administratively bring interface UP"),
        ("shutdown", "Administratively bring interface DOWN"),
        ("description <text>", "Set interface description label"),
        ("no description", "Remove interface description label"),
        ("ip nat inside", "Designate interface as internal private LAN network"),
        ("no ip nat inside", "Remove inside NAT designation"),
        ("ip nat outside", "Designate interface as external public WAN network"),
        ("no ip nat outside", "Remove outside NAT designation"),
        ("ip ospf cost <val>", "Set OSPF interface link cost metric (1-65535)"),
        ("no ip ospf cost", "Reset OSPF interface cost to default (1)"),
        ("ip access-group <id> in/out", "Apply ACL filter to interface inbound/outbound"),
        ("no ip access-group <id> in/out", "Remove ACL filter from interface"),
        ("do <command>", "Execute an EXEC command from interface config mode"),
        ("help / ?", "Display interface configuration commands"),
        ("exit", "Exit from interface configure mode"),
        ("end", "Exit to privileged EXEC mode"),
    ],
    IOSMode.CONFIG_SUBIF: [
        ("encapsulation dot1Q <vlan>", "Set IEEE 802.1Q VLAN encapsulation tag (Router-on-a-stick)"),
        ("no encapsulation dot1Q", "Remove 802.1Q encapsulation from subinterface"),
        ("ip address <ip> <subnet>", "Set subinterface IPv4 address and subnet mask"),
        ("no ip address", "Remove subinterface IP address"),
        ("no shutdown", "Bring subinterface UP"),
        ("shutdown", "Bring subinterface DOWN"),
        ("description <text>", "Set subinterface description label"),
        ("no description", "Remove subinterface description label"),
        ("ip nat inside", "Designate subinterface as inside NAT network"),
        ("ip nat outside", "Designate subinterface as outside NAT network"),
        ("ip ospf cost <val>", "Set OSPF subinterface link cost (1-65535)"),
        ("no ip ospf cost", "Reset OSPF subinterface cost to default (1)"),
        ("do <command>", "Execute an EXEC command from subinterface mode"),
        ("help / ?", "Display subinterface commands"),
        ("exit", "Exit from subinterface configure mode"),
        ("end", "Exit to privileged EXEC mode"),
    ],
    IOSMode.CONFIG_ROUTER: [
        ("network <net> <wildcard> area 0", "Define OSPF network statement with wildcard mask (OSPF)"),
        ("no network <net> <wildcard> area 0", "Remove OSPF network statement (OSPF)"),
        ("router-id <ip>", "Configure explicit OSPF Router ID (OSPF)"),
        ("no router-id", "Remove explicit OSPF Router ID (OSPF)"),
        ("network <net>", "Define RIP network statement by classful/subnet IP (RIP)"),
        ("no network <net>", "Remove RIP network statement (RIP)"),
        ("version 2", "Specify RIP version 2 (RIP)"),
        ("do <command>", "Execute an EXEC command from router configuration mode"),
        ("help / ?", "Display router protocol commands"),
        ("exit", "Exit from router configure mode"),
        ("end", "Exit to privileged EXEC mode"),
    ],
    IOSMode.CONFIG_DHCP_POOL: [
        ("network <net> <mask>", "Subnet network IP and mask for dynamic pool allocation"),
        ("default-router <ip>", "Default gateway IPv4 address handed out to DHCP clients"),
        ("dns-server <ip>", "DNS server IPv4 address distributed to DHCP clients"),
        ("lease <days> [hours] [min]", "DHCP lease duration"),
        ("do <command>", "Execute an EXEC command from DHCP configuration mode"),
        ("help / ?", "Display DHCP pool configuration commands"),
        ("exit", "Exit from DHCP configuration mode"),
        ("end", "Exit to privileged EXEC mode"),
    ]
}

# =====================================================================
# 2. Switch Specific Command Help (Cisco Catalyst Switch)
# =====================================================================
SWITCH_COMMAND_HELP = {
    IOSMode.USER: [
        ("enable", "Turn on privileged commands (enters Switch#)"),
        ("ping <ip>", "Send ICMP Echo packets to verify host reachability"),
        ("traceroute <ip>", "Trace hop-by-hop packet path to destination"),
        ("show ip interface brief", "Display summary of switch interfaces and SVI status"),
        ("show vlan brief", "Display active VLAN database and port memberships"),
        ("show vlan id <id>", "Display detailed info and ports for specific VLAN"),
        ("show mac address-table", "Display Layer 2 MAC address forwarding table"),
        ("show interfaces trunk", "Display 802.1Q trunk ports, native VLANs, and allowed VLANs"),
        ("show interfaces switchport", "Display detailed switchport administrative and operational states"),
        ("show interfaces status", "Display port connection state, speed, duplex, and VLAN"),
        ("show spanning-tree", "Display Spanning Tree topology, root bridge, and port states"),
        ("show version", "Display Cisco Catalyst switch software and hardware version"),
        ("help / ?", "Display list of available commands in current mode"),
        ("exit", "Exit the current EXEC session"),
    ],
    IOSMode.PRIVILEGED: [
        ("configure terminal", "Enter global configuration mode (enters config#)"),
        ("disable", "Turn off privileged commands (return to user mode)"),
        ("show running-config", "Display current operating configuration"),
        ("show ip interface brief", "Display summary of switch interfaces and SVI status"),
        ("show vlan brief", "Display active VLAN database and port memberships"),
        ("show vlan id <id>", "Display detailed info and ports for specific VLAN"),
        ("show mac address-table", "Display Layer 2 MAC address forwarding table"),
        ("show interfaces trunk", "Display 802.1Q trunk ports, native VLANs, and allowed VLANs"),
        ("show interfaces switchport", "Display detailed switchport administrative and operational states"),
        ("show interfaces status", "Display port connection state, speed, duplex, and VLAN"),
        ("show spanning-tree", "Display Spanning Tree topology, root bridge, and port states"),
        ("show version", "Display Cisco Catalyst switch software and hardware version"),
        ("clear mac address-table dynamic", "Clear dynamically learned MAC addresses"),
        ("ping <ip>", "Send ICMP Echo packets [repeat N] [size N] [source INT]"),
        ("traceroute <ip>", "Trace hop-by-hop packet path to destination"),
        ("write memory", "Save running configuration to startup memory"),
        ("reload", "Halt and perform a cold restart"),
        ("help / ?", "Display list of available commands in current mode"),
        ("exit", "Exit from privileged EXEC session"),
    ],
    IOSMode.CONFIG: [
        ("hostname <name>", "Set switch hostname"),
        ("interface <name>", "Select a physical port (e.g. g0/1) or SVI (e.g. vlan 10)"),
        ("vlan <id>", "Enter VLAN configuration mode to create or manage a VLAN"),
        ("no vlan <id>", "Delete VLAN from switch database"),
        ("ip default-gateway <ip>", "Configure default gateway for switch in-band management"),
        ("no ip default-gateway", "Remove switch default gateway"),
        ("spanning-tree vlan <id> priority <val>", "Set STP bridge priority for Root Bridge election"),
        ("do <command>", "Execute an EXEC command from configuration mode"),
        ("help / ?", "Display configuration commands"),
        ("exit", "Exit from configure mode"),
        ("end", "Exit to privileged EXEC mode"),
    ],
    IOSMode.CONFIG_IF: [
        ("switchport mode access", "Configure port to untagged Access mode for end devices"),
        ("switchport mode trunk", "Configure port to IEEE 802.1Q multi-VLAN trunk mode"),
        ("no switchport mode", "Reset switchport mode to default (access)"),
        ("switchport access vlan <id>", "Assign access port to specific VLAN broadcast domain"),
        ("no switchport access vlan", "Reset access port to default VLAN 1"),
        ("switchport trunk allowed vlan <vlans>", "Filter allowed VLANs on trunk link (e.g. 10,20 or 10-20)"),
        ("no switchport trunk allowed vlan", "Reset trunk allowed VLANs to default (all 1-4094)"),
        ("switchport trunk native vlan <id>", "Set Native VLAN for untagged trunk traffic"),
        ("no switchport trunk native vlan", "Reset trunk native VLAN to default (VLAN 1)"),
        ("no shutdown", "Administratively bring physical port UP"),
        ("shutdown", "Administratively bring physical port DOWN"),
        ("description <text>", "Set port description label"),
        ("no description", "Remove port description label"),
        ("do <command>", "Execute an EXEC command from interface config mode"),
        ("help / ?", "Display interface configuration commands"),
        ("exit", "Exit from interface configure mode"),
        ("end", "Exit to privileged EXEC mode"),
    ],
    "CONFIG_SVI": [
        ("ip address <ip> <subnet>", "Set SVI management IPv4 address and subnet mask"),
        ("no ip address", "Remove SVI IP address"),
        ("no shutdown", "Administratively bring SVI UP (requires active member port)"),
        ("shutdown", "Administratively bring SVI DOWN"),
        ("description <text>", "Set SVI description label"),
        ("no description", "Remove SVI description label"),
        ("do <command>", "Execute an EXEC command from SVI config mode"),
        ("help / ?", "Display SVI configuration commands"),
        ("exit", "Exit from SVI configure mode"),
        ("end", "Exit to privileged EXEC mode"),
    ],
    IOSMode.CONFIG_VLAN: [
        ("name <name>", "Specify ASCII name for this VLAN (e.g. SALES, ENGINEERING)"),
        ("no name", "Reset VLAN name to default (e.g. VLAN0010)"),
        ("do <command>", "Execute an EXEC command from VLAN configure mode"),
        ("help / ?", "Display VLAN configuration commands"),
        ("exit", "Exit from VLAN configure mode"),
        ("end", "Exit to privileged EXEC mode"),
    ]
}

# =====================================================================
# 3. Firewall Specific Command Help (FortiGate / Cisco ASA)
# =====================================================================
FIREWALL_COMMAND_HELP = {
    IOSMode.USER: [
        ("enable", "Turn on privileged commands (enters Firewall#)"),
        ("ping <ip>", "Send ICMP Echo packets to verify host reachability"),
        ("traceroute <ip>", "Trace hop-by-hop packet path to destination"),
        ("show nameif", "Display interface security zone names and security levels"),
        ("show conn", "Display active stateful TCP/UDP connection tracking table"),
        ("show xlate", "Display active NAT/PAT address translation sessions"),
        ("show access-list", "Display configured security Access Control Lists (ACL)"),
        ("show ip route", "Display firewall routing table and zone gateways"),
        ("show version", "Display firewall hardware and security software version"),
        ("help / ?", "Display list of available commands in current mode"),
        ("exit", "Exit the current EXEC session"),
    ],
    IOSMode.PRIVILEGED: [
        ("configure terminal", "Enter global configuration mode (enters config#)"),
        ("disable", "Turn off privileged commands (return to user mode)"),
        ("show running-config", "Display current operating configuration"),
        ("show nameif", "Display interface security zone names and security levels"),
        ("show conn", "Display active stateful TCP/UDP connection tracking table"),
        ("show xlate", "Display active NAT/PAT address translation sessions"),
        ("show access-list", "Display configured security Access Control Lists (ACL)"),
        ("show ip route", "Display firewall routing table and zone gateways"),
        ("show version", "Display firewall hardware and security software version"),
        ("clear conn", "Clear active stateful connection table"),
        ("clear xlate", "Clear active NAT/PAT translation sessions"),
        ("ping <ip>", "Send ICMP Echo packets [repeat N] [size N] [source INT]"),
        ("traceroute <ip>", "Trace hop-by-hop packet path to destination"),
        ("write memory", "Save running configuration to startup memory"),
        ("reload", "Halt and perform a cold restart"),
        ("help / ?", "Display list of available commands in current mode"),
        ("exit", "Exit from privileged EXEC session"),
    ],
    IOSMode.CONFIG: [
        ("hostname <name>", "Set firewall hostname"),
        ("interface <name>", "Select interface to configure (e.g. g0/0, g0/1)"),
        ("route <zone> <net> <mask> <gw>", "Establish static route through security zone gateway"),
        ("no route <zone> <net> <mask> <gw>", "Remove static route from security zone"),
        ("access-list <name> extended permit/deny <proto> <src> <dst>", "Define stateful inspection access rule"),
        ("no access-list <name>", "Delete access list"),
        ("access-group <name> in interface <zone>", "Apply ACL rule inbound to security zone interface"),
        ("no access-group <name> in interface <zone>", "Remove ACL from security zone interface"),
        ("nat (<inside_zone>,<outside_zone>) dynamic interface", "Configure dynamic Hide NAT / PAT to WAN interface"),
        ("no nat (<inside_zone>,<outside_zone>) dynamic interface", "Remove dynamic NAT rule"),
        ("do <command>", "Execute an EXEC command from configuration mode"),
        ("help / ?", "Display configuration commands"),
        ("exit", "Exit from configure mode"),
        ("end", "Exit to privileged EXEC mode"),
    ],
    IOSMode.CONFIG_IF: [
        ("nameif <zone>", "Assign logical security zone name (e.g. inside, outside, dmz)"),
        ("no nameif", "Remove security zone name from interface"),
        ("security-level <0-100>", "Set trust level (100 inside trusted, 0 outside untrusted)"),
        ("ip address <ip> <subnet>", "Set interface IPv4 address and subnet mask"),
        ("no ip address", "Remove interface IP address"),
        ("no shutdown", "Administratively bring interface UP"),
        ("shutdown", "Administratively bring interface DOWN"),
        ("description <text>", "Set interface description label"),
        ("no description", "Remove interface description label"),
        ("do <command>", "Execute an EXEC command from interface config mode"),
        ("help / ?", "Display interface configuration commands"),
        ("exit", "Exit from interface configure mode"),
        ("end", "Exit to privileged EXEC mode"),
    ]
}

# =====================================================================
# 4. Host / Server Specific Command Help (Linux / Windows Host)
# =====================================================================
HOST_COMMAND_HELP = [
    ("ping [-c N] [-s N] [-I IF] <ip>", "Send ICMP ECHO_REQUEST to network hosts"),
    ("traceroute <ip>", "Print the route packets trace to network host"),
    ("arp -a / ip neigh", "Display current ARP IP-to-MAC resolution table"),
    ("ifconfig / ip addr", "Display network interface addresses, mask, and status"),
    ("dhclient [if]", "Acquire dynamic IPv4 address lease via DHCP"),
    ("dhclient -r [if]", "Release acquired dynamic DHCP lease"),
    ("route / ip route", "Display current host routing table"),
    ("curl [-I] <url>", "Transfer data from or to a server (HTTP HEAD/GET)"),
    ("help / ?", "Display supported Linux shell commands"),
    ("clear / cls", "Clear terminal screen"),
    ("exit", "Close the terminal session"),
]

# Backward compatible single lookup
COMMAND_HELP = ROUTER_COMMAND_HELP

COMMAND_CATALOG = {
    mode: [item[0].split()[0] for item in items]
    for mode, items in ROUTER_COMMAND_HELP.items()
}


def get_device_command_help(device, mode, current_if=None):
    """
    Returns the strict, isolated list of (command, description) tuples for the specific device type.
    Commands are NEVER mixed between Routers, Switches, Firewalls, and Hosts.
    """
    if isinstance(device, Switch):
        if mode in (IOSMode.CONFIG_IF, IOSMode.CONFIG_SUBIF) and isinstance(current_if, SVI):
            return SWITCH_COMMAND_HELP.get("CONFIG_SVI", [])
        return SWITCH_COMMAND_HELP.get(mode, [])
    elif isinstance(device, Router):
        return ROUTER_COMMAND_HELP.get(mode, [])
    elif isinstance(device, Firewall):
        return FIREWALL_COMMAND_HELP.get(mode, [])
    elif isinstance(device, Host):
        return HOST_COMMAND_HELP
    # Fallback to router commands
    return ROUTER_COMMAND_HELP.get(mode, [])


def get_device_show_help(device):
    """
    Returns isolated, strictly segregated 'show ?' help text for each device type.
    """
    if isinstance(device, Switch):
        return (
            "Available Switch show commands:\n"
            "  ip interface brief    Brief summary of switch interface and SVI status\n"
            "  running-config        Current operating configuration\n"
            "  vlan brief            VLAN database status and port memberships\n"
            "  vlan id <id>          Detailed info and ports for specific VLAN\n"
            "  mac address-table     Layer 2 MAC forwarding table (CAM table)\n"
            "  interfaces trunk      802.1Q trunk status, native VLAN, and allowed VLANs\n"
            "  interfaces switchport Detailed administrative and operational switchport info\n"
            "  interfaces status     Physical port link, speed, duplex, and VLAN summary\n"
            "  spanning-tree         STP root bridge, port roles (Root/Desg/Alt) and states\n"
            "  version               Switch hardware and Cisco Catalyst version"
        )
    elif isinstance(device, Firewall):
        return (
            "Available Firewall show commands:\n"
            "  nameif                Interface security zones and IP addresses\n"
            "  conn                  Active stateful TCP/UDP connection tracking table\n"
            "  xlate                 Active NAT/PAT translation session table\n"
            "  access-list           Security access control rules and hit counters\n"
            "  ip route              Firewall routing table and zone gateways\n"
            "  running-config        Current operating configuration\n"
            "  version               Firewall hardware and security software version"
        )
    elif isinstance(device, Host):
        return (
            "Supported Host diagnostics commands:\n"
            "  ifconfig / ip addr    Display network interface configuration\n"
            "  arp -a                Display current ARP table\n"
            "  route / ip route      Display IP routing table\n"
            "  ping <ip>             Test end-to-end ICMP connectivity\n"
            "  traceroute <ip>       Trace multi-hop network path"
        )
    else:
        # Router default
        return (
            "Available Router show commands:\n"
            "  ip interface brief    Brief summary of interface IP and status\n"
            "  running-config        Current operating configuration\n"
            "  ip route              IPv4 routing table (Connected, Static, OSPF, RIP)\n"
            "  ip arp                IP to MAC address resolution table (ARP cache)\n"
            "  ip nat translations   Active NAT/PAT address mappings\n"
            "  ip nat statistics     NAT translation statistics\n"
            "  ip dhcp pool          DHCP address pool status and bindings\n"
            "  ip dhcp binding       Active DHCP client lease table\n"
            "  ip dhcp statistics    DHCP message counters\n"
            "  ip ospf               OSPF process parameters and Router ID\n"
            "  ip ospf neighbor      OSPF neighbor adjacency table and states\n"
            "  ip ospf database      OSPF Link-State Database (LSDB Router-LSAs)\n"
            "  ip rip                RIP routing database and metric status\n"
            "  ip protocols          Active dynamic routing protocols (OSPF, RIP)\n"
            "  access-list           Configured Access Control Lists (ACL)\n"
            "  version               System hardware and Cisco IOS version"
        )


class CommandParser:
    def __init__(self, executor):
        self.executor = executor

    def get_completions(self, text):
        """Returns auto-complete suggestions for current text buffer, strictly filtered by device type."""
        mode = self.executor.mode
        device = getattr(self.executor, "device", None)
        curr_if = getattr(self.executor, "current_interface", None)
        items = get_device_command_help(device, mode, curr_if)
        options = [item[0] for item in items]
        tokens = text.split()

        # Check interface completions if after 'int' or 'interface'
        if len(tokens) >= 1 and tokens[0].lower() in ("int", "interface"):
            ports = list(device.ports.keys()) if hasattr(device, "ports") else []
            if isinstance(device, Router) and hasattr(device, "subinterfaces"):
                ports.extend(list(device.subinterfaces.keys()))
            if hasattr(device, "vlans"):
                for vid in device.vlans.keys():
                    ports.append(f"vlan {vid}")
                    ports.append(f"Vlan{vid}")
            prefix = tokens[1].lower() if len(tokens) > 1 else ""
            matches = [p for p in ports if p.lower().startswith(prefix)]
            return matches

        prefix = text.lower()
        matches = [cmd for cmd in options if cmd.lower().startswith(prefix)]
        return matches

    def get_help(self, text=""):
        """Returns context-sensitive help documentation for current device and mode."""
        clean = text.strip().lower().rstrip("?").strip()
        mode = self.executor.mode
        device = getattr(self.executor, "device", None)

        if clean in ("show", "sh"):
            return get_device_show_help(device)

        if clean in ("int", "interface"):
            ports = list(device.ports.keys()) if hasattr(device, "ports") else []
            if isinstance(device, Router) and hasattr(device, "subinterfaces"):
                ports.extend(list(device.subinterfaces.keys()))
            if hasattr(device, "vlans"):
                for vid in device.vlans.keys():
                    ports.append(f"vlan {vid}")
                    ports.append(f"Vlan{vid}")
            dev_type = "Router" if isinstance(device, Router) else "Switch" if isinstance(device, Switch) else "Firewall" if isinstance(device, Firewall) else "Device"
            return f"Interfaces available on this {dev_type}:\n  " + "  ".join(ports)

        # Mode-level help table for this specific device
        curr_if = getattr(self.executor, "current_interface", None)
        items = get_device_command_help(device, mode, curr_if)

        if isinstance(device, Host):
            lines = ["Supported Linux shell commands:"]
            lines.append("-" * 75)
            for cmd, desc in items:
                lines.append(f"  {cmd:<34} {desc}")
            return "\n".join(lines)

        dev_title = "Router" if isinstance(device, Router) else "Switch" if isinstance(device, Switch) else "Firewall" if isinstance(device, Firewall) else "Device"
        lines = [f"Available Cisco IOS commands - {dev_title} ({mode} mode):"]
        lines.append("-" * 75)
        for cmd, desc in items:
            lines.append(f"  {cmd:<34} {desc}")
        return "\n".join(lines)
