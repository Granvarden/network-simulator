# Network Core Audit Report

## 1. ข้อมูลภาพรวมของระบบและโครงสร้างโมดูล (Module Overview)

Repository นี้เป็น Network Simulator ที่จำลองอุปกรณ์เครือข่าย Cisco IOS / Linux แบบเสมือนจริงในสภาพแวดล้อม 3D และ CLI โดยมีโมดูลหลักใน `network/` ดังนี้:

- **`network/device.py` (`BaseDevice`, `Port`, `LEDState`)**:
  - กำหนดโครงสร้างพื้นฐานของอุปกรณ์และพอร์ต (Layer 1/2/3)
  - รองรับพอร์ต RJ45, Fiber, Console
  - เก็บสถานะ shutdown, speed, duplex, access/trunk mode, access VLAN, trunk allowed VLANs, IP address, Subnet Mask และ MAC address
  - มีตาราง `arp_table` (`ip` -> `mac`, `interface`, `age_min`, `type`)
  - มีระบบ LED Link / Traffic indicator คำนวณจาก `last_traffic_time`
- **`network/cable.py` (`Cable`, `CableType`)**:
  - จัดการการเชื่อมต่อ Physical ระหว่าง 2 พอร์ต (`port_a`, `port_b`)
  - รองรับสถานะชำรุด `is_damaged`
  - คำนวณ Catenary curve 3D สำหรับการแสดงผลสายเคเบิล
- **`network/host.py` (`Host`)**:
  - รองรับอุปกรณ์ปลายทาง: Server, Engineer Laptop, ISP Gateway
  - จัดการ IP configuration, Default Gateway, DNS
- **`network/switch.py` (`Switch`)**:
  - จำลอง Managed Layer 2 Switch (Cisco Catalyst style)
  - จัดการ VLAN Database (`vlans`) และ MAC Table (`mac_table`)
  - ฟังก์ชัน `learn_mac(mac, port, vlan)` บันทึก source MAC
  - ฟังก์ชัน `forward_packet(in_port, src_mac, dst_mac, vlan)` สำหรับ flood/unicast ตาม VLAN
- **`network/router.py` (`Router`, `SubInterface`)**:
  - จำลอง Layer 3 Router (Cisco IOS style)
  - จัดการ Connected routes, Subinterfaces (`802.1Q`), Static routes
  - ค้นหาเส้นทางด้วย Longest Prefix Match (`lookup_route`)
  - รองรับ Standard IPv4 ACL (`access_lists`) และ Cisco IOS NAT/PAT Overload (`perform_nat`)
- **`network/firewall.py` (`Firewall`)**:
  - จำลอง Stateful Firewall (Cisco ASA style)
  - จัดการ Security Zones (`nameif`), Security Levels (`inside=100`, `outside=0`, `dmz=50`)
  - มีตาราง Session `connections` และ Extended ACL / `access-group`
- **`network/packet_engine.py` (`PacketEngine`, `PingResult`)**:
  - หัวใจหลักในการส่ง packet แบบ hop-by-hop
  - จำลอง ICMP Ping (`simulate_ping`), Single packet tracing (`trace_single_packet`), Traceroute (`simulate_traceroute`)
  - คำนวณ RTT, Jitter, TTL, และ Cisco status codes (`!`, `.`, `U`, `A`)

---

## 2. สิ่งที่ทำงานถูกต้องอยู่แล้ว (Working Correctly)

1. **Layer 1 Physical Link & Cable Disconnect**:
   - พอร์ตตรวจสอบ `is_link_up` ตามสถานะ shutdown และสายเคเบิลได้ถูกต้อง
   - การตัดสายเคเบิลทำให้ ping ล้มเหลว (`U` / Loss 100%) ทันที
2. **Subinterfaces (Router-on-a-stick)**:
   - สามารถสร้าง subinterface (เช่น `g0/0.10`) และผูกกับ VLAN tag 802.1Q ได้
