# DHCP Verification & Test Report

เอกสารสรุปผลการทดสอบและการตรวจสอบระบบ **DHCP IPv4 (Phase 3)** ใน Network Simulator

---

## 1. ผลการทดสอบโดยรวม (Overall Test Summary)

- **จำนวนชุดทดสอบทั้งหมด**: 28 Test Suites
- **ผลลัพธ์**: ผ่านทั้งหมด 28/28 (100% Pass Rate)
- **การทดสอบการถดถอย (Regression Testing)**: ไม่มีข้อผิดพลาด (Zero Regressions) ในฟังก์ชันเดิมทั้ง Router, Switch, VLAN, SVI, STP, NAT, ACL, Firewall, Packet Engine และ CLI

```
Total Test Suites : 28
Passed            : 28
Failed            : 0
Duration          : ~12s
```

---

## 2. รายละเอียดกรณีทดสอบ DHCP (`tests/test_dhcp.py`)

ชุดทดสอบ `tests/test_dhcp.py` ครอบคลุม 22 Scenarios หลัก:

| # | Test Scenario | รายละเอียดการทดสอบ | ผลลัพธ์ |
|---|---|---|:---:|
| 1 | `test_dhcp_pool_creation_and_subnet_arithmetic` | คำนวณ Subnet Host Address (/24 = 254 hosts, /30 = 2 hosts) และตัด Network/Broadcast ID | **PASS** |
| 2 | `test_dhcp_server_pool_management` | การสร้าง, ดึงข้อมูล, และลบ Pool พร้อมลบ Lease ที่ผูกอยู่ | **PASS** |
| 3 | `test_dhcp_excluded_addresses` | การยกเว้น IP Address เดี่ยวและช่วง IP (Range) ไม่ให้ถูกแจก | **PASS** |
| 4 | `test_dora_basic_handshake` | ทดสอบ DORA State Machine 4 สเต็ปครบถ้วน พร้อมตรวจสอบ Option 1, 3, 6, 51 | **PASS** |
| 5 | `test_host_dhcp_client_configuration` | Host ได้รับ IP, Subnet Mask, Default Gateway, DNS และสถานะกลายเป็น `BOUND` | **PASS** |
| 6 | `test_multiple_hosts_unique_leases` | โฮสต์หลายตัวขอ IP พร้อมกันและได้รับ IP ที่ไม่ซ้ำกัน (No Duplicate Leases) | **PASS** |
| 7 | `test_dhcp_pool_exhaustion` | เมื่อ IP ใน Pool หมด ระบบปฏิเสธอย่างถูกต้อง ไม่ Crash และคืนสถานะ Pool Exhausted | **PASS** |
| 8 | `test_dhcp_release_and_reclaim` | คำสั่ง Release ปลดปล่อย IP คืน Server ทันที และโฮสต์อื่นสามารถขอใช้ต่อได้ | **PASS** |
| 9 | `test_dhcp_re_request_same_ip` | Client เดิม (MAC เดิม) ขอ IP ซ้ำ จะได้รับ IP เดิมที่เคยเช่าไว้ | **PASS** |
| 10 | `test_dhcp_nak_on_invalid_request` | ส่ง DHCPNAK เมื่อ Client ขอ IP นอก Pool หรือ IP ที่ถูก Exclude ไว้ | **PASS** |
| 11 | `test_svi_as_dhcp_server` | Switch SVI (Layer 3) ทำหน้าที่เป็น DHCP Server แจก IP ให้พอร์ต Access ใน VLAN เดียวกัน | **PASS** |
| 12 | `test_vlan_aware_dhcp_isolation` | โฮสต์ใน VLAN 10 และ VLAN 20 ได้รับ IP แยกตาม Subnet ของแต่ละ VLAN อย่างถูกต้อง | **PASS** |
| 13 | `test_router_subinterfaces_dhcp_server` | Router-on-a-Stick (Subinterface .10, .20) แจก IP ข้าม 802.1Q Trunk ไปยังสวิตช์ | **PASS** |
| 14 | `test_stp_compatibility_dhcp_blocked_port` | แพ็กเก็ต DHCP Broadcast ถูกบล็อกบนพอร์ต STP `Blocking` ป้องกัน Loop | **PASS** |
| 15 | `test_static_ip_coexistence_and_ping` | โฮสต์ Static IP ทำงานร่วมกับโฮสต์ DHCP บน Subnet เดียวกันได้โดยไม่มีปัญหา IP ชนกัน | **PASS** |
| 16 | `test_dhcp_hosts_ping_each_other_and_gateway` | โฮสต์ที่ได้รับ IP จาก DHCP สามารถทำ ARP Resolution และส่ง ICMP Ping หากันและหา Gateway ได้ | **PASS** |
| 17 | `test_cisco_cli_dhcp_pool_configuration` | ทดสอบ Cisco CLI `ip dhcp pool`, `network`, `default-router`, `dns-server`, `lease`, `excluded-address` | **PASS** |
| 18 | `test_cisco_cli_show_commands` | ตรวจสอบการแสดงผล `show ip dhcp pool`, `show ip dhcp binding`, `show ip dhcp statistics` | **PASS** |
| 19 | `test_cisco_cli_ip_address_dhcp` | คำสั่ง `ip address dhcp` บนพอร์ต Router / Switch SVI และแสดง `DHCP` ใน `show ip int br` | **PASS** |
| 20 | `test_linux_host_cli_dhclient` | ทดสอบ Linux CLI บน Host: `dhclient` ขอ IP และ `dhclient -r` ปลดปล่อย IP | **PASS** |
| 21 | `test_show_running_config_dhcp` | ตรวจสอบว่า `show running-config` แสดง `ip dhcp excluded-address` และบล็อก `ip dhcp pool` ครบถ้วน | **PASS** |
| 22 | `test_multi_switch_dhcp_over_trunk` | ส่งผ่าน DHCP Broadcast ข้ามระหว่าง Switch 2 ตัวผ่าน 802.1Q Trunk Link สำเร็จ | **PASS** |

---

## 3. ผลการทดสอบ Regression Suites ทั้งหมด

```
[PASS] test_acl.py
[PASS] test_arp.py
[PASS] test_cable_physics.py
[PASS] test_camera_movement.py
[PASS] test_cli.py
[PASS] test_cli_help.py
[PASS] test_dhcp.py
[PASS] test_firewall.py
[PASS] test_game_loop.py
[PASS] test_icmp.py
[PASS] test_isp_gateway.py
[PASS] test_laptop_gui.py
[PASS] test_menu_mouse.py
[PASS] test_modes.py
[PASS] test_multihop.py
[PASS] test_nat.py
[PASS] test_nat_firewall_crouch.py
[PASS] test_network.py
[PASS] test_packet_engine.py
[PASS] test_realistic_ping.py
[PASS] test_router.py
[PASS] test_static_routing.py
[PASS] test_stp.py
[PASS] test_svi.py
[PASS] test_switch.py
[PASS] test_terminal_layout.py
[PASS] test_ttl.py
[PASS] test_vlan.py

Total: 28, Passed: 28, Failed: 0
```
