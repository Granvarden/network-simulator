# OSPFv2 Dynamic Routing (Open Shortest Path First version 2)

## 1. Overview & Architecture

Phase 4 introduces a complete, standards-compliant **OSPFv2 (Open Shortest Path First version 2)** engine for IPv4 Single Area (Area 0) to the Network Simulator.

OSPF is an **Interior Gateway Protocol (IGP)** based on **Link-State technology** (RFC 2328). Unlike distance-vector protocols such as RIP (which rely on "routing by rumor" and hop counts), each OSPF router:
1. Discovers adjacent neighbors using the **Hello Protocol**.
2. Establishes bidirectional adjacencies transitioning through a strict finite state machine: `DOWN -> INIT -> 2-WAY -> FULL`.
3. Originates and floods **Type 1 Router-LSAs** (Link-State Advertisements) with sequence numbers (`0x80000001+`) to synchronize a local **Link-State Database (LSDB)** across Area 0.
4. Independently runs **Dijkstra's Shortest Path First (SPF)** algorithm over its synchronized LSDB to calculate the shortest path tree rooted at itself based on cumulative **Interface Cost**.
5. Installs the best paths as dynamic `O` routes with **Administrative Distance 110** into the routing table.

```
+-------------------------------------------------------------------------------+
|                                Layer 3 Router                                 |
|                                                                               |
|  +---------------------+                       +---------------------------+  |
|  |     Cisco IOS       |                       |        OSPFProcess        |  |
|  |     Command CLI     |                       |                           |  |
|  |                     |  Configures / Queries |  - process_id: int        |  |
|  |  router ospf <id>   | --------------------> |  - router_id: str         |  |
|  |  router-id <ip>     |                       |  - area: 0                |  |
|  |  network <n> <w> a0 |                       |  - neighbors: dict        |  |
|  |  ip ospf cost <val> |                       |  - lsdb: Router-LSAs      |  |
|  |  show ip ospf ...   |                       |  - routes: dict           |  |
|  +---------------------+                       +-------------+-------------+  |
|                                                              |                |
|  +-----------------------------------------------------------v-------------+  |
|  |                      Link-State Engine & Convergence                    |  |
|  |                                                                         |  |
|  |   1. Hello Protocol: Neighbor Discovery (DOWN -> INIT -> 2-WAY -> FULL) |  |
|  |   2. LSA Origination: Router-LSA with Seq# (0x80000001+) & P2P/Stub     |  |
|  |   3. LSA Flooding: LSDB Synchronization across Area 0                   |  |
|  |   4. Dijkstra's Algorithm (SPF): Shortest Path Tree Calculation         |  |
|  +-----------------------------------------------------------+-------------+  |
|                                                              |                |
|  +-----------------------------------------------------------v-------------+  |
|  |                           Routing Table Lookup                          |  |
|  |                                                                         |  |
|  |   1. Longest Prefix Match (LPM: /32 > /24 > /16 > /0)                   |  |
|  |   2. Administrative Distance: Connected (0) < Static (1) < OSPF (110)   |  |
|  |      < RIP (120)                                                        |  |
|  |   3. Cumulative Path Cost (Metric)                                      |  |
|  +-----------------------------------------------------------+-------------+  |
|                                                              |                |
|  +-----------------------------------------------------------v-------------+  |
|  |                      PacketEngine Forwarding Pipeline                   |  |
|  |  - ARP Resolution -> L3 Hop -> TTL Decrement -> ACL -> NAT -> Firewall  |  |
+--+-------------------------------------------------------------------------+--+
```

---

## 2. Core Protocol Specifications & Comparison with RIPv2

| Parameter | OSPFv2 (RFC 2328) | RIPv2 (RFC 2453) | Description in Simulator |
| :--- | :--- | :--- | :--- |
| **Protocol Type** | Link-State IGP | Distance-Vector IGP | True LSDB graph vs hop count |
| **Algorithm** | Dijkstra Shortest Path First (SPF) | Bellman-Ford | Local tree computation vs vector updates |
| **Area Hierarchy** | Single Area (Area 0 Backbone) | Flat | Backbone Area 0 |
| **Metric** | Interface Cost (1 to 65535) | Hop Count (1 to 15) | Cumulative link cost |
| **Metric of Infinity** | Unreachable ($> 65535$ or disconnected) | 16 | Node disconnection in LSDB |
| **Administrative Distance**| **110** | **120** | OSPF preferred over RIP |
| **Convergence** | Event-Driven LSDB Flood & SPF | Periodic / Triggered | Deterministic event-driven convergence |
| **Loop Prevention** | Dijkstra DAG (No loops possible) | Split Horizon / Poison Reverse | Inherently loop-free SPF tree |
| **Subinterfaces** | Supported (802.1Q VLANs) | Supported (802.1Q VLANs) | Inter-VLAN trunking |