3. **Cisco CLI Interface Parser**:
   - คำสั่ง Cisco IOS พื้นฐาน เช่น `show ip interface brief`, `show ip route`, `show vlan brief`, `ip address`, `no shutdown` ทำงานได้ตรงตามไวยากรณ์
4. **Cold ARP Drop Simulation**:
   - เมื่อเปิด `simulate_arp=True` แพ็กเก็ตแรกที่ cold cache จะ drop (`.`) และเรียนรู้ ARP ให้แพ็กเก็ตถัดไปสำเร็จ (`!`)

---

## 3. Bug และจุดที่มีความเสี่ยงสำคัญที่พบ (Identified Bugs & Critical Risks)

### Bug 1: การ Overwrite Source IP ของ Packet ใน Router (Accidental NAT / Source Masking)
- **ตำแหน่ง**: `network/packet_engine.py` (บรรทัด 480)
- **สาเหตุ**: เมื่อ Router ทำการ Forward packet ต่อ มีการส่งพารามิเตอร์ต้นทางเป็น:
  `getattr(egress_if, "ip_address", active_src_ip)`
  ซึ่งเนื่องจาก interface ของ Router มี IP address เสมอ ทำให้ `getattr` เลือก `egress_if.ip_address` ไปแทนที่ `current_ip` ของ packet
- **ผลกระทบ**: ทุกครั้งที่ packet วิ่งผ่าน router ตัว source IP จะถูกเปลี่ยนเป็น IP ของ router ทันที (กลายเป็นการทำ Source NAT โดยไม่ได้ตั้งใจ) ส่งผลให้ downstream firewall หรือ ACL ที่ตรวจสอบ source IP เดิมทำงานผิดพลาดทั้งหมด

### Bug 2: Packet Engine Bypass MAC Learning & Unicast Forwarding ของ Switch
- **ตำแหน่ง**: `network/packet_engine.py` (บรรทัด 407)
- **สาเหตุ**: มีการ hardcode ค่า:
  `next_dev.forward_packet(peer_port, "00:AA:BB:CC:DD:EE", "FF:FF:FF:FF:FF:FF", in_vlan)`
- **ผลกระทบ**: Switch ไม่เคยได้เรียนรู้ MAC จริงของ Host/Router และทุก frame ถูกถือว่าเป็น Broadcast (`FF:FF:FF:FF:FF:FF`) เสมอ ทำให้ switch เกิด flooding ตลอดเวลา และระบบ Unicast MAC Lookup ไม่เคยถูกเรียกใช้งานจริงใน forwarding loop

### Bug 3: การจำลอง ICMP เป็น One-Way (ไม่มี Echo Reply Traversal)
- **ตำแหน่ง**: `network/packet_engine.py` (`_trace_packet`)
- **สาเหตุ**: การ trace ทำเฉพาะทิศทาง Request จาก Source ไป Destination เมื่อปลายทางตรงกับ `_is_device_ip` ฟังก์ชันจะคืนค่า `True` ทันที โดยไม่มีการส่ง Echo Reply ย้อนกลับมา
- **ผลกระทบ**:
  - ไม่มีการตรวจสอบว่าปลายทางมี Route ย้อนกลับหรือไม่ (แม้ปลายทางไม่มี Default Gateway หรือ Route กลับ ก็ยัง ping สำเร็จ)
  - ไม่มีการทดสอบ Reverse NAT
  - ไม่มีการทดสอบ Stateful Firewall สำหรับ Return Traffic
  - ไม่สามารถตรวจสอบ Asymmetric Route หรือ ACL ขากลับได้

