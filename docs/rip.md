# RIPv2 Dynamic Routing (Routing Information Protocol version 2)

## 1. Overview & Architecture

Phase 3.9 introduces deterministic, standards-compliant **Routing Information Protocol version 2 (RIPv2)** to the Network Simulator.

RIPv2 is an Interior Gateway Protocol (IGP) based on the **Bellman-Ford distance-vector routing algorithm**. It allows Layer 3 Routers to automatically discover neighbors, exchange IPv4 routing updates, compute shortest path metrics, dynamically populate routing tables, and adapt to network topological changes (link drops, recoveries, and interface reconfiguration) without manual static routing.

```
+-------------------------------------------------------------------------------+
|                                Layer 3 Router                                 |
|                                                                               |
|  +---------------------+                       +---------------------------+  |
|  |     Cisco IOS       |                       |        RIPProcess         |  |
|  |     Command CLI     |                       |                           |  |
|  |                     |                       |  - enabled: bool          |  |
|  |  router rip         |  Configures / Queries |  - version: 2             |  |
|  |  version 2          | --------------------> |  - networks: set          |  |
|  |  network <net>      |                       |  - neighbors: dict        |  |
|  |  show ip route      |                       |  - routes: dict           |  |
|  |  show ip rip        |                       +-------------+-------------+  |
|  +---------------------+                                     |                |
|                                                              |                |
|  +-----------------------------------------------------------v-------------+  |
|  |                           Routing Table Lookup                          |  |
|  |                                                                         |  |
|  |   1. Longest Prefix Match (LPM: /32 > /24 > /16 > /0)                   |  |
|  |   2. Administrative Distance: Connected (0) < Static (1) < RIP (120)    |  |
|  |   3. Metric (Hop Count: 1 to 15, 16 = Unreachable)                      |  |
|  +-----------------------------------------------------------+-------------+  |
|                                                              |                |
|  +-----------------------------------------------------------v-------------+  |
|  |                      PacketEngine Forwarding Pipeline                   |  |
|  |  - ARP Resolution -> L3 Hop -> TTL Decrement -> ACL -> NAT -> Firewall  |  |
+--+-------------------------------------------------------------------------+--+
```

---

## 2. Core RIPv2 Specifications & Timers

| Parameter | Standard / RFC 2453 | Simulator Value | Description |
| :--- | :--- | :--- | :--- |
| **Protocol Type** | Distance-Vector IGP | Distance-Vector IGP | Bellman-Ford shortest hop metric |
| **Transport / Multicast** | UDP Port 520 / 224.0.0.9 | Direct L2/L3 Frame updates | Simulated deterministically across physical and VLAN links |
| **Metric** | Hop Count (1–15) | Hop Count (1–15) | Number of router hops to destination |
| **Metric of Infinity** | 16 | 16 | Route considered unreachable and poisoned |
| **Administrative Distance** | 120 | 120 | Priority rank: Connected (0) < Static (1) < RIP (120) |
| **Update Timer** | 30 seconds | 30s (simulated) | Periodic routing table advertisements |
| **Invalid / Timeout Timer** | 180 seconds | 180s (simulated) | Time before a missing route is marked unreachable |
| **Flush Timer** | 240 seconds | 240s (simulated) | Time before an unreachable route is expunged |

---

## 3. Neighbor Discovery & Update Propagation

### 3.1 Network Participation
When RIP is enabled on a router via `router rip`, interfaces participate in RIP if their configured IPv4 address falls within any configured `network <prefix>` statement:
- Physical interfaces (`g0/0`, `g0/1`, etc.)
- 802.1Q VLAN Subinterfaces (`g0/0.10`, `g0/0.20`, etc.)

Only active, non-shutdown interfaces with an active link (`is_link_up == True`) participate in neighbor discovery and route advertisement.

### 3.2 Neighbor Discovery Over Cabled Links
Routers discover RIP neighbors through two primary topologies:
1. **Direct Cable Link**: Two routers connected directly via a physical cable on matching subnets.
2. **Layer 2 Switch & VLAN Access/Trunking**: Routers connected through one or more L2 switches, where ports belong to the same VLAN or 802.1Q trunk.