---

## 3. Neighbor Discovery & Adjacency State Machine

Router interfaces participate in OSPF Area 0 if their configured IPv4 address matches a configured `network <network> <wildcard-mask> area 0` statement and the interface is administratively UP with an active link (`is_link_up == True`).

### 3.1 Adjacency States
```
       +--------------+
       |     DOWN     | No Hello received from neighbor
       +-------+------+
               |
               | Hello received with neighbor Router ID
               v
       +-------+------+
       |     INIT     | Neighbor seen, but our own ID not in neighbor's list
       +-------+------+
               |
               | Bidirectional Hello confirmed
               v
       +-------+------+
       |    2-WAY     | Mutual communication established
       +-------+------+
               |
               | LSDB exchange & synchronization complete
               v
       +-------+------+
       |     FULL     | Full adjacency formed; links included in Router-LSA
       +--------------+
```

1. **DOWN**: Initial state; no Hello packet received from the peer.
2. **INIT**: Hello packet received from the peer, but the local router's ID is not yet listed in the peer's seen neighbors list.
3. **2-WAY**: Bi-directional communication confirmed; each router sees its own ID in the peer's Hello packet.
4. **FULL**: LSDB synchronization complete; routers are fully adjacent and describe this link in their respective Router-LSAs.

---

## 4. Link-State Database (LSDB) & Router-LSA

Every OSPF router maintains its own local **Link-State Database (`lsdb`)**, storing an LSA from every router in Area 0.

### 4.1 Type 1 Router-LSA Attributes
- **Advertising Router (`adv_router`)**: 32-bit Router ID of originating router (e.g. `1.1.1.1`).
- **LSA Type**: `Router-LSA` (Type 1).
- **Area**: `0`.
- **Sequence Number (`sequence`)**: 32-bit signed integer starting at `0x80000001`. Each time the router re-originates its LSA (due to topology change, interface cost update, or link failure), `sequence` is incremented by 1.
- **Age (`age`)**: Age in seconds.
- **Links (`links`)**:
  - **Point-to-Point Link**: Generated for each neighbor in `FULL` state:
    `{"type": "point-to-point", "link_id": neighbor_router_id, "link_data": local_interface_ip, "cost": interface_cost, "neighbor_ip": peer_interface_ip}`
  - **Stub Link**: Generated for each active directly connected subnet on participating interfaces:
    `{"type": "stub", "network": subnet_network, "mask": subnet_mask, "cost": interface_cost}`

### 4.2 LSA Flooding & Loop-Free Synchronization
When an LSA is originated or modified:
1. The originating router sends its LSA to all adjacent neighbors in `FULL` state.
2. The receiving neighbor inspects the LSA:
   - If the LSA is not in its LSDB or the received LSA has a higher `sequence` number, it updates its LSDB and forwards the LSA out all other FULL interfaces.
   - If the received LSA has an equal or lower `sequence` number, it is dropped.
3. Flooding terminates deterministically without infinite loops.

---

## 5. Dijkstra's Shortest Path First (SPF) Algorithm

Once the LSDB is synchronized across all routers, each router independently executes Dijkstra's SPF algorithm rooted at its own Router ID.

### 5.1 Algorithm Flow
1. **Graph Construction**:
   - Vertices: All `Router IDs` present in the local LSDB.
   - Directed Edges: Formed by `point-to-point` links with associated interface costs.
2. **Shortest Path Tree (SPT)**:
   - `dist[root] = 0`; `dist[v] = infinity` for all other vertices.
   - Using a priority queue / unvisited set, extract vertex $u$ with minimum distance.
   - For each outgoing point-to-point link $(u, v)$ with cost $w$:
     $$\text{alt} = dist[u] + w$$
     $$\text{If } \text{alt} < dist[v]: dist[v] = \text{alt}, \quad \text{first\_hop}[v] = \dots$$