### Bug 4: Stateful Firewall ขาดการตรวจสอบ Established Session ขากลับ
- **ตำแหน่ง**: `network/firewall.py` (`inspect_packet`)
- **สาเหตุ**: ในโค้ดมีขั้นตอนที่ 3 (Outbound: Higher -> Lower security level บันทึกลง `self.connections`) แล้วข้ามไปขั้นตอนที่ 5 (Inbound ACL) โดยไม่มีการนำ packet ขากลับมาเช็คกับ `self.connections` ที่เคยบันทึกไว้
- **ผลกระทบ**: หากมีการส่ง Return Traffic ผ่าน Firewall จริง traffic จะถูก drop ทันทีเนื่องจากคิดว่าเป็น Inbound connection ใหม่ที่ไม่มี ACL

### Bug 5: Router ขาด Reverse NAT Translation
- **ตำแหน่ง**: `network/router.py`
- **สาเหตุ**: มีเฉพาะฟังก์ชัน `perform_nat` (Inside -> Outside) แต่ไม่มีฟังก์ชันสำหรับ Outside -> Inside เพื่อแปลง Destination IP กลับจาก `inside_global` เป็น `inside_local` ตามตาราง `nat_translations`
- **ผลกระทบ**: Traffic ขากลับจาก Outside สู่ Inside Host จะไม่สามารถส่งถึงเครื่องปลายทางที่แท้จริงได้

### Bug 6: Switch VLAN Isolation รั่วไหลในกระบวนการ ARP Resolution
- **ตำแหน่ง**: `network/packet_engine.py` (`_probe_arp_resolution`)
- **สาเหตุ**: ในลูปตรวจสอบพอร์ตของ Switch มีการลูปทุกพอร์ตโดยไม่ได้ตรวจว่าพอร์ตนั้นอยู่ใน VLAN เดียวกันหรือไม่
- **ผลกระทบ**: Host ที่อยู่ต่าง VLAN บน Switch ตัวเดียวกันสามารถ resolve ARP ข้าม VLAN กันได้โดยตรง แม้ไม่มี Router

### Bug 7: ขาดฟังก์ชันลบ Static Route (`remove_static_route` / `no ip route`)
- **ตำแหน่ง**: `network/router.py`, `network/firewall.py`, `cli/command_executor.py`
- **สาเหตุ**: มีเฉพาะ `add_static_route` แต่ไม่มี `remove_static_route` และไม่มี parser รองรับ `no ip route <net> <mask> <gw>`
- **ผลกระทบ**: ไม่สามารถลบ route ที่ตั้งผิดได้ และการตรวจสอบว่า next-hop เป็น IP หรือ Interface ใช้ heuristic ที่เปราะบาง (`not next_hop_or_int.lower().startswith("g")`)

### Bug 8: Router ไม่ได้นำ ACL มาบังคับใช้ขณะ Forward Packet
- **ตำแหน่ง**: `network/router.py`, `network/packet_engine.py`
- **สาเหตุ**: `Router` มี `access_lists` และ `matches_acl` แต่ไม่ได้ผูกกับ interface (`access_groups`) และใน `_trace_packet` ส่วนของ Router ไม่มีการเรียกตรวจ ACL ก่อนหรือหลัง routing
- **ผลกระทบ**: ไม่สามารถทำ Ingress/Egress Packet Filtering ด้วย Standard ACL บน Router ได้

### Bug 9: การคำนวณ TTL Reply และ Drop Diagnostic ที่ไม่สมบูรณ์
- **ตำแหน่ง**: `network/packet_engine.py`
- **สาเหตุ**: คำนวณ TTL ขากลับโดยนับ substring ใน hostname เช่น `"router"`, `"firewall"` หากอุปกรณ์ชื่อ `R1`, `Core` หรือ `Border` จะไม่ถูกนับว่าลด TTL และเมื่อ drop ไม่มีการระบุเหตุผลที่ชัดเจน (เช่น No route, Interface down, ACL deny, ARP failure, VLAN mismatch)

---

## 4. สถานะ Test Suite เดิม (Existing Tests)

