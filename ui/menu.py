"""
ui/menu.py - Main Menu, Pause Dialog, Controls Cheatsheet, 2D Topology Visualizer, and Rack Device Manager
"""

import os
import json
import pygame
import math
from network.switch import Switch
from network.router import Router
from network.host import Host
from network.firewall import Firewall
from ui.topology_2d import Topology2D

SHOWCASE_COMMANDS = {
    "router": {
        "categories": ["ALL", "IP & INTERFACES", "STATIC ROUTING", "OSPF ROUTING", "RIP ROUTING", "ROUTER-ON-A-STICK", "DHCP SERVER", "NAT & PAT", "SHOW & DIAG"],
        "commands": [
            {
                "cmd": "interface <name>",
                "cat": "IP & INTERFACES",
                "desc": "Select network interface to configure (e.g. interface g0/0)",
                "desc_th": "เลือก Interface เพื่อเข้าสู่โหมดปรับแต่งพอร์ต เช่น interface g0/0",
                "example": "Router(config)# interface GigabitEthernet0/0"
            },
            {
                "cmd": "ip address <ip> <mask>",
                "cat": "IP & INTERFACES",
                "desc": "Assign IPv4 address and subnet mask to the selected interface",
                "desc_th": "กำหนดหมายเลข IPv4 Address และ Subnet Mask ให้กับพอร์ต",
                "example": "Router(config-if)# ip address 192.168.1.1 255.255.255.0"
            },
            {
                "cmd": "no shutdown",
                "cat": "IP & INTERFACES",
                "desc": "Bring interface administratively UP and enable physical link",
                "desc_th": "เปิดใช้งาน Interface ให้สถานะเปลี่ยนเป็น UP",
                "example": "Router(config-if)# no shutdown"
            },
            {
                "cmd": "description <text>",
                "cat": "IP & INTERFACES",
                "desc": "Add descriptive label explaining port purpose or connected link",
                "desc_th": "ใส่ข้อความระบุหน้าที่ของพอร์ตหรืออุปกรณ์ปลายทาง",
                "example": "Router(config-if)# description WAN Uplink to ISP Gateway"
            },
            {
                "cmd": "ip route 0.0.0.0 0.0.0.0 <gw>",
                "cat": "STATIC ROUTING",
                "desc": "Configure default static route (Gateway of Last Resort to Internet)",
                "desc_th": "กำหนด Default Route ส่งข้อมูลออก Internet ผ่าน Next-Hop",
                "example": "Router(config)# ip route 0.0.0.0 0.0.0.0 203.0.113.1"
            },
            {
                "cmd": "ip route <dest> <mask> <gw>",
                "cat": "STATIC ROUTING",
                "desc": "Add static route for a specific destination subnet via next-hop IP",
                "desc_th": "กำหนดเส้นทาง Static Route ไปยัง Subnet ปลายทางที่ต้องการ",
                "example": "Router(config)# ip route 10.10.20.0 255.255.255.0 192.168.1.254"
            },
            {
                "cmd": "router ospf <process-id>",
                "cat": "OSPF ROUTING",
                "desc": "Enable OSPF link-state dynamic routing process",
                "desc_th": "เปิดใช้งาน OSPF Dynamic Routing Process บนเราเตอร์",
                "example": "Router(config)# router ospf 1"
            },
            {
                "cmd": "network <net> <wildcard> area <area>",
                "cat": "OSPF ROUTING",
                "desc": "Advertise subnet and wildcard mask into an OSPF area",
                "desc_th": "ประกาศ Subnet และ Wildcard Mask เข้า OSPF Area (เช่น Area 0)",
                "example": "Router(config-router)# network 192.168.1.0 0.0.0.255 area 0"
            },
            {
                "cmd": "router-id <ip>",
                "cat": "OSPF ROUTING",
                "desc": "Manually set 32-bit unique OSPF Router Identifier",
                "desc_th": "กำหนดหมายเลข OSPF Router ID ประจำเครื่องเราเตอร์",
                "example": "Router(config-router)# router-id 1.1.1.1"
            },
            {
                "cmd": "router rip",
                "cat": "RIP ROUTING",
                "desc": "Enable Routing Information Protocol (RIP) dynamic routing",
                "desc_th": "เปิดใช้งาน RIP Dynamic Routing Process บนเราเตอร์",
                "example": "Router(config)# router rip"
            },
            {
                "cmd": "version 2",
                "cat": "RIP ROUTING",
                "desc": "Configure RIP to Version 2 supporting CIDR and subnet masks",
                "desc_th": "ปรับโหมดการทำงานเป็น RIPv2 เพื่อรองรับ Classless CIDR",
                "example": "Router(config-router)# version 2"
            },
            {
                "cmd": "network <major-net>",
                "cat": "RIP ROUTING",
                "desc": "Advertise major network boundary in RIP distance-vector routing",
                "desc_th": "ประกาศ Classful Network Boundary เข้าสู่โพรโทคอล RIP",
                "example": "Router(config-router)# network 10.0.0.0"
            },
            {
                "cmd": "interface <name>.<sub_id>",
                "cat": "ROUTER-ON-A-STICK",
                "desc": "Create a virtual subinterface for inter-VLAN routing (Router-on-a-Stick)",
                "desc_th": "สร้าง Subinterface เสมือนสำหรับ Inter-VLAN Routing",
                "example": "Router(config)# interface GigabitEthernet0/1.10"
            },
            {
                "cmd": "encapsulation dot1Q <vlan_id>",
                "cat": "ROUTER-ON-A-STICK",
                "desc": "Bind IEEE 802.1Q VLAN encapsulation tag to the subinterface",
                "desc_th": "ผูก Tag 802.1Q VLAN กับ Subinterface",
                "example": "Router(config-subif)# encapsulation dot1Q 10"
            },
            {
                "cmd": "ip dhcp pool <name>",
                "cat": "DHCP SERVER",
                "desc": "Create an IPv4 DHCP address pool for automated client allocation",
                "desc_th": "สร้าง DHCP Address Pool สำหรับแจก IP ให้ Client อัตโนมัติ",
                "example": "Router(config)# ip dhcp pool POOL_LAN_10"
            },
            {
                "cmd": "network <net> <mask>",
                "cat": "DHCP SERVER",
                "desc": "Define assignable network subnet and mask for DHCP pool",
                "desc_th": "กำหนด Subnet และ Mask ของวงเครือข่ายที่จะแจก IP",
                "example": "Router(dhcp-config)# network 192.168.10.0 255.255.255.0"
            },
            {
                "cmd": "default-router <ip>",
                "cat": "DHCP SERVER",
                "desc": "Specify default gateway IP address handed out to DHCP clients",
                "desc_th": "กำหนดหมายเลข Default Gateway ที่จะส่งให้เครื่องลูกข่าย",
                "example": "Router(dhcp-config)# default-router 192.168.10.1"
            },
            {
                "cmd": "dns-server <ip>",
                "cat": "DHCP SERVER",
                "desc": "Specify primary DNS server address distributed to DHCP clients",
                "desc_th": "กำหนดหมายเลข DNS Server ที่จะส่งให้เครื่องลูกข่าย",
                "example": "Router(dhcp-config)# dns-server 8.8.8.8"
            },
            {
                "cmd": "ip dhcp excluded-address <low> [high]",
                "cat": "DHCP SERVER",
                "desc": "Reserve static IP range excluded from dynamic allocation",
                "desc_th": "สงวนช่วง IP Address สำหรับอุปกรณ์ Static ไม่ให้ DHCP แจกซ้ำ",
                "example": "Router(config)# ip dhcp excluded-address 192.168.10.1 192.168.10.10"
            },
            {
                "cmd": "ip nat inside / ip nat outside",
                "cat": "NAT & PAT",
                "desc": "Designate interface as internal private LAN or external public WAN",
                "desc_th": "ระบุขอบเขต Interface ว่าเป็นฝั่ง Inside (LAN) หรือ Outside (WAN)",
                "example": "Router(config-if)# ip nat inside"
            },
            {
                "cmd": "ip nat inside source list <n> interface <if> overload",
                "cat": "NAT & PAT",
                "desc": "Enable Port Address Translation (PAT) to share one public IP",
                "desc_th": "เปิดใช้งาน PAT แชร์ IP ขาออกสู่ Internet สาธารณะ",
                "example": "Router(config)# ip nat inside source list 1 interface g0/0 overload"
            },
            {
                "cmd": "show ip route",
                "cat": "SHOW & DIAG",
                "desc": "Display the active IPv4 routing table (Connected, Static, OSPF, RIP)",
                "desc_th": "แสดงตารางเส้นทาง IPv4 Routing Table ทั้งหมด",
                "example": "Router# show ip route"
            },
            {
                "cmd": "show ip interface brief",
                "cat": "SHOW & DIAG",
                "desc": "Display summary table of all interface states, IPs, and link status",
                "desc_th": "แสดงตารางสรุปสถานะ Up/Down และหมายเลข IP ของทุกพอร์ต",
                "example": "Router# show ip interface brief"
            },
            {
                "cmd": "show ip ospf neighbor",
                "cat": "SHOW & DIAG",
                "desc": "Display OSPF neighbor 2-Way and Full adjacency states",
                "desc_th": "แสดงสถานะ Adjacency และเพื่อนบ้าน Neighbor ของโพรโทคอล OSPF",
                "example": "Router# show ip ospf neighbor"
            },
            {
                "cmd": "show ip ospf database",
                "cat": "SHOW & DIAG",
                "desc": "Display OSPF Link-State Database (LSDB Router-LSAs)",
                "desc_th": "แสดงฐานข้อมูล Link-State (LSDB) ของ OSPF",
                "example": "Router# show ip ospf database"
            },
            {
                "cmd": "show ip rip",
                "cat": "SHOW & DIAG",
                "desc": "Display RIP routing database, route metrics, and timers",
                "desc_th": "แสดงฐานข้อมูลและเมตริกของโพรโทคอล RIP",
                "example": "Router# show ip rip"
            },
            {
                "cmd": "ping <target_ip>",
                "cat": "SHOW & DIAG",
                "desc": "Send 5 ICMP Echo Requests to verify end-to-end network connectivity",
                "desc_th": "ส่งแพ็กเก็ต ICMP เพื่อทดสอบการเชื่อมต่อปลายทาง",
                "example": "Router# ping 8.8.8.8"
            }
        ]
    },
    "switch": {
        "categories": ["ALL", "VLAN CONFIG", "ACCESS PORTS", "TRUNK (802.1Q)", "SVI & MGMT", "SPANNING TREE", "SHOW & DIAG"],
        "commands": [
            {
                "cmd": "vlan <id>",
                "cat": "VLAN CONFIG",
                "desc": "Create a Layer 2 VLAN broadcast domain",
                "desc_th": "สร้าง VLAN วงใหม่ในฐานข้อมูล Switch",
                "example": "Switch(config)# vlan 10"
            },
            {
                "cmd": "name <vlan_name>",
                "cat": "VLAN CONFIG",
                "desc": "Assign descriptive name to the VLAN (e.g. SALES, ENGINEERING)",
                "desc_th": "ตั้งชื่อระบุกลุ่มงานให้กับ VLAN เช่น SALES, SERVERS",
                "example": "Switch(config-vlan)# name SALES_DEPT"
            },
            {
                "cmd": "show vlan brief",
                "cat": "VLAN CONFIG",
                "desc": "List all active VLANs and switchports currently assigned to them",
                "desc_th": "แสดงรายการ VLAN ทั้งหมดและพอร์ตที่สังกัดอยู่",
                "example": "Switch# show vlan brief"
            },
            {
                "cmd": "switchport mode access",
                "cat": "ACCESS PORTS",
                "desc": "Configure port to untagged Access mode for end devices (PCs, Servers)",
                "desc_th": "กำหนดให้พอร์ตทำงานในโหมด Access สำหรับต่อ End Device",
                "example": "Switch(config-if)# switchport mode access"
            },
            {
                "cmd": "switchport access vlan <id>",
                "cat": "ACCESS PORTS",
                "desc": "Assign access port to specific VLAN broadcast domain",
                "desc_th": "ผูกพอร์ต Access เข้ากับ VLAN ที่ต้องการ",
                "example": "Switch(config-if)# switchport access vlan 10"
            },
            {
                "cmd": "switchport mode trunk",
                "cat": "TRUNK (802.1Q)",
                "desc": "Configure port as an 802.1Q Trunk link carrying multi-VLAN tagged traffic",
                "desc_th": "ตั้งค่าพอร์ตให้เป็น Trunk สำหรับส่งผ่านข้อมูลหลาย VLAN ข้ามสวิตช์",
                "example": "Switch(config-if)# switchport mode trunk"
            },
            {
                "cmd": "switchport trunk allowed vlan <list>",
                "cat": "TRUNK (802.1Q)",
                "desc": "Filter which VLANs are permitted to traverse this trunk link (add, remove, all)",
                "desc_th": "จำกัดหมายเลข VLAN ที่ได้รับอนุญาตให้ส่งผ่าน Trunk พอร์ตนี้",
                "example": "Switch(config-if)# switchport trunk allowed vlan 10,20,30"
            },
            {
                "cmd": "switchport trunk native vlan <id>",
                "cat": "TRUNK (802.1Q)",
                "desc": "Set native untagged VLAN ID for 802.1Q trunk port (default 1)",
                "desc_th": "กำหนด Native VLAN สำหรับเฟรมที่ไม่ได้ติด Tag 802.1Q",
                "example": "Switch(config-if)# switchport trunk native vlan 99"
            },
            {
                "cmd": "interface vlan <id>",
                "cat": "SVI & MGMT",
                "desc": "Enter Switch Virtual Interface (SVI) for remote in-band management",
                "desc_th": "เข้าสู่โหมดปรับแต่ง SVI (Switch Virtual Interface) สำหรับจัดการ",
                "example": "Switch(config)# interface vlan 1"
            },
            {
                "cmd": "ip address <ip> <mask>",
                "cat": "SVI & MGMT",
                "desc": "Assign management IP address to the switch SVI",
                "desc_th": "กำหนดหมายเลข IP ให้กับ SVI เพื่อใช้ Remote SSH/Web/Ping",
                "example": "Switch(config-if)# ip address 192.168.1.2 255.255.255.0"
            },
            {
                "cmd": "ip default-gateway <ip>",
                "cat": "SVI & MGMT",
                "desc": "Configure default gateway IP so switch can be managed across subnets",
                "desc_th": "กำหนด Default Gateway ให้สวิตช์สามารถสื่อสารข้าม Subnet ได้",
                "example": "Switch(config)# ip default-gateway 192.168.1.1"
            },
            {
                "cmd": "spanning-tree mode rapid-pvst",
                "cat": "SPANNING TREE",
                "desc": "Enable Rapid Per-VLAN Spanning Tree protocol (802.1w) to prevent loops",
                "desc_th": "เปิดใช้งาน Rapid Spanning Tree เพื่อป้องกัน Loop และลู่เข้าเร็วขึ้น",
                "example": "Switch(config)# spanning-tree mode rapid-pvst"
            },
            {
                "cmd": "spanning-tree vlan <id> priority <val>",
                "cat": "SPANNING TREE",
                "desc": "Configure switch bridge priority to become STP Root Bridge",
                "desc_th": "กำหนดค่า Priority เพื่อให้สวิตช์ตัวนี้เป็น STP Root Bridge",
                "example": "Switch(config)# spanning-tree vlan 10 priority 4096"
            },
            {
                "cmd": "show spanning-tree",
                "cat": "SPANNING TREE",
                "desc": "Display STP topology, root bridge status, and port blocking states",
                "desc_th": "แสดงสถานะ Spanning Tree, Root Bridge และพอร์ตที่ Forwarding/Blocking",
                "example": "Switch# show spanning-tree"
            },
            {
                "cmd": "show mac address-table",
                "cat": "SHOW & DIAG",
                "desc": "Display CAM hardware table mapping learned MAC addresses to VLAN and port",
                "desc_th": "แสดงตาราง MAC Address Table แยกตาม VLAN และพอร์ตที่สวิตช์เรียนรู้ได้",
                "example": "Switch# show mac address-table"
            },
            {
                "cmd": "show interfaces trunk",
                "cat": "SHOW & DIAG",
                "desc": "Display active 802.1Q trunking ports, native VLANs, and allowed VLAN lists",
                "desc_th": "แสดงสถานะพอร์ตที่เป็น Trunk ทั้งหมด, Native VLAN และ VLAN ที่อนุญาต",
                "example": "Switch# show interfaces trunk"
            },
            {
                "cmd": "show interfaces switchport",
                "cat": "SHOW & DIAG",
                "desc": "Display detailed switchport mode, trunk encapsulation, and native VLAN",
                "desc_th": "แสดงรายละเอียดโหมดการทำงาน Switchport แบบละเอียดของแต่ละพอร์ต",
                "example": "Switch# show interfaces switchport"
            },
            {
                "cmd": "show interfaces status",
                "cat": "SHOW & DIAG",
                "desc": "Display summary table of all physical port states and VLAN memberships",
                "desc_th": "แสดงตารางสรุปสถานะพอร์ต Speed, Duplex, VLAN และ Link",
                "example": "Switch# show interfaces status"
            }
        ]
    },
    "server": {
        "categories": ["ALL", "NETWORK & IP", "ROUTING & GW", "DHCP CLIENT", "SERVICES", "DIAGNOSTICS"],
        "commands": [
            {
                "cmd": "ip addr show",
                "cat": "NETWORK & IP",
                "desc": "Display all network interfaces, assigned IP addresses, and MAC addresses",
                "desc_th": "แสดงรายการการ์ดแลน หมายเลข IP และ MAC Address ทั้งหมด",
                "example": "server:~$ ip addr show"
            },
            {
                "cmd": "ip addr add <ip>/<cidr> dev <if>",
                "cat": "NETWORK & IP",
                "desc": "Manually assign static IPv4 address and CIDR prefix to interface",
                "desc_th": "ตั้งค่าหมายเลข Static IPv4 Address ให้กับการ์ดแลน",
                "example": "server:~$ sudo ip addr add 192.168.1.50/24 dev eth0"
            },
            {
                "cmd": "ip link set <if> up",
                "cat": "NETWORK & IP",
                "desc": "Bring network interface administratively UP",
                "desc_th": "สั่งเปิดใช้งานการ์ดแลนให้เชื่อมต่อสัญญาณ",
                "example": "server:~$ sudo ip link set eth0 up"
            },
            {
                "cmd": "ip route add default via <gw> dev <if>",
                "cat": "ROUTING & GW",
                "desc": "Add default gateway route to Linux kernel routing table",
                "desc_th": "กำหนด Default Gateway ให้เครื่อง Server ออกสู่ภายนอก",
                "example": "server:~$ sudo ip route add default via 192.168.1.1 dev eth0"
            },
            {
                "cmd": "ip route show",
                "cat": "ROUTING & GW",
                "desc": "Display the active Linux kernel IPv4 routing table",
                "desc_th": "แสดงตารางเส้นทาง Routing Table ในระบบปฏิบัติการ Linux",
                "example": "server:~$ ip route show"
            },
            {
                "cmd": "dhclient -v <if>",
                "cat": "DHCP CLIENT",
                "desc": "Send DHCP DISCOVER to request new IP address lease from server",
                "desc_th": "ส่งคำขอหมายเลข IP อัตโนมัติจาก DHCP Server",
                "example": "server:~$ sudo dhclient -v eth0"
            },
            {
                "cmd": "dhclient -r <if>",
                "cat": "DHCP CLIENT",
                "desc": "Release currently held DHCP lease and clear assigned IP",
                "desc_th": "คืนหมายเลข IP กลับไปยัง DHCP Server",
                "example": "server:~$ sudo dhclient -r eth0"
            },
            {
                "cmd": "ping -c 4 <target_ip>",
                "cat": "DIAGNOSTICS",
                "desc": "Send 4 ICMP test packets to check server reachability and latency",
                "desc_th": "ทดสอบส่งสัญญาณ Ping ไปยังปลายทาง 4 ครั้ง",
                "example": "server:~$ ping -c 4 192.168.1.1"
            },
            {
                "cmd": "traceroute <target_ip>",
                "cat": "DIAGNOSTICS",
                "desc": "Trace multi-hop network path and round-trip delay per hop",
                "desc_th": "ตรวจสอบเส้นทางเครือข่ายและวัดค่าหน่วงเวลาทีละ Hop",
                "example": "server:~$ traceroute 8.8.8.8"
            },
            {
                "cmd": "ss -tulpn",
                "cat": "SERVICES",
                "desc": "Display listening TCP/UDP ports and active network service daemons",
                "desc_th": "แสดงรายการพอร์ต TCP/UDP ที่เปิดรับการเชื่อมต่ออยู่",
                "example": "server:~$ ss -tulpn"
            },
            {
                "cmd": "curl -I http://<target_ip>",
                "cat": "SERVICES",
                "desc": "Perform HTTP HEAD request to test web server status code",
                "desc_th": "ทดสอบการตอบสนองของ Web Server ด้วย HTTP HEAD",
                "example": "server:~$ curl -I http://192.168.1.1"
            }
        ]
    },
    "firewall": {
        "categories": ["ALL", "INTERFACE & ZONES", "ROUTING", "ACCESS CONTROL", "NAT & PAT", "MONITORING"],
        "commands": [
            {
                "cmd": "nameif <zone>",
                "cat": "INTERFACE & ZONES",
                "desc": "Assign interface to a logical security zone (outside, inside, dmz)",
                "desc_th": "กำหนด Security Zone ให้กับ Interface เช่น outside, inside, dmz",
                "example": "Firewall(config-if)# nameif outside"
            },
            {
                "cmd": "security-level <0-100>",
                "cat": "INTERFACE & ZONES",
                "desc": "Set trust level (100=trusted LAN, 50=DMZ, 0=untrusted WAN)",
                "desc_th": "กำหนดระดับความปลอดภัย (100 สูงสุด LAN, 0 ต่ำสุด WAN)",
                "example": "Firewall(config-if)# security-level 0"
            },
            {
                "cmd": "ip address <ip> <mask>",
                "cat": "INTERFACE & ZONES",
                "desc": "Assign IPv4 address and subnet mask to firewall interface",
                "desc_th": "กำหนดหมายเลข IP ให้กับพอร์ต Firewall",
                "example": "Firewall(config-if)# ip address 203.0.113.2 255.255.255.0"
            },
            {
                "cmd": "route <zone> 0.0.0.0 0.0.0.0 <gw>",
                "cat": "ROUTING",
                "desc": "Configure default route through WAN gateway to Internet ISP",
                "desc_th": "กำหนดเส้นทาง Default Route ขาออก Internet",
                "example": "Firewall(config)# route outside 0.0.0.0 0.0.0.0 203.0.113.1"
            },
            {
                "cmd": "access-list <name> permit <proto> <src> <dst>",
                "cat": "ACCESS CONTROL",
                "desc": "Define stateful firewall access rule permitting inbound traffic",
                "desc_th": "สร้างกฎความปลอดภัย (ACL) อนุญาตให้ทราฟฟิกไหลผ่าน",
                "example": "Firewall(config)# access-list WAN_IN permit tcp any host 192.168.1.10 eq 80"
            },
            {
                "cmd": "access-group <name> in interface <zone>",
                "cat": "ACCESS CONTROL",
                "desc": "Apply access list filter inbound on specified security zone",
                "desc_th": "นำ Access List มาผูกใช้งานกับ Zone ที่ต้องการกรองข้อมูล",
                "example": "Firewall(config)# access-group WAN_IN in interface outside"
            },
            {
                "cmd": "nat (inside,outside) dynamic interface",
                "cat": "NAT & PAT",
                "desc": "Configure dynamic Hide NAT translating internal IPs to WAN IP",
                "desc_th": "ตั้งค่า NAT แปลง IP ภายในทั้งหมดออกด้วย IP ขาภายนอก",
                "example": "Firewall(config)# nat (inside,outside) dynamic interface"
            },
            {
                "cmd": "show conn",
                "cat": "MONITORING",
                "desc": "Display active stateful TCP/UDP connection tracking table",
                "desc_th": "แสดงรายการ Connection ปัจจุบันที่มีการเชื่อมต่อผ่าน Firewall",
                "example": "Firewall# show conn"
            },
            {
                "cmd": "show xlate",
                "cat": "MONITORING",
                "desc": "Display current active NAT address translations",
                "desc_th": "แสดงตารางการแปลง IP (NAT Translation) ปัจจุบัน",
                "example": "Firewall# show xlate"
            }
        ]
    },
    "laptop": {
        "categories": ["ALL", "CLI COMMANDS", "DESKTOP APPS", "HARDWARE PORTS"],
        "commands": [
            {
                "cmd": "ip a / ifconfig",
                "cat": "CLI COMMANDS",
                "desc": "View local network adapter status, IP address, and link state",
                "desc_th": "ตรวจสอบสถานะการ์ดแลนและหมายเลข IP ของโน้ตบุ๊ก",
                "example": "engineer:~$ ip a"
            },
            {
                "cmd": "sudo dhclient eth0",
                "cat": "CLI COMMANDS",
                "desc": "Request automatic IP address from datacenter DHCP server",
                "desc_th": "ขอรับหมายเลข IP อัตโนมัติจากการ์ดแลน eth0",
                "example": "engineer:~$ sudo dhclient eth0"
            },
            {
                "cmd": "ping -c 4 <target_ip>",
                "cat": "CLI COMMANDS",
                "desc": "Test network latency and reachability to target host",
                "desc_th": "ทดสอบการเชื่อมต่อเครือข่ายไปยังอุปกรณ์เป้าหมาย",
                "example": "engineer:~$ ping -c 4 192.168.1.1"
            },
            {
                "cmd": "minicom -D /dev/ttyUSB0",
                "cat": "CLI COMMANDS",
                "desc": "Open Serial Console rollover terminal to Cisco equipment",
                "desc_th": "เชื่อมต่อสาย Console Rollover เข้าพอร์ต Console ของสวิตช์/เราเตอร์",
                "example": "engineer:~$ minicom -D /dev/ttyUSB0"
            },
            {
                "cmd": "Web Browser",
                "cat": "DESKTOP APPS",
                "desc": "Access web GUI management portals for Firewalls, PDU, and switches",
                "desc_th": "เปิดเบราว์เซอร์จัดการหน้าเว็บคอนฟิกอุปกรณ์เครือข่าย",
                "example": "Click Web Browser icon on Laptop Desktop"
            },
            {
                "cmd": "Network Settings",
                "cat": "DESKTOP APPS",
                "desc": "Configure IPv4 manual/DHCP via Ubuntu/Windows desktop GUI",
                "desc_th": "ตั้งค่าเครือข่ายแบบกราฟิกผ่านหน้าต่าง Network Manager",
                "example": "Open Settings -> Network -> IPv4 Settings"
            },
            {
                "cmd": "Terminal Emulator",
                "cat": "DESKTOP APPS",
                "desc": "Run shell scripts, SSH sessions, and troubleshooting commands",
                "desc_th": "เปิดโปรแกรม Terminal สำหรับพิมพ์คำสั่งตรวจสอบระบบ",
                "example": "Click Terminal icon on Dock / Taskbar"
            },
            {
                "cmd": "Wireshark",
                "cat": "DESKTOP APPS",
                "desc": "Capture and inspect live packets for protocol troubleshooting",
                "desc_th": "ดักจับและวิเคราะห์แพ็กเก็ตเครือข่ายเชิงลึก",
                "example": "Open Wireshark -> Select eth0 interface"
            },
            {
                "cmd": "eth0 (Left Side RJ45)",
                "cat": "HARDWARE PORTS",
                "desc": "Gigabit Ethernet Cat6 patch cable port for data network access",
                "desc_th": "พอร์ตแลน RJ45 ด้านซ้ายสำหรับเชื่อมต่อสายเคเบิลข้อมูล",
                "example": "Plug blue/yellow Cat6 cable into left side"
            },
            {
                "cmd": "con0 (Right Side Serial)",
                "cat": "HARDWARE PORTS",
                "desc": "Rollover console port for out-of-band serial management",
                "desc_th": "พอร์ต Console ด้านขวาสำหรับสายฟ้าผ่า (Console Cable)",
                "example": "Plug light-blue rollover cable into right side"
            }
        ]
    },
    "controls": {
        "categories": ["ALL", "NAVIGATION", "CABLING & PORTS", "CLI & TERMINAL", "MANAGEMENT"],
        "commands": [
            {
                "cmd": "W, A, S, D",
                "cat": "NAVIGATION",
                "desc": "Walk forward, strafe left, backward, strafe right in datacenter room",
                "desc_th": "เดินหน้า ถอยหลัง เดินไปทางซ้ายและขวาในห้องดาต้าเซ็นเตอร์",
                "example": "Use WASD keys for first-person movement"
            },
            {
                "cmd": "Mouse Look",
                "cat": "NAVIGATION",
                "desc": "Rotate camera pitch and yaw / Aim crosshair at racks, devices, and ports",
                "desc_th": "ขยับเมาส์เพื่อมองไปรอบห้อง เล็งเป้าที่ตู้ Rack อุปกรณ์ และพอร์ต",
                "example": "Move mouse freely to aim crosshair"
            },
            {
                "cmd": "Left Shift",
                "cat": "NAVIGATION",
                "desc": "Sprint / Walk 2x faster through datacenter aisles",
                "desc_th": "กดค้างเพื่อวิ่งเร็วขึ้น 2 เท่าในทางเดินดาต้าเซ็นเตอร์",
                "example": "Hold Left Shift while pressing WASD"
            },
            {
                "cmd": "Left Ctrl",
                "cat": "NAVIGATION",
                "desc": "Toggle Crouch stance (lowers eye level to inspect bottom rack slots)",
                "desc_th": "กดเพื่อย่อตัวลงตรวจดูอุปกรณ์ด้านล่างตู้ / กดอีกครั้งเพื่อลุกขึ้นยืน",
                "example": "Press Left Ctrl once to crouch, again to stand"
            },
            {
                "cmd": "[F11] Key",
                "cat": "NAVIGATION",
                "desc": "Toggle Fullscreen borderless display mode",
                "desc_th": "สลับโหมดเต็มจอภาพ (Fullscreen)",
                "example": "Press F11 anytime to toggle fullscreen"
            },
            {
                "cmd": "[E] Key",
                "cat": "CLI & TERMINAL",
                "desc": "Open Cisco IOS / Linux Console Terminal for aimed device",
                "desc_th": "เปิดหน้าต่าง CLI Console ของอุปกรณ์ที่เป้าเล็งอยู่",
                "example": "Aim at Router, Switch, or Server and press [E]"
            },
            {
                "cmd": "[F] Key",
                "cat": "CABLING & PORTS",
                "desc": "Pick up cable / Plug cable into aimed RJ45 or Console port",
                "desc_th": "หยิบสายเคเบิล หรือเสียบสายเข้ากับพอร์ตที่กำลังเล็งอยู่",
                "example": "Look at port until badge highlights, then press [F]"
            },
            {
                "cmd": "[X] Key",
                "cat": "CABLING & PORTS",
                "desc": "Cancel and drop cable currently held in hand",
                "desc_th": "ยกเลิกสายเคเบิลที่กำลังถืออยู่ในมือ",
                "example": "Press [X] when holding a cable to cancel"
            },
            {
                "cmd": "[O] Key",
                "cat": "MANAGEMENT",
                "desc": "Toggle Mission Objective & Concept Guide panel on/off",
                "desc_th": "เปิดหรือปิดกล่องภารกิจและเนื้อหาความรู้บนหน้าจอ",
                "example": "Press [O] to show/hide mission objectives"
            },
            {
                "cmd": "[M] Key",
                "cat": "MANAGEMENT",
                "desc": "Open 2D Logical Network Topology Diagram",
                "desc_th": "เปิดแผนภาพไดอะแกรมเครือข่าย 2 มิติ แสดงการเชื่อมโยงทั้งหมด",
                "example": "Press [M] to open topology map, [ESC] to return"
            },
            {
                "cmd": "[N] Key",
                "cat": "MANAGEMENT",
                "desc": "Open Rack Device Manager modal (Add/Remove devices in Sandbox)",
                "desc_th": "เปิดหน้าต่างจัดการตู้ Rack เพิ่มหรือลบอุปกรณ์ในโหมด Sandbox",
                "example": "Press [N] in Sandbox mode to manage devices"
            },
            {
                "cmd": "[Del] / [Backspace]",
                "cat": "MANAGEMENT",
                "desc": "Quick Delete the aimed device from rack (Sandbox mode)",
                "desc_th": "ลบอุปกรณ์ที่กำลังเล็งอยู่ออกจากตู้ Rack ทันที (โหมด Sandbox)",
                "example": "Aim at device in Sandbox and press [Delete]"
            },
            {
                "cmd": "[K] / [L] Keys",
                "cat": "MANAGEMENT",
                "desc": "Quick Save / Quick Load network topology JSON (Sandbox mode)",
                "desc_th": "บันทึกหรือโหลดการจัดวางอุปกรณ์และสายเคเบิล (โหมด Sandbox)",
                "example": "Press [K] to save topology, [L] to reload"
            },
            {
                "cmd": "[ESC] Key",
                "cat": "NAVIGATION",
                "desc": "Detach active CLI terminal / Open Pause Menu / Return to Menu",
                "desc_th": "ปิดหน้าต่าง Terminal / เปิดเมนูหยุดชั่วคราว / ย้อนกลับเมนูหลัก",
                "example": "Global Escape key for back and pause"
            }
        ]
    }
}

