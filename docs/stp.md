# Spanning Tree Protocol (STP) Documentation

เอกสารอธิบายการทำงานของ **Classic STP (IEEE 802.1D-Style Simulation)** ในโปรเจกต์ NetEngineer 3D

> **หมายเหตุสำคัญ:**
> การจำลอง STP ในระบบนี้เป็นการจำลองเชิงพฤติกรรม (Behavioral Simulation) ตามมาตรฐาน **Classic STP (IEEE 802.1D)** โดยใช้ขั้นตอนวิธี Deterministic Graph & Topology Convergence เพื่อให้ระบบเครือข่ายบรรจบ (Converge) ได้อย่างถูกต้องและรวดเร็ว เหมาะสำหรับการเรียนรู้ การทดสอบ และเกมจำลอง 3D โดยไม่ใช่ Production-Grade Kernel STP Stack

---

## 1. STP คืออะไร (What is Spanning Tree Protocol)
Spanning Tree Protocol (STP) เป็นโปรโตคอลการทำงานบน Layer 2 (Data Link Layer) ออกแบบโดย Radia Perlman และกำหนดเป็นมาตรฐานสากลใน IEEE 802.1D หน้าที่หลักคือ:
- ตรวจสอบโครงสร้างเครือข่ายสวิตช์ (Switch Topology) ที่มีการต่อสายแบบสำรอง (Redundant Links)
- ป้องกันปัญหา **Layer 2 Loop**, **Broadcast Storms**, และ **MAC Table Instability**
- บล็อก (Block) พอร์ตที่ซ้ำซ้อนเพื่อสร้างโครงสร้างแบบต้นไม้ (Loop-Free Spanning Tree Topology)
- เมื่อเกิดเหตุการณ์สายสัญญาณขาด (Link Failure) STP จะคำนวณเส้นทางใหม่โดยอัตโนมัติและเปิดพอร์ตสำรองให้กลับมาส่งข้อมูลได้

---

## 2. Bridge ID (BID)
สวิตช์แต่ละตัวจะมีตัวระบุเฉพาะเรียกว่า **Bridge ID** ประกอบด้วย 2 ส่วนหลัก:
$$\text{Bridge ID} = \text{Bridge Priority} + \text{MAC Address}$$

- **Bridge Priority**: ค่าลำดับความสำคัญช่วงตัวเลข $0 - 65535$ (Cisco ค่าเริ่มต้นคือ `32768`) ปรับแต่งได้ตามค่าขั้นบันได
- **MAC Address**: หมายเลขทางกายภาพเฉพาะตัวของสวิตช์ เช่น `00:11:22:33:44:01`
- **การเปรียบเทียบ**: ระบบจะเปรียบเทียบค่า **Priority ต่ำสุดก่อน** หากเท่ากันจึงใช้ **MAC Address ต่ำสุด** เป็นตัวตัดสิน (Tie-breaker)

---

## 3. Root Bridge
สวิตช์ที่เป็นจุดศูนย์กลางของต้นไม้ Spanning Tree ในเครือข่าย Layer 2:
- **การเลือกตั้ง (Election)**: สวิตช์ที่มีค่า **Bridge ID ต่ำที่สุด** ในกลุ่มเครือข่ายสวิตช์ที่เชื่อมต่อกันจะได้รับการเลือกเป็น Root Bridge
- **คุณลักษณะพิเศษ**:
  - บน Root Bridge ค่า `Root Path Cost = 0`
  - ทุกพอร์ตบน Root Bridge ที่เปิดใช้งานและเชื่อมต่ออยู่ จะได้รับบทบาทเป็น **Designated Port** เสมอ
  - ทุกพอร์ตบน Root Bridge จะอยู่ในสถานะ **Forwarding** เสมอ (ไม่มีพอร์ตใดถูกบล็อก)

---