- `tests/test_network.py`: ผ่าน (ทดสอบ topology พื้นฐาน 1 Switch 1 Router)
- `tests/test_realistic_ping.py`: โค้ด network ผ่าน แต่ติด error headless pygame ในฟังก์ชัน terminal UI
- `tests/test_nat_firewall_crouch.py`: ผ่าน (ผ่านเพราะ Ping เป็น one-way และไม่ได้ทดสอบ return traffic)
- `tests/test_isp_gateway.py`: ผ่าน
- `tests/test_cli.py` & `test_cli_help.py`: ผ่าน

---

## 5. แผนการเพิ่ม Automated Tests สำหรับแต่ละ Phase (Tests to Add)

1. **`tests/test_packet_engine.py`**: ทดสอบ Packet lifecycle, Hop-by-hop forwarding, TTL decrement, Drop diagnostic reasons
2. **`tests/test_arp.py`**: ทดสอบ Cold ARP drop, Cache hit, Cache lookup, Clear ARP, Unreachable ARP, Switch VLAN isolation ใน ARP
3. **`tests/test_icmp.py`**: ทดสอบ Two-way Echo Request & Echo Reply, PC->Router, PC->PC, Router->Router, Unreachable, Interface down, Link down
4. **`tests/test_router.py`**: ทดสอบ Connected routes (active/inactive interfaces), Subinterfaces 802.1Q, Next-hop forwarding, Default route
5. **`tests/test_static_routing.py`**: ทดสอบ Add/Remove static route, Longest Prefix Match (/24 vs /16 vs /8 vs /0), Invalid route rejection, Unreachable next-hop
6. **`tests/test_switch.py`**: ทดสอบ Source MAC learning, Destination MAC lookup, Known unicast forwarding, Unknown unicast flooding, Port shutdown
7. **`tests/test_vlan.py`**: ทดสอบ Access VLAN isolation, Trunk allowed VLANs, Inter-VLAN routing (Router-on-a-stick)
8. **`tests/test_nat.py`**: ทดสอบ Inside->Outside translation, Outside->Inside reverse translation, NAT table state, NAT ACL permit/deny
9. **`tests/test_acl.py`**: ทดสอบ Standard ACL permit/deny, Rule ordering, First-match, Implicit deny, Interface access-group in/out, Diagnostic drop reason
10. **`tests/test_firewall.py`**: ทดสอบ Security zone levels, Stateful permit & session table, Established return traffic, Unsolicited inbound drop, Extended ACL permit
11. **`tests/test_multihop.py`**: ทดสอบ Multi-hop topology เต็มรูปแบบ `PC1 -> SW1 -> R1 -> R2 -> SW2 -> PC2` ทั้งทิศทางไปและกลับ พร้อม failure testing

---

## 6. ตารางผลการทดสอบทั้งหมด (Test Matrix & Verification Results)

การทดสอบรันด้วย Python 3.11.9 ผ่านทั้งหมด 17/17 โมดูล (100% PASS Rate):

