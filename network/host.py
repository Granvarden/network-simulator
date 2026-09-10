"""
network/host.py - End Host models (Servers, Workstations, Engineer Laptops)
Supports dual-OS engineer laptops (Windows 11 and Ubuntu 22.04 LTS) with
both Cat6 Ethernet (eth0) and Serial Console Rollover (con0) ports.
"""

from .device import BaseDevice

class Host(BaseDevice):
    def __init__(self, id, hostname="Server", device_type="server", rack_id=1, u_slot=14, os_type="ubuntu"):
        super().__init__(id, hostname, device_type=device_type, rack_id=rack_id, u_slot=u_slot)
        self.os_type = os_type.lower()  # "windows" or "ubuntu"
        self.default_gateway = None
        self.dns_server = "8.8.8.8"
        self.dhcp_enabled = False

        if self.device_type == "laptop":
            # Compact 15.6" Laptop Dimensions
            self.width = 0.36
            self.height = 0.18
            self.depth = 0.28

            # Data Port (eth0 - Cat6 RJ45 Gigabit Ethernet) on left side
            eth0 = self.add_port("eth0", port_type="RJ45")
            eth0.is_shutdown = False

            # Management Port (con0 - Rollover Serial Console) on right side
            con0 = self.add_port("con0", port_type="CONSOLE")
            con0.is_shutdown = False
        elif self.device_type in ("isp_gateway", "isp") or "isp" in self.hostname.lower():
            # 1U Carrier Optical Demarcation & Provider Edge Gateway
            self.width = 0.48
            self.height = 0.044 * 1
            self.depth = 0.38
            eth0 = self.add_port("eth0", port_type="RJ45")
            eth0.is_shutdown = False
        else:
            # 2U Rack Server
            self.height = 0.044 * 2
            eth0 = self.add_port("eth0", port_type="RJ45")
            eth0.is_shutdown = False

    @property
    def eth0(self):
        return self.ports.get("eth0")

    @property
    def con0(self):
        return self.ports.get("con0")

    def get_port_local_pos(self, port_name, port_index=0):
        """Returns exact local coordinates (x, y, z) on Host/Server/Laptop/ISP Gateway."""
        clean = port_name.lower()
        if self.device_type == "laptop":
            # Left side for eth0 (RJ45), right side for con0 (Console USB/Serial)
            if "con" in clean:
                return (0.181, 0.009, 0.04)   # Right chassis flank
            return (-0.181, 0.009, 0.04)      # Left chassis flank

        if self.device_type in ("isp_gateway", "isp") or "isp" in self.hostname.lower():
            # 1U Carrier Demarcation: Customer Handoff RJ45 Port (eth0)
            front_z = (self.depth / 2.0) + 0.007
            return (0.04, 0.0, front_z)

        # Rack Server: front face
        front_z = (self.depth / 2.0) + 0.007
        return (0.14, -0.024, front_z)

    def configure_ip(self, ip, mask, gateway=None, dns=None):
        port = self.eth0
        if port:
            port.ip_address = ip
            port.subnet_mask = mask
        if gateway:
            self.default_gateway = gateway
        if dns:
            self.dns_server = dns