### 3.3 Convergence Engine (`converge_all_rip`)
In an interactive simulator where real-time socket loops are not used, convergence is driven by an iterative Bellman-Ford propagation engine (`converge_all_rip(max_rounds=6)`):
1. **Neighbor Discovery**: Each RIP router refreshes its neighbor adjacency table against current link states.
2. **Update Generation & Filtering**: Each router builds serialized route payloads for its active neighbors subject to **Split Horizon** and **Route Poisoning**.
3. **Route Ingestion & Metric Calculation**: Receiving routers calculate new metrics (`metric + 1`), evaluate poison markers (metric = 16), and update their routing tables.
4. **Convergence Detection**: Iterations repeat until no routing table changes occur across the entire topology (steady-state) or `max_rounds` is reached.
5. **Event-Driven Hooks**: Convergence is automatically triggered upon CLI commands (`router rip`, `network`, `no router rip`), interface state transitions (`shutdown`, `no shutdown`), cable connections/disconnections, and before `simulate_ping` / `simulate_traceroute` in `PacketEngine`.

---

## 4. Loop Prevention: Split Horizon & Route Poisoning

Distance-vector routing protocols are prone to routing loops and "counting to infinity" unless loop prevention mechanisms are strictly enforced.

```
        +----------+              +----------+              +----------+
        | Router-1 | <=========>  | Router-2 | <=========>  | Router-3 |
        +----------+  10.0.0.0/30 +----------+  10.0.1.0/30 +----------+
       192.168.1.0/24                                      192.168.3.0/24
```

### 4.1 Split Horizon
- **Rule**: A router never advertises a route out of the interface through which that route was learned, nor advertises a route back to the neighbor that originated/relayed it.
- **Example**: Router-2 learns `192.168.1.0/24` from Router-1 via interface `g0/0`. When Router-2 sends its periodic update to Router-1 out of `g0/0`, `192.168.1.0/24` is suppressed. Router-2 *does* advertise `192.168.1.0/24` out of `g0/1` to Router-3.

### 4.2 Route Poisoning & Poison Reverse
- **Rule**: When a link fails or a neighbor becomes unreachable, the router immediately sets the metric for routes traversing that link to **16 (Infinity / Unreachable)**.
- **Propagation**: The poisoned route (`metric = 16`) is advertised downstream. Upon receiving metric 16 from their designated next-hop, downstream routers immediately invalidate the route and flush it, rather than slowly counting to infinity.

---

## 5. Route Precedence & Lookup Pipeline

When a router evaluates an egress packet destination IP, it resolves the forwarding path using the following strict priority:

1. **Longest Prefix Match (LPM)**:
   A more specific route always wins regardless of Administrative Distance or metric.
   - `/32` Host route > `/28` Subnet > `/24` Class C > `/16` Class B > `/0` Default route.
2. **Administrative Distance (AD)**:
   When two routes have identical destination networks and prefix lengths, the route with the lowest Administrative Distance is preferred:
   - **Connected (`C`)**: `AD = 0`
   - **Static (`S`)**: `AD = 1`
   - **RIPv2 (`R`)**: `AD = 120`
3. **Metric (Hop Count)**:
   For routes of the same protocol and prefix length, the route with the lowest metric (fewest hops) is installed.

### Static Route Override & Fallback
- If a Static route and a RIP route exist for the same network (e.g. `192.168.20.0/24`), the Static route (`AD=1`) is active.
- If the administrator removes the static route (`no ip route 192.168.20.0 255.255.255.0 ...`), the RIP route (`AD=120`) immediately takes over forwarding without packet loss.

---

## 6. Cisco IOS CLI Reference

### 6.1 Configuration Commands

#### Global Configuration
```ios
Router(config)# router rip
Router(config-router)#
```
Enters RIP router configuration submode.

```ios
Router(config)# no router rip
```
Disables the RIP routing process, cancels advertisements, and removes all learned dynamic `R` routes from the routing table.

#### Router Submode (`config-router`)
```ios
Router(config-router)# version 2
```
Specifies RIP version 2.