3. **Route Construction**:
   - For each router $R$ reachable in the SPT ($dist[R] < \infty$):
     - For each `stub` network $(N, M)$ advertised by $R$ with stub cost $C_{\text{stub}}$:
       $$\text{Total Cost} = dist[R] + C_{\text{stub}}$$
       - If $R == \text{root}$: directly connected; handled by Connected route (`C`).
       - If $R \ne \text{root}$: install dynamic OSPF route into routing table:
         ```python
         {
             "network": N,
             "mask": M,
             "next_hop": first_hop[R].next_hop_ip,
             "interface": first_hop[R].outgoing_interface,
             "type": "O",
             "admin_distance": 110,
             "metric": Total_Cost,
             "cost": Total_Cost
         }
         ```

---

## 6. Route Precedence & Failover Hierarchy

Routing decisions in `Router.lookup_route(dest_ip)` follow strict Cisco-compliant precedence:

1. **Longest Prefix Match (LPM)**:
   More specific masks always win regardless of protocol (`/32 > /28 > /24 > /16 > /0`).
2. **Administrative Distance (AD)**:
   $$\text{Connected (0)} < \text{Static (1)} < \text{OSPF (110)} < \text{RIP (120)}$$
   - **Static vs OSPF**: If a Static route and an OSPF route exist for the same network, Static (`AD=1`) is active.
   - **Static Removal Fallback**: Removing the static route (`no ip route ...`) causes the OSPF route (`AD=110`) to immediately take over without loss.
   - **OSPF vs RIP**: If both OSPF and RIP advertise the same network, OSPF (`AD=110`) wins over RIP (`AD=120`).
   - **OSPF Removal Fallback**: Disabling OSPF causes RIP to become active.
3. **Metric (Cost)**:
   Among equal-prefix OSPF routes, the route with the lowest cumulative cost wins.

---

## 7. Topology Change, Failure & Recovery

```
        +----------+              +----------+              +----------+
        | Router-1 | <=========>  | Router-2 | <=========>  | Router-3 |
        +----------+  10.0.12.0/30+----------+  10.0.23.0/30+----------+
       192.168.10.0/24                                      192.168.30.0/24
```

### 7.1 Link Failure (Disconnect or Interface Shutdown)
1. Cable disconnection or `shutdown` causes interface `is_link_up` to become `False`.
2. Router neighbor discovery detects loss of peer; adjacency drops to `DOWN`.
3. The affected routers immediately originate a new Router-LSA with an incremented sequence number (`seq += 1`) that omits the failed link.
4. The updated LSA is flooded to all surviving neighbors.
5. Routers update their LSDB, re-run Dijkstra SPF, and remove the unreachable route from their routing tables.

### 7.2 Link Recovery (Reconnect or Interface No Shutdown)
1. Cable reconnection or `no shutdown` restores link state to `UP`.
2. OSPF Hello exchange discovers peer and transitions adjacency: `DOWN -> INIT -> 2-WAY -> FULL`.
3. Routers originate a new Router-LSA (`seq += 1`) containing the restored link.
4. The LSA is flooded, LSDB synchronizes, Dijkstra SPF recalculates, and the route is cleanly restored.

---

## 8. Cisco IOS CLI Reference

### 8.1 Configuration Commands

#### Global Configuration Mode
```ios
Router(config)# router ospf <process-id>
Router(config-router)#
```
Enters OSPF router configuration submode.

```ios
Router(config)# no router ospf <process-id>
```
Disables OSPF process, terminates adjacencies, clears LSDB, and removes all `O` routes.

#### Router Configuration Submode (`config-router`)
```ios
Router(config-router)# router-id <ip-address>
```
Sets an explicit 32-bit OSPF Router ID.

```ios
Router(config-router)# network <network-address> <wildcard-mask> area 0
```
Enables OSPF on any interface whose IP matches the network/wildcard statement in Area 0.

```ios
Router(config-router)# no network <network-address> <wildcard-mask> area 0
```
Removes network statement from OSPF process.

#### Interface & Subinterface Configuration Submodes (`config-if` / `config-subif`)
```ios
Router(config-if)# ip ospf cost <1-65535>
```
Sets explicit interface metric cost (default is 1).

```ios
Router(config-if)# no ip ospf cost
```
Resets interface cost to default (1).

---

### 8.2 Verification Commands

#### `show ip ospf`
```ios
Router# show ip ospf
 Routing Process "ospf 1" with ID 192.168.10.1
 Supports only single TOS(TOS0) routes
 Supports opaque LSA
 SPF schedule delay 5 secs, Hold time between two SPFs 10 secs
 Number of DCbitless external LSA 0
 Number of DoNotAge external LSA 0
 Number of areas in this router is 1. 1 normal 0 stub 0 nssa
    Area BACKBONE(0)
        Number of interfaces in this area is 2
        Interfaces: GigabitEthernet0/0 GigabitEthernet0/1
        Active neighbors: 1
        SPF algorithm executed 3 times
```