## 4. Root Port (RP)
สำหรับสวิตช์ทุกตัวที่ไม่ใช่ Root Bridge (Non-Root Bridge) จะต้องเลือก **Root Port 1 พอร์ต**:
- คือพอร์ตที่มีเส้นทางที่ดีที่สุด (ค่า Cost ต่ำที่สุด) กลับไปยัง Root Bridge
- **ลำดับเกณฑ์การตัดสิน (Tie-Breaking Order)**:
  1. ค่า **Root Path Cost** ต่ำสุด
  2. ค่า **Sender Bridge ID** (Priority + MAC ของสวิตช์เพื่อนบ้าน) ต่ำสุด
  3. ค่า **Sender Port ID** (หมายเลขพอร์ตของเพื่อนบ้าน) ต่ำสุด
  4. ค่า **Local Port ID** ต่ำสุด
- Root Port จะอยู่ในสถานะ **Forwarding** เสมอ

---

## 5. Designated Port (DP)
ในแต่ละส่วนของเครือข่าย (Segment / Link) ระหว่างสวิตช์ 2 ตัว จะต้องมี **Designated Port 1 พอร์ต**:
- ทำหน้าที่ส่งต่อข้อมูล (Forwarding) บน Segment นั้น
- สวิตช์ที่อยู่ใกล้ Root Bridge มากกว่า (Root Path Cost ต่ำกว่า) จะได้รับเลือกเป็น Designated Bridge บน Segment นั้น
- หากค่า Cost เท่ากัน สวิตช์ที่มี Bridge ID ต่ำกว่าจะเป็นผู้ชนะ
- พอร์ตบนสวิตช์ที่ชนะจะได้รับบทบาทเป็น **Designated Port** (สถานะ: **Forwarding**)
- พอร์ตที่เชื่อมต่อไปยัง Host / PC / Server / Router (Edge Ports) จะได้รับบทบาทเป็น **Designated Port** เสมอ

---

## 6. Blocking Port (Alternate Port)
พอร์ตที่ไม่ได้ถูกเลือกเป็น Root Port หรือ Designated Port บน Segment นั้น:
- ได้รับบทบาทเป็น **Alternate Port (Role: Alternate)**
- ได้รับสถานะเป็น **Blocking (State: Blocking)**
- **พฤติกรรมของ Blocking Port**:
  - **ไม่ส่งต่อ (Drop)** เฟรมข้อมูลทั่วไป (Data Frame)
  - **ไม่บันทึก (No Learn)** Source MAC ลงใน MAC Address Table
  - **ไม่ส่งเฟรมออก** ทางพอร์ตนี้ (ทั้ง Unicast, Multicast, และ Broadcast)
  - ป้องกันไม่ให้เกิดสัญญาณวนลูปในระดับกายภาพ

---

## 7. Root Path Cost
ต้นทุนของเส้นทางในการเดินทางจากสวิตช์กลับไปยัง Root Bridge:
- ตามมาตรฐาน IEEE 802.1D ความเร็วพอร์ต GigabitEthernet (1 Gbps / 1000 Mbps) มีค่าเริ่มต้นคือ **4**
- สวิตช์สะสมค่า Cost จากพอร์ตขาเข้า: $\text{Total Cost} = \text{Neighbor Root Path Cost} + \text{Local Port Cost}$

---

## 8. BPDU (Bridge Protocol Data Unit)
ในสถาปัตยกรรมการจำลองนี้ STP ใช้วิธีคำนวณ Spanning Tree Topology แบบครบวงจร:
- แลกเปลี่ยนข้อมูล Root Bridge ID, Path Cost, และ Sender Bridge ID
- ทำงานแยกขาดจาก Normal Data Traffic
- ไม่ถูกรบกวนโดยเฟรมข้อมูลของผู้ใช้

---