| Test Module | Phase / Target | Description & Coverage | Status |
| :--- | :--- | :--- | :---: |
| **`tests/test_packet_engine.py`** | Phase B: Packet Engine | วงจรชีวิต Packet, TTL decrement ข้าม L3, Loop detection, Drop diagnostic | **PASS** |
| **`tests/test_arp.py`** | Phase C: ARP | Cold ARP drop (`.!!!!`), Cache hit, Cache timeout, VLAN isolation ใน ARP probe | **PASS** |
| **`tests/test_icmp.py`** | Phase D: Two-way ICMP | Two-way ping (Echo Request -> Echo Reply), Return route check, Interface down | **PASS** |
| **`tests/test_router.py`** | Phase E: Router | Connected routes, Shutdown status, Subinterface (802.1Q), Multi-hop router forwarding | **PASS** |
| **`tests/test_static_routing.py`** | Phase F: Static Routing | Add/Remove static route (`no ip route`), Longest Prefix Match (/24 > /16 > /8 > /0) | **PASS** |
| **`tests/test_switch.py`** | Phase G: Switch MAC | Real MAC learning, Known unicast forwarding, Unknown unicast flooding, Port down | **PASS** |
| **`tests/test_vlan.py`** | Phase H: VLAN | Access VLAN isolation, Trunk allowed VLANs, Router-on-a-Stick inter-VLAN routing | **PASS** |
| **`tests/test_nat.py`** | Phase I: NAT | Inside->Outside PAT overload, Outside->Inside Reverse NAT translation | **PASS** |
| **`tests/test_acl.py`** | Phase J: ACL | Standard ACL permit/deny, First-match rule ordering, Implicit deny, Access-group | **PASS** |
| **`tests/test_firewall.py`** | Phase K: Firewall | Security zones, Stateful inspection, Return traffic matching established session | **PASS** |
| **`tests/test_multihop.py`** | Phase L & M: End-to-End & Failures | 6-Device topology (`PC1 <-> SW1 <-> R1 <-> R2 <-> SW2 <-> PC2`), Link down, Missing route, Invalid next-hop, VLAN mismatch, Router ACL deny, Firewall drop | **PASS** |
| **`tests/test_network.py`** | Regression | Core topology, Port traffic triggers, CLI basic ping | **PASS** |
| **`tests/test_nat_firewall_crouch.py`** | Regression | Realistic NAT overload, Outside ping pass/drop, Game physics state | **PASS** |
| **`tests/test_realistic_ping.py`** | Regression | Cisco IOS / Linux ping formatting, Jitter, Terminal streaming | **PASS** |
| **`tests/test_isp_gateway.py`** | Regression | WAN gateway forwarding, Public IP routing | **PASS** |
| **`tests/test_cli.py`** | Regression | Cisco CLI commands, Interface configs, Show commands | **PASS** |
| **`tests/test_cli_help.py`** | Regression | CLI context-sensitive help (`?` / tab completion) | **PASS** |

---

## 7. สรุปรายการแก้ไขและปรับปรุง Network Core (Summary of Fixes Implemented)

1. **`network/packet_engine.py`**:
   - **True Two-way ICMP Simulation**: แยกการประมวลผลเป็น Echo Request (ต้นทาง -> ปลายทาง) และ Echo Reply (ปลายทาง -> ต้นทาง) ตรวจสอบว่าเครื่องปลายทางมี Gateway หรือ Return Route ถูกต้องก่อนตอบกลับ
   - **Fix Accidental NAT / Source Masking**: รักษา IP ต้นทางที่แท้จริง (`active_src_ip`) ตลอด hop จนกว่าจะถูกแปลงด้วย Forward NAT อย่างตั้งใจ
   - **Real MAC Layer 2 Forwarding**: ส่ง MAC ต้นทางจริงและ MAC ปลายทางที่ resolve จาก ARP ไปยัง Switch ทำให้ Switch สามารถสร้างตาราง MAC Address Table ได้ถูกต้อง และใช้ Unicast Forwarding แทน Flooding ตลอดเวลา
   - **Router-on-a-Stick Loop Detection**: เปลี่ยนการจำกัดลูปจากการจำอุปกรณ์เดี่ยว (`dev.id`) เป็น Tuple `(dev.id, vlan_id)` ทำให้ Packet สามารถวิ่งผ่าน Switch เดิมได้ถูกต้องเมื่อเปลี่ยน VLAN ผ่าน Router
   - **Router ACL & Access-Group Integration**: นำ Ingress/Egress ACL (`access-groups`) มาตรวจสอบก่อน Forward แพ็กเก็ต และรายงานรหัส `'A'` พร้อมระบุข้อความกฎที่ Deny
   - **Stateful Return Path**: ตรวจสอบ Session ขากลับ (`is_reply=True`) บน Firewall และเรียก `perform_reverse_nat` บน Router ขากลับจาก Outside สู่ Inside