#### `show ip ospf neighbor`
```ios
Router# show ip ospf neighbor
Neighbor ID     Pri   State           Dead Time   Address         Interface
--------------------------------------------------------------------------------
2.2.2.2         1     FULL            00:00:35    10.0.12.2       GigabitEthernet0/0
```

#### `show ip ospf database`
```ios
Router# show ip ospf database
            OSPF Router with ID (1.1.1.1) (Process ID 1)

                Router Link States (Area 0)

Link ID         ADV Router      Age     Seq#          Checksum  Link count
----------------------------------------------------------------------------
1.1.1.1         1.1.1.1         1       0x80000003    0x0042    2
2.2.2.2         2.2.2.2         1       0x80000003    0x0042    3
3.3.3.3         3.3.3.3         1       0x80000003    0x0042    2
```

#### `show ip route`
```ios
Router# show ip route
Codes: C - connected, S - static, R - RIP, O - OSPF, * - candidate default
Gateway of last resort is not set

C    10.0.12.0/30 is directly connected, GigabitEthernet0/0
C    192.168.10.0/24 is directly connected, GigabitEthernet0/1
O    10.0.23.0/30 [110/2] via 10.0.12.2
O    192.168.30.0/24 [110/3] via 10.0.12.2
```

#### `show ip protocols`
```ios
Router# show ip protocols
*** IP Routing is NSF aware ***

Routing Protocol is "ospf 1"
  Outgoing update filter list for all interfaces is not set
  Incoming update filter list for all interfaces is not set
  Router ID 1.1.1.1
  Number of areas in this router is 1. 1 normal 0 stub 0 nssa
  Maximum path: 4
  Routing for Networks:
    10.0.12.0 0.0.0.3 area 0
    192.168.10.0 0.0.0.255 area 0
  Routing Information Sources:
    Gateway         Distance      Last Update
    2.2.2.2              110      00:00:10
  Distance: (default is 110)
```

#### `show running-config`
```ios
Router# show running-config
...
interface GigabitEthernet0/0
 ip address 10.0.12.1 255.255.255.252
 ip ospf cost 10
 no shutdown
!
router ospf 1
 router-id 1.1.1.1
 network 10.0.12.0 0.0.0.3 area 0
 network 192.168.10.0 0.0.0.255 area 0
!
end
```

---

## 9. PacketEngine Forwarding & Subsystems Integration

OSPF routes forward packets through the standard hop-by-hop pipeline without bypasses:
- **L3 Hop & Forwarding**: Packets traverse intermediate OSPF routers in sequence.
- **TTL Decrement**: Each OSPF hop decrements IP TTL by 1; expired packets generate ICMP Time Exceeded (`*` in traceroute).
- **ARP Resolution**: Next-hop IP addresses from OSPF routes are resolved to MAC addresses on local egress interfaces.
- **VLAN / 802.1Q Subinterfaces**: OSPF adjacencies form across 802.1Q subinterfaces (e.g. `g0/0.10`) through switch access/trunk ports.
- **STP Integration**: Ports blocked by Spanning Tree (`Blocking`) prevent OSPF Hello and adjacency formation.
- **DHCP Relay & Client**: DHCP clients acquire addresses and ping destinations across OSPF-routed subnets.
- **Security Policies**: OSPF-routed traffic is subject to ingress/egress Access Lists (`A` status on drop), NAT Overload translation, and Stateful Firewall state tracking.

---

## 10. Limitations & Boundaries (Out of Scope)

- **Single Area 0 Only**: Multi-Area OSPF, Area Border Routers (ABR), and Autonomous System Boundary Routers (ASBR) are not included.
- **IPv4 / OSPFv2 Only**: OSPFv3 and IPv6 are not implemented.
- **LSA Types**: Limited to Type 1 Router-LSA and connected stub networks; Type 2 Network-LSAs (DR/BDR elections), Type 3/4/5 External LSAs, and NSSA are not implemented.
- **No ECMP**: Equal-Cost Multi-Path is not enabled; the first minimum-cost path is installed.
- **No OSPF Authentication**: Plaintext / MD5 cryptographic authentication is omitted.
- **Deterministic Simulation**: OSPF does not use raw background UDP/IP protocol 89 sockets or threads; it executes deterministically upon topology events and CLI operations.
