# IEEE 802.1Q VLAN Trunking Verification Suite (Phase 4.5)

ตารางบันทึกผลการทดสอบการทำงานของ **IEEE 802.1Q VLAN Trunk Port** ครอบคลุมทั้งสิ้น 39 ชุดการทดสอบ (39/39 PASS, 100%)

---

## 1. ผลการรันชุดทดสอบภาพรวม (Summary)

- **Test Suite File**: [`tests/test_trunk.py`](file:///c:/Users/admin/Desktop/programming/game/tests/test_trunk.py)
- **Total Test Cases**: 39
- **Passed**: 39 (100%)
- **Failed**: 0 (0%)
- **Repository Regression**: 33/33 test suites passed (100%)

---

## 2. เมทริกซ์การทดสอบรายกรณี (Detailed Test Matrix)

### Group 1: Port Mode & Configuration Management (13 Tests)

| # | ชื่อการทดสอบ | เงื่อนไขเริ่มต้น (Preconditions) | การดำเนินการ (Actions) | ผลลัพธ์ที่คาดหวัง (Expected) | ผลลัพธ์จริง (Actual) | สถานะ |
|---|---|---|---|---|---|:---:|
| 1 | `test_set_port_mode_trunk` | Switch พอร์ต g0/1 เริ่มต้นเป็น access | สั่ง `switchport mode trunk` | `port.mode == "trunk"` | `port.mode == "trunk"` | **PASS** |
| 2 | `test_set_port_mode_access` | Switch พอร์ต g0/1 เป็น trunk | สั่ง `switchport mode access` | `port.mode == "access"` | `port.mode == "access"` | **PASS** |
| 3 | `test_configure_allowed_vlan_comma_list` | พอร์ตโหมด trunk | ตั้งค่า `switchport trunk allowed vlan 10,20,30` | `port.trunk_allowed_vlans == {10, 20, 30}` | `port.trunk_allowed_vlans == {10, 20, 30}` | **PASS** |
| 4 | `test_configure_allowed_vlan_range` | พอร์ตโหมด trunk | ตั้งค่า `switchport trunk allowed vlan 10-15` | `port.trunk_allowed_vlans == {10, 11, 12, 13, 14, 15}` | ตรงตามช่วง | **PASS** |
| 5 | `test_configure_allowed_vlan_combined` | พอร์ตโหมด trunk | ตั้งค่า `switchport trunk allowed vlan 1,5,10-12,20` | `port.trunk_allowed_vlans == {1, 5, 10, 11, 12, 20}` | ตรงตามช่วงและรายการ | **PASS** |
| 6 | `test_configure_native_vlan` | พอร์ตโหมด trunk (native vlan 1) | ตั้งค่า `switchport trunk native vlan 99` | `port.native_vlan == 99` | `port.native_vlan == 99` | **PASS** |
| 7 | `test_remove_trunk_allowed_vlan` | พอร์ตโหมด trunk กำหนด allowed vlan 10,20 | สั่ง `no switchport trunk allowed vlan` | รีเซ็ตกลับเป็น default `set(range(1, 4095))` | รีเซ็ตเป็น default 1-4094 | **PASS** |
| 8 | `test_remove_trunk_native_vlan` | พอร์ตโหมด trunk native vlan 99 | สั่ง `no switchport trunk native vlan` | รีเซ็ตกลับเป็น default `1` | `port.native_vlan == 1` | **PASS** |
| 9 | `test_invalid_vlan_id_rejected` | พอร์ตโหมด trunk | ทดสอบระบุ VLAN 0 และ 4095 | CLI แจ้ง Error และไม่เปลี่ยนค่าในพอร์ต | ปฏิเสธค่าที่ไม่ถูกต้อง | **PASS** |
| 10 | `test_invalid_vlan_range_rejected` | พอร์ตโหมด trunk | ทดสอบระบุช่วงกลับด้าน `30-20` | แจ้ง ValueError และไม่ยอมรับค่า | ปฏิเสธช่วงผิดพลาด | **PASS** |
| 11 | `test_duplicate_vlan_handling` | พอร์ตโหมด trunk | ระบุ `10,10,20,10,20` | ขจัดค่าซ้ำเหลือ `{10, 20}` | คืนค่า `{10, 20}` | **PASS** |
| 12 | `test_native_vlan_not_allowed_drops_ingress` | Trunk native vlan 99 แต่ allowed vlan มีเฉพาะ 1,10 | ส่งทราฟฟิก Untagged เข้าพอร์ต Trunk | ทราฟฟิกขาเข้าถูกดรอป (100% loss) | ทราฟฟิกดรอป 100% loss | **PASS** |
| 13 | `test_native_vlan_not_allowed_drops_egress` | Trunk native vlan 99 แต่ allowed vlan มีเฉพาะ 1 | ส่งทราฟฟิก VLAN 99 ข้าม Trunk | ทราฟฟิกขาออกถูกดรอป (100% loss) | ทราฟฟิกดรอป 100% loss | **PASS** |

---

### Group 2: Data Plane Forwarding & Isolation (8 Tests)

| # | ชื่อการทดสอบ | เงื่อนไขเริ่มต้น (Preconditions) | การดำเนินการ (Actions) | ผลลัพธ์ที่คาดหวัง (Expected) | ผลลัพธ์จริง (Actual) | สถานะ |
|---|---|---|---|---|---|:---:|
| 14 | `test_single_vlan_transport_over_trunk` | PC1 (VLAN 10) - SW1 - Trunk - SW2 - PC2 (VLAN 10) | PC1 ping PC2 | Ping สำเร็จ 0% loss (3/3 replies) | Ping สำเร็จ 0% loss | **PASS** |
| 15 | `test_multiple_vlans_over_single_trunk` | PC1/PC2 ใน VLAN 10, 20, 30 ข้าม Trunk เส้นเดียว | Ping แยกทีละคู่ VLAN 10, 20, 30 | ทุกคู่สื่อสารสำเร็จ 0% loss พร้อมกัน | ทุกคู่ 0% loss | **PASS** |
| 16 | `test_vlan_isolation_over_trunk` | PC1 (VLAN 10) และ PC2 (VLAN 20) แม้มี IP ซับเน็ตเดียวกัน | PC1 ping PC2 | ถูกดรอปโดย VLAN Isolation (100% loss) | ดรอป 100% loss | **PASS** |
| 17 | `test_access_to_trunk_to_access_flow` | PC1 (Access 10) -> SW1 -> Trunk -> SW2 -> PC2 (Access 10) | PC1 ping PC2 | แปลง Untagged -> Tagged -> Untagged สำเร็จ | 0% loss | **PASS** |
| 18 | `test_trunk_to_trunk_transit` | SW1 - Trunk1 - SW2 (Transit) - Trunk2 - SW3 | PC1 ping PC2 ข้าม 2 trunks | ทราฟฟิกส่งผ่านสวิตช์กลางได้สำเร็จ 0% loss | 0% loss | **PASS** |
| 19 | `test_allowed_vlan_passes_traffic` | Trunk กำหนด allowed vlan 10,20 | PC1 (VLAN 10) ping PC2 (VLAN 10) | ได้รับอนุญาตและส่งผ่านสำเร็จ | 0% loss | **PASS** |
| 20 | `test_disallowed_vlan_dropped_at_ingress` | Trunk บน SW2 ไม่อนุญาต VLAN 10 | PC1 (VLAN 10) ping PC2 (VLAN 10) | SW2 ดรอปทราฟฟิกที่ขาเข้า Trunk (100% loss) | 100% loss | **PASS** |
| 21 | `test_disallowed_vlan_dropped_at_egress` | Trunk บน SW1 ไม่อนุญาต VLAN 10 | PC1 (VLAN 10) ping PC2 (VLAN 10) | SW1 ดรอปทราฟฟิกที่ขาออก Trunk (100% loss) | 100% loss | **PASS** |

---

### Group 3: Tagging / Untagging Behavior (4 Tests)

| # | ชื่อการทดสอบ | เงื่อนไขเริ่มต้น (Preconditions) | การดำเนินการ (Actions) | ผลลัพธ์ที่คาดหวัง (Expected) | ผลลัพธ์จริง (Actual) | สถานะ |
|---|---|---|---|---|---|:---:|
| 22 | `test_allowed_vlan_update_stops_traffic_immediately` | Trunk เริ่มต้นอนุญาต VLAN 10 | ตัด VLAN 10 ออกจาก allowed list | ทราฟฟิกหยุดส่งผ่านทันที (100% loss) | 100% loss ทันที | **PASS** |
| 23 | `test_native_vlan_egress_is_untagged` | Trunk native vlan 99, frame vlan 99 | ส่งเฟรม vlan 99 ออกทาง trunk | เฟรมที่ส่งออกต้องเป็น `is_tagged == False` | `cand_tagged == False` | **PASS** |
| 24 | `test_non_native_vlan_egress_is_tagged` | Trunk native vlan 1, frame vlan 10 | ส่งเฟรม vlan 10 ออกทาง trunk | เฟรมที่ส่งออกต้องมีแท็ก 802.1Q (`is_tagged == True`) | `cand_tagged == True` | **PASS** |
| 25 | `test_untagged_ingress_maps_to_native_vlan` | Host ส่ง untagged เข้า trunk พอร์ต native vlan 10 | ตรวจสอบ VLAN ขาเข้าที่สวิตช์รับ | แมปเข้าสู่ `in_vlan == 10` และส่งต่อไปยัง access vlan 10 สำเร็จ | แมปเข้า VLAN 10 ถูกต้อง | **PASS** |

---

### Group 4: Native VLAN Mismatch Detection (1 Test)

| # | ชื่อการทดสอบ | เงื่อนไขเริ่มต้น (Preconditions) | การดำเนินการ (Actions) | ผลลัพธ์ที่คาดหวัง (Expected) | ผลลัพธ์จริง (Actual) | สถานะ |
|---|---|---|---|---|---|:---:|
| 26 | `test_native_vlan_mismatch_detected_and_blocked` | SW1 trunk native 10 vs SW2 trunk native 20 | ส่งทราฟฟิก Untagged ข้าม trunk | ตรวจพบ Native VLAN Mismatch ดรอปทราฟฟิกและแจ้งเตือน | ดรอป 100% และแจ้งเตือน Mismatch | **PASS** |

---

### Group 5: MAC Learning & Flooding (3 Tests)

| # | ชื่อการทดสอบ | เงื่อนไขเริ่มต้น (Preconditions) | การดำเนินการ (Actions) | ผลลัพธ์ที่คาดหวัง (Expected) | ผลลัพธ์จริง (Actual) | สถานะ |
|---|---|---|---|---|---|:---:|
| 27 | `test_mac_learning_per_vlan` | เฟรมจาก MAC_A เข้ามาบน VLAN 10 และ VLAN 20 | สวิตช์บันทึกตาราง MAC | `mac_vlan_table[(10, MAC_A)]` และ `(20, MAC_A)` แยกอิสระ | บันทึกแยกคีย์ Per-VLAN ชัดเจน | **PASS** |
| 28 | `test_broadcast_forwarding_isolated_to_vlan_over_trunk` | ส่ง Broadcast ใน VLAN 10 เข้าสวิตช์ | สวิตช์ Flood เฟรมออกพอร์ตสมาชิก | ส่งออกเฉพาะพอร์ตสมาชิก VLAN 10 และ Trunk ไม่ส่งออกพอร์ต VLAN 20 | ไม่หลุดไปยัง VLAN 20 | **PASS** |
| 29 | `test_unknown_unicast_flooding_respects_vlan_and_allowed_list` | ส่ง Unknown Unicast ใน VLAN 20 | สวิตช์ Flood เฟรม | ส่งออกเฉพาะพอร์ต VLAN 20 และ Trunk ที่ allowed VLAN 20 | ไม่ส่งออก Trunk ที่ disallow | **PASS** |

---

### Group 6: Spanning Tree Protocol (STP) Integration (1 Test)

| # | ชื่อการทดสอบ | เงื่อนไขเริ่มต้น (Preconditions) | การดำเนินการ (Actions) | ผลลัพธ์ที่คาดหวัง (Expected) | ผลลัพธ์จริง (Actual) | สถานะ |
|---|---|---|---|---|---|:---:|
| 30 | `test_stp_blocking_port_drops_trunk_traffic` | วงจร Triangle Loop สวิตช์ 3 ตัวเชื่อมต่อด้วย 802.1Q Trunks | STP คำนวณบล็อกพอร์ต SW3 g0/2 | พอร์ตที่ถูกบล็อกดรอปทราฟฟิกทุกชนิด ไม่ Flood และไม่เรียนรู้ MAC | ดรอปทราฟฟิกสมบูรณ์ | **PASS** |

---

### Group 7: Subsystems & Dynamic Routing Integration (6 Tests)

| # | ชื่อการทดสอบ | เงื่อนไขเริ่มต้น (Preconditions) | การดำเนินการ (Actions) | ผลลัพธ์ที่คาดหวัง (Expected) | ผลลัพธ์จริง (Actual) | สถานะ |
|---|---|---|---|---|---|:---:|
| 31 | `test_router_on_a_stick_subinterfaces_over_trunk` | Router subinterfaces (`g0/0.10`, `g0/0.20`) เชื่อมกับ Trunk | PC1 (VLAN 10) ping PC2 (VLAN 20) | เราเตอร์ Route ข้าม VLAN ผ่าน Trunk สำเร็จ (0% loss) | 0% loss (3/3 replies) | **PASS** |
| 32 | `test_dhcp_over_trunk_multiple_vlans` | DHCP Server บน Router แจก IP ข้าม Trunk ให้ VLAN 10 และ 20 | PC1 และ PC2 ขอรับ IP ผ่าน DORA | PC1 ได้ `192.168.10.x`, PC2 ได้ `192.168.20.x` ถูกต้อง | ได้รับ IP และ GW ตรงตาม Pool | **PASS** |
| 33 | `test_ripv2_over_trunk_subinterfaces` | R1 และ R2 รัน RIPv2 ผ่าน Trunk Subinterfaces | ตรวจสอบเส้นทางใน Routing Table | R1 เรียนรู้เส้นทาง `172.16.1.0/24` (Type R) จาก R2 | ติดตั้ง Dynamic Route R สำเร็จ | **PASS** |
| 34 | `test_ospfv2_over_trunk_subinterfaces` | R1 และ R2 รัน OSPFv2 (Area 0) ผ่าน Trunk Subinterfaces | ตรวจสอบ Adjacency และ Route | สถานะ Neighbor เป็น `FULL` และเรียนรู้เส้นทาง `Type O` | Neighbor FULL, ติดตั้ง Route O | **PASS** |
| 35 | `test_svi_communication_over_trunk` | SW1 (SVI Vlan30) เชื่อมต่อผ่าน Trunk กับ SW2 (SVI Vlan30) | SW1 ping SW2 Vlan30 IP | ปิงสำเร็จข้าม Trunk Port (0% loss) | 0% loss (3/3 replies) | **PASS** |
| 36 | `test_tagged_frame_on_access_port_dropped` | ส่งเฟรม Tagged 802.1Q เข้าพอร์ตโหมด Access | สวิตช์ตรวจสอบเฟรมขาเข้า | ดรอปเฟรมทันที (`Access port dropped tagged frame`) | ดรอปเฟรมถูกต้อง | **PASS** |

---

### Group 8: Cisco IOS CLI Show & Configuration Verification (3 Tests)

| # | ชื่อการทดสอบ | เงื่อนไขเริ่มต้น (Preconditions) | การดำเนินการ (Actions) | ผลลัพธ์ที่คาดหวัง (Expected) | ผลลัพธ์จริง (Actual) | สถานะ |
|---|---|---|---|---|---|:---:|
| 37 | `test_cli_show_interfaces_switchport` | พอร์ต g0/1 ตั้งค่าเป็น trunk allowed 10,20,30 native 10 | รัน `show interfaces switchport` | แสดง Operational Mode: trunk, Native VLAN: 10, Allowed: 10,20,30 | ผลลัพธ์ครบถ้วนถูกต้อง | **PASS** |
| 38 | `test_cli_show_interfaces_trunk` | พอร์ต g0/1 ตั้งค่าเป็น trunk allowed 10-15,20 native 10 | รัน `show interfaces trunk` | แสดงตารางพอร์ต trunk, 802.1q, Native vlan 10, Allowed 10-15,20 | แสดงตาราง 802.1q ถูกต้อง | **PASS** |
| 39 | `test_cli_show_running_config_trunk` | พอร์ต g0/1 ตั้งค่า trunk | รัน `show running-config` | แสดงคำสั่ง `switchport mode trunk`, `allowed vlan`, `native vlan` | แสดงบล็อกการตั้งค่าครบถ้วน | **PASS** |

---

## 3. สรุปผลการทดสอบ

ระบบ IEEE 802.1Q VLAN Trunk Port ในโปรเจกต์ NetEngineer 3D ผ่านเกณฑ์การทดสอบทั้งหมด **39 จาก 39 การทดสอบ (100%)** และรักษาความเข้ากันได้กับชุดทดสอบเดิมทั้งหมด **33 จาก 33 สวีท (100%)** โดยไม่มี Regression เกิดขึ้น