```ios
Router(config-router)# network <network-address>
```
Enables RIP on all interfaces whose IP address matches the specified network.

```ios
Router(config-router)# no network <network-address>
```
Removes the specified network from the RIP process.

```ios
Router(config-router)# exit
Router(config-router)# end
```
Exits router configuration submode back to global configuration or privileged EXEC mode.

### 6.2 Verification Commands

#### `show ip route`
Displays the full IP routing table including route codes (`C`, `S`, `R`).
```ios
Router# show ip route
Codes: C - connected, S - static, R - RIP, * - candidate default

Gateway of last resort is not set

      10.0.0.0/30 is subnetted, 1 subnets
C        10.0.0.0 is directly connected, GigabitEthernet0/0
R     192.168.20.0/24 [120/2] via 10.0.0.2, GigabitEthernet0/0
R     192.168.30.0/24 [120/3] via 10.0.0.2, GigabitEthernet0/0
```

#### `show ip rip`
Displays RIP process status, configuration parameters, and learned routes.
```ios
Router# show ip rip
Routing Protocol is "rip"
  Sending updates every 30 seconds, next due in 0 seconds
  Invalid after 180 seconds, hold down 180, flushed after 240
  Outgoing update filter list for all interfaces is not set
  Incoming update filter list for all interfaces is not set
  Default version control: send version 2, receive version 2
    Interface             Send  Recv  Triggered RIP  Key-chain
    GigabitEthernet0/0    2     2
  Routing for Networks:
    10.0.0.0
    192.168.10.0
  Routing Information Sources:
    Gateway         Distance      Last Update
    10.0.0.2             120      00:00:05
  Distance: (default is 120)
```

#### `show ip protocols`
Displays active routing protocols, version, networks routed, and neighbor gateways.
```ios
Router# show ip protocols
*** IP Routing is NSF aware ***

Routing Protocol is "rip"
  Outgoing update filter list for all interfaces is not set
  Incoming update filter list for all interfaces is not set
  Sending updates every 30 seconds, next due in 0 seconds
  Invalid after 180 seconds, hold down 180, flushed after 240
  Default version control: send version 2, receive version 2
  Routing for Networks:
    10.0.0.0
    192.168.10.0
  Routing Information Sources:
    Gateway         Distance      Last Update
    10.0.0.2             120      00:00:05
  Distance: (default is 120)
```

#### `show running-config`
Reflects configured `router rip` blocks and `network` statements.
```ios
Router# show running-config
...
router rip
 version 2
 network 10.0.0.0
 network 192.168.10.0
!
```

---

## 7. PacketEngine Integration

RIPv2 dynamic routes integrate natively into `PacketEngine` with zero bypasses:
- **L3 Hop Tracking & Forwarding**: Forward and return ICMP packets correctly traverse intermediate RIP routers.
- **TTL Decrement**: Each RIP router decrements IP TTL by 1; packets expiring at TTL=0 generate ICMP Time Exceeded (`*` in traceroute).
- **Next-Hop ARP Resolution**: RIP next-hop IP addresses are resolved via ARP on the egress interface.
- **VLAN / 802.1Q Subinterfaces**: Inter-VLAN routing across RIP operates smoothly with 802.1Q tags preserved over trunks.
- **ACL, NAT & Firewall**: Egress and ingress ACLs, NAT overload/pools, and stateful inspection firewall rules are evaluated on all RIP-routed packets.
- **DHCP Relay & Forwarding**: DHCP DISCOVER/OFFER/REQUEST/ACK packets pass between subnets across RIP-routed links.

---

## 8. Limitations & Future Scope

- **RIPv2 Only**: RIPv1 (classful broadcast) and RIPng (IPv6) are deliberately omitted per project specification.
- **Hop Count Bound**: Maximum valid metric is 15 hops; topologies exceeding 15 hops are marked unreachable (metric 16).
- **No ECMP (Equal-Cost Multi-Path)**: When multiple equal-cost paths exist, the first received valid route is preserved.
- **Authentication**: Plaintext or MD5 RIP authentication is currently disabled.