class MenuState:
    MAIN_MENU = "MAIN_MENU"
    TUTORIAL_SELECT = "TUTORIAL_SELECT"
    IN_GAME = "IN_GAME"
    PAUSE = "PAUSE"
    TOPOLOGY_MAP = "TOPOLOGY_MAP"
    HELP_GUIDE = "HELP_GUIDE"
    DEVICE_MANAGER = "DEVICE_MANAGER"

class MenuManager:
    def __init__(self):
        self.state = MenuState.MAIN_MENU
        self.topology_2d = Topology2D()
        self.font_logo = pygame.font.SysFont("Segoe UI", 38, bold=True) or pygame.font.Font(None, 44)
        self.font_title = pygame.font.SysFont("Segoe UI", 20, bold=True) or pygame.font.Font(None, 24)
        self.font_sub = pygame.font.SysFont("Segoe UI", 16) or pygame.font.Font(None, 20)
        self.font_btn = pygame.font.SysFont("Segoe UI", 16, bold=True) or pygame.font.Font(None, 20)
        self.font_bold = pygame.font.SysFont("Segoe UI", 14, bold=True) or pygame.font.Font(None, 18)
        self.font_body = pygame.font.SysFont("Segoe UI", 14) or pygame.font.Font(None, 18)
        self.font_small = pygame.font.SysFont("Segoe UI", 12) or pygame.font.Font(None, 15)
        self.font_mono = pygame.font.SysFont("Consolas", 13) or pygame.font.Font(None, 16)
        self.font_rack_badge = pygame.font.SysFont("Segoe UI", 12, bold=True) or pygame.font.Font(None, 14)
        self.font_rack_sub = pygame.font.SysFont("Segoe UI", 10, bold=True) or pygame.font.Font(None, 12)
        self.font_rack_micro = pygame.font.SysFont("Consolas", 9, bold=True) or pygame.font.Font(None, 11)
        self.font_rack_nano = pygame.font.SysFont("Consolas", 8) or pygame.font.Font(None, 10)

        self.font_mono_bold = pygame.font.SysFont("Consolas", 12, bold=True) or pygame.font.Font(None, 15)
        self.font_badge = pygame.font.SysFont("Segoe UI", 11, bold=True) or pygame.font.Font(None, 14)
        self.font_cat = pygame.font.SysFont("Segoe UI", 12, bold=True) or pygame.font.Font(None, 15)
        self.font_thai = pygame.font.SysFont("leelawadeeui,tahoma,angsanaupc", 12) or pygame.font.Font(None, 15)
        self.font_thai_small = pygame.font.SysFont("leelawadeeui,tahoma,angsanaupc", 11) or pygame.font.Font(None, 14)

        # Cheatsheet & Guide Dedicated High-Legibility Fonts (Enlarged)
        self.font_guide_title = pygame.font.SysFont("Segoe UI", 26, bold=True) or pygame.font.Font(None, 32)
        self.font_guide_sub = pygame.font.SysFont("Segoe UI", 13, bold=True) or pygame.font.Font(None, 17)
        self.font_guide_tab = pygame.font.SysFont("Segoe UI", 14, bold=True) or pygame.font.Font(None, 18)
        self.font_guide_dev_title = pygame.font.SysFont("Segoe UI", 16, bold=True) or pygame.font.Font(None, 20)
        self.font_guide_badge = pygame.font.SysFont("Segoe UI", 11, bold=True) or pygame.font.Font(None, 14)
        self.font_guide_rot = pygame.font.SysFont("Segoe UI", 12, bold=True) or pygame.font.Font(None, 15)
        self.font_guide_spec_k = pygame.font.SysFont("Segoe UI", 11, bold=True) or pygame.font.Font(None, 14)
        self.font_guide_spec_v = pygame.font.SysFont("Segoe UI", 13) or pygame.font.Font(None, 16)
        self.font_guide_cat = pygame.font.SysFont("Segoe UI", 13, bold=True) or pygame.font.Font(None, 16)
        self.font_guide_cmd = pygame.font.SysFont("Consolas", 14, bold=True) or pygame.font.Font(None, 17)
        self.font_guide_card_tag = pygame.font.SysFont("Segoe UI", 11, bold=True) or pygame.font.Font(None, 14)
        self.font_guide_desc = pygame.font.SysFont("Segoe UI", 13) or pygame.font.Font(None, 16)
        self.font_thai_guide = pygame.font.SysFont("leelawadeeui,tahoma,angsanaupc", 13) or pygame.font.Font(None, 16)
        self.font_guide_mono = pygame.font.SysFont("Consolas", 13) or pygame.font.Font(None, 16)
        self.font_guide_btn = pygame.font.SysFont("Segoe UI", 14, bold=True) or pygame.font.Font(None, 17)
        self.font_guide_hint = pygame.font.SysFont("Segoe UI", 12) or pygame.font.Font(None, 15)

        self.selected_button = 0
        self.menu_options = [
            ("TUTORIAL MODE", "Learn step-by-step from cabling to Cisco CLI"),
            ("CHALLENGE MODE", "Solve real-world incident tickets under pressure"),
            ("SANDBOX PLAYGROUND", "Freely build, cable, configure and save topologies"),
            ("CONTROLS & CLI CHEATSHEET", "View keybindings and Cisco command reference"),
            ("EXIT SIMULATOR", "Quit to desktop")
        ]

        # Device Manager UI State
        self.dm_rack_filter = 0  # 0: All, 1: Rack 1, 2: Rack 2, 3: Rack 3
        self.dm_selected_type = "switch"  # "switch", "router", "server"
        self.dm_selected_rack = 1
        self.dm_selected_slot = 12
        self.dm_hostname_input = "Switch-New"
        self.dm_hostname_active = False
        self.dm_scroll_offset = 0
        self.dm_feedback = ""
        self.dm_feedback_color = (15, 140, 65)

        # Chapter Selection UI State
        self.selected_chapter_idx = 0
        self._chapter_card_rects = []
        self._tutorial_back_btn_rect = None

        # 3D Showcase & CLI Cheatsheet State
        self.showcase_devices = []
        self.showcase_selected_idx = 0
        self.showcase_yaw = 25.0
        self.showcase_pitch = 18.0
        self.showcase_dragging = False
        self.showcase_last_mouse = (0, 0)
        self.showcase_cat_idx = 0
        self.showcase_scroll_y = 0
        self._max_scroll_y = 0
        self.help_guide_prev_state = MenuState.MAIN_MENU
        self._last_device_tab_rects = []
        self._last_category_rects = []
        self._last_back_btn_rect = None
        self._init_showcase()

    def _init_showcase(self):
        # 1. Cisco 2911 Router
        r1 = Router("sc_r1", hostname="R1-Core-Edge", rack_id=1, u_slot=10)
        r1.is_showcase = True
        r1.pos_x, r1.pos_y, r1.pos_z = 0.0, 0.0, 0.0
        if "g0/0" in r1.ports:
            r1.ports["g0/0"].is_shutdown = False
        if "g0/1" in r1.ports:
            r1.ports["g0/1"].is_shutdown = False

        # 2. Cisco Catalyst 2960-X Switch
        sw1 = Switch("sc_sw1", hostname="SW1-Dist-Access", rack_id=1, u_slot=14)
        sw1.is_showcase = True
        sw1.pos_x, sw1.pos_y, sw1.pos_z = 0.0, 0.0, 0.0
        for p_name in ("g0/1", "g0/2", "g0/3", "g0/24"):
            if p_name in sw1.ports:
                sw1.ports[p_name].is_shutdown = False

        # 3. Dell PowerEdge R750 Server
        srv1 = Host("sc_srv1", hostname="SRV-DCIM-01", device_type="server", rack_id=2, u_slot=20)
        srv1.is_showcase = True
        srv1.pos_x, srv1.pos_y, srv1.pos_z = 0.0, 0.0, 0.0
        srv1.is_powered = True
        if "eth0" in srv1.ports:
            srv1.ports["eth0"].is_shutdown = False

        # 4. Fortinet FortiGate 100F Firewall
        fw1 = Firewall("sc_fw1", hostname="FW-Perimeter", rack_id=2, u_slot=24)
        fw1.is_showcase = True
        fw1.pos_x, fw1.pos_y, fw1.pos_z = 0.0, 0.0, 0.0
        for p_name in ("g0/0", "g0/1", "m0/0"):
            if p_name in fw1.ports:
                fw1.ports[p_name].is_shutdown = False

        # 5. Field Engineer Laptop
        lap1 = Host("sc_lap1", hostname="ADMIN-LAPTOP", device_type="laptop", os_type="ubuntu")
        lap1.is_showcase = True
        lap1.pos_x, lap1.pos_y, lap1.pos_z = 0.0, 0.0, 0.0
        if "eth0" in lap1.ports:
            lap1.ports["eth0"].is_shutdown = False
        if "con0" in lap1.ports:
            lap1.ports["con0"].is_shutdown = False

        self.showcase_devices = [
            {
                "id": "router",
                "label": "1. Cisco Router",
                "device": r1,
                "title": "Cisco 2911 Integrated Services Router (ISR G2)",
                "form_factor": "19\" EIA 1U Rackmount",
                "os": "Cisco IOS 15.7M",
                "ports_desc": "3x GE RJ45, 1x Console, 2x EHWIC",
                "power_desc": "Dual Redundant 100-240V AC PSUs",
            },
            {
                "id": "switch",
                "label": "2. Catalyst Switch",
                "device": sw1,
                "title": "Cisco Catalyst 2960-X Enterprise L2/L3 Switch",
                "form_factor": "19\" EIA 1U Rackmount",
                "os": "Cisco IOS-XE 16.9",
                "ports_desc": "24x 10/100/1000 Ethernet, 2x SFP+ Uplinks",
                "power_desc": "Dual Hot-Swap PSUs + FlexStack-Plus",
            },
            {
                "id": "server",
                "label": "3. PowerEdge Server",
                "device": srv1,
                "title": "Dell PowerEdge R750 Enterprise 2U Rack Server",
                "form_factor": "19\" EIA 2U Heavy Chassis",
                "os": "Ubuntu 22.04 LTS / RHEL 9",
                "ports_desc": "4x 10GbE SFP28, 2x 1GbE, 1x iDRAC9 MGMT",
                "power_desc": "Dual Titanium 1400W Redundant PSUs",
            },
            {
                "id": "firewall",
                "label": "4. FortiGate Firewall",
                "device": fw1,
                "title": "Fortinet FortiGate 100F Next-Gen Firewall",
                "form_factor": "19\" EIA 1U Rackmount",
                "os": "FortiOS 7.2 Enterprise",
                "ports_desc": "2x 10GE SFP+, 4x GE SFP, 12x GE RJ45, MGMT",
                "power_desc": "Dual Redundant Hot-Swap AC Feeds",
            },
            {
                "id": "laptop",
                "label": "5. Field Laptop",
                "device": lap1,
                "title": "Field Engineer Mobile NOC Diagnostics Workstation",
                "form_factor": "15.6\" Rugged Mobile Workstation",
                "os": "Ubuntu 22.04 LTS / Windows 11",
                "ports_desc": "1x RJ45 Gigabit (eth0), 1x Serial Console (con0)",
                "power_desc": "90W Li-Ion Fast-Charging Battery + AC",
            },
            {
                "id": "controls",
                "label": "6. Simulator Controls",
                "device": r1,
                "title": "Datacenter Simulator Controls & Keybindings",
                "form_factor": "Full 3D Datacenter Simulation",
                "os": "Antigravity Physics & Packet Engine",
                "ports_desc": "Virtual Multi-Rack Datacenter & Patch Panels",
                "power_desc": "Real-time 60 FPS Hardware OpenGL",
            }
        ]

    def get_showcase_device(self):
        if not hasattr(self, "showcase_devices") or not self.showcase_devices:
            self._init_showcase()
        idx = max(0, min(len(self.showcase_devices) - 1, getattr(self, "showcase_selected_idx", 0)))
        dev = self.showcase_devices[idx]["device"]
        if dev is None:
            return self.showcase_devices[0]["device"]
        return dev

    def get_showcase_viewport(self, w, h):
        content_y = 100
        content_h = max(320, h - content_y - 44)
        margin_x = max(20, (w - 1240) // 2) if w > 1240 else 20
        content_w = w - margin_x * 2
        left_w = int(content_w * 0.44)
        left_x = margin_x
        vp_x = left_x + 12
        vp_y = content_y + 54
        vp_w = left_w - 24
        vp_h = max(180, content_h - 174)
        return (vp_x, vp_y, vp_w, vp_h)

    def update(self, dt):
        if self.state == MenuState.HELP_GUIDE:
            if not getattr(self, "showcase_dragging", False):
                self.showcase_yaw = (getattr(self, "showcase_yaw", 25.0) + dt * 15.0) % 360.0


    def get_main_menu_button_rect(self, idx, w, h):
        bx = 48
        btn_w = min(400, max(350, int(w * 0.30)))
        btn_h = 56
        start_y = 195
        by = start_y + idx * (btn_h + 14)
        return pygame.Rect(bx, by, btn_w, btn_h)

    def get_pause_button_rect(self, idx, w, h):
        cx, cy = w // 2, h // 2
        card_w, card_h = 420, 280
        rx, ry = cx - card_w // 2, cy - card_h // 2
        btn_w, btn_h = 360, 40
        by = ry + 95 + idx * 45
        bx = cx - btn_w // 2
        return pygame.Rect(bx, by, btn_w, btn_h)

    def _compute_dm_rects(self, w, h):
        win_w = min(1080, max(820, w - 80))
        win_h = min(640, max(520, h - 80))
        win_x = (w - win_w) // 2
        win_y = (h - win_h) // 2

        close_rect = pygame.Rect(win_x + win_w - 42, win_y + 12, 30, 30)

        # Left panel (Inventory): 57% width
        left_w = int(win_w * 0.57) - 20
        left_x = win_x + 18
        left_y = win_y + 55
        left_h = win_h - 70

        tab_names = ["All Racks", "Rack 1", "Rack 2", "Rack 3"]
        tab_w = (left_w - 18) // 4
        tab_rects = []
        for i in range(4):
            tab_rects.append(pygame.Rect(left_x + i * (tab_w + 6), left_y + 32, tab_w, 28))

        list_rect = pygame.Rect(left_x, left_y + 68, left_w, left_h - 76)

        # Right panel (Form): 43% width
        right_w = win_w - left_w - 54
        right_x = left_x + left_w + 18
        right_y = win_y + 55
        right_h = win_h - 70

        btn_type_w = (right_w - 18) // 4
        type_rects = {
            "switch": pygame.Rect(right_x, right_y + 52, btn_type_w, 34),
            "router": pygame.Rect(right_x + (btn_type_w + 6), right_y + 52, btn_type_w, 34),
            "firewall": pygame.Rect(right_x + (btn_type_w + 6) * 2, right_y + 52, btn_type_w, 34),
            "server": pygame.Rect(right_x + (btn_type_w + 6) * 3, right_y + 52, btn_type_w, 34),
        }

        btn_rack_w = (right_w - 12) // 3
        rack_rects = {
            1: pygame.Rect(right_x, right_y + 122, btn_rack_w, 32),
            2: pygame.Rect(right_x + btn_rack_w + 6, right_y + 122, btn_rack_w, 32),
            3: pygame.Rect(right_x + (btn_rack_w + 6) * 2, right_y + 122, btn_rack_w, 32),
        }

        slot_minus_rect = pygame.Rect(right_x, right_y + 188, 42, 34)
        slot_display_rect = pygame.Rect(right_x + 48, right_y + 188, right_w - 96, 34)
        slot_plus_rect = pygame.Rect(right_x + right_w - 42, right_y + 188, 42, 34)

        hostname_rect = pygame.Rect(right_x, right_y + 280, right_w, 34)
        install_btn_rect = pygame.Rect(right_x, right_y + 355, right_w, 46)

        return {
            "win_rect": pygame.Rect(win_x, win_y, win_w, win_h),
            "close_rect": close_rect,
            "left_rect": pygame.Rect(left_x, left_y, left_w, left_h),
            "tab_rects": tab_rects,
            "list_rect": list_rect,
            "right_rect": pygame.Rect(right_x, right_y, right_w, right_h),
            "type_rects": type_rects,
            "rack_rects": rack_rects,
            "slot_minus_rect": slot_minus_rect,
            "slot_display_rect": slot_display_rect,
            "slot_plus_rect": slot_plus_rect,
            "hostname_rect": hostname_rect,
            "install_btn_rect": install_btn_rect,
        }

    def handle_input(self, event, sound_mgr, screen_w=1280, screen_h=720, mode=None):
        if self.state == MenuState.MAIN_MENU:
            # 1. Mouse Hover
            if event.type == pygame.MOUSEMOTION:
                mouse_x, mouse_y = event.pos
                hovered = False
                for i in range(len(self.menu_options)):
                    rect = self.get_main_menu_button_rect(i, screen_w, screen_h)
                    if rect.collidepoint(mouse_x, mouse_y):
                        if self.selected_button != i:
                            self.selected_button = i
                            sound_mgr.play_key()
                        hovered = True
                        break
                try:
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if hovered else pygame.SYSTEM_CURSOR_ARROW)
                except Exception:
                    pass

            # 2. Mouse Left Click
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_x, mouse_y = event.pos
                for i in range(len(self.menu_options)):
                    rect = self.get_main_menu_button_rect(i, screen_w, screen_h)
                    if rect.collidepoint(mouse_x, mouse_y):
                        self.selected_button = i
                        sound_mgr.play_key()
                        return self._select_main_option(i)

            # 3. Keyboard Controls
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.selected_button = (self.selected_button - 1) % len(self.menu_options)
                    sound_mgr.play_key()
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.selected_button = (self.selected_button + 1) % len(self.menu_options)
                    sound_mgr.play_key()
                elif event.key == pygame.K_TAB:
                    mods = pygame.key.get_mods()
                    if mods & pygame.KMOD_SHIFT:
                        self.selected_button = (self.selected_button - 1) % len(self.menu_options)
                    else:
                        self.selected_button = (self.selected_button + 1) % len(self.menu_options)
                    sound_mgr.play_key()
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    sound_mgr.play_key()
                    return self._select_main_option(self.selected_button)
                elif event.key in (pygame.K_1, pygame.K_KP1):
                    sound_mgr.play_key()
                    return "TUTORIAL"
                elif event.key in (pygame.K_2, pygame.K_KP2):
                    sound_mgr.play_key()
                    return "CHALLENGE"
                elif event.key in (pygame.K_3, pygame.K_KP3):
                    sound_mgr.play_key()
                    return "SANDBOX"
                elif event.key in (pygame.K_4, pygame.K_KP4):
                    sound_mgr.play_key()
                    self.state = MenuState.HELP_GUIDE
                elif event.key in (pygame.K_5, pygame.K_KP5, pygame.K_ESCAPE):
                    sound_mgr.play_key()
                    return "EXIT"

        elif self.state == MenuState.PAUSE:
            # Mouse click in Pause Menu
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_x, mouse_y = event.pos
                for idx in range(3):
                    rect = self.get_pause_button_rect(idx, screen_w, screen_h)
                    if rect.collidepoint(mouse_x, mouse_y):
                        sound_mgr.play_key()
                        if idx == 0:
                            self.state = MenuState.IN_GAME
                            return "RESUME"
                        elif idx == 1:
                            return "RESTART"
                        elif idx == 2:
                            self.state = MenuState.MAIN_MENU
                            return "TO_MAIN_MENU"

            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_p):
                    self.state = MenuState.IN_GAME
                    return "RESUME"
                elif event.key == pygame.K_r:
                    return "RESTART"
                elif event.key == pygame.K_m:
                    self.state = MenuState.MAIN_MENU
                    return "TO_MAIN_MENU"

        elif self.state == MenuState.TUTORIAL_SELECT:
            return self._handle_tutorial_select_input(event, sound_mgr, screen_w, screen_h)

        elif self.state == MenuState.TOPOLOGY_MAP:
            action = self.topology_2d.handle_input(event, sound_mgr, screen_w, screen_h, mode)
            if action == "RESUME":
                self.state = MenuState.IN_GAME
            return action

        elif self.state == MenuState.HELP_GUIDE:
            return self._handle_help_guide_input(event, sound_mgr, screen_w, screen_h)

        elif self.state == MenuState.DEVICE_MANAGER:
            rects = self._compute_dm_rects(screen_w, screen_h)

            # 1. Keyboard handling in Device Manager
            if event.type == pygame.KEYDOWN:
                if self.dm_hostname_active:
                    if event.key == pygame.K_BACKSPACE:
                        self.dm_hostname_input = self.dm_hostname_input[:-1]
                        sound_mgr.play_key()
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                        self.dm_hostname_active = False
                        sound_mgr.play_key()
                    elif event.unicode and len(self.dm_hostname_input) < 22:
                        if event.unicode.isprintable():
                            self.dm_hostname_input += event.unicode
                            sound_mgr.play_key()
                    return None
                else:
                    if event.key in (pygame.K_ESCAPE, pygame.K_n):
                        sound_mgr.play_key()
                        self.state = MenuState.IN_GAME
                        return "RESUME"
                    elif event.key in (pygame.K_UP, pygame.K_PLUS, pygame.K_EQUALS):
                        self.dm_selected_slot = min(42, self.dm_selected_slot + 1)
                        sound_mgr.play_key()
                    elif event.key in (pygame.K_DOWN, pygame.K_MINUS):
                        self.dm_selected_slot = max(1, self.dm_selected_slot - 1)
                        sound_mgr.play_key()
                    elif event.key == pygame.K_TAB:
                        types = ["switch", "router", "firewall", "server"]
                        cur_idx = types.index(self.dm_selected_type)
                        self.dm_selected_type = types[(cur_idx + 1) % len(types)]
                        sound_mgr.play_key()

            # 2. Mouse Wheel scroll
            elif event.type == pygame.MOUSEWHEEL:
                self.dm_scroll_offset = max(0, self.dm_scroll_offset - event.y * 35)

            # 3. Mouse Click handling
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos

                # Close Button
                if rects["close_rect"].collidepoint(mx, my):
                    sound_mgr.play_key()
                    self.state = MenuState.IN_GAME
                    return "RESUME"

                # Filter Tabs
                for idx, tab_r in enumerate(rects["tab_rects"]):
                    if tab_r.collidepoint(mx, my):
                        self.dm_rack_filter = idx
                        self.dm_scroll_offset = 0
                        sound_mgr.play_key()
                        return None

                # Device List [Remove] buttons
                if mode and hasattr(mode, "devices"):
                    filtered_devs = [
                        d for d in mode.devices
                        if self.dm_rack_filter == 0 or d.rack_id == self.dm_rack_filter
                    ]
                    # Sort by rack then slot descending (top to bottom of rack)
                    filtered_devs.sort(key=lambda d: (
                        int(d.rack_id) if getattr(d, 'rack_id', None) is not None else 0,
                        -(int(d.u_slot) if getattr(d, 'u_slot', None) is not None else 0)
                    ))

                    row_h = 58
                    row_gap = 6
                    list_r = rects["list_rect"]
                    for i, dev in enumerate(filtered_devs):
                        ry = list_r.y + 4 + i * (row_h + row_gap) - self.dm_scroll_offset
                        if list_r.y <= ry <= list_r.bottom - row_h:
                            rem_btn = pygame.Rect(list_r.right - 85, ry + 14, 75, 28)
                            if rem_btn.collidepoint(mx, my):
                                ok, msg = mode.remove_device(dev)
                                self.dm_feedback = msg
                                self.dm_feedback_color = (220, 50, 40) if ok else (180, 100, 20)
                                sound_mgr.play_key()
                                return None

                # Right Panel: Device Type
                for t_name, t_rect in rects["type_rects"].items():
                    if t_rect.collidepoint(mx, my):
                        self.dm_selected_type = t_name
                        cnt = getattr(mode, "device_counter", 10) + 1 if mode else 10
                        if t_name == "switch":
                            self.dm_hostname_input = f"Switch-0{cnt}"
                        elif t_name == "router":
                            self.dm_hostname_input = f"Router-0{cnt}"
                        elif t_name == "firewall":
                            self.dm_hostname_input = f"Firewall-0{cnt}"
                        else:
                            self.dm_hostname_input = f"Server-0{cnt}"
                        sound_mgr.play_key()
                        return None

                # Destination Rack
                for r_id, r_rect in rects["rack_rects"].items():
                    if r_rect.collidepoint(mx, my):
                        self.dm_selected_rack = r_id
                        sound_mgr.play_key()
                        return None

                # Slot Stepper
                if rects["slot_minus_rect"].collidepoint(mx, my):
                    self.dm_selected_slot = max(1, self.dm_selected_slot - 1)
                    sound_mgr.play_key()
                    return None
                elif rects["slot_plus_rect"].collidepoint(mx, my):
                    self.dm_selected_slot = min(42, self.dm_selected_slot + 1)
                    sound_mgr.play_key()
                    return None

                # Hostname input box
                if rects["hostname_rect"].collidepoint(mx, my):
                    self.dm_hostname_active = True
                    sound_mgr.play_key()
                    return None
                else:
                    self.dm_hostname_active = False

                # Install Button
                if rects["install_btn_rect"].collidepoint(mx, my):
                    if mode and hasattr(mode, "add_device"):
                        ok, msg, new_dev = mode.add_device(
                            self.dm_selected_type,
                            self.dm_selected_rack,
                            self.dm_selected_slot,
                            self.dm_hostname_input
                        )
                        if ok:
                            self.dm_feedback = msg
                            self.dm_feedback_color = (15, 140, 65)
                            # Advance slot for next equipment
                            span = 1 if self.dm_selected_type in ("switch", "firewall") else 2
                            self.dm_selected_slot = min(42, self.dm_selected_slot + span)
                            cnt = getattr(mode, "device_counter", 10) + 1
                            if self.dm_selected_type == "switch":
                                self.dm_hostname_input = f"Switch-0{cnt}"
                            elif self.dm_selected_type == "router":
                                self.dm_hostname_input = f"Router-0{cnt}"
                            elif self.dm_selected_type == "firewall":
                                self.dm_hostname_input = f"Firewall-0{cnt}"
                            else:
                                self.dm_hostname_input = f"Server-0{cnt}"
                        else:
                            self.dm_feedback = msg
                            self.dm_feedback_color = (220, 50, 40)
                            sound_mgr.play_key()
                        return None

        return None

    def _select_main_option(self, idx):
        if idx == 0:
            return "TUTORIAL"
        elif idx == 1:
            return "CHALLENGE"
        elif idx == 2:
            return "SANDBOX"
        elif idx == 3:
            self.help_guide_prev_state = MenuState.MAIN_MENU
            self.state = MenuState.HELP_GUIDE
            return None
        elif idx == 4:
            return "EXIT"
        return None

    def _handle_help_guide_input(self, event, sound_mgr, screen_w, screen_h):
        vp_rect = pygame.Rect(*self.get_showcase_viewport(screen_w, screen_h))

        # 1. Mouse Button Down
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mouse_pos = event.pos

                # Check device selector tabs
                for idx, tab_rect in enumerate(getattr(self, "_last_device_tab_rects", [])):
                    if tab_rect.collidepoint(mouse_pos):
                        if self.showcase_selected_idx != idx:
                            self.showcase_selected_idx = idx
                            self.showcase_cat_idx = 0
                            self.showcase_scroll_y = 0
                            sound_mgr.play_key()
                        return None

                # Check 3D Viewport drag initiation
                if vp_rect.collidepoint(mouse_pos):
                    self.showcase_dragging = True
                    self.showcase_last_mouse = mouse_pos
                    return None

                # Check Category Filter pills in right pane
                for c_idx, cat_rect in enumerate(getattr(self, "_last_category_rects", [])):
                    if cat_rect.collidepoint(mouse_pos):
                        if self.showcase_cat_idx != c_idx:
                            self.showcase_cat_idx = c_idx
                            self.showcase_scroll_y = 0
                            sound_mgr.play_key()
                        return None

                # Check Back button
                back_rect = getattr(self, "_last_back_btn_rect", None)
                if back_rect and back_rect.collidepoint(mouse_pos):
                    sound_mgr.play_key()
                    self.showcase_dragging = False
                    self.state = getattr(self, "help_guide_prev_state", MenuState.MAIN_MENU)
                    return "RESUME" if self.state == MenuState.IN_GAME else None

            # Mouse wheel scroll (buttons 4 and 5) in command list
            elif event.button == 4:
                self.showcase_scroll_y = max(0, self.showcase_scroll_y - 45)
            elif event.button == 5:
                max_s = getattr(self, "_max_scroll_y", 0)
                self.showcase_scroll_y = max(0, min(max_s, self.showcase_scroll_y + 45))

        # 2. Mouse Button Up
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.showcase_dragging = False

        # 3. Mouse Motion
        elif event.type == pygame.MOUSEMOTION:
            if getattr(self, "showcase_dragging", False):
                dx = event.pos[0] - self.showcase_last_mouse[0]
                dy = event.pos[1] - self.showcase_last_mouse[1]
                self.showcase_yaw = (self.showcase_yaw + dx * 0.75) % 360.0
                self.showcase_pitch = max(-80.0, min(80.0, self.showcase_pitch + dy * 0.75))
                self.showcase_last_mouse = event.pos

        # 4. Mouse Wheel (Vertical scroll in right pane - NO zoom per user request)
        elif event.type == pygame.MOUSEWHEEL:
            max_s = getattr(self, "_max_scroll_y", 0)
            self.showcase_scroll_y = max(0, min(max_s, self.showcase_scroll_y - event.y * 45))

        # 5. Keyboard Navigation
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                sound_mgr.play_key()
                self.showcase_dragging = False
                self.state = getattr(self, "help_guide_prev_state", MenuState.MAIN_MENU)
                return "RESUME" if self.state == MenuState.IN_GAME else None

            elif event.key in (pygame.K_1, pygame.K_KP1):
                self.showcase_selected_idx = 0; self.showcase_cat_idx = 0; self.showcase_scroll_y = 0; sound_mgr.play_key()
            elif event.key in (pygame.K_2, pygame.K_KP2):
                self.showcase_selected_idx = 1; self.showcase_cat_idx = 0; self.showcase_scroll_y = 0; sound_mgr.play_key()
            elif event.key in (pygame.K_3, pygame.K_KP3):
                self.showcase_selected_idx = 2; self.showcase_cat_idx = 0; self.showcase_scroll_y = 0; sound_mgr.play_key()
            elif event.key in (pygame.K_4, pygame.K_KP4):
                self.showcase_selected_idx = 3; self.showcase_cat_idx = 0; self.showcase_scroll_y = 0; sound_mgr.play_key()
            elif event.key in (pygame.K_5, pygame.K_KP5):
                self.showcase_selected_idx = 4; self.showcase_cat_idx = 0; self.showcase_scroll_y = 0; sound_mgr.play_key()
            elif event.key in (pygame.K_6, pygame.K_KP6):
                self.showcase_selected_idx = 5; self.showcase_cat_idx = 0; self.showcase_scroll_y = 0; sound_mgr.play_key()

            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self.showcase_selected_idx = (self.showcase_selected_idx - 1) % len(self.showcase_devices)
                self.showcase_cat_idx = 0; self.showcase_scroll_y = 0; sound_mgr.play_key()
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.showcase_selected_idx = (self.showcase_selected_idx + 1) % len(self.showcase_devices)
                self.showcase_cat_idx = 0; self.showcase_scroll_y = 0; sound_mgr.play_key()

            elif event.key in (pygame.K_UP, pygame.K_PAGEUP):
                self.showcase_scroll_y = max(0, self.showcase_scroll_y - 45)
            elif event.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
                max_s = getattr(self, "_max_scroll_y", 0)
                self.showcase_scroll_y = max(0, min(max_s, self.showcase_scroll_y + 45))

        return None

    def _get_completed_chapters(self):
        """Read completed chapters list from tutorial_progress.json."""
        progress_path = "tutorial_progress.json"
        if os.path.exists(progress_path):
            try:
                with open(progress_path, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    if isinstance(data, dict):
                        return data.get("completed_chapters", [])
            except Exception:
                pass
        return []

    def _draw_tutorial_chapter_select(self, surface, screen_w, screen_h):
        """Draw interactive Chapter Selection Cards screen for Tutorial Mode."""
        # 1. Semi-transparent dark blue backdrop overlay
        overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        overlay.fill((10, 18, 32, 235))
        surface.blit(overlay, (0, 0))

        # 2. Header Bar
        self._tutorial_back_btn_rect = pygame.Rect(28, 18, 220, 36)
        mx, my = pygame.mouse.get_pos()
        is_back_hov = self._tutorial_back_btn_rect.collidepoint(mx, my)
        back_bg = (28, 48, 76) if is_back_hov else (18, 32, 54)
        back_border = (0, 160, 255) if is_back_hov else (45, 75, 115)
        pygame.draw.rect(surface, back_bg, self._tutorial_back_btn_rect, border_radius=6)
        pygame.draw.rect(surface, back_border, self._tutorial_back_btn_rect, width=1, border_radius=6)
        b_txt = self.font_guide_btn.render("< Return to Menu [ESC]", True, (240, 248, 255))
        surface.blit(b_txt, (self._tutorial_back_btn_rect.x + (self._tutorial_back_btn_rect.w - b_txt.get_width()) // 2, self._tutorial_back_btn_rect.y + 8))

        # Title & Subtitle
        header_title = self.font_guide_title.render("NETENGINEER ACADEMY // TRAINING CHAPTERS", True, (240, 248, 255))
        sub_title = self.font_guide_sub.render("Master hands-on network engineering from datacenter hardware to Cisco CLI", True, (100, 185, 255))
        surface.blit(header_title, (self._tutorial_back_btn_rect.right + 28, 12))
        surface.blit(sub_title, (self._tutorial_back_btn_rect.right + 28, 42))

        # 3. Chapter Cards Layout
        completed = self._get_completed_chapters()
        card_w = min(365, (screen_w - 90) // 3)
        card_h = min(545, screen_h - 145)
        gap = 18
        total_w = 3 * card_w + 2 * gap
        start_x = (screen_w - total_w) // 2
        card_y = 72

        chapters = [
            {
                "id": "chapter_1",
                "tag": "CHAPTER 01",
                "name": "Datacenter Onboarding",
                "desc_th": "สอนเล่น * ติดตั้งตู้ Rack * ต่อสาย * Cisco CLI * 2D Topology",
                "desc_en": "Learn foundational network engineer controls, equipment mounting, cabling, Cisco IOS modes, and 2D topology.",
                "pillars": [
                    "[1] Controls & Orientation (WASD, Mouse, Sprint)",
                    "[2] 42U Rack Equipment Mounting ([N])",
                    "[3] Physical Layer Cabling (Cat6 Server to Switch)",
                    "[4] Cisco IOS Navigation (User -> Config Mode)",
                    "[5] 2D Logical Topology & Inspection (Packet Tracer)",
                ],
                "diff": "BEGINNER",
                "time": "~5-8 MIN",
                "is_unlocked": True,
                "is_completed": "chapter_1" in completed,
            },
            {
                "id": "chapter_2",
                "tag": "CHAPTER 02",
                "name": "Switching & VLANs",
                "desc_th": "VLAN * Access / Trunk (802.1Q) * Spanning Tree (STP)",
                "desc_en": "Master Layer 2 broadcast domains, VLAN tagging, multi-VLAN trunks, and STP loop avoidance.",
                "pillars": [
                    "[1] VLAN Broadcast Domains (VLAN 10, 20)",
                    "[2] Switchport Mode Access Configuration",
                    "[3] 802.1Q Multi-VLAN Trunking & Native VLAN",
                    "[4] Rapid Per-VLAN Spanning Tree (STP)",
                    "[5] SVI Management Interface & Gateway",
                ],
                "diff": "INTERMEDIATE",
                "time": "~10-15 MIN",
                "is_unlocked": False,
                "is_completed": False,
            },
            {
                "id": "chapter_3",
                "tag": "CHAPTER 03",
                "name": "IP Routing & NAT Gateway",
                "desc_th": "Static Route * OSPF * DHCP Server * NAT/PAT Overload",
                "desc_en": "Configure Layer 3 static and dynamic OSPF routing, DHCP automated addressing, and NAT internet access.",
                "pillars": [
                    "[1] Default Route (Gateway of Last Resort)",
                    "[2] Dynamic Routing with OSPF Area 0",
                    "[3] Cisco IOS DHCP Server Address Pools",
                    "[4] NAT / PAT Overload for Internet Access",
                    "[5] Multi-hop Ping & Traceroute Verification",
                ],
                "diff": "ADVANCED",
                "time": "~15-20 MIN",
                "is_unlocked": False,
                "is_completed": False,
            }
        ]

        self._chapter_card_rects = []
        for idx, ch in enumerate(chapters):
            cx = start_x + idx * (card_w + gap)
            card_rect = pygame.Rect(cx, card_y, card_w, card_h)
            self._chapter_card_rects.append(card_rect)

            is_sel = (self.selected_chapter_idx == idx)
            is_hover = card_rect.collidepoint(mx, my)

            # Card Background
            card_bg = (255, 255, 255) if ch["is_unlocked"] else (24, 34, 48)
            border_col = (0, 140, 255) if (is_sel or is_hover) and ch["is_unlocked"] else ((65, 95, 135) if (is_sel or is_hover) else ((195, 215, 238) if ch["is_unlocked"] else (38, 52, 70)))
            border_w = 2 if (is_sel or is_hover) else 1

            pygame.draw.rect(surface, card_bg, card_rect, border_radius=10)
            pygame.draw.rect(surface, border_col, card_rect, width=border_w, border_radius=10)

            # Card Header Banner
            banner_h = 42
            banner_bg = (235, 244, 255) if ch["is_unlocked"] else (20, 28, 40)
            pygame.draw.rect(surface, banner_bg, (card_rect.x, card_rect.y, card_rect.w, banner_h), border_top_left_radius=10, border_top_right_radius=10)
            pygame.draw.line(surface, border_col, (card_rect.x, card_rect.y + banner_h), (card_rect.right, card_rect.y + banner_h), 1)

            # Chapter Tag
            tag_col = (0, 95, 200) if ch["is_unlocked"] else (130, 150, 175)
            tag_s = self.font_guide_cmd.render(ch["tag"], True, tag_col)
            surface.blit(tag_s, (card_rect.x + 14, card_rect.y + 11))

            # Status Badge
            if ch["is_completed"]:
                b_text = "COMPLETED"
                b_bg = (20, 165, 75)
                b_tc = (255, 255, 255)
            elif ch["is_unlocked"]:
                b_text = "AVAILABLE"
                b_bg = (0, 115, 230)
                b_tc = (255, 255, 255)
            else:
                b_text = "COMING SOON"
                b_bg = (40, 52, 68)
                b_tc = (150, 170, 195)

            b_surf = self.font_badge.render(b_text, True, b_tc)
            bw = b_surf.get_width() + 14
            b_rect = pygame.Rect(card_rect.right - bw - 12, card_rect.y + 9, bw, 24)
            pygame.draw.rect(surface, b_bg, b_rect, border_radius=12)
            surface.blit(b_surf, (b_rect.x + 7, b_rect.y + 4))

            # Chapter Title
            title_col = (10, 35, 75) if ch["is_unlocked"] else (200, 215, 235)
            title_s = self.font_guide_dev_title.render(ch["name"], True, title_col)
            surface.blit(title_s, (card_rect.x + 14, card_rect.y + 52))

            # Subtitle (Thai)
            sub_col = (0, 0, 0) if ch["is_unlocked"] else (135, 155, 180)
            sub_s = self.font_thai_small.render(ch["desc_th"], True, sub_col)
            surface.blit(sub_s, (card_rect.x + 14, card_rect.y + 76))

            # Divider
            div_y = card_rect.y + 100
            div_col = (225, 235, 246) if ch["is_unlocked"] else (36, 48, 64)
            pygame.draw.line(surface, div_col, (card_rect.x + 12, div_y), (card_rect.right - 12, div_y), 1)

            # Highlights List
            line_y = div_y + 12
            for pil in ch["pillars"]:
                p_col = (0, 0, 0) if ch["is_unlocked"] else (120, 140, 165)
                pil_s = self.font_small.render(pil, True, p_col)
                surface.blit(pil_s, (card_rect.x + 14, line_y))
                line_y += 24

            # Meta Info (Difficulty & Duration)
            meta_y = card_rect.y + card_h - 96
            pygame.draw.line(surface, div_col, (card_rect.x + 12, meta_y - 6), (card_rect.right - 12, meta_y - 6), 1)
            diff_col = (0, 0, 0) if ch["is_unlocked"] else (130, 150, 175)
            d_surf = self.font_small.render(f"Difficulty: {ch['diff']}   |   Est: {ch['time']}", True, diff_col)
            surface.blit(d_surf, (card_rect.x + 14, meta_y))

            # Action Button
            btn_rect = pygame.Rect(card_rect.x + 14, card_rect.y + card_h - 54, card_rect.w - 28, 40)
            if ch["is_unlocked"]:
                btn_hov = btn_rect.collidepoint(mx, my) or is_sel
                btn_bg = (0, 135, 255) if btn_hov else (0, 110, 225)
                pygame.draw.rect(surface, btn_bg, btn_rect, border_radius=6)
                btn_label = "[ REPLAY CHAPTER 1 ]" if ch["is_completed"] else "[ START CHAPTER 1 ]"
                btn_s = self.font_btn.render(btn_label, True, (255, 255, 255))
                surface.blit(btn_s, (btn_rect.x + (btn_rect.w - btn_s.get_width()) // 2, btn_rect.y + 10))
            else:
                pygame.draw.rect(surface, (32, 44, 58), btn_rect, border_radius=6)
                pygame.draw.rect(surface, (45, 58, 75), btn_rect, width=1, border_radius=6)
                btn_s = self.font_btn.render("[ LOCKED ]", True, (110, 130, 155))
                surface.blit(btn_s, (btn_rect.x + (btn_rect.w - btn_s.get_width()) // 2, btn_rect.y + 10))

        # 4. Bottom Hint Bar
        bot_bar_h = 36
        bot_y = screen_h - bot_bar_h
        pygame.draw.rect(surface, (14, 22, 36), (0, bot_y, screen_w, bot_bar_h))
        pygame.draw.line(surface, (35, 52, 75), (0, bot_y), (screen_w, bot_bar_h), 1)
        hint_text = "[<] [>] Arrow Keys: Select Chapter   |   [ENTER] / Click: Launch Chapter 1   |   [ESC] Return to Main Menu"
        hint_s = self.font_body.render(hint_text, True, (200, 220, 245))
        surface.blit(hint_s, ((screen_w - hint_s.get_width()) // 2, bot_y + 8))

    def _handle_tutorial_select_input(self, event, sound_mgr, screen_w, screen_h):
        """Handles mouse & keyboard inputs on Chapter Select Screen."""
        # 1. Mouse Motion
        if event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            for idx, r in enumerate(self._chapter_card_rects):
                if r.collidepoint(mx, my):
                    if self.selected_chapter_idx != idx:
                        self.selected_chapter_idx = idx
                        sound_mgr.play_key()
                    break

        # 2. Mouse Click
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # Back Button
            if self._tutorial_back_btn_rect and self._tutorial_back_btn_rect.collidepoint(mx, my):
                sound_mgr.play_key()
                self.state = MenuState.MAIN_MENU
                return "TO_MAIN_MENU"

            # Cards
            for idx, r in enumerate(self._chapter_card_rects):
                if r.collidepoint(mx, my):
                    if idx == 0:
                        sound_mgr.play_objective()
                        self.state = MenuState.IN_GAME
                        return "START_TUTORIAL:1"
                    else:
                        sound_mgr.play_key()
                        self.selected_chapter_idx = idx
                    return None

        # 3. Keyboard
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.selected_chapter_idx = max(0, self.selected_chapter_idx - 1)
                sound_mgr.play_key()
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.selected_chapter_idx = min(2, self.selected_chapter_idx + 1)
                sound_mgr.play_key()
            elif event.key in (pygame.K_1, pygame.K_KP1):
                self.selected_chapter_idx = 0
                sound_mgr.play_objective()
                self.state = MenuState.IN_GAME
                return "START_TUTORIAL:1"
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                if self.selected_chapter_idx == 0:
                    sound_mgr.play_objective()
                    self.state = MenuState.IN_GAME
                    return "START_TUTORIAL:1"
                else:
                    sound_mgr.play_key()
            elif event.key in (pygame.K_ESCAPE, pygame.K_m, pygame.K_BACKSPACE):
                sound_mgr.play_key()
                self.state = MenuState.MAIN_MENU
                return "TO_MAIN_MENU"

        return None


    def render(self, surface, screen_w, screen_h, devices=None, cables=None, mode=None):
        if self.state == MenuState.MAIN_MENU:
            self._render_main_menu(surface, screen_w, screen_h)
        elif self.state == MenuState.PAUSE:
            self._render_pause_menu(surface, screen_w, screen_h)
        elif self.state == MenuState.TOPOLOGY_MAP:
            self.topology_2d.render(surface, screen_w, screen_h, devices, cables, mode)
        elif self.state == MenuState.TUTORIAL_SELECT:
            self._draw_tutorial_chapter_select(surface, screen_w, screen_h)
        elif self.state == MenuState.HELP_GUIDE:
            self._render_help_guide(surface, screen_w, screen_h)
        elif self.state == MenuState.DEVICE_MANAGER:
            self._render_device_manager(surface, screen_w, screen_h, mode)

    def _draw_menu_bezier_cable(self, surface, p0, p1, p2, p3, color, width=2):
        """Draws smooth anti-aliased cubic Bezier cable with depth shadow and connector boots."""
        steps = 22
        pts = []
        for i in range(steps + 1):
            t = i / steps
            u = 1.0 - t
            x = (u**3)*p0[0] + 3*(u**2)*t*p1[0] + 3*u*(t**2)*p2[0] + (t**3)*p3[0]
            y = (u**3)*p0[1] + 3*(u**2)*t*p1[1] + 3*u*(t**2)*p2[1] + (t**3)*p3[1]
            pts.append((int(x), int(y)))

        shadow = (max(0, color[0] // 4), max(0, color[1] // 4), max(0, color[2] // 4))
        pygame.draw.lines(surface, shadow, False, pts, width + 2)
        pygame.draw.lines(surface, color, False, pts, width)
        pygame.draw.rect(surface, (38, 44, 56), (pts[0][0]-2, pts[0][1]-2, 5, 5), border_radius=1)
        pygame.draw.rect(surface, (38, 44, 56), (pts[-1][0]-2, pts[-1][1]-2, 5, 5), border_radius=1)

    def _render_main_menu(self, surface, w, h):
        now = pygame.time.get_ticks() / 1000.0

        # Start with transparent surface so the real 3D OpenGL datacenter scene shines through
        surface.fill((0, 0, 0, 0))

        # =========================================================================
        # LEFT PANE: TRANSLUCENT FROSTED GLASS OVERLAY CARD
        # =========================================================================
        left_w = min(470, max(420, int(w * 0.36)))

        glass_card = pygame.Surface((left_w, h), pygame.SRCALPHA)
        glass_card.fill((246, 249, 254, 235))

        # Subtle blueprint grid on the glass card
        grid_color = (230, 238, 248)
        for x in range(0, left_w, 40):
            pygame.draw.line(glass_card, grid_color, (x, 0), (x, h), 1)
        for y in range(0, h, 40):
            pygame.draw.line(glass_card, grid_color, (0, y), (left_w, y), 1)

        # Right border edge with subtle divider line
        pygame.draw.line(glass_card, (205, 218, 235), (left_w - 1, 0), (left_w - 1, h), 1)
        surface.blit(glass_card, (0, 0))

        # Soft floating shadow to the right of the glass pane
        for s_i in range(6):
            s_alpha = int(18 * (1.0 - s_i / 6.0))
            shadow_strip = pygame.Surface((1, h), pygame.SRCALPHA)
            shadow_strip.fill((10, 20, 35, s_alpha))
            surface.blit(shadow_strip, (left_w + s_i, 0))

        left_x = 48

        # Datacenter Live Status Badge
        badge_w, badge_h = 245, 24
        pygame.draw.rect(surface, (232, 242, 255), (left_x, 48, badge_w, badge_h), border_radius=12)
        pygame.draw.rect(surface, (180, 210, 245), (left_x, 48, badge_w, badge_h), width=1, border_radius=12)
        live_dot_color = (30, 210, 95) if (int(now * 2.0) % 2 == 0) else (15, 140, 60)
        pygame.draw.circle(surface, live_dot_color, (left_x + 14, 60), 4)
        tag_text = self.font_rack_micro.render("NETENGINEER // 3D DATACENTER ENGINE", True, (0, 85, 185))
        surface.blit(tag_text, (left_x + 24, 53))

        # Title Card
        logo_surf = self.font_logo.render("NETENGINEER 3D", True, (14, 38, 75))
        sub_surf = self.font_sub.render("Enterprise Datacenter & Cisco IOS Simulator", True, (0, 102, 204))
        surface.blit(logo_surf, (left_x, 75))
        surface.blit(sub_surf, (left_x, 126))

        specs_text = self.font_small.render("Layer 2/3 Switching  *  STP 802.1D  *  OSPF/NAT  *  Cisco CLI", True, (0, 0, 0))
        surface.blit(specs_text, (left_x, 154))

        btn_w = self.get_main_menu_button_rect(0, w, h).width
        pygame.draw.line(surface, (215, 226, 240), (left_x, 178), (left_x + btn_w, 178), 1)

        # Menu Buttons (Left-Aligned)
        for i, (title, desc) in enumerate(self.menu_options):
            btn_rect = self.get_main_menu_button_rect(i, w, h)
            is_hover = (i == self.selected_button)

            bg_col = (235, 245, 255) if is_hover else (255, 255, 255)
            border_col = (0, 115, 230) if is_hover else (205, 218, 235)

            # Drop shadow
            shadow_rect = pygame.Rect(btn_rect.x + 2, btn_rect.y + 3, btn_rect.w, btn_rect.h)
            pygame.draw.rect(surface, (210, 222, 238), shadow_rect, border_radius=8)

            pygame.draw.rect(surface, bg_col, btn_rect, border_radius=8)
            pygame.draw.rect(surface, border_col, btn_rect, width=2 if is_hover else 1, border_radius=8)

            # Active indicator bar on left edge
            if is_hover:
                pygame.draw.rect(surface, (0, 115, 230), (btn_rect.x, btn_rect.y, 5, btn_rect.h), border_top_left_radius=8, border_bottom_left_radius=8)

            t_color = (0, 85, 200) if is_hover else (0, 0, 0)
            d_color = (0, 105, 215) if is_hover else (0, 0, 0)

            t_surf = self.font_btn.render(f"[{i+1}] {title}", True, t_color)
            d_surf = self.font_body.render(desc, True, d_color)

            surface.blit(t_surf, (btn_rect.x + (22 if is_hover else 18), btn_rect.y + 8))
            surface.blit(d_surf, (btn_rect.x + (22 if is_hover else 18), btn_rect.y + 32))

        # Bottom System Info Card (Left)
        info_y = min(h - 135, self.get_main_menu_button_rect(4, w, h).bottom + 22)
        if info_y + 80 < h:
            info_rect = pygame.Rect(left_x, info_y, btn_w, 75)
            pygame.draw.rect(surface, (255, 255, 255), info_rect, border_radius=8)
            pygame.draw.rect(surface, (215, 228, 245), info_rect, width=1, border_radius=8)

            s1 = self.font_rack_micro.render("LIVE 3D ENGINE: 42U DUAL RACKS * CATENARY PHYSICS", True, (15, 135, 65))
            s2 = self.font_small.render("Controls: [1]-[5] / [W][S] / Mouse Click  |  [F11] Fullscreen", True, (0, 0, 0))
            s3 = self.font_small.render("Hardware: Real-Time 3D Cables & Blinking Status LEDs", True, (0, 0, 0))
            surface.blit(s1, (info_rect.x + 14, info_rect.y + 10))
            surface.blit(s2, (info_rect.x + 14, info_rect.y + 30))
            surface.blit(s3, (info_rect.x + 14, info_rect.y + 50))

        # Bottom hint
        footer = self.font_small.render("Click buttons with MOUSE, or press [1]-[5] / [Up/Down] + [ENTER]", True, (0, 0, 0))
        surface.blit(footer, (left_x, h - 30))

    def _render_main_menu_racks(self, surface, w, h, now):
        """Renders 2 detailed enterprise server racks side-by-side with full devices, cabling and animated LEDs."""
        btn_r0 = self.get_main_menu_button_rect(0, w, h)
        left_start = btn_r0.right + 45
        right_end = w - 45
        avail_w = max(400, right_end - left_start)

        gap = min(50, max(30, int(avail_w * 0.07)))
        rw = min(320, max(260, (avail_w - gap) // 2))
        total_w = rw * 2 + gap
        r1_x = left_start + max(0, (avail_w - total_w) // 2)
        r2_x = r1_x + rw + gap

        top_y = 52
        bottom_y = h - 42
        rack_h = bottom_y - top_y

        # -------------------------------------------------------------------------
        # 1. TOP OVERHEAD CABLE TRAY / LADDER RACK (BRIDGING BOTH RACKS)
        # -------------------------------------------------------------------------
        tray_x1 = r1_x - 14
        tray_x2 = r2_x + rw + 14
        tray_y = 22
        tray_h = 24

        # Steel Ladder Tray Rails
        pygame.draw.rect(surface, (238, 242, 248), (tray_x1, tray_y, tray_x2 - tray_x1, tray_h), border_radius=4)
        pygame.draw.rect(surface, (160, 175, 195), (tray_x1, tray_y, tray_x2 - tray_x1, tray_h), width=1, border_radius=4)
        pygame.draw.line(surface, (140, 155, 175), (tray_x1, tray_y + 4), (tray_x2, tray_y + 4), 2)
        pygame.draw.line(surface, (140, 155, 175), (tray_x1, tray_y + tray_h - 4), (tray_x2, tray_y + tray_h - 4), 2)

        # Ladder rungs
        for rung_x in range(tray_x1 + 15, tray_x2 - 10, 18):
            pygame.draw.line(surface, (170, 185, 205), (rung_x, tray_y + 4), (rung_x, tray_y + tray_h - 4), 2)

        # Yellow Fiber Optic Duct in center
        duct_y = tray_y + 7
        duct_h = 10
        pygame.draw.rect(surface, (245, 185, 20), (tray_x1 + 8, duct_y, tray_x2 - tray_x1 - 16, duct_h), border_radius=3)
        pygame.draw.rect(surface, (205, 145, 10), (tray_x1 + 8, duct_y, tray_x2 - tray_x1 - 16, duct_h), width=1, border_radius=3)

        duct_lbl = self.font_rack_nano.render("100G FIBER BACKBONE DUCT // OM4 / OS2", True, (60, 45, 5))
        surface.blit(duct_lbl, (r1_x + (total_w - duct_lbl.get_width()) // 2, duct_y - 1))

        # -------------------------------------------------------------------------
        # 2. RACK ENCLOSURES & VERTICAL 19" RAILS
        # -------------------------------------------------------------------------
        racks_meta = [
            (r1_x, "RACK-A01", "CORE / SPINE", 21.4, 0.86),
            (r2_x, "RACK-A02", "DIST / LEAF", 22.8, 1.14)
        ]

        for rx, r_label, r_sub, temp_c, kw in racks_meta:
            # Drop shadow
            pygame.draw.rect(surface, (216, 226, 238), (rx + 4, top_y + 4, rw, rack_h), border_radius=8)
            # Outer dark steel chassis
            pygame.draw.rect(surface, (20, 24, 32), (rx, top_y, rw, rack_h), border_radius=8)
            pygame.draw.rect(surface, (55, 65, 80), (rx, top_y, rw, rack_h), width=2, border_radius=8)

            # Header Banner (OLED & Status)
            header_h = 38
            pygame.draw.rect(surface, (28, 34, 46), (rx, top_y, rw, header_h), border_top_left_radius=8, border_top_right_radius=8)
            pygame.draw.line(surface, (60, 72, 92), (rx, top_y + header_h), (rx + rw, top_y + header_h), 1)

            # Top Breathing Beacon Bar
            pulse = 0.75 + 0.25 * math.sin(now * 2.5 + (0.0 if rx == r1_x else 1.6))
            beacon_col = (int(0 * pulse), int(210 * pulse), int(255 * pulse))
            pygame.draw.line(surface, beacon_col, (rx + 12, top_y + 4), (rx + rw - 12, top_y + 4), 2)

            # Rack Name & Role
            t_badge = self.font_rack_badge.render(r_label, True, (255, 255, 255))
            t_role = self.font_rack_micro.render(r_sub, True, (0, 215, 255))
            surface.blit(t_badge, (rx + 12, top_y + 8))
            surface.blit(t_role, (rx + 12 + t_badge.get_width() + 8, top_y + 10))

            # OLED Digital Readout
            oled_text = f"{temp_c:.1f}C * {kw:.2f}kW * OK"
            t_oled = self.font_rack_nano.render(oled_text, True, (35, 235, 120))
            surface.blit(t_oled, (rx + rw - t_oled.get_width() - 14, top_y + 11))

            # Inner Equipment Bay
            inner_x = rx + 14
            inner_w = rw - 28
            bay_top = top_y + header_h + 2
            bay_bot = bottom_y - 28
            bay_h = bay_bot - bay_top

            pygame.draw.rect(surface, (14, 17, 24), (inner_x, bay_top, inner_w, bay_h))

            # Vertical 19" Mounting Rails (Left & Right) with cage nut holes & U ticks
            rail_w = 8
            for rail_x in (inner_x - rail_w + 2, inner_x + inner_w - 2):
                pygame.draw.rect(surface, (36, 42, 54), (rail_x, bay_top, rail_w, bay_h))
                for tick_y in range(bay_top + 6, bay_bot - 6, 10):
                    pygame.draw.rect(surface, (16, 20, 28), (rail_x + 2, tick_y, 4, 3))

            # Base & Casters
            base_y = bottom_y - 26
            pygame.draw.rect(surface, (25, 30, 40), (rx, base_y, rw, 26), border_bottom_left_radius=8, border_bottom_right_radius=8)
            pygame.draw.line(surface, (50, 60, 75), (rx, base_y), (rx + rw, base_y), 1)

            # Casters
            for cx in (rx + 22, rx + rw - 36):
                pygame.draw.rect(surface, (80, 90, 105), (cx, base_y + 8, 14, 12), border_radius=2)
                pygame.draw.rect(surface, (45, 52, 62), (cx + 2, base_y + 14, 10, 8), border_radius=1)

            # Grounding wire
            pygame.draw.line(surface, (50, 180, 60), (rx + 10, base_y + 16), (rx + 10, base_y + 24), 2)
            pygame.draw.circle(surface, (215, 170, 40), (rx + 10, base_y + 16), 3)

        # -------------------------------------------------------------------------
        # 3. FULL DEVICE HARDWARE IN BOTH RACKS
        # -------------------------------------------------------------------------
        bay_top = top_y + 40
        ix1 = r1_x + 14
        iw = rw - 28
        ix2 = r2_x + 14

        # Slot layout definitions: (slot_idx, rel_y, h, name)
        # Total height budget approx ~ 520px
        slots = [
            (1,  0,   20, "brush"),      # Cable Brush Panel
            (2,  22,  48, "router"),     # Cisco ASR 1002-HX Router (2U)
            (3,  72,  32, "patch_a"),    # 24-Port Cat6 Patch Panel 1A
            (4,  106, 36, "switch_core1"),# Catalyst 9300-48P Core Switch #1
            (5,  144, 36, "switch_core2"),# Catalyst 9300-48P Core Switch #2
            (6,  182, 24, "wire_mgr"),   # 1U D-Ring Horizontal Wire Manager
            (7,  208, 34, "firewall"),   # Next-Gen Enterprise Firewall
            (8,  244, 28, "fiber_liu"),  # Fiber Optic LIU / ODF Tray
            (9,  274, 56, "server_san"),  # Dell PowerEdge Storage SAN (2U)
            (10, 332, 56, "server_host"), # Dell PowerEdge Compute Node (2U)
            (11, 390, 28, "sensor"),     # NetBotz Environmental Hub
            (12, 420, 56, "ups"),        # APC Smart-UPS 3000VA (2U)
        ]

        # Port coordinates map for drawing patch cables
        p_coords = {}

        # ------------------ RACK 1 DEVICES ------------------
        for sid, sy, sh, stype in slots:
            dy = bay_top + sy
            dev_rect = pygame.Rect(ix1, dy, iw, sh)

            if stype == "brush":
                pygame.draw.rect(surface, (26, 30, 38), dev_rect)
                # Nylon brush bristles
                pygame.draw.rect(surface, (12, 15, 20), (ix1 + 10, dy + 5, iw - 20, sh - 10))
                for bx in range(ix1 + 14, ix1 + iw - 14, 4):
                    pygame.draw.line(surface, (40, 48, 60), (bx, dy + 6), (bx, dy + sh - 6), 1)

            elif stype == "router":
                # Cisco ASR 1002-HX Titanium Faceplate
                pygame.draw.rect(surface, (34, 44, 60), dev_rect)
                pygame.draw.rect(surface, (55, 70, 95), dev_rect, width=1)
                # Cisco badge
                pygame.draw.rect(surface, (0, 115, 200), (ix1 + 8, dy + 8, 4, sh - 16))
                lbl = self.font_rack_micro.render("CISCO ASR 1002-HX", True, (230, 240, 255))
                surface.blit(lbl, (ix1 + 16, dy + 6))
                # Router status LEDs: PWR1, PWR2, STAT, ACT
                pwr1_col = (25, 230, 80)
                pwr2_col = (25, 230, 80)
                act_col = (255, 200, 30) if ((int(now * 4.0) % 3) != 0) else (30, 220, 80)
                pygame.draw.circle(surface, pwr1_col, (ix1 + 18, dy + 24), 2)
                pygame.draw.circle(surface, pwr2_col, (ix1 + 26, dy + 24), 2)
                pygame.draw.circle(surface, act_col, (ix1 + 34, dy + 24), 2)
                led_txt = self.font_rack_nano.render("PWR STAT ACT", True, (130, 155, 185))
                surface.blit(led_txt, (ix1 + 42, dy + 20))

                # Console / Aux ports
                pygame.draw.rect(surface, (0, 140, 220), (ix1 + 115, dy + 18, 10, 10), border_radius=2)
                p_coords["r1_router_con"] = (ix1 + 120, dy + 23)

                # 4x 10G SFP+ Ports on right
                for p_idx in range(4):
                    px = ix1 + iw - 65 + p_idx * 14
                    py = dy + 16
                    pygame.draw.rect(surface, (185, 195, 210), (px, py, 11, 14), border_radius=2)
                    pygame.draw.rect(surface, (70, 80, 95), (px + 2, py + 3, 7, 8))
                    # Optic LED
                    sfp_led = (25, 235, 90) if (math.sin(now * 15.0 + p_idx * 3.1) > -0.2) else (15, 90, 30)
                    pygame.draw.rect(surface, sfp_led, (px + 3, py - 3, 5, 2))
                    p_coords[f"r1_router_sfp_{p_idx}"] = (px + 5, py + 7)

            elif stype == "patch_a":
                # 24-Port Cat6 Patch Panel
                pygame.draw.rect(surface, (22, 26, 34), dev_rect)
                pygame.draw.rect(surface, (45, 52, 65), dev_rect, width=1)
                p_lbl = self.font_rack_nano.render("CAT6 PATCH 1A // 1-24", True, (160, 180, 205))
                surface.blit(p_lbl, (ix1 + 8, dy + 2))
                # 24 RJ45 Ports in 4 groups of 6
                port_idx = 0
                for grp in range(4):
                    gx = ix1 + 10 + grp * (iw - 20) // 4
                    for pi in range(6):
                        px = gx + pi * ((iw - 20) // 25)
                        py = dy + 14
                        pygame.draw.rect(surface, (14, 18, 24), (px, py, 8, 10), border_radius=1)
                        pygame.draw.rect(surface, (160, 140, 40), (px + 2, py + 2, 4, 3))
                        p_coords[f"r1_patch_{port_idx}"] = (px + 4, py + 5)
                        port_idx += 1

            elif stype in ("switch_core1", "switch_core2"):
                # Cisco Catalyst 9300-48P Switches
                pygame.draw.rect(surface, (30, 38, 52), dev_rect)
                pygame.draw.rect(surface, (0, 115, 220), (ix1, dy, 4, sh))
                pygame.draw.rect(surface, (50, 65, 88), dev_rect, width=1)

                sw_name = "CATALYST 9300-48P #1" if stype == "switch_core1" else "CATALYST 9300-48P #2 (STACK)"
                lbl = self.font_rack_nano.render(sw_name, True, (220, 235, 255))
                surface.blit(lbl, (ix1 + 8, dy + 2))

                # Mode LED
                pygame.draw.circle(surface, (0, 210, 255), (ix1 + iw - 68, dy + 6), 2)

                # Two rows of 24 RJ45 Ports + Blinking Activity LEDs
                sw_id = 1 if stype == "switch_core1" else 2
                for c in range(20):
                    px = ix1 + 8 + c * ((iw - 85) // 20)
                    for r in (0, 1):
                        py = dy + 12 + r * 10
                        pygame.draw.rect(surface, (15, 20, 28), (px, py, 7, 8), border_radius=1)
                        # Traffic activity animation
                        traffic = math.sin(now * (14.0 + (c % 5) * 2.7) + (c + r * 10 + sw_id * 7)) * \
                                  math.cos(now * (19.0 + (c % 3) * 3.3) + c * 1.9)
                        is_lit = traffic > 0.12
                        led_c = (25, 240, 85) if is_lit else (10, 80, 30)
                        pygame.draw.rect(surface, led_c, (px + 1, py - 2 if r == 0 else py + 8, 4, 1))

                        p_key = f"r1_sw{sw_id}_p_{c}_{r}"
                        p_coords[p_key] = (px + 3, py + 4)

                # 4x SFP+ Uplink cages on right
                for u_idx in range(4):
                    ux = ix1 + iw - 54 + u_idx * 13
                    uy = dy + 12
                    pygame.draw.rect(surface, (180, 190, 205), (ux, uy, 10, 18), border_radius=2)
                    pygame.draw.rect(surface, (60, 70, 85), (ux + 2, uy + 4, 6, 10))
                    # Optic LED
                    sfp_active = math.sin(now * 18.0 + u_idx * 4.1 + sw_id) > -0.1
                    sfp_col = (0, 235, 240) if sfp_active else (0, 80, 90)
                    pygame.draw.circle(surface, sfp_col, (ux + 5, uy - 2), 2)
                    p_coords[f"r1_sw{sw_id}_sfp_{u_idx}"] = (ux + 5, uy + 9)

            elif stype == "wire_mgr":
                # 1U D-Ring Horizontal Wire Manager
                pygame.draw.rect(surface, (20, 24, 32), dev_rect)
                for rx_i in range(5):
                    dx_ring = ix1 + 25 + rx_i * ((iw - 50) // 4)
                    pygame.draw.circle(surface, (160, 175, 195), (dx_ring, dy + sh // 2), 7, 2)
                    # Bundled cables running through rings
                    pygame.draw.line(surface, (0, 110, 220), (dx_ring - 12, dy + sh // 2 - 1), (dx_ring + 12, dy + sh // 2 - 1), 2)
                    pygame.draw.line(surface, (20, 195, 100), (dx_ring - 12, dy + sh // 2 + 2), (dx_ring + 12, dy + sh // 2 + 2), 2)

            elif stype == "firewall":
                # Fortinet FortiGate 100F (White & Red styling)
                pygame.draw.rect(surface, (244, 247, 252), dev_rect)
                pygame.draw.rect(surface, (215, 35, 45), (ix1, dy, 5, sh))
                pygame.draw.rect(surface, (210, 220, 235), dev_rect, width=1)
                fw_lbl = self.font_rack_micro.render("FORTIGATE 100F", True, (180, 25, 35))
                surface.blit(fw_lbl, (ix1 + 10, dy + 3))

                # HA Status LED (pulsing active)
                ha_col = (20, 230, 80) if (math.sin(now * 3.0) > -0.7) else (10, 120, 40)
                pygame.draw.circle(surface, ha_col, (ix1 + 110, dy + 9), 3)
                ha_txt = self.font_rack_nano.render("HA: MASTER", True, (0, 0, 0))
                surface.blit(ha_txt, (ix1 + 118, dy + 5))

                # 12x GE Ports
                for f_p in range(12):
                    fx = ix1 + 10 + f_p * ((iw - 75) // 12)
                    fy = dy + 16
                    pygame.draw.rect(surface, (28, 34, 45), (fx, fy, 8, 11), border_radius=1)
                    p_coords[f"r1_fw_p_{f_p}"] = (fx + 4, fy + 5)

                # HA-1 & HA-2 sync ports on right
                p_coords["r1_fw_ha1"] = (ix1 + iw - 38, dy + 18)
                p_coords["r1_fw_ha2"] = (ix1 + iw - 20, dy + 18)
                pygame.draw.rect(surface, (200, 30, 40), (ix1 + iw - 42, dy + 14, 10, 13), border_radius=1)
                pygame.draw.rect(surface, (200, 30, 40), (ix1 + iw - 24, dy + 14, 10, 13), border_radius=1)

            elif stype == "fiber_liu":
                # Optical Fiber LIU/ODF Tray
                pygame.draw.rect(surface, (25, 30, 40), dev_rect)
                p_lbl = self.font_rack_nano.render("FIBER ODF TRAY // LC DUPLEX OM4", True, (0, 205, 230))
                surface.blit(p_lbl, (ix1 + 8, dy + 2))
                for fib_idx in range(10):
                    fx = ix1 + 14 + fib_idx * ((iw - 28) // 10)
                    fy = dy + 14
                    col = (0, 210, 230) if fib_idx < 6 else (0, 115, 230)
                    pygame.draw.rect(surface, col, (fx, fy, 11, 9), border_radius=2)
                    pygame.draw.circle(surface, (255, 255, 255), (fx + 3, fy + 4), 1)
                    pygame.draw.circle(surface, (255, 255, 255), (fx + 8, fy + 4), 1)
                    p_coords[f"r1_fiber_{fib_idx}"] = (fx + 5, fy + 4)

            elif stype in ("server_san", "server_host"):
                # Dell PowerEdge R750 Enterprise 2U Servers
                pygame.draw.rect(surface, (34, 38, 46), dev_rect)
                pygame.draw.rect(surface, (65, 75, 90), dev_rect, width=1)
                # Hexagonal silver ventilation pattern on top strip
                pygame.draw.rect(surface, (24, 28, 35), (ix1 + 4, dy + 4, iw - 8, 12))
                srv_name = "DELL POWEREDGE R750 (SAN NODE)" if stype == "server_san" else "DELL POWEREDGE R750 (VM HOST)"
                lbl = self.font_rack_nano.render(srv_name, True, (215, 225, 240))
                surface.blit(lbl, (ix1 + 8, dy + 5))

                # Power button with blue halo LED
                pygame.draw.circle(surface, (0, 180, 255), (ix1 + iw - 16, dy + 10), 3)

                # 8x Hot-Swap SAS/NVMe 2.5" Drive Caddies with Blinking Activity LEDs
                d_w = (iw - 18) // 8
                srv_id = 1 if stype == "server_san" else 2
                for d_i in range(8):
                    dx = ix1 + 6 + d_i * d_w
                    dy_c = dy + 20
                    pygame.draw.rect(surface, (20, 24, 32), (dx, dy_c, d_w - 3, 30), border_radius=2)
                    pygame.draw.rect(surface, (48, 56, 68), (dx, dy_c, d_w - 3, 30), width=1, border_radius=2)
                    # Blue release lever tab
                    pygame.draw.rect(surface, (0, 120, 220), (dx + 2, dy_c + 22, d_w - 7, 5), border_radius=1)

                    # Disk I/O activity flicker animation
                    d_act = (math.sin(now * 22.0 + d_i * 4.3 + srv_id * 3.1) + \
                             math.sin(now * 37.0 + d_i * 1.7)) > 0.35
                    d_col = (255, 190, 30) if d_act else (55, 45, 12)
                    pygame.draw.circle(surface, (25, 220, 80), (dx + 4, dy_c + 4), 2)      # Power
                    pygame.draw.circle(surface, d_col, (dx + d_w - 7, dy_c + 4), 2)        # Activity

                p_coords[f"r1_srv{srv_id}_nic1"] = (ix1 + iw - 45, dy + sh - 8)
                p_coords[f"r1_srv{srv_id}_nic2"] = (ix1 + iw - 25, dy + sh - 8)

            elif stype == "sensor":
                # Environmental Hub NetBotz
                pygame.draw.rect(surface, (24, 28, 36), dev_rect)
                pygame.draw.rect(surface, (45, 55, 70), dev_rect, width=1)
                lbl = self.font_rack_nano.render("NETBOTZ 250 // SENSORS", True, (150, 175, 205))
                surface.blit(lbl, (ix1 + 8, dy + 3))
                # Digital Green Sensor Readout
                sens_text = f"TEMP: {temp_c:.1f}C  HUMIDITY: 42%  DEW: 9.4C"
                s_surf = self.font_rack_nano.render(sens_text, True, (30, 240, 110))
                surface.blit(s_surf, (ix1 + 8, dy + 15))

            elif stype == "ups":
                # APC Smart-UPS RT 3000VA
                pygame.draw.rect(surface, (20, 24, 32), dev_rect)
                pygame.draw.rect(surface, (50, 60, 75), dev_rect, width=1)
                lbl = self.font_rack_micro.render("APC SMART-UPS 3000VA", True, (215, 228, 245))
                surface.blit(lbl, (ix1 + 10, dy + 6))

                # Blue Backlit LCD Screen
                lcd_rect = pygame.Rect(ix1 + 10, dy + 22, 130, 26)
                pygame.draw.rect(surface, (10, 55, 120), lcd_rect, border_radius=2)
                pygame.draw.rect(surface, (0, 140, 255), lcd_rect, width=1, border_radius=2)
                lcd_text = "230.4 V  ~  50Hz"
                lcd_load = "LOAD: 48%  BATT: 100%"
                surface.blit(self.font_rack_nano.render(lcd_text, True, (180, 225, 255)), (lcd_rect.x + 6, lcd_rect.y + 3))
                surface.blit(self.font_rack_nano.render(lcd_load, True, (180, 225, 255)), (lcd_rect.x + 6, lcd_rect.y + 14))

                # 5-Bar Green Battery Gauge
                for b_i in range(5):
                    bx = ix1 + 155 + b_i * 9
                    pygame.draw.rect(surface, (25, 235, 90), (bx, dy + 26, 6, 16), border_radius=1)

                # Master power switch
                pygame.draw.rect(surface, (215, 40, 45), (ix1 + iw - 28, dy + 24, 18, 20), border_radius=2)

        # ------------------ RACK 2 DEVICES ------------------
        for sid, sy, sh, stype in slots:
            dy = bay_top + sy
            dev_rect = pygame.Rect(ix2, dy, iw, sh)

            if stype == "brush":
                pygame.draw.rect(surface, (26, 30, 38), dev_rect)
                pygame.draw.rect(surface, (12, 15, 20), (ix2 + 10, dy + 5, iw - 20, sh - 10))
                for bx in range(ix2 + 14, ix2 + iw - 14, 4):
                    pygame.draw.line(surface, (40, 48, 60), (bx, dy + 6), (bx, dy + sh - 6), 1)

            elif stype == "router":
                # In Rack 2: Cisco Catalyst 3850-24T Distribution Switch
                pygame.draw.rect(surface, (32, 40, 54), dev_rect)
                pygame.draw.rect(surface, (55, 70, 95), dev_rect, width=1)
                lbl = self.font_rack_micro.render("CATALYST 3850-24T (DIST)", True, (230, 242, 255))
                surface.blit(lbl, (ix2 + 8, dy + 6))

                # 24 Gigabit Ports + Traffic Blinking LEDs
                for c in range(12):
                    px = ix2 + 10 + c * ((iw - 75) // 12)
                    for r in (0, 1):
                        py = dy + 20 + r * 11
                        pygame.draw.rect(surface, (15, 20, 28), (px, py, 9, 9), border_radius=1)
                        is_lit = (math.sin(now * 16.0 + c * 3.7 + r * 2.1) * math.cos(now * 21.0 + c * 1.5)) > 0.1
                        led_col = (25, 240, 85) if is_lit else (10, 75, 25)
                        pygame.draw.rect(surface, led_col, (px + 2, py - 2 if r == 0 else py + 9, 5, 2))
                        p_coords[f"r2_dist_p_{c}_{r}"] = (px + 4, py + 4)

                # SFP+ Uplinks on right
                for u_i in range(2):
                    ux = ix2 + iw - 40 + u_i * 16
                    uy = dy + 20
                    pygame.draw.rect(surface, (185, 195, 210), (ux, uy, 12, 18), border_radius=2)
                    pygame.draw.rect(surface, (60, 70, 85), (ux + 2, uy + 4, 8, 10))
                    p_coords[f"r2_dist_sfp_{u_i}"] = (ux + 6, uy + 9)

            elif stype == "patch_a":
                # Catalyst 2960-X Access Switch (Office LAN)
                pygame.draw.rect(surface, (28, 36, 48), dev_rect)
                pygame.draw.rect(surface, (25, 165, 85), (ix2, dy, 4, sh))
                lbl = self.font_rack_nano.render("CATALYST 2960-X (ACCESS LAN)", True, (215, 235, 255))
                surface.blit(lbl, (ix2 + 8, dy + 2))
                for c in range(16):
                    px = ix2 + 8 + c * ((iw - 20) // 16)
                    py = dy + 14
                    pygame.draw.rect(surface, (15, 20, 28), (px, py, 7, 10), border_radius=1)
                    # Green PoE LED
                    pygame.draw.rect(surface, (25, 235, 80), (px + 1, py - 2, 4, 1))
                    p_coords[f"r2_acc_p_{c}"] = (px + 3, py + 5)

            elif stype == "switch_core1":
                # 24-Port Cat6 Patch Panel 2B (Field User Drops)
                pygame.draw.rect(surface, (22, 26, 34), dev_rect)
                p_lbl = self.font_rack_nano.render("PATCH PANEL 2B // USER DROPS 1-24", True, (160, 180, 205))
                surface.blit(p_lbl, (ix2 + 8, dy + 2))
                port_idx = 0
                for grp in range(4):
                    gx = ix2 + 10 + grp * (iw - 20) // 4
                    for pi in range(6):
                        px = gx + pi * ((iw - 20) // 25)
                        py = dy + 16
                        pygame.draw.rect(surface, (14, 18, 24), (px, py, 8, 11), border_radius=1)
                        pygame.draw.rect(surface, (160, 140, 40), (px + 2, py + 2, 4, 3))
                        p_coords[f"r2_patch_{port_idx}"] = (px + 4, py + 5)
                        port_idx += 1

            elif stype == "switch_core2":
                # Slotted Wire Manager
                pygame.draw.rect(surface, (20, 24, 32), dev_rect)
                for rx_i in range(5):
                    dx_ring = ix2 + 25 + rx_i * ((iw - 50) // 4)
                    pygame.draw.circle(surface, (160, 175, 195), (dx_ring, dy + sh // 2), 7, 2)
                    pygame.draw.line(surface, (0, 120, 240), (dx_ring - 12, dy + sh // 2 - 1), (dx_ring + 12, dy + sh // 2 - 1), 2)
                    pygame.draw.line(surface, (245, 120, 25), (dx_ring - 12, dy + sh // 2 + 2), (dx_ring + 12, dy + sh // 2 + 2), 2)

            elif stype == "wire_mgr":
                # In Rack 2: Palo Alto PA-850 Next-Gen Firewall
                pygame.draw.rect(surface, (32, 36, 44), dev_rect)
                pygame.draw.rect(surface, (245, 115, 25), (ix2, dy, 4, sh))
                fw_lbl = self.font_rack_micro.render("PALO ALTO PA-850", True, (245, 130, 35))
                surface.blit(fw_lbl, (ix2 + 8, dy + 5))
                # HA-1 & HA-2 sync ports on left
                p_coords["r2_fw_ha1"] = (ix2 + 110, dy + 12)
                p_coords["r2_fw_ha2"] = (ix2 + 125, dy + 12)
                pygame.draw.rect(surface, (240, 110, 25), (ix2 + 106, dy + 8, 8, 9), border_radius=1)
                pygame.draw.rect(surface, (240, 110, 25), (ix2 + 121, dy + 8, 8, 9), border_radius=1)

            elif stype == "firewall":
                # Network Traffic Flow Analyzer & Tap (Animated VU Meter Bar Graph!)
                pygame.draw.rect(surface, (26, 32, 42), dev_rect)
                lbl = self.font_rack_nano.render("FLOW ANALYZER // PACKET METER", True, (0, 215, 255))
                surface.blit(lbl, (ix2 + 8, dy + 3))

                # Real-Time Animated 12-Segment Throughput VU Meter
                bar_count = int(7 + 3.5 * math.sin(now * 3.2) + 1.5 * math.cos(now * 6.8))
                bar_count = max(2, min(12, bar_count))
                for seg_i in range(12):
                    sx = ix2 + 10 + seg_i * 9
                    sy_b = dy + 16
                    if seg_i < 7:
                        base_col = (30, 240, 90)
                    elif seg_i < 10:
                        base_col = (255, 205, 30)
                    else:
                        base_col = (255, 45, 45)

                    c_val = base_col if (seg_i < bar_count) else (max(10, base_col[0]//5), max(10, base_col[1]//5), max(10, base_col[2]//5))
                    pygame.draw.rect(surface, c_val, (sx, sy_b, 6, 12), border_radius=1)

                # Tap monitoring ports on right
                p_coords["r2_tap_1"] = (ix2 + iw - 35, dy + 22)
                p_coords["r2_tap_2"] = (ix2 + iw - 18, dy + 22)
                pygame.draw.rect(surface, (230, 180, 20), (ix2 + iw - 39, dy + 17, 8, 10), border_radius=1)
                pygame.draw.rect(surface, (230, 180, 20), (ix2 + iw - 22, dy + 17, 8, 10), border_radius=1)

            elif stype == "fiber_liu":
                # 1U KVM Console Drawer
                pygame.draw.rect(surface, (24, 28, 36), dev_rect)
                pygame.draw.rect(surface, (55, 65, 80), dev_rect, width=1)
                # Chrome pull handle
                pygame.draw.rect(surface, (180, 195, 215), (ix2 + (iw - 60)//2, dy + 8, 60, 6), border_radius=3)
                lbl = self.font_rack_nano.render("17-INCH RACK CONSOLE KVM", True, (140, 160, 185))
                surface.blit(lbl, (ix2 + 8, dy + 6))

            elif stype in ("server_san", "server_host"):
                # HPE ProLiant DL380 Gen10 Servers (Iconic silver lattice grille)
                pygame.draw.rect(surface, (36, 42, 50), dev_rect)
                pygame.draw.rect(surface, (70, 80, 95), dev_rect, width=1)
                # Silver lattice bezel
                pygame.draw.rect(surface, (170, 180, 195), (ix2 + 4, dy + 4, iw - 8, 12), border_radius=1)
                hpe_name = "HPE PROLIANT DL380 GEN10 #1" if stype == "server_san" else "HPE PROLIANT DL380 GEN10 #2"
                lbl = self.font_rack_nano.render(hpe_name, True, (0, 0, 0))
                surface.blit(lbl, (ix2 + 8, dy + 4))

                # UID Blue Beacon LED (Classic 1-second blink)
                uid_on = (int(now * 2.0) % 2 == 0)
                uid_col = (0, 190, 255) if uid_on else (0, 45, 80)
                pygame.draw.circle(surface, uid_col, (ix2 + iw - 16, dy + 10), 3)

                # 8x Hot-Swap Drive Bays with Activity Lights
                d_w = (iw - 18) // 8
                hpe_id = 1 if stype == "server_san" else 2
                for d_i in range(8):
                    dx = ix2 + 6 + d_i * d_w
                    dy_c = dy + 20
                    pygame.draw.rect(surface, (22, 26, 34), (dx, dy_c, d_w - 3, 30), border_radius=2)
                    pygame.draw.rect(surface, (55, 65, 78), (dx, dy_c, d_w - 3, 30), width=1, border_radius=2)
                    # SmartDrive circular activity ring LED
                    d_act = (math.sin(now * 24.0 + d_i * 3.9 + hpe_id * 5.2) + math.sin(now * 33.0 + d_i * 2.1)) > 0.4
                    d_col = (255, 195, 30) if d_act else (50, 40, 15)
                    pygame.draw.circle(surface, (25, 230, 80), (dx + 4, dy_c + 4), 2)
                    pygame.draw.circle(surface, d_col, (dx + d_w - 7, dy_c + 4), 2)

                p_coords[f"r2_srv{hpe_id}_nic1"] = (ix2 + 15, dy + sh - 8)
                p_coords[f"r2_srv{hpe_id}_nic2"] = (ix2 + 35, dy + sh - 8)

            elif stype == "sensor":
                # Environmental Hub NetBotz
                pygame.draw.rect(surface, (24, 28, 36), dev_rect)
                sens_text = f"RACK-02 // TEMP: {temp_c:.1f}C  HUMIDITY: 45%"
                s_surf = self.font_rack_nano.render(sens_text, True, (30, 240, 110))
                surface.blit(s_surf, (ix2 + 8, dy + 10))

            elif stype == "ups":
                # Eaton 9PX Smart Enterprise PDU / UPS
                pygame.draw.rect(surface, (20, 24, 32), dev_rect)
                pygame.draw.rect(surface, (50, 60, 75), dev_rect, width=1)
                lbl = self.font_rack_micro.render("EATON 9PX 3000VA UPS", True, (215, 228, 245))
                surface.blit(lbl, (ix2 + 10, dy + 6))
                # Status gauge
                for b_i in range(5):
                    bx = ix2 + 10 + b_i * 12
                    pygame.draw.rect(surface, (25, 235, 90), (bx, dy + 26, 8, 16), border_radius=1)
                lcd_txt = self.font_rack_nano.render("OUTPUT: 230V / ONLINE", True, (0, 215, 255))
                surface.blit(lcd_txt, (ix2 + 85, dy + 28))

        # -------------------------------------------------------------------------
        # 4. PATCH CABLES: INTRA-RACK & CROSS-RACK CABLING (โยงสายในตู้และข้ามตู้)
        # -------------------------------------------------------------------------
        c_blue = (0, 125, 245)
        c_mint = (20, 220, 115)
        c_yellow = (255, 205, 25)
        c_orange = (255, 115, 25)
        c_purple = (165, 65, 235)
        c_aqua = (0, 225, 245)
        c_red = (235, 45, 55)

        # ----------------- A. INTRA-RACK 1 CABLING -----------------
        # Patch Panel A -> Core Switch 1 (6 patch cords looping in neat arcs)
        for i, col in enumerate([c_blue, c_mint, c_yellow, c_blue, c_orange, c_purple]):
            p_src = p_coords.get(f"r1_patch_{i * 2 + 1}")
            p_dst = p_coords.get(f"r1_sw1_p_{i * 3 + 1}_0")
            if p_src and p_dst:
                c1 = (p_src[0], p_src[1] + 16)
                c2 = (p_dst[0], p_dst[1] - 16)
                self._draw_menu_bezier_cable(surface, p_src, c1, c2, p_dst, col, width=2)

        # Core Switch 1 -> Core Switch 2 (Stack links & local patching)
        for i, col in enumerate([c_blue, c_mint, c_orange, c_yellow]):
            p_src = p_coords.get(f"r1_sw1_p_{i * 4 + 2}_1")
            p_dst = p_coords.get(f"r1_sw2_p_{i * 4 + 2}_0")
            if p_src and p_dst:
                c1 = (p_src[0] - 8, p_src[1] + 12)
                c2 = (p_dst[0] - 8, p_dst[1] - 12)
                self._draw_menu_bezier_cable(surface, p_src, c1, c2, p_dst, col, width=2)

        # Core Router SFP+ -> Core Switch 1 SFP+ (Fiber cords looping neatly)
        r_sfp0 = p_coords.get("r1_router_sfp_0")
        sw_sfp0 = p_coords.get("r1_sw1_sfp_0")
        if r_sfp0 and sw_sfp0:
            c1 = (r1_x + rw - 12, r_sfp0[1] + 20)
            c2 = (r1_x + rw - 12, sw_sfp0[1] - 20)
            self._draw_menu_bezier_cable(surface, r_sfp0, c1, c2, sw_sfp0, c_aqua, width=2)

        r_sfp1 = p_coords.get("r1_router_sfp_1")
        sw_sfp1 = p_coords.get("r1_sw1_sfp_1")
        if r_sfp1 and sw_sfp1:
            c1 = (r1_x + rw - 8, r_sfp1[1] + 18)
            c2 = (r1_x + rw - 8, sw_sfp1[1] - 18)
            self._draw_menu_bezier_cable(surface, r_sfp1, c1, c2, sw_sfp1, c_yellow, width=2)

        # Fiber ODF -> Core Switch 2 SFP+
        fib0 = p_coords.get("r1_fiber_2")
        sw2_sfp0 = p_coords.get("r1_sw2_sfp_0")
        if fib0 and sw2_sfp0:
            c1 = (r1_x + rw - 10, fib0[1] - 30)
            c2 = (r1_x + rw - 10, sw2_sfp0[1] + 30)
            self._draw_menu_bezier_cable(surface, fib0, c1, c2, sw2_sfp0, c_aqua, width=2)

        # Storage Server 1 -> Core Switch 2 (10G DAC cables)
        srv1_nic = p_coords.get("r1_srv1_nic1")
        sw2_p = p_coords.get("r1_sw2_p_18_1")
        if srv1_nic and sw2_p:
            c1 = (srv1_nic[0] - 15, srv1_nic[1] - 35)
            c2 = (sw2_p[0] + 15, sw2_p[1] + 35)
            self._draw_menu_bezier_cable(surface, srv1_nic, c1, c2, sw2_p, c_purple, width=2)

        # ----------------- B. INTRA-RACK 2 CABLING -----------------
        # Distribution Switch -> Access Switch
        for i, col in enumerate([c_blue, c_mint, c_yellow, c_orange]):
            p_src = p_coords.get(f"r2_dist_p_{i * 2 + 1}_1")
            p_dst = p_coords.get(f"r2_acc_p_{i * 3 + 1}")
            if p_src and p_dst:
                c1 = (p_src[0], p_src[1] + 14)
                c2 = (p_dst[0], p_dst[1] - 14)
                self._draw_menu_bezier_cable(surface, p_src, c1, c2, p_dst, col, width=2)

        # Patch Panel 2B -> Access Switch
        for i, col in enumerate([c_blue, c_mint, c_yellow, c_purple, c_orange]):
            p_src = p_coords.get(f"r2_patch_{i * 3 + 2}")
            p_dst = p_coords.get(f"r2_acc_p_{i * 2 + 3}")
            if p_src and p_dst:
                c1 = (p_src[0] - 4, p_src[1] - 16)
                c2 = (p_dst[0] - 4, p_dst[1] + 16)
                self._draw_menu_bezier_cable(surface, p_src, c1, c2, p_dst, col, width=2)

        # Access Switch -> HPE Server 1
        hpe1_nic = p_coords.get("r2_srv1_nic1")
        acc_p0 = p_coords.get("r2_acc_p_0")
        if hpe1_nic and acc_p0:
            c1 = (ix2 + 6, acc_p0[1] + 50)
            c2 = (ix2 + 6, hpe1_nic[1] - 50)
            self._draw_menu_bezier_cable(surface, acc_p0, c1, c2, hpe1_nic, c_blue, width=2)

        # Access Switch -> HPE Server 2
        hpe2_nic = p_coords.get("r2_srv2_nic1")
        acc_p1 = p_coords.get("r2_acc_p_2")
        if hpe2_nic and acc_p1:
            c1 = (ix2 + 10, acc_p1[1] + 65)
            c2 = (ix2 + 10, hpe2_nic[1] - 65)
            self._draw_menu_bezier_cable(surface, acc_p1, c1, c2, hpe2_nic, c_mint, width=2)

        # Packet Analyzer Tap -> Distribution Switch
        tap1 = p_coords.get("r2_tap_1")
        dist_sfp1 = p_coords.get("r2_dist_sfp_1")
        if tap1 and dist_sfp1:
            c1 = (r2_x + rw - 12, tap1[1] - 40)
            c2 = (r2_x + rw - 12, dist_sfp1[1] + 40)
            self._draw_menu_bezier_cable(surface, tap1, c1, c2, dist_sfp1, c_yellow, width=2)

        # ----------------- C. CROSS-RACK CABLING (โยงข้ามระหว่าง 2 ตู้!) -----------------
        # 1. Direct Cross-Connects Across Middle Gap (Trunk Links)
        # Trunk 1: Core Switch 1 (Rack 1) -> Dist Switch (Rack 2) [Cisco Blue]
        sw1_sfp3 = p_coords.get("r1_sw1_sfp_3")
        dist_sfp0 = p_coords.get("r2_dist_sfp_0")
        if sw1_sfp3 and dist_sfp0:
            mid_x = (sw1_sfp3[0] + dist_sfp0[0]) // 2
            c1 = (mid_x - 10, sw1_sfp3[1] + 28)
            c2 = (mid_x + 10, dist_sfp0[1] + 28)
            self._draw_menu_bezier_cable(surface, sw1_sfp3, c1, c2, dist_sfp0, c_blue, width=3)

        # Trunk 2: Core Switch 2 (Rack 1) -> Access Switch (Rack 2) [Mint Green]
        sw2_sfp2 = p_coords.get("r1_sw2_sfp_2")
        acc_p15 = p_coords.get("r2_acc_p_15")
        if sw2_sfp2 and acc_p15:
            mid_x = (sw2_sfp2[0] + acc_p15[0]) // 2
            c1 = (mid_x - 12, sw2_sfp2[1] + 34)
            c2 = (mid_x + 12, acc_p15[1] + 34)
            self._draw_menu_bezier_cable(surface, sw2_sfp2, c1, c2, acc_p15, c_mint, width=2)

        # Trunk 3: Core Switch 2 (Rack 1) -> Dist Switch (Rack 2) [Bright Orange]
        sw2_sfp3 = p_coords.get("r1_sw2_sfp_3")
        dist_p11 = p_coords.get("r2_dist_p_11_0")
        if sw2_sfp3 and dist_p11:
            mid_x = (sw2_sfp3[0] + dist_p11[0]) // 2
            c1 = (mid_x - 8, sw2_sfp3[1] + 44)
            c2 = (mid_x + 8, dist_p11[1] + 44)
            self._draw_menu_bezier_cable(surface, sw2_sfp3, c1, c2, dist_p11, c_orange, width=2)

        # Trunk 4: Storage SAN (Rack 1) -> HPE Compute Cluster (Rack 2) [Purple 10G SAN Fabric]
        srv1_nic2 = p_coords.get("r1_srv1_nic2")
        hpe1_nic2 = p_coords.get("r2_srv1_nic2")
        if srv1_nic2 and hpe1_nic2:
            mid_x = (srv1_nic2[0] + hpe1_nic2[0]) // 2
            c1 = (mid_x - 10, srv1_nic2[1] + 32)
            c2 = (mid_x + 10, hpe1_nic2[1] + 32)
            self._draw_menu_bezier_cable(surface, srv1_nic2, c1, c2, hpe1_nic2, c_purple, width=2)

        # 2. Firewall High-Availability (HA) Cross-Sync Cable [Crimson Red]
        fw1_ha1 = p_coords.get("r1_fw_ha1")
        fw2_ha1 = p_coords.get("r2_fw_ha1")
        if fw1_ha1 and fw2_ha1:
            mid_x = (fw1_ha1[0] + fw2_ha1[0]) // 2
            c1 = (mid_x - 10, fw1_ha1[1] + 30)
            c2 = (mid_x + 10, fw2_ha1[1] + 30)
            self._draw_menu_bezier_cable(surface, fw1_ha1, c1, c2, fw2_ha1, c_red, width=2)

        # 3. Overhead Ladder Waterfall Fiber Optic Cables (Entering through Top Brush Panels on right side)
        # Yellow Single-Mode Fiber: Router SFP+ -> Top Brush R1 -> Overhead Tray -> Top Brush R2 -> Dist SFP+
        r_sfp3 = p_coords.get("r1_router_sfp_3")
        dist_sfp1_pt = p_coords.get("r2_dist_sfp_1")
        if r_sfp3 and dist_sfp1_pt:
            r1_brush_pt = (ix1 + iw - 25, bay_top + 10)
            r2_brush_pt = (ix2 + iw - 25, bay_top + 10)
            tray_drop1 = (ix1 + iw - 25, tray_y + 12)
            tray_drop2 = (ix2 + iw - 25, tray_y + 12)

            # R1 Router SFP+ -> R1 Brush
            self._draw_menu_bezier_cable(surface, r_sfp3, (r_sfp3[0] + 8, r_sfp3[1] - 12), (r1_brush_pt[0] + 4, r1_brush_pt[1] + 12), r1_brush_pt, c_yellow, width=2)
            # R1 Brush -> Tray Drop 1
            pygame.draw.line(surface, c_yellow, r1_brush_pt, tray_drop1, 2)
            # Horizontal across Tray
            pygame.draw.line(surface, c_yellow, tray_drop1, tray_drop2, 2)
            # Tray Drop 2 -> R2 Brush
            pygame.draw.line(surface, c_yellow, tray_drop2, r2_brush_pt, 2)
            # R2 Brush -> Dist SFP+
            self._draw_menu_bezier_cable(surface, r2_brush_pt, (r2_brush_pt[0] - 6, r2_brush_pt[1] + 12), (dist_sfp1_pt[0] + 6, dist_sfp1_pt[1] - 12), dist_sfp1_pt, c_yellow, width=2)

        # Aqua Multi-Mode Fiber: Core Switch 1 SFP+ -> Top Tray -> Access Switch SFP+
        sw1_sfp2 = p_coords.get("r1_sw1_sfp_2")
        acc_p14 = p_coords.get("r2_acc_p_14")
        if sw1_sfp2 and acc_p14:
            r1_brush_pt2 = (ix1 + iw - 45, bay_top + 10)
            r2_brush_pt2 = (ix2 + 25, bay_top + 10)
            tray_drop1_a = (ix1 + iw - 45, tray_y + 14)
            tray_drop2_a = (ix2 + 25, tray_y + 14)

            self._draw_menu_bezier_cable(surface, sw1_sfp2, (sw1_sfp2[0] + 12, sw1_sfp2[1] - 35), (r1_brush_pt2[0] + 8, r1_brush_pt2[1] + 20), r1_brush_pt2, c_aqua, width=2)
            pygame.draw.line(surface, c_aqua, r1_brush_pt2, tray_drop1_a, 2)
            pygame.draw.line(surface, c_aqua, tray_drop1_a, tray_drop2_a, 2)
            pygame.draw.line(surface, c_aqua, tray_drop2_a, r2_brush_pt2, 2)
            self._draw_menu_bezier_cable(surface, r2_brush_pt2, (r2_brush_pt2[0] - 8, r2_brush_pt2[1] + 20), (acc_p14[0] - 8, acc_p14[1] - 25), acc_p14, c_aqua, width=2)

    def _render_pause_menu(self, surface, w, h):
        # Semi-transparent light frosted overlay
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((244, 247, 252, 220))
        surface.blit(overlay, (0, 0))

        cx, cy = w // 2, h // 2
        card_w, card_h = 420, 280
        rx, ry = cx - card_w // 2, cy - card_h // 2
        card_rect = pygame.Rect(rx, ry, card_w, card_h)

        # Dialog Box
        pygame.draw.rect(surface, (210, 222, 238), (rx + 3, ry + 4, card_w, card_h), border_radius=10)
        pygame.draw.rect(surface, (255, 255, 255), card_rect, border_radius=10)
        pygame.draw.rect(surface, (0, 115, 230), card_rect, width=2, border_radius=10)

        # Title
        p_surf = self.font_title.render("SIMULATOR PAUSED", True, (15, 45, 90))
        surface.blit(p_surf, (cx - p_surf.get_width() // 2, ry + 25))

        # Buttons
        options = [
            ("RESUME SIMULATION", "[ESC] / [P]"),
            ("RESTART SCENARIO", "[R]"),
            ("RETURN TO MAIN MENU", "[M]")
        ]
        for i, (title, hotkey) in enumerate(options):
            b_rect = self.get_pause_button_rect(i, w, h)
            pygame.draw.rect(surface, (242, 247, 255), b_rect, border_radius=6)
            pygame.draw.rect(surface, (0, 115, 230), b_rect, width=1, border_radius=6)

            t_s = self.font_btn.render(title, True, (0, 85, 200))
            h_s = self.font_mono.render(hotkey, True, (0, 0, 0))
            surface.blit(t_s, (b_rect.x + 16, b_rect.y + 10))
            surface.blit(h_s, (b_rect.right - h_s.get_width() - 16, b_rect.y + 12))

    def _render_topology_map(self, surface, w, h, devices, cables):
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((246, 249, 254, 248))
        surface.blit(overlay, (0, 0))

        # Blueprint grid
        grid_color = (230, 237, 248)
        for x in range(0, w, 32):
            pygame.draw.line(surface, grid_color, (x, 0), (x, h), 1)
        for y in range(0, h, 32):
            pygame.draw.line(surface, grid_color, (0, y), (w, y), 1)

        # Title
        cx = w // 2
        title = self.font_logo.render("2D LOGICAL NETWORK TOPOLOGY", True, (16, 42, 82))
        sub = self.font_sub.render("Real-Time Device Interconnects & Link Operational Status", True, (0, 102, 204))
        surface.blit(title, (cx - title.get_width() // 2, 25))
        surface.blit(sub, (cx - sub.get_width() // 2, 70))

        if not devices:
            return

        # Tiered Layout: Routers (Top), Switches (Middle), Hosts/Servers (Bottom)
        node_positions = {}
        cy = h // 2

        routers = [d for d in devices if isinstance(d, Router)]
        firewalls = [d for d in devices if isinstance(d, Firewall)]
        switches = [d for d in devices if isinstance(d, Switch)]
        hosts = [d for d in devices if isinstance(d, Host)]

        def place_row(dev_list, y_pos):
            count = len(dev_list)
            if count == 0:
                return
            span = min(w - 200, count * 220)
            start_x = cx - span // 2
            step = span // max(1, count - 1) if count > 1 else 0
            for idx, dev in enumerate(dev_list):
                px = cx if count == 1 else (start_x + idx * step)
                node_positions[dev.id] = (px, y_pos)

        place_row(routers + firewalls, 140)
        place_row(switches, cy)
        place_row(hosts, h - 140)

        # Draw Connecting Cable Links
        if cables:
            for cable in cables:
                if not cable.port_a or not cable.port_b:
                    continue
                dev_a = cable.port_a.device
                dev_b = cable.port_b.device
                pos_a = node_positions.get(dev_a.id)
                pos_b = node_positions.get(dev_b.id)
                if pos_a and pos_b:
                    link_color = (15, 165, 75) if (cable.port_a.is_link_up and cable.port_b.is_link_up) else (225, 140, 20)
                    if cable.is_damaged:
                        link_color = (220, 50, 50)
                    pygame.draw.line(surface, link_color, pos_a, pos_b, 3)

                    # Port label tags at midpoints
                    mid_x = (pos_a[0] + pos_b[0]) // 2
                    mid_y = (pos_a[1] + pos_b[1]) // 2
                    tag = f"{cable.port_a.name} <-> {cable.port_b.name}"
                    t_s = self.font_mono.render(tag, True, (0, 0, 0))
                    pygame.draw.rect(surface, (255, 255, 255), (mid_x - t_s.get_width()//2 - 4, mid_y - 10, t_s.get_width() + 8, 20), border_radius=4)
                    pygame.draw.rect(surface, (200, 215, 235), (mid_x - t_s.get_width()//2 - 4, mid_y - 10, t_s.get_width() + 8, 20), width=1, border_radius=4)
                    surface.blit(t_s, (mid_x - t_s.get_width()//2, mid_y - 8))

        # Draw Device Nodes
        for dev in devices:
            pos = node_positions.get(dev.id)
            if not pos:
                continue
            dx, dy = pos
            nw, nh = 148, 68
            rect = pygame.Rect(dx - nw//2, dy - nh//2, nw, nh)

            bg_color = (255, 255, 255)
            border_color = (0, 115, 230)
            if isinstance(dev, Router):
                border_color = (0, 102, 204)
            elif isinstance(dev, Firewall):
                border_color = (200, 30, 45)
            elif isinstance(dev, Switch):
                border_color = (16, 160, 80)
            elif isinstance(dev, Host):
                border_color = (220, 130, 20)

            # Card with shadow
            shadow_rect = pygame.Rect(rect.x + 2, rect.y + 2, rect.w, rect.h)
            pygame.draw.rect(surface, (210, 222, 238), shadow_rect, border_radius=8)
            pygame.draw.rect(surface, bg_color, rect, border_radius=8)
            pygame.draw.rect(surface, border_color, rect, width=2, border_radius=8)

            d_name = self.font_btn.render(dev.hostname, True, (0, 0, 0))
            d_type = self.font_body.render(dev.device_type.upper(), True, border_color)
            surface.blit(d_name, (dx - d_name.get_width()//2, dy - 22))
            surface.blit(d_type, (dx - d_type.get_width()//2, dy + 4))

        close_lbl = self.font_btn.render("Press [M] or [ESC] to return to Datacenter 3D view", True, (0, 0, 0))
        surface.blit(close_lbl, (cx - close_lbl.get_width() // 2, h - 40))

    def _render_help_guide(self, surface, w, h):
        now = pygame.time.get_ticks() / 1000.0

        # 1. Clean Light Datacenter Backdrop Overlay
        backdrop = pygame.Surface((w, h), pygame.SRCALPHA)
        backdrop.fill((246, 249, 254, 250))
        surface.blit(backdrop, (0, 0))

        # Subtle blueprint grid lines
        grid_color = (230, 238, 248)
        for x in range(0, w, 32):
            pygame.draw.line(surface, grid_color, (x, 0), (x, h), 1)
        for y in range(0, h, 32):
            pygame.draw.line(surface, grid_color, (0, y), (w, y), 1)

        # 2. Main Title & Subtitle Header
        cx = w // 2
        title = self.font_guide_title.render("CONTROLS & HARDWARE CLI CHEATSHEET", True, (15, 42, 82))
        surface.blit(title, (cx - title.get_width() // 2, 8))

        sub_txt = "INTERACTIVE 3D DATACENTER APPLIANCE SHOWCASE & CLI COMMAND REFERENCE"
        sub = self.font_guide_sub.render(sub_txt, True, (0, 102, 204))
        surface.blit(sub, (cx - sub.get_width() // 2, 38))

        # 3. Top Device Selector Tabs
        tabs_y = 60
        tab_h = 32
        total_tab_w = min(w - 48, 1200)
        tab_w = total_tab_w // len(self.showcase_devices)
        start_tab_x = (w - total_tab_w) // 2

        mouse_pos = pygame.mouse.get_pos()
        self._last_device_tab_rects = []

        for idx, dev_info in enumerate(self.showcase_devices):
            t_rect = pygame.Rect(start_tab_x + idx * tab_w, tabs_y, tab_w - 4, tab_h)
            self._last_device_tab_rects.append(t_rect)

            is_active = (idx == self.showcase_selected_idx)
            is_hover = t_rect.collidepoint(mouse_pos)

            if is_active:
                pygame.draw.rect(surface, (0, 102, 204), t_rect, border_radius=6)
                pygame.draw.rect(surface, (0, 75, 165), t_rect, width=1, border_radius=6)
                # Cyan top indicator line
                pygame.draw.line(surface, (0, 220, 255), (t_rect.x + 4, t_rect.y + 1), (t_rect.right - 4, t_rect.y + 1), 2)
                t_col = (255, 255, 255)
            elif is_hover:
                pygame.draw.rect(surface, (238, 246, 255), t_rect, border_radius=6)
                pygame.draw.rect(surface, (0, 120, 225), t_rect, width=1, border_radius=6)
                t_col = (0, 85, 190)
            else:
                pygame.draw.rect(surface, (255, 255, 255), t_rect, border_radius=6)
                pygame.draw.rect(surface, (212, 224, 238), t_rect, width=1, border_radius=6)
                t_col = (0, 0, 0)

            lbl = self.font_guide_tab.render(dev_info["label"], True, t_col)
            surface.blit(lbl, (t_rect.centerx - lbl.get_width() // 2, t_rect.centery - lbl.get_height() // 2))

        # 4. Main Body Layout (Left: 3D Viewport, Right: CLI Cheatsheet)
        content_y = 100
        content_h = max(320, h - content_y - 44)
        margin_x = max(20, (w - 1240) // 2) if w > 1240 else 20
        content_w = w - margin_x * 2

        left_w = int(content_w * 0.44)
        left_rect = pygame.Rect(margin_x, content_y, left_w, content_h)

        right_x = left_rect.right + 12
        right_w = content_w - left_w - 12
        right_rect = pygame.Rect(right_x, content_y, right_w, content_h)

        curr_dev_info = self.showcase_devices[self.showcase_selected_idx]
        dev_key = curr_dev_info["id"]

        # === LEFT PANE: 3D HARDWARE VIEWPORT ===
        # Soft Drop Shadow & Clean White Card
        pygame.draw.rect(surface, (212, 224, 238), (left_rect.x + 2, left_rect.y + 2, left_rect.w, left_rect.h), border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), left_rect, border_radius=8)
        pygame.draw.rect(surface, (205, 220, 238), left_rect, width=1, border_radius=8)

        # Header Badge inside Left Pane
        pulse = 0.80 + 0.20 * math.sin(now * 4.0)
        pygame.draw.circle(surface, (15, int(185 * pulse), 75), (left_rect.x + 18, left_rect.y + 16), 5)

        hdr_tag = self.font_guide_badge.render("LIVE 3D HARDWARE TURNTABLE", True, (0, 102, 204))
        surface.blit(hdr_tag, (left_rect.x + 30, left_rect.y + 10))

        # Device Model Title (Enlarged, rich navy)
        d_title = self.font_guide_dev_title.render(curr_dev_info["title"], True, (15, 40, 75))
        surface.blit(d_title, (left_rect.x + 14, left_rect.y + 26))

        # 3D Viewport Rect (Must match get_showcase_viewport)
        vp_x, vp_y, vp_w, vp_h = self.get_showcase_viewport(w, h)
        vp_rect = pygame.Rect(vp_x, vp_y, vp_w, vp_h)

        # Punch transparent hole so OpenGL 3D buffer shows through!
        surface.fill((0, 0, 0, 0), vp_rect)

        # Clean Studio Viewport Frame & Reticles
        pygame.draw.rect(surface, (200, 216, 236), vp_rect, width=1)

        # Sci-Fi Corner Brackets
        crn_len = 14
        crn_col = (0, 115, 230)
        # Top-Left
        pygame.draw.line(surface, crn_col, (vp_rect.left, vp_rect.top), (vp_rect.left + crn_len, vp_rect.top), 2)
        pygame.draw.line(surface, crn_col, (vp_rect.left, vp_rect.top), (vp_rect.left + crn_len, vp_rect.top), 2)
        # Top-Right
        pygame.draw.line(surface, crn_col, (vp_rect.right - 1, vp_rect.top), (vp_rect.right - 1 - crn_len, vp_rect.top), 2)
        pygame.draw.line(surface, crn_col, (vp_rect.right - 1, vp_rect.top), (vp_rect.right - 1, vp_rect.top + crn_len), 2)
        # Bottom-Left
        pygame.draw.line(surface, crn_col, (vp_rect.left, vp_rect.bottom - 1), (vp_rect.left + crn_len, vp_rect.bottom - 1), 2)
        pygame.draw.line(surface, crn_col, (vp_rect.left, vp_rect.bottom - 1), (vp_rect.left, vp_rect.bottom - 1 - crn_len), 2)
        # Bottom-Right
        pygame.draw.line(surface, crn_col, (vp_rect.right - 1, vp_rect.bottom - 1), (vp_rect.right - 1 - crn_len, vp_rect.bottom - 1), 2)
        pygame.draw.line(surface, crn_col, (vp_rect.right - 1, vp_rect.bottom - 1), (vp_rect.right - 1, vp_rect.bottom - 1 - crn_len), 2)

        # Rotation interaction hint banner at bottom of 3D viewport (NO zoom text per user request)
        rot_hint_rect = pygame.Rect(vp_x + 1, vp_y + vp_h - 24, vp_w - 2, 24)
        surface.fill((242, 246, 252, 255), rot_hint_rect)
        pygame.draw.line(surface, (205, 220, 238), (rot_hint_rect.left, rot_hint_rect.top), (rot_hint_rect.right, rot_hint_rect.top), 1)

        rot_text = "↔ Drag Left Mouse to Rotate 360° (Turntable Yaw & Pitch)"
        rot_lbl = self.font_guide_rot.render(rot_text, True, (0, 95, 195))
        surface.blit(rot_lbl, (rot_hint_rect.centerx - rot_lbl.get_width() // 2, rot_hint_rect.centery - rot_lbl.get_height() // 2))

        # Hardware Specifications Panel below Viewport
        specs_y = vp_y + vp_h + 8
        specs_h = max(80, left_rect.bottom - specs_y - 8)
        specs_rect = pygame.Rect(vp_x, specs_y, vp_w, specs_h)
        pygame.draw.rect(surface, (246, 250, 255), specs_rect, border_radius=6)
        pygame.draw.rect(surface, (215, 228, 242), specs_rect, width=1, border_radius=6)

        specs_items = [
            ("FORM FACTOR", curr_dev_info["form_factor"]),
            ("FIRMWARE / OS", curr_dev_info["os"]),
            ("INTERFACES", curr_dev_info["ports_desc"]),
            ("POWER SYSTEM", curr_dev_info["power_desc"]),
        ]
        sp_mid_x = specs_rect.x + specs_rect.w // 2
        for s_i, (k, val) in enumerate(specs_items):
            sy = specs_rect.y + 8 + (s_i % 2) * 40
            sx = specs_rect.x + 12 if s_i < 2 else sp_mid_x + 8
            k_lbl = self.font_guide_spec_k.render(k, True, (0, 102, 204))
            v_lbl = self.font_guide_spec_v.render(val, True, (0, 0, 0))
            surface.blit(k_lbl, (sx, sy))
            surface.blit(v_lbl, (sx, sy + 17))

        # === RIGHT PANE: CATEGORIZED CLI CHEATSHEET ===
        # Soft Drop Shadow & Clean White Card
        pygame.draw.rect(surface, (212, 224, 238), (right_rect.x + 2, right_rect.y + 2, right_rect.w, right_rect.h), border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), right_rect, border_radius=8)
        pygame.draw.rect(surface, (205, 220, 238), right_rect, width=1, border_radius=8)

        # Category Filter Pills Bar
        cat_data = SHOWCASE_COMMANDS.get(dev_key, SHOWCASE_COMMANDS["router"])
        categories = cat_data["categories"]

        pills_y = right_rect.y + 10
        pills_x = right_rect.x + 12
        row_h = 28
        self._last_category_rects = []

        for c_idx, c_name in enumerate(categories):
            is_active_cat = (c_idx == self.showcase_cat_idx)
            pill_lbl = self.font_guide_cat.render(c_name, True, (255, 255, 255) if is_active_cat else (0, 0, 0))
            pill_w = pill_lbl.get_width() + 18

            # Wrap to next row if overflowing right boundary
            if pills_x + pill_w > right_rect.right - 12 and pills_x > right_rect.x + 12:
                pills_x = right_rect.x + 12
                pills_y += row_h + 6

            pill_r = pygame.Rect(pills_x, pills_y, pill_w, row_h)
            self._last_category_rects.append(pill_r)
            is_hover_cat = pill_r.collidepoint(mouse_pos)

            if is_active_cat:
                pygame.draw.rect(surface, (0, 102, 204), pill_r, border_radius=14)
                pygame.draw.rect(surface, (0, 75, 165), pill_r, width=1, border_radius=14)
            elif is_hover_cat:
                pygame.draw.rect(surface, (232, 242, 255), pill_r, border_radius=14)
                pygame.draw.rect(surface, (0, 120, 225), pill_r, width=1, border_radius=14)
                pill_lbl = self.font_guide_cat.render(c_name, True, (0, 85, 185))
            else:
                pygame.draw.rect(surface, (242, 247, 253), pill_r, border_radius=14)
                pygame.draw.rect(surface, (205, 220, 238), pill_r, width=1, border_radius=14)

            surface.blit(pill_lbl, (pill_r.centerx - pill_lbl.get_width() // 2, pill_r.centery - pill_lbl.get_height() // 2))
            pills_x += pill_w + 6

        # Filter command items according to active category
        active_cat_name = categories[min(len(categories) - 1, self.showcase_cat_idx)]
        all_cmds = cat_data["commands"]
        if active_cat_name == "ALL":
            filtered_cmds = all_cmds
        else:
            filtered_cmds = [c for c in all_cmds if c.get("cat") == active_cat_name]

        # Scrollable Cards Viewport
        list_y = pills_y + row_h + 10
        list_h = max(180, right_rect.bottom - list_y - 12)
        list_w = right_rect.w - 24
        list_rect = pygame.Rect(right_rect.x + 12, list_y, list_w, list_h)

        card_h = 92
        card_gap = 8
        total_content_h = len(filtered_cmds) * (card_h + card_gap)
        self._max_scroll_y = max(0, total_content_h - list_h)
        self.showcase_scroll_y = max(0, min(self._max_scroll_y, self.showcase_scroll_y))

        has_scrollbar = self._max_scroll_y > 0
        actual_card_w = list_w - (14 if has_scrollbar else 0)

        # Clip rendering to list_rect
        surface.set_clip(list_rect)

        for c_idx, cmd_item in enumerate(filtered_cmds):
            card_y = list_rect.y + c_idx * (card_h + card_gap) - self.showcase_scroll_y
            if card_y + card_h < list_rect.y or card_y > list_rect.bottom:
                continue

            card_r = pygame.Rect(list_rect.x, card_y, actual_card_w, card_h)
            is_card_hover = card_r.collidepoint(mouse_pos)

            # Card Background (Clean White & Soft Hover)
            card_bg = (245, 250, 255) if is_card_hover else (255, 255, 255)
            card_border = (0, 120, 225) if is_card_hover else (216, 228, 242)
            pygame.draw.rect(surface, card_bg, card_r, border_radius=6)
            pygame.draw.rect(surface, card_border, card_r, width=1, border_radius=6)

            # Left accent highlight on hover
            if is_card_hover:
                pygame.draw.rect(surface, (0, 115, 230), (card_r.x, card_r.y, 4, card_r.h), border_top_left_radius=6, border_bottom_left_radius=6)

            # Row 1: Command Syntax & Category Tag (Enlarged)
            cmd_s = self.font_guide_cmd.render(cmd_item["cmd"], True, (10, 125, 60))
            surface.blit(cmd_s, (card_r.x + 12, card_r.y + 7))

            cat_s = self.font_guide_card_tag.render(cmd_item.get("cat", "GENERAL"), True, (0, 95, 195))
            cat_tag_w = cat_s.get_width() + 12
            cat_tag_r = pygame.Rect(card_r.right - cat_tag_w - 10, card_r.y + 7, cat_tag_w, 20)
            pygame.draw.rect(surface, (235, 243, 255), cat_tag_r, border_radius=4)
            pygame.draw.rect(surface, (195, 216, 242), cat_tag_r, width=1, border_radius=4)
            surface.blit(cat_s, (cat_tag_r.centerx - cat_s.get_width() // 2, cat_tag_r.centery - cat_s.get_height() // 2))

            # Row 2: English Description (Enlarged)
            desc_en = cmd_item.get("desc", "")
            desc_en_s = self.font_guide_desc.render(desc_en, True, (0, 0, 0))
            surface.blit(desc_en_s, (card_r.x + 12, card_r.y + 28))

            # Row 3: Thai Description (Enlarged, Native Thai font)
            desc_th = cmd_item.get("desc_th", "")
            if desc_th:
                desc_th_s = self.font_thai_guide.render(desc_th, True, (0, 0, 0))
                surface.blit(desc_th_s, (card_r.x + 12, card_r.y + 46))

            # Row 4: Practical Example Console Box
            ex_box_r = pygame.Rect(card_r.x + 10, card_r.y + 65, card_r.w - 20, 22)
            pygame.draw.rect(surface, (242, 246, 252), ex_box_r, border_radius=4)
            pygame.draw.rect(surface, (210, 224, 240), ex_box_r, width=1, border_radius=4)

            ex_lbl = self.font_guide_mono.render(cmd_item.get("example", ""), True, (0, 90, 180))
            surface.blit(ex_lbl, (ex_box_r.x + 8, ex_box_r.centery - ex_lbl.get_height() // 2))

        surface.set_clip(None)

        # Vertical Scrollbar on right edge of list
        if has_scrollbar:
            sb_track = pygame.Rect(list_rect.right - 8, list_rect.y, 6, list_h)
            pygame.draw.rect(surface, (235, 242, 250), sb_track, border_radius=3)

            thumb_ratio = max(0.12, min(1.0, float(list_h) / float(total_content_h)))
            thumb_h = int(list_h * thumb_ratio)
            thumb_y = list_rect.y + int((list_h - thumb_h) * (float(self.showcase_scroll_y) / float(self._max_scroll_y)))
            sb_thumb = pygame.Rect(list_rect.right - 8, thumb_y, 6, thumb_h)
            pygame.draw.rect(surface, (160, 185, 215), sb_thumb, border_radius=3)

        # 5. Footer Bottom Bar
        footer_y = h - 38

        # Return to Menu Button
        btn_w, btn_h = 190, 28
        btn_r = pygame.Rect(right_rect.right - btn_w, footer_y, btn_w, btn_h)
        self._last_back_btn_rect = btn_r
        is_back_hover = btn_r.collidepoint(mouse_pos)

        if is_back_hover:
            pygame.draw.rect(surface, (0, 102, 204), btn_r, border_radius=5)
            pygame.draw.rect(surface, (0, 75, 165), btn_r, width=1, border_radius=5)
            b_col = (255, 255, 255)
        else:
            pygame.draw.rect(surface, (244, 248, 255), btn_r, border_radius=5)
            pygame.draw.rect(surface, (0, 115, 230), btn_r, width=1, border_radius=5)
            b_col = (0, 85, 195)

        back_txt = self.font_guide_btn.render("[ESC] Return to Menu", True, b_col)
        surface.blit(back_txt, (btn_r.centerx - back_txt.get_width() // 2, btn_r.centery - back_txt.get_height() // 2))

        # Bottom Controls Hint
        hint_text = "Shortcuts: [1-6] Select Device • [Drag Mouse] Rotate 360° • [Wheel / Up / Down] Scroll Cheatsheet"
        hint_lbl = self.font_guide_hint.render(hint_text, True, (0, 0, 0))
        surface.blit(hint_lbl, (margin_x, footer_y + 6))

    def _render_device_manager(self, surface, w, h, mode):
        """Renders the comprehensive Rack Device Manager modal overlay for Sandbox Mode."""
        # Frosted Backdrop Overlay
        backdrop = pygame.Surface((w, h), pygame.SRCALPHA)
        backdrop.fill((20, 32, 50, 190))
        surface.blit(backdrop, (0, 0))

        rects = self._compute_dm_rects(w, h)
        win_r = rects["win_rect"]

        # Drop shadow & Main Card Window
        shadow_r = pygame.Rect(win_r.x + 3, win_r.y + 4, win_r.w, win_r.h)
        pygame.draw.rect(surface, (10, 18, 28, 90), shadow_r, border_radius=12)
        pygame.draw.rect(surface, (250, 252, 255), win_r, border_radius=12)
        pygame.draw.rect(surface, (0, 115, 230), win_r, width=2, border_radius=12)

        # Top Title Bar
        header_r = pygame.Rect(win_r.x, win_r.y, win_r.w, 48)
        pygame.draw.rect(surface, (235, 243, 253), header_r, border_top_left_radius=12, border_top_right_radius=12)
        pygame.draw.line(surface, (210, 225, 245), (win_r.x, win_r.y + 48), (win_r.right, win_r.y + 48), 1)

        t_title = self.font_title.render("RACK HARDWARE MANAGER - SANDBOX PLAYGROUND", True, (15, 45, 90))
        surface.blit(t_title, (win_r.x + 20, win_r.y + 12))

        # Close [X] Button
        cls_r = rects["close_rect"]
        pygame.draw.rect(surface, (245, 248, 252), cls_r, border_radius=6)
        pygame.draw.rect(surface, (190, 205, 225), cls_r, width=1, border_radius=6)
        x_lbl = self.font_btn.render("X", True, (0, 0, 0))
        surface.blit(x_lbl, (cls_r.x + (cls_r.w - x_lbl.get_width())//2, cls_r.y + 5))

        # =========================================================================
        # LEFT PANEL: INSTALLED HARDWARE INVENTORY
        # =========================================================================
        left_r = rects["left_rect"]
        pygame.draw.rect(surface, (255, 255, 255), left_r, border_radius=8)
        pygame.draw.rect(surface, (220, 230, 245), left_r, width=1, border_radius=8)

        # Section Header
        dev_count = len(mode.devices) if mode and hasattr(mode, "devices") else 0
        h_left = self.font_bold.render(f"INSTALLED EQUIPMENT ({dev_count} DEVICES)", True, (20, 45, 80))
        surface.blit(h_left, (left_r.x + 12, left_r.y + 8))

        # Filter Tabs
        tab_names = ["All Racks", "Rack 1 (A01)", "Rack 2 (A02)", "Rack 3 (A03)"]
        for idx, tab_r in enumerate(rects["tab_rects"]):
            is_active = (self.dm_rack_filter == idx)
            bg = (0, 115, 230) if is_active else (244, 248, 253)
            border = (0, 115, 230) if is_active else (210, 222, 238)
            tc = (255, 255, 255) if is_active else (0, 0, 0)

            pygame.draw.rect(surface, bg, tab_r, border_radius=5)
            pygame.draw.rect(surface, border, tab_r, width=1, border_radius=5)

            lbl = self.font_small.render(tab_names[idx], True, tc)
            surface.blit(lbl, (tab_r.x + (tab_r.w - lbl.get_width())//2, tab_r.y + 6))

        # Scrollable Device Cards
        list_r = rects["list_rect"]
        pygame.draw.rect(surface, (249, 251, 254), list_r, border_radius=6)

        # Gather and filter devices
        dev_list = []
        if mode and hasattr(mode, "devices"):
            dev_list = [
                d for d in mode.devices
                if self.dm_rack_filter == 0 or d.rack_id == self.dm_rack_filter
            ]
            dev_list.sort(key=lambda d: (
                int(d.rack_id) if getattr(d, 'rack_id', None) is not None else 0,
                -(int(d.u_slot) if getattr(d, 'u_slot', None) is not None else 0)
            ))

        # Set up clipping for scrolling list
        prev_clip = surface.get_clip()
        surface.set_clip(list_r)

        row_h = 58
        row_gap = 6
        for i, dev in enumerate(dev_list):
            ry = list_r.y + 4 + i * (row_h + row_gap) - self.dm_scroll_offset
            row_r = pygame.Rect(list_r.x + 4, ry, list_r.w - 8, row_h)

            # Skip drawing if fully out of view
            if ry + row_h < list_r.y or ry > list_r.bottom:
                continue

            pygame.draw.rect(surface, (255, 255, 255), row_r, border_radius=6)
            pygame.draw.rect(surface, (222, 232, 245), row_r, width=1, border_radius=6)

            # Badge Color by Type
            badge_bg = (235, 250, 252)
            badge_tc = (15, 125, 140)
            badge_text = "SWITCH"
            if dev.device_type == "router":
                badge_bg = (235, 242, 255)
                badge_tc = (20, 80, 180)
                badge_text = "ROUTER"
            elif dev.device_type == "firewall":
                badge_bg = (255, 236, 238)
                badge_tc = (195, 30, 45)
                badge_text = "FIREWALL"
            elif dev.device_type in ("isp_gateway", "isp") or (dev.device_type == "server" and "isp" in dev.hostname.lower()):
                badge_bg = (230, 248, 255)
                badge_tc = (0, 130, 180)
                badge_text = "ISP WAN"
            elif dev.device_type == "server":
                badge_bg = (242, 244, 248)
                badge_tc = (0, 0, 0)
                badge_text = "SERVER"

            badge_r = pygame.Rect(row_r.x + 10, row_r.y + 8, 62, 20)
            pygame.draw.rect(surface, badge_bg, badge_r, border_radius=4)
            b_s = self.font_small.render(badge_text, True, badge_tc)
            surface.blit(b_s, (badge_r.x + (badge_r.w - b_s.get_width())//2, badge_r.y + 2))

            # Hostname
            h_s = self.font_bold.render(dev.hostname, True, (0, 0, 0))
            surface.blit(h_s, (row_r.x + 80, row_r.y + 8))

            # Location & Port info
            span = 1 if dev.device_type in ("switch", "firewall", "isp_gateway", "isp") else 2
            r_id = getattr(dev, "rack_id", 0) or 0
            u_s = getattr(dev, "u_slot", 0) or 0
            if r_id > 0 and u_s > 0:
                loc_str = f"RACK-0{r_id} (Slot {u_s}U" + (f"-{u_s+1}U" if span > 1 else "U") + ")"
            else:
                loc_str = "NOC Workbench / Desk"
            active_links = sum(1 for p in dev.ports.values() if p.cable)
            port_str = f"Ports: {len(dev.ports)} ({active_links} cabled)"
            sub_s = self.font_small.render(f"{loc_str}  |  {port_str}", True, (0, 0, 0))
            surface.blit(sub_s, (row_r.x + 12, row_r.y + 32))

            # [Remove] Button
            rem_btn = pygame.Rect(row_r.right - 85, row_r.y + 14, 75, 28)
            pygame.draw.rect(surface, (255, 242, 242), rem_btn, border_radius=5)
            pygame.draw.rect(surface, (235, 75, 75), rem_btn, width=1, border_radius=5)
            rem_lbl = self.font_small.render("Remove", True, (200, 30, 30))
            surface.blit(rem_lbl, (rem_btn.x + (rem_btn.w - rem_lbl.get_width())//2, rem_btn.y + 6))

        if len(dev_list) == 0:
            no_dev = self.font_body.render("No equipment currently installed in this selection.", True, (0, 0, 0))
            surface.blit(no_dev, (list_r.x + 20, list_r.y + 30))

        surface.set_clip(prev_clip)

        # =========================================================================
        # RIGHT PANEL: PROVISION / INSTALL NEW HARDWARE
        # =========================================================================
        right_r = rects["right_rect"]
        pygame.draw.rect(surface, (255, 255, 255), right_r, border_radius=8)
        pygame.draw.rect(surface, (220, 230, 245), right_r, width=1, border_radius=8)

        # Form Header
        h_right = self.font_bold.render("INSTALL NEW EQUIPMENT", True, (20, 45, 80))
        surface.blit(h_right, (right_r.x + 14, right_r.y + 10))

        # 1. Device Type
        lbl_type = self.font_small.render("1. SELECT HARDWARE TYPE:", True, (0, 0, 0))
        surface.blit(lbl_type, (right_r.x + 14, right_r.y + 34))

        type_labels = {
            "switch": "Switch (1U)",
            "router": "Router (2U)",
            "firewall": "Firewall (1U)",
            "server": "Server (2U)"
        }
        for t_name, t_rect in rects["type_rects"].items():
            is_active = (self.dm_selected_type == t_name)
            bg = (235, 245, 255) if is_active else (250, 252, 255)
            border = (0, 115, 230) if is_active else (215, 225, 240)
            tc = (0, 95, 210) if is_active else (0, 0, 0)
            pygame.draw.rect(surface, bg, t_rect, border_radius=5)
            pygame.draw.rect(surface, border, t_rect, width=2 if is_active else 1, border_radius=5)
            lbl = self.font_small.render(type_labels[t_name], True, tc)
            surface.blit(lbl, (t_rect.x + (t_rect.w - lbl.get_width())//2, t_rect.y + 9))

        # 2. Target Rack
        lbl_rack = self.font_small.render("2. DESTINATION 42U RACK:", True, (0, 0, 0))
        surface.blit(lbl_rack, (right_r.x + 14, right_r.y + 102))

        rack_labels = {1: "Rack 1 (A01)", 2: "Rack 2 (A02)", 3: "Rack 3 (A03)"}
        for r_id, r_rect in rects["rack_rects"].items():
            is_active = (self.dm_selected_rack == r_id)
            bg = (235, 245, 255) if is_active else (250, 252, 255)
            border = (0, 115, 230) if is_active else (215, 225, 240)
            tc = (0, 95, 210) if is_active else (0, 0, 0)
            pygame.draw.rect(surface, bg, r_rect, border_radius=5)
            pygame.draw.rect(surface, border, r_rect, width=2 if is_active else 1, border_radius=5)
            lbl = self.font_small.render(rack_labels[r_id], True, tc)
            surface.blit(lbl, (r_rect.x + (r_rect.w - lbl.get_width())//2, r_rect.y + 8))

        # 3. U-Slot Stepper
        lbl_slot = self.font_small.render("3. RACK MOUNTING SLOT (1U - 42U):", True, (0, 0, 0))
        surface.blit(lbl_slot, (right_r.x + 14, right_r.y + 168))

        # [-] button
        sm_r = rects["slot_minus_rect"]
        pygame.draw.rect(surface, (244, 248, 253), sm_r, border_radius=5)
        pygame.draw.rect(surface, (210, 222, 238), sm_r, width=1, border_radius=5)
        m_s = self.font_btn.render("-", True, (0, 102, 204))
        surface.blit(m_s, (sm_r.x + (sm_r.w - m_s.get_width())//2, sm_r.y + 5))

        # Display box
        sd_r = rects["slot_display_rect"]
        pygame.draw.rect(surface, (255, 255, 255), sd_r, border_radius=5)
        pygame.draw.rect(surface, (200, 215, 235), sd_r, width=1, border_radius=5)
        needed_span = 1 if self.dm_selected_type in ("switch", "firewall") else 2
        slot_text = f"Unit Slot: {self.dm_selected_slot}U" + (f" - {self.dm_selected_slot+1}U" if needed_span > 1 else "")
        sd_s = self.font_bold.render(slot_text, True, (0, 0, 0))
        surface.blit(sd_s, (sd_r.x + (sd_r.w - sd_s.get_width())//2, sd_r.y + 8))

        # [+] button
        sp_r = rects["slot_plus_rect"]
        pygame.draw.rect(surface, (244, 248, 253), sp_r, border_radius=5)
        pygame.draw.rect(surface, (210, 222, 238), sp_r, width=1, border_radius=5)
        p_s = self.font_btn.render("+", True, (0, 102, 204))
        surface.blit(p_s, (sp_r.x + (sp_r.w - p_s.get_width())//2, sp_r.y + 5))

        # Slot Availability Check Badge
        is_occ, occ_dev = False, None
        if mode and hasattr(mode, "is_slot_occupied"):
            is_occ, occ_dev = mode.is_slot_occupied(self.dm_selected_rack, self.dm_selected_slot, needed_span)

        status_box_r = pygame.Rect(right_r.x, right_r.y + 228, right_r.w, 24)
        if is_occ:
            pygame.draw.rect(surface, (255, 244, 230), status_box_r, border_radius=4)
            st_lbl = self.font_small.render(f"[!] Occupied by {occ_dev.hostname}", True, (200, 95, 10))
        else:
            pygame.draw.rect(surface, (235, 250, 240), status_box_r, border_radius=4)
            st_lbl = self.font_small.render(f"[OK] Slot {self.dm_selected_slot}U is available for install", True, (15, 140, 60))
        surface.blit(st_lbl, (status_box_r.x + 10, status_box_r.y + 4))

        # 4. Hostname Input Field
        lbl_host = self.font_small.render("4. DEVICE HOSTNAME:", True, (0, 0, 0))
        surface.blit(lbl_host, (right_r.x + 14, right_r.y + 258))

        h_rect = rects["hostname_rect"]
        h_bg = (255, 255, 255) if self.dm_hostname_active else (250, 252, 255)
        h_border = (0, 115, 230) if self.dm_hostname_active else (210, 222, 238)
        pygame.draw.rect(surface, h_bg, h_rect, border_radius=5)
        pygame.draw.rect(surface, h_border, h_rect, width=2 if self.dm_hostname_active else 1, border_radius=5)

        cursor_str = "|" if (self.dm_hostname_active and (pygame.time.get_ticks() // 400) % 2 == 0) else ""
        h_val = self.font_mono.render(self.dm_hostname_input + cursor_str, True, (0, 0, 0))
        surface.blit(h_val, (h_rect.x + 10, h_rect.y + 8))

        # Helper hint
        hint_s = self.font_small.render("Click box to edit name, [ENTER] when done", True, (0, 0, 0))
        surface.blit(hint_s, (h_rect.x, h_rect.bottom + 4))

        # 5. Big Install Button
        inst_r = rects["install_btn_rect"]
        can_install = not is_occ
        inst_bg = (0, 115, 230) if can_install else (220, 228, 238)
        inst_tc = (255, 255, 255) if can_install else (0, 0, 0)

        # Shadow
        if can_install:
            pygame.draw.rect(surface, (200, 215, 235), (inst_r.x + 2, inst_r.y + 2, inst_r.w, inst_r.h), border_radius=7)

        pygame.draw.rect(surface, inst_bg, inst_r, border_radius=7)
        btn_text = "+ INSTALL TO RACK" if can_install else "SLOT OCCUPIED"
        b_lbl = self.font_btn.render(btn_text, True, inst_tc)
        surface.blit(b_lbl, (inst_r.x + (inst_r.w - b_lbl.get_width())//2, inst_r.y + 14))

        # Bottom Feedback Toast Message
        if self.dm_feedback:
            fb_s = self.font_small.render(self.dm_feedback, True, self.dm_feedback_color)
            surface.blit(fb_s, (right_r.x, inst_r.bottom + 12))
