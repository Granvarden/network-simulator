"""
network/device.py - Base Device, Interface/Port models, and LED Status
"""

import time

class LEDState:
    OFF = "OFF"
    AMBER = "AMBER"          # Negotiating / Error-disabled / Shut
    GREEN = "GREEN"          # Up / Link established
    BLINK_GREEN = "BLINK_GREEN"  # Active data traffic

class Port:
    def __init__(self, device, name, port_type="RJ45", port_index=0):
        self.device = device
        self.name = name  # e.g. "g0/1"
        self.full_name = self._expand_name(name)
        self.port_type = port_type  # RJ45, FIBER, CONSOLE
        self.port_index = port_index

        # Layer 1 / Physical
        self.is_shutdown = True   # Cisco interfaces start administratively down
        self.cable = None
        self.speed_mbps = 1000
        self.duplex = "Full"

        # Layer 2 / Switchport
        self.mode = "access"      # "access" or "trunk"
        self.access_vlan = 1
        self.trunk_allowed_vlans = {1}  # default vlan 1
        self.native_vlan = 1

        # Layer 3 / IP
        self.ip_address = None
        self.subnet_mask = None
        self.mac_address = f"02:00:{hash(device.id)%255:02x}:{port_index:02x}:00:01"

        # LED State
        self.last_traffic_time = 0.0

    def _expand_name(self, name):
        lower = name.lower()
        if lower.startswith("g"):
            return "GigabitEthernet" + name[1:]
        elif lower.startswith("f"):
            return "FastEthernet" + name[1:]
        elif lower.startswith("con"):
            return "Console 0"
        return name

    @property
    def is_link_up(self):
        if self.is_shutdown:
            return False
        if not self.cable:
            return False
        if self.cable.is_damaged:
            return False
        peer = self.cable.get_peer_port(self)
        if not peer:
            return False
        if peer.is_shutdown:
            return False
        return True

    def get_led_state(self, current_time):
        if not self.cable:
            return LEDState.OFF
        if self.is_shutdown or self.cable.is_damaged:
            return LEDState.AMBER
        peer = self.cable.get_peer_port(self)
        if not peer or peer.is_shutdown:
            return LEDState.AMBER
        # Blink when active packet traffic was detected within 0.3s
        if current_time - self.last_traffic_time < 0.35:
            # Alternate on/off every 80ms
            blink = int((current_time - self.last_traffic_time) * 12) % 2 == 0
            return LEDState.BLINK_GREEN if blink else LEDState.OFF
        return LEDState.GREEN

    def trigger_traffic(self):
        self.last_traffic_time = time.time()

    def connect_cable(self, cable):
        self.cable = cable

    def get_world_pos(self):
        """Returns 3D world position coordinates (x, y, z) of this port."""
        if not self.device:
            return (0.0, 0.0, 0.0)
        return self.device.get_port_world_pos(self.name, self.port_index)


class BaseDevice:
    def __init__(self, id, hostname, device_type="device", rack_id=1, u_slot=10):
        self.id = id
        self.hostname = hostname
        self.device_type = device_type  # "router", "switch", "server", "laptop"
        self.rack_id = rack_id
        self.u_slot = u_slot  # 1 to 42U in standard 19-inch rack
        self.is_powered = True
        self.ports = {}  # name -> Port
        self.arp_table = {}  # ip -> {"mac": str, "interface": str, "age_min": int, "type": str}
        self.routing_table = []  # list of routes

        # 3D Transform in Datacenter space
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.pos_z = 0.0
        self.width = 0.48   # 19 inch = ~0.482m
        self.height = 0.044 * 1  # 1U = ~0.044m
        self.depth = 0.6    # ~60cm rack depth

    def add_arp_entry(self, ip, mac, interface="Vlan1", age=0):
        """Add or update an entry in the ARP table."""
        self.arp_table[ip] = {
            "mac": mac,
            "interface": interface,
            "age_min": age,
            "type": "ARPA"
        }

    def lookup_arp(self, ip):
        """Lookup an IP in the ARP table."""
        return self.arp_table.get(ip)

    def clear_arp(self):
        """Flush the ARP table."""
        self.arp_table.clear()

    def add_port(self, name, port_type="RJ45"):
        idx = len(self.ports)
        port = Port(self, name, port_type=port_type, port_index=idx)
        self.ports[name] = port
        return port

    def get_port(self, name):
        """Lookup port by short or full name (e.g. g0/1 or GigabitEthernet0/1)."""
        clean = name.strip().lower()
        for p_name, port in self.ports.items():
            if p_name.lower() == clean or port.full_name.lower() == clean:
                return port
        # Also check abbreviations like "int g0/1"
        for p_name, port in self.ports.items():
            if p_name.lower().replace("gigabitethernet", "g") == clean.replace("gigabitethernet", "g"):
                return port
        return None

    def get_port_local_pos(self, port_name, port_index=0):
        """Default local offset (x, y, z) relative to device center."""
        num_ports = max(1, len(self.ports))
        spacing = 0.035
        total_span = (num_ports - 1) * spacing
        start_x = -total_span / 2.0
        lx = start_x + port_index * spacing
        ly = 0.0
        lz = (self.depth / 2.0) + 0.008
        return (lx, ly, lz)

    def get_port_world_pos(self, port_name_or_index=0, port_index=None):
        """Calculates exact 3D world coordinates on the front face of this device."""
        if isinstance(port_name_or_index, int):
            port_index = port_name_or_index
            port_name = list(self.ports.keys())[port_index] if port_index < len(self.ports) else ""
        else:
            port_name = port_name_or_index
            if port_index is None:
                p = self.ports.get(port_name)
                port_index = p.port_index if p else 0

        lx, ly, lz = self.get_port_local_pos(port_name, port_index)
        return (self.pos_x + lx, self.pos_y + ly, self.pos_z + lz)
