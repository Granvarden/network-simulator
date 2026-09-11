"""
network/dhcp.py - Dynamic Host Configuration Protocol (DHCP) Engine
Implements RFC 2131 compliant DHCP Server, Client, Pools, Leases, Excluded Addresses,
DORA State Machine, Binding Table, Statistics, and VLAN-aware IP allocation.
"""

import time
from .router import is_ip_in_subnet, ip_to_int, int_to_ip, is_valid_ipv4, is_valid_netmask

class DHCPMessageType:
    DISCOVER = "DHCPDISCOVER"
    OFFER = "DHCPOFFER"
    REQUEST = "DHCPREQUEST"
    ACK = "DHCPACK"
    NAK = "DHCPNAK"
    RELEASE = "DHCPRELEASE"

class DHCPClientState:
    INIT = "INIT"
    SELECTING = "SELECTING"
    REQUESTING = "REQUESTING"
    BOUND = "BOUND"
    RENEWING = "RENEWING"

class DHCPMessage:
    def __init__(self, msg_type, xid=1, client_mac="", ciaddr="0.0.0.0",
                 yiaddr="0.0.0.0", siaddr="0.0.0.0", subnet_mask="255.255.255.0",
                 router=None, dns_server="8.8.8.8", lease_time=86400,
                 hostname="", vlan_id=1, server_id=None):
        self.msg_type = msg_type
        self.xid = xid
        self.client_mac = client_mac
        self.ciaddr = ciaddr          # Client IP (if known / renewing)
        self.yiaddr = yiaddr          # 'Your' (Client) IP assigned/offered
        self.siaddr = siaddr          # Next server IP
        self.subnet_mask = subnet_mask
        self.router = router          # Default gateway IP
        self.dns_server = dns_server  # DNS server IP
        self.lease_time = lease_time  # Lease duration in seconds
        self.hostname = hostname      # Client hostname
        self.vlan_id = vlan_id        # VLAN ID
        self.server_id = server_id or siaddr  # DHCP Server Identifier IP

    def __repr__(self):
        return f"<DHCPMessage {self.msg_type} xid={self.xid} mac={self.client_mac} yiaddr={self.yiaddr}>"


class DHCPPool:
    def __init__(self, name, network="192.168.1.0", subnet_mask="255.255.255.0",
                 default_router=None, dns_server="8.8.8.8", lease_duration=86400):
        self.name = name
        self.network = network
        self.subnet_mask = subnet_mask
        self.default_router = default_router
        self._dns_servers = [dns_server] if dns_server else ["8.8.8.8"]
        self.lease_duration = int(lease_duration)  # in seconds

    @property
    def dns_server(self):
        return self._dns_servers[0] if self._dns_servers else "8.8.8.8"

    @dns_server.setter
    def dns_server(self, val):
        if isinstance(val, list):
            self._dns_servers = val
        elif val:
            self._dns_servers = [val]
        else:
            self._dns_servers = []

    @property
    def dns_servers(self):
        return self._dns_servers

    @dns_servers.setter
    def dns_servers(self, val):
        if isinstance(val, list):
            self._dns_servers = val
        elif val:
            self._dns_servers = [val]
        else:
            self._dns_servers = []

    @property
    def lease_time_seconds(self):
        return self.lease_duration

    @lease_time_seconds.setter
    def lease_time_seconds(self, val):
        self.lease_duration = int(val)

    def is_ip_in_pool(self, ip_str):
        """Checks if ip_str belongs to this pool's network and is a usable host address."""
        if not is_valid_ipv4(ip_str):
            return False
        if not is_ip_in_subnet(ip_str, self.network, self.subnet_mask):
            return False

        # Exclude network address and broadcast address
        net_int = ip_to_int(self.network)
        mask_int = ip_to_int(self.subnet_mask)
        broadcast_int = net_int | (0xFFFFFFFF ^ mask_int)
        val = ip_to_int(ip_str)

        if val == net_int or val == broadcast_int:
            return False
        return True

    def get_total_addresses(self):
        """Returns total number of usable host addresses in this subnet."""
        mask_int = ip_to_int(self.subnet_mask)
        wildcard = 0xFFFFFFFF ^ mask_int
        # Usable addresses: wildcard - 1 (excluding network 0 and broadcast 1s)
        return max(0, wildcard - 1)

    def get_usable_ip_range(self):
        """Returns (first_usable_ip, last_usable_ip) tuple or (None, None)."""
        net_int = ip_to_int(self.network)
        mask_int = ip_to_int(self.subnet_mask)
        broadcast_int = net_int | (0xFFFFFFFF ^ mask_int)
        if broadcast_int - net_int <= 1:
            return None, None
        return int_to_ip(net_int + 1), int_to_ip(broadcast_int - 1)

    def get_all_host_ips(self):
        """Generates list of all usable host IPs in sequential order."""
        net_int = ip_to_int(self.network)
        mask_int = ip_to_int(self.subnet_mask)
        broadcast_int = net_int | (0xFFFFFFFF ^ mask_int)
        ips = []
        for i in range(net_int + 1, broadcast_int):
            ips.append(int_to_ip(i))
        return ips

    def get_available_ips(self, excluded_ips, leased_ips):
        """Returns ordered list of available IPs in this pool."""
        all_hosts = self.get_all_host_ips()
        available = []
        for ip in all_hosts:
            if ip not in excluded_ips and ip not in leased_ips:
                available.append(ip)
        return available