2. **`network/router.py`**:
   - เพิ่ม `is_valid_ipv4(ip_str)` สำหรับตรวจสอบความถูกต้องของ IP address
   - ปรับปรุงให้ Connected Route ถูกสร้างเฉพาะเมื่อ Interface มีสถานะ `is_link_up` (ไม่ถูก shutdown)
   - เพิ่มฟังก์ชัน `remove_static_route(network, mask, next_hop=None)`
   - เพิ่มฟังก์ชัน `set_access_group(acl_id, direction, interface_name)`
   - เพิ่มฟังก์ชัน `check_acl(acl_id, ip_address)` รองรับ First-match ordering และ Implicit Deny
   - เพิ่มฟังก์ชัน `perform_reverse_nat(target_ip, in_interface, protocol)` สำหรับ Outside -> Inside traffic

3. **`network/firewall.py`**:
   - เพิ่มฟังก์ชัน `remove_static_route(network, mask, next_hop=None, interface=None)`
   - ปรับปรุง `lookup_route` ให้ค้นหา Recursive Next-Hop Interface ได้อัตโนมัติ
   - ปรับปรุง `inspect_packet` ให้รองรับการตรวจสอบ Established Session สำหรับแพ็กเก็ตขากลับ (`is_reply=True`), ตรวจสอบ Ingress ACL ก่อน, และรองรับการถอดถอน ACL เมื่อส่ง `acl_name=None`

4. **`cli/command_executor.py`**:
   - เพิ่มคำสั่ง `no ip route <network> <subnet_mask> [next_hop/interface]`
   - เพิ่มคำสั่ง `ip access-group <acl_id> in|out` ใน Interface Configuration Mode

---

## 8. ข้อจำกัดของระบบปัจจุบันและแนวทางพัฒนาในอนาคต (Limitations & Future Roadmap)

ตามเงื่อนไขความปลอดภัยและเสถียรภาพสูงสุดของโครงการ ฟีเจอร์ต่อไปนี้ถูกจำกัดไม่ให้ถูกเพิ่มในระหว่างการปรับปรุง Network Core ครั้งนี้:

1. **Dynamic Routing Protocols**:
   - ปัจจุบันรองรับเฉพาะ Connected Routes และ Static Routing (Longest Prefix Match)
   - *Future Roadmap*: ในอนาคตสามารถพิจารณาเพิ่ม OSPF (Single Area 0) หรือ RIPv2 โดยใช้ Dijkstra Algorithm และ Periodic Updates
2. **Layer 2 Loop Prevention**:
   - ปัจจุบัน Switch ใช้ Loop Detection ของ Packet Engine (`visited` set) และไม่มี Spanning Tree Protocol (STP / 802.1D)
   - *Future Roadmap*: เพิ่ม BPDU generation, Port States (Blocking, Listening, Learning, Forwarding), และ Root Bridge Election
3. **Automated IP Allocation & Name Resolution**:
   - ปัจจุบัน Host ต้องกำหนด IP / Gateway แบบ Static เท่านั้น (ไม่มี DHCP และ DNS resolution)
   - *Future Roadmap*: เพิ่ม DHCP Server/Client DORA process และ Local DNS resolver
4. **Transport Layer Protocols**:
   - ปัจจุบัน Engine จำลองเฉพาะ ICMP (Ping / Traceroute)
   - *Future Roadmap*: เพิ่ม TCP 3-way handshake (SYN, SYN-ACK, ACK) และ UDP transport สำหรับการจำลอง Application Services เช่น HTTP, SSH, Telnet
5. **IPv6 Support**:
   - รองรับเฉพาะ IPv4 32-bit addressing
   - *Future Roadmap*: เพิ่ม IPv6 128-bit addressing, SLAAC, และ NDP (Neighbor Discovery Protocol)