## 9. Loop Prevention
ตัวอย่าง Topology รูปสามเหลี่ยม:
```text
          SW1 (Root Bridge, Priority 24576)
         /   \
        /     \
      SW2-----SW3 (Priority 32768, MAC สูงกว่า SW2)
             X
         (Blocking)
```
1. SW1 มี Priority 24576 ได้รับเลือกเป็น Root Bridge
2. SW2 และ SW3 มีพอร์ตชี้ไปหา SW1 เป็น Root Port (Forwarding)
3. สายเคเบิลระหว่าง SW2 และ SW3:
   - SW2 มี Bridge ID ต่ำกว่า SW3 -> SW2 เป็น Designated Bridge
   - พอร์ตฝั่ง SW2 เป็น Designated Port (Forwarding)
   - พอร์ตฝั่ง SW3 กลายเป็น **Alternate Port (Blocking)**
4. เมื่อมี Broadcast (เช่น ARP Request) ส่งเข้ามา:
   - เฟรมจะถูกกระจายจาก SW1 ไปยัง SW2 และ SW3
   - แต่ลิงก์ระหว่าง SW2 และ SW3 ถูกตัดการส่งต่อที่พอร์ต Blocking ของ SW3
   - **ไม่เกิด Broadcast Storm และการส่งต่อสิ้นสุดลงอย่างสมบูรณ์**

---

## 10. Link Failure & STP Recalculation
เมื่อสายสัญญาณที่ใช้งานอยู่ขาดลง (เช่น ปิดพอร์ตหรือถอดสาย SW1 <-> SW2):
1. สวิตช์ตรวจพบการเปลี่ยนแปลงของสถานะพอร์ต (`_stp_dirty = True`)
2. STP คำนวณโครงสร้างเครือข่ายใหม่ทันที (Recalculation):
   - พอร์ต SW3 <-> SW2 ที่เคยถูกบล็อกจะเปลี่ยนสถานะจาก **Blocking -> Forwarding**
   - พอร์ตบน SW2 กลายเป็น Root Port เชื่อมผ่าน SW3 ไปยัง SW1
   - การเชื่อมต่อฟื้นคืนกลับมาโดยอัตโนมัติ (Automatic Failover)

---

## 11. VLAN Interaction
STP ในเวอร์ชันนี้ทำงานควบคู่กับระบบ VLAN ของ Switch อย่างรัดกุม:
- **STP Loop Prevention**: บล็อกพอร์ตที่เป็นวงวนลูปบนระดับ Physical/Trunk Link
- **VLAN Isolation**: ตรวจสอบ Access VLAN และ Trunk Allowed VLANs บนทุกพอร์ต
- ทราฟฟิกบน VLAN 10 จะไม่รั่วไหลไปยัง VLAN 20 แม้จะมี STP คอยดูแลลูปอยู่

---

## 12. CLI (Command Line Interface)
คำสั่งตรวจสอบสถานะ STP สไตล์ Cisco IOS:

### คำสั่ง `show spanning-tree`
```text
Switch# show spanning-tree
VLAN0001
  Spanning tree enabled protocol ieee
  Root ID    Priority    24576
             Address     0011.2233.4401
             This bridge is the root

  Bridge ID  Priority    24576
             Address     0011.2233.4401
             Hello Time   2 sec  Max Age 20 sec  Forward Delay 15 sec

Interface   Role          State         Cost    Type
------------------------------------------------------------
g0/1        Designated    Forwarding    4       P2p
g0/2        Designated    Forwarding    4       P2p
g0/3        Designated    Forwarding    4       Edge
```

### คำสั่งปรับแต่ง Priority
```text
Switch(config)# spanning-tree vlan 1 priority 4096
```

---

## 13. Simulator Limitations
1. **Convergence Timer**: ระบบใช้การคำนวณและปรับสถานะพอร์ตทันที (Instant Deterministic Convergence) เพื่อให้การทดสอบและการเล่นเกมจำลอง 3D ลื่นไหล ไม่ต้องรอเวลา Forward Delay 15 วินาทีของฮาร์ดแวร์จริง
2. **Protocol Standard**: จำลองตามพื้นฐาน Classic STP (IEEE 802.1D) ยังไม่ได้แยกอินสแตนซ์เป็น PVST+ (Per-VLAN Spanning Tree) หรือ RSTP (802.1w)
