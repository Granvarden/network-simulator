"""
cli/command_executor.py - Cisco IOS Command Handlers & State Machine
Implements Cisco IOS command behaviors, output tables, and config state changes.
"""

from network.router import Router, SubInterface, is_valid_ipv4, is_valid_netmask
from network.switch import Switch, SVI
from network.host import Host
from network.firewall import Firewall
from network.packet_engine import PacketEngine, format_cisco_mac

class IOSMode:
    USER = "USER"                   # Switch>
    PRIVILEGED = "PRIVILEGED"       # Switch#
    CONFIG = "CONFIG"               # Switch(config)#
    CONFIG_IF = "CONFIG_IF"         # Switch(config-if)#
    CONFIG_SUBIF = "CONFIG_SUBIF"   # Router(config-subif)#
    CONFIG_VLAN = "CONFIG_VLAN"     # Switch(config-vlan)#
    CONFIG_DHCP_POOL = "CONFIG_DHCP_POOL" # Switch(dhcp-config)#

class CommandExecutor:
    def __init__(self, device):
        self.device = device
        self.mode = IOSMode.USER if isinstance(device, (Switch, Router, Firewall)) else IOSMode.PRIVILEGED
        self.current_interface = None
        self.current_vlan_id = None
        self.current_dhcp_pool = None
        self.saved_config = ""
        self.packet_engine = PacketEngine.get_instance()

    def get_prompt(self):
        h = self.device.hostname
        if isinstance(self.device, Host):
            return f"{h}:~$ "
        if self.mode == IOSMode.USER:
            return f"{h}>"
        elif self.mode == IOSMode.PRIVILEGED:
            return f"{h}#"
        elif self.mode == IOSMode.CONFIG:
            return f"{h}(config)#"
        elif self.mode == IOSMode.CONFIG_IF:
            return f"{h}(config-if)#"
        elif self.mode == IOSMode.CONFIG_SUBIF:
            return f"{h}(config-subif)#"
        elif self.mode == IOSMode.CONFIG_VLAN:
            return f"{h}(config-vlan)#{self.current_vlan_id}#"
        elif self.mode == IOSMode.CONFIG_DHCP_POOL:
            return f"{h}(dhcp-config)#"
        return f"{h}#"

    def execute(self, line):
        cmd = line.strip()
        if not cmd:
            return ""

        # Linux Host CLI emulation for servers/PCs
        if isinstance(self.device, Host):
            return self._exec_host_command(cmd)

        # Cisco IOS CLI emulation
        tokens = cmd.split()
        verb = tokens[0].lower()

        # Global commands accessible in multiple modes
        if verb in ("help", "?") or cmd.endswith("?"):
            return self._handle_help(cmd)
        if verb == "exit":
            return self._handle_exit()
        if verb == "end":
            self.mode = IOSMode.PRIVILEGED
            self.current_interface = None
            self.current_vlan_id = None
            self.current_dhcp_pool = None
            return ""

        if self.mode == IOSMode.USER:
            return self._exec_user(tokens)
        elif self.mode == IOSMode.PRIVILEGED:
            return self._exec_privileged(tokens)
        elif self.mode == IOSMode.CONFIG:
            return self._exec_config(tokens)
        elif self.mode in (IOSMode.CONFIG_IF, IOSMode.CONFIG_SUBIF):
            return self._exec_config_if(tokens)
        elif self.mode == IOSMode.CONFIG_VLAN:
            return self._exec_config_vlan(tokens)
        elif self.mode == IOSMode.CONFIG_DHCP_POOL:
            return self._exec_config_dhcp(tokens)

        return "% Invalid input detected at '^' marker."

    def _handle_exit(self):
        if self.mode in (IOSMode.CONFIG_IF, IOSMode.CONFIG_SUBIF, IOSMode.CONFIG_VLAN, IOSMode.CONFIG_DHCP_POOL):
            self.mode = IOSMode.CONFIG
            self.current_interface = None
            self.current_vlan_id = None
            self.current_dhcp_pool = None
            return ""
        elif self.mode == IOSMode.CONFIG:
            self.mode = IOSMode.PRIVILEGED
            return ""
        elif self.mode == IOSMode.PRIVILEGED:
            self.mode = IOSMode.USER
            return ""
        elif self.mode == IOSMode.USER:
            return "[Connection closed]"
        return ""

    def _handle_help(self, cmd):
        from .command_parser import COMMAND_HELP
        clean = cmd.strip().lower().rstrip("?").strip()

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
            ports = list(self.device.ports.keys())
            if isinstance(self.device, Router):
                ports.extend(list(self.device.subinterfaces.keys()))
            return "Interfaces available on this device:\n  " + "  ".join(ports)

        # Mode-level help table
        items = COMMAND_HELP.get(self.mode, [])
        lines = [f"Available Cisco IOS commands ({self.mode} mode):"]
        lines.append("-" * 75)
        for c_name, c_desc in items:
            lines.append(f"  {c_name:<34} {c_desc}")
        return "\n".join(lines)

    def _exec_user(self, tokens):
        v = tokens[0].lower()
        if v in ("enable", "en"):
            self.mode = IOSMode.PRIVILEGED
            return ""
        if v == "ping":
            return self._cmd_ping(tokens[1:])
        if v in ("traceroute", "trace"):
            return self._cmd_traceroute(tokens[1:])
        if v in ("show", "sh"):
            return self._cmd_show(tokens[1:])
        return "% Incomplete command or requires privileged mode."

    def _exec_privileged(self, tokens):
        v = tokens[0].lower()
        if v in ("disable", "dis"):
            self.mode = IOSMode.USER
            return ""
        if v in ("configure", "conf") and len(tokens) > 1 and tokens[1].lower() in ("terminal", "t"):
            self.mode = IOSMode.CONFIG
            return "Enter configuration commands, one per line. End with CNTL/Z."
        if v in ("show", "sh"):
            return self._cmd_show(tokens[1:])
        if v == "ping":
            return self._cmd_ping(tokens[1:])
        if v in ("traceroute", "trace"):
            return self._cmd_traceroute(tokens[1:])
        if v in ("write", "wr") or (v == "copy" and len(tokens) >= 3 and tokens[1].startswith("run")):
            return "Building configuration...\n[OK]"
        if v == "reload":
            return "Proceed with reload? [confirm]\n% System restarting..."
        if v == "clear":
            if len(tokens) >= 4 and tokens[1].lower() == "ip" and tokens[2].lower() == "nat" and tokens[3].lower().startswith("trans"):
                if isinstance(self.device, Router):
                    cnt = self.device.clear_nat_translations()
                    return f"% {cnt} active NAT translation(s) cleared."
            elif len(tokens) >= 2 and tokens[1].lower() == "conn":
                if isinstance(self.device, Firewall):
                    cnt = len(self.device.connections)
                    self.device.connections.clear()
                    return f"% {cnt} active connection(s) removed."
            elif (len(tokens) >= 3 and tokens[1].lower() == "ip" and tokens[2].lower() == "arp") or (len(tokens) >= 2 and tokens[1].lower() in ("arp", "arp-cache")):
                if hasattr(self.device, "clear_arp"):
                    self.device.clear_arp()
                    return "% Dynamic ARP entries cleared."
        return f"% Unknown or incomplete command '{tokens[0]}'. Type 'help' or '?' for commands."

    def _exec_config(self, tokens):
        v = tokens[0].lower()
        if v in ("hostname", "host") and len(tokens) > 1:
            self.device.hostname = tokens[1]
            return ""
        if v in ("interface", "int") and len(tokens) > 1:
            # Check for SVI on Switch: "interface vlan 10" or "interface vlan10"
            if isinstance(self.device, Switch):
                vid = None
                if tokens[1].lower() == "vlan" and len(tokens) > 2:
                    try:
                        vid = int(tokens[2])
                    except ValueError:
                        return "% Invalid VLAN ID."
                elif tokens[1].lower().startswith("vlan"):
                    vid_str = tokens[1][4:].strip()
                    if vid_str.isdigit():
                        vid = int(vid_str)

                if vid is not None:
                    if vid not in self.device.vlans:
                        return f"% VLAN {vid} does not exist."
                    svi = self.device.create_svi(vid)
                    self.current_interface = svi
                    self.mode = IOSMode.CONFIG_IF
                    return ""

            target_name = tokens[1]
            # Check for subinterface (e.g. g0/0.10)
            if "." in target_name and isinstance(self.device, Router):
                parts = target_name.split(".")
                parent_p = self.device.get_port(parts[0])
                if not parent_p:
                    return f"% Invalid interface {parts[0]}"
                sub = self.device.create_subinterface(parent_p.name, parts[1])
                self.current_interface = sub
                self.mode = IOSMode.CONFIG_SUBIF
                return ""
            p = self.device.get_port(target_name)
            if p:
                self.current_interface = p
                self.mode = IOSMode.CONFIG_IF
                return ""
            return f"% Invalid interface type or number: {target_name}"
        if v == "vlan" and len(tokens) > 1 and isinstance(self.device, Switch):
            try:
                vid = int(tokens[1])
                self.device.add_vlan(vid)
                self.current_vlan_id = vid
                self.mode = IOSMode.CONFIG_VLAN
                return ""
            except ValueError:
                return "% Invalid VLAN ID."

        # ip default-gateway <ip>
        if v == "ip" and len(tokens) >= 3 and tokens[1].lower() in ("default-gateway", "default-gw"):
            gw_ip = tokens[2]
            if not is_valid_ipv4(gw_ip):
                return "% Invalid IP address format."
            self.device.default_gateway = gw_ip
            return ""

        # no ip default-gateway
        if v == "no" and len(tokens) >= 3 and tokens[1].lower() == "ip" and tokens[2].lower() in ("default-gateway", "default-gw"):
            self.device.default_gateway = None
            return ""

        # ip dhcp pool <name>
        if v == "ip" and len(tokens) >= 4 and tokens[1].lower() == "dhcp" and tokens[2].lower() == "pool":
            pool_name = tokens[3]
            if hasattr(self.device, "dhcp_server") and self.device.dhcp_server:
                pool = self.device.dhcp_server.create_pool(pool_name)
                self.current_dhcp_pool = pool
                self.mode = IOSMode.CONFIG_DHCP_POOL
                return ""
            return "% DHCP server not supported on this device."

        # no ip dhcp pool <name>
        if v == "no" and len(tokens) >= 5 and tokens[1].lower() == "ip" and tokens[2].lower() == "dhcp" and tokens[3].lower() == "pool":
            pool_name = tokens[4]
            if hasattr(self.device, "dhcp_server") and self.device.dhcp_server:
                if self.device.dhcp_server.delete_pool(pool_name):
                    if self.current_dhcp_pool and self.current_dhcp_pool.name == pool_name:
                        self.current_dhcp_pool = None
                        self.mode = IOSMode.CONFIG
                    return ""
                return f"% Pool {pool_name} not found."
            return "% DHCP server not supported on this device."

        # ip dhcp excluded-address <low_ip> [high_ip]
        if v == "ip" and len(tokens) >= 4 and tokens[1].lower() == "dhcp" and tokens[2].lower() in ("excluded-address", "excluded"):
            low_ip = tokens[3]
            high_ip = tokens[4] if len(tokens) > 4 else None
            if not is_valid_ipv4(low_ip) or (high_ip and not is_valid_ipv4(high_ip)):
                return "% Invalid IP address format."
            if hasattr(self.device, "dhcp_server") and self.device.dhcp_server:
                self.device.dhcp_server.add_excluded_address(low_ip, high_ip)
                return ""
            return "% DHCP server not supported on this device."

        # no ip dhcp excluded-address <low_ip> [high_ip]
        if v == "no" and len(tokens) >= 5 and tokens[1].lower() == "ip" and tokens[2].lower() == "dhcp" and tokens[3].lower() in ("excluded-address", "excluded"):
            low_ip = tokens[4]
            high_ip = tokens[5] if len(tokens) > 5 else None
            if hasattr(self.device, "dhcp_server") and self.device.dhcp_server:
                self.device.dhcp_server.remove_excluded_address(low_ip, high_ip)
                return ""
            return "% DHCP server not supported on this device."

        # spanning-tree [vlan <id>] priority <prio>
        if (v.startswith("spanning-tree") or v == "spanning") and isinstance(self.device, Switch):
            for idx, tok in enumerate(tokens):
                if tok.lower() == "priority" and idx + 1 < len(tokens):
                    try:
                        self.device.stp_priority = int(tokens[idx + 1])
                        self.device.recalculate_stp()
                        return ""
                    except ValueError:
                        return "% Invalid priority value."
            return ""

        # access-list configuration (Router standard ACL & Firewall extended ACL)
        if v in ("access-list", "acl") and len(tokens) > 2:
            if isinstance(self.device, Router):
                # access-list 1 permit 192.168.0.0 0.0.255.255
                acl_id = tokens[1]
                action = tokens[2].lower()
                source = tokens[3].lower() if len(tokens) > 3 else "any"
                wildcard = tokens[4] if len(tokens) > 4 else "0.0.0.0"
                self.device.add_access_list(acl_id, action, source, wildcard)
                return ""
            elif isinstance(self.device, Firewall):
                # access-list OUTSIDE_IN extended permit icmp any any
                acl_name = tokens[1]
                idx = 2
                if idx < len(tokens) and tokens[idx].lower() == "extended":
                    idx += 1
                action = tokens[idx].lower() if idx < len(tokens) else "permit"
                proto = tokens[idx+1].lower() if idx+1 < len(tokens) else "ip"
                src = tokens[idx+2].lower() if idx+2 < len(tokens) else "any"
                dst = tokens[idx+3].lower() if idx+3 < len(tokens) else "any"
                self.device.add_access_list(acl_name, action, proto, src, dst)
                return ""

        # access-group (Firewall)
        if v in ("access-group",) and len(tokens) >= 4 and isinstance(self.device, Firewall):
            # access-group OUTSIDE_IN in interface outside
            acl_name = tokens[1]
            direction = tokens[2].lower()
            if tokens[3].lower() == "interface" and len(tokens) > 4:
                zone = tokens[4]
            else:
                zone = tokens[3]
            self.device.set_access_group(acl_name, direction, zone)
            return ""

        # route <zone> <net> <mask> <gw> (Firewall ASA syntax)
        if v == "route" and len(tokens) >= 5 and isinstance(self.device, Firewall):
            # route outside 0.0.0.0 0.0.0.0 203.0.113.1
            zone, net, mask, gw = tokens[1], tokens[2], tokens[3], tokens[4]
            self.device.add_static_route(net, mask, gw, interface=zone)
            return ""

        # no ip route <net> <mask4> [gw]
        if v == "no" and len(tokens) >= 5 and tokens[1].lower() == "ip" and tokens[2].lower() == "route" and isinstance(self.device, (Router, Firewall)):
            net, mask = tokens[3], tokens[4]
            gw = tokens[5] if len(tokens) > 5 else None
            self.device.remove_static_route(net, mask, gw)
            return ""

        # ip route <net> <mask4> <gw>
        if v == "ip" and len(tokens) >= 5 and tokens[1].lower() == "route" and isinstance(self.device, (Router, Firewall)):
            net, mask, nexthop = tokens[2], tokens[3], tokens[4]
            self.device.add_static_route(net, mask, nexthop)
            return ""

        # ip nat inside source list <acl> interface <if> overload
        if v == "ip" and len(tokens) >= 7 and tokens[1].lower() == "nat" and isinstance(self.device, Router):
            # ip nat inside source list 1 interface g0/0 overload
            if tokens[2].lower() == "inside" and tokens[3].lower() == "source" and tokens[4].lower() == "list":
                acl_id = tokens[5]
                out_if = tokens[7] if (len(tokens) > 7 and tokens[6].lower() == "interface") else tokens[6]
                is_overload = tokens[-1].lower() == "overload"
                self.device.add_nat_rule("overload" if is_overload else "static", acl_id, out_if)
                return ""

        if v in ("do",):
            # Execute privileged command in config mode
            return self._exec_privileged(tokens[1:])
        if v in ("show", "sh"):
            return self._cmd_show(tokens[1:])
        return "% Invalid configuration command."

    def _exec_config_dhcp(self, tokens):
        if not self.current_dhcp_pool:
            self.mode = IOSMode.CONFIG
            return "% No DHCP pool selected."

        v = tokens[0].lower()

        # network <net> <mask4> or network <net>/<prefix>
        if v == "network" and len(tokens) >= 2:
            arg = tokens[1]
            if "/" in arg:
                parts = arg.split("/")
                net = parts[0]
                try:
                    prefix = int(parts[1])
                    mask_int = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
                    from network.router import int_to_ip
                    mask = int_to_ip(mask_int)
                except Exception:
                    return "% Invalid subnet prefix."
            elif len(tokens) >= 3:
                net = tokens[1]
                mask = tokens[2]
            else:
                return "% Incomplete network command. Usage: network <network-number> [mask | /prefix]"

            if not is_valid_ipv4(net):
                return "% Invalid IP network address."
            if not is_valid_netmask(mask):
                return "% Invalid subnet mask format."

            self.current_dhcp_pool.network = net
            self.current_dhcp_pool.subnet_mask = mask
            return ""

        # no network
        if v == "no" and len(tokens) >= 2 and tokens[1].lower() == "network":
            self.current_dhcp_pool.network = "0.0.0.0"
            self.current_dhcp_pool.subnet_mask = "255.255.255.0"
            return ""

        # default-router <ip> or default-gateway <ip>
        if v in ("default-router", "default-gateway") and len(tokens) >= 2:
            gw = tokens[1]
            if not is_valid_ipv4(gw):
                return "% Invalid IP address format."
            self.current_dhcp_pool.default_router = gw
            return ""

        # no default-router
        if v == "no" and len(tokens) >= 2 and tokens[1].lower() in ("default-router", "default-gateway"):
            self.current_dhcp_pool.default_router = None
            return ""

        # dns-server <ip> [ip2 ...]
        if v in ("dns-server", "dns") and len(tokens) >= 2:
            servers = []
            for ip in tokens[1:]:
                if is_valid_ipv4(ip):
                    servers.append(ip)
            if not servers:
                return "% Invalid DNS server IP address."
            self.current_dhcp_pool.dns_servers = servers
            return ""

        # no dns-server
        if v == "no" and len(tokens) >= 2 and tokens[1].lower() in ("dns-server", "dns"):
            self.current_dhcp_pool.dns_servers = []
            return ""

        # lease <days> [hours] [minutes] or lease infinite
        if v == "lease" and len(tokens) >= 2:
            if tokens[1].lower() == "infinite":
                self.current_dhcp_pool.lease_duration = 365 * 86400
                return ""
            try:
                days = int(tokens[1])
                hours = int(tokens[2]) if len(tokens) > 2 else 0
                minutes = int(tokens[3]) if len(tokens) > 3 else 0
                self.current_dhcp_pool.lease_duration = days * 86400 + hours * 3600 + minutes * 60
                return ""
            except ValueError:
                return "% Invalid lease format. Usage: lease <days> [hours] [minutes] or lease infinite"

        # no lease
        if v == "no" and len(tokens) >= 2 and tokens[1].lower() == "lease":
            self.current_dhcp_pool.lease_duration = 86400
            return ""

        if v == "do":
            return self._exec_privileged(tokens[1:])
        if v in ("show", "sh"):
            return self._cmd_show(tokens[1:])

        # Transitions to global commands
        if v in ("interface", "int", "ip", "vlan", "hostname"):
            self.mode = IOSMode.CONFIG
            self.current_dhcp_pool = None
            return self._exec_config(tokens)

        return "% Invalid DHCP pool configuration command."

    def _exec_config_if(self, tokens):
        if not self.current_interface:
            self.mode = IOSMode.CONFIG
            return "% No interface selected."

        line = " ".join(tokens).lower()

        # Allow switching interface directly from (config-if)#
        if tokens[0].lower() in ("interface", "int") and len(tokens) > 1:
            return self._exec_config(tokens)

        # shutdown / no shutdown
        if line == "shutdown" or line == "shut":
            self.current_interface.is_shutdown = True
            return f"% Interface {self.current_interface.name}, changed state to administratively down"
        if line in ("no shutdown", "no shut"):
            self.current_interface.is_shutdown = False
            state = "up" if getattr(self.current_interface, "is_link_up", False) else "down"
            return (f"% Interface {self.current_interface.name}, changed state to up\n"
                    f"% LINEPROTO-5-UPDOWN: Line protocol on Interface {self.current_interface.name}, changed state to {state}")

        # no ip address
        if len(tokens) >= 3 and tokens[0].lower() == "no" and tokens[1].lower() == "ip" and tokens[2].lower() == "address":
            self.current_interface.ip_address = None
            self.current_interface.subnet_mask = None
            setattr(self.current_interface, "ip_method", "manual")
            return ""

        # ip default-gateway / no ip default-gateway
        if tokens[0].lower() == "ip" and len(tokens) >= 3 and tokens[1].lower() in ("default-gateway", "default-gw"):
            return self._exec_config(tokens)
        if len(tokens) >= 3 and tokens[0].lower() == "no" and tokens[1].lower() == "ip" and tokens[2].lower() in ("default-gateway", "default-gw"):
            return self._exec_config(tokens)

        # IP address assignment via DHCP: "ip address dhcp"
        if tokens[0].lower() == "ip" and len(tokens) >= 3 and tokens[1].lower() == "address" and tokens[2].lower() == "dhcp":
            setattr(self.current_interface, "ip_method", "DHCP")
            ok, res = self.packet_engine.simulate_dhcp_dora(self.device, self.current_interface)
            if ok:
                return ""
            else:
                return f"% DHCP failed: {res}"

        # IP address assignment
        if tokens[0].lower() == "ip" and len(tokens) >= 4 and tokens[1].lower() == "address":
            ip, mask = tokens[2], tokens[3]
            if not is_valid_ipv4(ip):
                return "% Invalid IP address format."
            if not is_valid_netmask(mask):
                return "% Invalid subnet mask format."

            # Check duplicate IP on the same device
            if hasattr(self.device, "ports"):
                for p in self.device.ports.values():
                    if p != self.current_interface and p.ip_address == ip:
                        return f"% IP address {ip} already assigned to interface {p.name}."
            if hasattr(self.device, "subinterfaces"):
                for sub in self.device.subinterfaces.values():
                    if sub != self.current_interface and sub.ip_address == ip:
                        return f"% IP address {ip} already assigned to interface {sub.name}."
            if hasattr(self.device, "svis"):
                for svi in self.device.svis.values():
                    if svi != self.current_interface and svi.ip_address == ip:
                        return f"% IP address {ip} already assigned to interface {svi.name}."

            self.current_interface.ip_address = ip
            self.current_interface.subnet_mask = mask
            setattr(self.current_interface, "ip_method", "manual")
            return ""

        # ip access-group <acl> in|out (Router)
        if tokens[0].lower() == "ip" and len(tokens) >= 4 and tokens[1].lower() in ("access-group", "access-list") and isinstance(self.device, Router):
            acl_id = tokens[2]
            direction = tokens[3].lower()
            self.device.set_access_group(acl_id, direction, self.current_interface.name)
            return ""

        # ip nat inside / outside (Router)
        if tokens[0].lower() == "ip" and len(tokens) >= 3 and tokens[1].lower() == "nat" and isinstance(self.device, Router):
            nat_dir = tokens[2].lower()
            if nat_dir == "inside":
                self.device.nat_inside_interfaces.add(self.current_interface.name)
                return ""
            elif nat_dir == "outside":
                self.device.nat_outside_interfaces.add(self.current_interface.name)
                return ""

        if len(tokens) >= 4 and tokens[0].lower() == "no" and tokens[1].lower() == "ip" and tokens[2].lower() == "nat" and isinstance(self.device, Router):
            nat_dir = tokens[3].lower()
            if nat_dir == "inside":
                self.device.nat_inside_interfaces.discard(self.current_interface.name)
                return ""
            elif nat_dir == "outside":
                self.device.nat_outside_interfaces.discard(self.current_interface.name)
                return ""

        # nameif <zone> (Firewall)
        if tokens[0].lower() == "nameif" and len(tokens) > 1 and isinstance(self.device, Firewall):
            zone = tokens[1].lower()
            self.device.set_nameif(self.current_interface.name, zone)
            lvl = self.device.security_levels.get(zone, 0)
            return f'INFO: Security level for "{zone}" set to {lvl} by default.'

        # security-level <0-100> (Firewall)
        if tokens[0].lower() in ("security-level", "security") and len(tokens) > 1 and isinstance(self.device, Firewall):
            self.device.set_security_level(self.current_interface.name, tokens[1])
            return ""

        # Encapsulation dot1Q <vlan> (for router subinterfaces)
        if tokens[0].lower() in ("encapsulation", "encap") and len(tokens) >= 3 and tokens[1].lower() in ("dot1q", "dot1"):
            if isinstance(self.current_interface, SubInterface):
                try:
                    self.current_interface.vlan_id = int(tokens[2])
                    return ""
                except ValueError:
                    return "% Invalid VLAN ID"

        # Switchport commands
        if tokens[0].lower() in ("switchport", "sw"):
            if len(tokens) >= 3 and tokens[1].lower() == "mode":
                mode = tokens[2].lower()
                if mode in ("access", "trunk"):
                    self.current_interface.mode = mode
                    return ""
            if len(tokens) >= 4 and tokens[1].lower() == "access" and tokens[2].lower() == "vlan":
                try:
                    vid = int(tokens[3])
                    self.current_interface.access_vlan = vid
                    return ""
                except ValueError:
                    return "% Invalid VLAN number"
            if len(tokens) >= 5 and tokens[1].lower() == "trunk" and tokens[2].lower() == "allowed":
                # allowed vlan 10,20
                vlan_str = tokens[4]
                try:
                    vlans = {int(x) for x in vlan_str.replace(",", " ").split()}
                    self.current_interface.trunk_allowed_vlans = vlans
                    return ""
                except Exception:
                    return "% Error parsing VLAN list"

        if tokens[0].lower() == "do":
            return self._exec_privileged(tokens[1:])
        if tokens[0].lower() in ("show", "sh"):
            return self._cmd_show(tokens[1:])

        return "% Invalid interface command."

    def _exec_config_vlan(self, tokens):
        if not self.current_vlan_id or not isinstance(self.device, Switch):
            self.mode = IOSMode.CONFIG
            return ""
        if tokens[0].lower() == "name" and len(tokens) > 1:
            name = tokens[1]
            self.device.add_vlan(self.current_vlan_id, name)
            return ""
        if tokens[0].lower() in ("interface", "int", "vlan", "hostname", "ip", "no"):
            self.mode = IOSMode.CONFIG
            self.current_vlan_id = None
            return self._exec_config(tokens)
        if tokens[0].lower() == "do":
            return self._exec_privileged(tokens[1:])
        return "% Invalid vlan command."

    def _cmd_ping(self, args):
        if not args:
            return "% Incomplete command. Usage: ping <target-ip> [repeat <count>] [size <bytes>] [timeout <seconds>] [source <interface>]"
        tokens = args.split() if isinstance(args, str) else list(args)
        if not tokens:
            return "% Incomplete command. Usage: ping <target-ip>"

        target_ip = tokens[0]
        count = 5
        size = 100
        timeout = 2
        source_if = None

        idx = 1
        while idx < len(tokens):
            tok = tokens[idx].lower()
            if tok in ("repeat", "count") and idx + 1 < len(tokens):
                try:
                    count = max(1, min(100, int(tokens[idx+1])))
                except ValueError:
                    pass
                idx += 2
            elif tok == "size" and idx + 1 < len(tokens):
                try:
                    size = max(36, min(18024, int(tokens[idx+1])))
                except ValueError:
                    pass
                idx += 2
            elif tok == "timeout" and idx + 1 < len(tokens):
                try:
                    timeout = max(1, min(30, int(tokens[idx+1])))
                except ValueError:
                    pass
                idx += 2
            elif tok == "source" and idx + 1 < len(tokens):
                source_if = tokens[idx+1]
                idx += 2
            else:
                idx += 1

        res = self.packet_engine.simulate_ping(self.device, target_ip, count=count,
                                               timeout=timeout, data_bytes=size,
                                               source_interface=source_if, simulate_arp=False)
        if res.error_message and res.packets_received == 0 and not res.status_codes:
            return res.error_message

        out = [
            "Type escape sequence to abort.",
            f"Sending {count}, {size}-byte ICMP Echos to {target_ip}, timeout is {timeout} seconds:",
            res.success_rate_cisco,
            f"Success rate is {100 - res.loss_percent} percent ({res.packets_received}/{count})"
        ]
        if res.rtt_ms:
            min_r = int(min(res.rtt_ms)) if min(res.rtt_ms).is_integer() else round(min(res.rtt_ms), 1)
            avg_r = round(sum(res.rtt_ms)/len(res.rtt_ms), 1)
            max_r = int(max(res.rtt_ms)) if max(res.rtt_ms).is_integer() else round(max(res.rtt_ms), 1)
            out.append(f"round-trip min/avg/max = {min_r}/{avg_r}/{max_r} ms")
        return "\n".join(out)

    def _cmd_traceroute(self, args):
        if not args:
            return "% Incomplete command. Usage: traceroute <target-ip>"
        tokens = args.split() if isinstance(args, str) else list(args)
        target_ip = tokens[0]

        hops = self.packet_engine.simulate_traceroute(self.device, target_ip)
        lines = [
            "Type escape sequence to abort.",
            f"Tracing the route to {target_ip}",
            "VRF info: (none)"
        ]
        for h in hops:
            if not h["rtts"]:
                lines.append(f"  {h['hop']} * * * Request timed out.")
            else:
                rtt_strs = "  ".join(f"{r} msec" for r in h["rtts"])
                lines.append(f"  {h['hop']} {h['ip']} [{h['name']}] {rtt_strs}")
        return "\n".join(lines)

    def _show_ip_arp(self):
        lines = [
            "Protocol  Address          Age (min)  Hardware Addr   Type   Interface"
        ]
        # Own interfaces
        if hasattr(self.device, "ports"):
            for p in self.device.ports.values():
                if not p.is_shutdown and p.ip_address:
                    c_mac = format_cisco_mac(p.mac_address)
                    lines.append(f"Internet  {p.ip_address:<16}        -   {c_mac}  ARPA   {p.full_name}")
        if hasattr(self.device, "subinterfaces"):
            for sub in self.device.subinterfaces.values():
                if not sub.is_shutdown and sub.ip_address:
                    c_mac = format_cisco_mac(getattr(sub.parent_port, "mac_address", "0200.1a00.0001"))
                    lines.append(f"Internet  {sub.ip_address:<16}        -   {c_mac}  ARPA   {sub.name}")

        # Learned ARP entries
        if hasattr(self.device, "arp_table"):
            for ip, entry in self.device.arp_table.items():
                mac = format_cisco_mac(entry.get("mac", ""))
                intf = entry.get("interface", "GigabitEthernet0/1")
                age = str(entry.get("age_min", 1))
                lines.append(f"Internet  {ip:<16} {age:>8}   {mac}  ARPA   {intf}")

        return "\n".join(lines)

    def _cmd_show(self, args):
        if not args:
            return "% Incomplete show command"
        sub = " ".join(args).lower()

        # show ip interface brief
        if sub in ("ip int br", "ip interface brief", "ip int brief"):
            return self._show_ip_int_brief()

        # show ip arp / show arp
        if sub in ("ip arp", "arp", "ip arp brief"):
            return self._show_ip_arp()

        # show vlan brief
        if sub in ("vlan brief", "vlan br", "vlan") and isinstance(self.device, Switch):
            return self._show_vlan_brief()

        # show mac address-table
        if sub in ("mac address-table", "mac-address-table", "mac") and isinstance(self.device, Switch):
            return self._show_mac_table()

        # show spanning-tree
        if (sub.startswith("spanning-tree") or sub in ("spanning", "span", "stp")) and isinstance(self.device, Switch):
            return self._show_spanning_tree(args)

        # show ip route / show route
        if (sub in ("ip route", "ip ro", "route") or sub.startswith("ip route")) and isinstance(self.device, (Router, Firewall)):
            return self._show_ip_route()

        # show ip nat translations
        if ("nat" in sub and "trans" in sub) and isinstance(self.device, Router):
            return self._show_ip_nat_translations()

        # show ip nat statistics
        if ("nat" in sub and "stat" in sub) and isinstance(self.device, Router):
            return self._show_ip_nat_statistics()

        # show access-lists / access-list
        if sub in ("access-list", "access-lists", "acl", "ip access-lists", "ip access-list") and isinstance(self.device, (Router, Firewall)):
            return self._show_access_lists()

        # show nameif (Firewall)
        if sub in ("nameif", "names", "name") and isinstance(self.device, Firewall):
            return self._show_nameif()

        # show conn (Firewall)
        if sub in ("conn", "connection", "connections") and isinstance(self.device, Firewall):
            return self._show_conn()

        # show running-config
        if sub in ("run", "running-config", "running"):
            return self._show_running_config()

        # show ip dhcp pool
        if sub in ("ip dhcp pool", "ip dhcp pools") or sub.startswith("ip dhcp pool"):
            return self._show_ip_dhcp_pool(args)

        # show ip dhcp binding
        if sub in ("ip dhcp binding", "ip dhcp bindings") or sub.startswith("ip dhcp binding"):
            return self._show_ip_dhcp_binding()

        # show ip dhcp statistics / server statistics
        if sub in ("ip dhcp stat", "ip dhcp stats", "ip dhcp statistics", "ip dhcp server statistics"):
            return self._show_ip_dhcp_statistics()

        # show interfaces [vlan <id>] / show int [vlan <id>]
        if sub in ("int", "interface", "interfaces") or sub.startswith("int ") or sub.startswith("interface ") or sub.startswith("interfaces "):
            return self._show_interface(args)

        return f"% Show command '{sub}' not recognized."

    def _show_ip_dhcp_pool(self, args):
        if not hasattr(self.device, "dhcp_server") or not self.device.dhcp_server:
            return "% DHCP server not supported on this device."
        server = self.device.dhcp_server
        if not server.pools:
            return "No DHCP pools configured."

        tokens = [x.lower() for x in args]
        specific_pool = None
        for i, t in enumerate(tokens):
            if t == "pool" and i + 1 < len(args):
                specific_pool = args[i + 1]
                break

        lines = []
        pools_to_show = [server.pools[specific_pool]] if (specific_pool and specific_pool in server.pools) else server.pools.values()

        for pool in pools_to_show:
            total = pool.get_total_addresses()
            leased = sum(1 for lease in server.binding_table.values() if lease.pool_name == pool.name)
            excluded_count = sum(1 for ip in server.excluded_addresses if pool.is_ip_in_pool(ip))
            first_ip, last_ip = pool.get_usable_ip_range()
            range_str = f"{first_ip} .. {last_ip}" if first_ip else "none"
            idx_ip = first_ip or "0.0.0.0"

            lines.extend([
                f"Pool {pool.name} :",
                f" Utilization mark (high/low)    : 100 / 0",
                f" Subnet size (lines/batches)    : {total}/0",
                f" Total addresses                : {total}",
                f" Leased addresses               : {leased}",
                f" Excluded addresses             : {excluded_count}",
                f" Pending addresses              : 0",
                f" 1 Subnet is currently in the pool :",
                f" Current index        IP address range                    Leased/Excluded/Total",
                f" {idx_ip:<20} {range_str:<35} {leased}    / {excluded_count:<8} / {total}",
                ""
            ])

        return "\n".join(lines).strip()

    def _show_ip_dhcp_binding(self):
        if not hasattr(self.device, "dhcp_server") or not self.device.dhcp_server:
            return "% DHCP server not supported on this device."
        server = self.device.dhcp_server
        lines = [
            "Bindings from all pools :",
            f"{'IP address':<20}{'Client-ID/':<24}{'Lease expiration':<24}{'Type'}",
            f"{'':<20}{'Hardware address/':<24}{'':<24}{''}",
            f"{'':<20}{'User name':<24}{'':<24}{''}"
        ]
        if not server.binding_table:
            return "\n".join(lines)

        for ip, lease in sorted(server.binding_table.items()):
            c_mac = format_cisco_mac(lease.mac_address)
            exp = lease.lease_expiration
            lines.append(f"{ip:<20}{c_mac:<24}{exp:<24}Automatic")
        return "\n".join(lines)

    def _show_ip_dhcp_statistics(self):
        if not hasattr(self.device, "dhcp_server") or not self.device.dhcp_server:
            return "% DHCP server not supported on this device."
        server = self.device.dhcp_server
        stats = server.statistics
        total_pools = len(server.pools)
        bindings = len(server.binding_table)

        lines = [
            "Memory used                     25600",
            f"Server configuration modes      {total_pools}",
            "Server interfaces               1",
            "",
            f"Address pools                   {total_pools}",
            "Database agents                 0",
            f"Automatic bindings              {bindings}",
            "Manual bindings                 0",
            "Expired bindings                0",
            "Malformed messages              0",
            "Secure arp entries              0",
            "",
            "Message                         Received",
            "BOOTREQUEST                     0",
            f"DHCPDISCOVER                    {stats.get('discover', 0)}",
            f"DHCPREQUEST                     {stats.get('request', 0)}",
            "DHCPDECLINE                     0",
            f"DHCPRELEASE                     {stats.get('release', 0)}",
            "DHCPINFORM                      0",
            "",
            "Message                         Sent",
            "BOOTREPLY                       0",
            f"DHCPOFFER                       {stats.get('offer', 0)}",
            f"DHCPACK                         {stats.get('ack', 0)}",
            f"DHCPNAK                         {stats.get('nak', 0)}"
        ]
        return "\n".join(lines)

    def _show_interface(self, args):
        tokens = [x.lower() for x in args]
        target_name = None
        if len(tokens) >= 3 and tokens[1] == "vlan":
            target_name = f"Vlan{tokens[2]}"
        elif len(tokens) >= 2:
            target_name = tokens[1]

        if target_name and isinstance(self.device, Switch):
            intf = self.device.get_interface(target_name)
            if intf and isinstance(intf, SVI):
                status = "administratively down" if intf.is_shutdown else "up"
                proto = "up" if intf.is_link_up else "down"
                ip_info = f"Internet address is {intf.ip_address}/{intf.subnet_mask}" if intf.ip_address else "Internet protocol processing disabled"
                c_mac = format_cisco_mac(intf.mac_address)
                lines = [
                    f"{intf.full_name} is {status}, line protocol is {proto}",
                    f"  Hardware is EtherSVI, address is {c_mac} (bia {c_mac})",
                    f"  {ip_info}",
                    f"  MTU 1500 bytes, BW 1000000 Kbit/sec, DLY 10 usec",
                    f"  Encapsulation ARPA, loopback not set",
                ]
                return "\n".join(lines)
            elif intf:
                status = "administratively down" if intf.is_shutdown else ("up" if intf.cable else "down")
                proto = "up" if intf.is_link_up else "down"
                lines = [
                    f"{intf.full_name} is {status}, line protocol is {proto}",
                    f"  Hardware is Gigabit Ethernet, address is {format_cisco_mac(intf.mac_address)}",
                    f"  MTU 1500 bytes, BW 1000000 Kbit/sec, DLY 10 usec"
                ]
                return "\n".join(lines)
            return f"% Interface {target_name} does not exist"
        return self._show_ip_int_brief()

    def _show_ip_int_brief(self):
        lines = [
            f"{'Interface':<24}{'IP-Address':<16}{'OK?':<6}{'Method':<8}{'Status':<22}{'Protocol'}",
            "-" * 84
        ]
        # Physical ports
        for p_name, port in self.ports_to_list():
            ip = port.ip_address if port.ip_address else "unassigned"
            status = "administratively down" if port.is_shutdown else ("up" if port.cable else "down")
            proto = "up" if port.is_link_up else "down"
            method = getattr(port, "ip_method", "manual") if port.ip_address else "unset"
            lines.append(f"{port.name:<24}{ip:<16}{'YES':<6}{method:<8}{status:<22}{proto}")

        # Subinterfaces
        if isinstance(self.device, Router):
            for s_name, sub in self.device.subinterfaces.items():
                ip = sub.ip_address if sub.ip_address else "unassigned"
                status = "administratively down" if sub.is_shutdown else ("up" if sub.is_link_up else "down")
                proto = "up" if sub.is_link_up else "down"
                method = getattr(sub, "ip_method", "manual") if sub.ip_address else "unset"
                lines.append(f"{sub.name:<24}{ip:<16}{'YES':<6}{method:<8}{status:<22}{proto}")

        # SVIs
        if isinstance(self.device, Switch) and hasattr(self.device, "svis"):
            for vid, svi in sorted(self.device.svis.items()):
                ip = svi.ip_address if svi.ip_address else "unassigned"
                status = "administratively down" if svi.is_shutdown else ("up" if svi.is_link_up else "down")
                proto = "up" if svi.is_link_up else "down"
                method = getattr(svi, "ip_method", "manual") if svi.ip_address else "unset"
                lines.append(f"{svi.name:<24}{ip:<16}{'YES':<6}{method:<8}{status:<22}{proto}")

        return "\n".join(lines)

    def ports_to_list(self):
        # Sort ports nicely
        return sorted(self.device.ports.items(), key=lambda x: x[0])

    def _show_vlan_brief(self):
        lines = [
            f"{'VLAN':<6}{'Name':<24}{'Status':<12}{'Ports'}",
            "-" * 65
        ]
        for vid, data in sorted(self.device.vlans.items()):
            assigned_ports = []
            for p in self.device.ports.values():
                if p.mode == "access" and p.access_vlan == vid:
                    assigned_ports.append(p.name)
            ports_str = ", ".join(assigned_ports)
            lines.append(f"{vid:<6}{data['name']:<24}{data['status']:<12}{ports_str}")
        return "\n".join(lines)

    def _show_mac_table(self):
        lines = [
            f"{'Vlan':<8}{'Mac Address':<20}{'Type':<10}{'Ports'}",
            "-" * 50
        ]
        if not self.device.mac_table:
            lines.append("Total Mac Addresses for this criterion: 0")
        else:
            for mac, info in self.device.mac_table.items():
                lines.append(f"{info['vlan']:<8}{mac:<20}{'DYNAMIC':<10}{info['port']}")
        return "\n".join(lines)

    def _show_spanning_tree(self, args=None):
        if not isinstance(self.device, Switch):
            return "% Spanning-tree command only supported on switches."

        if self.device.stp_enabled:
            self.device.recalculate_stp()

        root_prio, root_mac = self.device.root_bridge_id if self.device.root_bridge_id else self.device.bridge_id
        br_prio, br_mac = self.device.bridge_id

        cisco_root_mac = format_cisco_mac(root_mac)
        cisco_br_mac = format_cisco_mac(br_mac)

        is_root = self.device.is_root_bridge
        root_cost = self.device.root_path_cost
        rp_name = self.device.root_port.name if self.device.root_port else "None"

        lines = [
            "VLAN0001",
            "  Spanning tree enabled protocol ieee",
            f"  Root ID    Priority    {root_prio}",
            f"             Address     {cisco_root_mac}",
        ]
        if is_root:
            lines.append("             This bridge is the root")
        else:
            lines.append(f"             Cost        {root_cost}")
            lines.append(f"             Port        {rp_name}")

        lines.extend([
            f"  Bridge ID  Priority    {br_prio}",
            f"             Address     {cisco_br_mac}",
            "             Hello Time   2 sec  Max Age 20 sec  Forward Delay 15 sec",
            "",
            f"{'Interface':<12}{'Role':<14}{'State':<14}{'Cost':<8}{'Type'}",
            "-" * 60
        ])

        for p_name, p in sorted(self.device.ports.items(), key=lambda x: x[1].port_index):
            if p.port_type == "CONSOLE":
                continue
            role = getattr(p, "stp_role", "Designated")
            state = getattr(p, "stp_state", "Forwarding")
            cost = getattr(p, "stp_cost", 4)
            p_type = "P2p" if p.cable else "Edge"
            lines.append(f"{p.name:<12}{role:<14}{state:<14}{cost:<8}{p_type}")

        return "\n".join(lines)

    def _show_ip_route(self):
        lines = [
            "Codes: C - connected, S - static, R - RIP, O - OSPF",
            "Gateway of last resort is not set",
            ""
        ]
        routes = self.device.get_all_routes()
        if not routes:
            lines.append("No active routes in routing table.")
        for r in routes:
            t = r["type"]
            net = r["network"]
            mask = r["mask"]
            if r["next_hop"] == "directly connected":
                lines.append(f"{t}    {net}/{mask} is directly connected, {r['interface']}")
            else:
                lines.append(f"{t}    {net}/{mask} [1/0] via {r['next_hop']}")
        return "\n".join(lines)

    def _show_ip_nat_translations(self):
        lines = [
            f"{'Pro':<6}{'Inside global':<24}{'Inside local':<24}{'Outside local':<18}{'Outside global'}",
            "-" * 88
        ]
        if not self.device.nat_translations:
            lines.append("No active NAT translations.")
        else:
            for tr in self.device.nat_translations:
                lines.append(f"{tr['protocol']:<6}{tr['inside_global']:<24}{tr['inside_local']:<24}{tr['outside_local']:<18}{tr['outside_global']}")
        return "\n".join(lines)

    def _show_ip_nat_statistics(self):
        active = len(self.device.nat_translations)
        outside_ifs = ", ".join(self.device.nat_outside_interfaces) or "None"
        inside_ifs = ", ".join(self.device.nat_inside_interfaces) or "None"
        hits = active * 5
        lines = [
            f"Total active translations: {active} (0 static, {active} dynamic; {active} extended)",
            "Outside interfaces:",
            f"  {outside_ifs}",
            "Inside interfaces:",
            f"  {inside_ifs}",
            f"Hits: {hits}  Misses: 0",
            f"CEF Translated packets: {hits}, CEF Punted packets: 0",
            f"Expired translations: 0",
            f"Dynamic mappings: {len(self.device.nat_rules)}"
        ]
        for r in self.device.nat_rules:
            lines.append(f" -- Inside Source access-list {r['acl']} interface {r['interface']} refcount {active}")
        return "\n".join(lines)

    def _show_access_lists(self):
        lines = []
        if isinstance(self.device, Router):
            if not self.device.access_lists:
                return "No IP access lists configured."
            for acl_id, rules in sorted(self.device.access_lists.items()):
                lines.append(f"Standard IP access list {acl_id}")
                for idx, r in enumerate(rules):
                    wc_str = f", wildcard bits {r['wildcard']}" if r.get("wildcard") != "0.0.0.0" else ""
                    lines.append(f"    {(idx+1)*10} {r['action']} {r['source']}{wc_str}")
        elif isinstance(self.device, Firewall):
            if not self.device.access_lists:
                return "No access-lists configured on firewall."
            for acl_name, rules in self.device.access_lists.items():
                lines.append(f"access-list {acl_name}; {len(rules)} elements; name hash: 0x{abs(hash(acl_name))%0xFFFFFF:08x}")
                for idx, r in enumerate(rules):
                    lines.append(f"access-list {acl_name} line {idx+1} extended {r['action']} {r['protocol']} {r['src']} {r['dst']} (hitcnt=5) 0x{abs(hash(idx+1))%0xFFFFFF:08x}")
        return "\n".join(lines) if lines else "No access lists found."

    def _show_nameif(self):
        lines = [
            f"{'Interface':<28}{'Name':<20}{'Security'}",
            "-" * 60
        ]
        for p_name, port in self.ports_to_list():
            zone = self.device.nameif.get(p_name, "unassigned")
            sec = self.device.security_levels.get(zone, "N/A") if zone != "unassigned" else "N/A"
            lines.append(f"{port.full_name:<28}{zone:<20}{sec}")
        return "\n".join(lines)

    def _show_conn(self):
        lines = [
            f"{len(self.device.connections)} in use, {max(len(self.device.connections), 3)} most used"
        ]
        if not self.device.connections:
            lines.append("No active connections in state table.")
        else:
            for c in self.device.connections:
                lines.append(f"{c['protocol'].upper()} {c.get('out_zone','outside')} {c['dst_ip']} {c.get('in_zone','inside')} {c['src_ip']} idle 0:00:02 bytes 500 flags")
        return "\n".join(lines)

    def _show_running_config(self):
        if isinstance(self.device, Firewall):
            lines = [
                ": Saved",
                ":",
                "ASA Version 9.8(4)",
                "!",
                f"hostname {self.device.hostname}",
                "!"
            ]
            for p_name, port in self.ports_to_list():
                lines.append(f"interface {port.full_name}")
                zone = self.device.nameif.get(p_name)
                if zone:
                    lines.append(f" nameif {zone}")
                    sec = self.device.security_levels.get(zone)
                    if sec is not None:
                        lines.append(f" security-level {sec}")
                if port.ip_address:
                    lines.append(f" ip address {port.ip_address} {port.subnet_mask}")
                if port.is_shutdown:
                    lines.append(" shutdown")
                else:
                    lines.append(" no shutdown")
                lines.append("!")

            for acl_name, rules in self.device.access_lists.items():
                for r in rules:
                    lines.append(f"access-list {acl_name} extended {r['action']} {r['protocol']} {r['src']} {r['dst']}")

            for zone, dirs in self.device.access_groups.items():
                for d, acl in dirs.items():
                    lines.append(f"access-group {acl} {d} interface {zone}")

            for r in self.device.routes:
                if r.get("interface"):
                    lines.append(f"route {r['interface']} {r['network']} {r['mask']} {r['next_hop']}")
                else:
                    lines.append(f"route outside {r['network']} {r['mask']} {r['next_hop']}")

            lines.append("end")
            return "\n".join(lines)

        lines = [
            "Building configuration...",
            "Current configuration : 1024 bytes",
            "!",
            f"hostname {self.device.hostname}",
            "!"
        ]
        if hasattr(self.device, "dhcp_server") and self.device.dhcp_server:
            srv = self.device.dhcp_server
            for low, high in getattr(srv, "excluded_ranges", []):
                if low == high:
                    lines.append(f"ip dhcp excluded-address {low}")
                else:
                    lines.append(f"ip dhcp excluded-address {low} {high}")
            for pname, p in srv.pools.items():
                lines.append(f"ip dhcp pool {pname}")
                if p.network and p.subnet_mask:
                    lines.append(f" network {p.network} {p.subnet_mask}")
                if p.default_router:
                    lines.append(f" default-router {p.default_router}")
                if p.dns_servers:
                    lines.append(f" dns-server {' '.join(p.dns_servers)}")
                if p.lease_duration != 86400:
                    days = p.lease_duration // 86400
                    lines.append(f" lease {days}")
                lines.append("!")

        if isinstance(self.device, Switch):
            for vid, vdata in self.device.vlans.items():
                if vid != 1:
                    lines.extend([f"vlan {vid}", f" name {vdata['name']}", "!"])

        for p_name, port in self.ports_to_list():
            lines.append(f"interface {port.full_name}")
            if port.mode == "trunk":
                lines.append(" switchport mode trunk")
            elif isinstance(self.device, Switch) and port.access_vlan != 1:
                lines.append(f" switchport access vlan {port.access_vlan}")
            if getattr(port, "ip_method", "manual") == "DHCP":
                lines.append(" ip address dhcp")
            elif port.ip_address:
                lines.append(f" ip address {port.ip_address} {port.subnet_mask}")
            if isinstance(self.device, Router):
                if port.name in self.device.nat_inside_interfaces:
                    lines.append(" ip nat inside")
                if port.name in self.device.nat_outside_interfaces:
                    lines.append(" ip nat outside")
            if port.is_shutdown:
                lines.append(" shutdown")
            else:
                lines.append(" no shutdown")
            lines.append("!")

        if isinstance(self.device, Switch):
            if hasattr(self.device, "svis"):
                for vid, svi in sorted(self.device.svis.items()):
                    lines.append(f"interface {svi.full_name}")
                    if getattr(svi, "ip_method", "manual") == "DHCP":
                        lines.append(" ip address dhcp")
                    elif svi.ip_address:
                        lines.append(f" ip address {svi.ip_address} {svi.subnet_mask}")
                    if svi.is_shutdown:
                        lines.append(" shutdown")
                    else:
                        lines.append(" no shutdown")
                    lines.append("!")
            if getattr(self.device, "default_gateway", None):
                lines.append(f"ip default-gateway {self.device.default_gateway}")

        if isinstance(self.device, Router):
            for s_name, sub in self.device.subinterfaces.items():
                lines.append(f"interface {sub.full_name}")
                if sub.vlan_id:
                    lines.append(f" encapsulation dot1Q {sub.vlan_id}")
                if getattr(sub, "ip_method", "manual") == "DHCP":
                    lines.append(" ip address dhcp")
                elif sub.ip_address:
                    lines.append(f" ip address {sub.ip_address} {sub.subnet_mask}")
                lines.append("!")
            for acl_id, rules in self.device.access_lists.items():
                for r in rules:
                    wc_str = f" {r['wildcard']}" if r.get("wildcard") != "0.0.0.0" else ""
                    lines.append(f"access-list {acl_id} {r['action']} {r['source']}{wc_str}")
            for r in self.device.nat_rules:
                lines.append(f"ip nat inside source list {r['acl']} interface {r['interface']} {r['type']}")
            for r in self.device.routes:
                lines.append(f"ip route {r['network']} {r['mask']} {r['next_hop']}")

        lines.append("end")
        return "\n".join(lines)

    def _exec_host_command(self, cmd):
        tokens = cmd.split()
        if not tokens:
            return ""
        v = tokens[0].lower()
        if v == "ping":
            if len(tokens) < 2:
                return "Usage: ping [-c count] [-s size] [-i interval] [-I interface] <destination>"
            count = 4
            size = 56
            source_if = None
            target_ip = None

            idx = 1
            while idx < len(tokens):
                tok = tokens[idx]
                if tok == "-c" and idx + 1 < len(tokens):
                    try:
                        count = max(1, min(50, int(tokens[idx+1])))
                    except ValueError:
                        pass
                    idx += 2
                elif tok == "-s" and idx + 1 < len(tokens):
                    try:
                        size = max(0, min(65507, int(tokens[idx+1])))
                    except ValueError:
                        pass
                    idx += 2
                elif tok == "-I" and idx + 1 < len(tokens):
                    source_if = tokens[idx+1]
                    idx += 2
                elif tok.startswith("-"):
                    idx += 1
                else:
                    target_ip = tok
                    idx += 1

            if not target_ip:
                return "ping: usage error: Destination address required"

            res = self.packet_engine.simulate_ping(self.device, target_ip, count=count,
                                                   data_bytes=size, source_interface=source_if,
                                                   simulate_arp=False)
            out = [f"PING {target_ip} ({target_ip}) {size}({size+28}) bytes of data."]
            for i in range(count):
                if i < len(res.status_codes) and res.status_codes[i] == "!":
                    lat = res.rtt_ms[i] if i < len(res.rtt_ms) else 1.2
                    ttl = res.ttl_replies[i] if i < len(res.ttl_replies) else 64
                    out.append(f"{size+8} bytes from {target_ip}: icmp_seq={i+1} ttl={ttl} time={lat} ms")
                elif i < len(res.status_codes) and res.status_codes[i] == "A":
                    out.append(f"From {self.device.hostname}: Packet filtered by administrative policy")
                else:
                    out.append(f"From {self.device.hostname}: Destination Host Unreachable")

            out.append(f"--- {target_ip} ping statistics ---")
            total_time = int(count * 1000 + 4)
            out.append(f"{res.packets_sent} packets transmitted, {res.packets_received} received, {res.loss_percent}% packet loss, time {total_time}ms")
            if res.rtt_ms:
                min_r = round(min(res.rtt_ms), 3)
                avg_r = round(sum(res.rtt_ms)/len(res.rtt_ms), 3)
                max_r = round(max(res.rtt_ms), 3)
                mdev_r = res.mdev
                out.append(f"rtt min/avg/max/mdev = {min_r:.3f}/{avg_r:.3f}/{max_r:.3f}/{mdev_r:.3f} ms")
            return "\n".join(out)

        elif (v == "arp" and (len(tokens) == 1 or tokens[1] in ("-a", "-e"))) or (v == "ip" and len(tokens) > 1 and tokens[1] in ("neigh", "neighbor")):
            # Linux arp -a / ip neigh
            lines = []
            if hasattr(self.device, "arp_table") and self.device.arp_table:
                for ip, entry in self.device.arp_table.items():
                    mac = entry.get("mac", "02:00:1a:00:00:01")
                    lines.append(f"? ({ip}) at {mac} [ether] on eth0")
            if hasattr(self.device, "default_gateway") and self.device.default_gateway:
                gw = self.device.default_gateway
                if gw not in getattr(self.device, "arp_table", {}):
                    lines.append(f"gateway ({gw}) at 02:00:1a:00:00:01 [ether] on eth0")
            if not lines:
                return "No ARP entries found."
            return "\n".join(lines)

        elif v == "traceroute" and len(tokens) > 1:
            target_ip = tokens[1]
            hops = self.packet_engine.simulate_traceroute(self.device, target_ip)
            lines = [f"traceroute to {target_ip} ({target_ip}), 30 hops max, 60 byte packets"]
            for h in hops:
                if not h["rtts"]:
                    lines.append(f" {h['hop']:>2}  * * *")
                else:
                    rtt_strs = "  ".join(f"{r:.3f} ms" for r in h["rtts"])
                    lines.append(f" {h['hop']:>2}  {h['ip']} ({h['ip']})  {rtt_strs}")
            return "\n".join(lines)

        elif v in ("ifconfig", "ip") and (len(tokens) == 1 or tokens[1].lower() in ("a", "addr")):
            p = self.device.eth0
            ip = p.ip_address if p and p.ip_address else "unassigned"
            mask = p.subnet_mask if p and p.subnet_mask else "unassigned"
            gw = self.device.default_gateway or "none"
            state = "UP" if p and p.is_link_up else "DOWN"
            return (f"eth0: flags=4163<{state},BROADCAST,RUNNING,MULTICAST>  mtu 1500\n"
                    f"      inet {ip}  netmask {mask}\n"
                    f"      default gateway: {gw}  status: {state}")

        elif v == "dhclient":
            if len(tokens) > 1 and tokens[1] == "-r":
                target_if = tokens[2] if len(tokens) > 2 else "eth0"
                ok, msg = self.device.release_dhcp(target_if)
                if ok:
                    return "Killed old client process\nInternet Systems Consortium DHCP Client released IP."
                return f"dhclient -r failed: {msg}"
            else:
                target_if = tokens[1] if len(tokens) > 1 and not tokens[1].startswith("-") else "eth0"
                ok, msg = self.device.request_dhcp(target_if)
                if ok:
                    p = self.device.ports.get(target_if)
                    ip = p.ip_address if p else ""
                    server_id = getattr(msg, "server_id", "255.255.255.255")
                    lease_time = getattr(msg, "lease_time", 86400)
                    return (f"DHCPDISCOVER on {target_if} to 255.255.255.255 port 67...\n"
                            f"DHCPOFFER of {ip} from {server_id}\n"
                            f"DHCPREQUEST for {ip} on {target_if} to 255.255.255.255 port 67...\n"
                            f"DHCPACK of {ip} from {server_id}\n"
                            f"bound to {ip} -- renewal in {lease_time} seconds.")
                return f"dhclient: {msg}"

        elif v in ("help", "?", "--help"):
            return (
                "Supported Linux shell commands:\n"
                "  ping [-c N] <ip>     Send ICMP ECHO_REQUEST to network hosts\n"
                "  traceroute <ip>      Print the route packets trace to network host\n"
                "  arp -a               Display current ARP table\n"
                "  ifconfig             Display network interface configuration\n"
                "  ip addr              Display network interface addresses and status\n"
                "  dhclient             Acquire dynamic IP address via DHCP\n"
                "  dhclient -r          Release acquired dynamic DHCP lease\n"
                "  exit                 Close the terminal session"
            )
        return f"bash: {tokens[0]}: command not found"

    def parse_ping_job(self, cmd_line):
        """
        Parses cmd_line to check if it represents a ping invocation.
        Returns (is_ping: bool, params: dict or None).
        Used by TerminalUI for real-time progressive packet streaming.
        """
        line = cmd_line.strip()
        tokens = line.split()
        if not tokens:
            return False, None

        # Check if executed via 'do ping ...' in config modes
        if tokens[0].lower() == "do" and len(tokens) > 1:
            tokens = tokens[1:]

        if tokens[0].lower() != "ping":
            return False, None

        is_linux = isinstance(self.device, Host)
        if is_linux:
            if len(tokens) < 2:
                return False, None
            count = 4
            size = 56
            source_if = None
            target_ip = None
            idx = 1
            while idx < len(tokens):
                tok = tokens[idx]
                if tok == "-c" and idx + 1 < len(tokens):
                    try:
                        count = max(1, min(50, int(tokens[idx+1])))
                    except ValueError:
                        pass
                    idx += 2
                elif tok == "-s" and idx + 1 < len(tokens):
                    try:
                        size = max(0, min(65507, int(tokens[idx+1])))
                    except ValueError:
                        pass
                    idx += 2
                elif tok == "-I" and idx + 1 < len(tokens):
                    source_if = tokens[idx+1]
                    idx += 2
                elif tok.startswith("-"):
                    idx += 1
                else:
                    target_ip = tok
                    idx += 1
            if not target_ip:
                return False, None

            return True, {
                "target_ip": target_ip,
                "count": count,
                "size": size,
                "timeout": 2,
                "source_if": source_if,
                "type": "linux",
                "header_lines": [f"PING {target_ip} ({target_ip}) {size}({size+28}) bytes of data."]
            }
        else:
            # Cisco IOS / ASA
            if len(tokens) < 2:
                return False, None
            target_ip = tokens[1]
            count = 5
            size = 100
            timeout = 2
            source_if = None
            idx = 2
            while idx < len(tokens):
                tok = tokens[idx].lower()
                if tok in ("repeat", "count") and idx + 1 < len(tokens):
                    try:
                        count = max(1, min(100, int(tokens[idx+1])))
                    except ValueError:
                        pass
                    idx += 2
                elif tok == "size" and idx + 1 < len(tokens):
                    try:
                        size = max(36, min(18024, int(tokens[idx+1])))
                    except ValueError:
                        pass
                    idx += 2
                elif tok == "timeout" and idx + 1 < len(tokens):
                    try:
                        timeout = max(1, min(30, int(tokens[idx+1])))
                    except ValueError:
                        pass
                    idx += 2
                elif tok == "source" and idx + 1 < len(tokens):
                    source_if = tokens[idx+1]
                    idx += 2
                else:
                    idx += 1

            return True, {
                "target_ip": target_ip,
                "count": count,
                "size": size,
                "timeout": timeout,
                "source_if": source_if,
                "type": "cisco",
                "header_lines": [
                    "Type escape sequence to abort.",
                    f"Sending {count}, {size}-byte ICMP Echos to {target_ip}, timeout is {timeout} seconds:"
                ]
            }