class DHCPLease:
    def __init__(self, ip_address, mac_address, hostname, pool_name,
                 lease_start=None, lease_duration=86400, state="BOUND"):
        self.ip_address = ip_address
        self.mac_address = mac_address
        self.hostname = hostname
        self.pool_name = pool_name
        self.lease_start = lease_start or time.time()
        self.lease_duration = lease_duration
        self.state = state

    @property
    def lease_expiration(self):
        exp_time = self.lease_start + self.lease_duration
        return time.strftime("%b %d %Y %H:%M %p", time.localtime(exp_time))

    def __repr__(self):
        return f"<DHCPLease {self.ip_address} -> {self.mac_address} ({self.state})>"


class DHCPServer:
    def __init__(self, device):
        self.device = device
        self.pools = {}                 # pool_name -> DHCPPool
        self.excluded_addresses = set() # set of IP strings
        self.excluded_ranges = []       # list of (low_ip, high_ip) tuples
        self.binding_table = {}         # ip_address -> DHCPLease
        self.mac_to_ip = {}             # mac_address -> ip_address
        self.statistics = {
            "discover": 0,
            "offer": 0,
            "request": 0,
            "ack": 0,
            "nak": 0,
            "release": 0
        }

    def add_pool(self, name, network="192.168.1.0", subnet_mask="255.255.255.0",
                 default_router=None, dns_server="8.8.8.8", lease_duration=86400):
        pool = DHCPPool(name, network, subnet_mask, default_router, dns_server, lease_duration)
        self.pools[name] = pool
        return pool

    def create_pool(self, name):
        if name in self.pools:
            return self.pools[name]
        pool = DHCPPool(name)
        self.pools[name] = pool
        return pool

    def delete_pool(self, name):
        return self.remove_pool(name)

    def get_pool(self, name):
        return self.pools.get(name)

    def remove_pool(self, name):
        if name in self.pools:
            del self.pools[name]
            # Remove associated leases
            to_del = [ip for ip, lease in self.binding_table.items() if lease.pool_name == name]
            for ip in to_del:
                mac = self.binding_table[ip].mac_address
                del self.binding_table[ip]
                self.mac_to_ip.pop(mac, None)
            return True
        return False

    def add_excluded_address(self, low_ip, high_ip=None):
        """Adds a single IP or a range [low_ip, high_ip] to excluded addresses."""
        if not is_valid_ipv4(low_ip):
            return False
        if high_ip is None:
            self.excluded_addresses.add(low_ip)
            self.excluded_ranges.append((low_ip, low_ip))
            return True
        if not is_valid_ipv4(high_ip):
            return False
        low_val = ip_to_int(low_ip)
        high_val = ip_to_int(high_ip)
        if low_val > high_val:
            low_val, high_val = high_val, low_val
            low_ip, high_ip = high_ip, low_ip
        for val in range(low_val, high_val + 1):
            self.excluded_addresses.add(int_to_ip(val))
        self.excluded_ranges.append((low_ip, high_ip))
        return True

    def remove_excluded_address(self, low_ip, high_ip=None):
        """Removes a single IP or range from excluded addresses."""
        h_ip = high_ip or low_ip
        if (low_ip, h_ip) in self.excluded_ranges:
            self.excluded_ranges.remove((low_ip, h_ip))
        elif (h_ip, low_ip) in self.excluded_ranges:
            self.excluded_ranges.remove((h_ip, low_ip))

        if high_ip is None:
            self.excluded_addresses.discard(low_ip)
            return True
        low_val = ip_to_int(low_ip)
        high_val = ip_to_int(high_ip)
        if low_val > high_val:
            low_val, high_val = high_val, low_val
        for val in range(low_val, high_val + 1):
            self.excluded_addresses.discard(int_to_ip(val))
        return True

    def find_pool_for_context(self, in_subnet=None, in_vlan=1, in_ip=None):
        """
        Finds the appropriate DHCP Pool for an incoming request.
        Matches against incoming interface IP, subnet, or pool's default router.
        """
        # 1. If explicit in_ip or in_subnet provided, match pool network
        if in_ip:
            for pool in self.pools.values():
                if pool.is_ip_in_pool(in_ip):
                    return pool
        if in_subnet:
            for pool in self.pools.values():
                if pool.network == in_subnet:
                    return pool

        # 2. Check server device interfaces for matching subnet
        # For Router: inspect ports and subinterfaces
        if hasattr(self.device, "ports"):
            for port in self.device.ports.values():
                if port.ip_address and port.subnet_mask:
                    for pool in self.pools.values():
                        if is_ip_in_subnet(port.ip_address, pool.network, pool.subnet_mask):
                            return pool

        if hasattr(self.device, "subinterfaces"):
            for sub in self.device.subinterfaces.values():
                if sub.ip_address and sub.subnet_mask:
                    if sub.vlan_id is None or sub.vlan_id == in_vlan:
                        for pool in self.pools.values():
                            if is_ip_in_subnet(sub.ip_address, pool.network, pool.subnet_mask):
                                return pool

        # For Switch: inspect SVIs
        if hasattr(self.device, "svis"):
            svi = self.device.svis.get(in_vlan)
            if svi and svi.ip_address and svi.subnet_mask:
                for pool in self.pools.values():
                    if is_ip_in_subnet(svi.ip_address, pool.network, pool.subnet_mask):
                        return pool
            # Fallback across all active SVIs
            for s in self.device.svis.values():
                if s.ip_address and s.subnet_mask:
                    for pool in self.pools.values():
                        if is_ip_in_subnet(s.ip_address, pool.network, pool.subnet_mask):
                            return pool

        # 3. Fallback: If only 1 pool exists on server
        if len(self.pools) == 1:
            return list(self.pools.values())[0]

        return None

    def handle_discover(self, msg, in_subnet=None, in_vlan=1, in_ip=None, server_ip=None):
        """Processes DHCPDISCOVER and generates DHCPOFFER if available."""
        self.statistics["discover"] += 1
        pool = self.find_pool_for_context(in_subnet=in_subnet, in_vlan=in_vlan, in_ip=in_ip)
        if not pool:
            return None

        # Check if client MAC already has an active lease in this pool
        existing_ip = self.mac_to_ip.get(msg.client_mac)
        offered_ip = None
        if existing_ip and pool.is_ip_in_pool(existing_ip):
            offered_ip = existing_ip
        else:
            # Pick first available IP
            available_ips = pool.get_available_ips(self.excluded_addresses, set(self.binding_table.keys()))
            if not available_ips:
                return None  # Pool exhausted
            offered_ip = available_ips[0]

        s_ip = server_ip or pool.default_router or "192.168.1.1"
        self.statistics["offer"] += 1
        offer = DHCPMessage(
            msg_type=DHCPMessageType.OFFER,
            xid=msg.xid,
            client_mac=msg.client_mac,
            yiaddr=offered_ip,
            siaddr=s_ip,
            subnet_mask=pool.subnet_mask,
            router=pool.default_router,
            dns_server=pool.dns_server,
            lease_time=pool.lease_duration,
            vlan_id=in_vlan,
            server_id=s_ip
        )
        return offer

    def handle_request(self, msg, in_subnet=None, in_vlan=1, in_ip=None, server_ip=None):
        """Processes DHCPREQUEST and generates DHCPACK or DHCPNAK."""
        self.statistics["request"] += 1
        pool = self.find_pool_for_context(in_subnet=in_subnet, in_vlan=in_vlan, in_ip=in_ip)
        requested_ip = msg.yiaddr if (msg.yiaddr and msg.yiaddr != "0.0.0.0") else msg.ciaddr
        s_ip = server_ip or (pool.default_router if pool else "192.168.1.1")

        # Validate pool and requested IP
        if not pool or not pool.is_ip_in_pool(requested_ip):
            self.statistics["nak"] += 1
            return DHCPMessage(
                msg_type=DHCPMessageType.NAK,
                xid=msg.xid,
                client_mac=msg.client_mac,
                siaddr=s_ip,
                vlan_id=in_vlan,
                server_id=s_ip
            )

        # Check if requested IP is excluded
        if requested_ip in self.excluded_addresses:
            self.statistics["nak"] += 1
            return DHCPMessage(
                msg_type=DHCPMessageType.NAK,
                xid=msg.xid,
                client_mac=msg.client_mac,
                siaddr=s_ip,
                vlan_id=in_vlan,
                server_id=s_ip
            )

        # Check if requested IP is leased to another MAC
        current_lease = self.binding_table.get(requested_ip)
        if current_lease and current_lease.mac_address != msg.client_mac:
            self.statistics["nak"] += 1
            return DHCPMessage(
                msg_type=DHCPMessageType.NAK,
                xid=msg.xid,
                client_mac=msg.client_mac,
                siaddr=s_ip,
                vlan_id=in_vlan,
                server_id=s_ip
            )

        # Successful binding
        lease = DHCPLease(
            ip_address=requested_ip,
            mac_address=msg.client_mac,
            hostname=msg.hostname or f"Client-{msg.client_mac[-5:]}",
            pool_name=pool.name,
            lease_start=time.time(),
            lease_duration=pool.lease_duration,
            state="BOUND"
        )
        self.binding_table[requested_ip] = lease
        self.mac_to_ip[msg.client_mac] = requested_ip
        self.statistics["ack"] += 1

        ack = DHCPMessage(
            msg_type=DHCPMessageType.ACK,
            xid=msg.xid,
            client_mac=msg.client_mac,
            yiaddr=requested_ip,
            siaddr=s_ip,
            subnet_mask=pool.subnet_mask,
            router=pool.default_router,
            dns_server=pool.dns_server,
            lease_time=pool.lease_duration,
            vlan_id=in_vlan,
            server_id=s_ip
        )
        return ack

    def handle_release(self, msg):
        """Processes DHCPRELEASE and frees the lease."""
        self.statistics["release"] += 1
        rel_ip = msg.ciaddr if (msg.ciaddr and msg.ciaddr != "0.0.0.0") else msg.yiaddr
        if rel_ip in self.binding_table:
            lease = self.binding_table[rel_ip]
            if lease.mac_address == msg.client_mac:
                del self.binding_table[rel_ip]
                self.mac_to_ip.pop(msg.client_mac, None)
                return True
        # Check if MAC has any lease
        if msg.client_mac in self.mac_to_ip:
            ip = self.mac_to_ip.pop(msg.client_mac)
            self.binding_table.pop(ip, None)
            return True
        return False


class DHCPClient:
    def __init__(self, device):
        self.device = device
        self.state = DHCPClientState.INIT
        self.lease = None
        self.current_xid = 1000

    def start_dhcp(self, port_name="eth0"):
        """Initiates DHCP DORA handshake via PacketEngine."""
        from .packet_engine import PacketEngine
        pe = PacketEngine.get_instance()
        port = self.device.get_port(port_name) if hasattr(self.device, "get_port") else getattr(self.device, port_name, None)
        if not port:
            return False, "Interface not found"
        return pe.simulate_dhcp_dora(self.device, port)

    def release_dhcp(self, port_name="eth0"):
        """Releases current DHCP lease and resets interface IP."""
        from .packet_engine import PacketEngine
        pe = PacketEngine.get_instance()
        port = self.device.get_port(port_name) if hasattr(self.device, "get_port") else getattr(self.device, port_name, None)
        if not port:
            return False, "Interface not found"
        return pe.simulate_dhcp_release(self.device, port)
